# src/daemon/transport/gemini_web.py
from __future__ import annotations

import asyncio
import time
from typing import Optional, Tuple

from playwright.async_api import Page

from .web import WebTransport


class GeminiWebTransport(WebTransport):
    """
    Web transport tuned for Gemini's UI (selectors + overrides).
    Mimics ClaudeWebTransport structure exactly.
    """

    # --- Selectors (from F12 inspection) ---
    INPUT_BOX = "div.ql-editor[contenteditable='true'][aria-label*='prompt']"
    STOP_BUTTON = "mat-icon[fonticon='stop']"
    SEND_BUTTON = "button[aria-label='Send message']"
    NEW_CHAT_BUTTON = "button:has-text('New chat'), a:has-text('New chat')"
    RESPONSE_CONTAINER = "message-content"
    RESPONSE_CONTENT = "div.markdown.markdown-main-panel"

    # --- Timing knobs ---
    RESPONSE_WAIT_S = 60.0
    COMPLETION_CHECK_INTERVAL_S = 0.3
    SNIPPET_LENGTH = 280

    # ---------------------------------------------------------------------
    # Gemini-specific overrides
    # ---------------------------------------------------------------------

    async def _get_response_count(self, page: Page) -> int:
        """Count message-content elements (Gemini's response containers)."""
        try:
            return await page.locator(self.RESPONSE_CONTAINER).count()
        except Exception:
            return 0

    async def _send_message(self, page: Page, message: str) -> bool:
        """
        Send message to Gemini:
          - wait for INPUT_BOX visible
          - click + set innerText (contenteditable div)
          - press Enter or click send button
        """
        try:
            box = page.locator(self.INPUT_BOX).first
            await box.wait_for(state="visible", timeout=5000)

            # Click to focus
            await box.click(timeout=2000)
            await asyncio.sleep(0.1)
            
            # Set text in contenteditable div (Gemini uses Quill editor)
            await box.evaluate(f"el => el.innerText = {repr(message)}")
            await asyncio.sleep(0.2)
            
            # Try to click send button
            try:
                send_btn = page.locator(self.SEND_BUTTON).first
                await send_btn.wait_for(state="visible", timeout=2000)
                await send_btn.click()
            except Exception:
                # Fallback: press Enter
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

    async def _extract_response(self, page: Page, baseline_count: int) -> Tuple[str, str]:
        """
        Extract last response from Gemini's UI.
        Steps:
          - wait up to RESPONSE_WAIT_S for response_count > baseline_count
          - select last message-content element
          - get markdown content
        """
        content_sel = self.RESPONSE_CONTENT
        wait_s = float(self.RESPONSE_WAIT_S)
        poll = float(self.COMPLETION_CHECK_INTERVAL_S)

        # Wait for the new message to appear (beyond baseline)
        try:
            deadline = time.time() + wait_s
            while time.time() < deadline:
                count = await page.locator(self.RESPONSE_CONTAINER).count()
                if count > baseline_count:
                    break
                await asyncio.sleep(poll)
        except Exception:
            # Continue anyway; maybe the node is already there
            pass

        # Get all response containers
        containers = page.locator(self.RESPONSE_CONTAINER)
        container_count = await containers.count()
        
        if container_count == 0:
            return "", ""
        
        # Get the last container
        last_container = containers.nth(container_count - 1)
        
        # Try to get content from markdown element
        text: str = ""
        try:
            content = last_container.locator(content_sel).first
            if await content.count() > 0:
                text = (await content.inner_text() or "").strip()
        except Exception:
            pass

        # Fallback: get all text from container
        if not text:
            try:
                text = (await last_container.inner_text() or "").strip()
            except Exception:
                text = ""

        snippet = text[: self.SNIPPET_LENGTH] if text else ""
        return snippet, text
