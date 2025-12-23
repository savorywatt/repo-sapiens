# Git Discovery Module

Automatic Git repository discovery and URL parsing for Gitea automation.

## Quick Start

```python
from automation.git import GitDiscovery

# Detect repository info from current directory
discovery = GitDiscovery()
info = discovery.parse_repository()

print(f"{info.owner}/{info.repo} @ {info.base_url}")
# Output: myorg/myrepo @ https://gitea.com
```

## Features

- Automatic Git remote detection from local repositories
- Parsing of SSH and HTTPS Git URLs
- Extraction of owner/repo from Git URLs
- Support for multiple remotes with intelligent preference order
- Comprehensive error handling with helpful hints
- Type-safe with Pydantic models

## Installation

Add to your dependencies:

```toml
dependencies = [
    "gitpython>=3.1.40",
    "pydantic>=2.5.0",
]
```

Install:

```bash
pip install gitpython pydantic
```

## API Reference

### GitDiscovery

Main class for Git repository discovery.

```python
from automation.git import GitDiscovery

discovery = GitDiscovery(repo_path=".")  # defaults to current directory
```

#### Methods

##### `list_remotes() -> list[GitRemote]`

List all Git remotes in the repository.

```python
remotes = discovery.list_remotes()
for remote in remotes:
    print(f"{remote.name}: {remote.url} ({remote.url_type})")
```

##### `get_remote(remote_name=None, allow_multiple=False) -> GitRemote`

Get a specific remote or use preference order (origin > upstream > first).

```python
# Auto-detect (prefers origin)
remote = discovery.get_remote()

# Specific remote
remote = discovery.get_remote(remote_name="upstream")

# Allow multiple without error
remote = discovery.get_remote(allow_multiple=True)
```

##### `parse_repository(remote_name=None, allow_multiple=False) -> RepositoryInfo`

Parse complete repository information from Git remote.

```python
info = discovery.parse_repository()

print(info.owner)         # "myorg"
print(info.repo)          # "myrepo"
print(info.base_url)      # "https://gitea.com"
print(info.remote_name)   # "origin"
print(info.ssh_url)       # "git@gitea.com:myorg/myrepo.git"
print(info.https_url)     # "https://gitea.com/myorg/myrepo.git"
print(info.full_name)     # "myorg/myrepo"
```

##### `detect_gitea_config(remote_name=None) -> dict[str, str]`

Detect Gitea configuration suitable for config files.

```python
config = discovery.detect_gitea_config()
# Returns:
# {
#     'base_url': 'https://gitea.com',
#     'owner': 'myorg',
#     'repo': 'myrepo'
# }
```

### GitUrlParser

Parse Git URLs in SSH and HTTPS formats.

```python
from automation.git import GitUrlParser

parser = GitUrlParser("git@gitea.com:owner/repo.git")

print(parser.url_type)    # "ssh"
print(parser.host)        # "gitea.com"
print(parser.owner)       # "owner"
print(parser.repo)        # "repo"
print(parser.base_url)    # "https://gitea.com"
print(parser.ssh_url)     # "git@gitea.com:owner/repo.git"
print(parser.https_url)   # "https://gitea.com/owner/repo.git"
```

Supported URL formats:

- SSH: `git@gitea.com:owner/repo.git`
- HTTPS: `https://gitea.com/owner/repo.git`
- HTTPS with port: `https://gitea.com:3000/owner/repo.git`
- HTTP: `http://gitea.local/owner/repo.git`

### Helper Functions

#### `detect_git_origin(repo_path=".") -> str | None`

Quick helper to detect Git origin URL with None fallback.

```python
from automation.git import detect_git_origin

base_url = detect_git_origin()
if base_url:
    print(f"Detected: {base_url}")
else:
    print("No Git remote found")
```

## Models

### GitRemote

Represents a Git remote configuration (frozen dataclass).

```python
@dataclass(frozen=True)
class GitRemote:
    name: str                                    # "origin"
    url: str                                     # "git@gitea.com:owner/repo.git"
    url_type: Literal["ssh", "https", "unknown"] # "ssh"
```

### RepositoryInfo

Parsed repository information (Pydantic model).

```python
class RepositoryInfo(BaseModel):
    owner: str          # Repository owner/organization
    repo: str           # Repository name (without .git)
    base_url: HttpUrl   # Gitea instance URL
    remote_name: str    # Which remote was used
    ssh_url: str        # SSH clone URL
    https_url: str      # HTTPS clone URL

    @property
    def full_name(self) -> str:
        return f"{self.owner}/{self.repo}"
```

### MultipleRemotesInfo

Information about multiple remotes (Pydantic model).

```python
class MultipleRemotesInfo(BaseModel):
    remotes: list[GitRemote]  # All detected remotes
    suggested: GitRemote | None  # Suggested remote to use

    @property
    def remote_names(self) -> list[str]:
        return [r.name for r in self.remotes]
```

## Error Handling

All exceptions inherit from `GitDiscoveryError` and include helpful hints.

