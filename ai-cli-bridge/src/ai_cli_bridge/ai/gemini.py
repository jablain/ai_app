"""Gemini-specific AI implementation."""

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


class GeminiAI(BaseAI):
    """
    Gemini-specific implementation of browser automation.
    
    Handles Gemini's UI patterns, selectors, and timing requirements.
    Completion is detected by observing the appearance and subsequent
    disappearance of the "Stop response" button.
    """
    
    # =========================
    # Gemini-specific constants
    # =========================
    
    # Base URL and CDP
    BASE_URL = "https://gemini.google.com"
    CDP_PORT = 9223 # Match your browser launch script
    
    # Timing
    RESPONSE_WAIT_S = 10.0
    COMPLETION_CHECK_INTERVAL_S = 0.2
    
    # Content
    SNIPPET_LENGTH = 280
    SNIPPET_TRIM_WINDOW = 40
    
    # Gemini selectors
    INPUT_BOX = "div.ql-editor[aria-label*='prompt']"
    STOP_BUTTON = "button[aria-label='Stop response']"
    RESPONSE_CONTAINER = "div.response-container-content"
    RESPONSE_CONTENT = "div.markdown"

    # =========================
    # Class-level configuration
    # =========================
    
    @classmethod
    def get_default_config(cls) -> Dict[str, Any]:
        """Get Gemini's default configuration."""
        return {
            "ai_target": "gemini",
            "base_url": cls.BASE_URL,
            "cdp": {"port": cls.CDP_PORT}
        }
        
    def __init__(self, config: Dict[str, Any]):
        """Initialize Gemini AI instance."""
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
        """Gemini-specific implementation of the core interaction logic."""
        
        if not await self._ensure_chat_ready(page):
            self._debug("Chat interface not ready")
            return False, None, None, {"error": "chat_not_ready"}
        
        baseline_count = await self._get_response_count(page)
        self._debug(f"Baseline response count: {baseline_count}")
        
        try:
            await page.fill(self.INPUT_BOX, message, timeout=5000)
            await page.keyboard.press("Enter")
            self._debug("Message sent via Enter key")
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
        raise NotImplementedError("list_messages not yet implemented for Gemini")

    async def extract_message(self, index: int) -> Optional[str]:
        raise NotImplementedError("extract_message not yet implemented for Gemini")

    async def get_status(self) -> Dict[str, Any]:
        """Get current session status for Gemini."""
        if self._cdp_url is None:
            await self._discover_cdp_url()
    
        ws_url, ws_source = self.get_cdp_info()
    
        status = {
            "ai_target": "gemini",
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
    # Gemini-specific protected methods
    # =========================
    
    async def _ensure_chat_ready(self, page: Page) -> bool:
        """
        Ensure Gemini chat interface is ready for input by checking the URL
        and waiting for the input box.
        """
        self._debug(f"Checking if page URL '{page.url}' is correct.")
        
        if not page.url.startswith(self.BASE_URL):
            self._debug(f"Page is not on Gemini. Attempting to navigate to {self.BASE_URL}")
            try:
                await page.goto(self.BASE_URL, wait_until="domcontentloaded", timeout=10000)
                self._debug("Navigation successful.")
            except Exception as e:
                self._debug(f"Navigation to Gemini failed: {e}")
                return False

        try:
            await page.wait_for_selector(self.INPUT_BOX, state="visible", timeout=5000)
            self._debug("Input box is visible, chat is ready.")
            return True
        except PWTimeout:
            self._debug("Timed out waiting for input box after ensuring correct URL.")
            return False

    async def _wait_for_response_complete(self, page: Page, timeout_s: int) -> bool:
        """
        Wait for Gemini response to complete by polling for the stop button's
        disappearance from within Python, respecting Trusted Type policies.
        """
        try:
            # Phase 1: Wait for the stop button to appear (response has started)
            self._debug("Waiting for stop button to appear...")
            await page.wait_for_selector(self.STOP_BUTTON, state="visible", timeout=10000)
            self._debug("Stop button appeared. Response generation has started.")
            
            # Phase 2: Poll from Python until the stop button is gone.
            self._debug("Polling until stop button disappears...")
            deadline = time.time() + timeout_s
            while time.time() < deadline:
                count = await page.locator(self.STOP_BUTTON).count()
                if count == 0:
                    self._debug("Stop button is gone. Response is complete.")
                    return True
                await asyncio.sleep(0.2)
            
            self._debug("Polling timed out. Stop button never disappeared.")
            return False

        except Exception as e:
            self._debug(f"An error occurred while waiting for completion: {e}")
            return True

    async def _extract_response(
        self,
        page: Page,
        baseline_count: int
    ) -> Tuple[Optional[str], Optional[str]]:
        """Extract the last Gemini response from the page."""
        try:
            deadline = time.time() + self.RESPONSE_WAIT_S
            while time.time() < deadline:
                current_count = await page.locator(self.RESPONSE_CONTAINER).count()
                if current_count > baseline_count:
                    break
                await asyncio.sleep(self.COMPLETION_CHECK_INTERVAL_S)
            
            last_response_content = page.locator(self.RESPONSE_CONTENT).last
            if await last_response_content.count() == 0:
                 self._debug("No markdown content found in the last response.")
                 return None, None
            
            html = await last_response_content.inner_html()
            
            if not html:
                return None, None
            
            markdown_text = ""
            if markdownify:
                markdown_text = markdownify.markdownify(html, heading_style="ATX").strip()
            else:
                markdown_text = await last_response_content.inner_text()
            
            snippet = self._create_snippet(markdown_text)
            
            return snippet, markdown_text
            
        except Exception as e:
            self._debug(f"Extraction error: {e}")
            return None, None
    
    # =========================
    # Gemini-specific helpers
    # =========================

    async def _get_response_count(self, page: Page) -> int:
        """Get current count of response containers."""
        return await page.locator(self.RESPONSE_CONTAINER).count()
        
    def _create_snippet(self, text: str) -> str:
        """Create a smart-trimmed snippet from text."""
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

# Register GeminiAI with the factory
AIFactory.register("gemini", GeminiAI)
