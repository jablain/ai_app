"""ChatGPT-specific AI implementation (stub)."""

from typing import Optional, Tuple, Dict, Any
from playwright.async_api import Page
from .base import BaseAI
from .factory import AIFactory


class ChatGPTAI(BaseAI):
    """
    ChatGPT-specific implementation (NOT YET IMPLEMENTED).
    
    This is a placeholder stub to prevent crashes.
    All methods raise NotImplementedError.
    """
    
    @classmethod
    def get_default_config(cls) -> Dict[str, Any]:
        """Get ChatGPT's default configuration."""
        return {
            "ai_target": "chatgpt",
            "base_url": "https://chat.openai.com",
            "cdp": {"port": 9222}
        }
    
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize ChatGPT AI instance."""
        super().__init__(config)
        self._debug("ChatGPTAI initialized (stub - not functional)")
    
    
    async def send_prompt(
        self,
        message: str,
        wait_for_response: bool = True,
        timeout_s: int = 120
    ) -> Tuple[bool, Optional[str], Optional[str], Optional[Dict[str, Any]]]:
        """Send prompt to ChatGPT (NOT IMPLEMENTED)."""
        raise NotImplementedError(
            "ChatGPT support not yet implemented. "
            "Only Claude is currently supported."
        )
    
    
    async def list_messages(self) -> list[Dict[str, Any]]:
        """List ChatGPT messages (NOT IMPLEMENTED)."""
        raise NotImplementedError("ChatGPT support not yet implemented.")
    
    
    async def extract_message(self, index: int) -> Optional[str]:
        """Extract ChatGPT message (NOT IMPLEMENTED)."""
        raise NotImplementedError("ChatGPT support not yet implemented.")
    
    
    async def get_status(self) -> Dict[str, Any]:
        """Get ChatGPT status (NOT IMPLEMENTED)."""
        raise NotImplementedError("ChatGPT support not yet implemented.")
    
    
    async def _wait_for_response_complete(self, page: Page, timeout_s: int) -> bool:
        """Wait for ChatGPT response (NOT IMPLEMENTED)."""
        raise NotImplementedError("ChatGPT support not yet implemented.")
    
    
    async def _extract_response(
        self,
        page: Page,
        baseline_count: int
    ) -> Tuple[Optional[str], Optional[str]]:
        """Extract ChatGPT response (NOT IMPLEMENTED)."""
        raise NotImplementedError("ChatGPT support not yet implemented.")
    
    
    async def _ensure_chat_ready(self, page: Page) -> bool:
        """Ensure ChatGPT chat ready (NOT IMPLEMENTED)."""
        raise NotImplementedError("ChatGPT support not yet implemented.")


# Register ChatGPTAI with factory
AIFactory.register("chatgpt", ChatGPTAI)
