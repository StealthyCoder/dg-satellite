from base64 import b32encode
from json import dumps as json_dumps
from os import urandom
from redis import Redis
from typing import Dict, Tuple

from utils.env import AUTH_REDIS_HOST, AUTH_REDIS_TOKEN_TTL


_REDIS_PREFIX = "access-token-test-dspl-"
_HEADER_PREFIX = "ota-lite-test-dspl-"


_memory_cache: Dict[Tuple[str, str], str] = {}


def gen_token(userid: str, factory: str) -> str:
    memkey = (userid, factory)
    if memkey in _memory_cache:
        return _memory_cache[memkey]

    cache = Redis(AUTH_REDIS_HOST)
    token = {
        "uid": userid,
        "source": "test-dspl",
        "subscriber": True,
        "orgs": [
            "demo",
            "development",
            factory,
        ],
        "scopes": [
            f"{factory}:{privilege}"
            for privilege in (
                "containers:create",
                "containers:read-update",
                "devices:create",
                "devices:delete",
                "devices:read-update",
                "targets:create",
                "targets:read-update",
            )
        ],
        "ip": "",
        "max_devices": 1000000,
    }

    key = b32encode(urandom(20)).decode().lower()
    cache.setex(
        f"{_REDIS_PREFIX}{key}",
        value=json_dumps(token).encode(),
        time=AUTH_REDIS_TOKEN_TTL,
    )
    _memory_cache[memkey] = res = f"{_HEADER_PREFIX}{key}"
    return res
