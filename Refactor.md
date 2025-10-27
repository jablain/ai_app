Strategy: Evolve ai_app to Multi-Transport Architecture (Option B)

This is the agreed end-to-end plan you can keep as the single source of truth. It preserves today’s working Claude-via-web flow while reshaping the code to cleanly support multiple transports (web now, API later) without breaking daemon clients.

High-level goals

Preserve current behavior (Claude via web transport keeps working end-to-end).

Isolate “Product” (Claude/ChatGPT/Gemini) from “Transport” (web/api) via a small, stable interface.

Make transport selection a runtime config (per AI).

Keep daemon endpoints and clients unchanged and oblivious to transport.

Enable incremental refactors + frequent verification after each small change.

Target architecture (mental model)
Daemon (/send, /status)
    └── AI Registry (product name → Product class, configured transport)
          ├── Product: ClaudeAI (business rules, prompts, model awareness)
          │     └── ITransport (stable interface)
          │          ├── WebTransport   (current working flow migrated here)
          │          └── ApiTransport   (future)
          ├── Product: ChatGPTAI
          └── Product: GeminiAI

Stable transport interface (ITransport)

Minimal, product-agnostic surface:

async send_prompt(message: str, wait_for_response: bool, timeout_s: float) -> (success, snippet, markdown, meta)

async start_new_session() -> bool

get_transport_status() -> dict

Division of responsibilities

Product (Claude/ChatGPT/Gemini): selectors or API endpoints that are product-specific, small glue logic, any product-level defaults (timeouts, quirks).

Transport (Web/API): how to send/receive (Playwright/CDP vs HTTP), waiting, extraction, telemetry.

Daemon: loads config, instantiates Product with a chosen Transport, exposes /send and /status.

Phased migration plan

Each phase is small, testable, and backward-compatible.

Phase 0 — Configuration knob (no behavior change)

Goal: Prepare daemon to accept a transport choice but still use existing web code.

Add config:

[ai.claude]
transport = "web"     # {web, api} — default: "web"


Wire daemon startup to read this knob and pass it to the Claude Product constructor.

Test gate: Daemon boots, /status unchanged, current /send for Claude still works.

Phase 1 — Define ITransport (interface only)

Goal: Create the seam.

Create ITransport ABC with send_prompt, start_new_session, get_transport_status.

No implementation yet; Product continues using the existing path.

Test gate: Pure import/boot test; no runtime change.

Phase 2 — Extract current Web flow into WebTransport

Goal: Move the working code as-is from WebAIBase into WebTransport, with minimal edits.

Create WebTransport that hosts:

CDP discovery/connection, page pick

_execute_web_interaction orchestration

wait/extract utilities

transport status

Keep all selectors + site quirks delegated from Product via small hooks (see Phase 3).

Test gate: Switch Claude to use WebTransport internally; /send parity maintained (same inputs/outputs).

Phase 3 — Convert ClaudeAI into a thin Product using hooks

Goal: Claude provides only product-specific bits; WebTransport does the rest.

In ClaudeAI, implement only:

get_page_url_hint() (e.g., "claude.ai")

Selectors (input, stop, content containers)

Hook methods used by WebTransport:

_get_response_count(page)

_send_message(page, message)

_wait_for_response_complete(page, timeout_s)

_extract_response(page, baseline_count)

ClaudeAI delegates send_prompt() to self.transport.send_prompt(...).

Test gate: /send parity & logs show transport path; extraction and snippets unchanged.

Phase 4 — Daemon wiring (per-AI transport)

Goal: Daemon instantiates Product + Transport based on config.

In startup:

Read [ai.<name>].transport

Build ClaudeAI(transport=WebTransport(...))

AIFactory returns a Product that already holds the transport.

Test gate: /status shows transport status block; /send works.

Phase 5 — Observability + errors (no behavior change)

Goal: Standardize metadata so swapping transport won’t surprise clients.

Ensure metadata contains:

transport_type ("web"), cdp_url, page_url, request_id, elapsed_ms, stage_log, warnings, error?

Ensure /status merges product + transport status cleanly.

Test gate: Response schema matches current behavior plus extra fields (non-breaking).

Phase 6 — Tighten Claude(web) implementation

Goal: Stabilize what exists before adding more transports.

Finish selectors; robust readiness; improved extraction; handle long responses.

Harden error handling (auth walls, banners, rate limits); meaningful error.codes.

Test gate: Regression suite for common flows; run a set of prompts and ensure stable outcomes.

Phase 7 — Prep for API transport (scaffold only)

Goal: Zero behavior change; just lay the groundwork.

Create ApiTransport skeleton (no network calls yet) implementing ITransport, raising NotImplementedError.

transport="api" is accepted but returns a clear error at runtime.

Test gate: Configuring api returns a deterministic error; web still OK.

Testing strategy (at each phase)

Smoke: python3 -m daemon.main boots; /healthz, /status.

Claude happy path: curl /send with “Hello” → 200 success, valid snippet/markdown.

Timeout path: Set a short timeout → deterministic RESPONSE_TIMEOUT error.

Status shape: Clients see identical fields; new transport fields are additive.

Logging: Request IDs present; stage timings reasonable.

Acceptance criteria (for “Phase 6 complete” checkpoint)

Claude via web transport behaves equal or better than before.

ITransport interface stable; WebTransport manages all browser logic.

Product classes are thin and only provide product-specific hooks.

Daemon clients (e.g., scripts using /send) unchanged.

Config selects transport per AI; switching to api yields a friendly “not implemented” error (no crash).

File/Module layout (suggested)
src/daemon/
  ai/
    base.py              # Product-facing abstract BaseAI (unchanged public surface)
    factory.py
    transports/
      base.py            # ITransport ABC
      web.py             # WebTransport (migrated logic)
      api.py             # ApiTransport (scaffold, later real)
    claude.py            # ClaudeAI (thin product; selectors + hooks)
    chatgpt.py           # (later)
    gemini.py            # (later)
  browser/
    connection_pool.py   # CDP management (reused by WebTransport)

Backward compatibility & risk management

No API surface changes to daemon endpoints (/send, /status).

Incremental PRs per phase; each is revertable.

Conservative refactor: First move code as-is, then improve.

Selector drift is the main runtime risk; keep hooks in Product to localize fixes.

What “done” looks like (before adding API transport)

ClaudeAI uses WebTransport through ITransport.

ChatGPT/Gemini can be ported by repeating the same pattern.

Switching transports is a config change, not a refactor.

Adding an API transport for Claude is “just” implementing ApiTransport and setting transport="api".

Quick checklist (to keep me aligned)

 Phase 0: config knob added, no behavior change

 Phase 1: ITransport ABC exists

 Phase 2: WebTransport created (migrate code)

 Phase 3: ClaudeAI reduced to product hooks, delegates to transport

 Phase 4: Daemon builds Product+Transport from config

 Phase 5: Metadata/telemetry standardized

 Phase 6: Claude(web) hardened

 Phase 7: ApiTransport scaffold added

If I drift from this playbook, point me back to this doc and I’ll realign.
