AI-CLI-Bridge Enhancement Implementation Plan
Version: 1.0
Date: 2025-11-02
Author: System Architect

📋 Executive Summary
This document outlines the complete implementation plan for adding 5 major features to the AI-CLI-Bridge system:

Context Usage Warning - Visual alerts when context window filling up
Chat Management - New/list/switch chat commands
Project Context Injection - Automatic codebase context injection
Conversation Export - Save chats as JSON
Prompt Templates - Reusable prompt macros with variables

Estimated Total Effort: 40-50 hours
Implementation Phases: 5 stages with incremental delivery
Testing Strategy: Test each feature before proceeding to next

🎯 Requirements Summary
Feature #1: Context Usage Warning

Thresholds: 70% (yellow), 85% (orange), 95% (red) - configurable
UI Display: Color + icon (⚠️) in stats sidebar usage label
CLI Display: Warning message in output (non-blocking)
Config Location: Daemon config file (daemon_config.toml)

Feature #2: Chat Management

Commands:

chats new <ai> - Start new chat
chats list <ai> - List open chats
chats switch <ai> <id|url|index> - Switch to specific chat


List Display: Active marker, index #, title (scraped from DOM)
Identification: Support chat-id, full URL, or list index
Storage: No persistent database, open browser tabs only
Status: Include current_chat_id and current_chat_url in AI status

Feature #3: Project Context Injection

Script: Integrate with existing generate-context command
Presets: @project, @module, @cwd
Config Presets: .ai-cli-bridge/context-presets.toml in project
Regeneration: Always generate fresh (no caching)
Size Management: Fail with error if context exceeds AI token limit
Variables: Support {var}, {@file}, {@context:preset}

Feature #4: Conversation Export

Format: Simple JSON with chat metadata + messages array
Scope: Single chat only
Command: chats export <ai> <chat-id>
Output: Stdout (pipe to file)
Import: Not implemented (deferred)

Feature #5: Prompt Templates

Storage: .ai-cli-bridge/templates.toml (project-local only)
Variables:

{placeholder} - Simple substitution
{@file.py} - File content injection
{@context:preset} - Context injection


Usage: --template <name> flag in send command


🏗️ Architecture Overview
System Layers
┌─────────────────────────────────────────────────────────────┐
│ Chat UI (GTK4)                                              │
│ • Context warning UI (color coding)                         │
│ • Chat list display (future)                                │
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────┐
│ CLI Client (ai-cli-bridge)                                  │
│ • chats new/list/switch commands                            │
│ • --context flag processing                                 │
│ • --template flag processing                                │
│ • Context warning display                                   │
└────────────────────┬────────────────────────────────────────┘
                     │ HTTP API
┌────────────────────▼────────────────────────────────────────┐
│ Daemon API Layer                                            │
│ • POST /chats/new                                           │
│ • GET  /chats/list                                          │
│ • POST /chats/switch                                        │
│ • POST /chats/export                                        │
│ • Enhanced /send (template + context processing)           │
│ • Enhanced /status (current_chat_* fields)                  │
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────┐
│ AI Adapter Layer (Claude/ChatGPT/Gemini)                   │
│ • Delegates to transport                                    │
│ • Returns enhanced metadata                                 │
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────┐
│ Transport Layer (WebTransport)                              │
│ • list_chats() - Scrape open tabs                          │
│ • switch_chat(chat_id) - Navigate to chat                  │
│ • start_new_chat() - Click new chat button                 │
│ • get_current_chat() - Get active chat info                │
│ • export_chat(chat_id) - Scrape all messages               │
└────────────────────┬────────────────────────────────────────┘
                     │ CDP
┌────────────────────▼────────────────────────────────────────┐
│ Browser (Chromium via CDP)                                  │
│ • Claude.ai / ChatGPT / Gemini tabs                         │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ Supporting Components                                        │
├─────────────────────────────────────────────────────────────┤
│ • Context Generator (generate-context script)               │
│ • Template Engine (variable substitution)                   │
│ • Config Manager (load thresholds, presets, templates)     │
└─────────────────────────────────────────────────────────────┘

📊 Data Flow Diagrams
Context Warning Flow
User sends message with 85% context usage
           ↓
Daemon calculates usage: 85%
           ↓
Returns in metadata: {"ctaw_usage_percent": 85}
           ↓
     ┌────┴────┐
     ↓         ↓
  CLI        UI
     ↓         ↓
  Print      Check thresholds
  warning    (70%/85%/95%)
     ↓         ↓
             Apply color:
             • 70-84%: yellow + ⚠️
             • 85-94%: orange + ⚠️
             • 95%+: red + ⚠️
Chat Management Flow
User: ai-cli-bridge chats list claude
           ↓
CLI → GET /chats/list?ai=claude
           ↓
Daemon → AI Adapter → Transport
           ↓
Transport.list_chats():
  • Query browser tabs via CDP
  • For each tab matching claude.ai:
    - Extract chat ID from URL
    - Scrape title from DOM
    - Mark if current page
           ↓
Return: [{chat_id, title, is_current}, ...]
           ↓
CLI formats and displays:
  Active  #  Title
  *       1  Python refactoring
          2  Code review help
Context Injection Flow
User: ai-cli-bridge send claude "review code" --context @project
           ↓
CLI parses --context @project
           ↓
Resolve preset:
  • Check .ai-cli-bridge/context-presets.toml
  • @project → {discover: "project", ...}
           ↓
Shell out: generate-context --discover-project
           ↓
Wait for completion
           ↓
Read chunks from: ./context_reports/latest/chunk_*.txt
           ↓
Calculate token count
           ↓
If tokens > AI limit:
  → Error: "Context too large (450k > 200k)"
           ↓
Prepend context to user message:
  <context chunks>
  ---
  <user message>
           ↓
Send to daemon → AI → Response

🗂️ File Structure Changes
New Files to Create
src/daemon/
├── config.py                           # MODIFY: Add context warning thresholds
├── main.py                             # MODIFY: Add new endpoints
├── chats/                              # NEW MODULE
│   ├── __init__.py
│   ├── manager.py                      # Chat management logic
│   ├── exporter.py                     # Export functionality
│   └── types.py                        # ChatInfo, ExportFormat types
├── context/                            # NEW MODULE
│   ├── __init__.py
│   ├── generator.py                    # generate-context integration
│   ├── injector.py                     # Context injection logic
│   ├── presets.py                      # Preset management
│   └── validator.py                    # Token count validation
└── templates/                          # NEW MODULE
    ├── __init__.py
    ├── loader.py                       # Load templates from TOML
    ├── engine.py                       # Variable substitution
    └── types.py                        # Template definition types

src/daemon/transport/
├── base.py                             # MODIFY: Add chat management methods
└── web.py                              # MODIFY: Implement chat methods

src/daemon/ai/
├── base.py                             # MODIFY: Add chat delegation methods
└── claude.py/chatgpt.py/gemini.py     # MODIFY: Implement chat methods

