# ruff: noqa: E402
"""Response display widget for showing AI responses with markdown rendering"""

from __future__ import annotations

import logging

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, GLib, Gtk

from chat_ui.markdown_parser import MarkdownParser

logger = logging.getLogger(__name__)

# UI Constants
MARGIN_SMALL = 6
MARGIN_MEDIUM = 12
COPY_FEEDBACK_TIMEOUT_S = 2


class ResponseDisplay(Gtk.Box):
    """Widget to display AI responses with markdown formatting"""

    def __init__(self) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=MARGIN_SMALL)

        # Create scrolled window
        self.scrolled_window = Gtk.ScrolledWindow()
        self.scrolled_window.set_hexpand(True)
        self.scrolled_window.set_vexpand(True)
        self.scrolled_window.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)

        # Create text view
        self.text_view = Gtk.TextView()
        self.text_view.set_editable(False)
        self.text_view.set_wrap_mode(Gtk.WrapMode.WORD)
        self.text_view.set_left_margin(MARGIN_MEDIUM)
        self.text_view.set_right_margin(MARGIN_MEDIUM)
        self.text_view.set_top_margin(MARGIN_MEDIUM)
        self.text_view.set_bottom_margin(MARGIN_MEDIUM)

        # Get buffer
        self.buffer = self.text_view.get_buffer()

        # Add text view to scrolled window
        self.scrolled_window.set_child(self.text_view)
        self.append(self.scrolled_window)

        # Create toolbar with copy button
        toolbar = self._build_toolbar()
        self.append(toolbar)

        # Create markdown parser
        self.parser = MarkdownParser(self.buffer)

    def _build_toolbar(self) -> Gtk.Box:
        """Build the toolbar with copy button"""
        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=MARGIN_SMALL)
        toolbar.set_margin_top(MARGIN_SMALL)
        toolbar.set_margin_bottom(MARGIN_SMALL)
        toolbar.set_margin_start(MARGIN_SMALL)
        toolbar.set_margin_end(MARGIN_SMALL)

        self.copy_button = Gtk.Button(label="Copy Response")
        self.copy_button.connect("clicked", self._on_copy_clicked)
        toolbar.append(self.copy_button)

        # Status label for copy feedback
        self.copy_status_label = Gtk.Label(label="")
        self.copy_status_label.set_margin_start(MARGIN_MEDIUM)
        toolbar.append(self.copy_status_label)

        return toolbar

    def set_markdown(self, markdown: str) -> None:
        """
        Display markdown response

        Args:
            markdown: Markdown text to render
        """
        # Clear existing content
        self.buffer.set_text("")

        if markdown:
            try:
                self.parser.parse_and_format(markdown)
            except Exception as e:
                logger.error(f"Failed to parse markdown: {e}")
                # Fallback to plain text
                self.buffer.set_text(markdown)

        # Auto-scroll to bottom
        self._scroll_to_bottom()

    def set_text(self, text: str) -> None:
        """
        Display plain text (for errors)

        Args:
            text: Plain text to display
        """
        self.buffer.set_text(text or "")

        # Auto-scroll to bottom
        self._scroll_to_bottom()

    def clear(self) -> None:
        """Clear the response display"""
        self.buffer.set_text("")

    def _scroll_to_bottom(self) -> None:
        """Scroll text view to bottom (common in chat UIs)"""
        end_iter = self.buffer.get_end_iter()
        self.text_view.scroll_to_iter(end_iter, 0.0, False, 0, 0)

    def _on_copy_clicked(self, button: Gtk.Button) -> None:
        """Handle copy button click"""
        # Get all text from buffer
        start = self.buffer.get_start_iter()
        end = self.buffer.get_end_iter()
        text = self.buffer.get_text(start, end, False)

        if text:
            try:
                # GTK4 clipboard API
                display = Gdk.Display.get_default()
                if not display:
                    raise RuntimeError("No default display available")

                clipboard = display.get_clipboard()
                clipboard.set(text)

                logger.info("Response copied to clipboard")

                # Show brief "Copied!" feedback
                self._show_copy_feedback()

            except Exception as e:
                logger.error(f"Failed to copy to clipboard: {e}")
                self.copy_status_label.set_text("Copy failed")
                GLib.timeout_add_seconds(COPY_FEEDBACK_TIMEOUT_S, self._clear_copy_feedback)

    def _show_copy_feedback(self) -> bool:
        """Show temporary 'Copied!' message"""
        self.copy_status_label.set_text("✓ Copied!")
        self.copy_button.set_sensitive(False)

        # Clear after timeout
        GLib.timeout_add_seconds(COPY_FEEDBACK_TIMEOUT_S, self._clear_copy_feedback)

        return False  # Don't repeat

    def _clear_copy_feedback(self) -> bool:
        """Clear copy feedback message"""
        self.copy_status_label.set_text("")
        self.copy_button.set_sensitive(True)
        return False  # Don't repeat this timeout

    def get_widget(self) -> Gtk.Widget:
        """
        Get the widget for adding to containers

        Returns:
            Self (this widget is the container)
        """
        return self