### Exception Hierarchy

```python
GitDiscoveryError
├── NotGitRepositoryError     # Directory is not a Git repository
├── NoRemotesError             # No remotes configured
├── MultipleRemotesError       # Multiple remotes, need to specify
├── InvalidGitUrlError         # URL format not recognized
└── UnsupportedHostError       # Host is not Gitea
```

### Example: Handle Multiple Remotes

```python
from automation.git import GitDiscovery, MultipleRemotesError

discovery = GitDiscovery()

try:
    info = discovery.parse_repository()
except MultipleRemotesError as e:
    print(f"Error: {e.message}")
    print(f"Hint: {e.hint}")

    # Access exception attributes
    print("\nAvailable remotes:")
    for remote in e.remotes:
        marker = "→" if remote == e.suggested else " "
        print(f"  {marker} {remote.name}: {remote.url}")

    # Use suggested remote
    if e.suggested:
        info = discovery.parse_repository(remote_name=e.suggested.name)
```

### Example: Graceful Fallback

```python
from automation.git import GitDiscovery, GitDiscoveryError

try:
    discovery = GitDiscovery()
    config = discovery.detect_gitea_config()
except GitDiscoveryError as e:
    print(f"Auto-detection failed: {e}")
    # Fall back to manual input
    config = {
        'base_url': input("Enter Gitea URL: "),
        'owner': input("Enter owner: "),
        'repo': input("Enter repo: ")
    }
```

## Advanced Usage

### Working with Specific Directories

```python
from pathlib import Path

# Specify repository path
repo_path = Path("/path/to/repo")
discovery = GitDiscovery(repo_path)
```

### Search Parent Directories

GitDiscovery automatically searches parent directories for `.git/`:

```python
# Even if you're in a subdirectory, it will find the repo
discovery = GitDiscovery("/path/to/repo/src/subdir")
info = discovery.parse_repository()
```

### Getting Information About All Remotes

```python
info = discovery.get_multiple_remotes_info()

print(f"Found {len(info.remotes)} remotes:")
for remote in info.remotes:
    print(f"  - {remote.name}: {remote.url}")

if info.suggested:
    print(f"\nSuggested: {info.suggested.name}")
```

### URL Conversion

```python
# Convert between SSH and HTTPS
parser = GitUrlParser("git@gitea.com:owner/repo.git")

print(parser.ssh_url)      # git@gitea.com:owner/repo.git
print(parser.https_url)    # https://gitea.com/owner/repo.git
```

## Testing

Run the test suite:

```bash
# All tests
pytest tests/git/ -v

# Specific test file
pytest tests/git/test_parser.py -v

# With coverage
pytest tests/git/ --cov=automation.git --cov-report=term-missing
```

## Common Scenarios

### Fork Workflow

```python
# When you have both origin (your fork) and upstream (original)
discovery = GitDiscovery()

# Automatically uses origin (your fork)
info = discovery.parse_repository(allow_multiple=True)
print(f"Your fork: {info.owner}/{info.repo}")

# Explicitly get upstream
upstream_info = discovery.parse_repository(remote_name="upstream")
print(f"Upstream: {upstream_info.owner}/{upstream_info.repo}")
```

### Self-Hosted Gitea

```python
# Works with custom ports and domains
discovery = GitDiscovery()
info = discovery.parse_repository()

# Example: https://git.company.com:8443/team/project
print(info.base_url)  # https://git.company.com:8443
```

### CLI Integration

```python
import click
from automation.git import GitDiscovery, GitDiscoveryError

@click.command()
@click.option("--remote", help="Git remote name")
def init(remote):
    """Initialize configuration."""
    try:
        discovery = GitDiscovery()
        config = discovery.detect_gitea_config(remote)

        click.echo(f"Detected: {config['owner']}/{config['repo']}")
        click.echo(f"Base URL: {config['base_url']}")

    except GitDiscoveryError as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()
```

## Edge Cases

The module handles many edge cases:

- URLs with and without `.git` suffix
- Custom ports (`:3000`, `:8443`, etc.)
- HTTP vs HTTPS
- Nested repository paths
- Special characters (hyphens, underscores, numbers)
- Whitespace in URLs
- Empty owner/repo validation
- No remotes configured
- Not a Git repository
- Multiple remotes without preferred names

## Performance

- Lazy loading of Git repository (only loads when needed)
- Cached repository object (no repeated Git operations)
- No network calls (local-only operations)
- Fast path for common case (single remote named "origin")

## Type Safety

All code includes type hints and works with mypy:

```bash
mypy automation/git/ --strict
```

Models use Pydantic for runtime validation:

```python
# This will raise ValidationError
info = RepositoryInfo(
    owner="",  # Error: owner must not be empty
    repo="myrepo",
    # ...
)
```

## Dependencies

- **gitpython** (>=3.1.40) - Git repository interaction
- **pydantic** (>=2.5.0) - Data validation

## License

MIT License - see LICENSE file for details.
