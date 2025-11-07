# ruff: noqa: E402
"""Main window for AI Chat UI"""

from __future__ import annotations

import logging
import subprocess
import threading
from typing import Any

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk

from chat_ui import stats_helper
from chat_ui.cli_wrapper import CLIWrapper, SendResponse
from chat_ui.response_display import ResponseDisplay
from chat_ui.stats_display import StatsDisplay

logger = logging.getLogger(__name__)

# UI Constants
SIDEBAR_WIDTH = 200
STATS_PANEL_WIDTH = 250
INPUT_HEIGHT = 80
MARGIN_SMALL = 6
MARGIN_MEDIUM = 12
SPACING_SMALL = 4
SPACING_MEDIUM = 6

# Timeout Constants (seconds)
REFRESH_INTERVAL_S = 3
SEND_TIMEOUT_S = 120
DAEMON_STOP_TIMEOUT_S = 10

# Context Warning Thresholds (percent)
DEFAULT_YELLOW_THRESHOLD = 70
DEFAULT_ORANGE_THRESHOLD = 85
DEFAULT_RED_THRESHOLD = 95


class ChatWindow(Gtk.ApplicationWindow):
    """Main application window for AI Chat"""

    def __init__(self, application: Gtk.Application, daemon_client: CLIWrapper) -> None:
        super().__init__(application=application)
        self.daemon_client = daemon_client
        self.current_ai = "claude"  # Default AI
        self._refresh_timeout_id: int | None = None
        self._ai_change_guard = False  # Prevent double-refresh on AI change

        self.set_title("AI Chat")
        self.set_default_size(1000, 700)

        # Build UI
        self._build_ui()

        # Load available AIs dynamically
        self._load_available_ais()

        # Initial stats refresh (in background)
        threading.Thread(target=self._refresh_status_thread, daemon=True).start()

        # Initial chat list load (in background)
        threading.Thread(target=self._load_chats_thread, daemon=True).start()

        # Start periodic refresh
        self._start_periodic_refresh()

    def _build_ui(self) -> None:
        """Build the GTK4 interface"""
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        # Header bar with AI selector
        self._build_header_bar()

        # Content area (chat list + response + stats)
        content_box = self._build_content_area()
        main_box.append(content_box)

        # Input area
        input_box = self._build_input_area()
        main_box.append(input_box)

        # Status bar
        self.status_label = self._build_status_bar()
        main_box.append(self.status_label)

        self.set_child(main_box)

        # Set focus to input view so user can type immediately
        self.input_view.grab_focus()

    def _build_header_bar(self) -> None:
        """Build header bar with AI selector"""
        header = Gtk.HeaderBar()

        # AI selector (GTK4 DropDown with StringList)
        self.ai_model = Gtk.StringList()
        self.ai_selector = Gtk.DropDown(model=self.ai_model)
        self.ai_selector.connect("notify::selected", self._on_ai_changed)
        header.pack_start(self.ai_selector)

        self.set_titlebar(header)

    def _build_content_area(self) -> Gtk.Box:
        """Build the main content area with chat list, response display, and stats"""
        content_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=MARGIN_MEDIUM)
        content_box.set_margin_top(MARGIN_MEDIUM)
        content_box.set_margin_bottom(MARGIN_MEDIUM)
        content_box.set_margin_start(MARGIN_MEDIUM)
        content_box.set_margin_end(MARGIN_MEDIUM)

        # Chat list sidebar
        chat_sidebar = self._build_chat_sidebar()
        content_box.append(chat_sidebar)

        # Response display
        self.response_display = ResponseDisplay()
        self.response_display.set_hexpand(True)
        content_box.append(self.response_display.get_widget())

        # Stats display
        self.stats_display = StatsDisplay()
        self.stats_display.set_size_request(STATS_PANEL_WIDTH, -1)
        content_box.append(self.stats_display.get_widget())

        return content_box

    def _build_chat_sidebar(self) -> Gtk.Box:
        """Build the chat list sidebar with header and list"""
        chat_sidebar = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=SPACING_MEDIUM)
        chat_sidebar.set_size_request(SIDEBAR_WIDTH, -1)

        # Chat list header with buttons
        chat_header = self._build_chat_header()
        chat_sidebar.append(chat_header)

        # Chat list in scrolled window
        chat_scroll = Gtk.ScrolledWindow()
        chat_scroll.set_vexpand(True)
        chat_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)

        self.chat_listbox = Gtk.ListBox()
        self.chat_listbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.chat_listbox.connect("row-activated", self._on_chat_selected)
        chat_scroll.set_child(self.chat_listbox)

        chat_sidebar.append(chat_scroll)

        return chat_sidebar

    def _build_chat_header(self) -> Gtk.Box:
        """Build the chat header with label and buttons"""
        chat_header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=SPACING_SMALL)

        chat_label = Gtk.Label(label="Chats")
        chat_label.set_hexpand(True)
        chat_label.set_halign(Gtk.Align.START)
        chat_header.append(chat_label)

        # New chat button
        new_chat_btn = Gtk.Button(label="+")
        new_chat_btn.connect("clicked", self._on_new_chat_clicked)
        new_chat_btn.set_tooltip_text("New Chat")
        chat_header.append(new_chat_btn)

        # Refresh button
        refresh_btn = Gtk.Button(label="⟳")
        refresh_btn.connect("clicked", self._on_refresh_chats_clicked)
        refresh_btn.set_tooltip_text("Refresh Chat List")
        chat_header.append(refresh_btn)

        return chat_header

    def _build_input_area(self) -> Gtk.Box:
        """Build the input text area with send button"""
        input_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=SPACING_MEDIUM)
        input_box.set_margin_top(0)
        input_box.set_margin_bottom(MARGIN_MEDIUM)
        input_box.set_margin_start(MARGIN_MEDIUM)
        input_box.set_margin_end(MARGIN_MEDIUM)

        # Input text view in scrolled window
        scroll = Gtk.ScrolledWindow()
        scroll.set_size_request(-1, INPUT_HEIGHT)
        scroll.set_hexpand(True)
        scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)

        self.input_view = Gtk.TextView()
        self.input_view.set_wrap_mode(Gtk.WrapMode.WORD)
        self.input_view.set_left_margin(MARGIN_SMALL)
        self.input_view.set_right_margin(MARGIN_SMALL)
        self.input_view.set_top_margin(MARGIN_SMALL)
        self.input_view.set_bottom_margin(MARGIN_SMALL)
        scroll.set_child(self.input_view)
        input_box.append(scroll)

        # Send button
        self.send_button = Gtk.Button(label="Send")
        self.send_button.connect("clicked", self._on_send_clicked)
        self.send_button.set_valign(Gtk.Align.END)
        input_box.append(self.send_button)

        return input_box

    def _build_status_bar(self) -> Gtk.Label:
        """Build the status bar at the bottom"""
        status_label = Gtk.Label(label="Ready")
        status_label.set_halign(Gtk.Align.START)
        status_label.set_margin_start(MARGIN_MEDIUM)
        status_label.set_margin_bottom(MARGIN_SMALL)
        return status_label

    def _load_available_ais(self) -> None:
        """Populate AI dropdown from daemon (with fallback)"""
        ais = self.daemon_client.get_available_ais()
        logger.info(f"Loading available AIs: {ais}")

        # Guard against change notifications during rebuild
        self._ai_change_guard = True

        # Clear StringList model
        while self.ai_model.get_n_items() > 0:
            self.ai_model.remove(0)

        # Populate with available AIs
        for ai in ais:
            self.ai_model.append(ai)

        # Set to current AI (case-insensitive lookup)
        ai_lower = {ai.lower(): i for i, ai in enumerate(ais)}
        idx = ai_lower.get(self.current_ai.lower(), 0)
        self.ai_selector.set_selected(idx)

        # Update current_ai from selection
        if ais:
            self.current_ai = ais[idx]
            logger.debug(f"Selected AI: {self.current_ai}")

        # Release guard
        self._ai_change_guard = False

    def _on_ai_changed(self, dropdown: Gtk.DropDown, _param: Any) -> None:
        """Handle AI selection change"""
        # Prevent double-refresh during dropdown rebuild
        if self._ai_change_guard:
            return

        # Guard against invalid selection
        idx = self.ai_selector.get_selected()
        if idx < 0:
            return

        ai = self.ai_model.get_string(idx)

        if ai and ai != self.current_ai:
            self.current_ai = ai
            logger.info(f"Switched to AI: {self.current_ai}")
            # Clear response display to avoid showing stale content
            self.response_display.clear()
            # Refresh stats for new AI (in background)
            threading.Thread(target=self._refresh_status_thread, daemon=True).start()
            # Refresh chat list for new AI
            threading.Thread(target=self._load_chats_thread, daemon=True).start()

    def _extract_ai_fields(self, ai_json: dict[str, Any]) -> dict[str, Any]:
        """
        Extract fields from AI status JSON with robust fallbacks

        Args:
            ai_json: AI status dict from daemon

        Returns:
            Dict with normalized field names and values
        """
        # Clamp percentage to 0-100 range
        ctw_pct_raw = ai_json.get("ctaw_usage_percent", ai_json.get("context_used_percent", 0.0))
        ctw_pct = max(0.0, min(100.0, float(ctw_pct_raw)))

        return {
            "turns": ai_json.get("turn_count", 0),
            "messages": ai_json.get("message_count", 0),
            "tokens_total": ai_json.get("token_count", 0),
            "tokens_sent": ai_json.get("sent_tokens", 0),
            "tokens_response": ai_json.get("response_tokens", 0),
            "session_s": round(float(ai_json.get("session_duration_s", 0.0)), 1),
            # Context window: support both names
            "ctw": ai_json.get("ctaw_size", ai_json.get("context_window_tokens", 0)),
            "ctw_used_pct": ctw_pct,
            # Transport
            "transport": ai_json.get("transport_type", "unknown"),
            "connected": bool(ai_json.get("connected", False)),
            "page_url": ai_json.get("last_page_url") or "",
            "cdp_source": ai_json.get("cdp_source") or "",
        }

    def _refresh_status_thread(self) -> None:
        """Refresh status in background thread, update UI via idle_add"""
        try:
            status = self.daemon_client.get_status()
            if not status:
                GLib.idle_add(self._render_status_error, "Failed to get daemon status")
                return

            daemon_info = status.get("daemon", {})
            ais = status.get("ais", {})

            # Case-insensitive AI lookup
            ai_key_map = {k.lower(): k for k in ais.keys()}
            key = ai_key_map.get(self.current_ai.lower())

            if not key:
                GLib.idle_add(self._render_ai_unavailable, daemon_info)
                return

            # Extract fields with fallbacks
            fields = self._extract_ai_fields(ais[key])

            # Render stats on main thread - pass both fields and full AI status
            GLib.idle_add(self._render_stats, fields, daemon_info, ais[key])

        except Exception as e:
            logger.exception("Error refreshing status")
            GLib.idle_add(self._render_status_error, str(e))

    def _render_stats(
        self, fields: dict[str, Any], daemon_info: dict[str, Any], ai_status: dict[str, Any]
    ) -> bool:
        """
        Render stats to display (runs on main thread)

        Args:
            fields: Extracted AI fields
            daemon_info: Daemon info dict
            ai_status: Full AI status dict from daemon

        Returns:
            False to not repeat this idle callback
        """
        # Determine connection status
        cdp_healthy = daemon_info.get("cdp_healthy", False)

        if fields["connected"]:
            status_text = f"Connected to {self.current_ai}"
        elif cdp_healthy:
            status_text = f"{self.current_ai} available (no session)"
        else:
            status_text = f"{self.current_ai} unavailable (CDP down)"

        self.status_label.set_text(status_text)

        # Update AI info (model will use fallback since daemon doesn't provide it)
        self.stats_display.update_ai_info(self.current_ai, None)

        # Build metadata dict for stats display
        metadata = {
            "turn_count": fields["turns"],
            "message_count": fields["messages"],
            "token_count": fields["tokens_total"],
            "prompt_tokens": fields["tokens_sent"],
            "completion_tokens": fields["tokens_response"],
            "ctaw_size": fields["ctw"],
            "ctaw_usage_percent": fields["ctw_used_pct"],
            "session_duration_s": fields["session_s"],
        }

        # Add performance metrics from AI status (if available)
        performance_keys = [
            "last_response_time_ms",
            "tokens_per_sec",
            "avg_response_time_ms",
            "avg_tokens_per_sec",
        ]
        for key in performance_keys:
            if key in ai_status:
                metadata[key] = ai_status[key]

        # Update context warning thresholds from daemon config (if available)
        thresholds = daemon_info.get("context_warning_thresholds", {})
        if thresholds:
            logger.debug(f"Updating context warning thresholds: {thresholds}")
            self.stats_display.set_context_warning_thresholds(
                yellow=thresholds.get("yellow", DEFAULT_YELLOW_THRESHOLD),
                orange=thresholds.get("orange", DEFAULT_ORANGE_THRESHOLD),
                red=thresholds.get("red", DEFAULT_RED_THRESHOLD),
            )
        else:
            logger.warning("No context_warning_thresholds in daemon status response")

        self.stats_display.update_from_metadata(metadata)

        logger.debug(
            f"Stats updated for {self.current_ai}: {fields['turns']} turns, "
            f"{fields['tokens_total']} tokens"
        )

        return False  # Don't repeat this idle callback

    def _render_ai_unavailable(self, daemon_info: dict[str, Any]) -> bool:
        """Render unavailable state (runs on main thread)"""
        self.status_label.set_text(f"{self.current_ai} not available")
        self.stats_display.clear()
        logger.warning(f"AI {self.current_ai} not found in daemon status")
        return False  # Don't repeat

    def _render_status_error(self, error: str) -> bool:
        """Render error state (runs on main thread)"""
        self.status_label.set_text(f"Status error: {error}")
        logger.error(f"Status refresh error: {error}")
        return False  # Don't repeat

    def _start_periodic_refresh(self) -> None:
        """Start periodic status refresh"""

        def refresh_callback() -> bool:
            # GTK4-correct visibility check
            if self.get_visible():
                threading.Thread(target=self._refresh_status_thread, daemon=True).start()
            return True  # Continue repeating

        self._refresh_timeout_id = GLib.timeout_add_seconds(REFRESH_INTERVAL_S, refresh_callback)
        logger.debug(f"Started periodic status refresh ({REFRESH_INTERVAL_S}s interval)")

    def _stop_periodic_refresh(self) -> None:
        """Stop periodic refresh"""
        if self._refresh_timeout_id:
            GLib.source_remove(self._refresh_timeout_id)
            self._refresh_timeout_id = None
            logger.debug("Stopped periodic status refresh")

    def _get_input_text(self) -> str:
        """Get text from input view"""
        buffer = self.input_view.get_buffer()
        start = buffer.get_start_iter()
        end = buffer.get_end_iter()
        return buffer.get_text(start, end, False)

    def _clear_input(self) -> None:
        """Clear input text view"""
        buffer = self.input_view.get_buffer()
        buffer.set_text("")

    def _on_send_clicked(self, button: Gtk.Button) -> None:
        """Handle send button click"""
        prompt = self._get_input_text()

        # Validate input
        if not prompt.strip():
            self.status_label.set_text("⚠ Enter a message...")
            return

        # Quick daemon check (optional - don't auto-start)
        if not self.daemon_client.is_running():
            self.status_label.set_text("⚠ Daemon not running. Restart the app.")
            logger.error("Daemon not running when send clicked")
            return

        # Clear input and show loading
        self._clear_input()
        self.status_label.set_text("Sending...")
        self.send_button.set_sensitive(False)

        logger.info(f"Sending prompt to {self.current_ai}")

        # Send in background thread
        thread = threading.Thread(target=self._send_message_thread, args=(prompt,), daemon=True)
        thread.start()

    def _send_message_thread(self, prompt: str) -> None:
        """Background thread to send message (don't block UI)"""
        try:
            response = self.daemon_client.send_prompt(
                ai=self.current_ai,
                prompt=prompt,
                wait_for_response=True,
                timeout_s=SEND_TIMEOUT_S,
            )

            # Update UI on main thread
            GLib.idle_add(self._handle_response, response)

        except Exception as e:
            logger.exception("Error in send thread")
            GLib.idle_add(self._handle_error, str(e))

    def _handle_response(self, response: SendResponse) -> bool:
        """Handle successful response (runs on main thread)"""
        self.send_button.set_sensitive(True)

        if response.success:
            # Update stats with per-message metadata FIRST (before background refresh)
            if response.metadata:
                self.stats_display.update_from_metadata(response.metadata)
                logger.debug(f"Updated stats with per-message tokens: {response.metadata}")

            # Display markdown if available
            if response.markdown:
                self.response_display.set_markdown(response.markdown)
                logger.info("Response received and displayed")

            # Then refresh full status (updates session totals, turn count, etc.)
            threading.Thread(target=self._refresh_status_thread, daemon=True).start()

            # Show elapsed time if available
            elapsed_ms = None
            if response.metadata:
                elapsed_ms = stats_helper.extract_elapsed_ms(response.metadata)

            if elapsed_ms:
                self.status_label.set_text(f"✓ Complete ({elapsed_ms}ms)")
            else:
                self.status_label.set_text("✓ Complete")
        else:
            # Show error
            error_msg = response.error or "Unknown error"
            self.status_label.set_text(f"✗ {error_msg}")

        return False  # Don't repeat this idle callback

    def _load_chats_thread(self) -> None:
        """Load chats in background thread and update UI"""
        try:
            chats = self.daemon_client.list_chats(self.current_ai)
            GLib.idle_add(self._update_chat_list, chats)
        except Exception as e:
            logger.error(f"Failed to load chats in thread: {e}")

    def _update_chat_list(self, chats: list[dict[str, Any]]) -> bool:
        """
        Update chat list in UI (must be called from main thread)

        Args:
            chats: List of chat dictionaries

        Returns:
            False to not repeat this idle callback
        """
        try:
            # Clear current list
            while True:
                row = self.chat_listbox.get_row_at_index(0)
                if row is None:
                    break
                self.chat_listbox.remove(row)

            # Add chats to list and track current chat row
            current_row = None
            for chat in chats:
                row = self._create_chat_row(chat)

                # Track the current chat row
                if chat.get("is_current"):
                    current_row = row

                self.chat_listbox.append(row)

            # Select the current chat row to highlight it
            if current_row:
                self.chat_listbox.select_row(current_row)
            else:
                # If no current chat, unselect all
                self.chat_listbox.unselect_all()

            logger.debug(f"Updated UI with {len(chats)} chats")
        except Exception as e:
            logger.error(f"Failed to update chat list: {e}")

        return False  # Don't repeat this idle callback

    def _create_chat_row(self, chat: dict[str, Any]) -> Gtk.ListBoxRow:
        """
        Create a chat list row widget

        Args:
            chat: Chat dictionary with title and metadata

        Returns:
            Configured ListBoxRow widget
        """
        row = Gtk.ListBoxRow()
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=SPACING_SMALL)
        box.set_margin_start(MARGIN_SMALL)
        box.set_margin_end(MARGIN_SMALL)
        box.set_margin_top(SPACING_SMALL)
        box.set_margin_bottom(SPACING_SMALL)

        # Title label
        title = chat.get("title", "Untitled")
        if chat.get("is_current"):
            title = "→ " + title

        label = Gtk.Label(label=title)
        label.set_hexpand(True)
        label.set_halign(Gtk.Align.START)
        label.set_ellipsize(3)  # PANGO_ELLIPSIZE_END
        box.append(label)

        row.set_child(box)
        row.chat_data = chat  # Store chat data on row
        return row

    def _on_chat_selected(self, listbox: Gtk.ListBox, row: Gtk.ListBoxRow) -> None:
        """Handle chat selection"""
        if not row or not hasattr(row, "chat_data"):
            return

        chat = row.chat_data
        chat_id = chat.get("chat_id")

        if chat_id:
            logger.info(f"Switching to chat: {chat_id}")
            success = self.daemon_client.switch_chat(self.current_ai, chat_id)
            if success:
                # Clear response display to avoid showing stale content
                self.response_display.clear()
                self.status_label.set_text(f"✓ Switched to: {chat.get('title', 'chat')}")
                # Reload chat list to update current indicator
                threading.Thread(target=self._load_chats_thread, daemon=True).start()
            else:
                self.status_label.set_text("✗ Failed to switch chat")

    def _on_new_chat_clicked(self, button: Gtk.Button) -> None:
        """Handle new chat button click"""
        logger.info("Creating new chat")
        success = self.daemon_client.new_chat(self.current_ai)
        if success:
            # Clear response display for new chat
            self.response_display.clear()
            self.status_label.set_text("✓ New chat created")
            # Reload chat list
            threading.Thread(target=self._load_chats_thread, daemon=True).start()
        else:
            self.status_label.set_text("✗ Failed to create new chat")

    def _on_refresh_chats_clicked(self, button: Gtk.Button) -> None:
        """Handle refresh chats button click"""
        logger.info("Refreshing chat list")
        threading.Thread(target=self._load_chats_thread, daemon=True).start()

    def _handle_error(self, error: str) -> bool:
        """Handle error (runs on main thread)"""
        self.send_button.set_sensitive(True)
        self.status_label.set_text(f"✗ Error: {error}")
        self.response_display.set_text(f"Error: {error}")
        logger.error(f"Send error: {error}")
        return False  # Don't repeat this idle callback

    def do_close_request(self) -> bool:
        """Handle window close - stop daemon and CDP"""
        # Stop periodic refresh
        self._stop_periodic_refresh()

        logger.info("Window closing, stopping daemon and CDP...")

        # Stop the daemon (which should also stop CDP)
        try:
            result = subprocess.run(
                ["ai-cli-bridge", "daemon", "stop"],
                capture_output=True,
                text=True,
                timeout=DAEMON_STOP_TIMEOUT_S,
            )
            if result.returncode == 0:
                logger.info("✓ Daemon stopped successfully")
            else:
                logger.warning(f"Daemon stop returned non-zero: {result.stderr}")
        except subprocess.TimeoutExpired:
            logger.error(f"Daemon stop timed out after {DAEMON_STOP_TIMEOUT_S} seconds")
        except Exception as e:
            logger.error(f"Failed to stop daemon: {e}")

        return False  # Allow close
