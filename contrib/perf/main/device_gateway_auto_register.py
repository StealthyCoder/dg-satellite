from main.device_gateway import BaseTest

# For auto-register we need a constant shape (ignore spawn rate)
from utils.locust import ConstantShape


class Test(BaseTest):
    register_offline = True

    def wait_time(self):
        # We need a new device for each task to trigger an auto-registration
        # Clear all connections to enforce the new client certificate.
        for adapter in self.client.adapters.values():
            adapter.poolmanager.clear()
        self._register()
        self._del_certs()
        self._set_certs()
        return 0
