# AI Subsystem Architecture Documentation

**Project:** AI-App v2.0.0
**Last Updated:** October 27, 2025
**Subsystem:** `src/daemon/ai/`

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture Principles](#architecture-principles)
3. [Component Structure](#component-structure)
4. [Class Hierarchy](#class-hierarchy)
5. [Core Components](#core-components)
6. [AI Adapters](#ai-adapters)
7. [Factory Pattern](#factory-pattern)
8. [Session Management](#session-management)
9. [Integration with Transport Layer](#integration-with-transport-layer)
10. [Usage Examples](#usage-examples)
11. [Extension Guide](#extension-guide)
12. [Troubleshooting](#troubleshooting)

---

## Overview

The AI subsystem provides a **transport-agnostic abstraction layer** for interacting with multiple AI chat services (Claude, ChatGPT, Gemini). It separates the **what** (AI operations like sending prompts, tracking sessions) from the **how** (web automation, API calls).

### Key Features

- **Pure adapters**: AI classes contain zero transport logic
- **Session tracking**: Token counting, turn tracking, context window management
- **Fail-fast design**: Clear errors when transport missing (no silent fallbacks)
- **Factory registration**: Dynamic AI discovery and instantiation
- **Public API stability**: `/send` and `/status` endpoints remain unchanged

### Design Goals

1. **Separation of Concerns**: AI logic separate from transport mechanics
2. **Extensibility**: Add new AIs or transports without modifying existing code
3. **Testability**: Mock transports for unit testing
4. **Maintainability**: Site-specific changes isolated to transport layer
5. **Type Safety**: Clear interfaces and contracts

---

## Architecture Principles

### 1. Transport Agnosticism

AI adapters **never** directly interact with:
- Playwright/CDP
- HTTP clients
- WebSocket connections
- Browser automation

All interaction happens through the **transport interface**.

### 2. Dependency Inversion

```
┌─────────────────┐
│   AI Adapter    │ (high-level: business logic)
│   (ClaudeAI)    │
└────────┬────────┘
         │ depends on
         ▼
┌─────────────────┐
│   ITransport    │ (interface/contract)
│   (abstract)    │
└────────┬────────┘
         │ implemented by
         ▼
┌─────────────────┐
│  WebTransport   │ (low-level: implementation)
│  APITransport   │
└─────────────────┘
```

High-level modules (AI adapters) depend on abstractions (ITransport), not implementations.

### 3. Single Responsibility

Each class has **one reason to change**:

- **BaseAI**: Session tracking and token counting logic changes
- **AI Adapters**: AI-specific configuration changes
- **Transports**: Site-specific selector/workflow changes

### 4. Fail-Fast Philosophy

**No silent fallbacks or legacy code paths.**

If a transport is not attached:
```python
return False, None, None, {
    "error": {
        "code": "TRANSPORT_NOT_ATTACHED",
        "message": "No transport attached to ClaudeAI.",
        "severity": "error",
        "suggested_action": "Attach a transport at startup."
    }
}
```

Clear, actionable error messages guide developers to fix issues immediately.

---

## Component Structure

```
src/daemon/ai/
├── __init__.py           # Package exports
├── base.py               # BaseAI abstract class
├── factory.py            # AIFactory for registration/instantiation
├── claude.py             # ClaudeAI adapter
├── chatgpt.py            # ChatGPTAI adapter
└── gemini.py             # GeminiAI adapter
```

### File Responsibilities

| File | Purpose | Lines of Code |
|------|---------|---------------|
| `base.py` | Abstract base class, session state, token counting | ~400 |
| `factory.py` | Registration and discovery pattern | ~100 |
| `claude.py` | Claude-specific adapter | ~150 |
| `chatgpt.py` | ChatGPT-specific adapter | ~150 |
| `gemini.py` | Gemini-specific adapter | ~150 |

---

## Class Hierarchy

```
BaseAI (Abstract)
├── Properties
│   ├── ai_target: str
│   ├── config: dict
│   └── _session: SessionState
├── Abstract Methods
│   ├── send_prompt()
│   ├── list_messages()
│   ├── extract_message()
│   ├── start_new_session()
│   └── get_transport_status()
└── Concrete Methods
    ├── get_ai_status()
    ├── get_ai_target()
    ├── _count_tokens()
    └── _update_session_from_interaction()

ClaudeAI, ChatGPTAI, GeminiAI (Concrete Implementations)
├── Inherit from BaseAI
├── Implement all abstract methods
├── Add: attach_transport()
└── Delegate operations to transport
```

---

## Core Components

### 1. SessionState (Dataclass)

Encapsulates all session tracking without knowing HOW operations are performed.

```python
@dataclass
class SessionState:
    """Self-contained session tracking."""

    turn_count: int = 0
    token_count: int = 0
    message_count: int = 0
    ctaw_size: int = 200000  # Context window size
    session_start_time: float = field(default_factory=time.time)
    last_interaction_time: float | None = None
    message_history: list[dict[str, Any]] = field(default_factory=list)
```

**Key Methods:**

- `add_message(sent_tokens, response_tokens)` → Records exchange, returns tokens used
- `reset()` → Clear all state for new session
- `get_duration_s()` → Session duration in seconds
- `get_ctaw_usage_percent()` → Context window usage percentage
- `to_dict()` → Export for status reporting

**Design Note:** Fully self-contained with its own CTAW tracking. No external dependencies.

### 2. BaseAI (Abstract Base Class)

Defines **WHAT** operations are possible with an AI system, without specifying **HOW**.

#### Abstract Methods (Must Implement)

```python
async def send_prompt(
    self,
    message: str,
    wait_for_response: bool = True,
    timeout_s: int = 120
) -> tuple[bool, str | None, str | None, dict[str, Any]]:
    """
    Send message and optionally wait for response.

    Returns:
        (success, snippet, full_response, metadata)
    """
    pass

async def list_messages(self) -> list[dict[str, Any]]:
    """List all messages in current conversation."""
    pass

async def extract_message(self, baseline_count: int = 0) -> dict:
    """Extract most recent assistant message."""
    pass

async def start_new_session(self) -> bool:
    """Start new chat session/conversation."""
    pass

def get_transport_status(self) -> dict[str, Any]:
    """Get transport-layer status."""
    pass
```

#### Concrete Methods (Inherited)

```python
def get_ai_status(self) -> AIStatus:
    """Get AI session status (implementation-agnostic)."""
    return {
        "ai_target": self.get_ai_target(),
        **self._session.to_dict(),
    }

def _count_tokens(self, text: str) -> int:
    """
    Count tokens using tiktoken or fallback.

    If tiktoken available: accurate token count
    Fallback: len(text) // 4 (rough approximation)
    """
    if self._tokenizer:
        return len(self._tokenizer.encode(text))
    return len(text) // 4

def _update_session_from_interaction(
    self,
    message: str,
    response: str
) -> dict[str, Any]:
    """
    Update session state after interaction.

    Returns metadata dict with token counts.
    """
    sent_tokens = self._count_tokens(message)
    response_tokens = self._count_tokens(response)
    tokens_used = self._session.add_message(sent_tokens, response_tokens)

    return {
        "turn_count": self._session.turn_count,
        "message_count": self._session.message_count,
        "token_count": self._session.token_count,
        "tokens_used": tokens_used,
        "sent_tokens": sent_tokens,
        "response_tokens": response_tokens,
        "ctaw_usage_percent": self._session.get_ctaw_usage_percent(),
        "ctaw_size": self._session.ctaw_size,
        "session_duration_s": round(self._session.get_duration_s(), 1),
    }
```

#### Key Principles

**No references to:**
- Transport mechanisms (CDP, HTTP, WebSocket)
- Implementation details (Playwright, browsers, API clients)
- Site-specific selectors or workflows

**Only logical AI operations:**
- Send message
- List messages
- Extract responses
- Session state tracking

---

## AI Adapters

All three adapters (Claude, ChatGPT, Gemini) follow **identical structure**.

### Common Pattern

```python
class [AI-Name]AI(BaseAI):
    """Transport-agnostic [AI-Name] adapter."""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self._transport: Optional["ITransport"] = None

    def attach_transport(self, transport: "ITransport") -> None:
        """Attach transport at startup."""
        self._transport = transport
        logger.info("[AI]AI: transport attached -> %s",
                    getattr(transport, "name", "unknown"))

    async def send_prompt(self, message, wait_for_response, timeout_s, **kwargs):
        """Delegate to transport; preserve session accounting."""

        # 1. Verify transport attached
        if not self._transport:
            return False, None, None, {
                "error": {
                    "code": "TRANSPORT_NOT_ATTACHED",
                    "message": "No transport attached to [AI]AI.",
                    "severity": "error",
                    "suggested_action": "Attach a transport at startup.",
                }
            }

        # 2. Delegate to transport
        success, snippet, markdown, meta = await self._transport.send_prompt(
            message, wait_for_response=wait_for_response, timeout_s=timeout_s
        )

        # 3. Add session accounting if successful
        if success and (markdown or snippet):
            response_text = markdown or snippet or ""
            session_meta = self._update_session_from_interaction(message, response_text)
            for k, v in session_meta.items():
                meta.setdefault(k, v)

        # 4. Ensure timeout_s present
        meta.setdefault("timeout_s", timeout_s)

        return success, snippet, markdown, meta

    # ... other methods follow same pattern: check transport, delegate, return

    def get_ai_status(self) -> Dict[str, Any]:
        """Extend BaseAI status with transport info."""
        base = super().get_ai_status()
        base["transport"] = self.get_transport_status()
        return base

    @classmethod
    def get_default_config(cls) -> Dict[str, Any]:
        """AI-specific defaults."""
        return {
            "ai_target": "[ai-name]",
            "max_context_tokens": [size],  # AI-specific context window
            "response_wait_s": 60.0,
            "completion_check_interval_s": 0.3,
        }
```

### ClaudeAI Specifics

```python
@classmethod
def get_default_config(cls) -> Dict[str, Any]:
    return {
        "ai_target": "claude",
        "max_context_tokens": 200000,  # 200K context window
        "response_wait_s": 60.0,
        "completion_check_interval_s": 0.3,
    }

# Registered with factory
AIFactory.register("claude", ClaudeAI)
```

### ChatGPTAI Specifics

```python
@classmethod
def get_default_config(cls) -> Dict[str, Any]:
    return {
        "ai_target": "chatgpt",
        "max_context_tokens": 128000,  # 128K context window (GPT-4)
        "response_wait_s": 60.0,
        "completion_check_interval_s": 0.3,
    }

# Registered with factory
AIFactory.register("chatgpt", ChatGPTAI)
```

### GeminiAI Specifics

```python
@classmethod
def get_default_config(cls) -> Dict[str, Any]:
    return {
        "ai_target": "gemini",
        "max_context_tokens": 2000000,  # 2M context window (Gemini 1.5 Pro)
        "response_wait_s": 60.0,
        "completion_check_interval_s": 0.3,
    }

# Registered with factory
AIFactory.register("gemini", GeminiAI)
```

---

## Factory Pattern

### AIFactory Class

**Purpose:** Manages registration and instantiation of AI implementations.

```python
class AIFactory:
    """Factory for creating AI instances."""

    _registry: dict[str, type[BaseAI]] = {}

    @classmethod
    def register(cls, ai_name: str, ai_class: type[BaseAI]) -> None:
        """Register an AI implementation."""
        normalized_name = ai_name.lower().strip()
        cls._registry[normalized_name] = ai_class

    @classmethod
    def get_class(cls, ai_name: str) -> type[BaseAI]:
        """Get the AI class without instantiating."""
        normalized = ai_name.lower().strip()
        if normalized not in cls._registry:
            raise ValueError(f"Unknown AI: {ai_name}")
        return cls._registry[normalized]

    @classmethod
    def create(cls, ai_name: str, config: dict[str, Any]) -> BaseAI:
        """Create an AI instance."""
        ai_class = cls.get_class(ai_name)
        return ai_class(config)

    @classmethod
    def list_available(cls) -> list[str]:
        """List all registered AIs."""
        return sorted(cls._registry.keys())

    @classmethod
    def import_all_ais(cls) -> None:
        """Import all AI modules to trigger registration."""
        from . import claude, chatgpt, gemini  # noqa
```

### Registration Flow

```
1. AI module loads (e.g., claude.py)
   ↓
2. ClaudeAI class defined
   ↓
3. At module bottom: AIFactory.register("claude", ClaudeAI)
   ↓
4. Class registered in factory registry
   ↓
5. Available for discovery via AIFactory.list_available()
```

### Usage in main.py

```python
# Daemon startup
AIFactory.import_all_ais()
available_ais = AIFactory.list_available()  # ['chatgpt', 'claude', 'gemini']

for ai_name in available_ais:
    ai_class = AIFactory.get_class(ai_name)
    config = ai_class.get_default_config()
    instance = AIFactory.create(ai_name, config)
    ai_instances[ai_name] = instance
```

**Benefits:**

- ✅ No hardcoded AI list
- ✅ New AIs auto-discovered on import
- ✅ Centralized registration
- ✅ Type-safe instantiation

---

## Session Management

### Session State Lifecycle

```
┌──────────────────┐
│ Daemon Starts    │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ AI Instance      │
│ Created          │
│                  │
│ SessionState:    │
│ - turn_count: 0  │
│ - token_count: 0 │
│ - start_time: now│
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ send_prompt()    │
│ called           │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Transport        │
│ handles request  │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Response         │
│ received         │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ _update_session_ │
│ from_interaction │
│                  │
│ - Count tokens   │
│ - Increment turn │
│ - Update CTAW%   │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Return metadata  │
│ with session info│
└──────────────────┘
```

### Token Counting Strategy

**Primary: tiktoken (accurate)**
```python
if self._tokenizer:
    return len(self._tokenizer.encode(text))
```

**Fallback: Character approximation**
```python
return len(text) // 4  # ~4 chars per token
```

### Context Window (CTAW) Management

**Formula:**
```python
ctaw_usage_percent = (token_count / ctaw_size) * 100.0
```

**Example:**
```python
# After 10 messages totaling 5,000 tokens
# Claude with 200K window:
usage = (5000 / 200000) * 100 = 2.5%

# ChatGPT with 128K window:
usage = (5000 / 128000) * 100 = 3.9%
```

### Session Metadata Structure

```python
{
    "turn_count": 5,              # Number of exchanges
    "message_count": 5,           # Same as turn_count for now
    "token_count": 1250,          # Total tokens used
    "tokens_used": 250,           # Last exchange only
    "sent_tokens": 150,           # User message tokens
    "response_tokens": 100,       # AI response tokens
    "ctaw_usage_percent": 0.63,   # Context window usage
    "ctaw_size": 200000,          # Max context window
    "session_duration_s": 45.2,   # Time since session start
    "last_interaction_time": 1730044567.234
}
```

---

## Integration with Transport Layer

### Transport Interface Contract

From `src/daemon/transport/base.py`:

```python
class ITransport(ABC):
    """Abstract transport interface."""

    @abstractmethod
    async def send_prompt(
        self,
        message: str,
        *,
        wait_for_response: bool = True,
        timeout_s: float = 60.0,
    ) -> SendResult:
        """
        Send prompt and return result.

        Returns:
            Tuple[bool, Optional[str], Optional[str], Dict[str, Any]]
            (success, snippet, markdown, metadata)
        """
        pass

    @abstractmethod
    def get_status(self) -> dict[str, Any]:
        """Get transport status."""
        pass
```

### Attachment Flow

**In main.py (daemon startup):**

```python
# 1. Create AI instances
ai_instances = {}
for ai_name in ['claude', 'chatgpt', 'gemini']:
    config = AIFactory.get_class(ai_name).get_default_config()
    ai_instances[ai_name] = AIFactory.create(ai_name, config)

# 2. Create transports
claude_transport = ClaudeWebTransport(
    base_url="https://claude.ai",
    browser_pool=browser_pool,
    logger=logger
)

chatgpt_transport = ChatGPTWebTransport(
    base_url="https://chatgpt.com",
    browser_pool=browser_pool,
    logger=logger
)

gemini_transport = GeminiWebTransport(
    base_url="https://gemini.google.com",
    browser_pool=browser_pool,
    logger=logger
)

# 3. Attach transports to AIs
ai_instances['claude'].attach_transport(claude_transport)
ai_instances['chatgpt'].attach_transport(chatgpt_transport)
ai_instances['gemini'].attach_transport(gemini_transport)
```

### Message Flow

```
FastAPI /send endpoint
  │
  ├─► Validate request
  │
  ├─► Get AI instance: ai_instances[target]
  │
  ├─► Call: ai.send_prompt(message, ...)
  │     │
  │     ├─► Check transport attached
  │     │
  │     ├─► Delegate: transport.send_prompt(...)
  │     │     │
  │     │     ├─► Get CDP connection
  │     │     ├─► Navigate/reuse page
  │     │     ├─► Send message
  │     │     ├─► Wait for response
  │     │     └─► Extract response
  │     │
  │     ├─► Update session state
  │     │
  │     └─► Return (success, snippet, markdown, metadata)
  │
  └─► Return JSON response
```

### Status Reporting

**AI Status (from adapter):**
```json
{
  "ai_target": "claude",
  "turn_count": 5,
  "token_count": 1250,
  "message_count": 5,
  "session_duration_s": 45.2,
  "last_interaction_time": 1730044567.234,
  "ctaw_size": 200000,
  "ctaw_usage_percent": 0.63,
  "transport": {
    "attached": true,
    "name": "WebTransport",
    "kind": "web",
    "status": {
      "kind": "web",
      "base_url": "https://claude.ai",
      "cdp_cached": true,
      "cdp_origin": "discovered"
    }
  }
}
```

---

## Usage Examples

### Example 1: Send a Prompt

```python
# Get AI instance
claude = ai_instances['claude']

# Send prompt
success, snippet, markdown, metadata = await claude.send_prompt(
    message="What is the capital of France?",
    wait_for_response=True,
    timeout_s=60
)

if success:
    print(f"Response: {markdown}")
    print(f"Tokens used: {metadata['tokens_used']}")
    print(f"Turn count: {metadata['turn_count']}")
else:
    print(f"Error: {metadata['error']}")
```

### Example 2: Check AI Status

```python
# Get status
status = claude.get_ai_status()

print(f"AI: {status['ai_target']}")
print(f"Turns: {status['turn_count']}")
print(f"Tokens: {status['token_count']}")
print(f"CTAW Usage: {status['ctaw_usage_percent']}%")
print(f"Transport: {status['transport']['attached']}")
```

### Example 3: Start New Session

```python
# Start fresh conversation
success = await claude.start_new_session()

if success:
    print("New session started")
    # Session state is reset
    status = claude.get_ai_status()
    print(f"Turn count: {status['turn_count']}")  # 0
    print(f"Token count: {status['token_count']}")  # 0
```

### Example 4: Handle Missing Transport

```python
# AI without transport
gemini = GeminiAI({"ai_target": "gemini", "max_context_tokens": 2000000})

# Try to send prompt (no transport attached)
success, snippet, markdown, metadata = await gemini.send_prompt(
    message="Hello",
    wait_for_response=True,
    timeout_s=60
)

print(success)  # False
print(metadata['error'])
# {
#     "code": "TRANSPORT_NOT_ATTACHED",
#     "message": "No transport attached to GeminiAI.",
#     "severity": "error",
#     "suggested_action": "Attach a transport at startup."
# }
```

---

## Extension Guide

### Adding a New AI Provider

**Example: Adding Perplexity**

**Step 1: Create the adapter file**

`src/daemon/ai/perplexity.py`:

```python
import logging
from typing import Any, Dict, Optional, Tuple

from .base import BaseAI
from .factory import AIFactory

try:
    from daemon.transport.base import ITransport
except Exception:
    ITransport = object

logger = logging.getLogger(__name__)


class PerplexityAI(BaseAI):
    """Transport-agnostic Perplexity adapter."""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self._transport: Optional["ITransport"] = None

    def attach_transport(self, transport: "ITransport") -> None:
        self._transport = transport
        logger.info("PerplexityAI: transport attached -> %s",
                    getattr(transport, "name", "unknown"))

    async def send_prompt(self, message, wait_for_response, timeout_s, **kwargs):
        if not self._transport:
            return False, None, None, {
                "error": {
                    "code": "TRANSPORT_NOT_ATTACHED",
                    "message": "No transport attached to PerplexityAI.",
                    "severity": "error",
                    "suggested_action": "Attach a transport at startup.",
                }
            }

        success, snippet, markdown, meta = await self._transport.send_prompt(
            message, wait_for_response=wait_for_response, timeout_s=timeout_s
        )

        if success and (markdown or snippet):
            response_text = markdown or snippet or ""
            session_meta = self._update_session_from_interaction(message, response_text)
            for k, v in session_meta.items():
                meta.setdefault(k, v)

        meta.setdefault("timeout_s", timeout_s)
        return success, snippet, markdown, meta

    # ... implement other abstract methods ...

    def get_transport_status(self) -> Dict[str, Any]:
        t = self._transport
        status = {
            "attached": bool(t),
            "name": getattr(t, "name", None),
            "kind": getattr(getattr(t, "kind", None), "value", None),
        }
        if t and hasattr(t, "get_status"):
            status["status"] = t.get_status()
        return status

    def get_ai_status(self) -> Dict[str, Any]:
        base = super().get_ai_status()
        base["transport"] = self.get_transport_status()
        return base

    @classmethod
    def get_default_config(cls) -> Dict[str, Any]:
        return {
            "ai_target": "perplexity",
            "max_context_tokens": 127000,  # Perplexity context window
            "response_wait_s": 60.0,
            "completion_check_interval_s": 0.3,
        }


# Register with factory
AIFactory.register("perplexity", PerplexityAI)
```

**Step 2: Update `__init__.py`**

`src/daemon/ai/__init__.py`:

```python
from .base import BaseAI
from .factory import AIFactory

# Import implementations to trigger registration
from .claude import ClaudeAI
from .chatgpt import ChatGPTAI
from .gemini import GeminiAI
from .perplexity import PerplexityAI  # Add this line

__all__ = ["BaseAI", "AIFactory", "ClaudeAI", "ChatGPTAI", "GeminiAI", "PerplexityAI"]
```

**Step 3: Create the transport**

`src/daemon/transport/perplexity_web.py` (follow Claude/ChatGPT pattern)

**Step 4: Wire in main.py**

```python
# In daemon startup
perplexity_transport = PerplexityWebTransport(
    base_url="https://perplexity.ai",
    browser_pool=browser_pool,
    logger=logger
)
ai_instances['perplexity'].attach_transport(perplexity_transport)
```

**Done!** Perplexity is now available via `/send` endpoint.

---

## Troubleshooting

### Problem: "TRANSPORT_NOT_ATTACHED" Error

**Symptoms:**
```json
{
  "success": false,
  "error": {
    "code": "TRANSPORT_NOT_ATTACHED",
    "message": "No transport attached to ClaudeAI."
  }
}
```

**Causes:**
1. Transport not created in `main.py`
2. `attach_transport()` not called
3. Transport attachment failed silently

**Solution:**
Check daemon startup logs for:
```
INFO - Attached ClaudeWebTransport to 'claude'
```

If missing, verify:
```python
# In main.py
claude_transport = ClaudeWebTransport(...)
ai_instances['claude'].attach_transport(claude_transport)
```

---

### Problem: Session Stats Not Updating

**Symptoms:**
- `turn_count` stays at 0
- `token_count` not incrementing
- `ctaw_usage_percent` always 0%

**Causes:**
1. `_update_session_from_interaction()` not called
2. Response text empty (no tokens to count)
3. Session state not properly initialized

**Solution:**
Verify in adapter's `send_prompt()`:
```python
if success and (markdown or snippet):
    response_text = markdown or snippet or ""
    session_meta = self._update_session_from_interaction(message, response_text)
    # ... merge into metadata
```

---

### Problem: Token Counts Seem Wrong

**Symptoms:**
- Token count much lower than expected
- CTAW usage percentage seems off

**Causes:**
1. Tiktoken not installed (using fallback approximation)
2. Wrong encoding used
3. Text preprocessing issue

**Solution:**

Check if tiktoken is available:
```python
# In BaseAI.__init__
if TIKTOKEN_AVAILABLE:
    self._tokenizer = tiktoken.get_encoding("cl100k_base")
```

Install tiktoken:
```bash
pip install tiktoken --break-system-packages
```

---

### Problem: AI Status Missing Transport Info

**Symptoms:**
```json
{
  "ai_target": "claude",
  "turn_count": 5,
  // No "transport" key
}
```

**Causes:**
1. `get_ai_status()` not extended in adapter
2. `get_transport_status()` not implemented

**Solution:**
Verify adapter has:
```python
def get_ai_status(self) -> Dict[str, Any]:
    base = super().get_ai_status()
    base["transport"] = self.get_transport_status()
    return base
```

---

## Summary

### Key Takeaways

1. **Pure Adapters**: AI classes delegate to transports, contain zero automation logic
2. **Session Tracking**: Self-contained `SessionState` tracks tokens, turns, CTAW usage
3. **Factory Pattern**: Dynamic AI discovery and registration
4. **Fail-Fast**: Clear errors when transport missing (no silent fallbacks)
5. **Extensibility**: Add new AIs by creating adapter + transport (~200 lines total)

### Directory Structure

```
src/daemon/ai/
├── __init__.py           # Package exports
├── base.py               # BaseAI abstract class + SessionState
├── factory.py            # AIFactory registration system
├── claude.py             # ClaudeAI adapter (150 lines)
├── chatgpt.py            # ChatGPTAI adapter (150 lines)
└── gemini.py             # GeminiAI adapter (150 lines)
```

### Architecture Benefits

✅ **Separation of Concerns**: AI logic separate from transport mechanics
✅ **Testability**: Mock transports for unit tests
✅ **Maintainability**: Site changes isolated to transport layer
✅ **Extensibility**: Add new AIs without modifying existing code
✅ **Type Safety**: Clear interfaces and contracts

---

**Document Version:** 1.0
**Last Reviewed:** October 27, 2025
**Maintainer:** AI-App Development Team
