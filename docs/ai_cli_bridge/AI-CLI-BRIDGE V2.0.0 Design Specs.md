
# AI-CLI-Bridge v2.0.0

## Software Architecture Design Document

**Version:** 2.0.0  
**Release Date:** October 18, 2025  
**Status:** Production Ready  
**Document Classification:** Technical Architecture Specification

---
## Executive Summary

AI-CLI-Bridge is a production-grade command-line interface system providing programmatic access to multiple browser-based AI assistants (Claude, Gemini, ChatGPT) through a persistent daemon architecture. The system leverages Chrome DevTools Protocol (CDP) to maintain authenticated browser sessions while providing a unified, efficient interface for AI interactions with comprehensive session management and telemetry.
### Key Capabilities

- **Multi-AI Unified Interface**: Single CLI supporting Claude, Gemini, and ChatGPT
- **Persistent Daemon Architecture**: Long-running service maintaining browser connections
- **Token & Context Tracking**: Real-time monitoring of token usage and context window consumption
- **Session Persistence**: Authenticated sessions preserved across system restarts
- **High Performance**: Sub-second command response through connection pooling
- **Extensible Design**: Clean abstractions enabling rapid integration of new AI platforms
### Technical Achievements

- **37% Code Reduction**: Through DRY principles and strategic abstraction
- **Zero Configuration**: Sensible defaults with optional configuration override
- **Filesystem-Agnostic**: Self-contained tree structure deployable anywhere
- **Production Hardened**: Comprehensive error handling and graceful degradation

---
## 1. System Architecture Overview

### 1.1 Architectural Style

AI-CLI-Bridge implements a **client-daemon architecture** with the following characteristics:

```
┌─────────────────────────────────────────────────────────────┐
│                    User/Script Layer                        │
│  (Shell scripts, automation tools, interactive terminal)    │
└──────────────────────┬──────────────────────────────────────┘
                       │ CLI Commands
                       ↓
┌─────────────────────────────────────────────────────────────┐
│                   CLI Interface Layer                       │
│  (Command parsing, validation, HTTP client, formatting)     │
└──────────────────────┬──────────────────────────────────────┘
                       │ HTTP/REST
                       ↓
┌─────────────────────────────────────────────────────────────┐
│                  Daemon Service Layer                       │
│  (FastAPI server, request routing, session management)      │
└──────────────────────┬──────────────────────────────────────┘
                       │ Factory Pattern
                       ↓
┌─────────────────────────────────────────────────────────────┐
│               AI Abstraction Layer                          │
│  BaseAI → WebAIBase → [ClaudeAI|GeminiAI|ChatGPTAI]         │
└──────────────────────┬──────────────────────────────────────┘
                       │ CDP WebSocket
                       ↓
┌─────────────────────────────────────────────────────────────┐
│               Browser Automation Layer                      │
│  (Playwright, CDP protocol, browser process management)     │
└──────────────────────┬──────────────────────────────────────┘
                       │ User Data Dir
                       ↓
┌─────────────────────────────────────────────────────────────┐
│           Persistent Browser Sessions                       │
│  (Chromium with authenticated AI sessions, cookies)         │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 Core Design Principles

#### 1.2.1 Single-Tree Philosophy

**Principle**: All project artifacts exist within a single, self-contained directory tree with exclusively relative internal references.

**Rationale**:

- **Portability**: Tree can be placed anywhere in filesystem without configuration changes
- **Isolation**: No pollution of system directories or user home directory (except for virtual environment)
- **Reproducibility**: Identical structure across development, staging, and production
- **Simplicity**: No complex path resolution or environment-dependent lookups
- **Maintenance**: Easy backup, migration, and version control

**Implementation**:

```python
# All path resolution anchored to project root
PROJECT_ROOT = pathlib.Path(__file__).parent.parent.parent.resolve()
RUNTIME_DIR = PROJECT_ROOT / "runtime"  # Relative path
```

This eliminates absolute paths and enables:

```bash
# Move entire project anywhere
mv ~/dev/ai_app/ai-cli-bridge /opt/ai-bridge
# Continues working without reconfiguration
```

#### 1.2.2 DRY (Don't Repeat Yourself)

Common patterns abstracted into reusable base classes:

- `BaseAI`: Core AI interaction protocol
- `WebAIBase`: Stop-button pattern for web-based AIs
- Concrete implementations: Only selectors and AI-specific quirks

Result: ~410 lines for 3 AIs vs. ~750+ lines with duplication (37% reduction)

#### 1.2.3 Separation of Concerns

Clear layer boundaries:

- **CLI**: User interaction, command parsing, output formatting
- **Daemon**: Process management, request routing, state persistence
- **AI Layer**: Browser automation, selector management, response extraction
- **Browser**: CDP connection, session persistence, cookie management

#### 1.2.4 Fail-Safe Defaults

System operable immediately after installation:

- No required configuration files
- Sensible default values for all parameters
- Graceful degradation when optional features unavailable

---
## 2. Directory Structure & Design Philosophy

### 2.1 Complete Directory Tree

```
~/dev/ai_app/ai-cli-bridge/                    # Project root (relocatable)
│
├── src/                                        # Source code
│   └── ai_cli_bridge/                         # Python package
│       ├── __init__.py                        # Package initialization
│       ├── cli.py                             # Main CLI entry point
│       │
│       ├── daemon/                            # Daemon subsystem
│       │   ├── __init__.py
│       │   ├── main.py                        # FastAPI application
│       │   ├── config.py                      # Configuration management
│       │   ├── daemon_cmd.py                  # Daemon control commands
│       │   └── process_manager.py             # Process lifecycle management
│       │
│       ├── ai/                                # AI integration layer
│       │   ├── __init__.py
│       │   ├── base.py                        # BaseAI abstract class
│       │   ├── web_base.py                    # WebAIBase for web AIs
│       │   ├── factory.py                     # AI factory pattern
│       │   ├── claude.py                      # Claude implementation
│       │   ├── gemini.py                      # Gemini implementation
│       │   └── chatgpt.py                     # ChatGPT implementation
│       │
│       └── commands/                          # CLI command implementations
│           ├── __init__.py
│           ├── send_cmd.py                    # Send message command
│           ├── status_cmd.py                  # Status reporting
│           ├── doctor_cmd.py                  # System diagnostics
│           ├── open_cmd.py                    # Browser navigation
│           ├── init_cmd.py                    # Initialization
│           └── init_cdp_cmd.py                # CDP setup
│
├── runtime/                                    # Runtime data (gitignored)
│   ├── profiles/                              # Browser profiles
│   │   └── multi_ai_cdp/                     # Shared profile for all AIs
│   │       └── Default/                       # Chromium default profile
│   │           ├── Cookies                    # SQLite cookie database
│   │           ├── Local Storage/             # Web storage data
│   │           └── Preferences                # Browser preferences
│   │
│   ├── config/                                # Configuration files
│   │   └── daemon_config.toml                # Optional daemon config
│   │
│   ├── logs/                                  # Log files
│   │   └── daemon.log                        # Daemon output log
│   │
│   ├── ai_state/                              # AI session state (future)
│   │   ├── claude_state.json
│   │   ├── gemini_state.json
│   │   └── chatgpt_state.json
│   │
│   ├── daemon.pid                             # Daemon process ID
│   └── browser.pid                            # Browser process ID
│
├── LaunchCDP.sh                               # Browser launch script
├── StopCDP.sh                                 # Browser stop script
├── pyproject.toml                             # Project metadata & dependencies
├── README.md                                  # User documentation
└── .gitignore                                 # VCS ignore rules
```
### 2.2 Design Philosophy Explanation

#### 2.2.1 Source Code Organization (`src/`)

**Structure**: Single `src/ai_cli_bridge/` package containing all Python code

**Philosophy**:

- **Namespace Isolation**: Package name matches project, preventing import conflicts
- **Logical Grouping**: Subsystems (`daemon/`, `ai/`, `commands/`) clearly separated
- **Import Clarity**: All imports use fully-qualified names from package root
    
    ```python
    from ai_cli_bridge.ai.factory import AIFactoryfrom ai_cli_bridge.daemon import config
    ```

**Benefits**:

- IDE autocomplete works reliably
- Circular import issues impossible with proper layering
- Easy to reason about dependencies

#### 2.2.2 Runtime Data Isolation (`runtime/`)

**Structure**: All mutable runtime data in single `runtime/` directory

**Philosophy**:

- **Separation of Code & Data**: Source immutable; runtime data mutable
- **Gitignore Simplicity**: Single pattern excludes all runtime artifacts
    
    ```
    runtime/
    ```
    
- **Backup/Restore**: Single directory contains all state
- **Security**: Sensitive data (cookies, PIDs) contained in known location

**Categories**:

- `profiles/`: Browser state (cookies, storage, preferences)
- `config/`: User configuration overrides
- `logs/`: Operational logs for debugging
- `ai_state/`: AI session state (future feature)
- `*.pid`: Process identifiers for daemon/browser

#### 2.2.3 Shell Scripts at Root

**Structure**: `LaunchCDP.sh` and `StopCDP.sh` at project root

**Philosophy**:

- **Visibility**: Launch scripts immediately visible, not buried in subdirectories
- **Convention**: Shell scripts at root is familiar Unix/Linux pattern
- **Simplicity**: User runs `./LaunchCDP.sh` without path traversal
- **Separation**: Browser lifecycle separate from Python codebase

**Alternative Considered**: Could be in `scripts/` subdirectory, but rejected for reduced discoverability.

#### 2.2.4 Relative Path Resolution

**Implementation Pattern**:

```python
# In any module, resolve paths relative to package root
PROJECT_ROOT = pathlib.Path(__file__).parent.parent.parent.resolve()
RUNTIME_DIR = PROJECT_ROOT / "runtime"
CONFIG_FILE = RUNTIME_DIR / "config" / "daemon_config.toml"
```

**Philosophy**:

- **No Hardcoded Paths**: No `/home/user/...` or `/opt/...` paths in code
- **No Environment Variables**: No reliance on `$HOME`, `$XDG_CONFIG_HOME`, etc.
- **Pure Relativity**: All paths computed from `__file__` location

**Result**: Project functions identically regardless of filesystem location

#### 2.2.5 Executable Location Philosophy

**Installation**: Package installed in shared virtual environment:

```
~/dev/ai_app/shared/runtime/venv/bin/ai-cli-bridge
```

**Philosophy**:

- **Shared Dependencies**: Multiple projects share single venv (reduced disk usage)
- **PATH Integration**: Venv activation adds `bin/` to PATH
- **Standard Practice**: Follows Python packaging conventions
- **Separation**: Executable separate from source (editable install pattern)

**How It Works**:

1. Package installed with `pip install -e .` (editable mode)
2. Executable created in venv `bin/` directory
3. Executable imports from source tree via relative imports
4. Source tree remains editable; changes reflected immediately

---
## 3. Daemon Architecture

### 3.1 Overview

The daemon is a long-running FastAPI-based HTTP server that maintains persistent connections to AI services and manages browser lifecycle. It implements a stateful service pattern with careful resource management.

### 3.2 Daemon Lifecycle

```
┌───────────────────────────────────────────────────────────┐
│                   Daemon Startup                           │
└─────────────────────┬─────────────────────────────────────┘
                      │
        ┌─────────────┴──────────────┐
        │                             │
        ↓                             ↓
  Load Config                   Verify CDP Browser
  (daemon_config.toml)          (Port 9223 check)
        │                             │
        └─────────────┬───────────────┘
                      ↓
            Read Browser PID
            (runtime/browser.pid)
                      │
                      ↓
          ┌───────────────────────┐
          │ Import AI Modules     │
          │ (Trigger registration)│
          └───────────┬───────────┘
                      │
          ┌───────────┴────────────┐
          │                         │
          ↓                         ↓
    Create Claude Instance    Create Gemini Instance
          │                         │
          └───────────┬─────────────┘
                      ↓
            Create ChatGPT Instance
                      │
                      ↓
          Initialize Async Locks
          (Per-AI concurrency control)
                      │
                      ↓
