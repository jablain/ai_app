# src/daemon/transport/claude_web.py
from __future__ import annotations

import asyncio
import time

try:
    import markdownify  # optional
except Exception:
    markdownify = None  # type: ignore

from playwright.async_api import Page

from .web import WebTransport


class ClaudeWebTransport(WebTransport):
    """
    Web transport tuned for Claude's UI (selectors + a couple of small overrides).
    Uses the exact method you outlined:
      - send via contenteditable + Enter
      - wait for Stop button to disappear OR response-count stabilize
      - extract last .standard-markdown (text first, then html→markdownify fallback)
    """

    # --- Selectors (robust, broad) ---
    INPUT_BOX = "div[contenteditable='true']"
    STOP_BUTTON = "button[aria-label='Stop response']"
    NEW_CHAT_BUTTON = "button[aria-label*='New chat']"
    RESPONSE_CONTAINER = "div.font-claude-response"
    RESPONSE_CONTENT = ".standard-markdown"

    # --- Timing knobs (inherit sane defaults from WebTransport, override if needed) ---
    RESPONSE_WAIT_S = 60.0
    COMPLETION_CHECK_INTERVAL_S = 0.3
    SNIPPET_LENGTH = 280

    # ---------------------------------------------------------------------
    # Claude-specific overrides
    # ---------------------------------------------------------------------

    async def _get_response_count(self, page: Page) -> int:
        """Count only bubbles that actually contain markdown content."""
        try:
            sel = f"{self.RESPONSE_CONTAINER}:has({self.RESPONSE_CONTENT})"
            return await page.locator(sel).count()
        except Exception:
            return 0

    async def _send_message(self, page: Page, message: str) -> bool:
        """
        Old, reliable injection:
          - wait for INPUT_BOX visible
          - try fill(); if that fails (common on contenteditable), click+type
          - press Enter
        """
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
        except Exception:
            return False

    async def _wait_for_response_complete(self, page: Page, timeout_s: float) -> bool:
        """
        Wait pattern:
          1) If Stop button appears, wait until it disappears (or timeout).
          2) If Stop never appears (fast response), treat as done.
        """
        sel = self.STOP_BUTTON
        try:
            # Try to see it appear (fast responses may skip this)
            try:
                await page.wait_for_selector(sel, state="visible", timeout=8000)
                # Now wait for it to disappear (i.e., completion)
                deadline = time.time() + timeout_s
                while time.time() < deadline:
                    if await page.locator(sel).count() == 0:
                        return True
                    await asyncio.sleep(self.COMPLETION_CHECK_INTERVAL_S)
                return False  # still visible after timeout
            except Exception:
                # Stop never visible => likely instantaneous response
                return True
        except Exception:
            # Be permissive; extraction step will verify content
            return True

    async def _extract_response(self, page: Page, baseline_count: int) -> tuple[str, str]:
        """
        Extract last markdown block from Claude's UI.
        Steps:
          - wait up to RESPONSE_WAIT_S for response_count > baseline_count
          - select last .standard-markdown
          - prefer inner_text(); if empty, inner_html() and markdownify fallback
        """
        content_sel = self.RESPONSE_CONTENT
        wait_s = float(self.RESPONSE_WAIT_S)
        poll = float(self.COMPLETION_CHECK_INTERVAL_S)

        # Wait for the new bubble to appear (beyond baseline)
        try:
            deadline = time.time() + wait_s
            while time.time() < deadline:
                count = await page.locator(f"{self.RESPONSE_CONTAINER}:has({content_sel})").count()
                if count > baseline_count:
                    break
                await asyncio.sleep(poll)
        except Exception:
            # Continue anyway; maybe the node is already there
            pass

        last = page.locator(content_sel).last
        if await last.count() == 0:
            # Nothing to extract
            return "", ""

        # Prefer readable text first
        text: str = ""
        try:
            text = (await last.inner_text() or "").strip()
        except Exception:
            text = ""

        if not text:
            # Fallback to HTML → markdownify (if available)
            html: str = ""
            try:
                html = (await last.inner_html() or "").strip()
            except Exception:
                html = ""

            if html and markdownify:
                try:
                    text = markdownify.markdownify(html, heading_style="ATX").strip()
                except Exception:
                    text = html or ""
            else:
                text = html or ""

        snippet = text[: self.SNIPPET_LENGTH] if text else ""
        return snippet, text