src/cli_bridge/
├── commands/
│   ├── chats_cmd.py                    # NEW: Chat management commands
│   ├── send_cmd.py                     # MODIFY: Add --context, --template
│   └── status_cmd.py                   # MODIFY: Display current_chat_*
└── context_helper.py                   # NEW: Context CLI logic
└── template_helper.py                  # NEW: Template CLI logic

src/chat_ui/
├── stats_display.py                    # MODIFY: Add warning colors/icons
├── config_manager.py                   # NEW: Load UI config
└── chat_ui_config.toml                 # NEW: UI-specific config

Project Root:
├── .ai-cli-bridge/                     # NEW (per-project config)
│   ├── templates.toml                  # Prompt templates
│   └── context-presets.toml            # Context generation presets
└── runtime/daemon/config/
    └── daemon_config.toml              # MODIFY: Add warning thresholds

🔌 API Specifications
New Endpoints
POST /chats/new
Request:
json{
  "ai": "claude"
}
Response:
json{
  "success": true,
  "chat_id": "new-chat-123",
  "chat_url": "https://claude.ai/chat/new-chat-123"
}
Errors:

400: Invalid AI name
500: Failed to create chat


GET /chats/list
Query Parameters:

ai (required): AI name (claude/chatgpt/gemini)

Response:
json{
  "success": true,
  "chats": [
    {
      "chat_id": "abc-123",
      "title": "Python refactoring discussion",
      "is_current": true,
      "url": "https://claude.ai/chat/abc-123"
    },
    {
      "chat_id": "def-456",
      "title": "Code review help",
      "is_current": false,
      "url": "https://claude.ai/chat/def-456"
    }
  ]
}

POST /chats/switch
Request:
json{
  "ai": "claude",
  "chat_id": "abc-123"
}
Response:
json{
  "success": true,
  "chat_id": "abc-123",
  "chat_url": "https://claude.ai/chat/abc-123"
}
Errors:

400: Invalid AI or chat_id
404: Chat not found
500: Failed to switch


POST /chats/export
Request:
json{
  "ai": "claude",
  "chat_id": "abc-123"
}
Response:
json{
  "success": true,
  "export": {
    "chat_id": "abc-123",
    "ai": "claude",
    "exported_at": "2025-11-02T10:00:00Z",
    "messages": [
      {
        "role": "user",
        "content": "Hello"
      },
      {
        "role": "assistant",
        "content": "Hi there! How can I help?"
      }
    ]
  }
}

Modified Endpoints
GET /status (Enhanced)
Response (additions):
json{
  "ais": {
    "claude": {
      "current_chat_id": "abc-123",
      "current_chat_url": "https://claude.ai/chat/abc-123",
      "current_chat_title": "Python refactoring",
      ...existing fields...
    }
  }
}
POST /send (Enhanced)
Request (new fields):
json{
  "target": "claude",
  "prompt": "review code",
  "template": "code-review",           // NEW
  "template_vars": {                   // NEW
    "criteria": "bugs,security"
  },
  "context_preset": "project",         // NEW
  "wait_for_response": true,
  "timeout_s": 120
}
Response (unchanged)

📝 Configuration File Formats
Daemon Config (Enhanced)
File: runtime/daemon/config/daemon_config.toml
toml[daemon]
host = "127.0.0.1"
port = 8000
log_level = "INFO"

[cdp]
port = 9223
# ... existing fields ...

[features]
token_align_frequency = 5000

# NEW: Context warning thresholds
[context_warning]
yellow_threshold = 70    # Percentage
orange_threshold = 85
red_threshold = 95

[ai]
# ... existing ai configs ...

Context Presets
File: .ai-cli-bridge/context-presets.toml (project root)
toml# Built-in presets (handled by CLI if file missing)
[presets.project]
discover = "project"
include_tests = false
include_dotfiles = false
chunk = 1500
max_file_bytes = 350000

[presets.module]
discover = "module"
include_tests = false
include_dotfiles = false
chunk = 1500

[presets.cwd]
discover = false  # Don't walk up
include_tests = false
include_dotfiles = false
chunk = 1500

# User can add custom presets
[presets.full]
discover = "project"
include_tests = true
include_dotfiles = true
chunk = 2000

[presets.quick]
discover = "module"
include_tests = false
include_dotfiles = false
chunk = 1000
max_file_bytes = 100000

Prompt Templates
File: .ai-cli-bridge/templates.toml (project root)
toml[templates.code-review]
prompt = """
Review this code for: {criteria}
Focus on: bugs, security, performance, best practices
Code:
{@target_file}
"""
default_vars = { criteria = "all aspects" }

[templates.explain]
prompt = """
Given this project context:
{@context:module}

Explain the following code in detail:
{@file}
"""

[templates.refactor]
prompt = """
Refactor this {language} code to improve:
- Readability
- Performance
- Maintainability

Code:
{code}
"""
default_vars = { language = "Python" }

[templates.debug]
prompt = """
I'm getting this error:
{error}

In this code:
{@file}

Help me debug it.
"""

🎭 Implementation Phases (Staging Strategy)
Phase 0: Preparation (0.5 hours)
Goal: Set up infrastructure for new features
Tasks:

Create new module directories:

src/daemon/chats/
src/daemon/context/
src/daemon/templates/


Add type definitions:

ChatInfo, ExportFormat in chats/types.py
ContextPreset in context/types.py
Template in templates/types.py


Update imports in __init__.py files

Testing:

Verify imports work
No breaking changes

Deliverable: Clean project structure ready for implementation

Phase 1: Context Usage Warning (2-3 hours)
Goal: Add visual warnings when context fills up
Why First?

Smallest feature, easiest to test
No dependencies on other features
Immediate user value
Tests entire stack (daemon → CLI → UI)

1.1 Daemon Config (0.5 hours)
File: src/daemon/config.py
Changes:
python@dataclass
class ContextWarningConfig:
    """Context usage warning thresholds."""
    yellow_threshold: int = 70
    orange_threshold: int = 85
    red_threshold: int = 95

@dataclass
class FeaturesConfig:
    """Feature flags and settings."""
    token_align_frequency: int = 5000
    context_warning: ContextWarningConfig = field(default_factory=ContextWarningConfig)
Update load_config():
pythonif "context_warning" in loaded.get("features", {}):
    warning_data = loaded["features"]["context_warning"]
    for key in ["yellow_threshold", "orange_threshold", "red_threshold"]:
        if key in warning_data:
            val = _as_int(warning_data[key], getattr(config.features.context_warning, key))
            setattr(config.features.context_warning, key, val)
1.2 Chat UI Warning Display (1 hour)
File: src/chat_ui/stats_display.py
Changes:
pythondef update_from_metadata(self, metadata: dict[str, Any]):
    # ... existing code ...
    
    # Context usage with warning colors
    usage_pct = stats_helper.extract_context_usage_percent(metadata)
    if usage_pct is not None:
        # Determine color based on thresholds (hardcoded for now)
        if usage_pct >= 95:
            color = "red"
            icon = " 🛑"
        elif usage_pct >= 85:
            color = "orange"
            icon = " ⚠️"
        elif usage_pct >= 70:
            color = "yellow"
            icon = " ⚠️"
        else:
            color = None
            icon = ""
        
        text = f"Usage: {usage_pct:.1f}%{icon}"
        
        if color:
            self.usage_label.set_markup(f'<span foreground="{color}">{text}</span>')
        else:
            self.usage_label.set_text(text)
    else:
        self.usage_label.set_text("Usage: -")
