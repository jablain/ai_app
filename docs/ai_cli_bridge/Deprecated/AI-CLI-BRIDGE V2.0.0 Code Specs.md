
# AI-CLI-Bridge v2.0.0

## Software Engineering Implementation Document

**Version:** 2.0.0
**Release Date:** October 18, 2025
**Status:** Production Implementation
**Document Classification:** Technical Implementation Specification

---

## Executive Summary

This document provides detailed implementation specifications for AI-CLI-Bridge v2.0.0, complementing the Architecture Design Document with concrete technical details including software stack, dependencies, build process, deployment procedures, testing strategies, and internal implementation patterns. This document is intended for software engineers implementing, maintaining, or extending the system.

**Scope**: This document covers implementation details NOT included in the architecture document:

- Complete software stack and dependency specifications
- Build and deployment procedures
- Internal implementation patterns and idioms
- Code organization and module responsibilities
- Testing infrastructure and strategies
- Performance tuning and optimization techniques
- Debugging and development workflows

---

---

## 1. Software Stack Specification

### 1.1 Core Runtime Environment

#### 1.1.1 Python Version

**Required**: Python 3.10 or higher
**Tested**: Python 3.10.12, 3.11.5, 3.12.0
**Recommended**: Python 3.10.12 (LTS)

**Rationale for 3.10+**:

- **Type Hints**: Support for `|` union syntax (`str | None` vs `Union[str, None]`)
- **Pattern Matching**: `match` statement for cleaner conditional logic (future use)
- **Performance**: 10-15% faster than 3.9 due to optimizations
- **asyncio**: Improved async exception handling and task groups

**Version Check**:

```python
# In cli.py or main entry points
import sys
if sys.version_info < (3, 10):
    print("Error: Python 3.10 or higher required")
    sys.exit(1)
```

#### 1.1.2 Operating System Support

**Supported Platforms**:

- **Linux**: Ubuntu 20.04+, Debian 11+, Fedora 35+, Arch Linux (primary target)
- **macOS**: macOS 11 (Big Sur) or higher (secondary target)
- **Windows**: Windows 10/11 with WSL2 (experimental, limited support)

**Platform-Specific Considerations**:

**Linux**:

- Native Chromium support (optimal performance)
- Standard POSIX signal handling
- systemd integration available (daemon management)

**macOS**:

- Uses bundled Chromium from Playwright
- Requires Xcode Command Line Tools
- Process management via launchd (optional)

**Windows/WSL2**:

- Requires WSL2 (not WSL1)
- X11 server needed for browser display (VcXsrv, X410)
- Some performance overhead vs native Linux

### 1.2 Core Dependencies

#### 1.2.1 Web Framework: FastAPI

**Version**: 0.104.1
**Purpose**: HTTP server for daemon REST API
**Why FastAPI**:

- **Performance**: Built on Starlette and Uvicorn (async ASGI)
- **Type Safety**: Automatic validation via Pydantic
- **Auto-Documentation**: OpenAPI/Swagger generation
- **Async Native**: First-class async/await support
- **Minimal Overhead**: Lightweight, no bloat

**Installation**:

```bash
pip install fastapi==0.104.1
```

**Key Features Used**:

- **Lifespan Events**: `@asynccontextmanager` for startup/shutdown
- **Path Parameters**: `/session/new/{ai_name}`
- **Request Body Validation**: Automatic via type hints
- **Exception Handlers**: Custom error responses

#### 1.2.2 ASGI Server: Uvicorn

**Version**: 0.24.0
**Purpose**: Production ASGI server for FastAPI
**Why Uvicorn**:

- **Fast**: Written in Cython, optimized for async I/O
- **Stable**: Production-grade, widely used
- **Simple**: Minimal configuration required
- **Reload**: Auto-reload during development

**Installation**:

```bash
pip install uvicorn==0.24.0
```

**Production Configuration**:

```python
uvicorn.run(
    "ai_cli_bridge.daemon.main:app",
    host="127.0.0.1",
    port=8000,
    log_level="info",
    access_log=False  # Disable access logs (performance)
)
```

#### 1.2.3 Browser Automation: Playwright

**Version**: 1.40.0
**Purpose**: CDP browser control and automation
**Why Playwright**:

- **Modern**: Actively developed by Microsoft
- **Cross-Browser**: Chromium, Firefox, WebKit support
- **Async Native**: Built for async/await from ground up
- **Selector Engine**: Robust, resilient selectors
- **CDP Protocol**: First-class Chrome DevTools Protocol support

