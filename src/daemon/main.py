"""
AI Daemon - Main FastAPI application with lifecycle management.
"""

import logging
import time
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from daemon.ai.factory import AIFactory
from daemon.browser.connection_pool import BrowserConnectionPool
from daemon.config import load_config
from daemon.health import HealthMonitor
from daemon.transport import WebTransport

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Version
VERSION = "2.1.0"

# Global state
daemon_state: dict[str, Any] = {
    "browser_pool": None,
    "ai_instances": {},
    "health_monitor": None,
    "startup_time": None,
    "config": None,
}


# --- Request/Response Models ---


class SendRequest(BaseModel):
    """Request model for /send endpoint."""

    target: str = Field(..., description="AI target (claude, chatgpt, gemini)")
    prompt: str = Field(..., description="User prompt to send")
    wait_for_response: bool = Field(True, description="Wait for AI response")
    timeout_s: float = Field(60.0, description="Timeout in seconds")


class SendResponse(BaseModel):
    """Response model for /send endpoint."""

    success: bool
    snippet: str | None = None
    markdown: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class StatusResponse(BaseModel):
    """Response model for /status endpoint."""

    daemon: dict[str, Any]
    ais: dict[str, dict[str, Any]]


class HealthResponse(BaseModel):
    """Response model for /healthz endpoint."""

    status: str
    version: str
    uptime_s: float


