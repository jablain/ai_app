"""
Main chat window with prompt input and response display
Fixed for libadwaita 1.0 compatibility (GNOME 42) and proper async handling
Includes automatic CDP browser launch
"""
import asyncio
import threading
import subprocess
import time
from pathlib import Path
from gi.repository import Gtk, Adw, GLib, Gdk

# Import ai-cli-bridge components
try:
    from ai_cli_bridge.ai.factory import AIFactory
except ImportError:
    print("Warning: ai-cli-bridge not found. Install with: pip install -e /path/to/ai-cli-bridge")
    AIFactory = None

from .response_display import ResponseDisplay


class ChatWindow(Adw.ApplicationWindow):
    """Main application window"""
    
    def __init__(self, **kwargs):
        print("ChatWindow.__init__ called")  # ADD THIS LINE
        super().__init__(**kwargs)
     
        # Window properties
        self.set_title("AI Chat")
        self.set_default_size(800, 600)
    
        # Current AI instance
        self.current_ai = None
        self.ai_name = "claude"  # Default
    
        # Track if we launched CDP (so we know whether to close it)
        self.cdp_launched_by_us = False
    
        # Build UI
        self._build_ui()
    
        # Connect close signal
        self.connect("close-request", self._on_window_close)
    
        # Connect realize signal - called when window fully shown
        self.connect("realize", lambda w: GLib.idle_add(self._check_cdp_and_init))
        
    def _build_ui(self):
        """Construct the UI hierarchy"""
        
        # Main container
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        
        # Header bar
        header = Adw.HeaderBar()
        
        # AI selector in header
        self.ai_selector = Gtk.DropDown()
        if AIFactory:
            ai_list = AIFactory.list_available()
            string_list = Gtk.StringList()
            for ai in ai_list:
                string_list.append(ai)
            self.ai_selector.set_model(string_list)
            self.ai_selector.connect("notify::selected", self._on_ai_changed)
        header.pack_start(self.ai_selector)
        
        # Status label
        self.status_label = Gtk.Label(label="Ready")
        self.status_label.add_css_class("dim-label")
        header.pack_end(self.status_label)
        
        # Add header to main box
        main_box.append(header)
        
        # Content area - split into response and input
        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        content_box.set_margin_top(12)
        content_box.set_margin_bottom(12)
        content_box.set_margin_start(12)
        content_box.set_margin_end(12)
        
        # Response display area
        response_frame = Gtk.Frame()
        self.response_display = ResponseDisplay()
        response_frame.set_child(self.response_display.get_widget())
        content_box.append(response_frame)
        
        # Separator
        separator = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        content_box.append(separator)
        
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
        content_box.append(input_frame)
        
        # Set proportions (response gets 60%, input gets 40%)
        response_frame.set_vexpand(True)
        input_frame.set_vexpand(False)
        
        main_box.append(content_box)
        
        self.set_content(main_box)
    
    def _init_ai(self):
        """Initialize the AI instance"""
        if not AIFactory:
            self._set_status("Error: ai-cli-bridge not available")
            return
        
        try:
            ai_class = AIFactory.get_class(self.ai_name)
            config = ai_class.get_default_config()
            self.current_ai = AIFactory.create(self.ai_name, config)
            self._set_status(f"Ready - {self.ai_name}")
        except Exception as e:
            self._set_status(f"Error: {e}")
    
    def _on_ai_changed(self, dropdown, _):
        """Handle AI selection change"""
        selected = dropdown.get_selected()
        if AIFactory:
            ai_list = AIFactory.list_available()
            if selected < len(ai_list):
                self.ai_name = ai_list[selected]
                self._init_ai()
    
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
        
        if not self.current_ai:
            self._set_status("Error: No AI initialized")
            return
        
        # Disable send button during processing
        self.send_button.set_sensitive(False)
        self._set_status("Sending...")
        
        # Run async operation in a thread to avoid blocking GTK
        thread = threading.Thread(target=self._send_prompt_thread, args=(prompt,))
        thread.daemon = True
        thread.start()
    
    def _send_prompt_thread(self, prompt):
        """Thread function to run async prompt sending"""
        # Create new event loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # Run the async operation
            loop.run_until_complete(self._send_prompt_async(prompt))
        finally:
            loop.close()
    
    async def _send_prompt_async(self, prompt):
        """Send prompt to AI and display response"""
        try:
            # Call ai-cli-bridge
            success, snippet, markdown, metadata = await self.current_ai.send_prompt(
                prompt,
                wait_for_response=True,
                timeout_s=120
            )
            
            if success:
                # Display response (use GLib.idle_add for thread safety)
                GLib.idle_add(self._display_response, markdown or snippet)
                elapsed = metadata.get('elapsed_ms', 0)
                GLib.idle_add(self._set_status, f"Complete ({elapsed}ms)")
            else:
                GLib.idle_add(self._set_status, "Error: Send failed")
                
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
    
    def _close_cdp_browser(self):
        """Close CDP browser gracefully"""
        import urllib.request
        import json
        
        try:
            # Get list of browser targets
            response = urllib.request.urlopen('http://127.0.0.1:9223/json', timeout=2)
            targets = json.loads(response.read().decode())
            
            # Find the browser target and close it
            for target in targets:
                if target.get('type') == 'page':
                    target_id = target.get('id')
                    close_url = f"http://127.0.0.1:9223/json/close/{target_id}"
                    try:
                        urllib.request.urlopen(close_url, timeout=1)
                    except:
                        pass
            
            # Give browser time to close gracefully
            time.sleep(0.5)
            
        except Exception as e:
            print(f"Note: Could not close CDP browser gracefully: {e}")
    
    def _on_window_close(self, window):
        """Handle window close event"""
        if self.cdp_launched_by_us and self._check_cdp_running():
            # We launched CDP, so close it
            thread = threading.Thread(target=self._close_cdp_browser)
            thread.daemon = True
            thread.start()
            
            # Small delay to allow closing
            time.sleep(0.3)
        
        return False  # Allow window to close
    
    def _check_cdp_running(self):
        """Check if CDP is accessible on port 9223"""
        import urllib.request
        try:
            urllib.request.urlopen('http://127.0.0.1:9223/json', timeout=1)
            return True
        except:
            return False
    
    def _launch_cdp_browser(self):
        """Attempt to launch CDP browser using launch_cdp.sh"""
        # Find launch script
        script_paths = [
            Path.home() / "dev/ai_app/shared/scripts/launch_cdp.sh",
            Path.home() / "dev/ai_app/launch_cdp.sh",
        ]
        
        launch_script = None
        for path in script_paths:
            if path.exists():
                launch_script = path
                break
        
        if not launch_script:
            return False, "launch_cdp.sh not found"
        
        try:
            # Launch script in background
            subprocess.Popen(
                [str(launch_script)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True
            )
            
            # Wait up to 15 seconds for CDP to become available
            for i in range(15):
                time.sleep(1)
                if self._check_cdp_running():
                    return True, "CDP browser launched successfully"
            
            return False, "CDP browser launched but not responding"
            
        except Exception as e:
            return False, f"Failed to launch: {e}"
    
    def _check_cdp_and_init(self):
        """Check CDP status and launch if needed, then initialize AI"""
        print("_check_cdp_and_init CALLED")  # ADD THIS LINE
        self._set_status("Checking CDP browser...")
        
        if self._check_cdp_running():
            # CDP already running (not launched by us)
            self._set_status("CDP browser connected")
            self.cdp_launched_by_us = False
            self._init_ai()
            return False
        
        # CDP not running, try to launch
        self._set_status("CDP browser not running, launching...")
        self.cdp_launched_by_us = True  # Mark that we launched it
        
        # Run launch in thread to avoid blocking UI
        thread = threading.Thread(target=self._launch_cdp_thread)
        thread.daemon = True
        thread.start()
        
        return False
    
    def _launch_cdp_thread(self):
        """Thread function to launch CDP"""
        success, message = self._launch_cdp_browser()
        
        if success:
            GLib.idle_add(self._set_status, "CDP browser ready")
            GLib.idle_add(self._init_ai)
        else:
            GLib.idle_add(self._show_cdp_error, message)
    
    def _show_cdp_error(self, message):
        """Show error dialog for CDP failure"""
        dialog = Adw.MessageDialog.new(
            self,
            "CDP Browser Not Available",
            message
        )
        dialog.add_response("ok", "OK")
        dialog.set_default_response("ok")
        dialog.set_close_response("ok")
        
        # Add details
        dialog.set_body(
            f"{message}\n\n"
            "Please launch the CDP browser manually:\n"
            "~/dev/ai_app/shared/scripts/launch_cdp.sh"
        )
        
        dialog.present()
        self._set_status("Error: CDP browser not available")
        return False