**Installation**:

```bash
pip install playwright==1.40.0
playwright install chromium  # Downloads bundled Chromium
```

**Bundled Chromium Version**: 1140 (119.0.6045.9)

**Key Features Used**:

- **CDP Connection**: `playwright.chromium.connect_over_cdp()`
- **Page Interaction**: `page.fill()`, `page.keyboard.press()`
- **Selector Waiting**: `page.wait_for_selector()`
- **DOM Queries**: `page.query_selector()`, `page.locator()`
- **Content Extraction**: `element.inner_html()`, `element.inner_text()`

#### 1.2.4 CLI Framework: Typer

**Version**: 0.9.0
**Purpose**: Command-line interface parsing and help generation
**Why Typer**:

- **Type-Based**: Uses type hints for validation
- **Auto Help**: Generates `--help` from docstrings
- **Rich Output**: Built-in support for colored output (via Rich)
- **Minimal Boilerplate**: Decorator-based API

**Installation**:

```bash
pip install typer==0.9.0
```

**Example Pattern**:

```python
import typer
app = typer.Typer()

@app.command()
def send(
    ai_name: str = typer.Argument(..., help="AI to target"),
    message: str = typer.Argument(..., help="Message to send"),
    wait: bool = typer.Option(True, "--wait/--no-wait")
):
    """Send message to AI."""
    # Implementation
```

#### 1.2.5 HTTP Client: Requests

**Version**: 2.31.0
**Purpose**: HTTP client for CLI → daemon communication
**Why Requests**:

- **Ubiquitous**: De facto standard Python HTTP library
- **Simple**: Intuitive API, minimal learning curve
- **Reliable**: Battle-tested, mature
- **Synchronous**: Matches CLI's blocking nature

**Installation**:

```bash
pip install requests==2.31.0
```

**Usage Pattern**:

```python
response = requests.post(
    "http://127.0.0.1:8000/send",
    json={"target": ai_name, "prompt": message},
    timeout=timeout_s + 5  # Add buffer for HTTP overhead
)
```

#### 1.2.6 Markdown Conversion: markdownify

**Version**: 0.11.6
**Purpose**: HTML to Markdown conversion
**Why markdownify**:

- **Clean Output**: Better than html2text for AI responses
- **Customizable**: Control heading style, bullet format
- **Lightweight**: No heavy dependencies

**Installation**:

```bash
pip install markdownify==0.11.6
```

**Usage**:

```python
import markdownify
markdown = markdownify.markdownify(html, heading_style="ATX")
# ATX style: # Heading vs Setext style: Heading\n========
```

#### 1.2.7 Configuration Parsing: tomli

**Version**: 2.0.1
**Purpose**: TOML configuration file parsing
**Why tomli**:

- **Standard**: Pure Python TOML 1.0.0 implementation
- **Fast**: C implementation available (tomli-w for writing)
- **Bundled**: Included in Python 3.11+ as `tomllib`

**Installation**:

```bash
pip install tomli==2.0.1  # Python 3.10
# Python 3.11+: use built-in tomllib
```

**Usage**:

```python
import tomli
with open("config.toml", "rb") as f:
    config = tomli.load(f)
```

### 1.3 Development Dependencies

#### 1.3.1 Code Quality Tools

**Black** (Code Formatter):

```bash
pip install black==23.11.0
black src/ --line-length 100
```

**isort** (Import Sorter):

```bash
pip install isort==5.12.0
isort src/ --profile black
```

**flake8** (Linter):

```bash
pip install flake8==6.1.0
flake8 src/ --max-line-length 100
```

**mypy** (Type Checker):

```bash
pip install mypy==1.7.0
mypy src/ --strict
```

#### 1.3.2 Testing Tools (Future)

**pytest**:

```bash
pip install pytest==7.4.3
pip install pytest-asyncio==0.21.1  # Async test support
pip install pytest-cov==4.1.0       # Coverage reporting
```

**pytest-playwright**:

```bash
pip install pytest-playwright==0.4.3
```

### 1.4 Runtime Dependencies Summary

**Complete `requirements.txt`**:

