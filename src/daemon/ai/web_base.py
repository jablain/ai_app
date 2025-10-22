"""Base class for web-based AIs using browser automation.

This module implements the BaseAI interface using Playwright and CDP
for browser automation. All web/browser-specific logic lives here.
"""

import asyncio
import time
from abc import abstractmethod
from typing import Optional, Tuple, Dict, Any

from playwright.async_api import Page, Browser, TimeoutError as PWTimeout
from .base import BaseAI

try:
    import markdownify
except ImportError:
    markdownify = None


class BrowserConnectionPool:
    """
    Manages persistent Playwright browser connections.
    
    This should be created once at the daemon level and injected
    into WebAIBase instances to enable connection reuse.
    Includes connection health checks for reliability.
    """
    
    def __init__(self):
        self._playwright = None
        self._connections: Dict[str, Browser] = {}
        self._lock = asyncio.Lock()
    
    async def get_connection(self, ws_url: str) -> Browser:
        """
        Get or create a browser connection to the given CDP URL.
        
        Includes health check to detect and recover from stale connections.
        
        Args:
            ws_url: WebSocket URL for CDP connection
            
        Returns:
            Connected browser instance
        """
        async with self._lock:
            # Lazy-initialize Playwright
            if not self._playwright:
                from playwright.async_api import async_playwright
                self._playwright = await async_playwright().start()
            
            # Check if we have an existing connection
            browser = self._connections.get(ws_url)
            
            if browser:
                # Health check: verify connection is alive
                try:
                    _ = browser.contexts
                    return browser
                except Exception:
                    # Connection is dead, remove it
                    del self._connections[ws_url]
            
            # Create new connection
            browser = await self._playwright.chromium.connect_over_cdp(ws_url)
            self._connections[ws_url] = browser
            return browser
    
    async def close_all(self):
        """Close all connections and stop Playwright."""
        for browser in self._connections.values():
            try:
                await browser.close()
            except Exception:
                pass  # Ignore errors during cleanup
        self._connections.clear()
        
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None


