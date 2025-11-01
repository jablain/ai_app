# src/daemon/transport/web.py
# WebTransport — concrete ITransport implementation using Playwright/CDP.
# Drives a web chat UI end-to-end (type prompt, wait, extract).

from __future__ import annotations

import asyncio
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from playwright.async_api import Page, TimeoutError as PWTimeout

from .base import ITransport, TransportKind, SendResult, ErrorCategory, ErrorCode, TransportError


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()



def _create_error(
    category: ErrorCategory,
    code: ErrorCode,
    message: str,
    user_action: str | None = None,
    recoverable: bool = True,
    **transport_details
) -> dict[str, Any]:
    """
    Helper to create standardized error response.
    
    Args:
        category: Error category
        code: Standardized error code
        message: User-friendly message
        user_action: Optional suggested action
        recoverable: Whether retry might work
        **transport_details: Transport-specific debug info
    
    Returns:
        Error dict for metadata
    """
    error = TransportError(
        category=category,
        code=code,
        message=message,
        user_action=user_action,
        recoverable=recoverable,
        transport_details=transport_details if transport_details else None
    )
    return error.to_dict()


def _create_metadata(
    start_ts: float,
    timeout_s: float,
    ws_url: str | None = None,
    ws_source: str = "none",
    error: dict | None = None,
    **extra
) -> dict[str, Any]:
    """
    Helper to create consistent metadata structure.
    
    Args:
        start_ts: Operation start timestamp
        timeout_s: Configured timeout
        ws_url: CDP WebSocket URL (if available)
        ws_source: CDP origin
        error: Error dict from _create_error
        **extra: Additional metadata fields
    
    Returns:
        Metadata dict
    """
    meta = {
        "transport": "web",
        "start_ts": start_ts,
        "timeout_s": timeout_s,
        "duration_s": round(time.time() - start_ts, 3),
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }
    
    if ws_url:
        meta["cdp_url"] = ws_url
    if ws_source:
        meta["cdp_origin"] = ws_source
    if error:
        meta["error"] = error
    
    meta.update(extra)
    return meta


