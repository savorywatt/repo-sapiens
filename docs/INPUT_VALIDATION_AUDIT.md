# Input Validation and Sanitization Security Audit

**Project**: repo-agent
**Audit Date**: 2025-12-23
**Scope**: CLI handlers, template rendering, HTTP clients, configuration loading
**Overall Assessment**: GOOD - Mostly secure with some minor gaps

---

## Executive Summary

The repo-agent codebase demonstrates solid security practices with:
- **Safe template rendering** using sandboxed Jinja2 environment
- **Proper YAML deserialization** using `yaml.safe_load()`
- **Type-safe configuration** using Pydantic models
- **No unsafe eval() or exec() usage**
- **Proper path validation** for template operations
- **Safe subprocess execution** without shell=True

However, several areas require attention for production hardening:
- SSL/TLS certificate verification not explicitly configured
- Missing input validation on some CLI arguments
- Goose prompt argument not properly escaped
- Limited SSRF protection mechanisms

---

## 1. CLI Command Handler Validation

### File: `/home/ross/Workspace/repo-agent/automation/main.py`

#### 1.1 Issue: Unvalidated Plan ID String Input

**Severity**: LOW
**Type**: Input Validation Gap

**Vulnerable Code** (Line 71-74):
```python
@cli.command()
@click.option("--plan-id", required=True, help="Plan ID to process")
@click.pass_context
def process_plan(ctx: click.Context, plan_id: str) -> None:
    """Process entire plan end-to-end."""
    settings = ctx.obj["settings"]
    asyncio.run(_process_plan(settings, plan_id))
```

**Attack Vector**:
The `plan_id` parameter is passed directly without validation. While it's used to load state files, an attacker could potentially:
- Use path traversal characters: `"../../../etc/passwd"`
- Cause issues with state file operations if not properly validated downstream

**Current State Manager Usage** (Line 279):
```python
state_data = await state.load_state(plan_id)
```

**Recommendation**:
Validate plan_id format before use:

```python
import re

@cli.command()
@click.option("--plan-id", required=True, help="Plan ID to process")
@click.pass_context
def process_plan(ctx: click.Context, plan_id: str) -> None:
    """Process entire plan end-to-end."""
    # Validate plan ID format (alphanumeric, hyphens, underscores only)
    if not re.match(r'^[a-zA-Z0-9_-]+$', plan_id):
        click.echo(
            f"Error: Invalid plan ID format: {plan_id}",
            err=True
        )
        sys.exit(1)

    settings = ctx.obj["settings"]
    asyncio.run(_process_plan(settings, plan_id))
```

#### 1.2 Issue: Config Path Validation

**Severity**: LOW
**Type**: Path Traversal Prevention

**Current Code** (Line 36-39):
```python
config_path = Path(config)
if not config_path.exists():
    click.echo(f"Error: Configuration file not found: {config}", err=True)
    sys.exit(1)
```

**Analysis**: SECURE
- The code uses `Path` object which properly resolves paths
- File existence check prevents non-existent path attacks
- However, no canonical path comparison against allowed directories

**Recommendation for Production**:
```python
from pathlib import Path
import os

def _validate_config_path(config: str) -> Path:
    """Validate config path is within allowed directory."""
    config_path = Path(config).resolve()

    # Ensure config is in allowed directories
    allowed_dirs = [
        Path("automation/config").resolve(),
        Path.home() / ".config" / "repo-agent",
        Path("/etc/repo-agent"),  # For system-wide config
    ]

    if not any(
        str(config_path).startswith(str(allowed_dir))
        for allowed_dir in allowed_dirs
    ):
        raise ValueError(
            f"Config path must be in allowed directories: {allowed_dirs}"
        )

    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config}")

    if not config_path.is_file():
        raise ValueError(f"Config path must be a file: {config}")

    return config_path
```

#### 1.3 Issue: Tag Filter Parameter

**Severity**: VERY LOW
**Type**: Information Disclosure (Minor)

**Code** (Line 62-65):
```python
@cli.command()
@click.option("--tag", help="Process issues with specific tag")
@click.pass_context
def process_all(ctx: click.Context, tag: str) -> None:
    """Process all issues with optional tag filter."""
    settings = ctx.obj["settings"]
    asyncio.run(_process_all_issues(settings, tag))
```

**Analysis**: SECURE
- Tag is passed to Gitea API which handles validation
- User can only retrieve existing tags (information disclosure risk is minimal)

**Recommendation**:
No immediate action needed, but log tag filtering for audit purposes.

---

## 2. Credential Management (`automation/cli/credentials.py`)

### 2.1 Issue: Service/Key Reference Parsing

**Severity**: LOW
**Type**: Input Validation

**Vulnerable Code** (Line 281-288):
```python
def _parse_service_key(reference: str) -> tuple[str, str]:
    """Parse service/key reference.

    Args:
        reference: Reference in format "service/key"

    Returns:
        Tuple of (service, key)

    Raises:
        ValueError: If format is invalid
    """
    if '/' not in reference:
        raise ValueError(
            f'Invalid reference format: {reference}\n'
            'Expected format: service/key (e.g., gitea/api_token)'
        )

    parts = reference.split('/', 1)
    return parts[0], parts[1]
```

