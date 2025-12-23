# Type Checking Guidelines for repo-sapiens

## Overview

repo-sapiens uses **mypy in strict mode** for comprehensive type checking. All code must pass `mypy --strict` with zero errors.

## Configuration

### mypy Configuration (pyproject.toml)

```toml
[tool.mypy]
python_version = "3.11"
strict = true
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
```

### py.typed Marker

The `automation/py.typed` file marks this package as typed for downstream consumers.

## Type Hint Requirements

### 1. Function Signatures

All public and private functions must have complete type annotations:

```python
# ✓ Correct: Complete type hints
async def process_issue(issue: Issue) -> None:
    """Process a single issue."""
    pass

# ✗ Incorrect: Missing return type
async def process_issue(issue: Issue):
    pass

# ✓ Correct: Explicit Optional for None returns
def get_config(key: str) -> str | None:
    """Get config value or None if not found."""
    return self.config.get(key)

# ✗ Incorrect: Implicit Optional
def get_config(key: str) -> str:
    return self.config.get(key)  # May return None!
```

### 2. Optional Types

Use the modern union syntax (`X | None`) or `Optional[X]`:

```python
# ✓ Modern syntax (Python 3.10+)
def create_branch(name: str, from_branch: str | None = None) -> Branch:
    pass

# ✓ Classic syntax (compatible with 3.11)
from typing import Optional
def create_branch(name: str, from_branch: Optional[str] = None) -> Branch:
    pass

# ✗ Incorrect: None not represented
def create_branch(name: str, from_branch: str = None) -> Branch:
    pass
```

### 3. Container Types

Use modern generic syntax for built-in containers:

```python
# ✓ Modern syntax (Python 3.9+)
def process_issues(issues: list[Issue]) -> dict[str, TaskResult]:
    pass

# ✓ Classic syntax (with imports)
from typing import List, Dict
def process_issues(issues: List[Issue]) -> Dict[str, TaskResult]:
    pass

# ✗ Incorrect: bare list/dict
def process_issues(issues: list) -> dict:
    pass
```

### 4. Any Types

Minimize use of `Any`. Use specific types instead:

```python
# ✓ Correct: Specific type
def parse_response(data: dict[str, any]) -> dict[str, int]:
    """Parse API response."""
    pass

# ✓ Acceptable: When type truly unknown (rare)
def handle_generic_data(data: Any) -> None:
    """Process data from unknown external source."""
    pass

# ✗ Incorrect: Over-using Any
def parse_config(data: dict[str, Any]) -> dict[str, Any]:
    # This loses type safety
    pass

# ✗ Incorrect: Implicit Any
def parse_config(data):
    pass
```

### 5. Protocol Types

Use Protocol for duck typing and structural typing:

```python
from typing import Protocol

# ✓ Correct: Protocol for duck typing
class Drawable(Protocol):
    """Something that can be drawn."""

    def draw(self) -> None:
        """Draw the object."""
        ...

def render(obj: Drawable) -> None:
    """Render any drawable object."""
    obj.draw()

# ✓ Correct: Existing Protocol from base.py
from automation.credentials.backend import CredentialBackend

def resolve_credentials(backend: CredentialBackend) -> str:
    """Resolve credentials using any backend."""
    return backend.get("service", "key") or ""
```

### 6. Callable Types

Use `Callable` for function types:

```python
from typing import Callable

# ✓ Correct: Full signature
def apply_handler(data: list[str], handler: Callable[[str], int]) -> list[int]:
    """Apply handler to each item."""
    return [handler(item) for item in data]

# ✓ Correct: Multiple arguments
def run_callback(callback: Callable[[str, int, bool], None]) -> None:
    """Run a callback with specific signature."""
    callback("test", 42, True)
```

### 7. TypeVar and Generics

Use TypeVar for generic functions:

```python
from typing import TypeVar

T = TypeVar("T")
U = TypeVar("U")

# ✓ Correct: Generic function
def first(items: list[T]) -> T | None:
    """Get first item from list."""
    return items[0] if items else None

# ✓ Correct: Multiple type variables
def zip_lists(items1: list[T], items2: list[U]) -> list[tuple[T, U]]:
    """Zip two lists together."""
    return list(zip(items1, items2))
```

## Common Issues and Fixes

### Issue 1: Missing Type Hints on Properties

```python
# ✗ Incorrect
class Config:
    @property
    def state_dir(self):
        return Path(self.path)

# ✓ Correct
from pathlib import Path

class Config:
    @property
    def state_dir(self) -> Path:
        """Get state directory as Path object."""
        return Path(self.path)
```

### Issue 2: Untyped Exception Handlers

```python
# ✗ Incorrect
try:
    result = some_function()
except Exception:  # Too broad
    pass

# ✓ Correct
try:
    result = some_function()
except (ValueError, KeyError) as e:
    logger.error("Processing error", error=str(e))
```

### Issue 3: Dict Access Without Type Guards

