"""
Configuration constants for CLI operations.
"""

# Daemon readiness polling
DAEMON_READINESS_POLL_INTERVAL_S = 0.5  # Poll interval for health checks (also used as backoff cap)
DAEMON_READINESS_DEFAULT_TIMEOUT_S = 15.0  # Default timeout waiting for readiness
DAEMON_READINESS_TIMEOUT_BUFFER_S = 5.0  # Buffer added to CDP timeout

# Daemon shutdown
GRACEFUL_SHUTDOWN_TIMEOUT_S = 12.0  # Time to wait for SIGTERM to complete
SIGTERM_RETRY_INTERVAL_S = 0.1  # How often to check if process died
FORCE_KILL_RETRY_WAIT_S = 1.0  # Wait after SIGKILL before final check

# API communication
API_HEALTH_CHECK_TIMEOUT_S = 1.0  # Timeout for /healthz endpoint
API_STATUS_CHECK_TIMEOUT_S = 3.0  # Timeout for /status endpoint (heavier)
API_REQUEST_TIMEOUT_BUFFER_S = 10  # Added to operation timeout for HTTP request
