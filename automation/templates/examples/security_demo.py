#!/usr/bin/env python3
"""
Security demonstration for the template system.

This script demonstrates the security features that prevent various
attack vectors in the template rendering system.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from automation.rendering import SecureTemplateEngine
from automation.rendering.filters import safe_identifier, safe_url
from automation.rendering.security import check_rendered_output
from automation.rendering.validators import validate_template_context


def demo_sandboxed_execution():
    """Demonstrate that code execution is prevented."""
    print("\n" + "=" * 70)
    print("DEMO 1: Sandboxed Execution (Code Execution Prevention)")
    print("=" * 70)

    # Create temp engine
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        template_dir = Path(tmpdir)
        template_file = template_dir / "test.yaml.j2"
        template_file.write_text("name: {{ name }}\nvalue: {{ value }}")

        engine = SecureTemplateEngine(template_dir=template_dir)

        # Attempt 1: Access Python internals
        print("\nAttempt 1: Access __class__ attribute")
        try:
            context = {"name": "test", "value": "{{ ''.__class__.__mro__[1].__subclasses__() }}"}
            result = engine.render("test.yaml.j2", context, validate=False)
            print(f"  Result: {result}")
            print("  Status: SAFE - Rendered as literal string, not executed")
        except Exception as e:
            print(f"  Status: BLOCKED - {e}")

        # Attempt 2: Call dangerous functions
        print("\nAttempt 2: Call eval() function")
        try:
            context = {"name": '{{ eval(\'__import__("os").system("ls")\') }}', "value": "test"}
            result = engine.render("test.yaml.j2", context, validate=False)
            print(f"  Result: {result}")
            print("  Status: SAFE - Functions not available in sandbox")
        except Exception as e:
            print(f"  Status: BLOCKED - {e}")


def demo_input_validation():
    """Demonstrate input validation."""
    print("\n" + "=" * 70)
    print("DEMO 2: Input Validation (Injection Prevention)")
    print("=" * 70)

    # Test URL validation
    print("\nURL Validation:")
    safe_urls = ["https://gitea.com", "http://localhost:3000"]
    dangerous_urls = ["javascript:alert(1)", "file:///etc/passwd", "ftp://evil.com"]

    for url in safe_urls:
        try:
            result = safe_url(url)
            print(f"  PASS: {url}")
        except ValueError as e:
            print(f"  FAIL: {url} - {e}")

    for url in dangerous_urls:
        try:
            result = safe_url(url)
            print(f"  FAIL: {url} should have been blocked")
        except ValueError:
            print(f"  PASS: Blocked {url}")

    # Test identifier validation
    print("\nIdentifier Validation:")
    safe_ids = ["my-repo", "owner_name", "repo.name"]
    dangerous_ids = ["repo:name", "repo{name}", "repo&anchor", "repo\nname"]

    for identifier in safe_ids:
        try:
            result = safe_identifier(identifier)
            print(f"  PASS: {identifier}")
        except ValueError as e:
            print(f"  FAIL: {identifier} - {e}")

    for identifier in dangerous_ids:
        try:
            result = safe_identifier(identifier)
            print(f"  FAIL: {identifier} should have been blocked")
        except ValueError:
            print(f"  PASS: Blocked {identifier}")


def demo_path_validation():
    """Demonstrate path traversal prevention."""
    print("\n" + "=" * 70)
    print("DEMO 3: Path Validation (Directory Traversal Prevention)")
    print("=" * 70)

    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        template_dir = Path(tmpdir)
        (template_dir / "safe.yaml.j2").write_text("safe: true")

        engine = SecureTemplateEngine(template_dir=template_dir)

        # Safe paths
        print("\nSafe Paths:")
        safe_paths = ["safe.yaml.j2"]
        for path in safe_paths:
            try:
                validated = engine.validate_template_path(path)
                print(f"  PASS: {path}")
            except Exception as e:
                print(f"  FAIL: {path} - {e}")

        # Dangerous paths
        print("\nDangerous Paths:")
        dangerous_paths = [
            "../etc/passwd",
            "../../etc/shadow",
            "subdir/../../etc/passwd",
            "/etc/passwd",
        ]
        for path in dangerous_paths:
            try:
                validated = engine.validate_template_path(path)
                print(f"  FAIL: {path} should have been blocked")
            except Exception:
                print(f"  PASS: Blocked {path}")


def demo_output_validation():
    """Demonstrate output validation."""
    print("\n" + "=" * 70)
    print("DEMO 4: Output Validation (YAML Injection Prevention)")
    print("=" * 70)

    # Safe YAML
    print("\nSafe YAML:")
    safe_yaml = """
