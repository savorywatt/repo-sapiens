# Package Release Checklist

Use this checklist before every PyPI release to ensure quality and consistency.

## Pre-Build

- [ ] Version bumped in `automation/__version__.py`
- [ ] CHANGELOG.md updated with new version and changes
- [ ] All tests pass: `pytest tests/`
- [ ] Type checking passes: `mypy automation/`
- [ ] Linting passes: `ruff check automation/`
- [ ] Git working directory clean: `git status`
- [ ] All changes committed

## Build

- [ ] Clean previous builds: `rm -rf dist/ build/ *.egg-info/`
- [ ] Build package: `python3 -m build`
- [ ] Verify outputs exist: `ls -lh dist/`
  - Should see: `repo_agent-X.Y.Z-py3-none-any.whl`
  - Should see: `repo_agent-X.Y.Z.tar.gz`

## Validation

### Automated Validation

- [ ] Run twine check: `twine check dist/*`
  - Should show: PASSED for both files

### Manual Inspection

- [ ] Inspect wheel contents:
  ```bash
  unzip -l dist/repo_agent-*.whl | grep py.typed
  # Should show: automation/py.typed
  ```

- [ ] Inspect source dist contents:
  ```bash
  tar -tzf dist/repo_agent-*.tar.gz | grep py.typed
  # Should show: repo_agent-X.Y.Z/automation/py.typed
  ```

- [ ] Check METADATA:
  ```bash
  unzip -p dist/repo_agent-*.whl */METADATA | head -20
  # Verify:
  # - Name: repo-agent
  # - Version: matches __version__.py
  # - License-Expression: MIT
  # - Requires-Python: >=3.11
  ```

### Installation Tests

- [ ] Test wheel installation in clean venv:
  ```bash
  python3 -m venv /tmp/test-wheel
  source /tmp/test-wheel/bin/activate
  pip install dist/repo_agent-*.whl
  python3 -c "import automation; print(automation.__version__)"
  automation --help
  # Verify no optional dependencies:
  pip list | grep -E "fastapi|uvicorn|prometheus"
  # Should be empty
  deactivate
  rm -rf /tmp/test-wheel
  ```

- [ ] Test source dist installation in clean venv:
  ```bash
  python3 -m venv /tmp/test-sdist
  source /tmp/test-sdist/bin/activate
  pip install dist/repo_agent-*.tar.gz
  python3 -c "import automation; print(automation.__version__)"
  automation --help
  deactivate
  rm -rf /tmp/test-sdist
  ```

- [ ] Test optional dependencies:
  ```bash
  python3 -m venv /tmp/test-extras
  source /tmp/test-extras/bin/activate
  pip install dist/repo_agent-*.whl
  pip install "repo-agent[monitoring]"
  pip list | grep -E "fastapi|uvicorn|prometheus"
  # Should show all three
  deactivate
  rm -rf /tmp/test-extras
  ```

### Type Hints Verification

- [ ] Verify py.typed installed:
  ```bash
  python3 -m venv /tmp/test-types
  source /tmp/test-types/bin/activate
  pip install dist/repo_agent-*.whl
  python3 -c "import automation, os; print('py.typed exists:', os.path.exists(os.path.join(os.path.dirname(automation.__file__), 'py.typed')))"
  # Should print: py.typed exists: True
  deactivate
  rm -rf /tmp/test-types
  ```

## Test PyPI (Recommended Before Production)

- [ ] Configure Test PyPI credentials in `~/.pypirc`:
  ```ini
  [testpypi]
  username = __token__
  password = pypi-...
  ```

- [ ] Upload to Test PyPI:
  ```bash
  twine upload --repository testpypi dist/*
  ```

- [ ] Install from Test PyPI in clean venv:
  ```bash
  python3 -m venv /tmp/test-testpypi
  source /tmp/test-testpypi/bin/activate
  pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ repo-agent
  python3 -c "import automation; print(automation.__version__)"
  automation --help
  deactivate
  rm -rf /tmp/test-testpypi
  ```

  Note: `--extra-index-url https://pypi.org/simple/` is needed because dependencies are on production PyPI

- [ ] Verify package page on Test PyPI: https://test.pypi.org/project/repo-agent/

## Production PyPI

### Pre-Upload

- [ ] All validation tests passed
- [ ] Version is unique (never uploaded before)
- [ ] Git tag created: `git tag vX.Y.Z`
- [ ] Git tag pushed: `git push origin vX.Y.Z`

### Upload

- [ ] Configure PyPI credentials in `~/.pypirc` or use token
- [ ] Upload to PyPI:
  ```bash
  twine upload dist/*
  ```

### Post-Upload Verification

- [ ] Verify package page: https://pypi.org/project/repo-agent/
  - Check version is correct
  - Check README renders correctly
  - Check classifiers are correct

- [ ] Install from PyPI in clean venv:
  ```bash
  python3 -m venv /tmp/test-pypi
  source /tmp/test-pypi/bin/activate
  pip install repo-agent
  python3 -c "import automation; print(automation.__version__)"
  automation --help
  deactivate
  rm -rf /tmp/test-pypi
  ```

- [ ] Check metadata via API:
  ```bash
  curl -s https://pypi.org/pypi/repo-agent/json | jq '.info.version'
  # Should show: "X.Y.Z"
  ```

## Post-Release

- [ ] Create GitHub/Gitea release with changelog
- [ ] Update documentation if needed
- [ ] Announce release (if applicable)
- [ ] Monitor for issues in first 24 hours
- [ ] Update internal documentation with new version

## Rollback Procedure (If Needed)

If the release is broken:

1. **Do NOT delete from PyPI** (not allowed)
2. **Yank the release** via PyPI web interface:
   - Go to https://pypi.org/project/repo-agent/
   - Click on the broken version
   - Click "Options" → "Yank release"
   - Provide reason
3. **Fix the issue locally**
4. **Bump version** (e.g., 0.1.0 → 0.1.1)
5. **Run this checklist again** for the patch version
6. **Release the fix**

## Notes

- Never reuse a version number
- Always test on Test PyPI before production (unless trivial change)
- Keep this checklist updated as process evolves
- Estimated time for full checklist: 30-45 minutes
