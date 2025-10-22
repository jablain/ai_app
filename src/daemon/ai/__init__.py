"""AI abstraction layer for browser automation."""

from .base import BaseAI
from .factory import AIFactory

# Import AI implementations to trigger registration
from .claude import ClaudeAI
from .chatgpt import ChatGPTAI
from .gemini import GeminiAI

__all__ = ["BaseAI", "AIFactory", "ClaudeAI", "ChatGPTAI", "GeminiAI"]