1.3 CLI Warning Display (0.5 hours)
File: src/cli_bridge/commands/send_cmd.py
Changes:
python# In run() function, after response received:
if response_data.get("success"):
    metadata = response_data.get("metadata", {})
    
    # Check for context warning
    usage = metadata.get("ctaw_usage_percent", 0)
    if usage >= 70:
        if usage >= 95:
            typer.secho(f"  ⚠️  Context: {usage:.1f}% (CRITICAL - start new chat!)", fg=typer.colors.RED)
        elif usage >= 85:
            typer.secho(f"  ⚠️  Context: {usage:.1f}% (HIGH - consider new chat)", fg=typer.colors.YELLOW)
        else:
            typer.secho(f"  ⚠️  Context: {usage:.1f}% (growing)", fg=typer.colors.YELLOW)
1.4 Testing Phase 1
Test Cases:

✅ Send messages until context reaches 70% - verify yellow warning
✅ Continue to 85% - verify orange warning
✅ Continue to 95% - verify red warning
✅ CLI shows warnings at thresholds
✅ UI shows colored text + icons
✅ Config file changes thresholds correctly

Acceptance Criteria:

Warnings display at correct thresholds
Colors/icons visible in UI
CLI warnings non-blocking
Config thresholds customizable


Phase 2: Chat Management - Core (5-7 hours)
Goal: Implement basic chat operations (new, list, switch)
Why Second?

Foundation for other features
Tests transport layer enhancements
Independent of context/templates

2.1 Transport Interface (1 hour)
File: src/daemon/transport/base.py
Add to ITransport:
python@dataclass
class ChatInfo:
    """Information about a chat."""
    chat_id: str
    title: str
    url: str
    is_current: bool

class ITransport(ABC):
    # ... existing methods ...
    
    @abstractmethod
    async def list_chats(self) -> list[ChatInfo]:
        """List all available chats (open tabs)."""
        pass
    
    @abstractmethod
    async def get_current_chat(self) -> ChatInfo | None:
        """Get currently active chat info."""
        pass
    
    @abstractmethod
    async def switch_chat(self, chat_id: str) -> bool:
        """Switch to a specific chat by ID or URL."""
        pass
    
    @abstractmethod
    async def start_new_chat(self) -> ChatInfo | None:
        """Start a new chat and return its info."""
        pass
2.2 WebTransport Implementation (3 hours)
File: src/daemon/transport/web.py
Implement methods:
pythonasync def list_chats(self) -> list[ChatInfo]:
    """List chats from open browser tabs."""
    # 1. Get all pages from browser pool
    # 2. Filter pages matching self.base_url
    # 3. For each matching page:
    #    - Extract chat_id from URL
    #    - Scrape title from page
    #    - Check if current page
    # 4. Return list of ChatInfo
    pass

async def get_current_chat(self) -> ChatInfo | None:
    """Get info about currently active chat."""
    # 1. Get current page
    # 2. Extract chat info
    # 3. Return ChatInfo or None
    pass

async def switch_chat(self, chat_id: str) -> bool:
    """Navigate to specific chat."""
    # 1. Resolve chat_id (support ID, URL, or index)
    # 2. Build full URL
    # 3. Navigate page
    # 4. Wait for load
    # 5. Return success
    pass

async def start_new_chat(self) -> ChatInfo | None:
    """Click new chat button and return info."""
    # 1. Find "new chat" button
    # 2. Click it
    # 3. Wait for navigation
    # 4. Get new chat info
    # 5. Return ChatInfo
    pass
AI-Specific Implementations:
File: src/daemon/transport/claude_web.py
python# Override selectors:
NEW_CHAT_BUTTON = "button[aria-label*='New chat']"
CHAT_TITLE_SELECTOR = "h1" or check page title
CHAT_ID_REGEX = r'/chat/([a-f0-9-]+)'
File: src/daemon/transport/chatgpt_web.py
pythonNEW_CHAT_BUTTON = "a:has-text('New chat')"
CHAT_TITLE_SELECTOR = "..."
CHAT_ID_REGEX = r'/c/([a-zA-Z0-9-]+)'
File: src/daemon/transport/gemini_web.py
pythonNEW_CHAT_BUTTON = "button:has-text('New chat')"
CHAT_TITLE_SELECTOR = "..."
CHAT_ID_REGEX = r'/chat/([a-zA-Z0-9-]+)'
2.3 AI Adapter Delegation (0.5 hours)
Files: claude.py, chatgpt.py, gemini.py
Add methods:
pythonasync def list_chats(self) -> list[dict[str, Any]]:
    """List chats (delegate to transport)."""
    if self._transport and hasattr(self._transport, "list_chats"):
        chats = await self._transport.list_chats()
        return [
            {
                "chat_id": c.chat_id,
                "title": c.title,
                "url": c.url,
                "is_current": c.is_current
            }
            for c in chats
        ]
    return []

async def get_current_chat(self) -> dict[str, Any] | None:
    """Get current chat info."""
    if self._transport and hasattr(self._transport, "get_current_chat"):
        chat = await self._transport.get_current_chat()
        if chat:
            return {
                "chat_id": chat.chat_id,
                "title": chat.title,
                "url": chat.url
            }
    return None

async def switch_chat(self, chat_id: str) -> bool:
    """Switch to specific chat."""
    if self._transport and hasattr(self._transport, "switch_chat"):
        return await self._transport.switch_chat(chat_id)
    return False

async def start_new_chat(self) -> dict[str, Any] | None:
    """Start new chat."""
    if self._transport and hasattr(self._transport, "start_new_chat"):
        chat = await self._transport.start_new_chat()
        if chat:
            return {
                "chat_id": chat.chat_id,
                "title": chat.title,
                "url": chat.url
            }
    return None
2.4 Daemon API Endpoints (1 hour)
File: src/daemon/main.py
Add endpoints:
python@app.post("/chats/new")
async def chats_new(request: dict):
    """Start a new chat."""
    ai_name = request.get("ai")
    if not ai_name or ai_name not in daemon_state["ai_instances"]:
        return {"success": False, "error": "Invalid AI"}
    
    ai = daemon_state["ai_instances"][ai_name]
    chat_info = await ai.start_new_chat()
    
    if chat_info:
        return {"success": True, **chat_info}
    else:
        return {"success": False, "error": "Failed to create chat"}

@app.get("/chats/list")
async def chats_list(ai: str):
    """List available chats."""
    if ai not in daemon_state["ai_instances"]:
        return {"success": False, "error": "Invalid AI"}
    
    ai_instance = daemon_state["ai_instances"][ai]
    chats = await ai_instance.list_chats()
    
    return {"success": True, "chats": chats}

