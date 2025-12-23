# Rollback Strategy for PyPI Releases

## Critical Understanding: PyPI Does Not Allow Deletions

PyPI does not allow deletion of published releases except in extreme circumstances (legal/security issues). Once a version is uploaded, it is **permanent**. This policy:

- Prevents dependency confusion attacks
- Ensures reproducibility for all users
- Protects the integrity of the Python ecosystem

**Never expect to delete a release from PyPI.**

## When a Release is Broken

If you discover a release has critical issues after uploading to PyPI, you have several options:

### Option 1: Yank the Release (Recommended for Broken Releases)

Yanking makes a release unavailable for new installations while keeping it accessible for existing users who pinned that exact version.

#### Via PyPI Web Interface:

1. Log in to https://pypi.org
2. Navigate to your project: https://pypi.org/project/repo-agent/
3. Click on the broken version
4. Click "Options" → "Yank release"
5. Provide a clear reason (e.g., "Broken: py.typed missing in wheel")
6. Confirm the action

#### Via Twine (Alternative):

```bash
# Note: Yanking via twine is not supported. Use web interface.
```

#### What Yanking Does:

- ✅ `pip install repo-agent` will **skip** the yanked version
- ✅ `pip install repo-agent==0.1.0` will **still work** (explicit version)
- ✅ Version shows as "Yanked" on PyPI with your reason
- ✅ Already-installed packages are **not affected**

#### When to Yank:

- Critical bugs that break core functionality
- Missing files (e.g., py.typed missing)
- Incorrect dependencies that cause install failures
- Security vulnerabilities (along with patching)

### Option 2: Release a Patch Version (Always Required After Yanking)

Yanking only prevents new installations. You **must** release a fixed version.

#### Step-by-Step:

1. **Fix the issue locally:**
   ```bash
   # Fix code/configuration
   # Verify the fix works
   ```

2. **Bump version:**
   ```bash
   # Edit automation/__version__.py
   __version__ = "0.1.1"  # Increment patch version
   ```

3. **Update CHANGELOG.md:**
   ```markdown
   ## [0.1.1] - 2025-12-23

   ### Fixed
   - Fixed critical bug in 0.1.0: py.typed missing from wheel
   - Added missing dependency configuration
   ```

4. **Run full validation:**
   ```bash
   # Follow PACKAGE_CHECKLIST.md completely
   rm -rf dist/ build/ *.egg-info/
   python3 -m build
   twine check dist/*
   # Test in clean venv
   # etc.
   ```

5. **Upload to PyPI:**
   ```bash
   twine upload dist/*
   ```

6. **Announce the fix:**
   - Update project README if needed
   - Create GitHub/Gitea release notes
   - If critical, notify users directly

### Option 3: Emergency Contact (Extreme Cases Only)

For critical security vulnerabilities or legal issues:

1. Contact PyPI support: https://pypi.org/help/
2. Provide detailed justification:
   - Security vulnerability details (CVE if available)
   - Legal requirement (DMCA, court order)
   - Impact assessment
3. Request takedown

**This is rarely granted.** Only for severe issues where yanking is insufficient.

## Prevention Strategies

### Always Use Test PyPI First

```bash
# Upload to Test PyPI
twine upload --repository testpypi dist/*

# Test installation
pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ repo-agent

# Verify functionality
python3 -c "import automation; print(automation.__version__)"
automation --help
```

This catches 90% of issues before production upload.

### Use the Package Checklist

Follow `PACKAGE_CHECKLIST.md` religiously. It covers:

- Build validation
- Metadata verification
- Installation testing (wheel + source dist)
- Type hints verification
- Optional dependencies testing

### Version Number Guidelines

Follow semantic versioning strictly:

- **MAJOR.MINOR.PATCH** (e.g., 0.1.0)
- **PATCH** for bug fixes (0.1.0 → 0.1.1)
- **MINOR** for new features (0.1.0 → 0.2.0)
- **MAJOR** for breaking changes (0.9.0 → 1.0.0)

Never reuse a version number, even if yanked.

### Pre-Release Versions for Testing

For risky changes, use pre-release versions:

```bash
# In automation/__version__.py
__version__ = "0.2.0b1"  # Beta 1
__version__ = "0.2.0rc1"  # Release Candidate 1
```

These can be tested by users who opt-in:
```bash
pip install --pre repo-agent
```

## Rollback Scenarios and Solutions

### Scenario 1: Missing File in Distribution