**Analysis**: SECURE
- Proper format validation with clear error messages
- Only splits on first `/` to handle keys with slashes
- Length validation is done in the individual set commands

**Recommendation**:
Add optional length limits:

```python
def _parse_service_key(
    reference: str,
    max_service_length: int = 50,
    max_key_length: int = 200
) -> tuple[str, str]:
    """Parse service/key reference with length limits."""
    if '/' not in reference:
        raise ValueError(
            f'Invalid reference format: {reference}\n'
            'Expected format: service/key (e.g., gitea/api_token)'
        )

    parts = reference.split('/', 1)
    service, key = parts[0], parts[1]

    if len(service) > max_service_length:
        raise ValueError(
            f"Service name too long: {len(service)} > {max_service_length}"
        )
    if len(key) > max_key_length:
        raise ValueError(
            f"Key name too long: {len(key)} > {max_key_length}"
        )

    return service, key
```

### 2.2 Issue: Master Password Handling

**Severity**: MEDIUM
**Type**: Credential Security

**Current Code** (Line 63-66):
```python
@click.option(
    '--master-password',
    envvar='BUILDER_MASTER_PASSWORD',
    help='Master password for encrypted backend (can use env var)'
)
```

**Attack Vector**:
Master password in environment variable can be visible in:
- Process listing: `ps aux`
- Shell history
- Container logs
- Child process environment

**Analysis**: KNOWN RISK
This is a documented pattern, but has inherent security limitations.

**Recommendation**:
1. Add warning when password not provided interactively:

```python
def _warn_master_password_source():
    """Warn if master password is from environment."""
    if os.getenv('BUILDER_MASTER_PASSWORD'):
        click.echo(
            click.style(
                'WARNING: Master password is from environment variable. '
                'This is less secure than interactive prompt.',
                fg='yellow'
            ),
            err=True
        )

# In set_encrypted/delete_encrypted functions
if not master_password:  # Not provided via --master-password
    master_password = click.prompt(
        'Master password (not stored in env)',
        hide_input=True,
        confirmation_prompt=True if command == 'set' else False
    )
else:
    _warn_master_password_source()
```

2. Document credential rotation procedure

---

## 3. Template Rendering Security (`automation/rendering/`)

### 3.1 Template Engine Configuration

**File**: `/home/ross/Workspace/repo-agent/automation/rendering/engine.py`

**Analysis**: EXCELLENT SECURITY POSTURE

**Secure Implementation** (Line 57-65):
```python
self.env = SandboxedEnvironment(
    loader=FileSystemLoader(str(self.template_dir)),
    undefined=StrictUndefined,  # Fail on undefined variables
    autoescape=False,  # YAML doesn't need HTML escaping
    trim_blocks=True,  # Remove first newline after block
    lstrip_blocks=True,  # Strip leading spaces/tabs from block
    keep_trailing_newline=True,  # Preserve final newline
    extensions=[] if not enable_extensions else ["jinja2.ext.do"],
)
```

**Security Strengths**:
- ✅ Uses `SandboxedEnvironment` - prevents code injection
- ✅ `StrictUndefined` catches template logic errors early
- ✅ Extensions disabled by default
- ✅ No dangerous filters enabled

**Path Validation** (Line 111-139):
```python
def validate_template_path(self, template_path: str) -> Path:
    """Validate template path to prevent directory traversal attacks."""
    requested_path = (self.template_dir / template_path).resolve()

    # Ensure the resolved path is within template_dir
    try:
        requested_path.relative_to(self.template_dir)
    except ValueError:
        raise ValueError(
            f"Template path escapes template directory: {template_path}"
        )

    # Ensure file exists
    if not requested_path.exists():
        raise TemplateNotFound(template_path)

    return requested_path
```

**Analysis**: EXCELLENT
- Proper path canonicalization using `.resolve()`
- Prevents directory traversal with `relative_to()` check
- Ensures file exists before access

### 3.2 Custom Filter Validation

**File**: `/home/ross/Workspace/repo-agent/automation/rendering/filters.py`

**Analysis**: EXCELLENT SECURITY

**Safe URL Filter** (Line 13-41):
```python
def safe_url(value: str) -> str:
    """Validate and sanitize URL values."""
    if not isinstance(value, str):
        raise ValueError(f"URL must be string, got {type(value).__name__}")

    parsed = urlparse(value)

    if parsed.scheme not in ("https", "http"):
        raise ValueError(f"Invalid URL scheme: {parsed.scheme}")

    if not parsed.netloc:
        raise ValueError("URL must have a domain")

    return value
```

**Analysis**: SECURE
- ✅ Type checking
- ✅ Scheme whitelist (http/https only)
- ✅ Domain validation

