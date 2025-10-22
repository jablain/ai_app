"""
Statistics display widget for AI session metrics.
"""

from gi.repository import Gtk, Pango
from typing import Dict, Any, Optional
import time


class StatsDisplay:
    """Sidebar widget displaying AI session statistics."""
    
    def __init__(self):
        """Initialize statistics display."""
        
        # Main container - vertical box with frame
        self.frame = Gtk.Frame()
        self.frame.set_margin_top(12)
        self.frame.set_margin_bottom(12)
        self.frame.set_margin_start(12)
        self.frame.set_margin_end(6)
        
        # Inner box with padding
        inner_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        inner_box.set_margin_top(12)
        inner_box.set_margin_bottom(12)
        inner_box.set_margin_start(12)
        inner_box.set_margin_end(12)
        
        # Title
        title_label = Gtk.Label()
        title_label.set_markup("<b>📊 Session Stats</b>")
        title_label.set_halign(Gtk.Align.START)
        inner_box.append(title_label)
        
        # Separator
        separator = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        inner_box.append(separator)
        
        # Stats labels - create them as instance variables so we can update them
        self.ai_label = self._create_stat_label("AI:", "Not connected")
        self.model_label = self._create_stat_label("Model:", "—")
        self.turn_label = self._create_stat_label("Turn:", "0")
        self.token_label = self._create_stat_label("Tokens:", "0")
        self.ctaw_label = self._create_stat_label("CTAW:", "0.00%")
        self.duration_label = self._create_stat_label("Duration:", "0s")
        self.last_label = self._create_stat_label("Last reply:", "—")
        self.elapsed_label = self._create_stat_label("Elapsed:", "—")
        
        # Add all labels to box
        inner_box.append(self.ai_label)
        inner_box.append(self.model_label)
        inner_box.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))
        inner_box.append(self.turn_label)
        inner_box.append(self.token_label)
        inner_box.append(self.ctaw_label)
        inner_box.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))
        inner_box.append(self.duration_label)
        inner_box.append(self.last_label)
        inner_box.append(self.elapsed_label)
        
        self.frame.set_child(inner_box)
        
        # Store last interaction timestamp for "X ago" calculation
        self.last_interaction_time: Optional[float] = None
    
    def _create_stat_label(self, label: str, value: str) -> Gtk.Box:
        """
        Create a label pair for displaying a stat.
        
        Args:
            label: Label text (e.g., "Turn:")
            value: Value text (e.g., "5")
            
        Returns:
            Box containing label and value
        """
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        
        # Label part (bold)
        label_widget = Gtk.Label(label=label)
        label_widget.set_halign(Gtk.Align.START)
        label_widget.set_markup(f"<b>{label}</b>")
        
        # Value part (monospace for numbers)
        value_widget = Gtk.Label(label=value)
        value_widget.set_halign(Gtk.Align.START)
        value_widget.set_hexpand(True)
        
        # Store value widget as attribute so we can update it
        setattr(box, "value_label", value_widget)
        
        box.append(label_widget)
        box.append(value_widget)
        
        return box
    
    def _update_label_value(self, label_box: Gtk.Box, value: str):
        """Update the value part of a stat label."""
        value_label = getattr(label_box, "value_label", None)
        if value_label:
            value_label.set_text(value)
    
    def update_from_status(self, status: Dict[str, Any], ai_name: str):
        """
        Update all statistics from daemon status response.
        
        Args:
            status: Status dict from daemon (for specific AI)
            ai_name: Current AI name
        """
        # AI name
        self._update_label_value(self.ai_label, ai_name.capitalize())
        
        # Model (if available in metadata - we'll add this later)
        # For now, show AI-specific model names
        model_map = {
            "claude": "Claude Sonnet 4.5",
            "chatgpt": "GPT-4",
            "gemini": "Gemini Pro"
        }
        model_name = model_map.get(ai_name.lower(), "Unknown")
        self._update_label_value(self.model_label, model_name)
        
        # Turn count
        turn_count = status.get("turn_count", 0)
        self._update_label_value(self.turn_label, str(turn_count))
        
        # Token count (with K suffix for thousands)
        token_count = status.get("token_count", 0)
        if token_count >= 1000:
            token_str = f"{token_count / 1000:.1f}K"
        else:
            token_str = str(token_count)
        self._update_label_value(self.token_label, token_str)
        
        # CTAW usage
        ctaw_percent = status.get("ctaw_usage_percent", 0.0)
        self._update_label_value(self.ctaw_label, f"{ctaw_percent:.2f}%")
        
        # Session duration
        duration_s = status.get("session_duration_s", 0)
        duration_str = self._format_duration(duration_s)
        self._update_label_value(self.duration_label, duration_str)
    
    def update_from_metadata(self, metadata: Dict[str, Any]):
        """
        Update statistics from send response metadata.
        
        Args:
            metadata: Metadata dict from send_prompt response
        """
        # Last elapsed time
        elapsed_ms = metadata.get("elapsed_ms")
        if elapsed_ms is not None:
            elapsed_str = f"{elapsed_ms / 1000:.1f}s"
            self._update_label_value(self.elapsed_label, elapsed_str)
            
            # Update last interaction timestamp
            self.last_interaction_time = time.time()
            self._update_label_value(self.last_label, "Just now")
    
    def update_last_interaction_time(self):
        """
        Update the "Last reply: X ago" label based on stored timestamp.
        Call this periodically to keep the time accurate.
        """
        if self.last_interaction_time is None:
            return
        
        elapsed = time.time() - self.last_interaction_time
        
        if elapsed < 60:
            time_str = f"{int(elapsed)}s ago"
        elif elapsed < 3600:
            time_str = f"{int(elapsed / 60)}m ago"
        else:
            time_str = f"{int(elapsed / 3600)}h ago"
        
        self._update_label_value(self.last_label, time_str)
    
    def _format_duration(self, seconds: float) -> str:
        """
        Format duration in human-readable form.
        
        Args:
            seconds: Duration in seconds
            
        Returns:
            Formatted string (e.g., "2m 15s", "1h 23m")
        """
        if seconds < 60:
            return f"{int(seconds)}s"
        elif seconds < 3600:
            minutes = int(seconds / 60)
            secs = int(seconds % 60)
            return f"{minutes}m {secs}s"
        else:
            hours = int(seconds / 3600)
            minutes = int((seconds % 3600) / 60)
            return f"{hours}h {minutes}m"
    
    def get_widget(self) -> Gtk.Frame:
        """Get the main widget for adding to window."""
        return self.frame
    
    def clear(self):
        """Reset all stats to default values."""
        self._update_label_value(self.ai_label, "Not connected")
        self._update_label_value(self.model_label, "—")
        self._update_label_value(self.turn_label, "0")
        self._update_label_value(self.token_label, "0")
        self._update_label_value(self.ctaw_label, "0.00%")
        self._update_label_value(self.duration_label, "0s")
        self._update_label_value(self.last_label, "—")
        self._update_label_value(self.elapsed_label, "—")
        self.last_interaction_time = None
