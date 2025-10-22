"""
Configuration management for the AI-CLI-Bridge Daemon.

This module defines the paths for runtime files (PID, logs, config)
and handles loading the daemon's configuration from a TOML file.

Change summary (2025-10-20):
- Removed stdout prints; now uses the logging module (INFO/WARNING).
- Behavior and returned structures are unchanged.
"""

from __future__ import annotations

import logging
import os
import pathlib
from typing import Dict, Any

import tomli

# Logger for this module (do not configure global logging here)
_logger = logging.getLogger("ai_cli_bridge.daemon.config")

# Define the root path for all runtime data to keep the project self-contained.
# Navigate up from this file to the project root
PROJECT_ROOT = pathlib.Path(__file__).parent.parent.parent.parent.resolve()
RUNTIME_DIR = PROJECT_ROOT / "runtime" / "daemon"

# Define specific paths for daemon management files.
CONFIG_DIR = RUNTIME_DIR / "config"
LOG_DIR = RUNTIME_DIR / "logs"
PID_FILE = RUNTIME_DIR / "daemon.pid"
LOG_FILE = LOG_DIR / "daemon.log"
CONFIG_FILE = CONFIG_DIR / "daemon_config.toml"

# --- Default Configuration ---
# These values will be used if they are not specified in the TOML file.
DEFAULT_CONFIG: Dict[str, Any] = {
    "daemon": {
        "host": "127.0.0.1",
        "port": 8000,
        "log_level": "INFO",
    },
    "features": {
        "token_align_frequency": 5000,
    },
}


def load_config() -> Dict[str, Any]:
    """
    Loads the daemon configuration from the TOML file.

    If the config file does not exist, returns the default configuration.
    It merges the loaded configuration with the defaults to ensure
    all necessary keys are present.

    Returns:
        A dictionary containing the loaded and merged configuration.
    """
    # Ensure the config directory exists.
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    # Start from a shallow copy of defaults
    config: Dict[str, Any] = {k: (v.copy() if isinstance(v, dict) else v) for k, v in DEFAULT_CONFIG.items()}

    if not CONFIG_FILE.exists():
        _logger.info("Using default configuration (no config file at: %s)", CONFIG_FILE)
        return config

    try:
        with open(CONFIG_FILE, "rb") as f:
            loaded_config = tomli.load(f)

        # Deep merge the loaded config into the default config
        for section, values in loaded_config.items():
            if section in config and isinstance(config[section], dict) and isinstance(values, dict):
                config[section].update(values)
            else:
                config[section] = values

        _logger.info("Loaded configuration from: %s", CONFIG_FILE)

    except tomli.TOMLDecodeError as e:
        _logger.warning("Error decoding TOML file at %s: %s", CONFIG_FILE, e)
        _logger.info("Using default configuration.")
    except Exception as e:
        _logger.warning("Error reading config file %s: %s", CONFIG_FILE, e)
        _logger.info("Using default configuration.")

    return config


def initialize_runtime_dirs() -> None:
    """
    Creates all necessary runtime directories for the daemon.

    Sets restrictive permissions on the runtime directory.
    """
    RUNTIME_DIR.mkdir(exist_ok=True)
    CONFIG_DIR.mkdir(exist_ok=True)
    LOG_DIR.mkdir(exist_ok=True)

    # Set restrictive permissions on runtime directory
    try:
        os.chmod(RUNTIME_DIR, 0o700)
    except Exception as e:
        # Non-fatal; log at debug to avoid noise by default
        _logger.debug("Could not chmod runtime dir %s: %s", RUNTIME_DIR, e)


# --- Create necessary directories on import ---
initialize_runtime_dirs()

