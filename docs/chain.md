
# AI App Project - Complete Context Summary

## Project Overview

**ai_app** is a unified Python-based AI automation toolset with CLI and GUI interfaces for browser-based AI services (Claude, ChatGPT, Gemini). The project uses Playwright with Chrome DevTools Protocol (CDP) to automate web-based AI interactions without requiring API keys.

---

## Project Structure

```
~/dev/ai_app/                           # Project root (Git repository)
├── ai-cli-bridge/                      # CLI automation tool
│   ├── src/                            # Python source (git tracked)
│   │   ├── ai_cli_bridge/
│   │   │   ├── ai/                     # AI abstraction layer
│   │   │   │   ├── base.py            # BaseAI abstract class
│   │   │   │   ├── factory.py         # AIFactory for instantiation
│   │   │   │   ├── claude.py          # ClaudeAI (FULLY IMPLEMENTED)
│   │   │   │   ├── chatgpt.py         # ChatGPTAI (STUB)
│   │   │   │   └── gemini.py          # GeminiAI (STUB)
│   │   │   ├── commands/              # CLI command modules
│   │   │   │   ├── send_cmd.py        # Send prompt command
│   │   │   │   ├── status_cmd.py      # Connection status
│   │   │   │   └── ...
│   │   │   ├── cli.py                 # Typer CLI entry point
│   │   │   └── ...
│   │   └── pyproject.toml
│   └── runtime/                        # Runtime data (git ignored)
│       └── profiles/main/              # Browser profile (cookies, sessions)
│
├── ai-chat-ui/                         # GTK4 GUI interface
│   ├── src/                            # Python source (git tracked)
│   │   ├── ai_chat_ui/
│   │   │   ├── main.py                # Adw.Application entry
│   │   │   ├── window.py              # Main window with auto-CDP launch
│   │   │   ├── response_display.py   # TextView with markdown tags
│   │   │   └── markdown_parser.py     # Basic markdown formatter
│   │   └── pyproject.toml
│   ├── desktop/                        # Desktop integration (git tracked)
│   │   ├── ai-chat-ui.desktop         # GNOME app launcher entry
│   │   └── ai-chat-ui.svg             # Application icon
│   └── runtime/                        # Runtime data (git ignored)
│
├── shared/
│   ├── scripts/                        # Utility scripts (git tracked)
│   │   ├── launch_cdp.sh              # Launch Playwright Chromium with CDP
│   │   ├── launch-ui.sh               # Wrapper: activate venv + launch UI
│   │   └── activate.sh                # Quick venv activation helper
│   └── runtime/
│       └── venv/                       # Shared Python virtual environment
│
├── .gitignore                          # Ignores all */runtime/ directories
├── README.md                           # Complete documentation
└── setup scripts...
```

---

## Architecture

### **Design Pattern: Strategy Pattern with Factory**

```
AIFactory
  ├── get_class(ai_name) → AI class
  ├── create(ai_name, config) → AI instance
  └── list_available() → ["claude", "chatgpt", "gemini"]

BaseAI (Abstract)
  ├── Public interface (abstract methods)
  │   ├── send_prompt(message) → (success, snippet, markdown, metadata)
  │   ├── list_messages() → list[dict]              # NOT IMPLEMENTED
  │   ├── extract_message(index) → str              # NOT IMPLEMENTED
  │   └── get_status() → dict
  │
  ├── Common implementation
  │   ├── _discover_cdp_url() → (ws_url, source)
  │   └── _pick_page(remote, base_url) → Page
  │
  └── AI-specific abstract methods (must implement)
      ├── _wait_for_response_complete(page, timeout)
      ├── _extract_response(page, baseline_count)
      └── _ensure_chat_ready(page)

ClaudeAI(BaseAI)  # ✅ FULLY IMPLEMENTED
  - CDP Port: 9223 (custom, not default 9222)
  - Completion detection: Button-state watching
  - Response extraction: .font-claude-response selector
  - Converts HTML → markdown using markdownify

ChatGPTAI(BaseAI)  # ⚠️ STUB - raises NotImplementedError
GeminiAI(BaseAI)   # ⚠️ STUB - raises NotImplementedError
```

