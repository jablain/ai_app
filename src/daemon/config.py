"""
Configuration management for the AI-CLI-Bridge Daemon.

This module defines the paths for runtime files (PID, logs, config)
and handles loading the daemon's configuration from a TOML file.

Pass 1 enhancements:
- Exit codes defined as constants
- CDP configuration with browser lifecycle management
- Profile directory resolution and validation
- Enhanced TOML parsing with exit code 7 on syntax errors
- Separate log files for daemon and browser output
- Type coercion and validation for numeric config values
- Environment variable override for config path
- Timing and threshold validation
"""

from __future__ import annotations

import logging
import os
import pathlib
import stat
import sys
from dataclasses import dataclass, field

import tomli

# POSIX-only imports (Linux/Unix) - defensive imports
try:
    import pwd
    import grp

    _POSIX_AVAILABLE = True
except ImportError:
    _POSIX_AVAILABLE = False

# Logger for this module (do not configure global logging here)
_logger = logging.getLogger("ai_cli_bridge.daemon.config")

# ---------------------------------------------------------------------------
# Exit Codes
# ---------------------------------------------------------------------------

EXIT_SUCCESS = 0
EXIT_GENERIC_FAILURE = 1
EXIT_PID_LOCK_HELD = 2  # Daemon already running
EXIT_PROFILE_DIR_NOT_WRITABLE = 3  # CDP profile directory issue
EXIT_DAEMON_PORT_BUSY = 4  # Daemon port already in use
EXIT_FLATPAK_MISSING = 5  # Flatpak package not installed
EXIT_CDP_CONFLICT_OR_TIMEOUT = 6  # CDP already running or failed to start
EXIT_CONFIG_INVALID = 7  # TOML parse error or invalid config

# ---------------------------------------------------------------------------
# Project Paths
# ---------------------------------------------------------------------------

# Define the root path for all runtime data to keep the project self-contained.
# Navigate up from this file to the project root
PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[2]
RUNTIME_DIR = PROJECT_ROOT / "runtime" / "daemon"

# Daemon-specific paths
CONFIG_DIR = RUNTIME_DIR / "config"
LOG_DIR = RUNTIME_DIR / "logs"

# PID files (ownership and process tracking)
PID_FILE = RUNTIME_DIR / "daemon.pid"  # Daemon's own PID (for external signaling)
OWNER_PID_FILE = RUNTIME_DIR / "daemon_owner.pid"  # Ownership assertion lock

# Log files (separate for daemon and browser output - handlers configured in main.py)
DAEMON_LOG_FILE = LOG_DIR / "daemon.log"
BROWSER_STDOUT_LOG = LOG_DIR / "browser_stdout.log"
BROWSER_STDERR_LOG = LOG_DIR / "browser_stderr.log"

# Config file location (can be overridden by AI_APP_CONFIG env var)
CONFIG_FILE = CONFIG_DIR / "daemon_config.toml"

# CDP browser paths
BROWSER_DIR = RUNTIME_DIR / "browser"
BROWSER_PID_FILE = BROWSER_DIR / "browser.pid"  # Browser process PID
BROWSER_OWNER_PID_FILE = BROWSER_DIR / "owner.pid"  # Which daemon owns the browser
DEFAULT_PROFILE_DIR = BROWSER_DIR / "profiles" / "multi_ai_cdp"

# ---------------------------------------------------------------------------
# Configuration Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class DaemonConfig:
    """Daemon server configuration."""

    host: str = "127.0.0.1"
    port: int = 8000
    log_level: str = "INFO"


@dataclass
class CDPHealthConfig:
    """CDP health monitoring configuration."""

    poll_interval_s: float = 3.0  # Health check interval in seconds
    fail_threshold: int = 3  # Consecutive failures before declaring unhealthy
    shutdown_wait_s: float = 10.0  # Wait after SIGTERM before SIGKILL


@dataclass
class CDPStartURLs:
    """URLs to open when starting CDP browser."""

    claude: str = "https://claude.ai/new"
    gemini: str = "https://gemini.google.com/app"
    chatgpt: str = "https://chatgpt.com"  # Standardized to chatgpt.com (chat.openai.com redirects)


@dataclass
class CDPConfig:
    """CDP browser configuration."""

    port: int = 9223
    profile_dir: str = ""  # Empty means use DEFAULT_PROFILE_DIR
    cmd: str = "flatpak run io.github.ungoogled_software.ungoogled_chromium"
    start_timeout_s: float = 15.0  # Timeout waiting for CDP to become ready
    probe_timeout_s: float = 2.0  # Timeout for individual health probes
    probe_interval_s: float = 0.5  # Interval between startup readiness probes
    health: CDPHealthConfig = field(default_factory=CDPHealthConfig)
    start_urls: CDPStartURLs = field(default_factory=CDPStartURLs)


