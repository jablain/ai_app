"""
Main chat window - V2.0.0 daemon-based architecture
"""
import threading
from gi.repository import Gtk, Adw, GLib, Gdk

from .daemon_client import DaemonClient
from .response_display import ResponseDisplay
from .stats_display import StatsDisplay


class ChatWindow(Adw.ApplicationWindow):
    """Main application window"""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        # Window properties
        self.set_title("AI Chat UI")
        self.set_default_size(1000, 700)
        
        # Daemon client
        self.daemon_client = DaemonClient()
        
        # Current AI name
        self.ai_name = "claude"
        
        # Build UI
        self._build_ui()
        
        # Initial stats update
        self._update_stats()
        
        # Schedule periodic stats updates (for "X ago" timestamps)
        GLib.timeout_add_seconds(10, self._periodic_stats_update)
    
    def _build_ui(self):
        """Construct the UI hierarchy"""
        
        # Main container
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        
        # Header bar
        header = Adw.HeaderBar()
        
        # AI selector in header
        self.ai_selector = Gtk.DropDown()
        string_list = Gtk.StringList()
        for ai in ["claude", "chatgpt", "gemini"]:
            string_list.append(ai)
        self.ai_selector.set_model(string_list)
        self.ai_selector.set_selected(0)  # Default to claude
        self.ai_selector.connect("notify::selected", self._on_ai_changed)
        header.pack_start(self.ai_selector)
        
        # Status label
        self.status_label = Gtk.Label(label="Ready")
        self.status_label.add_css_class("dim-label")
        header.pack_end(self.status_label)
        
        main_box.append(header)
        
        # Content area - horizontal split: stats sidebar + main area
        content_paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        content_paned.set_shrink_start_child(False)
        content_paned.set_shrink_end_child(False)
        content_paned.set_resize_start_child(False)
        content_paned.set_resize_end_child(True)
        
        # Left: Statistics sidebar
        self.stats_display = StatsDisplay()
        content_paned.set_start_child(self.stats_display.get_widget())
        
        # Right: Response and input area
        right_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        right_box.set_margin_top(12)
        right_box.set_margin_bottom(12)
        right_box.set_margin_start(6)
        right_box.set_margin_end(12)
        
        # Response display area
        response_frame = Gtk.Frame()
        self.response_display = ResponseDisplay()
        response_frame.set_child(self.response_display.get_widget())
        right_box.append(response_frame)
        
        # Separator
        separator = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        right_box.append(separator)
        
        # Prompt input area
        input_frame = Gtk.Frame()
        input_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        
        # Prompt text view
        prompt_scroll = Gtk.ScrolledWindow()
        prompt_scroll.set_min_content_height(100)
        prompt_scroll.set_vexpand(False)
        
        self.prompt_view = Gtk.TextView()
        self.prompt_view.set_wrap_mode(Gtk.WrapMode.WORD)
        self.prompt_view.set_left_margin(6)
        self.prompt_view.set_right_margin(6)
        self.prompt_view.set_top_margin(6)
        self.prompt_view.set_bottom_margin(6)
        
        # Enable Ctrl+Enter to send
        controller = Gtk.EventControllerKey()
        controller.connect("key-pressed", self._on_key_pressed)
        self.prompt_view.add_controller(controller)
        
        prompt_scroll.set_child(self.prompt_view)
        input_box.append(prompt_scroll)
        
        # Send button
        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        button_box.set_halign(Gtk.Align.END)
        button_box.set_margin_top(6)
        button_box.set_margin_bottom(6)
        button_box.set_margin_end(6)
        
        self.send_button = Gtk.Button(label="Send")
        self.send_button.add_css_class("suggested-action")
        self.send_button.connect("clicked", self._on_send_clicked)
        button_box.append(self.send_button)
        
        input_box.append(button_box)
        input_frame.set_child(input_box)
        right_box.append(input_frame)
        
        # Set proportions (response gets more space)
        response_frame.set_vexpand(True)
        input_frame.set_vexpand(False)
        
        content_paned.set_end_child(right_box)
        
        # Set initial paned position (stats sidebar width)
        content_paned.set_position(220)
        
        main_box.append(content_paned)
        
        self.set_content(main_box)
    
    def _on_ai_changed(self, dropdown, _):
        """Handle AI selection change"""
        selected = dropdown.get_selected()
        ai_list = ["claude", "chatgpt", "gemini"]
        if selected < len(ai_list):
            self.ai_name = ai_list[selected]
            self._update_stats()
            self._set_status(f"Switched to {self.ai_name}")
    
    def _on_key_pressed(self, controller, keyval, keycode, state):
        """Handle keyboard shortcuts"""
        # Ctrl+Enter to send
        if (keyval == Gdk.KEY_Return and 
            state & Gdk.ModifierType.CONTROL_MASK):
            self._on_send_clicked(None)
            return True
        return False
    
    def _on_send_clicked(self, button):
        """Handle send button click"""
        # Get prompt text
        buffer = self.prompt_view.get_buffer()
        start = buffer.get_start_iter()
        end = buffer.get_end_iter()
        prompt = buffer.get_text(start, end, False).strip()
        
        if not prompt:
            return
        
        # Disable send button during processing
        self.send_button.set_sensitive(False)
        self._set_status("Sending...")
        
        # Run in thread to avoid blocking GTK
        thread = threading.Thread(target=self._send_prompt_thread, args=(prompt,))
        thread.daemon = True
        thread.start()
    
    def _send_prompt_thread(self, prompt):
        """Thread function to send prompt via daemon"""
        try:
            # Send to daemon
            success, snippet, markdown, metadata = self.daemon_client.send_prompt(
                ai_name=self.ai_name,
                prompt=prompt,
                wait_for_response=True,
                timeout_s=120
            )
            
            if success:
                # Display response
                response_text = markdown or snippet or "(No response)"
                GLib.idle_add(self._display_response, response_text)
                
                # Update stats from metadata
                if metadata:
                    GLib.idle_add(self._update_stats_from_metadata, metadata)
                
                # Status
                elapsed = metadata.get('elapsed_ms', 0) if metadata else 0
                GLib.idle_add(self._set_status, f"Complete ({elapsed}ms)")
            else:
                error = metadata.get("error", "Unknown error") if metadata else "Unknown error"
                GLib.idle_add(self._set_status, f"Error: {error}")
                
        except Exception as e:
            GLib.idle_add(self._set_status, f"Error: {e}")
        
        finally:
            # Re-enable send button
            GLib.idle_add(self.send_button.set_sensitive, True)
    
    def _display_response(self, text):
        """Display AI response"""
        self.response_display.set_text(text)
        return False  # Don't repeat this idle callback
    
    def _set_status(self, text):
        """Update status label"""
        self.status_label.set_label(text)
        return False  # Don't repeat this idle callback
    
    def _update_stats(self):
        """Update statistics display from daemon status"""
        status = self.daemon_client.get_ai_status(self.ai_name)
        if status:
            self.stats_display.update_from_status(status, self.ai_name)
        return False  # Don't repeat if called from idle_add
    
    def _update_stats_from_metadata(self, metadata):
        """Update statistics from send response metadata"""
        self.stats_display.update_from_metadata(metadata)
        # Also refresh full status to get updated turn/token counts
        self._update_stats()
        return False  # Don't repeat this idle callback
    
    def _periodic_stats_update(self):
        """Periodic callback to update time-sensitive stats"""
        # Update "X ago" timestamp
        self.stats_display.update_last_interaction_time()
        
        # Continue periodic updates
        return True  # Keep calling this function
