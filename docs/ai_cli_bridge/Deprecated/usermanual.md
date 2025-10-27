
# AI-CLI-Bridge — User Manual (v1.3.1)

Date: 2025-10-08
Spec Alignment: AI-CLI-Bridge Design Specs v1.3 / Code Specs v1.3.1
Platform: Linux (Pop!_OS 22.04 baseline). macOS/Windows may work but are not officially supported in v1.x.

---
## Table of Contents

1. What & Why
2. Architecture Overview
3. Requirements & Installation
4. Filesystem Layout
5. Configuration
    - 5.1 Schema & Example
    - 5.2 Rules, Validation, Env Overrides
6. Lock File Protocol
7. Browser Lifecycle & Auth Readiness
    - 7.1 Headed-only policy
    - 7.2 Built-in Playwright mode
    - 7.3 External Browser (CDP) mode
8. Message Block Model
    - 8.1 Discovery, Classification
    - 8.2 Extraction Semantics
9. Response Completion Detection
10. CLI Commands
    - 10.1 init
    - 10.2 open
    - 10.3 send
    - 10.4 list
    - 10.5 extract
    - 10.6 status
    - 10.7 doctor
    - 10.8 init-cdp
11. Logging & Retention
12. Error & Exit Codes
13. Security, Privacy & Disk Budget
14. Troubleshooting & FAQs
15. End-to-End Example Workflow
16. Acceptance Criteria (v1.3.1)
17. Glossary

---
## 1) What & Why

AI-CLI-Bridge lets you operate web-based AI chat UIs (Claude, ChatGPT, Gemini) from the terminal. It provides predictable, testable automation around:

- Opening/attaching to a **headed** browser session
- Sending prompts (optionally with file uploads)
- Listing/extracting response blocks (text, canvas artifacts, images)
- Health checks and diagnostics

The project intentionally forbids headless/CI because many AI UIs aggressively challenge automation; headed browsing is both more reliable and auditable.

---
## 2) Architecture Overview

- CLI (ai-cli-bridge) dispatches subcommands.
- Config (per AI) provides selectors, timeouts, base URL, CDP settings.
- Browser Manager either:
    - launches a **Playwright**-bundled Chromium persistent context, or
    - attaches to a **head**ed browser over **CDP** (Chrome DevTools Protocol).
- Auth Readiness gate ensures the page is truly usable (input present, no login/error overlays).
- Block Model discovers and classifies output elements with deterministic indexing.
- Completion Detection (Spinner + Stability) decides when a reply is “done”.
- Locking guarantees only one active session per AI profile.
- Logging & diagnostics emphasize privacy and actionable information.

---
## 3) Requirements & Installation

Required:

- Linux desktop (Wayland/X11) with a graphical session (headless forbidden).
- Python ≥ 3.10 (tested 3.12), Playwright ≥ 1.45 (tested 1.48), Chromium (tested 129).
- Network access to the target AI sites.

Typical setup:

`# venv (example) python3 -m venv ~/.ai_cli_bridge/venv source ~/.ai_cli_bridge/venv/bin/activate  pip install --upgrade pip pip install playwright typer  # One-time browser download playwright install`

---
## 4) Filesystem Layout

All data is under ~/.ai_cli_bridge/

`~/.ai_cli_bridge/
├── config/             # per-AI JSON configs (0600)
├── data/
│   └── profiles/     # per-AI browser profiles (0700)
├── cache/
│   └── locks/         # session lock files (0700)
└── logs/                # per-session logs (0600)`

Permissions:

- Directories: 0700
- Files: 0600
- If permissions are lax, the tool will auto-correct (with a warning), surfaced by doctor.

---
## 5) Configuration

### 5.1 Schema & Example

File: ~/.ai_cli_bridge/config/<AI_NAME>.json

Example (Claude):

`{
    "schema_version": "1.0.0",
    "ai_target": "claude",
     "base_url": "https://claude.ai",
     "selectors": {
          "input_box": "div[contenteditable='true']",
           "send_button": "button[aria-label='Send Message']",     "message_blocks": "div.message-content",
           "canvas_blocks": "div.artifact",
           "spinner": "div.loading-spinner",
           "image_blocks": "img.message-image",
           "file_upload_input": "input[type='file']",
           "upload_confirmation": ".file-attached",
           "login_form": "form[aria-label='Sign in']",
           "error_indicator": ".rate-limit,.error"
       },
       "timeouts": {
           "browser_launch": 30,
           "page_load": 60,
           "response_wait": 120,
           "file_upload": 30,
           "response_stability_ms": 2000
       },
       "cdp": {
           "enable_autostart": true,
           "launcher": "playwright",             // or "flatpak"
           "port": 9223,
           "wait_seconds": 12,
           "user_data_dir": "/home/you/.ai_cli_bridge/data/profiles/claude_cdp_pw",
           "startup_urls": [
                 "https://claude.ai/chat",
            "https://chat.openai.com",
            "https://gemini.google.com"
           ]
           },
      "log_level": "info"
   }`

