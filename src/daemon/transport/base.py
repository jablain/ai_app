# src/daemon/transport/base.py
"""
Unified transport interface.

This module defines the abstract base interface that all transports
(e.g., Web/CDP automation, direct HTTP API, mock transports) must implement.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional


class TransportKind(str, Enum):
    """Kinds of transports supported by the daemon."""

    WEB = "web"  # Browser/CDP-based automation
    API = "api"  # Direct HTTP API
    MOCK = "mock"  # Test-only or local fake


@dataclass(frozen=True)
class SendMetadata:
    """
    Metadata returned alongside a send operation.

    This is intentionally unopinionated; concrete transports may add fields
    (timings, request ids, model name, page url, etc.). Keep values JSON-safe.
    """

    data: dict[str, Any]


SendResult = tuple[bool, Optional[str], Optional[str], dict[str, Any]]
# (success, snippet, markdown, metadata)


class ITransport(ABC):
    """
    Transport interface all backends must implement.

    The daemon and AI classes should depend on this interface (not on a
    specific transport), so we can swap transports without touching the
    higher layers.
    """

    # ---------- Identity ----------

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable name for logging/diagnostics (e.g., 'claude-web')."""
        raise NotImplementedError

    @property
    @abstractmethod
    def kind(self) -> TransportKind:
        """Transport kind (web/api/mock)."""
        raise NotImplementedError

    # ---------- Core ops ----------

    @abstractmethod
    async def send_prompt(
        self,
        message: str,
        *,
        wait_for_response: bool = True,
        timeout_s: float = 60.0,
    ) -> SendResult:
        """
        Send a message through the transport and optionally wait for a response.

        Returns:
            Tuple: (success, snippet, markdown, metadata)
            - success: True if operation succeeded end-to-end
            - snippet: short preview of the response (or None)
            - markdown: full response in markdown/plain text (or None)
            - metadata: JSON-safe dict (timings, ids, debug info)
        """
        raise NotImplementedError

    @abstractmethod
    async def start_new_session(self) -> bool:
        """
        Start/ensure a fresh conversation session on the remote end.

        Should clear provider-side context, reset tabs, or do whatever
        is necessary to begin a clean chat.
        """
        raise NotImplementedError

    # ---------- Optional convenience ops (not required by daemon paths) ----------

    async def list_messages(self) -> list[dict[str, Any]]:
        """
        Optional: return a lightweight list of recent messages for debugging.
        Default implementation communicates that it's unsupported.
        """
        raise NotImplementedError(f"{self.__class__.__name__}.list_messages is not implemented")

    async def extract_message(self, baseline_count: int = 0) -> dict[str, Any]:
        """
        Optional: extract the most recent message since a baseline.
        """
        raise NotImplementedError(f"{self.__class__.__name__}.extract_message is not implemented")

    # ---------- Status / diagnostics ----------

    @abstractmethod
    def get_status(self) -> dict[str, Any]:
        """
        Return transport-level status for /status.

        Should include:
        - transport_kind
        - connected/session flags
        - any relevant endpoint/page info
        - model name if known
        """
        raise NotImplementedError
