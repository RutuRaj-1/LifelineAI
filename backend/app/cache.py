"""Redis cache with an in-process fallback (embedding cache; keeps OpenAI cost down for repeat SOS events)."""
import json
import logging

from .config import get_settings

log = logging.getLogger("lifeline.cache")
_mem: dict[str, str] = {}
_redis = None
_url = get_settings().redis_url
if _url:
    try:
        import redis

        _redis = redis.Redis.from_url(_url, socket_connect_timeout=1, decode_responses=True)
        _redis.ping()
    except Exception as exc:  # noqa: BLE001
        log.warning("Redis unavailable (%s) - using in-process cache", exc)
        _redis = None


def cache_get(key: str):
    try:
        raw = _redis.get(key) if _redis else _mem.get(key)
    except Exception:  # noqa: BLE001
        raw = _mem.get(key)
    return json.loads(raw) if raw else None


def cache_set(key: str, value, ttl: int = 86400) -> None:
    raw = json.dumps(value)
    try:
        _redis.set(key, raw, ex=ttl) if _redis else _mem.__setitem__(key, raw)
    except Exception:  # noqa: BLE001
        _mem[key] = raw
