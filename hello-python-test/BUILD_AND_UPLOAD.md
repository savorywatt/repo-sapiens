# Build and Upload Guide

This guide shows how to build and upload this package to TestPyPI.

## Prerequisites

Install required build tools:

```bash
python -m pip install --upgrade pip
python -m pip install build twine
```

## Building the Package

From the project root directory (`hello-python-test/`):

```bash
# Build both wheel and source distribution
python -m build
```

This creates:
- `dist/hello_python_test_shireadmin-0.0.1-py3-none-any.whl` (wheel)
- `dist/hello_python_test_shireadmin-0.0.1.tar.gz` (source distribution)

## Verify the Build

Check that the package was built correctly:

```bash
# List contents of the wheel
python -m zipfile -l dist/hello_python_test_shireadmin-0.0.1-py3-none-any.whl

# Check package metadata
python -m twine check dist/*
```

## Upload to TestPyPI

### 1. Create a TestPyPI account

Visit https://test.pypi.org/account/register/ and create an account.

### 2. Create an API token

1. Go to https://test.pypi.org/manage/account/
2. Scroll to "API tokens"
3. Click "Add API token"
4. Name it (e.g., "hello-python-test")
5. Copy the token (starts with `pypi-`)

### 3. Upload the package

```bash
python -m twine upload --repository testpypi dist/*
```

When prompted:
- Username: `__token__`
- Password: (paste your API token)

Or use a `.pypirc` file in your home directory:

```ini
[testpypi]
username = __token__
password = pypi-YOUR_TOKEN_HERE
```

Then upload:

```bash
python -m twine upload --repository testpypi dist/*
```

## Test the Installation

After uploading, test the installation:

```bash
# Create a new virtual environment
python -m venv test_env
source test_env/bin/activate  # On Windows: test_env\Scripts\activate

# Install from TestPyPI
pip install --index-url https://test.pypi.org/simple/ hello-python-test-shireadmin

# Test it
python -c "from hello_python_test import greet; greet()"
python -c "from hello_python_test import get_greeting; print(get_greeting('TestPyPI'))"
```

## Clean Build Artifacts

To clean up before rebuilding:

```bash
rm -rf build/ dist/ src/*.egg-info
```

## Troubleshooting

### Package name already exists

If you get a conflict error, the package name is taken. Change the name in `pyproject.toml`:

```toml
name = "hello-python-test-yourname-uniqueid"
```

Then rebuild and upload.

### Version already exists

If you've already uploaded version 0.0.1, increment the version in `pyproject.toml`:

```toml
version = "0.0.2"
```

Also update `__version__` in `src/hello_python_test/__init__.py`.

### Import errors after installation

Make sure you're using the correct package name for imports:

```python
# Correct
from hello_python_test import greet

# Incorrect (package name uses hyphens, not underscores)
from hello-python-test import greet
```
