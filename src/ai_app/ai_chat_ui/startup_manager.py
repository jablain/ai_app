"""Startup manager for ensuring daemon is ready"""

import subprocess
import time
import logging
import threading
from typing import Optional

import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, GLib

logger = logging.getLogger(__name__)


class StartupDialog(Gtk.Window):
    """Simple startup dialog with spinner"""
    
    def __init__(self, parent: Optional[Gtk.Window] = None):
        super().__init__()
        self.set_title("Starting AI Chat")
        
        # Only set modal if we have a parent
        if parent:
            self.set_transient_for(parent)
            self.set_modal(True)
        
        self.set_default_size(300, 150)
        self.set_resizable(False)
        
        # Layout
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_top(20)
        box.set_margin_bottom(20)
        box.set_margin_start(20)
        box.set_margin_end(20)
        
        # Spinner
        spinner = Gtk.Spinner()
        spinner.start()
        spinner.set_size_request(32, 32)
        box.append(spinner)
        
        # Status label
        self.status_label = Gtk.Label()
        self.status_label.set_text("Starting daemon...")
        self.status_label.set_wrap(True)
        self.status_label.set_max_width_chars(40)
        box.append(self.status_label)
        
        self.set_child(box)
    
    def set_status(self, message: str):
        """Update status message"""
        self.status_label.set_text(message)


class StartupManager:
    """Ensures daemon is running before UI starts"""
    
    def __init__(self, daemon_client):
        self.daemon_client = daemon_client
        self.max_wait_seconds = 30
        self.cli_error = ""
    
    def ensure_daemon_ready(self, parent_window: Optional[Gtk.Window] = None) -> bool:
        """
        Ensure daemon is running and ready
        
        Must be called from the main thread.
        
        Returns True if daemon is ready, False if failed to start
        """
        # Check if already running
        if self.daemon_client.is_running():
            logger.info("✓ Daemon already running")
            return True
        
        # Show startup dialog
        dialog = StartupDialog(parent_window)
        dialog.present()
        
        # Start daemon via CLI in background thread with Event synchronization
        done = threading.Event()
        result = {"ok": False}
        
        def worker():
            ok = self._start_daemon_via_cli()
            if ok:
                ok = self._wait_for_daemon_ready(dialog)
            result["ok"] = ok
            GLib.idle_add(self._on_startup_complete, dialog, ok, parent_window)
            done.set()
        
        thread = threading.Thread(target=worker, daemon=True)
        thread.start()
        
        # Mini loop until done is set; keeps UI responsive (GTK4 pattern)
        # Note: This must run on the main thread
        ctx = GLib.MainContext.default()
        while not done.is_set():
            while ctx.pending():
                ctx.iteration(False)
            time.sleep(0.05)  # Small sleep to avoid busy-waiting
        
        return result["ok"]
    
    def _start_daemon_via_cli(self) -> bool:
        """Start daemon using ai-cli-bridge CLI"""
        try:
            logger.info("Starting daemon via CLI...")
            result = subprocess.run(
                ["ai-cli-bridge", "daemon", "start", "--wait"],
                capture_output=True,
                text=True,
                timeout=self.max_wait_seconds
            )
            
            if result.returncode == 0:
                logger.info("✓ CLI reported daemon started")
                return True
            else:
                # Combine stderr and stdout for full error context
                parts = []
                if result.stderr:
                    parts.append(result.stderr.strip())
                if result.stdout:
                    parts.append(result.stdout.strip())
                self.cli_error = "\n".join(parts)
                logger.error(f"✗ Daemon start failed:\n{self.cli_error}")
                return False
                
        except subprocess.TimeoutExpired:
            error = f"Daemon start timed out after {self.max_wait_seconds}s"
            logger.error(f"✗ {error}")
            self.cli_error = error
            return False
        except FileNotFoundError:
            error = "ai-cli-bridge command not found. Please ensure it is installed."
            logger.error(f"✗ {error}")
            self.cli_error = error
            return False
        except Exception as e:
            error = f"Failed to start daemon: {e}"
            logger.exception(f"✗ {error}")
            self.cli_error = str(e)
            return False
    
    def _wait_for_daemon_ready(self, dialog: StartupDialog) -> bool:
        """Poll /healthz until daemon responds or timeout"""
        start_time = time.time()
        attempt = 0
        
        while time.time() - start_time < 10:  # Extra 10s for safety
            attempt += 1
            
            # Update dialog on main thread
            GLib.idle_add(
                dialog.set_status,
                f"Waiting for daemon (attempt {attempt})..."
            )
            
            if self.daemon_client.is_running():
                logger.info(f"✓ Daemon ready after {attempt} attempts")
                return True
            
            time.sleep(0.5)
        
        logger.error("✗ Daemon not ready after polling")
        self.cli_error = "Daemon started but did not become healthy in time"
        return False
    
    def _on_startup_complete(self, dialog: StartupDialog, success: bool, parent: Optional[Gtk.Window]):
        """Called on main thread when startup completes"""
        dialog.close()
        
        if not success:
            self._show_error_dialog(parent)
        
        return False  # Don't repeat this idle callback
    
    def _show_error_dialog(self, parent: Optional[Gtk.Window]):
        """Show error dialog if daemon failed to start"""
        error_detail = self.cli_error or "Unknown error"
        
        # Truncate if too long
        if len(error_detail) > 500:
            error_detail = error_detail[:500] + "..."
        
        dialog = Gtk.MessageDialog(
            transient_for=parent,
            modal=True,
            message_type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.OK,
            text="Failed to Start Daemon"
        )
        dialog.format_secondary_text(
            f"Could not start the AI daemon.\n\n"
            f"Error:\n{error_detail}\n\n"
            f"Please ensure ai-cli-bridge is installed and try:\n"
            f"  ai-cli-bridge daemon start\n\n"
            f"Then restart the application."
        )
        
        def on_response(d, response_id):
            d.close()
            return False  # Don't repeat
        
        dialog.connect("response", on_response)
        dialog.present()
