# FILE: src/daemon/ai/gemini.py

import logging
from typing import Any, Dict, Optional, Tuple

from .base import BaseAI
from .factory import AIFactory

try:
    # Optional, for type hints only
    from daemon.transport.base import ITransport  # type: ignore
except Exception:  # pragma: no cover
    ITransport = object  # type: ignore

logger = logging.getLogger(__name__)


class GeminiAI(BaseAI):
    """
    Transport-agnostic Gemini adapter.

    - No Playwright/Web logic here.
    - Delegates all chat operations to the attached transport (e.g., GeminiWebTransport).
    - Keeps BaseAI session accounting and public API stable.
    """

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self._transport: Optional["ITransport"] = None

    # ---------- Public adapter surface ----------

    def attach_transport(self, transport: "ITransport") -> None:
        """Attach a transport (web/api/mock). Safe to call once at startup."""
        self._transport = transport
        logger.info("GeminiAI: transport attached -> %s", getattr(transport, "name", "unknown"))

    async def send_prompt(
        self,
        message: str,
        wait_for_response: bool = True,
        timeout_s: float = 60.0,
        **kwargs,
    ) -> Tuple[bool, Optional[str], Optional[str], Dict[str, Any]]:
        """
        Delegate to transport; preserve BaseAI token/session accounting.
        """
        if not self._transport:
            meta = {
                "error": {
                    "code": "TRANSPORT_NOT_ATTACHED",
                    "message": "No transport attached to GeminiAI.",
                    "severity": "error",
                    "suggested_action": "Attach a transport (e.g., GeminiWebTransport) at startup.",
                },
                "waited": wait_for_response,
                "timeout_s": timeout_s,
            }
            return False, None, None, meta

        success, snippet, markdown, meta = await self._transport.send_prompt(
            message, wait_for_response=wait_for_response, timeout_s=timeout_s
        )

        # Add BaseAI session accounting if we got any response
        if success and (markdown or snippet):
            try:
                response_text = markdown or snippet or ""
                session_meta = self._update_session_from_interaction(message, response_text)
                for k, v in session_meta.items():
                    meta.setdefault(k, v)
            except Exception as e:
                logger.debug("GeminiAI: session accounting failed: %s", e)

        # Ensure timeout_s present for consistency
        meta.setdefault("timeout_s", timeout_s)
        return success, snippet, markdown, meta

    async def list_messages(self) -> list[dict[str, Any]]:
        """
        Optional passthrough; many transports won't implement this.
        """
        try:
            if self._transport and hasattr(self._transport, "list_messages"):
                return await self._transport.list_messages()  # type: ignore[attr-defined]
        except Exception as e:
            logger.debug("GeminiAI.list_messages passthrough failed: %s", e)
        return []

    async def extract_message(self, baseline_count: int = 0) -> dict:
        """
        Optional passthrough; many transports won't implement this.
        """
        try:
            if self._transport and hasattr(self._transport, "extract_message"):
                return await self._transport.extract_message(baseline_count)  # type: ignore[attr-defined]
        except Exception as e:
            logger.debug("GeminiAI.extract_message passthrough failed: %s", e)
        return {"snippet": "", "markdown": ""}

    async def start_new_session(self) -> bool:
        """
        Delegate to transport if supported.
        """
        try:
            if self._transport and hasattr(self._transport, "start_new_session"):
                return await self._transport.start_new_session()  # type: ignore[attr-defined]
        except Exception as e:
            logger.debug("GeminiAI.start_new_session passthrough failed: %s", e)
        # Not fatal if transport doesn't support it
        return True

    def get_transport_status(self) -> Dict[str, Any]:
        """
        Return transport-layer status (for /status endpoint wiring).
        """
        t = self._transport
        status: Dict[str, Any] = {
            "attached": bool(t),
            "name": getattr(t, "name", None),
            "kind": getattr(getattr(t, "kind", None), "value", None),
        }
        if t and hasattr(t, "get_status"):
            try:
                status["status"] = t.get_status()  # type: ignore[attr-defined]
            except Exception as e:
                status["status"] = {"error": f"transport_status_unavailable: {e}"}
        return status

    def get_ai_status(self) -> Dict[str, Any]:
        """
        Extend BaseAI session status with transport info.
        """
        base = super().get_ai_status()
        base["transport"] = self.get_transport_status()
        return base

    # ---------- Static config ----------

    @classmethod
    def get_default_config(cls) -> Dict[str, Any]:
        """
        Gemini-specific defaults (context window, etc.).
        """
        return {
            "ai_target": "gemini",
            "max_context_tokens": 2000000,  # Gemini 1.5 Pro context window
            "response_wait_s": 60.0,
            "completion_check_interval_s": 0.3,
        }


# Register this adapter with the factory under the key 'gemini'
AIFactory.register("gemini", GeminiAI)
