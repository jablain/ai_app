PROJECT PRIMER — ai_app (Alignment + Working Agreement)

Objective
- Maintain a working daemon that can chat with Claude via the current web transport.
- Incrementally migrate to a transport-agnostic architecture (“Option B”) with small, testable steps.
- Preserve the public API (FastAPI endpoints), UX, and existing behavior while refactoring.

Terminology
- AI: Claude, ChatGPT, Gemini, etc. Concrete model personalities.
- Transport: The mechanism an AI uses to interact (e.g., web automation via Playwright/CDP, direct HTTP API). Interchangeable behind a clean interface.
- Daemon: The FastAPI service orchestrating transports and AIs.

Current Status (as of last run)
- Working chain: Claude via web automation (Playwright/CDP) can send a prompt and extract a response.
- New transport package added: src/daemon/transport/{__init__.py, base.py, web.py}.
- ClaudeAI still uses the existing WebAIBase; we have not yet “injected” the new transport into Claude or the daemon.
- Goal now: introduce transport injection without breaking current behavior; Claude should continue working via “web” transport.

Guiding Principles
- Incremental changes + immediate tests (catch failures fast, revert quickly).
- No async/background promises: every step must be testable synchronously via the existing /send endpoint.
- Minimize churn: keep public interfaces stable; do not rename endpoints or change payloads.
- Wide logging, narrow changes. Prefer adding adapters/shims over large edits.

Target Architecture (Option B)
- BaseAI: transport-agnostic abstract interface (send_prompt, list_messages, start_new_session, status).
- Transports live in src/daemon/transport/ (e.g., WebTransport) implementing a common interface:
    - send_prompt(message, wait_for_response, timeout_s) -> (success, snippet, markdown, meta)
    - start_new_session() -> bool
    - get_status() -> dict
- Each AI class becomes a thin adapter that:
    - is constructed with (config, transport)
    - may provide model-specific selectors or knobs that a given transport needs (for web)
    - delegates send_prompt to transport
- Daemon wires each AI to a single transport at startup based on config (e.g., claude=web), and keeps that fixed for the daemon lifetime.
- Clients (curl, CLI) remain oblivious to transports.

Incremental Plan (high level)
1) Keep Claude working as-is. Add the new WebTransport and verify it can perform the same flow end-to-end using the already-open tabs.
2) Inject the transport into ClaudeAI: constructor accepts `transport`, `send_prompt` delegates to the transport. No behavior change.
3) Update daemon startup to instantiate a transport per AI according to config and pass it to the AI.
4) Once Claude is green, repeat for ChatGPT and Gemini (still using web transport).
5) Only after all AIs are stable on the transport interface, add a second transport (e.g., HTTP API) and make it selectable via config.

Coding / Review Rules
- Every change keeps Claude /send working with the same JSON shape.
- Add logging on failures with structured fields (code, stage, page_url, request_id).
- Prefer small PR-sized diffs. After each diff, test:
    - `curl -X POST http://127.0.0.1:8000/send -d '{"target":"claude","prompt":"ping","wait_for_response":true,"timeout_s":60}'`
- If a step breaks Claude, back out or patch before proceeding.

How to read context
- You will receive N chunk_XXXX.txt files produced by src/tools/generate_report.py.
- Treat them as the single source of truth.
- Do not invent missing code; ask for the file if absent.
- When proposing changes, output unified diffs (git-style) limited to the touched files only.

Success Criteria for Each Step
- Claude still responds successfully via /send.
- No change to API contract.
- Tests/logs show the new seam (transport) is installed and reported in /status.

End of primer.