@app.post("/chats/switch")
async def chats_switch(request: dict):
    """Switch to specific chat."""
    ai_name = request.get("ai")
    chat_id = request.get("chat_id")
    
    if not ai_name or ai_name not in daemon_state["ai_instances"]:
        return {"success": False, "error": "Invalid AI"}
    
    ai = daemon_state["ai_instances"][ai_name]
    success = await ai.switch_chat(chat_id)
    
    if success:
        # Get updated chat info
        chat_info = await ai.get_current_chat()
        return {"success": True, **chat_info}
    else:
        return {"success": False, "error": "Failed to switch chat"}

# Modify /status endpoint
@app.get("/status")
async def status():
    # ... existing code ...
    for name, instance in ai_instances.items():
        ai_status = instance.get_ai_status()
        # Add current chat info
        current_chat = await instance.get_current_chat()
        if current_chat:
            ai_status["current_chat_id"] = current_chat["chat_id"]
            ai_status["current_chat_url"] = current_chat["url"]
            ai_status["current_chat_title"] = current_chat["title"]
        ai_statuses[name] = ai_status
    # ...
2.5 CLI Commands (1.5 hours)
File: src/cli_bridge/commands/chats_cmd.py (NEW)
pythonimport typer
from ..constants import API_REQUEST_TIMEOUT_S

app = typer.Typer(help="Manage AI chat sessions", no_args_is_help=True)

@app.command("new")
def new(ai_name: str = typer.Argument(..., help="AI name (claude/chatgpt/gemini)")):
    """Start a new chat session."""
    # POST to /chats/new
    # Display new chat URL
    pass

@app.command("list")
def list_chats(ai_name: str = typer.Argument(..., help="AI name")):
    """List available chat sessions."""
    # GET /chats/list?ai=<ai_name>
    # Format output:
    #   Active  #  Title
    #   *       1  Python refactoring
    #           2  Code review
    pass

@app.command("switch")
def switch(
    ai_name: str = typer.Argument(..., help="AI name"),
    chat_ref: str = typer.Argument(..., help="Chat ID, URL, or index number")
):
    """Switch to a specific chat."""
    # Resolve chat_ref (could be ID, URL, or index)
    # If index: list chats first, get by index
    # POST to /chats/switch
    # Display success message
    pass
File: src/cli_bridge/cli.py
Add chats command group:
pythonfrom .commands import chats_cmd

app.add_typer(chats_cmd.app, name="chats")
2.6 Testing Phase 2
Test Cases:

✅ chats new claude - creates new chat
✅ chats list claude - shows open chats with titles
✅ chats switch claude <id> - switches by ID
✅ chats switch claude <url> - switches by URL
✅ chats switch claude 2 - switches by index
✅ /status includes current_chat_* fields
✅ Test with all 3 AIs (claude/chatgpt/gemini)

Acceptance Criteria:

All chat commands work
Titles scraped correctly
Current chat marked with *
Status endpoint shows current chat
Works across all AI providers


Phase 3: Chat Export (2-3 hours)
Goal: Export conversations to JSON
Why Third?

Builds on Phase 2 (chat management)
Requires message scraping (new capability)
Standalone feature (no dependencies from later phases)

3.1 Message Scraping (1.5 hours)
File: src/daemon/transport/web.py
Add method:
pythonasync def export_chat_messages(self, chat_id: str) -> list[dict]:
    """Scrape all messages from a chat."""
    # 1. Switch to chat (if not current)
    # 2. Scroll to load all messages
    # 3. Find all message elements
    # 4. For each message:
    #    - Determine role (user/assistant)
    #    - Extract content
    # 5. Return message list
    pass
AI-Specific Selectors:
Each transport needs selectors for:

User message container
Assistant message container
Message content area

Claude:
pythonUSER_MESSAGE = "div.font-user-message"
ASSISTANT_MESSAGE = "div.font-claude-message"
MESSAGE_CONTENT = ".standard-markdown, div[class*='content']"
3.2 Export Logic (0.5 hours)
File: src/daemon/chats/exporter.py (NEW)
pythonfrom datetime import datetime, timezone
from typing import Any

async def export_chat(ai_instance, chat_id: str) -> dict[str, Any]:
    """Export a chat to JSON format."""
    # Get current chat info
    current = await ai_instance.get_current_chat()
    
    # Get messages
    messages = await ai_instance.export_chat_messages(chat_id)
    
    # Build export structure
    export = {
        "chat_id": chat_id,
        "ai": ai_instance.ai_target,
        "exported_at": datetime.now(timezone.utc).isoformat() + "Z",
        "messages": messages
    }
    
    return export
3.3 API Endpoint (0.5 hours)
File: src/daemon/main.py
python@app.post("/chats/export")
async def chats_export(request: dict):
    """Export chat as JSON."""
    ai_name = request.get("ai")
    chat_id = request.get("chat_id")
    
    if not ai_name or ai_name not in daemon_state["ai_instances"]:
        return {"success": False, "error": "Invalid AI"}
    
    ai = daemon_state["ai_instances"][ai_name]
    
    try:
        from daemon.chats.exporter import export_chat
        export_data = await export_chat(ai, chat_id)
        return {"success": True, "export": export_data}
    except Exception as e:
        return {"success": False, "error": str(e)}
3.4 CLI Command (0.5 hours)
File: src/cli_bridge/commands/chats_cmd.py
python@app.command("export")
def export(
    ai_name: str = typer.Argument(..., help="AI name"),
    chat_ref: str = typer.Argument(..., help="Chat ID, URL, or index"),
    output: str = typer.Option(None, "--output", "-o", help="Output file (default: stdout)")
):
    """Export chat conversation as JSON."""
    # 1. Resolve chat_ref to chat_id
    # 2. POST to /chats/export
    # 3. Get export JSON
    # 4. If --output: write to file
    #    Else: print to stdout
    pass
3.5 Testing Phase 3
Test Cases:

✅ Export chat with 10+ messages
✅ Verify JSON structure correct
✅ All messages captured (user + assistant)
✅ Export to stdout works
✅ Export to file works (-o chat.json)
✅ Export by ID, URL, and index

Acceptance Criteria:

All messages exported correctly
JSON format matches spec
Works for all AI providers
Both stdout and file output work


Phase 4: Project Context Injection (8-10 hours)
Goal: Integrate generate-context and inject into prompts
Why Fourth?

Most complex feature
Requires subprocess management
File system operations
Token counting
Error handling

4.1 Context Presets Config (1 hour)
File: src/daemon/context/presets.py (NEW)
pythonfrom pathlib import Path
import tomli

@dataclass
class ContextPreset:
    """Context generation preset configuration."""
    name: str
    discover: str | None  # "project", "module", or None (cwd)
    include_tests: bool = False
    include_dotfiles: bool = False
    chunk: int = 1500
    max_file_bytes: int = 350000

DEFAULT_PRESETS = {
    "project": ContextPreset(
        name="project",
        discover="project",
        include_tests=False,
        include_dotfiles=False
    ),
    "module": ContextPreset(
        name="module",
        discover="module",
        include_tests=False,
        include_dotfiles=False
    ),
    "cwd": ContextPreset(
        name="cwd",
        discover=None,
        include_tests=False,
        include_dotfiles=False
    ),
}

