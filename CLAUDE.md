# Project Instructions for Claude Code

## Git Commits

- Do NOT add Claude annotations, attribution, or co-author lines to git commits
- Do NOT append generated-by footers or signatures
- Keep commit messages clean and focused on the changes only

## Project Structure

- **Package manager**: `uv` (use `uv run` for all Python commands)
- **CLI framework**: Click
- **Config validation**: Pydantic
- **Project state**: `.sapiens/` directory (config, state, etc.)
- **Async patterns**: Uses `asyncio.run()` for async entry points

## Configuration

### YAML Generation
- Always quote values starting with `@` or `$` (e.g., `api_token: "@keyring:gitea/api_token"`)
- These are credential references, not YAML anchors

### Valid Agent Provider Types
Only these values are valid for `agent_provider.provider_type`:
- `claude-local`, `claude-api`
- `goose-local`, `goose-api`
- `openai`, `openai-compatible`, `ollama`

Do NOT use `react` as a provider type.

### Valid Git Provider Types
- `github`, `gitea`

## Testing

Quick config validation:
```bash
uv run sapiens --config .sapiens/config.yaml health-check
```

Syntax check for Python files:
```bash
uv run python -m py_compile <file.py>
```

Run tests:
```bash
uv run pytest tests/unit/ -v
```

## File Editing

- Linters may modify files between read and write operations
- Always re-read a file if an edit fails due to modification
- The project uses ruff for formatting/linting

## Preferences

- Keep changes minimal and focused
- Prefer editing existing files over creating new ones
- Use `.sapiens/` for all project state (not `.automation/`)
- Test commands should be quick and non-destructive
