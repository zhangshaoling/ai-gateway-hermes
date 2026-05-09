"""
FastAPI dependency for API key authentication.

Usage in a route::

    from middleware.auth import require_api_key, APIKeyMetadata

    @router.post("/v1/chat/completions")
    async def chat(meta: APIKeyMetadata = Depends(require_api_key)):
        ...
"""

from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from middleware import APIKeyManager, APIKeyMetadata

# Shared singleton — wired in during app startup via ``app.state``.
_key_manager: APIKeyManager | None = None
_security = HTTPBearer(auto_error=False)


def init_key_manager(mgr: APIKeyManager) -> None:
    global _key_manager
    _key_manager = mgr


# ──────────────────────────────────────────────
#  Dependency
# ──────────────────────────────────────────────
async def require_api_key(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_security),
) -> APIKeyMetadata:
    """
    FastAPI dependency that extracts the Bearer token from the
    ``Authorization`` header and looks it up in the key store.

    Raises ``401 Unauthorized`` on missing / invalid / expired keys.
    """
    # 1. Header
    raw_key: str | None = None
    if credentials is not None:
        raw_key = credentials.credentials

    # 2. Fallback: X-API-Key header (convenience for clients that cannot set Bearer)
    if raw_key is None:
        raw_key = request.headers.get("X-API-Key")

    if raw_key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key. Provide via Authorization: Bearer <key> or X-API-Key header.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    mgr = _key_manager
    if mgr is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Key manager not initialised.",
        )

    meta = mgr.authenticate(raw_key)
    if meta is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid, inactive, or expired API key.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return meta


# ──────────────────────────────────────────────
#  Optional auth (for public endpoints)
# ──────────────────────────────────────────────
async def optional_api_key(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_security),
) -> APIKeyMetadata | None:
    """Like ``require_api_key`` but returns ``None`` instead of raising."""
    raw_key: str | None = None
    if credentials is not None:
        raw_key = credentials.credentials
    if raw_key is None:
        raw_key = request.headers.get("X-API-Key")
    if raw_key is None or _key_manager is None:
        return None
    return _key_manager.authenticate(raw_key)
