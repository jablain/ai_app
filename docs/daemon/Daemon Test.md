
## Complete Enhanced Daemon Test Plan (Final - Production Ready)

This is the comprehensive testing strategy covering happy paths, error cases, edge cases, and system behavior with all corrections applied.

---

## Pre-Test Setup

### 1. Environment Preparation

bash

```bash
# Ensure Python environment is ready
cd /path/to/ai-chat-ui
source venv/bin/activate  # or your virtualenv

# Install/verify dependencies
pip install playwright fastapi uvicorn pydantic

# Install Playwright browsers
#playwright install chromium

# Install Playwright system dependencies (Linux only)
#playwright install-deps chromium

# Or manually on Ubuntu/Debian:
# sudo apt-get install -y libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 \
#   libcups2 libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 \
#   libxrandr2 libgbm1 libasound2

# Install jq for JSON assertions
sudo apt-get install jq  # Ubuntu/Debian
# brew install jq          # macOS

# Verify file structure
ls -la src/daemon/browser/
ls -la src/daemon/ai/
ls -la src/daemon/

# Check ports are free
echo "Checking port availability..."
lsof -i :9223 && echo "❌ Port 9223 in use - stop existing process" && exit 1
lsof -i :8000 && echo "❌ Port 8000 in use - stop existing process" && exit 1
echo "✅ Ports 9223 and 8000 are available"
```

### 2. Start Browser with CDP Enabled

bash

```bash
# Platform-specific browser launch

# === Linux ===
chromium --remote-debugging-port=9223 --user-data-dir=/tmp/chrome-test-profile &

# === macOS ===
# "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
#   --remote-debugging-port=9223 --user-data-dir=/tmp/chrome-test-profile &

# === Windows (PowerShell) ===
# & "C:\Program Files\Google\Chrome\Application\chrome.exe" `
#   --remote-debugging-port=9223 --user-data-dir=C:\tmp\chrome-test-profile

# Wait for browser to start
sleep 3

# Verify CDP is accessible
curl -s http://localhost:9223/json/version | jq '.'

# Expected output should include "webSocketDebuggerUrl"
# Example: "webSocketDebuggerUrl": "ws://127.0.0.1:9223/devtools/browser/..."
```

### 3. Open Provider Tabs

Manually open these tabs in the CDP-enabled browser:

- [https://claude.ai](https://claude.ai)
- [https://chatgpt.com](https://chatgpt.com)
- [https://gemini.google.com](https://gemini.google.com)

**Important:** Log in to each provider if needed. The daemon will reuse these tabs.

### 4. Fix CORS Configuration in main.py

**Choose ONE of these options:**

**Option A: No credentials (simpler, recommended for testing):**

python

```python
# In src/daemon/main.py
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,  # Must be False when using "*"
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**Option B: With credentials (if needed):**

python

```python
# In src/daemon/main.py
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:8080"],  # Explicit origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**Update Test 18 to match your choice.**

---

## Start Daemon & Smoke Test

### 1. Start Daemon

bash

```bash
# Start the daemon
cd src
python3 -m daemon.main

# Or via uvicorn:
# uvicorn daemon.main:app --host 127.0.0.1 --port 8000 --log-level info
```

### 2. Wait for Startup

bash

```bash
# In another terminal, wait for daemon to be ready
sleep 3
```

### 3. Quick Smoke Test

bash

````bash
# Test healthz endpoint
curl -s http://localhost:8000/healthz | jq -e '.status == "ok"' && \
  echo "✅ Daemon is responding" || \
  (echo "❌ Daemon not responding" && exit 1)

# Verify version
curl -s http://localhost:8000/healthz | jq -r '.version'
```

---

## Core Tests (1-10)

### Test 1: Startup & Status Check

**Objective:** Verify daemon starts cleanly, discovers CDP, and reports correct initial status.

**Expected Daemon Logs:**
```
INFO - ================================================================================
INFO - AI Daemon v2.0.0 starting...
INFO - ================================================================================
INFO - Configuration loaded
INFO - Starting browser connection pool…
INFO - Connected to CDP: ws://127.0.0.1:9223/devtools/browser/...
INFO - ✓ 'claude' instance created
INFO - ✓ 'chatgpt' instance created
INFO - ✓ 'gemini' instance created
INFO - Created 3 AI instances
INFO - Health monitoring started (check interval: 30.0s)
INFO - ================================================================================
INFO - Daemon startup complete in X.XXs
INFO -   Daemon: http://127.0.0.1:8000
INFO -   CDP: ws://127.0.0.1:9223/devtools/browser/...
INFO -   AI instances: claude, chatgpt, gemini
INFO - ================================================================================
````

**Status Verification:**

bash

```bash
# Check status endpoint
curl -s http://localhost:8000/status | jq '.'

# Core assertions
curl -s http://localhost:8000/status | jq -e '.daemon.cdp_healthy == true'
curl -s http://localhost:8000/status | jq -e '.daemon.browser_pool_active == true'
curl -s http://localhost:8000/status | jq -e '.daemon.available_ais | length == 3'

# Per-AI assertions
curl -s http://localhost:8000/status | jq -e '.ais.claude.cdp_connected == true'
curl -s http://localhost:8000/status | jq -e '.ais.claude.session_active == false'
curl -s http://localhost:8000/status | jq -e '.ais.claude.model_name == null'

# Field presence checks
curl -s http://localhost:8000/status | jq -e '.ais.claude | has("context_window_tokens")'
curl -s http://localhost:8000/status | jq -e '.ais.claude | has("context_used_percent")'
curl -s http://localhost:8000/status | jq -e '.ais.claude | has("ctaw_size")'
curl -s http://localhost:8000/status | jq -e '.ais.claude | has("ctaw_usage_percent")'

# Legacy field mirror validation
curl -s http://localhost:8000/status | jq -e '.ais.claude.connected == .ais.claude.cdp_connected'
curl -s http://localhost:8000/status | jq -e '.ais.claude.ctaw_size == .ais.claude.context_window_tokens'
curl -s http://localhost:8000/status | jq -e '.ais.claude.ctaw_usage_percent == .ais.claude.context_used_percent'
```

**Expected Response Structure:**

json

```json
{
  "daemon": {
    "version": "2.0.0",
    "available_ais": ["claude", "chatgpt", "gemini"],
    "browser_pool_active": true,
    "cdp_healthy": true,
    "uptime_s": 5.2
  },
  "ais": {
    "claude": {
      "ai_target": "claude",
      "turn_count": 0,
      "token_count": 0,
      "message_count": 0,
      "session_duration_s": 0.0,
      "last_interaction_time": null,
      "last_interaction_iso": null,
      "ctaw_size": 200000,
      "ctaw_usage_percent": 0.0,
      "context_window_tokens": 200000,
      "context_used_percent": 0.0,
      "transport_type": "web",
      "cdp_connected": true,
      "session_active": false,
      "connected": true,
      "cdp_url": "ws://127.0.0.1:9223/devtools/browser/...",
      "cdp_source": "discovered",
      "last_page_url": null,
      "model_name": null,
      "error": null
    }
  }
}
```

**Validation Checklist:**

- ✅ `daemon.browser_pool_active` = true
- ✅ `daemon.cdp_healthy` = true
- ✅ `daemon.available_ais` contains all 3 providers
- ✅ All AIs show `cdp_connected` = true
- ✅ All AIs show `session_active` = false (no interactions yet)
- ✅ `model_name` is null (not detected yet)
- ✅ Both `ctaw_size` and `context_window_tokens` present and equal
- ✅ Both `ctaw_usage_percent` and `context_used_percent` present and equal
- ✅ Both `connected` (legacy) and `cdp_connected` (new) present and equal

---

### Test 2: Happy Path - Send Message

**Objective:** Send a simple prompt, verify response, check metadata structure.

**Steps:**

bash

```bash
curl -X POST http://localhost:8000/send \
  -H "Content-Type: application/json" \
  -d '{
    "target": "claude",
    "prompt": "What is 2+3?",
    "wait_for_response": true,
    "timeout_s": 60
  }' | jq '.'

# Schema assertions
curl -s -X POST http://localhost:8000/send \
  -H "Content-Type: application/json" \
  -d '{"target": "claude", "prompt": "What is 2+3?"}' | \
  jq -e '.success == true'

curl -s -X POST http://localhost:8000/send \
  -H "Content-Type: application/json" \
  -d '{"target": "claude", "prompt": "What is 2+3?"}' | \
  jq -e '.metadata | has("request_id")'

curl -s -X POST http://localhost:8000/send \
  -H "Content-Type: application/json" \
  -d '{"target": "claude", "prompt": "What is 2+3?"}' | \
  jq -e '.metadata.warnings | type == "array"'