┌─────────────────────────────────────────────────────────────┐
│              Daemon Running (Event Loop)                     │
│  - Accept HTTP requests on localhost:8000                   │
│  - Route to appropriate AI instance                         │
│  - Acquire lock, execute, release                           │
└─────────────────────┬───────────────────────────────────────┘
                      │
                (SIGTERM/SIGINT)
                      ↓
┌─────────────────────────────────────────────────────────────┐
│                  Daemon Shutdown                             │
│  1. Stop accepting new requests                             │
│  2. Wait for in-flight requests to complete                 │
│  3. Send SIGTERM to browser process (graceful)              │
│  4. Wait up to 10 seconds for browser exit                  │
│  5. SIGKILL browser if still running (force)                │
│  6. Clean up PID files                                      │
│  7. Exit                                                    │
└─────────────────────────────────────────────────────────────┘
```

### 3.3 Core Components

#### 3.3.1 FastAPI Application (`daemon/main.py`)

**Responsibilities**:

- HTTP server hosting (via Uvicorn)
- Request routing to AI instances
- Lifespan management (startup/shutdown hooks)
- Error handling and response formatting

**Configuration**:

```python
app = FastAPI(
    title="AI-CLI-Bridge Daemon",
    version="2.0.0",
    lifespan=lifespan  # Manages startup/shutdown
)
```

**Endpoints**:

- `GET /`: Health check
- `GET /status`: System and AI status
- `POST /send`: Send message to AI
- `POST /session/new/{ai_name}`: Reset AI session state

#### 3.3.2 AI Instance Management

**Pattern**: Factory-created persistent instances

```python
daemon_state = {
    "ai_instances": {
        "claude": ClaudeAI(config),
        "gemini": GeminiAI(config),
        "chatgpt": ChatGPTAI(config)
    },
    "locks": {
        "claude": asyncio.Lock(),
        "gemini": asyncio.Lock(),
        "chatgpt": asyncio.Lock()
    },
    "browser_pid": 12345
}
```

**Rationale**:

- **Persistence**: Instances maintain state across requests (token counts, session timers)
- **Efficiency**: No reconnection overhead per request
- **Concurrency Control**: Locks prevent race conditions during AI interactions
- **Resource Management**: Single CDP connection reused

#### 3.3.3 Concurrency Model

**Strategy**: Per-AI locks with async request handling

```python
async with daemon_state["locks"][ai_name]:
    # Only one request to this AI at a time
    result = await ai_instance.send_prompt(message)
    return result
```

**Characteristics**:

- **Multiple AIs**: Different AIs can process requests concurrently
- **Single AI**: Requests to same AI serialized (prevents browser conflicts)
- **Non-blocking**: Async/await enables efficient resource utilization
- **Fairness**: FIFO queueing per AI (lock acquisition order)

#### 3.3.4 Configuration Management (`daemon/config.py`)

**Pattern**: Default-first with optional override

```python
DEFAULT_CONFIG = {
    "daemon": {
        "host": "127.0.0.1",
        "port": 8000,
        "log_level": "INFO"
    },
    "features": {
        "token_align_frequency": 5000
    }
}
```

**Override Mechanism**:

1. Load defaults
2. Check for `runtime/config/daemon_config.toml`
3. Deep merge TOML values over defaults
4. Return merged configuration

**Benefits**:

- Zero-configuration operation
- Gradual customization (only override specific values)
- Type-safe defaults in code (no parsing errors)

#### 3.3.5 Browser Process Management

**Lifecycle Integration**:

```python
# Startup: Read PID for later shutdown
browser_pid = read_browser_pid()
daemon_state["browser_pid"] = browser_pid

# Shutdown: Graceful termination
if daemon_state.get("browser_pid"):
    stop_browser(daemon_state["browser_pid"])
```

**Stop Logic**:

1. Send `SIGTERM` (graceful shutdown signal)
2. Poll process existence (10 second timeout)
3. If timeout, send `SIGKILL` (force termination)
4. Clean up PID file

**Design Decision**: Daemon owns browser lifecycle because:

- Daemon depends on browser being available
- Centralized shutdown logic (user doesn't manage browser separately)
- Clean resource cleanup on daemon exit

### 3.4 Process Management (`daemon/process_manager.py`)

**Responsibilities**:

- Fork daemon into background process
- Manage PID file lifecycle
- Process status checking
- Clean process termination

**Background Launch Pattern**:

```python
def start_background():
    pid = os.fork()
    if pid == 0:  # Child process
        os.setsid()  # Detach from terminal
        run_daemon()  # Start FastAPI server
    else:  # Parent process
        save_pid(pid)
        print(f"Daemon started with PID {pid}")
```

### 3.5 Daemon State Persistence (Future)

**Current**: State lost on daemon restart (in-memory only)

**Future Enhancement**:

```python
# On shutdown
save_ai_state({
    "claude": {
        "turn_count": instance.get_turn_count(),
        "token_count": instance.get_token_count(),
        # ...
    }
})

