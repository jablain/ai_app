"""
Main entry point for the AI-CLI-Bridge Daemon (v2.0.0 with typed DTOs).

Key features (unchanged from behavior perspective):
- Browser connection pool created once and injected into AI instances
- Web-specific dependencies properly isolated
- Clean separation between BaseAI interface and WebAI implementation
- Separate AI status and transport status endpoints
- Standard Python logging configured at startup

NEW in this revision:
- Introduced Pydantic DTOs for /send and /status to validate requests and
  guarantee response shapes without changing external behavior.
"""

from __future__ import annotations

import asyncio
import logging
import os
import signal
import time
from pathlib import Path
from typing import Any, Dict, Optional, List

from fastapi import FastAPI, HTTPException
from contextlib import asynccontextmanager

from pydantic import BaseModel, Field, ConfigDict

from .ai.factory import AIFactory
from .ai.web_base import BrowserConnectionPool, WebAIBase
from . import config

# ---------------------------------------------------------------------------
# Daemon State
# ---------------------------------------------------------------------------

daemon_state: Dict[str, Any] = {
    "ai_instances": {},           # Persistent AI objects {name: instance}
    "locks": {},                  # Concurrency locks {name: asyncio.Lock}
    "browser_pool": None,         # Shared browser connection pool
    "browser_pid": None,          # Browser process ID for shutdown
}


# ---------------------------------------------------------------------------
# DTOs (Data Transfer Objects)
# ---------------------------------------------------------------------------

class SendRequest(BaseModel):
    """Request payload for /send."""
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    target: str = Field(..., description="AI name (e.g., 'claude', 'chatgpt', 'gemini')")
    prompt: str = Field(..., description="Message to send to the AI")
    wait_for_response: bool = Field(True, description="Wait for AI response")
    timeout_s: int = Field(120, ge=1, description="Overall timeout in seconds")
    debug: bool = Field(False, description="Enable debug output (currently unused server-side)")
    inject: Optional[str] = Field(None, description="Reserved for future use")
    context_size: Optional[int] = Field(
        None,
        ge=1,
        description="Reserved for future use (context window override)"
    )


class SendResponse(BaseModel):
    """Response envelope for /send."""
    model_config = ConfigDict(extra="allow")

    success: bool
    snippet: Optional[str] = None
    markdown: Optional[str] = None
    metadata: Dict[str, Any]


class DaemonInfo(BaseModel):
    """Daemon-level status section."""
    version: str
    available_ais: List[str]
    browser_pool_active: bool


class AIStatusPayload(BaseModel):
    """
    AI status payload (combined domain + transport fields).

    NOTE: We allow extras so we don't break if a transport adds fields later.
    """
    model_config = ConfigDict(extra="allow")

    # Domain/session metrics (BaseAI)
    ai_target: str
    turn_count: int
    token_count: int
    message_count: int
    session_duration_s: float
    last_interaction_time: Optional[float] = None
    ctaw_size: int
    ctaw_usage_percent: float

    # Transport status (web/api-specific)
    transport_type: str
    connected: bool
    cdp_url: Optional[str] = None
    cdp_source: Optional[str] = None
    last_page_url: Optional[str] = None

    # Error (if any)
    error: Optional[str] = None


class StatusEnvelope(BaseModel):
    """Top-level status envelope returned by /status."""
    daemon: DaemonInfo
    ais: Dict[str, AIStatusPayload]


# ---------------------------------------------------------------------------
# CDP Browser Verification
# ---------------------------------------------------------------------------

def verify_cdp_browser() -> bool:
    """Verify that the CDP browser is running on port 9223."""
    import urllib.request
    import json

    try:
        with urllib.request.urlopen("http://127.0.0.1:9223/json/version", timeout=2) as response:
            data = json.loads(response.read().decode())
            ws_url = data.get("webSocketDebuggerUrl")
            if ws_url and ws_url.startswith("ws://"):
                print(f"    ✓ CDP browser detected: {ws_url}")
                return True
    except Exception as e:
        print(f"    ✗ CDP browser not accessible: {e}")

    return False


def read_browser_pid() -> int | None:
    """Read the browser PID from the PID file."""
    pid_file = config.PROJECT_ROOT / "runtime" / "browser.pid"

    if not pid_file.exists():
        return None

    try:
        pid = int(pid_file.read_text().strip())
        os.kill(pid, 0)  # Verify process exists
        return pid
    except (ValueError, ProcessLookupError, PermissionError):
        return None


