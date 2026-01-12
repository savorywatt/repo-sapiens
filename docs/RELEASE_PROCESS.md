# Release Process

This document describes how to create and publish new releases of repo-sapiens.

## Overview

There are two ways to create releases:

### Option A: Automated via UI (Recommended)
Use the **Prepare Release** workflow in Gitea Actions to automatically:
1. Update `pyproject.toml` version
2. Generate and insert CHANGELOG.md entry
3. Commit changes
4. Create and push version tag
5. Trigger the release workflow

### Option B: Manual
Manually update files, commit, and push tags (see Manual Release section).

## Release Workflows

The release automation uses two workflows:

1. **`.gitea/workflows/prepare-release.yaml`** - Prepares release files (manual trigger)
2. **`.gitea/workflows/release.yaml`** - Builds and publishes (triggered by tags)

When you run the prepare-release workflow, it automatically triggers the release workflow by pushing a version tag.

### Release Notes Extraction

The release workflow automatically extracts release notes from `CHANGELOG.md`:

1. **Searches for version heading**: `## [1.2.3] - 2026-01-11`
2. **Extracts all content** between this heading and the next version heading
3. **Uses as release body** for both PyPI and Gitea releases

**Example CHANGELOG.md:**
```markdown
## [1.2.3] - 2026-01-11

### Added
- New feature X
- New feature Y

### Fixed
- Bug fix Z

## [1.2.2] - 2026-01-05
...
```

**Extracted release notes:**
```markdown
### Added
- New feature X
- New feature Y

### Fixed
- Bug fix Z
```

This content appears in the Gitea release page automatically.

## Prerequisites

### 1. PyPI Token

Add a PyPI API token as a repository secret:

1. Generate token at https://pypi.org/manage/account/token/
   - Scope: "Entire account" or specific to "repo-sapiens" project
   - Note: Save the token immediately (only shown once)

2. Add to Gitea repository secrets:
   - Navigate to: `Settings > Secrets > Actions`
   - Name: `PYPI_TOKEN`
   - Value: `pypi-...` (your token)

### 2. Gitea Token

The workflow uses `${{ secrets.GITEA_TOKEN }}` which should be automatically available in Gitea Actions.

If not, create a token:
- Navigate to: `User Settings > Applications > Generate New Token`
- Scopes: `repo` (all), `write:packages`
- Add as repository secret: `GITEA_TOKEN`

## Automated Release (Recommended)

### Using the Prepare Release Workflow

1. **Navigate to Actions**
   - Go to your repository in Gitea
   - Click `Actions` tab
   - Find "Prepare Release" workflow
   - Click `Run workflow` button

2. **Fill in the form:**

   | Field | Description | Example |
   |-------|-------------|---------|
   | **version** | Version number without 'v' prefix | `1.2.3` |
   | **release_type** | Semantic version bump type | `minor` |
   | **changelog_added** | New features (one per line) | `Native mode support` <br> `Slack integration` |
   | **changelog_changed** | Changes (one per line) | `Improved init workflow` |
   | **changelog_fixed** | Bug fixes (one per line) | `Fixed daemon crash` |
   | **changelog_deprecated** | Deprecations (optional) | `Old API endpoint` |
   | **changelog_removed** | Removals (optional) | `Python 3.8 support` |
   | **prerelease** | Pre-release suffix (optional) | `beta.1` or leave empty |

3. **Run the workflow**
   - Click "Run workflow"
   - Monitor progress in the Actions tab

4. **What happens automatically:**
   - ✅ `pyproject.toml` version updated
   - ✅ New entry added to `CHANGELOG.md`
   - ✅ Changes committed to main branch
   - ✅ Git tag created and pushed
   - ✅ Release workflow triggered automatically
   - ✅ Package published to PyPI
   - ✅ Gitea release created with artifacts

5. **Verify release:**
   - Check PyPI: https://pypi.org/project/repo-sapiens/
   - Check Gitea Releases tab
   - Test installation: `uv pip install repo-sapiens==1.2.3`

### Example: Releasing v1.2.3

```yaml
version: 1.2.3
release_type: minor
changelog_added: |
  Native trigger mode for Gitea Actions
  Automated release workflow
  Support for GitLab CI/CD
changelog_changed: |
  Improved init command with mode selection
  Better error messages in credential handling
changelog_fixed: |
  Fixed daemon polling interval
  Resolved config validation bug
prerelease: (leave empty)
```

After clicking "Run workflow", everything is automated. The release will be live on PyPI within minutes.

## Manual Release Steps

### 1. Update Version

Edit `pyproject.toml` and update the version:

```toml
[project]
name = "repo-sapiens"
version = "1.2.3"  # Update this
```

### 2. Update CHANGELOG.md

