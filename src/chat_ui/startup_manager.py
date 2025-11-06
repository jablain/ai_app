# ruff: noqa: E402
"""Startup manager for ensuring daemon is ready"""

from __future__ import annotations

import logging
import subprocess
import threading
import time

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk

logger = logging.getLogger(__name__)

# Startup Constants
STARTUP_DIALOG_WIDTH = 300
STARTUP_DIALOG_HEIGHT = 150
SPINNER_SIZE = 32
MARGIN = 20
MAX_ERROR_LENGTH = 500

# Timeout Constants (seconds)
DEFAULT_MAX_WAIT_S = 30
DAEMON_READY_WAIT_S = 10
POLL_INTERVAL_S = 0.5
MAIN_LOOP_SLEEP_S = 0.05


class StartupDialog(Gtk.Window):
    """Simple startup dialog with spinner"""

    def __init__(self, parent: Gtk.Window | None = None) -> None:
        super().__init__()
        self.set_title("Starting AI Chat")

        # Only set modal if we have a parent
        if parent:
            self.set_transient_for(parent)
            self.set_modal(True)

        self.set_default_size(STARTUP_DIALOG_WIDTH, STARTUP_DIALOG_HEIGHT)
        self.set_resizable(False)

        # Layout
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_top(MARGIN)
        box.set_margin_bottom(MARGIN)
        box.set_margin_start(MARGIN)
        box.set_margin_end(MARGIN)

        # Spinner
        spinner = Gtk.Spinner()
        spinner.start()
        spinner.set_size_request(SPINNER_SIZE, SPINNER_SIZE)
        box.append(spinner)

        # Status label
        self.status_label = Gtk.Label()
        self.status_label.set_text("Starting daemon...")
        self.status_label.set_wrap(True)
        self.status_label.set_max_width_chars(40)
        box.append(self.status_label)

        self.set_child(box)

    def set_status(self, message: str) -> None:
        """Update status message"""
        self.status_label.set_text(message)


class StartupManager:
    """Ensures daemon is running before UI starts"""

    def __init__(self, daemon_client: object) -> None:
        self.daemon_client = daemon_client
        self.max_wait_seconds = DEFAULT_MAX_WAIT_S
        self.cli_error = ""

    def ensure_daemon_ready(self, parent_window: Gtk.Window | None = None) -> bool:
        """
        Ensure daemon is running and ready

        Must be called from the main thread.

        Args:
            parent_window: Optional parent window for dialog

        Returns:
            True if daemon is ready, False if failed to start
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

        def worker() -> None:
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
            time.sleep(MAIN_LOOP_SLEEP_S)  # Small sleep to avoid busy-waiting

        return result["ok"]

    def _start_daemon_via_cli(self) -> bool:
        """Start daemon using ai-cli-bridge CLI"""
        try:
            logger.info("Starting daemon via CLI...")
            result = subprocess.run(
                ["ai-cli-bridge", "daemon", "start", "--wait"],
                capture_output=True,
                text=True,
                timeout=self.max_wait_seconds,
            )

            if result.returncode == 0:
                logger.info("✓ CLI reported daemon started")
                return True

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

        while time.time() - start_time < DAEMON_READY_WAIT_S:
            attempt += 1

            # Update dialog on main thread
            GLib.idle_add(dialog.set_status, f"Waiting for daemon (attempt {attempt})...")

            if self.daemon_client.is_running():
                logger.info(f"✓ Daemon ready after {attempt} attempts")
                return True

            time.sleep(POLL_INTERVAL_S)

        logger.error("✗ Daemon not ready after polling")
        self.cli_error = "Daemon started but did not become healthy in time"
        return False

    def _on_startup_complete(
        self, dialog: StartupDialog, success: bool, parent: Gtk.Window | None
    ) -> bool:
        """Called on main thread when startup completes"""
        dialog.close()

        if not success:
            self._show_error_dialog(parent)

        return False  # Don't repeat this idle callback

    def _show_error_dialog(self, parent: Gtk.Window | None) -> None:
        """Show error dialog if daemon failed to start"""
        error_detail = self.cli_error or "Unknown error"

        # Truncate if too long
        if len(error_detail) > MAX_ERROR_LENGTH:
            error_detail = error_detail[:MAX_ERROR_LENGTH] + "..."

        dialog = Gtk.MessageDialog(
            transient_for=parent,
            modal=True,
            message_type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.OK,
            text="Failed to Start Daemon",
        )
        dialog.format_secondary_text(
            f"Could not start the AI daemon.\n\n"
            f"Error:\n{error_detail}\n\n"
            f"Please ensure ai-cli-bridge is installed and try:\n"
            f"  ai-cli-bridge daemon start\n\n"
            f"Then restart the application."
        )

        def on_response(d: Gtk.MessageDialog, response_id: int) -> bool:
            d.close()
            return False  # Don't repeat

        dialog.connect("response", on_response)
        dialog.present()
