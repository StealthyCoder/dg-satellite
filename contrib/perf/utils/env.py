from os import getenv
from typing import Optional, Union


def _get_str(name: str, default: str = "") -> str:
    return getenv(name, default)


def _get_optional_bool(name: str, default: Optional[bool] = None) -> Optional[bool]:
    v = getenv(name, "").lower()
    if v in ("1", "on", "t", "true", "y", "yes"):
        return True
    elif v in ("0", "f", "false", "off", "n", "no"):
        return False
    else:
        return default


def _get_ca(name: str) -> Union[str, bool]:
    v = _get_optional_bool(name)
    if v is not None:
        return v
    return _get_str(name) or True


# A path to a CA certificate to verify HTTPS requests to API.
# Can be a boolean value, where True means to verify using system CA (default); False - no verify.
API_CA = _get_ca("API_CA")

# A mandatory factory name to use for API operations.
API_FACTORY = _get_str("API_FACTORY")

# An optional IP address to use for ota-lite API calls.
# If not specified, a DNS resolution will be used for a hostname provided via locust.
API_OVERRIDE_IP = _get_str("API_OVERRIDE_IP")

# An optional osf-token header value to authenticate with ota-lite API.
# If not set, a test will try to generate a new token for API_USERID and use it.
API_TOKEN = _get_str("API_TOKEN")

# An optional user ID used to generate an ota-lite API token if API_TOKEN is not set.
# Either API_TOKEN or API_USERID is mandatory, but API_USERID only works if AUTH_REDIS_HOST points
# to a valid token cache e.g. it doesn't work on-prem.
API_USERID = _get_str("API_USERID")

# An optional Redis hostname used to generate an API token.
AUTH_REDIS_HOST = _get_str("REDIS_HOST", "web-session.heracles")

# An optional TTL used when storing a token in Redis.
AUTH_REDIS_TOKEN_TTL = int(_get_str("AUTH_REDIS_TOKEN_TTL", "1800"))

# An optional boolean specifying if a device mTLS connection to device-gateway should be closed
# after each request.  True - close on each request; False - never close; None (default) - a
# user/tasks class defines if/when a connection should be closed.
DEVICE_CLOSE_CONN = _get_optional_bool("DEVICE_CLOSE_CONN")

# An optional boolean specifying it the mTLS session should be resumed between re-connects.
# True - resume, False - no (default).  Usually used with DEVICE_CLOSE_CONN.
DEVICE_RESUME_TLS = _get_optional_bool("DEVICE_RESUME_TLS", False)

# An optional boolean specifying if a device config should be created after registering the device.
DEVICE_CREATE_CONFIG = _get_optional_bool("DEVICE_CREATE_CONFIG", False)

# An optional network shape used on an emulated device for all calls to device-gateway.
# Must be specified in a utils/shapers.py format.  ATM only the netem shaper is supported.
DEVICE_NETWORK_SHAPE = _get_str("DEVICE_NETWORK_SHAPE")

# An optional device tag to use for requests to device-gateway; default "master".
DEVICE_TAG = _get_str("DEVICE_TAG", "master")

# An optional device group to add device to (doesn't work with offline registration).
DEVICE_GROUP = _get_str("DEVICE_GROUP")

# An optional IP address to use for device-gateway API calls.
# If not specified, a DNS resolution will be used for a hostname provided in sota.toml received
# during the device registration.
GATEWAY_OVERRIDE_IP = _get_str("GATEWAY_OVERRIDE_IP")

# An optional IP address to use for the ostree server API calls.
# If not specified, a DNS resolution will be used for a hostname provided in sota.toml received
# during the device registration.
OSTREE_OVERRIDE_IP = _get_str("OSTREE_OVERRIDE_IP")

# An optional Kubernetes namespace used to fetch secrets.
# Used by some tests (e.g. device auto-registration).
SECRETS_NAMESPACE = _get_str("SECRETS_NAMESPACE")

# An optional boolean enabling tc based network shaping.
# This prevents an accidental installation of tc network shapers.
# It is enabled in k8s by default to allow running shaped scenarios.
# It should only be enabled locally when run inside a container.
# When enabled on host system - it can make your host machine networking unusable.
TC_SHAPER_ENABLED = _get_optional_bool("TC_SHAPER_ENABLED", False)

# Needed only for the registry testing of Docker
# The value of the uploaded image digest in order to get image back during testing

# The value of the uploaded image tag, defaults to hub-test
# Can be a simple sha hash as well, and it just pertains to the image you want to get from hub.foundries.io for testing
HUB_IMAGE_TAG = _get_str("HUB_IMAGE_TAG", "hub-test")

# The value of the manifest image list digest
HUB_MANIFEST_LIST_DIGEST = _get_str("HUB_MANIFEST_LIST_DIGEST", "alpine")

# The value of the docker image arch
HUB_IMAGE_ARCH = _get_str("HUB_IMAGE_ARCH", "amd64")

# The value to override the IP of the registry of hub.foundries.io location
HUB_OVERRIDE_IP = _get_str("HUB_OVERRIDE_IP")

# The value for setting the host of Hub
HUB_HOST = _get_str("HUB_HOST")

# The value for setting the host of Hub
HUB_AUTH_HOST = _get_str("HUB_AUTH_HOST")

# The value for setting if GCP calls should be made, defaults to False
HUB_GCP_ENABLED = _get_optional_bool("HUB_GCP_ENABLED", False)
