"""Claude AI adapter - configuration only."""

import logging
from typing import Any

from .base import BaseAI
from .factory import AIFactory

logger = logging.getLogger(__name__)


class ClaudeAI(BaseAI):
    """
    Claude AI adapter.

    This class now only provides Claude-specific configuration.
    All delegation logic is handled by BaseAI.
    """

    @classmethod
    def get_default_config(cls) -> dict[str, Any]:
        """
        Claude-specific configuration including selectors for web automation.

        Returns:
            Configuration dict with:
            - ai_target: 'claude'
            - max_context_tokens: Claude's context window size
            - base_url: Claude web interface URL
            - selectors: CSS selectors for Claude's UI elements
            - context_warning: Warning thresholds for context usage
            - timing: Response timing configuration
        """
        return {
            "ai_target": "claude",
            "max_context_tokens": 200000,
            "base_url": "https://claude.ai",
            # Context usage warning thresholds
            "context_warning": {
                "yellow_threshold": 70,  # Warning starts at 70%
                "orange_threshold": 85,  # More urgent at 85%
                "red_threshold": 95,  # Critical at 95%
            },
            # Timing configuration
            "response_wait_s": 60.0,
            "completion_check_interval_s": 0.3,
            # CSS Selectors for Claude's UI
            "selectors": {
                "input_box": "div[contenteditable='true']",
                "stop_button": "button[aria-label='Stop response']",
                "send_button": "button[aria-label='Send Message']",
                "new_chat_button": "button[aria-label*='New chat']",
                "response_container": "div.font-claude-response",
                "response_content": ".standard-markdown",
                # Chat management selectors
                "chat_sidebar": "ul",  # The <ul> containing chat list items
                "chat_item": "a[href^='/chat/']",  # Links to chat pages
                "chat_title": "span.truncate",  # Title text within chat item
             },
             # Additional Claude-specific settings
             "snippet_length": 280,
         }


# Register this adapter with the factory under the key 'claude'
AIFactory.register("claude", ClaudeAI)
