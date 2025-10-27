
# CDP Browser Foundation Documentation

## Overview

This document describes the CDP (Chrome DevTools Protocol) browser infrastructure for the ai-cli-bridge project. This is the foundation layer that enables the daemon to interact with AI web interfaces (Claude, Gemini, ChatGPT) through browser automation.

---
## Architecture

### **Design Principles**

1. **Persistent Profile**: Browser uses a persistent user data directory to maintain login cookies across sessions
2. **Single Shared Profile**: All three AIs share one browser instance with separate tabs (not separate profiles)
3. **Always Three Tabs**: Every launch opens exactly 3 tabs (Claude, Gemini, ChatGPT) - predictable and consistent
4. **Cookie Preservation**: Login sessions persist across browser restarts via the profile's Cookie database
5. **Self-Contained**: All runtime data lives within the project tree at `~/dev/ai_app/ai-cli-bridge/runtime/`

---

## File Structure

```
~/dev/ai_app/ai-cli-bridge/
├── LaunchCDP.sh                    # Launch CDP browser
├── StopCDP.sh                      # Stop CDP browser gracefully
└── runtime/
    ├── profiles/
    │   └── multi_ai_cdp/           # Persistent browser profile
    │       ├── Default/
    │       │   ├── Cookies         # SQLite database with login cookies
    │       │   ├── Local Storage/  # Web storage data
    │       │   ├── Preferences     # Browser settings
    │       │   └── ...             # Other browser data
    │       └── ...
    └── browser.pid                 # Process ID of running browser
```

---

## Components

### **1. LaunchCDP.sh**

**Purpose**: Launch Playwright Chromium with CDP enabled and persistent profile.

**Location**: `~/dev/ai_app/ai-cli-bridge/LaunchCDP.sh`

**Key Features**:

- Activates shared virtual environment from `~/dev/ai_app/shared/scripts/activate.sh`
- Checks if browser already running (via PID file and HTTP probe)
- Launches Playwright's bundled Chromium with specific flags
- Opens exactly 3 tabs (Claude, Gemini, ChatGPT URLs)
- Saves browser PID to `runtime/browser.pid`
- Waits for CDP endpoint to be ready (polls for up to 15 seconds)
- Reports WebSocket URL for CDP connection

**Critical Flags**:

bash

```bash
--remote-debugging-port=9223          # Enable CDP on port 9223
--user-data-dir="$PROFILE_DIR"        # Use persistent profile
--no-first-run                        # Skip first-run experience
--no-default-browser-check            # Don't prompt about default browser
```

**Notable Design Decisions**:

- **NO `--restore-last-session` flag**: We always open the same 3 tabs, not restore previous session
- **Suppress stderr**: Chromium outputs many harmless warnings - we redirect `2>/dev/null`
- **Port 9223**: Universally used across all components (not 9222)

**Exit Codes**:

- `0`: Success (browser launched or already running)
- `1`: Failure (venv not found, Chromium not found, CDP not ready, etc.)

---

### **2. StopCDP.sh**

**Purpose**: Gracefully stop the running CDP browser.

**Location**: `~/dev/ai_app/ai-cli-bridge/StopCDP.sh`

**Key Features**:

- Reads PID from `runtime/browser.pid`
- Checks if process is actually running
- Sends `SIGTERM` for graceful shutdown
- Waits up to 10 seconds for clean exit
- Falls back to `SIGKILL` if process doesn't stop
- Cleans up PID file on success

**Exit Codes**:

