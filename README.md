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

### Installation

    # 1. Clone repository
    git clone https://github.com/jablain/ai_app.git ~/dev/ai_app
    cd ~/dev/ai_app

    # 2. Run setup scripts
    ./setup_structure.sh
    ./setup_venv.sh

    # 3. Move scripts to shared folder
    mv *.sh shared/scripts/

### First Use

    # Activate environment
    source ~/dev/ai_app/shared/scripts/activate.sh

    # Launch UI (auto-starts CDP browser)
    ai-chat-ui

    # Or use CLI
    ai-cli-bridge send claude "your prompt"

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
