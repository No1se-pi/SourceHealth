"""Разные ключи для snapshot и платформенных данных. Redis полностью удаляем."""

import hashlib
import json
from typing import Any

from redis import Redis
from redis.exceptions import RedisError


def fingerprint(kind: str, **parts: Any) -> str:
    encoded = json.dumps({"kind": kind, **parts}, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(encoded.encode()).hexdigest()


def code_cache_key(repository_id: str, head_sha: str, analyzer: str, version: str, configuration: str) -> str:
    if not head_sha:
        raise ValueError("unknown HEAD must not be cached as a code snapshot")
    return "code:" + fingerprint("code-v1", repository_id=repository_id, head_sha=head_sha,
                                 analyzer=analyzer, version=version, configuration=configuration)


def platform_cache_key(repository_id: str, resource: str, authorization_scope: str = "public") -> str:
    return "platform:" + fingerprint("platform-v1", repository_id=repository_id, resource=resource,
                                     authorization_scope=authorization_scope)


class JsonCache:
    """Cache failure = miss. Значения — только очищенные versioned facts/results."""

    def __init__(self, redis: Redis) -> None:
        self.redis = redis

    def get(self, key: str) -> dict | None:
        try:
            value = self.redis.get(key)
            parsed = json.loads(value) if value else None
            return parsed if isinstance(parsed, dict) else None
        except (RedisError, ValueError, TypeError):
            return None

    def put(self, key: str, value: dict, ttl: int) -> None:
        if ttl < 1:
            raise ValueError("cache TTL must be positive")
        serialized = json.dumps(value, allow_nan=False)
        try:
            self.redis.set(key, serialized, ex=ttl)
        except RedisError:
            pass
