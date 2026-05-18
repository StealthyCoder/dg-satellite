import atexit
import subprocess

from collections import deque
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from itertools import chain
from netifaces import interfaces, ifaddresses
from socket import socket
from typing import Deque, Dict, Generator, List, Literal, Optional, Tuple, Type, Union


_addr = str
_iface = str
_id = str
_idx = int

IfaceAddrs = Dict[_iface, List[_addr]]
AddrIfaces = Dict[_addr, Tuple[_iface, _idx]]
_TcInstallItem = Union[
    Tuple[Literal["qdisc", "class"], _iface, _id, _id],
    Tuple[Literal["filter"], _iface, _id, _id, _id, _id],
]
TcInstallContext = Deque[_TcInstallItem]


class _TcShaper:
    _iface_addrs: Optional[IfaceAddrs] = None
    _addr_ifaces: Optional[AddrIfaces] = None
    # lifo stacks for install context allowing to properly uninstall later
    _installed_global: TcInstallContext
    _installed_local: ContextVar[TcInstallContext] = ContextVar(
        "tc_shaper_installed_local"
    )

    def __init__(self):
        self._installed_global = deque()

    @property
    def iface_addrs(self) -> IfaceAddrs:
        if self._iface_addrs is None:
            raise RuntimeError(
                "You must call install_default_root_htb before any other method"
            )
        return self._iface_addrs

    def get_iface_by_addr(self, addr: str) -> Tuple[str, int]:
        if self._addr_ifaces is None:
            raise RuntimeError(
                "You must call install_default_root_htb before any other method"
            )
        return self._addr_ifaces.get(addr, ("", 0))

    @contextmanager
    def install_context(self):
        """Create a local install context to capture a series of operations.

        Example usage:
        class SomeClass:
            ctx = None

            def install(self):
                with tc_shaper.install_context() as ctx:
                    self.ctx = ctx
                    # Call some tc_shaper.install_xxx methods here

            def close(self):
                if self.ctx is not None:
                    tc_shaper.uninstall(ctx)
        """
        ctx = deque()
        token = self._installed_local.set(ctx)
        try:
            yield ctx
        finally:
            self._installed_local.reset(token)

    def install_default_root_htb(self, idroot: int = 1, iddef: int = 2):
        """Creates a root classful HTB qdisc on all interfaces.

        It also creates a default unlimited qdisc for regular traffic; here "unlimited" really means
        at most 100gbps rate (which is practically unlimited).  This also sets an sfq class for
        regular traffic which distributes traffic more evenly between clients than the default Linux
        pfifo_fast class; this is quite helpful for testing with multiple connections.

        This method is singleton but not thread-safe - it is a responsibility of a caller to sync.
        """
        if self._iface_addrs is not None:
            # Default HTB qdisc/class set already installed
            return
        iface_addrs, addr_ifaces = self._get_ifaces()

        rid = f"{idroot:x}:"
        cid = f"{idroot:x}:{iddef:x}"
        qid = f"{iddef:x}:"
        for iface in iface_addrs.keys():
            self.install_qdisc(iface, "", rid, f"htb default {iddef:x}")
            self.install_class(iface, rid, cid, "htb rate 100gbps")
            self.install_qdisc(iface, cid, qid, "sfq divisor 2048 perturb 90")

        self._iface_addrs, self._addr_ifaces = iface_addrs, addr_ifaces

    def install_sock_leaf_htb(self, sock: socket, params: str, idroot: int = 1):
        """Creates a HTB class and leaf qdisc with given parameters for a socket.

        This method automatically selects which interfaces are applicable to this socket.
        Usually, that is one interface for client connections; may be multiple in case of a bind.

        It also creates a filter which configures a given class/qdisk to be only applicable to a
        source address/port derived from a socket.

        For applications opening many connections an `install_mark_leaf_htb` is preferred.
        """
        addr, port = sock.getsockname()[:2]
        addr_iface_name, idx = self.get_iface_by_addr(addr)
        install_ifaces = (
            [addr_iface_name] if addr_iface_name else self.iface_addrs.keys()
        )

        pid = f"{idroot:x}:"
        cid = f"{idroot:x}:{port:x}"
        qid = f"{port:x}:"
        fprio = f"{port}"
        for iface in install_ifaces:
            self.install_class(iface, pid, cid, "htb rate 100gbps")
            self.install_qdisc(iface, cid, qid, params)
            # No necessity to match by addr as a port is unique per interface (device).
            # Because of that a priority will also be unique for each filter per device.
            self.install_filter(
                iface,
                pid,
                fprio,
                f"match ip sport {port} 0xffff flowid {cid}",
            )

    def install_mark_leaf_htb(self, mark: int, params: str, idroot: int = 1):
        """Creates a HTB class and leaf qdisc with given parameters and mark.

        This function also creates a filter which configures a given class/qdisk to be only
        applicable to all packets which contains a given netfilter mark.  Consequently, each socket
        that should get into this class must set the same netfilter mark using setsockopt.

        A mark must be between 1 and 0xFFFF as we also use it as a class name.
        """
        if mark < 1 or mark > 0xFFFF:
            raise ValueError(
                f"A mark must be a positive 16-bit unsigned integer: {mark}"
            )
        if mark == idroot:
            raise ValueError(f"A mark must not equal idroot: {mark}")

        pid = f"{idroot:x}:"
        cid = f"{idroot:x}:{mark:x}"
        qid = f"{mark:x}:"
        fprio = f"{mark}"
        for iface in self.iface_addrs.keys():
            self.install_class(iface, pid, cid, "htb rate 100gbps")
            self.install_qdisc(iface, cid, qid, params)
            self.install_filter(
                iface,
                pid,
                fprio,
                f"match mark {mark} 0xffff flowid {cid}",
            )

    def install_qdisc(self, iface: str, pid: str, qid: str, params: str):
        pid_op = f"parent {pid}" if pid else "root"
        self._call_tc(f"qdisc add dev {iface} {pid_op} handle {qid} {params}")
        self._push_installed(("qdisc", iface, pid, qid))

    def install_class(self, iface: str, pid: str, cid: str, params: str):
        self._call_tc(f"class add dev {iface} parent {pid} classid {cid} {params}")
        self._push_installed(("class", iface, pid, cid))

    def install_filter(
        self,
        iface: str,
        pid: str,
        prio: str,
        params: str,
        proto: str = "ip",
        type: str = "u32",
    ):
        # Individual simple filters can only be reliably deleted (without deleting all filters on
        # the same device) if a unique pid/proto/prio/type quadruple was assigned to each filter.
        # Given that pid/proto/type are usually the same in our case, a prio is our only remedy.
        # An alternative would be to build our own filters hash table that is way more complex.
        self._call_tc(
            f"filter add dev {iface} parent {pid} protocol {proto} prio {prio} {type} {params}"
        )
        self._push_installed(("filter", iface, pid, proto, prio, type))

    def uninstall(self, ctx: TcInstallContext):
        """Uninstall all tc objects previously created within a scope of this install context."""
        # Remove everything in reverse order
        for i in self._pop_installed(ctx):
            if i[0] == "qdisc":
                _, iface, pid, qid = i
                pid_op = f"parent {pid}" if pid else "root"
                self._call_tc(f"qdisc del dev {iface} {pid_op} handle {qid}")
            elif i[0] == "class":
                _, iface, pid, cid = i
                self._call_tc(f"class del dev {iface} parent {pid} classid {cid}")
            elif i[0] == "filter":
                _, iface, pid, proto, prio, type = i
                self._call_tc(
                    f"filter del dev {iface} parent {pid} protocol {proto} prio {prio} {type}"
                )
            else:
                assert False, "Unexpected _TcInstallItem value"

    def close(self):
        self.uninstall(self._installed_global)

    def _push_installed(self, i: _TcInstallItem):
        self._installed_global.appendleft(i)
        try:
            ctx = self._installed_local.get()
        except LookupError:
            return
        else:
            ctx.appendleft(i)

    def _pop_installed(
        self, ctx: TcInstallContext
    ) -> Generator[_TcInstallItem, None, None]:
        while len(ctx) > 0:
            i = ctx.popleft()
            if ctx is not self._installed_global:
                # This is why we use popleft/appendleft: remove always starts from left
                try:
                    self._installed_global.remove(i)
                except ValueError:
                    # potential race condition at application shutdown when everything closes
                    continue
            yield i

    @staticmethod
    def _get_ifaces() -> Tuple[IfaceAddrs, AddrIfaces]:
        iface_names = [i for i in interfaces() if i != "lo"]
        iface_addrs = {
            i: [a["addr"] for a in chain(*ifaddresses(i).values())] for i in iface_names
        }
        addr_ifaces = {}
        for iface, addrs in iface_addrs.items():
            for idx, addr in enumerate(addrs):
                addr_ifaces[addr] = (iface, idx + 1)
        return iface_addrs, addr_ifaces

    @staticmethod
    def _call_tc(args: str):
        print(f"run tc {args}")  # handy debug code
        subprocess.run("tc " + args, shell=True, check=True)