def load_presets(config_path: Path = None) -> dict[str, ContextPreset]:
    """Load context presets from config file."""
    presets = DEFAULT_PRESETS.copy()
    
    if config_path and config_path.exists():
        with open(config_path, "rb") as f:
            data = tomli.load(f)
        
        for name, preset_data in data.get("presets", {}).items():
            presets[name] = ContextPreset(
                name=name,
                discover=preset_data.get("discover"),
                include_tests=preset_data.get("include_tests", False),
                include_dotfiles=preset_data.get("include_dotfiles", False),
                chunk=preset_data.get("chunk", 1500),
                max_file_bytes=preset_data.get("max_file_bytes", 350000)
            )
    
    return presets
4.2 Context Generator Integration (2 hours)
File: src/daemon/context/generator.py (NEW)
pythonimport subprocess
import logging
from pathlib import Path
from .presets import ContextPreset

logger = logging.getLogger(__name__)

async def generate_context(preset: ContextPreset, cwd: Path) -> Path:
    """
    Run generate-context and return path to latest report.
    
    Returns:
        Path to context_reports/latest/
    
    Raises:
        RuntimeError: If generation fails
    """
    # Build command
    cmd = ["generate-context"]
    
    if preset.discover == "project":
        cmd.append("--discover-project")
    elif preset.discover == "module":
        cmd.append("--discover-module")
    
    if preset.include_tests:
        cmd.append("--include-tests")
    
    if preset.include_dotfiles:
        cmd.append("--include-dotfiles")
    
    cmd.extend(["--chunk", str(preset.chunk)])
    cmd.extend(["--max-file-bytes", str(preset.max_file_bytes)])
    
    logger.info(f"Running: {' '.join(cmd)}")
    
    # Run subprocess
    result = subprocess.run(
        cmd,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=300  # 5 minute timeout
    )
    
    if result.returncode != 0:
        error_msg = result.stderr or result.stdout or "Unknown error"
        raise RuntimeError(f"generate-context failed: {error_msg}")
    
    # Return path to latest report
    latest_path = cwd / "context_reports" / "latest"
    
    if not latest_path.exists():
        raise RuntimeError("Context generation succeeded but latest/ not found")
    
    logger.info(f"Context generated at: {latest_path}")
    return latest_path
4.3 Context Loader & Token Counter (2 hours)
File: src/daemon/context/injector.py (NEW)
pythonfrom pathlib import Path
import logging

logger = logging.getLogger(__name__)

def load_context_chunks(context_dir: Path) -> str:
    """Load all chunk files and concatenate."""
    chunks = sorted(context_dir.glob("chunk_*.txt"))
    
    if not chunks:
        raise RuntimeError(f"No chunks found in {context_dir}")
    
    content_parts = []
    for chunk_file in chunks:
        with open(chunk_file, "r", encoding="utf-8") as f:
            content_parts.append(f.read())
    
    full_context = "\n\n".join(content_parts)
    logger.info(f"Loaded {len(chunks)} chunks, total length: {len(full_context)} chars")
    
    return full_context

def count_tokens(text: str) -> int:
    """Estimate token count (using tiktoken if available)."""
    try:
        import tiktoken
        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))
    except Exception:
        # Fallback: ~4 chars per token
        return len(text) // 4

def validate_context_size(context: str, max_tokens: int) -> None:
    """Validate context fits within token limit."""
    token_count = count_tokens(context)
    
    if token_count > max_tokens:
        raise ValueError(
            f"Context too large: {token_count:,} tokens exceeds limit of {max_tokens:,} tokens.\n"
            f"Try:\n"
            f"  1. Use smaller scope: --context @module instead of @project\n"
            f"  2. Use a more restrictive preset\n"
            f"  3. Generate context manually with filters"
        )
    
    logger.info(f"Context validation passed: {token_count:,} / {max_tokens:,} tokens")

async def inject_context(
    prompt: str,
    preset_name: str,
    ai_max_tokens: int,
    cwd: Path,
    presets: dict
) -> str:
    """
    Generate context and inject into prompt.
    
    Returns:
        Modified prompt with context prepended
    
    Raises:
        ValueError: Context too large
        RuntimeError: Generation failed
    """
    from .generator import generate_context
    
    # Get preset
    preset = presets.get(preset_name)
    if not preset:
        raise ValueError(f"Unknown context preset: {preset_name}")
    
    # Generate context
    context_dir = await generate_context(preset, cwd)
    
    # Load chunks
    context = load_context_chunks(context_dir)
    
    # Validate size
    validate_context_size(context, ai_max_tokens)
    
    # Inject into prompt
    injected_prompt = f"{context}\n\n---\n\nUser Request:\n{prompt}"
    
    return injected_prompt
4.4 Daemon /send Enhancement (1 hour)
File: src/daemon/main.py
Modify SendRequest:
pythonclass SendRequest(BaseModel):
    target: str
    prompt: str
    wait_for_response: bool = True
    timeout_s: float = 60.0
    context_preset: str | None = None  # NEW
Modify /send handler:
python@app.post("/send")
async def send(request: SendRequest):
    # ... existing validation ...
    
    prompt = request.prompt
    
    # Context injection
    if request.context_preset:
        from daemon.context.injector import inject_context
        from daemon.context.presets import load_presets
        
        # Load presets from project root
        project_root = Path.cwd()
        config_path = project_root / ".ai-cli-bridge" / "context-presets.toml"
        presets = load_presets(config_path)
        
        # Get AI's max tokens
        ai = ai_instances[request.target]
        max_tokens = ai.config.get("max_context_tokens", 200000)
        
        try:
            prompt = await inject_context(
                prompt=request.prompt,
                preset_name=request.context_preset,
                ai_max_tokens=max_tokens,
                cwd=project_root,
                presets=presets
            )
        except ValueError as e:
            # Context too large
            return SendResponse(
                success=False,
                metadata={
                    "error": {
                        "code": "CONTEXT_TOO_LARGE",
                        "message": str(e),
                        "severity": "error"
                    }
                }
            )
        except Exception as e:
            # Generation failed
            return SendResponse(
                success=False,
                metadata={
                    "error": {
                        "code": "CONTEXT_GENERATION_FAILED",
                        "message": str(e),
                        "severity": "error"
                    }
                }
            )
    
    # Continue with normal send logic...
    success, snippet, markdown, metadata = await ai.send_prompt(
        message=prompt,
        wait_for_response=request.wait_for_response,
        timeout_s=request.timeout_s,
    )
    
    # Add context info to metadata
    if request.context_preset:
        metadata["context_preset"] = request.context_preset
        metadata["context_injected"] = True
    
    return SendResponse(...)