```
# Core runtime
fastapi==0.104.1
uvicorn==0.24.0
playwright==1.40.0
typer==0.9.0
requests==2.31.0
markdownify==0.11.6
tomli==2.0.1  # Python 3.10 only

# Transitive dependencies (auto-installed)
starlette==0.27.0
pydantic==2.5.0
click==8.1.7
certifi==2023.7.22
charset-normalizer==3.3.2
idna==3.4
urllib3==2.1.0
soupsieve==2.5
beautifulsoup4==4.12.2
greenlet==3.0.1
pyee==11.0.1
```

**Total Dependency Size**: ~150 MB (including Playwright Chromium)

---

## 2. Dependency Management

### 2.1 Virtual Environment Strategy

#### 2.1.1 Shared Virtual Environment

**Location**: `~/dev/ai_app/shared/runtime/venv/`

**Rationale**:

- Multiple projects share single venv (disk space efficiency)
- Centralized dependency management
- Consistent Python version across projects

**Creation**:

```bash
python3.10 -m venv ~/dev/ai_app/shared/runtime/venv
```

**Activation Script**: `~/dev/ai_app/shared/scripts/activate.sh`

```bash
#!/bin/bash
# Activate shared virtual environment

VENV_PATH="$HOME/dev/ai_app/shared/runtime/venv"

if [ ! -d "$VENV_PATH" ]; then
    echo "Error: Virtual environment not found at $VENV_PATH"
    exit 1
fi

source "$VENV_PATH/bin/activate"

echo "✓ Activated shared venv"
echo "  ai-cli-bridge: $(which ai-cli-bridge)"
echo "  ai-chat-ui:    $(which ai-chat-ui)"
```

### 2.2 Dependency Pinning Strategy

#### 2.2.1 Version Pinning Philosophy

**Strategy**: Pin major + minor versions, allow patch updates

**Example**:

```
fastapi==0.104.1   # Pin exact (critical dependency)
requests~=2.31.0   # Allow 2.31.x patches
playwright>=1.40.0,<2.0.0  # Pin major version
```

**Rationale**:

- **Exact Pins** (==): For critical dependencies where behavior must be consistent
- **Compatible Release** (~=): Allow patch updates (bug fixes) but not minor version changes
- **Range** (>=,<): For flexible dependencies where breaking changes unlikely

#### 2.2.2 Dependency Update Process

**Check for Updates**:

```bash
pip list --outdated
```

**Update Procedure**:

1. Review changelog for breaking changes
2. Update in development environment
3. Run full test suite
4. Update `requirements.txt`
5. Test in staging
6. Deploy to production

**Security Updates**:

```bash
# Check for known vulnerabilities
pip-audit
# Or
safety check
```

### 2.3 Installation Methods

#### 2.3.1 Editable Install (Development)

**Command**:

```bash
cd ~/dev/ai_app/ai-cli-bridge
pip install -e .
```

**What Happens**:

- Creates symlink from venv to source directory
- Changes to source code immediately reflected
- No reinstall needed during development
- Executable created in venv `bin/`

**Verification**:

```bash
which ai-cli-bridge
# Output: /home/user/dev/ai_app/shared/runtime/venv/bin/ai-cli-bridge

python -c "import ai_cli_bridge; print(ai_cli_bridge.__file__)"
# Output: /home/user/dev/ai_app/ai-cli-bridge/src/ai_cli_bridge/__init__.py
```

#### 2.3.2 Standard Install (Production)

**Command**:

```bash
pip install .
# Or from wheel:
pip install ai_cli_bridge-2.0.0-py3-none-any.whl
```

**What Happens**:

- Copies source to venv `lib/python3.10/site-packages/`
- Creates frozen installation
- Changes to source require reinstall

### 2.4 Dependency Isolation

#### 2.4.1 No Global Dependencies

**Principle**: Never use system Python packages

**Verification**:

```bash
# Should be empty or minimal
pip list --user

# Always activate venv first
source ~/dev/ai_app/shared/scripts/activate.sh
```

#### 2.4.2 Playwright Browser Isolation

**Playwright Browsers**: Downloaded to user cache, NOT in venv

**Location**:

```bash
~/.cache/ms-playwright/chromium-1140/
```

**Rationale**: Browsers are large (~200MB), shared across Python environments

**Manual Management**:

```bash
# List installed browsers
playwright install --help

# Remove all browsers
rm -rf ~/.cache/ms-playwright/

# Reinstall
playwright install chromium
```

---

## 3. Build System & Packaging

### 3.1 Project Metadata: pyproject.toml

