"""ChatGPT AI adapter - configuration only."""

import logging
from typing import Any

from .base import BaseAI
from .factory import AIFactory

logger = logging.getLogger(__name__)


class ChatGPTAI(BaseAI):
    """
    ChatGPT AI adapter.

    This class now only provides ChatGPT-specific configuration.
    All delegation logic is handled by BaseAI.
    """

    @classmethod
    def get_default_config(cls) -> dict[str, Any]:
        """
        ChatGPT-specific configuration including selectors for web automation.

        Returns:
            Configuration dict with:
            - ai_target: 'chatgpt'
            - max_context_tokens: ChatGPT's context window size
            - base_url: ChatGPT web interface URL
            - selectors: CSS selectors for ChatGPT's UI elements
            - context_warning: Warning thresholds for context usage
            - timing: Response timing configuration
        """
        return {
            "ai_target": "chatgpt",
            "max_context_tokens": 128000,  # ChatGPT-4 context window
            "base_url": "https://chatgpt.com",
            # Context usage warning thresholds (slightly more conservative)
            "context_warning": {
                "yellow_threshold": 65,  # Warning starts earlier due to smaller window
                "orange_threshold": 80,  # More urgent at 80%
                "red_threshold": 90,  # Critical at 90%
            },
            # Timing configuration
            "response_wait_s": 60.0,
            "completion_check_interval_s": 0.3,
            # CSS Selectors for ChatGPT's UI
            "selectors": {
                "input_box": "div#prompt-textarea[contenteditable='true']",
                "stop_button": "button[data-testid='stop-button']",
                "send_button": "button[data-testid='send-button']",
                "new_chat_button": "button:has-text('New chat'), a:has-text('New chat')",
                "response_container": "div[data-message-author-role='assistant']",
                "response_content": "div.markdown.prose",
                # Chat management selectors
                "chat_sidebar": "div#history",
                "chat_item": "#history a[href^='/c/']",
                "chat_title": "span[dir='auto']",
                "active_chat": "a[data-active]",
            },
            # Additional ChatGPT-specific settings
            "snippet_length": 280,
        }


# Register this adapter with the factory under the key 'chatgpt'
AIFactory.register("chatgpt", ChatGPTAI)
