"""Abstract base class for AI interactions.

This module defines the pure interface for interacting with AI systems,
completely independent of any transport mechanism (web, API, etc.).
"""

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, TypedDict

try:
    import tiktoken

    TIKTOKEN_AVAILABLE = True
except ImportError:
    TIKTOKEN_AVAILABLE = False

# =========================
# Type Definitions
# =========================


class AIConfig(TypedDict, total=False):
    """Configuration dictionary for AI instances."""

    ai_target: str
    max_context_tokens: int
    base_url: str  # For web-based AIs
    cdp: dict  # For web-based AIs


class AIStatus(TypedDict):
    """AI status dictionary structure."""

    ai_target: str
    turn_count: int
    token_count: int
    message_count: int
    session_duration_s: float
    last_interaction_time: float | None
    ctaw_size: int
    ctaw_usage_percent: float


# =========================
# Session State
# =========================


@dataclass
class SessionState:
    """
    Encapsulates all session tracking state.

    This is implementation-agnostic - tracks logical operations
    without knowing HOW they're performed. Fully self-contained
    with its own CTAW tracking and usage calculation.
    """

    turn_count: int = 0
    token_count: int = 0
    message_count: int = 0
    ctaw_size: int = 200000  # Default, overridden by config
    session_start_time: float = field(default_factory=time.time)
    last_interaction_time: float | None = None
    message_history: list[dict[str, Any]] = field(default_factory=list)

    # NEW: Token breakdown tracking

    sent_tokens: int = 0
    response_tokens: int = 0

    # NEW: Timing and velocity tracking
    last_response_time_ms: int | None = None
    tokens_per_sec: float | None = None

    # NEW: Running averages
    avg_response_time_ms: float | None = None
    avg_tokens_per_sec: float | None = None

    # NEW: Response time history for calculating averages
    response_times_ms: list[int] = field(default_factory=list)

    def add_message(
        self, sent_tokens: int, response_tokens: int, response_time_ms: int | None = None
    ) -> int:
        """
        Record a message exchange and return tokens used.

        Args:
            sent_tokens: Token count of sent message
            response_tokens: Token count of response
            response_time_ms: Response time in milliseconds (optional)

        Returns:
            Total tokens used in this exchange
        """
        self.turn_count += 1
        self.message_count += 1
        self.last_interaction_time = time.time()

        tokens_used = sent_tokens + response_tokens
        self.token_count += tokens_used

        # NEW: Track token breakdown
        self.sent_tokens += sent_tokens
        self.response_tokens += response_tokens

        # NEW: Track timing and velocity
        if response_time_ms is not None and response_time_ms > 0:
            self.last_response_time_ms = response_time_ms
            self.response_times_ms.append(response_time_ms)

            # Calculate tokens per second for this message
            response_time_s = response_time_ms / 1000.0
            if response_time_s > 0:
                self.tokens_per_sec = response_tokens / response_time_s

            # Update running averages
            if len(self.response_times_ms) > 0:
                self.avg_response_time_ms = sum(self.response_times_ms) / len(
                    self.response_times_ms
                )

                # Calculate average tokens per second across all responses
                total_response_time_s = sum(self.response_times_ms) / 1000.0
                if total_response_time_s > 0:
                    self.avg_tokens_per_sec = self.response_tokens / total_response_time_s

        self.message_history.append(
            {
                "turn": self.turn_count,
                "timestamp": self.last_interaction_time,
                "sent_tokens": sent_tokens,
                "response_tokens": response_tokens,
                "tokens_used": tokens_used,
                "response_time_ms": response_time_ms,
            }
        )
        return tokens_used

    def reset(self) -> None:
        """Reset all state for a new session."""
        self.turn_count = 0
        self.token_count = 0
        self.message_count = 0
        self.session_start_time = time.time()
        self.last_interaction_time = None
        self.message_history.clear()

        # NEW: Reset token breakdown
        self.sent_tokens = 0
        self.response_tokens = 0

        # NEW: Reset timing and velocity
        self.last_response_time_ms = None
        self.tokens_per_sec = None
        self.avg_response_time_ms = None
        self.avg_tokens_per_sec = None
        self.response_times_ms.clear()

    def get_duration_s(self) -> float:
        """Get session duration in seconds."""
        return time.time() - self.session_start_time

    def get_ctaw_usage_percent(self) -> float:
        """
        Calculate CTAW usage as a percentage.

        Formula: (TokenCount / CTAWSize) * 100

        Returns:
            Percentage (0.0 to 100.0+)
        """
        if self.ctaw_size <= 0:
            return 0.0
        return (self.token_count / self.ctaw_size) * 100.0

    def to_dict(self) -> dict[str, Any]:
        """Export state as dictionary for status reporting."""
        result = {
            "turn_count": self.turn_count,
            "token_count": self.token_count,
            "message_count": self.message_count,
            "session_duration_s": round(self.get_duration_s(), 1),
            "last_interaction_time": self.last_interaction_time,
            "ctaw_size": self.ctaw_size,
            "ctaw_usage_percent": round(self.get_ctaw_usage_percent(), 2),
            # NEW: Token breakdown
            "sent_tokens": self.sent_tokens,
            "response_tokens": self.response_tokens,
            # NEW: Timing and velocity (only include if available)
            "last_response_time_ms": self.last_response_time_ms,
            "tokens_per_sec": round(self.tokens_per_sec, 1)
            if self.tokens_per_sec is not None
            else None,
            # NEW: Running averages (only include if available)
            "avg_response_time_ms": round(self.avg_response_time_ms, 1)
            if self.avg_response_time_ms is not None
            else None,
            "avg_tokens_per_sec": round(self.avg_tokens_per_sec, 1)
            if self.avg_tokens_per_sec is not None
            else None,
        }
        return result


