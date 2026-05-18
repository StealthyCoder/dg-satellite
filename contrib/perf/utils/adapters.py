import socket
import urllib3

from locust.clients import HttpSession
from requests.adapters import HTTPAdapter

# requests.packages.urllib3 has type hints whereas urllib3 does not
from requests.packages.urllib3.connectionpool import (
    HTTPConnectionPool,
    HTTPSConnectionPool,
)
from requests.packages.urllib3.connection import create_urllib3_context  # type: ignore
from tempfile import mkdtemp
from threading import RLock
from typing import Any, ClassVar, Dict, List, Optional, Tuple
from zlib import crc32

from utils.env import TC_SHAPER_ENABLED
from utils.events import tracking
from utils.shapers import tc_shaper


class _WrapsHTTPAdapter:

    __wrapped__: ClassVar[List[str]]
    __client__: HttpSession
    __adapter__: HTTPAdapter
    __original__: Dict[str, Any]

    @classmethod
    def install(cls, client: HttpSession, *args, **kwargs):
        for schema in ("http://", "https://"):
            adapter = client.get_adapter(schema)
            wrapper = cls.__new__(cls, *args, **kwargs)  # type: ignore
            wrapper.__client__ = client
            wrapper.__adapter__ = adapter
            wrapper.__original__ = {
                attr: getattr(adapter, attr) for attr in cls.__wrapped__
            }
            for attr in cls.__wrapped__:
                setattr(adapter, attr, getattr(wrapper, attr))
            wrapper.__init__(*args, **kwargs)


class NamedHTTPAdapter(_WrapsHTTPAdapter):
    """Allows to override a connection's hostname without editing /etc/hosts"""

    __wrapped__ = ["get_connection"]

    def __init__(self, server_ip: str):
        self.server_ip = server_ip

    def get_connection(self, *args, **kwargs) -> HTTPConnectionPool:
        pool = self.__original__["get_connection"](*args, **kwargs)
        pool.conn_kw.setdefault("server_hostname", pool.host)
        pool.host = self.server_ip
        return pool


class LetsEncryptStagingHTTPSAdapter(_WrapsHTTPAdapter):
    """Add lets encrypt staging root CAs automatically"""

    __wrapped__ = ["get_connection"]

    ca_cert_dir = mkdtemp()

    def __init__(self):
        http = urllib3.PoolManager()
        with open(f"{self.ca_cert_dir}/ca.pem", "wb") as f:
            resp = http.request(
                "GET",
                "https://letsencrypt.org/certs/staging/letsencrypt-stg-root-x1.pem",
            )
            f.write(resp.data)
        with open(f"{self.ca_cert_dir}/ca.pem", "ab") as f:
            resp = http.request(
                "GET",
                "https://letsencrypt.org/certs/staging/letsencrypt-stg-root-x2.pem",
            )
            f.write(resp.data)
        self._ssl_context = create_urllib3_context()
        self._ssl_context.load_verify_locations(f"{self.ca_cert_dir}/ca.pem")

    def get_connection(self, *args, **kwargs) -> HTTPConnectionPool:
        pool = self.__original__["get_connection"](*args, **kwargs)
        pool.conn_kw["ssl_context"] = self._ssl_context
        return pool


