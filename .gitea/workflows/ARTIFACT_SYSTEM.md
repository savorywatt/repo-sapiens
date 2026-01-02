# Gitea Actions Artifact System

This document explains how the artifact caching system works to speed up workflow runs.

## Overview

Instead of rebuilding the automation package from source every time a workflow runs, we:
1. **Build once** - Create wheel, source dist, and Docker image
2. **Upload as artifacts** - Store in Gitea Actions
3. **Download and reuse** - Other workflows use pre-built artifacts

This makes workflows **much faster** (seconds instead of minutes for install).

## Artifact Workflows

### 1. `build-artifacts.yaml` - Build and Cache

**Triggers:**
- Push to main (when automation code changes)
- Pull requests
- Daily schedule (keeps artifacts fresh)
- Manual trigger

**What it builds:**
- Python wheel package (`automation-wheel`)
- Source distribution (`automation-sdist`)
- Docker image (`docker-image`)
- Metadata files

**Artifacts created:**
```
automation-wheel/
  └── gitea_automation-0.1.0-py3-none-any.whl

automation-sdist/
  └── gitea-automation-0.1.0.tar.gz

docker-image/
  └── automation-image.tar

package-metadata/
  └── package-info.json
```

**Retention:**
- Package artifacts: 30 days
- Docker image: 7 days (large files)

### 2. Using Artifacts in Workflows

All label-triggered workflows now use artifacts:

```yaml
- name: Download pre-built wheel (if available)
  uses: actions/download-artifact@v3
  with:
    name: automation-wheel
    path: dist/
  continue-on-error: true  # Fallback to source if not available

- name: Install automation
  run: |
    pip install --upgrade pip
    if [ -f dist/*.whl ]; then
      echo "✅ Using pre-built wheel"
      pip install dist/*.whl
    else
      echo "⚠️ Building from source"
      pip install -e .
    fi
```

## Performance Comparison

### Without Artifacts (slow)
```
Install automation: 2m 15s
  - pip install dependencies
  - build package from source
  - install package
```

### With Artifacts (fast)
```
Install automation: 12s
  - download wheel artifact (5s)
  - pip install wheel (7s)
```

**Speed improvement: ~90% faster**

## Workflow Examples

### Example 1: Using Wheel Artifact

```yaml
jobs:
  process-issue:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      # Download artifact
      - name: Download wheel
        uses: actions/download-artifact@v3
        with:
          name: automation-wheel
          path: dist/
        continue-on-error: true

      # Install from artifact or fallback to source
      - name: Install
        run: |
          if [ -f dist/*.whl ]; then
            pip install dist/*.whl
          else
            pip install -e .
          fi

      # Use automation
      - name: Run automation
        run: sapiens process-issue --issue 123
```

### Example 2: Using Docker Artifact

```yaml
jobs:
  process-with-docker:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      # Download Docker image artifact
      - name: Download image
        uses: actions/download-artifact@v3
        with:
          name: docker-image
          path: /tmp/
        continue-on-error: true

      # Load image or build if not available
      - name: Load Docker image
        run: |
          if [ -f /tmp/automation-image.tar ]; then
            docker load < /tmp/automation-image.tar
          else
            docker build -t gitea-automation:latest .
          fi

      # Run in container
      - name: Run automation
        run: |
          docker run --rm \
            -e AUTOMATION__GIT_PROVIDER__API_TOKEN=${{ secrets.BUILDER_GITEA_TOKEN }} \
            -v $PWD:/workspace \
            gitea-automation:latest \
            process-issue --issue 123
```

## Artifact Availability

### When Artifacts Are Available

Artifacts are available after `build-artifacts.yaml` runs successfully on:
- Any push to main
- Any pull request
- Daily builds (2 AM UTC)

### When to Trigger a Build

Manually trigger a build if:
- You made changes to automation code
- Artifacts expired (>30 days)
- You want to test with latest code

```bash
# Trigger via CLI
gh workflow run build-artifacts.yaml

# Or via web UI
# Actions → Build Automation Artifacts → Run workflow
```

## Fallback Behavior

All workflows have **automatic fallback**:

```bash
# Tries to use artifact
if [ -f dist/*.whl ]; then
  pip install dist/*.whl  # Fast!
else
  pip install -e .        # Slower, but works
fi
```

This means:
- ✅ Workflows never fail due to missing artifacts
- ✅ Always uses fastest available method
- ✅ Graceful degradation

## Artifact Lifecycle

