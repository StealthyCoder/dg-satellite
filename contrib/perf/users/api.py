import locust  # type: ignore

from utils.adapters import NamedHTTPAdapter, install_letsencrypt
from utils.auth import gen_token
from utils.env import (
    API_CA,
    API_FACTORY,
    API_OVERRIDE_IP,
    API_TOKEN,
    API_USERID,
)


class ApiUser(locust.HttpUser):
    abstract = True
    factory = API_FACTORY
    server_ca = API_CA
    server_ip = API_OVERRIDE_IP
    token = API_TOKEN
    userid = API_USERID

    def on_start(self):
        if not self.factory:
            raise RuntimeError("An API_FACTORY env variable is mandatory")
        if not self.token:
            if not self.userid:
                raise RuntimeError(
                    "Either API_TOKEN or API_USERID env variable is mandatory"
                )
            self.token = gen_token(self.userid, self.factory)

        self.client.verify = self.server_ca
        if not self.client.verify:
            import urllib3

            urllib3.disable_warnings()
        self.client.headers["osf-token"] = self.token
        if self.server_ip:
            NamedHTTPAdapter.install(self.client, self.server_ip)
        install_letsencrypt(self.environment.host, self.client)
