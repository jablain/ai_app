# AI-App Feature Enhancement Implementation Plan

**Date:** November 4, 2025  
**Version:** 2.0.0  
**Status:** Planning Phase

---

## Executive Summary

This document outlines the implementation plan for five major features being added to ai-app:

1. **Context Usage Warning** - Visual warnings when context window fills up
2. **Chat Management** - Commands to create, list, and switch between chats
3. **Project Context Injection** - Automated codebase context generation and injection
4. **Conversation Export** - Export chat history to JSON format
5. **Prompt Templates** - Reusable prompt templates with variable substitution

**Overall Progress:** ~30% foundation complete  
**Estimated Complexity:** Medium-High  
**Dependencies:** All features can be developed independently except Template system depends on Context Injection

---

## Table of Contents

- [Feature #1: Context Usage Warning](#feature-1-context-usage-warning)
- [Feature #2: Chat Management](#feature-2-chat-management)
- [Feature #3: Project Context Injection](#feature-3-project-context-injection)
- [Feature #4: Conversation Export](#feature-4-conversation-export)
- [Feature #5: Prompt Templates](#feature-5-prompt-templates)
- [Implementation Priority](#implementation-priority)
- [Architecture Overview](#architecture-overview)
- [Development Guidelines](#development-guidelines)

---

## Feature #1: Context Usage Warning

### Status: 70% Complete ⚠️ (needs per-AI refactoring)

### Requirements
- **Thresholds:** 70% (yellow), 85% (orange), 95% (red) - configurable **per AI**
- **UI Display:** Color + icon (⚠️) in stats sidebar usage label
- **CLI Display:** Warning message in output (non-blocking)
- **Config Location:** Per-AI profile in daemon config file (daemon_config.toml)
- **Rationale:** Different AIs have different context window sizes (Claude: 200k, GPT-4: 8k-128k, Gemini: up to 1M+), so thresholds should be AI-specific

### What's Already Implemented

✅ **Configuration Infrastructure** (`src/daemon/config.py`)
```python
# Lines 91-104: ContextWarningConfig dataclass exists
@dataclass
class ContextWarningConfig:
    yellow_threshold: int = 70
    orange_threshold: int = 85
    red_threshold: int = 95
```

⚠️ **Config Loading Logic** (`src/daemon/config.py:408-436`)
- Parses `[features.context_warning]` section from TOML
- Validates threshold values as positive integers
- **NEEDS UPDATE:** Currently applies globally, should be per-AI profile instead

✅ **CLI Display** (`src/cli_bridge/commands/send_cmd.py:126-149`)
```python
# Color-coded warnings already implemented:
if usage >= red:
    typer.secho(f"  ⚠️  Context: {usage:.1f}% (CRITICAL - start new chat!)", 
                fg=typer.colors.RED)
elif usage >= orange:
    typer.secho(f"  ⚠️  Context: {usage:.1f}% (HIGH - consider new chat)", 
                fg=typer.colors.YELLOW)
else:
    typer.secho(f"  ⚠️  Context: {usage:.1f}% (growing)", 
                fg=typer.colors.YELLOW)
```

### Remaining Work

❌ **1. Update Config System to Support Per-AI Thresholds**

**File:** `src/daemon/config.py`

**Changes Needed:**
- Move `ContextWarningConfig` from global to per-AI profile
- Update config loading to read thresholds from each AI profile section
- Provide sensible defaults if thresholds not specified

**File:** `runtime/daemon/config/daemon_config.toml`

**Add per-AI threshold configuration:**
```toml
[ai_profiles.claude]
name = "claude"
# ... existing config ...

[ai_profiles.claude.context_warning]
yellow_threshold = 70
orange_threshold = 85
red_threshold = 95

[ai_profiles.chatgpt]
name = "chatgpt"
# ... existing config ...

[ai_profiles.chatgpt.context_warning]
yellow_threshold = 60   # More conservative due to smaller context window
orange_threshold = 75
red_threshold = 90

[ai_profiles.gemini]
name = "gemini"
# ... existing config ...

[ai_profiles.gemini.context_warning]
yellow_threshold = 80   # More relaxed due to larger context window
orange_threshold = 90
red_threshold = 95
```

**Effort:** 1-2 hours  
**Risk:** Low (refactoring existing config structure)

---

❌ **2. Update CLI to Use Per-AI Thresholds**

**File:** `src/cli_bridge/commands/send_cmd.py`

**Changes Needed:**
- Fetch thresholds from the AI's specific configuration (from status response)
- Use AI-specific thresholds instead of hardcoded values

**Implementation:**
```python
# Get AI-specific thresholds from status response
thresholds = status_data.get('context_warning_thresholds', {
    'yellow': 70,
    'orange': 85,
    'red': 95
})

yellow = thresholds.get('yellow', 70)
orange = thresholds.get('orange', 85)
red = thresholds.get('red', 95)

# Rest of existing display logic...
```

**Effort:** 30 minutes  
**Risk:** Low

---

❌ **3. GTK4 UI Stats Sidebar Enhancement**

**File:** `src/chat_ui/stats_display.py` or `src/chat_ui/window.py`

**Implementation:**
```python
def update_context_display(self, usage_percent: float, thresholds: dict):
    """Update context usage label with color coding using AI-specific thresholds."""
    
    # Determine color based on AI-specific thresholds
    if usage_percent >= thresholds['red']:
        color = 'red'
        icon = '⚠️'
        severity = 'CRITICAL'
    elif usage_percent >= thresholds['orange']:
        color = 'orange'
        icon = '⚠️'
        severity = 'HIGH'
    elif usage_percent >= thresholds['yellow']:
        color = 'yellow'
        icon = '⚠️'
        severity = 'WARNING'
    else:
        color = 'green'
        icon = '✓'
        severity = 'OK'
    
    # Update GTK label with Pango markup
    markup = f'<span foreground="{color}">{icon} Context: {usage_percent:.1f}% ({severity})</span>'
    self.context_label.set_markup(markup)
```

**Effort:** 1-2 hours  
**Risk:** Low (GTK4 markup is standard)

---

### Testing Checklist

- [ ] Config loads correctly with per-AI custom thresholds
- [ ] Config validates (rejects negative values, invalid types)
- [ ] Different AIs can have different thresholds
- [ ] CLI displays correct colors at each threshold for each AI
- [ ] GTK4 UI updates in real-time with AI-specific thresholds
- [ ] Default values work when AI profile lacks context_warning section
- [ ] Warnings appear non-blocking (don't prevent send)
- [ ] Switching between AIs applies correct thresholds

### Completion Criteria

- ⚠️ Config infrastructure (exists but needs refactoring for per-AI support)
- ⚠️ CLI display (exists but needs update to use AI-specific thresholds)
- ❌ Config system refactored to per-AI
- ❌ Config file populated with per-AI thresholds
- ❌ CLI updated to fetch and use AI-specific thresholds
- ❌ GTK4 UI implementation with AI-specific thresholds
- ❌ Tests written

**Estimated Time to Complete:** 3-5 hours (increased due to per-AI refactoring)

---

## Feature #2: Chat Management

### Status: 40% Complete (Foundation Exists)

### Requirements

**Commands:**
- `chats new <ai>` - Start new chat
- `chats list <ai>` - List open chats
- `chats switch <ai> <id|url|index>` - Switch to specific chat

**Features:**
- List Display: Active marker, index #, title (scraped from DOM)
- Identification: Support chat-id, full URL, or list index
- Storage: No persistent database, open browser tabs only
- Status: Include current_chat_id and current_chat_url in AI status

### What's Already Implemented

✅ **Type Definitions** (`src/daemon/chats/types.py`)
```python
@dataclass
class ChatInfo:
    chat_id: str
    title: str
    url: str
    is_current: bool
```

✅ **Transport Layer** (`src/daemon/transport/base.py:231-257`)
```python
async def list_chats(self) -> List[ChatInfo]: ...
async def get_current_chat(self) -> ChatInfo | None: ...
async def switch_chat(self, chat_id: str) -> bool: ...
```

✅ **Web Transport Implementation** (`src/daemon/transport/web.py:607-740`)
- Chat listing from browser tabs
- Current chat detection
- Chat switching by ID/URL
- Title scraping from DOM

✅ **AI Base Class Delegation** (`src/daemon/ai/base.py:374-420`)
- Methods delegate to transport layer
- Error handling in place

### Remaining Work

❌ **1. Create CLI Command Module**

**File:** `src/cli_bridge/commands/chats_cmd.py` (NEW)

```python
"""Chat management commands for ai-cli-bridge."""

from __future__ import annotations

import requests
import typer
from rich.console import Console
from rich.table import Table

from ..errors import DaemonNotRunning

app = typer.Typer(help="Manage AI chat sessions", no_args_is_help=True)
console = Console()


@app.command("new")
def new_chat(
    ai: str = typer.Argument(..., help="AI name (claude, chatgpt, gemini)"),
    host: str = "127.0.0.1",
    port: int = 8000,
):
    """Start a new chat session."""
    try:
        response = requests.post(
            f"http://{host}:{port}/chats/new",
            json={"ai": ai},
            timeout=10
        )
        response.raise_for_status()
        data = response.json()
        
        if data.get("success"):
            chat_info = data.get("chat")
            typer.secho(f"✓ New chat started", fg=typer.colors.GREEN)
            typer.echo(f"  ID: {chat_info.get('chat_id')}")
            typer.echo(f"  URL: {chat_info.get('url')}")
        else:
            typer.secho(f"✗ Failed: {data.get('error')}", fg=typer.colors.RED)
            raise typer.Exit(1)
    except requests.exceptions.ConnectionError:
        typer.secho("✗ Cannot connect to daemon", fg=typer.colors.RED)
        raise typer.Exit(DaemonNotRunning.exit_code)


@app.command("list")
def list_chats(
    ai: str = typer.Argument(..., help="AI name (claude, chatgpt, gemini)"),
    host: str = "127.0.0.1",
    port: int = 8000,
    as_json: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """List all open chat sessions."""
    try:
        response = requests.get(
            f"http://{host}:{port}/chats/list",
            params={"ai": ai},
            timeout=10
        )
        response.raise_for_status()
        data = response.json()
        
        chats = data.get("chats", [])
        
        if as_json:
            import json
            typer.echo(json.dumps({"chats": chats}, indent=2))
            return
        
        if not chats:
            typer.echo(f"No open chats for {ai}")
            return
        
        # Rich table display
        table = Table(title=f"{ai.title()} Chats")
        table.add_column("#", style="cyan")
        table.add_column("Active", style="green")
        table.add_column("Chat ID", style="yellow")
        table.add_column("Title", style="white")
        
        for idx, chat in enumerate(chats):
            active = "●" if chat.get("is_current") else " "
            table.add_row(
                str(idx),
                active,
                chat.get("chat_id", "")[:20],  # Truncate
                chat.get("title", "Untitled")[:50]
            )
        
        console.print(table)
        
    except requests.exceptions.ConnectionError:
        typer.secho("✗ Cannot connect to daemon", fg=typer.colors.RED)
        raise typer.Exit(DaemonNotRunning.exit_code)


@app.command("switch")
def switch_chat(
    ai: str = typer.Argument(..., help="AI name (claude, chatgpt, gemini)"),
    identifier: str = typer.Argument(..., help="Chat ID, URL, or list index"),
    host: str = "127.0.0.1",
    port: int = 8000,
):
    """Switch to a specific chat session."""
    try:
        response = requests.post(
            f"http://{host}:{port}/chats/switch",
            json={"ai": ai, "identifier": identifier},
            timeout=10
        )
        response.raise_for_status()
        data = response.json()
        
        if data.get("success"):
            chat_info = data.get("chat")
            typer.secho(f"✓ Switched to chat", fg=typer.colors.GREEN)
            typer.echo(f"  Title: {chat_info.get('title')}")
            typer.echo(f"  URL: {chat_info.get('url')}")
        else:
            typer.secho(f"✗ Failed: {data.get('error')}", fg=typer.colors.RED)
            raise typer.Exit(1)
            
    except requests.exceptions.ConnectionError:
        typer.secho("✗ Cannot connect to daemon", fg=typer.colors.RED)
        raise typer.Exit(DaemonNotRunning.exit_code)
```

**Effort:** 2-3 hours  
**Risk:** Low (follows existing command patterns)

---

❌ **2. Register Command Group in CLI**

**File:** `src/cli_bridge/cli.py`

**Changes:**
```python
# Add import (around line 21)
from .commands import chats_cmd

# Register command group (after line 40)
app.add_typer(chats_cmd.app, name="chats")
```

**Effort:** 5 minutes  
**Risk:** None

---

❌ **3. Add Daemon API Endpoints**

**File:** `src/daemon/main.py`

**Add Pydantic Models (after line 72):**
```python
class ChatsListRequest(BaseModel):
    """Request model for listing chats."""
    ai: str = Field(..., description="AI target name")


class ChatsNewRequest(BaseModel):
    """Request model for creating new chat."""
    ai: str = Field(..., description="AI target name")


class ChatsSwitchRequest(BaseModel):
    """Request model for switching chats."""
    ai: str = Field(..., description="AI target name")
    identifier: str = Field(..., description="Chat ID, URL, or index")


class ChatsResponse(BaseModel):
    """Response model for chat operations."""
    success: bool
    chat: dict[str, Any] | None = None
    chats: list[dict[str, Any]] | None = None
    error: str | None = None
```

**Add Endpoints (after line 349):**
```python
@app.get("/chats/list", response_model=ChatsResponse)
async def list_chats(ai: str):
    """List all open chats for an AI."""
    ai_instances = daemon_state["ai_instances"]
    
    if ai not in ai_instances:
        return ChatsResponse(
            success=False,
            error=f"Unknown AI: {ai}"
        )
    
    try:
        ai_instance = ai_instances[ai]
        chats = await ai_instance.list_chats()
        return ChatsResponse(
            success=True,
            chats=chats
        )
    except Exception as e:
        logger.error(f"Failed to list chats for {ai}: {e}")
        return ChatsResponse(
            success=False,
            error=str(e)
        )


@app.post("/chats/new", response_model=ChatsResponse)
async def new_chat(request: ChatsNewRequest):
    """Start a new chat session."""
    ai_instances = daemon_state["ai_instances"]
    
    if request.ai not in ai_instances:
        return ChatsResponse(
            success=False,
            error=f"Unknown AI: {request.ai}"
        )
    
    try:
        ai_instance = ai_instances[request.ai]
        # Use transport to navigate to new chat URL
        if hasattr(ai_instance, "_transport"):
            transport = ai_instance._transport
            config = ai_instance.get_config()
            new_chat_url = config.get("new_chat_url", "")
            
            if new_chat_url:
                browser_pool = daemon_state["browser_pool"]
                page = await browser_pool.get_page()
                await page.goto(new_chat_url)
                
                # Get the new chat info
                current_chat = await ai_instance.get_current_chat()
                return ChatsResponse(
                    success=True,
                    chat=current_chat
                )
        
        return ChatsResponse(
            success=False,
            error="New chat creation not supported for this AI"
        )
        
    except Exception as e:
        logger.error(f"Failed to create new chat for {request.ai}: {e}")
        return ChatsResponse(
            success=False,
            error=str(e)
        )


@app.post("/chats/switch", response_model=ChatsResponse)
async def switch_chat(request: ChatsSwitchRequest):
    """Switch to a specific chat."""
    ai_instances = daemon_state["ai_instances"]
    
    if request.ai not in ai_instances:
        return ChatsResponse(
            success=False,
            error=f"Unknown AI: {request.ai}"
        )
    
    try:
        ai_instance = ai_instances[request.ai]
        success = await ai_instance.switch_chat(request.identifier)
        
        if success:
            current_chat = await ai_instance.get_current_chat()
            return ChatsResponse(
                success=True,
                chat=current_chat
            )
        else:
            return ChatsResponse(
                success=False,
                error="Failed to switch chat"
            )
            
    except Exception as e:
        logger.error(f"Failed to switch chat for {request.ai}: {e}")
        return ChatsResponse(
            success=False,
            error=str(e)
        )
```

**Effort:** 2-3 hours  
**Risk:** Medium (needs testing with actual browser)

---

❌ **4. Enhance Status Endpoint**

**File:** `src/daemon/main.py`

**Modify status() function (around line 260):**
```python
ai_statuses = {}
for name, instance in ai_instances.items():
    try:
        status = instance.get_ai_status()
        
        # Add current chat info
        try:
            current_chat = await instance.get_current_chat()
            if current_chat:
                status["current_chat_id"] = current_chat.get("chat_id")
                status["current_chat_url"] = current_chat.get("url")
                status["current_chat_title"] = current_chat.get("title")
        except Exception:
            pass  # Non-fatal
        
        ai_statuses[name] = status
    except Exception as e:
        logger.error(f"Failed to get status for {name}: {e}")
        ai_statuses[name] = {"error": str(e), "ai_target": name}
```

**Effort:** 30 minutes  
**Risk:** Low

---

### Testing Checklist

- [ ] `chats new claude` creates new chat
- [ ] `chats list claude` shows all tabs
- [ ] Active chat marked with ●
- [ ] `chats switch claude 0` works (by index)
- [ ] `chats switch claude <chat-id>` works
- [ ] `chats switch claude https://...` works (by URL)
- [ ] Status shows current chat info
- [ ] Works for all AIs (claude, chatgpt, gemini)
- [ ] Error handling for invalid AI names
- [ ] Error handling for invalid chat identifiers

### Completion Criteria

- ✅ Transport layer methods
- ✅ Type definitions
- ❌ CLI commands
- ❌ Daemon endpoints
- ❌ Status integration
- ❌ Tests

**Estimated Time to Complete:** 6-8 hours

---

## Feature #3: Project Context Injection

### Status: 20% Complete (Tools Exist)

### Requirements

- **Script:** Integrate with existing `generate-context` command
- **Presets:** @project, @module, @cwd
- **Config Presets:** `.ai-cli-bridge/context-presets.toml` in project
- **Regeneration:** Always generate fresh (no caching)
- **Size Management:** Fail with error if context exceeds AI token limit
- **Variables:** Support {var}, {@file}, {@context:preset}

### What's Already Implemented

✅ **Context Generation Tool** (`src/tools/generate_context.py`)
- Full chunking logic for large codebases
- Tree walking with exclusions
- Python file outline generation
- Configurable chunk sizes
- Manifest generation

✅ **Script Wrapper** (`scripts/generate_context`)
- Bash wrapper for tool invocation
- Preface/suffix file support

✅ **Dependencies**
- `tiktoken` library already in dependencies for token counting

### Remaining Work

❌ **1. Create Context Module**

**File:** `src/common/context.py` (NEW)

```python
"""
Context injection system for ai-cli-bridge.

Handles preset loading, context generation, and variable substitution.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import tiktoken
import tomli


@dataclass
class ContextPreset:
    """A context preset configuration."""
    
    name: str
    description: str
    include_patterns: list[str]
    exclude_patterns: list[str]
    max_tokens: int | None = None


class ContextInjector:
    """Manages context injection with preset support."""
    
    def __init__(self, project_root: Path | None = None):
        """
        Initialize context injector.
        
        Args:
            project_root: Project root directory (defaults to cwd)
        """
        self.project_root = project_root or Path.cwd()
        self.presets_file = self.project_root / ".ai-cli-bridge" / "context-presets.toml"
        self.presets: dict[str, ContextPreset] = {}
        self._load_presets()
    
    def _load_presets(self) -> None:
        """Load presets from config file and add built-ins."""
        # Built-in presets
        self.presets["project"] = ContextPreset(
            name="project",
            description="Full project context",
            include_patterns=["**/*.py", "**/*.md", "**/*.toml"],
            exclude_patterns=[
                ".git/**", 
                "__pycache__/**", 
                "*.pyc",
                ".venv/**",
                "venv/**"
            ],
            max_tokens=None
        )
        
        self.presets["module"] = ContextPreset(
            name="module",
            description="Current module only",
            include_patterns=["*.py"],
            exclude_patterns=["__pycache__/**"],
            max_tokens=50000
        )
        
        self.presets["cwd"] = ContextPreset(
            name="cwd",
            description="Current working directory",
            include_patterns=["**/*"],
            exclude_patterns=[".git/**", "__pycache__/**"],
            max_tokens=100000
        )
        
        # Load custom presets from file
        if self.presets_file.exists():
            try:
                with open(self.presets_file, "rb") as f:
                    data = tomli.load(f)
                
                for name, config in data.get("presets", {}).items():
                    self.presets[name] = ContextPreset(
                        name=name,
                        description=config.get("description", ""),
                        include_patterns=config.get("include", []),
                        exclude_patterns=config.get("exclude", []),
                        max_tokens=config.get("max_tokens")
                    )
            except Exception as e:
                # Non-fatal: continue with built-in presets
                pass
    
    def generate_context(self, preset_name: str) -> str:
        """
        Generate context for a preset.
        
        Args:
            preset_name: Name of the preset
            
        Returns:
            Generated context as string
            
        Raises:
            ValueError: If preset not found or context exceeds token limit
        """
        if preset_name not in self.presets:
            raise ValueError(f"Unknown preset: {preset_name}")
        
        preset = self.presets[preset_name]
        
        # Build generate_context command
        cmd = [
            "python3", "-m", "tools.generate_context",
            "--output-dir", tempfile.gettempdir(),
            "--chunk-lines", "10000",  # Large chunks for single-shot
        ]
        
        # Add include/exclude patterns
        for pattern in preset.exclude_patterns:
            cmd.extend(["--exclude", pattern])
        
        # Run from project root
        result = subprocess.run(
            cmd,
            cwd=self.project_root,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode != 0:
            raise RuntimeError(f"Context generation failed: {result.stderr}")
        
        # Read generated context (chunks)
        # For simplicity, concatenate all chunks
        output_dir = Path(tempfile.gettempdir()) / "context_reports"
        latest_dir = output_dir / "latest"
        
        context_parts = []
        if latest_dir.exists():
            for chunk_file in sorted(latest_dir.glob("chunk_*.txt")):
                with open(chunk_file) as f:
                    context_parts.append(f.read())
        
        context = "\n\n".join(context_parts)
        
        # Validate token count
        token_count = count_tokens(context)
        
        if preset.max_tokens and token_count > preset.max_tokens:
            raise ValueError(
                f"Context exceeds token limit: {token_count} > {preset.max_tokens}"
            )
        
        return context
    
    def inject_file(self, file_path: str) -> str:
        """
        Read and return file contents.
        
        Args:
            file_path: Path to file (relative to project root)
            
        Returns:
            File contents
        """
        full_path = self.project_root / file_path
        
        if not full_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        with open(full_path) as f:
            return f.read()
    
    def substitute_variables(self, template: str, variables: dict[str, str]) -> str:
        """
        Substitute variables in template.
        
        Supports:
        - {var} - Simple variable substitution
        - {@file.py} - File content injection
        - {@context:preset} - Context preset injection
        
        Args:
            template: Template string
            variables: Variable values
            
        Returns:
            Rendered template
        """
        import re
        
        result = template
        
        # 1. File injection: {@file.py}
        file_pattern = r'\{@([^}]+)\}'
        for match in re.finditer(file_pattern, template):
            file_path = match.group(1)
            
            if file_path.startswith("context:"):
                # Context preset injection
                preset_name = file_path.split(":", 1)[1]
                try:
                    content = self.generate_context(preset_name)
                    result = result.replace(match.group(0), content)
                except Exception as e:
                    raise ValueError(f"Failed to inject context:{preset_name}: {e}")
            else:
                # File injection
                try:
                    content = self.inject_file(file_path)
                    result = result.replace(match.group(0), content)
                except Exception as e:
                    raise ValueError(f"Failed to inject file {file_path}: {e}")
        
        # 2. Simple variable substitution: {var}
        var_pattern = r'\{([a-zA-Z_][a-zA-Z0-9_]*)\}'
        for match in re.finditer(var_pattern, template):
            var_name = match.group(1)
            if var_name in variables:
                result = result.replace(match.group(0), variables[var_name])
        
        return result


def count_tokens(text: str, model: str = "gpt-4") -> int:
    """
    Count tokens in text using tiktoken.
    
    Args:
        text: Text to count
        model: Model name for tokenizer
        
    Returns:
        Token count
    """
    try:
        encoding = tiktoken.encoding_for_model(model)
        return len(encoding.encode(text))
    except Exception:
        # Fallback: rough estimate (4 chars per token)
        return len(text) // 4
```

**Effort:** 4-5 hours  
**Risk:** Medium (subprocess handling, token counting)

---

❌ **2. Create Preset Config Template**

**File:** `.ai-cli-bridge/context-presets.toml.example` (NEW)

```toml
# Context preset definitions
# Copy to .ai-cli-bridge/context-presets.toml in your project root

[presets.backend]
description = "Backend code only"
include = [
    "src/daemon/**/*.py",
    "src/common/**/*.py"
]
exclude = [
    "**/__pycache__/**",
    "**/*.pyc"
]
max_tokens = 100000

[presets.frontend]
description = "Frontend UI code"
include = [
    "src/chat_ui/**/*.py",
    "assets/**/*"
]
exclude = [
    "**/__pycache__/**"
]
max_tokens = 50000

[presets.docs]
description = "Documentation only"
include = [
    "docs/**/*.md",
    "README.md",
    "*.md"
]
exclude = []
max_tokens = 30000
```

**Effort:** 30 minutes  
**Risk:** None

---

❌ **3. Integrate with Send Command**

**File:** `src/cli_bridge/commands/send_cmd.py`

**Modify run() function:**

```python
# Add at top of file
from common.context import ContextInjector

def run(
    host: str,
    port: int,
    ai_name: str,
    message: str,
    wait: bool,
    timeout: int,
    as_json: bool,
    debug: bool,
    inject: str | None = None,
    contextsize: int | None = None,
) -> int:
    """..."""
    
    # NEW: Handle context injection
    if inject:
        try:
            injector = ContextInjector()
            
            # Check if it's a preset reference
            if inject.startswith("@"):
                preset_name = inject[1:]  # Remove @ prefix
                
                if debug:
                    typer.echo(f"Generating context for preset: {preset_name}")
                
                context = injector.generate_context(preset_name)
                
                # Prepend to message
                message = f"{context}\n\n---\n\n{message}"
                
                if debug:
                    typer.echo(f"Context injected: {len(context)} chars")
            else:
                # Treat as file path
                if debug:
                    typer.echo(f"Injecting file: {inject}")
                
                content = injector.inject_file(inject)
                message = f"{content}\n\n---\n\n{message}"
                
        except Exception as e:
            typer.secho(f"✗ Context injection failed: {e}", fg=typer.colors.RED)
            return 1
    
    # Rest of existing code...
```

**Effort:** 1-2 hours  
**Risk:** Low

---

❌ **4. Update Send Command Help**

**File:** `src/cli_bridge/cli.py`

```python
@app.command("send")
def send(
    # ... existing params ...
    inject: str | None = typer.Option(
        None,
        "--inject",
        help=(
            "Inject context: @preset, @module, @project, or file path. "
            "Example: --inject @project or --inject src/main.py"
        ),
    ),
```

**Effort:** 10 minutes  
**Risk:** None

---

### Testing Checklist

- [ ] Built-in presets work (@project, @module, @cwd)
- [ ] Custom presets load from .ai-cli-bridge/context-presets.toml
- [ ] File injection works (--inject path/to/file.py)
- [ ] Context generation respects exclusions
- [ ] Token limit validation triggers error
- [ ] Large contexts don't crash
- [ ] Debug output shows context size
- [ ] Works with all AI targets

### Completion Criteria

- ✅ Context generation tool
- ❌ Context module
- ❌ Preset loading
- ❌ Variable substitution
- ❌ Send command integration
- ❌ Token validation
- ❌ Tests

**Estimated Time to Complete:** 8-10 hours

---

## Feature #4: Conversation Export

### Status: 30% Complete (Types Exist)

### Requirements

- **Format:** Simple JSON with chat metadata + messages array
- **Scope:** Single chat only
- **Command:** `chats export <ai> <chat-id>`
- **Output:** Stdout (pipe to file)
- **Import:** Not implemented (deferred)

### What's Already Implemented

✅ **Export Type** (`src/daemon/chats/types.py:19-26`)
```python
@dataclass
class ExportFormat:
    chat_id: str
    ai: str
    exported_at: str
    messages: List[Dict[str, Any]]
```

✅ **Browser Access**
- Web transport has full DOM access via Playwright
- Can scrape message elements

### Remaining Work

❌ **1. Implement Message Extraction in Transport**

**File:** `src/daemon/transport/web.py`

**Add method (around line 740):**

```python
async def export_chat(self) -> dict[str, Any]:
    """
    Export current chat messages to structured format.
    
    Returns:
        Export data with chat metadata and messages
    """
    try:
        page = await self._browser_pool.get_page()
        
        # Get current chat info
        current_chat = await self.get_current_chat()
        if not current_chat:
            raise RuntimeError("No active chat to export")
        
        # AI-specific message selectors
        # These need to be customized per AI
        message_selector = self._get_message_selector()
        
        # Extract all messages
        messages = []
        message_elements = await page.query_selector_all(message_selector)
        
        for elem in message_elements:
            try:
                # Determine role (user vs assistant)
                role = await self._extract_message_role(elem)
                
                # Extract content
                content = await elem.inner_text()
                
                # Extract timestamp if available
                timestamp = await self._extract_message_timestamp(elem)
                
                messages.append({
                    "role": role,
                    "content": content.strip(),
                    "timestamp": timestamp
                })
            except Exception as e:
                self._logger.warning(f"Failed to extract message: {e}")
                continue
        
        # Build export format
        import datetime
        export_data = {
            "chat_id": current_chat.get("chat_id"),
            "ai": self._ai_name,  # Needs to be set
            "exported_at": datetime.datetime.now().isoformat(),
            "title": current_chat.get("title"),
            "url": current_chat.get("url"),
            "message_count": len(messages),
            "messages": messages
        }
        
        return export_data
        
    except Exception as e:
        self._logger.error(f"Failed to export chat: {e}")
        raise


def _get_message_selector(self) -> str:
    """Get CSS selector for messages (override per AI)."""
    # This is AI-specific and needs customization
    # Claude example:
    return "div[data-test-render-count]"


async def _extract_message_role(self, element) -> str:
    """Determine if message is from user or assistant."""
    # Check element attributes/classes to determine role
    classes = await element.get_attribute("class") or ""
    
    if "user" in classes.lower():
        return "user"
    elif "assistant" in classes.lower() or "claude" in classes.lower():
        return "assistant"
    else:
        return "unknown"


async def _extract_message_timestamp(self, element) -> str | None:
    """Extract timestamp from message element if available."""
    try:
        time_elem = await element.query_selector("time")
        if time_elem:
            return await time_elem.get_attribute("datetime")
    except Exception:
        pass
    return None
```

**Effort:** 3-4 hours (needs per-AI customization)  
**Risk:** Medium (DOM selectors can be fragile)

---

❌ **2. Add Export Method to AI Base**

**File:** `src/daemon/ai/base.py`

```python
async def export_chat(self) -> dict[str, Any]:
    """
    Export current chat conversation.
    
    Returns:
        Export data structure
    """
    try:
        if self._transport and hasattr(self._transport, "export_chat"):
            return await self._transport.export_chat()
        return {}
    except Exception as e:
        self._logger.error(f"Export failed: {e}")
        raise
```

**Effort:** 15 minutes  
**Risk:** Low

---

❌ **3. Add Daemon Endpoint**

**File:** `src/daemon/main.py`

```python
@app.get("/chats/export", response_model=ChatsResponse)
async def export_chat(ai: str):
    """Export current chat for an AI."""
    ai_instances = daemon_state["ai_instances"]
    
    if ai not in ai_instances:
        return ChatsResponse(
            success=False,
            error=f"Unknown AI: {ai}"
        )
    
    try:
        ai_instance = ai_instances[ai]
        export_data = await ai_instance.export_chat()
        
        return ChatsResponse(
            success=True,
            chat=export_data
        )
    except Exception as e:
        logger.error(f"Failed to export chat for {ai}: {e}")
        return ChatsResponse(
            success=False,
            error=str(e)
        )
```

**Effort:** 30 minutes  
**Risk:** Low

---

❌ **4. Add CLI Command**

**File:** `src/cli_bridge/commands/chats_cmd.py`

```python
@app.command("export")
def export_chat(
    ai: str = typer.Argument(..., help="AI name (claude, chatgpt, gemini)"),
    chat_id: str = typer.Argument(
        ..., 
        help="Chat ID (use 'current' for active chat)"
    ),
    host: str = "127.0.0.1",
    port: int = 8000,
    output: str | None = typer.Option(
        None,
        "--output", "-o",
        help="Output file (default: stdout)"
    ),
):
    """Export chat conversation to JSON."""
    try:
        # If specific chat ID, switch to it first
        if chat_id != "current":
            switch_response = requests.post(
                f"http://{host}:{port}/chats/switch",
                json={"ai": ai, "identifier": chat_id},
                timeout=10
            )
            if not switch_response.json().get("success"):
                typer.secho("✗ Failed to switch to chat", fg=typer.colors.RED)
                raise typer.Exit(1)
        
        # Export
        response = requests.get(
            f"http://{host}:{port}/chats/export",
            params={"ai": ai},
            timeout=30
        )
        response.raise_for_status()
        data = response.json()
        
        if data.get("success"):
            import json
            export_json = json.dumps(data.get("chat"), indent=2)
            
            if output:
                # Write to file
                with open(output, "w") as f:
                    f.write(export_json)
                typer.secho(f"✓ Exported to {output}", fg=typer.colors.GREEN)
            else:
                # Write to stdout
                typer.echo(export_json)
        else:
            typer.secho(f"✗ Export failed: {data.get('error')}", fg=typer.colors.RED)
            raise typer.Exit(1)
            
    except requests.exceptions.ConnectionError:
        typer.secho("✗ Cannot connect to daemon", fg=typer.colors.RED)
        raise typer.Exit(DaemonNotRunning.exit_code)
```

**Effort:** 1 hour  
**Risk:** Low

---

### Testing Checklist

- [ ] Export captures all messages
- [ ] User vs assistant roles correctly identified
- [ ] Timestamps extracted when available
- [ ] Large conversations export successfully
- [ ] Output piped to file works
- [ ] JSON structure matches ExportFormat
- [ ] Works for all AIs (need per-AI selectors)
- [ ] Handles empty chats gracefully

### Completion Criteria

- ✅ Export type definition
- ❌ Message extraction implementation
- ❌ Daemon endpoint
- ❌ CLI command
- ❌ Per-AI selector customization
- ❌ Tests

**Estimated Time to Complete:** 6-8 hours (including per-AI customization)

---

## Feature #5: Prompt Templates

### Status: 10% Complete (Minimal Foundation)

### Requirements

- **Storage:** `.ai-cli-bridge/templates.toml` (project-local only)
- **Variables:**
  - `{placeholder}` - Simple substitution
  - `{@file.py}` - File content injection
  - `{@context:preset}` - Context injection
- **Usage:** `--template <name>` flag in send command

### What's Already Implemented

✅ **Send Command Parameter Stub** (`src/cli_bridge/commands/send_cmd.py:92-95`)
- `--inject` parameter exists (can be repurposed)

### Remaining Work

❌ **1. Create Templates Module**

**File:** `src/common/templates.py` (NEW)

```python
"""
Prompt template system for ai-cli-bridge.

Loads templates from .ai-cli-bridge/templates.toml and handles
variable substitution using the context injection system.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import tomli

from .context import ContextInjector


@dataclass
class Template:
    """A prompt template."""
    
    name: str
    description: str
    prompt: str
    variables: list[str]  # Required variable names
    defaults: dict[str, str]  # Default values


class TemplateManager:
    """Manages prompt templates."""
    
    def __init__(self, project_root: Path | None = None):
        """
        Initialize template manager.
        
        Args:
            project_root: Project root directory (defaults to cwd)
        """
        self.project_root = project_root or Path.cwd()
        self.templates_file = self.project_root / ".ai-cli-bridge" / "templates.toml"
        self.templates: dict[str, Template] = {}
        self.context_injector = ContextInjector(project_root)
        self._load_templates()
    
    def _load_templates(self) -> None:
        """Load templates from config file."""
        if not self.templates_file.exists():
            return
        
        try:
            with open(self.templates_file, "rb") as f:
                data = tomli.load(f)
            
            for name, config in data.get("templates", {}).items():
                self.templates[name] = Template(
                    name=name,
                    description=config.get("description", ""),
                    prompt=config.get("prompt", ""),
                    variables=config.get("variables", []),
                    defaults=config.get("defaults", {})
                )
        except Exception as e:
            raise RuntimeError(f"Failed to load templates: {e}")
    
    def get_template(self, name: str) -> Template:
        """
        Get a template by name.
        
        Args:
            name: Template name
            
        Returns:
            Template object
            
        Raises:
            KeyError: If template not found
        """
        if name not in self.templates:
            raise KeyError(f"Template not found: {name}")
        
        return self.templates[name]
    
    def list_templates(self) -> list[str]:
        """List all available template names."""
        return list(self.templates.keys())
    
    def render(
        self, 
        template_name: str, 
        variables: dict[str, str] | None = None
    ) -> str:
        """
        Render a template with variable substitution.
        
        Args:
            template_name: Name of template to render
            variables: Variable values to substitute
            
        Returns:
            Rendered prompt text
            
        Raises:
            KeyError: If template not found
            ValueError: If required variables missing or substitution fails
        """
        template = self.get_template(template_name)
        
        # Merge defaults with provided variables
        all_vars = {**template.defaults}
        if variables:
            all_vars.update(variables)
        
        # Check required variables
        missing = [v for v in template.variables if v not in all_vars]
        if missing:
            raise ValueError(f"Missing required variables: {', '.join(missing)}")
        
        # Use context injector for substitution
        try:
            rendered = self.context_injector.substitute_variables(
                template.prompt,
                all_vars
            )
            return rendered
        except Exception as e:
            raise ValueError(f"Template rendering failed: {e}")
```

**Effort:** 2-3 hours  
**Risk:** Low (builds on context module)

---

❌ **2. Create Template Config Example**

**File:** `.ai-cli-bridge/templates.toml.example` (NEW)

```toml
# Prompt template definitions
# Copy to .ai-cli-bridge/templates.toml in your project root

[templates.code-review]
description = "Code review template"
prompt = """
Please review the following code for best practices, bugs, and improvements:

{@file}

Focus on:
- {focus_area_1}
- {focus_area_2}
- {focus_area_3}

Provide specific suggestions with line numbers where applicable.
"""
variables = ["file", "focus_area_1", "focus_area_2", "focus_area_3"]

[templates.code-review.defaults]
focus_area_1 = "Error handling"
focus_area_2 = "Code clarity"
focus_area_3 = "Performance"


[templates.refactor]
description = "Refactoring request with full context"
prompt = """
I need help refactoring the following component:

{@context:module}

Target component: {component}
Goals: {goals}

Please suggest a refactored version that:
1. Maintains existing functionality
2. Improves code organization
3. Follows Python best practices
"""
variables = ["component", "goals"]

[templates.refactor.defaults]
goals = "Improve readability and maintainability"


[templates.bug-fix]
description = "Bug investigation template"
prompt = """
I'm investigating a bug in this code:

{@file}

Bug description: {bug_description}
Expected behavior: {expected}
Actual behavior: {actual}

Please help me:
1. Identify the root cause
2. Suggest a fix
3. Recommend tests to prevent regression
"""
variables = ["file", "bug_description", "expected", "actual"]


[templates.feature]
description = "New feature implementation"
prompt = """
Project context:
{@context:project}

I need to implement a new feature:

Feature: {feature_name}
Description: {feature_description}
Requirements:
{requirements}

Please provide:
1. Implementation plan
2. Code structure suggestions
3. Potential challenges to consider
"""
variables = ["feature_name", "feature_description", "requirements"]
```

**Effort:** 1 hour  
**Risk:** None

---

❌ **3. Add Template Flag to Send Command**

**File:** `src/cli_bridge/cli.py`

```python
@app.command("send")
def send(
    ai_name: str = typer.Argument(..., help="Target AI profile (e.g., 'claude')."),
    message: str = typer.Argument(
        ..., 
        help="Text to send OR template variable in key=value format when using --template."
    ),
    # ... existing params ...
    template: str | None = typer.Option(
        None,
        "--template", "-t",
        help="Template name from .ai-cli-bridge/templates.toml"
    ),
    template_var: list[str] | None = typer.Option(
        None,
        "--var", "-v",
        help="Template variable (format: key=value). Can be used multiple times."
    ),
```

**Effort:** 30 minutes  
**Risk:** Low

---

❌ **4. Integrate Templates in Send Command**

**File:** `src/cli_bridge/commands/send_cmd.py`

```python
# Add at top
from common.templates import TemplateManager

def run(
    host: str,
    port: int,
    ai_name: str,
    message: str,
    wait: bool,
    timeout: int,
    as_json: bool,
    debug: bool,
    inject: str | None = None,
    contextsize: int | None = None,
    template: str | None = None,  # NEW
    template_vars: list[str] | None = None,  # NEW
) -> int:
    """..."""
    
    # NEW: Handle template rendering
    if template:
        try:
            manager = TemplateManager()
            
            # Parse template variables
            variables = {}
            if template_vars:
                for var_str in template_vars:
                    if "=" not in var_str:
                        typer.secho(
                            f"✗ Invalid variable format: {var_str} (use key=value)",
                            fg=typer.colors.RED
                        )
                        return 1
                    
                    key, value = var_str.split("=", 1)
                    variables[key.strip()] = value.strip()
            
            if debug:
                typer.echo(f"Rendering template: {template}")
                typer.echo(f"Variables: {variables}")
            
            # Render template
            message = manager.render(template, variables)
            
            if debug:
                typer.echo(f"Rendered message ({len(message)} chars)")
                
        except KeyError as e:
            typer.secho(f"✗ Template not found: {e}", fg=typer.colors.RED)
            return 1
        except ValueError as e:
            typer.secho(f"✗ Template error: {e}", fg=typer.colors.RED)
            return 1
        except Exception as e:
            typer.secho(f"✗ Failed to render template: {e}", fg=typer.colors.RED)
            if debug:
                raise
            return 1
    
    # Existing context injection code...
    if inject:
        # ... existing code ...
    
    # Rest of function...
```

**Effort:** 1-2 hours  
**Risk:** Low

---

❌ **5. Add Template List Command**

**File:** `src/cli_bridge/cli.py`

```python
@app.command("templates")
def list_templates(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show descriptions")
):
    """List available prompt templates."""
    from common.templates import TemplateManager
    
    try:
        manager = TemplateManager()
        templates = manager.list_templates()
        
        if not templates:
            typer.echo("No templates found.")
            typer.echo("Create .ai-cli-bridge/templates.toml to define templates.")
            return
        
        typer.secho(f"Available templates ({len(templates)}):", fg=typer.colors.GREEN)
        
        for name in sorted(templates):
            if verbose:
                template = manager.get_template(name)
                typer.echo(f"\n  {name}")
                typer.echo(f"    {template.description}")
                if template.variables:
                    typer.echo(f"    Variables: {', '.join(template.variables)}")
            else:
                typer.echo(f"  - {name}")
                
    except Exception as e:
        typer.secho(f"✗ Failed to list templates: {e}", fg=typer.colors.RED)
        raise typer.Exit(1)
```

**Effort:** 30 minutes  
**Risk:** Low

---

### Usage Examples

```bash
# List templates
ai-cli-bridge templates
ai-cli-bridge templates --verbose

# Use template with variables
ai-cli-bridge send claude "Review please" \
  --template code-review \
  --var "file=src/main.py" \
  --var "focus_area_1=Error handling"

# Use template with context injection
ai-cli-bridge send claude "Help me refactor" \
  --template refactor \
  --var "component=DatabaseHandler" \
  --var "goals=Add async support"

# Template with defaults (minimal vars needed)
ai-cli-bridge send claude "Fix bug" \
  --template bug-fix \
  --var "file=src/daemon/main.py" \
  --var "bug_description=Server crashes on startup"
```

### Testing Checklist

- [ ] Templates load from .ai-cli-bridge/templates.toml
- [ ] Simple variable substitution works ({var})
- [ ] File injection works ({@file})
- [ ] Context injection works ({@context:preset})
- [ ] Default values applied
- [ ] Required variables validated
- [ ] Error messages are clear
- [ ] Template listing works
- [ ] Multiple --var flags work
- [ ] Combines with --inject if needed

### Completion Criteria

- ❌ Templates module
- ❌ Template loading
- ❌ Variable substitution
- ❌ Send command integration
- ❌ Template list command
- ❌ Example templates
- ❌ Documentation
- ❌ Tests

**Estimated Time to Complete:** 6-8 hours

---

## Implementation Priority

### Recommended Order

#### Phase 1: Complete Context Warning (High ROI, Medium Effort)
1. **Feature #1** - Refactor config to per-AI, update daemon_config.toml + CLI + GTK4 UI
   - **Time:** 3-5 hours
   - **Value:** Complete an 80% done feature with proper per-AI support
   - **Dependencies:** None
   - **Risk:** Low (refactoring existing infrastructure)

#### Phase 2: Chat Management (High Value, Foundation Exists)
2. **Feature #2** - CLI commands + Daemon endpoints
   - **Time:** 6-8 hours
   - **Value:** Core functionality users want
   - **Dependencies:** None
   - **Risk:** Medium (browser testing needed)

#### Phase 3: Context System (Enables Templates)
3. **Feature #3** - Context injection with presets
   - **Time:** 8-10 hours
   - **Value:** High for developers
   - **Dependencies:** None (but enables #5)
   - **Risk:** Medium (subprocess handling)

#### Phase 4: Templates (Builds on Context)
4. **Feature #5** - Template system
   - **Time:** 6-8 hours
   - **Value:** Power user feature
   - **Dependencies:** Feature #3 (context injection)
   - **Risk:** Low

#### Phase 5: Export (Nice-to-Have)
5. **Feature #4** - Conversation export
   - **Time:** 6-8 hours
   - **Value:** Medium (archival/analysis)
   - **Dependencies:** Feature #2 (chat management)
   - **Risk:** Medium (per-AI selectors fragile)

### Total Estimated Time
- **Minimum:** 29 hours
- **Maximum:** 39 hours
- **With testing/polish:** 42-52 hours

---

## Architecture Overview

### Current Structure
```
ai-app/
├── src/
│   ├── cli_bridge/          # Typer CLI application
│   │   ├── cli.py           # Main app + commands
│   │   ├── commands/
│   │   │   ├── daemon_cmd.py
│   │   │   ├── send_cmd.py
│   │   │   ├── status_cmd.py
│   │   │   └── chats_cmd.py      # ❌ TO ADD
│   │   ├── constants.py
│   │   └── errors.py
│   │
│   ├── daemon/              # FastAPI service
│   │   ├── main.py          # API endpoints
│   │   ├── config.py        # ⚠️ Has ContextWarningConfig (needs per-AI refactor)
│   │   ├── health.py
│   │   ├── ai/
│   │   │   ├── base.py      # ✅ Has chat methods
│   │   │   ├── factory.py
│   │   │   ├── claude.py
│   │   │   ├── chatgpt.py
│   │   │   └── gemini.py
│   │   ├── browser/
│   │   │   └── connection_pool.py
│   │   ├── chats/
│   │   │   └── types.py     # ✅ ChatInfo, ExportFormat
│   │   ├── context/         # ❌ TO ADD
│   │   │   └── types.py
│   │   ├── templates/       # ❌ TO ADD
│   │   │   └── types.py
│   │   └── transport/
│   │       ├── base.py      # ✅ Has chat method signatures
│   │       └── web.py       # ✅ Has chat implementations
│   │
│   ├── chat_ui/             # GTK4 UI
│   │   ├── main.py
│   │   ├── window.py
│   │   └── stats_display.py # ⚠️ NEEDS context warning UI
│   │
│   ├── common/              # Shared utilities
│   │   ├── paths.py
│   │   ├── context.py       # ❌ TO ADD
│   │   └── templates.py     # ❌ TO ADD
│   │
│   └── tools/
│       └── generate_context.py  # ✅ EXISTS
│
├── scripts/
│   └── generate_context    # ✅ EXISTS
│
├── runtime/
│   └── daemon/
│       └── config/
│           └── daemon_config.toml  # ⚠️ NEEDS per-AI [context_warning] sections
│
└── .ai-cli-bridge/          # ❌ TO CREATE (project-local configs)
    ├── context-presets.toml
    └── templates.toml
```

### New API Endpoints to Add
```python
# src/daemon/main.py

# Chat management
GET  /chats/list?ai=<name>           # List open chats
POST /chats/new                       # Start new chat
POST /chats/switch                    # Switch to chat
GET  /chats/export?ai=<name>         # Export current chat

# Existing endpoints (no changes needed)
GET  /health                          # Health check
GET  /status                          # Daemon status (enhance with chat info)
POST /send                            # Send prompt (enhance with templates)
```

### Configuration Files

#### Global Config: `runtime/daemon/config/daemon_config.toml`
```toml
# Per-AI context warning thresholds
[ai_profiles.claude.context_warning]
yellow_threshold = 70
orange_threshold = 85
red_threshold = 95

[ai_profiles.chatgpt.context_warning]
yellow_threshold = 60
orange_threshold = 75
red_threshold = 90

[ai_profiles.gemini.context_warning]
yellow_threshold = 80
orange_threshold = 90
red_threshold = 95
```

#### Project-Local: `.ai-cli-bridge/context-presets.toml`
```toml
[presets.backend]
description = "Backend code only"
include = ["src/daemon/**/*.py"]
exclude = ["**/__pycache__/**"]
max_tokens = 100000
```

#### Project-Local: `.ai-cli-bridge/templates.toml`
```toml
[templates.code-review]
prompt = "Review: {@file}\n\nFocus: {focus}"
variables = ["file", "focus"]
```

---

## Development Guidelines

### Code Style (from AGENTS.md)

```python
# Always use future annotations
from __future__ import annotations

# Modern type hints (not typing module)
def process(data: dict[str, Any]) -> list[str]:
    ...

# Custom exceptions with exit codes
class TemplateNotFound(CLIError):
    exit_code = 10
    
# Line length: 100 chars (ruff enforced)
```

### Testing Commands

```bash
# Install dev dependencies
make dev

# Run all tests
make test
pytest tests/ -v

# Run single test
pytest tests/test_context.py::test_preset_loading -v

# Lint and format
make check  # Runs format + lint
make lint   # Just linting
make format # Just formatting
```

### Git Workflow

```bash
# Create feature branch
git checkout -b feature/context-warning

# Make changes...

# Test
make check
make test

# Commit (follow existing message style)
git commit -m "Add context warning UI display to GTK4 stats sidebar"

# Push
git push origin feature/context-warning
```

### Error Handling Pattern

```python
# CLI commands
try:
    result = do_something()
except SomeError as e:
    typer.secho(f"✗ Operation failed: {e}", fg=typer.colors.RED)
    return 1  # Exit code

# Daemon endpoints
try:
    result = await do_something()
    return Response(success=True, data=result)
except Exception as e:
    logger.error(f"Operation failed: {e}", exc_info=True)
    return Response(success=False, error=str(e))
```

### Logging Conventions

```python
# Use module-level logger
logger = logging.getLogger(__name__)

# Log levels:
logger.debug("Detailed info for debugging")
logger.info("Important state changes")
logger.warning("Recoverable issues")
logger.error("Errors that prevent operation")
```

---

## Risk Assessment

### Low Risk Features
- ✅ Feature #1: Context Warning (config + UI)
- ✅ Feature #2: Chat Management CLI (uses existing transport)
- ✅ Feature #5: Templates (builds on proven patterns)

### Medium Risk Features
- ⚠️ Feature #3: Context Injection (subprocess handling, token counting)
- ⚠️ Feature #4: Export (DOM selectors are fragile, per-AI customization)

### High Risk Areas
- 🔴 Browser automation reliability (all features touching web transport)
- 🔴 Per-AI DOM selector maintenance (Feature #4 especially)
- 🔴 Large context handling (memory, token limits)

### Mitigation Strategies

1. **Browser Automation**
   - Extensive error handling
   - Timeout management
   - Graceful degradation

2. **DOM Selectors**
   - Abstract per-AI selectors to config
   - Version detection
   - Fallback strategies

3. **Large Contexts**
   - Stream processing where possible
   - Token limit validation before send
   - Chunking strategies

---

## Success Criteria

### Feature #1: Context Warning
- [ ] Config loads and validates thresholds
- [ ] CLI shows colored warnings at correct thresholds
- [ ] GTK4 UI shows colored warnings with icons
- [ ] Non-blocking (doesn't prevent sends)
- [ ] Works for all AI targets

### Feature #2: Chat Management
- [ ] Can create new chat for each AI
- [ ] Can list all open chats with active marker
- [ ] Can switch by ID, URL, or index
- [ ] Status shows current chat info
- [ ] Works reliably across browser sessions

### Feature #3: Context Injection
- [ ] Built-in presets work (@project, @module, @cwd)
- [ ] Custom presets load from config
- [ ] Token validation prevents oversized contexts
- [ ] Always generates fresh (no stale cache)
- [ ] Clear error messages

### Feature #4: Conversation Export
- [ ] Exports all messages with roles
- [ ] Includes timestamps when available
- [ ] Valid JSON output
- [ ] Pipes to file successfully
- [ ] Works for all AI targets

### Feature #5: Templates
- [ ] Templates load from config
- [ ] All variable types work ({var}, {@file}, {@context})
- [ ] Required variables validated
- [ ] Defaults applied correctly
- [ ] List command shows all templates
- [ ] Clear error messages

---

## Next Steps

1. **Review this plan** - Validate approach and priorities
2. **Set up .ai-cli-bridge/** - Create project-local config directory
3. **Start with Feature #1** - Quick win to build momentum
4. **Test incrementally** - Don't wait until the end
5. **Document as you go** - Update user manual with new features
6. **Get feedback early** - Test with real workflows

---

## Questions for Consideration

1. **Context Limits**: What should the default max tokens be for different presets?
2. **Chat Identification**: Should we support chat titles in addition to IDs/URLs?
3. **Export Format**: Do we need multiple export formats (JSON, Markdown, etc.)?
4. **Template Inheritance**: Should templates support extending other templates?
5. **Error Recovery**: How should we handle browser disconnects during operations?

---

**Document Version:** 1.0  
**Last Updated:** November 4, 2025  
**Next Review:** After completing Phase 1 (Feature #1)
