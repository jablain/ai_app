
# AI-CLI-BRIDGE V2.0.0 REFACTORING SPECIFICATION (CLIENT/DAEMON MODEL)

This document details the architectural redesign of the `ai-cli-bridge` to version 2.0.0, transitioning from a stateless command-line tool to a powerful, stateful **Client/Daemon (Server) architecture**.

## 1. RATIONALE: THE NEED FOR PERSISTENCE (Why We Refactor)

The original architecture failed for the newly requested features because the primary AI objects (`ClaudeAI`, `GeminiAI`, etc.) were created and destroyed for every single CLI command.

|Feature Type|Requirement|Status in V1.x (Stateless)|
|---|---|---|
|**Turn/Token Counters**|Requires the object to live across multiple commands.|Always reset to zero; non-functional.|
|**Context Warnings**|Requires a cumulative token count over time.|Could never accumulate history; non-functional.|
|**Automatic `!align`**|Needs the token count to grow past a threshold (e.g., 5000).|Never triggers; non-functional.|
|**Initial Inject Prompt**|Must be sent ONLY once at session start.|Would be re-sent for every single CLI command.|

The solution is to decouple the AI object's lifespan from the ephemeral CLI execution.

## 2. NEW ARCHITECTURE: DECOUPLING LIFE CYCLES

The application is split into two asynchronous components communicating via a local HTTP server (FastAPI):

### 2.1. The AI Daemon (Server)

- **Role:** Long-lived, persistent background process.

- **Lifecycle:** Starts with `daemon start` and stops with `daemon stop`.

- **Core Responsibility:** Hosts the persistent, stateful `BaseAI` descendant objects. Manages the browser session (CDP).


### 2.2. The CLI Commands (Client)

- **Role:** Lightweight process that runs for a moment.

- **Core Responsibility:** Parses user input and immediately sends an HTTP request to the running Daemon. Prints the resulting data from the Daemon and exits.


## 3. DAEMON CORE RESPONSIBILITIES (AI Session Manager)

The Daemon manages the following critical components:

### A. Browser Session and Concurrency

- **CDP Browser Management:** The Daemon is the _only_ component responsible for launching the persistent Chromium instance using the shared profile (the current `init-cdp` shell script logic will be absorbed here).

- **AI Object Instantiation:** Creates **one long-lived instance** of every available AI (`claude`, `gemini`, etc.) on startup.

- **Concurrency Locking:** An `asyncio.Lock` will be created for _each_ AI instance. All browser interactions by that AI must acquire its specific lock before proceeding, preventing simultaneous execution and race conditions.


### B. Session State and Management

- **Predictable Start:** Upon daemon launch, an **explicit `session new <ai_name>`** command will be executed for every instantiated AI. This guarantees a clean starting state and accurate local counters.

- **API Exposure:** The Daemon exposes all state (counters, usage %) and capabilities (send, switch) via FastAPI endpoints.


## 4. API ENDPOINTS AND CLIENT ROUTING

The Daemon will run a local FastAPI web server to handle all requests. The CLI commands will be refactored into clients that hit these endpoints.

|CLI Command (Client)|HTTP Method & Path|Daemon Action (Server)|
|---|---|---|
|`daemon status`|`GET /status`|Returns structured JSON of all AI states (metrics, connection, session name).|
|`daemon stop`|`POST /stop`|Reads PID file, sends SIGTERM, closes browser/AI objects gracefully.|
|**`send <target> <prompt>`**|`POST /send`|Routes prompt to the target AI object, acquires lock, executes `send_prompt`, updates state, checks warnings.|
|`session list <target>`|`GET /session/list/{ai_name}`|Acquires lock, scrapes the active AI's history panel, returns conversation titles/IDs. **(High Fragility)**|
|`session new <target>`|`POST /session/new/{ai_name}`|Acquires lock, commands AI to click "New Chat," resets local counters, and sends the initial Governance prompt.|
|`session switch <target> <id>`|`POST /session/switch/{ai_name}`|Acquires lock, loads the specific conversation URL, injects initial prompt, and resets local counters.|

## 5. FINALIZED IMPLEMENTATION DETAILS (Loose Ends)

### 5.1. Process Management & Logging (PID)

- **Daemon PID File:** Will be stored at `~/dev/ai_app/ai-cli-bridge/runtime/daemon.pid`. The `daemon start` command will write its PID here.

- **Daemon Logging:** All background output will be redirected to `~/dev/ai_app/ai-cli-bridge/runtime/logs/daemon.log` for debugging.


### 5.2. Configuration

- Configuration will be loaded from a file (e.g., `daemon_config.toml` in `runtime/config`) to set persistent values like the Daemon's API **port (Default: 8000)** and logging level.


### 5.3. Warning Codes

The `send_prompt` call's return tuple will be extended to include a `warning_status` field (e.g., in the metadata dictionary) that carries one of the following constants: `NORMAL`, `HIGH_WARNING`, or `CRITICAL_WARNING`.
