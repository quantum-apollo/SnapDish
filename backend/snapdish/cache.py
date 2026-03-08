"""
SnapDish caching layer.

Production: Redis via SNAPDISH_REDIS_URL (store in AWS Secrets or env).
Dev/fallback: Thread-safe in-memory LRU dict with TTL.

Redis key namespacing: "sd:<namespace>:<key>"
"""

from __future__ import annotations

import json
import threading
import time
from collections import OrderedDict
from typing import Any

from .config import get_logger, get_secret

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# In-memory LRU fallback (capped at 2 000 entries, suitable for single-process)
# ---------------------------------------------------------------------------

_MAX_MEMORY_ENTRIES = 2_000
_memory: OrderedDict[str, tuple[Any, float]] = OrderedDict()
_memory_lock = threading.Lock()


def _memory_get(key: str) -> Any | None:
    with _memory_lock:
        entry = _memory.get(key)
        if entry is None:
            return None
        value, expires_at = entry
        if time.time() > expires_at:
            _memory.pop(key, None)
            return None
        # LRU: move to end
        _memory.move_to_end(key)
        return value


def _memory_set(key: str, value: Any, ttl_seconds: int) -> None:
    with _memory_lock:
        _memory[key] = (value, time.time() + ttl_seconds)
        _memory.move_to_end(key)
        if len(_memory) > _MAX_MEMORY_ENTRIES:
            _memory.popitem(last=False)


def _memory_delete(key: str) -> None:
    with _memory_lock:
        _memory.pop(key, None)


# ---------------------------------------------------------------------------
# Redis client (lazy, singleton)
# ---------------------------------------------------------------------------

_redis = None
_redis_init = False
_redis_lock = threading.Lock()


def _get_redis():
    global _redis, _redis_init
    if _redis_init:
        return _redis
    with _redis_lock:
        if _redis_init:
            return _redis
        _redis_init = True
        redis_url = get_secret("SNAPDISH_REDIS_URL")
        if not redis_url:
            logger.info("cache_using_memory_fallback", extra={"reason": "SNAPDISH_REDIS_URL not set"})
            return None
        try:
            import redis as redis_lib  # type: ignore

            client = redis_lib.from_url(
                redis_url,
                decode_responses=True,
                socket_connect_timeout=2,
                socket_timeout=2,
                retry_on_timeout=True,
            )
            client.ping()
            _redis = client
            logger.info("redis_connected")
        except Exception as exc:
            logger.warning("redis_unavailable", extra={"error": str(exc)})
            _redis = None
        return _redis


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

_NS = "sd"


def _full_key(namespace: str, key: str) -> str:
    return f"{_NS}:{namespace}:{key}"


def cache_get(namespace: str, key: str) -> Any | None:
    """Return cached value or None (miss / expired)."""
    fk = _full_key(namespace, key)
    r = _get_redis()
    if r is not None:
        try:
            raw = r.get(fk)
            if raw is not None:
                return json.loads(raw)
            return None
        except Exception as exc:
            logger.debug("cache_redis_get_error", extra={"error": str(exc)})
    return _memory_get(fk)


def cache_set(namespace: str, key: str, value: Any, ttl_seconds: int = 3_600) -> None:
    """Store value in cache."""
    fk = _full_key(namespace, key)
    r = _get_redis()
    if r is not None:
        try:
            r.setex(fk, ttl_seconds, json.dumps(value, default=str))
            return
        except Exception as exc:
            logger.debug("cache_redis_set_error", extra={"error": str(exc)})
    _memory_set(fk, value, ttl_seconds)


def cache_delete(namespace: str, key: str) -> None:
    """Invalidate a cache entry."""
    fk = _full_key(namespace, key)
    r = _get_redis()
    if r is not None:
        try:
            r.delete(fk)
        except Exception:
            pass
    _memory_delete(fk)


# Convenience TTL constants
TTL_FOOD_NUTRITION = 86_400     # 24 h — nutrition data rarely changes
TTL_FOOD_SEARCH = 3_600         # 1 h — recipe/product search
TTL_DIETARY_PROFILE = 300       # 5 min — user profile
TTL_ANALYZE_RESPONSE = 300      # 5 min — AI analysis (same request, same result)
TTL_MEAL_ALTERNATIVES = 3_600   # 1 h — meal alternative suggestions
