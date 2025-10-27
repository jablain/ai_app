
# AI-CLI-Bridge Design Specs V1.3

## 1. Overview

**AI-CLI-Bridge** is a command-line tool that automates interactions with AI web interfaces (e.g., ChatGPT, Claude, Gemini) through a **visible Playwright-controlled browser**. Its purpose is to provide deterministic, scriptable control of AI chat UIs while preserving full human observability.

## 2. Guiding Principles

- **Headed-only operation:** Browser is always visible; headless mode is forbidden.
- **Deterministic simplicity:** All automation must be human-inspectable.
- **User-centric persistence:** Once logged in, the user should never need to re-authenticate manually unless cookies expire or profile data is deleted.
- **Single-root filesystem policy:** All files live strictly under `~/.ai_cli_bridge`.
- **Explicit version scoping:** v1.x prioritizes stability; advanced context features deferred to v2.

## 3. Runtime Environment Requirements

- Must run inside a **graphical display session** (X11, Wayland, or equivalent).
- Execution in CI/headless contexts is **forbidden**.
- On startup, the CLI checks for display availability using Playwright's built-in detection and aborts with an explicit error if absent.

**Error example:**

```
E001: No graphical display detected. AI-CLI-Bridge cannot run headless.
```

## 4. Architecture Summary

### Components

|Component|Description|
|---|---|
|**CLI Core**|Parses user commands, routes to Playwright automation layer.|
|**Playwright Runtime**|Controls a visible Chromium instance per AI target.|
|**Profile Manager**|Maintains persistent authenticated profiles per AI.|
|**Config Store**|JSON configs under `~/.ai_cli_bridge/config/`.|
|**Logger**|Structured log output under `~/.ai_cli_bridge/logs/`.|
|**Lock Manager**|Prevents concurrent sessions via lock files.|

### Directory Structure

```
~/.ai_cli_bridge/
├── config/
│   └── claude.json
├── data/
│   └── profiles/
│       └── claude/
├── cache/
│   └── locks/
│       └── claude.lock
└── logs/
    └── session_2025-10-08_14-23-11.log
```

**Directory Purposes:**

- **`config/`**: JSON configuration files for each AI target
- **`data/`**: Persistent data including Playwright browser profiles
- **`cache/`**: Temporary files, lock files, and session-scoped data
- **`logs/`**: Rotating timestamped log files

All paths are relative to `~/.ai_cli_bridge/`. No files are ever created outside this root.

## 5. Persistent Authentication

- Each AI target has its own **Playwright user profile directory** under `data/profiles/<AI_NAME>/`.
- Once the user manually logs in via the visible browser, cookies persist across CLI runs.
- On next startup, Playwright reuses that profile, bypassing login friction.
- If the browser profile directory is deleted, login will be required again.

## 6. Message Block Model

AI responses are composed of multiple **blocks**, where each block is a discrete unit of content:

- **Text Block**: Standard textual response
- **Canvas Block**: Interactive artifacts (code, documents, visualizations)
- **Image Block**: Generated or referenced images
- **Other Block Types**: Future extensibility for new AI capabilities

The `list` command enumerates all blocks with indexes and types. The `extract` command retrieves raw content of a specific block by index.

**Indexing:**

- Index 0 = first (oldest) block in the conversation
- Indexes increment chronologically
- Indexes are stable within a single CLI session

“Block type detection is based on matching configured selectors (`message_blocks`, `canvas_blocks`) in DOM order.”
## 7. Commands (v1.3)

|Command|Description|
|---|---|
|`open AI_NAME [--conversation URL]`|Launches browser, authenticates, loads chat interface.|
|`list [--json]`|Lists all message blocks with index, type, and preview.|
|`send TEXT [--attach PATH]`|Sends a message with optional file attachment.|
|`extract INDEX`|Extracts raw content of block at INDEX to stdout.|
|`status [--json]`|Shows session state, profile path, browser PID, last activity.|
|`doctor [--startup] [--json]`|Validates selectors, profile integrity, lock status (non-destructive).|
|`init AI_NAME`|Creates skeleton config file if it doesn't exist (idempotent).|

### Command Enhancements (v1.3)

- All major commands (`status`, `doctor`, `list`) support `--json` output for programmatic use.
- Exit codes standardized for automation (see Section 10).
- Startup diagnostics integrated into `doctor --startup`.

