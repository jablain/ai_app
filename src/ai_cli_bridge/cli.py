# ai_cli_bridge/cli.py

from __future__ import annotations
import typer

# Import only commands that still exist
from .commands.status_cmd import run as status_run
from .commands.send_cmd import run as send_run
from .commands.init_cdp_cmd import run as init_cdp_run

# Import daemon command group
from .commands import daemon_cmd

app = typer.Typer(
    add_completion=False,
    help="ai-cli-bridge — Drive logged-in AI web UIs via CDP (Playwright).",
    no_args_is_help=True,
)

# Add daemon subcommand group
app.add_typer(daemon_cmd.app, name="daemon")

@app.command("init-cdp")
def init_cdp(
    ai_name: str = typer.Argument(..., help="Target AI (e.g., 'claude'). Launch Playwright Chromium in CDP mode."),
):
    """
    Launch Playwright Chromium with remote debugging and a persistent user data dir.
    Prints the DevTools ws URL.
    """
    raise typer.Exit(init_cdp_run(ai_name))

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
        help="Overall wait timeout in seconds (default 120; if unchanged, config.response_wait applies).",
        min=1,
    ),
    json: bool = typer.Option(
        False,
        "--json",
        help="Emit a JSON envelope (includes 'snippet' and 'markdown' when available).",
    ),
    debug: bool = typer.Option(
        False,
        "--debug",
        help="Enable debug output.",
    ),
):
    """
    Send a message to the current conversation.
    """
    raise typer.Exit(send_run(ai_name, message, wait, timeout, json, debug))

@app.command("status")
def status(
    ai_name: str = typer.Argument(..., help="Target AI profile name (e.g., 'claude')."),
    json: bool = typer.Option(False, "--json", help="Emit a JSON envelope."),
):
    """Report CDP attach, current page URL, and selector sanity for the target."""
    raise typer.Exit(status_run(ai_name, json))

@app.command("version")
def version():
    """
    Print ai-cli-bridge version.
    """
    typer.echo("ai-cli-bridge 2.0.0")

def main():
    app()

if __name__ == "__main__":
    main()
