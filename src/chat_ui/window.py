# ruff: noqa: E402
"""Main window for AI Chat UI"""

import logging
import threading

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GLib

from chat_ui.cli_wrapper import CLIWrapper, SendResponse
from chat_ui.response_display import ResponseDisplay
from chat_ui.stats_display import StatsDisplay
from chat_ui import stats_helper

logger = logging.getLogger(__name__)


class ChatWindow(Gtk.ApplicationWindow):
    """Main application window for AI Chat"""

    def __init__(self, application, daemon_client: CLIWrapper):
        super().__init__(application=application)
        self.daemon_client = daemon_client
        self.current_ai = "claude"  # Default AI
        self._refresh_timeout_id = None
        self._ai_change_guard = False  # Prevent double-refresh on AI change

        self.set_title("AI Chat")
        self.set_default_size(1000, 700)

        # Build UI
        self._build_ui()

        # Load available AIs dynamically
        self._load_available_ais()

        # Initial stats refresh (in background)
        threading.Thread(target=self._refresh_status_thread, daemon=True).start()

        # Start periodic refresh (every 3 seconds)
        self._start_periodic_refresh()

    def _build_ui(self):
        """Build the GTK4 interface"""
        # Main layout
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        # Header bar with AI selector
        header = Gtk.HeaderBar()

        # AI selector (GTK4 DropDown with StringList)
        self.ai_model = Gtk.StringList()
        self.ai_selector = Gtk.DropDown(model=self.ai_model)
        self.ai_selector.connect("notify::selected", self._on_ai_changed)
        header.pack_start(self.ai_selector)

        self.set_titlebar(header)

        # Content area (response + stats)
        content_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        content_box.set_margin_top(12)
        content_box.set_margin_bottom(12)
        content_box.set_margin_start(12)
        content_box.set_margin_end(12)

        # Response display
        self.response_display = ResponseDisplay()
        self.response_display.set_hexpand(True)
        content_box.append(self.response_display.get_widget())

        # Stats display
        self.stats_display = StatsDisplay()
        self.stats_display.set_size_request(250, -1)
        content_box.append(self.stats_display.get_widget())

        main_box.append(content_box)

        # Input area
        input_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        input_box.set_margin_top(0)
        input_box.set_margin_bottom(12)
        input_box.set_margin_start(12)
        input_box.set_margin_end(12)

        # Input text view in scrolled window
        scroll = Gtk.ScrolledWindow()
        scroll.set_size_request(-1, 80)
        scroll.set_hexpand(True)
        scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)

        self.input_view = Gtk.TextView()
        self.input_view.set_wrap_mode(Gtk.WrapMode.WORD)
        self.input_view.set_left_margin(6)
        self.input_view.set_right_margin(6)
        self.input_view.set_top_margin(6)
        self.input_view.set_bottom_margin(6)
        scroll.set_child(self.input_view)
        input_box.append(scroll)

        # Send button
        self.send_button = Gtk.Button(label="Send")
        self.send_button.connect("clicked", self._on_send_clicked)
        self.send_button.set_valign(Gtk.Align.END)
        input_box.append(self.send_button)

        main_box.append(input_box)

        # Status bar
        self.status_label = Gtk.Label(label="Ready")
        self.status_label.set_halign(Gtk.Align.START)
        self.status_label.set_margin_start(12)
        self.status_label.set_margin_bottom(6)
        main_box.append(self.status_label)

        self.set_child(main_box)

    def _load_available_ais(self):
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

    def _on_ai_changed(self, dropdown, _param):
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
            # Refresh stats for new AI (in background)
            threading.Thread(target=self._refresh_status_thread, daemon=True).start()

    def _extract_ai_fields(self, ai_json: dict) -> dict:
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

    def _refresh_status_thread(self):
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

            # Render stats on main thread
            GLib.idle_add(self._render_stats, fields, daemon_info)

        except Exception as e:
            logger.exception("Error refreshing status")
            GLib.idle_add(self._render_status_error, str(e))

    def _render_stats(self, fields: dict, daemon_info: dict):
        """
        Render stats to display (runs on main thread)

        Args:
            fields: Extracted AI fields
            daemon_info: Daemon info dict
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
            "sent_tokens": fields["tokens_sent"],
            "response_tokens": fields["tokens_response"],
            "ctaw_size": fields["ctw"],
            "ctaw_usage_percent": fields["ctw_used_pct"],
            "session_duration_s": fields["session_s"],
        }

        self.stats_display.update_from_metadata(metadata)

        logger.debug(
            f"Stats updated for {self.current_ai}: {fields['turns']} turns, {fields['tokens_total']} tokens"
        )

        return False  # Don't repeat this idle callback

    def _render_ai_unavailable(self, daemon_info: dict):
        """Render unavailable state (runs on main thread)"""
        self.status_label.set_text(f"{self.current_ai} not available")
        self.stats_display.clear()
        logger.warning(f"AI {self.current_ai} not found in daemon status")

        return False  # Don't repeat

    def _render_status_error(self, error: str):
        """Render error state (runs on main thread)"""
        self.status_label.set_text(f"Status error: {error}")
        logger.error(f"Status refresh error: {error}")

        return False  # Don't repeat

    def _start_periodic_refresh(self):
        """Start periodic status refresh (every 3 seconds)"""

        def refresh_callback():
            # GTK4-correct visibility check
            if self.get_visible():
                threading.Thread(target=self._refresh_status_thread, daemon=True).start()
            return True  # Continue repeating

        self._refresh_timeout_id = GLib.timeout_add_seconds(3, refresh_callback)
        logger.debug("Started periodic status refresh (3s interval)")

    def _stop_periodic_refresh(self):
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

    def _clear_input(self):
        """Clear input text view"""
        buffer = self.input_view.get_buffer()
        buffer.set_text("")

    def _on_send_clicked(self, button):
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

    def _send_message_thread(self, prompt: str):
        """Background thread to send message (don't block UI)"""
        try:
            response = self.daemon_client.send_prompt(
                ai=self.current_ai, prompt=prompt, wait_for_response=True, timeout_s=120
            )

            # Update UI on main thread
            GLib.idle_add(self._handle_response, response)

        except Exception as e:
            logger.exception("Error in send thread")
            GLib.idle_add(self._handle_error, str(e))

    def _handle_response(self, response: SendResponse):
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
            if response.metadata:
                elapsed_ms = stats_helper.extract_elapsed_ms(response.metadata)
                if elapsed_ms:
                    self.status_label.set_text(f"✓ Complete ({elapsed_ms}ms)")
                else:
                    self.status_label.set_text("✓ Complete")
            else:
                self.status_label.set_text("✓ Complete")
        else:
            # Show error
            error_msg = response.error or "Unknown error"
            self.status_label.set_text(f"✗ {error_msg}")
            self.response_display.set_text(f"Error: {error_msg}")
            logger.error(f"Response error: {error_msg}")

        return False  # Don't repeat this idle callback

    def _handle_error(self, error: str):
        """Handle error (runs on main thread)"""
        self.send_button.set_sensitive(True)
        self.status_label.set_text(f"✗ Error: {error}")
        self.response_display.set_text(f"Error: {error}")
        logger.error(f"Send error: {error}")

        return False  # Don't repeat this idle callback

    def do_close_request(self):
        """Handle window close - stop daemon and CDP"""
        # Stop periodic refresh
        self._stop_periodic_refresh()
        
        logger.info("Window closing, stopping daemon and CDP...")
        
        # Stop the daemon (which should also stop CDP)
        try:
            import subprocess
            result = subprocess.run(
                ["ai-cli-bridge", "daemon", "stop"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                logger.info("✓ Daemon stopped successfully")
            else:
                logger.warning(f"Daemon stop returned non-zero: {result.stderr}")
        except subprocess.TimeoutExpired:
            logger.error("Daemon stop timed out after 10 seconds")
        except Exception as e:
            logger.error(f"Failed to stop daemon: {e}")
        
        return False  # Allow close