"""
Client implementation for the 'send' command.

This module is responsible for sending a prompt to the running AI daemon
and displaying the response. It acts as a lightweight client, packaging the
user's request and sending it over HTTP.
"""

import json

import requests
import typer

from ..constants import API_REQUEST_TIMEOUT_BUFFER_S
from ..errors import DaemonNotRunning


def run(
    host: str,
    port: int,
    ai_name: str,
    message: str,
    wait: bool,
    timeout: int,
    as_json: bool,
    debug: bool,
    inject: str | None = None,
    contextsize: int | None = None,
) -> int:
    """
    Executes the 'send' command by sending a request to the daemon.

    Args:
        host: Daemon host (from config)
        port: Daemon port (from config)
        ai_name: Target AI name
        message: Message to send
        wait: Whether to wait for response
        timeout: Operation timeout in seconds
        as_json: Output as JSON
        debug: Enable debug output
        inject: Optional injection parameter
        contextsize: Optional context size parameter

    Returns:
        Exit code (0 for success, non-zero for errors)
    """
    # Validate AI name
    ai_name = ai_name.strip()
    if not ai_name:
        typer.secho("✗ AI name cannot be empty", fg=typer.colors.RED)
        return 1
    if len(ai_name) > 64:
        typer.secho("✗ AI name too long (max 64 characters)", fg=typer.colors.RED)
        return 1

    try:
        daemon_url = f"http://{host}:{port}/send"

        # Validate timeout
        request_timeout = max(timeout + API_REQUEST_TIMEOUT_BUFFER_S, 15)

        # Construct payload
        payload = {
            "target": ai_name,
            "prompt": message,
            "wait_for_response": wait,
            "timeout_s": timeout,
            "debug": debug,
            "inject": inject,
            "context_size": contextsize,
        }

        # Send request
        response = requests.post(daemon_url, json=payload, timeout=request_timeout)
        response.raise_for_status()

        # Process response - handle non-JSON responses
        try:
            response_data = response.json()
        except json.JSONDecodeError:
            typer.secho("✗ Invalid response from daemon (not JSON)", fg=typer.colors.RED)
            typer.echo(f"  Status: {response.status_code}")
            typer.echo(f"  Body preview: {response.text[:200]}")
            if debug:
                typer.echo(f"  Full body: {response.text}")
            return 1

        if as_json:
            # Uniform JSON envelope
            success = response_data.get("success", False)
            metadata = response_data.get("metadata", {})

            envelope = {
                "ok": success,
                "code": 0 if success else 1,
                "message": "Success"
                if success
                else (
                    metadata.get("error", {}).get("message")
                    if isinstance(metadata.get("error"), dict)
                    else str(metadata.get("error", "Failed"))
                ),
                "data": {
                    "snippet": response_data.get("snippet"),
                    "markdown": response_data.get("markdown"),
                    # Pass through ALL metadata from daemon
                    **metadata,  # This spreads all metadata fields into data
                },
            }
            typer.echo(json.dumps(envelope, indent=2))
        else:
            # Human-readable output
            if response_data.get("success"):
                typer.secho("✓ Sent", fg=typer.colors.GREEN)
                metadata = response_data.get("metadata", {})
                snippet = response_data.get("snippet")

                if snippet:
                    typer.echo(f"  elapsed: {metadata.get('elapsed_ms')} ms")
                    typer.echo("  response:")
                    # Fixed formatting: only add indentation once
                    for line in snippet.splitlines():
                        typer.echo(f"    {line}")
            else:
                error_data = response_data.get("metadata", {}).get("error", {})
                if isinstance(error_data, dict):
                    error_msg = error_data.get("message", "Unknown error")
                else:
                    error_msg = str(error_data) if error_data else "Unknown error"
                typer.secho(f"✗ Error: {error_msg}", fg=typer.colors.RED)
                return 1

        return 0

    except requests.exceptions.ConnectionError:
        typer.secho(
            "✗ Cannot connect to daemon",
            fg=typer.colors.RED,
        )
        typer.echo("  Is it running? Try: aicli daemon start")
        return DaemonNotRunning.exit_code

    except requests.exceptions.HTTPError as e:
        typer.secho(
            f"✗ Daemon error (HTTP {e.response.status_code})",
            fg=typer.colors.RED,
        )
        try:
            detail = e.response.json()
            typer.echo(f"  {detail.get('detail', 'No details provided')}")
        except Exception:
            # Daemon returned non-JSON error
            typer.echo(f"  Response: {e.response.text[:200]}")
        return 1

    except Exception as e:
        typer.secho(f"✗ Unexpected error: {e}", fg=typer.colors.RED)
        if debug:
            raise
        return 1
