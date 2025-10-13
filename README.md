# AI App - Unified AI Toolset

Personal AI automation toolset with CLI and GUI interfaces for Claude, ChatGPT, and Gemini.

## Project Structure

    ai_app/
    ├── ai-cli-bridge/          # CLI automation tool
    │   └── src/                # Source code (tracked)
    ├── ai-chat-ui/             # GTK4 GUI interface  
    │   └── src/                # Source code (tracked)
    ├── shared/
    │   └── scripts/            # Utility scripts (tracked)
    └── docs/                   # Documentation (tracked)

Note: runtime/ directories contain user data (profiles, logs, venvs) and are NOT tracked in git.

## Setup

### Prerequisites

- Python 3.10+
- GTK4 + libadwaita (for GUI)
- Playwright

### Prerequisites

    **System packages (Ubuntu/Pop!_OS/Debian):**

    sudo apt update
    sudo apt install -y \
      python3 python3-pip python3-venv \
      python3-gi gir1.2-gtk-4.0 gir1.2-adw-1

    **Other distributions:**
    - Arch: `python python-pip python-gobject gtk4 libadwaita`
    - Fedora: `python3 python3-pip python3-gobject gtk4 libadwaita`

    **Verify GTK4:**

    python3 -c "import gi; gi.require_version('Gtk', '4.0'); gi.require_version('Adw', '1'); from gi.repository import Gtk, Adw; print('✓ GTK4 ready')"
    
### Installation

    # 1. Clone repository
    git clone https://github.com/jablain/ai_app.git ~/dev/ai_app
    cd ~/dev/ai_app

    # 2. Run setup scripts
    ./setup_structure.sh
    ./setup_venv.sh

    # 3. Move scripts to shared folder
    mv *.sh shared/scripts/

    # 4. Download Playwright browser
    source shared/scripts/activate.sh
    playwright install chromium

    # 5. Install desktop entry and icon
    cp ai-chat-ui/desktop/ai-chat-ui.desktop ~/.local/share/applications/
    mkdir -p ~/.local/share/icons/hicolor/scalable/apps/
    cp ai-chat-ui/desktop/ai-chat-ui.svg ~/.local/share/icons/hicolor/scalable/apps/
    update-desktop-database ~/.local/share/applications
    gtk-update-icon-cache -f -t ~/.local/share/icons/hicolor

### First Use

    # Activate environment
    source ~/dev/ai_app/shared/scripts/activate.sh

    # Launch UI (auto-starts CDP browser)
    ai-chat-ui

    # Or use CLI
    ai-cli-bridge send claude "your prompt"

    **Important:** On first launch:
    1. CDP browser will open
    2. Navigate to https://claude.ai
    3. Log in manually (one time only)
    4. Close browser properly (Ctrl+Q or click X)
    5. Future launches will remember your login

## Features

### ai-cli-bridge (CLI)
- Automate AI conversations via CDP
- No API keys required
- Support for Claude, ChatGPT, Gemini

### ai-chat-ui (GUI)
- Native GNOME GTK4 interface
- Auto-launch CDP browser
- Auto-close on exit
- Markdown formatting
- Copy to clipboard

## Development

Source code locations:
- CLI: ai-cli-bridge/src/
- UI: ai-chat-ui/src/

Both installed as editable packages - changes take effect immediately.

## License

Personal use
