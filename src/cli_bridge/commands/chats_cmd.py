"""
Chat management commands.

This module provides CLI commands for managing chat history:
- list: List all chats from the sidebar
- switch: Switch to a specific chat
- new: Create a new chat
"""

from __future__ import annotations

import json

import requests
import typer

from ..errors import DaemonNotRunning

app = typer.Typer(help="Manage chat history", no_args_is_help=True)


def _make_request(host: str, port: int, endpoint: str, payload: dict) -> dict:
    """
    Make a request to the daemon API.

    Args:
        host: Daemon host
        port: Daemon port
        endpoint: API endpoint path
        payload: Request payload

    Returns:
        Response data as dict

    Raises:
        DaemonNotRunning: If daemon is not reachable
        requests.RequestException: On other HTTP errors
    """
    url = f"http://{host}:{port}{endpoint}"
    try:
        resp = requests.post(url, json=payload, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.ConnectionError as e:
        raise DaemonNotRunning(
            f"Cannot connect to daemon at {host}:{port}. Is it running?"
        ) from e


@app.command("list")
def list_chats(
    ai_name: str = typer.Argument(..., help="AI target (claude, chatgpt, gemini)"),
    host: str = typer.Option("127.0.0.1", help="Daemon host"),
    port: int = typer.Option(8000, help="Daemon port"),
    as_json: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """List all chats from the sidebar."""
    try:
        result = _make_request(host, port, "/chats/list", {"target": ai_name})

        if as_json:
            typer.echo(json.dumps(result, indent=2))
            return

        if not result.get("success"):
            error = result.get("error", {})
            typer.secho(f"Error: {error.get('message', 'Unknown error')}", fg=typer.colors.RED)
            raise typer.Exit(1)

        chats = result.get("chats", [])
        if not chats:
            typer.echo("No chats found.")
            return

        typer.secho(f"\nChats for {ai_name}:", fg=typer.colors.BRIGHT_CYAN, bold=True)
        for chat in chats:
            prefix = "→ " if chat.get("is_current") else "  "
            title = chat.get("title", "Untitled")
            chat_id = chat.get("chat_id", "")
            typer.echo(f"{prefix}{title} ({chat_id})")

    except DaemonNotRunning as e:
        typer.secho(str(e), fg=typer.colors.RED)
        raise typer.Exit(1)
    except Exception as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED)
        raise typer.Exit(1)


@app.command("switch")
def switch_chat(
    ai_name: str = typer.Argument(..., help="AI target (claude, chatgpt, gemini)"),
    chat_id: str = typer.Argument(..., help="Chat ID or URL to switch to"),
    host: str = typer.Option("127.0.0.1", help="Daemon host"),
    port: int = typer.Option(8000, help="Daemon port"),
):
    """Switch to a specific chat."""
    try:
        result = _make_request(
            host, port, "/chats/switch", {"target": ai_name, "chat_id": chat_id}
        )

        if result.get("success"):
            typer.secho(f"✓ Switched to chat: {chat_id}", fg=typer.colors.GREEN)
        else:
            error = result.get("error", {})
            typer.secho(f"Error: {error.get('message', 'Unknown error')}", fg=typer.colors.RED)
            raise typer.Exit(1)

    except DaemonNotRunning as e:
        typer.secho(str(e), fg=typer.colors.RED)
        raise typer.Exit(1)
    except Exception as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED)
        raise typer.Exit(1)


@app.command("new")
def new_chat(
    ai_name: str = typer.Argument(..., help="AI target (claude, chatgpt, gemini)"),
    host: str = typer.Option("127.0.0.1", help="Daemon host"),
    port: int = typer.Option(8000, help="Daemon port"),
):
    """Create a new chat."""
    try:
        result = _make_request(host, port, "/chats/new", {"target": ai_name})

        if result.get("success"):
            chat = result.get("chat", {})
            title = chat.get("title", "Untitled")
            typer.secho(f"✓ Created new chat: {title}", fg=typer.colors.GREEN)
        else:
            error = result.get("error", {})
            typer.secho(f"Error: {error.get('message', 'Unknown error')}", fg=typer.colors.RED)
            raise typer.Exit(1)

    except DaemonNotRunning as e:
        typer.secho(str(e), fg=typer.colors.RED)
        raise typer.Exit(1)
    except Exception as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED)
        raise typer.Exit(1)



