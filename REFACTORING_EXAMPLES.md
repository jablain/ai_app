# Refactoring Examples - Before & After

## Example 1: Eliminating Code Duplication

### Before: Two Nearly Identical Methods (~90 lines total)

```python
def _load_chats(self):
    """Load chat list for current AI"""
    try:
        chats = self.daemon_client.list_chats(self.current_ai)
        
        # Clear current list
        while True:
            row = self.chat_listbox.get_row_at_index(0)
            if row is None:
                break
            self.chat_listbox.remove(row)
        
        # Add chats to list and track current chat row
        current_row = None
        for chat in chats:
            row = Gtk.ListBoxRow()
            box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
            box.set_margin_start(6)
            box.set_margin_end(6)
            box.set_margin_top(4)
            box.set_margin_bottom(4)
            
            # Title label
            title = chat.get("title", "Untitled")
            if chat.get("is_current"):
                title = "→ " + title
                current_row = row
            
            label = Gtk.Label(label=title)
            label.set_hexpand(True)
            label.set_halign(Gtk.Align.START)
            label.set_ellipsize(3)
            box.append(label)
            
            row.set_child(box)
            row.chat_data = chat
            self.chat_listbox.append(row)
        
        # Select the current chat row
        if current_row:
            self.chat_listbox.select_row(current_row)
        else:
            self.chat_listbox.unselect_all()
            
        logger.debug(f"Loaded {len(chats)} chats")
    except Exception as e:
        logger.error(f"Failed to load chats: {e}")

def _update_chat_list(self, chats):
    """Update chat list in UI"""
    try:
        # Clear current list
        while True:
            row = self.chat_listbox.get_row_at_index(0)
            if row is None:
                break
            self.chat_listbox.remove(row)
        
        # Add chats to list and track current chat row
        current_row = None
        for chat in chats:
            row = Gtk.ListBoxRow()
            box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
            box.set_margin_start(6)
            box.set_margin_end(6)
            box.set_margin_top(4)
            box.set_margin_bottom(4)
            
            # Title label
            title = chat.get("title", "Untitled")
            if chat.get("is_current"):
                title = "→ " + title
                current_row = row
            
            label = Gtk.Label(label=title)
            label.set_hexpand(True)
            label.set_halign(Gtk.Align.START)
            label.set_ellipsize(3)
            box.append(label)
            
            row.set_child(box)
            row.chat_data = chat
            self.chat_listbox.append(row)
        
        # Select the current chat row
        if current_row:
            self.chat_listbox.select_row(current_row)
        else:
            self.chat_listbox.unselect_all()
            
        logger.debug(f"Updated UI with {len(chats)} chats")
    except Exception as e:
        logger.error(f"Failed to update chat list: {e}")
    
    return False
```

### After: DRY Code with Helper Method (~50 lines total)

```python
def _update_chat_list(self, chats: list[dict[str, Any]]) -> bool:
    """
    Update chat list in UI (must be called from main thread)
    
    Args:
        chats: List of chat dictionaries
        
    Returns:
        False to not repeat this idle callback
    """
    try:
        # Clear current list
        while True:
            row = self.chat_listbox.get_row_at_index(0)
            if row is None:
                break
            self.chat_listbox.remove(row)

        # Add chats to list and track current chat row
        current_row = None
        for chat in chats:
            row = self._create_chat_row(chat)
            
            # Track the current chat row
            if chat.get("is_current"):
                current_row = row
            
            self.chat_listbox.append(row)

        # Select the current chat row to highlight it
        if current_row:
            self.chat_listbox.select_row(current_row)
        else:
            self.chat_listbox.unselect_all()

        logger.debug(f"Updated UI with {len(chats)} chats")
    except Exception as e:
        logger.error(f"Failed to update chat list: {e}")

    return False

def _create_chat_row(self, chat: dict[str, Any]) -> Gtk.ListBoxRow:
    """
    Create a chat list row widget
    
    Args:
        chat: Chat dictionary with title and metadata
        
    Returns:
        Configured ListBoxRow widget
    """
    row = Gtk.ListBoxRow()
    box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=SPACING_SMALL)
    box.set_margin_start(MARGIN_SMALL)
    box.set_margin_end(MARGIN_SMALL)
    box.set_margin_top(SPACING_SMALL)
    box.set_margin_bottom(SPACING_SMALL)

    # Title label
    title = chat.get("title", "Untitled")
    if chat.get("is_current"):
        title = "→ " + title

    label = Gtk.Label(label=title)
    label.set_hexpand(True)
    label.set_halign(Gtk.Align.START)
    label.set_ellipsize(3)  # PANGO_ELLIPSIZE_END
    box.append(label)

    row.set_child(box)
    row.chat_data = chat
    return row
```