tc_shaper = _TcShaper()
atexit.register(tc_shaper.close)


@dataclass
class TcNetemShape:
    # See https://man7.org/linux/man-pages/man8/tc-netem.8.html
    limit: Optional[str] = None  # limit - packets, e.g. 100
    latency: Optional[str] = None  # delay - time, e.g. 500ms
    jitter: Optional[str] = None  # delay - jitter, e.g. 100ms
    jitter_corr: Optional[str] = None  # delay - correlation, e.g. 10
    jitter_dist: Optional[str] = None  # delay - distribution, e.g. normal
    rate: Optional[str] = None  # rate - rate, e.g. 500kbps
    overhead: Optional[str] = None  # rate - packet overhead, e.g. 40
    loss_random: Optional[str] = None  # loss - random - percent, e.g. 10
    loss_bernoulli: Optional[str] = None  # loss - gemodel - p, e.g. 10
    # Other more complex loss parameters can be added later if needed
    corrupt: Optional[str] = None  # loss - percent, e.g. 10
    duplicate: Optional[str] = None  # duplicate - percent, e.g. 10
    reorder: Optional[str] = None  # reorder - percent, e.g. 10
    reorder_gap: Optional[str] = None  # reorder - gap, e.g. 5
    # The man page says that correlation for loss/corrupt/etc behaves badly and is deprecated
    slot_dist: Optional[str] = None  # slot - distribution, e.g. normal
    slot_delay: Optional[str] = None  # slot - delay, e.g. 500us
    slot_jitter: Optional[str] = None  # slot - jitter, e.g. 100us
    slot_packets: Optional[str] = None  # slot - packets, e.g. 10
    slot_bytes: Optional[str] = None  # slot - bytes, e.g. 5000
    # A slot min/max can be easily achieved via distribution, hence not supported

    @classmethod
    def parse(cls, s: Optional[str]) -> Optional["TcNetemShape"]:
        if not s:
            return None
        # format is `netem.latency=500ms:jitter=100ms:rate=10kbps`
        prefix, body = s.split(".", 1)
        if prefix != "netem":
            raise ValueError("Unsupported network shaper")
        if not body:
            raise ValueError("At least one network shaping parameter must be set")
        kw = {k: v for k, v in [p.split("=", 1) for p in body.split(":")]}
        shape = TcNetemShape(**kw)

        # Do some basic validation for dependencies, assuming that a user knows metric units
        if not shape.latency:
            if shape.jitter or shape.jitter_corr or shape.jitter_dist:
                raise ValueError("A jitter can only be set with latency")
        if not shape.jitter:
            if shape.jitter_corr or shape.jitter_dist:
                raise ValueError(
                    "A jitter correlation or distribution can only be set with jitter"
                )
        if not shape.rate and shape.overhead:
            raise ValueError("An overhead can only be set with rate")
        if shape.loss_random and shape.loss_bernoulli:
            raise ValueError("Only random or bernoulli loss can be set but not both")
        if not shape.reorder and shape.reorder_gap:
            raise ValueError("A reorder gap can only be set with reorder")
        if not shape.slot_dist:
            if shape.slot_delay or shape.slot_jitter:
                raise ValueError(
                    "A slot delay or jitter can only be set with slot distribution"
                )
        if shape.slot_dist:
            if not shape.slot_delay or not shape.slot_jitter:
                raise ValueError(
                    "A slot delay and jitter must be set if with slot distribution"
                )

        return shape

    def format(self) -> str:
        s = "netem"
        if self.limit:
            s += f" limit {self.limit}"
        if self.latency:
            s += f" delay {self.latency}"
            if self.jitter:
                s += f" {self.jitter}"
                if self.jitter_corr:
                    s += f" {self.jitter_corr}%"
                if self.jitter_dist:
                    s += f" distribution {self.jitter_dist}"
        if self.rate:
            s += f" rate {self.rate}"
            if self.overhead:
                s += f" {self.overhead}"
        if self.loss_random:
            s += f" loss random {self.loss_random}"
        elif self.loss_bernoulli:
            s += f" loss state {self.loss_bernoulli}"
        if self.corrupt:
            s += f" corrupt {self.corrupt}%"
        if self.duplicate:
            s += f" duplicate {self.duplicate}%"
        if self.reorder:
            s += f" reorder {self.reorder}%"
            if self.reorder_gap:
                s += f" gap {self.reorder_gap}"
        if self.slot_dist or self.slot_packets or self.slot_bytes:
            s += " slot"
            if self.slot_dist:
                s += f" distribution {self.slot_dist} {self.slot_delay} {self.slot_jitter}"
            if self.slot_packets:
                s += f" packets {self.slot_packets}"
            if self.slot_bytes:
                s += f" bytes {self.slot_bytes}"

        return s
