# Developer shortcuts. Requires GNU make (on Windows: Git Bash + `choco install make`,
# or run the underlying commands directly — each target is a single command).

PYTHON ?= python

.PHONY: help install install-dev test lint format format-check check clean

help:
	@echo "Targets:"
	@echo "  install       Install the package in editable mode"
	@echo "  install-dev   Install the package with development tools (pytest, ruff)"
	@echo "  test          Run the test suite"
	@echo "  lint          Run Ruff lint checks"
	@echo "  format        Auto-format code with Ruff"
	@echo "  format-check  Verify formatting without modifying files"
	@echo "  check         lint + format-check + test (what CI runs)"
	@echo "  clean         Remove caches and build artifacts"

install:
	$(PYTHON) -m pip install -e .

install-dev:
	$(PYTHON) -m pip install -e ".[dev]"

test:
	$(PYTHON) -m pytest

lint:
	$(PYTHON) -m ruff check .

format:
	$(PYTHON) -m ruff format .
	$(PYTHON) -m ruff check --fix .

format-check:
	$(PYTHON) -m ruff format --check .

check: lint format-check test

clean:
	$(PYTHON) -c "import pathlib, shutil; [shutil.rmtree(p, ignore_errors=True) for pat in ('**/__pycache__', '.pytest_cache', '.ruff_cache', 'build', 'dist', '**/*.egg-info') for p in pathlib.Path('.').glob(pat)]"