---

### 7.1 `open` Command

**Syntax:**

```bash
ai-cli-bridge open <AI_NAME> [--conversation URL] [--force]
```

**Behavior:**

1. Checks for existing lock file for this AI
2. If lock exists and process is alive: abort with E005
3. If `--force` specified: override stale lock
4. Creates lock file in `cache/locks/<AI_NAME>.lock`
5. Launches Chromium with persistent profile from `data/profiles/<AI_NAME>/`
6. Navigates to AI's chat interface
7. If `--conversation` provided: loads that specific chat URL
8. Otherwise: loads default new conversation page
9. Waits for page to be fully loaded and authenticated
10. Returns control to user when ready

**Error Conditions:**

- E001: No display detected
- E005: Another session active (unless `--force` used)
- E003: Config file not found or malformed

**Exit Codes:**

- 0: Success
- 3: Display error (E001)
- 4: Concurrency error (E005)
- 2: Config error (E003)

**Example:**

```bash
$ ai-cli-bridge open claude
✓ Browser launched (PID: 23412)
✓ Loaded: https://claude.ai/chat
✓ Ready for commands
```

**Implementation Notes:**

- Lock file must be created atomically to prevent race conditions
- Browser launch timeout: 30 seconds (configurable in config file)
- Authentication detection: checks for presence of chat input box selector
- Stale lock detection: checks if PID exists and is alive before aborting

---

### 7.2 `list` Command

**Syntax:**

```bash
ai-cli-bridge list [--json]
```

**Behavior:**

- Queries current page for all message blocks
- Returns indexed list with type and preview
- With `--json`: outputs structured JSON array

**Output Format (Text):**

```
[0] text: "What is the capital of France?"
[1] text: "The capital of France is Paris. Paris has been..."
[2] canvas: "React Component - TodoApp"
[3] text: "Let me explain how this component works..."
```

**Output Format (JSON):**

```json
[
  {
    "index": 0,
    "type": "text",
    "preview": "What is the capital of France?",
    "length": 35
  },
  {
    "index": 1,
    "type": "text",
    "preview": "The capital of France is Paris. Paris has been...",
    "length": 543
  },
  {
    "index": 2,
    "type": "canvas",
    "preview": "React Component - TodoApp",
    "title": "TodoApp",
    "length": 2847
  }
]
```

**Error Conditions:**

- E002: Browser session not found
- E004: Selector not found

**Exit Codes:**

- 0: Success
- 1: Session error (E002)
- 2: Selector error (E004)

**Implementation Notes:**

- Preview length: 60 characters max (truncated with "...")
- Block detection: uses `message_blocks` and `canvas_blocks` selectors from config
- Empty conversation: returns empty array (not an error)
- Blocks are discovered via DOM traversal in document order

---

### 7.3 `send` Command

**Syntax:**

```bash
ai-cli-bridge send "MESSAGE TEXT" [--attach PATH]
```

**Behavior:**

1. Locates input box using configured selector
2. If `--attach` specified: uploads file first
3. Types message into input box
4. Clicks send button
5. Waits for response to complete (spinner disappears, new blocks appear)
6. Returns when response is fully rendered

**File Attachment (v1.3 Constraints):**

- Max file size: 10 MB
- Timeout: 30 seconds for upload
- Supported types: Platform-dependent (no validation in v1.3)
- Upload mechanism: File uploads are executed by injecting the file path directly into the `<input type='file'>` element; native dialogs are bypassed.

**Error Conditions:**

- E002: Browser session not found
- E004: Selector not found (input box or send button)
- E009: File not found or too large

**Exit Codes:**

- 0: Success
- 1: Session error (E002)
- 2: Selector error (E004)
- 5: File I/O error (E009)

**Example:**

```bash
$ ai-cli-bridge send "Analyze this data" --attach report.csv
✓ File uploaded: report.csv (2.3 MB)
✓ Message sent
✓ Response received (3.2s)
```

**Implementation Notes:**

- Message typing uses human-like delays (10-50ms per character) to avoid detection
- Response completion detection: polls for spinner absence + new block presence
- Response timeout: 120 seconds (configurable via `timeouts.response_wait` in config)
- File upload: clicks attachment button, injects file path into native dialog