# On startup
restore_ai_state(instances)
```

**Storage**: JSON files in `runtime/ai_state/`

---

## 4. CLI Architecture

### 4.1 Command Structure

```
ai-cli-bridge                       # Main executable
├── daemon                          # Daemon management
│   ├── start                      # Launch daemon
│   ├── stop                       # Stop daemon
│   └── status                     # Check daemon status
├── send <ai> <message>            # Send message to AI
├── status <ai>                    # Get AI status
├── doctor                         # System diagnostics
├── open <ai> [--conversation URL] # Open/navigate browser
├── init <ai>                      # Initialize AI profile
├── init-cdp <ai>                  # Initialize CDP connection
└── version                        # Show version
```

### 4.2 Design Pattern: Command Module Pattern

Each command implemented as separate module in `commands/`:

```python
# commands/send_cmd.py
def run(ai_name: str, message: str, wait: bool, timeout: int, 
        json: bool, debug: bool) -> int:
    """Execute send command, return exit code."""
    # 1. Load config
    # 2. Make HTTP request to daemon
    # 3. Format and print response
    # 4. Return 0 (success) or 1 (failure)
```

**Rationale**:

- **Separation**: Each command is independent module
- **Testability**: Functions with clear inputs/outputs
- **Reusability**: Core logic separated from CLI parsing
- **Maintainability**: Add new commands without modifying existing

### 4.3 Main CLI Entry Point (`cli.py`)

**Pattern**: Typer-based declarative CLI

```python
import typer
from .commands import send_cmd, status_cmd, ...

app = typer.Typer(help="ai-cli-bridge — Drive AI web UIs via CDP")

@app.command("send")
def send(
    ai_name: str = typer.Argument(...),
    message: str = typer.Argument(...),
    wait: bool = typer.Option(True, "--wait/--no-wait"),
    ...
):
    """Send message to AI."""
    raise typer.Exit(send_cmd.run(ai_name, message, wait, ...))
```

**Benefits**:

- **Auto-generated Help**: `--help` works for all commands
- **Type Validation**: Typer validates argument types
- **Consistent UX**: Uniform command structure
- **Minimal Boilerplate**: Decorators handle parsing

### 4.4 Command Implementations

#### 4.4.1 `daemon start`

**Flow**:

```
1. Check if daemon already running (PID file exists, process alive)
2. If running: Exit with message
3. Fork background process
4. Child: Start FastAPI server (blocking)
5. Parent: Save PID, print success message, exit
```

**Output**:

```
Starting daemon in the background...
Logs will be written to: /path/to/daemon.log
Daemon started successfully with PID 12345.
```

#### 4.4.2 `daemon stop`

**Flow**:

```
1. Read PID file
2. Check process exists
3. Send SIGTERM
4. Wait for process exit (timeout: 5s)
5. If still running: Send SIGKILL
6. Remove PID file
```

**Output**:

```
Stopping daemon with PID 12345...
Daemon stopped successfully.
```

#### 4.4.3 `daemon status`

**Flow**:

```
1. Check PID file
2. If no PID: Report "Not Running"
3. If PID exists: Make HTTP GET request to /status
4. If request succeeds: Print JSON response
5. If request fails: Report "Running but not responding"
```

**Output**:

```
Daemon status: ✅ Running

Daemon Response:
{
  "daemon": {"version": "2.0.0", "available_ais": ["claude", "gemini", "chatgpt"]},
  "ais": {
    "claude": {"connected": true, "token_count": 150, ...},
    ...
  }
}
```

#### 4.4.4 `send <ai> <message>`

**Flow**:

```
1. Validate AI name
2. Load config (get daemon host/port)
3. Make HTTP POST to /send
   Body: {"target": ai, "prompt": message, "wait_for_response": true, ...}
4. Parse response
5. Format output (plain text or JSON)
6. Return exit code
```

**Output (Plain)**:

```
✓ Sent
  elapsed: 4275 ms
  response:
    Hello! How can I help you today?
```

**Output (JSON)**:

```json
{
  "success": true,
  "snippet": "Hello! How can I help...",
  "markdown": "Full response text...",
  "metadata": {
    "elapsed_ms": 4275,
    "token_count": 150,
    ...
  }
}
```

#### 4.4.5 `status <ai>`

**Flow**:

```
1. Make HTTP GET to /status
2. Extract AI-specific status from response
3. Format and print
```

**Output**:

```
Claude Status:
  Connected: Yes
  Last URL: https://claude.ai/chat/...
  Turn Count: 5
  Token Count: 2,450
  CTAW Usage: 1.23%
  Session Duration: 325.4s
```

#### 4.4.6 `doctor`

**Purpose**: System diagnostics and troubleshooting

**Checks**:

```
1. Python version (>= 3.10)
2. Playwright installation
3. Chromium binary present
4. CDP browser running (port 9223 check)
5. Daemon running (port 8000 check)
6. Runtime directory structure
7. Write permissions
```

**Output**:

```
System Diagnostics:
✓ Python 3.10.12
✓ Playwright installed
✓ Chromium binary found
✓ CDP browser running (port 9223)
✓ Daemon running (port 8000)
✓ Runtime directory exists
✓ Write permissions OK

All checks passed!
```

### 4.5 Error Handling Philosophy

**Principle**: Fail loudly with actionable messages

**Examples**:

```bash
# Daemon not running
$ ai-cli-bridge send claude "Hello"
✗ Error: Daemon not running
  Start it with: ai-cli-bridge daemon start

# Invalid AI name
$ ai-cli-bridge send gpt4 "Hello"
✗ Error: Unknown AI 'gpt4'
  Available: claude, gemini, chatgpt

# Connection timeout
$ ai-cli-bridge send claude "Hello"
✗ Error: Request timeout
  Check daemon logs: tail -f runtime/logs/daemon.log
```

**Exit Codes**:

- `0`: Success
- `1`: User error (invalid arguments, daemon not running, etc.)
- `2`: System error (network failure, unexpected exception)

---

## 5. AI Integration Layer

### 5.1 Class Hierarchy

```
BaseAI (abstract)
  │
  ├─ Methods: send_prompt(), get_status(), reset_session_state()
  ├─ State: turn_count, token_count, message_count, session_start_time
  ├─ Tracking: Token estimation, CTAW usage, session duration
  │
  └── WebAIBase (abstract)
        │
        ├─ Pattern: Stop-button detection (appears → disappears)
        ├─ Methods: _wait_for_response_complete(), _extract_response()
        ├─ Shared: Message sending, response extraction, snippet creation
        │
        ├── ClaudeAI (concrete)
        │     └─ Selectors: INPUT_BOX, STOP_BUTTON, RESPONSE_CONTAINER, ...
        │
        ├── GeminiAI (concrete)
        │     └─ Selectors: INPUT_BOX, STOP_BUTTON, RESPONSE_CONTAINER, ...
        │
        └── ChatGPTAI (concrete)
              ├─ Selectors: INPUT_BOX, STOP_BUTTON, RESPONSE_CONTAINER, ...
              └─ Overrides: _ensure_chat_ready(), _send_message()
```

### 5.2 BaseAI: Foundation Layer

**Responsibilities**:

- CDP connection discovery and management
- Page selection from browser contexts
- Token and turn count tracking
- Session duration monitoring
- CTAW (Context Token Active Window) usage calculation

**Key Methods**:

```python
async def send_prompt(message, wait_for_response, timeout_s):
    """Template method: Connect → Pick Page → Execute → Track"""
    
async def get_status():
    """Return connection state, token counts, CTAW usage"""
    
def reset_session_state():
    """Clear all counters, restart session timer"""
```

**State Management**:

```python
self._turn_count = 0           # Number of prompt-response cycles
self._message_count = 0        # Total messages (user + assistant)
self._token_count = 0          # Estimated tokens consumed
self._ctaw_size = 200000       # Context window size (AI-specific)
self._session_start_time = time.time()
self._message_history = []     # Per-message token tracking
```

**Token Estimation**:

```python
# Rough estimate: 4 characters per token
sent_tokens = len(message) // 4
response_tokens = len(response) // 4
self._token_count += (sent_tokens + response_tokens)

# CTAW usage percentage
ctaw_usage = (self._token_count / self._ctaw_size) * 100
```

### 5.3 WebAIBase: Stop-Button Pattern

**Observation**: Claude, Gemini, and ChatGPT all use a "Stop" button during response generation that disappears when complete.

**Pattern Implementation**:

```python
async def _wait_for_response_complete(page, timeout_s):
    # Wait for stop button to appear (generation started)
    await page.wait_for_selector(STOP_BUTTON, state="visible")
    
    # Poll until stop button disappears (generation complete)
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if await page.locator(STOP_BUTTON).count() == 0:
            return True  # Complete!
        await asyncio.sleep(0.2)
    
    return False  # Timeout
