"""Browser connection pool for managing CDP connections and page access."""

from __future__ import annotations

import asyncio
import json
import logging
import shlex
import subprocess
import urllib.request
from pathlib import Path
from typing import Any

from playwright.async_api import async_playwright, Browser, Page, Playwright

logger = logging.getLogger(__name__)


class BrowserConnectionPool:
    """
    Maintains one shared Playwright CDP connection and hands out pages that
    match a URL hint (e.g., 'claude.ai'). If none found, opens a new page and
    navigates to https://{hint}.

    Auto-launches browser with CDP if not already running.
    Uses config.cdp.cmd for browser command.
    """

    def __init__(self, config: dict[str, Any] | Any):
        """
        Initialize browser connection pool.

        Args:
            config: Either a dict or an AppConfig object (Pydantic model)
        """
        self.config = config

        # Helper to get config values (works with both dict and Pydantic models)
        def get_config(section: str, key: str, default: Any) -> Any:
            if hasattr(self.config, section):
                # Pydantic model with nested sections
                section_obj = getattr(self.config, section)
                if section_obj is not None:
                    return getattr(section_obj, key, default)
                return default
            elif isinstance(self.config, dict):
                # Plain dict
                section_dict = self.config.get(section, {})
                return section_dict.get(key, default)
            else:
                # Unknown config type, use defaults
                return default

        # CDP configuration (using YOUR schema)
        self._host: str = "127.0.0.1"
        self._port: int = int(get_config("cdp", "port", 9223))
        self._cmd: str = str(get_config("cdp", "cmd", "chromium"))
        self._profile_dir: str = str(get_config("cdp", "profile_dir", ""))
        self._start_timeout_s: float = float(get_config("cdp", "start_timeout_s", 15.0))
        self._probe_timeout_s: float = float(get_config("cdp", "probe_timeout_s", 2.0))

        # Expand profile dir if provided
        if self._profile_dir:
            self._profile_dir = str(Path(self._profile_dir).expanduser())

        # Log configuration
        logger.info(f"Browser command: {self._cmd}")
        if self._profile_dir:
            logger.info(f"  Profile dir: {self._profile_dir}")
        logger.info(f"  CDP port: {self._port}")

        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._cdp_url: str | None = None
        self._browser_process: subprocess.Popen | None = None
        self._lock = asyncio.Lock()

    # --- lifecycle ---------------------------------------------------------

    async def start(self) -> None:
        """Start browser pool - auto-launch browser if CDP not available."""
        logger.info("Starting browser connection pool...")
        async with self._lock:
            if self._playwright and self._browser:
                logger.info("Browser pool already started")
                return

            # Initialize Playwright
            self._playwright = await async_playwright().start()
            logger.info("Playwright initialized")

            # Try to discover existing CDP endpoint
            self._cdp_url = await self._discover_cdp_ws()

            # If no CDP found, launch browser
            if not self._cdp_url:
                logger.info("No running CDP browser found - launching browser...")
                success = await self._launch_browser()

                if not success:
                    raise RuntimeError(
                        f"Failed to launch browser with command: {self._cmd}. "
                        "Check cdp.cmd in config."
                    )

                # Wait and retry discovery
                logger.info(f"Waiting up to {self._start_timeout_s}s for browser to start...")
                await asyncio.sleep(min(2.0, self._start_timeout_s))

                # Retry discovery with timeout
                start_time = asyncio.get_event_loop().time()
                while (asyncio.get_event_loop().time() - start_time) < self._start_timeout_s:
                    self._cdp_url = await self._discover_cdp_ws()
                    if self._cdp_url:
                        logger.info("CDP endpoint discovered")
                        break
                    await asyncio.sleep(0.5)

            if not self._cdp_url:
                raise RuntimeError(
                    f"CDP WebSocket URL not discovered after {self._start_timeout_s}s. "
                    f"Check if browser started successfully on port {self._port}."
                )

            # Connect to CDP
            self._browser = await self._playwright.chromium.connect_over_cdp(self._cdp_url)
            logger.info(f"Connected to CDP: {self._cdp_url}")
            logger.info("Browser connection pool started successfully")

    async def stop(self) -> None:
        """Stop browser pool and optionally terminate launched browser."""
        logger.info("Stopping browser connection pool...")
        async with self._lock:
            try:
                if self._browser:
                    await self._browser.close()
            except Exception as e:
                logger.warning(f"Error closing browser: {e}")
            finally:
                self._browser = None

            try:
                if self._playwright:
                    await self._playwright.stop()
            except Exception as e:
                logger.warning(f"Error stopping Playwright: {e}")
            finally:
                self._playwright = None

            # Terminate browser process if we launched it
            if self._browser_process:
                try:
                    logger.info("Terminating launched browser process and children...")
                    # Get the process group ID (since we used start_new_session=True)
                    import os
                    import signal
                    pgid = os.getpgid(self._browser_process.pid)
                    logger.debug(f"Killing process group {pgid}")
                    
                    # Kill the entire process group (parent + all children)
                    try:
                        os.killpg(pgid, signal.SIGTERM)
                        # Wait for graceful shutdown
                        self._browser_process.wait(timeout=5)
                        logger.info("Browser process group terminated gracefully")
                    except subprocess.TimeoutExpired:
                        logger.warning("Browser didn't terminate gracefully, force killing...")
                        os.killpg(pgid, signal.SIGKILL)
                        self._browser_process.wait()
                        logger.info("Browser process group killed")
                except ProcessLookupError:
                    logger.debug("Browser process already gone")
                except Exception as e:
                    logger.warning(f"Error terminating browser process: {e}")
                finally:
                    self._browser_process = None

            logger.info("Browser pool stopped")

    async def close_all(self) -> None:
        """Alias for older callers"""
        await self.stop()

    # --- browser launch ----------------------------------------------------

    async def _launch_browser(self) -> bool:
        """
        Launch browser with CDP enabled using config.cdp.cmd.

        Returns:
            True if launch succeeded, False otherwise
        """
        try:
            # Parse the command string (handles "flatpak run APP_ID" etc.)
            cmd_parts = shlex.split(self._cmd)

            # Build full command with CDP flags
            cmd = cmd_parts.copy()

            # Add CDP port
            cmd.append(f"--remote-debugging-port={self._port}")

            # Add profile dir if specified
            if self._profile_dir:
                cmd.append(f"--user-data-dir={self._profile_dir}")

            # Add stability flags
            cmd.extend(
                [
                    "--no-first-run",
                    "--no-default-browser-check",
                    "--disable-background-networking",
                    "--disable-background-timer-throttling",
                    "--disable-backgrounding-occluded-windows",
                    "--disable-breakpad",
                    "--disable-component-extensions-with-background-pages",
                    "--disable-dev-shm-usage",
                    "--disable-extensions",
                    "--disable-features=TranslateUI",
                    "--disable-ipc-flooding-protection",
                    "--disable-renderer-backgrounding",
                    "--enable-features=NetworkService,NetworkServiceInProcess",
                    "--force-color-profile=srgb",
                    "--metrics-recording-only",
                ]
            )

            # Add startup URLs (opens tabs at launch)
            start_urls_cfg = getattr(self.config, "cdp", None)
            if start_urls_cfg and hasattr(start_urls_cfg, "start_urls"):
                start_urls = start_urls_cfg.start_urls
                if hasattr(start_urls, "claude"):
                    cmd.append(start_urls.claude)
                if hasattr(start_urls, "gemini"):
                    cmd.append(start_urls.gemini)
                if hasattr(start_urls, "chatgpt"):
                    cmd.append(start_urls.chatgpt)

            logger.debug(f"Launching browser: {' '.join(cmd)}")

            # Launch browser process
            self._browser_process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,  # Detach from parent
            )

            logger.info(f"Browser process launched (PID: {self._browser_process.pid})")
            return True

        except FileNotFoundError as e:
            logger.error(
                f"Browser command not found: {self._cmd}. " f"Check cdp.cmd in config. Error: {e}"
            )
            return False
        except Exception as e:
            logger.error(f"Failed to launch browser: {e}")
            return False

    # --- discovery / accessors --------------------------------------------

    @property
    def cdp_url(self) -> str | None:
        return self._cdp_url

    async def get_cdp_url(self) -> str | None:
        if self._cdp_url:
            return self._cdp_url
        self._cdp_url = await self._discover_cdp_ws()
        return self._cdp_url

    async def _discover_cdp_ws(self) -> str | None:
        """Query http://host:port/json/version to get webSocketDebuggerUrl."""
        url = f"http://{self._host}:{self._port}/json/version"

        def _probe() -> str | None:
            try:
                with urllib.request.urlopen(url, timeout=self._probe_timeout_s) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    ws = data.get("webSocketDebuggerUrl")
                    if ws and (ws.startswith("ws://") or ws.startswith("wss://")):
                        return ws
            except Exception as e:
                logger.debug(f"CDP probe failed at {url}: {e}")
            return None

        result = await asyncio.to_thread(_probe)
        if result:
            logger.debug(f"CDP discovered: {result}")
        return result

    async def _ensure_connected(self) -> Browser:
        if not self._playwright or not self._browser:
            await self.start()
        assert self._browser is not None
        return self._browser

    # --- shim for new transports ---
    async def get_connection(self, _ws_url: str | None = None) -> Browser:
        """
        Compatibility shim for WebTransport: return the connected Browser.
        Ignores ws_url because this pool already manages a single CDP session.
        """
        return await self._ensure_connected()

    # --- page selection ----------------------------------------------------

    async def get_page(self, cdp_url: str, page_url_hint: str) -> Page | None:
        """
        Return a Page whose URL contains page_url_hint (case-insensitive).
        If none exists, create a new page and navigate to https://{hint}.
        """
        async with self._lock:
            browser = await self._ensure_connected()

            # If the caller passes a different CDP URL, log but keep current connection.
            if self._cdp_url and cdp_url and (self._cdp_url != cdp_url):
                logger.debug(
                    "Requested CDP differs (using existing): %s != %s",
                    cdp_url,
                    self._cdp_url,
                )

            hint = (page_url_hint or "").lower().strip()

            # Look across all contexts/pages
            pages: list[Page] = []
            for ctx in list(browser.contexts):
                try:
                    pages.extend(ctx.pages)
                except Exception:
                    continue

            for p in pages:
                try:
                    if hint and hint in (p.url or "").lower():
                        logger.debug("Reusing page: %s", p.url)
                        return p
                except Exception:
                    continue

            # No match → open a new page and navigate
            ctx = browser.contexts[0] if browser.contexts else await browser.new_context()
            page = await ctx.new_page()

            if hint and "." in hint and "://" not in hint:
                nav_url = f"https://{hint}"
            else:
                nav_url = page_url_hint if "://" in page_url_hint else f"https://{page_url_hint}"

            try:
                await page.goto(nav_url, wait_until="domcontentloaded", timeout=30000)
                logger.info("Opened new page at %s", nav_url)
            except Exception as e:
                logger.warning("Failed to navigate to %s: %s", nav_url, e)

            return page

    # --- debugging ---------------------------------------------------------

    async def list_pages(self) -> list[dict[str, str]]:
        info: list[dict[str, str]] = []
        async with self._lock:
            if not self._playwright or not self._browser:
                return info
            try:
                for ctx in self._browser.contexts:
                    for p in ctx.pages:
                        try:
                            title = await p.title()
                        except Exception:
                            title = ""
                        info.append({"url": p.url, "title": title})
            except Exception as e:
                logger.error("Failed to list pages: %s", e)
        return info
