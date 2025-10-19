"""
Configuration management for the AI-CLI-Bridge Daemon.

This module defines the paths for runtime files (PID, logs, config)
and handles loading the daemon's configuration from a TOML file.
"""

import os
import pathlib
import tomli
from typing import Dict, Any

# Define the root path for all runtime data to keep the project self-contained.
# Navigate up from this file to the project root
PROJECT_ROOT = pathlib.Path(__file__).parent.parent.parent.parent.resolve()
RUNTIME_DIR = PROJECT_ROOT / "runtime"

# Define specific paths for daemon management files.
CONFIG_DIR = RUNTIME_DIR / "config"
LOG_DIR = RUNTIME_DIR / "logs"
PID_FILE = RUNTIME_DIR / "daemon.pid"
LOG_FILE = LOG_DIR / "daemon.log"
CONFIG_FILE = CONFIG_DIR / "daemon_config.toml"

# --- Default Configuration ---
# These values will be used if they are not specified in the TOML file.
DEFAULT_CONFIG = {
    "daemon": {
        "host": "127.0.0.1",
        "port": 8000,
        "log_level": "INFO",
    },
    "features": {
        "token_align_frequency": 5000,
    }
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

    config = DEFAULT_CONFIG.copy()

    if not CONFIG_FILE.exists():
        print(f"[Config] Using default configuration (no config file at: {CONFIG_FILE})")
        return config

    try:
        with open(CONFIG_FILE, "rb") as f:
            loaded_config = tomli.load(f)
            # Deep merge the loaded config into the default config
            for section, values in loaded_config.items():
                if section in config and isinstance(config[section], dict):
                    config[section].update(values)
                else:
                    config[section] = values
        print(f"[Config] Loaded configuration from: {CONFIG_FILE}")
    except tomli.TOMLDecodeError as e:
        print(f"[Config] Error decoding TOML file at {CONFIG_FILE}: {e}")
        print("[Config] Using default configuration.")
    except Exception as e:
        print(f"[Config] Error reading config file: {e}")
        print("[Config] Using default configuration.")
    
    return config


# --- Create necessary directories on import ---
def initialize_runtime_dirs():
    """
    Creates all necessary runtime directories for the daemon.
    """
    RUNTIME_DIR.mkdir(exist_ok=True)
    CONFIG_DIR.mkdir(exist_ok=True)
    LOG_DIR.mkdir(exist_ok=True)
    
    # Set restrictive permissions on runtime directory
    try:
        os.chmod(RUNTIME_DIR, 0o700)
    except Exception:
        pass


initialize_runtime_dirs()
