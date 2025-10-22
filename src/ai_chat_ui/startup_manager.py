"""
Manages CDP browser and daemon startup sequence.
"""

import subprocess
import time
import os
from pathlib import Path
from typing import Tuple, Optional
import urllib.request
import json


class StartupManager:
    """Handles CDP and daemon startup/verification."""
    
    # Paths
    LAUNCH_CDP_SCRIPT = Path.home() / "dev/ai_app/ai-cli-bridge/LaunchCDP.sh"
    
    # Timeouts
    CDP_WAIT_TIMEOUT = 15  # seconds
    DAEMON_WAIT_TIMEOUT = 10  # seconds
    
    def __init__(self, daemon_client):
        """
        Initialize startup manager.
        
        Args:
            daemon_client: DaemonClient instance for health checks
        """
        self.daemon_client = daemon_client
    
    def check_cdp_running(self) -> bool:
        """
        Check if CDP browser is accessible on port 9223.
        
        Returns:
            True if CDP responds, False otherwise
        """
        try:
            with urllib.request.urlopen("http://127.0.0.1:9223/json/version", timeout=2) as response:
                data = json.loads(response.read().decode())
                ws_url = data.get("webSocketDebuggerUrl")
                return ws_url is not None and ws_url.startswith("ws://")
        except Exception:
            return False
    
    def launch_cdp(self) -> Tuple[bool, str]:
        """
        Launch CDP browser using LaunchCDP.sh script.
        
        Returns:
            Tuple of (success, message)
        """
        if not self.LAUNCH_CDP_SCRIPT.exists():
            return False, f"LaunchCDP.sh not found at: {self.LAUNCH_CDP_SCRIPT}"
        
        try:
            # Make script executable
            os.chmod(self.LAUNCH_CDP_SCRIPT, 0o755)
            
            # Launch script
            process = subprocess.Popen(
                [str(self.LAUNCH_CDP_SCRIPT)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Wait for CDP to become available
            start_time = time.time()
            while time.time() - start_time < self.CDP_WAIT_TIMEOUT:
                if self.check_cdp_running():
                    return True, "CDP browser started successfully"
                time.sleep(0.5)
            
            # Timeout - check if process is still running
            if process.poll() is None:
                # Process running but CDP not responding
                return False, "CDP browser started but not responding (timeout)"
            else:
                # Process died
                _, stderr = process.communicate(timeout=1)
                return False, f"CDP browser failed to start: {stderr[:200]}"
                
        except Exception as e:
            return False, f"Error launching CDP: {str(e)}"
    
    def check_daemon_running(self) -> bool:
        """
        Check if daemon is running and responsive.
        
        Returns:
            True if daemon responds to health check
        """
        return self.daemon_client.is_running()
    
    def start_daemon(self) -> Tuple[bool, str]:
        """
        Start the ai-cli-bridge daemon.
        
        Returns:
            Tuple of (success, message)
        """
        try:
            # Start daemon using CLI command
            process = subprocess.Popen(
                ["ai-cli-bridge", "daemon", "start"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Wait for daemon to become responsive
            start_time = time.time()
            while time.time() - start_time < self.DAEMON_WAIT_TIMEOUT:
                if self.check_daemon_running():
                    return True, "Daemon started successfully"
                time.sleep(0.5)
            
            # Timeout - check process status
            if process.poll() is None:
                return False, "Daemon process started but not responding (timeout)"
            else:
                _, stderr = process.communicate(timeout=1)
                return False, f"Daemon failed to start: {stderr[:200]}"
                
        except FileNotFoundError:
            return False, "ai-cli-bridge command not found. Is it installed?"
        except Exception as e:
            return False, f"Error starting daemon: {str(e)}"
    
    def ensure_ready(self) -> Tuple[bool, str]:
        """
        Ensure both CDP and daemon are running (start them if needed).
        
        This is the main entry point that follows the startup sequence:
        1. Check daemon
        2. If daemon down, check CDP
        3. If CDP down, launch it
        4. If CDP ok, start daemon
        5. Verify daemon is responsive
        
        Returns:
            Tuple of (success, message)
        """
        # Step 1: Check if daemon is already running
        if self.check_daemon_running():
            return True, "Daemon already running"
        
        # Step 2: Daemon not running, check CDP
        if not self.check_cdp_running():
            # Step 3: CDP not running, launch it
            success, message = self.launch_cdp()
            if not success:
                return False, f"Failed to launch CDP: {message}"
        
        # Step 4: CDP is running, start daemon
        success, message = self.start_daemon()
        if not success:
            return False, f"Failed to start daemon: {message}"
        
        # Step 5: Verify daemon is responsive
        if not self.check_daemon_running():
            return False, "Daemon started but not responding"
        
        return True, "CDP and daemon ready"