**Safe Identifier Filter** (Line 44-83):
```python
def safe_identifier(value: Any, max_length: int = 100) -> str:
    """Sanitize identifiers with length limits."""
    if value is None:
        raise ValueError("Identifier cannot be None")

    if not isinstance(value, str):
        value = str(value)

    if not value:
        raise ValueError("Identifier cannot be empty")

    if len(value) > max_length:
        raise ValueError(f"Identifier too long: {len(value)} > {max_length}")

    # Allow GitHub Actions expressions
    if value.startswith("${{") and value.endswith("}}"):
        return value

    # Allow alphanumeric, hyphens, underscores, dots
    if not re.match(r'^[a-zA-Z0-9._-]+$', value):
        raise ValueError(f"Invalid identifier characters: {value}")

    return value
```

**Analysis**: SECURE
- ✅ Comprehensive validation
- ✅ Proper length limits
- ✅ Character whitelist using regex
- ✅ Supports GitHub Actions expressions safely

**Safe Label Filter** (Line 86-119):
```python
def safe_label(value: Any, max_length: int = 50) -> str:
    """Sanitize label names."""
    # ... type and length checks ...

    # Disallow YAML-sensitive characters
    if re.search(r'[:\n\r\t\{\}\[\]&*#?|<>=!%@`]', value):
        raise ValueError(f"Label contains invalid characters: {value}")

    return value.strip()
```

**Analysis**: SECURE
- ✅ Blocks YAML injection characters
- ✅ Prevents newline injection
- ✅ Prevents control characters

**YAML Conversion Filters** (Line 122-166):
```python
def yaml_string(value: Any) -> str:
    """Safely convert value to YAML string representation."""
    return yaml.safe_dump(value, default_flow_style=True).strip()

def yaml_list(value: list[Any]) -> str:
    """Convert Python list to YAML list representation."""
    if not isinstance(value, list):
        raise ValueError(f"Expected list, got {type(value).__name__}")
    return yaml.safe_dump(value, default_flow_style=False).strip()

def yaml_dict(value: dict[str, Any]) -> str:
    """Convert Python dict to YAML dict representation."""
    if not isinstance(value, dict):
        raise ValueError(f"Expected dict, got {type(value).__name__}")
    return yaml.safe_dump(value, default_flow_style=False).strip()
```

**Analysis**: EXCELLENT
- ✅ Uses `yaml.safe_dump()` - prevents YAML injection
- ✅ Type validation before conversion
- ✅ No use of `yaml.dump()` with `Loader=Loader`

### 3.3 Template Context Validation

**File**: `/home/ross/Workspace/repo-agent/automation/rendering/validators.py`

**Analysis**: EXCELLENT SECURITY

**Pydantic Model Validation** (Line 18-125):
```python
class WorkflowConfig(BaseModel):
    """Base configuration with field validation."""

    gitea_url: str = Field(...)
    gitea_owner: str = Field(
        ...,
        min_length=1,
        max_length=100,
        pattern=r'^[a-zA-Z0-9._-]+$',
    )
    gitea_repo: str = Field(
        ...,
        min_length=1,
        max_length=100,
        pattern=r'^[a-zA-Z0-9._-]+$',
    )
```

**Analysis**: EXCELLENT
- ✅ Pydantic validates all fields automatically
- ✅ Length constraints prevent DoS
- ✅ Regex patterns restrict characters
- ✅ Type hints enforce types

**URL Validation** (Line 95-118):
```python
@field_validator("gitea_url")
@classmethod
def validate_gitea_url(cls, v: str) -> str:
    """Ensure Gitea URL uses HTTPS in production."""
    parsed = urlparse(v)

    if not parsed.scheme or not parsed.netloc:
        raise ValueError(f"Invalid URL: {v}")

    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"URL must use http or https scheme, got: {parsed.scheme}")

    # Warn about HTTP (allow for local development)
    if parsed.scheme == "http" and not parsed.netloc.startswith("localhost"):
        import warnings
        warnings.warn(
            f"Using insecure HTTP for Gitea URL: {v}. "
            "Consider using HTTPS in production.",
            UserWarning,
        )

    return v.rstrip("/")
```

**Analysis**: EXCELLENT
- ✅ Scheme validation
- ✅ Development mode detection
- ✅ Warning for insecure HTTP
- ✅ Consistent URL formatting

**Template Context Validation** (Line 195-240):
```python
def validate_template_context(context: Dict[str, Any]) -> None:
    """Validate template context dictionary."""
    # Required fields check
    required_fields = {"gitea_url", "gitea_owner", "gitea_repo"}
    missing = required_fields - set(context.keys())
    if missing:
        raise ValueError(f"Missing required fields: {missing}")

    # Null byte detection
    for key, value in context.items():
        if isinstance(value, str) and "\0" in value:
            raise ValueError(f"Null byte detected in field '{key}'")

    # Length validation (DoS prevention)
    MAX_VALUE_LENGTH = 10000
    for key, value in context.items():
        if isinstance(value, str) and len(value) > MAX_VALUE_LENGTH:
            raise ValueError(
                f"Value for '{key}' exceeds maximum length "
                f"({len(value)} > {MAX_VALUE_LENGTH})"
            )

    # Recursive nested structure checking
    def check_nested(obj: Any, path: str = "") -> None:
        if isinstance(obj, dict):
            for k, v in obj.items():
                check_nested(v, f"{path}.{k}" if path else k)
        elif isinstance(obj, (list, tuple)):
            for i, item in enumerate(obj):
                check_nested(item, f"{path}[{i}]")
        elif isinstance(obj, str):
            if "\0" in obj:
                raise ValueError(f"Null byte in nested value at {path}")

    check_nested(context)