Add a new section at the top of `CHANGELOG.md` following [Keep a Changelog](https://keepachangelog.com/) format:

```markdown
## [1.2.3] - 2026-01-11

### Added
- New feature X
- New command Y

### Changed
- Improved Z

### Fixed
- Bug fix for issue #123
```

The release workflow will automatically extract this section for the release notes.

### 3. Commit Changes

```bash
git add pyproject.toml CHANGELOG.md
git commit -m "chore: Bump version to 1.2.3"
git push origin main
```

### 4. Create and Push Tag

```bash
# Create annotated tag
git tag -a v1.2.3 -m "Release v1.2.3"

# Push tag to trigger release workflow
git push origin v1.2.3
```

**Important:** The tag must:
- Start with `v` (e.g., `v1.2.3`, not `1.2.3`)
- Match the version in `pyproject.toml` (without the `v` prefix)

### 5. Monitor Release

1. Check workflow progress:
   - Navigate to: `Actions > Release`
   - View the running workflow for your tag

2. Verify outputs:
   - **PyPI**: https://pypi.org/project/repo-sapiens/1.2.3/
   - **Gitea Release**: `https://your-gitea/owner/repo-sapiens/releases/tag/v1.2.3`

## Release Workflow Details

### What the Workflow Does

```yaml
on:
  push:
    tags:
      - 'v*'  # Matches v1.2.3, v0.1.0-beta, etc.
```

**Steps:**
1. **Extract version**: Strips `v` prefix from tag (e.g., `v1.2.3` → `1.2.3`)
2. **Verify version**: Ensures tag matches `pyproject.toml` version
3. **Extract release notes**: Parses `CHANGELOG.md` for the version section
4. **Build package**: Runs `uv build` to create wheel and sdist
5. **Test package**: Installs and validates the built wheel
6. **Publish to PyPI**: Uses `uv publish` with `PYPI_TOKEN` secret
7. **Create Gitea release**: Creates release via Gitea API
8. **Upload artifacts**: Attaches wheel and tarball to Gitea release

### Skipped Steps

If `PYPI_TOKEN` is not configured, the workflow will:
- Log a warning
- Skip PyPI publishing
- Continue with Gitea release creation

This allows testing the release process without publishing to PyPI.

## Troubleshooting

### Version Mismatch Error

```
Error: pyproject.toml version (1.2.2) doesn't match tag (1.2.3)
```

**Solution:** Update `pyproject.toml` to match the tag version or delete the incorrect tag:

```bash
git tag -d v1.2.3
git push origin :refs/tags/v1.2.3
```

### PyPI Token Invalid

```
Error: Invalid or expired API token
```

**Solution:**
1. Generate new token at https://pypi.org/manage/account/token/
2. Update `PYPI_TOKEN` secret in repository settings

### No Release Notes Found

```
⚠️ No release notes found for version 1.2.3 in CHANGELOG.md
```

**Solution:** Add section to `CHANGELOG.md`:

```markdown
## [1.2.3] - 2026-01-11

### Added
- Release notes here
```

### Gitea API Errors

If Gitea release creation fails:

1. Check `GITEA_TOKEN` secret exists and has correct permissions
2. Verify Gitea Actions has access to repository secrets
3. Check Gitea API is accessible from Actions runners

## Manual Release (Fallback)

If automated release fails, you can manually publish:

```bash
# Build package
uv build

# Publish to PyPI
uv publish

# Create Gitea release via UI
# Navigate to: Releases > New Release
# - Tag: Select existing tag
# - Title: v1.2.3
# - Description: Copy from CHANGELOG.md
# - Attach: dist/*.whl and dist/*.tar.gz
```

## Release Checklist

### Automated Release
- [ ] PyPI token configured in repository secrets
- [ ] Navigate to Actions > Prepare Release
- [ ] Fill in version and changelog details
- [ ] Run workflow and monitor progress
- [ ] Verify both workflows completed successfully
- [ ] Check PyPI package published
- [ ] Check Gitea release created with artifacts
- [ ] Test installation: `uv pip install repo-sapiens==X.Y.Z`

### Manual Release
- [ ] Version updated in `pyproject.toml`
- [ ] CHANGELOG.md updated with new section
- [ ] Changes committed and pushed to main
- [ ] Git tag created: `git tag -a vX.Y.Z -m "Release vX.Y.Z"`
- [ ] Tag pushed: `git push origin vX.Y.Z`
- [ ] Release workflow completed successfully
- [ ] PyPI package published and visible
- [ ] Gitea release created with artifacts
- [ ] Installation tested: `uv pip install repo-sapiens==X.Y.Z`

## Versioning Strategy

We follow [Semantic Versioning](https://semver.org/):

- **MAJOR** (X.0.0): Breaking changes
- **MINOR** (0.X.0): New features, backward compatible
- **PATCH** (0.0.X): Bug fixes, backward compatible

### Pre-releases

For beta/alpha releases:

```bash
# Update version in pyproject.toml
version = "1.3.0-beta.1"

# Create tag
git tag -a v1.3.0-beta.1 -m "Beta release 1.3.0-beta.1"
git push origin v1.3.0-beta.1
```

PyPI will recognize this as a pre-release and not serve it by default unless explicitly requested.
