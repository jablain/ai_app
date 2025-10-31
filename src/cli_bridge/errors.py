"""
Custom exceptions for CLI error handling.
"""

class CLIError(Exception):
    """Base exception for all CLI errors."""
    exit_code: int = 1
    
    def __init__(self, message: str, exit_code: int | None = None):
        super().__init__(message)
        if exit_code is not None:
            self.exit_code = exit_code


class DaemonNotRunning(CLIError):
    """Daemon is not running or unreachable."""
    exit_code = 1


class DaemonUnhealthy(CLIError):
    """Daemon is running but unhealthy."""
    exit_code = 2


class UnknownAI(CLIError):
    """Requested AI target does not exist."""
    exit_code = 2


class DaemonStartupFailed(CLIError):
    """Daemon failed to start."""
    exit_code = 3


class DaemonShutdownFailed(CLIError):
    """Daemon failed to shut down cleanly."""
    exit_code = 4


class InvalidConfiguration(CLIError):
    """Configuration is invalid or cannot be loaded."""
    exit_code = 5