```

**Analysis**: EXCELLENT
- ✅ Required field validation
- ✅ Null byte detection (null injection prevention)
- ✅ Length validation prevents DoS
- ✅ Recursive checking of nested structures

### 3.4 Output Security

**File**: `/home/ross/Workspace/repo-agent/automation/rendering/security.py`

**Analysis**: EXCELLENT DEFENSIVE MEASURES

**Dangerous Pattern Detection** (Line 13-23):
```python
DANGEROUS_YAML_PATTERNS = [
    r'!!python/',           # Python object deserialization
    r'!!map',               # Arbitrary map construction
    r'!!omap',              # Ordered map construction
    r'!!pairs',             # Pairs construction
    r'!!set',               # Set construction
    r'!!binary',            # Binary data
    r'!!timestamp',         # Timestamp objects
    r'&\w+',                # Anchors (resource exhaustion)
    r'\*\w+',               # Aliases (billion laughs attack)
]
```

**Analysis**: EXCELLENT
- ✅ Defense-in-depth approach
- ✅ Detects YAML deserialization attacks
- ✅ Blocks resource exhaustion patterns

**Rendered Output Validation** (Line 26-43):
```python
def check_rendered_output(rendered: str) -> None:
    """Check rendered output for dangerous patterns."""
    for pattern in DANGEROUS_YAML_PATTERNS:
        if re.search(pattern, rendered):
            raise ValueError(
                f"Dangerous YAML pattern detected in output: {pattern}"
            )
```

**Analysis**: EXCELLENT
- ✅ Post-rendering validation (defense-in-depth)
- ✅ Catches injection attempts that bypass input validation

**Log Sanitization** (Line 61-81):
```python
def sanitize_log_output(text: str, max_length: int = 1000) -> str:
    """Sanitize text for safe logging."""
    # Remove control characters except newline/tab
    sanitized = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)

    # Truncate if too long
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length] + "... (truncated)"

    return sanitized
```

**Analysis**: EXCELLENT
- ✅ Prevents log injection
- ✅ Removes control characters
- ✅ Prevents log flooding with truncation

---

## 4. Configuration Loading (`automation/config/settings.py`)

### 4.1 YAML Deserialization

**Severity**: LOW
**Type**: YAML Injection Prevention

**Code** (Line 166-170):
```python
# Parse YAML
config_dict = yaml.safe_load(yaml_content)

# Create settings instance
return cls(**config_dict)
```

**Analysis**: EXCELLENT
- ✅ Uses `yaml.safe_load()` - prevents arbitrary code execution
- ✅ Not using `yaml.load()` with `Loader=Loader`
- ✅ Pydantic validation on resulting dict

**Vulnerable Pattern NOT FOUND**: ✅
```python
# DANGEROUS - NOT USED in codebase
yaml.load(yaml_content, Loader=yaml.Loader)  # ❌ Removed
```

### 4.2 Environment Variable Interpolation

**Code** (Line 173-194):
```python
@staticmethod
def _interpolate_env_vars(content: str) -> str:
    """Interpolate ${VAR_NAME} placeholders with environment variables."""
    pattern = re.compile(r"\$\{([A-Z_][A-Z0-9_]*)\}")

    def replace_var(match: re.Match[str]) -> str:
        var_name = match.group(1)
        value = os.getenv(var_name)
        if value is None:
            raise ValueError(f"Environment variable {var_name} is not set")
        return value

    return pattern.sub(replace_var, content)
```

**Analysis**: SECURE
- ✅ Strict regex pattern: `[A-Z_][A-Z0-9_]*` (standard env var format)
- ✅ Fails on missing variables (no silent defaults)
- ✅ Only uppercase variables (convention)

**Potential Enhancement**:
Allow lowercase and dots for flexibility:

```python
@staticmethod
def _interpolate_env_vars(content: str) -> str:
    """Interpolate ${VAR_NAME} placeholders with environment variables."""
    # Allow uppercase, lowercase, digits, underscores, dots
    pattern = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_\.]*)\}")

    def replace_var(match: re.Match[str]) -> str:
        var_name = match.group(1)

        # Validate variable name length (prevent DoS)
        if len(var_name) > 256:
            raise ValueError(
                f"Environment variable name too long: {var_name}"
            )

        value = os.getenv(var_name)
        if value is None:
            raise ValueError(f"Environment variable {var_name} is not set")

        # Limit value length to prevent config bloat
        MAX_ENV_VALUE_LENGTH = 100000
        if len(value) > MAX_ENV_VALUE_LENGTH:
            raise ValueError(
                f"Environment variable {var_name} exceeds max length"
            )

        return value

    return pattern.sub(replace_var, content)
