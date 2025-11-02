# ruff: noqa: E402
"""Stats display widget for showing AI and token information"""

import gi

gi.require_version("Gtk", "4.0")
from typing import Any

from gi.repository import Gtk

from chat_ui import stats_helper


class StatsDisplay(Gtk.Box):
    """Widget to display AI statistics and token usage"""

    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.set_margin_top(6)
        self.set_margin_bottom(6)
        self.set_margin_start(6)
        self.set_margin_end(6)

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

        Args:
            metadata: Response metadata dictionary from daemon
        """
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
            self.usage_label.set_text(f"Usage: {usage_pct:.1f}%")
        else:
            self.usage_label.set_text("Usage: -")

    def clear(self):
        """Clear all stats to default values"""
        self.ai_label.set_text("AI: -")
        self.model_label.set_text("Model: -")
        self.turn_label.set_text("Turn: -")
        self.tokens_label.set_markup("<span font_family='monospace'>Tokens: -</span>")
        self.context_label.set_text("Context: -")
        self.usage_label.set_text("Usage: -")

    def get_widget(self) -> Gtk.Widget:
        """
        Get the widget for adding to containers

        Returns:
            Self (this widget is the container)
        """
        return self