**Problem**: py.typed missing from wheel

**Symptoms**: Type checkers don't recognize package types

**Solution**:
1. Yank broken version via PyPI web interface
2. Fix MANIFEST.in and package-data
3. Bump version (0.1.0 → 0.1.1)
4. Rebuild and test
5. Upload new version

### Scenario 2: Incorrect Dependencies

**Problem**: Optional dependency installed as core dependency

**Symptoms**: Users complain about large install size

**Solution**:
1. Yank broken version
2. Fix pyproject.toml dependencies structure
3. Test in clean venv: `pip list | grep <unwanted-package>`
4. Bump version
5. Upload fix

### Scenario 3: Critical Runtime Bug

**Problem**: Code crashes on import or basic usage

**Symptoms**: Users report ImportError or immediate crashes

**Solution**:
1. **Immediately yank** the broken version
2. Add clear yank reason: "Broken: crashes on import"
3. Fix the bug
4. Add regression test
5. Bump version
6. Upload fix
7. Announce: "Version 0.1.0 was yanked, please upgrade to 0.1.1"

### Scenario 4: Security Vulnerability

**Problem**: Discovered CVE in dependency or code

**Symptoms**: Security scanner alerts

**Solution**:
1. **Immediately yank** affected versions
2. Fix vulnerability
3. Bump version
4. Upload fix
5. File CVE advisory if needed
6. Announce with clear upgrade instructions
7. Consider yanking **all** affected versions (0.1.0, 0.1.1, etc.)

### Scenario 5: Wrong Version Number

**Problem**: Uploaded 0.2.0 but meant to upload 0.1.1

**Symptoms**: Version confusion

**Solution**:
1. Accept the mistake (cannot change)
2. Yank 0.2.0 with reason: "Incorrect version number"
3. Upload 0.2.1 with actual changes
4. Update CHANGELOG to explain

**Prevention**: Double-check `automation/__version__.py` before upload

### Scenario 6: Broken on Specific Python Version

**Problem**: Works on Python 3.11, crashes on Python 3.12

**Symptoms**: Platform-specific bug reports

**Solution**:
1. Yank version
2. Fix compatibility issue
3. Test on all supported Python versions (3.11, 3.12, 3.13)
4. Bump version
5. Upload
6. Consider adding CI for multi-version testing

## Communication Template

When announcing a yanked release:

```markdown
## Version 0.1.0 Yanked

Version 0.1.0 of repo-agent has been yanked from PyPI due to [specific issue].

**Issue**: [Clear description]

**Impact**: [Who is affected and how]

**Resolution**: Please upgrade to version 0.1.1:

    pip install --upgrade repo-agent

If you have explicitly pinned to 0.1.0:

    pip install repo-agent==0.1.1

**Changes in 0.1.1**: See CHANGELOG.md

Thank you for your patience.
```

## Version History Management

Keep a record of yanked versions in CHANGELOG.md:

```markdown
## [0.1.1] - 2025-12-23

### Fixed
- Fixed py.typed missing from wheel distribution

## [0.1.0] - 2025-12-22 [YANKED]

**Yanked Reason**: Missing py.typed in wheel distribution

- Initial release (yanked, use 0.1.1 instead)
```

## Monitoring After Release

For 24-48 hours after release:

1. Monitor PyPI download stats (if available)
2. Watch GitHub/Gitea issues for bug reports
3. Check installation works on different platforms
4. Monitor error reporting (if instrumented)
5. Check dependency compatibility

## Final Notes

- **Prevention > Reaction**: Use Test PyPI and checklist
- **Be Transparent**: Clearly communicate issues and fixes
- **Be Prompt**: Yank and fix quickly when issues arise
- **Learn**: Update checklist and process after each issue
- **Version Bumps Are Cheap**: Don't hesitate to release patches

PyPI's permanence policy protects the ecosystem. Work within it, not against it.

## Quick Reference

| Situation | Action | Timeline |
|-----------|--------|----------|
| Critical bug | Yank + patch release | Within hours |
| Minor bug | Patch release (no yank) | Within days |
| Enhancement | Minor version bump | Planned |
| Breaking change | Major version bump | Well-announced |
| Security issue | Yank + emergency patch | Immediately |

## Resources

- PyPI Help: https://pypi.org/help/
- Packaging Guide: https://packaging.python.org/
- PEP 440 (Versioning): https://peps.python.org/pep-0440/
- Security Reporting: security@pypi.org