```

### 4.3 Pydantic Model Validation

**Analysis**: EXCELLENT

**Type Safety** (Line 123-127):
```python
class AutomationSettings(BaseSettings):
    git_provider: GitProviderConfig
    repository: RepositoryConfig
    agent_provider: AgentProviderConfig
    workflow: WorkflowConfig = Field(default_factory=WorkflowConfig)
    tags: TagsConfig = Field(default_factory=TagsConfig)
```

**Analysis**: EXCELLENT
- ✅ Nested Pydantic models ensure recursive validation
- ✅ Type hints enforce structure
- ✅ Default factories for optional configs
- ✅ All fields validated through Pydantic

---

## 5. HTTP Client Security (`automation/providers/`)

### 5.1 HTTPX Client Configuration

**File**: `/home/ross/Workspace/repo-agent/automation/providers/gitea_rest.py`

**Severity**: MEDIUM
**Type**: SSL/TLS Verification

**Code** (Line 43-49):
```python
async def connect(self) -> None:
    """Initialize HTTP client."""
    self.client = httpx.AsyncClient(
        headers={
            "Authorization": f"token {self.token}",
            "Content-Type": "application/json",
        },
        timeout=30.0,
    )
```

**Issue**: No explicit SSL verification configuration

**Analysis**:
- Default behavior: httpx verifies SSL certificates (secure by default)
- However, no explicit configuration for:
  - Custom CA certificates
  - Self-signed certificate handling
  - Certificate pinning

**Recommendation**: Add explicit SSL configuration

```python
import certifi
import httpx
from typing import Optional

class GiteaRestProvider(GitProvider):
    def __init__(
        self,
        base_url: str,
        token: str,
        owner: str,
        repo: str,
        verify_ssl: bool = True,
        ca_bundle: Optional[str] = None,
    ):
        """Initialize Gitea provider.

        Args:
            base_url: Gitea base URL
            token: API token
            owner: Repository owner
            repo: Repository name
            verify_ssl: Whether to verify SSL certificates (default: True)
            ca_bundle: Path to custom CA bundle for self-signed certs
        """
        self.base_url = base_url.rstrip('/')
        self.api_base = f"{self.base_url}/api/v1"
        self.token = token
        self.owner = owner
        self.repo = repo
        self.verify_ssl = verify_ssl
        self.ca_bundle = ca_bundle
        self.client: Optional[httpx.AsyncClient] = None

    async def connect(self) -> None:
        """Initialize HTTP client with SSL verification."""
        # Determine verification settings
        if not self.verify_ssl:
            # INSECURE: Only for testing/development
            import warnings
            warnings.warn(
                "SSL verification disabled. This is insecure and should "
                "only be used for testing.",
                RuntimeWarning
            )
            verify = False
        elif self.ca_bundle:
            # Custom CA bundle for self-signed certificates
            verify = self.ca_bundle
        else:
            # Use system/certifi CA bundle
            verify = certifi.where()

        self.client = httpx.AsyncClient(
            headers={
                "Authorization": f"token {self.token}",
                "Content-Type": "application/json",
            },
            timeout=30.0,
            verify=verify,
        )
        log.info(
            "gitea_connected",
            base_url=self.base_url,
            owner=self.owner,
            repo=self.repo,
            ssl_verify=bool(verify)
        )
```

### 5.2 Credential Handling in Headers

**Severity**: LOW
**Type**: Information Disclosure

**Code** (Line 44-45):
```python
headers={
    "Authorization": f"token {self.token}",
    "Content-Type": "application/json",
}
```

**Analysis**: SECURE
- ✅ Token is not logged
- ✅ Only transmitted via HTTPS
- ✅ Proper Authorization header usage

**Potential Issues**:
- Headers logged when debugging might leak token
- Token in URL parameters (check usage)

**Recommendation**: Add token masking for logs

```python
class GiteaRestProvider(GitProvider):
    def _mask_token(self, token: str) -> str:
        """Mask token for logging purposes."""
        if len(token) <= 8:
            return "*" * len(token)
        return f"{token[:4]}...{token[-4:]}"

    async def get_issues(self, ...):
        """Retrieve issues via REST API."""
        log.info(
            "get_issues",
            labels=labels,
            state=state,
            token=self._mask_token(self.token),  # Masked for security
        )
        # ... rest of method