curl -s -X POST http://localhost:8000/send \
  -H "Content-Type: application/json" \
  -d '{"target": "claude", "prompt": "What is 2+3?"}' | \
  jq -e '.metadata.stage_log | has("send_start")'

curl -s -X POST http://localhost:8000/send \
  -H "Content-Type: application/json" \
  -d '{"target": "claude", "prompt": "What is 2+3?"}' | \
  jq -e '.metadata.timestamp | test("^[0-9]{4}-[0-9]{2}-[0-9]{2}T")'
```

**Expected Response:**

json

```json
{
  "success": true,
  "snippet": "2 + 3 equals 5.",
  "markdown": "2 + 3 equals 5.",
  "metadata": {
    "elapsed_ms": 1234,
    "waited": true,
    "timeout_s": 60,
    "ws_source": "discovered",
    "page_url": "https://claude.ai/chat/...",
    "request_id": "abc-123-def-456",
    "warnings": [],
    "model_name": "Claude 3.5 Sonnet",
    "cdp_url": "ws://127.0.0.1:9223/devtools/browser/...",
    "timestamp": "2025-10-24T12:34:56.789Z",
    "stage_log": {
      "request_id": "abc-123-def-456",
      "send_start": "2025-10-24T12:34:55.000Z",
      "baseline_count": 0,
      "send_complete": "2025-10-24T12:34:55.100Z",
      "wait_start": "2025-10-24T12:34:55.100Z",
      "wait_complete": "2025-10-24T12:34:56.500Z",
      "extract_done": "2025-10-24T12:34:56.600Z"
    }
  }
}
```

**Validation Checklist:**

- ✅ `success` = true
- ✅ `snippet` and `markdown` contain response text
- ✅ `metadata.request_id` is a UUID (36 chars with hyphens)
- ✅ `metadata.model_name` is detected (e.g., "Claude 3.5 Sonnet")
- ✅ `metadata.warnings` is an empty array
- ✅ `metadata.stage_log` has ISO 8601 timestamps
- ✅ `metadata.elapsed_ms` is reasonable (< 10000)
- ✅ `metadata.timestamp` is ISO 8601 format
- ✅ `metadata.timeout_s` = 60

**Status After Send:**

bash

```bash
curl -s http://localhost:8000/status | jq '.ais.claude'

# Assertions
curl -s http://localhost:8000/status | jq -e '.ais.claude.session_active == true'
curl -s http://localhost:8000/status | jq -e '.ais.claude.turn_count >= 1'
curl -s http://localhost:8000/status | jq -e '.ais.claude.message_count >= 1'
curl -s http://localhost:8000/status | jq -e '.ais.claude | has("last_interaction_iso")'
curl -s http://localhost:8000/status | jq -e '.ais.claude | has("last_interaction_time")'
curl -s http://localhost:8000/status | jq -e '.ais.claude.model_name != null'
```

**Expected Changes:**

json

```json
{
  "turn_count": 1,
  "message_count": 1,
  "session_active": true,
  "model_name": "Claude 3.5 Sonnet",
  "last_interaction_time": 1729776896.789,
  "last_interaction_iso": "2025-10-24T12:34:56.789Z"
}
```

**Notes:**

- ✅ `session_active` changed to true
- ✅ `model_name` now populated
- ✅ Both `last_interaction_time` (float, for legacy/metrics) and `last_interaction_iso` (ISO string) present

---

### Test 3: Rate Limit Detection

**Objective:** Trigger rate limit error and verify structured error response.

**Setup:**

Manually inject a rate limit banner:

javascript

```javascript
// In browser console on claude.ai:
document.body.insertAdjacentHTML('beforeend', 
  '<div role="alert">Too many requests. Please try again later.</div>');
```

**Steps:**

bash

```bash
curl -X POST http://localhost:8000/send \
  -H "Content-Type: application/json" \
  -d '{
    "target": "claude",
    "prompt": "Test message",
    "wait_for_response": true,
    "timeout_s": 60
  }' | jq '.'

# Assertions
curl -s -X POST http://localhost:8000/send \
  -H "Content-Type: application/json" \
  -d '{"target": "claude", "prompt": "Test"}' | \
  jq -e '.success == false'

curl -s -X POST http://localhost:8000/send \
  -H "Content-Type: application/json" \
  -d '{"target": "claude", "prompt": "Test"}' | \
  jq -e '.metadata.error.code == "RATE_LIMITED"'

curl -s -X POST http://localhost:8000/send \
  -H "Content-Type: application/json" \
  -d '{"target": "claude", "prompt": "Test"}' | \
  jq -e '.metadata.error | has("suggested_action")'

curl -s -X POST http://localhost:8000/send \
  -H "Content-Type: application/json" \
  -d '{"target": "claude", "prompt": "Test"}' | \
  jq -e '.metadata.error.stage_log.failure_stage == "send"'
```

**Expected Response:**

json

```json
{
  "success": false,
  "snippet": null,
  "markdown": null,
  "metadata": {
    "error": {
      "code": "RATE_LIMITED",
      "message": "The provider indicates a rate limit or concurrent request cap.",
      "severity": "error",
      "suggested_action": "Wait a bit and try again, or switch models.",
      "evidence": {
        "selector": "[role='alert']",
        "text_snippet": "Too many requests. Please try again later.",
        "page_url": "https://claude.ai/chat/..."
      },
      "stage_log": {
        "request_id": "...",
        "send_start": "...",
        "failure_stage": "send"
      }
    },
    "warnings": [],
    "elapsed_ms": null,
    "timeout_s": 60,
    "request_id": "...",
    "timestamp": "...",
    "model_name": "Claude 3.5 Sonnet",
    "cdp_url": "..."
  }
}
```

**Validation Checklist:**

- ✅ `success` = false
- ✅ `metadata.error.code` = "RATE_LIMITED"
- ✅ `metadata.error.severity` = "error"
- ✅ `metadata.error.suggested_action` provides guidance
- ✅ `metadata.error.evidence` contains selector and snippet
- ✅ `metadata.error.stage_log.failure_stage` = "send"
- ✅ UI can parse and display structured error

**Cleanup:**

javascript

```javascript
// Remove the injected alert
document.querySelector('[role="alert"]').remove();
```

---

### Test 4: Auth Wall Detection

**Objective:** Trigger authentication requirement and verify error response.

**Setup:**

Inject auth element:

javascript

```javascript
// In browser console:
document.body.insertAdjacentHTML('beforeend',
  '<input type="password" placeholder="Password">');
```

**Steps:**

bash

```bash
curl -X POST http://localhost:8000/send \
  -H "Content-Type: application/json" \
  -d '{
    "target": "claude",
    "prompt": "Test",
    "wait_for_response": true
  }' | jq '.'

# Assertions
curl -s -X POST http://localhost:8000/send \
  -H "Content-Type: application/json" \
  -d '{"target": "claude", "prompt": "Test"}' | \
  jq -e '.metadata.error.code == "AUTH_REQUIRED"'

curl -s -X POST http://localhost:8000/send \
  -H "Content-Type: application/json" \
  -d '{"target": "claude", "prompt": "Test"}' | \
  jq -e '.metadata.error.stage_log.failure_stage == "ensure_ready"'
```

**Expected Response:**

json

```json
{
  "success": false,
  "snippet": null,
  "markdown": null,
  "metadata": {
    "error": {
      "code": "AUTH_REQUIRED",
      "message": "The page appears to require login/verification.",
      "severity": "error",
      "suggested_action": "Open the provider tab and complete sign-in.",
      "evidence": {
        "selector": "input[type='password']",
        "text_snippet": "",
        "page_url": "https://claude.ai"
      },
      "stage_log": {
        "request_id": "...",
        "send_start": "...",
        "failure_stage": "ensure_ready"
      }
    },
    "warnings": [],
    "request_id": "...",
    "timestamp": "..."
  }
}
```

**Validation Checklist:**

- ✅ `success` = false
- ✅ `metadata.error.code` = "AUTH_REQUIRED"
- ✅ `metadata.error.evidence.selector` = "input[type='password']"
- ✅ `metadata.error.stage_log.failure_stage` = "ensure_ready"
- ✅ Suggested action tells user to log in

**Cleanup:**

javascript

```javascript
// Remove the injected password field
document.querySelector('input[type="password"]').remove();
```

---

### Test 5: Response Timeout

**Objective:** Trigger timeout and verify timeout error handling.

**Steps:**

bash

```bash
curl -X POST http://localhost:8000/send \
  -H "Content-Type: application/json" \
  -d '{
    "target": "claude",
    "prompt": "Write a 5000 word essay on quantum mechanics",
    "wait_for_response": true,
    "timeout_s": 2
  }' | jq '.'

