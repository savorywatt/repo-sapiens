# mypy Type Checking Status

## Current Status

As of 2025-12-23, mypy strict mode type checking has been partially implemented.

### Summary

- **Total Files Checked**: 78 Python source files
- **Files with Issues**: 40 files
- **Total Errors Found**: 261 errors
- **Target**: 0 errors for production code

## Error Categories

### 1. Missing Type Stubs (31 errors)
External libraries need type information:
- `yaml` (PyYAML) - Needs: `pip install types-PyYAML`
- `aiofiles` - Needs: `pip install types-aiofiles`
- `fastapi` (optional dependency) - Needs: `pip install fastapi`
- `uvicorn` (optional dependency) - Needs: `pip install uvicorn`
- `prometheus_client` (optional dependency) - Needs: `pip install prometheus-client`

### 2. Missing Type Annotations (98 errors)
Functions without complete type hints:

**CLI Module** (`automation/cli/credentials.py`):
- 5 functions missing return type annotations
- Example: `def credentials_group()` → `def credentials_group() -> None:`

**Rendering Module** (`automation/rendering/`, `automation/templates/examples/`):
- Filters returning `Any` instead of specific types
- Security demo functions missing return types
- Example usage missing return types

**Utility Modules** (`automation/utils/`):
- `status_reporter.py`: Functions missing annotations
- `batch_operations.py`: Variables need explicit type annotation
- `mcp_client.py`: Functions returning `Any` without explicit return type

**Provider Modules** (`automation/providers/`):
- `external_agent.py`: Multiple untyped functions and variables
- `agent_provider.py`: Dict parameters without type parameters
- `git_provider.py`: Returning `Any` from functions declared to return `str`

### 3. Missing Generic Parameters (67 errors)
Unspecified container types like `dict`, `list`, `tuple`:

```python
# ✗ Before
async def save_state(data: dict) -> None:
    pass

# ✓ After
async def save_state(data: dict[str, Any]) -> None:
    pass
```

Affected files:
- `automation/providers/base.py`
- `automation/engine/` modules
- `automation/utils/` modules
- `automation/webhook_server.py`

### 4. Incompatible Types (35 errors)
Type mismatches between assignment and declaration:

- `StateManager` expects `str`, receives `Path`
- `Plan` missing required `tasks` parameter
- `Review` unexpected keyword `confidence` (should be `confidence_score`)
- `Task` unexpected keyword `plan_id`
- Conditional type mismatches

### 5. Decorator Issues (14 errors)
Untyped decorators making functions untyped:
- FastAPI route decorators (`@app.get()`, `@app.post()`)
- Click decorators (`@click.command()`, `@click.option()`)

### 6. Name and Attribute Errors (15 errors)
- Missing imports: `PullRequest`, `Task` not imported in some modules
- Missing methods: `GitProvider.get_pull_request()`, `AgentProvider.execute_prompt()`
- Missing attributes: `AgentProvider.working_dir`, `TagsConfig.needs_implementation`

## Priority Fixes

### Phase 1: Critical (Blocks Production) - 45 errors
1. **Install type stubs**:
   ```bash
   pip install types-PyYAML types-aiofiles
   ```

2. **Fix main.py** (8 errors):
   - Fix StateManager argument type
   - Fix base_url type compatibility
   - Fix agent assignment type

3. **Fix configuration** (12 errors):
   - Add type annotations to credential_fields.py
   - Fix settings.py yaml import stubs
   - Fix CredentialSecret.get_secret_value() return type

4. **Fix credentials** (5 errors):
   - Fix encrypted_backend Fernet initialization
   - Fix resolver return type issue

### Phase 2: High Priority (Type Safety) - 98 errors
1. Add return type annotations to all CLI functions
2. Add return type annotations to rendering/security functions
3. Fix Any returns to specific types in providers
4. Add missing type parameters to dict/list throughout

### Phase 3: Medium Priority (Code Quality) - 67 errors
1. Add type parameters to all generic containers
2. Fix decorator type issues
3. Add missing attribute definitions

### Phase 4: Low Priority (Completeness) - 51 errors
1. Fix name definitions (missing imports)
2. Fix attribute references (missing methods)
3. Refine domain model definitions

## Installation Steps

### 1. Install Type Stubs

```bash
# Install type stubs for untyped libraries
python3.13 -m pip install types-PyYAML types-aiofiles --break-system-packages

# Or use mypy's auto-installer
python3.13 -m mypy --install-types automation/ --strict
```

### 2. Run Type Checking

```bash
# Check all files
python3.13 -m mypy automation/ --strict

# Check specific file
python3.13 -m mypy automation/main.py --strict

# Show all errors with codes
python3.13 -m mypy automation/ --strict --show-error-codes

# See detailed errors
python3.13 -m mypy automation/ --strict --pretty
```

### 3. Fix Errors Systematically

Use the priority phases above to address errors in order.

## Common Fixes

### Missing Return Type
```python
# ✗ Before
async def process_issue(issue: Issue):
    pass

# ✓ After
async def process_issue(issue: Issue) -> None:
    pass
```

### Missing Generic Parameters
```python
# ✗ Before
def parse_data(data: dict) -> dict:
    pass

# ✓ After
from typing import Any
def parse_data(data: dict[str, Any]) -> dict[str, Any]:
    pass
```

### Optional Types
```python
# ✗ Before
def get_name(self) -> str:
    return self.name  # Could be None!

# ✓ After
def get_name(self) -> str | None:
    return self.name
```

### Type Ignore (Last Resort)
```python
# Use when mypy is wrong
result = some_untyped_func()  # type: ignore[return-value]
# Explanation: func returns Any; we trust it at runtime
```

## Configuration

### pyproject.toml

Already configured with strict settings:

```toml
[tool.mypy]
python_version = "3.11"
strict = true
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
```

### py.typed Marker

Present at: `automation/py.typed`

This marks the package as typed for downstream type-checking.

## CI/CD Integration

Add to GitHub/Gitea Actions:

```yaml
- name: Type check with mypy (strict mode)
  run: |
    python3 -m pip install mypy types-PyYAML types-aiofiles
    python3 -m mypy automation/ --strict
```

## Resources

- [mypy Documentation](https://mypy.readthedocs.io/)
- [PEP 484 - Type Hints](https://www.python.org/dev/peps/pep-0484/)
- [typing Module Docs](https://docs.python.org/3/library/typing.html)
- [See TYPE_CHECKING.md for guidelines](docs/TYPE_CHECKING.md)

## Next Steps

1. **Immediate** (1-2 hours):
   - Install type stubs
   - Fix critical imports and main.py errors
   - Run mypy to verify improvements

2. **Short-term** (1 day):
   - Fix all function return type annotations
   - Add missing generic parameters
   - Resolve domain model mismatches

3. **Medium-term** (2-3 days):
   - Complete all attribute and method definitions
   - Fix decorator type issues
   - Achieve strict mode compliance

4. **Long-term** (Ongoing):
   - Maintain strict mode compliance in PR reviews
   - Use mypy in CI/CD pipeline
   - Update documentation with type checking guidelines

## Questions?

Refer to the comprehensive guidelines in `/home/ross/Workspace/repo-agent/docs/TYPE_CHECKING.md`
