#!/usr/bin/env python3
"""Verification script for credential management system implementation.

This script verifies that all components of the credential management system
are properly implemented and accessible.
"""

import sys
from pathlib import Path


def check_file(path: Path, description: str) -> bool:
    """Check if a file exists and report."""
    exists = path.exists()
    status = "✓" if exists else "✗"
    print(f"{status} {description}: {path}")
    return exists


def check_import(module: str, description: str) -> bool:
    """Check if a module can be imported."""
    try:
        __import__(module)
        print(f"✓ {description}: {module}")
        return True
    except ImportError as e:
        print(f"✗ {description}: {module} - {e}")
        return False


def main():
    """Run verification checks."""
    print("=" * 70)
    print("Credential Management System - Verification Report")
    print("=" * 70)
    print()

    checks_passed = 0
    checks_total = 0

    # Core implementation files
    print("Core Implementation Files:")
    print("-" * 70)

    core_files = [
        ("automation/credentials/__init__.py", "Package initialization"),
        ("automation/credentials/exceptions.py", "Exception hierarchy"),
        ("automation/credentials/backend.py", "Backend protocol"),
        ("automation/credentials/keyring_backend.py", "Keyring backend"),
        ("automation/credentials/environment_backend.py", "Environment backend"),
        ("automation/credentials/encrypted_backend.py", "Encrypted file backend"),
        ("automation/credentials/resolver.py", "Credential resolver"),
    ]

    for file_path, desc in core_files:
        checks_total += 1
        if check_file(Path(file_path), desc):
            checks_passed += 1

    print()

    # Integration files
    print("Integration Files:")
    print("-" * 70)

    integration_files = [
        ("automation/config/credential_fields.py", "Pydantic field types"),
        ("automation/cli/credentials.py", "CLI commands"),
    ]

    for file_path, desc in integration_files:
        checks_total += 1
        if check_file(Path(file_path), desc):
            checks_passed += 1

    print()

    # Test files
    print("Test Files:")
    print("-" * 70)

    test_files = [
        ("tests/test_credentials/__init__.py", "Test package init"),
        ("tests/test_credentials/test_exceptions.py", "Exception tests"),
        ("tests/test_credentials/test_keyring_backend.py", "Keyring tests"),
        ("tests/test_credentials/test_environment_backend.py", "Environment tests"),
        ("tests/test_credentials/test_encrypted_backend.py", "Encrypted tests"),
        ("tests/test_credentials/test_resolver.py", "Resolver tests"),
        ("tests/test_credentials/test_integration.py", "Integration tests"),
        ("tests/test_credentials/test_security.py", "Security tests"),
    ]

    for file_path, desc in test_files:
        checks_total += 1
        if check_file(Path(file_path), desc):
            checks_passed += 1

    print()

    # Documentation files
    print("Documentation Files:")
    print("-" * 70)

    doc_files = [
        ("CREDENTIAL_SYSTEM_IMPLEMENTATION_SUMMARY.md", "Implementation summary"),
        ("docs/CREDENTIAL_QUICK_START.md", "Quick start guide"),
        ("plans/credential-management-implementation.md", "Implementation plan"),
    ]

    for file_path, desc in doc_files:
        checks_total += 1
        if check_file(Path(file_path), desc):
            checks_passed += 1

    print()

    # Import checks
    print("Module Imports:")
    print("-" * 70)

    imports = [
        ("automation.credentials", "Main package"),
        ("automation.credentials.exceptions", "Exceptions module"),
        ("automation.credentials.backend", "Backend protocol"),
        ("automation.credentials.keyring_backend", "Keyring backend"),
        ("automation.credentials.environment_backend", "Environment backend"),
        ("automation.credentials.encrypted_backend", "Encrypted backend"),
        ("automation.credentials.resolver", "Credential resolver"),
        ("automation.config.credential_fields", "Pydantic fields"),
        ("automation.cli.credentials", "CLI commands"),
    ]

    for module, desc in imports:
        checks_total += 1
        if check_import(module, desc):
            checks_passed += 1

    print()

    # Functional checks
    print("Functional Checks:")
    print("-" * 70)

    try:
        from automation.credentials import (
            CredentialResolver,
            KeyringBackend,
            EnvironmentBackend,
            EncryptedFileBackend,
        )

        # Test resolver initialization
        checks_total += 1
        try:
            resolver = CredentialResolver()
            print(f"✓ CredentialResolver initialization")
            checks_passed += 1
        except Exception as e:
            print(f"✗ CredentialResolver initialization: {e}")

        # Test backend initialization
        backends = [
            (KeyringBackend, "KeyringBackend"),
            (EnvironmentBackend, "EnvironmentBackend"),
        ]

        for backend_class, name in backends:
            checks_total += 1
            try:
                backend = backend_class()
                print(f"✓ {name} initialization")
                checks_passed += 1
            except Exception as e:
                print(f"✗ {name} initialization: {e}")

        # Test EncryptedFileBackend with temp path
        checks_total += 1
        try:
            from tempfile import TemporaryDirectory
            with TemporaryDirectory() as tmpdir:
                backend = EncryptedFileBackend(
                    Path(tmpdir) / "test.enc",
                    "test-password"
                )
                print(f"✓ EncryptedFileBackend initialization")
                checks_passed += 1
        except Exception as e:
            print(f"✗ EncryptedFileBackend initialization: {e}")

        # Test reference parsing
        checks_total += 1
        try:
            assert resolver.KEYRING_PATTERN.match("@keyring:service/key")
            assert resolver.ENV_PATTERN.match("${VAR_NAME}")
            assert resolver.ENCRYPTED_PATTERN.match("@encrypted:service/key")
            print(f"✓ Reference pattern matching")
            checks_passed += 1
        except Exception as e:
            print(f"✗ Reference pattern matching: {e}")

    except ImportError as e:
        print(f"✗ Cannot import credential modules: {e}")
        checks_total += 5  # Account for skipped checks

    print()

    # CLI integration check
    print("CLI Integration:")
    print("-" * 70)

    checks_total += 1
    try:
        from automation.main import cli
        from automation.cli.credentials import credentials_group

        # Check if credentials command is registered
        if 'credentials' in cli.commands:
            print(f"✓ Credentials command group registered in main CLI")
            checks_passed += 1
        else:
            print(f"✗ Credentials command group not registered in main CLI")
    except Exception as e:
        print(f"✗ CLI integration check: {e}")

    print()

    # Summary
    print("=" * 70)
    print("Summary")
    print("=" * 70)

    percentage = (checks_passed / checks_total * 100) if checks_total > 0 else 0

    print(f"Total checks: {checks_total}")
    print(f"Passed: {checks_passed}")
    print(f"Failed: {checks_total - checks_passed}")
    print(f"Success rate: {percentage:.1f}%")
    print()

    if checks_passed == checks_total:
        print("✓ ALL CHECKS PASSED - Credential system fully implemented!")
        return 0
    else:
        print(f"✗ {checks_total - checks_passed} checks failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
