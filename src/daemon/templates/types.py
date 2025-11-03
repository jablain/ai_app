"""
Type definitions for prompt templates.
"""

from dataclasses import dataclass
from typing import Dict


@dataclass
class Template:
    """Prompt template definition."""

    name: str
    prompt: str
    default_vars: Dict[str, str]