4.5 CLI Context Flag (2 hours)
File: src/cli_bridge/commands/send_cmd.py
Add parameter:
pythondef send(
    ai_name: str,
    message: str,
    # ... existing params ...
    context: str | None = typer.Option(
        None,
        "--context",
        help="Inject project context. Format: @preset (e.g., @project, @module)"
    ),
):
    """Send message with optional context injection."""
    
    # Parse context preset
    context_preset = None
    if context:
        if context.startswith("@"):
            context_preset = context[1:]  # Remove @
        else:
            typer.secho("✗ Context must be in format: @preset", fg=typer.colors.RED)
            return 1
    
    # Build payload
    payload = {
        "target": ai_name,
        "prompt": message,
        "wait_for_response": wait,
        "timeout_s": timeout,
        "context_preset": context_preset,  # NEW
    }
    
    # Send request (existing logic)
    # ...
    
    # Handle context errors specifically
    if not response_data.get("success"):
        error = response_data.get("metadata", {}).get("error", {})
        if error.get("code") == "CONTEXT_TOO_LARGE":
            typer.secho("✗ Context Too Large", fg=typer.colors.RED)
            typer.echo(error.get("message"))
            return 1
        elif error.get("code") == "CONTEXT_GENERATION_FAILED":
            typer.secho("✗ Context Generation Failed", fg=typer.colors.RED)
            typer.echo(error.get("message"))
            return 1
    
    # ... rest of existing logic
4.6 CLI Helper for Presets (1 hour)
File: src/cli_bridge/commands/context_cmd.py (NEW)
pythonimport typer
from pathlib import Path
import tomli

app = typer.Typer(help="Manage context generation presets", no_args_is_help=True)

@app.command("list")
def list_presets():
    """List available context presets."""
    config_path = Path.cwd() / ".ai-cli-bridge" / "context-presets.toml"
    
    # Show built-in presets
    typer.echo("Built-in presets:")
    typer.echo("  @project  - Full project context")
    typer.echo("  @module   - Current module context")
    typer.echo("  @cwd      - Current directory only")
    
    # Show custom presets if config exists
    if config_path.exists():
        with open(config_path, "rb") as f:
            data = tomli.load(f)
        
        custom = data.get("presets", {})
        if custom:
            typer.echo("\nCustom presets:")
            for name in custom.keys():
                typer.echo(f"  @{name}")

@app.command("init")
def init_config():
    """Create example context-presets.toml in current project."""
    config_dir = Path.cwd() / ".ai-cli-bridge"
    config_dir.mkdir(exist_ok=True)
    
    config_file = config_dir / "context-presets.toml"
    
    if config_file.exists():
        typer.echo(f"Config already exists: {config_file}")
        return
    
    example = """# Context Generation Presets
# Use with: ai-cli-bridge send <ai> "prompt" --context @preset

[presets.full]
discover = "project"
include_tests = true
include_dotfiles = true
chunk = 2000

[presets.quick]
discover = "module"
include_tests = false
include_dotfiles = false
chunk = 1000
max_file_bytes = 100000
"""
    
    config_file.write_text(example)
    typer.secho(f"✓ Created: {config_file}", fg=typer.colors.GREEN)
Add to main CLI:
python# In cli.py
from .commands import context_cmd
app.add_typer(context_cmd.app, name="context")
4.7 Testing Phase 4
Test Cases:

✅ send claude "review" --context @project - generates and injects
✅ send claude "review" --context @module - uses module scope
✅ Context too large - fails with helpful error
✅ generate-context not found - fails with clear error
✅ Custom preset from config file works
✅ context list shows all presets
✅ context init creates config file
✅ Token counting accurate
✅ Multiple chunks loaded correctly

Acceptance Criteria:

Context generates successfully
Injected into prompt correctly
Size validation works
Errors are clear and helpful
Custom presets supported
CLI commands intuitive


Phase 5: Prompt Templates (4-6 hours)
Goal: Reusable prompt templates with variables
Why Last?

Builds on context injection (uses same variable system)
Least critical feature (nice-to-have)
Can test entire system end-to-end

5.1 Template Config Format (0.5 hours)
File: .ai-cli-bridge/templates.toml (example)
toml[templates.code-review]
prompt = """
Review this code for: {criteria}

Code:
{@file}
"""
default_vars = { criteria = "bugs, security, performance" }

[templates.with-context]
prompt = """
Given this project:
{@context:module}

Please {task}
"""
default_vars = { task = "explain the architecture" }
5.2 Template Loader (1 hour)
File: src/daemon/templates/loader.py (NEW)
pythonfrom pathlib import Path
from dataclasses import dataclass
import tomli

@dataclass
class Template:
    """Prompt template definition."""
    name: str
    prompt: str
    default_vars: dict[str, str]

def load_templates(config_path: Path = None) -> dict[str, Template]:
    """Load templates from TOML file."""
    if not config_path or not config_path.exists():
        return {}
    
    with open(config_path, "rb") as f:
        data = tomli.load(f)
    
    templates = {}
    for name, template_data in data.get("templates", {}).items():
        templates[name] = Template(
            name=name,
            prompt=template_data.get("prompt", ""),
            default_vars=template_data.get("default_vars", {})
        )
    
    return templates
5.3 Variable Substitution Engine (2 hours)
File: src/daemon/templates/engine.py (NEW)
pythonimport re
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

async def substitute_variables(
    template: str,
    variables: dict[str, str],
    context_presets: dict,
    ai_max_tokens: int,
    cwd: Path
) -> str:
    """
    Substitute variables in template.
    
    Supports:
    - {var} - simple variable
    - {@file.py} - file content injection
    - {@context:preset} - context injection
    """
    result = template
    
    # 1. File injection: {@file}
    file_pattern = r'\{@([^}]+)\}'
    for match in re.finditer(file_pattern, template):
        file_ref = match.group(1)
        
        # Check if it's a context reference
        if file_ref.startswith("context:"):
            preset_name = file_ref.split(":", 1)[1]
            # Handle context injection (similar to Phase 4)
            from daemon.context.injector import inject_context
            
            # Generate context
            context_content = await inject_context(
                prompt="",  # Empty prompt, just get context
                preset_name=preset_name,
                ai_max_tokens=ai_max_tokens,
                cwd=cwd,
                presets=context_presets
            )
            
            # Replace in template
            result = result.replace(match.group(0), context_content)
        else:
            # File path injection
            file_path = cwd / file_ref
            
            if not file_path.exists():
                logger.warning(f"File not found: {file_path}")
                result = result.replace(match.group(0), f"[File not found: {file_ref}]")
            else:
                with open(file_path, "r") as f:
                    file_content = f.read()
                result = result.replace(match.group(0), file_content)
    
    # 2. Simple variable substitution: {var}
    for var_name, var_value in variables.items():
        placeholder = f"{{{var_name}}}"
        result = result.replace(placeholder, var_value)
    
    # 3. Check for unresolved placeholders
    unresolved = re.findall(r'\{([^}]+)\}', result)
    if unresolved:
        logger.warning(f"Unresolved placeholders: {unresolved}")
    
    return result
5.4 Daemon Integration (1 hour)
File: src/daemon/main.py
Modify SendRequest:
pythonclass SendRequest(BaseModel):
    target: str
    prompt: str
    wait_for_response: bool = True
    timeout_s: float = 60.0
    context_preset: str | None = None
    template: str | None = None           # NEW
    template_vars: dict[str, str] = {}    # NEW