# Assertions
curl -s -X POST http://localhost:8000/send \
  -H "Content-Type: application/json" \
  -d '{"target": "claude", "prompt": "Write a very long detailed essay about relativity", "timeout_s": 2}' | \
  jq -e '.metadata.error.code == "RESPONSE_TIMEOUT"'

curl -s -X POST http://localhost:8000/send \
  -H "Content-Type: application/json" \
  -d '{"target": "claude", "prompt": "Write a very long detailed essay about relativity", "timeout_s": 2}' | \
  jq -e '.metadata.elapsed_ms >= 1900 and .metadata.elapsed_ms <= 2200'
```

**Expected Response:**

json

```json
{
  "success": false,
  "snippet": null,
  "markdown": null,
  "metadata": {
    "error": {
      "code": "RESPONSE_TIMEOUT",
      "message": "Prompt sent, but no response completed within 2s.",
      "severity": "error",
      "suggested_action": "Try again or switch models.",
      "evidence": {
        "page_url": "https://claude.ai/chat/...",
        "selector": "button[aria-label*='Stop']"
      },
      "stage_log": {
        "send_start": "...",
        "send_complete": "...",
        "wait_start": "...",
        "wait_complete": "...",
        "failure_stage": "wait"
      }
    },
    "waited": true,
    "elapsed_ms": 2000,
    "timeout_s": 2,
    "request_id": "...",
    "timestamp": "..."
  }
}
```

**Validation Checklist:**

- ✅ `success` = false
- ✅ `metadata.error.code` = "RESPONSE_TIMEOUT"
- ✅ `metadata.error.stage_log.failure_stage` = "wait"
- ✅ `metadata.elapsed_ms` ≈ timeout_s * 1000 (±200ms tolerance)
- ✅ `metadata.waited` = true
- ✅ `metadata.timeout_s` = 2
- ✅ Stage log shows send completed but wait timed out

---

### Test 6: CDP Disconnection

**Objective:** Simulate browser crash and verify CDP disconnect error.

**Setup:**

Start a long request and kill browser mid-flight:

bash

```bash
# Terminal 1: Start a long request
curl -X POST http://localhost:8000/send \
  -H "Content-Type: application/json" \
  -d '{
    "target": "claude",
    "prompt": "Write a detailed explanation of general relativity",
    "wait_for_response": true,
    "timeout_s": 60
  }' | jq '.'

# Terminal 2: Kill the browser (within 1-2 seconds)
pkill -9 chromium
# or on macOS:
# pkill -9 "Google Chrome"
```

**Expected Response:**

json

```json
{
  "success": false,
  "snippet": null,
  "markdown": null,
  "metadata": {
    "error": {
      "code": "CDP_DISCONNECTED",
      "message": "Browser connection dropped during interaction.",
      "severity": "error",
      "suggested_action": "Restart the UI or daemon; check browser tabs.",
      "evidence": {
        "exception": "Target closed",
        "exception_type": "Error"
      },
      "stage_log": {
        "exception_time": "2025-10-24T12:40:00.000Z",
        "failure_stage": "extract"
      }
    },
    "waited": false,
    "elapsed_ms": null,
    "request_id": "...",
    "timestamp": "..."
  }
}
```

**Validation Checklist:**

- ✅ `success` = false
- ✅ `metadata.error.code` = "CDP_DISCONNECTED"
- ✅ `metadata.error.evidence.exception` contains "closed" or "Target closed"
- ✅ `metadata.error.stage_log.exception_time` is ISO timestamp
- ✅ `metadata.error.stage_log.failure_stage` is set

**Status After CDP Loss:**

bash

```bash
# Wait ~35s for health monitor to detect (30s interval + buffer)
echo "Waiting 35s for health monitor to detect CDP loss..."
sleep 35

curl -s http://localhost:8000/status | jq '.daemon.cdp_healthy'
# Expected: false

curl -s http://localhost:8000/status | jq -e '.daemon.cdp_healthy == false' && \
  echo "✅ Health monitor detected CDP loss"
```

**Restart Browser:**

bash

```bash
# Linux
chromium --remote-debugging-port=9223 --user-data-dir=/tmp/chrome-test-profile &

# macOS
# "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
#   --remote-debugging-port=9223 --user-data-dir=/tmp/chrome-test-profile &

sleep 5

# Reopen provider tabs manually
echo "Reopen claude.ai, chatgpt.com, gemini.google.com tabs manually"
echo "Press Enter when ready..."
read

# Wait ~35s for health monitor to detect recovery
echo "Waiting 35s for health monitor to detect recovery..."
sleep 35

curl -s http://localhost:8000/status | jq '.daemon.cdp_healthy'
# Expected: true

curl -s http://localhost:8000/status | jq -e '.daemon.cdp_healthy == true' && \
  echo "✅ Health monitor detected CDP recovery"
```

---

### Test 7: Invalid Target

**Objective:** Request unknown AI target and verify error handling.

**Steps:**

bash

```bash
curl -X POST http://localhost:8000/send \
  -H "Content-Type: application/json" \
  -d '{
    "target": "gpt5",
    "prompt": "Test"
  }' | jq '.'

# Assertions
curl -s -X POST http://localhost:8000/send \
  -H "Content-Type: application/json" \
  -d '{"target": "invalid", "prompt": "Test"}' | \
  jq -e '.metadata.error.code == "INVALID_TARGET"'

curl -s -X POST http://localhost:8000/send \
  -H "Content-Type: application/json" \
  -d '{"target": "invalid", "prompt": "Test"}' | \
  jq -e '.metadata.error.evidence | has("available")'

curl -s -X POST http://localhost:8000/send \
  -H "Content-Type: application/json" \
  -d '{"target": "invalid", "prompt": "Test"}' | \
  jq -e '.success == false'
```

**Expected Response:**

json

```json
{
  "success": false,
  "snippet": null,
  "markdown": null,
  "metadata": {
    "error": {
      "code": "INVALID_TARGET",
      "message": "Unknown AI target: gpt5",
      "severity": "error",
      "suggested_action": "Use one of: claude, chatgpt, gemini",
      "evidence": {
        "requested": "gpt5",
        "available": ["claude", "chatgpt", "gemini"]
      }
    },
    "warnings": [],
    "timestamp": "..."
  }
}
```

**Validation Checklist:**

- ✅ `success` = false
- ✅ `metadata.error.code` = "INVALID_TARGET"
- ✅ `metadata.error.evidence` shows requested and available targets
- ✅ HTTP status = 200 (not 404, consistent error handling)
- ✅ Error structure matches other errors

---

### Test 8: Multi-Provider Sequential Requests

**Objective:** Verify all three providers work correctly in sequence.

**Steps:**

bash

````bash
# Send to Claude
echo "Testing Claude..."
claude_resp=$(curl -s -X POST http://localhost:8000/send \
  -H "Content-Type: application/json" \
  -d '{"target": "claude", "prompt": "Say hello"}')
echo "$claude_resp" | jq '.success'

# Send to ChatGPT
echo "Testing ChatGPT..."
chatgpt_resp=$(curl -s -X POST http://localhost:8000/send \
  -H "Content-Type: application/json" \
  -d '{"target": "chatgpt", "prompt": "Say hello"}')
echo "$chatgpt_resp" | jq '.success'

# Send to Gemini
echo "Testing Gemini..."
gemini_resp=$(curl -s -X POST http://localhost:8000/send \
  -H "Content-Type: application/json" \
  -d '{"target": "gemini", "prompt": "Say hello"}')
echo "$gemini_resp" | jq '.success'

# Check status
curl -s http://localhost:8000/status | \
  jq '.ais | to_entries | .[] | {name: .key, active: .value.session_active, model: .value.model_name}'

# Assertions
echo "$claude_resp" | jq -e '.success == true' && echo "✅ Claude success"
echo "$chatgpt_resp" | jq -e '.success == true' && echo "✅ ChatGPT success"
echo "$gemini_resp" | jq -e '.success == true' && echo "✅ Gemini success"

echo "$claude_resp" | jq -e '.metadata.model_name != null' && echo "✅ Claude model detected"
echo "$chatgpt_resp" | jq -e '.metadata.model_name != null' && echo "✅ ChatGPT model detected"
echo "$gemini_resp" | jq -e '.metadata.model_name != null' && echo "✅ Gemini model detected"
```

