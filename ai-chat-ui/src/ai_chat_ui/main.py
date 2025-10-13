"""
AI Chat UI - GTK4/libadwaita frontend for ai-cli-bridge
Main application entry point
"""
import sys
import gi

gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')

from gi.repository import Gtk, Adw, GLib
from .window import ChatWindow


class AIChatApplication(Adw.Application):
    """Main GTK application"""
    
    def __init__(self):
        super().__init__(
            application_id=None,
            flags=0
        )
        self.window = None
    
    def do_activate(self):
        """Called when application is activated"""
        if not self.window:
            self.window = ChatWindow(application=self)
        self.window.present()


def main():
    """Application entry point"""
    app = AIChatApplication()
    return app.run(sys.argv)


if __name__ == '__main__':
    sys.exit(main())