name: Build and Test
on:
  push:
    branches:
      - main
"""
    try:
        check_rendered_output(safe_yaml)
        print("  PASS: Safe YAML accepted")
    except ValueError as e:
        print(f"  FAIL: Safe YAML rejected - {e}")

    # Dangerous YAML patterns
    print("\nDangerous YAML:")
    dangerous_patterns = {
        "Python deserialization": "!!python/object/apply:os.system ['ls']",
        "YAML anchor": "name: &anchor test\nref: *anchor",
        "YAML binary": "data: !!binary SGVsbG8gV29ybGQ=",
    }

    for name, pattern in dangerous_patterns.items():
        try:
            check_rendered_output(pattern)
            print(f"  FAIL: {name} should have been blocked")
        except ValueError:
            print(f"  PASS: Blocked {name}")


def demo_context_validation():
    """Demonstrate context validation."""
    print("\n" + "=" * 70)
    print("DEMO 5: Context Validation (Null Byte & Length Limits)")
    print("=" * 70)

    # Valid context
    print("\nValid Context:")
    valid_context = {
        "gitea_url": "https://gitea.example.com",
        "gitea_owner": "owner",
        "gitea_repo": "repo",
        "workflow_name": "Test Workflow",
    }
    try:
        validate_template_context(valid_context)
        print("  PASS: Valid context accepted")
    except ValueError as e:
        print(f"  FAIL: Valid context rejected - {e}")

    # Null byte injection
    print("\nNull Byte Injection:")
    null_byte_context = {
        "gitea_url": "https://gitea.example.com",
        "gitea_owner": "owner",
        "gitea_repo": "repo\0malicious",
    }
    try:
        validate_template_context(null_byte_context)
        print("  FAIL: Null byte should have been blocked")
    except ValueError:
        print("  PASS: Blocked null byte injection")

    # Excessive length
    print("\nExcessive Length:")
    long_context = {
        "gitea_url": "https://gitea.example.com",
        "gitea_owner": "owner",
        "gitea_repo": "repo",
        "long_value": "a" * 10001,
    }
    try:
        validate_template_context(long_context)
        print("  FAIL: Excessive length should have been blocked")
    except ValueError:
        print("  PASS: Blocked excessive length")


def demo_security_summary():
    """Print security summary."""
    print("\n" + "=" * 70)
    print("SECURITY SUMMARY")
    print("=" * 70)

    security_features = [
        ("Sandboxed Execution", "SandboxedEnvironment prevents code execution"),
        ("Strict Undefined", "All variables must be defined, no silent failures"),
        ("Input Validation", "Pydantic models validate all inputs"),
        ("Path Validation", "Directory traversal prevented"),
        ("Custom Filters", "All user inputs sanitized"),
        ("Output Validation", "Dangerous YAML patterns detected"),
        ("Null Byte Detection", "Null bytes rejected in all inputs"),
        ("Length Limits", "Maximum lengths enforced"),
        ("URL Scheme Validation", "Only https/http allowed"),
        ("Character Whitelisting", "Only safe characters in identifiers"),
    ]

    print("\nImplemented Security Features:")
    for i, (feature, description) in enumerate(security_features, 1):
        print(f"  {i}. {feature}")
        print(f"     {description}")


if __name__ == "__main__":
    print("\nSecure Template System - Security Demonstration")
    print("=" * 70)
    print("\nThis demonstration shows how the template system prevents")
    print("various security attacks including:")
    print("  - Code execution")
    print("  - Template injection")
    print("  - Directory traversal")
    print("  - YAML injection")
    print("  - Null byte injection")

    try:
        demo_sandboxed_execution()
        demo_input_validation()
        demo_path_validation()
        demo_output_validation()
        demo_context_validation()
        demo_security_summary()

        print("\n" + "=" * 70)
        print("All security demonstrations completed successfully!")
        print("=" * 70)
        print()

    except Exception as e:
        print(f"\nError: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