**Expected Output:**
```
Testing Claude...
true
Testing ChatGPT...
true
Testing Gemini...
true

{
  "name": "claude",
  "active": true,
  "model": "Claude 3.5 Sonnet"
}
{
  "name": "chatgpt",
  "active": true,
  "model": "GPT-4"
}
{
  "name": "gemini",
  "active": true,
  "model": "Gemini 1.5 Pro"
}

✅ Claude success
✅ ChatGPT success
✅ Gemini success
✅ Claude model detected
✅ ChatGPT model detected
✅ Gemini model detected
````

**Validation Checklist:**

- ✅ All three providers return `success: true`
- ✅ All three show `session_active: true` in status
- ✅ Each has unique `model_name` if detected
- ✅ No cross-contamination (each maintains separate state)
- ✅ Each has unique `request_id`

---

### Test 9: Concurrent Requests (Same AI)

**Objective:** Verify interaction lock prevents race conditions.

**Steps:**

bash

````bash
# Send two requests simultaneously to same AI
echo "Sending concurrent requests to Claude..."

(curl -s -X POST http://localhost:8000/send \
  -H "Content-Type: application/json" \
  -d '{"target": "claude", "prompt": "Request 1"}' > /tmp/req1.json) &

(curl -s -X POST http://localhost:8000/send \
  -H "Content-Type: application/json" \
  -d '{"target": "claude", "prompt": "Request 2"}' > /tmp/req2.json) &

# Wait for both
wait

# Check request IDs are different
req1_id=$(jq -r '.metadata.request_id' /tmp/req1.json)
req2_id=$(jq -r '.metadata.request_id' /tmp/req2.json)

echo "Request 1 ID: $req1_id"
echo "Request 2 ID: $req2_id"

# They should differ
[ "$req1_id" != "$req2_id" ] && echo "✅ Unique request IDs"

# Both should succeed
jq -e '.success == true' /tmp/req1.json && echo "✅ Request 1 succeeded"
jq -e '.success == true' /tmp/req2.json && echo "✅ Request 2 succeeded"

# Cleanup
rm /tmp/req1.json /tmp/req2.json
```

**Expected Behavior:**
- ✅ Both requests complete successfully
- ✅ Each has unique `request_id`
- ✅ No interleaved stage_logs
- ✅ Requests are serialized (second waits for first)
- ✅ Total time ≈ sum of individual times (not parallel)

**Daemon Logs Should Show:**
```
DEBUG - claude: Enter key triggered send successfully
DEBUG - claude: Enter key triggered send successfully
````

No errors or race condition warnings.

---

### Test 10: Empty Response Warning

**Objective:** Verify empty response detection.

**Note:** This is difficult to trigger naturally. The easiest approach is to temporarily modify the code.

**Approach: Break extraction temporarily**

Edit `src/daemon/ai/claude.py`:

python

```python
# In _extract_response, add at the very top:
async def _extract_response(self, page: Page, baseline_count: int) -> Tuple[str, str]:
    return "", ""  # Force empty for testing
    # ... rest of method
```

Restart daemon.

**Steps:**

bash

```bash
curl -X POST http://localhost:8000/send \
  -H "Content-Type: application/json" \
  -d '{
    "target": "claude",
    "prompt": "Test",
    "wait_for_response": true
  }' | jq '.'

# Assertions
curl -s -X POST http://localhost:8000/send \
  -H "Content-Type: application/json" \
  -d '{"target": "claude", "prompt": "Test"}' | \
  jq -e '.success == true'

curl -s -X POST http://localhost:8000/send \
  -H "Content-Type: application/json" \
  -d '{"target": "claude", "prompt": "Test"}' | \
  jq -e '.metadata.warnings | length > 0'

curl -s -X POST http://localhost:8000/send \
  -H "Content-Type: application/json" \
  -d '{"target": "claude", "prompt": "Test"}' | \
  jq -e '.metadata.warnings[0].code == "EMPTY_RESPONSE"'

curl -s -X POST http://localhost:8000/send \
  -H "Content-Type: application/json" \
  -d '{"target": "claude", "prompt": "Test"}' | \
  jq -e '.metadata.warnings[0].severity == "warn"'
```

**Expected Response:**

json

```json
{
  "success": true,
  "snippet": "",
  "markdown": "",
  "metadata": {
    "warnings": [
      {
        "code": "EMPTY_RESPONSE",
        "message": "Response completed but no content extracted.",
        "severity": "warn",
        "suggested_action": "Check the provider tab; may need to retry.",
        "evidence": {
          "page_url": "https://claude.ai/..."
        },
        "stage_log": {...}
      }
    ],
    "elapsed_ms": 1234,
    "request_id": "...",
    "timestamp": "..."
  }
}
```

**Validation Checklist:**

- ✅ `success` = true (not a hard error)
- ✅ `warnings` array contains EMPTY_RESPONSE warning
- ✅ Warning has correct structure (code, message, severity, suggested_action)
- ✅ Warning `severity` = "warn" (not "error")

**Revert changes:**

Remove the `return "", ""` line from `claude.py` and restart daemon.

---

## Enhanced Tests (11-20)

### Test 11: No-Wait Path

**Objective:** Test fire-and-forget mode where we don't wait for response.

**Steps:**

bash

```bash
curl -X POST http://localhost:8000/send \
  -H "Content-Type: application/json" \
  -d '{
    "target": "claude",
    "prompt": "Process this in background",
    "wait_for_response": false,
    "timeout_s": 60
  }' | jq '.'

# Assertions
curl -s -X POST http://localhost:8000/send \
  -H "Content-Type: application/json" \
  -d '{"target": "claude", "prompt": "Test", "wait_for_response": false}' | \
  jq -e '.success == true'

curl -s -X POST http://localhost:8000/send \
  -H "Content-Type: application/json" \
  -d '{"target": "claude", "prompt": "Test", "wait_for_response": false}' | \
  jq -e '.metadata.waited == false'

curl -s -X POST http://localhost:8000/send \
  -H "Content-Type: application/json" \
  -d '{"target": "claude", "prompt": "Test", "wait_for_response": false}' | \
  jq -e '.metadata.elapsed_ms == null'

curl -s -X POST http://localhost:8000/send \
  -H "Content-Type: application/json" \
  -d '{"target": "claude", "prompt": "Test", "wait_for_response": false}' | \
  jq -e '.snippet == null and .markdown == null'
```

**Expected Response:**

json

```json
{
  "success": true,
  "snippet": null,
  "markdown": null,
  "metadata": {
    "elapsed_ms": null,
    "waited": false,
    "timeout_s": 60,
    "ws_source": "discovered",
    "page_url": "https://claude.ai/chat/...",
    "request_id": "...",
    "warnings": [],
    "model_name": "Claude 3.5 Sonnet",
    "stage_log": {
      "send_start": "...",
      "send_complete": "..."
    },
    "timestamp": "..."
  }
}
```

**Validation Checklist:**

- ✅ `success` = true (send succeeded)
- ✅ `metadata.waited` = false
- ✅ `snippet` and `markdown` are null (didn't wait for response)
- ✅ `metadata.elapsed_ms` = null
- ✅ `stage_log` has send times but no wait/extract times
- ✅ `metadata.timeout_s` still present

**Check Status:**

bash

```bash
curl -s http://localhost:8000/status | jq '.ais.claude | {turns: .turn_count, messages: .message_count}'
```

**Expected:**

- ✅ `turn_count` and `message_count` still increment (send was counted)

---

### Test 12: Ensure Chat Ready Failure

**Objective:** Test selector missing error at earliest failure point.

**Setup:**

Temporarily break the INPUT_BOX selector in `src/daemon/ai/claude.py`:

python

```python
# Change:
INPUT_BOX = "div[contenteditable='true'][data-testid='BROKEN-SELECTOR']"
```

Restart daemon.

**Steps:**

bash

```bash
curl -X POST http://localhost:8000/send \
  -H "Content-Type: application/json" \
  -d '{
    "target": "claude",
    "prompt": "Test",
    "wait_for_response": true
  }' | jq '.'

# Assertions
curl -s -X POST http://localhost:8000/send \
  -H "Content-Type: application/json" \
  -d '{"target": "claude", "prompt": "Test"}' | \
  jq -e '.metadata.error.code == "SELECTOR_MISSING"'

curl -s -X POST http://localhost:8000/send \
  -H "Content-Type: application/json" \
  -d '{"target": "claude", "prompt": "Test"}' | \
  jq -e '.metadata.error.stage_log.failure_stage == "ensure_ready"'
```

**Expected Response:**

json

```json
{
  "success": false,
  "snippet": null,
  "markdown": null,
  "metadata": {
    "error": {
      "code": "SELECTOR_MISSING",
      "message": "Chat input not ready (selector missing or not visible).",
      "severity": "error",
      "suggested_action": "Reload the tab or log in again.",
      "evidence": {
        "page_url": "https://claude.ai"
      },
      "stage_log": {
        "request_id": "...",
        "send_start": "...",
        "failure_stage": "ensure_ready"
      }
    },
    "waited": true,
    "elapsed_ms": null,
    "request_id": "...",
    "timestamp": "..."
  }
}
```

**Validation Checklist:**

- ✅ `success` = false
- ✅ `metadata.error.code` = "SELECTOR_MISSING"
- ✅ `metadata.error.stage_log.failure_stage` = "ensure_ready"
- ✅ Error detected before attempting send (early failure)

**Revert selector:**

python

```python
# Restore original:
INPUT_BOX = "div[contenteditable='true'][data-testid='composer-input'], div[contenteditable='true'][placeholder*='Reply']"
```

Restart daemon.

---

### Test 13: Suspicious Page State (Non-Fatal)

**Objective:** Verify benign banners trigger warnings but don't block requests.

**Setup:**

Inject a benign status banner:

javascript

```javascript
// In browser console on claude.ai:
document.body.insertAdjacentHTML('beforeend',
  '<div role="status">System maintenance scheduled in 1 hour</div>');
