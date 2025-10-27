"""Lightweight HTTP client for AI daemon"""

import os
import logging
import threading
from typing import Any
from dataclasses import dataclass

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)

# Timeout constants
HEALTH_TIMEOUT_S = 2
STATUS_TIMEOUT_S = 5
SESSION_TIMEOUT_S = 10
EXTRA_REQUEST_WIGGLE_S = 10


@dataclass
class SendResponse:
    """Response from daemon send operation"""

    success: bool
    snippet: str | None = None
    markdown: str | None = None
    metadata: dict[str, Any] | None = None
    error: str | None = None


class DaemonClient:
    """Lightweight client for daemon HTTP API"""

    def __init__(self, base_url: str | None = None):
        """
        Initialize daemon client

        Args:
            base_url: Daemon base URL (overrides environment variables)
        """
        # Allow override via environment variables (with aliases)
        raw_url = (
            base_url
            or os.environ.get("AI_CLI_DAEMON_URL")
            or os.environ.get("AI_CLI_BRIDGE_URL")
            or "http://127.0.0.1:8000"
        )
        self.base_url = raw_url.rstrip("/")

        # Create session with headers
        self.session = requests.Session()
        self.session.headers.update(
            {"Content-Type": "application/json", "User-Agent": "ai-chat-ui/2.0.0"}
        )

        # Add retry adapter for transient network issues
        retry = Retry(total=2, backoff_factor=0.3, status_forcelist=(502, 503, 504))
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

        # Thread safety for session access
        self._session_lock = threading.Lock()

        logger.debug(f"DaemonClient initialized for {self.base_url}")

    def is_running(self) -> bool:
        """
        Check if daemon is healthy (quick check)

        Returns:
            True if daemon is responding and healthy
        """
        try:
            with self._session_lock:
                response = self.session.get(f"{self.base_url}/healthz", timeout=HEALTH_TIMEOUT_S)
            if response.status_code == 200:
                try:
                    data = response.json()
                    return bool(data.get("ok", False))
                except Exception:
                    return False
            return False
        except Exception:
            # Fallback: some dev builds might only have `/`
            try:
                with self._session_lock:
                    response = self.session.get(f"{self.base_url}/", timeout=HEALTH_TIMEOUT_S)
                return response.status_code == 200
            except Exception:
                logger.debug(f"Daemon health check failed at {self.base_url}")
                return False

    def get_status(self) -> dict[str, Any] | None:
        """
        Get daemon status including available AIs

        Returns:
            Status dict with 'daemon' and 'ais' keys, or None if failed
        """
        try:
            with self._session_lock:
                response = self.session.get(f"{self.base_url}/status", timeout=STATUS_TIMEOUT_S)
            response.raise_for_status()

            try:
                return response.json()
            except ValueError:
                logger.error(f"Invalid JSON in status response from {self.base_url}")
                return None

        except Exception as e:
            logger.error(f"Failed to get daemon status from {self.base_url}: {e}")
            return None

    def get_available_ais(self) -> list[str]:
        """
        Get list of available AI providers

        Returns:
            List of AI names (e.g., ['claude', 'chatgpt', 'gemini'])
        """
        status = self.get_status()
        if status and "daemon" in status:
            ais = status["daemon"].get("available_ais") or []
            if ais:
                logger.debug(f"Available AIs from daemon: {ais}")
                return ais

        # Fallback to known AIs if daemon unreachable or returns empty
        logger.debug("Using fallback AI list")
        return ["claude", "chatgpt", "gemini"]

    def get_ai_status(self, ai_name: str) -> dict[str, Any] | None:
        """
        Get status of specific AI provider
        Extracts from /status response (no dedicated /ai/{name}/status endpoint)

        Args:
            ai_name: AI provider name (case-insensitive)

        Returns:
            AI status dict with 'connected', 'model', etc., or None if not found
        """
        try:
            status = self.get_status()
            if not status or "ais" not in status:
                return None

            ais = status["ais"]

            # Case-insensitive lookup with stripped input
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
        """
        Send a prompt to the daemon

        Args:
            ai: AI provider name (claude, chatgpt, gemini)
            prompt: The message to send
            wait_for_response: Whether to wait for full response (default True)
            timeout_s: Daemon processing timeout in seconds
            debug: Enable debug mode

        Returns:
            SendResponse with success, markdown, metadata, or error
        """
        # Input validation
        if not ai or not ai.strip():
            return SendResponse(success=False, error="Missing AI target")
        if not prompt or not prompt.strip():
            return SendResponse(success=False, error="Prompt is empty")

        # Ensure sane timeout
        timeout_s = max(1, int(timeout_s))
        request_timeout = timeout_s + EXTRA_REQUEST_WIGGLE_S

        try:
            payload = {
                "target": ai.strip(),
                "prompt": prompt,
                "wait_for_response": wait_for_response,
                "timeout_s": timeout_s,
                "debug": debug,
            }

            logger.debug(f"Sending prompt to {ai} at {self.base_url}/send")

            with self._session_lock:
                response = self.session.post(
                    f"{self.base_url}/send", json=payload, timeout=request_timeout
                )

            # Handle HTTP errors with detailed messages
            if response.status_code == 404:
                try:
                    data = response.json()
                except Exception:
                    data = {}
                detail = data.get("detail", f"Unknown AI: {ai}")
                logger.warning(f"404 error from {self.base_url}: {detail}")
                return SendResponse(success=False, error=detail)

            if response.status_code >= 500:
                try:
                    data = response.json()
                except Exception:
                    data = {}
                detail = data.get("detail", "Internal server error")
                logger.error(f"5xx error from {self.base_url}: {detail}")
                return SendResponse(success=False, error=f"Server error: {detail}")

            if response.status_code >= 400:
                try:
                    data = response.json()
                except Exception:
                    data = {}
                detail = data.get("detail", f"Error {response.status_code}")
                logger.warning(f"4xx error from {self.base_url}: {detail}")
                return SendResponse(success=False, error=detail)

            response.raise_for_status()

            # Parse success response with JSON guard
            try:
                data = response.json()
            except ValueError:
                logger.error(f"Invalid JSON in success response from {self.base_url}")
                return SendResponse(success=False, error="Invalid JSON from daemon")

            logger.info(f"Prompt sent successfully to {ai}")

            return SendResponse(
                success=data.get("success", False),
                snippet=data.get("snippet"),
                markdown=data.get("markdown"),
                metadata=data.get("metadata"),
                error=data.get("error"),
            )

        except requests.Timeout:
            error_msg = f"Request timed out after {timeout_s}s"
            logger.error(f"{error_msg} at {self.base_url}")
            return SendResponse(success=False, error=error_msg)
        except requests.RequestException as e:
            error_msg = f"Network error: {str(e)}"
            logger.error(f"{error_msg} at {self.base_url}")
            return SendResponse(success=False, error=error_msg)
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            logger.exception(f"{error_msg} at {self.base_url}")
            return SendResponse(success=False, error=error_msg)

    def new_session(self, ai: str) -> bool:
        """
        Start a new session for an AI (optional feature)

        Args:
            ai: AI provider name

        Returns:
            True if session started successfully
        """
        try:
            with self._session_lock:
                response = self.session.post(
                    f"{self.base_url}/session/new/{ai}", timeout=SESSION_TIMEOUT_S
                )
            response.raise_for_status()

            # Log any detail from response
            try:
                data = response.json()
                if "detail" in data or "message" in data:
                    logger.info(f"New session response: {data}")
            except Exception:
                pass

            return True
        except Exception as e:
            logger.error(f"Failed to start new session at {self.base_url}: {e}")
            return False

    def close(self):
        """Close the session and clean up resources"""
        try:
            with self._session_lock:
                self.session.close()
                logger.debug(f"DaemonClient closed for {self.base_url}")
        except Exception:
            pass

    def __del__(self):
        """Cleanup on deletion"""
        self.close()