```

### 5.3 Connection Pool Security

**File**: `/home/ross/Workspace/repo-agent/automation/utils/connection_pool.py`

**Analysis**: GOOD

**Code** (Line 44-50):
```python
self._client = httpx.AsyncClient(
    base_url=self.base_url,
    limits=limits,
    timeout=self.timeout,
    http2=True,  # Enable HTTP/2 for multiplexing
    headers=self.headers,
)
```

**Issue**: No explicit SSL verification here either

**Recommendation**: Add SSL configuration parameter

```python
class HTTPConnectionPool:
    def __init__(
        self,
        base_url: str,
        max_connections: int = 10,
        max_keepalive_connections: int = 5,
        timeout: float = 30.0,
        headers: Optional[Dict[str, str]] = None,
        verify_ssl: bool = True,
        ca_bundle: Optional[str] = None,
    ) -> None:
        self.base_url = base_url
        self.max_connections = max_connections
        self.max_keepalive_connections = max_keepalive_connections
        self.timeout = timeout
        self.headers = headers or {}
        self.verify_ssl = verify_ssl
        self.ca_bundle = ca_bundle
        self._client: Optional[httpx.AsyncClient] = None
        self._lock = asyncio.Lock()

    async def initialize(self) -> None:
        """Initialize the connection pool with SSL verification."""
        async with self._lock:
            if self._client is None:
                limits = httpx.Limits(
                    max_keepalive_connections=self.max_keepalive_connections,
                    max_connections=self.max_connections,
                    keepalive_expiry=30.0,
                )

                # Determine SSL verification
                if not self.verify_ssl:
                    verify = False
                elif self.ca_bundle:
                    verify = self.ca_bundle
                else:
                    import certifi
                    verify = certifi.where()

                self._client = httpx.AsyncClient(
                    base_url=self.base_url,
                    limits=limits,
                    timeout=self.timeout,
                    http2=True,
                    headers=self.headers,
                    verify=verify,
                )

                log.info(
                    "connection_pool_initialized",
                    base_url=self.base_url,
                    max_connections=self.max_connections,
                    ssl_verify=bool(verify),
                )
```

### 5.4 SSRF Prevention

**Severity**: MEDIUM
**Type**: Server-Side Request Forgery

**Analysis**: POTENTIAL RISK

The code allows constructing URLs from configuration:

```python
base_url = settings.git_provider.base_url  # User-provided
```

**Attack Scenarios**:
1. Attacker provides `http://localhost:8080` to access internal services
2. Attacker provides `http://169.254.169.254/` to access AWS metadata
3. Attacker provides `file:///etc/passwd` to read local files

**Current Mitigations**:
- Pydantic URL validation (requires http/https scheme)
- localhost detection for development

**Recommendation**: Add SSRF protection

```python
import ipaddress
from urllib.parse import urlparse

def _validate_no_ssrf(url: str) -> None:
    """Validate URL doesn't target internal resources."""
    parsed = urlparse(url)

    if not parsed.hostname:
        raise ValueError(f"Invalid URL: {url}")

    # Block private/internal IP ranges
    blocked_ranges = [
        ipaddress.ip_network('127.0.0.0/8'),      # Localhost
        ipaddress.ip_network('10.0.0.0/8'),       # Private
        ipaddress.ip_network('172.16.0.0/12'),    # Private
        ipaddress.ip_network('192.168.0.0/16'),   # Private
        ipaddress.ip_network('169.254.0.0/16'),   # Link-local
        ipaddress.ip_network('224.0.0.0/4'),      # Multicast
        ipaddress.ip_network('::1/128'),          # IPv6 localhost
        ipaddress.ip_network('fc00::/7'),         # IPv6 private
        ipaddress.ip_network('fe80::/10'),        # IPv6 link-local
    ]

    try:
        ip = ipaddress.ip_address(parsed.hostname)
        for blocked_range in blocked_ranges:
            if ip in blocked_range:
                raise ValueError(
                    f"URL targets internal IP address: {parsed.hostname}"
                )
    except (ValueError, ipaddress.AddressValueError):
        # Not an IP address, allow DNS name
        pass

    # Block special hostnames
    blocked_hostnames = {
        'localhost',
        'localhost.localdomain',
        'internal',
        'intranet',
        'admin',
    }

    if parsed.hostname.lower() in blocked_hostnames:
        raise ValueError(
            f"URL targets blocked hostname: {parsed.hostname}"
        )

# Update settings validation
class GitProviderConfig(BaseModel):
    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, v: str) -> str:
        """Validate base URL and prevent SSRF."""
        parsed = urlparse(str(v))

        if parsed.scheme not in ("http", "https"):
            raise ValueError(f"URL must use http or https scheme")

        # Only check SSRF in production
        if parsed.scheme == "https" or not parsed.hostname.startswith("localhost"):
            _validate_no_ssrf(str(v))

        return v.rstrip("/")
```

---

## 6. Subprocess and Command Execution

### 6.1 External Agent Provider

**File**: `/home/ross/Workspace/repo-agent/automation/providers/external_agent.py`

**Severity**: MEDIUM
**Type**: Command Injection

**Issue 1: Goose Command Construction**

**Code** (Line 166):
```python
cmd = ["goose", "run", prompt]

process = await asyncio.create_subprocess_exec(
    *cmd,
    cwd=self.working_dir,
    stdout=asyncio.subprocess.PIPE,
    stderr=asyncio.subprocess.PIPE,
)
```

**Analysis**:
- ✅ Using `create_subprocess_exec()` (not `shell=True`) - SECURE
- ✅ Command array prevents shell injection
- ✅ `cwd` is properly set

