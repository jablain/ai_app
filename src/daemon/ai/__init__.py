"""AI abstraction layer for browser automation."""

from .base import BaseAI
from .chatgpt import ChatGPTAI

# Import AI implementations to trigger registration
from .claude import ClaudeAI
from .factory import AIFactory
from .gemini import GeminiAI

__all__ = ["BaseAI", "AIFactory", "ClaudeAI", "ChatGPTAI", "GeminiAI"]
