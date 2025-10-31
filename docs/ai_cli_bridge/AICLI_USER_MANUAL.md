# AI-CLI-Bridge User Manual

**Version 2.0.0**

A unified AI interface that provides CLI access to multiple AI assistants (Claude, ChatGPT, Gemini) through a self-managing daemon with browser automation.

---

## Table of Contents

1. [Overview](#overview)
2. [Installation](#installation)
3. [Quick Start](#quick-start)
4. [Architecture](#architecture)
5. [Command Reference](#command-reference)
6. [Configuration](#configuration)
7. [Usage Examples](#usage-examples)
8. [Troubleshooting](#troubleshooting)
9. [Exit Codes](#exit-codes)
10. [Advanced Topics](#advanced-topics)

---

## Overview

### What is AI-CLI-Bridge?

AI-CLI-Bridge is a command-line interface that allows you to interact with multiple AI assistants from your terminal. It uses browser automation (CDP - Chrome DevTools Protocol) to communicate with AI web interfaces while you remain logged in.

### Key Features

- **Multi-AI Support**: Claude, ChatGPT, and Gemini in one interface
- **Self-Managing Daemon**: Background service handles all browser processes
- **Persistent Sessions**: Stay logged in across multiple commands
- **JSON Output**: Machine-readable responses for scripting
- **Context Management**: Inject context and control window size
- **Graceful Shutdown**: Clean process and browser cleanup

### Components

1. **CLI Bridge** (`aicli`): Command-line interface for user interaction
2. **Daemon** (`ai-daemon`): Background service managing browser automation
3. **Chat UI** (`ai-chat-ui`): GTK4 graphical interface (separate component)

---

## Installation

### Requirements

- **Python**: 3.10 or higher
- **Operating System**: Linux (Ubuntu 24.04 recommended)
- **Browser**: ungoogled-chromium (via Flatpak)
- **Dependencies**: Automatically installed via pip

### Install from Source

```bash
# Clone the repository
git clone https://github.com/yourusername/ai-app.git
cd ai-app

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install in development mode
pip install -e .

# Verify installation
aicli --help
```

### Install from PyPI

```bash
pip install ai-app
```

### System Dependencies

The daemon requires ungoogled-chromium via Flatpak:

```bash
# Install Flatpak (if not already installed)
sudo apt install flatpak

# Add Flathub repository
flatpak remote-add --if-not-exists flathub https://flathub.org/repo/flathub.flatpakrepo

# Install ungoogled-chromium
flatpak install flathub com.github.Eloston.UngoogledChromium
```

---

## Quick Start

### 1. Start the Daemon

```bash
aicli daemon start
```

**Output:**
```
Starting daemon...
  Spawned process (PID: 12345)
  Logs: /home/user/ai_app/runtime/daemon/logs/daemon.log
  Waiting for daemon to become ready...
✓ Daemon ready (PID: 12345)
  API: http://127.0.0.1:8000
```

### 2. Check Status

```bash
aicli status
```

**Output:**
```
Daemon:
  Version:           2.1.0
  PID:               12345
  Available AIs:     chatgpt, claude, gemini
  Browser Pool:      active
  CDP Health:        OK

[claude]
  Transport:         unknown
  Connected:         False
  Message Count:     0
  Session Duration:  0.5s
  Context Window:    200000 tokens
  Context Used:      0.0%
```

### 3. Send a Message

```bash
aicli send claude "What is the weather in Paris?"
```

**Output:**
```
✓ Sent
  elapsed: 3421 ms
  response:
    I don't have access to real-time weather data. To get current weather 
    information for Paris, I recommend checking:
    - weather.com
    - A weather app on your phone
    - Google "Paris weather"
```

### 4. Stop the Daemon

```bash
aicli daemon stop
```

**Output:**
```
Stopping daemon (PID: 12345)…
  Sent SIGTERM, waiting for graceful shutdown…
✓ Daemon stopped gracefully
```

---

## Architecture

### System Design

```
┌─────────────┐
│   User CLI  │ (aicli commands)
└──────┬──────┘
       │ HTTP (localhost:8000)
       ▼
┌─────────────────┐
│  Daemon Service │ (FastAPI)
│  - Health Check │
│  - Request Queue│
│  - CDP Manager  │
└────────┬────────┘
         │ CDP Protocol (localhost:9222)
         ▼
┌─────────────────────────┐
│  ungoogled-chromium     │
│  ├── Tab: claude.ai     │
│  ├── Tab: chatgpt.com   │
│  └── Tab: gemini.google │
└─────────────────────────┘
```

### Process Lifecycle

1. **Daemon Start**: Spawns process group, launches browser with CDP
2. **Browser Init**: Opens tabs for each configured AI
3. **Ready State**: Health check passes, accepts commands
4. **Message Flow**: CLI → Daemon → Browser → AI → Response
5. **Daemon Stop**: SIGTERM → cleanup → browser close → exit

### Configuration Flow

```
~/.config/ai_app/config.toml
         │
         ▼
    load_config()
         │
         ├─→ Daemon settings (host, port, timeouts)
         ├─→ CDP settings (browser path, port)
         └─→ AI settings (URLs, models)
```

---

## Command Reference

### Global Options

All commands support:
- `--help`: Show command help

### `aicli daemon start`

Start the background daemon service.

**Usage:**
```bash
aicli daemon start [OPTIONS]
```

**Options:**
- `--wait / --no-wait`: Wait for daemon readiness (default: `--wait`)
- `--timeout FLOAT`: Seconds to wait for ready state (default: config + 5s)
- `--verbose`: Show daemon logs during startup

**Examples:**
```bash
# Standard start
aicli daemon start

# Start without waiting
aicli daemon start --no-wait

# Start with verbose logging
aicli daemon start --verbose

# Start with custom timeout
aicli daemon start --timeout 30
```

**Exit Codes:**
- `0`: Success (daemon started)
- `1`: Daemon already running
- `2`: Startup failed (check logs)

---

### `aicli daemon stop`

Stop the running daemon service.

**Usage:**
```bash
aicli daemon stop [OPTIONS]
```

**Options:**
- `--force`: Force kill if graceful shutdown fails

**Examples:**
```bash
# Graceful stop (waits 12 seconds)
aicli daemon stop

# Force kill if hung
aicli daemon stop --force
```

**Exit Codes:**
- `0`: Success (daemon stopped)
- `1`: Daemon not running
- `3`: Shutdown failed

---

### `aicli daemon status`

Check daemon process health.

**Usage:**
```bash
aicli daemon status [OPTIONS]
```

**Options:**
- `--json`: Output as JSON

**Examples:**
```bash
# Human-readable
aicli daemon status

# JSON output
aicli daemon status --json
```

**Output (Human):**
```
Daemon status: ✅ Running (PID: 12345)
  Health: ✅ OK
  API: http://127.0.0.1:8000

  (Use 'aicli status' for AI instance details)
```

**Output (JSON):**
```json
{
  "ok": true,
  "code": 0,
  "message": "Daemon running and healthy",
  "data": {
    "running": true,
    "pid": 12345,
    "api_url": "http://127.0.0.1:8000"
  }
}
```

**Exit Codes:**
- `0`: Daemon running and healthy
- `1`: Daemon not running

---

### `aicli send`

Send a message to an AI assistant.

**Usage:**
```bash
aicli send AI_NAME MESSAGE [OPTIONS]
```

**Arguments:**
- `AI_NAME`: Target AI (`claude`, `chatgpt`, or `gemini`)
- `MESSAGE`: Text to send

**Options:**
- `--wait / --no-wait`: Wait for response (default: `--wait`)
- `--timeout INTEGER`: Response timeout in seconds (default: `120`)
- `--json`: Output as JSON
- `--debug`: Enable debug output
- `--inject TEXT`: Inject additional context
- `--context-size INTEGER`: Override context window size

**Examples:**

```bash
# Simple question
aicli send claude "Explain quantum entanglement"

# No-wait mode (fire and forget)
aicli send chatgpt "Summarize this article" --no-wait

# JSON output for scripting
aicli send gemini "What is 2+2?" --json

# With context injection
aicli send claude "Tell me a joke" --inject "You are a pirate"

# With custom context size
aicli send claude "Long analysis" --context-size 100000

# Combined options
aicli send claude "Explain AI" --inject "Use simple terms" --timeout 60 --json
```

**Output (Human, with --wait):**
```
✓ Sent
  elapsed: 3421 ms
  response:
    Quantum entanglement is a physical phenomenon where two or more particles 
    become correlated in such a way that the state of one particle instantly 
    influences the state of the other, regardless of distance...
```

**Output (Human, with --no-wait):**
```
✓ Sent
```

**Output (JSON):**
```json
{
  "ok": true,
  "code": 0,
  "message": "Success",
  "data": {
    "snippet": "Quantum entanglement is a physical phenomenon...",
    "markdown": "**Quantum entanglement** is a physical phenomenon...",
    "elapsed_ms": 3421,
    "timeout_s": 120.0
  }
}
```

**Exit Codes:**
- `0`: Success
- `1`: Daemon not running, invalid AI name, or request failed

---

### `aicli status`

Get detailed status of AI instances.

**Usage:**
```bash
aicli status [AI_NAME] [OPTIONS]
```

**Arguments:**
- `AI_NAME`: Optional, filter to specific AI (or empty for all)

**Options:**
- `--json`: Output as JSON

**Examples:**

```bash
# All AIs
aicli status

# Single AI
aicli status claude

# JSON output
aicli status --json

# Single AI as JSON
aicli status gemini --json
```

**Output (Human, all AIs):**
```
Daemon:
  Version:           2.1.0
  PID:               12345
  Available AIs:     chatgpt, claude, gemini
  Browser Pool:      active
  CDP Health:        OK

[chatgpt]
  Transport:         unknown
  Connected:         False
  Message Count:     5
  Session Duration:  120.5s
  Context Window:    128000 tokens
  Context Used:      2.3%

[claude]
  Transport:         unknown
  Connected:         False
  Message Count:     12
  Session Duration:  450.2s
  Context Window:    200000 tokens
  Context Used:      5.1%

[gemini]
  Transport:         unknown
  Connected:         False
  Message Count:     0
  Session Duration:  0.5s
  Context Window:    2000000 tokens
  Context Used:      0.0%
```

**Output (JSON):**
```json
{
  "ok": true,
  "code": 0,
  "message": "Status retrieved",
  "data": {
    "daemon": {
      "version": "2.1.0",
      "pid": 12345,
      "browser_pool_active": true,
      "cdp_healthy": true,
      "uptime_s": 450.2
    },
    "ais": {
      "claude": {
        "ai_target": "claude",
        "message_count": 12,
        "session_duration_s": 450.2,
        "ctaw_size": 200000,
        "ctaw_usage_percent": 5.1
      }
    }
  }
}
```

**Exit Codes:**
- `0`: Success
- `1`: Daemon not running
- `2`: Requested AI not found

---

### `aicli version`

Display version information.

**Usage:**
```bash
aicli version
```

**Output:**
```
ai-cli-bridge 2.0.0
```

---

## Configuration

### Configuration File Location

```
~/.config/ai_app/config.toml
```

### Default Configuration

```toml
[daemon]
host = "127.0.0.1"
port = 8000
log_level = "INFO"

[cdp]
browser_path = "flatpak run com.github.Eloston.UngoogledChromium"
cdp_port = 9222
start_timeout_s = 10.0

[ai.claude]
url = "https://claude.ai"
model = "claude-sonnet-4"
context_window = 200000

[ai.chatgpt]
url = "https://chatgpt.com"
model = "gpt-4"
context_window = 128000

[ai.gemini]
url = "https://gemini.google.com"
model = "gemini-pro"
context_window = 2000000
```

### Configuration Options

#### `[daemon]`
- `host`: Daemon API host (default: `127.0.0.1`)
- `port`: Daemon API port (default: `8000`)
- `log_level`: Logging verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`)

#### `[cdp]`
- `browser_path`: Command to launch browser
- `cdp_port`: Chrome DevTools Protocol port (default: `9222`)
- `start_timeout_s`: Browser startup timeout (default: `10.0`)

#### `[ai.*]`
- `url`: Base URL for the AI service
- `model`: Model identifier
- `context_window`: Maximum context size in tokens

### Customizing Configuration

```bash
# Edit config file
nano ~/.config/ai_app/config.toml

# Restart daemon to apply changes
aicli daemon stop
aicli daemon start
```

---

## Usage Examples

### Scripting with JSON Output

**Example: Daily Weather Report**

```bash
#!/bin/bash

# Start daemon if not running
aicli daemon status --json | jq -e '.ok' || aicli daemon start

# Get weather for multiple cities
cities=("Paris" "London" "Tokyo")

for city in "${cities[@]}"; do
  echo "=== $city ==="
  aicli send claude "What's the weather in $city?" --json | \
    jq -r '.data.snippet' | \
    head -c 200
  echo -e "\n"
done
```

**Example: Summarize Git Commits**

```bash
#!/bin/bash

# Get recent commits
commits=$(git log --oneline -n 10)

# Ask AI to summarize
response=$(aicli send claude "Summarize these commits: $commits" --json)

# Extract snippet
echo "$response" | jq -r '.data.snippet'
```

---

### Multiple AIs for Comparison

```bash
#!/bin/bash

question="What is the capital of France?"

echo "=== Claude ==="
aicli send claude "$question" | grep -A 20 "response:"

echo -e "\n=== ChatGPT ==="
aicli send chatgpt "$question" | grep -A 20 "response:"

echo -e "\n=== Gemini ==="
aicli send gemini "$question" | grep -A 20 "response:"
```

---

### Context Injection for Role-Playing

```bash
# Make AI respond as a specific character
aicli send claude "Tell me about the weather" \
  --inject "You are a medieval knight. Speak in old English."

# Output:
# Hark! The heavens doth bestow upon us a most clement day...
```

---

### Monitoring Daemon Health

```bash
#!/bin/bash

# Cron job to check daemon health every 5 minutes
while true; do
  if ! aicli daemon status --json | jq -e '.ok' > /dev/null; then
    echo "[$(date)] Daemon unhealthy, restarting..."
    aicli daemon stop --force
    aicli daemon start
  fi
  sleep 300
done
```

---

### Processing Large Context

```bash
# Read a large file and analyze it
content=$(cat large_document.txt)

aicli send claude "Summarize this document: $content" \
  --context-size 150000 \
  --timeout 300 \
  --json > summary.json
```

---

## Troubleshooting

### Daemon Won't Start

**Symptom:**
```
✗ Daemon crashed during startup (exit code: 4)
  Daemon port already in use
```

**Solution:**
```bash
# Check if port 8000 is in use
lsof -i :8000

# Kill the process or change port in config
# ~/.config/ai_app/config.toml
[daemon]
port = 8001
```

---

### Browser Not Found

**Symptom:**
```
✗ Daemon crashed during startup (exit code: 5)
  Flatpak or ungoogled-chromium not installed
```

**Solution:**
```bash
# Install ungoogled-chromium
flatpak install flathub com.github.Eloston.UngoogledChromium

# Verify installation
flatpak list | grep -i chromium
```

---

### CDP Connection Timeout

**Symptom:**
```
✗ Daemon did not become ready in time
  Check logs: /home/user/ai_app/runtime/daemon/logs/daemon.log
```

**Solution:**
```bash
# Check logs
tail -f ~/ai_app/runtime/daemon/logs/daemon.log

# Increase timeout in config
[cdp]
start_timeout_s = 20.0

# Restart daemon
aicli daemon stop --force
aicli daemon start --timeout 30
```

---

### AI Not Responding

**Symptom:**
```
✓ Sent
  elapsed: 120000 ms
  response:
    (timeout)
```

**Solution:**
```bash
# Check if you're logged into the AI web interface
# Open browser manually and log in:
flatpak run com.github.Eloston.UngoogledChromium

# Navigate to:
# - https://claude.ai
# - https://chatgpt.com
# - https://gemini.google.com

# Log in to each service

# Restart daemon
aicli daemon stop
aicli daemon start
```

---

### Permission Denied

**Symptom:**
```
✗ Permission denied (cannot kill PID 12345)
```

**Solution:**
```bash
# Daemon was started by another user
# Check owner
ps aux | grep daemon

# Stop as correct user or use sudo
sudo aicli daemon stop --force
```

---

### Logs Location

All logs are stored in:
```
~/ai_app/runtime/daemon/logs/daemon.log
```

View logs:
```bash
# Real-time monitoring
tail -f ~/ai_app/runtime/daemon/logs/daemon.log

# Last 100 lines
tail -n 100 ~/ai_app/runtime/daemon/logs/daemon.log

# Search for errors
grep ERROR ~/ai_app/runtime/daemon/logs/daemon.log
```

---

## Exit Codes

### Daemon Commands

| Code | Meaning |
|------|---------|
| `0` | Success |
| `1` | Daemon not running |
| `2` | Profile directory not writable |
| `3` | Shutdown failed |
| `4` | Daemon port busy |
| `5` | Flatpak/browser missing |
| `6` | CDP conflict or timeout |

### Send Command

| Code | Meaning |
|------|---------|
| `0` | Success |
| `1` | Daemon not running, invalid AI, or request failed |

### Status Command

| Code | Meaning |
|------|---------|
| `0` | Success |
| `1` | Daemon not running |
| `2` | Requested AI not found |

---

## Advanced Topics

### Running Multiple Instances

You can run multiple daemon instances on different ports:

**Config for Instance 1:**
```toml
# ~/.config/ai_app/config.toml
[daemon]
port = 8000

[cdp]
cdp_port = 9222
```

**Config for Instance 2:**
```toml
# ~/.config/ai_app/config-alt.toml
[daemon]
port = 8001

[cdp]
cdp_port = 9223
```

**Usage:**
```bash
# Start first instance
AI_APP_CONFIG=~/.config/ai_app/config.toml aicli daemon start

# Start second instance (in another terminal)
AI_APP_CONFIG=~/.config/ai_app/config-alt.toml aicli daemon start
```

---

### Integration with Other Tools

#### Vim Integration

```vim
" ~/.vimrc
function! AskClaude()
  let question = input("Ask Claude: ")
  let response = system('aicli send claude "' . question . '" --json | jq -r .data.snippet')
  echo response
endfunction

nnoremap <leader>ai :call AskClaude()<CR>
```

#### Tmux Integration

```bash
# Send current pane content to AI
tmux capture-pane -p | aicli send claude "Explain this terminal output" --json
```

#### Shell Alias

```bash
# ~/.bashrc
alias ask='aicli send claude'
alias askgpt='aicli send chatgpt'
alias askgem='aicli send gemini'

# Usage:
# ask "What is Docker?"
```

---

### Performance Tuning

#### Reduce Startup Time

```toml
[cdp]
# Use already-running browser
browser_path = "chromium-browser --remote-debugging-port=9222"
start_timeout_s = 5.0
```

#### Increase Timeout for Long Responses

```toml
[daemon]
default_timeout = 300  # 5 minutes
```

---

### Security Considerations

1. **Local Only**: Daemon binds to `127.0.0.1` by default (localhost only)
2. **No Authentication**: Do not expose daemon to network without auth
3. **Browser Profile**: Uses isolated profile, separate from your main browser
4. **Credentials**: Your AI login credentials stay in the browser session

**To secure network access:**

```toml
[daemon]
host = "0.0.0.0"  # Listen on all interfaces
port = 8000

# Then use a reverse proxy with auth:
# nginx, caddy, or traefik with basic auth
```

---

### Debugging

#### Enable Debug Logging

```toml
[daemon]
log_level = "DEBUG"
```

#### Verbose CLI Output

```bash
aicli send claude "test" --debug
```

#### Inspect HTTP Traffic

```bash
# Install mitmproxy
pip install mitmproxy

# Run daemon through proxy
HTTP_PROXY=http://localhost:8080 aicli daemon start

# In another terminal
mitmproxy
```

---

### Uninstallation

```bash
# Stop daemon
aicli daemon stop

# Remove package
pip uninstall ai-app

# Remove config and data
rm -rf ~/.config/ai_app
rm -rf ~/ai_app/runtime

# Remove browser (optional)
flatpak uninstall com.github.Eloston.UngoogledChromium
```

---

## Support

### Getting Help

1. **Documentation**: This manual
2. **Issues**: https://github.com/yourusername/ai-app/issues
3. **Discussions**: https://github.com/yourusername/ai-app/discussions

### Reporting Bugs

Include:
1. Output of `aicli version`
2. Output of `aicli daemon status --json`
3. Relevant log excerpt from `~/ai_app/runtime/daemon/logs/daemon.log`
4. Steps to reproduce

### Contributing

Contributions welcome! See `CONTRIBUTING.md` in the repository.

---

## License

This project is licensed under the MIT License. See `LICENSE` file for details.

---

## Changelog

### Version 2.0.0 (Current)

**New Features:**
- Dependency injection for cleaner architecture
- Uniform JSON envelope across all commands
- Context injection via `--inject` flag
- Context size override via `--context-size` flag
- Exponential backoff for faster daemon startup

**Improvements:**
- Simplified `daemon status` command (process health only)
- Removed unnecessary import guards
- Input validation on AI names
- Robust non-JSON error handling
- Consistent output functions throughout

**Bug Fixes:**
- Fixed missing CLI arguments for inject/contextsize
- Safe config access (no crashes on missing fields)
- Removed race conditions in daemon startup

### Version 1.0.0

- Initial release
- Basic daemon management
- Support for Claude, ChatGPT, Gemini
- JSON output support

---

**End of Manual**

For the latest version of this manual, visit: https://github.com/yourusername/ai-app/blob/main/docs/USER_MANUAL.md