---
### 7.4 `extract` Command

**Syntax:**

```bash
ai-cli-bridge extract INDEX
```

**Behavior:**

- Retrieves block at specified index
- Outputs **raw content** to stdout (no JSON wrapper)
- For text blocks: plain text or markdown
- For canvas blocks: HTML source
- For image blocks: base64-encoded data or URL

**Error Conditions:**

- E002: Browser session not found
- E006: Index out of range
- E007: Invalid block type for extraction

**Exit Codes:**

- 0: Success
- 1: Session or index error (E002, E006, E007)

**Example:**

```bash
$ ai-cli-bridge extract 2 > component.html
✓ Extracted canvas block (2847 bytes)
```

**Implementation Notes:**

- Raw content means: no headers, no metadata, just the content itself
- Text blocks: extracted via `.textContent` or `.innerText` depending on formatting
- Canvas blocks: extracted via `.innerHTML` of artifact container
- Image blocks: extracted as data URLs or source URLs depending on availability
- Binary content (images): base64-encoded if data URL not available

---

### 7.5 `status` Command

**Syntax:**

```bash
ai-cli-bridge status [--json]
```

**Behavior:**

- Reports current session state
- Shows browser PID and health
- Displays profile location
- Shows last activity timestamps

**Output Format (Text):**

```
AI: claude
Browser PID: 23412 (alive)
Profile: ~/.ai_cli_bridge/data/profiles/claude
Last Auth: 2025-10-06 14:31:05
Last Doctor Check: 2025-10-07 09:10:21
Active Conversation: https://claude.ai/chat/xyz123
Lock Status: Active
Session Duration: 1h 23m 45s
```

**Output Format (JSON):**

```json
{
  "ai": "claude",
  "browser_pid": 23412,
  "browser_status": "alive",
  "profile_path": "~/.ai_cli_bridge/data/profiles/claude",
  "last_auth": "2025-10-06T14:31:05Z",
  "last_doctor_check": "2025-10-07T09:10:21Z",
  "active_conversation": "https://claude.ai/chat/xyz123",
  "lock_status": "active",
  "session_duration_seconds": 5025
}
```

**Error Conditions:**

- E002: Browser session not found (but still reports status)

**Exit Codes:**

- 0: Session active
- 1: Session not found (E002)

**Implementation Notes:**

- Browser health check: attempts to send a no-op command to browser (e.g., page title query)
- If browser doesn't respond within 2s: marked as "unresponsive"
- Session duration: calculated from lock file creation timestamp
- All timestamps in ISO 8601 format for JSON output

---

### 7.6 `doctor` Command

**Syntax:**

```bash
ai-cli-bridge doctor [--startup] [--json]
```

**Behavior (Non-Destructive Diagnostics):**

**Standard mode:**

- Validates all selectors against live DOM
- Checks profile directory integrity
- Verifies lock file status
- Tests browser process health
- Validates config schema

**With `--startup` flag:**

- Performs pre-flight checks before any session
- Validates Python & Playwright versions
- Checks display availability
- Verifies directory permissions (0700)
- Tests config file readability
- Does NOT require active browser session

**Output Format (Text - Standard):**

```
✓ Selectors: All valid
✓ Profile: Intact (2.3 MB)
✓ Lock: Active (PID 23412)
✓ Browser: Responsive (142ms)
✓ Config: Schema v1.0.0 valid
```

**Output Format (Text - Startup):**

```
✓ Python: 3.12.0 (>= 3.10 required)
✓ Playwright: 1.48.0 (>= 1.45 required)
✓ Display: Available (Wayland)
✓ Permissions: Correct (0700)
✓ Config: Readable and valid
```

**Output Format (JSON - Standard):**

```json
{
  "selectors": {
    "status": "valid",
    "details": {
      "input_box": "found",
      "send_button": "found",
      "message_blocks": "found",
      "canvas_blocks": "found",
      "spinner": "found"
    }
  },
  "profile": {
    "status": "intact",
    "size_mb": 2.3
  },
  "lock": {
    "status": "active",
    "pid": 23412
  },
  "browser": {
    "status": "responsive",
    "response_time_ms": 142
  },
  "config": {
    "status": "valid",
    "schema_version": "1.0.0"
  }
}
```

**Error Conditions:**