Modify /send handler:
python@app.post("/send")
async def send(request: SendRequest):
    # ... existing code ...
    
    prompt = request.prompt
    
    # Template processing
    if request.template:
        from daemon.templates.loader import load_templates
        from daemon.templates.engine import substitute_variables
        from daemon.context.presets import load_presets
        
        # Load templates
        project_root = Path.cwd()
        template_path = project_root / ".ai-cli-bridge" / "templates.toml"
        templates = load_templates(template_path)
        
        if request.template not in templates:
            return SendResponse(
                success=False,
                metadata={"error": {"code": "TEMPLATE_NOT_FOUND", "message": f"Template '{request.template}' not found"}}
            )
        
        template_obj = templates[request.template]
        
        # Merge default vars with provided vars
        variables = {**template_obj.default_vars, **request.template_vars}
        
        # Load context presets
        preset_path = project_root / ".ai-cli-bridge" / "context-presets.toml"
        presets = load_presets(preset_path)
        
        # Get AI max tokens
        ai = ai_instances[request.target]
        max_tokens = ai.config.get("max_context_tokens", 200000)
        
        # Substitute variables
        try:
            prompt = await substitute_variables(
                template=template_obj.prompt,
                variables=variables,
                context_presets=presets,
                ai_max_tokens=max_tokens,
                cwd=project_root
            )
        except Exception as e:
            return SendResponse(
                success=False,
                metadata={"error": {"code": "TEMPLATE_SUBSTITUTION_FAILED", "message": str(e)}}
            )
    
    # Context injection (if separate from template)
    elif request.context_preset:
        # ... existing context injection logic ...
        pass
    
    # ... continue with send ...
5.5 CLI Template Flag (1 hour)
File: src/cli_bridge/commands/send_cmd.py
Add parameters:
pythondef send(
    ai_name: str,
    message: str,
    # ... existing params ...
    template: str | None = typer.Option(
        None,
        "--template",
        "-t",
        help="Use prompt template"
    ),
    var: list[str] = typer.Option(
        [],
        "--var",
        help="Template variable (format: key=value)"
    ),
):
    """Send message with optional template."""
    
    # Parse variables
    template_vars = {}
    for v in var:
        if "=" not in v:
            typer.secho(f"✗ Invalid variable format: {v} (use key=value)", fg=typer.colors.RED)
            return 1
        key, value = v.split("=", 1)
        template_vars[key.strip()] = value.strip()
    
    # Build payload
    payload = {
        "target": ai_name,
        "prompt": message,
        "wait_for_response": wait,
        "timeout_s": timeout,
        "template": template,
        "template_vars": template_vars,
    }
    
    # ... rest of send logic ...
5.6 Template Management Commands (1 hour)
File: src/cli_bridge/commands/templates_cmd.py (NEW)
pythonimport typer
from pathlib import Path

app = typer.Typer(help="Manage prompt templates", no_args_is_help=True)

@app.command("list")
def list_templates():
    """List available templates."""
    config_path = Path.cwd() / ".ai-cli-bridge" / "templates.toml"
    
    if not config_path.exists():
        typer.echo("No templates found. Run 'templates init' to create config.")
        return
    
    import tomli
    with open(config_path, "rb") as f:
        data = tomli.load(f)
    
    templates = data.get("templates", {})
    if not templates:
        typer.echo("No templates defined in config.")
        return
    
    for name, template_data in templates.items():
        prompt_preview = template_data.get("prompt", "")[:60].replace("\n", " ")
        typer.echo(f"{name:20} {prompt_preview}...")
        
        defaults = template_data.get("default_vars", {})
        if defaults:
            typer.echo(f"  Default vars: {', '.join(defaults.keys())}")

@app.command("show")
def show_template(name: str):
    """Show template details."""
    config_path = Path.cwd() / ".ai-cli-bridge" / "templates.toml"
    
    if not config_path.exists():
        typer.secho("✗ No templates config found", fg=typer.colors.RED)
        return
    
    import tomli
    with open(config_path, "rb") as f:
        data = tomli.load(f)
    
    templates = data.get("templates", {})
    if name not in templates:
        typer.secho(f"✗ Template '{name}' not found", fg=typer.colors.RED)
        return
    
    template = templates[name]
    typer.echo(f"Template: {name}")
    typer.echo(f"\nPrompt:\n{template['prompt']}")
    
    defaults = template.get("default_vars", {})
    if defaults:
        typer.echo(f"\nDefault variables:")
        for key, value in defaults.items():
            typer.echo(f"  {key} = {value}")

@app.command("init")
def init_config():
    """Create example templates.toml."""
    config_dir = Path.cwd() / ".ai-cli-bridge"
    config_dir.mkdir(exist_ok=True)
    
    config_file = config_dir / "templates.toml"
    
    if config_file.exists():
        typer.echo(f"Config already exists: {config_file}")
        return
    
    example = """# Prompt Templates
# Use with: ai-cli-bridge send <ai> "message" --template <name>

[templates.code-review]
prompt = \"\"\"
Review this code for: {criteria}

Code:
{@file}
\"\"\"
default_vars = { criteria = "bugs, security, performance" }

[templates.explain]
prompt = \"\"\"
Given this project context:
{@context:module}

Explain the following in detail:
{topic}
\"\"\"
default_vars = { topic = "the architecture" }
"""
    
    config_file.write_text(example)
    typer.secho(f"✓ Created: {config_file}", fg=typer.colors.GREEN)
Add to main CLI:
python# In cli.py
from .commands import templates_cmd
app.add_typer(templates_cmd.app, name="templates")
5.7 Testing Phase 5
Test Cases:

✅ templates init creates config
✅ templates list shows templates
✅ templates show code-review displays template
✅ send claude --template code-review --var criteria=security works
✅ File injection {@file.py} loads file content
✅ Context injection {@context:module} works in template
✅ Default variables used when not provided
✅ Unresolved placeholders logged as warning
✅ Template not found error clear

Acceptance Criteria:

Templates load from config
Variable substitution works
File and context injection work
CLI commands intuitive
Error messages helpful


📈 Effort Estimation
PhaseFeatureHoursComplexity0Preparation0.5Low1Context Warning2-3Low2Chat Management5-7Medium3Chat Export2-3Medium4Context Injection8-10High5Prompt Templates4-6MediumTotal22-29.5
With Testing & Documentation: 30-40 hours
With Buffer (20%): 40-50 hours

✅ Testing Strategy
Unit Tests
For each phase, create unit tests:
python# tests/test_context_warning.py
def test_warning_thresholds():
    """Test warning color selection at thresholds."""
    assert get_warning_level(65) == "none"
    assert get_warning_level(70) == "yellow"
    assert get_warning_level(85) == "orange"
    assert get_warning_level(95) == "red"

# tests/test_chat_management.py
async def test_list_chats():
    """Test listing chats from browser."""
    chats = await transport.list_chats()
    assert len(chats) > 0
    assert all("chat_id" in c for c in chats)