```python
# ✗ Incorrect: mypy warns about missing keys
def process_data(data: dict[str, str]) -> None:
    value = data["key"]  # What if key doesn't exist?

# ✓ Correct: Use get() with default
def process_data(data: dict[str, str]) -> None:
    value = data.get("key", "default")

# ✓ Correct: Check existence first
def process_data(data: dict[str, str]) -> None:
    if "key" in data:
        value = data["key"]
```

### Issue 4: Context Objects (Click/FastAPI)

When using frameworks with context objects, use type: ignore with explanation:

```python
@click.group()
@click.pass_context
def cli(ctx: click.Context) -> None:  # type: ignore[misc]
    """CLI entry point."""
    # Click's context typing is complex; this is acceptable
    ctx.obj = {"settings": load_settings()}
```

## Strict Mode Rules

Strict mode enforces these rules:

1. **No untyped definitions**: All functions must have argument and return types
2. **No implicit Optional**: If a function might return None, it must be explicit
3. **No Any by default**: `Any` types must be used intentionally, not by default
4. **No skipped lines**: `# type: ignore` requires explanation
5. **Warn on unreachable code**: Code that can never execute is flagged
6. **Check for unused variables**: Defines but doesn't use variables

## Using type: ignore

When mypy rejects valid code, use `# type: ignore` with explanation:

```python
# ✓ Correct: Explanation provided
result = some_function()  # type: ignore[arg-type]
# The function's return type is too strict; we handle it correctly at runtime

# ✓ Correct: Specific error code
data = response.json()  # type: ignore[no-any-return]
# httpx returns Any; we trust the response structure

# ✗ Incorrect: No explanation
result = some_function()  # type: ignore

# ✗ Incorrect: Ignoring too broadly
long_function_call(  # type: ignore
    arg1, arg2, arg3
)
```

## Running Type Checks

### Local Development

```bash
# Check entire automation module
mypy automation/ --strict

# Check specific file
mypy automation/main.py --strict

# Verbose output for debugging
mypy automation/ --strict --show-error-codes --pretty

# Show all inferred types
mypy automation/ --strict --reveal-type
```

### CI/CD Pipeline

The GitHub/Gitea Actions workflow automatically runs:

```yaml
- name: Type check with mypy
  run: mypy automation/ --strict
```

All PRs must pass type checking before merge.

## Gradual Typing Strategy

For large refactors, gradually increase type safety:

1. **Phase 1**: Add type hints to function signatures
2. **Phase 2**: Fix Optional and return types
3. **Phase 3**: Replace Any with specific types
4. **Phase 4**: Add Protocol types for duck typing
5. **Phase 5**: Run strict mode and fix remaining issues

## Type Hints in Different Contexts

### Async Functions

```python
# ✓ Correct: Async return type
async def fetch_data(url: str) -> bytes:
    """Fetch data from URL."""
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
    return response.content

# ✓ Correct: Coroutine type for storing
from typing import Coroutine

def schedule_task(task: Coroutine[any, any, None]) -> None:
    """Schedule a coroutine for execution."""
    asyncio.create_task(task)
```

### Class Methods and Properties

```python
from typing import ClassVar

class Manager:
    instances: ClassVar[dict[str, Manager]] = {}  # Class variable

    def __init__(self, name: str) -> None:
        """Initialize manager."""
        self.name = name
        Manager.instances[name] = self

    @classmethod
    def get(cls, name: str) -> Manager | None:
        """Get manager by name."""
        return cls.instances.get(name)

    @staticmethod
    def validate(data: str) -> bool:
        """Validate data format."""
        return len(data) > 0
```

### Dataclasses

```python
from dataclasses import dataclass, field

@dataclass
class Task:
    """A task to execute."""
    id: str
    title: str
    dependencies: list[str] = field(default_factory=list)
    metadata: dict[str, str] = field(default_factory=dict)

    def add_dependency(self, dep_id: str) -> None:
        """Add a dependency to this task."""
        if dep_id not in self.dependencies:
            self.dependencies.append(dep_id)
```

## Benefits of Strict Type Checking

1. **Early Error Detection**: Catch bugs at type-check time, not runtime
2. **Better IDE Support**: IDEs provide accurate autocompletion and refactoring
3. **Living Documentation**: Type hints serve as documentation
4. **Safer Refactoring**: Change code with confidence knowing types match
5. **Easier Maintenance**: Future developers understand expected types
6. **Better Performance**: Allows Python optimizers to understand code better

## Further Reading

- [mypy Documentation](https://mypy.readthedocs.io/)
- [PEP 484 - Type Hints](https://www.python.org/dev/peps/pep-0484/)
- [PEP 585 - Type Hinting Generics](https://www.python.org/dev/peps/pep-0585/)
- [PEP 604 - Union Types](https://www.python.org/dev/peps/pep-0604/)
- [typing module documentation](https://docs.python.org/3/library/typing.html)

## Questions?

For type checking questions or issues:

1. Check this guide for examples
2. Look at existing code patterns in `automation/`
3. Refer to mypy error messages (they're usually helpful!)
4. Check mypy documentation for specific error codes
5. Open an issue with type checking examples
