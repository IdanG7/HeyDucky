.PHONY: install test lint fmt check build publish publish-test clean setup run help

PYTHON ?= python3

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

install: ## Install in editable mode with all extras
	$(PYTHON) -m pip install -e ".[tts,dev]"

test: ## Run test suite
	$(PYTHON) -m pytest tests/ -v

lint: ## Run ruff linter
	$(PYTHON) -m ruff check heyducky/ tests/

fmt: ## Auto-format with ruff
	$(PYTHON) -m ruff format heyducky/ tests/
	$(PYTHON) -m ruff check --fix heyducky/ tests/

check: lint ## Run all checks (lint + format check + tests)
	$(PYTHON) -m ruff format --check heyducky/ tests/
	$(PYTHON) -m pytest tests/ -v

build: clean ## Build wheel and sdist for PyPI
	$(PYTHON) -m build

publish: build ## Upload to PyPI (requires twine + PyPI token)
	$(PYTHON) -m twine upload dist/*

publish-test: build ## Upload to TestPyPI
	$(PYTHON) -m twine upload --repository testpypi dist/*

clean: ## Remove build artifacts
	rm -rf dist/ build/ *.egg-info heyducky/*.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name '*.pyc' -delete 2>/dev/null || true

setup: ## Run the first-time setup wizard
	ducky --setup

run: ## Launch ducky
	ducky
