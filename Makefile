# repo-sapiens Makefile
# Convenient commands for development

.PHONY: help install dev test test-unit test-integration lint format type-check \
        pre-commit clean build docker-build docker-run repl

# Default target
help:
	@echo "repo-sapiens development commands:"
	@echo ""
	@echo "  make install        Install production dependencies"
	@echo "  make dev            Install development dependencies"
	@echo "  make test           Run all tests"
	@echo "  make test-unit      Run unit tests only"
	@echo "  make test-cov       Run tests with coverage report"
	@echo "  make lint           Run linters (ruff)"
	@echo "  make format         Format code (ruff)"
	@echo "  make type-check     Run type checker (mypy)"
	@echo "  make pre-commit     Run all pre-commit hooks"
	@echo "  make clean          Clean build artifacts"
	@echo "  make build          Build package"
	@echo "  make docker-build   Build Docker image"
	@echo "  make docker-run     Run Docker container"
	@echo "  make repl           Start ReAct agent REPL"
	@echo ""

# Installation
install:
	uv sync --no-dev

dev:
	uv sync

# Testing
test:
	uv run pytest tests/ -v

test-unit:
	uv run pytest tests/unit/ -v

test-integration:
	uv run pytest tests/integration/ -v

test-cov:
	uv run pytest tests/ --cov=repo_sapiens --cov-report=html --cov-report=term

test-fast:
	uv run pytest tests/unit/ -q --tb=short

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