class WebAIBase(BaseAI):
    """
    Base class for AI implementations using web browser automation.
    
    This class adds all web-specific concepts:
    - CDP (Chrome DevTools Protocol) discovery and connection
    - Playwright browser/page management
    - DOM interaction (selectors, waiting, extraction)
    - Page navigation
    
    Subclasses must define:
    - Selector properties (INPUT_BOX, STOP_BUTTON, etc.)
    - AI-specific interaction logic (via overrides if needed)
    """
    
    # =========================
    # Common timing constants
    # =========================
    
    RESPONSE_WAIT_S = 10.0
    COMPLETION_CHECK_INTERVAL_S = 0.2
    SNIPPET_LENGTH = 280
    SNIPPET_TRIM_WINDOW = 40
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize web-based AI.
        
        Args:
            config: Configuration dict with web-specific settings:
                - base_url: AI website URL
                - cdp: CDP configuration (port, etc.)
                - selectors: DOM selector configuration (optional)
        """
        super().__init__(config)
        
        # Web-specific state
        self._cdp_url: Optional[str] = None
        self._cdp_source: Optional[str] = None
        self._last_page_url: Optional[str] = None
        
        # CDP URL caching (60 second TTL)
        self._cdp_cache: Optional[Tuple[str, str]] = None
        self._cdp_cache_time: float = 0
        self._cdp_cache_ttl: int = 60  # seconds
        
        # Browser connection pool (injected by daemon)
        self._browser_pool: Optional[BrowserConnectionPool] = None
    
    # =========================
    # Dependency Injection
    # =========================
    
    def set_browser_pool(self, pool: BrowserConnectionPool) -> None:
        """
        Inject the browser connection pool.
        
        This should be called by the daemon after creating the AI instance.
        
        Args:
            pool: Shared BrowserConnectionPool instance
        """
        self._browser_pool = pool
    
    # =========================
    # Implementation of BaseAI Interface
    # =========================
    
    async def send_prompt(
        self,
        message: str,
        wait_for_response: bool = True,
        timeout_s: int = 120
    ) -> Tuple[bool, Optional[str], Optional[str], Optional[Dict[str, Any]]]:
        """
        Web implementation of send_prompt using browser automation.
        
        Flow:
        1. Discover/connect to browser via CDP (with caching)
        2. Get appropriate page from browser
        3. Execute web-specific interaction (type, click, wait)
        4. Extract response from DOM
        5. Update session state
        
        Args:
            message: Text to send to the AI
            wait_for_response: Whether to wait for AI's reply
            timeout_s: Maximum time to wait for response
            
        Returns:
            Tuple of (success, snippet, full_response, metadata)
        """
        # Step 1: CDP Discovery (with caching)
        ws_url, ws_source = await self._get_cdp_url()
        if not ws_url:
            self._logger.error(f"CDP discovery failed: {ws_source}")
            return False, None, None, {"error": "no_cdp", "source": ws_source}
        
        self._logger.debug(f"CDP connected via {ws_source}: {ws_url}")
        
        # Step 2: Browser Connection
        if not self._browser_pool:
            self._logger.error("No browser pool configured")
            return False, None, None, {"error": "no_browser_pool"}
        
        try:
            browser = await self._browser_pool.get_connection(ws_url)
            page = await self._pick_page(browser, self._get_base_url())
            
            if not page:
                self._logger.error("No suitable page found")
                return False, None, None, {"error": "no_page"}
            
            self._last_page_url = page.url
            self._logger.debug(f"Operating on page: {page.url}")
            
            # Step 3: Execute Web Interaction
            success, snippet, markdown, metadata = await self._execute_web_interaction(
                page, message, wait_for_response, timeout_s
            )
            
            # Step 4: Update Session State
            if success and markdown:
                session_metadata = self._update_session_from_interaction(message, markdown)
                metadata.update(session_metadata)
            
            # Add web-specific metadata
            if metadata:
                metadata["ws_source"] = ws_source
                metadata["page_url"] = page.url
            
            return success, snippet, markdown, metadata
            
        except Exception as e:
            self._logger.error(f"Error in send_prompt: {e}", exc_info=True)
            return False, None, None, {"error": "exception", "message": str(e)}
    
    def get_transport_status(self) -> Dict[str, Any]:
        """
        Get web transport status.
        
        Returns connection details specific to web automation.
        
        Returns:
            Dictionary with web transport information
        """
        return {
            "transport_type": "web",
            "connected": self._cdp_url is not None,
            "cdp_url": self._cdp_url,
            "cdp_source": self._cdp_source,
            "last_page_url": self._last_page_url,
        }
    
    async def start_new_session(self) -> bool:
        """
        Start a new chat session (web implementation).
        
        Uses the current browser connection to click the "new chat" button
        and resets the session state.
        
        Returns:
            True if new session started successfully
        """
        try:
            # Get current browser connection
            ws_url, _ = await self._get_cdp_url()
            if not ws_url or not self._browser_pool:
                self._logger.error("Cannot start new session: no browser connection")
                return False
            
            browser = await self._browser_pool.get_connection(ws_url)
            page = await self._pick_page(browser, self._get_base_url())
            
            if not page:
                self._logger.error("Cannot start new session: no page found")
                return False
            
            # Click new chat button
            button = page.locator(self.NEW_CHAT_BUTTON).first
            await button.wait_for(state="visible", timeout=5000)
            await button.click()
            
            # Wait for input box to be ready
            await page.wait_for_selector(self.INPUT_BOX, state="visible", timeout=5000)
            
            # Reset session state
            self._reset_session_state()
            
            self._logger.info("Started new session successfully")
            return True
            
        except Exception as e:
            self._logger.error(f"Failed to start new session: {e}", exc_info=True)
            return False
    
    # =========================
    # CDP Discovery & Connection (with Caching)
    # =========================
    
    async def _get_cdp_url(self) -> Tuple[Optional[str], str]:
        """
        Get CDP URL with caching to reduce HTTP probes.
        
        Cache is valid for 60 seconds, then re-discovered.
        
        Returns:
            Tuple of (ws_url or None, source: 'env'|'discovered'|'none')
        """
        now = time.time()
        
        # Return cached value if still valid
        if self._cdp_cache and (now - self._cdp_cache_time) < self._cdp_cache_ttl:
            return self._cdp_cache
        
        # Cache expired or not present, discover CDP URL
        result = await self._discover_cdp_url()
        self._cdp_cache = result
        self._cdp_cache_time = now
        
        return result
    
    async def _discover_cdp_url(self) -> Tuple[Optional[str], str]:
        """
        Discover CDP WebSocket URL.
        
        Checks:
        1. Environment variable AI_CLI_BRIDGE_CDP_URL
        2. HTTP probe to http://127.0.0.1:<port>/json/version
        
        Returns:
            Tuple of (ws_url or None, source: 'env'|'discovered'|'none')
        """
        import os
        from urllib.request import urlopen
        from urllib.error import URLError, HTTPError
        import json
        
        # Check environment variable
        env = (os.environ.get("AI_CLI_BRIDGE_CDP_URL") or "").strip()
        if env.startswith(("ws://", "wss://")) and "/devtools/browser/" in env:
            self._cdp_url = env
            self._cdp_source = "env"
            self._logger.debug(f"CDP URL from environment: {env}")
            return env, "env"
        
        # Probe HTTP endpoint
        port = self._get_cdp_port()
        url = f"http://127.0.0.1:{port}/json/version"
        
        try:
            with urlopen(url, timeout=2.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                ws = (data.get("webSocketDebuggerUrl") or "").strip()
                if ws.startswith(("ws://", "wss://")) and "/devtools/browser/" in ws:
                    self._cdp_url = ws
                    self._cdp_source = "discovered"
                    self._logger.debug(f"CDP URL discovered: {ws}")
                    return ws, "discovered"
        except (URLError, HTTPError, TimeoutError, ValueError, json.JSONDecodeError) as e:
            self._logger.warning(f"CDP discovery failed: {e}")
        
        self._cdp_url = None
        self._cdp_source = "none"
        return None, "none"
    
    async def _pick_page(self, browser: Browser, base_url: Optional[str]) -> Optional[Page]:
        """
        Pick a page from browser contexts.
        
        Prefers pages matching base_url, else returns first page.
        
        Args:
            browser: Playwright browser instance
            base_url: Preferred base URL to match
            
        Returns:
            Page object or None
        """
        try:
            contexts = getattr(browser, "contexts", []) or []
            pages = []
            for ctx in contexts:
                pages.extend(getattr(ctx, "pages", []) or [])
            
            if base_url:
                for p in pages:
                    try:
                        if (p.url or "").startswith(base_url):
                            return p
                    except Exception:
                        continue
            
            return pages[0] if pages else None
        except Exception:
            return None
    
    # =========================
    # Configuration Helpers
    # =========================
    
    def _get_base_url(self) -> str:
        """Get base URL from config."""
        return self._config.get("base_url", "")
    
    def _get_cdp_port(self) -> int:
        """Get CDP port from config (default 9223)."""
        try:
            return int(self._config.get("cdp", {}).get("port", 9223))
        except Exception:
            return 9223
    
    # =========================
    # Abstract Selectors (must be defined by subclass)
    # =========================
    
    @property
    @abstractmethod
    def INPUT_BOX(self) -> str:
        """Selector for the message input box."""
        pass
    
    @property
    @abstractmethod
    def STOP_BUTTON(self) -> str:
        """Selector for the stop/cancel button during generation."""
        pass
    
    @property
    @abstractmethod
    def NEW_CHAT_BUTTON(self) -> str:
        """Selector for the new chat button."""
        pass
    
    @property
    @abstractmethod
    def RESPONSE_CONTAINER(self) -> str:
        """Selector for the response container element."""
        pass
    
    @property
    @abstractmethod
    def RESPONSE_CONTENT(self) -> str:
        """Selector for the actual response content within container."""
        pass
    
    # =========================
    # Web Interaction Flow
    # =========================
    
    async def _execute_web_interaction(
        self,
        page: Page,
        message: str,
        wait_for_response: bool,
        timeout_s: int
    ) -> Tuple[bool, Optional[str], Optional[str], Optional[Dict[str, Any]]]:
        """
        Execute the standard web interaction flow.
        
        Flow:
        1. Ensure chat is ready
        2. Get baseline response count
        3. Send message
        4. Wait for response completion
        5. Extract response
        
        Args:
            page: Playwright page object
            message: Message to send
            wait_for_response: Whether to wait for reply
            timeout_s: Maximum wait time
            
        Returns:
            Tuple of (success, snippet, full_markdown, metadata)
        """
        if not await self._ensure_chat_ready(page):
            return False, None, None, {"error": "chat_not_ready"}
        
        baseline_count = await self._get_response_count(page)
        
        if not await self._send_message(page, message):
            return False, None, None, {"error": "send_failed"}
        
        snippet, markdown, elapsed_ms = None, None, None
        
        if wait_for_response:
            t0 = time.time()
            
            completed = await self._wait_for_response_complete(page, timeout_s)
            
            if completed:
                snippet, markdown = await self._extract_response(page, baseline_count)
            
            elapsed_ms = int((time.time() - t0) * 1000)
        
        metadata = {
            "elapsed_ms": elapsed_ms,
            "waited": wait_for_response,
        }
        
        return True, snippet, markdown, metadata
    
    async def _ensure_chat_ready(self, page: Page) -> bool:
        """
        Ensure chat interface is ready for input.
        
        Args:
            page: Playwright page object
            
        Returns:
            True if ready, False otherwise
        """
        # Navigate if needed
        if not page.url.startswith(self._get_base_url()):
            try:
                await page.goto(
                    self._get_base_url(),
                    wait_until="domcontentloaded",
                    timeout=10000
                )
            except Exception as e:
                self._logger.error(f"Navigation failed: {e}")
                return False
        
        # Wait for input box
        try:
            await page.wait_for_selector(self.INPUT_BOX, state="visible", timeout=5000)
            return True
        except PWTimeout:
            self._logger.error("Input box not visible within timeout")
            return False
    
    async def _send_message(self, page: Page, message: str) -> bool:
        """
        Send message to the AI.
        
        Args:
            page: Playwright page object
            message: Message text to send
            
        Returns:
            True if sent successfully, False otherwise
        """
        try:
            await page.fill(self.INPUT_BOX, message, timeout=5000)
            await page.keyboard.press("Enter")
            return True
        except Exception as e:
            self._logger.error(f"Failed to send message: {e}")
            return False
    
    async def _wait_for_response_complete(self, page: Page, timeout_s: int) -> bool:
        """
        Wait for response to complete using stop-button pattern.
        
        Algorithm:
        1. Wait for stop button to appear
        2. Poll until it disappears
        3. Timeout if button stays visible too long
        
        Args:
            page: Playwright page object
            timeout_s: Maximum time to wait
            
        Returns:
            True if completion detected, False on timeout
        """
        try:
            # Wait for stop button to appear
            await page.wait_for_selector(self.STOP_BUTTON, state="visible", timeout=10000)
            
            # Poll until it disappears
            deadline = time.time() + timeout_s
            while time.time() < deadline:
                if await page.locator(self.STOP_BUTTON).count() == 0:
                    return True
                await asyncio.sleep(self.COMPLETION_CHECK_INTERVAL_S)
            
            self._logger.warning("Response timeout: stop button still visible")
            return False
        
        except PWTimeout:
            # Stop button never appeared (instant response)
            self._logger.debug("Stop button never appeared (instant response)")
            return True
        except Exception as e:
            self._logger.warning(f"Error waiting for completion: {e}")
            return True
    
    async def _extract_response(
        self,
        page: Page,
        baseline_count: int
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Extract the last response from the page.
        
        Args:
            page: Playwright page object
            baseline_count: Number of responses before sending prompt
            
        Returns:
            Tuple of (snippet, full_markdown) or (None, None)
        """
        content_sel = f"{self.RESPONSE_CONTAINER}:has({self.RESPONSE_CONTENT})"
        
        try:
            # Wait for new response
            deadline = time.time() + self.RESPONSE_WAIT_S
            while time.time() < deadline:
                if await page.locator(content_sel).count() > baseline_count:
                    break
                await asyncio.sleep(self.COMPLETION_CHECK_INTERVAL_S)
            
            # Get last response content
            last_response_content = page.locator(self.RESPONSE_CONTENT).last
            if await last_response_content.count() == 0:
                self._logger.warning("No response content found")
                return None, None
            
            html = await last_response_content.inner_html()
            if not html:
                return None, None
            
            # Convert to markdown
            if markdownify:
                markdown_text = markdownify.markdownify(html, heading_style="ATX").strip()
            else:
                markdown_text = await last_response_content.inner_text()
            
            snippet = self._create_snippet(markdown_text)
            
            return snippet, markdown_text
        
        except Exception as e:
            self._logger.error(f"Failed to extract response: {e}")
            return None, None
    
    async def _get_response_count(self, page: Page) -> int:
        """
        Get current count of response containers.
        
        Args:
            page: Playwright page object
            
        Returns:
            Number of response containers found
        """
        content_sel = f"{self.RESPONSE_CONTAINER}:has({self.RESPONSE_CONTENT})"
        try:
            return await page.locator(content_sel).count()
        except Exception:
            return 0
    
    def _create_snippet(self, text: str) -> str:
        """
        Create smart-trimmed snippet from text.
        
        Args:
            text: Full text to create snippet from
            
        Returns:
            Truncated text with ellipsis if needed
        """
        if not text:
            return ""
        
        if len(text) <= self.SNIPPET_LENGTH:
            return text
        
        cut = text[:self.SNIPPET_LENGTH]
        last_break = max(
            cut.rfind("\n"), cut.rfind(" "), cut.rfind("."),
            cut.rfind("!"), cut.rfind("?")
        )
        
        if last_break >= self.SNIPPET_LENGTH - self.SNIPPET_TRIM_WINDOW:
            return cut[:last_break].rstrip() + " …"
        
        return cut + " …"
    
    # =========================
    # Abstract stubs (not implemented for web AIs yet)
    # =========================
    
    async def list_messages(self) -> list[Dict[str, Any]]:
        """List messages - not yet implemented for web AIs."""
        raise NotImplementedError(
            f"list_messages not yet implemented for {self.__class__.__name__}"
        )
    
    async def extract_message(self, index: int) -> Optional[str]:
        """Extract message - not yet implemented for web AIs."""
        raise NotImplementedError(
            f"extract_message not yet implemented for {self.__class__.__name__}"
        )
