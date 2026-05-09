"""
Health checker — periodically pings upstream backends and reports status
to the LoadBalancer.

Uses a simple background asyncio task that fires at a configurable interval.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Optional

import httpx

from config import BackendConfig, get_config
from middleware.load_balancer import LoadBalancer
from models import BackendHealth

logger = logging.getLogger("hermes.health")


class HealthChecker:
    """
    Background health-check loop.

    Usage::

        hc = HealthChecker(lb)
        await hc.start()    # spawns a background task
        ...
        await hc.stop()     # cancels the task
    """

    def __init__(self, lb: LoadBalancer) -> None:
        self._lb = lb
        self._cfg = get_config()
        self._task: Optional[asyncio.Task] = None
        self._client: Optional[httpx.AsyncClient] = None

    # ── Lifecycle ─────────────────────────────
    async def start(self) -> None:
        if self._task is not None:
            return
        self._client = httpx.AsyncClient(timeout=self._cfg.health_check_timeout_sec)
        self._task = asyncio.create_task(self._loop())
        logger.info("Health checker started (interval=%ds)", self._cfg.health_check_interval_sec)

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        if self._client is not None:
            await self._client.aclose()
            self._client = None
        logger.info("Health checker stopped")

    # ── The loop ──────────────────────────────
    async def _loop(self) -> None:
        while True:
            try:
                await self._check_all()
            except Exception:
                logger.exception("Health-check cycle failed")
            await asyncio.sleep(self._cfg.health_check_interval_sec)

    async def _check_all(self) -> None:
        backends = get_config().backends
        tasks = [self._check_one(b) for b in backends]
        await asyncio.gather(*tasks)

    async def _check_one(self, backend: BackendConfig) -> None:
        assert self._client is not None
        url = backend.base_url.rstrip("/") + "/" + backend.health_path.lstrip("/")
        start = time.monotonic()
        try:
            resp = await self._client.get(url)
            latency = (time.monotonic() - start) * 1000  # ms
            if resp.is_success:
                self._record(backend.name, BackendHealth.HEALTHY, latency)
            else:
                logger.warning("Health-check %s returned %d", backend.name, resp.status_code)
                self._record(backend.name, BackendHealth.DEGRADED, latency)
        except (httpx.TimeoutException, httpx.ConnectError) as exc:
            logger.warning("Health-check %s failed: %s", backend.name, exc)
            self._record(backend.name, BackendHealth.UNHEALTHY, 0.0)

    def _record(self, name: str, health: BackendHealth, latency_ms: float) -> None:
        self._lb.update_health(name, health, latency_ms)