# =========================
# Base AI Class
# =========================


class BaseAI(ABC):
    """
    Pure abstract base class for AI interactions.

    Defines WHAT operations are possible with an AI system,
    without specifying HOW they're implemented.

    Key Principles:
    - No references to transport mechanisms (CDP, HTTP, WebSocket, etc.)
    - No references to implementation details (Playwright, browsers, etc.)
    - Only logical AI operations (send message, list messages, etc.)
    - Session state tracking is implementation-agnostic

    """

    @property
    def ai_target(self) -> str:
        """Convenient read-only alias used by subclasses/logging."""
        return self.get_ai_target()

    @property
    def config(self) -> dict[str, Any]:
        return self._config

    def __init__(self, config: dict[str, Any]):
        """
        Initialize base AI.

        Args:
            config: Configuration dict with required fields:
                - ai_target: AI identifier (e.g., 'claude', 'chatgpt')
                - max_context_tokens: Context window size

        Raises:
            ValueError: If required config fields are missing
        """
        # Validate required config fields
        if "ai_target" not in config:
            raise ValueError("Config must include 'ai_target'")
        if "max_context_tokens" not in config:
            raise ValueError("Config must include 'max_context_tokens'")

        self._config = config

        # Set up logging
        self._logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

        # Initialize session state with CTAW size from config
        self._session = SessionState(ctaw_size=config["max_context_tokens"])

        # Set up tokenizer (tiktoken if available, fallback to char/4)
        self._tokenizer = None
        if TIKTOKEN_AVAILABLE:
            try:
                self._tokenizer = tiktoken.get_encoding("cl100k_base")
                self._logger.debug("Initialized tiktoken tokenizer")
            except Exception as e:
                self._logger.warning(f"Failed to initialize tiktoken: {e}")

    # =========================
    # Core AI Operations (Abstract Interface)
    # =========================

    @abstractmethod
    async def send_prompt(
        self, message: str, wait_for_response: bool = True, timeout_s: int = 120
    ) -> tuple[bool, str | None, str | None, dict[str, Any] | None]:
        """
        Send a message to the AI and optionally wait for response.

        This is the primary interaction method. Subclasses implement
        the actual transport mechanism (web automation, API call, etc.).

        Args:
            message: Text to send to the AI
            wait_for_response: Whether to wait for AI's reply
            timeout_s: Maximum time to wait for response

        Returns:
            Tuple of (success, snippet, full_response, metadata)
            - success: True if message was sent (and response received if waiting)
            - snippet: First ~280 chars of response (for display)
            - full_response: Complete response text/markdown
            - metadata: Dict with timing, token usage, etc.
        """
        pass

    @abstractmethod
    async def list_messages(self) -> list[dict[str, Any]]:
        """
        List all messages in the current conversation.

        Returns:
            List of message dictionaries with keys:
            - index: int (0-based)
            - type: 'user' | 'assistant' | 'system'
            - preview: str (first ~60 chars)
            - length: int (character count)
        """
        pass

    @abstractmethod
    async def extract_message(self, baseline_count: int = 0) -> dict:
        """
        Extract the most recent assistant message since a baseline count.

        Args:
            baseline_count: Count of assistant messages before sending

        Returns:
            Dict with:
              - snippet: short preview
              - markdown: full extracted content
        """
        pass
        pass

    @abstractmethod
    async def start_new_session(self) -> bool:
        """
        Start a new chat session/conversation.

        This resets the conversation history in the AI interface
        and resets local session state tracking.

        Returns:
            True if new session started successfully
        """
        pass

    @abstractmethod
    def get_transport_status(self) -> dict[str, Any]:
        """
        Get transport/connection status.

        This is implementation-specific (web has CDP info, API has endpoint info).
        Subclasses must implement this to provide transport-layer details.

        Returns:
            Dictionary with transport-specific status information
        """
        pass

    # =========================
    # AI Status (Concrete Implementation)
    # =========================

    def get_ai_status(self) -> AIStatus:
        """
        Get AI session status (implementation-agnostic).

        Returns universal AI metrics that apply regardless of
        transport mechanism (web, API, etc.).

        Returns:
            Dictionary with AI session information
        """
        return {
            "ai_target": self.get_ai_target(),
            **self._session.to_dict(),
        }

    def get_ai_target(self) -> str:
        """Get the AI target name (e.g., 'claude', 'chatgpt')."""
        return self._config.get("ai_target", "unknown")

    # =========================
    # Token Counting
    # =========================

    def _count_tokens(self, text: str) -> int:
        """
        Count tokens in text using tiktoken or fallback.

        Args:
            text: Text to count tokens in

        Returns:
            Token count
        """
        if self._tokenizer:
            try:
                return len(self._tokenizer.encode(text))
            except Exception as e:
                self._logger.warning(f"Token counting failed: {e}")

        # Fallback: 4 chars ≈ 1 token
        return len(text) // 4

    # =========================
    # Protected Helpers for Subclasses
    # =========================

    def _update_session_from_interaction(
        self, message: str, response: str, response_time_ms: int | None = None
    ) -> dict[str, Any]:
        """
        Update session state after a successful interaction.

        This is a helper method for subclasses to call after they've
        successfully completed a send_prompt operation. Returns metadata
        to be merged with transport-specific metadata.

        Args:
            message: The sent message
            response: The received response
            response_time_ms: Response time in milliseconds (optional)

        Returns:
            Metadata dict with session information
        """
        # Count tokens
        sent_tokens = self._count_tokens(message)
        response_tokens = self._count_tokens(response)

        # Update session state (NOW includes timing)
        tokens_used = self._session.add_message(sent_tokens, response_tokens, response_time_ms)

        # Build metadata
        metadata = {
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "turn_count": self._session.turn_count,
            "message_count": self._session.message_count,
            "token_count": self._session.token_count,
            "tokens_used": tokens_used,
            "sent_tokens": sent_tokens,
            "response_tokens": response_tokens,
            "ctaw_usage_percent": round(self._session.get_ctaw_usage_percent(), 2),
            "ctaw_size": self._session.ctaw_size,
            "session_duration_s": round(self._session.get_duration_s(), 1),
        }

        # NEW: Include timing/velocity if available
        if response_time_ms is not None:
            metadata["response_time_ms"] = response_time_ms
        if self._session.tokens_per_sec is not None:
            metadata["tokens_per_sec"] = round(self._session.tokens_per_sec, 1)

        self._logger.debug(
            f"Turn: {self._session.turn_count}, "
            f"Tokens: {self._session.token_count}, "
            f"CTAW: {self._session.get_ctaw_usage_percent():.1f}%"
        )

        return metadata

    def _reset_session_state(self) -> None:
        """
        Reset all session state (private - called by start_new_session).

        This clears turn counter, token counts, and message history.
        Should only be called from start_new_session() implementation.
        """
        self._logger.info("Resetting session state")
        self._session.reset()

    # =========================
    # Configuration Access
    # =========================

    def get_config(self) -> dict[str, Any]:
        """Get the full configuration dictionary."""
        return self._config

    # =========================
    # Class-level Configuration
    # =========================

    @classmethod
    @abstractmethod
    def get_default_config(cls) -> dict[str, Any]:
        """
        Get default configuration for this AI implementation.

        Returns:
            Dict with ai_target, max_context_tokens, and implementation-specific settings
        """
        pass
