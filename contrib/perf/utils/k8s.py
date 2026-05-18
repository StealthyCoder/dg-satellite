import requests

from base64 import b64decode, b64encode
from typing import Any, Dict

from utils.env import SECRETS_NAMESPACE


_K8S_CA = "/var/run/secrets/kubernetes.io/serviceaccount/ca.crt"
_K8S_TOKEN = "/var/run/secrets/kubernetes.io/serviceaccount/token"
_K8S_V1_API = "https://kubernetes.default/api/v1"


def _secret_url(namespace: str, secret: str) -> str:
    return _K8S_V1_API + "/namespaces/" + namespace + "/secrets/" + secret


def _decode(val: str) -> str:
    return b64decode(val.encode()).decode()


def _encode(val: str) -> str:
    return b64encode(val.encode()).decode()


def _get_secret(namespace: str, secret: str) -> Dict[str, Any]:
    headers = None
    if _K8S_TOKEN:
        with open(_K8S_TOKEN) as f:
            headers = {"Authorization": "Bearer " + f.read()}
    r = requests.get(_secret_url(namespace, secret), verify=_K8S_CA, headers=headers)
    r.raise_for_status()
    return r.json()


def get_k8s_secret(namespace: str, secret: str) -> Dict[str, str]:
    data = _get_secret(namespace, secret)["data"]
    assert isinstance(data, dict)
    return {k: _decode(v) for k, v in data.items()}


def get_k8s_secret_attr(namespace: str, secret: str, attr: str) -> str:
    data = _get_secret(namespace, secret)["data"]
    return _decode(data[attr])


def get_gateway_keys(repo_id: str, allow_shared: bool = True) -> Dict[str, str]:
    if not SECRETS_NAMESPACE:
        raise RuntimeError("SECRETS_NAMESPACE not set, required by this test")

    try:
        keys = get_k8s_secret(SECRETS_NAMESPACE, f"gateway-{repo_id}")
    except requests.HTTPError as why:
        if why.response.status_code == 404:
            if allow_shared:
                return get_k8s_secret(SECRETS_NAMESPACE, "gateway-default")
            else:
                raise RuntimeError("This factory did not take factory PKI offline")
        else:
            raise
    else:
        keys["ca_pass"] = "og123" + "".join(reversed(repo_id))
        return keys
