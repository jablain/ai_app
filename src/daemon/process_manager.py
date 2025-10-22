"""
Handles the lifecycle of the AI-CLI-Bridge daemon as a background process.

This module provides functions to start, stop, and check the status of the
daemon using a PID file to track the running process. This abstracts away
the OS-specific details of process management.
"""

import os
import signal
import subprocess
import sys
import time
from . import config

def is_running() -> bool:
    """
    Check if the daemon process is currently running.

    Returns:
        True if the PID file exists and a process with that PID is running,
        False otherwise.
    """
    if not config.PID_FILE.exists():
        return False
    
    try:
        pid = int(config.PID_FILE.read_text())
        # Sending signal 0 to a PID on Unix-like systems checks if the process
        # exists without actually sending a signal.
        os.kill(pid, 0)
    except (IOError, ValueError, OSError):
        # PID file might be corrupt, or process might not exist.
        return False
    else:
        return True

def start_daemon_process() -> bool:
    """
    Starts the daemon as a detached background process.

    It will check if the daemon is already running. If not, it spawns a new
    Python process to run the daemon's main module, redirects its output to
    a log file, and stores its PID.

    Returns:
        True if the daemon was started successfully, False otherwise.
    """
    if is_running():
        pid = config.PID_FILE.read_text()
        print(f"Daemon is already running with PID {pid}.")
        return False

    print(f"Starting daemon in the background...")
    print(f"Logs will be written to: {config.LOG_FILE}")

    # Ensure the log directory exists
    config.LOG_DIR.mkdir(parents=True, exist_ok=True)

    try:
        # Open the log file for stdout and stderr redirection
        log_file = open(config.LOG_FILE, 'a')
        
        # Command to run the daemon module
        command = [sys.executable, "-m", "ai_cli_bridge.daemon.main"]

        # Use subprocess.Popen to launch the process in the background.
        # os.setsid() is used on Unix to detach the new process from the
        # current terminal session, allowing it to continue running after
        # the parent script exits.
        process = subprocess.Popen(
            command,
            stdout=log_file,
            stderr=log_file,
            preexec_fn=os.setsid  # Detach from the terminal
        )

        # Write the new process's PID to the PID file.
        config.PID_FILE.write_text(str(process.pid))
        
        print(f"Daemon started successfully with PID {process.pid}.")
        return True
    except Exception as e:
        print(f"Error starting daemon: {e}", file=sys.stderr)
        return False

def stop_daemon_process() -> bool:
    """
    Stops the running daemon process.

    It reads the PID from the PID file and sends a termination signal
    to the process.

    Returns:
        True if the daemon was stopped successfully, False otherwise.
    """
    if not is_running():
        print("Daemon is not running.")
        return False

    try:
        pid = int(config.PID_FILE.read_text())
        print(f"Stopping daemon with PID {pid}...")
        
        # Send a SIGTERM signal to gracefully shut down the process.
        os.kill(pid, signal.SIGTERM)
        
        # Wait a moment to ensure the process has time to shut down.
        time.sleep(1)
        
        # Clean up the PID file if the process is gone.
        if not is_running():
            config.PID_FILE.unlink()
            print("Daemon stopped successfully.")
        else:
            print("Warning: Daemon process may not have shut down correctly.")
            
        return True
    except (IOError, ValueError, OSError) as e:
        print(f"Error stopping daemon: {e}", file=sys.stderr)
        # If we can't read the PID or the process is already gone,
        # just remove the stale PID file.
        if config.PID_FILE.exists():
            config.PID_FILE.unlink()
        return False