@dataclass
class FeaturesConfig:
    """Feature flags and settings."""

    token_align_frequency: int = 5000


@dataclass
class AppConfig:
    """Complete application configuration."""

    daemon: DaemonConfig = field(default_factory=DaemonConfig)
    cdp: CDPConfig = field(default_factory=CDPConfig)
    features: FeaturesConfig = field(default_factory=FeaturesConfig)
    # Per-AI transport selection, e.g. {"claude": "web", "chatgpt": "api"}
    ai_transports: dict[str, str] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Validation Helpers
# ---------------------------------------------------------------------------

# Valid log levels
VALID_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}


def _as_int(value: any, field_name: str) -> int:
    """
    Coerces a value to int with clear error message.

    Args:
        value: Value to coerce
        field_name: Name of the config field (for error messages)

    Returns:
        Integer value

    Exits:
        EXIT_CONFIG_INVALID if coercion fails
    """
    try:
        return int(value)
    except (ValueError, TypeError):
        _logger.error("Invalid type for %s: %r (expected int)", field_name, value)
        sys.exit(EXIT_CONFIG_INVALID)


def _as_float(value: any, field_name: str) -> float:
    """
    Coerces a value to float with clear error message.

    Args:
        value: Value to coerce
        field_name: Name of the config field (for error messages)

    Returns:
        Float value

    Exits:
        EXIT_CONFIG_INVALID if coercion fails
    """
    try:
        return float(value)
    except (ValueError, TypeError):
        _logger.error("Invalid type for %s: %r (expected float)", field_name, value)
        sys.exit(EXIT_CONFIG_INVALID)


def _validate_port(port: int, field_name: str) -> int:
    """
    Validates that a port is in the valid range for non-root users.

    Args:
        port: Port number to validate
        field_name: Name of the config field (for error messages)

    Returns:
        Valid port number

    Exits:
        EXIT_CONFIG_INVALID if port is out of range
    """
    if not (1024 <= port <= 65535):
        _logger.error("Port %d for %s out of valid range (1024-65535)", port, field_name)
        sys.exit(EXIT_CONFIG_INVALID)
    return port


def _validate_positive_float(value: float, field_name: str) -> float:
    """
    Validates that a float value is positive (> 0).

    Args:
        value: Value to validate
        field_name: Name of the config field (for error messages)

    Returns:
        Valid positive float

    Exits:
        EXIT_CONFIG_INVALID if value is not positive
    """
    if value <= 0:
        _logger.error("%s must be > 0, got %f", field_name, value)
        sys.exit(EXIT_CONFIG_INVALID)
    return value


def _validate_positive_int(value: int, field_name: str, minimum: int = 1) -> int:
    """
    Validates that an int value meets minimum threshold.

    Args:
        value: Value to validate
        field_name: Name of the config field (for error messages)
        minimum: Minimum acceptable value (inclusive)

    Returns:
        Valid integer

    Exits:
        EXIT_CONFIG_INVALID if value is below minimum
    """
    if value < minimum:
        _logger.error("%s must be >= %d, got %d", field_name, minimum, value)
        sys.exit(EXIT_CONFIG_INVALID)
    return value


def _normalize_log_level(level: str) -> str:
    """
    Normalizes and validates log level.

    Args:
        level: Log level string

    Returns:
        Normalized log level (uppercase) or "INFO" if invalid
    """
    normalized = level.upper()
    if normalized not in VALID_LOG_LEVELS:
        _logger.warning("Invalid log_level '%s', using INFO", level)
        return "INFO"
    return normalized


# ---------------------------------------------------------------------------
# Configuration Loading
# ---------------------------------------------------------------------------