def stop_browser(pid: int) -> None:
    """Gracefully stop the CDP browser process."""
    try:
        print(f"    → Stopping browser (PID: {pid})...")
        os.kill(pid, signal.SIGTERM)

        # Wait up to 10 seconds for graceful shutdown
        for _ in range(100):
            try:
                os.kill(pid, 0)
                time.sleep(0.1)
            except ProcessLookupError:
                print("    ✓ Browser stopped gracefully")
                return

        # Force kill if still running
        print("    ⚠ Browser did not stop gracefully, forcing...")
        os.kill(pid, signal.SIGKILL)
        time.sleep(0.5)
        print("    ✓ Browser stopped (forced)")

    except ProcessLookupError:
        print("    ✓ Browser already stopped")
    except Exception as e:
        print(f"    ⚠ Error stopping browser: {e}")


# ---------------------------------------------------------------------------
# FastAPI Lifespan Management
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Handles startup and shutdown events for the FastAPI application.

    Startup:
    - Configure logging
    - Verify CDP browser is running
    - Create shared browser connection pool
    - Create persistent AI instances
    - Inject browser pool into web-based AIs

    Shutdown:
    - Close all browser connections
    - Stop CDP browser gracefully
    """
    print("🚀 AI-CLI-Bridge Daemon starting up...")

    # Step 0: Configure logging
    app_config = config.load_config()
    log_level = app_config.get("daemon", {}).get("log_level", "INFO").upper()
    logging.basicConfig(
        level=getattr(logging, log_level, logging.INFO),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)
    logger.info("Logging configured")

    # Load configuration
    daemon_state["config"] = app_config
    print("    ✓ Configuration loaded")

    # Step 1: Verify CDP browser is running
    print("    → Verifying CDP browser...")
    if not verify_cdp_browser():
        print("\n❌ CRITICAL: CDP browser is not running on port 9223")
        print("   Please start it first:")
        print("   ./LaunchCDP.sh")
        raise RuntimeError("CDP browser not available")

    # Step 2: Read browser PID for later shutdown
    browser_pid = read_browser_pid()
    if browser_pid:
        daemon_state["browser_pid"] = browser_pid
        print(f"    ✓ Browser PID: {browser_pid}")
    else:
        print("    ⚠ Warning: Could not read browser PID (shutdown may not work)")

    # Step 3: Create shared browser connection pool
    print("    → Creating browser connection pool...")
    daemon_state["browser_pool"] = BrowserConnectionPool()
    print("    ✓ Browser connection pool created")

    # Step 4: Import all AI modules to trigger registration
    print("    → Registering AI implementations...")
    AIFactory.import_all_ais()
    available_ais = AIFactory.list_available()
    print(f"    ✓ Available AIs: {', '.join(available_ais)}")

    # Step 5: Create persistent AI instances
    print("    → Creating persistent AI instances...")
    for ai_name in available_ais:
        try:
            # Get AI class and its default config
            ai_class = AIFactory.get_class(ai_name)
            ai_config = ai_class.get_default_config()

            # Create instance
            instance = AIFactory.create(ai_name, ai_config)

            # Inject browser pool if this is a web-based AI
            if isinstance(instance, WebAIBase):
                instance.set_browser_pool(daemon_state["browser_pool"])
                print(f"      ✓ '{ai_name}' instance created (web-based)")
            else:
                print(f"      ✓ '{ai_name}' instance created (API-based)")

            # Store instance and create lock
            daemon_state["ai_instances"][ai_name] = instance
            daemon_state["locks"][ai_name] = asyncio.Lock()

        except Exception as e:
            logger.error(f"Failed to create '{ai_name}': {e}", exc_info=True)
            print(f"      ✗ Failed to create '{ai_name}': {e}")
            # Continue with other AIs even if one fails

    if not daemon_state["ai_instances"]:
        print("\n❌ CRITICAL: No AI instances were created")
        raise RuntimeError("No AI instances available")

    print("✅ Daemon startup complete. Ready for requests.\n")

    # Yield control to FastAPI (server runs here)
    yield

    # --- Shutdown Logic ---
    print("\n🔌 AI-CLI-Bridge Daemon shutting down...")

    # Close browser connection pool
    if daemon_state["browser_pool"]:
        print("    → Closing browser connections...")
        await daemon_state["browser_pool"].close_all()
        print("    ✓ Browser connections closed")

    # Stop the CDP browser if we have its PID
    if daemon_state.get("browser_pid"):
        stop_browser(daemon_state["browser_pid"])

        # Clean up PID file
        pid_file = config.PROJECT_ROOT / "runtime" / "browser.pid"
        try:
            pid_file.unlink(missing_ok=True)
            print("    ✓ Cleaned up browser PID file")
        except Exception as e:
            print(f"    ⚠ Could not clean up PID file: {e}")

    print("🛑 Daemon shutdown complete.")


# ---------------------------------------------------------------------------
# FastAPI App Initialization
# ---------------------------------------------------------------------------

app = FastAPI(
    title="AI-CLI-Bridge Daemon",
    description="Manages persistent AI instances and browser interactions",
    version="2.0.0",
    lifespan=lifespan
)


# ---------------------------------------------------------------------------
# API Endpoints
# ---------------------------------------------------------------------------

@app.get("/")
async def root():
    """Root endpoint - basic health check."""
    return {
        "service": "ai-cli-bridge-daemon",
        "version": "2.0.0",
        "status": "running",
        "architecture": "clean_separation_v2"
    }


@app.get("/status", response_model=StatusEnvelope)
async def get_status():
    """
    Get high-level status of all managed AI instances.

    Returns separate AI status and transport status for clean separation.
    """
    daemon_info = DaemonInfo(
        version="2.0.0",
        available_ais=list(daemon_state["ai_instances"].keys()),
        browser_pool_active=daemon_state["browser_pool"] is not None,
    )

    ais: Dict[str, AIStatusPayload] = {}

    # Get status from each AI instance
    for ai_name, ai_instance in daemon_state["ai_instances"].items():
        try:
            # Combine AI status and transport status
            ai_status = ai_instance.get_ai_status()       # domain-agnostic metrics
            transport_status = ai_instance.get_transport_status()  # transport info

            payload = {**ai_status, **transport_status}
            # Coerce into model (allows extra fields for forward-compat)
            ais[ai_name] = AIStatusPayload(**payload)

        except Exception as e:
            logging.getLogger(__name__).error(
                f"Error getting status for {ai_name}: {e}",
                exc_info=True
            )
            ais[ai_name] = AIStatusPayload(
                ai_target=ai_name,
                turn_count=0,
                token_count=0,
                message_count=0,
                session_duration_s=0.0,
                last_interaction_time=None,
                ctaw_size=0,
                ctaw_usage_percent=0.0,
                transport_type="unknown",
                connected=False,
                cdp_url=None,
                cdp_source=None,
                last_page_url=None,
                error=str(e),
            )

    return StatusEnvelope(daemon=daemon_info, ais=ais)


@app.post("/send", response_model=SendResponse)
async def send_prompt_to_ai(req: SendRequest):
    """
    Send a prompt to an AI instance.

    Body: SendRequest
    Response: SendResponse (same outward JSON as before)
    """
    logger = logging.getLogger(__name__)

    target = req.target
    prompt = req.prompt

    # Validate request fields (FastAPI/Pydantic already validated types)
    if not target or not prompt:
        raise HTTPException(
            status_code=400,
            detail="Request must include 'target' and 'prompt'"
        )

    # Get AI instance
    ai_instance = daemon_state["ai_instances"].get(target)
    if not ai_instance:
        available = ", ".join(daemon_state["ai_instances"].keys())
        raise HTTPException(
            status_code=404,
            detail=f"AI target '{target}' not found. Available: {available}"
        )

    # Get lock for this AI (prevent concurrent access)
    lock = daemon_state["locks"].get(target)
    if not lock:
        raise HTTPException(
            status_code=500,
            detail=f"Internal error: lock not found for '{target}'"
        )

    # Acquire lock and send prompt
    async with lock:
        try:
            success, snippet, markdown, metadata = await ai_instance.send_prompt(
                message=prompt,
                wait_for_response=req.wait_for_response,
                timeout_s=req.timeout_s,
            )

            # Preserve outward JSON shape
            return SendResponse(
                success=success,
                snippet=snippet,
                markdown=markdown,
                metadata=metadata or {},
            )

        except Exception as e:
            logger.error(f"Error during interaction with {target}: {e}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=f"Error during interaction: {str(e)}"
            )


@app.post("/session/new/{ai_name}")
async def new_session(ai_name: str):
    """Start a new chat session for the specified AI."""
    logger = logging.getLogger(__name__)

    ai_instance = daemon_state["ai_instances"].get(ai_name)
    if not ai_instance:
        raise HTTPException(
            status_code=404,
            detail=f"AI '{ai_name}' not found"
        )

    try:
        success = await ai_instance.start_new_session()

        if success:
            ai_status = ai_instance.get_ai_status()
            return {
                "success": True,
                "message": f"New session started for '{ai_name}'",
                **ai_status,
            }
        else:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to start new session for '{ai_name}'"
            )
    except Exception as e:
        logger.error(f"Error starting new session for {ai_name}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error starting new session: {str(e)}"
        )


# ---------------------------------------------------------------------------
# Server Entry Point
# ---------------------------------------------------------------------------

def run_daemon():
    """
    Main function to run the Uvicorn server.
    Called by: ai-cli-bridge daemon start
    """
    import uvicorn

    app_config = config.load_config()
    daemon_config = app_config.get("daemon", {})

    host = daemon_config.get("host", "127.0.0.1")
    port = daemon_config.get("port", 8000)
    log_level = daemon_config.get("log_level", "info").lower()

    print(f"Starting daemon on {host}:{port}")

    uvicorn.run(
        "ai_cli_bridge.daemon.main:app",
        host=host,
        port=port,
        log_level=log_level,
    )


if __name__ == "__main__":
    run_daemon()

