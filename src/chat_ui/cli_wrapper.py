"""CLI wrapper for ai-cli-bridge - replaces direct HTTP daemon client"""

from __future__ import annotations

import json
import logging
import subprocess
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

# Timeout constants (seconds)
HEALTH_TIMEOUT_S = 2
STATUS_TIMEOUT_S = 10
SEND_TIMEOUT_S = 120
LIST_CHATS_TIMEOUT_S = 10
SWITCH_CHAT_TIMEOUT_S = 10
NEW_CHAT_TIMEOUT_S = 20  # Increased for Gemini's slower SPA transitions


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

    def __init__(self) -> None:
        """Initialize CLI wrapper"""
        logger.debug("CLIWrapper initialized")

    def is_running(self) -> bool:
        """Check if daemon is running via CLI"""
        try:
            result = subprocess.run(
                ["ai-cli-bridge", "daemon", "status"],
                capture_output=True,
                text=True,
                timeout=HEALTH_TIMEOUT_S,
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
                timeout=STATUS_TIMEOUT_S,
            )

            if result.returncode != 0:
                logger.error(f"Status command failed: {result.stderr}")
                return None

            try:
                response = json.loads(result.stdout)
                # CLI returns {"ok": true, "data": {...}}
                if response.get("ok") and "data" in response:
                    return response["data"]
                logger.error("Unexpected status response format")
                return None
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON in status response: {e}")
                return None

        except subprocess.TimeoutExpired:
            logger.error("Status command timed out")
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
        timeout_s: int = SEND_TIMEOUT_S,
        debug: bool = False,
    ) -> SendResponse:
        """
        Send a prompt via CLI

        Args:
            ai: Target AI provider name
            prompt: User prompt text
            wait_for_response: Whether to wait for response
            timeout_s: Timeout in seconds
            debug: Enable debug logging

        Returns:
            SendResponse with result
        """
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
            if timeout_s != SEND_TIMEOUT_S:
                cmd.extend(["--timeout", str(timeout_s)])
            if debug:
                cmd.append("--debug")

            logger.debug(f"Sending prompt to {ai} via CLI")

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=command_timeout)

            if result.returncode != 0:
                error_msg = result.stderr.strip() or result.stdout.strip() or "Command failed"
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

            # All metadata fields are now in 'data' thanks to **metadata spread in send_cmd.py
            # Just pass through the entire data dict (excluding snippet/markdown)
            metadata = {k: v for k, v in data.items() if k not in ("snippet", "markdown")}

            logger.info(f"Prompt sent successfully to {ai} via CLI")
            logger.debug(f"Response metadata: {metadata}")

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

    def list_chats(self, ai: str) -> list[dict[str, Any]]:
        """
        List all chats for an AI

        Args:
            ai: AI provider name

        Returns:
            List of chat dictionaries
        """
        try:
            logger.debug(f"Listing chats for AI: {ai}")
            result = subprocess.run(
                ["ai-cli-bridge", "chats", "list", ai.strip(), "--json"],
                capture_output=True,
                text=True,
                timeout=LIST_CHATS_TIMEOUT_S,
            )

            if result.returncode != 0:
                logger.error(f"List chats command failed (exit {result.returncode})")
                logger.error(f"stderr: {result.stderr}")
                logger.error(f"stdout: {result.stdout}")
                return []

            logger.debug(f"List chats stdout: {result.stdout[:200]}...")

            try:
                response = json.loads(result.stdout)
                logger.debug(f"Parsed response: {response}")

                if response.get("success"):
                    chats = response.get("chats", [])
                    logger.info(f"Retrieved {len(chats)} chats for {ai}")
                    return chats
                error = response.get("error", {})
                logger.error(f"List chats failed: {error}")
                return []
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON response: {e}")
                logger.error(f"Raw output: {result.stdout}")
                return []

        except subprocess.TimeoutExpired:
            logger.error("List chats command timed out")
            return []
        except Exception as e:
            logger.error(f"Failed to list chats: {e}", exc_info=True)
            return []

    def switch_chat(self, ai: str, chat_id: str) -> bool:
        """
        Switch to a specific chat

        Args:
            ai: AI provider name
            chat_id: Chat ID to switch to

        Returns:
            True if successful
        """
        try:
            result = subprocess.run(
                ["ai-cli-bridge", "chats", "switch", ai.strip(), chat_id],
                capture_output=True,
                text=True,
                timeout=SWITCH_CHAT_TIMEOUT_S,
            )
            return result.returncode == 0
        except Exception as e:
            logger.error(f"Failed to switch chat: {e}")
            return False

    def new_chat(self, ai: str) -> bool:
        """
        Create a new chat

        Args:
            ai: AI provider name

        Returns:
            True if successful
        """
        try:
            result = subprocess.run(
                ["ai-cli-bridge", "chats", "new", ai.strip()],
                capture_output=True,
                text=True,
                timeout=NEW_CHAT_TIMEOUT_S,
            )
            return result.returncode == 0
        except Exception as e:
            logger.error(f"Failed to create new chat: {e}")
            return False

    def close(self) -> None:
        """Close the wrapper (no-op for CLI)"""
        logger.debug("CLIWrapper closed (no-op)")

    def __del__(self) -> None:
        """Cleanup on deletion (no-op for CLI)"""
        pass
