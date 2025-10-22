"""
Typer command module for managing the AI-CLI-Bridge Daemon.

This file defines the `daemon` command group and its subcommands:
`start`, `stop`, and `status`. It uses the `process_manager` to handle the
actual lifecycle of the daemon process.
"""

import typer
import requests
from daemon import process_manager, config

# Create a new Typer app just for the 'daemon' subcommands
app = typer.Typer(
    help="Manage the long-running AI daemon process.",
    no_args_is_help=True
)

@app.command("start")
def start_daemon():
    """
    Start the background AI daemon.
    Initializes all AI instances and launches the browser for the session.
    """
    if process_manager.start_daemon_process():
        raise typer.Exit(0)
    else:
        raise typer.Exit(1)

@app.command("stop")
def stop_daemon():
    """
    Stop the background AI daemon.
    """
    if process_manager.stop_daemon_process():
        raise typer.Exit(0)
    else:
        raise typer.Exit(1)

@app.command("status")
def daemon_status():
    """
    Check the status of the AI daemon.
    """
    if not process_manager.is_running():
        print("Daemon status: 🛑 Not Running")
        raise typer.Exit(1)
    
    app_config = config.load_config()
    daemon_config = app_config.get("daemon", {})
    host = daemon_config.get("host", "127.0.0.1")
    port = daemon_config.get("port", 8000)
    url = f"http://{host}:{port}/status"
    
    try:
        response = requests.get(url, timeout=2)
        if response.status_code == 200:
            print("Daemon status: ✅ Running")
            # TODO: Add logic to pretty-print the JSON response from the status dashboard.
            print("\nDaemon Response:")
            print(response.json())
            return
        else:
            print(f"Daemon status: ⚠️ Responded with status {response.status_code}")
            raise typer.Exit(1)
    except requests.ConnectionError:
        print("Daemon status: 🟡 Running, but API is not responding.")
        print("   - Check logs for errors: tail -f " + str(config.LOG_FILE))
        raise typer.Exit(1)
    except Exception as e:
        print(f"An error occurred while checking status: {e}")
        raise typer.Exit(1)

# This is the entry point that the main cli.py will call
def run():
    app()

