
# AI-CLI-Bridge Code Specs **V1.3.1**

**Date:** 2025-10-08  
**Aligns with:** _AI-CLI-Bridge Design Specs V1.3_  
**Status:** Approved by architect

## 0. Change Log (from V1.3.0 → V1.3.1)

- **Completion detection**: Implements **Spinner + Stability** algorithm with `response_stability_ms` (A1, B2).
    
- **File uploads**: Uses `input.set_input_files()`; added selectors `file_upload_input` and `upload_confirmation` (A2, B3).
    
- **Block classification**: **Canvas > Image > Text** precedence; parent-only extraction for nested artifacts (A3, B4).
    
- **Auth readiness**: Now requires input present, login form absent, and no error indicator (A4, B5).
    
- **Canvas extraction**: Return **raw innerHTML** (A5, B4).
    
- **Signals**: Graceful close; force-kill after 5s if needed; locks always cleaned (A6, B10).
    
- **Profiles & disk budget**: Excluded from the ≤2GB temp/disk budget; warn only for logs/cache (A7, B11).
    
- **JSON output**: `list --json` returns **raw array** by default; `--envelope` adds `{status,timestamp,data}` (A8, B8).
    
- **Headless**: **Hard-forbid**; enforce at launch (B6).
    
- **Locking**: Atomic create via `O_CREAT|O_EXCL` (B7).
    
- **QoL flags**: `--quiet`, `--no-color` (B9).
    
- **Doctor/Status**: Extra diagnostics (display type, permissions autocorrect notice, optional disk usage) (B11).
    
- **Docs/Examples** updated to match (B12, C).
    

---

## 1. Runtime & Environment (unchanged unless noted)

- **Requires headed GUI**; CI/headless is forbidden.
    
- Display detection: check `$DISPLAY`/`$WAYLAND_DISPLAY`; log detected **X11/Wayland/Unknown**.
    
- If Playwright or environment forces headless → **E001**: "No graphical display detected. AI-CLI-Bridge cannot run headless."
    

---

## 2. Directory Layout (recap)

```
~/.ai_cli_bridge/
├── config/
├── data/
│   └── profiles/
├── cache/
│   └── locks/
└── logs/
```

- Sensitive directories (`config/`, `data/`, `cache/`) kept at **0700**; files **0600**.
    
- On access, permissions may be **auto-corrected** with a WARNING (convenience over strictness); surfaced in `doctor` output.
    

---

## 3. Configuration Schema (V1.3.1)

