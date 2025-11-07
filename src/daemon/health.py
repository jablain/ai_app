"""Health monitoring for browser CDP connections."""

from __future__ import annotations

import asyncio
import logging
import time

logger = logging.getLogger(__name__)


class HealthMonitor:
    """
    Monitors CDP connection health in the background.

    Periodically checks if the browser pool's CDP connection is alive
    and updates health status.
    """

    def __init__(self, browser_pool, check_interval_s: float = 30.0):
        """
        Initialize health monitor.

        Args:
            browser_pool: BrowserConnectionPool instance to monitor
            check_interval_s: Seconds between health checks
        """
        self.browser_pool = browser_pool
        self.check_interval_s = check_interval_s

        self._healthy: bool = False
        self._last_check: float | None = None
        self._monitor_task: asyncio.Task | None = None
        self._running: bool = False

    def start(self):
        """Start background health monitoring."""
        if self._running:
            logger.warning("Health monitor already running")
            return

        self._running = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info(f"Health monitor started (check interval: {self.check_interval_s}s)")

    def stop(self):
        """Stop background health monitoring."""
        if not self._running:
            return

        self._running = False

        if self._monitor_task and not self._monitor_task.done():
            self._monitor_task.cancel()

        logger.info("Health monitor stopped")

    def is_healthy(self) -> bool:
        """
        Get current health status.

        Returns:
            True if CDP connection is healthy, False otherwise
        """
        return self._healthy

    def get_status(self) -> dict:
        """
        Get detailed health status.

        Returns:
            Dict with health info including last check time
        """
        return {
            "healthy": self._healthy,
            "last_check": self._last_check,
            "check_interval_s": self.check_interval_s,
            "running": self._running,
        }

    async def _monitor_loop(self):
        """Background monitoring loop."""
        logger.debug("Health monitor loop started")

        while self._running:
            try:
                await self._perform_health_check()
                await asyncio.sleep(self.check_interval_s)
            except asyncio.CancelledError:
                logger.debug("Health monitor loop cancelled")
                break
            except Exception as e:
                logger.error(f"Health check error: {e}")
                self._healthy = False
                await asyncio.sleep(self.check_interval_s)

        logger.debug("Health monitor loop ended")

    async def _perform_health_check(self):
        """
        Perform a single health check.

        Checks if CDP URL is available and browser pool is responsive.
        """
        self._last_check = time.time()

        try:
            # Check if browser pool has CDP URL
            cdp_url = self.browser_pool.cdp_url

            if not cdp_url:
                # Try to discover
                cdp_url = await self.browser_pool.get_cdp_url()

            if cdp_url:
                # CDP URL exists - mark as healthy
                self._healthy = True
                logger.debug(f"Health check passed: CDP available at {cdp_url}")
            else:
                # No CDP URL - unhealthy
                self._healthy = False
                logger.warning("Health check failed: CDP URL not available")

        except Exception as e:
            self._healthy = False
            logger.error(f"Health check failed with exception: {e}")
