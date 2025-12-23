# PyPI Publication Quick Checklist

**Quick reference for publishing repo-agent to PyPI. See `pypi-distribution.md` for detailed instructions.**

---

## Pre-Flight Checklist

### Code Quality
- [ ] All tests passing: `pytest tests/ -v`
- [ ] Type checking clean: `mypy automation/`
- [ ] Linting clean: `ruff check automation/`
- [ ] Code formatted: `black --check automation/`

### Package Structure
- [ ] `automation/__version__.py` contains correct version
- [ ] `automation/py.typed` exists
- [ ] `README.md` up to date
- [ ] `LICENSE` present
- [ ] `CHANGELOG.md` updated

### Metadata
- [ ] `pyproject.toml` validated
- [ ] Dependencies correct (core vs optional)
- [ ] No sensitive files in package

---

## Build Process

```bash
# 1. Clean previous builds
rm -rf dist/ build/ *.egg-info

# 2. Build distributions
source .venv/bin/activate
python -m pip install --upgrade build twine
python -m build

# 3. Validate
twine check dist/*
ls -lh dist/
```

**Expected files:**
- `dist/repo-agent-X.Y.Z.tar.gz`
- `dist/repo_agent-X.Y.Z-py3-none-any.whl`

---

## TestPyPI Upload

```bash
# 1. Upload
twine upload --repository testpypi dist/*

# 2. Verify on web
# Visit: https://test.pypi.org/project/repo-agent/

# 3. Test installation
cd /tmp
python3.11 -m venv test-env
source test-env/bin/activate
pip install --index-url https://test.pypi.org/simple/ \
    --extra-index-url https://pypi.org/simple/ \
    repo-agent

# 4. Smoke test
python -c "from automation import __version__; print(__version__)"
automation --version
builder --version

# 5. Cleanup
deactivate
cd -
```

**TestPyPI checklist:**
- [ ] Upload successful
- [ ] Package visible on TestPyPI
- [ ] Installation works
- [ ] Version correct
- [ ] CLI commands available
- [ ] README renders properly

---

## Production PyPI Upload

### Final Pre-Production Check
- [ ] TestPyPI verification complete
- [ ] All tests still passing
- [ ] CHANGELOG.md updated
- [ ] No known critical bugs
- [ ] Team approval (if applicable)

### Upload

```bash
# 1. Upload to PyPI
twine upload --repository pypi dist/*

# 2. Verify on web
# Visit: https://pypi.org/project/repo-agent/
```

**WARNING**: Can't delete or replace versions once uploaded to PyPI!

---

## Post-Publication

```bash
# 1. Test production installation
python3.11 -m venv /tmp/prod-test
source /tmp/prod-test/bin/activate
pip install repo-agent
python -c "from automation import __version__; print(__version__)"
deactivate

# 2. Create git tag
git tag -a vX.Y.Z -m "Release vX.Y.Z"
git push origin vX.Y.Z

# 3. Update documentation
# - Add PyPI installation to README
# - Update CHANGELOG
# - Commit and push
```

**Post-publication checklist:**
- [ ] Production installation verified
- [ ] Git tag created and pushed
- [ ] README updated with PyPI install
- [ ] CHANGELOG committed
- [ ] Release created in Gitea UI

---

## CI/CD Setup (One-Time)

### Gitea Secrets
1. Go to: http://100.89.157.127:3000/shireadmin/repo-agent/settings/secrets
2. Add secrets:
   - `TESTPYPI_API_TOKEN`: Token from https://test.pypi.org
   - `PYPI_API_TOKEN`: Token from https://pypi.org

### Workflow File
- File: `.gitea/workflows/pypi-publish.yml`
- Triggers on: Tags matching `v*.*.*`

### Test Automation
```bash
# 1. Bump version
sed -i 's/__version__ = "X.Y.Z"/__version__ = "X.Y.Z+1"/' automation/__version__.py

# 2. Commit and tag
git add automation/__version__.py CHANGELOG.md
git commit -m "chore: Bump version to X.Y.Z+1"
git push origin main
git tag -a vX.Y.Z+1 -m "Release vX.Y.Z+1"
git push origin vX.Y.Z+1

# 3. Monitor workflow
# Visit: http://100.89.157.127:3000/shireadmin/repo-agent/actions
```

---

## Troubleshooting Quick Reference

| Problem | Quick Fix |
|---------|-----------|
| "Version already exists" | Increment version, rebuild |
| "twine check fails" | Fix pyproject.toml, rebuild |
| "CLI not found" | Check [project.scripts] section |
| "Import fails" | Check package structure |
| "Token invalid" | Regenerate token, update secret |
| "Workflow not triggering" | Check tag format: v*.*.* |

---

## Emergency Rollback

If you published a broken version:

### Option 1: Yank (Recommended)
1. Go to: https://pypi.org/project/repo-agent/
2. Click "Manage" → "Yank version X.Y.Z"
3. Reason: "Critical bug"

### Option 2: Publish Fix
1. Increment version immediately
2. Fix the issue
3. Release new version ASAP

**Remember**: You cannot delete or replace PyPI versions!

---

## Quick Commands Cheat Sheet

```bash
# Build
python -m build

# Check
twine check dist/*

# Upload TestPyPI
twine upload --repository testpypi dist/*

# Upload PyPI
twine upload dist/*

# Test install from TestPyPI
pip install --index-url https://test.pypi.org/simple/ \
    --extra-index-url https://pypi.org/simple/ \
    repo-agent

# Test install from PyPI
pip install repo-agent

# Verify
python -c "from automation import __version__; print(__version__)"
automation --version
```

---

**Last Updated**: 2025-12-22
**See Also**: `pypi-distribution.md` for complete detailed plan
