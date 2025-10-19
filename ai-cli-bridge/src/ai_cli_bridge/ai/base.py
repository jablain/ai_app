"""Abstract base class for AI browser automation."""

import asyncio
import time
from abc import ABC, abstractmethod
from typing import Optional, Tuple, Dict, Any, List
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
            Dict with ai_target, base_url, cdp port, max_context_tokens, etc.
        """
        pass
    
    
    # =========================
    # Common state (shared by all AIs)
    # =========================
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize base AI.
        
        Args:
            config: Config dict with 'ai_target', 'cdp', and 'max_context_tokens' keys
        """
        self._config = config
        self._debug_enabled = False
        self._cdp_url: Optional[str] = None
        self._cdp_source: Optional[str] = None
        self._last_page_url: Optional[str] = None
        
        # Persistent session state
        self._turn_count: int = 0
        self._token_count: int = 0  # Renamed from _token_estimate for clarity
        self._message_count: int = 0
        self._session_start_time: float = time.time()
        self._last_interaction_time: Optional[float] = None
        self._message_history: List[Dict[str, Any]] = []
        
        # CTAW (Current Active Token Window) size from config
        self._ctaw_size: int = config.get("max_context_tokens", 200000)

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
            
            # --- CENTRALIZED STATE TRACKING ---
            if success:
                # Increment counters
                self._turn_count += 1
                self._message_count += 1
                self._last_interaction_time = time.time()
                
                # Update token count: (sent + response) / 4
                sent_chars = len(message)
                response_chars = len(markdown or snippet or "")
                tokens_used = (sent_chars + response_chars) // 4
                self._token_count += tokens_used
                
                # Track message in history
                self._message_history.append({
                    "turn": self._turn_count,
                    "timestamp": self._last_interaction_time,
                    "sent_chars": sent_chars,
                    "response_chars": response_chars,
                    "tokens_used": tokens_used,
                })
                
                self._debug(
                    f"Turn: {self._turn_count}, "
                    f"Tokens: {self._token_count}, "
                    f"CTAW: {self.get_ctaw_usage_percent():.1f}%"
                )

            # Add common metadata
            if metadata:
                metadata.update({
                    "ws_source": ws_source,
                    "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                    "turn_count": self._turn_count,
                    "message_count": self._message_count,
                    "token_count": self._token_count,
                    "ctaw_usage_percent": round(self.get_ctaw_usage_percent(), 2),
                    "ctaw_size": self._ctaw_size,
                    "session_duration_s": round(self.get_session_duration_s(), 1),
                })

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
    
    
    # =========================
    # Session state management (implemented in base)
    # =========================
    
    async def get_status(self) -> Dict[str, Any]:
        """
        Get current session status.
        
        Returns:
            Dictionary with connection and session state
        """
        # Ensure CDP info is discovered
        if self._cdp_url is None:
            await self._discover_cdp_url()
        
        ws_url, ws_source = self.get_cdp_info()
        
        return {
            "ai_target": self._config.get("ai_target", "unknown"),
            "connected": ws_url is not None,
            "cdp_source": ws_source,
            "cdp_url": ws_url,
            "last_page_url": self._last_page_url,
            "message_count": self._message_count,
            "turn_count": self._turn_count,
            "token_count": self._token_count,
            "ctaw_size": self._ctaw_size,
            "ctaw_usage_percent": round(self.get_ctaw_usage_percent(), 2),
            "session_duration_s": round(self.get_session_duration_s(), 1),
            "debug_enabled": self._debug_enabled,
        }
    
    def get_turn_count(self) -> int:
        """Get the current turn count for the session."""
        return self._turn_count
    
    def get_message_count(self) -> int:
        """Get the current message count for the session."""
        return self._message_count
    
    def get_token_count(self) -> int:
        """Get the current token count for the session."""
        return self._token_count
    
    def get_ctaw_size(self) -> int:
        """Get the CTAW (context window) size for this AI."""
        return self._ctaw_size
    
    def get_ctaw_usage_percent(self) -> float:
        """
        Get the CTAW usage as a percentage.
        
        Formula: (TokenCount / CTAWSize) * 100
        
        Returns:
            Percentage (0.0 to 100.0+)
        """
        if self._ctaw_size <= 0:
            return 0.0
        return (self._token_count / self._ctaw_size) * 100.0
    
    def get_session_duration_s(self) -> float:
        """Get the session duration in seconds since creation."""
        return time.time() - self._session_start_time
    
    def reset_session_state(self) -> None:
        """
        Reset all session state (call when starting new chat).
        
        This clears turn counter, token counts, and message history.
        """
        self._debug("Resetting session state")
        self._turn_count = 0
        self._message_count = 0
        self._token_count = 0
        self._session_start_time = time.time()
        self._last_interaction_time = None
        self._message_history.clear()

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
        """Get CDP port from config (default 9223)."""
        try:
            return int(self._config.get("cdp", {}).get("port", 9223))
        except Exception:
            return 9223
            
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

    @abstractmethod
    async def start_new_session(self, page: Page) -> bool:
        """
        Start a new chat session/conversation (AI-specific implementation).

        Args:
            page: Playwright page object targeting this AI's website.

        Returns:
            True if a new session was started successfully, False otherwise.
        """
        pass
