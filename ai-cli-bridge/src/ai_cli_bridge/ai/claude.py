"""Claude-specific AI implementation."""

import asyncio
import time
from typing import Optional, Tuple, Dict, Any

from playwright.async_api import Page, TimeoutError as PWTimeout
from .base import BaseAI
from .factory import AIFactory

try:
    import markdownify
except ImportError:
    markdownify = None


class ClaudeAI(BaseAI):
    """
    Claude-specific implementation of browser automation.
    
    Handles Claude's UI patterns, selectors, and timing requirements.
    All configuration is self-contained - no external config files needed.
    """
    
    # =========================
    # Claude-specific constants
    # =========================
    
    # Base URL and CDP
    BASE_URL = "https://claude.ai"
    CDP_PORT = 9223 # Match your browser launch script
    
    # Timing
    STOP_BUTTON_WAIT_S = 3.0
    BUTTON_STABILITY_MS = 500
    RESPONSE_WAIT_S = 10.0
    NEW_CHAT_WAIT_S = 0.5
    COMPOSER_CHECK_TIMEOUT_S = 3.0
    TYPING_DELAY_MS = 30
    CHAT_NAV_TIMEOUT_MS = 10000
    
    # Content
    SNIPPET_LENGTH = 280
    SNIPPET_TRIM_WINDOW = 40
    
    # Claude selectors
    INPUT_BOX = "div[contenteditable='true']"
    SEND_BUTTON = "button[aria-label='Send message']"
    STOP_BUTTON = "button[aria-label='Stop response']"
    SEND_BUTTON_DISABLED = "button[aria-label='Send message'][disabled]"
    SEND_ICON_PATH = "svg path[d*='208.49,120.49']"
    RESPONSE_CONTAINER = ".font-claude-response"
    RESPONSE_CONTENT = ".standard-markdown"
    
    NEW_CHAT_BUTTONS = [
        "button[aria-label*='New chat']",
        "a[aria-label*='New chat']",
        "button:has-text('New chat')",
    ]

    # =========================
    # Class-level configuration
    # =========================
    
    @classmethod
    def get_default_config(cls) -> Dict[str, Any]:
        """Get Claude's default configuration."""
        return {
            "ai_target": "claude",
            "base_url": cls.BASE_URL,
            "cdp": {"port": cls.CDP_PORT}
        }
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize Claude AI instance."""
        super().__init__(config)
        self._message_count: int = 0
    
    # =========================
    # Abstract method implementations
    # =========================
    
    async def _execute_interaction(
        self,
        page: Page,
        message: str,
        wait_for_response: bool,
        timeout_s: int
    ) -> Tuple[bool, Optional[str], Optional[str], Optional[Dict[str, Any]]]:
        """Claude-specific implementation of the core interaction logic."""

        if not await self._ensure_chat_ready(page):
            self._debug("Chat interface not ready")
            return False, None, None, {"error": "chat_not_ready"}
        
        baseline_count = await self._get_response_count(page)
        self._debug(f"Baseline response count: {baseline_count}")
        
        # Focus, clear, and type message
        try:
            el = await page.wait_for_selector(self.INPUT_BOX, state="visible", timeout=5000)
            await el.click()
            await page.keyboard.press("Control+A")
            await page.keyboard.press("Backspace")
            await page.keyboard.type(message, delay=self.TYPING_DELAY_MS)
            await page.keyboard.press("Enter")
            self._debug("Message sent")
        except Exception as e:
            self._debug(f"Failed to send prompt: {e}")
            return False, None, None, {"error": "send_failed"}

        snippet, markdown, elapsed_ms = None, None, None
        
        if wait_for_response:
            t0 = time.time()
            
            self._debug("Waiting for response completion...")
            completed = await self._wait_for_response_complete(page, timeout_s)
            self._debug(f"Response complete signal: {completed}")
            
            if completed:
                snippet, markdown = await self._extract_response(page, baseline_count)
                self._debug(f"Extracted - snippet: {len(snippet) if snippet else 0} chars...")

            elapsed_ms = int((time.time() - t0) * 1000)
            
        self._message_count += 1
        
        metadata = {
            "page_url": page.url,
            "elapsed_ms": elapsed_ms,
            "waited": wait_for_response,
        }
        
        return True, snippet, markdown, metadata

    async def list_messages(self) -> list[Dict[str, Any]]:
        raise NotImplementedError("list_messages not yet implemented for Claude")

    async def extract_message(self, index: int) -> Optional[str]:
        raise NotImplementedError("extract_message not yet implemented for Claude")
    
    async def get_status(self) -> Dict[str, Any]:
        """Get current session status for Claude."""
        if self._cdp_url is None:
            await self._discover_cdp_url()
    
        ws_url, ws_source = self.get_cdp_info()
    
        status = {
            "ai_target": "claude",
            "connected": ws_url is not None,
            "cdp_source": ws_source,
            "cdp_url": ws_url,
            "last_page_url": self._last_page_url,
            "message_count": self._message_count,
            "turn_count": self.get_turn_count(),
            "debug_enabled": self.get_debug(),
        }
        return status
    
    # =========================
    # Claude-specific protected methods
    # =========================
    
    async def _ensure_chat_ready(self, page: Page) -> bool:
        """Ensure Claude chat interface is ready for input."""
        try:
            url = page.url or ""
        except Exception:
            url = ""
        
        if not url.startswith(f"{self.BASE_URL}/chat"):
            try:
                await page.goto(
                    f"{self.BASE_URL}/chat",
                    wait_until="domcontentloaded",
                    timeout=self.CHAT_NAV_TIMEOUT_MS
                )
                self._debug(f"Navigated to {self.BASE_URL}/chat")
            except Exception:
                pass
        
        try:
            el = await page.wait_for_selector(
                self.INPUT_BOX, state="visible", timeout=int(self.COMPOSER_CHECK_TIMEOUT_S * 1000)
            )
            if el:
                self._debug("Composer visible")
                return True
        except Exception:
            pass
        
        for sel in self.NEW_CHAT_BUTTONS:
            try:
                btn = await page.query_selector(sel)
                if btn and await btn.is_visible():
                    await btn.click()
                    await asyncio.sleep(self.NEW_CHAT_WAIT_S)
                    self._debug(f"Clicked new chat button: {sel}")
                    break
            except Exception:
                continue
        
        try:
            el = await page.wait_for_selector(
                self.INPUT_BOX, state="visible", timeout=int(self.COMPOSER_CHECK_TIMEOUT_S * 1000)
            )
            return bool(el)
        except Exception:
            return False
    
    
    async def _wait_for_response_complete(self, page: Page, timeout_s: int) -> bool:
        """Wait for Claude response to complete by watching button states."""
        deadline = time.time() + timeout_s
        
        # Phase 1: Wait for stop button (response started)
        stop_button_deadline = time.time() + self.STOP_BUTTON_WAIT_S
        response_started = False
        
        while time.time() < stop_button_deadline:
            if await page.locator(self.STOP_BUTTON).count() > 0:
                response_started = True
                self._debug("Stop button visible - response started")
                break
            await asyncio.sleep(0.1)
        
        if not response_started:
            self._debug("Stop button never appeared (instant/cached response?)")
        
        # Phase 2: Wait for disabled send button (response complete)
        stable_since = None
        
        while time.time() < deadline:
            try:
                send_button = page.locator(self.SEND_BUTTON_DISABLED)
                if await send_button.count() > 0 and await send_button.locator(self.SEND_ICON_PATH).count() > 0:
                    now = time.time()
                    if stable_since is None:
                        stable_since = now
                        self._debug("Send button disabled - checking stability")
                    elif (now - stable_since) * 1000 >= self.BUTTON_STABILITY_MS:
                        self._debug(f"Stable for {self.BUTTON_STABILITY_MS}ms - complete")
                        return True
                else:
                    stable_since = None
            except Exception:
                stable_since = None
            
            await asyncio.sleep(0.1)
        
        self._debug("Response completion timeout")
        return False
    
    
    async def _extract_response(
        self,
        page: Page,
        baseline_count: int
    ) -> Tuple[Optional[str], Optional[str]]:
        """Extract the last Claude response."""
        content_sel = f"{self.RESPONSE_CONTAINER}:has({self.RESPONSE_CONTENT})"
        
        try:
            # Wait for new response
            deadline = time.time() + self.RESPONSE_WAIT_S
            while time.time() < deadline:
                if await page.locator(content_sel).count() > baseline_count:
                    break
                await asyncio.sleep(0.2)
            
            last_response = page.locator(content_sel).last
            content = last_response.locator(self.RESPONSE_CONTENT)
            
            html = await content.inner_html()
            if not html or len(html) < 10:
                return None, None
            
            # Strip UI chrome via JavaScript
            cleaned_html = await page.evaluate("""
                (html) => {
                    const temp = document.createElement('div');
                    temp.innerHTML = html;
                    const selectors = ['button', '[role="button"]', '[data-testid*="toolbar"]', '[data-testid*="menu"]', '[aria-label*="Copy"]', '[aria-label*="Retry"]'];
                    selectors.forEach(sel => temp.querySelectorAll(sel).forEach(el => el.remove()));
                    return temp.innerHTML;
                }
            """, html)
            
            markdown = markdownify.markdownify(cleaned_html, heading_style="ATX").strip() if markdownify else (await content.inner_text()).strip()
            snippet = self._create_snippet(markdown)
            
            return snippet, markdown
            
        except Exception as e:
            self._debug(f"Extraction error: {e}")
            return None, None
    
    # =========================
    # Claude-specific helpers
    # =========================
    
    async def _get_response_count(self, page: Page) -> int:
        """Get current count of response bubbles with content."""
        content_sel = f"{self.RESPONSE_CONTAINER}:has({self.RESPONSE_CONTENT})"
        try:
            return await page.locator(content_sel).count()
        except Exception:
            return 0
    
    def _create_snippet(self, text: str) -> str:
        """Create smart-trimmed snippet from text."""
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

# Register ClaudeAI with factory
AIFactory.register("claude", ClaudeAI)
