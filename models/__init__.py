"""
Data models for API-key management, request/response schemas,
and health-status reporting.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ──────────────────────────────────────────────
#  API Key models
# ──────────────────────────────────────────────
class KeyPermission(str, Enum):
    """Granular permission levels for an API key."""

    READ = "read"
    WRITE = "write"
    ADMIN = "admin"


class APIKeyMetadata(BaseModel):
    """Persistent metadata associated with an API key."""

    key_prefix: str = Field(..., description="First 8 chars of the hashed key, for identification")
    user_id: str
    permissions: KeyPermission = KeyPermission.READ
    rate_limit_per_minute: int = 30
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    is_active: bool = True
    allowed_models: List[str] = Field(default_factory=list)
    """Empty list means all models are allowed."""

    usage_count: int = 0
    last_used_at: Optional[datetime] = None


class APIKeyCreateRequest(BaseModel):
    """Request body to create a new API key."""

    user_id: str
    permissions: KeyPermission = KeyPermission.READ
    rate_limit_per_minute: int = 30
    expires_in_days: Optional[int] = None


class APIKeyCreateResponse(BaseModel):
    """Response returned after key creation — contains the raw key once."""

    api_key: str = Field(..., description="Full API key — show this only once!")
    metadata: APIKeyMetadata


class APIKeyStatusResponse(BaseModel):
    """Public status info for a key (no secret material)."""

    key_prefix: str
    user_id: str
    permissions: KeyPermission
    is_active: bool
    usage_count: int
    created_at: datetime
    expires_at: Optional[datetime]


# ──────────────────────────────────────────────
#  Proxy / routing models
# ──────────────────────────────────────────────
class BackendHealth(str, Enum):
    UNKNOWN = "unknown"
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class BackendStatus(BaseModel):
    """Runtime status of a single upstream backend."""

    name: str
    base_url: str
    health: BackendHealth = BackendHealth.UNKNOWN
    latency_ms: float = 0.0
    active_requests: int = 0
    last_checked: Optional[datetime] = None
    consecutive_failures: int = 0
    weight: int = 1
    tags: List[str] = Field(default_factory=list)


class ProxyRequest(BaseModel):
    """The internal representation of a proxied upstream request."""

    method: str = "POST"
    path: str = "/v1/chat/completions"
    headers: Dict[str, str] = Field(default_factory=dict)
    body: Optional[Any] = None
    stream: bool = False


class ProxyResponse(BaseModel):
    """Normalised upstream response metadata (full body streamed out-of-band)."""

    status_code: int
    headers: Dict[str, str] = Field(default_factory=dict)
    backend_name: str
    latency_ms: float


# ──────────────────────────────────────────────
#  Health / status endpoints
# ──────────────────────────────────────────────
class HealthCheckResponse(BaseModel):
    """Top-level gateway health."""

    status: str = "ok"
    version: str = "1.0.0"
    uptime_sec: float = 0.0
    backends: List[BackendStatus] = Field(default_factory=list)


class MetricsSummary(BaseModel):
    """Lightweight metric snapshot for the /status endpoint."""

    total_requests: int = 0
    requests_last_minute: int = 0
    active_connections: int = 0
    error_rate: float = 0.0
    avg_latency_ms: float = 0.0