# tests/test_context_injection.py
async def test_generate_context():
    """Test context generation."""
    preset = ContextPreset(name="test", discover="module")
    path = await generate_context(preset, Path.cwd())
    assert path.exists()
    assert (path / "chunk_0001.txt").exists()

# tests/test_templates.py
def test_variable_substitution():
    """Test simple variable substitution."""
    template = "Hello {name}"
    result = substitute_variables_sync(template, {"name": "World"})
    assert result == "Hello World"
Integration Tests
Test full stack for each phase:
bash# Phase 1: Context Warning
# 1. Start daemon
# 2. Send messages until 70%
# 3. Verify CLI shows warning
# 4. Verify UI shows yellow color

# Phase 2: Chat Management
# 1. Create new chat
# 2. List chats
# 3. Verify new chat in list
# 4. Switch to another chat
# 5. Verify /status shows correct current_chat

# Phase 3: Export
# 1. Create chat with 5 messages
# 2. Export chat
# 3. Verify JSON has all messages
# 4. Verify roles correct

# Phase 4: Context Injection
# 1. Create .ai-cli-bridge/context-presets.toml
# 2. Send with --context @project
# 3. Verify context generated
# 4. Verify prompt includes context
# 5. Test error: context too large

# Phase 5: Templates
# 1. Create .ai-cli-bridge/templates.toml
# 2. Send with --template test
# 3. Verify variables substituted
# 4. Test file injection
# 5. Test context injection in template
Manual Testing Checklist
After Each Phase:

 Feature works in daemon (API endpoints)
 Feature works in CLI
 Feature works in chat_ui (if applicable)
 Errors handled gracefully
 Help text clear and accurate
 Documentation updated

Before Final Release:

 All unit tests pass
 All integration tests pass
 No regressions in existing features
 Performance acceptable
 Memory usage reasonable
 Error messages helpful
 User documentation complete


🚀 Deployment & Rollout
Version Numbering
Current: v2.1.0
After all phases: v2.2.0 (minor version bump for new features)
Individual phase releases (optional):

Phase 1: v2.1.1 (patch - warning feature)
Phase 2: v2.1.2 (patch - chat management)
Phase 3: v2.1.3 (patch - export)
Phase 4: v2.1.4 (patch - context)
Phase 5: v2.2.0 (minor - templates complete)

Migration Guide
For Users:

Update Config (Phase 1):

toml   # Add to daemon_config.toml
   [context_warning]
   yellow_threshold = 70
   orange_threshold = 85
   red_threshold = 95

Create Project Configs (Phase 4 & 5):

bash   mkdir -p .ai-cli-bridge
   ai-cli-bridge context init
   ai-cli-bridge templates init

Install generate-context (Phase 4):

Ensure generate-context is in PATH
Or install in monorepo with direnv



Breaking Changes: None (all features additive)

📚 Documentation Updates Needed
README.md Updates
Add sections for:

Context Warning Configuration
Chat Management Commands
Project Context Injection
Conversation Export
Prompt Templates

New Documentation Files
Create:

docs/CONTEXT_INJECTION.md - Context generation guide
docs/TEMPLATES.md - Template syntax and examples
docs/CHAT_MANAGEMENT.md - Chat operations guide

CLI Help Text
Ensure all new commands have:

Clear descriptions
Usage examples
Common error scenarios


🐛 Known Limitations & Future Work
Phase 2: Chat Management

Limitation: Only shows currently open browser tabs
Future: Persistent chat history database

Phase 3: Export

Limitation: No import functionality
Future: Import chat to recreate conversation

Phase 4: Context Injection

Limitation: Always regenerates (no caching)
Future: Smart caching with staleness detection

Phase 5: Templates

Limitation: Project-local only
Future: Global templates + project override

Deferred Features

Chat search (needs persistent storage)
Auto-cleanup (needs chat metadata)
Session persistence (needs state management)


📞 Support & Troubleshooting
Common Issues
Context generation fails:

Check generate-context is in PATH
Verify direnv is loaded
Check for file permission issues

Chat list empty:

Ensure browser tabs are open
Check CDP connection healthy
Verify correct AI URL pattern

Template not found:

Check .ai-cli-bridge/templates.toml exists
Verify template name spelling
Run templates list to see available

Context too large:

Use smaller preset (@module instead of @project)
Create custom preset with filters
Generate manually with --max-file-bytes


✨ Success Metrics
Phase 1: Context Warning

✅ Warnings display at correct thresholds
✅ User feedback: "helpful reminder to start new chat"

Phase 2: Chat Management

✅ Can switch between chats in <2 seconds
✅ Chat titles display correctly 95%+ of the time

Phase 3: Export

✅ Export completes in <10 seconds for 50-message chat
✅ All messages captured accurately

Phase 4: Context Injection

✅ Context generation completes in <30 seconds for medium project
✅ Token validation catches oversized context 100% of the time

Phase 5: Templates

✅ Variable substitution works for all supported formats
✅ Templates reduce typing by 50%+ for common tasks


🎯 Implementation Checklist
Phase 0: Preparation

 Create new module directories
 Add type definitions
 Update imports

Phase 1: Context Warning

 Add config dataclass
 Update config loader
 Implement UI warning display
 Implement CLI warning display
 Test all thresholds
 Update documentation

Phase 2: Chat Management

 Define ITransport interface
 Implement WebTransport methods
 Add AI-specific selectors
 Create daemon endpoints
 Build CLI commands
 Update /status endpoint
 Test all 3 AIs
 Update documentation

Phase 3: Export

 Implement message scraping
 Create export logic
 Add daemon endpoint
 Build CLI command
 Test export formats
 Update documentation

Phase 4: Context Injection

 Create presets config
 Implement generator integration
 Build context loader
 Add token counter
 Modify /send endpoint
 Add CLI flag
 Create context commands
 Test all presets
 Update documentation

Phase 5: Templates

 Define template format
 Implement template loader
 Build substitution engine
 Modify /send endpoint
 Add CLI flags
 Create template commands
 Test all variable types
 Update documentation


End of Implementation Plan

Quick Reference
Command Summary
bash# Context Warning (Phase 1)
# - Automatic in UI/CLI output

# Chat Management (Phase 2)
ai-cli-bridge chats new claude
ai-cli-bridge chats list claude
ai-cli-bridge chats switch claude <id|url|index>

# Export (Phase 3)
ai-cli-bridge chats export claude <id> > chat.json

# Context Injection (Phase 4)
ai-cli-bridge send claude "review" --context @project
ai-cli-bridge context list
ai-cli-bridge context init

# Templates (Phase 5)
ai-cli-bridge send claude "msg" --template code-review --var criteria=bugs
ai-cli-bridge templates list
ai-cli-bridge templates show <name>
ai-cli-bridge templates init
File Locations
runtime/daemon/config/daemon_config.toml     # Context warning thresholds
.ai-cli-bridge/context-presets.toml          # Context generation presets
.ai-cli-bridge/templates.toml                # Prompt templates
context_reports/latest/                       # Generated context