- E004: Selector validation failed (warning, not fatal)
- E002: Browser session not found (in standard mode)

**Exit Codes:**

- 0: All checks passed
- 1: Session error (standard mode only)
- 2: Validation warnings present

**Implementation Notes:**

- Selector validation: attempts to query each selector with 5s timeout
- If selector not found: logs warning but doesn't fail (UI may have changed)
- Startup mode can run without active session (useful for CI/pre-flight)
- Browser health check timeout: 5 seconds
- Config validation: checks schema version, required fields, selector format

**Reserved for v2.0:** Auto-fix capability (`doctor --fix`) to update selectors

---

### 7.7 `init` Command

**Syntax:**

```bash
ai-cli-bridge init AI_NAME
```

**Behavior:**

- Checks if `config/<AI_NAME>.json` exists
- If exists: no-op, returns success message
- If not exists: creates skeleton config with defaults
- Creates `data/profiles/<AI_NAME>/` directory
- Does NOT launch browser

**Idempotent:** Safe to run multiple times

**Output:**

```
✓ Created ~/.ai_cli_bridge/config/claude.json
✓ Created ~/.ai_cli_bridge/data/profiles/claude/
→ Run 'ai-cli-bridge open claude' to authenticate.
```

**If config already exists:**

```
✓ Config already exists: ~/.ai_cli_bridge/config/claude.json
→ Ready to use. Run 'ai-cli-bridge open claude'.
```

**Error Conditions:**

- E003: Unable to create config (filesystem error)
- E010: Unable to create profile directory (permission error)

**Exit Codes:**

- 0: Success (created or already exists)
- 2: Config creation error (E003)
- 5: Filesystem error (E010)

**Default Config Template:**

```json
{
  "schema_version": "1.0.0",
  "ai_target": "<AI_NAME>",
  "base_url": "https://<ai_name>.ai",
  "selectors": {
    "input_box": "PLACEHOLDER - REQUIRES MANUAL UPDATE",
    "send_button": "PLACEHOLDER - REQUIRES MANUAL UPDATE",
    "message_blocks": "PLACEHOLDER - REQUIRES MANUAL UPDATE",
    "canvas_blocks": "PLACEHOLDER - REQUIRES MANUAL UPDATE",
    "spinner": "PLACEHOLDER - REQUIRES MANUAL UPDATE"
  },
  "timeouts": {
    "page_load": 30,
    "response_wait": 120,
    "file_upload": 30
  },
  "log_level": "info"
}
```

**Implementation Notes:**

- AI_NAME converted to lowercase for consistency
- base_url uses common pattern but may need manual correction
- All selectors marked as placeholders requiring manual configuration
- User must run `doctor` after manually updating selectors
- Profile directory created with 0700 permissions

---

## 8. Config Schema

“Schema validation is implemented internally in Python; no external schema files are required.”
### Example: `config/claude.json`

```json
{
  "schema_version": "1.0.0",
  "ai_target": "claude",
  "base_url": "https://claude.ai",
  "selectors": {
    "input_box": "div[contenteditable='true']",
    "send_button": "button[aria-label='Send Message']",
    "message_blocks": "div.message-content",
    "canvas_blocks": "div.artifact",
    "spinner": "div.loading-spinner"
  },
  "timeouts": {
    "page_load": 30,
    "response_wait": 120,
    "file_upload": 30
  },
  "log_level": "info"
}
```
“Selector updates are made manually in the config JSON file. The CLI never modifies selectors automatically in v1.x.”
### Schema Rules

1. **`schema_version`** (string, required): Must match `MAJOR.MINOR.PATCH` format
2. **`ai_target`** (string, required): Identifier for the AI platform
3. **`base_url`** (string, required): Root URL for the AI interface
4. **`selectors`** (object, required): CSS selectors for page elements
5. **`timeouts`** (object, optional): Timeout values in seconds (defaults apply if omitted)
6. **`log_level`** (string, optional): One of `info`, `debug`, `trace` (default: `info`)
### Config Priority

Configuration values are resolved in the following order (highest to lowest priority):

1. **CLI Flags** (e.g., `--log-level debug`)
2. **Environment Variables** (prefixed with `AI_CLI_BRIDGE_`)
3. **Config File Defaults**

**Example Environment Variables:**