```

**Benefits**:

- **Reliable**: Button visibility is consistent signal
- **Simple**: No complex heuristics or timing assumptions
- **Reusable**: Works for all three AIs with same logic

**Shared Implementations**:

- `_send_message()`: Fill input box, press Enter
- `_extract_response()`: Locate response container, convert to markdown
- `_get_response_count()`: Count existing responses (baseline)
- `_create_snippet()`: Smart truncation with word boundaries

### 5.4 Concrete AI Implementations

#### 5.4.1 ClaudeAI

**File Size**: 60 lines  
**Unique Logic**: None (uses all WebAIBase defaults)

**Configuration**:

```python
BASE_URL = "https://claude.ai"
max_context_tokens = 200000  # 200K token context window
```

**Selectors**:

```python
INPUT_BOX = "div[contenteditable='true']"
STOP_BUTTON = "button[aria-label='Stop response']"
NEW_CHAT_BUTTON = "button[aria-label*='New chat']"
RESPONSE_CONTAINER = ".font-claude-response"
RESPONSE_CONTENT = ".standard-markdown"
```

#### 5.4.2 GeminiAI

**File Size**: 60 lines  
**Unique Logic**: None (uses all WebAIBase defaults)

**Configuration**:

```python
BASE_URL = "https://gemini.google.com"
max_context_tokens = 2000000  # 2M token context window
```

**Selectors**:

```python
INPUT_BOX = "div.ql-editor[aria-label*='prompt']"
STOP_BUTTON = "button[aria-label='Stop response']"
NEW_CHAT_BUTTON = "a.new-chat-button"
RESPONSE_CONTAINER = "div.response-container-content"
RESPONSE_CONTENT = "div.markdown"
```

#### 5.4.3 ChatGPTAI

**File Size**: 90 lines  
**Unique Logic**: Custom `_ensure_chat_ready()` and `_send_message()`

**Why Custom?**: ChatGPT uses a hidden textarea (`display: none`) for accessibility, requiring special handling.

**Configuration**:

```python
BASE_URL = "https://chatgpt.com"
max_context_tokens = 128000  # 128K token context window (GPT-4 Turbo)
```

**Selectors**:

```python
INPUT_BOX = "textarea[name='prompt-textarea']"
STOP_BUTTON = "button[data-testid='stop-button']"
NEW_CHAT_BUTTON = "a[data-testid='create-new-chat-button']"
RESPONSE_CONTAINER = "div[data-message-author-role='assistant']"
RESPONSE_CONTENT = "div.markdown.prose"
```

**Custom Implementations**:

```python
async def _ensure_chat_ready(page):
    # Check textarea exists in DOM (even if hidden)
    textarea = await page.query_selector(INPUT_BOX)
    return textarea is not None

async def _send_message(page, message):
    # Focus hidden textarea, type via keyboard
    textarea = await page.query_selector(INPUT_BOX)
    await textarea.focus()
    await page.keyboard.type(message, delay=10)
    await page.keyboard.press("Enter")
```

### 5.5 Factory Pattern

**Purpose**: Centralized AI instance creation with automatic registration

**Implementation** (`ai/factory.py`):

```python
class AIFactory:
    _registry: Dict[str, type[BaseAI]] = {}
    
    @classmethod
    def register(cls, ai_name: str, ai_class: type[BaseAI]):
        """Register AI implementation"""
        cls._registry[ai_name.lower()] = ai_class
    
    @classmethod
    def create(cls, ai_name: str, config: Dict) -> BaseAI:
        """Create AI instance"""
        ai_class = cls._registry[ai_name.lower()]
        return ai_class(config)
    
    @classmethod
    def import_all_ais(cls):
        """Trigger registration by importing modules"""
        from . import claude, gemini, chatgpt
```

**Registration Pattern**:

```python
# At bottom of claude.py
AIFactory.register("claude", ClaudeAI)
```

**Benefits**:

- **Decoupled**: AI implementations register themselves
- **Dynamic**: New AIs added without modifying factory
- **Type-Safe**: Registry ensures correct types
- **Discoverable**: `list_available()` shows all registered AIs

---

## 6. Data Flow & Process Model

### 6.1 Complete Request Flow

```
┌─────────────────────────────────────────────────────────────┐
│ User executes: ai-cli-bridge send claude "Hello"            │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ↓
┌─────────────────────────────────────────────────────────────┐
│ CLI: Parse arguments, validate                               │
│  - ai_name = "claude"                                        │
│  - message = "Hello"                                         │
│  - Load config (daemon host/port)                            │
└────────────────────────┬────────────────────────────────────┘
                         │ HTTP POST
                         ↓
┌─────────────────────────────────────────────────────────────┐
│ Daemon: Receive request at POST /send                       │
│  - Validate: target="claude", prompt="Hello"                │
│  - Get AI instance: daemon_state["ai_instances"]["claude"]  │
│  - Get lock: daemon_state["locks"]["claude"]                │
└────────────────────────┬────────────────────────────────────┘
                         │ async with lock
                         ↓
