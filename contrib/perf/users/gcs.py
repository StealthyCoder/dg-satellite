import locust

from users.device import DeviceOstreeUser
from utils.adapters import ShapeHTTPAdapter


class GCSUser(locust.HttpUser):
    abstract = True
    _device = None
    network_adjuster = None

    def on_start(self):
        DeviceOstreeUser.host = self.environment.host
        self._device = DeviceOstreeUser(self.environment)
        # don't shape network for device registration calls since it happens just once per GCSUser,
        # so the network shouldn't be overwhelmed with the registration requests in case of GCS testing
        self._device.network_shape = None
        self._device.on_start()
        self._set_host()
        self._set_download_list()
        self._set_delta_list()

    def on_stop(self):
        self._device.on_stop()

    def _set_host(self):
        r = self._device.client.post("/download-urls")
        r.raise_for_status()
        urls = r.json()
        self.host = self.client.base_url = urls[0]["download_url"]
        self.client.headers["Authorization"] = "Bearer " + urls[0]["access_token"]
        if self.network_adjuster is not None:
            ShapeHTTPAdapter.install(self.client, self.network_adjuster.format())

    def _set_download_list(self):
        r = self.client.get("/objects/objects.list", name="ostree:gcs:list")
        r.raise_for_status()
        self.objects = r.text.split("\n")

    def _set_delta_list(self):
        r = self.client.get("/objects/deltas.list", name="ostree:gcs:deltas:list")
        r.raise_for_status()
        self.deltas = r.text.split("\n")