---

## Key Technologies

### **Browser Automation**

- **Playwright 1.48.0**: Python library for browser automation
- **CDP (Chrome DevTools Protocol)**: Port 9223 for remote debugging
- **Profile**: `~/dev/ai_app/ai-cli-bridge/runtime/profiles/main/`
- **Browser**: Playwright's Chromium (downloaded via `playwright install chromium`)

### **Why CDP Instead of Direct Playwright?**

- **Bot detection bypass**: Manual authentication in CDP browser avoids automation detection
- **Session persistence**: Browser profile saves cookies, chat history (IndexedDB)
- **Manual launch required**: User starts browser with `--remote-debugging-port=9223`
- **Playwright connects**: Via `connect_over_cdp(ws://127.0.0.1:9223/...)`

### **GUI Framework**

- **GTK4 + libadwaita**: Native GNOME toolkit (already on Pop!_OS)
- **PyGObject**: Python bindings to GTK (system package, not pip)
- **Async handling**: Threading + asyncio bridge for non-blocking UI

---

## Current Implementation Status

### **ai-cli-bridge (CLI)**

**Working:**

- ✅ `status claude` - Shows CDP connection status
- ✅ `send claude "prompt"` - Sends prompt, extracts response
- ✅ `--json` flag - Machine-readable output
- ✅ `--debug` flag - Verbose logging
- ✅ Claude integration via CDP (selectors, timing, extraction)
- ✅ Markdown conversion (HTML → markdown)

**Not Implemented:**

- ❌ `list` command - List all messages in conversation
- ❌ `extract` command - Extract specific message by index
- ❌ `list_messages()` method in ClaudeAI
- ❌ `extract_message(index)` method in ClaudeAI
- ❌ ChatGPT automation
- ❌ Gemini automation

### **ai-chat-ui (GUI)**

**Working:**

- ✅ GTK4/libadwaita native GNOME interface
- ✅ Auto-launch CDP browser if not running
- ✅ Auto-close CDP on exit (if UI launched it)
- ✅ Send prompts via UI (Ctrl+Enter or button)
- ✅ Display responses with basic markdown formatting
- ✅ Copy response to clipboard (📋 button)
- ✅ AI selector dropdown (currently only Claude works)
- ✅ Status bar with connection/operation feedback
- ✅ Desktop launcher integration (pinnable to dock)

**Basic Markdown Support (Phase 1):**

