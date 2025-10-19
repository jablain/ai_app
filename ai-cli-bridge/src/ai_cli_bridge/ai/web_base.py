"""Base class for web-based AIs using the stop-button pattern."""

import asyncio
import time
from abc import abstractmethod
from typing import Optional, Tuple, Dict, Any

from playwright.async_api import Page, TimeoutError as PWTimeout
from .base import BaseAI

try:
    import markdownify
except ImportError:
    markdownify = None


class WebAIBase(BaseAI):
    """
    Base class for web-based AI interfaces that follow the stop-button pattern.
    
    This covers AIs like Claude and Gemini that:
    - Use contenteditable input boxes
    - Show a "Stop" button during response generation
    - Hide the button when complete
    - Extract responses from markdown containers
    
    Subclasses must define selectors and AI-specific logic.
    """
    
    # =========================
    # Common timing constants
    # =========================
    
    RESPONSE_WAIT_S = 10.0
    COMPLETION_CHECK_INTERVAL_S = 0.2
    SNIPPET_LENGTH = 280
    SNIPPET_TRIM_WINDOW = 40
    
    # =========================
    # Abstract selectors (must be defined by subclass)
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
    # Shared implementation
    # =========================
    
    async def _execute_interaction(
        self,
        page: Page,
        message: str,
        wait_for_response: bool,
        timeout_s: int
    ) -> Tuple[bool, Optional[str], Optional[str], Optional[Dict[str, Any]]]:
        """Standard web AI interaction flow."""
        
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
            "page_url": page.url,
            "elapsed_ms": elapsed_ms,
            "waited": wait_for_response,
        }
        
        return True, snippet, markdown, metadata
    
    async def start_new_session(self, page: Page) -> bool:
        """Start a new chat session (standard implementation)."""
        try:
            button = page.locator(self.NEW_CHAT_BUTTON).first
            await button.wait_for(state="visible", timeout=5000)
            await button.click()
            
            await page.wait_for_selector(self.INPUT_BOX, state="visible", timeout=5000)
            return True
        except Exception:
            return False
    
    async def _ensure_chat_ready(self, page: Page) -> bool:
        """Ensure chat interface is ready for input."""
        # Navigate if needed
        if not page.url.startswith(self.get_base_url()):
            try:
                await page.goto(
                    self.get_base_url(),
                    wait_until="domcontentloaded",
                    timeout=10000
                )
            except Exception:
                return False
        
        # Wait for input box
        try:
            await page.wait_for_selector(self.INPUT_BOX, state="visible", timeout=5000)
            return True
        except PWTimeout:
            return False
    
    async def _send_message(self, page: Page, message: str) -> bool:
        """Send message to the AI."""
        try:
            await page.fill(self.INPUT_BOX, message, timeout=5000)
            await page.keyboard.press("Enter")
            return True
        except Exception:
            return False
    
    async def _wait_for_response_complete(self, page: Page, timeout_s: int) -> bool:
        """Wait for response to complete using stop-button pattern."""
        try:
            # Wait for stop button to appear
            await page.wait_for_selector(self.STOP_BUTTON, state="visible", timeout=10000)
            
            # Poll until it disappears
            deadline = time.time() + timeout_s
            while time.time() < deadline:
                if await page.locator(self.STOP_BUTTON).count() == 0:
                    return True
                await asyncio.sleep(self.COMPLETION_CHECK_INTERVAL_S)
            
            return False
        
        except PWTimeout:
            # Stop button never appeared (instant response)
            return True
        except Exception:
            return True
    
    async def _extract_response(
        self,
        page: Page,
        baseline_count: int
    ) -> Tuple[Optional[str], Optional[str]]:
        """Extract the last response from the page."""
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
        
        except Exception:
            return None, None
    
    async def _get_response_count(self, page: Page) -> int:
        """Get current count of response containers."""
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
    
    # =========================
    # Abstract stubs (not implemented for web AIs yet)
    # =========================
    
    async def list_messages(self) -> list[Dict[str, Any]]:
        raise NotImplementedError(f"list_messages not yet implemented for {self.__class__.__name__}")
    
    async def extract_message(self, index: int) -> Optional[str]:
        raise NotImplementedError(f"extract_message not yet implemented for {self.__class__.__name__}")