# --- Lifecycle Management ---


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager - handles startup and shutdown.
    """
    # --- STARTUP ---
    logger.info("=" * 80)
    logger.info(f"AI Daemon v{VERSION} starting…")
    logger.info("=" * 80)

    startup_start = time.time()
    daemon_state["startup_time"] = startup_start

    try:
        # Load configuration
        config = load_config()
        daemon_state["config"] = config
        logger.info("Configuration loaded.")

        # Start browser pool (with auto-launch)
        try:
            browser_pool = BrowserConnectionPool(config)
            await browser_pool.start()
            daemon_state["browser_pool"] = browser_pool
            logger.info("Browser connection pool started.")
        except Exception as e:
            logger.error(f"Failed to start browser pool: {e}")
            raise

        # Create AI instances using static factory API
        try:
            logger.info("Discovering AIs…")

            # Import all AI implementations
            AIFactory.import_all_ais()

            # Get list of available AIs
            available_ais = AIFactory.list_available()
            logger.info(f"Discovered AIs: {available_ais}")

            # Create instances for each available AI
            ai_instances = {}
            for ai_name in available_ais:
                try:
                    ai_class = AIFactory.get_class(ai_name)
                    ai_config = ai_class.get_default_config()
                    instance = AIFactory.create(ai_name, ai_config)

                    if hasattr(instance, "set_browser_pool"):
                        instance.set_browser_pool(browser_pool)

                    ai_instances[ai_name] = instance
                    logger.info(f"✓ '{ai_name}' ready")
                except Exception as e:
                    logger.error(f"Failed to create '{ai_name}' instance: {e}")
                    continue

            if not ai_instances:
                raise RuntimeError("No AI instances created")

            daemon_state["ai_instances"] = ai_instances

        except Exception as e:
            logger.error(f"Failed to create AI instances: {e}")
            raise

        # Attach transports - NEW SIMPLIFIED PATTERN
        try:
            transports_cfg = getattr(config, "ai_transports", {}) or {}

            for ai_name, ai_instance in ai_instances.items():
                transport_mode = (transports_cfg.get(ai_name, "web") or "web").lower().strip()

                if transport_mode == "web":
                    try:
                        # Get AI's config (which includes selectors)
                        ai_config = ai_instance.get_config()

                        # Create generic WebTransport with AI-specific config
                        transport = WebTransport(
                            config=ai_config,
                            browser_pool=browser_pool,
                            logger=logger,
                        )

                        # Attach transport to AI instance
                        ai_instance.attach_transport(transport)
                        logger.info(f"✓ Attached WebTransport to '{ai_name}'")

                    except Exception as te:
                        logger.error(f"Transport attach failed for {ai_name}: {te}")

        except Exception as e:
            logger.warning(f"Transport wiring skipped due to error: {e}")

        # Start health monitor
        health_monitor = HealthMonitor(browser_pool)
        health_monitor.start()
        daemon_state["health_monitor"] = health_monitor
        logger.info("Health monitor started.")

        startup_duration = time.time() - startup_start
        logger.info("Startup complete in %.2fs", startup_duration)
        logger.info("=" * 80)

        yield

    except Exception as e:
        logger.error(f"Startup failed: {e}")
        raise

    # --- SHUTDOWN ---
    logger.info("=" * 80)
    logger.info("AI Daemon shutting down…")
    logger.info("=" * 80)

    if daemon_state["health_monitor"]:
        daemon_state["health_monitor"].stop()
        logger.info("Health monitor stopped.")

    if daemon_state["browser_pool"]:
        await daemon_state["browser_pool"].stop()
        logger.info("Browser pool stopped.")

    logger.info("Shutdown complete")


# --- FastAPI Application ---

app = FastAPI(
    title="AI Daemon",
    version=VERSION,
    description="Unified daemon for managing AI chat interactions",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,  # Must be False when using "*"
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Endpoints ---


@app.get("/health", response_model=HealthResponse)
async def health():
    """Health check endpoint."""
    uptime = time.time() - daemon_state["startup_time"] if daemon_state["startup_time"] else 0
    return HealthResponse(
        status="ok",
        version=VERSION,
        uptime_s=uptime,
    )


@app.get("/status", response_model=StatusResponse)
async def status():
    """
    Get daemon and AI instance status.
    """
    import os  # Add at top of function

    browser_pool = daemon_state["browser_pool"]
    ai_instances = daemon_state["ai_instances"]
    health_monitor = daemon_state["health_monitor"]
    cfg = daemon_state.get("config")

    uptime = time.time() - daemon_state["startup_time"] if daemon_state["startup_time"] else 0
    daemon_status = {
        "version": VERSION,
        "pid": os.getpid(),
        "browser_pool_active": browser_pool is not None,
        "cdp_healthy": health_monitor.is_healthy() if health_monitor else False,
        "uptime_s": uptime,
        "configured_ai_transports": getattr(cfg, "ai_transports", {}) if cfg else {},
    }

    ai_statuses = {}
    for name, instance in ai_instances.items():
        try:
            ai_statuses[name] = instance.get_ai_status()
        except Exception as e:
            logger.error(f"Failed to get status for {name}: {e}")
            ai_statuses[name] = {
                "error": str(e),
                "ai_target": name,
            }

    return StatusResponse(
        daemon=daemon_status,
        ais=ai_statuses,
    )


@app.post("/send", response_model=SendResponse)
async def send(request: SendRequest):
    """
    Send a prompt to an AI and optionally wait for response.
    """
    ai_instances = daemon_state["ai_instances"]

    if request.target not in ai_instances:
        return SendResponse(
            success=False,
            snippet=None,
            markdown=None,
            metadata={
                "error": {
                    "code": "INVALID_TARGET",
                    "message": f"Unknown AI target: {request.target}",
                    "severity": "error",
                    "suggested_action": f"Use one of: {', '.join(ai_instances.keys())}",
                    "evidence": {
                        "requested": request.target,
                        "available": list(ai_instances.keys()),
                    },
                },
                "warnings": [],
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime()),
                "timeout_s": request.timeout_s,
            },
        )

    ai = ai_instances[request.target]

    try:
        success, snippet, markdown, metadata = await ai.send_prompt(
            message=request.prompt,
            wait_for_response=request.wait_for_response,
            timeout_s=request.timeout_s,
        )

        if metadata is None:
            metadata = {}

        metadata.setdefault("timeout_s", request.timeout_s)

        return SendResponse(
            success=bool(success),
            snippet=snippet,
            markdown=markdown,
            metadata=metadata,
        )

    except Exception as e:
        logger.error(f"Error sending to {request.target}: {e}", exc_info=True)
        return SendResponse(
            success=False,
            snippet=None,
            markdown=None,
            metadata={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": f"Internal error: {str(e)}",
                    "severity": "error",
                    "suggested_action": "Check daemon logs and retry.",
                    "evidence": {
                        "exception": str(e),
                        "exception_type": type(e).__name__,
                    },
                },
                "warnings": [],
                "timeout_s": request.timeout_s,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime()),
            },
        )


# --- Main Entry Point ---

if __name__ == "__main__":
    import uvicorn

    cfg = daemon_state.get("config")
    host = "127.0.0.1"
    port = 8000
    if cfg and getattr(cfg, "daemon", None):
        host = getattr(cfg.daemon, "host", host)
        port = getattr(cfg.daemon, "port", port)

    uvicorn.run(app, host=host, port=port, log_level="info")
