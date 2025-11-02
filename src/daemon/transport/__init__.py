# src/daemon/transport/__init__.py
"""
Transport layer package.

Exports:
- ITransport          (interface)
- WebTransport        (generic web/CDP transport)
- ClaudeWebTransport  (Claude-tuned web transport)
- ChatGPTWebTransport (ChatGPT-tuned web transport)
- GeminiWebTransport  (Gemini-tuned web transport)
"""

from __future__ import annotations

# Always export the interface
from .base import ITransport  # noqa: F401
from .chatgpt_web import ChatGPTWebTransport  # noqa: F401
from .claude_web import ClaudeWebTransport  # noqa: F401
from .gemini_web import GeminiWebTransport  # noqa: F401

# Explicit imports for concrete transports (raise on real problems)
from .web import WebTransport  # noqa: F401

__all__ = [
    "ITransport",
    "WebTransport",
    "ClaudeWebTransport",
    "ChatGPTWebTransport",
    "GeminiWebTransport",
]
