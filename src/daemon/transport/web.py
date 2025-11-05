# WebTransport — concrete ITransport implementation using Playwright/CDP.
# Drives a web chat UI end-to-end (type prompt, wait, extract).

from __future__ import annotations

import asyncio
import re
import time
import uuid
from datetime import datetime, timezone
from typing import Any, List

from playwright.async_api import Page
from playwright.async_api import TimeoutError as PWTimeout

from .base import (
    ChatInfo,
    ErrorCategory,
    ErrorCode,
    ITransport,
    SendResult,
    TransportError,
    TransportKind,
)


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _create_error(
    category: ErrorCategory,
    code: ErrorCode,
    message: str,
    user_action: str | None = None,
    recoverable: bool = True,
    **transport_details,
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
        transport_details=transport_details if transport_details else None,
    )
    return error.to_dict()


def _create_metadata(
    start_ts: float,
    timeout_s: float,
    ws_url: str | None = None,
    ws_source: str = "none",
    error: dict | None = None,
    **extra,
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

    Now fully selector-driven via config - no need for AI-specific subclasses.
    Selectors are provided via the config dict during initialization.
    """

    def __init__(self, *, config: dict[str, Any], browser_pool, logger=None):
        """
        Args:
            config: Configuration dict containing:
                - base_url: target base URL (e.g. 'https://claude.ai')
                - selectors: dict of CSS selectors
                - response_wait_s: timeout for response (optional)
                - completion_check_interval_s: polling interval (optional)
                - snippet_length: max snippet length (optional)
            browser_pool: shared BrowserConnectionPool instance
            logger: optional logger for diagnostics
        """
        self.base_url = config.get("base_url", "").rstrip("/")
        self.browser_pool = browser_pool
        self._logger = logger

        # Read selectors from config (with defaults)
        selectors = config.get("selectors", {})
        self.INPUT_BOX = selectors.get("input_box", "div[contenteditable='true']")
        self.STOP_BUTTON = selectors.get("stop_button", "button[aria-label*='Stop']")
        self.SEND_BUTTON = selectors.get("send_button", "button[aria-label='Send']")
        self.NEW_CHAT_BUTTON = selectors.get(
            "new_chat_button", "button:has-text('New chat'), a:has-text('New chat')"
        )
        self.RESPONSE_CONTAINER = selectors.get(
            "response_container", "div[data-message-author-role='assistant']"
        )
        self.RESPONSE_CONTENT = selectors.get("response_content", ".standard-markdown")

        # Read timing configuration from config (with defaults)
        self.RESPONSE_WAIT_S = config.get("response_wait_s", 60.0)
        self.COMPLETION_CHECK_INTERVAL_S = config.get("completion_check_interval_s", 0.3)
        self.SNIPPET_LENGTH = config.get("snippet_length", 280)

        # Cached CDP info
        self._cdp_url: str | None = None
        self._cdp_origin: str = "none"

        # Last used page (not strictly required, but handy for chat operations)
        self._page: Page | None = None

        # Ready flag - set to True when page is loaded and input is visible
        self._ready: bool = False  # ← ADD THIS

        # Store full config for reference
        self._config = config

    # ---------- ITransport identity ----------
    @property
    def name(self) -> str:
        ai_target = self._config.get("ai_target", "unknown")
        return f"WebTransport-{ai_target}"

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
                # 1. CDP_UNAVAILABLE
                return (
                    False,
                    None,
                    None,
                    _create_metadata(
                        start_ts=start_ts,
                        timeout_s=timeout_s,
                        ws_url=None,
                        ws_source=ws_source,
                        error=_create_error(
                            category=ErrorCategory.CONNECTION,
                            code=ErrorCode.CONNECTION_UNAVAILABLE,
                            message="Cannot connect to AI service",
                            user_action="Please check that the browser is running and accessible.",
                            recoverable=True,
                            transport_error="CDP_UNAVAILABLE",
                            original_message="No browser CDP endpoint available.",
                        ),
                    ),
                )

            page = await self._pick_page(ws_url)
            if not page:
                # 2. PAGE_UNAVAILABLE
                return (
                    False,
                    None,
                    None,
                    _create_metadata(
                        start_ts=start_ts,
                        timeout_s=timeout_s,
                        ws_url=ws_url,
                        ws_source=ws_source,
                        error=_create_error(
                            category=ErrorCategory.CONNECTION,
                            code=ErrorCode.CONNECTION_UNAVAILABLE,
                            message="Cannot connect to AI service",
                            user_action="Please check the AI service tab in your browser.",
                            recoverable=True,
                            transport_error="PAGE_UNAVAILABLE",
                            original_message="Could not obtain a page for the target site.",
                        ),
                    ),
                )

            self._page = page

            # Ensure chat is ready (input visible)
            ready = await self._ensure_chat_ready(page)
            if not ready:
                # 3. SELECTOR_MISSING
                return (
                    False,
                    None,
                    None,
                    _create_metadata(
                        start_ts=start_ts,
                        timeout_s=timeout_s,
                        ws_url=ws_url,
                        ws_source=ws_source,
                        error=_create_error(
                            category=ErrorCategory.AUTHENTICATION,
                            code=ErrorCode.SESSION_INVALID,
                            message="Your session needs to be refreshed",
                            user_action="Reload the tab or sign in again.",
                            recoverable=True,
                            transport_error="SELECTOR_MISSING",
                            original_message="Chat input not ready (selector missing or not visible).",
                            page_url=page.url,
                        ),
                    ),
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
                # 4. SEND_FAILED
                return (
                    False,
                    None,
                    None,
                    _create_metadata(
                        start_ts=start_ts,
                        timeout_s=timeout_s,
                        ws_url=ws_url,
                        ws_source=ws_source,
                        error=_create_error(
                            category=ErrorCategory.INPUT,
                            code=ErrorCode.SEND_FAILED,
                            message="Failed to send message",
                            user_action="Please try sending the message again.",
                            recoverable=False,
                            transport_error="SEND_FAILED",
                            original_message="Failed to send message (input not fillable).",
                            page_url=page.url,
                        ),
                    ),
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
                        # 6. EMPTY_RESPONSE
                        warnings.append(
                            _create_error(
                                category=ErrorCategory.RESPONSE,
                                code=ErrorCode.EMPTY_RESPONSE,
                                message="AI returned an empty response",
                                user_action="Check the provider tab; may need to retry.",
                                recoverable=True,
                                transport_error="EMPTY_RESPONSE",
                                original_message="Response completed but no content extracted.",
                                severity="warn",
                                page_url=page.url,
                                stage_log=dict(stage_log),
                            )
                        )
                else:
                    # 5. RESPONSE_TIMEOUT
                    return (
                        False,
                        None,
                        None,
                        _create_metadata(
                            start_ts=start_ts,
                            timeout_s=timeout_s,
                            ws_url=ws_url,
                            ws_source=ws_source,
                            stage_log=dict(stage_log),
                            error=_create_error(
                                category=ErrorCategory.TIMEOUT,
                                code=ErrorCode.RESPONSE_TIMEOUT,
                                message="AI is taking too long to respond",
                                user_action="Please try again. If this persists, try reloading the session.",
                                recoverable=True,
                                transport_error="RESPONSE_TIMEOUT",
                                original_message=f"Prompt sent, but no response completed within {timeout_s}s.",
                                page_url=page.url,
                                selector=self.STOP_BUTTON,
                            ),
                        ),
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
            # 7. UNEXPECTED_EXCEPTION
            return (
                False,
                None,
                None,
                _create_metadata(
                    start_ts=start_ts,
                    timeout_s=timeout_s,
                    ws_url=self._cdp_url,
                    ws_source=self._cdp_origin,
                    error=_create_error(
                        category=ErrorCategory.UNEXPECTED,
                        code=ErrorCode.UNEXPECTED,
                        message="An unexpected error occurred",
                        user_action="Please report this bug.",
                        recoverable=True,
                        transport_error="UNEXPECTED_EXCEPTION",
                        original_message=str(e),
                        exception_type=type(e).__name__,
                    ),
                ),
            )

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
        """Count response messages."""
        try:
            return await page.locator(self.RESPONSE_CONTAINER).count()
        except Exception:
            return 0

    async def _send_message(self, page: Page, message: str) -> bool:
        """
        Type the message and send it.

        Tries multiple strategies:
        1. Fill the input box (works for simple inputs)
        2. Click + type (works for contenteditable)
        3. Click + evaluate innerText (works for complex editors)
        4. Press Enter to send
        """
        try:
            box = page.locator(self.INPUT_BOX).first
            await box.wait_for(state="visible", timeout=5000)

            # Try fill first
            try:
                await box.fill(message, timeout=2000)
            except Exception:
                # Fallback: click + type or evaluate
                await box.click(timeout=2000)
                await asyncio.sleep(0.1)

                # Try typing first
                try:
                    await page.keyboard.type(message)
                except Exception:
                    # Last resort: set innerText directly (for Quill/complex editors)
                    await box.evaluate(f"el => el.innerText = {repr(message)}")
                    await asyncio.sleep(0.2)

            # Send the message (Enter key)
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
                # Wait for the stop button to appear first
                await page.wait_for_selector(self.STOP_BUTTON, state="visible", timeout=10000)
                # Now, wait for it to disappear within the main timeout
                deadline = time.time() + timeout_s
                while time.time() < deadline:
                    if await page.locator(self.STOP_BUTTON).count() == 0:
                        return True  # It appeared and then disappeared
                    await asyncio.sleep(self.COMPLETION_CHECK_INTERVAL_S)
                return False  # Timed out waiting for it to disappear
            except PWTimeout:
                # wait_for_selector timed out (stop never appeared)
                return True  # Treat as instant completion
            except Exception:
                # Other error (e.g., page closed)
                return True  # Don't hang
        except Exception:
            # Outer try/except
            return True

    async def _extract_response(
        self, page: Page, baseline_count: int
    ) -> tuple[str | None, str | None]:
        """
        Extract the latest response text (markdown/plain).

        Waits for new response to appear, then extracts content from the last
        response container using the configured selectors.
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

            # Try to get content from the specific content selector first
            content = page.locator(self.RESPONSE_CONTENT).last
            if await content.count() > 0:
                text = (await content.inner_text() or "").strip()
                snippet = text[: self.SNIPPET_LENGTH]
                return snippet, text

            # Fallback: last response container's text
            last_bubble = page.locator(self.RESPONSE_CONTAINER).last
            if await last_bubble.count() > 0:
                txt = (await last_bubble.inner_text() or "").strip()
                return (txt[: self.SNIPPET_LENGTH], txt)

            return "", ""
        except Exception as e:
            if self._logger:
                self._logger.warning(f"_extract_response failed: {e}")
            return "", ""

    # ---------- Chat Management ----------

    async def list_chats(self) -> List[ChatInfo]:
        """
        List all available chats from browser tabs.

        Returns:
            List of ChatInfo objects for matching tabs
        """
        try:
            # Ensure we have connection
            await self._get_cdp_url()
            pages_info = await self.browser_pool.list_pages()

            chats = []
            for page_info in pages_info:
                url = page_info.get("url", "")
                title = page_info.get("title", "") or "Untitled"

                # Check if this page matches our base URL
                if self.base_url in url:
                    chat_id = self._extract_chat_id_from_url(url)
                    is_current = False  # We don't track current page in base implementation

                    chats.append(
                        ChatInfo(
                            chat_id=chat_id or url, title=title, url=url, is_current=is_current
                        )
                    )

            return chats

        except Exception as e:
            if self._logger:
                self._logger.error(f"Failed to list chats: {e}")
            return []

    async def get_current_chat(self) -> ChatInfo | None:
        """
        Get info about currently active chat.

        Returns:
            ChatInfo for current chat, or None if not available
        """
        try:
            if not self._page:
                return None

            url = self._page.url
            title = await self._page.title() if self._page else "Untitled"
            chat_id = self._extract_chat_id_from_url(url)

            return ChatInfo(chat_id=chat_id or url, title=title, url=url, is_current=True)
        except Exception as e:
            if self._logger:
                self._logger.error(f"Failed to get current chat: {e}")
            return None

    async def switch_chat(self, chat_id: str) -> bool:
        """
        Switch to a specific chat by ID or URL.

        Args:
            chat_id: Chat ID, URL, or identifier

        Returns:
            True if successful, False otherwise
        """
        try:
            # If it looks like a URL, navigate directly
            if chat_id.startswith(("http://", "https://")):
                target_url = chat_id
            else:
                # Assume it's a chat ID - construct URL
                target_url = f"{self.base_url}/chat/{chat_id}"

            if not self._page:
                # Get a new page for this URL
                ws_url, _ = await self._get_cdp_url()
                self._page = await self._pick_page(ws_url)
                if not self._page:
                    return False

            await self._page.goto(target_url, wait_until="domcontentloaded", timeout=15000)
            await self._page.wait_for_selector(self.INPUT_BOX, state="visible", timeout=5000)
            return True

        except Exception as e:
            if self._logger:
                self._logger.error(f"Failed to switch chat: {e}")
            return False

    async def start_new_chat(self) -> ChatInfo | None:
        """
        Start a new chat by clicking new chat button.
        This is the ONLY way to start fresh - there is no "reset" in web UIs.

        Returns:
            ChatInfo for new chat, or None if failed
        """
        try:
            if not self._page:
                ws_url, _ = await self._get_cdp_url()
                self._page = await self._pick_page(ws_url)
                if not self._page:
                    return None

            self._ready = False  # Navigating to new chat

            # Try to click new chat button
            new_chat_btn = self._page.locator(self.NEW_CHAT_BUTTON)
            if await new_chat_btn.count() > 0:
                await new_chat_btn.first.click()
                # Wait for navigation to complete
                await self._page.wait_for_load_state("networkidle", timeout=10000)
                # Wait for input to be ready
                await self._page.wait_for_selector(self.INPUT_BOX, state="visible", timeout=5000)
                self._ready = True

                # Get new chat info
                return await self.get_current_chat()
            else:
                # Fallback: navigate to new chat URL
                new_chat_url = f"{self.base_url}/new"
                await self._page.goto(new_chat_url, wait_until="domcontentloaded", timeout=15000)
                await self._page.wait_for_selector(self.INPUT_BOX, state="visible", timeout=5000)
                self._ready = True
                return await self.get_current_chat()

        except Exception as e:
            if self._logger:
                self._logger.error(f"Failed to start new chat: {e}")
            self._ready = False
            return None

    def _extract_chat_id_from_url(self, url: str) -> str:
        """
        Extract chat ID from URL.

        Args:
            url: Page URL

        Returns:
            Chat ID or empty string if not found
        """
        # Common patterns for chat URLs
        patterns = [
            r"/chat/([a-f0-9-]+)",  # Claude pattern
            r"/c/([a-zA-Z0-9-]+)",  # ChatGPT pattern
            r"/([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})",  # UUID pattern
        ]

        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)

        return ""
