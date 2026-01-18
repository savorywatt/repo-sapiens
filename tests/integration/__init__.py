"""Integration tests for repo-sapiens.

These tests require external services to be running:
- Gitea: docker compose -f plans/validation/docker/gitea.yaml up -d
- GitLab: docker compose -f plans/validation/docker/gitlab.yaml up -d
- Ollama: ollama serve

Run with: uv run pytest tests/integration/ -v -m integration
"""