**Improvements:**
- Removed duplicate `_load_chats()` method
- Extracted row creation into reusable `_create_chat_row()` helper
- Used named constants instead of magic numbers
- Added comprehensive type hints
- Added detailed docstrings
- Reduced code by 44%

---

## Example 2: Extracting Magic Numbers to Constants

### Before: Magic Numbers Scattered Throughout

```python
def _build_ui(self):
    # Margins and spacing hardcoded everywhere
    content_box.set_margin_top(12)
    content_box.set_margin_bottom(12)
    content_box.set_margin_start(12)
    content_box.set_margin_end(12)
    
    chat_sidebar.set_size_request(200, -1)
    self.stats_display.set_size_request(250, -1)
    
    scroll.set_size_request(-1, 80)
    
    self.input_view.set_left_margin(6)
    self.input_view.set_right_margin(6)

def _start_periodic_refresh(self):
    self._refresh_timeout_id = GLib.timeout_add_seconds(3, refresh_callback)

def _send_message_thread(self, prompt: str):
    response = self.daemon_client.send_prompt(
        ai=self.current_ai, 
        prompt=prompt,
        wait_for_response=True, 
        timeout_s=120
    )

def do_close_request(self):
    result = subprocess.run(
        ["ai-cli-bridge", "daemon", "stop"],
        capture_output=True,
        text=True,
        timeout=10
    )
```

### After: Named Constants with Clear Intent

```python
# UI Constants
SIDEBAR_WIDTH = 200
STATS_PANEL_WIDTH = 250
INPUT_HEIGHT = 80
MARGIN_SMALL = 6
MARGIN_MEDIUM = 12
SPACING_SMALL = 4
SPACING_MEDIUM = 6

# Timeout Constants (seconds)
REFRESH_INTERVAL_S = 3
SEND_TIMEOUT_S = 120
DAEMON_STOP_TIMEOUT_S = 10

def _build_ui(self):
    # Clear, self-documenting code
    content_box.set_margin_top(MARGIN_MEDIUM)
    content_box.set_margin_bottom(MARGIN_MEDIUM)
    content_box.set_margin_start(MARGIN_MEDIUM)
    content_box.set_margin_end(MARGIN_MEDIUM)
    
    chat_sidebar.set_size_request(SIDEBAR_WIDTH, -1)
    self.stats_display.set_size_request(STATS_PANEL_WIDTH, -1)
    
    scroll.set_size_request(-1, INPUT_HEIGHT)
    
    self.input_view.set_left_margin(MARGIN_SMALL)
    self.input_view.set_right_margin(MARGIN_SMALL)

def _start_periodic_refresh(self):
    self._refresh_timeout_id = GLib.timeout_add_seconds(
        REFRESH_INTERVAL_S, 
        refresh_callback
    )

def _send_message_thread(self, prompt: str):
    response = self.daemon_client.send_prompt(
        ai=self.current_ai, 
        prompt=prompt,
        wait_for_response=True, 
        timeout_s=SEND_TIMEOUT_S
    )

def do_close_request(self):
    result = subprocess.run(
        ["ai-cli-bridge", "daemon", "stop"],
        capture_output=True,
        text=True,
        timeout=DAEMON_STOP_TIMEOUT_S
    )
```

**Improvements:**
- All magic numbers replaced with descriptive constants
- Easy to modify timeouts and dimensions from one location
- Self-documenting code
- Consistent naming convention

---

## Example 3: Breaking Down Large Method

### Before: Monolithic 110-line _build_ui() Method

