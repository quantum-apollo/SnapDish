"""
OpenAI client — enterprise-grade singleton for ~1M daily users.

Design principles:
  - API key: AWS Secrets Manager ONLY in production. No env fallback for the key.
  - Connection reuse: single httpx connection pool shared across all requests.
  - Adaptive retry: exponential backoff with jitter on 429 / 5xx (openai SDK built-in).
  - Timeouts: connect 10 s, read 120 s (long enough for streaming voice), no silent hangs.
  - HTTPS: enforced by the OpenAI SDK — all calls go to https://api.openai.com.
  - Thread-safe: singleton init is guarded with a lock; safe under FastAPI's threadpool.
  - Async client: separate async singleton for async endpoints (voice pipeline).

All capabilities — image analysis, text, voice STT/TTS, real-time, web search —
share the same OPENAI_API_KEY from AWS Secrets. No third-party fallback needed;
OpenAI is the fallback for everything.
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

from .config import get_logger, get_secret, is_production

if TYPE_CHECKING:
    from openai import AsyncOpenAI, OpenAI

logger = get_logger(__name__)

# Thread-safe singleton guards
_client: "OpenAI | None" = None
_async_client: "AsyncOpenAI | None" = None
_lock = threading.Lock()

# Enterprise timeouts (seconds)
_CONNECT_TIMEOUT = 10.0   # fail fast on network issues
_READ_TIMEOUT = 120.0     # allow long voice/streaming responses
_POOL_CONNECTIONS = 20    # httpx connection pool — tune per instance count
_MAX_RETRIES = 3          # SDK-level retry with exponential backoff + jitter


def _load_api_key() -> str:
    api_key = get_secret("OPENAI_API_KEY")
    if not api_key:
        if is_production():
            logger.error("OPENAI_API_KEY_missing_in_aws_secrets")
            raise RuntimeError(
                "OPENAI_API_KEY not found in AWS Secrets Manager. "
                "Add it to the secret named by AWS_SECRET_NAME."
            )
        raise RuntimeError(
            "OPENAI_API_KEY not set. In development, set it in your environment or .env file."
        )
    return api_key


def get_client() -> "OpenAI":
    """
    Return the shared sync OpenAI client. Thread-safe singleton.

    Used by: text analysis, image analysis, batch, food-api web-search fallback,
             nutrition analysis, moderation (guardrails), web search.

    Connection pool (httpx): _POOL_CONNECTIONS persistent HTTPS connections.
    Retry: up to _MAX_RETRIES on 429 / 502 / 503 with jitter.
    Timeout: _CONNECT_TIMEOUT connect, _READ_TIMEOUT read.
    All traffic: https://api.openai.com (SDK enforced, no HTTP downgrade possible).
    """
    global _client
    if _client is not None:
        return _client
    with _lock:
        if _client is None:
            import httpx
            from openai import OpenAI

            api_key = _load_api_key()
            transport = httpx.HTTPTransport(
                retries=_MAX_RETRIES,
                limits=httpx.Limits(
                    max_connections=_POOL_CONNECTIONS,
                    max_keepalive_connections=_POOL_CONNECTIONS,
                    keepalive_expiry=60,
                ),
            )
            http_client = httpx.Client(
                transport=transport,
                timeout=httpx.Timeout(
                    connect=_CONNECT_TIMEOUT,
                    read=_READ_TIMEOUT,
                    write=30.0,
                    pool=5.0,
                ),
                verify=True,  # TLS certificate verification — NEVER disable in production
            )
            _client = OpenAI(
                api_key=api_key,
                http_client=http_client,
                max_retries=_MAX_RETRIES,
                timeout=_READ_TIMEOUT,
            )
            logger.info(
                "openai_client_init",
                extra={
                    "pool_connections": _POOL_CONNECTIONS,
                    "max_retries": _MAX_RETRIES,
                    "connect_timeout": _CONNECT_TIMEOUT,
                    "read_timeout": _READ_TIMEOUT,
                },
            )
    return _client


def get_async_client() -> "AsyncOpenAI":
    """
    Return the shared async OpenAI client. Thread-safe singleton.

    Used by: voice pipeline (AsyncOpenAI is required by the Agents SDK VoicePipeline),
             real-time audio streaming endpoints.

    Same pool / retry / timeout configuration as the sync client.
    """
    global _async_client
    if _async_client is not None:
        return _async_client
    with _lock:
        if _async_client is None:
            import httpx
            from openai import AsyncOpenAI

            api_key = _load_api_key()
            async_transport = httpx.AsyncHTTPTransport(
                retries=_MAX_RETRIES,
                limits=httpx.Limits(
                    max_connections=_POOL_CONNECTIONS,
                    max_keepalive_connections=_POOL_CONNECTIONS,
                    keepalive_expiry=60,
                ),
            )
            async_http_client = httpx.AsyncClient(
                transport=async_transport,
                timeout=httpx.Timeout(
                    connect=_CONNECT_TIMEOUT,
                    read=_READ_TIMEOUT,
                    write=30.0,
                    pool=5.0,
                ),
                verify=True,
            )
            _async_client = AsyncOpenAI(
                api_key=api_key,
                http_client=async_http_client,
                max_retries=_MAX_RETRIES,
                timeout=_READ_TIMEOUT,
            )
            logger.info("openai_async_client_init")
    return _async_client


def reset_client() -> None:
    """For tests only: clear both singletons."""
    global _client, _async_client
    with _lock:
        _client = None
        _async_client = None
