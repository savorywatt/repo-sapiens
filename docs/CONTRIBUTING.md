# Contributing to repo-sapiens

We welcome contributions to repo-sapiens! This document provides guidelines and instructions for contributing to the project.

## Table of Contents

- [Contributor License Agreement](#contributor-license-agreement)
- [Development Setup](#development-setup)
- [Code Style](#code-style)
- [Testing Requirements](#testing-requirements)
- [Pull Request Process](#pull-request-process)
- [Code Review Guidelines](#code-review-guidelines)
- [Release Process](#release-process)
- [Getting Help](#getting-help)

## Contributor License Agreement

**Before contributing code, you must agree to our Contributor License Agreement (CLA).**

### Why We Have a CLA

The CLA protects both you and the project by:
- Confirming you have the right to contribute your code
- Ensuring the project can distribute your contributions under the MIT License
- Protecting all users of the project from legal issues
- Clarifying that you retain ownership of your contributions

### Quick Summary

Our CLA is simple and developer-friendly:
- **You keep ownership** of your contributions
- **You grant us permission** to use and distribute your code under MIT License
- **Standard open source agreement** similar to Apache, Django, and other major projects
- **No separate signing required** - just add `Signed-off-by` to your commits

### How to Sign

We use the Developer Certificate of Origin (DCO) sign-off process. Simply add a sign-off line to each commit:

```bash
git commit -s -m "feat: your commit message"
```

This automatically adds:
```
Signed-off-by: Your Name <your.email@example.com>
```

**All commits in your pull request must include this sign-off.**

### Read the Full Agreement

Please read the complete CLA before contributing:
- [CONTRIBUTOR_LICENSE_AGREEMENT.md](CONTRIBUTOR_LICENSE_AGREEMENT.md)

If you have questions, open an issue or contact the maintainers.

## Development Setup

### Prerequisites

- Python 3.11 or 3.12
- Git
- uv package manager (https://docs.astral.sh/uv/)

### Fork and Clone

1. Fork the repository on GitHub/Gitea
2. Clone your fork locally:
   ```bash
   git clone https://github.com/YOUR-USERNAME/repo-sapiens.git
   cd repo-sapiens
   ```
3. Add the upstream repository:
   ```bash
   git remote add upstream https://github.com/savorywatt/repo-sapiens.git
   ```

### Install Development Dependencies

Install all dependencies using uv:

```bash
uv sync --group dev
```

This installs:
- Core dependencies (pydantic, click, httpx, jinja2, etc.)
- Development tools (pytest, ruff, mypy)
- Testing utilities (pytest-asyncio, pytest-cov, pytest-mock)
- Pre-commit hooks

### Run Tests

Verify your setup by running the test suite:

```bash
uv run pytest tests/ -v
uv run pytest tests/ --cov=repo_sapiens --cov-report=term-missing  # With coverage
```

## Code Style

### PEP 8 Compliance

All code must follow [PEP 8](https://www.python.org/dev/peps/pep-0008/) style guidelines. Key points:

- Use 4 spaces for indentation
- Line length: 100 characters (enforced by Ruff)
- Two blank lines between top-level definitions
- One blank line between method definitions
- Imports should be grouped and sorted (enforced by Ruff)

### Type Hints

Type hints are **required** for all public functions and methods. Examples:

```python
def get_user_config(config_path: str) -> dict[str, Any]:
    """Load user configuration from file.

    Args:
        config_path: Path to the configuration file.

    Returns:
        Dictionary containing configuration data.
    """
    ...

async def fetch_repository(owner: str, repo: str) -> RepositoryInfo:
    """Fetch repository information asynchronously."""
    ...
```

For complex types, use `typing` module imports:

```python
from typing import Optional, Union, Callable

def process_items(items: list[str], callback: Callable[[str], bool]) -> Optional[str]:
    """Process items with a callback function."""
    ...
```

### Docstring Format

We use **Google-style** docstrings for all public modules, classes, and functions:

```python
"""Module docstring on single line if brief, or expanded if needed.

Longer description can explain the module's purpose and provide context
for developers using or maintaining this code.
"""

class MyClass:
    """Brief description of the class.

    Attributes:
        attr1: Description of first attribute.
        attr2: Description of second attribute.
    """

    def __init__(self, attr1: str, attr2: int) -> None:
        """Initialize MyClass.

        Args:
            attr1: The first attribute value.
            attr2: The second attribute value.

        Raises:
            ValueError: If attr2 is negative.
        """
        if attr2 < 0:
            raise ValueError("attr2 must be non-negative")
        self.attr1 = attr1
        self.attr2 = attr2

    def process(self, data: str) -> dict[str, int]:
        """Process input data and return statistics.

        Args:
            data: Input string to process.

        Returns:
            Dictionary with statistics including word count and length.

        Raises:
            ValueError: If data is empty.
        """
        ...
```

### Code Formatting and Linting with Ruff

Format and lint code using Ruff:

```bash
# Format code
uv run ruff format repo_sapiens/ tests/

# Check code quality
uv run ruff check repo_sapiens/ tests/

# Auto-fix fixable issues
uv run ruff check --fix repo_sapiens/ tests/
```

The project is configured with:
- Line length: 100 characters
- Target Python version: 3.11+

The project is configured to check:
- Error codes (E, F)
- Import sorting (I)
- Naming conventions (N)
- Warnings (W)
- Upgrades (UP)
- Bugbear (B)
- Comprehensions (C4)
- And more (see `pyproject.toml`)

### Pre-commit Hooks (Automated Quality Checks)

We use **pre-commit** to automatically run code quality checks before each commit. This ensures consistent code quality and catches issues early.

#### Initial Setup

Install pre-commit hooks (one-time setup):

```bash
# Install the git hooks (pre-commit is included in dev dependencies)
uv run pre-commit install
```

#### What Gets Checked Automatically

When you commit, pre-commit automatically runs:
- **Ruff**: Code formatting, linting, and import sorting (auto-fixes when possible)
- **MyPy**: Type checking on changed files
- **Bandit**: Security vulnerability scanning
- **pyupgrade**: Automatic syntax upgrades for Python 3.11+
- **File checks**: Trailing whitespace, EOF newlines, YAML/JSON/TOML syntax
- **Secrets detection**: Prevents committing API keys, passwords, etc.

#### Manual Pre-commit Runs

Run hooks manually on all files:

```bash
# Run all hooks on all files
uv run pre-commit run --all-files

# Run all hooks on staged files only
uv run pre-commit run

# Run a specific hook
uv run pre-commit run ruff --all-files
uv run pre-commit run ruff-format --all-files
uv run pre-commit run mypy --all-files
```

#### Bypassing Hooks (Emergency Only)

In rare cases where you need to bypass hooks:

```bash
# Skip all pre-commit hooks (use with caution!)
git commit --no-verify -m "emergency fix"
```

**Warning**: Only bypass hooks when absolutely necessary. CI/CD will still run all checks.

#### Manual Workflow (Alternative)

If you prefer to run tools manually instead of using pre-commit:

```bash
# Format code
uv run ruff format repo_sapiens/ tests/

# Fix linting issues
uv run ruff check --fix repo_sapiens/ tests/

# Type checking
uv run mypy repo_sapiens/

# Security scanning
uv run bandit -c pyproject.toml -r repo_sapiens/

# Run tests
uv run pytest tests/ -v
```

#### Updating Pre-commit Hooks

Update hooks to latest versions:

```bash
# Update all hooks to latest versions
uv run pre-commit autoupdate

# Update a specific hook
uv run pre-commit autoupdate --repo https://github.com/astral-sh/ruff-pre-commit
```

## Testing Requirements

### Write Tests for New Features

All new features must include tests. Test files should be placed in `tests/` with matching directory structure to the source code.

Example test structure:

```
repo_sapiens/credentials/resolver.py  →  tests/test_credentials/test_resolver.py
repo_sapiens/git/discovery.py         →  tests/git/test_discovery.py
```

Write tests using pytest:

```python
# tests/test_credentials/test_resolver.py
import pytest
from repo_sapiens.credentials.resolver import CredentialResolver


@pytest.fixture
def resolver() -> CredentialResolver:
    """Create a credential resolver for testing."""
    return CredentialResolver()


def test_resolve_environment_variable(resolver):
    """Test resolving credentials from environment variables."""
    # Arrange
    import os
    os.environ["TEST_TOKEN"] = "secret123"

    # Act
    result = resolver.resolve("${TEST_TOKEN}")

    # Assert
    assert result == "secret123"


@pytest.mark.asyncio
async def test_resolve_keyring_credential(resolver):
    """Test resolving credentials from keyring."""
    # Arrange & Act
    result = await resolver.resolve_async("@keyring:service/account")

    # Assert
    assert isinstance(result, str)
```

### Maintain 75%+ Code Coverage

- Run coverage reports: `uv run pytest --cov=repo_sapiens --cov-report=html`
- Coverage reports are generated in `htmlcov/index.html`
- Aim for 75%+ line coverage; critical paths should have higher coverage
- Use `# pragma: no cover` sparingly for untestable code (e.g., CLI entry points)

### Run Full Test Suite Before PR

Before submitting a pull request, ensure:

```bash
# Run all tests
uv run pytest tests/ -v

# Check coverage
uv run pytest tests/ --cov=repo_sapiens --cov-report=term-missing

# Type checking
uv run mypy repo_sapiens/

# Formatting and linting
uv run ruff format --check repo_sapiens/ tests/
uv run ruff check repo_sapiens/ tests/
```

## Pull Request Process

### Create Feature Branch

Create a descriptive branch name:

```bash
git checkout -b feature/add-github-provider
git checkout -b fix/credential-resolver-bug
git checkout -b docs/update-architecture
```

Branch naming conventions:
- `feature/`: New features
- `fix/`: Bug fixes
- `docs/`: Documentation updates
- `refactor/`: Code refactoring without behavior changes
- `test/`: Test coverage improvements
- `chore/`: Dependencies, configuration, tooling

### Write Descriptive Commit Messages

Follow conventional commit format:

```
type(scope): brief description

Longer explanation of the change, why it was needed,
and any important details for reviewers.

Closes #123
```

Types:
- `feat`: A new feature
- `fix`: A bug fix
- `docs`: Documentation changes
- `style`: Formatting, missing semicolons, etc.
- `refactor`: Code refactoring without changing behavior
- `perf`: Performance improvements
- `test`: Adding or updating tests
- `chore`: Build process, dependencies, tooling

Examples:

```
feat(credentials): add support for encrypted backend

Implement encrypted credential backend using fernet encryption.
Supports secure storage of credentials in configuration files
with automatic decryption at runtime.

Closes #45
```

```
fix(git): handle gracefully when local branch diverges

Previously would raise exception. Now performs merge-base
check and prompts user for merge strategy.

Closes #67
```

### Update Documentation

- Update docstrings for modified functions/classes
- Update relevant documentation files in `docs/`
- Update `README.md` if adding new features or CLI commands
- Update `CHANGELOG.md` with your changes (see [Release Process](#release-process))

### Update CHANGELOG.md

Add an entry to the "Unreleased" section at the top of `CHANGELOG.md`:

```markdown
## [Unreleased]

### Added
- Brief description of added features

### Changed
- Brief description of changed behavior

### Fixed
- Brief description of bug fixes

### Deprecated
- Brief description of deprecated features (if any)

---

## [1.0.0] - 2025-01-15
...
```

### Submit the Pull Request

1. **Ensure all commits are signed off**: Every commit must include `Signed-off-by` (see [CLA](#contributor-license-agreement))
   ```bash
   # Check your commits have sign-off
   git log --show-signature

   # If missing, amend your commits
   git commit --amend -s
   ```

2. Push your branch: `git push origin feature/add-github-provider`

3. Open a pull request on GitHub/Gitea

4. Fill in the PR template with:
   - Description of changes
   - Motivation and context
   - Type of change (feature/fix/refactor/docs)
   - How to test
   - Checklist of completed items
   - **Confirmation that all commits are signed off**

5. Request review from maintainers

**Note**: Pull requests with unsigned commits will not be accepted. Please ensure all commits include the `Signed-off-by` line as required by our [CLA](#contributor-license-agreement).

## Code Review Guidelines

### What Reviewers Look For

Reviewers will assess:

1. **Correctness**: Does the code solve the problem correctly?
2. **Design**: Is the solution well-designed and maintainable?
3. **Type Safety**: Are type hints complete and correct?
4. **Testing**: Are tests comprehensive and meaningful?
5. **Documentation**: Are docstrings clear and complete?
6. **Performance**: Are there obvious performance issues?
7. **Security**: Are there security vulnerabilities?
8. **Style**: Does it follow project conventions?

### Common Feedback Patterns

**Missing type hints:**
```python
# Bad
def get_config(path):
    ...

# Good
def get_config(path: str) -> dict[str, Any]:
    ...
```

**Incomplete docstrings:**
```python
# Bad
def process(data):
    """Process the data."""
    ...

# Good
def process(data: str) -> str:
    """Process input data by normalizing whitespace.

    Args:
        data: Raw input string.

    Returns:
        Normalized string with collapsed whitespace.
    """
    ...
```

**Missing test coverage:**
```python
# Add tests for:
# - Happy path
# - Error conditions
# - Edge cases
# - Integration scenarios
```

**Performance concerns:**
```python
# Bad - N+1 query problem
for user in users:
    user.profile = load_profile(user.id)

# Good - Batch loading
profiles = load_profiles([u.id for u in users])
user_profiles = {p.user_id: p for p in profiles}
for user in users:
    user.profile = user_profiles[user.id]
```

## Release Process

### Version Numbering (Semantic Versioning)

We follow [Semantic Versioning 2.0.0](https://semver.org/):

- **MAJOR**: Breaking changes (e.g., 1.0.0 → 2.0.0)
- **MINOR**: New features, backward compatible (e.g., 1.0.0 → 1.1.0)
- **PATCH**: Bug fixes, backward compatible (e.g., 1.0.0 → 1.0.1)

Format: `MAJOR.MINOR.PATCH` (optionally with pre-release: `1.0.0-rc.1`)

### Changelog Updates

When releasing a new version:

1. Update version in `repo_sapiens/__version__.py`:
   ```python
   __version__ = "1.1.0"
   ```

2. Update `CHANGELOG.md`:
   ```markdown
   ## [1.1.0] - 2025-01-15

   ### Added
   - GitHub provider support
   - Credential encryption backend

   ### Changed
   - Improved error messages in CLI

   ### Fixed
   - Bug in credential resolver with environment variables

   ---

   ## [1.0.0] - 2024-12-20
   ...
   ```

3. Add comparison links at the bottom:
   ```markdown
   [1.1.0]: https://github.com/savorywatt/repo-sapiens/compare/v1.0.0...v1.1.0
   [1.0.0]: https://github.com/savorywatt/repo-sapiens/releases/tag/v1.0.0
   ```

### Tag Creation

Create a Git tag for the release:

```bash
# Create an annotated tag
git tag -a v1.1.0 -m "Release version 1.1.0

- Added GitHub provider support
- Improved error handling in CLI
"

# Push the tag
git push upstream v1.1.0

# Or push all tags
git push upstream --tags
```

### Release Checklist

- [ ] All pre-commit hooks pass: `uv run pre-commit run --all-files`
- [ ] All tests pass: `uv run pytest tests/ -v`
- [ ] Coverage is acceptable: `uv run pytest --cov=repo_sapiens`
- [ ] Code is formatted: `uv run ruff format repo_sapiens/ tests/`
- [ ] Linting passes: `uv run ruff check repo_sapiens/`
- [ ] Type checking passes: `uv run mypy repo_sapiens/`
- [ ] Security scan passes: `uv run bandit -c pyproject.toml -r repo_sapiens/`
- [ ] Version updated in `repo_sapiens/__version__.py`
- [ ] `CHANGELOG.md` is updated
- [ ] Git tag is created and pushed
- [ ] Release notes are published
- [ ] Package is built and tested: `uv build`

## Getting Help

### Documentation

- [Architecture Overview](docs/ARCHITECTURE.md) - System design and components
- [README.md](README.md) - Project overview and quick start
- Code comments and docstrings - Implementation details

### Communication

- Open an issue for bugs or feature requests
- Discuss design decisions in pull request comments
- Ask questions in issue discussions

### Common Issues

**ImportError when running tests:**
```bash
# Ensure package is installed in development mode
uv sync --group dev
```

**Ruff formatting conflicts:**
```bash
# Ruff handles both formatting and linting
# If issues occur, check pyproject.toml matches project standards
```

**Async test failures:**
```bash
# Ensure pytest-asyncio is installed and configured
uv run pytest --asyncio-mode=auto tests/
```

---

Thank you for contributing to repo-sapiens! Your efforts help make this project better for everyone.