- `0`: Success (browser stopped)
- `1`: Failure (no PID file, process not running, couldn't stop)

---

### **3. Browser Profile**

**Location**: `~/dev/ai_app/ai-cli-bridge/runtime/profiles/multi_ai_cdp/`

**Purpose**: Persistent storage for all browser data across launches.

**Key Contents**:

#### **Cookies** (`Default/Cookies`)

- SQLite database containing authentication cookies
- **Critical**: This is what keeps you logged in across restarts
- Automatically managed by Chromium
- Never manually edit this file

#### **Local Storage** (`Default/Local Storage/`)

- Web storage data for each origin
- Key-value pairs stored by websites
- Persists across sessions

#### **Preferences** (`Default/Preferences`)

- JSON file with browser settings
- Created automatically on first launch
- Contains extension states, permissions, etc.

#### **Cache** (`Default/Cache/`)

- HTTP cache for faster page loads
- Not critical for functionality
- Can be deleted to clear cache

**Profile Lifecycle**:

1. **First Launch**: Profile directory created, empty `Default/` subdirectory initialized
2. **Login**: Cookies written to `Default/Cookies` database
3. **Browser Close**: All data persisted to disk
4. **Relaunch**: Chromium reads existing profile, cookies restored → still logged in

---

## Configuration

### **Constants** (defined in LaunchCDP.sh)

bash

```bash
CDP_PORT=9223                              # CDP debugging port
PROJECT_ROOT="$HOME/dev/ai_app/ai-cli-bridge"
SHARED_ROOT="$HOME/dev/ai_app/shared"      # Shared venv location
PROFILE_DIR="$PROJECT_ROOT/runtime/profiles/multi_ai_cdp"
PID_FILE="$PROJECT_ROOT/runtime/browser.pid"

# AI URLs (always opened on launch)
CLAUDE_URL="https://claude.ai/new"
GEMINI_URL="https://gemini.google.com/app"
CHATGPT_URL="https://chat.openai.com/"
```

---

## Operational Workflows

### **Initial Setup**

bash

```bash
cd ~/dev/ai_app/ai-cli-bridge

# Make scripts executable
chmod +x LaunchCDP.sh StopCDP.sh

# Launch browser for first time
./LaunchCDP.sh

# Manually login to all 3 AIs in browser tabs
# Cookies are automatically saved to profile

# Stop browser
./StopCDP.sh

# Relaunch - should still be logged in
./LaunchCDP.sh
```

---

### **Normal Operation Cycle**

bash

```bash
# Start browser (called by daemon or manually)
./LaunchCDP.sh
# → Browser opens with 3 tabs
# → Still logged in from previous session

# Work with AIs...

# Stop browser (called by daemon on shutdown or manually)
./StopCDP.sh
# → Browser closes gracefully
# → All cookies saved
```

---

### **Troubleshooting**

#### **Problem: Browser already running**

bash

```bash
# LaunchCDP.sh will detect and report:
✓ CDP browser already running (PID: 12345)

# To restart:
./StopCDP.sh
./LaunchCDP.sh
```

#### **Problem: Stale PID file**

bash

```bash
# LaunchCDP.sh automatically detects and cleans:
→ Removing stale PID file

# If manual cleanup needed:
rm ~/dev/ai_app/ai-cli-bridge/runtime/browser.pid
```

#### **Problem: Lost login sessions**

bash

```bash
# Cookies are in the profile - check if profile exists:
ls -la ~/dev/ai_app/ai-cli-bridge/runtime/profiles/multi_ai_cdp/Default/Cookies

# If Cookies file exists but sessions lost:
# - Websites may have invalidated cookies (security timeout)
# - Profile may be corrupted
# Solution: Delete profile and re-login:
rm -rf ~/dev/ai_app/ai-cli-bridge/runtime/profiles/multi_ai_cdp
./LaunchCDP.sh
# Login again to all 3 AIs
```

#### **Problem: CDP not responding**

bash

```bash
# Check if browser process exists:
cat ~/dev/ai_app/ai-cli-bridge/runtime/browser.pid
ps -p <PID>

# Check if CDP endpoint responds:
curl http://127.0.0.1:9223/json/version

# If browser running but CDP not responding:
# - Browser may have crashed but process lingering
# - Force kill and restart:
./StopCDP.sh  # Will use SIGKILL if needed
./LaunchCDP.sh
```

#### **Problem: Chromium not found**

bash

````bash
# LaunchCDP.sh will report:
✗ Error: Could not locate Playwright Chromium
  Install with: playwright install chromium

# Solution:
source ~/dev/ai_app/shared/scripts/activate.sh
playwright install chromium
```

---

## Integration with Daemon

### **Daemon Startup Sequence**

1. Daemon calls `LaunchCDP.sh` (or expects it to be running)
2. Daemon verifies CDP is accessible at port 9223
3. Daemon creates persistent AI instances
4. AI instances connect to CDP browser when needed

### **Daemon Shutdown Sequence**

1. Daemon stops accepting new requests
2. Daemon waits for in-flight requests to complete
3. Daemon calls `StopCDP.sh` to gracefully close browser
4. Daemon exits

### **Browser Ownership**

- **Launched by**: `LaunchCDP.sh` script (can be manual or daemon-triggered)
- **Managed by**: Daemon (via PID file)
- **Stopped by**: `StopCDP.sh` (called by daemon on shutdown)

**Important**: The browser is NOT launched directly by the daemon's Python code. The daemon calls the shell scripts.

---

## CDP Protocol Details

### **WebSocket URL Format**
```
ws://127.0.0.1:9223/devtools/browser/<UUID>
```

Example:
```
ws://127.0.0.1:9223/devtools/browser/9c818fb0-7410-4464-a711-9fd06d34f5d0
````

### **HTTP Endpoints**

**Version Info** (used to get WebSocket URL):

bash

```bash
curl http://127.0.0.1:9223/json/version
```

Response:

json

```json
{
  "Browser": "Chrome/129.0.6668.91",
  "Protocol-Version": "1.3",
  "User-Agent": "Mozilla/5.0 ...",
  "V8-Version": "12.9.202.21",
  "WebKit-Version": "537.36",
  "webSocketDebuggerUrl": "ws://127.0.0.1:9223/devtools/browser/<UUID>"
}
```

**List All Targets** (tabs/pages):

bash

```bash
curl http://127.0.0.1:9223/json
```

---

## Security Considerations

### **Local-Only Access**

- CDP listens on `127.0.0.1` (localhost only)
- Not accessible from network
- No authentication required (assumes local trust)

### **Profile Permissions**

- Profile directory has permissions `drwx------` (700)
- Only the user can read/write profile data
- Cookies database protected by OS file permissions

### **Browser Isolation**

- Each project should use its own profile directory
- Multiple projects can run simultaneously with different ports
- Shared profile between multiple instances = undefined behavior

---

## Debugging

### **Enable Verbose Output**

Remove `2>/dev/null` from LaunchCDP.sh to see all Chromium output:

bash

```bash
# In LaunchCDP.sh, change:
"$CHROMIUM_PATH" \
  --remote-debugging-port=$CDP_PORT \
  ... 2>/dev/null &

# To:
"$CHROMIUM_PATH" \
  --remote-debugging-port=$CDP_PORT \
  ... &
```

### **Check Browser State**

bash

```bash
# Process running?
ps aux | grep chrome | grep 9223

# CDP responding?
curl -s http://127.0.0.1:9223/json/version | jq

# List all tabs:
curl -s http://127.0.0.1:9223/json | jq

# Profile size:
du -sh ~/dev/ai_app/ai-cli-bridge/runtime/profiles/multi_ai_cdp/
```

### **Manual Browser Launch** (for testing)

bash

```bash
source ~/dev/ai_app/shared/scripts/activate.sh

CHROMIUM=$(python3 -c "from playwright.sync_api import sync_playwright; p = sync_playwright().start(); print(p.chromium.executable_path); p.stop()")

$CHROMIUM \
  --remote-debugging-port=9223 \
  --user-data-dir=/tmp/test-profile \
  https://claude.ai/new
```

---

## Future Enhancements

### **Potential Improvements**

1. **Health Checks**: Periodic CDP ping to detect browser crashes
2. **Auto-Recovery**: Automatically restart browser if CDP becomes unresponsive
3. **Profile Backup**: Periodic backup of Cookies database
4. **Multi-Profile Support**: Allow multiple isolated profiles for different use cases
5. **Headless Mode**: Option to run browser in headless mode (no GUI) for servers
6. **Custom Browser**: Support for non-Playwright Chromium (system browser, Ungoogled Chromium, etc.)
7. **Tab Management**: API to close/reopen specific AI tabs without full restart

### **Known Limitations**

1. **Single Instance**: Only one CDP browser per port - cannot run multiple instances
2. **Manual Login**: Initial login must be done manually (no automated login)
3. **Cookie Expiry**: If AI websites expire cookies, manual re-login required
4. **No Session Restore**: Extra tabs opened manually are not restored on relaunch
5. **Port Conflicts**: If port 9223 in use, launch fails (no automatic port selection)

---

## Change Log

### **Version 1.0** (Current)

- Initial implementation
- Removed `--restore-last-session` flag for predictable behavior
- Always opens 3 tabs (Claude, Gemini, ChatGPT)
- Port 9223 universally adopted
- Profile location: `runtime/profiles/multi_ai_cdp`
- Integrated with shared venv activation script

---

## Reference

### **Related Files**

- `src/ai_cli_bridge/daemon/main.py` - Daemon startup/shutdown logic
- `src/ai_cli_bridge/ai/base.py` - AI base class using CDP
- `src/ai_cli_bridge/ai/claude.py` - Claude AI implementation
- `src/ai_cli_bridge/ai/gemini.py` - Gemini AI implementation

### **External Documentation**

- Chrome DevTools Protocol: [https://chromerdevtools.github.io/devtools-protocol/](https://chromerdevtools.github.io/devtools-protocol/)
- Playwright Python: [https://playwright.dev/python/](https://playwright.dev/python/)
- Chromium Command Line Switches: [https://peter.sh/experiments/chromium-command-line-switches/](https://peter.sh/experiments/chromium-command-line-switches/)

---

## Contact & Support

For issues with CDP browser infrastructure:

1. Check this documentation first
2. Review troubleshooting section
3. Check browser process state and logs
4. Verify profile integrity
5. Test with manual browser launch to isolate issue

---

**Document Version**: 1.0
**Last Updated**: 2025-10-17
**Author**: AI-CLI-Bridge Team
**Status**: Production Ready