(Comments shown above are illustrative; JSON files must not contain comments.)

### 5.2 Rules, Validation, Env Overrides

- schema_version must be 1.x.x
- CSS selectors only (no XPath)
- Timeouts bounds:
    - browser_launch, page_load: 5–120s
    - response_wait: 10–600s
- Unknown fields → warning; ignored
- Env var overrides: flat names (e.g., AI_CLI_BRIDGE_TIMEOUT_PAGE_LOAD=45). Selectors are not overridable by env.

---
## 6) Lock File Protocol

Path: ~/.ai_cli_bridge/cache/locks/<AI_NAME>.lock

- Atomic create: O_CREAT | O_EXCL → write JSON → fsync → close
- Format (example):
    {
    "version": "1.0",
    "pid": 23412,
    "created_at": "2025-10-08T14:23:11Z",
    "ai_target": "claude",
    "conversation_url": "[https://claude.ai/chat/xyz123](https://claude.ai/chat/xyz123)"
    }
- Stale if PID is dead or file > 24h old
- open --force removes stale lock and proceeds

---
## 7) Browser Lifecycle & Auth Readiness

### 7.1 Headed-only policy

- Detects $DISPLAY / $WAYLAND_DISPLAY and the compositor type.
- If forced headless, returns E001 (“cannot run headless”).
### 7.2 Built-in Playwright mode

- Uses Chromium persistent context with a user_data_dir under data/profiles/.
- Soft fingerprint-hardening (navigator.webdriver undefined, realistic UA/headers) within legal/ToS boundaries.
- Auth Readiness is satisfied when:
    1. input_box present and enabled,
    2. login_form not visible,
    3. error_indicator not visible.
- If not satisfied by page_load timeout: E002 with guidance to complete login and retry.
### 7.3 External Browser (CDP) mode

