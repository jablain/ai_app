# AI Chat UI

GTK4/libadwaita graphical interface for ai-cli-bridge.

## Features

- ✅ Native GNOME integration (GTK4 + libadwaita)
- ✅ AI-agnostic interface (works with Claude, ChatGPT, Gemini)
- ✅ Large prompt support (paste megabytes from clipboard)
- ✅ Large response handling (efficient scrolling)
- ✅ Basic markdown formatting (bold, italic, code, headers, lists)
- ✅ Copy to clipboard button
- ✅ Keyboard shortcuts (Ctrl+Enter to send)

## Requirements

### System Dependencies (already on your Pop!_OS)
- Python 3.10+
- GTK4
- libadwaita
- PyGObject

Verify installation:
```bash
python3 -c "import gi; gi.require_version('Gtk', '4.0'); gi.require_version('Adw', '1'); from gi.repository import Gtk, Adw; print('✓ GTK4 + libadwaita ready')"
```

### Python Dependencies
- `pygobject` (GTK bindings)
- `ai-cli-bridge` (installed separately)

## Installation

### 1. Create project directory
```bash
mkdir -p ~/projects/ai-chat-ui
cd ~/projects/ai-chat-ui
```

### 2. Create the package structure
```
ai-chat-ui/
├── ai_chat_ui/
│   ├── __init__.py
│   ├── main.py
│   ├── window.py
│   ├── response_display.py
│   └── markdown_parser.py
├── pyproject.toml
└── README.md
```

Copy the provided files into this structure.

### 3. Install in editable mode
```bash
# Activate ai-cli-bridge venv or create new one
source ~/.ai_cli_bridge/venv/bin/activate

# Install ai-chat-ui
pip install -e ~/projects/ai-chat-ui
```

## Usage

### 1. Start CDP browser (Claude)
```bash
# Launch browser with remote debugging
chromium --remote-debugging-port=9223 \
  --user-data-dir=~/.ai_cli_bridge/data/profiles/claude \
  https://claude.ai
```

Authenticate manually if needed.

### 2. Launch UI
```bash
ai-chat-ui
```

### 3. Using the interface

**Send a prompt:**
1. Select AI from dropdown (default: Claude)
2. Type or paste prompt in bottom text area
3. Click "Send" or press Ctrl+Enter

**Copy response:**
- Click the copy button (📋) below the response area

**Keyboard shortcuts:**
- `Ctrl+Enter` - Send prompt
- `Ctrl+V` - Paste into prompt area (handles large pastes)

## Architecture

### Component Overview

```
AIChatApplication (Adw.Application)
    └── ChatWindow (Adw.ApplicationWindow)
        ├── HeaderBar (AI selector, status)
        ├── ResponseDisplay (formatted output + copy button)
        │   ├── TextView (with TextTags)
        │   └── MarkdownParser (basic formatting)
        └── Prompt Input (TextView + Send button)
```

### Markdown Support (Phase 1)

Supported formatting:
- `**bold**` → **Bold text**
- `*italic*` → *Italic text*
- `` `code` `` → `Monospace inline code`
- ` ```code block``` ` → Monospace block with background
- `# Header` → Large bold text
- `- List item` → Bulleted lists

### Integration with ai-cli-bridge

The UI imports `AIFactory` directly:
```python
from ai_cli_bridge.ai.factory import AIFactory

# Get available AIs
ai_list = AIFactory.list_available()

# Create AI instance
ai_class = AIFactory.get_class("claude")
config = ai_class.get_default_config()
ai = AIFactory.create("claude", config)

# Send prompt
success, snippet, markdown, metadata = await ai.send_prompt(message)
```

## Future Enhancements (Phase 2)

- Full markdown rendering with WebKitGTK
- Conversation history navigation
- Multiple conversation tabs
- File upload support
- Image extraction from responses
- Custom themes
- Message export

## Troubleshooting

### "ai-cli-bridge not found"
Ensure ai-cli-bridge is installed in the same venv:
```bash
pip install -e /path/to/ai-cli-bridge
```

### "Connection failed"
1. Verify CDP browser is running with `--remote-debugging-port=9223`
2. Check: `ai-cli-bridge status claude`

### UI not launching
Verify GTK4 dependencies:
```bash
python3 -c "from gi.repository import Gtk, Adw"
```

## Development

### Running from source
```bash
cd ~/projects/ai-chat-ui
python -m ai_chat_ui.main
```

### Debug mode
Add debug output to ai-cli-bridge operations:
```python
self.current_ai.set_debug(True)
```

## License

MIT (or match ai-cli-bridge license)
