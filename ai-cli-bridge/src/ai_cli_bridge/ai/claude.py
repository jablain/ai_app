"""Claude-specific AI implementation."""

from typing import Dict, Any
from .web_base import WebAIBase
from .factory import AIFactory


class ClaudeAI(WebAIBase):
    """Claude-specific implementation using the web AI base."""
    
    # =========================
    # Claude configuration
    # =========================
    
    BASE_URL = "https://claude.ai"
    CDP_PORT = 9223
    
    @classmethod
    def get_default_config(cls) -> Dict[str, Any]:
        """Get Claude's default configuration."""
        return {
            "ai_target": "claude",
            "base_url": cls.BASE_URL,
            "cdp": {"port": cls.CDP_PORT},
            "max_context_tokens": 200000
        }
    
    # =========================
    # Claude selectors
    # =========================
    
    @property
    def INPUT_BOX(self) -> str:
        return "div[contenteditable='true']"
    
    @property
    def STOP_BUTTON(self) -> str:
        return "button[aria-label='Stop response']"
    
    @property
    def NEW_CHAT_BUTTON(self) -> str:
        return "button[aria-label*='New chat']"
    
    @property
    def RESPONSE_CONTAINER(self) -> str:
        return ".font-claude-response"
    
    @property
    def RESPONSE_CONTENT(self) -> str:
        return ".standard-markdown"


# Register ClaudeAI with factory
AIFactory.register("claude", ClaudeAI)