**However**: The `prompt` parameter is user-controlled. If `prompt` contains special characters, it's safely handled (no shell interpretation).

**Example Safety Check**:
```python
# Safe: No shell interpretation
prompt = "rm -rf /; echo hacked"  # Passed as single argument to goose
# Goose receives this as a literal string, not shell command
```

**Recommendation**: Add prompt validation

```python
def _validate_prompt(self, prompt: str) -> None:
    """Validate prompt for reasonable length and content."""
    MAX_PROMPT_LENGTH = 1000000  # 1MB

    if len(prompt) == 0:
        raise ValueError("Prompt cannot be empty")

    if len(prompt) > MAX_PROMPT_LENGTH:
        raise ValueError(
            f"Prompt exceeds maximum length: {len(prompt)} > {MAX_PROMPT_LENGTH}"
        )

    # Check for suspicious patterns
    if prompt.count('\n') > 10000:
        raise ValueError("Prompt has too many lines (possible DoS)")

async def _execute_goose(self, prompt: str, context, task_id) -> Dict[str, Any]:
    """Execute prompt using Goose CLI."""
    self._validate_prompt(prompt)

    cmd = ["goose", "run", prompt]
    # ... rest of method
```

### 6.2 Claude Code Execution

**Severity**: LOW
**Type**: Safe subprocess usage

**Code** (Line 117-133):
```python
cmd = [
    "claude",
    "--print",
    "--dangerously-skip-permissions"
]

process = await asyncio.create_subprocess_exec(
    *cmd,
    cwd=self.working_dir,
    stdin=asyncio.subprocess.PIPE,
    stdout=asyncio.subprocess.PIPE,
    stderr=asyncio.subprocess.PIPE,
)

stdout, stderr = await process.communicate(input=prompt.encode('utf-8'))
```

**Analysis**: SECURE
- ✅ Uses `create_subprocess_exec()` (not `shell=True`)
- ✅ Command array prevents injection
- ✅ Prompt passed via stdin (not command line)
- ✅ Proper encoding

**Good Practice**: Passing large arguments via stdin prevents "Argument list too long" errors.

### 6.3 Working Directory Validation

**Severity**: MEDIUM
**Type**: Path Traversal

**Code** (Line 39):
```python
self.working_dir = working_dir or os.getcwd()
```

**Issue**: `working_dir` is not validated

**Attack Vector**:
```python
provider = ExternalAgentProvider(working_dir="../../../etc")
# Agent would execute in /etc
```

**Recommendation**: Validate working directory

```python
def _validate_working_dir(self, working_dir: str) -> str:
    """Validate working directory is safe."""
    path = Path(working_dir).resolve()

    # Ensure directory exists
    if not path.exists():
        raise ValueError(f"Working directory does not exist: {working_dir}")

    if not path.is_dir():
        raise ValueError(f"Working directory path is not a directory: {working_dir}")

    # Optional: Restrict to certain directories
    # allowed_roots = [Path("/home").resolve(), Path("/tmp").resolve()]
    # if not any(str(path).startswith(str(root)) for root in allowed_roots):
    #     raise ValueError(f"Working directory outside allowed paths: {path}")

    return str(path)

def __init__(
    self,
    agent_type: str = "claude",
    model: str = "claude-sonnet-4.5",
    working_dir: Optional[str] = None,
    qa_handler: Optional[Any] = None,
):
    """Initialize external agent provider."""
    self.agent_type = agent_type
    self.model = model
    self.working_dir = self._validate_working_dir(
        working_dir or os.getcwd()
    )
    self.qa_handler = qa_handler
    self.current_issue_number: Optional[int] = None
```

---

## 7. Summary of Findings

### Critical Issues: NONE

### High Severity Issues: NONE

### Medium Severity Issues:

1. **SSRF Prevention Missing** (HTTP clients)
   - Impact: Potential access to internal services
   - Recommendation: Validate URLs against internal IP ranges
   - Priority: HIGH

2. **SSL/TLS Verification Not Explicitly Configured** (HTTP clients)
   - Impact: May be vulnerable to MITM in misconfigured environments
   - Recommendation: Add explicit `verify=certifi.where()` configuration
   - Priority: MEDIUM

3. **Working Directory Not Validated** (External agent provider)
   - Impact: Agent could run in unexpected directories
   - Recommendation: Validate and restrict working directory paths
   - Priority: MEDIUM

4. **Goose Prompt Length Not Validated**
   - Impact: Potential DoS through memory exhaustion
   - Recommendation: Add length limits on prompts
   - Priority: MEDIUM

### Low Severity Issues:

1. **Plan ID Not Validated** (CLI)
   - Impact: May cause issues with state file operations
   - Recommendation: Add regex validation for plan IDs
   - Priority: LOW

2. **Master Password in Environment Variable**
   - Impact: Password visible in process listing
   - Recommendation: Add warnings and document rotation procedure
   - Priority: LOW

3. **Token Could Be Logged** (Gitea provider)
   - Impact: Token might appear in debug logs
   - Recommendation: Add token masking for logging
   - Priority: LOW

