"""
Load balancer — weighted-round-robin with passive health awareness.

Picks the next healthy backend based on configured weights.  Backends that
have been marked *unhealthy* by the HealthChecker are skipped until they
recover.
"""

from __future__ import annotations

import asyncio
import itertools
import random
from typing import Dict, List, Optional

from config import BackendConfig, get_config
from models import BackendHealth, BackendStatus


class LoadBalancer:
    """
    Weighted-round-robin load balancer.

    Typical setup::

        lb = LoadBalancer()
        # On each health-check tick:
        lb.update_health(backend_name="deepseek-main", health=BackendStatus(...))

        # On each request:
        backend = lb.pick()
    """

    def __init__(self, backends: Optional[List[BackendConfig]] = None) -> None:
        cfg = get_config()
        self._configs: List[BackendConfig] = backends or cfg.backends
        # Runtime state keyed by backend name
        self._status: Dict[str, BackendStatus] = {
            b.name: BackendStatus(name=b.name, base_url=b.base_url, weight=b.weight, tags=b.tags)
            for b in self._configs
        }

        # Build a weighted round-robin cycle
        self._cycle = self._build_cycle()

    # ── Public API ────────────────────────────
    def update_health(self, name: str, health: BackendHealth, latency_ms: float = 0.0) -> None:
        status = self._status.get(name)
        if status is None:
            return
        status.health = health
        status.latency_ms = latency_ms
        status.last_checked = __import__("datetime").datetime.utcnow()

    def pick(self) -> Optional[BackendConfig]:
        """Return the next healthy backend, or ``None`` if none are available."""
        for _ in range(len(self._configs) * 2):  # safety iterator limit
            name = next(self._cycle)
            st = self._status.get(name)
            if st is not None and st.health == BackendHealth.HEALTHY:
                config = next((c for c in self._configs if c.name == name), None)
                if config is not None:
                    st.active_requests += 1
                    return config
        return None  # all backends are unhealthy or missing

    def release(self, name: str) -> None:
        """Decrement the active-request counter after a backend call completes."""
        st = self._status.get(name)
        if st is not None:
            st.active_requests = max(0, st.active_requests - 1)

    def all_statuses(self) -> List[BackendStatus]:
        return list(self._status.values())

    def is_healthy(self, name: str) -> bool:
        st = self._status.get(name)
        return st is not None and st.health == BackendHealth.HEALTHY

    # ── Internal ──────────────────────────────
    def _build_cycle(self) -> itertools.cycle:
        """Build an infinite weighted round-robin iterator."""
        pool: List[str] = []
        for c in self._configs:
            pool.extend([c.name] * c.weight)
        random.shuffle(pool)  # avoid thundering-herd on startup
        return itertools.cycle(pool)

    def _rebuild_cycle(self) -> None:
        """Call after config changes (hot-reload scenario)."""
        self._cycle = self._build_cycle()
