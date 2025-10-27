Primer — Refactor ChatGPT & Gemini to Pure Transport Adapters (Claude-style), With Zero Legacy Fallback
Non-negotiables

Claude stays green. Do not change ClaudeWebTransport or Claude’s working selectors.

No WebAIBase usage anywhere. Remove it from ChatGPT/Gemini paths and from imports.

Thin adapters only. ChatGPTAI and GeminiAI become dumb shells that require a transport and delegate.

Fail fast if transport missing. If an AI is constructed/used without a transport, raise a clear error.

Public API unchanged. /send and /status shapes stay identical (including metadata fields you already emit).

Target Architecture (same as Claude’s new shape)

src/daemon/ai/{claude,chatgpt,gemini}.py = thin adapters

__init__(config) + attach_transport(transport) or pass transport in ctor.

send_prompt(...) → delegate to transport; then run session accounting (tokens, counts) exactly as Claude does now.

get_ai_status() → include a transport block (attached, name, kind, status).

Transports in src/daemon/transport/:

Existing: claude_web.py (do not touch).

New: chatgpt_web.py, gemini_web.py (site-specific selectors; Claude-pattern mechanics).

main.py wires every AI to exactly one transport at startup, based on config.

What’s Getting Deleted / Banned

Any reference to WebAIBase in ChatGPT/Gemini code paths.

Any fallback code that says “if no transport, do legacy…”.

Any selectors/mechanics for ChatGPT/Gemini that live inside the AI class — mechanics move to transports.

Step-by-Step, Reversible (but strict) Plan
0) Guardrails

Tag current green state: git tag claude-green.

Tiny commits; after each step: run /send for Claude.

1) Export New Transports

Add skeletons:

src/daemon/transport/chatgpt_web.py

src/daemon/transport/gemini_web.py

Update src/daemon/transport/__init__.py to export both new classes.

Rules for these transports (clone Claude’s mechanics):

Provide robust _send_message, _wait_for_response_complete, _extract_response, _get_response_count.

Keep multiple input selectors and fallbacks; press Enter; then stabilize on response count or stop button.

Return (success, snippet, markdown, metadata) and populate stage_log, warnings, and structured errors exactly like Claude.

2) Make Adapters Pure

In src/daemon/ai/chatgpt.py and src/daemon/ai/gemini.py:

Remove any inheritance/imports of WebAIBase.

Add self._transport = None in __init__.

Add attach_transport(self, transport); no-op is not allowed — it must set a non-None transport.

send_prompt(...):

If self._transport is None → raise RuntimeError("ChatGPTAI requires a transport") (replace “ChatGPTAI” with the class).

Delegate to self._transport.send_prompt(...).

If success, run the same session accounting Claude uses now (reuse your existing token counting util).

Ensure timeout_s is included in metadata.

get_ai_status() should include the transport section exactly like Claude’s.

Delete any legacy selectors/mechanics from these AI files.

3) Wire in main.py

After creating AI instances and reading config.ai_transports:

For "chatgpt": "web", construct ChatGPTWebTransport(base_url="https://chatgpt.com", browser_pool=..., logger=...) and attach_transport.

For "gemini": "web", construct GeminiWebTransport(base_url="https://gemini.google.com", browser_pool=..., logger=...) and attach_transport.

If attach fails, log an error and do not leave a fallback — calls to /send will raise a clean “requires transport” error.

4) Remove WebAIBase from imports/build

Grep for WebAIBase and remove all references except Claude’s old code if any still exists (but per your rule, Claude already uses transport; if anything’s left, remove it too).

If WebAIBase is its own file and now unused, delete it in a separate commit.

5) Test Matrix (each step)

Claude sanity:

curl -s -X POST http://127.0.0.1:8000/send \
  -H 'Content-Type: application/json' \
  -d '{"target":"claude","prompt":"Reply with PONG only.","wait_for_response":true,"timeout_s":60}'


Status shows transport for all three AIs:

curl -s http://127.0.0.1:8000/status | jq .


ChatGPT/Gemini (expect actual PONG once selectors are in):

curl -s -X POST http://127.0.0.1:8000/send \
  -H 'Content-Type: application/json' \
  -d '{"target":"chatgpt","prompt":"Reply with PONG only.","wait_for_response":true,"timeout_s":60}'

curl -s -X POST http://127.0.0.1:8000/send \
  -H 'Content-Type: application/json' \
  -d '{"target":"gemini","prompt":"Reply with PONG only.","wait_for_response":true,"timeout_s":60}'


If either fails on first pass (selector tuning), you still must not re-enable any legacy code. Fix the transport selectors/mechanics.

Selector Starting Points (you will refine during testing)
ChatGPT (chatgpt.com)

Input candidates (try in order):

textarea[name='prompt-textarea']

textarea#prompt-textarea

div[contenteditable='true'][data-placeholder*='message']

div[role='textbox'][contenteditable='true']

textarea, div[contenteditable='true']

Send button (fallback): button[data-testid='send-button']

Stop button: button[data-testid='stop-button']

Response container/content:

Container: div[data-message-author-role='assistant']

Content: div.markdown.prose (fallback: container inner_text())

Gemini (gemini.google.com/app)

Input candidates (try in order):

div.ql-editor[contenteditable='true']

rich-textarea[aria-label*='prompt']

div[contenteditable='true'][aria-label*='prompt']

div[contenteditable='true'], div[role='textbox'], textarea

Send button (fallback): button[aria-label*='Send'], button[mattooltip*='Send']

Stop button: button[aria-label*='Stop'], button[mattooltip*='Stop']

Response container/content:

Container: message-content[data-model-role='model'], div[data-role='model-response']

Content: div.markdown, div.model-response-text (fallback: container inner_text())

Error Semantics (no fallback allowed)

If input not found → return error SELECTOR_MISSING with failure_stage: "ensure_ready".

If send fails on all candidates → SELECTOR_MISSING with failure_stage: "send".

If timeout before stabilization → RESPONSE_TIMEOUT.

Always include stage_log timestamps and page_url in metadata.

Acceptance Criteria (end state)

/status shows all three AIs with transport.attached = true, and no mention of WebAIBase.

/send works for Claude (proved), and for ChatGPT/Gemini after selector tuning.

Grep shows zero references to WebAIBase anywhere in the repo.

Commit history shows small, reversible steps — but no reintroduction of legacy behavior.

If you want, I can now proceed with the exact file diffs (in the strict, no-fallback shape) for:

transport/__init__.py (export new classes),

transport/chatgpt_web.py and transport/gemini_web.py,

ai/chatgpt.py and ai/gemini.py (pure adapters),

main.py wiring (attach or error, no fallback).

Say the word and I’ll send them one file at a time, waiting for your install confirmation after each.