**Complete File**:

```toml
[project]
name = "ai-cli-bridge"
version = "2.0.0"
description = "CLI interface for browser-based AI assistants via CDP"
readme = "README.md"
requires-python = ">=3.10"
license = {text = "MIT"}
authors = [
    {name = "Your Name", email = "your.email@example.com"}
]
keywords = ["ai", "cli", "automation", "claude", "gemini", "chatgpt"]
classifiers = [
    "Development Status :: 4 - Beta",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Topic :: Software Development :: Libraries :: Python Modules",
]

dependencies = [
    "fastapi==0.104.1",
    "uvicorn==0.24.0",
    "playwright==1.40.0",
    "typer==0.9.0",
    "requests==2.31.0",
    "markdownify==0.11.6",
    "tomli==2.0.1; python_version < '3.11'",
]

[project.optional-dependencies]
dev = [
    "black==23.11.0",
    "isort==5.12.0",
    "flake8==6.1.0",
    "mypy==1.7.0",
]
test = [
    "pytest==7.4.3",
    "pytest-asyncio==0.21.1",
    "pytest-cov==4.1.0",
    "pytest-playwright==0.4.3",
]

[project.scripts]
ai-cli-bridge = "ai_cli_bridge.cli:main"

[project.urls]
Homepage = "https://github.com/your-org/ai-cli-bridge"
Documentation = "https://docs.ai-cli-bridge.io"
Repository = "https://github.com/your-org/ai-cli-bridge"
"Bug Tracker" = "https://github.com/your-org/ai-cli-bridge/issues"

[build-system]
requires = ["setuptools>=65.0", "wheel"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]

[tool.black]
line-length = 100
target-version = ['py310']
include = '\.pyi?$'
extend-exclude = '''
/(
  # directories
  \.eggs
  | \.git
  | \.venv
  | build
  | dist
)/
'''

[tool.isort]
profile = "black"
line_length = 100
src_paths = ["src", "tests"]

[tool.mypy]
python_version = "3.10"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
disallow_incomplete_defs = true
check_untyped_defs = true
no_implicit_optional = true
warn_redundant_casts = true
warn_unused_ignores = true
warn_no_return = true
follow_imports = "normal"
strict_optional = true

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
addopts = "-v --tb=short --strict-markers"
markers = [
    "slow: marks tests as slow (deselect with '-m \"not slow\"')",
    "integration: marks tests as integration tests",
]
```

### 3.2 Package Building

#### 3.2.1 Build Distribution Package

**Install Build Tools**:

```bash
pip install build
```

**Build**:

```bash
cd ~/dev/ai_app/ai-cli-bridge
python -m build
```

**Output**:

```
dist/
├── ai_cli_bridge-2.0.0-py3-none-any.whl  # Wheel (preferred)
└── ai_cli_bridge-2.0.0.tar.gz            # Source distribution
```

#### 3.2.2 Wheel Structure

**Contents of .whl** (unzipped):

```
ai_cli_bridge-2.0.0.dist-info/
├── METADATA
├── WHEEL
├── top_level.txt
├── entry_points.txt
└── RECORD

ai_cli_bridge/
├── __init__.py
├── cli.py
├── daemon/
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   ├── daemon_cmd.py
│   └── process_manager.py
├── ai/
│   ├── __init__.py
│   ├── base.py
│   ├── web_base.py
│   ├── factory.py
│   ├── claude.py
│   ├── gemini.py
│   └── chatgpt.py
└── commands/
    ├── __init__.py
    ├── send_cmd.py
    ├── status_cmd.py
    ├── doctor_cmd.py
    ├── open_cmd.py
    ├── init_cmd.py
    └── init_cdp_cmd.py
```

### 3.3 Entry Point Generation

**Entry Point Specification** (in pyproject.toml):

```toml
[project.scripts]
ai-cli-bridge = "ai_cli_bridge.cli:main"
```

**Generated Executable** (`venv/bin/ai-cli-bridge`):

```python
#!/home/user/dev/ai_app/shared/runtime/venv/bin/python3.10
# -*- coding: utf-8 -*-
import re
import sys
from ai_cli_bridge.cli import main

if __name__ == '__main__':
    sys.argv[0] = re.sub(r'(-script\.pyw|\.exe)?$', '', sys.argv[0])
    sys.exit(main())
```

---

## 4. Code Organization & Patterns