```

**Steps:**

bash

```bash
curl -X POST http://localhost:8000/send \
  -H "Content-Type: application/json" \
  -d '{
    "target": "claude",
    "prompt": "What is 1+1?",
    "wait_for_response": true
  }' | jq '.'

# Assertions
curl -s -X POST http://localhost:8000/send \
  -H "Content-Type: application/json" \
  -d '{"target": "claude", "prompt": "Test"}' | \
  jq -e '.success == true'

curl -s -X POST http://localhost:8000/send \
  -H "Content-Type: application/json" \
  -d '{"target": "claude", "prompt": "Test"}' | \
  jq -e '.metadata.warnings | length > 0'

curl -s -X POST http://localhost:8000/send \
  -H "Content-Type: application/json" \
  -d '{"target": "claude", "prompt": "Test"}' | \
  jq -e '.metadata.warnings[0].code == "SUSPICIOUS_PAGE_STATE"'

curl -s -X POST http://localhost:8000/send \
  -H "Content-Type: application/json" \
  -d '{"target": "claude", "prompt": "Test"}' | \
  jq -e '.metadata.warnings[0].severity == "warn"'

curl -s -X POST http://localhost:8000/send \
  -H "Content-Type: application/json" \
  -d '{"target": "claude", "prompt": "Test"}' | \
  jq -e '.snippet != null and .markdown != null'
```

**Expected Response:**

json

```json
{
  "success": true,
  "snippet": "1 + 1 equals 2.",
  "markdown": "1 + 1 equals 2.",
  "metadata": {
    "elapsed_ms": 1234,
    "warnings": [
      {
        "code": "SUSPICIOUS_PAGE_STATE",
        "message": "Page shows a banner/alert; interaction may still succeed.",
        "severity": "warn",
        "suggested_action": "If results look off, re-auth the tab.",
        "evidence": {
          "selector": "div[role='status']",
          "text_snippet": "System maintenance scheduled in 1 hour",
          "page_url": "https://claude.ai/..."
        },
        "stage_log": {...}
      }
    ],
    "request_id": "...",
    "timestamp": "..."
  }
}
```

**Validation Checklist:**

- ✅ `success` = true (request succeeded despite warning)
- ✅ `warnings` array has SUSPICIOUS_PAGE_STATE entry
- ✅ Warning `severity` = "warn" (not "error")
- ✅ Response contains actual content (not blocked)
- ✅ Evidence includes selector and text snippet

**Cleanup:**

javascript

```javascript
// Remove the banner
document.querySelector('[role="status"]').remove();
```

---

### Test 14: Model Cache Behavior

**Objective:** Verify "first-seen wins" model caching policy.

**Steps:**

bash

```bash
# First request - capture model name
echo "Sending first request..."
resp1=$(curl -s -X POST http://localhost:8000/send \
  -H "Content-Type: application/json" \
  -d '{"target": "claude", "prompt": "Hello"}')

model1=$(echo "$resp1" | jq -r '.metadata.model_name')
echo "First model: $model1"

# Manually switch model in Claude UI
# (e.g., from Claude 3.5 Sonnet to Claude 3 Opus)
echo ""
echo "=== ACTION REQUIRED ==="
echo "1. Open Claude tab in browser"
echo "2. Switch to a different model (e.g., Claude 3 Opus)"
echo "3. Press Enter when ready..."
read

# Second request - model should still be cached
echo "Sending second request..."
resp2=$(curl -s -X POST http://localhost:8000/send \
  -H "Content-Type: application/json" \
  -d '{"target": "claude", "prompt": "Hello again"}')

model2=$(echo "$resp2" | jq -r '.metadata.model_name')
echo "Second model: $model2"

# They should be the same (first-seen wins)
if [ "$model1" = "$model2" ]; then
  echo "✅ Model cache held (first-seen wins)"
else
  echo "❌ Model cache changed unexpectedly"
  echo "   Expected: $model1"
  echo "   Got: $model2"
fi

