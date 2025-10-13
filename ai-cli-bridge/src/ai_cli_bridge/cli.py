# ai_cli_bridge/cli.py

from __future__ import annotations
import typer

# Import run() directly from each module (harmonized style)
from .commands.open_cmd import run as open_run
from .commands.doctor_cmd import run as doctor_run
from .commands.init_cmd import run as init_run
from .commands.init_cdp_cmd import run as init_cdp_run
from .commands.status_cmd import run as status_run
from .commands.send_cmd import run as send_run

# If you've added inspect_cmd.py, uncomment these two lines:
# from .commands.inspect_cmd import run as inspect_run

app = typer.Typer(
    add_completion=False,
    help="ai-cli-bridge — Drive logged-in AI web UIs via CDP (Playwright).",
    no_args_is_help=True,
)

@app.command("init")
def init(
    ai_name: str = typer.Argument(..., help="Target AI profile to initialize (non-CDP)."),
):
    """
    Initialize target AI profile (non-CDP).
    """
    raise typer.Exit(init_run(ai_name))


@app.command("init-cdp")
def init_cdp(
    ai_name: str = typer.Argument(..., help="Target AI (e.g., 'claude'). Launch Playwright Chromium in CDP mode."),
):
    """
    Launch Playwright Chromium with remote debugging and a persistent user data dir.
    Prints the DevTools ws URL.
    """
    raise typer.Exit(init_cdp_run(ai_name))


@app.command("open")
def open_cmd(
    ai_name: str = typer.Argument(..., help="Target AI profile (e.g., 'claude')."),
    conversation: str | None = typer.Option(
        None,
        "--conversation",
        help="Optional conversation URL to open/attach.",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help="Force navigation even if already on the same origin.",
    ),
):
    """
    Attach to the running CDP Chromium and open/attach to a target conversation.
    Respects 'no reload if already on origin' logic.
    """
    raise typer.Exit(open_run(ai_name, conversation, force))


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
    debug: bool = typer.Option(  # ADD THIS
        False,
        "--debug",
        help="Enable debug output.",
    ),
):
    """
    Send a message to the current conversation.
    """
    raise typer.Exit(send_run(ai_name, message, wait, timeout, json, debug))  # Pass debug

@app.command("doctor")
def doctor():
    """
    Basic environment/system checks.
    """
    raise typer.Exit(doctor_run())


# If you've added inspect_cmd.py, uncomment this command to expose it:
# @app.command("inspect")
# def inspect(
#     ai_name: str = typer.Argument(..., help="Target AI (e.g., 'claude')."),
# ):
#     """
#     Capture structural snapshots of the current page (selectors matrix, AX tree, HTML, screenshot).
#     Artifacts are written under ~/.ai_cli_bridge/debug/<timestamp>/.
#     """
#     raise typer.Exit(inspect_run(ai_name))


@app.command("version")
def version():
    """
    Print ai-cli-bridge version.
    """
    # Keep in sync with pyproject.toml
    typer.echo("ai-cli-bridge 1.3.1")


def main():
    app()


if __name__ == "__main__":
    main()
    
@app.command("status")
def status(
    ai_name: str = typer.Argument(..., help="Target AI profile name (e.g., 'claude')."),
    json: bool = typer.Option(False, "--json", help="Emit a JSON envelope."),
):
    """Report CDP attach, current page URL, and selector sanity for the target."""
    raise typer.Exit(status_run(ai_name, json))

