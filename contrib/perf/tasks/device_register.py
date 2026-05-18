import locust  # type: ignore
import os
import tempfile
import uuid

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Optional, Tuple

from utils.pki import DevicePki, FactoryKeys


filename = str


@dataclass
class Device:
    uuid: str
    name: str
    key: bytes
    cert: bytes
    ca: bytes
    sota: str

    _files: Optional[Tuple[filename, filename, filename]] = None

    def save_pki(self) -> Tuple[filename, filename, filename]:
        def _save(prefix, data):
            fd, filename = tempfile.mkstemp(prefix=prefix)
            os.write(fd, data)
            os.close(fd)
            return filename

        self._files = (
            _save("fio-dg-cert-", self.cert),
            _save("fio-dg-key-", self.key),
            _save("fio-dg-ca-", self.ca),
        )
        return self._files

    def clear_pki(self):
        if self._files is not None:
            for f in self._files:
                os.remove(f)
            self._files = None


class DeviceRegisterTasks(locust.TaskSet):
    user: Any  # mypy

    @locust.task
    @locust.tag("device:register")
    def register_device(self):
        self.do_register_device_online()

    def do_register_device_online(self, name: str = None) -> Device:
        duuid = uuid.uuid4().hex
        if name is None:
            # Put a prefix into the device name to easily find it.
            name = f"test-dspl-{duuid}"
        pk, csr = DevicePki.gen_device_csr(self.user.factory, duuid)

        req = {
            "uuid": duuid,
            "name": name,
            "hardware-id": "intel",
            "csr": csr.decode(),
            "use-ostree-server": "true",
        }
        resp = self.client.post(
            "/ota/devices/",
            json=req,
            name="api:create-device",
        )
        resp.raise_for_status()
        data = resp.json()
        # Used by offline registration, so that we don't need to generate sota.toml
        DevicePki.cache_sota_toml(self.user.factory, data["sota.toml"])
        return Device(
            uuid=duuid,
            name=name,
            key=pk,
            cert=data["client.pem"].encode(),
            ca=data["root.crt"].encode(),
            sota=data["sota.toml"],
        )

    def do_register_device_offline(self, name: str = None):
        duuid = uuid.uuid4().hex
        if name is None:
            # Put a prefix into the device uuid to easily find it.
            # Note that a device name is actually ignored during an auto-registration
            name = f"test-dspl-{duuid}"
        pk, csr = DevicePki.gen_device_csr(self.user.factory, duuid)

        repo_id = self._get_repo_id()
        sota_toml = self._get_sota_toml()
        keys = DevicePki.get_gateway_keys(repo_id)
        cert = DevicePki.sign_device_csr_offline(csr, keys)
        return Device(
            uuid=duuid,
            name=name,
            key=pk,
            cert=b"\n".join((cert, keys.ca_crt_bytes)),
            ca=keys.root_crt_bytes,
            sota=sota_toml,
        )

    def _get_repo_id(self):
        def update_repo_ids():
            resp = self.client.get("/ota/factories/", name="api:get-factory-list")
            resp.raise_for_status()
            DevicePki.cache_repo_ids(
                {f["name"]: f["reposerver-id"] for f in resp.json()}
            )

        return DevicePki.get_repo_id(self.user.factory, update_repo_ids)

    def _get_sota_toml(self):
        return DevicePki.get_sota_toml(
            self.user.factory, self.do_register_device_online
        )
