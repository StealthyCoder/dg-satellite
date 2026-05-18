import re
import time
from contextlib import contextmanager

import locust  # type: ignore

from tasks.device_gateway import GatewayConfigTasks
from tasks.device_register import DeviceRegisterTasks
from users.api import ApiUser
from utils.adapters import NamedHTTPAdapter, ShapeHTTPAdapter, TlsSessionHTTPSAdapter
from utils.env import (
    DEVICE_CLOSE_CONN,
    DEVICE_CREATE_CONFIG,
    DEVICE_GROUP,
    DEVICE_NETWORK_SHAPE,
    DEVICE_RESUME_TLS,
    DEVICE_TAG,
    GATEWAY_OVERRIDE_IP,
    OSTREE_OVERRIDE_IP,
)
from utils.shapers import TcNetemShape


class DeviceUser(locust.HttpUser):
    abstract = True
    tag = DEVICE_TAG
    group = DEVICE_GROUP
    server_ip = GATEWAY_OVERRIDE_IP
    network_shape = TcNetemShape.parse(DEVICE_NETWORK_SHAPE)
    should_close_conn = DEVICE_CLOSE_CONN
    should_create_config = DEVICE_CREATE_CONFIG
    should_resume_tls = DEVICE_RESUME_TLS
    register_offline = False
    # Connection refresh helps to properly load-balance sessions during scaling
    conn_refresh_interval = 60  # seconds
    # A sota.toml's attribute that refers (base URL) to an OTA server, either Device Gateway or OSTree service
    sota_server_attr = "server"

    def on_start(self):
        self._init_api_user()
        self._register()
        self._set_host()
        self._set_certs()
        self._set_config()
        self.client.headers["x-ats-tags"] = self.tag
        if self.should_close_conn:
            self.client.headers["connection"] = "close"
        else:
            self.client.request = self._refreshable_request_handler(self.client.request)
        if self.should_resume_tls:
            TlsSessionHTTPSAdapter.install(self.client)
        self._last_conn_refresh_time = time.time()
        self._inside_close_conn = False

    def on_stop(self):
        self._del_certs()

    def _refreshable_request_handler(self, request_handler):
        def wrapper(*args, **kwargs):
            if time.time() - self._last_conn_refresh_time > self.conn_refresh_interval:
                with self.close_conn():
                    return request_handler(*args, **kwargs)
            else:
                return request_handler(*args, **kwargs)

        return wrapper

    def _init_api_user(self):
        # A locust sets host on each "active" user class before creating users
        # But ApiUser might be inactive at the moment.
        ApiUser.host = self.environment.host
        self._api_user = ApiUser(self.environment)
        self._api_user.on_start()

    def _register(self):
        reg = DeviceRegisterTasks(self._api_user)
        if self.register_offline:
            self.device = reg.do_register_device_offline()
        else:
            self.device = reg.do_register_device_online()

    def _set_config(self):
        if self.register_offline and (self.group or self.should_create_config):
            raise RuntimeError(
                "Device config isn't supported for auto-registered devices"
            )
        if self.group:
            # TODO: Need a better place for this, keep here for now.
            self._api_user.client.patch(
                f"/ota/devices/{self.device.name}/",
                name="api:device:set-group",
                json={"group": self.group},
            ).raise_for_status()
        if self.should_create_config:
            cfg = GatewayConfigTasks(self)
            cfg.set_config()

    def _set_certs(self):
        self.certfile, self.keyfile, self.cafile = self.device.save_pki()
        self.client.cert = self.certfile, self.keyfile
        self.client.verify = self.cafile

    def _set_host(self):
        match = re.search(
            r'^{}\s*=\s*"(.+?)"$'.format(self.sota_server_attr),
            self.device.sota,
            re.MULTILINE,
        )
        if not match:
            raise RuntimeError("No server setting in sota.toml")

        self.host = self.client.base_url = match.group(1)
        if self.server_ip:
            NamedHTTPAdapter.install(self.client, self.server_ip)
        if self.network_shape is not None:
            ShapeHTTPAdapter.install(self.client, self.network_shape.format())

    def _del_certs(self):
        if hasattr(self, "device"):
            self.device.clear_pki()

    @contextmanager
    def close_conn(self):
        if not self._inside_close_conn and self.should_close_conn is None:
            self._inside_close_conn = True
            self.client.headers["connection"] = "close"
            try:
                yield None
            finally:
                self._inside_close_conn = False
                self._last_conn_refresh_time = time.time()
                del self.client.headers["connection"]
        else:
            yield None


class DeviceOstreeUser(DeviceUser):
    abstract = True
    sota_server_attr = "ostree_server"
    server_ip = OSTREE_OVERRIDE_IP
