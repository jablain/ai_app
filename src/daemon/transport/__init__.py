# src/daemon/transport/__init__.py
"""
Transport layer package.

Exports:
- ITransport          (interface)
- WebTransport        (generic web/CDP transport)
"""

from __future__ import annotations

# Always export the interface
from .base import ITransport  # noqa: F401

# Export the generic WebTransport (no AI-specific transports needed)
from .web import WebTransport  # noqa: F401

__all__ = [
    "ITransport",
    "WebTransport",
]
