"""
Type definitions for chat management.
"""

from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass
class ChatInfo:
    """Information about a chat session."""

    chat_id: str
    title: str
    url: str
    is_current: bool


@dataclass
class ExportFormat:
    """Chat export data structure."""

    chat_id: str
    ai: str
    exported_at: str
    messages: List[Dict[str, Any]]
