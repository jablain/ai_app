# AI Chat UI V2.0.0

GTK4/libadwaita graphical interface for ai-cli-bridge V2.0.0 daemon.

## What's New in V2.0.0

- 🔄 **Daemon Architecture** - Persistent AI sessions via HTTP API
- 📊 **Live Statistics** - Real-time token tracking, CTAW usage, session metrics
- 🚀 **Auto-Startup** - Automatically launches CDP browser and daemon
- 🎯 **Multi-AI Support** - Switch between Claude, ChatGPT, and Gemini
- ⚡ **Improved Performance** - No browser restarts, persistent sessions

## Features

- ✅ Native GNOME integration (GTK4 + libadwaita)
- ✅ AI-agnostic interface (works with Claude, ChatGPT, Gemini)
- ✅ Large prompt support (paste megabytes from clipboard)
- ✅ Large response handling (efficient scrolling)
- ✅ Basic markdown formatting (bold, italic, code, headers, lists)
- ✅ Copy to clipboard button
- ✅ Keyboard shortcuts (Ctrl+Enter to send)
- ✅ Real-time statistics sidebar
- ✅ Automatic CDP and daemon management

## Architecture
```
┌─────────────────────────────────────────────────┐
│  AI Chat UI (GTK4)                              │
│  ├─ Startup Manager (CDP/Daemon launcher)      │
│  ├─ Daemon Client (HTTP API)                   │
│  ├─ Stats Display (metrics sidebar)            │
│  └─ Main Window (chat interface)               │
└─────────────────┬───────────────────────────────┘
                  │ HTTP (localhost:8000)
┌─────────────────▼───────────────────────────────┐
│  ai-cli-bridge Daemon                           │
│  ├─ Persistent AI Instances                     │
│  ├─ Token Tracking                              │
│  └─ Session State Management                    │
└─────────────────┬───────────────────────────────┘
                  │ CDP (localhost:9223)
┌─────────────────▼───────────────────────────────┐
│  CDP Browser (Chromium)                         │
│  └─ Claude.ai / ChatGPT / Gemini                │
└─────────────────────────────────────────────────┘
```

## Requirements

### System Dependencies (Pop!_OS 22.04)
- Python 3.10+
- GTK4
- libadwaita
- PyGObject

Verify installation:
```bash
python3 -c "import gi; gi.require_version('Gtk', '4.0'); gi.require_version('Adw', '1'); from gi.repository import Gtk, Adw; print('✓ GTK4 + libadwaita ready')"
```

### Python Dependencies
- `requests>=2.31.0` (HTTP client for daemon API)

### External Requirements
- `ai-cli-bridge` CLI tool installed and in PATH
- LaunchCDP.sh script at: `~/dev/ai_app/ai-cli-bridge/LaunchCDP.sh`

## Installation

### 1. Ensure ai-cli-bridge is installed
```bash
# Activate shared venv
source ~/dev/ai_app/shared/scripts/activate.sh

# Verify ai-cli-bridge is available
which ai-cli-bridge
# Should show: /home/your-user/dev/ai_app/shared/runtime/venv/bin/ai-cli-bridge
```

### 2. Install ai-chat-ui
```bash
# Navigate to source directory
cd ~/dev/ai_app/ai_chat_ui/src

# Install in editable mode
pip install -e .

# Verify installation
which ai_chat_ui
# Should show: /home/your-user/dev/ai_app/shared/runtime/venv/bin/ai_chat_ui
```

## Usage

### Quick Start
```bash
# Activate venv
source ~/dev/ai_app/shared/scripts/activate.sh

# Launch UI (handles CDP and daemon startup automatically)
ai_chat_ui
```

The UI will:
1. Check if daemon is running
2. If not, check if CDP browser is running
3. If not, launch CDP browser via LaunchCDP.sh
4. Start the daemon
5. Open the main window

### Manual Startup (if needed)

If automatic startup fails, you can start components manually:
```bash
# 1. Start CDP browser
~/dev/ai_app/ai-cli-bridge/LaunchCDP.sh

# 2. Start daemon
ai-cli-bridge daemon start

# 3. Launch UI
ai_chat_ui
```

### Using the Interface

**Send a prompt:**
1. Select AI from dropdown (Claude, ChatGPT, or Gemini)
2. Type or paste prompt in bottom text area
3. Click "Send" or press Ctrl+Enter

**View statistics:**
- Turn count - Number of interactions in this session
- Tokens - Estimated token usage
- CTAW - Context window usage percentage
- Duration - Session duration
- Last reply - Time since last AI response
- Elapsed - Time taken for last response

**Copy response:**
- Click the copy button (📋) below the response area

**Switch AI:**
- Use the dropdown in the header bar
- Stats will update to show the selected AI's state

**Keyboard shortcuts:**
- `Ctrl+Enter` - Send prompt
- `Ctrl+V` - Paste into prompt area

## Project Structure
```
~/dev/ai_app/ai_chat_ui/
├── runtime/                    # Runtime data (created automatically)
│   ├── logs/
│   └── state/
└── src/                        # Source code
    ├── pyproject.toml         # Project configuration
    ├── README.md              # This file
    └── ai_chat_ui/            # Python package
        ├── __init__.py
        ├── main.py            # Application entry point
        ├── window.py          # Main window
        ├── startup_manager.py # CDP/Daemon launcher
        ├── daemon_client.py   # HTTP API client
        ├── stats_display.py   # Statistics sidebar
        ├── response_display.py # Response area
        └── markdown_parser.py  # Markdown formatting
```

## Configuration

The UI inherits configuration from ai-cli-bridge:
- CDP port: 9223 (default)
- Daemon API: http://127.0.0.1:8000
- AI configurations: `~/.ai_cli_bridge/config/`

## Troubleshooting

### "CDP browser not found"
Ensure LaunchCDP.sh exists:
```bash
ls -la ~/dev/ai_app/ai-cli-bridge/LaunchCDP.sh
```

### "Daemon failed to start"
Check daemon logs:
```bash
tail -f ~/dev/ai_app/ai-cli-bridge/runtime/logs/daemon.log
```

### "Cannot connect to daemon"
Verify daemon is running:
```bash
ai-cli-bridge daemon status
```

### UI doesn't launch
Check GTK4 dependencies:
```bash
python3 -c "from gi.repository import Gtk, Adw"
```

## Development

### Running from source
```bash
cd ~/dev/ai_app/ai_chat_ui/src
python -m ai_chat_ui.main
```

### Debug mode
Set environment variable:
```bash
GTK_DEBUG=interactive ai_chat_ui
```

## Differences from V1.3.1

| Feature | V1.3.1 | V2.0.0 |
|---------|--------|--------|
| Architecture | Direct AI instances | Daemon-based HTTP API |
| Browser Management | Manual CDP launch | Automatic startup |
| Statistics | None | Real-time sidebar |
| Session Persistence | No | Yes (via daemon) |
| Token Tracking | No | Yes |
| Multi-AI Switching | Requires restart | Instant |

## License

MIT (or match ai-cli-bridge license)

## Version History

### V2.0.0 (2025-10-20)
- Complete rewrite for daemon architecture
- Added statistics sidebar
- Automatic CDP/daemon startup
- Persistent AI sessions
- Real-time token tracking

### V1.3.1 (2024)
- Initial release
- Direct AI instance management
- Basic markdown support
