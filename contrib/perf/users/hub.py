import locust

from tasks.device_gateway import GatewayDockerHubTasks
from users.device import DeviceUser
from utils.adapters import NamedHTTPAdapter, ShapeHTTPAdapter, install_letsencrypt
from utils.env import (
    API_FACTORY,
    API_CA,
    DEVICE_NETWORK_SHAPE,
    HUB_GCP_ENABLED,
    HUB_HOST,
    HUB_IMAGE_ARCH,
    HUB_IMAGE_TAG,
    HUB_MANIFEST_LIST_DIGEST,
    HUB_OVERRIDE_IP,
    HUB_AUTH_HOST,
)
from utils.shapers import TcNetemShape


class HubUser(locust.HttpUser):
    abstract = True

    factory_repo = f"{API_FACTORY}/{HUB_IMAGE_TAG}"
    image_arch = HUB_IMAGE_ARCH
    server_ip = HUB_OVERRIDE_IP
    server_ca = API_CA
    docker_manifest_list_digest = HUB_MANIFEST_LIST_DIGEST
    gcp_enabled = HUB_GCP_ENABLED
    network_shape = TcNetemShape.parse(DEVICE_NETWORK_SHAPE)
    hub_auth_host = HUB_AUTH_HOST

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.client.base_url = HUB_HOST
        self.client.verify = self.server_ca
        if not self.client.verify:
            import urllib3

            urllib3.disable_warnings()
        self.gcp_client = locust.clients.HttpSession(
            "", request_event=self.environment.events.request, user=self
        )

    def on_start(self):
        if not self.docker_manifest_list_digest:
            raise RuntimeError("An HUB_MANIFEST_LIST_DIGEST env variable is mandatory")
        if not API_FACTORY:
            raise RuntimeError("An API_FACTORY env variable is mandatory")
        if self.server_ip:
            NamedHTTPAdapter.install(self.client, self.server_ip)
        if self.network_shape is not None:
            ShapeHTTPAdapter.install(self.client, self.network_shape.format())
        install_letsencrypt(self.environment.host, self.client)
        DeviceUser.host = self.environment.host
        device_user = DeviceUser(environment=self.environment)
        device_user.on_start()
        self.docker_auth = GatewayDockerHubTasks(device_user).hub_creds().json()
