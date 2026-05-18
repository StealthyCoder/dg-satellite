import locust
from functools import lru_cache
from requests.auth import HTTPBasicAuth
from utils.events import tracking
from urllib.parse import urlparse


@lru_cache
def _auth_host(hub_auth_host):
    return urlparse(hub_auth_host).netloc


@locust.tag("hub")
@locust.tag("hub:auth")
class HubAuthTasks(locust.TaskSet):
    def __init__(self, parent):
        super().__init__(parent)
        self._auth_params = (
            f"service=registry&scope=repository:{self.user.factory_repo}:pull"
        )
        self._device_auth = HTTPBasicAuth(
            self.user.docker_auth["Username"], self.user.docker_auth["Secret"]
        )

    @locust.task
    @locust.tag("hub:auth:device")
    def get_device_token(self):
        resp = self.client.get(
            f"{self.user.hub_auth_host}/token-auth/",
            headers={"Host": _auth_host(self.user.hub_auth_host)},
            name="hub:auth:device",
            auth=self._device_auth,
            params=self._auth_params,
        )
        resp.raise_for_status()
        return resp


@locust.tag("hub")
@locust.tag("hub:baseline")
class HubAnonymousTasks(locust.TaskSet):
    @locust.task
    @locust.tag("hub:baseline:registry")
    def registry_baseline(self):
        """Get a simple request to just Docker Registry HTTP API v2, without actual creds"""
        with self.client.get(
            "/v2/", catch_response=True, name="hub:baseline:registry"
        ) as resp:
            (
                resp.success()
                if resp.status_code == 401
                else resp.failure(Exception(resp.reason))
            )

    @locust.tag("hub:baseline:token")
    @locust.task
    def registry_token_baseline(self):
        """Get a simple request to just token_auth, without actual creds"""
        with self.client.get(
            f"{self.user.hub_auth_host}/token-auth/",
            headers={"Host": _auth_host(self.user.hub_auth_host)},
            catch_response=True,
            name="hub:baseline:token",
        ) as resp:
            (
                resp.success()
                if resp.status_code == 400
                else resp.failure(Exception(resp.reason))
            )


@locust.tag("hub")
@locust.tag("hub:registry")
class HubRegistryTasks(locust.TaskSet):
    def __init__(self, parent):
        super().__init__(parent)
        self.auth_tasks = HubAuthTasks(parent)
        if not hasattr(self.user, "hub_registry_initialized"):
            self.user.auth_token = (
                f"Bearer {self.auth_tasks.get_device_token().json()['token']}"
            )
            self._init_manifest()
            self._init_layers_and_config()
            self.user.hub_registry_initialized = True

    def _init_manifest(self):
        resp = self.fetch_manifests()
        for manifest in resp.json()["manifests"]:
            if manifest["platform"]["architecture"] == self.user.image_arch:
                self.user.manifest_digest = manifest["digest"]
                self.user.manifest_mediatype = manifest["mediaType"]

    def _init_layers_and_config(self):
        resp = self.fetch_manifest()
        self.user.layers = resp.json()["layers"]
        config = resp.json()["config"]
        self.user.config_digest = config["digest"]
        self.user.config_mediatype = config["mediaType"]

    @locust.task
    @locust.tag("hub:registry:registry")
    def root_request(self):
        self.client.get(
            f"/v2/",
            headers={"Authorization": self.user.auth_token},
            name="hub:registry:registry",
        ).raise_for_status()

    @locust.task
    @locust.tag("hub:registry:manifests")
    def fetch_manifests(self):
        resp = self.client.get(
            f"/v2/{self.user.factory_repo}/manifests/{self.user.docker_manifest_list_digest}",
            name="hub:registry:manifests",
            headers={
                "Accept": "application/vnd.docker.distribution.manifest.list.v2+json",
                "Authorization": self.user.auth_token,
            },
        )
        resp.raise_for_status()
        return resp

    @locust.tag("hub:registry:manifest")
    @locust.task
    def fetch_manifest(self):
        """Get the manifest digest"""
        resp = self.client.get(
            f"/v2/{self.user.factory_repo}/manifests/{self.user.manifest_digest}",
            name="hub:registry:manifest",
            headers={
                "Accept": self.user.manifest_mediatype,
                "Authorization": self.user.auth_token,
            },
        )
        resp.raise_for_status()
        return resp

    @locust.tag("hub:registry:layers")
    @locust.task
    def hub_registry_layers(self):
        """Get the individual layers"""
        with tracking(self, "hub:registry:layers:fetch-layers"):
            for layer in self.user.layers:
                layer_resp = self.client.get(
                    f"/v2/{self.user.factory_repo}/blobs/{layer['digest']}",
                    headers={
                        "Accept": layer["mediaType"],
                        "Authorization": self.user.auth_token,
                    },
                    name="hub:registry:layers:blob-hub",
                    allow_redirects=False,
                )
                layer_resp.raise_for_status()
                if self.user.gcp_enabled:
                    gcp_resp = self.user.gcp_client.get(
                        layer_resp.headers["Location"],
                        headers=layer_resp.request.headers,
                        name="hub:registry:layers:blob-gcp",
                    )
                    gcp_resp.raise_for_status()

    @locust.tag("hub:registry:config")
    @locust.task
    def hub_registry_config(self):
        """Get the config blobs"""
        with tracking(self, "hub:registry:config:fetch-config"):
            config_resp = self.client.get(
                f"/v2/{self.user.factory_repo}/blobs/{self.user.config_digest}",
                headers={
                    "Accept": self.user.config_mediatype,
                    "Authorization": self.user.auth_token,
                },
                name="hub:registry:config:fetch-config-hub",
                allow_redirects=False,
            )
            config_resp.raise_for_status()
            if self.user.gcp_enabled:
                gcp_resp = self.user.gcp_client.get(
                    config_resp.headers["Location"],
                    headers=config_resp.request.headers,
                    name="hub:registry:config:fetch-config-gcp",
                )
                gcp_resp.raise_for_status()


@locust.tag("hub")
@locust.tag("hub:registry:flow")
class HubTasksFlow(locust.TaskSet):
    def __init__(self, parent):
        super().__init__(parent)
        self.registry_tasks = HubRegistryTasks(parent)

    @locust.tag("hub:registry:flow")
    @locust.task
    def registry_flow(self):
        with tracking(self, "hub:registry:flow"):
            self.registry_tasks.auth_tasks.get_device_token()
            self.registry_tasks.fetch_manifests()
            self.registry_tasks.fetch_manifest()
            self.registry_tasks.hub_registry_layers()
            self.registry_tasks.hub_registry_config()