```bash
export AI_CLI_BRIDGE_LOG_LEVEL=debug
export AI_CLI_BRIDGE_CONFIG=~/.ai_cli_bridge/config/claude.json
export AI_CLI_BRIDGE_TIMEOUT_PAGE_LOAD=45
```
### Config Versioning

- **v1.x:** CLI validates schema version matches `1.x.x`
- Unknown fields are ignored but logged as warnings
- **Reserved for v2.0:** Auto-upgrade mechanism for older config versions
## 9. Browser Lifecycle Protocol

### Launch Sequence (Triggered by `open`)

1. Display detection check (abort if headless)
2. Lock file check (abort if concurrent session, unless `--force`)
3. Create lock file with PID
4. Launch Chromium with persistent profile
5. Navigate to target URL
6. Wait for authentication/page ready
7. Transition to IDLE state

### Shutdown Sequence (Triggered by CLI Exit)

1. Gracefully close all browser tabs
2. Terminate browser process
3. Remove lock file
4. Flush logs
5. Exit CLI

### Crash Recovery

If browser crashes during operation:

1. CLI detects broken pipe or process termination
2. Logs crash event with details
3. Removes stale lock file
4. Exits with E002: Browser session terminated
5. User must manually run `open` again to recover

**Reserved for v2.0:** Automatic crash recovery with session restoration

---

## 10. Error Codes and Exit Codes

“Only the first encountered fatal error determines the exit code; warnings do not alter exit status.”

|Code|Meaning|Exit|Typical Action|
|---|---|---|---|
|E001|No display detected|3|Run in graphical environment|
|E002|Browser session not found|1|Run `open` command|
|E003|Config parse error|2|Check JSON syntax, run `doctor`|
|E004|Selector not found|2|Run `doctor`, update config|
|E005|Concurrent session detected|4|Close other session or use `--force`|
|E006|Index out of range|1|Run `list` to see valid indexes|
|E007|Invalid block type|1|Check block type with `list`|
|E008|Config version mismatch|2|Update config or use compatible CLI|
|E009|File upload error|5|Check file size/path, retry|
|E010|Filesystem permission error|5|Check directory permissions|
### Error Code Groups

|Range|Category|
|---|---|
|1xx|Environment/Dependency|
|2xx|Config/Schema|
|3xx|Selector/DOM|
|4xx|Concurrency/Locking|
|5xx|I/O or Filesystem|

**Note:** Error codes follow standardized `EXXX` format for consistency and log parsing. Exit codes follow POSIX conventions for shell scripting compatibility.

---

## 11. Lock File Protocol

### Lock File Location

```
~/.ai_cli_bridge/cache/locks/<AI_NAME>.lock
```

### Lock File Format (JSON)

```json
{
  "pid": 23412,
  "created_at": "2025-10-08T14:23:11Z",
  "ai_target": "claude",
  "conversation_url": "https://claude.ai/chat/xyz123"
}
```

### Lock Acquisition

1. Check if lock file exists
2. If exists: read PID and check if process is alive
3. If process alive: abort with E005
4. If process dead (stale lock): remove lock and proceed
5. Create new lock file with current PID atomically

### Lock Release

- On normal exit: remove lock file
- On crash: lock becomes stale (next `open` will clean up)
- Manual override: `--force` flag on `open` command

### Stale Lock Handling

A lock is considered stale if:

- Lock file exists, but PID does not match any running process
- Lock file is older than 24 hours (safety mechanism)

Stale locks are automatically removed on next `open` attempt.

---

## 12. Signal Handling

|Signal|Behavior|
|---|---|
|SIGINT|Graceful shutdown (close browser, remove lock, flush logs)|
|SIGTERM|Graceful shutdown (same as SIGINT)|
|SIGKILL|Immediate termination (leaves stale lock for cleanup)|

**Graceful Shutdown Steps:**

1. Catch signal
2. Log shutdown event
3. Close browser gracefully (5s timeout)
4. Remove lock file
5. Flush logs
6. Exit with code 0

---

## 13. Retry & Backoff Policy

All retryable operations (DOM queries, sends, page loads) follow exponential backoff:

```
Attempts: 3
Delays: 1s → 2s → 4s
```

This behavior is **not user-configurable** in v1.x.

**Operations subject to retry:**

