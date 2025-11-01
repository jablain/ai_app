"""AI Chat UI - GTK4 interface for AI daemon"""

__version__ = "2.0.0"

# Defensive imports for setup/documentation contexts
try:
    from chat_ui.cli_wrapper import CLIWrapper as DaemonClient
    from chat_ui.main import main
except ImportError:
    DaemonClient = None
    main = None

__all__ = ["DaemonClient", "main", "__version__"]