- `**bold**`, `*italic*`, `` `code` ``
- Code blocks (`...`)
- Headers (#, ##, ###)
- Lists (- item)
- Uses GTK TextTags for formatting

**Not Implemented:**

- ❌ Message history panel
- ❌ Context management (token counter, turn counter)
- ❌ Auto-inject governance/contexts
- ❌ Session monitoring (context %, warnings)
- ❌ `!align`, `!summarize` buttons
- ❌ Phase 2: Full markdown with WebKitGTK (tables, images, syntax highlighting)

---

## Critical Implementation Details

### **ClaudeAI Response Detection**

**Method: Button-State Watching**

python

```python
# Phase 1: Wait for stop button (response started)
await page.wait_for_selector(STOP_BUTTON, timeout=RESPONSE_WAIT_S)

# Phase 2: Wait for disabled send button with send icon (response complete)
while True:
    disabled = await page.query_selector(SEND_BUTTON_DISABLED)
    if disabled:
        icon = await disabled.query_selector(SEND_ICON_PATH)
        if icon:
            await asyncio.sleep(BUTTON_STABILITY_MS / 1000)
            # Verify still disabled - if yes, response complete
            break
```

**Rationale:** More reliable than spinner detection; works for instant/cached responses.

### **Response Extraction**

**Selector:** `.font-claude-response:has(.standard-markdown)`

- Filters out UI badges (like "Sonnet 4.5")
- Waits for count > baseline_count (ensures NEW response)
- Strips UI chrome via JavaScript
- Converts HTML → markdown using `markdownify`

**Snippet Creation:** 280 chars, smart word-boundary trimming

### **CDP Discovery**

python

```python
def _discover_cdp_url():
    # Try port 9223 first (ClaudeAI custom)
    response = requests.get('http://127.0.0.1:9223/json')
    targets = response.json()
    # Find browser target
    return ws_url, "discovered"
```

### **GTK4 Async Integration**

**Problem:** GTK uses GLib event loop, asyncio uses its own loop

**Solution:**

python

```python
def _on_send_clicked(self):
    thread = threading.Thread(target=self._send_prompt_thread, args=(prompt,))
    thread.start()

def _send_prompt_thread(self, prompt):
    loop = asyncio.new_event_loop()
    loop.run_until_complete(self._send_prompt_async(prompt))
    loop.close()

async def _send_prompt_async(self, prompt):
    result = await self.current_ai.send_prompt(prompt)
    GLib.idle_add(self._display_response, result)  # Back to GTK thread
```

---

## Installation & Setup

### **System Prerequisites**

bash

```bash
# Ubuntu/Pop!_OS/Debian
sudo apt install python3 python3-pip python3-venv python3-gi gir1.2-gtk-4.0 gir1.2-adw-1
```

### **Setup Process**

bash

```bash
git clone https://github.com/jablain/ai_app.git ~/dev/ai_app
cd ~/dev/ai_app
./setup_structure.sh                    # Create directories
./setup_venv.sh                         # Create venv, install packages
mv *.sh shared/scripts/                 # Move scripts
source shared/scripts/activate.sh
playwright install chromium             # Download browser
cp ai-chat-ui/desktop/* ~/.local/share/...  # Install desktop entry/icon
```

### **First Use**

bash

```bash
ai-chat-ui                              # Launches UI + CDP browser
# Navigate to claude.ai, log in manually (one time)
# Close browser properly (Ctrl+Q)
# Future launches: auto-logged in
```

---

## Current Workflow

### **Daily Use**

bash

```bash
# Option 1: GUI
ai-chat-ui                              # Auto-launches CDP if needed

# Option 2: CLI
source ~/dev/ai_app/shared/scripts/activate.sh
ai-cli-bridge send claude "your prompt"
```

### **CDP Browser Management**

- **Manual launch:** `~/dev/ai_app/shared/scripts/launch_cdp.sh`
- **Auto-launch:** UI detects if CDP not running, launches automatically
- **Auto-close:** UI closes CDP on exit (if UI launched it)
- **Session persistence:** Browser saves login, cookies, chat history

---

## Known Issues & Limitations

### **Bot Detection Workaround**

**Problem:** Playwright's `launch_persistent_context()` exposes automation markers **Solution:** Launch Chromium manually with CDP, authenticate manually, Playwright connects after auth

### **Profile Paths**

- Hard-coded to `~/dev/ai_app/` - if cloned elsewhere, paths need adjustment
- `launch_cdp.sh` uses absolute paths (no ~) to work from GNOME launcher

### **Single AI Profile**

- One browser profile shared by all AIs (Claude, ChatGPT, Gemini tabs)
- CDP port 9223 shared
- Tab routing handled by Playwright (finds correct tab by URL)

### **Config Files Eliminated**

- Old approach required `~/.ai_cli_bridge/config/*.json`
- New approach: Each AI class has `get_default_config()` class method
- Self-contained, no external config files

---

## Development Context

### **User Information**

- **Name:** Jacques
- **Location:** Brossard, Quebec, Canada
- **System:** Pop!_OS 22.04 LTS, GNOME 42.9, Wayland
- **Python:** 3.10.12
- **Development style:** Software architect, prefers clean OOP patterns

### **Project Evolution**

1. Started with monolithic `send_cmd.py` (~600 lines, Claude-specific)
2. Refactored to OOP with Strategy pattern (~85 lines, AI-agnostic)
3. Added GTK4 GUI with auto-launch/close
4. Unified project structure under `~/dev/ai_app/`
5. Git repository: [https://github.com/jablain/ai_app](https://github.com/jablain/ai_app)

### **Design Decisions**

- **No config files:** Self-contained AI classes
- **Shared venv:** Both CLI and GUI use same virtual environment
- **Editable installs:** `pip install -e` - changes reflect immediately
- **Git ignores runtime:** Only source code tracked, not user data
- **CDP manual launch:** Avoids bot detection, session persistence works

---

## Immediate Next Steps (Planned)

### **Priority 1: Message Block Extraction**

- Implement `list_messages()` in ClaudeAI
- Implement `extract_message(index)` in ClaudeAI
- Add CLI commands: `list` and `extract`
- UI: Message history panel with extract buttons

### **Priority 2: Session Monitoring**

- Token counter (estimate from text length)
- Turn counter (message count)
- Context usage percentage bar
- Warning when >80% context used

### **Priority 3: Context Management**

- Auto-inject governance document
- Auto-inject software context
- Chain summary preparation
- UI: Checkboxes/buttons for injection

### **Priority 4: Meta Commands**

- `!align` button (context refresh)
- `!summarize` button (create summary)
- Integration with existing governance system

---

## Code Examples for Common Tasks

### **Adding a New AI (Example: ChatGPT)**

python

```python
# In ai_cli_bridge/ai/chatgpt.py
class ChatGPTAI(BaseAI):
    BASE_URL = "https://chat.openai.com"
    CDP_PORT = 9222  # Default port
    
    # ChatGPT-specific selectors
    INPUT_BOX = "textarea[data-id='root']"
    SEND_BUTTON = "button[data-testid='send-button']"
    
    @classmethod
    def get_default_config(cls):
        return {"base_url": cls.BASE_URL, "cdp_port": cls.CDP_PORT}
    
    async def _wait_for_response_complete(self, page, timeout):
        # Implement ChatGPT-specific completion detection
        pass
    
    async def _extract_response(self, page, baseline_count):
        # Implement ChatGPT-specific extraction
        pass
```

### **Using AIFactory**

python

```python
# Get AI class
ai_class = AIFactory.get_class("claude")

# Get default config
config = ai_class.get_default_config()

# Create instance
ai = AIFactory.create("claude", config)

# Send prompt
success, snippet, markdown, metadata = await ai.send_prompt("Hello")
```

---

## File Locations for Quick Reference

**Core AI Logic:**

- `~/dev/ai_app/ai-cli-bridge/src/ai_cli_bridge/ai/base.py` - Base class
- `~/dev/ai_app/ai-cli-bridge/src/ai_cli_bridge/ai/claude.py` - Claude implementation
- `~/dev/ai_app/ai-cli-bridge/src/ai_cli_bridge/ai/factory.py` - Factory pattern

**CLI Commands:**

- `~/dev/ai_app/ai-cli-bridge/src/ai_cli_bridge/commands/send_cmd.py` - Send command
- `~/dev/ai_app/ai-cli-bridge/src/ai_cli_bridge/commands/status_cmd.py` - Status command
- `~/dev/ai_app/ai-cli-bridge/src/ai_cli_bridge/cli.py` - CLI entry point

**GUI:**

- `~/dev/ai_app/ai-chat-ui/src/ai_chat_ui/window.py` - Main window with CDP auto-launch
- `~/dev/ai_app/ai-chat-ui/src/ai_chat_ui/response_display.py` - Response widget
- `~/dev/ai_app/ai-chat-ui/src/ai_chat_ui/markdown_parser.py` - Basic markdown

**Scripts:**

- `~/dev/ai_app/shared/scripts/launch_cdp.sh` - Launch Chromium with CDP
- `~/dev/ai_app/shared/scripts/launch-ui.sh` - Venv activation + UI launch

---

## Testing Commands

bash

```bash
# Activate environment
source ~/dev/ai_app/shared/scripts/activate.sh

# Test CLI
ai-cli-bridge status claude
ai-cli-bridge send claude "test message"

# Test GUI
ai-chat-ui

# Manual CDP launch
~/dev/ai_app/shared/scripts/launch_cdp.sh

# Check CDP connection
curl -s http://127.0.0.1:9223/json | jq
```

---

This summary provides complete context for an AI to continue development effectively. The AI can now ask for specific source files to implement planned features.