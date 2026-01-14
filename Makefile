# repo-sapiens Makefile
# Convenient commands for development

.PHONY: help install dev test test-unit test-integration lint format type-check \
        pre-commit clean build docker-build docker-run repl docs docs-serve \
        validate-quick validate-gitea validate-gitlab validate-full \
        infra-up infra-down infra-gitlab bootstrap-gitea bootstrap-gitea-full

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
	@echo "Validation:"
	@echo "  make validate-quick   Run quick validation (unit tests + config)"
	@echo "  make validate-gitea   Run Gitea E2E validation (needs SAPIENS_GITEA_TOKEN)"
	@echo "  make validate-gitlab  Run GitLab E2E validation (needs GITLAB_TOKEN)"
	@echo "  make validate-full    Run full validation suite"
	@echo ""
	@echo "Infrastructure:"
	@echo "  make infra-up              Start Gitea container"
	@echo "  make bootstrap-gitea       Start Gitea + auto-configure for testing"
	@echo "  make bootstrap-gitea-full  Same as above + Actions runner for CI/CD"
	@echo "  make infra-down            Stop all test infrastructure"
	@echo "  make infra-gitlab          Start GitLab (resource-intensive, ~5 min)"
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

# Coverage with parallel execution (pytest-cov handles xdist automatically)
test-cov:
	uv run pytest tests/ -n 4 --cov=repo_sapiens --cov-report=html --cov-report=term-missing --cov-fail-under=10

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
	uv run sapiens task --repl

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

# =============================================================================
# Validation targets
# =============================================================================

# Quick validation (unit tests + local config check)
validate-quick:
	@echo "Running quick validation..."
	uv run pytest tests/unit/test_providers_*.py -v --tb=short
	@if [ -f .sapiens/config.yaml ]; then \
		uv run sapiens health-check --config .sapiens/config.yaml --skip-connectivity; \
	fi
	@echo "Quick validation complete."

# Gitea-focused E2E validation
# Use: make validate-gitea (requires SAPIENS_GITEA_TOKEN)
#  or: make validate-gitea BOOTSTRAP=1 (auto-configures Gitea)
validate-gitea:
	@echo "Running Gitea E2E validation..."
	@if [ -n "$(BOOTSTRAP)" ]; then \
		./scripts/run-gitea-e2e.sh --bootstrap; \
	elif [ -z "$$SAPIENS_GITEA_TOKEN" ]; then \
		echo "Error: SAPIENS_GITEA_TOKEN not set"; \
		echo "Either set the token or run: make validate-gitea BOOTSTRAP=1"; \
		exit 1; \
	else \
		./scripts/run-gitea-e2e.sh; \
	fi
	@echo "Gitea validation complete."

# GitLab-focused E2E validation
validate-gitlab:
	@echo "Running GitLab E2E validation..."
	@if [ -z "$$GITLAB_TOKEN" ]; then \
		echo "Error: GITLAB_TOKEN not set"; exit 1; \
	fi
	./scripts/run-gitlab-e2e.sh
	@echo "GitLab validation complete."

# Full validation suite (all providers)
validate-full:
	@echo "Running full validation suite..."
	./scripts/run-validation.sh
	@echo "Full validation complete."

# Start Gitea container only (needs manual setup or bootstrap)
infra-up:
	docker compose -f plans/validation/docker/gitea.yaml up -d gitea
	@echo "Waiting for Gitea container..."
	@timeout=60; elapsed=0; \
	while ! curl -sf http://localhost:3000/api/healthz > /dev/null 2>&1; do \
		sleep 2; elapsed=$$((elapsed + 2)); \
		if [ $$elapsed -ge $$timeout ]; then echo "Timeout waiting for Gitea"; exit 1; fi; \
	done
	@echo "Gitea container ready at http://localhost:3000"
	@echo "Run 'make bootstrap-gitea' to auto-configure for testing"

# Bootstrap Gitea for testing (starts container + configures user/token/repo)
bootstrap-gitea:
	@echo "Bootstrapping Gitea for testing..."
	@# Start container if not running
	@if ! curl -sf http://localhost:3000/api/healthz > /dev/null 2>&1; then \
		$(MAKE) infra-up; \
	fi
	@# Run bootstrap script
	./scripts/bootstrap-gitea.sh --url http://localhost:3000 --output .env.gitea-test
	@echo ""
	@echo "Gitea is ready! To use:"
	@echo "  source .env.gitea-test"
	@echo "  make validate-gitea"

# Bootstrap Gitea with Actions runner for full CI/CD testing
bootstrap-gitea-full:
	@echo "Bootstrapping Gitea with Actions runner..."
	@# Start container if not running
	@if ! curl -sf http://localhost:3000/api/healthz > /dev/null 2>&1; then \
		$(MAKE) infra-up; \
	fi
	@# Run bootstrap script with runner
	./scripts/bootstrap-gitea.sh --url http://localhost:3000 --output .env.gitea-test --with-runner
	@echo ""
	@echo "Gitea + Actions runner ready! To use:"
	@echo "  source .env.gitea-test"
	@echo "  make validate-gitea"

# Stop test infrastructure
infra-down:
	docker compose -f plans/validation/docker/gitea.yaml down -v
	docker compose -f plans/validation/docker/gitlab.yaml down -v 2>/dev/null || true
	@echo "Infrastructure stopped."

# Start GitLab (resource-intensive)
infra-gitlab:
	docker compose -f plans/validation/docker/gitlab.yaml up -d
	@echo "Waiting for GitLab (this takes ~5 minutes)..."
	@until curl -sf http://localhost:8080/-/health > /dev/null 2>&1; do sleep 10; done
	@echo "GitLab ready at http://localhost:8080"