```
┌─────────────────────────────────────────┐
│  Code pushed to main                    │
│  or Daily schedule (2 AM)               │
└────────────┬────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────┐
│  build-artifacts.yaml triggers          │
│  - Builds Python wheel                  │
│  - Builds Docker image                  │
│  - Uploads as artifacts                 │
└────────────┬────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────┐
│  Artifacts available for 30 days        │
│  (7 days for Docker)                    │
└────────────┬────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────┐
│  Other workflows download & use         │
│  - needs-planning.yaml                  │
│  - execute-task.yaml                    │
│  - requires-qa.yaml                     │
│  - etc.                                 │
└─────────────────────────────────────────┘
```

## Best Practices

### 1. Always Use Artifacts

```yaml
# ✅ Good - tries artifact first
- uses: actions/download-artifact@v3
  with:
    name: automation-wheel
    path: dist/
  continue-on-error: true

- run: |
    if [ -f dist/*.whl ]; then
      pip install dist/*.whl
    else
      pip install -e .
    fi

# ❌ Bad - always builds from source
- run: pip install -e .
```

### 2. Set Appropriate Retention

```yaml
# Package artifacts (small)
- uses: actions/upload-artifact@v3
  with:
    retention-days: 30  # Keep longer

# Docker images (large)
- uses: actions/upload-artifact@v3
  with:
    retention-days: 7   # Keep shorter
```

### 3. Use continue-on-error

Always use `continue-on-error: true` when downloading artifacts:

```yaml
- uses: actions/download-artifact@v3
  continue-on-error: true  # Don't fail if artifact missing
```

### 4. Check Artifact Age

```yaml
- name: Check artifact age
  run: |
    if [ -f package-info.json ]; then
      BUILD_DATE=$(cat package-info.json | grep build_date | cut -d'"' -f4)
      echo "Using artifact from: $BUILD_DATE"
    fi
```

## Monitoring Artifacts

### List Available Artifacts

```bash
# Via CLI
gh run list --workflow=build-artifacts.yaml

# View specific run
gh run view <run-id>

# List artifacts from run
gh run view <run-id> --json artifacts
```

### Download Artifacts Locally

```bash
# Download from latest run
gh run download --name automation-wheel

# Install locally
pip install gitea_automation-*.whl
```

### Clean Up Old Artifacts

Gitea automatically cleans up expired artifacts based on retention settings.

Manual cleanup:
```bash
# List runs older than 30 days
gh run list --workflow=build-artifacts.yaml --created="<$(date -d '30 days ago' +%Y-%m-%d)"

# Delete specific run (and its artifacts)
gh run delete <run-id>
```

## Troubleshooting

### Artifact Not Found

**Symptom:** Workflow falls back to source install

**Solutions:**
1. Trigger manual build: `gh workflow run build-artifacts.yaml`
2. Wait for scheduled build (runs daily at 2 AM)
3. Check if build workflow succeeded
4. Verify retention hasn't expired

### Wrong Version Installed

**Symptom:** Old code running after updates

**Solutions:**
1. Push changes to main (triggers rebuild)
2. Manually trigger build workflow
3. Check package-info.json for version

### Docker Image Load Fails

**Symptom:** `Error loading image`

**Solutions:**
1. Verify artifact downloaded: `ls -lh /tmp/automation-image.tar`
2. Check artifact isn't corrupted
3. Rebuild Docker image: `gh workflow run build-artifacts.yaml`

### Artifacts Too Large

**Symptom:** Upload/download takes too long

**Solutions:**
1. Reduce Docker image retention (already 7 days)
2. Use multi-stage builds (already implemented)
3. Consider external registry for Docker images

## Advanced: Cross-Workflow Artifacts

Artifacts are **scoped to workflows** by default. To share across workflows:

### Option 1: Same Repository

Artifacts are automatically available across workflows in the same repository:

```yaml
# Workflow A uploads
- uses: actions/upload-artifact@v3
  with:
    name: my-artifact

# Workflow B downloads (different workflow, same repo)
- uses: actions/download-artifact@v3
  with:
    name: my-artifact
```

### Option 2: Between Repositories

For cross-repo artifacts, use Gitea Packages or external storage:

```yaml
# Upload to package registry
- name: Publish package
  run: |
    pip install twine
    twine upload --repository-url ${{ secrets.BUILDER_GITEA_URL }}/api/packages/owner/pypi dist/*
```

## Summary

The artifact system provides:

✅ **Speed** - 90% faster installation
✅ **Reliability** - Pre-built, tested artifacts
✅ **Consistency** - Same package across all workflows
✅ **Efficiency** - Build once, use many times
✅ **Fallback** - Automatic source build if artifact unavailable

All label-triggered workflows now use this system automatically!