┌─────────────────────────────────────────────────────────────┐
│ ClaudeAI: Execute send_prompt()                             │
│  1. Discover CDP URL (ws://127.0.0.1:9223/...)             │
│  2. Connect to CDP browser                                  │
│  3. Pick Claude page from browser contexts                  │
│  4. Execute _execute_interaction()                          │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ↓
┌─────────────────────────────────────────────────────────────┐
│ WebAIBase: _execute_interaction()                           │
│  1. Ensure chat ready (input box visible)                   │
│  2. Get baseline response count                             │
│  3. Send message (fill input, press Enter)                  │
│  4. Wait for response complete (stop button pattern)        │
│  5. Extract response (locate container, convert markdown)   │
│  6. Calculate elapsed time                                  │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ↓
┌─────────────────────────────────────────────────────────────┐
│ ClaudeAI: Update state                                      │
│  - Increment turn_count                                     │
│  - Increment message_count                                  │
│  - Add tokens: (len(prompt) + len(response)) / 4           │
│  - Update timestamp                                         │
│  - Add to message_history                                   │
└────────────────────────┬────────────────────────────────────┘
                         │ Return result
                         ↓
┌─────────────────────────────────────────────────────────────┐
│ Daemon: Build response                                      │
│  - success: true                                            │
│  - snippet: "First 280 chars..."                            │
│  - markdown: "Full response text"                           │
│  - metadata: {turn_count, token_count, elapsed_ms, ...}     │
└────────────────────────┬────────────────────────────────────┘
                         │ HTTP 200 OK
                         ↓
┌─────────────────────────────────────────────────────────────┐
│ CLI: Format and display                                     │
│  ✓ Sent                                                     │
│    elapsed: 4275 ms                                         │
│    response:                                                │
│      Hello! How can I help you today?                       │
└────────────────────────┬────────────────────────────────────┘
                         │ Exit 0
                         ↓
                    [Complete]
```

### 6.2 Browser Session Persistence

```
┌─────────────────────────────────────────────────────────────┐
│ Initial Setup (First Time)                                  │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ↓
         LaunchCDP.sh executed
                         │
                         ↓
┌─────────────────────────────────────────────────────────────┐
│ Chromium launches with:                                     │
│  - User data dir: runtime/profiles/multi_ai_cdp            │
│  - CDP port: 9223                                           │
│  - Opens: claude.ai/new, gemini.google.com, chatgpt.com    │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ↓
┌─────────────────────────────────────────────────────────────┐
│ User manually logs in to all 3 AIs                         │
│  - Cookies saved to: Default/Cookies (SQLite)              │
│  - Local storage saved                                      │
│  - Session tokens persisted                                 │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ↓
         [Browser running with authenticated sessions]
                         │
              (User stops browser)
                         ↓
┌─────────────────────────────────────────────────────────────┐
│ Browser closes gracefully                                   │
│  - All cookies flushed to disk                             │
│  - Profile data saved                                       │
└────────────────────────┬────────────────────────────────────┘
                         │
              (Later: LaunchCDP.sh again)
                         ↓
┌─────────────────────────────────────────────────────────────┐
│ Chromium launches with same user data dir                  │
│  - Reads cookies from Default/Cookies                      │
│  - Restores session tokens                                  │
│  - Opens 3 fresh chat tabs                                  │
│  - Already authenticated (no login required!)               │
└─────────────────────────────────────────────────────────────┘
```

**Key Files**:

- `Default/Cookies`: SQLite database with authentication cookies
- `Default/Local Storage/`: Web storage data
- `Default/Preferences`: Browser settings and state

### 6.3 Concurrent Request Handling

**Scenario**: Multiple commands executed simultaneously

```
Time →

t=0s:  CLI1: send claude "Query 1"
       CLI2: send gemini "Query 2"
       CLI3: send claude "Query 3"

┌──────────────────────────────────────────────────────────┐
│                      Daemon                               │
│                                                           │
│  Thread 1: Handle CLI1                                   │
│    ↓                                                      │
│    Acquire claude_lock ✓                                 │
│    Execute Claude interaction (4s)                       │
│    Release claude_lock                                   │
│                                                           │
│  Thread 2: Handle CLI2 (parallel!)                       │
│    ↓                                                      │
│    Acquire gemini_lock ✓                                 │
│    Execute Gemini interaction (6s)                       │
│    Release gemini_lock                                   │
│                                                           │
│  Thread 3: Handle CLI3                                   │
│    ↓                                                      │
│    Try acquire claude_lock ✗ (blocked by Thread 1)      │
│    Wait in queue...                                      │
│    (Thread 1 releases lock at t=4s)                      │
│    Acquire claude_lock ✓                                 │
│    Execute Claude interaction (4s)                       │
│    Release claude_lock                                   │
└──────────────────────────────────────────────────────────┘

Timeline:
t=0s:  CLI1 starts, CLI2 starts (parallel), CLI3 waits
t=4s:  CLI1 completes, CLI3 starts
t=6s:  CLI2 completes
t=8s:  CLI3 completes
```

**Guarantees**:

- Different AIs never block each other
- Same AI serialized (prevents browser race conditions)
- FIFO ordering per AI (fairness)

---

## 7. Security & Privacy

### 7.1 Threat Model

**Assets to Protect**:

- Authentication cookies (AI login sessions)
- Conversation history (stored in browser)
- API communication (CLI ↔ Daemon)
- Process control (daemon lifecycle)

**Threat Actors**:

- Local unprivileged users
- Malicious local processes
- Network attackers (if exposed beyond localhost)

### 7.2 Security Measures

#### 7.2.1 Localhost-Only Binding

**Implementation**:

```python
# Daemon binds to 127.0.0.1 (loopback only)
uvicorn.run(app, host="127.0.0.1", port=8000)
```

**Protection**: Prevents network access to daemon API

**Risk Mitigation**: No remote exploitation possible without first compromising host

#### 7.2.2 Filesystem Permissions

**Runtime Directory**:

```bash
runtime/                    # 700 (rwx------)
  profiles/                 # 700
    multi_ai_cdp/           # 700
      Default/Cookies       # 600 (rw-------)
```

**Protection**: Only owner can read authentication cookies

**Implementation**: Set during directory creation in `config.py`

#### 7.2.3 PID File Security

**Risk**: Malicious process could read PID, send signals to daemon/browser

**Mitigation**:

- PID files in protected runtime directory (700 permissions)
- Process ownership checked before signal sending
- Stale PID files detected and cleaned

#### 7.2.4 No Authentication on Daemon API

**Current State**: No API keys, tokens, or authentication

**Rationale**:

- Localhost-only binding provides network isolation
- User owns both CLI and daemon (same UID)
- Adding auth adds complexity without significant benefit in single-user scenario

**Future Consideration**: If daemon exposed remotely, add:

- Token-based authentication
- TLS encryption
- Rate limiting

### 7.3 Privacy Considerations

#### 7.3.1 Data Retention

**What's Stored**:

- Browser cookies (indefinitely, until browser profile deleted)
- Daemon logs (append-only, no automatic rotation)
- No conversation transcripts stored by ai-cli-bridge (only in browser)

**User Control**:

```bash
# Clear all sessions
rm -rf runtime/profiles/multi_ai_cdp/

# Clear logs
rm runtime/logs/daemon.log

# Clear all runtime data
rm -rf runtime/
```

#### 7.3.2 Logging Practices

**What's Logged**:

- Daemon startup/shutdown events
- AI instance creation
- Request timestamps and AI targets
- Error messages and stack traces

**What's NOT Logged**:

- Message content (prompts or responses)
- Authentication tokens or cookies
- Personal identifying information

**Log File**: `runtime/logs/daemon.log` (user-readable only)

### 7.4 Secure Coding Practices

**Input Validation**:

```python
# All user inputs validated before processing
if ai_name not in daemon_state["ai_instances"]:
    raise HTTPException(status_code=404, detail="Unknown AI")
```

**Exception Handling**:

```python
# Never expose internal details in error messages
try:
    result = await ai_instance.send_prompt(...)
except Exception as e:
    # Log full error internally
    logger.error(f"Internal error: {e}", exc_info=True)
    # Return generic message to user
    raise HTTPException(status_code=500, detail="Internal error")
```

**Resource Cleanup**:

```python
# Always clean up resources, even on error
try:
    remote = await playwright.connect_over_cdp(url)
    # ... use remote ...
finally:
    if remote:
        await remote.close()
    await playwright.stop()
```

---

## 8. Performance Characteristics

### 8.1 Latency Analysis

**CLI Command Overhead**:

```
User invocation → CLI parsing → HTTP request → Response → Display
     <1ms           1-2ms         2-5ms        (AI time)    1ms
```

**Total Overhead**: ~5-10ms (negligible compared to AI response time)

**AI Response Times** (measured):

- **Claude**: 3-5 seconds (typical), 10+ seconds (long responses)
- **Gemini**: 3-15 seconds (varies significantly with response length)
- **ChatGPT**: 1-8 seconds (fastest, but can vary)

**Why Variations?**:

- Network latency to AI service
- Response length (longer = more time)
- AI model load (peak times slower)
- Browser rendering time (markdown conversion)

### 8.2 Resource Usage

**Memory**:

- Daemon process: ~50-80 MB (Python + FastAPI)
- AI instances: ~10 MB each (3x = 30 MB)
- Browser process: ~200-400 MB (Chromium + 3 tabs)
- **Total**: ~300-500 MB

**CPU**:

- Idle daemon: <1% CPU
- During AI interaction: 5-15% CPU (browser automation)
- Browser rendering: 10-30% CPU (during AI response generation)

**Disk**:

- Source code: ~200 KB
- Dependencies (venv): ~150 MB (Playwright, FastAPI, etc.)
- Browser profile: ~50-100 MB (cookies, cache, storage)
- Logs: Grows unbounded (recommend periodic rotation)

### 8.3 Scalability Limits

**Concurrent Requests**:

- **Per AI**: 1 (serialized by lock)
- **Total**: 3 (one per AI, parallelized)

**Why Limited?**:

- Browser tab interaction not thread-safe
- CDP protocol doesn't support concurrent control of same tab

**Future Enhancement**: Multi-profile architecture

```
Browser 1: Claude session 1
Browser 2: Claude session 2
Browser 3: Claude session 3
...
```

Enables true parallelism per AI, but increases resource usage.

### 8.4 Optimization Strategies

**Current Optimizations**:

1. **Persistent Connections**: CDP WebSocket stays open (no reconnection overhead)
2. **Instance Reuse**: AI objects persist across requests (no re-initialization)
3. **Async I/O**: Non-blocking HTTP and browser automation
4. **Minimal Parsing**: Direct markdown extraction (no heavy HTML parsing)

**Future Optimizations**:

1. **Response Streaming**: Stream AI responses token-by-token (lower perceived latency)
2. **Connection Pooling**: Multiple browsers per AI (higher concurrency)
3. **Caching**: Cache AI responses for identical prompts (faster repeated queries)
4. **Preloading**: Keep input focused, reduce activation time

---

## 9. Future Roadmap

### 9.1 Phase 4: Enhanced Session Management

**Timeline**: Q1 2026  
**Status**: Design Phase

#### 9.1.1 Conversation Navigation

**Feature**: List and switch between previous conversations

**CLI Commands**:

```bash
# List all conversations for an AI
ai-cli-bridge session list claude
# Output: 
#   1. [2025-10-15] "Discuss Python architecture" (47 messages)
#   2. [2025-10-14] "Debug async code" (23 messages)
#   ...

# Switch to specific conversation
ai-cli-bridge session switch claude <conversation-id>
# Navigates browser to that conversation URL

# Get current conversation info
ai-cli-bridge session current claude
# Output: URL, message count, started time
```

**Implementation**:

- Scrape conversation list from AI sidebar
- Extract conversation IDs and metadata
- Navigate to conversation URL via CDP
- Reset daemon state tracking to match conversation

**Challenges**:

- Each AI has different conversation list structure
- Conversation IDs format varies (Claude: UUID, ChatGPT: path segment)
- Pagination for users with many conversations

#### 9.1.2 Session State Persistence

**Feature**: Preserve session state across daemon restarts

**Implementation**:

```python
# On daemon shutdown
save_state({
    "claude": {
        "turn_count": 10,
        "token_count": 5000,
        "session_start_time": 1729267890,
        "conversation_url": "https://claude.ai/chat/abc123"
    }
})

# On daemon startup
state = load_state()
for ai_name, ai_instance in ai_instances.items():
    restore_state(ai_instance, state[ai_name])
```

**Storage**: JSON files in `runtime/ai_state/`

**Benefits**:

- Accurate token tracking across restarts
- Resume conversations seamlessly
- Historical session data for analytics

#### 9.1.3 Multi-Turn Context Optimization

**Feature**: Intelligent context window management

**Strategies**:

1. **Summarization**: Automatically summarize old messages when approaching context limit
2. **Pruning**: Remove less relevant messages (keep first/last N, summarize middle)
3. **Warning**: Alert user when 80% context consumed

**CLI Command**:

```bash
# Show context usage with breakdown
ai-cli-bridge session analyze claude
# Output:
#   Context Usage: 185,234 / 200,000 tokens (92.6%)
#   Breakdown:
#     System prompt: 1,234 tokens
#     Messages 1-10: 45,000 tokens
#     Messages 11-20: 89,000 tokens (oldest, candidate for summarization)
#     Messages 21-30: 50,000 tokens (most recent)
#   
#   Recommendation: Summarize messages 11-20 (save ~70K tokens)
```

### 9.2 Phase 5: File Operations

**Timeline**: Q2 2026  
**Status**: Planning

#### 9.2.1 File Upload Support

**Feature**: Upload files to AI conversations

**CLI Command**:

```bash
# Upload file to current conversation
ai-cli-bridge file upload claude /path/to/document.pdf
ai-cli-bridge file upload claude /path/to/image.png --message "Analyze this"

# Upload multiple files
ai-cli-bridge file upload gemini file1.py file2.py file3.py
```

**Implementation**:

- Locate file upload button/input in AI interface (AI-specific selectors)
- Use Playwright file chooser API: `page.set_input_files()`
- Wait for upload confirmation
- Optionally send follow-up message

**Challenges**:

- Each AI has different upload UI
- File type restrictions vary
- Upload progress tracking (large files)
- Error handling (file too large, unsupported type)

#### 9.2.2 File Download Support

**Feature**: Download AI-generated files (code, documents, images)

**CLI Command**:

```bash
# List downloadable artifacts in conversation
ai-cli-bridge file list claude
# Output:
#   1. script.py (Python, 1.2 KB)
#   2. diagram.svg (Image, 45 KB)
#   3. report.md (Markdown, 8 KB)

# Download specific file
ai-cli-bridge file download claude 1 --output ./script.py

# Download all files
ai-cli-bridge file download-all claude --directory ./claude-files/
```

**Implementation**:

- Detect downloadable artifacts (code blocks, images, documents)
- Extract content via DOM manipulation
- Save to local filesystem with appropriate name/extension
- Handle binary vs. text files appropriately

**Use Cases**:

- Save AI-generated code snippets
- Download diagrams and visualizations
- Archive conversation artifacts

#### 9.2.3 Artifact Management

**Feature**: Track and manage AI-generated artifacts

**Storage**:

```
runtime/artifacts/
  claude/
    2025-10-18_142033_script.py
    2025-10-18_143015_diagram.svg
  gemini/
    ...
```

**CLI Commands**:

```bash
# List all saved artifacts
ai-cli-bridge artifacts list

# Search artifacts
ai-cli-bridge artifacts search "Python script"

# Clean old artifacts
ai-cli-bridge artifacts clean --older-than 30days
```

### 9.3 Phase 6: User Experience Enhancements

**Timeline**: Q3 2026  
**Status**: Conceptual

#### 9.3.1 Intelligent Error Recovery

**Feature**: Automatic retry and recovery from transient failures

**Scenarios**:

**1. Network Timeout**:

```
Current: ✗ Error: Request timeout
Enhanced: ⚠ Network timeout, retrying (attempt 1/3)...
          ✓ Succeeded on retry
```

**2. Browser Not Responding**:

```
Current: ✗ Error: CDP not responding
Enhanced: ⚠ Browser unresponsive, attempting recovery...
          → Restarting browser process...
          → Reconnecting CDP...
          ✓ Recovery successful, retrying original request
```

**3. AI Interface Changed**:

```
Current: ✗ Error: Element not found
Enhanced: ⚠ UI element missing (possible interface update)
          → Attempting alternative selectors...
          ✓ Found element with fallback selector
          ℹ Please report: UI may have changed
```

**Implementation**:

- Exponential backoff retry logic
- Multiple selector fallbacks per element
- Browser process health monitoring and auto-restart
- User-friendly error messages with recovery actions

#### 9.3.2 Progress Indicators

**Feature**: Real-time progress feedback for long operations

**Example**:

```bash
$ ai-cli-bridge send claude "Write a comprehensive guide..."
⏳ Sending prompt...
⏳ Waiting for AI response...
   ⣾ Generating... (5s)
   ⣷ Generating... (10s)
   ⣯ Generating... (15s)
✓ Response received (18.3s)

  The comprehensive guide begins...
```

**Implementation**:

- Spinner animation during wait
- Elapsed time display
- Cancellation support (Ctrl+C)

#### 9.3.3 Better Error Messages

**Current**:

```
✗ Error: send_failed
```

**Enhanced**:

```
✗ Error: Failed to send message to Claude

  Possible causes:
    • Input box not found (UI may have changed)
    • Browser not responding
    • Network connectivity issue

  Troubleshooting steps:
    1. Check browser is running: ./LaunchCDP.sh
    2. Verify daemon is running: ai-cli-bridge daemon status
    3. Check logs: tail -f runtime/logs/daemon.log
    4. Try restarting daemon: ai-cli-bridge daemon stop && ai-cli-bridge daemon start

  For more help, see: https://docs.ai-cli-bridge.io/troubleshooting
```

**Design Principles**:

- **Explain What Happened**: Clear description of failure
- **Suggest Why**: Possible root causes
- **Show How to Fix**: Concrete action steps
- **Provide Resources**: Link to documentation

#### 9.3.4 Configuration Wizard

**Feature**: Interactive first-time setup

**Flow**:

```bash
$ ai-cli-bridge init
Welcome to AI-CLI-Bridge!

This wizard will help you set up the system.

[1/5] Install Playwright...
  ✓ Playwright already installed

[2/5] Install Chromium browser...
  ⏳ Downloading Chromium (120 MB)...
  ✓ Chromium installed

[3/5] Launch browser...
  ✓ Browser launched on port 9223

[4/5] Configure AI logins...
  ℹ Browser opened. Please log in to:
    • Claude (https://claude.ai)
    • Gemini (https://gemini.google.com)
    • ChatGPT (https://chatgpt.com)
  
  Press Enter when done...
  ✓ All AIs authenticated

[5/5] Start daemon...
  ✓ Daemon started (PID 12345)

✅ Setup complete! Try:
   ai-cli-bridge send claude "Hello, world!"
```

**Benefits**:

- Guided setup for new users
- Reduces configuration errors
- Validates each step before proceeding

### 9.4 Phase 7: Graphical User Interface

**Timeline**: Q4 2026  
**Status**: Design Phase

#### 9.4.1 Architecture Overview

```
┌──────────────────────────────────────────────────────────┐
│                  Desktop Application                      │
│               (Electron or Tauri-based)                   │
└────────────────────────┬─────────────────────────────────┘
                         │ HTTP/REST API
                         ↓
┌──────────────────────────────────────────────────────────┐
│              Existing Daemon (unchanged)                  │
│  All CLI functionality exposed via REST API               │
└──────────────────────────────────────────────────────────┘
```

**Design Principle**: GUI is a client of the daemon, same as CLI. No duplicate logic.

#### 9.4.2 Core Features

**1. Multi-AI Chat Interface**:

```
┌─────────────────────────────────────────────────────────┐
│ AI-CLI-Bridge                                    [- □ ×] │
├────────────┬────────────────────────────────────────────┤
│            │                                             │
│  Claude    │  You: What is the capital of France?       │
│  Gemini    │                                             │
│  ChatGPT   │  Claude: The capital of France is Paris.   │
│            │         It is located in the north-central  │
│ Sessions   │         part of the country...              │
│  └ Active  │                                             │
│  └ Recent  │  You: Tell me more                          │
│            │                                             │
│            │  Claude: Paris is one of the most visited  │
│            │         cities in the world...              │
│            │                                             │
│            │  ┌────────────────────────────────────────┐ │
│            │  │ Type your message...              [Send]│ │
│            │  └────────────────────────────────────────┘ │
└────────────┴────────────────────────────────────────────┘
```

**2. Session Management**:

- Sidebar: List of conversations per AI
- Quick switch between conversations
- Search conversations by content or date
- Archive/delete old conversations

**3. Status Dashboard**:

```
┌─────────────────────────────────────────────────────────┐
│ System Status                                           │
├─────────────────────────────────────────────────────────┤
│                                                          │
│ Daemon: ● Running (PID 12345)                          │
│ Browser: ● Running (PID 12346)                          │
│                                                          │
│ ┌────────────────────────────────────────────────────┐ │
│ │ Claude      Connected   Token Usage: 1.2%  [Reset] │ │
│ │ Gemini      Connected   Token Usage: 0.5%  [Reset] │ │
│ │ ChatGPT     Connected   Token Usage: 3.8%  [Reset] │ │
│ └────────────────────────────────────────────────────┘ │
│                                                          │
│ [View Logs]  [Restart Daemon]  [Settings]              │
└─────────────────────────────────────────────────────────┘
```

**4. Settings Panel**:

- Daemon configuration (host, port, log level)
- AI-specific settings (context window, timeouts)
- Theme selection (light/dark)
- Keyboard shortcuts

**5. File Management**:

- Drag-and-drop file upload
- Visual artifact gallery
- Preview code/images inline
- One-click download of AI-generated files

#### 9.4.3 Technology Stack Options

**Option A: Electron + React**

- **Pros**: Rich ecosystem, mature tooling, cross-platform
- **Cons**: Large bundle size (~100MB), high memory usage
- **Best For**: Feature-rich desktop application

**Option B: Tauri + Svelte**

- **Pros**: Smaller bundle (~10MB), lower memory, native performance
- **Cons**: Smaller ecosystem, newer technology
- **Best For**: Lightweight, modern desktop application

**Option C: Web-Based (Browser Extension)**

- **Pros**: No installation, universal access
- **Cons**: Browser security restrictions, limited native integration
- **Best For**: Simple use cases, maximum portability

**Recommendation**: Tauri + Svelte for optimal size/performance balance

#### 9.4.4 Implementation Strategy

**Phase 1: MVP (Minimum Viable Product)**

- Single AI chat interface
- Basic send/receive functionality
- Status display
- Settings panel

**Phase 2: Feature Parity**

- All CLI commands exposed in GUI
- Multi-AI tab support
- Session management
- File upload/download

**Phase 3: Enhanced UX**

- Syntax highlighting for code
- Markdown rendering with LaTeX support
- Real-time typing indicators
- Conversation search and filter
- Export conversations (PDF, Markdown)

**Phase 4: Advanced Features**

- Side-by-side AI comparison mode
- Conversation templates
- Snippet library
- Analytics dashboard (token usage over time)

#### 9.4.5 API Extensions Required

**New Endpoints**:

```python
# Streaming responses
GET /stream/{ai_name}
# Server-Sent Events for real-time updates

# Conversation management
GET /conversations/{ai_name}
POST /conversations/{ai_name}/switch
DELETE /conversations/{ai_name}/{conversation_id}

# File operations
POST /file/upload/{ai_name}
GET /file/download/{ai_name}/{file_id}
GET /file/list/{ai_name}

# Settings
GET /settings
PUT /settings
```

---

## 10. Appendices

### 10.1 Appendix A: Configuration Reference

#### 10.1.1 Daemon Configuration File

**Location**: `runtime/config/daemon_config.toml`

**Format**: TOML (Tom's Obvious, Minimal Language)

**Full Example**:

```toml
[daemon]
host = "127.0.0.1"          # Bind address (localhost only recommended)
port = 8000                 # HTTP port
log_level = "INFO"          # Logging verbosity: DEBUG, INFO, WARNING, ERROR

[features]
token_align_frequency = 5000  # Token estimation sync interval (future use)

[ai.claude]
max_context_tokens = 200000   # Override default context window
base_url = "https://claude.ai"  # Override base URL (for testing)

[ai.gemini]
max_context_tokens = 2000000

[ai.chatgpt]
max_context_tokens = 128000
```

**Usage**: Only specify values you want to override. All have sensible defaults.

#### 10.1.2 Environment Variables

**Supported Variables**:

```bash
# Override CDP WebSocket URL (bypass discovery)
export AI_CLI_BRIDGE_CDP_URL="ws://127.0.0.1:9223/devtools/browser/abc123"

# Override daemon host/port (for CLI client)
export AI_CLI_BRIDGE_DAEMON_HOST="127.0.0.1"
export AI_CLI_BRIDGE_DAEMON_PORT="8000"

# Enable debug mode (verbose logging)
export AI_CLI_BRIDGE_DEBUG="1"
```

**Priority**: Environment variables > Config file > Defaults

### 10.2 Appendix B: Troubleshooting Guide

#### 10.2.1 Common Issues

**Issue**: `✗ Error: Daemon not running`

**Solution**:

```bash
# Check daemon status
ai-cli-bridge daemon status

# If not running, start it
ai-cli-bridge daemon start

# If start fails, check logs
tail -f runtime/logs/daemon.log
```

---

**Issue**: `✗ Error: CDP browser not running`

**Solution**:

```bash
# Launch CDP browser
./LaunchCDP.sh

# Verify it's running
curl http://127.0.0.1:9223/json/version

# Check browser process
ps aux | grep chromium | grep 9223
```

---

**Issue**: `✗ Error: chat_not_ready`

**Solution**:

- Open the CDP browser manually
- Navigate to the AI's page
- Verify you're logged in
- Check if CAPTCHA is present (solve manually)
- Ensure page loaded completely

---

**Issue**: Response extraction fails (empty response)

**Solution**:

- AI interface may have changed (selectors outdated)
- Check GitHub for updates
- Run with `--debug` flag to see detailed logs
- Report issue with browser console screenshot

---

**Issue**: High memory usage

**Solution**:

```bash
# Restart daemon to clear accumulated state
ai-cli-bridge daemon stop
ai-cli-bridge daemon start

# Clean browser profile to reduce size
rm -rf runtime/profiles/multi_ai_cdp/Default/Cache/
```

---

**Issue**: Stale PID file errors

**Solution**:

```bash
# Manually clean PID files
rm runtime/daemon.pid
rm runtime/browser.pid

# Restart system
./LaunchCDP.sh
ai-cli-bridge daemon start
```

#### 10.2.2 Debug Mode

**Enable Debug Output**:

```bash
# For single command
ai-cli-bridge send claude "Test" --debug

# For daemon (via environment)
export AI_CLI_BRIDGE_DEBUG=1
ai-cli-bridge daemon start

# View detailed logs
tail -f runtime/logs/daemon.log
```

**Debug Output Includes**:

- CDP connection details
- Page navigation events
- Selector query results
- Element interaction timing
- Response extraction process

#### 10.2.3 Log Analysis

**Key Log Patterns**:

```
# Successful interaction
[ClaudeAI] CDP connected via discovered: ws://...
[ClaudeAI] Operating on page: https://claude.ai/chat/...
[ClaudeAI] Message sent
[ClaudeAI] Stop button appeared
[ClaudeAI] Stop button disappeared - complete
[ClaudeAI] Extracted - snippet: 280 chars

# Failed interaction
[ClaudeAI] CDP connected via discovered: ws://...
[ClaudeAI] No suitable page found
ERROR: AI interaction failed: no_page

# Browser crash
ERROR: CDP endpoint did not become ready after 15 seconds
ERROR: Browser process exited unexpectedly (code: 139)
```

### 10.3 Appendix C: Development Guide

#### 10.3.1 Project Setup for Development

**Clone and Setup**:

```bash
# Clone repository
git clone https://github.com/your-org/ai-cli-bridge.git
cd ai-cli-bridge

# Create shared venv (if not exists)
python3.10 -m venv ../shared/runtime/venv

# Activate venv
source ../shared/scripts/activate.sh

# Install in editable mode
pip install -e .

# Install Playwright browsers
playwright install chromium

# Launch browser
./LaunchCDP.sh

# Start daemon in foreground (for development)
python -m ai_cli_bridge.daemon.main
```

#### 10.3.2 Adding a New AI

**Step-by-Step**:

1. **Create AI Module** (`src/ai_cli_bridge/ai/newai.py`):

```python
"""NewAI-specific AI implementation."""

from typing import Dict, Any
from playwright.async_api import Page
from .web_base import WebAIBase
from .factory import AIFactory

class NewAI(WebAIBase):
    BASE_URL = "https://newai.example.com"
    CDP_PORT = 9223
    
    @classmethod
    def get_default_config(cls) -> Dict[str, Any]:
        return {
            "ai_target": "newai",
            "base_url": cls.BASE_URL,
            "cdp": {"port": cls.CDP_PORT},
            "max_context_tokens": 100000
        }
    
    @property
    def INPUT_BOX(self) -> str:
        return "textarea#prompt"
    
    @property
    def STOP_BUTTON(self) -> str:
        return "button[aria-label='Stop']"
    
    @property
    def NEW_CHAT_BUTTON(self) -> str:
        return "button.new-chat"
    
    @property
    def RESPONSE_CONTAINER(self) -> str:
        return "div.message"
    
    @property
    def RESPONSE_CONTENT(self) -> str:
        return "div.content"

AIFactory.register("newai", NewAI)
```

2. **Update Factory** (`src/ai_cli_bridge/ai/factory.py`):

```python
@classmethod
def import_all_ais(cls):
    try:
        from . import claude, gemini, chatgpt, newai  # Add newai
    except ImportError as e:
        print(f"Warning: Could not import AI: {e}")
```

3. **Update LaunchCDP.sh** (add URL):

```bash
NEWAI_URL="https://newai.example.com/"
# Add to launch command
```

4. **Test**:

```bash
ai-cli-bridge daemon stop
./LaunchCDP.sh
ai-cli-bridge daemon start
ai-cli-bridge send newai "Hello"
```

#### 10.3.3 Running Tests (Future)

**Test Structure**:

```
tests/
├── unit/
│   ├── test_factory.py
│   ├── test_base_ai.py
│   └── test_config.py
├── integration/
│   ├── test_daemon.py
│   ├── test_claude.py
│   └── test_cli.py
└── e2e/
    └── test_full_flow.py
```

**Run Tests**:

```bash
# Unit tests (fast, no browser required)
pytest tests/unit/

# Integration tests (requires daemon)
pytest tests/integration/

# E2E tests (full system, slow)
pytest tests/e2e/

# All tests with coverage
pytest --cov=ai_cli_bridge tests/
```

### 10.4 Appendix D: API Reference

#### 10.4.1 Daemon REST API

**Base URL**: `http://127.0.0.1:8000`

---

**`GET /`**

Health check endpoint.

**Response**:

```json
{
  "service": "ai-cli-bridge-daemon",
  "version": "2.0.0",
  "status": "running"
}
```

---

**`GET /status`**

Get system and AI status.

**Response**:

```json
{
  "daemon": {
    "version": "2.0.0",
    "available_ais": ["claude", "gemini", "chatgpt"]
  },
  "ais": {
    "claude": {
      "ai_target": "claude",
      "connected": true,
      "cdp_source": "discovered",
      "cdp_url": "ws://127.0.0.1:9223/devtools/browser/...",
      "last_page_url": "https://claude.ai/chat/...",
      "message_count": 10,
      "turn_count": 10,
      "token_count": 2450,
      "ctaw_size": 200000,
      "ctaw_usage_percent": 1.23,
      "session_duration_s": 325.4,
      "debug_enabled": false
    },
    "gemini": { /* similar */ },
    "chatgpt": { /* similar */ }
  }
}
```

---

**`POST /send`**

Send message to AI.

**Request Body**:

```json
{
  "target": "claude",
  "prompt": "Hello, world!",
  "wait_for_response": true,
  "timeout_s": 120,
  "debug": false
}
```

**Response**:

```json
{
  "success": true,
  "snippet": "Hello! I'm Claude, an AI assistant...",
  "markdown": "Full response text in markdown format...",
  "metadata": {
    "page_url": "https://claude.ai/chat/...",
    "elapsed_ms": 4275,
    "waited": true,
    "ws_source": "discovered",
    "timestamp": "2025-10-18T14:23:45Z",
    "turn_count": 1,
    "message_count": 1,
    "token_count": 150,
    "ctaw_usage_percent": 0.075,
    "ctaw_size": 200000,
    "session_duration_s": 45.2
  }
}
```

**Error Response** (400):

```json
{
  "detail": "Request must include 'target' and 'prompt'"
}
```

**Error Response** (404):

```json
{
  "detail": "AI target 'gpt4' not found. Available: claude, gemini, chatgpt"
}
```

**Error Response** (500):

```json
{
  "detail": "Error during interaction: chat_not_ready"
}
```

---

**`POST /session/new/{ai_name}`**

Reset AI session state.

**Parameters**:

- `ai_name` (path): AI identifier (claude, gemini, chatgpt)

**Response**:

```json
{
  "success": true,
  "message": "New session started for 'claude'",
  "turn_count": 0,
  "token_count": 0
}
```

### 10.5 Appendix E: Glossary

**AI**: Artificial Intelligence (Claude, Gemini, ChatGPT)

**CDP**: Chrome DevTools Protocol - Remote debugging protocol for Chromium-based browsers

**CTAW**: Current Active Token Window - The portion of the AI's context window currently in use

**Context Window**: Maximum number of tokens an AI can process in a single conversation

**Daemon**: Long-running background process that maintains state and provides services

**Factory Pattern**: Creational design pattern for object instantiation

**Playwright**: Browser automation framework for testing and scraping

**Session**: A conversation with an AI, tracked from start to finish

**Stop Button Pattern**: UI pattern where a "Stop" button appears during AI response generation and disappears when complete

**Token**: Unit of text processed by AI (roughly 4 characters in English)

**Turn**: One prompt-response cycle (user sends message, AI responds)

**WebSocket**: Bi-directional communication protocol over TCP

### 10.6 Appendix F: Version History

#### Version 2.0.0 (October 18, 2025)

**Major Changes**:

- Complete architecture redesign with daemon pattern
- Unified AI abstraction layer (BaseAI → WebAIBase → ConcreteAI)
- Token tracking and CTAW usage monitoring
- Persistent browser sessions with cookie management
- 37% code reduction through DRY principles
- ChatGPT integration (joins Claude and Gemini)

**Breaking Changes**:

- Removed `browser_manager.py` (replaced by CDP scripts)
- Configuration file format changed (now TOML)
- CLI command structure updated
- All commands now go through daemon (no direct browser control)

**Migration Guide from 1.x**:

1. Stop any running v1.x processes
2. Backup `runtime/` directory (optional)
3. Install v2.0.0
4. Launch CDP browser: `./LaunchCDP.sh`
5. Start daemon: `ai-cli-bridge daemon start`
6. Test: `ai-cli-bridge send claude "Hello"`

#### Version 1.3.1 (Previous)

- Direct browser control (no daemon)
- Separate browser manager per AI
- Basic CDP integration
- Claude and Gemini support only

---
## Conclusion

AI-CLI-Bridge v2.0.0 represents a significant evolution in architecture and capability. The daemon-based design provides a solid foundation for future enhancements while maintaining simplicity and reliability. The single-tree philosophy ensures portability and ease of deployment, while the DRY principles enable rapid feature development with minimal code duplication.

The roadmap outlined in this document provides a clear path forward, with each phase building on the robust foundation established in v2.0.0. From enhanced session management to file operations to a graphical user interface, the system is designed to grow while maintaining its core principles of simplicity, efficiency, and user-centricity.
### Key Takeaways

1. **Architecture**: Client-daemon pattern with persistent connections
2. **Philosophy**: Single-tree, DRY, separation of concerns, fail-safe defaults
3. **Performance**: Sub-10ms overhead, efficient resource usage
4. **Security**: Localhost-only, filesystem isolation, minimal attack surface
5. **Extensibility**: Clean abstractions enable rapid AI integration
6. **Future**: Session management, file operations, GUI, enhanced UX

---
**Document Prepared By**: AI-CLI-Bridge Team  
**Last Updated**: October 18, 2025  
**Document Version**: 1.0  
**Next Review**: January 2026# AI-CLI-Bridge v2.0.0
