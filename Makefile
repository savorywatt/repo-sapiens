# repo-sapiens Makefile
# Convenient commands for development

.PHONY: help install dev test test-unit test-integration lint format type-check \
        pre-commit clean build docker-build docker-run repl docs docs-serve

# Default target
help:
	@echo "repo-sapiens development commands:"
	@echo ""
	@echo "  make install        Install production dependencies"
	@echo "  make dev            Install development dependencies"
	@echo "  make test           Run all tests (parallel)"
	@echo "  make test-unit      Run unit tests (parallel)"
	@echo "  make test-cov       Run tests with coverage (sequential)"
	@echo "  make test-verbose   Run tests with verbose output"
	@echo "  make lint           Run linters (ruff)"
	@echo "  make format         Format code (ruff)"
	@echo "  make type-check     Run type checker (mypy)"
	@echo "  make pre-commit     Run all pre-commit hooks"
	@echo "  make clean          Clean build artifacts"
	@echo "  make build          Build package"
	@echo "  make docker-build   Build Docker image"
	@echo "  make docker-run     Run Docker container"
	@echo "  make repl           Start ReAct agent REPL"
	@echo "  make docs           Build documentation"
	@echo "  make docs-serve     Build and serve docs with live reload"
	@echo ""

# Installation
install:
	uv sync --no-dev

dev:
	uv sync

# Testing (parallel by default via pyproject.toml: -n auto)
test:
	uv run pytest tests/

test-unit:
	uv run pytest tests/unit/

test-integration:
	uv run pytest tests/integration/ -n 0

# Coverage requires sequential execution for accurate results
test-cov:
	uv run pytest tests/ -n 0 --cov=repo_sapiens --cov-report=html --cov-report=term-missing --cov-fail-under=10

# Verbose output for debugging
test-verbose:
	uv run pytest tests/unit/ -n 0 -v --tb=short

# Code quality
lint:
	uv run ruff check repo_sapiens/ tests/

format:
	uv run ruff format repo_sapiens/ tests/
	uv run ruff check --fix repo_sapiens/ tests/

type-check:
	uv run mypy repo_sapiens/

pre-commit:
	uv run pre-commit run --all-files

# Cleaning
clean:
	rm -rf build/ dist/ *.egg-info/ .pytest_cache/ .mypy_cache/ .ruff_cache/
	rm -rf htmlcov/ .coverage coverage.xml
	rm -rf docs/build/ docs/source/api/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true

# Building
build: clean
	uv build

# Docker
docker-build:
	docker build -t repo-sapiens:latest .

docker-run:
	docker run --rm -it repo-sapiens:latest --help

# Development shortcuts
repl:
	uv run sapiens react --repl

run:
	uv run sapiens --help

# Health check
health:
	uv run sapiens health-check

# Documentation
docs:
	uv run sphinx-apidoc -f -o docs/source/api repo_sapiens
	uv run sphinx-build docs/source docs/build/html
	@echo "Documentation built in docs/build/html/"

docs-serve:
	uv run sphinx-apidoc -f -o docs/source/api repo_sapiens
	uv run sphinx-autobuild docs/source docs/build/html
