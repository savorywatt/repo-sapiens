#!/usr/bin/env python3
"""
Test script to verify the hello_python_test package works correctly.

Run this after installing the package:
    pip install dist/hello_python_test_shireadmin-0.0.1-py3-none-any.whl

Or from TestPyPI:
    pip install --index-url https://test.pypi.org/simple/ hello-python-test-shireadmin
"""

def test_imports():
    """Test that all expected imports work."""
    print("Testing imports...")
    try:
        from hello_python_test import greet, get_greeting, __version__
        print("  Imports: OK")
        return True
    except ImportError as e:
        print(f"  Import failed: {e}")
        return False


def test_greet_function():
    """Test the greet function."""
    print("\nTesting greet() function...")
    try:
        from hello_python_test import greet

        # Test default greeting
        print("  Testing greet() with no arguments:")
        greet()

        # Test custom name
        print("  Testing greet('Python'):")
        greet('Python')

        print("  greet() function: OK")
        return True
    except Exception as e:
        print(f"  greet() failed: {e}")
        return False


def test_get_greeting_function():
    """Test the get_greeting function."""
    print("\nTesting get_greeting() function...")
    try:
        from hello_python_test import get_greeting

        # Test default greeting
        result = get_greeting()
        expected = "Hello, World!"
        assert result == expected, f"Expected '{expected}', got '{result}'"
        print(f"  get_greeting() = '{result}': OK")

        # Test custom name
        result = get_greeting("TestPyPI")
        expected = "Hello, TestPyPI!"
        assert result == expected, f"Expected '{expected}', got '{result}'"
        print(f"  get_greeting('TestPyPI') = '{result}': OK")

        print("  get_greeting() function: OK")
        return True
    except Exception as e:
        print(f"  get_greeting() failed: {e}")
        return False


def test_version():
    """Test that version is accessible."""
    print("\nTesting __version__...")
    try:
        from hello_python_test import __version__
        print(f"  Version: {__version__}")
        assert __version__ == "0.0.1"
        print("  Version check: OK")
        return True
    except Exception as e:
        print(f"  Version check failed: {e}")
        return False


def main():
    """Run all tests."""
    print("=" * 60)
    print("Testing hello-python-test-shireadmin package")
    print("=" * 60)

    tests = [
        test_imports,
        test_greet_function,
        test_get_greeting_function,
        test_version,
    ]

    results = [test() for test in tests]

    print("\n" + "=" * 60)
    if all(results):
        print("All tests PASSED!")
        print("=" * 60)
        return 0
    else:
        print(f"Some tests FAILED ({sum(results)}/{len(results)} passed)")
        print("=" * 60)
        return 1


if __name__ == "__main__":
    exit(main())
