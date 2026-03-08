"""
SnapDish configuration: production-first, enterprise standards.

Production (AWS_SECRET_NAME set):
  - OPENAI_API_KEY is read only from AWS Secrets Manager. No .env or process env fallback.
  - CORS must be explicit (SNAPDISH_CORS_ORIGINS). No wildcard.
  - Structured JSON logging for CloudWatch (SNAPDISH_LOG_JSON=1).

Secrets in AWS: JSON e.g. {"OPENAI_API_KEY": "sk-..."}. Optionally include SNAPDISH_MODEL.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

# ---------------------------------------------------------------------------
# Production vs dev
# ---------------------------------------------------------------------------

def is_production() -> bool:
    """True when running in production: AWS_SECRET_NAME is set; secrets come only from AWS."""
    return bool(os.environ.get("AWS_SECRET_NAME", "").strip())


# ---------------------------------------------------------------------------
# Secrets: AWS Secrets Manager only in production; no env fallback for API key
# ---------------------------------------------------------------------------

def _get_secrets_from_aws(secret_name: str, region: str | None) -> dict[str, str]:
    """Fetch secret from AWS Secrets Manager. Returns dict of key/value strings."""
    try:
        import boto3
        from botocore.exceptions import ClientError
    except ImportError:
        return {}
    client = boto3.client("secretsmanager", region_name=region or os.environ.get("AWS_REGION"))
    try:
        resp = client.get_secret_value(SecretId=secret_name)
    except ClientError as e:
        _log = logging.getLogger("snapdish")
        _log.warning("aws_secrets_fetch_failed", extra={"secret_name": secret_name, "error": str(e)})
        return {}
    raw = resp.get("SecretString") or ""
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"OPENAI_API_KEY": raw}


def get_secret(key: str, default: str | None = None) -> str | None:
    """
    Get a secret. Production: only from AWS Secrets Manager (AWS_SECRET_NAME).
    No fallback to os.environ for OPENAI_API_KEY in production.
    """
    secret_name = os.environ.get("AWS_SECRET_NAME", "").strip()
    if secret_name:
        secrets = _get_secrets_from_aws(secret_name, os.environ.get("AWS_REGION"))
        val = secrets.get(key)
        if val is not None:
            return str(val)
        return default
    return os.environ.get(key, default)


def get_env(key: str, default: str | None = None) -> str | None:
    """Non-sensitive config from environment only."""
    return os.environ.get(key, default)


# ---------------------------------------------------------------------------
# Structured logging (CloudWatch-friendly JSON when SNAPDISH_LOG_JSON=1)
# ---------------------------------------------------------------------------

class StructuredFormatter(logging.Formatter):
    """JSON formatter for production (e.g. CloudWatch Logs Insights)."""

    def format(self, record: logging.LogRecord) -> str:
        log_obj: dict[str, Any] = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)
        if getattr(record, "extra", None):
            log_obj.update(record.extra)
        return json.dumps(log_obj)


def get_logger(name: str | None = None) -> logging.Logger:
    """Root SnapDish logger. Configure once at app startup via configure_logging()."""
    return logging.getLogger(name or "snapdish")


def configure_logging(
    level: str | int = None,
    json_logs: bool | None = None,
) -> None:
    """
    Configure SnapDish logging. Call from main.py on startup.
    Production: set SNAPDISH_LOG_JSON=1 for CloudWatch.
    """
    if level is None:
        level = os.environ.get("SNAPDISH_LOG_LEVEL", "INFO")
    if json_logs is None:
        json_logs = os.environ.get("SNAPDISH_LOG_JSON", "").strip() in ("1", "true", "yes")
    root = logging.getLogger("snapdish")
    root.setLevel(getattr(logging, str(level).upper(), logging.INFO))
    if not root.handlers:
        handler = logging.StreamHandler()
        if json_logs:
            handler.setFormatter(StructuredFormatter())
        else:
            handler.setFormatter(logging.Formatter("[%(levelname)s] %(name)s: %(message)s"))
        root.addHandler(handler)


# ---------------------------------------------------------------------------
# App config (non-secrets)
# ---------------------------------------------------------------------------

def get_model_id() -> str:
    return get_env("SNAPDISH_MODEL") or get_secret("SNAPDISH_MODEL") or "gpt-4o"


def get_cors_origins() -> list[str]:
    """
    CORS allowed origins. Production: SNAPDISH_CORS_ORIGINS is required (no wildcard).
    """
    raw = get_env("SNAPDISH_CORS_ORIGINS", "").strip()
    if is_production() and not raw:
        get_logger().warning("cors_not_configured", extra={"message": "SNAPDISH_CORS_ORIGINS required in production"})
        return []
    if not raw:
        raw = "*"
    return [o.strip() for o in raw.split(",") if o.strip()]


def get_max_analyze_batch_size() -> int:
    try:
        return int(get_env("SNAPDISH_MAX_BATCH_SIZE") or "100")
    except ValueError:
        return 100


def get_max_request_body_size_bytes() -> int:
    """Max request body size for /v1/analyze and /v1/voice (guardrail)."""
    try:
        return int(get_env("SNAPDISH_MAX_BODY_MB") or "10") * 1024 * 1024
    except ValueError:
        return 10 * 1024 * 1024


def get_rate_limit_rpm() -> int:
    """Max requests per minute per user/IP for analyze endpoints."""
    try:
        return int(get_env("SNAPDISH_RATE_LIMIT_RPM") or "60")
    except ValueError:
        return 60
