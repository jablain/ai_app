"""
Client implementation for the 'send' command.

This module is responsible for sending a prompt to the running AI daemon
and displaying the response. It acts as a lightweight client, packaging the
user's request and sending it over HTTP.
"""

import typer
import requests
import json as json_lib  # Renamed to avoid conflict with the 'json' parameter

# Import the daemon config to know where to connect
from daemon import config as daemon_config


def run(
    ai_name: str,
    message: str,
    wait: bool,
    timeout: int,
    json: bool,
    debug: bool,
    # New parameters to be added in the future
    inject: str | None = None,
    contextsize: int | None = None,
) -> int:
    """
    Executes the 'send' command by sending a request to the daemon.
    """
    try:
        # Load daemon configuration to get host and port
        cfg = daemon_config.load_config()
        host = cfg.daemon.host
        port = cfg.daemon.port
        daemon_url = f"http://{host}:{port}/send"

        # Construct the JSON payload for the request
        payload = {
            "target": ai_name,
            "prompt": message,
            "wait_for_response": wait,
            "timeout_s": timeout,
            # Pass along other relevant options
            "debug": debug,
            "inject": inject,
            "context_size": contextsize,
        }

        # Send the request to the daemon
        # The timeout for the request should be slightly longer than the operation timeout
        response = requests.post(daemon_url, json=payload, timeout=timeout + 10)
        response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)

        # Process the response from the daemon
        response_data = response.json()

        if json:
            # If --json flag is used, print the entire JSON response
            typer.echo(json_lib.dumps(response_data, indent=2))
        else:
            # Otherwise, provide a human-readable summary
            if response_data.get("success"):
                typer.secho("✓ Sent", fg=typer.colors.GREEN)
                metadata = response_data.get("metadata", {})
                snippet = response_data.get("snippet")

                if snippet:
                    typer.echo(f"  elapsed: {metadata.get('elapsed_ms')} ms")
                    typer.echo("  response:")
                    # CORRECTED LOGIC: Perform the replacement before the f-string
                    formatted_snippet = snippet.replace("\n", "\n    ")
                    typer.echo(f"    {formatted_snippet}")
            else:
                error_msg = response_data.get("metadata", {}).get("error", "Unknown error")
                typer.secho(f"✗ Error: {error_msg}", fg=typer.colors.RED)
                return 1

    except requests.exceptions.ConnectionError:
        typer.secho(
            "Error: Cannot connect to the AI daemon. Is it running?",
            fg=typer.colors.RED,
        )
        typer.echo("Please start it with 'ai-cli-bridge daemon start'")
        return 1
    except requests.exceptions.HTTPError as e:
        typer.secho(
            f"Error: Received an error response from the daemon: {e.response.status_code}",
            fg=typer.colors.RED,
        )
        try:
            # Try to print the detailed error from the daemon's response
            typer.echo(e.response.json().get("detail", "No details provided."))
        except json_lib.JSONDecodeError:
            typer.echo("Could not parse error details from the daemon response.")
        return 1
    except Exception as e:
        typer.secho(f"An unexpected error occurred: {e}", fg=typer.colors.RED)
        return 1

    return 0