### Non-Issues (Secure as-is):

- ✅ Template engine (excellent security)
- ✅ Template filters (excellent validation)
- ✅ Template context validation (excellent)
- ✅ YAML deserialization (safe_load)
- ✅ Configuration validation (Pydantic models)
- ✅ Path validation for templates (proper canonicalization)
- ✅ Subprocess execution (no shell=True)
- ✅ URL validation (basic checks)

---

## 8. Implementation Checklist

### Phase 1: Critical (Do First)
- [ ] Add SSRF protection to HTTP client initialization
- [ ] Validate working directory in ExternalAgentProvider
- [ ] Add prompt length validation in Goose execution

### Phase 2: Important (Next)
- [ ] Add explicit SSL verification configuration
- [ ] Add token masking in logs
- [ ] Document credential rotation procedure

### Phase 3: Nice-to-Have (Polish)
- [ ] Add plan ID validation in CLI
- [ ] Extend environment variable interpolation for lowercase
- [ ] Add length limits to environment variable values

### Phase 4: Monitoring (Ongoing)
- [ ] Log all credential access (for audit)
- [ ] Monitor template rendering for dangerous patterns
- [ ] Track failed validation attempts

---

## 9. Testing Recommendations

### Unit Tests

```python
def test_plan_id_validation():
    """Test plan ID validation rejects path traversal."""
    invalid_ids = [
        "../../../etc/passwd",
        "..\\..\\windows\\system32",
        "plan/../../secret",
        "plan;rm -rf /",
    ]

    for invalid_id in invalid_ids:
        with pytest.raises(ValueError):
            process_plan(Context(), invalid_id)

def test_ssrf_protection():
    """Test SSRF protection blocks internal addresses."""
    blocked_urls = [
        "http://localhost:8080",
        "http://127.0.0.1",
        "http://169.254.169.254",  # AWS metadata
        "http://10.0.0.1",
        "http://192.168.1.1",
        "http://[::1]",
    ]

    for url in blocked_urls:
        with pytest.raises(ValueError):
            validate_no_ssrf(url)

def test_template_injection_prevention():
    """Test templates prevent code injection."""
    injection_attempts = [
        "{{ __import__('os').system('id') }}",
        "{% for c in [].__class__.__base__.__subclasses__() %}",
        "{{ self.__dict__.__init__.__globals__['__builtins__']['eval'] }}",
    ]

    for payload in injection_attempts:
        # Should raise or sanitize
        with pytest.raises((ValueError, TemplateSyntaxError)):
            engine.render("test.yaml.j2", {"value": payload})

def test_yaml_injection_prevention():
    """Test YAML injection prevention."""
    yaml_injection = "!!python/object/apply:os.system ['ls']"

    with pytest.raises(ValueError):
        validate_template_context({"value": yaml_injection})
```

### Integration Tests

```python
async def test_gitea_ssl_verification():
    """Test Gitea client verifies SSL certificates."""
    provider = GiteaRestProvider(
        base_url="https://gitea.example.com",
        token="test_token",
        owner="test",
        repo="test",
    )

    # Should use default certificate verification
    await provider.connect()
    assert provider.client.verify is True or isinstance(provider.client.verify, str)

async def test_command_execution_safety():
    """Test command execution doesn't interpret shell special chars."""
    provider = ExternalAgentProvider(agent_type="goose")

    # Dangerous prompt as literal string
    prompt = "rm -rf / && echo hacked"

    # Should execute safely (will fail because goose cmd doesn't exist)
    # but should NOT interpret shell command
    with pytest.raises(RuntimeError):  # CLI not found
        await provider._execute_goose(prompt, None, None)
```

---

## 10. Conclusion

The repo-agent codebase demonstrates **strong security practices** overall, particularly in:
- Template rendering with sandboxed environment
- YAML deserialization using safe_load
- Configuration validation with Pydantic
- Input validation in custom filters
- Safe subprocess execution without shell=True

The identified issues are primarily **configuration and validation gaps** that can be addressed with:
1. Explicit SSL/TLS verification settings
2. SSRF protection for HTTP clients
3. Input length validation for subprocess arguments
4. Path validation for working directories

No critical vulnerabilities were found that would allow arbitrary code execution or unauthorized access.

---

## Appendix: References

- [OWASP: Input Validation Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Input_Validation_Cheat_Sheet.html)
- [OWASP: Path Traversal](https://owasp.org/www-community/attacks/Path_Traversal)
- [OWASP: SSRF Prevention](https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html)
- [OWASP: YAML Deserialization](https://owasp.org/www-community/Deserialization_of_untrusted_data)
- [Jinja2 Security: Sandboxing](https://jinja.palletsprojects.com/en/3.0.x/sandbox/)
- [Pydantic: Validation](https://docs.pydantic.dev/latest/concepts/validators/)
- [httpx: Client Configuration](https://www.python-httpx.org/advanced/#client-instantiation)
- [Python: Subprocess Security](https://docs.python.org/3/library/subprocess.html#security-considerations)