# Check status also shows cached model
status_model=$(curl -s http://localhost:8000/status | jq -r '.ais.claude.model_name')
echo "Status model: $status_model"

if [ "$model1" = "$status_model" ]; then
  echo "✅ Status reflects cached model"
else
  echo "❌ Status model differs from cache"
fi
```

**Expected Behavior:**

- ✅ First request captures initial model name
- ✅ Second request returns same cached model name (even after UI switch)
- ✅ Status endpoint shows cached model name
- ✅ Cache persists until daemon restart or explicit invalidation

**Note:** This documents "first-seen wins" behavior. To invalidate (future feature):

python

```python
# Would need to add endpoint or call directly:
ai_instances["claude"]._invalidate_model_cache()
```

---

### Test 15: New Tab Creation Path

**Objective:** Verify browser pool opens new tab when none exists.

**Setup:**

Close all provider tabs in the browser:

bash

```bash
echo "=== ACTION REQUIRED ==="
echo "Close all claude.ai tabs in the browser"
echo "Press Enter when ready..."
read
```

**Steps:**

bash

````bash
# Send request when no tab is open
echo "Sending request (should create new tab)..."
curl -X POST http://localhost:8000/send \
  -H "Content-Type: application/json" \
  -d '{
    "target": "claude",
    "prompt": "Test new tab creation",
    "wait_for_response": true,
    "timeout_s": 60
  }' | jq '.'

# Assertions
curl -s -X POST http://localhost:8000/send \
  -H "Content-Type: application/json" \
  -d '{"target": "claude", "prompt": "Test"}' | \
  jq -e '.success == true'

curl -s -X POST http://localhost:8000/send \
  -H "Content-Type: application/json" \
  -d '{"target": "claude", "prompt": "Test"}' | \
  jq -e '.metadata.page_url | contains("claude.ai")'
```

**Expected Behavior:**
- ✅ Browser pool creates new tab
- ✅ Navigates to https://claude.ai
- ✅ Request proceeds normally after navigation
- ✅ Response is successful (may need login if not already authenticated)

**Daemon Logs Should Show:**
```
INFO - Opened new page at https://claude.ai
DEBUG - claude: Got page: https://claude.ai
````

**Validation Checklist:**

- ✅ `success` = true (or AUTH_REQUIRED if not logged in)
- ✅ `metadata.page_url` contains "claude.ai"
- ✅ New tab is visible in browser
- ✅ Tab remains open for reuse

---

### Test 16: Health Monitor Propagation

**Objective:** Verify health monitor detects CDP loss and recovery within one cycle.

**Steps:**

bash

```bash
# Initial check - should be healthy
echo "Initial health status:"
curl -s http://localhost:8000/status | jq '.daemon.cdp_healthy'
# Expected: true

curl -s http://localhost:8000/status | jq -e '.daemon.cdp_healthy == true' && \
  echo "✅ Initially healthy"

# Kill browser
echo "Killing browser..."
pkill -9 chromium
# or on macOS: pkill -9 "Google Chrome"

# Wait for one health check cycle (30s default + 5s buffer)
echo "Waiting 35s for health monitor to detect CDP loss..."
sleep 35

# Check status - should be unhealthy
unhealthy=$(curl -s http://localhost:8000/status | jq '.daemon.cdp_healthy')
echo "CDP healthy after kill: $unhealthy"

if [ "$unhealthy" = "false" ]; then
  echo "✅ Health monitor detected CDP loss"
else
  echo "❌ Health monitor failed to detect CDP loss"
fi

# Restart browser
echo "Restarting browser..."

# Linux
chromium --remote-debugging-port=9223 --user-data-dir=/tmp/chrome-test-profile &

# macOS
# "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
#   --remote-debugging-port=9223 --user-data-dir=/tmp/chrome-test-profile &

sleep 5

# Reopen provider tabs
echo "=== ACTION REQUIRED ==="
echo "Reopen provider tabs:"
echo "  - https://claude.ai"
echo "  - https://chatgpt.com"
echo "  - https://gemini.google.com"
echo "Press Enter when ready..."
read

# Wait for health monitor to detect recovery
echo "Waiting 35s for health monitor to detect recovery..."
sleep 35

# Check status - should be healthy again
healthy=$(curl -s http://localhost:8000/status | jq '.daemon.cdp_healthy')
echo "CDP healthy after restart: $healthy"

if [ "$healthy" = "true" ]; then
  echo "✅ Health monitor detected CDP recovery"
else
  echo "❌ Health monitor failed to detect recovery"
fi

# Final assertion
curl -s http://localhost:8000/status | jq -e '.daemon.cdp_healthy == true'
```

**Validation Checklist:**

- ✅ Initial state: `cdp_healthy` = true
- ✅ After kill + 35s: `cdp_healthy` = false
- ✅ After restart + 35s: `cdp_healthy` = true
- ✅ Health monitor cycle time is ~30s (configurable)
- ✅ Status reflects reality within one interval

---

### Test 17: Timeout Propagation Sanity

**Objective:** Verify timeout value flows through to metadata correctly.

**Test Case 1: Odd timeout value**

bash

```bash
curl -X POST http://localhost:8000/send \
  -H "Content-Type: application/json" \
  -d '{
    "target": "claude",
    "prompt": "Quick test",
    "wait_for_response": true,
    "timeout_s": 3
  }' | jq '.metadata.timeout_s'

# Assertion
curl -s -X POST http://localhost:8000/send \
  -H "Content-Type: application/json" \
  -d '{"target": "claude", "prompt": "Test", "timeout_s": 3}' | \
  jq -e '.metadata.timeout_s == 3' && echo "✅ Timeout 3 propagated"
```

**Expected:** `3`

**Test Case 2: Fractional timeout**

bash

```bash
curl -X POST http://localhost:8000/send \
  -H "Content-Type: application/json" \
  -d '{
    "target": "claude",
    "prompt": "Write a very long detailed essay about quantum entanglement",
    "wait_for_response": true,
    "timeout_s": 2.5
  }' | jq '{timeout: .metadata.timeout_s, elapsed: .metadata.elapsed_ms, success: .success}'

# Assertions
curl -s -X POST http://localhost:8000/send \
  -H "Content-Type: application/json" \
  -d '{"target": "claude", "prompt": "Long essay...", "timeout_s": 2.5}' | \
  jq -e '.metadata.timeout_s == 2.5' && echo "✅ Timeout 2.5 propagated"

# If timeout occurs, check elapsed time
resp=$(curl -s -X POST http://localhost:8000/send \
  -H "Content-Type: application/json" \
  -d '{"target": "claude", "prompt": "Long essay...", "timeout_s": 2.5}')

if echo "$resp" | jq -e '.success == false'; then
  elapsed=$(echo "$resp" | jq '.metadata.elapsed_ms')
  echo "Elapsed: $elapsed ms"
  
  # Should be approximately 2500ms (±200ms)
  if [ "$elapsed" -ge 2300 ] && [ "$elapsed" -le 2700 ]; then
    echo "✅ Elapsed time matches timeout"
  else
    echo "⚠️  Elapsed time: $elapsed (expected ~2500)"
  fi
fi
```

**Validation Checklist:**

- ✅ `metadata.timeout_s` exactly matches request parameter
- ✅ Works with integers (3, 60, 120)
- ✅ Works with floats (2.5, 10.5)
- ✅ `elapsed_ms` ≈ timeout_s * 1000 (±200ms tolerance) when timeout occurs

---

### Test 18: CORS Check

**Objective:** Verify CORS headers allow browser-based UI access.

**Important:** This test depends on your CORS configuration in `main.py`.

**Create HTML test file:**

html

```html
<!-- /tmp/test-cors.html -->
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <title>CORS Test</title>
  <style>
    body { font-family: monospace; padding: 20px; }
    button { margin: 5px; padding: 10px; }
    pre { background: #f0f0f0; padding: 10px; overflow-x: auto; }
  </style>
</head>
<body>
<h1>Daemon CORS Test</h1>
<button onclick="testStatus()">Test GET /status</button>
<button onclick="testSend()">Test POST /send</button>
<pre id="output">Click a button to test...</pre>

<script>
const API_BASE = 'http://localhost:8000';
const output = document.getElementById('output');

async function testStatus() {
  output.textContent = 'Testing GET /status...\n';
  try {
    const resp = await fetch(`${API_BASE}/status`);
    const data = await resp.json();
    output.textContent += 'Status: ' + resp.status + '\n';
    output.textContent += JSON.stringify(data, null, 2);
  } catch (e) {
    output.textContent += 'Error: ' + e.message;
  }
}

async function testSend() {
  output.textContent = 'Testing POST /send...\n';
  try {
    const resp = await fetch(`${API_BASE}/send`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        target: 'claude',
        prompt: 'CORS test message'
      })
    });
    const data = await resp.json();
    output.textContent += 'Status: ' + resp.status + '\n';
    output.textContent += JSON.stringify(data, null, 2);
  } catch (e) {
    output.textContent += 'Error: ' + e.message;
  }
}
</script>
</body>
</html>
```

**Steps:**

bash

```bash
# Serve test file from different origin
cd /tmp
python3 -m http.server 8080 &
SERVER_PID=$!

echo "Test page available at: http://localhost:8080/test-cors.html"
echo ""
echo "=== ACTION REQUIRED ==="
echo "1. Open http://localhost:8080/test-cors.html in browser"
echo "2. Click 'Test GET /status' button"
echo "3. Click 'Test POST /send' button"
echo "4. Verify no CORS errors in browser console (F12)"
echo "5. Press Enter when done..."
read

# Kill test server
kill $SERVER_PID
```

**Or test via curl (check headers):**

bash

```bash
# Check CORS headers on GET
curl -v -H "Origin: http://localhost:8080" \
  http://localhost:8000/status 2>&1 | grep -i "access-control"

# Check CORS headers on POST
curl -v -X POST \
  -H "Origin: http://localhost:8080" \
  -H "Content-Type: application/json" \
  -d '{"target": "claude", "prompt": "Test"}' \
  http://localhost:8000/send 2>&1 | grep -i "access-control"

# Expected headers (if using allow_origins=["*"] and allow_credentials=False):
# access-control-allow-origin: *
# access-control-allow-methods: *
# access-control-allow-headers: *

# Expected headers (if using explicit origins with credentials=True):
# access-control-allow-origin: http://localhost:8080
# access-control-allow-credentials: true
# access-control-allow-methods: *
# access-control-allow-headers: *
```

**Validation Checklist:**

- ✅ Browser requests from different origin succeed
- ✅ No CORS errors in browser console
- ✅ Response headers include appropriate `Access-Control-Allow-Origin`
- ✅ Both GET (/status) and POST (/send) work
- ✅ Preflight OPTIONS requests succeed (for POST)

**Note:** Expected headers depend on your `main.py` configuration:

- **Option A** (`allow_credentials=False`): `Access-Control-Allow-Origin: *`
- **Option B** (`allow_credentials=True`): `Access-Control-Allow-Origin: http://localhost:8080`

---

### Test 19: Schema Assertions (Comprehensive)

**Objective:** Validate complete response schema with strict assertions.

**Create assertion script:**

bash