- Selector queries (`input_box`, `send_button`, etc.)
- Page load waits
- File uploads
- Message send confirmation

**Non-retryable errors:**

- E001 (No display)
- E003 (Config parse error)
- E006 (Index out of range)

---

## 14. Logging

### Log Files

- **Location:** `~/.ai_cli_bridge/logs/`
- **Format:** `session_YYYY-MM-DD_HH-MM-SS.log`
- **Rotation:** One log per session (new log on each `open`)

### Retention Policy

- **Max log size:** 10 MB per file
- **Retention count:** 10 most recent logs
- **Cleanup:** Automatic on session start (removes oldest logs beyond retention)

### Log Levels

Configurable in config file via `log_level` field:

- `info` (default): Standard operational events
- `debug`: Detailed selector queries and timing
- `trace`: Full Playwright API calls and DOM inspection

### Log Format

```
2025-10-08 14:23:11.423 [INFO] Browser launched (PID: 23412)
2025-10-08 14:23:15.102 [DEBUG] Selector found: input_box
2025-10-08 14:23:18.891 [INFO] Message sent successfully
```

### Sensitive Data Protection

- Passwords never logged
- Session tokens never logged
- Profile paths logged (non-sensitive)
- Message content not logged by default (requires `trace` level)

---

## 15. Compliance & Version Matrix

|Component|Minimum|Tested|Notes|
|---|---|---|---|
|Python|3.10|3.12|LTS verified|
|Playwright|1.45|1.48|Stable baseline|
|Chromium|120|129|Via Playwright|
|OS|Pop!_OS 22.04|Ubuntu 24.04|GNOME/Wayland|

**Compatibility Notes:**

- Python 3.9 and below: Not supported
- Playwright versions below 1.45: Missing critical selectors API
- Windows/macOS: Untested but should work with appropriate display detection
- Headless environments: Explicitly forbidden per guiding principles

“Chromium versions are Playwright-managed; regression testing required on Playwright upgrades.”

“macOS and Windows may work but are not officially supported or tested in v1.x.”
## 16. Startup Diagnostics

The `doctor --startup` command performs comprehensive pre-flight checks before any browser session begins.

**Checks Performed:**

- Python version validation (>= 3.10)
- Playwright version validation (>= 1.45)
- Display availability (X11, Wayland, or equivalent)
- Directory permissions (0700 for sensitive directories)
- Config file readability and schema validation
- Profile directory existence and integrity

**Example Output:**

```
✓ Python: 3.12.0 (>= 3.10 required)
✓ Playwright: 1.48.0 (>= 1.45 required)
✓ Display: Available (Wayland)
✓ Permissions: ~/.ai_cli_bridge/config (0700)
✓ Permissions: ~/.ai_cli_bridge/data (0700)
✓ Permissions: ~/.ai_cli_bridge/cache (0700)
✓ Config: claude.json readable and valid
```

**Use Cases:**

- Pre-deployment validation in new environments
- Troubleshooting installation issues
- Automated testing in CI/CD (without launching browser)

---

## 17. Command-Line Autocompletion

AI-CLI-Bridge provides shell autocompletion via `argcomplete`.

**Installation:**

```bash
# For bash
eval "$(register-python-argcomplete ai-cli-bridge)"

# For zsh
eval "$(register-python-argcomplete ai-cli-bridge)"
```

**Persistent Setup:**

Add to `~/.bashrc` or `~/.zshrc`:

```bash
eval "$(register-python-argcomplete ai-cli-bridge)"
```

**Completions Provided:**

- Command names (`open`, `send`, `list`, `extract`, etc.)
- AI target names (from `config/` directory)
- Flags (`--json`, `--attach`, `--force`, `--startup`)

---

## 18. Security

### Authentication & Storage

- **Local-only authentication:** Profiles stored in `data/profiles/` using Playwright's secure storage
- **No network telemetry:** Zero data collection or reporting in v1.x
- **Cookie isolation:** Each AI profile maintains separate cookie store

### File System Security

- **Permissions:** 0700 (read/write/execute for owner only) on all sensitive directories:
    - `config/`
    - `data/`
    - `cache/`
- **Sensitive paths:** Never logged, even at `trace` level
- **Lock file security:** PID-based validation prevents session hijacking

### Threat Model

**Protected Against:**

