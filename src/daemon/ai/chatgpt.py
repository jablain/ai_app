"""ChatGPT-specific AI implementation."""

from typing import Dict, Any
from playwright.async_api import Page
from .web_base import WebAIBase
from .factory import AIFactory


class ChatGPTAI(WebAIBase):
    """ChatGPT-specific implementation using the web AI base."""
    
    # =========================
    # ChatGPT configuration
    # =========================
    
    BASE_URL = "https://chatgpt.com"
    CDP_PORT = 9223
    
    @classmethod
    def get_default_config(cls) -> Dict[str, Any]:
        """Get ChatGPT's default configuration."""
        return {
            "ai_target": "chatgpt",
            "base_url": cls.BASE_URL,
            "cdp": {"port": cls.CDP_PORT},
            "max_context_tokens": 128000  # GPT-4 Turbo context window
        }
    
    # =========================
    # ChatGPT selectors
    # =========================
    
    @property
    def INPUT_BOX(self) -> str:
        return "textarea[name='prompt-textarea']"
    
    @property
    def STOP_BUTTON(self) -> str:
        return "button[data-testid='stop-button']"
    
    @property
    def NEW_CHAT_BUTTON(self) -> str:
        return "a[data-testid='create-new-chat-button']"
    
    @property
    def RESPONSE_CONTAINER(self) -> str:
        return "div[data-message-author-role='assistant']"
    
    @property
    def RESPONSE_CONTENT(self) -> str:
        return "div.markdown.prose"
    
    # =========================
    # ChatGPT-specific overrides
    # =========================
    
    async def _ensure_chat_ready(self, page: Page) -> bool:
        """ChatGPT-specific - skip textarea visibility check."""
        # Navigate to ChatGPT if needed
        if not page.url.startswith(self._get_base_url()):
            try:
                await page.goto(self._get_base_url(), wait_until="domcontentloaded", timeout=10000)
            except Exception as e:
                self._logger.error(f"Navigation failed: {e}")
                return False
        
        # Just check if textarea exists in DOM (even if hidden)
        try:
            textarea = await page.query_selector(self.INPUT_BOX)
            return textarea is not None
        except Exception as e:
            self._logger.error(f"Input box check failed: {e}")
            return False
    
    async def _send_message(self, page: Page, message: str) -> bool:
        """ChatGPT-specific send - handle hidden textarea."""
        try:
            # ChatGPT's textarea is hidden - focus and type
            textarea = await page.query_selector(self.INPUT_BOX)
            if textarea:
                await textarea.focus()
                await page.keyboard.type(message, delay=10)
                await page.keyboard.press("Enter")
                return True
            
            return False
        except Exception as e:
            self._logger.error(f"Failed to send message: {e}")
            return False


# Register ChatGPTAI with factory
AIFactory.register("chatgpt", ChatGPTAI)
