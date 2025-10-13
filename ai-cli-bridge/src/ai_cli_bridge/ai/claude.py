"""Claude-specific AI implementation."""

import asyncio
import time
from typing import Optional, Tuple, Dict, Any
from datetime import datetime, timezone

from playwright.async_api import async_playwright, Page, TimeoutError as PWTimeout
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
    
    # Base URL
    BASE_URL = "https://claude.ai"
    CDP_PORT = 9223  # ADD THIS
    
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
        self._session_start_time: Optional[float] = None
        self._message_count: int = 0
        self._last_page_url: Optional[str] = None
    
    # =========================
    # Public interface implementation
    # =========================
    
    async def send_prompt(
        self,
        message: str,
        wait_for_response: bool = True,
        timeout_s: int = 120
    ) -> Tuple[bool, Optional[str], Optional[str], Optional[Dict[str, Any]]]:
        """Send a prompt to Claude and optionally wait for response."""
        
        # Discover CDP connection
        ws_url, ws_source = await self._discover_cdp_url()
        
        if not ws_url:
            self._debug(f"CDP discovery failed: {ws_source}")
            return False, None, None, {"error": "no_cdp", "source": ws_source}
        
        self._debug(f"CDP connected via {ws_source}: {ws_url}")
        
        pw = await async_playwright().start()
        remote = None
        
        try:
            # Connect to browser
            remote = await pw.chromium.connect_over_cdp(ws_url)
            page = await self._pick_page(remote, self.BASE_URL)
            
            if not page:
                self._debug("No page found")
                return False, None, None, {"error": "no_page"}
            
            self._last_page_url = page.url
            self._debug(f"Operating on page: {page.url}")
            
            # Ensure chat is ready
            if not await self._ensure_chat_ready(page):
                self._debug("Chat interface not ready")
                return False, None, None, {"error": "chat_not_ready"}
            
            # Record baseline before sending
            baseline_count = await self._get_response_count(page)
            self._debug(f"Baseline response count: {baseline_count}")
            
            # Focus and clear input
            try:
                el = await page.wait_for_selector(self.INPUT_BOX, state="visible", timeout=5000)
                await el.click()
                await page.keyboard.press("Control+A")
                await page.keyboard.press("Backspace")
            except Exception as e:
                self._debug(f"Input focus failed: {e}")
                return False, None, None, {"error": "input_not_visible"}
            
            # Type message
            try:
                await page.keyboard.type(message, delay=self.TYPING_DELAY_MS)
            except Exception as e:
                self._debug(f"Typing failed: {e}")
                return False, None, None, {"error": "type_failed"}
            
            # Send via Enter
            try:
                await page.keyboard.press("Enter")
                self._debug("Message sent")
            except Exception as e:
                self._debug(f"Send failed: {e}")
                return False, None, None, {"error": "send_failed"}
            
            # Scroll to bottom
            try:
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            except Exception:
                pass
            
            snippet = None
            markdown = None
            elapsed_ms = None
            
            if wait_for_response:
                t0 = time.time()
                
                # Wait for completion
                self._debug("Waiting for response completion...")
                completed = await self._wait_for_response_complete(page, timeout_s)
                self._debug(f"Response complete: {completed}")
                
                if completed:
                    # Extract response
                    snippet, markdown = await self._extract_response(page, baseline_count)
                    self._debug(f"Extracted - snippet: {len(snippet) if snippet else 0} chars, markdown: {len(markdown) if markdown else 0} chars")
                
                elapsed_ms = int((time.time() - t0) * 1000)
            
            self._message_count += 1
            
            metadata = {
                "page_url": page.url,
                "elapsed_ms": elapsed_ms,
                "waited": wait_for_response,
                "ws_source": ws_source,
                "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            }
            
            return True, snippet, markdown, metadata
            
        finally:
            try:
                if remote:
                    await remote.close()
            except Exception:
                pass
            try:
                await pw.stop()
            except Exception:
                pass
    
    
    async def list_messages(self) -> list[Dict[str, Any]]:
        """List all messages in current conversation."""
        raise NotImplementedError("list_messages not yet implemented for Claude")
    
    
    async def extract_message(self, index: int) -> Optional[str]:
        """Extract full content of a specific message."""
        raise NotImplementedError("extract_message not yet implemented for Claude")
    
    
    async def get_status(self) -> Dict[str, Any]:
        """Get current session status."""
        # Actively discover CDP if not already known
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
            "debug_enabled": self.get_debug(),
        }
    
        if self._session_start_time:
            elapsed = time.time() - self._session_start_time
            status["session_duration_s"] = elapsed
    
        return status    
    
    # =========================
    # Claude-specific implementation (template methods)
    # =========================
    
    async def _ensure_chat_ready(self, page: Page) -> bool:
        """Ensure Claude chat interface is ready for input."""
        try:
            url = page.url or ""
        except Exception:
            url = ""
        
        # Navigate to /chat if not there
        if not url.startswith(f"{self.BASE_URL}/chat"):
            try:
                await page.goto(
                    f"{self.BASE_URL}/chat",
                    wait_until="domcontentloaded",
                    timeout=self.CHAT_NAV_TIMEOUT_MS
                )
                self._debug(f"Navigated to {self.BASE_URL}/chat")
            except Exception as e:
                self._debug(f"Navigation failed: {e}")
                pass
        
        # Quick check for composer
        try:
            el = await page.wait_for_selector(
                self.INPUT_BOX,
                state="visible",
                timeout=int(self.COMPOSER_CHECK_TIMEOUT_S * 1000)
            )
            if el:
                self._debug("Composer visible")
                return True
        except Exception:
            pass
        
        # Try clicking 'New chat' button
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
        
        # Final check
        try:
            el = await page.wait_for_selector(
                self.INPUT_BOX,
                state="visible",
                timeout=int(self.COMPOSER_CHECK_TIMEOUT_S * 1000)
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
            try:
                stop_button = page.locator(self.STOP_BUTTON)
                if await stop_button.count() > 0:
                    response_started = True
                    self._debug("Stop button visible - response started")
                    break
            except Exception:
                pass
            await asyncio.sleep(0.1)
        
        if not response_started:
            self._debug("Stop button never appeared (instant/cached response?)")
        
        # Phase 2: Wait for disabled send button (response complete)
        stable_since = None
        
        while time.time() < deadline:
            try:
                send_button = page.locator(self.SEND_BUTTON_DISABLED)
                
                if await send_button.count() > 0:
                    # Verify send icon present
                    has_icon = await send_button.locator(self.SEND_ICON_PATH).count() > 0
                    
                    if has_icon:
                        now = time.time()
                        
                        if stable_since is None:
                            stable_since = now
                            self._debug("Send button disabled - checking stability")
                        elif (now - stable_since) * 1000 >= self.BUTTON_STABILITY_MS:
                            self._debug(f"Stable for {self.BUTTON_STABILITY_MS}ms - complete")
                            return True
                    else:
                        stable_since = None
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
        # Selector for responses WITH content (avoids UI badges)
        content_responses_sel = f"{self.RESPONSE_CONTAINER}:has({self.RESPONSE_CONTENT})"
        
        try:
            # Wait for new response
            deadline = time.time() + self.RESPONSE_WAIT_S
            while time.time() < deadline:
                current_count = await page.locator(content_responses_sel).count()
                if current_count > baseline_count:
                    break
                await asyncio.sleep(0.2)
            
            # Get last response with content
            locator = page.locator(content_responses_sel)
            count = await locator.count()
            
            self._debug(f"Found {count} responses with content (baseline: {baseline_count})")
            
            if count == 0:
                return None, None
            
            last_response = locator.last
            content = last_response.locator(self.RESPONSE_CONTENT)
            
            # Get HTML
            html = await content.inner_html()
            
            if not html or len(html) < 10:
                return None, None
            
            # Strip UI chrome
            cleaned_html = await page.evaluate("""
                (html) => {
                    const temp = document.createElement('div');
                    temp.innerHTML = html;
                    
                    const selectors = [
                        'button',
                        '[role="button"]',
                        '[data-testid*="toolbar"]',
                        '[data-testid*="menu"]',
                        '[aria-label*="Copy"]',
                        '[aria-label*="Retry"]',
                    ];
                    
                    selectors.forEach(sel => {
                        temp.querySelectorAll(sel).forEach(el => el.remove());
                    });
                    
                    return temp.innerHTML;
                }
            """, html)
            
            # Convert to markdown
            markdown = None
            if markdownify:
                markdown = markdownify.markdownify(cleaned_html, heading_style="ATX")
                markdown = markdown.strip()
            else:
                # Fallback: plain text
                text = await content.inner_text()
                markdown = text.strip()
            
            # Create snippet
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
        content_responses_sel = f"{self.RESPONSE_CONTAINER}:has({self.RESPONSE_CONTENT})"
        
        try:
            return await page.locator(content_responses_sel).count()
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
            cut.rfind("\n"),
            cut.rfind(" "),
            cut.rfind("."),
            cut.rfind("!"),
            cut.rfind("?")
        )
        
        if last_break >= self.SNIPPET_LENGTH - self.SNIPPET_TRIM_WINDOW:
            return cut[:last_break].rstrip() + " …"
        
        return cut + " …"


# Register ClaudeAI with factory
AIFactory.register("claude", ClaudeAI)
