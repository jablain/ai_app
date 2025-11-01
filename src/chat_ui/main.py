# ruff: noqa: E402
"""Main entry point for AI Chat UI"""

import sys
import logging

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Gio

from chat_ui.cli_wrapper import CLIWrapper
from chat_ui.startup_manager import StartupManager
from chat_ui.window import ChatWindow

# Application ID (reverse-DNS format)
APP_ID = "ai.app.chat_ui"

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def main():
    """Main entry point for AI Chat UI"""

    logger.info("Starting AI Chat UI v2.0.0")

    # Create daemon client
    daemon_client = CLIWrapper()
    logger.debug("CLIWrapper initialized")

    # Ensure daemon is running (blocks until ready or fails)
    startup_manager = StartupManager(daemon_client)
    if not startup_manager.ensure_daemon_ready():
        logger.error("Failed to start daemon. Exiting.")
        sys.exit(1)

    logger.info("Daemon ready, starting UI")

    # Create GTK application
    app = Gtk.Application(application_id=APP_ID, flags=Gio.ApplicationFlags.FLAGS_NONE)

    def on_activate(application):
        """Create and show main window"""
        window = ChatWindow(application=application, daemon_client=daemon_client)
        window.present()
        logger.info("Main window presented")

    def on_shutdown(application):
        """Cleanup on application shutdown"""
        logger.info("Application shutting down")
        # Close daemon client session
        daemon_client.close()
        logger.info("Daemon client closed")

    app.connect("activate", on_activate)
    app.connect("shutdown", on_shutdown)

    # Run GTK main loop
    exit_code = app.run(sys.argv)

    # Clean exit (daemon keeps running for other clients)
    logger.info("AI Chat UI exited (daemon continues running)")
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