class TlsSessionHTTPSAdapter(_WrapsHTTPAdapter):
    """Allows to persist TLS session between re-connects"""

    __wrapped__ = ["get_connection"]

    def __init__(self):
        import ssl

        self._ssl_session = None
        self._ssl_context = create_urllib3_context()
        # TLSv1.3 must not work like TLSv1.2, Python default is the opposite
        self._ssl_context.options &= ~ssl.OP_ENABLE_MIDDLEBOX_COMPAT
        # urlllib3 disables TLS session resumption, see https://github.com/urllib3/urllib3/issues/1898
        self._ssl_context.options &= ~ssl.OP_NO_TICKET
        self._ssl_context.wrap_socket = self._wrap_socket(self._ssl_context.wrap_socket)

    def get_connection(self, *args, **kwargs) -> HTTPConnectionPool:
        pool = self.__original__["get_connection"](*args, **kwargs)
        pool.conn_kw["ssl_context"] = ssl_ctx = self._ssl_context
        return pool

    def _wrap_socket(self, orig_wrap_socket):
        def wrap_socket(sock, *args, **kwargs):
            if self._ssl_session is not None and kwargs.get("session", None) is None:
                kwargs["session"] = self._ssl_session
            ssl_sock = orig_wrap_socket(sock, *args, **kwargs)

            # Setting kwags["do_handshake_on_connect"] and saving session right after the handshake
            # is not enough: while it works in TLSv1.2, session ticket arrives later in TLSv1.3.
            # See the https://github.com/openssl/openssl/issues/1550 and
            # https://github.com/openssl/openssl/issues/6262 which explain it well.
            def _close(*args, **kwargs):
                if ssl_sock.session is not None and ssl_sock.session.has_ticket:
                    self._ssl_session = ssl_sock.session
                return orig_close(*args, **kwargs)

            orig_close, ssl_sock.close = ssl_sock.close, _close
            return ssl_sock

        return wrap_socket


class ShapeHTTPAdapter(_WrapsHTTPAdapter):
    """Allows to configure network shaping using a tc utility"""

    __wrapped__ = ["get_connection"]
    _install_lock: ClassVar[RLock] = RLock()
    _installed_leaf_shapes: ClassVar[Dict[str, int]] = {}  # shape to mark
    _installed_leaf_marks: ClassVar[Dict[int, str]] = {}  # mark to shape

    def __init__(self, shape: str):
        self.shape = shape
        if not TC_SHAPER_ENABLED:
            raise RuntimeError(
                "A network shaping disabled.  Please, see utils.env.TC_SHAPER_ENABLED for details."
            )
        with tracking(self.__client__.user, "tc:install"):
            with self._install_lock:
                tc_shaper.install_default_root_htb()
                self.mark, installed = self._reserve_mark(self.shape)
                if not installed:
                    tc_shaper.install_mark_leaf_htb(self.mark, self.shape)

    @classmethod
    def _reserve_mark(cls, shape: str) -> Tuple[int, bool]:
        mark = cls._installed_leaf_shapes.get(shape)
        if mark is not None:
            return mark, True
        # By default Linux opens ephemeral ports above 0x8000 for client connections.
        # Application ports tend to be usually less then 0x4000.
        # Thus, it's safe to reserve values between 0x4000 and 0x8000 for marks.
        # Consistent hash allows to predict a mark value with high accuracy for debugging.
        mark = crc32(shape.encode()) & 0x7FFF | 0x4000
        if mark in cls._installed_leaf_marks:
            for mark in range(0x4000, 0x8000):
                if mark not in cls._installed_leaf_marks:
                    break
            else:
                raise RuntimeError(
                    "Run out of available marks, too many different shapers"
                )
        cls._installed_leaf_shapes[shape], cls._installed_leaf_marks[mark] = mark, shape
        return mark, False

    def get_connection(self, *args, **kwargs) -> HTTPConnectionPool:
        pool = self.__original__["get_connection"](*args, **kwargs)
        if hasattr(pool, "_tc_shaper_installed"):
            return pool

        class _ConnCls(pool.ConnectionCls):  # type: ignore
            def _new_conn(conn) -> socket.socket:
                sock = super()._new_conn()
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_MARK, self.mark)
                return sock

        pool.ConnectionCls = _ConnCls
        setattr(pool, "_tc_shaper_installed", True)
        return pool


def install_letsencrypt(host, client):
    from urllib.parse import urlparse
    import ssl
    import socket
    from cryptography import x509

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    hostname = urlparse(host).netloc

    with socket.create_connection((hostname, 443)) as sock:
        with ctx.wrap_socket(sock, server_hostname=hostname) as ssock:
            cert = x509.load_der_x509_certificate(ssock.getpeercert(True))
            issuer = cert.issuer.get_attributes_for_oid(x509.oid.NameOID.COMMON_NAME)[
                0
            ].value
            if issuer.startswith("(STAGING)"):
                LetsEncryptStagingHTTPSAdapter.install(client)
