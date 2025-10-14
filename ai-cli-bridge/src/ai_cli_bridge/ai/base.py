"""Abstract base class for AI browser automation."""

import asyncio
import time
from abc import ABC, abstractmethod
from typing import Optional, Tuple, Dict, Any
from datetime import datetime, timezone

from playwright.async_api import async_playwright, Page, TimeoutError as PWTimeout

class BaseAI(ABC):
    """
    Abstract base class for AI-specific browser automation.
    
    Defines the public interface and common implementation for all AI targets.
    Each concrete AI class (ClaudeAI, ChatGPTAI, etc.) must implement
    the abstract methods with AI-specific logic.
    """
    
    # =========================
    # Class-level configuration
    # =========================
    
    @classmethod
    @abstractmethod
    def get_default_config(cls) -> Dict[str, Any]:
        """
        Get default configuration for this AI.
        
        Returns:
            Dict with ai_target, base_url, cdp port, etc.
        """
        pass
    
    
    # =========================
    # Common state (shared by all AIs)
    # =========================
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize base AI.
        
        Args:
            config: Config dict with 'ai_target' and 'cdp' keys
        """
        self._config = config
        self._debug_enabled = False
        self._cdp_url: Optional[str] = None
        self._cdp_source: Optional[str] = None
        self._turn_count: int = 0
        self._last_page_url: Optional[str] = None

    # =========================
    # Public interface (Template Method)
    # =========================
    
    async def send_prompt(
        self,
        message: str,
        wait_for_response: bool = True,
        timeout_s: int = 120
    ) -> Tuple[bool, Optional[str], Optional[str], Optional[Dict[str, Any]]]:
        """
        Public method to send a prompt using the Template Method Pattern.
        Handles connection, page selection, and cleanup, then calls the
        subclass-specific implementation.
        """
        ws_url, ws_source = await self._discover_cdp_url()
        if not ws_url:
            self._debug(f"CDP discovery failed: {ws_source}")
            return False, None, None, {"error": "no_cdp", "source": ws_source}
            
        self._debug(f"CDP connected via {ws_source}: {ws_url}")
        
        pw = await async_playwright().start()
        remote = None
        
        try:
            remote = await pw.chromium.connect_over_cdp(ws_url)
            page = await self._pick_page(remote, self.get_base_url())
            
            if not page:
                self._debug("No suitable page found")
                return False, None, None, {"error": "no_page"}
                
            self._last_page_url = page.url
            self._debug(f"Operating on page: {page.url}")
            
            # Call the subclass-specific implementation
            success, snippet, markdown, metadata = await self._execute_interaction(
                page, message, wait_for_response, timeout_s
            )
            
            # --- CENTRAlIZED LOGIC ---
            if success:
                self._turn_count += 1
                self._debug(f"Turn count incremented to: {self._turn_count}")

            # Add common metadata
            if metadata:
                 metadata["ws_source"] = ws_source
                 metadata["timestamp"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

            return success, snippet, markdown, metadata
            
        finally:
            if remote: await remote.close()
            await pw.stop()

    # =========================
    # Abstract methods (to be implemented by subclasses)
    # =========================

    @abstractmethod
    async def _execute_interaction(
        self,
        page: Page,
        message: str,
        wait_for_response: bool,
        timeout_s: int
    ) -> Tuple[bool, Optional[str], Optional[str], Optional[Dict[str, Any]]]:
        """
        Subclass-specific implementation for the core AI interaction.
        This method is called by the public send_prompt method.
        """
        pass
        
    @abstractmethod
    async def list_messages(self) -> list[Dict[str, Any]]:
        """
        List all messages in the current conversation.
        
        Returns:
            List of message dictionaries with keys:
            - index: int
            - type: 'user' | 'assistant' | 'system'
            - preview: str (first ~60 chars)
            - length: int (character count)
        """
        pass
    
    
    @abstractmethod
    async def extract_message(self, index: int) -> Optional[str]:
        """
        Extract the full content of a specific message.
        
        Args:
            index: Message index (from list_messages)
            
        Returns:
            Full message content or None if not found
        """
        pass
    
    
    @abstractmethod
    async def get_status(self) -> Dict[str, Any]:
        """
        Get current session status.
        
        Returns:
            Dictionary with:
            - connected: bool
            - page_url: str
            - message_count: int
            - session_duration_s: float
            - etc. (AI-specific fields)
        """
        pass
    
    # =========================
    # Public interface (common implementation)
    # =========================
    
    def get_turn_count(self) -> int:
        """Get the current turn count for the session."""
        return self._turn_count

    def reset_turn_count(self) -> None:
        """Reset the session turn count to 0."""
        self._debug("Turn count reset to 0.")
        self._turn_count = 0
        
    def set_debug(self, enabled: bool) -> None:
        """Enable or disable debug output."""
        self._debug_enabled = enabled
    
    
    def get_debug(self) -> bool:
        """Get current debug state."""
        return self._debug_enabled
    
    
    def get_cdp_info(self) -> Tuple[Optional[str], Optional[str]]:
        """
        Get CDP connection information.
        
        Returns:
            Tuple of (ws_url, source) where source is 'env'|'discovered'|'none'
        """
        return self._cdp_url, self._cdp_source
    
    
    def get_cdp_port(self) -> int:
        """Get CDP port from config (default 9222)."""
        try:
            return int(self._config.get("cdp", {}).get("port", 9222))
        except Exception:
            return 9222
            
    def get_base_url(self) -> str:
        """Helper to get base_url from config."""
        return self._config.get("base_url", "")
    
    
    # =========================
    # Protected helpers (available to subclasses)
    # =========================
    
    def _debug(self, msg: str) -> None:
        """Print debug message if debugging is enabled."""
        if self._debug_enabled:
            print(f"[{self.__class__.__name__}] {msg}")
    
    
    # =========================
    # Template methods (can be overridden by subclasses)
    # =========================
    
    async def _discover_cdp_url(self) -> Tuple[Optional[str], str]:
        """
        Discover CDP WebSocket URL.
        
        Default implementation checks:
        1. Environment variable AI_CLI_BRIDGE_CDP_URL
        2. HTTP probe to http://127.0.0.1:<port>/json/version
        
        Subclasses can override for custom discovery logic.
        
        Returns:
            Tuple of (ws_url or None, source: 'env'|'discovered'|'none')
        """
        import os
        from urllib.request import urlopen
        from urllib.error import URLError, HTTPError
        import json
        
        # Check environment variable
        env = (os.environ.get("AI_CLI_BRIDGE_CDP_URL") or "").strip()
        if env.startswith(("ws://", "wss://")) and "/devtools/browser/" in env:
            self._cdp_url = env
            self._cdp_source = "env"
            return env, "env"
        
        # Probe HTTP endpoint
        port = self.get_cdp_port()
        
        url = f"http://127.0.0.1:{port}/json/version"
        try:
            with urlopen(url, timeout=2.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                ws = (data.get("webSocketDebuggerUrl") or "").strip()
                if ws.startswith(("ws://", "wss://")) and "/devtools/browser/" in ws:
                    self._cdp_url = ws
                    self._cdp_source = "discovered"
                    return ws, "discovered"
        except (URLError, HTTPError, TimeoutError, ValueError, json.JSONDecodeError):
            pass
        
        self._cdp_url = None
        self._cdp_source = "none"
        return None, "none"
    
    
    async def _pick_page(self, remote, base_url: Optional[str]):
        """
        Pick a page from browser contexts.
        
        Default implementation prefers pages matching base_url, else first page.
        
        Args:
            remote: Playwright browser instance connected via CDP
            base_url: Preferred base URL to match
            
        Returns:
            Page object or None
        """
        try:
            contexts = getattr(remote, "contexts", []) or []
            pages = []
            for ctx in contexts:
                pages.extend(getattr(ctx, "pages", []) or [])
            
            if base_url:
                for p in pages:
                    try:
                        if (p.url or "").startswith(base_url):
                            return p
                    except Exception:
                        continue
            
            return pages[0] if pages else None
        except Exception:
            return None
    
    
    # =========================
    # AI-specific methods (must be implemented by subclasses)
    # =========================
    
    @abstractmethod
    async def _wait_for_response_complete(self, page: Page, timeout_s: int) -> bool:
        """
        Wait for AI response to complete (AI-specific implementation).
        
        Args:
            page: Playwright page object
            timeout_s: Maximum time to wait
            
        Returns:
            True if completion detected, False on timeout
        """
        pass
    
    
    @abstractmethod
    async def _extract_response(
        self,
        page: Page,
        baseline_count: int
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Extract the last AI response from the page (AI-specific implementation).
        
        Args:
            page: Playwright page object
            baseline_count: Number of responses before sending prompt
            
        Returns:
            Tuple of (snippet, full_markdown) or (None, None)
        """
        pass
    
    
    @abstractmethod
    async def _ensure_chat_ready(self, page: Page) -> bool:
        """
        Ensure the chat interface is ready for input (AI-specific implementation).
        
        Args:
            page: Playwright page object
            
        Returns:
            True if chat is ready, False otherwise
        """
        pass
