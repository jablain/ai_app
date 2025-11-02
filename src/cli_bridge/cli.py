"""ai-cli-bridge CLI application entry point.

Defines the main Typer app and registers commands:
- daemon: Manage the background service (start, stop, status).
- send:   Send prompts to configured AI instances via the daemon.
- status: Check the status of the daemon and specific AI instances.
- version: Display the application version.
"""

from __future__ import annotations

import typer

# Import config and errors for dependency injection
from daemon.config import load_config

# Import version
from . import __version__

# Import command modules
from .commands import daemon_cmd
from .commands.send_cmd import run as send_run
from .commands.status_cmd import run as status_run
from .errors import InvalidConfiguration

# Create root CLI app
app = typer.Typer(
    add_completion=False,
    help=(
        "aicli — Drive logged-in AI web UIs via CDP.\n\n"
        "Examples:\n"
        "  aicli-bridge daemon start\n"
        "  aicli-bridge send claude 'hello'\n"
        "  aicli-bridge status --json\n"
    ),
    no_args_is_help=True,
)

# Wire in daemon command group (start, stop, status)
app.add_typer(daemon_cmd.app, name="daemon")


# ---------------------------------------------------------------------------
# Config Helper (Dependency Injection)
# ---------------------------------------------------------------------------


def _get_daemon_conn() -> tuple[str, int]:
    """
    Load daemon config and return (host, port).

    Centralizes config loading for all commands that need to connect to daemon.
    """
    try:
        cfg = load_config()
        return cfg.daemon.host, cfg.daemon.port
    except Exception as e:
        typer.secho(f"✗ Failed to load daemon config: {e}", fg=typer.colors.RED)
        raise typer.Exit(InvalidConfiguration.exit_code)


# ---------------------------------------------------------------------------
# Send Command
# ---------------------------------------------------------------------------


@app.command("send")
def send(
    ai_name: str = typer.Argument(..., help="Target AI profile (e.g., 'claude')."),
    message: str = typer.Argument(..., help="Text to send to the current conversation."),
    wait: bool = typer.Option(
        True,
        "--wait/--no-wait",
        help="Wait for assistant response and return a snippet (default: --wait).",
    ),
    timeout: int = typer.Option(
        120,
        "--timeout",
        help="Overall wait timeout in seconds (default 120).",
        min=1,
    ),
    as_json: bool = typer.Option(
        False,
        "--json",
        help="Emit a JSON envelope (includes 'snippet' and 'markdown' when available).",
    ),
    debug: bool = typer.Option(
        False,
        "--debug",
        help="Enable debug output.",
    ),
    inject: str | None = typer.Option(
        None,
        "--inject",
        help="Inject additional context into the conversation.",
    ),
    contextsize: int | None = typer.Option(
        None,
        "--context-size",
        help="Override context window size.",
    ),
):
    """
    Send a message to the current conversation.

    The daemon must be running for this command to work.
    Use 'daemon start' to start the daemon first.

    Examples:
        ai-cli-bridge send claude "What is the weather?"
        ai-cli-bridge send gemini --no-wait "Summarize this article"
        ai-cli-bridge send chatgpt --json "Translate to French: Hello"
        ai-cli-bridge send claude --inject "You are a pirate" "Tell me a story"
    """
    host, port = _get_daemon_conn()
    raise typer.Exit(
        send_run(host, port, ai_name, message, wait, timeout, as_json, debug, inject, contextsize)
    )


# ---------------------------------------------------------------------------
# Status Command
# ---------------------------------------------------------------------------


@app.command("status")
def status(
    ai_name: str = typer.Argument(
        "", help="Target AI profile name (e.g., 'claude'). Leave empty for all AIs."
    ),
    as_json: bool = typer.Option(False, "--json", help="Emit a JSON envelope."),
):
    """
    Report status for one or all AI instances.

    Shows connection status, transport type, and session metrics.
    The daemon must be running for this command to work.

    Examples:
        ai-cli-bridge status
        ai-cli-bridge status claude
        ai-cli-bridge status gemini --json
    """
    host, port = _get_daemon_conn()
    raise typer.Exit(status_run(host, port, ai_name, as_json))


# ---------------------------------------------------------------------------
# Version Command
# ---------------------------------------------------------------------------


@app.command("version")
def version():
    """Print ai-cli-bridge version."""
    typer.echo(f"ai-cli-bridge {__version__}")


# ---------------------------------------------------------------------------
# Main Entry Point
# ---------------------------------------------------------------------------


def main():
    """Main entry point for the CLI."""
    app()


if __name__ == "__main__":
    main()
