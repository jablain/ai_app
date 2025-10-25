"""Gemini-specific AI implementation."""
import asyncio
import logging
from typing import Dict, Any, Tuple
from playwright.async_api import Page
from .web_base import WebAIBase
from .factory import AIFactory

logger = logging.getLogger(__name__)


class GeminiAI(WebAIBase):
    """Gemini-specific implementation using the web AI base."""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
    
    # =========================
    # Gemini configuration
    # =========================
    
    BASE_URL = "https://gemini.google.com"
    CDP_PORT = 9223
    
    # Class-level selector definitions (required by WebAIBase)
    INPUT_BOX = "div.ql-editor[contenteditable='true'], rich-textarea[aria-label*='prompt'], div[contenteditable='true'][aria-label*='prompt']"
    SEND_BUTTON = "button[aria-label*='Send'], button[mattooltip*='Send']"
    STOP_BUTTON = "button[aria-label*='Stop'], button[aria-label*='generat'], button[mattooltip*='Stop']"
    RESPONSE_CONTAINER = "message-content[data-model-role='model'], div[data-role='model-response']"
    
    # Additional Gemini-specific selectors
    NEW_CHAT_BUTTON = "a.new-chat-button, button[aria-label*='New chat']"
    RESPONSE_CONTENT = "div.markdown, div.model-response-text"
    MODEL_SELECTOR = "button[aria-label*='model'], div[class*='model-selector']"
    
    @classmethod
    def get_default_config(cls) -> Dict[str, Any]:
        """Get Gemini's default configuration."""
        return {
            "ai_target": "gemini",
            "base_url": cls.BASE_URL,
            "cdp": {"port": cls.CDP_PORT},
            "max_context_tokens": 2000000,  # Gemini 1.5 Pro context window
            "features": {
                "suspicious_scan": True
            }
        }
    
    # =========================
    # Required abstract methods
    # =========================
    
    def _get_page_url_hint(self) -> str:
        """
        Return URL hint for page selection.
        
        Supports both gemini.google.com and aistudio.google.com
        (AI Studio redirects to Gemini for some users).
        """
        return "gemini.google.com"

    async def start_new_session(self) -> bool:
        try:
            page = await self._get_or_open_page(self._get_page_url_hint())
            try:
                new_btn = page.locator("button:has-text('New chat'), a:has-text('New chat')")
                if await new_btn.count() > 0:
                    await new_btn.first.click()
                    return True
            except Exception:
                pass
            await page.goto(f"{self.BASE_URL}/app", wait_until="domcontentloaded", timeout=30000)
            return True
        except Exception as e:
            logger.error(f"{self.ai_target}: start_new_session failed: {e}")
            return False

    async def list_messages(self) -> list[dict]:
        items: list[dict] = []
        try:
            page = await self._get_or_open_page(self._get_page_url_hint())
            loc = page.locator(self.RESPONSE_CONTAINER)
            n = await loc.count()
            for i in range(n):
                try:
                    txt = await loc.nth(i).inner_text()
                    items.append({"role": "assistant", "text": (txt or "").strip()})
                except Exception:
                    continue
        except Exception as e:
            logger.error(f"{self.ai_target}: list_messages failed: {e}")
        return items

    async def extract_message(self, baseline_count: int = 0) -> dict:
        try:
            page = await self._get_or_open_page(self._get_page_url_hint())
            snippet, markdown = await self._extract_response(page, baseline_count)
            return {"snippet": snippet, "markdown": markdown}
        except Exception as e:
            logger.error(f"{self.ai_target}: extract_message failed: {e}")
            return {"snippet": "", "markdown": ""}

    
    async def _guess_model_name(self, page: Page) -> str | None:
        """
        Gemini-specific model name detection.
        
        Looks for model selector button or chip with model name.
        """
        if self._model_name_cache:
            return self._model_name_cache
        
        try:
            model_loc = page.locator(self.MODEL_SELECTOR)
            if await model_loc.count() > 0:
                txt = (await model_loc.first.inner_text() or "").strip()
                # Extract model name (e.g., "Gemini 1.5 Pro", "Gemini 2.0 Flash")
                if txt and 2 < len(txt) < 80:
                    self._model_name_cache = txt
                    logger.info(f"{self.ai_target}: Detected model: {txt}")
                    return txt
        except Exception as e:
            logger.debug(f"{self.ai_target}: Model detection failed: {e}")
        
        return await super()._guess_model_name(page)
    
    async def _get_response_count(self, page: Page) -> int:
        """
        Get current count of model response messages.
        
        Uses data-model-role or data-role to ensure we only count model responses.
        """
        try:
            responses = page.locator(self.RESPONSE_CONTAINER)
            count = await responses.count()
            return count
        except Exception:
            return 0
    
    async def _send_message(self, page: Page, message: str) -> bool:
        """
        Minimal, resilient send using fill() with a small fallback.
        """
        try:
            baseline = await self._get_response_count(page)

            # Primary: provider selector(s)
            loc = page.locator(self.INPUT_BOX)
            if await loc.count() > 0:
                await loc.first.fill(message, timeout=5000)
                await page.keyboard.press("Enter")
                await asyncio.sleep(0.3)
                if await self._get_response_count(page) > baseline:
                    return True

            # Fallback: generic editable selector
            fb = page.locator("div[contenteditable='true'], rich-textarea[aria-label], textarea, div[role='textbox']")
            if await fb.count() > 0:
                await fb.first.fill(message, timeout=5000)
                await page.keyboard.press("Enter")
                await asyncio.sleep(0.3)
                if await self._get_response_count(page) > baseline:
                    return True

            # Try explicit send button as last attempt
            send_button = page.locator(self.SEND_BUTTON)
            if await send_button.count() > 0:
                await send_button.first.click()
                await asyncio.sleep(0.3)
                if await self._get_response_count(page) > baseline:
                    return True

            logger.warning(f"{self.ai_target}: Send attempts did not produce a new response")
            return False

        except Exception as e:
            logger.error(f"{self.ai_target}: Failed to send message: {e}")
            return False
    
    async def _wait_for_response_complete(self, page: Page, timeout_s: float) -> bool:
        """
        Wait for Gemini's response to complete.
        
        Uses two strategies:
        1. Wait for stop button to disappear
        2. Wait for response count to stabilize
        """
        try:
            baseline = await self._get_response_count(page)
            start_time = asyncio.get_event_loop().time()
            
            while (asyncio.get_event_loop().time() - start_time) < timeout_s:
                # Check if stop button is visible
                stop_button = page.locator(self.STOP_BUTTON)
                stop_visible = await stop_button.count() > 0
                
                if stop_visible:
                    # Still generating, wait a bit
                    await asyncio.sleep(0.5)
                    continue
                
                # Stop button not visible, check if we have a new response
                current_count = await self._get_response_count(page)
                if current_count > baseline:
                    # New response appeared, wait for stability (500ms)
                    await asyncio.sleep(0.5)
                    final_count = await self._get_response_count(page)
                    if final_count == current_count:
                        # Count stable, response complete
                        return True
                
                await asyncio.sleep(0.3)
            
            return False
            
        except Exception as e:
            logger.error(f"{self.ai_target}: Wait for completion failed: {e}")
            return False
    
    async def _extract_response(self, page: Page, baseline_count: int) -> Tuple[str, str]:
        """
        Extract the latest response from Gemini.
        
        Tries markdown container first, falls back to full message text.
        """
        try:
            responses = page.locator(self.RESPONSE_CONTAINER)
            count = await responses.count()
            
            if count <= baseline_count:
                logger.warning(f"{self.ai_target}: No new responses (baseline={baseline_count}, current={count})")
                return "", ""
            
            # Get the last response
            last_response = responses.nth(count - 1)
            
            # Try to extract markdown content first
            markdown = ""
            markdown_container = last_response.locator(self.RESPONSE_CONTENT)
            if await markdown_container.count() > 0:
                markdown = await markdown_container.inner_text()
            else:
                # Fallback: get entire message text
                markdown = await last_response.inner_text()
            
            # Clean and create snippet
            markdown = markdown.strip()
            snippet = markdown[:200] + ("..." if len(markdown) > 200 else "")
            
            return snippet, markdown
            
        except Exception as e:
            logger.error(f"{self.ai_target}: Failed to extract response: {e}")
            return "", ""


# Register GeminiAI with factory
AIFactory.register("gemini", GeminiAI)
