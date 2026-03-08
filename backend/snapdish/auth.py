"""
Enterprise JWT authentication for SnapDish.

Provider: AWS Cognito (RS256) — validated against the Cognito JWKS endpoint.
Development (AWS_SECRET_NAME not set): JWT payload decoded without signature
validation so local dev works without a Cognito pool.

Required secrets (AWS Secrets Manager in production, env vars in dev):
  COGNITO_REGION        — e.g. us-east-1
  COGNITO_USER_POOL_ID  — e.g. us-east-1_AbCdEfGhI
  COGNITO_CLIENT_ID     — Cognito App Client ID (audience claim)

FastAPI dependencies exported:
  get_current_user_id(request, credentials) -> str | None   (optional auth)
  require_auth(user_id)                     -> str           (enforced auth)
"""

from __future__ import annotations

import base64
import json
import os
import threading
import time
from typing import Optional

import httpx
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import get_logger, get_secret, is_production

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# JWKS cache — refreshed every hour, thread-safe
# ---------------------------------------------------------------------------

_JWKS_CACHE: dict[str, dict] = {}  # {cache_key: {"keys": [...], "ts": float}}
_JWKS_TTL = 3600.0
_JWKS_LOCK = threading.Lock()
_JWKS_CLIENTS: dict[str, object] = {}  # PyJWKClient instances keyed by user pool


def _get_cognito_config() -> tuple[str, str, str] | None:
    """Return (region, user_pool_id, client_id) or None if not fully configured."""
    region = get_secret("COGNITO_REGION") or os.environ.get("COGNITO_REGION", "")
    pool_id = get_secret("COGNITO_USER_POOL_ID") or os.environ.get("COGNITO_USER_POOL_ID", "")
    client_id = get_secret("COGNITO_CLIENT_ID") or os.environ.get("COGNITO_CLIENT_ID", "")
    if region and pool_id and client_id:
        return region.strip(), pool_id.strip(), client_id.strip()
    return None


# ---------------------------------------------------------------------------
# Cognito RS256 validation
# ---------------------------------------------------------------------------

def _validate_cognito_token(token: str, region: str, user_pool_id: str, client_id: str) -> dict:
    """
    Validate a Cognito-issued JWT.
    - Fetches the JWKS from Cognito (cached 1 hour, thread-safe).
    - Validates RS256 signature, expiry, issuer, and audience.
    Returns the decoded payload dict on success.
    Raises HTTPException 401 on any validation failure.
    """
    try:
        import jwt
        from jwt import PyJWKClient
    except ImportError as exc:
        logger.error("pyjwt_not_installed", extra={"error": str(exc)})
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service misconfigured — PyJWT not installed.",
        ) from exc

    jwks_url = f"https://cognito-idp.{region}.amazonaws.com/{user_pool_id}/.well-known/jwks.json"
    issuer = f"https://cognito-idp.{region}.amazonaws.com/{user_pool_id}"

    pool_key = f"{region}/{user_pool_id}"
    with _JWKS_LOCK:
        if pool_key not in _JWKS_CLIENTS:
            _JWKS_CLIENTS[pool_key] = PyJWKClient(
                jwks_url,
                cache_keys=True,
                cache_jwk_set=True,
                max_cached_keys=16,
                lifespan=int(_JWKS_TTL),
            )
        jwks_client = _JWKS_CLIENTS[pool_key]

    try:
        signing_key = jwks_client.get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=client_id,
            issuer=issuer,
            options={
                "verify_exp": True,
                "verify_iss": True,
                "verify_aud": True,
                "require": ["sub", "exp", "iss"],
            },
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has expired.")
    except jwt.InvalidAudienceError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token audience mismatch.")
    except jwt.InvalidIssuerError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token issuer mismatch.")
    except jwt.InvalidTokenError as exc:
        logger.warning("jwt_invalid", extra={"error": str(exc)})
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token.")


# ---------------------------------------------------------------------------
# Development fallback: decode without signature validation
# ---------------------------------------------------------------------------

def _dev_decode_sub(token: str) -> str | None:
    """
    Development ONLY: extract 'sub' from JWT payload without signature validation.
    Never used in production (guarded by is_production() check).
    """
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        padded = parts[1] + "=" * (-len(parts[1]) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded))
        return str(payload.get("sub") or payload.get("user_id") or "") or None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# FastAPI dependencies
# ---------------------------------------------------------------------------

_bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user_id(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
) -> str | None:
    """
    Extract and (in production) validate the user ID from the Bearer token.

    Flow:
      1. If Authorization: Bearer <token> present → validate (prod) or decode (dev).
      2. If X-SnapDish-User-ID header present → accept (for API Gateway pre-auth).
      3. Otherwise → return None (anonymous request allowed).

    Use require_auth() below to enforce authentication on protected endpoints.
    """
    token: str | None = None

    if credentials and credentials.scheme.lower() == "bearer":
        token = credentials.credentials
    else:
        # API Gateway / internal service pre-validated user ID header
        internal_id = request.headers.get("x-snapdish-user-id", "").strip()
        return internal_id or None

    if not token:
        return None

    cognito_config = _get_cognito_config()

    if is_production():
        if not cognito_config:
            logger.error("cognito_config_missing_in_production")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Authentication service not configured.",
            )
        region, user_pool_id, client_id = cognito_config
        payload = _validate_cognito_token(token, region, user_pool_id, client_id)
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token missing required sub claim.",
            )
        return str(user_id)
    else:
        # Development: decode without validation
        if cognito_config:
            # Cognito configured in dev — still validate properly
            region, user_pool_id, client_id = cognito_config
            try:
                payload = _validate_cognito_token(token, region, user_pool_id, client_id)
                return str(payload.get("sub") or "")
            except HTTPException:
                raise
        return _dev_decode_sub(token)


def require_auth(
    user_id: Optional[str] = Depends(get_current_user_id),
) -> str:
    """
    FastAPI dependency that enforces authentication.
    Raises HTTP 401 if no valid Bearer token is provided.

    Usage:
        @app.get("/v1/profile/dietary")
        def get_profile(user_id: str = Depends(require_auth)):
            ...
    """
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Include a valid Bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user_id