### 4.1 Module Responsibilities

#### 4.1.1 `cli.py`: CLI Entry Point

**Responsibility**: Command registration and routing

**Key Functions**:

- Register Typer commands
- Parse command-line arguments
- Route to command implementations
- Handle top-level exceptions

**Pattern**:

```python
import typer
from .commands import send_cmd, status_cmd, ...
from .daemon import daemon_cmd

app = typer.Typer(no_args_is_help=True)
app.add_typer(daemon_cmd.app, name="daemon")

@app.command("send")
def send(...):
    raise typer.Exit(send_cmd.run(...))

def main():
    app()
```

**Design Decision**: Commands in separate modules for testability and separation of concerns

#### 4.1.2 `daemon/main.py`: Daemon Core

**Responsibility**: FastAPI application, lifespan management, request handling

**Key Components**:

```python
# State management
daemon_state = {
    "ai_instances": {},
    "locks": {},
    "browser_pid": None
}

# Lifespan hook
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic
    yield
    # Shutdown logic

# API endpoints
@app.get("/status")
@app.post("/send")
@app.post("/session/new/{ai_name}")
```

**Thread Safety**: Uses asyncio locks, not threading locks (async/await model)

#### 4.1.3 `ai/base.py`: AI Base Class

**Responsibility**: Core AI interaction protocol, state tracking

**Key Methods**:

```python
async def send_prompt(): # Template method
async def get_status():  # State reporting
def reset_session_state():  # State management

# Abstract methods (subclass implements)
async def _execute_interaction():
async def list_messages():
async def extract_message():
```

**Pattern**: Template Method Pattern

- `send_prompt()` defines algorithm skeleton
- Subclasses override `_execute_interaction()` for specifics

#### 4.1.4 `ai/web_base.py`: Web AI Base

**Responsibility**: Stop-button pattern implementation

**Key Methods**:

```python
async def _execute_interaction():  # Concrete implementation
async def _wait_for_response_complete():  # Stop-button logic
async def _extract_response():  # Markdown extraction
async def _send_message():  # Input box interaction
```

**Design**: Single Responsibility - all stop-button AIs share this

#### 4.1.5 `ai/{claude,gemini,chatgpt}.py`: Concrete AIs

**Responsibility**: Selectors and AI-specific quirks only

**Structure**:

```python
class ClaudeAI(WebAIBase):
    # Configuration
    BASE_URL = "https://claude.ai"

    # Selectors (properties)
    @property
    def INPUT_BOX(self) -> str:
        return "div[contenteditable='true']"

    # Overrides (only if needed)
    async def _ensure_chat_ready(self, page):
        # Custom logic
```

**Line Count Goal**: <100 lines per AI (achieved: Claude 60, Gemini 60, ChatGPT 90)

#### 4.1.6 `ai/factory.py`: Factory Pattern

**Responsibility**: AI registration and instantiation

**Pattern**: Registry Pattern

```python
class AIFactory:
    _registry: Dict[str, type[BaseAI]] = {}

    @classmethod
    def register(cls, ai_name, ai_class):
        cls._registry[ai_name.lower()] = ai_class

    @classmethod
    def create(cls, ai_name, config) -> BaseAI:
        return cls._registry[ai_name]
```

**Auto-Registration**: Each AI module calls `AIFactory.register()` at module level

#### 4.1.7 `daemon/config.py`: Configuration Management

**Responsibility**: Load, merge, and provide configuration

**Key Functions**:

python

```python
PROJECT_ROOT = pathlib.Path(__file__).parent.parent.parent.resolve()
RUNTIME_DIR = PROJECT_ROOT / "runtime"

def load_config() -> Dict[str, Any]:
    config = DEFAULT_CONFIG.copy()
    if CONFIG_FILE.exists():
        loaded = tomli.load(CONFIG_FILE.open("rb"))
        # Deep merge
    return config
```

**Pattern**: Default-first with override

#### 4.1.8 `commands/*.py`: Command Implementations

**Responsibility**: Execute specific CLI commands

**Signature Pattern**:

python

```python
def run(arg1: type1, arg2: type2, ...) -> int:
    """
    Execute command.

    Returns:
        0 on success, 1 on error
    """
    try:
        # Implementation
        return 0
    except Exception as e:
        print(f"✗ Error: {e}")
        return 1
```

**Design**: Pure functions with clear inputs/outputs (testable)
