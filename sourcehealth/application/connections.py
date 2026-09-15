"""Ограниченные ожидания Redis, чтобы outage не блокировал HTTP бесконечно."""

from redis import Redis


def create_redis(url: str) -> Redis:
    return Redis.from_url(url, socket_connect_timeout=3, socket_timeout=3)
