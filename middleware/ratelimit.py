"""
Rate limiter wrapper around slowapi.

Provides a convenient ``@rate_limit`` decorator / dependency that can be
applied per-route or globally.
"""

from __future__ import annotations

from typing import Optional

from fastapi import Request, HTTPException, status
from slowapi import Limiter
from slowapi.util import get_remote_address

from config import get_config


def _key_func(request: Request) -> str:
    """
    Determine the rate-limit key for a request.

    Priority:
      1. Authenticated user ID (set by middleware)
      2. API key prefix (set by middleware)
      3. Client IP address
    """
    user_id: Optional[str] = getattr(request.state, "user_id", None)
    if user_id:
        return f"user:{user_id}"

    key_prefix: Optional[str] = getattr(request.state, "key_prefix", None)
    if key_prefix:
        return f"key:{key_prefix}"

    return get_remote_address(request)


# Shared limiter instance
limiter = Limiter(key_func=_key_func, default_limits=[])


def init_rate_limiter() -> None:
    """Called during app startup to configure limits from settings."""
    cfg = get_config()
    # Global rate limit is set on the app middleware, not on individual routes.
    limiter._default_limits = [f"{cfg.rate_limit_per_minute}/minute"]