### 3.1 JSON Example

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
    "spinner": "div.loading-spinner",

    "image_blocks": "img.message-image",           
    "file_upload_input": "input[type='file']",     
    "upload_confirmation": ".file-attached",       
    "login_form": "form[aria-label='Sign in']",    
    "error_indicator": ".rate-limit,.error"        
  },
  
  "timeouts": {
    "browser_launch": 30,            
    "page_load": 30,
    "response_wait": 120,
    "file_upload": 30,
    "response_stability_ms": 2000    
  },

  "log_level": "info"
}
```

### 3.2 Rules & Validation

- `schema_version` must be `1.x.x`.
    
- Placeholders are **rejected** at load (E003).
    
- Timeouts bounds: `browser_launch`/`page_load` **5–120s**; `response_wait` **10–600s**.
    
- Unknown fields → single WARNING, ignored.
    
- No XPath in v1.x; CSS only.
    
- Env var overrides: flat names (e.g., `AI_CLI_BRIDGE_TIMEOUT_PAGE_LOAD=45`). Selectors are **not** overrideable by env.
    

---

## 4. Lock File Protocol (updated)

- Path: `~/.ai_cli_bridge/cache/locks/<AI_NAME>.lock`
    
- **Atomic create** with `os.open(path, O_CREAT|O_EXCL)` → write JSON → `fsync` → close.
    
- Format:
    

```json
{
  "version": "1.0",
  "pid": 23412,
  "created_at": "2025-10-08T14:23:11Z",
  "ai_target": "claude",
  "conversation_url": "https://claude.ai/chat/xyz123"
}
```

- Stale if PID dead **or** file older than 24h.
    
- `--force` on `open` removes stale lock and proceeds.
    

---

## 5. Browser Lifecycle & Auth Readiness

**Launch sequence (open):** display check → lock acquire → launch Chromium (profile) → navigate → **auth readiness** check.

**Auth readiness =**

1. `input_box` present & enabled, **and**
    
2. `login_form` **absent**, **and**
    
3. `error_indicator` **absent**.  
    If not satisfied within `page_load`, fail with **E002** and guidance: _"Open the page and complete login, then retry."_
    

Shutdown: graceful close; if not done in **5s**, force-kill, remove lock, flush logs, exit 0.

Crash: detect via Playwright `disconnected`; mark session terminated (E002).

---

## 6. Message Block Model (classification & extraction)

### 6.1 Discovery & Indexing

- Query DOM and **classify with precedence**: `canvas_blocks` → `image_blocks` → `message_blocks`.
    
- If an element matches multiple roles or has nested matches, choose the **highest-precedence ancestor once**.
    
- Sort by DOM order (document position). Indices start at 0; stable for the current session & conversation URL.
    

### 6.2 Extraction Semantics

- **text**: plain text/markdown via `.innerText`/`.textContent` (choose best fidelity per target).
    
- **canvas**: return **raw `innerHTML`** of the artifact container.
    
- **image**: data URL (base64) if available; else `src` URL.
    
- Output is **raw content only** (no metadata wrapper). Binary prints to stdout as bytes.
    

---

## 7. Response Completion Detection (final)

Algorithm = **Spinner + Stability**:

1. If `spinner` visible → **not complete**.
    
2. When spinner absent (or never observed), start **stability window**: every **500ms**, measure _(a)_ block count and _(b)_ last block DOM size.
    
3. If either changes, **reset** the stability timer.
    
4. Consider complete when stable for **`response_stability_ms`**.
    
5. Hard deadline: **`response_wait`**. On timeout, return with warning and continue (command still succeeds unless caller opted to treat as error; see send behavior).
    

---

## 8. CLI Commands (authoritative)

### 8.1 `open`

```
ai-cli-bridge open <AI_NAME> [--conversation URL] [--force]
```

**Behavior:**

1. Forbid headless; verify display.
    
2. Lock acquire atomically; respect `--force` for stale locks.
    
3. Launch Chromium with persistent profile; navigate to `base_url` or `--conversation`.
    
4. Wait for **auth readiness** (Sec. 5).
    

**Errors:** E001 (display/headless), E005 (concurrent), E003 (config), E002 (auth not ready).  
**Exit:** 0 on success; 3/4/2/1 as mapped above.  
**Notes:** `browser_launch` timeout governs initial launch; `page_load` governs initial page readiness.

---

### 8.2 `list`

```
ai-cli-bridge list [--json] [--envelope]
```

- Collects blocks per Sec. 6; truncates previews at **60 chars on word boundary** (unicode-aware, emoji=1 char).
    
- `--json`: **raw array** of block descriptors.
    
- `--json --envelope`: wraps in `{status,timestamp,data}`.
    

**Text example:**

```
[0] text: "What is the capital of France?"
[1] text: "The capital of France is Paris. Paris has been..."
[2] canvas: "React Component - TodoApp"
[3] image: "data:image/png;base64,iVBOR..."
```

**JSON (raw array):**

```json
[
  {"index":0,"type":"text","preview":"What is the capital of France?","length":35},
  {"index":1,"type":"text","preview":"The capital of France is Paris. Paris has been...","length":543},
  {"index":2,"type":"canvas","preview":"React Component - TodoApp","title":"TodoApp","length":2847}
]
```

**Errors:** E002 (no session), E004 (selector not found).  
**Exit:** 0 success; 1 session error; 2 selector warning/error.

---

### 8.3 `send`

```
ai-cli-bridge send "MESSAGE TEXT" [--attach PATH]
```

**Behavior:**

1. Find `input_box`; optional attach:
    
    - Validate file: exists, is file, readable, **<10 MB**; else **E009**.
        
    - Use `file_upload_input.set_input_files(PATH)`.
        
    - Success if `upload_confirmation` appears **or** file input value set with no console errors.
        
2. Type message with human-like delays **10–50ms/char**, adding small pauses after spaces/punctuation.
    
3. Click `send_button`.
    
4. Wait for **completion** (Sec. 7).
    

**Timeouts:** `file_upload`, `response_wait`, `response_stability_ms`.

**On response timeout:** command exits **0** with a **warning** (still usable for streaming UIs).  
**Errors:** E002 (session), E004 (selectors), E009 (file I/O).  
**Exit:** 0 success; 1/2/5 as above.

---

### 8.4 `extract`

```
ai-cli-bridge extract INDEX
```

- Emits **raw content** for block at `INDEX` (Sec. 6.2) to **stdout**.
    
- Text ends with trailing `\n`; binary/image emits bytes or data URL.
    

**Errors:** E002 (session), E006 (range), E007 (invalid type).  
**Exit:** 0 success; 1 otherwise.

---

### 8.5 `status`

```
ai-cli-bridge status [--json]
```

- Reports AI target, browser PID/health (2s `page.title()` probe), profile path, last auth, last doctor, active conversation, lock status, session duration.
    
- When `--json`: include optional `disk_usage_mb` per `{config,data,cache,logs}` and a `warnings` array (e.g., large logs/cache).
    
- Profiles are **excluded** from the 2GB temp/disk budget.
    

**Exit:** 0 if session active; 1 if not found.

---

### 8.6 `doctor`

```
ai-cli-bridge doctor [--startup] [--json]
```

**Standard:**

- Validate selectors (5s each, 3 retries), profile integrity, lock status, browser responsiveness, config schema.
    
- Colorize ✓/✗ (respect `--no-color` / `NO_COLOR`).
    

**`--startup`:**

- Validate Python/Playwright versions, display availability & type, directory permissions (0700), config readability.
    
- Surfacing: notes if permissions were auto-corrected.
    

**Exit:** 0 all good; 1 session error (standard only); 2 warnings present.

---

### 8.7 `init`

```
ai-cli-bridge init AI_NAME
```

- Normalize AI name: lowercase, `[a-z0-9_-]`, collapse underscores, max 32; reject empty after normalization.
    
- Create skeleton config & profile directory (0700).
    
- Idempotent.
    

**Errors:** E003 (config create), E010 (filesystem permissions).  
**Exit:** 0 success; 2/5 as above.

---

## 9. Logging

- One log per `open` (UTC timestamps with " UTC").
    
- Retain **10** most recent logs; each ≤ **10 MB**; cleanup oldest on session start.
    
- Levels: `info` (default), `debug`, `trace`. Message content logged **only at trace**.
    
- Sensitive data (passwords/tokens) never logged.
    

---

## 10. Error & Exit Codes (unchanged mapping)

|Code|Meaning|Exit|Suggested Action|
|---|---|---|---|
|E001|No display / headless forbidden|3|Run in graphical env; ensure headless is disabled|
|E002|Browser session not found/ready|1|Run `open`; complete login if needed|
|E003|Config parse/validation error|2|Fix JSON/schema; run `doctor --startup`|
|E004|Selector not found/invalid|2|Update selectors; run `doctor`|
|E005|Concurrent session detected|4|Close other session or use `--force`|
|E006|Index out of range|1|Run `list` to see valid indexes|
|E007|Invalid block type for extraction|1|Verify block type with `list`|
|E008|Config version mismatch|2|Update config or use compatible CLI|
|E009|File upload error|5|Check size/path/permissions; retry|
|E010|Filesystem permission error|5|Fix directory perms (0700)|

**Rule:** first fatal error determines exit code; warnings do not change it.

---

## 11. Global Flags & Output Conventions

- `--quiet, -q` suppresses banner and non-essential TTY output.
    
- `--no-color` disables ANSI colors (overrides `NO_COLOR`).
    
- All timestamps in JSON are ISO-8601 UTC.
    
- Durations: human-readable in text; ISO 8601 (e.g., `PT1H23M45S`) in JSON.
    

---

## 12. Testing Strategy (implementation-facing)

- **Unit (~200):** config parsing & env overrides; lock atomicity; selector validation; error mappings; permission autocorrect notices.
    
- **Integration (~50):** open→send→list→extract flows (mock Playwright); lock collision; file upload; completion detection stability window; signal handling (graceful + force-kill).
    
- **Mocks:** mock Playwright `Page/Locator`; mock filesystem for lock & perms; manual acceptance with real Chromium for at least one target.
    

**Performance targets:** config load <50ms; lock acquire <10ms; health probe <=2s; selector query (with retries) <7s.

---

## 13. Compatibility & Support (recap)

- Python ≥ 3.10 (tested 3.12), Playwright ≥ 1.45 (tested 1.48), Chromium via Playwright (tested 129).
    
- Linux (Pop!_OS 22.04 baseline). macOS/Windows may work but are not officially supported in v1.x.
    
- Headless & CI usage: explicitly forbidden.
    

---

## 14. Reference CLI Examples

**Open:**

```
$ ai-cli-bridge open claude
✓ Browser launched (PID: 23412)
✓ Loaded: https://claude.ai/chat
✓ Ready (auth verified)
```

**Send with attach:**

```
$ ai-cli-bridge send "Analyze this data" --attach report.csv
✓ File uploaded: report.csv (2.3 MB)
✓ Message sent
✓ Response received (3.2s)
```

**List JSON (raw array):**

```
$ ai-cli-bridge list --json
[ {"index":0,"type":"text","preview":"...","length":123}, ... ]
```

**Extract:**

```
$ ai-cli-bridge extract 2 > artifact.html
✓ Extracted canvas block (2847 bytes)
```

**Doctor (startup):**

```
$ ai-cli-bridge doctor --startup
✓ Python: 3.12.0 (>= 3.10)
✓ Playwright: 1.48.0 (>= 1.45)
✓ Display: Available (Wayland)
✓ Permissions: Correct (0700)
✓ Config: Readable and valid
```

---

## 15. Acceptance Criteria (v1.3.1)

- **Headed-only** enforced; E001 on headless attempts.
    
- `open` verifies **auth readiness** per Sec. 5.
    
- `send` honors **completion detection** per Sec. 7; warns (not errors) on `response_wait` timeouts.
    
- File uploads succeed via `set_input_files` or error with E009 and actionable message.
    
- `list --json` returns **raw array**; `--envelope` available across JSON outputs.
    
- Locks created atomically; stale locks cleaned; force-kill on stuck shutdown after 5s.
    
- `doctor` and `status` emit enhanced diagnostics; permissions autocorrect surfaced.
    
- Logging, retention, and privacy rules honored.
    

---

**End of Code Specification V1.3.1**
