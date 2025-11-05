# ruff: noqa: E402
"""Stats display widget for showing AI and token information"""

import logging

import gi

gi.require_version("Gtk", "4.0")
from typing import Any

from gi.repository import Gtk

from chat_ui import stats_helper

logger = logging.getLogger(__name__)


class StatsDisplay(Gtk.Box):
    """Widget to display AI statistics and token usage"""

    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.set_margin_top(6)
        self.set_margin_bottom(6)
        self.set_margin_start(6)
        self.set_margin_end(6)

        # Store performance metrics persistently (don't clear on status refresh)
        self._last_response_ms: int | None = None
        self._avg_response_ms: float | None = None
        self._tokens_per_sec: float | None = None
        self._avg_tokens_per_sec: float | None = None

        # Store context warning thresholds (updated from daemon config)
        self._yellow_threshold: int = 70
        self._orange_threshold: int = 85
        self._red_threshold: int = 95

        # Add title
        title = Gtk.Label()
        title.set_markup("<b>Statistics</b>")
        title.set_halign(Gtk.Align.START)
        self.append(title)

        # Add separator
        separator = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        self.append(separator)

        # Create stat labels
        self._create_labels()

        # Initialize with empty values
        self.clear()

    def _create_labels(self):
        """Create all stat labels"""
        # AI info
        self.ai_label = self._create_stat_label("AI: -", selectable=True)
        self.model_label = self._create_stat_label("Model: -", selectable=True)

        # Add separator
        separator = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        self.append(separator)

        # Message stats
        self.turn_label = self._create_stat_label("Turn: -", selectable=True)

        # Token stats (monospace for better alignment)
        self.tokens_label = self._create_stat_label("Tokens: -", selectable=True, monospace=True)

        # Context stats
        self.context_label = self._create_stat_label("Context: -", selectable=True)
        self.usage_label = self._create_stat_label("Usage: -", selectable=True)
        self.usage_label.set_use_markup(True)  # Enable markup for color-coded warnings

        # Add separator for performance metrics
        separator2 = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        self.append(separator2)

        # Performance section title
        perf_title = Gtk.Label()
        perf_title.set_markup("<b>Performance</b>")
        perf_title.set_halign(Gtk.Align.START)
        self.append(perf_title)

        # Response timing
        self.last_response_label = self._create_stat_label("Last Response: -", selectable=True)
        self.avg_response_label = self._create_stat_label("Avg Response: -", selectable=True)

        # Token velocity
        self.tokens_per_sec_label = self._create_stat_label("Tokens/sec: -", selectable=True)
        self.avg_tokens_per_sec_label = self._create_stat_label(
            "Avg Tokens/sec: -", selectable=True
        )

        # Session duration
        self.session_duration_label = self._create_stat_label("Session: -", selectable=True)

    def _create_stat_label(
        self, text: str, selectable: bool = False, monospace: bool = False
    ) -> Gtk.Label:
        """
        Helper to create a stat label

        Args:
            text: Initial label text
            selectable: Whether text can be selected/copied
            monospace: Whether to use monospace font
        """
        label = Gtk.Label(label=text)
        label.set_halign(Gtk.Align.START)
        label.set_wrap(True)
        label.set_xalign(0)  # Left align text
        label.set_selectable(selectable)

        if monospace:
            # Use Pango markup for monospace font
            label.set_use_markup(True)

        self.append(label)
        return label

    def update_ai_info(self, ai_name: str, model: str | None = None):
        """
        Update AI and model display

        Args:
            ai_name: Name of the AI (e.g., 'claude', 'chatgpt')
            model: Model name if available
        """
        self.ai_label.set_text(f"AI: {ai_name}")

        if model:
            self.model_label.set_text(f"Model: {model}")
        else:
            # Fallback to known models
            model_map = {
                "claude": "Claude Sonnet 4.5",
                "chatgpt": "GPT-4",
                "gemini": "Gemini Pro",
            }
            fallback = model_map.get(ai_name.lower(), "Unknown")
            self.model_label.set_text(f"Model: {fallback}")

    def update_from_metadata(self, metadata: dict[str, Any]):
        """
        Update stats from response metadata (tolerant parsing)

        This method updates session stats (turn, tokens, context) and
        optionally updates performance metrics if present in metadata.

        Args:
            metadata: Response metadata dictionary from daemon
        """
        # Update context warning thresholds from AI-specific config (if present)
        if "context_warning" in metadata:
            warning_config = metadata["context_warning"]
            yellow = warning_config.get("yellow_threshold", 70)
            orange = warning_config.get("orange_threshold", 85)
            red = warning_config.get("red_threshold", 95)
            self.set_context_warning_thresholds(yellow, orange, red)
            logger.debug(f"Updated context warning thresholds: Y={yellow}, O={orange}, R={red}")
        
        # Turn count (use helper for tolerance)
        turn_count = stats_helper.extract_turn_count(metadata)
        self.turn_label.set_text(f"Turn: {turn_count}")

        # Token counts (use helpers for tolerance)
        total_tokens = stats_helper.extract_total_tokens(metadata)
        prompt_tokens = stats_helper.extract_prompt_tokens(metadata)
        completion_tokens = stats_helper.extract_completion_tokens(metadata)

        # Format with thousands separators and monospace for alignment
        token_text = (
            f"<span font_family='monospace'>"
            f"Tokens: {total_tokens:,}\n"
            f"  Prompt: {prompt_tokens:>8,}\n"
            f"  Compl.: {completion_tokens:>8,}"
            f"</span>"
        )
        self.tokens_label.set_markup(token_text)

        # Context window (optional field, use helper)
        context_window = stats_helper.extract_context_window(metadata)
        if context_window:
            self.context_label.set_text(f"Context: {context_window:,}")
        else:
            self.context_label.set_text("Context: -")

        # Context usage percentage (optional, use helper)
        usage_pct = stats_helper.extract_context_usage_percent(metadata)
        if usage_pct is not None:
            self._update_usage_with_warning(usage_pct)
        else:
            self.usage_label.set_text("Usage: -")

        # Session duration (always update if present)
        session_duration_s = stats_helper.extract_session_duration_s(metadata)
        if session_duration_s is not None:
            if session_duration_s >= 3600:
                hours = int(session_duration_s // 3600)
                minutes = int((session_duration_s % 3600) // 60)
                self.session_duration_label.set_text(f"Session: {hours}h {minutes}m")
            elif session_duration_s >= 60:
                minutes = int(session_duration_s // 60)
                seconds = int(session_duration_s % 60)
                self.session_duration_label.set_text(f"Session: {minutes}m {seconds}s")
            else:
                self.session_duration_label.set_text(f"Session: {session_duration_s:.0f}s")
        else:
            self.session_duration_label.set_text("Session: -")

        # Performance metrics: Only update if present in metadata (sticky behavior)
        # This allows status refreshes to update session stats without clearing performance
        self._update_performance_if_present(metadata)

    def _update_performance_if_present(self, metadata: dict[str, Any]):
        """
        Update performance metrics only if they're present in metadata.
        This makes them "sticky" - they persist across status refreshes.

        Args:
            metadata: Response metadata dictionary
        """
        # Last response time
        last_response_ms = stats_helper.extract_last_response_time_ms(metadata)
        if last_response_ms is not None:
            self._last_response_ms = last_response_ms

        # Average response time
        avg_response_ms = stats_helper.extract_avg_response_time_ms(metadata)
        if avg_response_ms is not None:
            self._avg_response_ms = avg_response_ms

        # Tokens per second (current)
        tokens_per_sec = stats_helper.extract_tokens_per_sec(metadata)
        if tokens_per_sec is not None:
            self._tokens_per_sec = tokens_per_sec

        # Average tokens per second
        avg_tokens_per_sec = stats_helper.extract_avg_tokens_per_sec(metadata)
        if avg_tokens_per_sec is not None:
            self._avg_tokens_per_sec = avg_tokens_per_sec

        # Update labels with stored values
        self._render_performance_metrics()

    def _render_performance_metrics(self):
        """Render performance metrics from stored values."""
        # Last response time
        if self._last_response_ms is not None:
            if self._last_response_ms >= 1000:
                self.last_response_label.set_text(
                    f"Last Response: {self._last_response_ms / 1000:.1f}s"
                )
            else:
                self.last_response_label.set_text(f"Last Response: {self._last_response_ms}ms")
        else:
            self.last_response_label.set_text("Last Response: -")

        # Average response time
        if self._avg_response_ms is not None:
            if self._avg_response_ms >= 1000:
                self.avg_response_label.set_text(
                    f"Avg Response: {self._avg_response_ms / 1000:.1f}s"
                )
            else:
                self.avg_response_label.set_text(f"Avg Response: {self._avg_response_ms:.0f}ms")
        else:
            self.avg_response_label.set_text("Avg Response: -")

        # Tokens per second (current)
        if self._tokens_per_sec is not None:
            self.tokens_per_sec_label.set_text(f"Tokens/sec: {self._tokens_per_sec:.1f}")
        else:
            self.tokens_per_sec_label.set_text("Tokens/sec: -")

        # Average tokens per second
        if self._avg_tokens_per_sec is not None:
            self.avg_tokens_per_sec_label.set_text(
                f"Avg Tokens/sec: {self._avg_tokens_per_sec:.1f}"
            )
        else:
            self.avg_tokens_per_sec_label.set_text("Avg Tokens/sec: -")

    def set_context_warning_thresholds(self, yellow: int = 70, orange: int = 85, red: int = 95):
        """
        Update context warning thresholds from daemon config.

        Args:
            yellow: Yellow warning threshold (default 70%)
            orange: Orange warning threshold (default 85%)
            red: Red warning threshold (default 95%)
        """
        self._yellow_threshold = yellow
        self._orange_threshold = orange
        self._red_threshold = red

    def _update_usage_with_warning(self, usage_pct: float):
        """
        Update context usage label with color-coded warning.

        Args:
            usage_pct: Context usage percentage (0-100)
        """
        logger.debug(
            f"Context usage: {usage_pct:.1f}% (thresholds: Y={self._yellow_threshold}, "
            f"O={self._orange_threshold}, R={self._red_threshold})"
        )

        # Determine color and warning level based on stored thresholds
        if usage_pct >= self._red_threshold:
            color = "red"
            icon = "⚠️"
            severity = "CRITICAL"
        elif usage_pct >= self._orange_threshold:
            color = "orange"
            icon = "⚠️"
            severity = "HIGH"
        elif usage_pct >= self._yellow_threshold:
            color = "#FFA500"  # Orange color for yellow threshold
            icon = "⚠️"
            severity = "WARNING"
        else:
            # Below warning threshold - show green with checkmark
            color = "green"
            icon = "✓"
            severity = "OK"

        # Apply color markup
        markup = f'<span foreground="{color}">{icon} Usage: {usage_pct:.1f}% ({severity})</span>'
        logger.debug(f"Applying markup: {markup}")
        self.usage_label.set_markup(markup)

    def clear(self):
        """Clear all stats to default values"""
        self.ai_label.set_text("AI: -")
        self.model_label.set_text("Model: -")
        self.turn_label.set_text("Turn: -")
        self.tokens_label.set_markup("<span font_family='monospace'>Tokens: -</span>")
        self.context_label.set_text("Context: -")
        self.usage_label.set_text("Usage: -")
        self.session_duration_label.set_text("Session: -")

        # Clear performance metrics
        self._last_response_ms = None
        self._avg_response_ms = None
        self._tokens_per_sec = None
        self._avg_tokens_per_sec = None
        self._render_performance_metrics()

    def get_widget(self) -> Gtk.Widget:
        """
        Get the widget for adding to containers

        Returns:
            Self (this widget is the container)
        """
        return self