def load_config() -> AppConfig:
    """
    Loads the daemon configuration from the TOML file.

    Checks AI_APP_CONFIG environment variable for custom config path.
    If the config file does not exist, returns the default configuration.
    Exits with code 7 if TOML is malformed or has type errors.

    Returns:
        AppConfig: The loaded and validated configuration.

    Note:
        All callers must use dataclass attributes (e.g., config.daemon.port)
        rather than dict access (config.get("daemon", {})).
    """
    # Ensure the config directory exists
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    # Check for environment variable override
    env_config_path = os.environ.get("AI_APP_CONFIG")
    if env_config_path:
        config_file = pathlib.Path(env_config_path).expanduser().resolve()
        _logger.info("Using config from AI_APP_CONFIG env var: %s", config_file)
    else:
        config_file = CONFIG_FILE

    # Start with defaults
    config = AppConfig()

    if not config_file.exists():
        _logger.info(
            "No config file found at %s. Using defaults. " "Create the file to customize settings.",
            config_file,
        )
        return config

    # Load and parse TOML
    try:
        with open(config_file, "rb") as f:
            loaded = tomli.load(f)
        _logger.info("Loaded configuration from: %s", config_file)
    except tomli.TOMLDecodeError as e:
        _logger.error("Invalid TOML syntax in config file %s: %s", config_file, e)
        sys.exit(EXIT_CONFIG_INVALID)
    except Exception as e:
        _logger.error("Error reading config file %s: %s", config_file, e)
        sys.exit(EXIT_CONFIG_INVALID)

    # Merge loaded config into defaults with type coercion and validation
    try:
        # Daemon section
        if "daemon" in loaded:
            for key, value in loaded["daemon"].items():
                if key == "port":
                    port = _as_int(value, "daemon.port")
                    config.daemon.port = _validate_port(port, "daemon.port")
                elif key == "log_level":
                    config.daemon.log_level = _normalize_log_level(value)
                elif hasattr(config.daemon, key):
                    setattr(config.daemon, key, value)

        # CDP section
        if "cdp" in loaded:
            cdp_data = loaded["cdp"]
            for key, value in cdp_data.items():
                if key == "health" and isinstance(value, dict):
                    for hkey, hval in value.items():
                        if hkey == "fail_threshold":
                            threshold = _as_int(hval, "cdp.health.fail_threshold")
                            config.cdp.health.fail_threshold = _validate_positive_int(
                                threshold, "cdp.health.fail_threshold", minimum=1
                            )
                        elif hkey == "poll_interval_s":
                            interval = _as_float(hval, "cdp.health.poll_interval_s")
                            config.cdp.health.poll_interval_s = _validate_positive_float(
                                interval, "cdp.health.poll_interval_s"
                            )
                        elif hkey == "shutdown_wait_s":
                            wait = _as_float(hval, "cdp.health.shutdown_wait_s")
                            config.cdp.health.shutdown_wait_s = _validate_positive_float(
                                wait, "cdp.health.shutdown_wait_s"
                            )
                        elif hasattr(config.cdp.health, hkey):
                            setattr(config.cdp.health, hkey, hval)
                elif key == "start_urls" and isinstance(value, dict):
                    for ukey, uval in value.items():
                        if hasattr(config.cdp.start_urls, ukey):
                            setattr(config.cdp.start_urls, ukey, uval)
                elif key == "port":
                    port = _as_int(value, "cdp.port")
                    config.cdp.port = _validate_port(port, "cdp.port")
                elif key == "start_timeout_s":
                    timeout = _as_float(value, "cdp.start_timeout_s")
                    config.cdp.start_timeout_s = _validate_positive_float(
                        timeout, "cdp.start_timeout_s"
                    )
                elif key == "probe_timeout_s":
                    timeout = _as_float(value, "cdp.probe_timeout_s")
                    config.cdp.probe_timeout_s = _validate_positive_float(
                        timeout, "cdp.probe_timeout_s"
                    )
                elif key == "probe_interval_s":
                    interval = _as_float(value, "cdp.probe_interval_s")
                    config.cdp.probe_interval_s = _validate_positive_float(
                        interval, "cdp.probe_interval_s"
                    )
                elif hasattr(config.cdp, key):
                    setattr(config.cdp, key, value)

        # Features section
        if "features" in loaded:
            for key, value in loaded["features"].items():
                if key == "token_align_frequency":
                    config.features.token_align_frequency = _as_int(
                        value, "features.token_align_frequency"
                    )
                elif hasattr(config.features, key):
                    setattr(config.features, key, value)

        # AI section (per-AI transport selection)
        # Expected TOML:
        # [ai.claude]
        # transport = "web"    # or "api" (future)
        if "ai" in loaded and isinstance(loaded["ai"], dict):
            for ai_name, ai_obj in loaded["ai"].items():
                if not isinstance(ai_obj, dict):
                    continue
                raw = str(ai_obj.get("transport", "web")).strip().lower()
                transport = raw if raw in {"web", "api"} else "web"
                if raw not in {"web", "api"}:
                    _logger.warning(
                        "Unknown transport '%s' for ai.%s; defaulting to 'web'",
                        raw,
                        ai_name,
                    )
                config.ai_transports[ai_name.lower().strip()] = transport
    except SystemExit:
        # Re-raise exit from validation helpers
        raise
    except Exception as e:
        _logger.error("Error merging config values: %s", e)
        sys.exit(EXIT_CONFIG_INVALID)

    return config


# ---------------------------------------------------------------------------
# Profile Directory Setup
# ---------------------------------------------------------------------------


