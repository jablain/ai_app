"""
AI Chat UI - Main application entry point
V2.0.0 - Daemon-based architecture with startup management
Compatible with libadwaita 1.0 (GNOME 42)
"""
import sys
import gi

# IMPORTANT: Require GTK versions BEFORE importing
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')

from gi.repository import Gtk, Adw, GLib

from .daemon_client import DaemonClient
from .startup_manager import StartupManager
from .window import ChatWindow


class StartupDialog(Gtk.Window):
    """Simple startup status window (libadwaita 1.0 compatible)"""
    
    def __init__(self):
        super().__init__()
        self.set_title("AI Chat UI")
        self.set_default_size(400, 150)
        self.set_resizable(False)
        
        # Main box
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_top(24)
        box.set_margin_bottom(24)
        box.set_margin_start(24)
        box.set_margin_end(24)
        
        # Title
        title = Gtk.Label()
        title.set_markup("<b>Starting AI Chat UI</b>")
        box.append(title)
        
        # Status label
        self.status_label = Gtk.Label(label="Checking daemon status...")
        box.append(self.status_label)
        
        # Spinner
        self.spinner = Gtk.Spinner()
        self.spinner.start()
        box.append(self.spinner)
        
        # Cancel button
        cancel_button = Gtk.Button(label="Cancel")
        cancel_button.connect("clicked", lambda b: self.close())
        box.append(cancel_button)
        
        self.set_child(box)
    
    def set_status(self, text):
        """Update status text"""
        self.status_label.set_text(text)


class ErrorDialog(Gtk.Window):
    """Simple error dialog (libadwaita 1.0 compatible)"""
    
    def __init__(self, title, message, on_close_callback):
        super().__init__()
        self.set_title(title)
        self.set_default_size(400, 200)
        self.set_resizable(False)
        self.on_close_callback = on_close_callback
        
        # Main box
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_top(24)
        box.set_margin_bottom(24)
        box.set_margin_start(24)
        box.set_margin_end(24)
        
        # Title
        title_label = Gtk.Label()
        title_label.set_markup(f"<b>{title}</b>")
        box.append(title_label)
        
        # Message
        message_label = Gtk.Label(label=message)
        message_label.set_wrap(True)
        message_label.set_max_width_chars(50)
        box.append(message_label)
        
        # Exit button
        exit_button = Gtk.Button(label="Exit")
        exit_button.connect("clicked", self._on_exit_clicked)
        box.append(exit_button)
        
        self.set_child(box)
    
    def _on_exit_clicked(self, button):
        """Handle exit button click"""
        self.close()
        if self.on_close_callback:
            self.on_close_callback()


class AIChatApplication(Adw.Application):
    """Main GTK application"""
    
    def __init__(self):
        super().__init__(
            application_id=None,
            flags=0
        )
        self.window = None
        self.startup_complete = False
    
    def do_activate(self):
        """Called when application is activated"""
        if not self.window:
            # Show startup sequence first
            self._run_startup_sequence()
        else:
            self.window.present()
    
    def _run_startup_sequence(self):
        """
        Run startup sequence:
        1. Check daemon
        2. If down, check CDP
        3. If CDP down, launch it
        4. Start daemon
        5. Verify everything ready
        6. Show main window
        """
        # Create startup dialog
        self.startup_dialog = StartupDialog()
        self.startup_dialog.set_application(self)  # CRITICAL: Keep app alive
        self.startup_dialog.present()
        
        # Run startup in background thread
        import threading
        thread = threading.Thread(target=self._startup_thread)
        thread.daemon = True
        thread.start()
    
    def _startup_thread(self):
        """Background thread for startup sequence"""
        daemon_client = DaemonClient()
        startup_manager = StartupManager(daemon_client)
        
        # Update dialog status
        GLib.idle_add(self._update_startup_status, "Checking daemon...")
        
        # Run startup sequence
        success, message = startup_manager.ensure_ready()
        
        if success:
            GLib.idle_add(self._startup_success)
        else:
            GLib.idle_add(self._startup_failed, message)
    
    def _update_startup_status(self, status_text):
        """Update startup dialog status"""
        if hasattr(self, 'startup_dialog') and self.startup_dialog:
            self.startup_dialog.set_status(status_text)
        return False
    
    def _startup_success(self):
        """Handle successful startup"""
        self.startup_complete = True
        
        # Close startup dialog
        if hasattr(self, 'startup_dialog') and self.startup_dialog:
            self.startup_dialog.close()
        
        # Create and show main window
        self.window = ChatWindow(application=self)
        self.window.present()
        
        return False
    
    def _startup_failed(self, error_message):
        """Handle startup failure"""
        # Close startup dialog
        if hasattr(self, 'startup_dialog') and self.startup_dialog:
            self.startup_dialog.close()
        
        # Show error dialog
        error_dialog = ErrorDialog(
            "Startup Failed",
            error_message,
            on_close_callback=lambda: self.quit()
        )
        error_dialog.set_application(self)  # CRITICAL: Keep app alive
        error_dialog.present()
        
        return False


def main():
    """Application entry point"""
    app = AIChatApplication()
    return app.run(sys.argv)


if __name__ == '__main__':
    sys.exit(main())