- Attaches to a running, headed browser via DevTools (CDP).
- AI_CLI_BRIDGE_CDP_URL can be exported (ws://127.0.0.1:PORT/devtools/browser/<id>).
- init-cdp can launch a CDP-enabled browser and print a ready ws:// URL.
- open will **avoid navigation** if you’re already on a Claude route; it only navigates when necessary.

Why CDP mode? It leverages your trusted headed browser profile to reduce bot challenges and preserve login state.

---
## 8) Message Block Model

### 8.1 Discovery, Classification

- Query DOM and classify with precedence:
    1. canvas_blocks
    2. image_blocks
    3. message_blocks
- If an element matches multiple roles or has nested matches, choose the highest-precedence ancestor once.
- Sort by DOM order; indices (0..N-1) are stable for the session.

### 8.2 Extraction Semantics

- text: innerText/textContent (best fidelity per target)
- canvas: raw innerHTML of the artifact container
- image: data URL (base64) if available; else src URL
- Output is the raw content only (no wrapper metadata). Text ends with trailing newline; binary/image emits bytes or data URLs.

---
## 9) Response Completion Detection

Algorithm: Spinner + Stability

1. If spinner visible → not complete
2. Once spinner absent (or never observed), start stability window:
    - Every 500ms measure (a) block count, (b) last-block DOM size
3. If either changes → reset timer
4. Mark complete when stable for response_stability_ms (e.g., 2000ms)
5. Hard deadline: response_wait. On timeout, return with a warning (command still succeeds unless the caller opts to treat timeout as error)

---
## 10) CLI Commands

Notes:

- All commands return meaningful exit codes (see Section 12).
- Timestamps in JSON outputs are ISO-8601 UTC; durations are ISO 8601 (e.g., PT1H23M45S).
### 10.1 init

Initialize AI target profile and skeleton config.

`ai-cli-bridge init <AI_NAME>`

Behavior:

- Normalize AI_NAME (lowercase, [a-z0-9_-], collapse underscores, ≤32 chars)
- Create config file and profile directory (0700)
- Idempotent

Errors:

- E003 (config create/parse), E010 (filesystem permissions)
### 10.2 open

Launch/attach and verify auth readiness.

`ai-cli-bridge open <AI_NAME> [--conversation URL] [--force]`

Behavior:

1. Display check; forbid headless (E001)
2. Acquire lock atomically; --force cleans stale locks
3. Launch Playwright persistent context or attach via CDP
4. Navigate to base_url or --conversation only if needed (avoid unnecessary reloads)
5. Verify auth readiness (3 checks)

Exit: 0 on success; first fatal error maps to exit (see Section 12).
### 10.3 send

Send a message (and optionally attach a file), then wait for completion.

`ai-cli-bridge send "MESSAGE TEXT" [--attach PATH]`

Behavior:

- Find input_box; type with human-like delays (10–50ms/char + small pauses)
- Optional attach:
    - Validate file exists, readable, < 10MB (E009 on error)
    - Use file_upload_input.set_input_files(PATH)
    - Success if upload_confirmation appears OR the file input value is set without console errors
- Click send_button
- Wait for completion using Spinner + Stability

Timeouts: file_upload, response_wait, response_stability_ms
On response_wait timeout: exit 0 with a warning (streaming-friendly)
### 10.4 list

List discovered blocks or emit JSON.

`ai-cli-bridge list [--json] [--envelope]`

Behavior:

- Previews truncated to 60 chars on a word boundary (unicode-aware)
- --json emits a raw array; --envelope wraps in {status,timestamp,data}

Text output sample:

[0] text: "What is the capital of France?"
[1]   text: "The capital of France is Paris. Paris has been..."
[2] canvas: "React Component - TodoApp"
[3] image: "data:image/png;base64,iVBOR..."

JSON output sample:

[
    {"index":0,"type":"text","preview":"What is the capital of France?","length":35},   {"index":1,"type":"text","preview":"The capital of France is Paris. Paris has been...","length":543},
    {"index":2,"type":"canvas","preview":"React Component - TodoApp","title":"TodoApp","length":2847}
]

### 10.5 extract

Emit the raw content of a block to stdout.

`ai-cli-bridge extract INDEX`

- Text: ends with newline
- Canvas: raw HTML
- Image: bytes or data URL

Errors: E006 (range), E007 (invalid type)
### 10.6 status

Report current session health and metadata.

`ai-cli-bridge status [--json]`

Reports:

- AI target, PID/health (2s page.title() probe), profile path
- last auth, last doctor, active conversation, lock status, session duration
- --json may include {config,data,cache,logs} disk_usage_mb and warnings

Exit: 0 if session active; 1 otherwise.
### 10.7 doctor

Validate system & target selectors.

`ai-cli-bridge doctor [--startup] [--json]`

Standard:

- Validate selectors (5s each, 3 retries), profile integrity, lock status, browser responsiveness, config schema
- Colorized output (respects --no-color / NO_COLOR)

--startup:

- Validate Python/Playwright versions, display availability & type, directory permissions (0700), config readability
- Surface auto-corrected permissions notices

Exit: 0 all good; 1 session error (standard only); 2 warnings present
### 10.8 init-cdp

Launch a CDP-enabled browser with your configured profile and startup URLs, then print a ws:// DevTools URL.

`ai-cli-bridge init-cdp <AI_NAME>`

Config (cdp block):

- launcher: "playwright" | "flatpak" (default often "flatpak")
- port: integer (e.g., 9222/9223)
- wait_seconds: how long to wait for DevTools endpoint
- user_data_dir: absolute path for the profile dir (required)
- flatpak_id: when launcher="flatpak" (e.g., io.github.ungoogled_software.ungoogled_chromium)
- startup_urls: array of tabs to open

Typical sequence:

`ai-cli-bridge init-cdp claude export AI_CLI_BRIDGE_CDP_URL="$(curl -s http://127.0.0.1:9223/json/version | jq -r .webSocketDebuggerUrl)" ai-cli-bridge open claude --conversation "https://claude.ai/chat"`

---
## 11) Logging & Retention

- One log per open; timestamps suffixed with " UTC"
- Retain 10 most recent logs; each ≤ 10 MB
- Levels: info (default), debug, trace. Message content is logged only at trace.
- Sensitive data (passwords/tokens) never logged.

---
## 12) Error & Exit Codes

| Code | Meaning                           | Exit | Action                                 |
| ---- | --------------------------------- | ---- | -------------------------------------- |
| E001 | No display / headless forbidden   | 3    | Run in graphical env; disable headless |
| E002 | Browser session not found/ready   | 1    | Run open; complete login if needed     |
| E003 | Config parse/validation error     | 2    | Fix JSON/schema; run doctor --startup  |
| E004 | Selector not found/invalid        | 2    | Update selectors; run doctor           |
| E005 | Concurrent session detected       | 4    | Close other session or use --force     |
| E006 | Index out of range                | 1    | Run list to see valid indexes          |
| E007 | Invalid block type for extraction | 1    | Verify block type with list            |
| E008 | Config version mismatch           | 2    | Update config or use compatible CLI    |
| E009 | File upload error                 | 5    | Check size/path/permissions; retry     |
| E010 | Filesystem permission error       | 5    | Fix directory perms (0700)             |

First fatal error determines exit code; warnings don’t change it.

---
## 13) Security, Privacy & Disk Budget

- Headed-only design; CI/headless forbidden.
- Profiles/cookies live under data/profiles/ (0700).
- Profiles are excluded from the ≤2GB temp/disk budget; warnings target logs/cache only.
- Sensitive data never logged; request/response bodies appear only at trace level (opt-in).

---
## 14) Troubleshooting & FAQs

• Stuck in “prove you’re human”
– Prefer CDP mode with a trusted, headed browser profile (init-cdp). Avoid unnecessary reloads; open won’t navigate if already on a Claude route.

• Headless forbidden error (E001)
– Ensure DISPLAY or WAYLAND_DISPLAY is set and you’re not forcing headless in config/code.

• Selectors changed after a site update
– Run doctor; adjust selectors in your config file; re-try.

• File upload errors (E009)
– Ensure file < 10MB; path exists; input selector is correct; wait for upload_confirmation.

• JSON output shape
– list --json returns a raw array by default. Add --envelope to wrap responses in {status,timestamp,data}.

• Locks never clear
– Use open --force to remove stale lock; investigate if a stray process is holding it.

---
## 15) End-to-End Example Workflow

Goal: Operate Claude via CDP with a dedicated persistent profile.

1. Configure the cdp block in ~/.ai_cli_bridge/config/claude.json:

    "cdp": {
     "enable_autostart": true,
     "launcher": "playwright",
     "port": 9223,
     "wait_seconds": 12,
     "user_data_dir": "/home/you/.ai_cli_bridge/data/profiles/claude_cdp_pw",
     "startup_urls": [
         "[https://claude.ai/chat](https://claude.ai/chat)",
         "[https://chat.openai.com](https://chat.openai.com)",
         "[https://gemini.google.com](https://gemini.google.com)"
     ]
    }

2. Launch CDP browser and export ws URL:

    ai-cli-bridge init-cdp claude
    export AI_CLI_BRIDGE_CDP_URL="$(curl -s [http://127.0.0.1:9223/json/version](http://127.0.0.1:9223/json/version) | jq -r .webSocketDebuggerUrl)"

3. Attach and verify readiness:

    ai-cli-bridge open claude --conversation "[https://claude.ai/chat](https://claude.ai/chat)"

    # ✓ Browser launched
    # ✓ Loaded: [https://claude.ai/new](https://claude.ai/new)
    # ✓ Ready (auth verified)

4. Operate (examples, if implemented):

    ai-cli-bridge send "Analyze this CSV" --attach ~/report.csv
    ai-cli-bridge list --json
    ai-cli-bridge extract 2 > artifact.html

5. Diagnostics:

    ai-cli-bridge doctor
    ai-cli-bridge status --json

1. Shutdown:

- Close the CDP browser window (graceful). Next open will recover/clean stale locks as needed.

---
## 16) Acceptance Criteria (v1.3.1)

- Headed-only enforced (E001 on headless)
- open checks Auth Readiness (input present/enabled; no login/error overlays)
- send uses Spinner + Stability; warns (not errors) on response_wait timeout
- File uploads via set_input_files(); E009 on failure
- list --json returns raw array; --envelope available
- Locks created atomically; stale locks cleaned; force-kill on stuck shutdown after 5s
- doctor/status expose enhanced diagnostics; permission auto-fix surfaced
- Logging retention and privacy rules honored

---
## 17) Glossary

- CDP: Chrome DevTools Protocol; lets CLI attach to a running headed browser.
- Auth Readiness: Gate that ensures the UI is genuinely usable before subsequent actions.
- Block: A discovered UI element representing text, an image, or a canvas artifact.
- Spinner + Stability: Response-completion algorithm using a spinner check and a DOM stability window.
- Profile: Browser user data directory (cookies, local storage) under data/profiles/.