- Concurrent session conflicts (lock mechanism)
- Accidental credential exposure in logs
- Cross-profile authentication leakage

**Not Protected Against:**

- Root user access (by design)
- Physical access to filesystem
- Malicious browser extensions (user responsibility)

---

## 19. Non-Functional Requirements

|Category|Requirement|
|---|---|
|Portability|Must run on Linux (Pop!_OS 22.04 LTS baseline).|
|Resource use|≤ 250 MB RAM idle; ≤ 2 GB temporary disk usage.|
|Dependencies|Playwright ≥ 1.45, Python ≥ 3.10.|
|Startup time|≤ 2 s typical cold start (excluding browser launch).|
|Browser launch|≤ 5 s typical (network-dependent).|
|Shutdown|≤ 3 s graceful browser termination.|
|File permissions|0700 on all `config/`, `data/`, and `cache/` directories.|

---

## 20. Operational Event Hooks (Reserved for v2.0)

**Status:** Documented but not implemented in v1.x

A future event stream mechanism will be added to `cache/events.log` for telemetry and monitoring:

```json
{"timestamp":"2025-10-08T14:23:11Z","event":"send","ai":"claude","status":"ok","duration_ms":3200}
{"timestamp":"2025-10-08T14:26:45Z","event":"extract","ai":"claude","status":"ok","block_index":2}
```

**Usage (v2.0+):**

- Real-time monitoring dashboards
- Performance analytics
- Error pattern detection
- Usage metrics

**Implementation Note:** Do not create `events.log` in v1.x implementations. This file is reserved for future use.

---

## 21. Maintenance & Support Policy

### Version Management

- **Schema updates:** Reviewed per minor release (v1.1, v1.2, etc.)
- **Config compatibility:** Backward compatible within major version (v1.x)
- **Deprecation notice:** Minimum 2 minor versions before removal

### Dependency Management

- **Playwright version bumps:** Quarterly, after regression testing
- **Python version support:** Follow Python LTS schedule
- **Chromium updates:** Automatic via Playwright

### Quality Assurance

- **Lock handling review:** Quarterly audit of concurrency mechanisms
- **Selector validation:** Per-AI review when UI changes detected
- **Bug triage cycle:** Monthly review and prioritization

### Support Channels

- **Documentation:** Primary source at project repository
- **Issue tracking:** GitHub Issues for bug reports and feature requests
- **Security issues:** Dedicated security@project email (to be established)

---

## 22. Version Banner

On startup, AI-CLI-Bridge displays:

```
AI-CLI-Bridge v1.3.0 (Schema v1.0.0)
© 2025, All Rights Reserved
```

**Display Conditions:**

- Shown once per session on first command
- Suppressed when `--json` flag is used
- Includes CLI version and schema version for compatibility verification

---

## 23. Version 2.0 Roadmap

| Planned Feature                            | Priority  |
| ------------------------------------------ | --------- |
| Selector auto-refresh (`doctor --fix`)     | 🔺 High   |
| Context metrics (token usage, latency)     | 🔺 High   |
| `save INDEX PATH [--format md\|txt\|html]` | 🔺 High   |
| `dump --all [--format md]`                 | 🔺 High   |
| Config auto-upgrade from v1.x              | 🔺 High   |
| Multi-tab/multi-conversation               | 🔻 Medium |
| Auto-recovery from browser crashes         | 🔻 Medium |
| Event hook telemetry (Section 20)          | 🔻 Medium |
| Full analytics/telemetry (opt-in)          | 🔻 Low    |

---

## 24. Summary

v1.3 of AI-CLI-Bridge delivers a production-grade, deterministic CLI automation layer for AI web interfaces with comprehensive lifecycle management, block-based message handling, strong concurrency control, and operational maturity.

**Key Features:**

- Headed-only browser automation for full observability
- Persistent authentication via Playwright profiles
- Block-based message model for multi-content responses
- Robust lock mechanism preventing concurrent sessions
- Standardized exit codes for automation friendliness
- JSON output support for programmatic integration
- Comprehensive diagnostics and health checks
- Enterprise-ready compliance and maintenance policies

The architecture prioritizes predictability, single-user clarity, and operational transparency. All command specifications are fully detailed for implementation, and the design provides clean expansion points for v2.0 without requiring architectural rewrites.

---

**End of Specification Document v1.3**
