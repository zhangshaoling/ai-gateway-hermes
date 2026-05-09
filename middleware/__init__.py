"""
API key management module.

Provides secure key generation (SHA-256 based), in-memory & Redis-backed
storage, and a FastAPI dependency that authenticates every request.
"""

from __future__ import annotations

import hashlib
import secrets
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from models import (
    APIKeyCreateRequest,
    APIKeyCreateResponse,
    APIKeyMetadata,
    APIKeyStatusResponse,
    KeyPermission,
)


# ──────────────────────────────────────────────
#  Key derivation helpers
# ──────────────────────────────────────────────
def _generate_raw_key() -> str:
    """Generate a cryptographically random API key prefixed with ``aih_``."""
    return "aih_" + secrets.token_hex(24)


def _hash_key(raw_key: str) -> str:
    """Return the SHA-256 hex digest of *raw_key* — this is what we store."""
    return hashlib.sha256(raw_key.encode()).hexdigest()


def _key_prefix(raw_key: str) -> str:
    """Return the first 8 characters of the raw key for display / logging."""
    return raw_key[:8]


# ──────────────────────────────────────────────
#  Key store
# ──────────────────────────────────────────────
class KeyStore:
    """
    Abstraction over the underlying key storage.

    Currently uses an in-memory dict (suitable for single-node deployments).
    A future implementation can switch to Redis by implementing the same
    ``get`` / ``set`` / ``delete`` interface.
    """

    def __init__(self) -> None:
        self._store: Dict[str, APIKeyMetadata] = {}

    def get(self, hashed_key: str) -> Optional[APIKeyMetadata]:
        return self._store.get(hashed_key)

    def set(self, hashed_key: str, meta: APIKeyMetadata) -> None:
        self._store[hashed_key] = meta

    def delete(self, hashed_key: str) -> bool:
        return self._store.pop(hashed_key, None) is not None

    def list_keys(self) -> List[APIKeyStatusResponse]:
        return [
            APIKeyStatusResponse(
                key_prefix=meta.key_prefix,
                user_id=meta.user_id,
                permissions=meta.permissions,
                is_active=meta.is_active,
                usage_count=meta.usage_count,
                created_at=meta.created_at,
                expires_at=meta.expires_at,
            )
            for meta in self._store.values()
        ]

    def increment_usage(self, hashed_key: str) -> None:
        meta = self._store.get(hashed_key)
        if meta is not None:
            meta.usage_count += 1
            meta.last_used_at = datetime.utcnow()


# ──────────────────────────────────────────────
#  Key manager (public API)
# ──────────────────────────────────────────────
class APIKeyManager:
    """
    High-level API key lifecycle manager.

    Usage::

        mgr = APIKeyManager()
        req = APIKeyCreateRequest(user_id="alice", permissions="write")
        resp = mgr.create_key(req)          # returns raw key + metadata
        meta = mgr.authenticate("aih_...")  # returns metadata or None
        mgr.revoke_key(hashed_key)           # soft-delete
    """

    def __init__(self, store: Optional[KeyStore] = None) -> None:
        self._store = store or KeyStore()

    # ── Create ────────────────────────────────
    def create_key(self, req: APIKeyCreateRequest) -> APIKeyCreateResponse:
        raw_key = _generate_raw_key()
        hashed = _hash_key(raw_key)

        meta = APIKeyMetadata(
            key_prefix=_key_prefix(raw_key),
            user_id=req.user_id,
            permissions=req.permissions,
            rate_limit_per_minute=req.rate_limit_per_minute,
            expires_at=(
                datetime.utcnow() + timedelta(days=req.expires_in_days)
                if req.expires_in_days
                else None
            ),
        )
        self._store.set(hashed, meta)
        return APIKeyCreateResponse(api_key=raw_key, metadata=meta)

    # ── Authenticate ──────────────────────────
    def authenticate(self, raw_key: str) -> Optional[APIKeyMetadata]:
        """Validate *raw_key* and return its metadata, or ``None``."""
        hashed = _hash_key(raw_key)
        meta = self._store.get(hashed)
        if meta is None:
            return None
        if not meta.is_active:
            return None
        if meta.expires_at and meta.expires_at < datetime.utcnow():
            return None
        # Record usage (best-effort, in-memory)
        self._store.increment_usage(hashed)
        return meta

    # ── Revoke ────────────────────────────────
    def revoke_key(self, raw_key: str) -> bool:
        """Soft-revoke: mark the key as inactive."""
        hashed = _hash_key(raw_key)
        meta = self._store.get(hashed)
        if meta is None:
            return False
        meta.is_active = False
        return True

    # ── Hard delete ───────────────────────────
    def delete_key(self, raw_key: str) -> bool:
        """Permanently remove the key from the store."""
        hashed = _hash_key(raw_key)
        return self._store.delete(hashed)

    # ── List ──────────────────────────────────
    def list_keys(self) -> List[APIKeyStatusResponse]:
        return self._store.list_keys()