```python
def _build_ui(self):
    """Build the GTK4 interface"""
    # Main layout
    main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

    # Header bar with AI selector
    header = Gtk.HeaderBar()
    self.ai_model = Gtk.StringList()
    self.ai_selector = Gtk.DropDown(model=self.ai_model)
    self.ai_selector.connect("notify::selected", self._on_ai_changed)
    header.pack_start(self.ai_selector)
    self.set_titlebar(header)

    # Content area (chat list + response + stats)
    content_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
    content_box.set_margin_top(12)
    content_box.set_margin_bottom(12)
    # ... 50+ more lines of UI building ...
    
    # Input area
    input_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
    # ... 30+ more lines ...
    
    # Status bar
    self.status_label = Gtk.Label(label="Ready")
    # ... more setup ...
    
    self.set_child(main_box)
    self.input_view.grab_focus()
```

### After: Organized into Focused Helper Methods

```python
def _build_ui(self) -> None:
    """Build the GTK4 interface"""
    main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

    # Header bar with AI selector
    self._build_header_bar()

    # Content area (chat list + response + stats)
    content_box = self._build_content_area()
    main_box.append(content_box)

    # Input area
    input_box = self._build_input_area()
    main_box.append(input_box)

    # Status bar
    self.status_label = self._build_status_bar()
    main_box.append(self.status_label)

    self.set_child(main_box)
    self.input_view.grab_focus()

def _build_header_bar(self) -> None:
    """Build header bar with AI selector"""
    # Focused implementation

def _build_content_area(self) -> Gtk.Box:
    """Build the main content area with chat list, response display, and stats"""
    # Focused implementation

def _build_chat_sidebar(self) -> Gtk.Box:
    """Build the chat list sidebar with header and list"""
    # Focused implementation

def _build_chat_header(self) -> Gtk.Box:
    """Build the chat header with label and buttons"""
    # Focused implementation

def _build_input_area(self) -> Gtk.Box:
    """Build the input text area with send button"""
    # Focused implementation

def _build_status_bar(self) -> Gtk.Label:
    """Build the status bar at the bottom"""
    # Focused implementation
```

**Improvements:**
- Single Responsibility Principle - each method has one job
- Easier to test individual components
- Easier to understand and maintain
- Reusable building blocks
- Clear hierarchy and organization

---

## Example 4: Adding Comprehensive Type Hints

### Before: Minimal Type Information

```python
def _on_ai_changed(self, dropdown, _param):
    """Handle AI selection change"""
    idx = self.ai_selector.get_selected()
    if idx < 0:
        return
    ai = self.ai_model.get_string(idx)
    # ...

def _extract_ai_fields(self, ai_json: dict) -> dict:
    """Extract fields from AI status JSON"""
    # ...

def _render_stats(self, fields: dict, daemon_info: dict, ai_status: dict):
    """Render stats to display"""
    # ...
```

### After: Complete Type Coverage

```python
def _on_ai_changed(self, dropdown: Gtk.DropDown, _param: Any) -> None:
    """Handle AI selection change"""
    idx = self.ai_selector.get_selected()
    if idx < 0:
        return
    ai = self.ai_model.get_string(idx)
    # ...

def _extract_ai_fields(self, ai_json: dict[str, Any]) -> dict[str, Any]:
    """
    Extract fields from AI status JSON with robust fallbacks

    Args:
        ai_json: AI status dict from daemon

    Returns:
        Dict with normalized field names and values
    """
    # ...

def _render_stats(
    self, 
    fields: dict[str, Any], 
    daemon_info: dict[str, Any], 
    ai_status: dict[str, Any]
) -> bool:
    """
    Render stats to display (runs on main thread)

    Args:
        fields: Extracted AI fields
        daemon_info: Daemon info dict
        ai_status: Full AI status dict from daemon

    Returns:
        False to not repeat this idle callback
    """
    # ...
```

**Improvements:**
- Complete type coverage for better IDE support
- Catch type errors at development time
- Self-documenting parameter types
- Modern Python 3.10+ syntax
- Comprehensive docstrings with Args/Returns sections

---

## Summary

These refactorings demonstrate:
1. **DRY Principle** - Don't Repeat Yourself
2. **Single Responsibility** - One method, one job
3. **Named Constants** - Self-documenting code
4. **Type Safety** - Catch errors early
5. **Documentation** - Clear intent and usage

The result is cleaner, more maintainable, and more professional code that's easier to work with and extend.
