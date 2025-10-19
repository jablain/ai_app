"""Gemini-specific AI implementation."""

from typing import Dict, Any

from .web_base import WebAIBase
from .factory import AIFactory


class GeminiAI(WebAIBase):
    """Gemini-specific implementation using the web AI base."""
    
    # =========================
    # Gemini configuration
    # =========================
    
    BASE_URL = "https://gemini.google.com"
    CDP_PORT = 9223
    
    @classmethod
    def get_default_config(cls) -> Dict[str, Any]:
        """Get Gemini's default configuration."""
        return {
            "ai_target": "gemini",
            "base_url": cls.BASE_URL,
            "cdp": {"port": cls.CDP_PORT},
            "max_context_tokens": 2000000
        }
    
    # =========================
    # Gemini selectors
    # =========================
    
    @property
    def INPUT_BOX(self) -> str:
        return "div.ql-editor[aria-label*='prompt']"
    
    @property
    def STOP_BUTTON(self) -> str:
        return "button[aria-label='Stop response']"
    
    @property
    def NEW_CHAT_BUTTON(self) -> str:
        return "a.new-chat-button"
    
    @property
    def RESPONSE_CONTAINER(self) -> str:
        return "div.response-container-content"
    
    @property
    def RESPONSE_CONTENT(self) -> str:
        return "div.markdown"


# Register GeminiAI with factory
AIFactory.register("gemini", GeminiAI)