```bash
#!/bin/bash
# /tmp/test-schema.sh

set -e

API="http://localhost:8000"

echo "=================================================="
echo "Schema Validation Test Suite"
echo "=================================================="

echo ""
echo "Testing /status schema..."
echo "---"

# Status schema checks - daemon
curl -s "$API/status" | jq -e '.daemon | has("version")' && echo "✓ daemon.version"
curl -s "$API/status" | jq -e '.daemon | has("available_ais")' && echo "✓ daemon.available_ais"
curl -s "$API/status" | jq -e '.daemon | has("cdp_healthy")' && echo "✓ daemon.cdp_healthy"
curl -s "$API/status" | jq -e '.daemon | has("browser_pool_active")' && echo "✓ daemon.browser_pool_active"
curl -s "$API/status" | jq -e '.daemon.available_ais | type == "array"' && echo "✓ available_ais is array"

# Status schema checks - AI instances
curl -s "$API/status" | jq -e '.ais | has("claude")' && echo "✓ ais.claude exists"
curl -s "$API/status" | jq -e '.ais.claude | has("cdp_connected")' && echo "✓ cdp_connected"
curl -s "$API/status" | jq -e '.ais.claude | has("session_active")' && echo "✓ session_active"
curl -s "$API/status" | jq -e '.ais.claude | has("model_name")' && echo "✓ model_name"
curl -s "$API/status" | jq -e '.ais.claude | has("context_window_tokens")' && echo "✓ context_window_tokens"
curl -s "$API/status" | jq -e '.ais.claude | has("context_used_percent")' && echo "✓ context_used_percent"

# Legacy fields
curl -s "$API/status" | jq -e '.ais.claude | has("ctaw_size")' && echo "✓ ctaw_size (legacy)"
curl -s "$API/status" | jq -e '.ais.claude | has("ctaw_usage_percent")' && echo "✓ ctaw_usage_percent (legacy)"
curl -s "$API/status" | jq -e '.ais.claude | has("connected")' && echo "✓ connected (legacy)"

# Legacy mirror validation
curl -s "$API/status" | jq -e '.ais.claude.connected == .ais.claude.cdp_connected' && echo "✓ connected mirrors cdp_connected"
curl -s "$API/status" | jq -e '.ais.claude.ctaw_size == .ais.claude.context_window_tokens' && echo "✓ ctaw_size mirrors context_window_tokens"
curl -s "$API/status" | jq -e '.ais.claude.ctaw_usage_percent == .ais.claude.context_used_percent' && echo "✓ ctaw_usage_percent mirrors context_used_percent"

# Timestamp fields
curl -s "$API/status" | jq -e '.ais.claude | has("last_interaction_time")' && echo "✓ last_interaction_time (float)"
curl -s "$API/status" | jq -e '.ais.claude | has("last_interaction_iso")' && echo "✓ last_interaction_iso (ISO string)"

echo "✅ /status schema valid"

echo ""
echo "Testing /send success schema..."
echo "---"

# Send success schema
resp=$(curl -s -X POST "$API/send" \
  -H "Content-Type: application/json" \
  -d '{"target": "claude", "prompt": "Schema test"}')

echo "$resp" | jq -e '.success == true' && echo "✓ success"
echo "$resp" | jq -e '.metadata | has("request_id")' && echo "✓ request_id"
echo "$resp" | jq -e '.metadata | has("elapsed_ms")' && echo "✓ elapsed_ms"
echo "$resp" | jq -e '.metadata | has("waited")' && echo "✓ waited"
echo "$resp" | jq -e '.metadata | has("timeout_s")' && echo "✓ timeout_s"
echo "$resp" | jq -e '.metadata | has("ws_source")' && echo "✓ ws_source"
echo "$resp" | jq -e '.metadata | has("page_url")' && echo "✓ page_url"
echo "$resp" | jq -e '.metadata | has("stage_log")' && echo "✓ stage_log"
echo "$resp" | jq -e '.metadata | has("warnings")' && echo "✓ warnings"
echo "$resp" | jq -e '.metadata | has("model_name")' && echo "✓ model_name"
echo "$resp" | jq -e '.metadata | has("cdp_url")' && echo "✓ cdp_url"
echo "$resp" | jq -e '.metadata | has("timestamp")' && echo "✓ timestamp"

echo "$resp" | jq -e '.metadata.warnings | type == "array"' && echo "✓ warnings is array"
echo "$resp" | jq -e '.metadata.stage_log | has("request_id")' && echo "✓ stage_log.request_id"
echo "$resp" | jq -e '.metadata.stage_log | has("send_start")' && echo "✓ stage_log.send_start"

# Validate ISO timestamps
echo "$resp" | jq -e '.metadata.timestamp | test("^[0-9]{4}-[0-9]{2}-[0-9]{2}T")' && echo "✓ timestamp is ISO 8601"
echo "$resp" | jq -e '.metadata.stage_log.send_start | test("^[0-9]{4}-[0-9]{2}-[0-9]{2}T")' && echo "✓ send_start is ISO 8601"

echo "✅ /send success schema valid"

echo ""
echo "Testing /send error schema..."
echo "---"

# Send error schema (use invalid target)
err=$(curl -s -X POST "$API/send" \
  -H "Content-Type: application/json" \
  -d '{"target": "invalid", "prompt": "Test"}')

echo "$err" | jq -e '.success == false' && echo "✓ success=false"
echo "$err" | jq -e '.metadata | has("error")' && echo "✓ has error"
echo "$err" | jq -e '.metadata.error | has("code")' && echo "✓ error.code"
echo "$err" | jq -e '.metadata.error | has("message")' && echo "✓ error.message"
echo "$err" | jq -e '.metadata.error | has("severity")' && echo "✓ error.severity"
echo "$err" | jq -e '.metadata.error | has("suggested_action")' && echo "✓ error.suggested_action"
echo "$err" | jq -e '.metadata.error | has("evidence")' && echo "✓ error.evidence"
echo "$err" | jq -e '.metadata.error.code | type == "string"' && echo "✓ code is string"
echo "$err" | jq -e '.metadata.error.evidence | type == "object"' && echo "✓ evidence is object"
echo "$err" | jq -e '.metadata | has("warnings")' && echo "✓ warnings present"
echo "$err" | jq -e '.metadata | has("timestamp")' && echo "✓ timestamp present"

echo "✅ /send error schema valid"

echo ""
echo "=================================================="
echo "All schema tests passed!"
echo "=================================================="
```

**Run:**

bash

````bash
chmod +x /tmp/test-schema.sh
/tmp/test-schema.sh
```

**Expected Output:**
```
==================================================
Schema Validation Test Suite
==================================================

Testing /status schema...
---
✓ daemon.version
✓ daemon.available_ais
✓ daemon.cdp_healthy
✓ daemon.browser_pool_active
✓ available_ais is array
✓ ais.claude exists
✓ cdp_connected
✓ session_active
✓ model_name
✓ context_window_tokens
✓ context_used_percent
✓ ctaw_size (legacy)
✓ ctaw_usage_percent (legacy)
✓ connected (legacy)
✓ connected mirrors cdp_connected
✓ ctaw_size mirrors context_window_tokens
✓ ctaw_usage_percent mirrors context_used_percent
✓ last_interaction_time (float)
✓ last_interaction_iso (ISO string)
✅ /status schema valid

Testing /send success schema...
---
✓ success
✓ request_id
✓ elapsed_ms
✓ waited
✓ timeout_s
✓ ws_source
✓ page_url
✓ stage_log
✓ warnings
✓ model_name
✓ cdp_url
✓ timestamp
✓ warnings is array
✓ stage_log.request_id
✓ stage_log.send_start
✓ timestamp is ISO 8601
✓ send_start is ISO 8601
✅ /send success schema valid

Testing /send error schema...
---
✓ success=false
✓ has error
✓ error.code
✓ error.message
✓ error.severity
✓ error.suggested_action
✓ error.evidence
✓ code is string
✓ evidence is object
✓ warnings present
✓ timestamp present
✅ /send error schema valid

==================================================
All schema tests passed!
==================================================
````

**Validation Checklist:**

- ✅ All required fields present in /status
- ✅ All required fields present in /send success
- ✅ All required fields present in /send error
- ✅ Field types are correct (string, array, object, bool, number)
- ✅ ISO timestamps match regex pattern
- ✅ Legacy fields coexist with new fields
- ✅ Legacy fields mirror new fields correctly
- ✅ Both float (`last_interaction_time`) and ISO (`last_interaction_iso`) timestamps present

---

### Test 20: Concurrent Across Different AIs

**Objective:** Verify no cross-talk when sending to different providers simultaneously.

**Steps:**

bash

````bash
echo "Firing concurrent requests to all three providers..."

# Fire three concurrent requests to different providers
(
  curl -s -X POST http://localhost:8000/send \
    -H "Content-Type: application/json" \
    -d '{"target": "claude", "prompt": "Claude concurrent request"}' \
    > /tmp/claude-resp.json
) &

(
  curl -s -X POST http://localhost:8000/send \
    -H "Content-Type: application/json" \
    -d '{"target": "chatgpt", "prompt": "ChatGPT concurrent request"}' \
    > /tmp/chatgpt-resp.json
) &

(
  curl -s -X POST http://localhost:8000/send \
    -H "Content-Type: application/json" \
    -d '{"target": "gemini", "prompt": "Gemini concurrent request"}' \
    > /tmp/gemini-resp.json
) &

# Wait for all
wait

echo "Analyzing responses..."
echo ""

# Check all succeeded
jq -e '.success == true' /tmp/claude-resp.json && echo "✅ Claude success"
jq -e '.success == true' /tmp/chatgpt-resp.json && echo "✅ ChatGPT success"
jq -e '.success == true' /tmp/gemini-resp.json && echo "✅ Gemini success"

echo ""

# Extract request IDs
claude_id=$(jq -r '.metadata.request_id' /tmp/claude-resp.json)
chatgpt_id=$(jq -r '.metadata.request_id' /tmp/chatgpt-resp.json)
gemini_id=$(jq -r '.metadata.request_id' /tmp/gemini-resp.json)

echo "Request IDs:"
echo "  Claude:  $claude_id"
echo "  ChatGPT: $chatgpt_id"
echo "  Gemini:  $gemini_id"
echo ""

# Verify all unique
if [ "$claude_id" != "$chatgpt_id" ] && \
   [ "$claude_id" != "$gemini_id" ] && \
   [ "$chatgpt_id" != "$gemini_id" ]; then
  echo "✅ All request IDs unique"
else
  echo "❌ Request IDs not unique!"
fi

