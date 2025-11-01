"""CLI wrapper for ai-cli-bridge - replaces direct HTTP daemon client"""

import subprocess
import json
import logging
from typing import Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Timeout constants
HEALTH_TIMEOUT_S = 2
STATUS_TIMEOUT_S = 10
SEND_TIMEOUT_S = 120


@dataclass
class SendResponse:
    """Response from CLI send operation"""
    success: bool
    snippet: str | None = None
    markdown: str | None = None
    metadata: dict[str, Any] | None = None
    error: str | None = None


class CLIWrapper:
    """Wrapper for ai-cli-bridge CLI commands"""

    def __init__(self):
        """Initialize CLI wrapper"""
        logger.debug("CLIWrapper initialized")

    def is_running(self) -> bool:
        """Check if daemon is running via CLI"""
        try:
            result = subprocess.run(
                ["ai-cli-bridge", "daemon", "status"],
                capture_output=True,
                text=True,
                timeout=HEALTH_TIMEOUT_S
            )
            return result.returncode == 0
        except subprocess.TimeoutExpired:
            logger.debug("Daemon status check timed out")
            return False
        except Exception as e:
            logger.debug(f"Daemon status check failed: {e}")
            return False

    def get_status(self) -> dict[str, Any] | None:
        """Get daemon status - extracts from CLI wrapper format"""
        try:
            result = subprocess.run(
                ["ai-cli-bridge", "status", "--json"],
                capture_output=True,
                text=True,
                timeout=STATUS_TIMEOUT_S
            )
            
            if result.returncode != 0:
                logger.error(f"Status command failed: {result.stderr}")
                return None
            
            try:
                response = json.loads(result.stdout)
                # CLI returns {"ok": true, "data": {...}}
                if response.get("ok") and "data" in response:
                    return response["data"]
                else:
                    logger.error(f"Unexpected status response format")
                    return None
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON in status response: {e}")
                return None

        except subprocess.TimeoutExpired:
            logger.error(f"Status command timed out")
            return None
        except Exception as e:
            logger.error(f"Failed to get status: {e}")
            return None

    def get_available_ais(self) -> list[str]:
        """Get list of available AI providers"""
        status = self.get_status()
        if status and "daemon" in status:
            transports = status["daemon"].get("configured_ai_transports", {})
            if transports:
                ais = list(transports.keys())
                logger.debug(f"Available AIs from CLI: {ais}")
                return ais

        logger.debug("Using fallback AI list")
        return ["claude", "chatgpt", "gemini"]

    def get_ai_status(self, ai_name: str) -> dict[str, Any] | None:
        """Get status of specific AI provider"""
        try:
            status = self.get_status()
            if not status or "ais" not in status:
                return None

            ais = status["ais"]
            ai_key = (ai_name or "").strip().lower()
            key = next((k for k in ais if k.lower() == ai_key), None)
            return ais.get(key) if key else None

        except Exception as e:
            logger.error(f"Failed to get {ai_name} status: {e}")
            return None

    def send_prompt(
        self,
        ai: str,
        prompt: str,
        wait_for_response: bool = True,
        timeout_s: int = 120,
        debug: bool = False,
    ) -> SendResponse:
        """Send a prompt via CLI"""
        if not ai or not ai.strip():
            return SendResponse(success=False, error="Missing AI target")
        if not prompt or not prompt.strip():
            return SendResponse(success=False, error="Prompt is empty")

        timeout_s = max(1, int(timeout_s))
        command_timeout = timeout_s + 10

        try:
            cmd = ["ai-cli-bridge", "send", ai.strip(), prompt, "--json"]
            
            if not wait_for_response:
                cmd.append("--no-wait")
            if timeout_s != 120:
                cmd.extend(["--timeout", str(timeout_s)])
            if debug:
                cmd.append("--debug")

            logger.debug(f"Sending prompt to {ai} via CLI")

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=command_timeout
            )

            if result.returncode != 0:
                error_msg = result.stderr.strip() or result.stdout.strip() or f"Command failed"
                logger.error(f"Send command failed: {error_msg}")
                return SendResponse(success=False, error=error_msg)

            try:
                response = json.loads(result.stdout)
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON response: {e}")
                return SendResponse(success=False, error="Invalid JSON from CLI")

            # CLI returns {"ok": true, "data": {...}}
            if not response.get("ok"):
                error_msg = response.get("message", "Request failed")
                logger.error(f"CLI returned error: {error_msg}")
                return SendResponse(success=False, error=error_msg)

            data = response.get("data", {})
            
            # Build metadata
            metadata = {}
            if "elapsed_ms" in data:
                metadata["elapsed_ms"] = data["elapsed_ms"]
            if "timeout_s" in data:
                metadata["timeout_s"] = data["timeout_s"]

            logger.info(f"Prompt sent successfully to {ai} via CLI")

            return SendResponse(
                success=True,
                snippet=data.get("snippet"),
                markdown=data.get("markdown"),
                metadata=metadata if metadata else None,
                error=None,
            )

        except subprocess.TimeoutExpired:
            error_msg = f"Request timed out after {timeout_s}s"
            logger.error(error_msg)
            return SendResponse(success=False, error=error_msg)
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            logger.exception(error_msg)
            return SendResponse(success=False, error=error_msg)

    def close(self):
        """Close the wrapper (no-op for CLI)"""
        logger.debug("CLIWrapper closed (no-op)")

    def __del__(self):
        """Cleanup on deletion (no-op for CLI)"""
        pass
