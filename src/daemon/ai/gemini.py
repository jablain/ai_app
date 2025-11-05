"""Gemini AI adapter - configuration only."""

import logging
from typing import Any

from .base import BaseAI
from .factory import AIFactory

logger = logging.getLogger(__name__)


class GeminiAI(BaseAI):
    """
    Gemini AI adapter.

    This class now only provides Gemini-specific configuration.
    All delegation logic is handled by BaseAI.
    """

    @classmethod
    def get_default_config(cls) -> dict[str, Any]:
        """
        Gemini-specific configuration including selectors for web automation.

        Returns:
            Configuration dict with:
            - ai_target: 'gemini'
            - max_context_tokens: Gemini's context window size
            - base_url: Gemini web interface URL
            - selectors: CSS selectors for Gemini's UI elements
            - context_warning: Warning thresholds for context usage
            - timing: Response timing configuration
        """
        return {
            "ai_target": "gemini",
            "max_context_tokens": 2000000,  # Gemini 1.5 Pro context window
            "base_url": "https://gemini.google.com",
            # Context usage warning thresholds (higher due to massive context)
            "context_warning": {
                "yellow_threshold": 80,  # Huge context - can go further before warning
                "orange_threshold": 90,  # More urgent at 90%
                "red_threshold": 95,  # Critical at 95%
            },
            # Timing configuration
            "response_wait_s": 60.0,
            "completion_check_interval_s": 0.3,
            # CSS Selectors for Gemini's UI
            "selectors": {
                "input_box": "div.ql-editor[contenteditable='true'][aria-label*='prompt']",
                "stop_button": "mat-icon[fonticon='stop']",
                "send_button": "button[aria-label='Send message']",
                "new_chat_button": "button:has-text('New chat'), a:has-text('New chat')",
                "response_container": "message-content",
                "response_content": "div.markdown.markdown-main-panel",
            },
            # Additional Gemini-specific settings
            "snippet_length": 280,
        }


# Register this adapter with the factory under the key 'gemini'
AIFactory.register("gemini", GeminiAI)
