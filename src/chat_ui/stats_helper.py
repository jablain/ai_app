"""Helper functions for tolerant metadata parsing"""

from collections.abc import Iterable
from typing import Any, Union

Number = Union[int, float]

__all__ = [
    "extract_turn_count",
    "extract_total_tokens",
    "extract_prompt_tokens",
    "extract_completion_tokens",
    "extract_context_window",
    "extract_context_usage_percent",
    "extract_elapsed_ms",
]


def _first_present(d: dict[str, Any], keys: Iterable[str]) -> Any:
    """Return the first value whose key exists in dict (even if value == 0), ignoring only None."""
    for k in keys:
        if k in d and d[k] is not None:
            return d[k]
    return None


def _as_int(value: Any, default: int = 0) -> int:
    """Safely convert value to int"""
    try:
        # Accept strings like "123", floats like 123.0
        return int(float(value))
    except Exception:
        return default


def _as_float(value: Any, default: float | None = None) -> float | None:
    """Safely convert value to float"""
    if value is None:
        return default
    try:
        return float(value)
    except Exception:
        return default


def extract_turn_count(metadata: dict[str, Any]) -> int:
    """
    Extract turn/message count with field name tolerance

    Args:
        metadata: Response metadata dictionary

    Returns:
        Turn count (0 if not found)
    """
    v = _first_present(metadata, ("turn_count", "message_count"))
    return _as_int(v, 0)


def extract_total_tokens(metadata: dict[str, Any]) -> int:
    """
    Extract total token count with field name tolerance

    Args:
        metadata: Response metadata dictionary

    Returns:
        Total tokens (0 if not found)
    """
    v = _first_present(metadata, ("token_count", "total_tokens", "tokens", "tokens_used"))
    return _as_int(v, 0)


def extract_prompt_tokens(metadata: dict[str, Any]) -> int:
    """
    Extract prompt tokens

    Args:
        metadata: Response metadata dictionary

    Returns:
        Prompt tokens (0 if not found)
    """
    v = _first_present(metadata, ("prompt_tokens", "sent_tokens"))
    return _as_int(v, 0)


def extract_completion_tokens(metadata: dict[str, Any]) -> int:
    """
    Extract completion tokens

    Args:
        metadata: Response metadata dictionary

    Returns:
        Completion tokens (0 if not found)
    """
    v = _first_present(metadata, ("completion_tokens", "response_tokens"))
    return _as_int(v, 0)


def extract_context_window(metadata: dict[str, Any]) -> int | None:
    """
    Extract context window size

    Args:
        metadata: Response metadata dictionary

    Returns:
        Context window size or None if not found
    """
    v = _first_present(metadata, ("context_window_tokens", "ctaw_size", "context_window"))
    result = _as_int(v, 0)
    return result if v is not None else None


def extract_context_usage_percent(metadata: dict[str, Any]) -> float | None:
    """
    Extract context usage percentage

    Args:
        metadata: Response metadata dictionary

    Returns:
        Usage percentage or None if not found
    """
    v = _first_present(metadata, ("ctaw_usage_percent", "context_usage_percent", "usage_percent"))
    return _as_float(v, None)


def extract_elapsed_ms(metadata: dict[str, Any]) -> int | None:
    """
    Extract elapsed time in milliseconds

    Args:
        metadata: Response metadata dictionary

    Returns:
        Elapsed time in ms or None if not found
    """
    v = _first_present(metadata, ("elapsed_ms", "duration_ms", "latency_ms"))
    result = _as_int(v, 0)
    return result if v is not None else None
