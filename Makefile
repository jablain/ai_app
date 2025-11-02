.PHONY: install dev test clean lint format check all

install:
	pip install -e .

dev:
	pip install -e ".[dev]"

test:
	pytest tests/ -v

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	rm -rf dist/ build/ .pytest_cache/ .ruff_cache/ .mypy_cache/

lint:
	@echo "🔍 Linting code..."
	ruff check src/

format:
	@echo "✨ Formatting code..."
	ruff format src/

check: format lint
	@echo "✅ All checks passed! Ready to commit."

all: clean check test