def resolve_profile_dir(config_value: str) -> pathlib.Path:
    """
    Resolves the CDP profile directory path.

    Uses config value if provided, otherwise uses DEFAULT_PROFILE_DIR.
    Expands ~ and resolves to absolute path.

    Args:
        config_value: Profile directory from config (empty string means use default)

    Returns:
        Absolute path to profile directory
    """
    if config_value:
        path = pathlib.Path(config_value)
    else:
        path = DEFAULT_PROFILE_DIR

    # Expand ~ and resolve to absolute path
    path = path.expanduser().resolve()
    return path


def setup_profile_dir(profile_dir: pathlib.Path) -> None:
    """
    Creates and validates the CDP profile directory.

    Creates the directory with restrictive permissions (0o700).
    Verifies write access and exits with code 3 if not writable.

    Profile directories are intended to be private and not shared between users.

    Args:
        profile_dir: Path to the profile directory

    Exits:
        EXIT_PROFILE_DIR_NOT_WRITABLE if directory cannot be created or is not writable
    """
    # Create directory with restrictive umask
    old_umask = os.umask(0o077)
    try:
        profile_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        _logger.error("Failed to create profile directory %s: %s", profile_dir, e)
        sys.exit(EXIT_PROFILE_DIR_NOT_WRITABLE)
    finally:
        os.umask(old_umask)

    # Attempt to set restrictive permissions (best-effort, Option A)
    try:
        os.chmod(profile_dir, 0o700)
        _logger.debug("Set profile dir permissions to 0700: %s", profile_dir)
    except Exception as e:
        _logger.warning(
            "Could not set permissions on profile dir %s: %s. "
            "Ensure this directory is not shared and has restrictive permissions.",
            profile_dir,
            e,
        )

    # Validate write access
    test_file = profile_dir / ".write_test"
    try:
        test_file.touch()
        test_file.unlink()
    except PermissionError:
        uid, gid = os.getuid(), os.getgid()

        # Try to get human-readable names (POSIX only)
        if _POSIX_AVAILABLE:
            try:
                user_name = pwd.getpwuid(uid).pw_name
                group_name = grp.getgrgid(gid).gr_name
            except KeyError:
                user_name, group_name = str(uid), str(gid)
        else:
            user_name, group_name = str(uid), str(gid)

        _logger.error(
            "CDP profile dir not writable: %s\n"
            "  Running as: %s:%s (uid=%d, gid=%d)\n"
            "  Check: Flatpak permissions, SELinux, or override [cdp].profile_dir",
            profile_dir,
            user_name,
            group_name,
            uid,
            gid,
        )
        sys.exit(EXIT_PROFILE_DIR_NOT_WRITABLE)
    except Exception as e:
        _logger.error("Cannot write to profile directory %s: %s", profile_dir, e)
        sys.exit(EXIT_PROFILE_DIR_NOT_WRITABLE)

    # Post-write-test: check if permissions are actually 0700
    try:
        stat_info = os.stat(profile_dir)
        actual_mode = stat.S_IMODE(stat_info.st_mode)
        if actual_mode != 0o700:
            mode_str = oct(actual_mode)
            _logger.warning(
                "Profile dir %s has permissions %s (expected 0700). "
                "For security, run: chmod 700 %s",
                profile_dir,
                mode_str,
                profile_dir,
            )
    except Exception as e:
        _logger.debug("Could not stat profile dir for permission check: %s", e)

    _logger.info("CDP profile directory: %s", profile_dir)


# ---------------------------------------------------------------------------
# Runtime Directory Initialization
# ---------------------------------------------------------------------------


def initialize_runtime_dirs() -> None:
    """
    Creates all necessary runtime directories for the daemon.

    Sets restrictive permissions (0o700) on all directories.

    Note: AI_APP_CONFIG env var affects config file path only, not runtime
    directory layout. Runtime dirs always use PROJECT_ROOT/runtime/daemon/*.
    AI_APP_CONFIG must be set before process start if using custom config paths.
    """
    RUNTIME_DIR.mkdir(exist_ok=True)
    CONFIG_DIR.mkdir(exist_ok=True)
    LOG_DIR.mkdir(exist_ok=True)
    BROWSER_DIR.mkdir(exist_ok=True)

    # Set restrictive permissions on all runtime directories (best-effort)
    for directory in [RUNTIME_DIR, CONFIG_DIR, LOG_DIR, BROWSER_DIR]:
        try:
            os.chmod(directory, 0o700)
        except Exception as e:
            # Non-fatal; log at debug to avoid noise by default
            _logger.debug("Could not chmod %s: %s", directory, e)


# --- Create necessary directories on import ---
initialize_runtime_dirs()
