"""
Response display widget with markdown formatting support
"""
from gi.repository import Gtk, Gdk, Pango
from .markdown_parser import MarkdownParser

class ResponseDisplay:
    """TextView with markdown formatting and copy button"""
    
    def __init__(self):
        # Main container
        self.container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        
        # Scrolled text view
        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        scroll.set_min_content_height(200)
        
        self.text_view = Gtk.TextView()
        self.text_view.set_editable(False)
        self.text_view.set_wrap_mode(Gtk.WrapMode.WORD)
        self.text_view.set_left_margin(12)
        self.text_view.set_right_margin(12)
        self.text_view.set_top_margin(12)
        self.text_view.set_bottom_margin(12)
        
        self.buffer = self.text_view.get_buffer()
        
        # Setup text tags for formatting
        self._setup_tags()
        
        scroll.set_child(self.text_view)
        self.container.append(scroll)
        
        # Action bar with copy button
        action_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        action_bar.set_margin_top(6)
        action_bar.set_margin_bottom(6)
        action_bar.set_margin_end(6)
        action_bar.set_halign(Gtk.Align.END)
        
        copy_button = Gtk.Button()
        copy_button.set_icon_name("edit-copy-symbolic")
        copy_button.set_tooltip_text("Copy response to clipboard")
        copy_button.connect("clicked", self._on_copy_clicked)
        action_bar.append(copy_button)
        
        self.container.append(action_bar)
        
        # Markdown parser
        self.parser = MarkdownParser(self.buffer)
    
    def _setup_tags(self):
        """Create TextTags for markdown formatting"""
        tag_table = self.buffer.get_tag_table()
        
        # Bold
        bold_tag = self.buffer.create_tag("bold")
        bold_tag.set_property("weight", Pango.Weight.BOLD)
        
        # Italic
        italic_tag = self.buffer.create_tag("italic")
        italic_tag.set_property("style", Pango.Style.ITALIC)
        
        # Inline code
        code_tag = self.buffer.create_tag("code")
        code_tag.set_property("family", "monospace")
        code_tag.set_property("background", "#f0f0f0")
        code_tag.set_property("foreground", "#333333")
        
        # Code block
        code_block_tag = self.buffer.create_tag("code-block")
        code_block_tag.set_property("family", "monospace")
        code_block_tag.set_property("background", "#f5f5f5")
        code_block_tag.set_property("left-margin", 20)
        code_block_tag.set_property("right-margin", 20)
        code_block_tag.set_property("pixels-above-lines", 4)
        code_block_tag.set_property("pixels-below-lines", 4)
        
        # Header 1
        h1_tag = self.buffer.create_tag("h1")
        h1_tag.set_property("weight", Pango.Weight.BOLD)
        h1_tag.set_property("scale", 1.5)
        h1_tag.set_property("pixels-above-lines", 10)
        h1_tag.set_property("pixels-below-lines", 5)
        
        # Header 2
        h2_tag = self.buffer.create_tag("h2")
        h2_tag.set_property("weight", Pango.Weight.BOLD)
        h2_tag.set_property("scale", 1.3)
        h2_tag.set_property("pixels-above-lines", 8)
        h2_tag.set_property("pixels-below-lines", 4)
        
        # Header 3
        h3_tag = self.buffer.create_tag("h3")
        h3_tag.set_property("weight", Pango.Weight.BOLD)
        h3_tag.set_property("scale", 1.1)
        h3_tag.set_property("pixels-above-lines", 6)
        h3_tag.set_property("pixels-below-lines", 3)
        
        # List item
        list_tag = self.buffer.create_tag("list")
        list_tag.set_property("left-margin", 20)
    
    def set_text(self, text):
        """Set and format text content"""
        self.buffer.set_text("")  # Clear existing
        self.parser.parse_and_format(text)
    
    def get_text(self):
        """Get plain text content"""
        start = self.buffer.get_start_iter()
        end = self.buffer.get_end_iter()
        return self.buffer.get_text(start, end, False)
    
    def get_widget(self):
        """Get the container widget"""
        return self.container
    
    def _on_copy_clicked(self, button):
        """Copy response text to clipboard"""
        text = self.get_text()
        if text:
            clipboard = Gdk.Display.get_default().get_clipboard()
            clipboard.set(text)
