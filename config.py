"""
AI Gateway Hermes — Configuration Management.

Loads settings from environment variables (preferred) or a YAML config file.
The GatewayConfig class is frozen to prevent runtime mutation after startup.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, List, Optional

import yaml
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# ──────────────────────────────────────────────
#  Upstream backend definition
# ──────────────────────────────────────────────
class BackendConfig(BaseSettings):
    """A single upstream AI service backend."""

    name: str = "default"
    """Human-readable label (used in metrics & logs)."""

    base_url: str = "http://localhost:8001"
    """Full URL of the backend, e.g. http://10.0.1.42:8080/v1."""

    weight: int = 1
    """Relative routing weight for weighted-round-robin (default 1)."""

    max_connections: int = 100
    """Max concurrent connections allowed to this backend."""

    health_path: str = "/health"
    """Endpoint used for liveness checks, e.g. /health or /v1/health."""

    api_key: Optional[str] = None
    """Optional static API key sent as Bearer token to upstream."""

    tags: List[str] = Field(default_factory=list)
    """Arbitrary tags for filtering (e.g. ["gpt-4", "vision"])."""


# ──────────────────────────────────────────────
#  Global gateway configuration
# ──────────────────────────────────────────────
class GatewayConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="HERMES_",
        env_nested_delimiter="__",
        extra="ignore",
        frozen=True,
    )

    # ── Server ─────────────────────────────────
    host: str = "0.0.0.0"
    port: int = 8080
    workers: int = 4
    log_level: str = "INFO"
    request_timeout_sec: float = 60.0

    # ── API Keys ───────────────────────────────
    # Static key-store directory (YAML files); falls back to env if empty.
    keys_dir: str = "config/keys"
    master_api_key: str = "hermes-master-key-change-me"

    # ── Rate limit ────────────────────────────
    rate_limit_per_minute: int = 60
    rate_limit_per_user_per_minute: int = 30

    # ── Backends ──────────────────────────────
    backends: List[BackendConfig] = Field(default_factory=lambda: [
        BackendConfig(name="deepseek-main", base_url="https://api.deepseek.com/v1"),
        BackendConfig(name="deepseek-fallback", base_url="https://api.deepseek.com/v1", weight=2),
    ])

    # ── Health check ──────────────────────────
    health_check_interval_sec: int = 10
    health_check_timeout_sec: float = 5.0
    unhealthy_threshold: int = 3       # consecutive failures before marking DOWN
    healthy_threshold: int = 2          # consecutive successes before marking UP again

    # ── Redis (optional cache / rate-limit backend) ─
    redis_url: Optional[str] = None     # e.g. redis://localhost:6379/0

    # ── Prometheus ────────────────────────────
    metrics_enabled: bool = True
    metrics_path: str = "/metrics"

    # ── Proxy behaviour ──────────────────────
    max_retries: int = 2
    retry_backoff_base_sec: float = 0.5
    streaming_enabled: bool = True

    # ── Forwarded headers ─────────────────────
    forward_headers: bool = True
    additional_forward_headers: List[str] = Field(default_factory=lambda: [
        "x-request-id",
        "x-trace-id",
        "x-user-id",
    ])

    # ──────────────────────────────────────────
    #  Helper accessors
    # ──────────────────────────────────────────
    def get_backend_by_name(self, name: str) -> Optional[BackendConfig]:
        return next((b for b in self.backends if b.name == name), None)

    @property
    def healthy_backends(self) -> List[BackendConfig]:
        """Return all backends — actual health state is managed by the
        HealthChecker at runtime; this is a static view."""
        return list(self.backends)


# ──────────────────────────────────────────────
#  Singleton loader
# ──────────────────────────────────────────────
_CONFIG: Optional[GatewayConfig] = None


def load_config(path: Optional[str] = None) -> GatewayConfig:
    """
    Load the gateway configuration.

    Priority:
      1. Environment variables (HERMES_* prefix)
      2. YAML file (if *path* is given and exists)
      3. pydantic-settings defaults
    """
    global _CONFIG

    overrides: Dict = {}

    # Try YAML file first
    if path and Path(path).exists():
        with open(path, "r") as fh:
            raw = yaml.safe_load(fh) or {}
        overrides.update(raw)

    # Environment variables take precedence
    _CONFIG = GatewayConfig(**overrides)
    return _CONFIG


def get_config() -> GatewayConfig:
    """Return the cached config singleton (loads defaults on first call)."""
    global _CONFIG
    if _CONFIG is None:
        _CONFIG = load_config()
    return _CONFIG