class WebTransport(ITransport):
    """
    Generic browser/CDP-based transport.

    Subclasses (e.g., ClaudeWebTransport) override CSS selectors and, if needed,
    the _get_response_count/_extract_response routines tailored to a given site.
    """

    # Tunables (subclasses can override constants if desired)
    RESPONSE_WAIT_S = 60.0
    COMPLETION_CHECK_INTERVAL_S = 0.3
    SNIPPET_LENGTH = 280

    # Generic selectors (subclass SHOULD override to be site-specific)
    INPUT_BOX = "div[contenteditable='true']"
    STOP_BUTTON = "button[aria-label*='Stop']"
    NEW_CHAT_BUTTON = "button:has-text('New chat'), a:has-text('New chat')"
    RESPONSE_CONTAINER = "div[data-message-author-role='assistant']"
    RESPONSE_CONTENT = ".standard-markdown"

    def __init__(self, *, base_url: str, browser_pool, logger=None):
        """
        Args:
            base_url: target base URL (e.g. 'https://claude.ai')
            browser_pool: shared BrowserConnectionPool instance
            logger: optional logger for diagnostics
        """
        self.base_url = base_url.rstrip("/")
        self.browser_pool = browser_pool
        self._logger = logger

        # Cached CDP info
        self._cdp_url: str | None = None
        self._cdp_origin: str = "none"

        # Last used page (not strictly required, but handy for start_new_session)
        self._page: Page | None = None

    # ---------- ITransport identity ----------
    @property
    def name(self) -> str:
        return "WebTransport"

    @property
    def kind(self) -> TransportKind:
        return TransportKind.WEB

    # ---------- ITransport core ----------
    async def send_prompt(
        self,
        message: str,
        *,
        wait_for_response: bool = True,
        timeout_s: float = 60.0,
    ) -> SendResult:
        """
        Full end-to-end interaction:
          1) obtain CDP + page
          2) ensure chat is ready
          3) capture baseline
          4) type + send the prompt
          5) wait for completion (stop button / stability)
          6) extract latest response
        """
        request_id = str(uuid.uuid4())
        start_ts = time.time()
        stage_log: dict[str, Any] = {"request_id": request_id, "send_start": _iso_now()}
        warnings: list[dict] = []

        try:
            ws_url, ws_source = await self._get_cdp_url()
            if not ws_url:
                return (
                    False,
                    None,
                    None,
                    {
                        "transport": "web",
                        "start_ts": start_ts,
                        "timeout_s": timeout_s,
                        "cdp_url": None,
                        "cdp_origin": ws_source,
                        "duration_s": round(time.time() - start_ts, 3),
                        "timestamp": datetime.utcnow().isoformat() + "Z",
                        "error": {
                            "code": "CDP_UNAVAILABLE",
                            "message": "No browser CDP endpoint available.",
                        },
                    },
                )

            page = await self._pick_page(ws_url)
            if not page:
                return (
                    False,
                    None,
                    None,
                    {
                        "transport": "web",
                        "start_ts": start_ts,
                        "timeout_s": timeout_s,
                        "cdp_url": ws_url,
                        "cdp_origin": ws_source,
                        "duration_s": round(time.time() - start_ts, 3),
                        "timestamp": datetime.utcnow().isoformat() + "Z",
                        "error": {
                            "code": "PAGE_UNAVAILABLE",
                            "message": "Could not obtain a page for the target site.",
                        },
                    },
                )

            self._page = page

            # Ensure chat is ready (input visible)
            ready = await self._ensure_chat_ready(page)
            if not ready:
                return (
                    False,
                    None,
                    None,
                    {
                        "transport": "web",
                        "start_ts": start_ts,
                        "timeout_s": timeout_s,
                        "cdp_url": ws_url,
                        "cdp_origin": ws_source,
                        "duration_s": round(time.time() - start_ts, 3),
                        "timestamp": datetime.utcnow().isoformat() + "Z",
                        "error": {
                            "code": "SELECTOR_MISSING",
                            "message": "Chat input not ready (selector missing or not visible).",
                            "suggested_action": "Reload the tab or sign in again.",
                            "evidence": {"page_url": page.url},
                        },
                    },
                )

            # Opportunistic banner/alert check (non-fatal)
            suspicious = await self._detect_page_state(page)
            if suspicious:
                warnings.append(
                    {
                        "code": "SUSPICIOUS_PAGE_STATE",
                        "message": "Page shows a banner/alert; interaction may still succeed.",
                        "severity": "warn",
                        "suggested_action": "If results look off, re-auth the tab.",
                        "evidence": suspicious,
                        "stage_log": dict(stage_log),
                    }
                )

            # Baseline response count
            baseline_count = await self._get_response_count(page)
            stage_log["baseline_count"] = baseline_count

            # Send the message
            sent_ok = await self._send_message(page, message)
            stage_log["send_complete"] = _iso_now()
            if not sent_ok:
                return (
                    False,
                    None,
                    None,
                    {
                        "transport": "web",
                        "start_ts": start_ts,
                        "timeout_s": timeout_s,
                        "cdp_url": ws_url,
                        "cdp_origin": ws_source,
                        "duration_s": round(time.time() - start_ts, 3),
                        "timestamp": datetime.utcnow().isoformat() + "Z",
                        "error": {
                            "code": "SEND_FAILED",
                            "message": "Failed to send message (input not fillable).",
                            "evidence": {"page_url": page.url},
                        },
                    },
                )

            snippet = None
            markdown = None
            elapsed_ms: int | None = None

            if wait_for_response:
                t0 = time.time()
                stage_log["wait_start"] = _iso_now()
                completed = await self._wait_for_response_complete(page, timeout_s)
                stage_log["wait_complete"] = _iso_now()
                if completed:
                    snippet, markdown = await self._extract_response(page, baseline_count)
                    stage_log["extract_done"] = _iso_now()
                    if not markdown or not markdown.strip():
                        warnings.append(
                            {
                                "code": "EMPTY_RESPONSE",
                                "message": "Response completed but no content extracted.",
                                "severity": "warn",
                                "suggested_action": "Check the provider tab; may need to retry.",
                                "evidence": {"page_url": page.url},
                                "stage_log": dict(stage_log),
                            }
                        )
                else:
                    return (
                        False,
                        None,
                        None,
                        {
                            "transport": "web",
                            "start_ts": start_ts,
                            "timeout_s": timeout_s,
                            "cdp_url": ws_url,
                            "cdp_origin": ws_source,
                            "duration_s": round(time.time() - start_ts, 3),
                            "timestamp": datetime.utcnow().isoformat() + "Z",
                            "error": {
                                "code": "RESPONSE_TIMEOUT",
                                "message": f"Prompt sent, but no response completed within {timeout_s}s.",
                                "evidence": {
                                    "page_url": page.url,
                                    "selector": self.STOP_BUTTON,
                                },
                                "stage_log": dict(stage_log),
                            },
                        },
                    )
                elapsed_ms = int((time.time() - t0) * 1000)

            meta = {
                "elapsed_ms": elapsed_ms,
                "waited": wait_for_response,
                "timeout_s": timeout_s,
                "ws_source": ws_source,
                "page_url": page.url,
                "stage_log": stage_log,
                "request_id": request_id,
                "warnings": warnings,
                "model_name": None,
                "cdp_url": ws_url,
                "timestamp": datetime.utcnow().isoformat() + "Z",
            }

            return True, snippet, markdown, meta

        except Exception as e:
            if self._logger:
                self._logger.error(f"WebTransport.send_prompt failed: {e}", exc_info=True)
            return (
                False,
                None,
                None,
                {
                    "transport": "web",
                    "start_ts": start_ts,
                    "timeout_s": timeout_s,
                    "cdp_url": self._cdp_url,
                    "cdp_origin": self._cdp_origin,
                    "duration_s": round(time.time() - start_ts, 3),
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "error": {
                        "code": "UNEXPECTED_EXCEPTION",
                        "message": str(e),
                    },
                },
            )

    async def start_new_session(self) -> bool:
        """Click 'new chat' if present; otherwise no-op."""
        try:
            if not self._page:
                return True
            btn = self._page.locator(self.NEW_CHAT_BUTTON)
            if await btn.count() > 0:
                await btn.first.click()
                await self._page.wait_for_selector(self.INPUT_BOX, state="visible", timeout=5000)
            return True
        except Exception:
            return False

    def get_status(self) -> dict[str, Any]:
        """Return current transport state for diagnostics."""
        return {
            "kind": self.kind.value,
            "base_url": self.base_url,
            "cdp_cached": bool(self._cdp_url),
            "cdp_origin": self._cdp_origin,
        }

    # ---------- Internals ----------
    async def _get_cdp_url(self) -> tuple[str | None, str]:
        """
        Ask the shared BrowserConnectionPool for the CDP URL.
        """
        try:
            if self._cdp_url:
                return self._cdp_url, "cached"
            ws = await self.browser_pool.get_cdp_url()
            if ws:
                self._cdp_url = ws
                self._cdp_origin = "discovered"
                if self._logger:
                    self._logger.info(f"Transport: CDP discovered: {ws}")
                return ws, "discovered"
            return None, "none"
        except Exception:
            return None, "error"

    async def _pick_page(self, ws_url: str) -> Page | None:
        """
        Reuse an existing page matching base_url, or open a new one.
        Delegates to the BrowserConnectionPool so we share the same Playwright instance.
        """
        hint = self.base_url.replace("https://", "").replace("http://", "")
        try:
            page = await self.browser_pool.get_page(ws_url, hint)
            return page
        except Exception as e:
            if self._logger:
                self._logger.error(f"_pick_page failed: {e}", exc_info=True)
            return None

    async def _ensure_chat_ready(self, page: Page) -> bool:
        """Wait for chat input to be visible."""
        try:
            await page.locator(self.INPUT_BOX).first.wait_for(state="visible", timeout=8000)
            return True
        except Exception:
            return False

    async def _detect_page_state(self, page: Page, max_text_len: int = 300) -> dict | None:
        """
        Lightweight check for banners/toasts/rate limits/auth walls. Non-fatal.
        """
        candidates = [
            # Auth / login
            "input[type='password']",
            "button:has-text('Sign in'), button:has-text('Log in'), a:has-text('Sign in'), a:has-text('Log in')",
            # Captcha / verification
            "iframe[src*='captcha']",
            "div:has-text('verify you are human')",
            # Rate limit / quota
            "div:has-text('Too many requests'), div:has-text('rate limit'), div:has-text('concurrent')",
            # Generic alerts / banners / toasts
            "[role='alert']",
            "div[data-testid='toast']",
            "div[role='status']",
        ]
        try:
            for css in candidates:
                loc = page.locator(css)
                if await loc.count() > 0:
                    text = ""
                    try:
                        text = (await loc.first.inner_text()) or ""
                    except Exception:
                        pass
                    if len(text) > max_text_len:
                        text = text[:max_text_len] + " …"
                    return {"selector": css, "text_snippet": text, "page_url": page.url}
        except Exception:
            pass
        return None

    async def _get_response_count(self, page: Page) -> int:
        """Count response messages; subclasses can override for accuracy."""
        try:
            return await page.locator(self.RESPONSE_CONTAINER).count()
        except Exception:
            return 0

    async def _send_message(self, page: Page, message: str) -> bool:
        """Type the message and press Enter with a couple of fallbacks."""
        try:
            box = page.locator(self.INPUT_BOX).first
            await box.wait_for(state="visible", timeout=5000)
            try:
                await box.fill(message, timeout=2000)
            except Exception:
                await box.click(timeout=2000)
                await page.keyboard.type(message)
            await page.keyboard.press("Enter")
            return True
        except Exception as e:
            if self._logger:
                self._logger.error(f"_send_message failed: {e}")
            return False

    async def _wait_for_response_complete(self, page: Page, timeout_s: float) -> bool:
        """
        Wait for 'Stop response' button to disappear (classic UI pattern).
        If it never appears, we assume the response was very fast.
        """
        try:
            try:
                await page.wait_for_selector(self.STOP_BUTTON, state="visible", timeout=10000)
                # Disappear within timeout_s
                deadline = time.time() + timeout_s
                while time.time() < deadline:
                    if await page.locator(self.STOP_BUTTON).count() == 0:
                        return True
                    await asyncio.sleep(self.COMPLETION_CHECK_INTERVAL_S)
                return False
            except PWTimeout:
                return True  # stop never appeared; treat as instant
            except Exception:
                return True
        except Exception:
            return True

    async def _extract_response(
        self, page: Page, baseline_count: int
    ) -> tuple[str | None, str | None]:
        """
        Extract the latest response text (markdown/plain). Subclasses can override.
        Default: pick the last RESPONSE_CONTENT (inner_text), fallback to last assistant bubble.
        """
        try:
            # Wait briefly for DOM to attach the new content after stop disappears
            deadline = self.RESPONSE_WAIT_S
            waited = 0.0
            while waited < deadline:
                if await page.locator(self.RESPONSE_CONTAINER).count() > baseline_count:
                    break
                await page.wait_for_timeout(int(self.COMPLETION_CHECK_INTERVAL_S * 1000))
                waited += self.COMPLETION_CHECK_INTERVAL_S

            content = page.locator(self.RESPONSE_CONTENT).last
            if await content.count() > 0:
                text = (await content.inner_text() or "").strip()
                snippet = text[: self.SNIPPET_LENGTH]
                return snippet, text

            # Fallback: last assistant container's text
            last_bubble = page.locator(self.RESPONSE_CONTAINER).last
            if await last_bubble.count() > 0:
                txt = (await last_bubble.inner_text() or "").strip()
                return (txt[: self.SNIPPET_LENGTH], txt)

            return "", ""
        except Exception as e:
            if self._logger:
                self._logger.warning(f"_extract_response failed: {e}")
            return "", ""
