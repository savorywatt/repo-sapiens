# PyPI Distribution Plan for Builder Automation

## Executive Summary

This plan outlines the steps to transform the builder automation system into a production-ready Python package that can be published to PyPI and installed with `pip install builder-automation`.

## 1. Package Naming Strategy

### Recommendation: Use "builder-automation"

**Rationale:**
- Current name "gitea-automation" is too specific to the Git provider
- "builder" aligns with the repository name and broader vision
- More marketable for future expansion to GitHub, GitLab, etc.
- Easier to brand and remember

**PyPI Package Name:** `builder-automation`
**Import Name:** `automation` (keep current structure)
**CLI Command:** `automation` (backward compatible)

### Alternative Entry Points (Phase 2)
- Consider adding `builder` as an alias: `builder daemon`, `builder process-issue`
- This provides better branding while maintaining compatibility

## 2. Version Management Strategy

### Semantic Versioning (SemVer)

**Current:** 0.1.0 (pre-release)
**Target:** 0.1.0 for first PyPI release, then follow SemVer

**Version Scheme:**
- **0.x.y**: Pre-1.0 releases (breaking changes in minor versions)
- **1.0.0**: First stable release
- **1.x.y**: Stable releases (semver strict)

### Version Source of Truth

**Create:** `automation/__version__.py`
```python
__version__ = "0.1.0"
__author__ = "Builder Automation Team"
```

**Update pyproject.toml to reference it:**
```toml
[project]
name = "builder-automation"
dynamic = ["version"]

[tool.setuptools.dynamic]
version = {attr = "automation.__version__.__version__"}
```

### Version Management Tools

**Option 1: Manual (Simple)**
- Edit `__version__.py` manually
- Tag releases with `git tag v0.1.0`

**Option 2: bump2version (Recommended)**
```bash
pip install bump2version
# .bumpversion.cfg configuration
# bump2version patch/minor/major
```

**Option 3: setuptools-scm (Git-based)**
- Auto-generate versions from git tags
- Best for automated workflows

## 3. Package Structure Improvements

### Current Structure (Good)
```
automation/
├── __init__.py
├── __version__.py (to add)
├── config/
├── engine/
├── models/
├── providers/
├── processors/
├── utils/
└── main.py
```

### Required Additions

#### 3.1. Add `__version__.py`
- Single source of truth for version
- Importable: `from automation import __version__`

#### 3.2. Update `__init__.py`
- Export version and key classes
- Enable `import automation; automation.__version__`

#### 3.3. Add LICENSE file
- **Critical for PyPI**
- Recommend: MIT or Apache 2.0
- Must exist at root: `LICENSE`

#### 3.4. Update README.md
- Add PyPI installation instructions
- Badge for PyPI version
- Quick start for pip users
- Clear examples

### Files to Include in Distribution

