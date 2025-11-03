"""
Type definitions for context generation.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class ContextPreset:
    """Context generation preset configuration."""

    name: str
    discover: Optional[str]  # "project", "module", or None (cwd)
    include_tests: bool = False
    include_dotfiles: bool = False
    chunk: int = 1500
    max_file_bytes: int = 350000
