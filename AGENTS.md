# Agent Guidelines for ai-app

## Build & Test Commands
- **Install dev**: `make dev` or `pip install -e ".[dev]"`
- **Run tests**: `pytest tests/ -v` or `make test`
- **Single test**: `pytest tests/test_file.py::test_function -v`
- **Lint**: `ruff check src/` or `make lint`
- **Format**: `ruff format src/` or `make format`
- **Full check**: `make check` (format + lint)

## Code Style
- **Python**: 3.10+, line length 100 chars (ruff enforced)
- **Imports**: Use `from __future__ import annotations`; standard lib → third-party → local; ruff sorts (isort)
- **Types**: Use type hints; prefer modern syntax (`dict[str, Any]` not `Dict[str, Any]`)
- **Naming**: snake_case for functions/variables, PascalCase for classes, UPPER_CASE for constants
- **Docstrings**: Use for public APIs/modules; keep concise
- **Error handling**: Custom exceptions in `*.errors` modules (inherit from base errors); set exit_codes where applicable

## Project Structure
- **src/**: `cli_bridge/` (Typer CLI), `daemon/` (FastAPI service), `chat_ui/` (GTK4 UI), `common/` (shared), `tools/` (utilities)
- **Entry points**: `ai-cli-bridge`, `ai-daemon`, `ai-chat-ui` (defined in pyproject.toml)
- **Config**: daemon.config.load_config() for settings; avoid hardcoded paths

## Key Patterns
- FastAPI uses Pydantic models (see daemon/main.py)
- Browser automation via Playwright CDP (daemon/browser/connection_pool.py)
- AI providers abstracted via factory pattern (daemon/ai/factory.py)
