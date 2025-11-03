"""
Configuration manager for chat UI.
"""

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class UIConfigManager:
    """Manages UI-specific configuration."""

    def __init__(self, config_path: Path | None = None):
        """
        Initialize UI config manager.

        Args:
            config_path: Path to UI config file (optional)
        """
        self.config_path = config_path
        self.config = {
            "context_warning": {"yellow_threshold": 70, "orange_threshold": 85, "red_threshold": 95}
        }

    def load_config(self) -> dict[str, Any]:
        """Load UI configuration."""
        # For now, return defaults
        # In future, can load from config file
        return self.config

    def get_warning_thresholds(self) -> dict[str, int]:
        """Get context warning thresholds."""
        return self.config["context_warning"]