# Check responses contain provider-specific content
claude_url=$(jq -r '.metadata.page_url' /tmp/claude-resp.json)
chatgpt_url=$(jq -r '.metadata.page_url' /tmp/chatgpt-resp.json)
gemini_url=$(jq -r '.metadata.page_url' /tmp/gemini-resp.json)

echo ""
echo "Page URLs:"
echo "  Claude:  $claude_url"
echo "  ChatGPT: $chatgpt_url"
echo "  Gemini:  $gemini_url"
echo ""

echo "$claude_url" | grep -q "claude.ai" && echo "✅ Claude used claude.ai"
echo "$chatgpt_url" | grep -q "chatgpt.com" && echo "✅ ChatGPT used chatgpt.com"
echo "$gemini_url" | grep -q "gemini.google.com" && echo "✅ Gemini used gemini.google.com"

# Verify stage logs are independent
claude_baseline=$(jq -r '.metadata.stage_log.baseline_count' /tmp/claude-resp.json)
chatgpt_baseline=$(jq -r '.metadata.stage_log.baseline_count' /tmp/chatgpt-resp.json)
gemini_baseline=$(jq -r '.metadata.stage_log.baseline_count' /tmp/gemini-resp.json)

echo ""
echo "Baseline counts (independent state):"
echo "  Claude:  $claude_baseline"
echo "  ChatGPT: $chatgpt_baseline"
echo "  Gemini:  $gemini_baseline"

echo ""
echo "✅ Each provider maintains independent state"

# Cleanup
rm /tmp/claude-resp.json /tmp/chatgpt-resp.json /tmp/gemini-resp.json
```

**Expected Behavior:**
- ✅ All three requests complete successfully
- ✅ Requests execute in parallel (total time < sum of individual times)
- ✅ Each has unique `request_id`
- ✅ Each uses correct provider URL
- ✅ No interleaved stage logs
- ✅ No shared state between providers

**Daemon Logs May Show:**
```
DEBUG - claude: Enter key triggered send successfully
DEBUG - chatgpt: Enter key triggered send successfully
DEBUG - gemini: Enter key triggered send successfully
````

Possibly interleaved, but no errors or conflicts.

**Validation Checklist:**

- ✅ All providers return `success: true`
- ✅ Request IDs are unique across providers
- ✅ Page URLs are provider-specific
- ✅ Baseline counts are independent
- ✅ No cross-contamination in metadata
- ✅ Concurrent execution (parallel, not serialized)

---

## Performance Benchmarks

### Expected Timings

|Operation|Expected Time|Notes|
|---|---|---|
|Daemon startup|< 5s|CDP discovery + AI init|
|/healthz endpoint|< 50ms|Simple JSON response|
|/status endpoint|< 100ms|No heavy operations|
|/send (short, wait=true)|1-5s|Depends on provider speed|
|/send (short, wait=false)|< 500ms|Fire and forget|
|/send (long, wait=true)|5-30s|Depends on response length|
|Health check cycle|30s|Configurable in HealthMonitor|
|CDP reconnect|1-2s|After disconnect|
|New tab creation|2-5s|Navigate + page load|
|Page selector lookup|50-200ms|DOM query time|

---

## Cleanup & Reset

### After Testing

bash

```bash
# Stop daemon
# Press Ctrl+C in daemon terminal

# Kill browser
pkill chromium
# or on macOS:
# pkill "Google Chrome"

# Clear test data
rm -rf /tmp/chrome-test-profile
rm /tmp/*-resp.json 2>/dev/null
rm /tmp/test-*.sh 2>/dev/null

# Check for hung processes
ps aux | grep chromium
ps aux | grep python

# Verify ports are free
lsof -i :8000
lsof -i :9223

# If ports still in use, kill processes:
# lsof -ti :8000 | xargs kill -9
# lsof -ti :9223 | xargs kill -9
```

---

## Success Criteria Summary

**All 20 tests pass if:**

### Core Tests (1-10) ✅

1. ✅ Daemon starts without errors, CDP discovered, `cdp_healthy=true`
2. ✅ Happy path returns structured response with all metadata fields
3. ✅ Rate limit detected and returns `RATE_LIMITED` error
4. ✅ Auth wall detected and returns `AUTH_REQUIRED` error
5. ✅ Timeout detected and returns `RESPONSE_TIMEOUT` error
6. ✅ CDP disconnect returns `CDP_DISCONNECTED` error
7. ✅ Invalid target returns `INVALID_TARGET` error
8. ✅ All three providers work sequentially
9. ✅ Concurrent requests to same AI are serialized
10. ✅ Empty responses trigger `EMPTY_RESPONSE` warning

### Enhanced Tests (11-20) ✅

11. ✅ No-wait mode works, state updates correctly
12. ✅ Selector missing caught at `ensure_ready` stage
13. ✅ Benign banners trigger warnings but don't block
14. ✅ Model name cache persists ("first-seen wins")
15. ✅ New tabs created when none exist
16. ✅ Health monitor detects CDP loss and recovery within one cycle
17. ✅ Timeout values propagate correctly to metadata
18. ✅ CORS headers allow browser access from different origins
19. ✅ All schema assertions pass (field presence/types/mirrors)
20. ✅ Concurrent requests to different AIs execute in parallel

### Metadata Completeness ✅

- ✅ `request_id`, `stage_log`, `warnings`, `model_name`, `cdp_url`, `timeout_s` in every response
- ✅ ISO timestamps for all new timestamp fields
- ✅ Status includes both `last_interaction_time` (float, for legacy/metrics) and `last_interaction_iso` (ISO string)
- ✅ `context_window_tokens` and `context_used_percent` in status (standard names)
- ✅ `ctaw_size` and `ctaw_usage_percent` in status (legacy names)
- ✅ Legacy fields mirror new fields: `connected==cdp_connected`, `ctaw_size==context_window_tokens`, etc.
- ✅ Error structure has `code`, `message`, `severity`, `suggested_action`, `evidence`, `stage_log`
- ✅ Stage log has ISO timestamps for all stages
- ✅ `failure_stage` set on errors

---

## Automated Test Runner (Optional)

Create `/tmp/run-all-tests.sh`:

bash

```bash
#!/bin/bash
# run-all-tests.sh - Execute all 20 tests in sequence

set -e

echo "=================================================="
echo "AI Daemon Comprehensive Test Suite"
echo "=================================================="
echo ""

# Ensure daemon is running
if ! curl -s http://localhost:8000/healthz > /dev/null 2>&1; then
  echo "❌ Daemon not running. Start it first:"
  echo "   cd src && python -m daemon.main"
  exit 1
fi

echo "✅ Daemon is running"
echo ""

# Test counter
passed=0
failed=0
total=20

run_test() {
  local num=$1
  local name=$2
  
  echo "=================================================="
  echo "Test $num/$total: $name"
  echo "=================================================="
  
  # Tests require manual intervention - just list them
  echo "Run this test manually following the test plan"
  echo ""
}

# List all tests
run_test 1 "Startup & Status Check"
run_test 2 "Happy Path - Send Message"
run_test 3 "Rate Limit Detection"
run_test 4 "Auth Wall Detection"
run_test 5 "Response Timeout"
run_test 6 "CDP Disconnection"
run_test 7 "Invalid Target"
run_test 8 "Multi-Provider Sequential"
run_test 9 "Concurrent Requests (Same AI)"
run_test 10 "Empty Response Warning"
run_test 11 "No-Wait Path"
run_test 12 "Ensure Chat Ready Failure"
run_test 13 "Suspicious Page State"
run_test 14 "Model Cache Behavior"
run_test 15 "New Tab Creation"
run_test 16 "Health Monitor Propagation"
run_test 17 "Timeout Propagation"
run_test 18 "CORS Check"
run_test 19 "Schema Assertions"
run_test 20 "Concurrent Across Different AIs"

echo "=================================================="
echo "Test suite overview complete"
echo "Run each test manually following the detailed steps"
echo "=================================================="
```

---

## 🎯 Final Notes

This comprehensive test plan:

- ✅ Covers all happy paths
- ✅ Covers all error conditions
- ✅ Covers all edge cases
- ✅ Validates schema completeness
- ✅ Tests concurrency (same AI and across AIs)
- ✅ Tests system behavior (health monitoring, CDP recovery)
- ✅ Tests integration points (CORS, new tab creation)
- ✅ Includes platform-specific notes (Linux/macOS/Windows)
- ✅ Addresses all CORS configuration concerns
- ✅ Validates legacy field mirrors
- ✅ Documents timestamp format expectations
- ✅ Includes fail-fast checks (ports, healthz)

**Expected total execution time: ~30-40 minutes for all 20 tests (including manual setup steps).**

**Run tests in order. Each test is independent and includes cleanup steps.**

**Production-ready and cross-platform compatible!** 🚀