**Already configured in MANIFEST.in:**
- README.md
- QUICK_START.md
- CI_CD_GUIDE.md
- .env.example
- automation/config/*.yaml

**Add to MANIFEST.in:**
```manifest
include LICENSE
include automation/__version__.py
```

## 4. Entry Points Configuration

### Current Configuration (Good)
```toml
[project.scripts]
automation = "automation.main:cli"
```

### Enhanced Configuration
```toml
[project.scripts]
automation = "automation.main:cli"
builder = "automation.main:cli"  # Alias for better branding
```

## 5. Distribution Build Process

### Build Tools

**Current:** setuptools + wheel (good)

**Build command:**
```bash
python -m build
```

**Output:**
- `dist/builder-automation-0.1.0.tar.gz` (source distribution)
- `dist/builder_automation-0.1.0-py3-none-any.whl` (wheel)

### Pre-build Checklist

1. **Clean previous builds**
   ```bash
   rm -rf dist/ build/ *.egg-info/
   ```

2. **Update version** in `__version__.py`

3. **Run tests**
   ```bash
   pytest tests/ -v
   ```

4. **Check package metadata**
   ```bash
   python -m build --sdist --wheel
   twine check dist/*
   ```

5. **Test local installation**
   ```bash
   pip install dist/builder_automation-0.1.0-py3-none-any.whl
   automation --version
   ```

### Build Script

**Create:** `scripts/build.sh`
```bash
#!/bin/bash
set -e

echo "Building builder-automation package..."

# Clean previous builds
rm -rf dist/ build/ *.egg-info/

# Install build tools
pip install --upgrade build twine

# Build distributions
python -m build

# Check distributions
twine check dist/*

echo "Build complete! Distributions in dist/"
ls -lh dist/
```

## 6. PyPI Publishing Process

### 6.1. Test PyPI (REQUIRED FIRST)

**Purpose:** Test the entire publishing and installation process without affecting real PyPI

**Steps:**

1. **Create Test PyPI account**
   - Visit: https://test.pypi.org/account/register/
   - Verify email

2. **Create API token**
   - Go to Account Settings → API tokens
   - Create token with scope: "Entire account"
   - Save as `~/.pypirc`:
   ```ini
   [testpypi]
   username = __token__
   password = pypi-AgEIcHlwaS5vcmc...
   ```

3. **Upload to Test PyPI**
   ```bash
   twine upload --repository testpypi dist/*
   ```

4. **Test installation**
   ```bash
   pip install --index-url https://test.pypi.org/simple/ \
       --extra-index-url https://pypi.org/simple/ \
       builder-automation
   ```

5. **Verify functionality**
   ```bash
   automation --help
   automation --version
   ```

6. **Fix issues and re-upload**
   - Increment version (e.g., 0.1.0 → 0.1.1)
   - Cannot reupload same version
   - Rebuild and reupload

### 6.2. Production PyPI

**Prerequisites:**
- Successful Test PyPI deployment
- All tests passing
- Documentation complete
- LICENSE file present

**Steps:**

1. **Create PyPI account**
   - Visit: https://pypi.org/account/register/
   - Verify email

2. **Create API token**
   - Create token for the specific project (after first upload)
   - Save to `~/.pypirc`:
   ```ini
   [pypi]
   username = __token__
   password = pypi-AgENcHl...
   ```

3. **Upload to PyPI**
   ```bash
   twine upload dist/*
   ```

4. **Verify on PyPI**
   - Visit: https://pypi.org/project/builder-automation/
   - Check metadata, description, links

5. **Test installation**
   ```bash
   pip install builder-automation
   automation --version
   ```

### Publishing Script

**Create:** `scripts/publish.sh`
```bash
#!/bin/bash
set -e

REPO=${1:-testpypi}

if [ "$REPO" != "testpypi" ] && [ "$REPO" != "pypi" ]; then
    echo "Usage: $0 [testpypi|pypi]"
    exit 1
fi

if [ "$REPO" = "pypi" ]; then
    read -p "Are you sure you want to publish to PyPI? (yes/no) " confirm
    if [ "$confirm" != "yes" ]; then
        echo "Aborted."
        exit 0
    fi
fi

echo "Publishing to $REPO..."
twine upload --repository $REPO dist/*

echo "Published successfully!"
echo "Install with: pip install builder-automation"
```

## 7. Documentation Updates

### 7.1. README.md Updates

**Add PyPI installation section:**

```markdown
## Installation

### From PyPI (Recommended)

```bash
pip install builder-automation
```

### From Source

```bash
git clone https://github.com/yourorg/builder.git
cd builder
pip install -e .
```
```

**Add badges:**
```markdown
[![PyPI version](https://badge.fury.io/py/builder-automation.svg)](https://badge.fury.io/py/builder-automation)
[![Python versions](https://img.shields.io/pypi/pyversions/builder-automation.svg)](https://pypi.org/project/builder-automation/)
```

### 7.2. Create CHANGELOG.md

**Format:** Keep a Changelog (keepachangelog.com)

**Example:**
```markdown
# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

## [0.1.0] - 2025-12-22

### Added
- Initial public release
- CLI commands: daemon, process-issue, process-all
- Gitea integration via REST API
- AI agent support (Claude, Ollama)
- Workflow orchestration with state management
- Docker support
- CI/CD integration guides
```

### 7.3. Update pyproject.toml Metadata

```toml
[project]
name = "builder-automation"
version = "0.1.0"  # Or dynamic from __version__.py
description = "AI-driven automation system for Git workflows"
readme = "README.md"
requires-python = ">=3.11"
license = {text = "MIT"}
authors = [
    {name = "Your Name", email = "your.email@example.com"}
]
keywords = [
    "gitea",
    "automation",
    "ai",
    "workflow",
    "ci-cd",
    "claude",
    "builder"
]
classifiers = [
    "Development Status :: 4 - Beta",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Topic :: Software Development :: Build Tools",
]

[project.urls]
Homepage = "https://github.com/yourorg/builder"
Documentation = "https://github.com/yourorg/builder#readme"
Repository = "https://github.com/yourorg/builder"
"Bug Tracker" = "https://github.com/yourorg/builder/issues"
Changelog = "https://github.com/yourorg/builder/blob/main/CHANGELOG.md"
```

## 8. CI/CD Integration for Automated Publishing

### Gitea Actions Workflow

**Create:** `.gitea/workflows/publish-pypi.yaml`

```yaml
name: Publish to PyPI

on:
  push:
    tags:
      - 'v*.*.*'  # Trigger on version tags like v0.1.0

jobs:
  build-and-publish:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout code
        uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install build tools
        run: |
          python -m pip install --upgrade pip
          pip install build twine

      - name: Build distributions
        run: python -m build

      - name: Check distributions
        run: twine check dist/*

      - name: Publish to PyPI
        env:
          TWINE_USERNAME: __token__
          TWINE_PASSWORD: ${{ secrets.PYPI_TOKEN }}
        run: twine upload dist/*
```

## 9. Implementation Steps Summary

### Phase 1: Preparation (1-2 hours)

1. Create `LICENSE` file (MIT or Apache 2.0)
2. Create `automation/__version__.py`
3. Update `automation/__init__.py` to export version
4. Update `pyproject.toml` metadata
5. Create `CHANGELOG.md`
6. Update `README.md` with installation instructions

### Phase 2: Testing (30 minutes)

1. Run existing tests: `pytest tests/ -v`
2. Test local build: `python -m build`
3. Test wheel installation locally
4. Check package with `twine check dist/*`

### Phase 3: Test PyPI (1 hour)

1. Create Test PyPI account
2. Create API token
3. Upload to Test PyPI
4. Test installation from Test PyPI
5. Verify functionality

### Phase 4: Production PyPI (30 minutes)

1. Create PyPI account
2. Create API token
3. Upload to PyPI
4. Test installation from PyPI
5. Create git tag for release

### Phase 5: Automation (1-2 hours)

1. Create `.gitea/workflows/publish-pypi.yaml`
2. Add PYPI_TOKEN secret
3. Test workflow with pre-release tag

### Total Estimated Time: 4-6 hours

## 10. Critical Next Steps

1. **Create LICENSE file** - Required for PyPI
2. **Add `__version__.py`** - Version management
3. **Test build process** - Ensure it works
4. **Upload to Test PyPI** - Verify before production
5. **Document installation** - Update README

---

**Status**: Ready for implementation
**Priority**: High - Enables wider adoption
**Effort**: Medium (4-6 hours)
**Risk**: Low - Well-established process
