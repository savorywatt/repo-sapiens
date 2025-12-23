# PyPI Critical Packaging Fixes - Implementation Plan

**Project**: repo-agent
**Location**: /home/ross/Workspace/repo-agent
**Status**: Ready for immediate execution
**Created**: 2025-12-22
**Based On**: Technical Review (plans/packageit/TECHNICAL_REVIEW.md)

## Executive Summary

This plan addresses the **7 critical packaging fixes** identified in the Python expert technical review, preparing repo-agent for PyPI publication. Most fixes were already implemented in commits 507dfcb and b75ea8d, but this plan documents what was done, identifies remaining issues, and provides verification steps.

**Current Status**:
- Package renamed from builder-automation → repo-agent
- Core fixes applied (version, license, py.typed)
- Dependencies split into core + optional
- Built successfully: repo_agent-0.1.0-py3-none-any.whl (110K)

**Remaining Work**:
- Fix version reference syntax error (CRITICAL)
- Update MANIFEST.in for py.typed
- Verify package naming consistency
- Run full validation suite
- Document rollback strategy

---

## PROJECT OVERVIEW

### What We're Fixing

We're implementing 7 critical fixes to make repo-agent PyPI-compliant:

1. **Version Dynamic Reference Syntax** - Fix incorrect attr reference
2. **License Specification** - Use SPDX identifier (already done)
3. **Package Naming Consistency** - Resolve PyPI vs import vs CLI naming
4. **Dependency Splitting** - Separate core from optional dependencies (already done)
5. **py.typed File** - PEP 561 type hints marker (file exists, needs MANIFEST update)
6. **__version__.py Structure** - Proper version module (already done)
7. **MANIFEST.in Updates** - Include py.typed in source distribution

### Key Architectural Decisions

**Decision 1: Package Naming Strategy**
- **PyPI Name**: `repo-agent` (kebab-case, descriptive)
- **Import Name**: `automation` (existing codebase, avoid breaking changes)
- **CLI Commands**: `automation` (primary), `builder` (legacy alias)
- **Rationale**: Minimizes breaking changes while providing clear PyPI identity

**Decision 2: Dependency Structure**
- **Core**: Only essential dependencies for CLI operation
- **Optional Groups**: monitoring, analytics, dev
- **Rationale**: Reduces installation size, allows users to install only what they need

**Decision 3: Version Management**
- **Single Source**: automation/__version__.py
- **Dynamic Loading**: pyproject.toml references via setuptools
- **Rationale**: Follows Python packaging best practices (PEP 621)

### Technology Stack

- **Build System**: setuptools >= 61.0 (PEP 517 compliant)
- **Build Frontend**: python-build (PEP 517)
- **Distribution Format**: Wheel (.whl) + Source (.tar.gz)
- **Version Management**: setuptools dynamic versioning
- **Type Checking**: mypy with py.typed marker (PEP 561)

---

## ARCHITECTURE DIAGRAM

```
repo-agent/
├── pyproject.toml          # Project metadata + build config
│   ├── [project]
│   │   ├── name = "repo-agent"
│   │   ├── dynamic = ["version"]  → reads from automation.__version__
│   │   ├── license = "MIT"        # SPDX identifier
│   │   └── dependencies = [...]   # Core only
│   ├── [project.optional-dependencies]
│   │   ├── monitoring = [...]
│   │   ├── analytics = [...]
│   │   ├── dev = [...]
│   │   └── all = [...]
│   └── [tool.setuptools.dynamic]
│       └── version = {attr = "automation.__version__"}  # MUST FIX
│
├── automation/             # Python package
│   ├── __init__.py        # Exports __version__
│   ├── __version__.py     # __version__ = "0.1.0"
│   ├── py.typed           # Empty PEP 561 marker
│   └── ...
│
├── MANIFEST.in            # Controls source distribution contents
│   └── include py.typed   # MUST ADD
│
├── LICENSE                # MIT license text
└── README.md              # PyPI landing page
```

### Data Flow: Version Resolution

```
1. setuptools reads pyproject.toml
2. Sees version = {attr = "automation.__version__"}
3. Imports automation package
4. Reads automation.__version__.py
5. Extracts __version__ = "0.1.0"
6. Uses "0.1.0" as package version
7. Embeds in wheel metadata
```

### Package Installation Flow

```
User: pip install repo-agent
  ↓
PyPI serves: repo_agent-0.1.0-py3-none-any.whl
  ↓
Pip extracts wheel
  ↓
Installs to: site-packages/automation/
  ↓
Creates CLI entries:
  - /usr/local/bin/automation → automation.main:cli
  - /usr/local/bin/builder → automation.main:cli
  ↓
User can: import automation
User can: automation --help
```

---

## DEVELOPMENT PHASES

### Phase 0: Pre-Flight Checks (PARALLEL GROUP A)
*Tasks that validate current state before making changes*

**Objective**: Verify current package state and identify exactly what needs fixing

#### Task 0.1: Audit Current pyproject.toml Configuration
**Parallel Status**: Can run in parallel with Tasks 0.2, 0.3, 0.4

- **Objective**: Verify all pyproject.toml settings match requirements
- **Prerequisites**: None
- **Technical Approach**:
  1. Read `/home/ross/Workspace/repo-agent/pyproject.toml`
  2. Check each critical field:
     - `name`: Should be "repo-agent"
     - `license`: Should be "MIT" (SPDX identifier, not {text = "MIT"})
     - `dynamic`: Should be ["version"]
     - `[tool.setuptools.dynamic].version`: Should be `{attr = "automation.__version__"}`
     - `dependencies`: Should contain only core deps
     - `[project.optional-dependencies]`: Should have monitoring, analytics, dev
     - `[tool.setuptools.package-data]`: Should include "py.typed"
  3. Document any discrepancies
- **Acceptance Criteria**:
  - [x] name = "repo-agent" ✓
  - [x] license = "MIT" ✓
  - [x] dynamic = ["version"] ✓
  - [ ] version = {attr = "automation.__version__"} - **NEEDS FIX**: Currently has double attribute reference
  - [x] Dependencies split ✓
  - [x] package-data includes py.typed ✓
- **Estimated Complexity**: Simple
- **Files to Check**: `/home/ross/Workspace/repo-agent/pyproject.toml`

#### Task 0.2: Verify __version__.py Structure
**Parallel Status**: Can run in parallel with Tasks 0.1, 0.3, 0.4

- **Objective**: Ensure version module follows best practices
- **Prerequisites**: None
- **Technical Approach**:
  1. Read `/home/ross/Workspace/repo-agent/automation/__version__.py`
  2. Verify structure:
     ```python
     """Version information for automation package."""

     __version__ = "0.1.0"
     ```
  3. Check that `automation/__init__.py` exports `__version__`
  4. Test import: `python3 -c "from automation import __version__; print(__version__)"`
- **Acceptance Criteria**:
  - [x] __version__.py exists with correct structure ✓
  - [x] __init__.py exports __version__ ✓
  - [ ] Import test succeeds (verify)
- **Estimated Complexity**: Simple
- **Files to Check**:
  - `/home/ross/Workspace/repo-agent/automation/__version__.py`
  - `/home/ross/Workspace/repo-agent/automation/__init__.py`

#### Task 0.3: Verify py.typed File Exists and is Included
**Parallel Status**: Can run in parallel with Tasks 0.1, 0.2, 0.4

- **Objective**: Ensure PEP 561 marker is present and will be distributed
- **Prerequisites**: None
- **Technical Approach**:
  1. Check file exists: `ls -la /home/ross/Workspace/repo-agent/automation/py.typed`
  2. Verify it's empty (correct per PEP 561)
  3. Check `pyproject.toml` includes it in package-data
  4. Check `MANIFEST.in` includes it for source distribution
- **Acceptance Criteria**:
  - [x] py.typed file exists ✓
  - [x] File is empty ✓
  - [x] Listed in pyproject.toml package-data ✓
  - [ ] **NEEDS FIX**: Not explicitly in MANIFEST.in
- **Estimated Complexity**: Simple
- **Files to Check**:
  - `/home/ross/Workspace/repo-agent/automation/py.typed`
  - `/home/ross/Workspace/repo-agent/pyproject.toml`
  - `/home/ross/Workspace/repo-agent/MANIFEST.in`

#### Task 0.4: Verify Package Naming Consistency
**Parallel Status**: Can run in parallel with Tasks 0.1, 0.2, 0.3

- **Objective**: Document all naming references and verify consistency
- **Prerequisites**: None
- **Technical Approach**:
  1. Check PyPI name in pyproject.toml: `name = "repo-agent"`
  2. Check import name: Directory is `automation/`
  3. Check CLI entry points in pyproject.toml
  4. Grep for any hardcoded package names in README, docs
  5. Create naming reference table
- **Acceptance Criteria**:
  - PyPI name documented: "repo-agent"
  - Import name documented: "automation"
  - CLI commands documented: "automation", "builder"
  - No inconsistencies in documentation
  - Naming strategy justified in this plan
- **Estimated Complexity**: Simple
- **Files to Check**:
  - `/home/ross/Workspace/repo-agent/pyproject.toml`
  - `/home/ross/Workspace/repo-agent/README.md`
  - `/home/ross/Workspace/repo-agent/automation/`

---

### Phase 1: Critical Fixes (SEQUENTIAL - Depends on Phase 0)
*Must be executed after Phase 0 identifies issues*

**Objective**: Fix the identified critical issues

#### Task 1.1: Fix Version Dynamic Reference Syntax
**Parallel Status**: MUST run before Task 1.3 (build test)

- **Objective**: Correct the setuptools version attribute reference
- **Prerequisites**: Task 0.1 completed
- **Technical Approach**:
  1. **Problem Identified**: Current syntax may have double reference
  2. **File to Edit**: `/home/ross/Workspace/repo-agent/pyproject.toml`
  3. **Current (potentially incorrect)**:
     ```toml
     [tool.setuptools.dynamic]
     version = {attr = "automation.__version__.__version__"}
     ```
  4. **Correct Syntax**:
     ```toml
     [tool.setuptools.dynamic]
     version = {attr = "automation.__version__"}
     ```
  5. **Why This Works**:
     - setuptools imports the `automation` package
     - Looks for the `__version__` attribute at the module level
     - The file `automation/__version__.py` contains `__version__ = "0.1.0"`
     - When Python imports `automation`, it reads `__init__.py` which does:
       ```python
       from automation.__version__ import __version__
       ```
     - This makes `__version__` available at `automation.__version__`
  6. **Edit Command**:
     ```bash
     # If current state is wrong, fix it:
     sed -i 's|version = {attr = "automation.__version__.__version__"}|version = {attr = "automation.__version__"}|g' \
       /home/ross/Workspace/repo-agent/pyproject.toml
     ```
- **Acceptance Criteria**:
  - pyproject.toml contains `version = {attr = "automation.__version__"}`
  - No double attribute reference (no `.__version__.__version__`)
  - Test build succeeds (Task 1.3)
- **Estimated Complexity**: Simple
- **Technology Stack**: TOML, setuptools
- **Rollback Strategy**: Git revert or restore from backup
- **Files Modified**: `/home/ross/Workspace/repo-agent/pyproject.toml`

#### Task 1.2: Update MANIFEST.in for py.typed
**Parallel Status**: Can run in parallel with Task 1.1

- **Objective**: Ensure py.typed is included in source distribution
- **Prerequisites**: Task 0.3 completed
- **Technical Approach**:
  1. **File to Edit**: `/home/ross/Workspace/repo-agent/MANIFEST.in`
  2. **Current State**: Check if py.typed is explicitly included
  3. **Required Addition**:
     ```
     # Include type information
     recursive-include automation *.typed
     ```
     OR more explicitly:
     ```
     include automation/py.typed
     ```
  4. **Why This Matters**:
     - `pyproject.toml` package-data handles wheel distribution
     - `MANIFEST.in` handles source distribution (.tar.gz)
     - Need both for complete coverage
  5. **Implementation**:
     ```bash
     echo "" >> /home/ross/Workspace/repo-agent/MANIFEST.in
     echo "# Include type checking marker (PEP 561)" >> /home/ross/Workspace/repo-agent/MANIFEST.in
     echo "include automation/py.typed" >> /home/ross/Workspace/repo-agent/MANIFEST.in
     ```
  6. **Verification**:
     ```bash
     # After building, extract tar.gz and verify:
     tar -tzf dist/repo_agent-0.1.0.tar.gz | grep py.typed
     # Should show: repo_agent-0.1.0/automation/py.typed
     ```
- **Acceptance Criteria**:
  - MANIFEST.in contains explicit reference to py.typed
  - Source distribution includes automation/py.typed (verified via tar -tzf)
  - Comment explains PEP 561 purpose
- **Estimated Complexity**: Simple
- **Technology Stack**: setuptools manifest system
- **Rollback Strategy**: Remove added lines from MANIFEST.in
- **Files Modified**: `/home/ross/Workspace/repo-agent/MANIFEST.in`

#### Task 1.3: Build and Verify Package
**Parallel Status**: MUST run after Tasks 1.1 and 1.2

- **Objective**: Build package with fixes and verify correctness
- **Prerequisites**: Tasks 1.1, 1.2 completed
- **Technical Approach**:
  1. **Clean Previous Builds**:
     ```bash
     cd /home/ross/Workspace/repo-agent
     rm -rf dist/ build/ *.egg-info/
     ```
  2. **Build Package**:
     ```bash
     python3 -m build
     ```
  3. **Verify Outputs**:
     ```bash
     ls -lh dist/
     # Should see:
     # - repo_agent-0.1.0-py3-none-any.whl
     # - repo_agent-0.1.0.tar.gz
     ```
  4. **Extract and Inspect Wheel**:
     ```bash
     mkdir -p /tmp/wheel-check
     cd /tmp/wheel-check
     unzip -q /home/ross/Workspace/repo-agent/dist/repo_agent-0.1.0-py3-none-any.whl

     # Verify contents:
     ls -la automation/py.typed  # Should exist
     cat automation/__version__.py  # Should show __version__ = "0.1.0"
     cat repo_agent-0.1.0.dist-info/METADATA | grep -E "^Name:|^Version:"
     # Should show:
     # Name: repo-agent
     # Version: 0.1.0
     ```
  5. **Extract and Inspect Source Distribution**:
     ```bash
     mkdir -p /tmp/sdist-check
     cd /tmp/sdist-check
     tar -xzf /home/ross/Workspace/repo-agent/dist/repo_agent-0.1.0.tar.gz

     # Verify py.typed is included:
     ls -la repo_agent-0.1.0/automation/py.typed
     ```
- **Acceptance Criteria**:
  - Build completes without errors
  - Wheel contains automation/py.typed
  - Wheel METADATA shows Name: repo-agent, Version: 0.1.0
  - Source distribution contains automation/py.typed
  - File sizes reasonable (~110KB wheel, ~90KB tar.gz)
- **Estimated Complexity**: Simple
- **Technology Stack**: python-build, setuptools, wheel
- **Rollback Strategy**: Previous dist/ artifacts saved in git history
- **Files Generated**:
  - `/home/ross/Workspace/repo-agent/dist/repo_agent-0.1.0-py3-none-any.whl`
  - `/home/ross/Workspace/repo-agent/dist/repo_agent-0.1.0.tar.gz`

---

### Phase 2: Validation and Testing (PARALLEL GROUP B)
*Comprehensive testing after fixes are applied*

**Objective**: Verify package works correctly in isolated environments

#### Task 2.1: Test Local Installation in Virtual Environment
**Parallel Status**: Can run in parallel with Task 2.2 after Phase 1 complete

- **Objective**: Verify package installs and works in clean environment
- **Prerequisites**: Task 1.3 completed (package built)
- **Technical Approach**:
  1. **Create Test Environment**:
     ```bash
     cd /tmp
     python3 -m venv test-repo-agent
     source test-repo-agent/bin/activate
     ```
  2. **Install from Wheel**:
     ```bash
     pip install /home/ross/Workspace/repo-agent/dist/repo_agent-0.1.0-py3-none-any.whl
     ```
  3. **Test Import**:
     ```bash
     python3 -c "import automation; print(automation.__version__)"
     # Should print: 0.1.0
     ```
  4. **Test CLI Commands**:
     ```bash
     automation --version
     builder --version
     automation --help
     ```
  5. **Test Type Hints**:
     ```bash
     # In venv, create test file:
     cat > test_types.py << 'EOF'
     from automation.models import BuildResult

     def check_result(result: BuildResult) -> bool:
         return result.success
     EOF

     # Run mypy (if installed in test env):
     pip install mypy
     mypy test_types.py --strict
     # Should type-check successfully
     ```
  6. **Test Optional Dependencies**:
     ```bash
     # Should NOT have monitoring deps:
     pip list | grep fastapi  # Should be empty

     # Install optional group:
     pip install 'repo-agent[monitoring]'
     pip list | grep fastapi  # Should show fastapi
     ```
  7. **Cleanup**:
     ```bash
     deactivate
     rm -rf /tmp/test-repo-agent
     ```
- **Acceptance Criteria**:
  - Package installs without errors
  - Import works: `import automation`
  - __version__ accessible and correct
  - Both CLI commands work
  - Type hints recognized by mypy
  - Optional dependencies install correctly
  - No unexpected dependencies in base install
- **Estimated Complexity**: Medium
- **Technology Stack**: venv, pip, mypy
- **Rollback Strategy**: N/A (testing only)

#### Task 2.2: Validate Package Metadata
**Parallel Status**: Can run in parallel with Task 2.1 after Phase 1 complete

- **Objective**: Ensure all metadata is correct and PyPI-compliant
- **Prerequisites**: Task 1.3 completed
- **Technical Approach**:
  1. **Install validation tools**:
     ```bash
     pip install twine check-manifest
     ```
  2. **Run twine check**:
     ```bash
     cd /home/ross/Workspace/repo-agent
     python3 -m twine check dist/*
     ```
     - Should show: "PASSED" for all files
     - Validates README renders correctly on PyPI
     - Checks metadata compliance
  3. **Run check-manifest**:
     ```bash
     check-manifest
     ```
     - Validates MANIFEST.in completeness
     - Ensures all expected files are included
  4. **Inspect METADATA file directly**:
     ```bash
     unzip -p dist/repo_agent-0.1.0-py3-none-any.whl repo_agent-0.1.0.dist-info/METADATA > /tmp/metadata.txt

     # Check critical fields:
     grep "^Name:" /tmp/metadata.txt
     grep "^Version:" /tmp/metadata.txt
     grep "^License:" /tmp/metadata.txt
     grep "^Requires-Python:" /tmp/metadata.txt
     grep "^Requires-Dist:" /tmp/metadata.txt

     # Should show:
     # Name: repo-agent
     # Version: 0.1.0
     # License: MIT
     # Requires-Python: >=3.11
     # Requires-Dist: pydantic>=2.5.0
     # ... (other core deps, no optional deps unless extras specified)
     ```
  5. **Validate classifiers**:
     ```bash
     grep "^Classifier:" /tmp/metadata.txt
     # Should NOT contain duplicate license classifiers
     # Should include valid PyPI classifiers
     ```
- **Acceptance Criteria**:
  - twine check passes all files
  - check-manifest finds no issues
  - METADATA contains correct Name, Version, License
  - Requires-Python set to >=3.11
  - Only core dependencies in base Requires-Dist
  - No classifier conflicts
  - README content present in METADATA (Description field)
- **Estimated Complexity**: Simple
- **Technology Stack**: twine, check-manifest, setuptools
- **Rollback Strategy**: N/A (validation only)

#### Task 2.3: Test Installation from Source Distribution
**Parallel Status**: Can run after Task 1.3, can run parallel with 2.1/2.2

- **Objective**: Verify source distribution builds and installs correctly
- **Prerequisites**: Task 1.3 completed
- **Technical Approach**:
  1. **Create test environment**:
     ```bash
     cd /tmp
     python3 -m venv test-sdist
     source test-sdist/bin/activate
     ```
  2. **Install from source tarball**:
     ```bash
     pip install /home/ross/Workspace/repo-agent/dist/repo_agent-0.1.0.tar.gz
     ```
     - This will trigger setuptools build process
     - Verifies build works on end-user machines
  3. **Run same tests as Task 2.1**:
     ```bash
     python3 -c "import automation; print(automation.__version__)"
     automation --version
     ```
  4. **Verify py.typed was installed**:
     ```bash
     python3 -c "import automation; import os; print(os.path.dirname(automation.__file__))"
     # Note the path, then:
     ls -la $(python3 -c "import automation, os; print(os.path.dirname(automation.__file__))")/py.typed
     ```
  5. **Cleanup**:
     ```bash
     deactivate
     rm -rf /tmp/test-sdist
     ```
- **Acceptance Criteria**:
  - Source distribution builds and installs successfully
  - All import and CLI tests pass
  - py.typed file installed in correct location
  - No build warnings or errors
- **Estimated Complexity**: Simple
- **Technology Stack**: pip, setuptools
- **Rollback Strategy**: N/A (testing only)

---

### Phase 3: Documentation and Finalization (PARALLEL GROUP C)
*Can start while Phase 2 tests are running*

**Objective**: Document changes and prepare for publication

#### Task 3.1: Update CHANGELOG.md
**Parallel Status**: Can run in parallel with Tasks 3.2, 3.3

- **Objective**: Document all fixes in changelog
- **Prerequisites**: Phase 1 completed
- **Technical Approach**:
  1. **File to Edit**: `/home/ross/Workspace/repo-agent/CHANGELOG.md`
  2. **Add New Section**:
     ```markdown
     ## [0.1.1] - 2025-12-22

     ### Fixed
     - Fixed version dynamic reference syntax in pyproject.toml
     - Added automation/py.typed to MANIFEST.in for source distributions
     - Verified PEP 561 type hint support

     ### Changed
     - Updated package metadata validation
     - Improved build verification process
     ```
  3. **Only if Significant**: If these are pre-release fixes before 0.1.0:
     ```markdown
     ## [0.1.0] - 2025-12-22

     ### Fixed (Pre-release)
     - Fixed version dynamic reference syntax in pyproject.toml
     - Corrected license specification to use SPDX identifier (MIT)
     - Split dependencies into core and optional groups
     - Added py.typed marker file for PEP 561 compliance
     - Updated MANIFEST.in to include py.typed in source distribution

     ### Changed (Pre-release)
     - Renamed package from builder-automation to repo-agent
     - Improved package naming consistency (PyPI: repo-agent, import: automation)

     ### Added
     - Initial release
     - AI-driven Git workflow automation
     - Gitea API integration
     - Monitoring and analytics optional dependencies
     ```
- **Acceptance Criteria**:
  - CHANGELOG.md updated with all fixes
  - Follows Keep a Changelog format
  - Version number matches package version
  - Date is accurate
  - All 7 critical fixes mentioned
- **Estimated Complexity**: Simple
- **Technology Stack**: Markdown
- **Rollback Strategy**: Git revert
- **Files Modified**: `/home/ross/Workspace/repo-agent/CHANGELOG.md`

#### Task 3.2: Create Package Verification Checklist
**Parallel Status**: Can run in parallel with Tasks 3.1, 3.3

- **Objective**: Document verification steps for future releases
- **Prerequisites**: Phase 2 completed
- **Technical Approach**:
  1. **Create File**: `/home/ross/Workspace/repo-agent/PACKAGE_CHECKLIST.md`
  2. **Content Template**:
     ```markdown
     # Package Release Checklist

     Use this checklist before every PyPI release to ensure quality.

     ## Pre-Build
     - [ ] Version bumped in `automation/__version__.py`
     - [ ] CHANGELOG.md updated with new version and changes
     - [ ] All tests pass: `pytest tests/`
     - [ ] Type checking passes: `mypy automation/`
     - [ ] Linting passes: `ruff check automation/`
     - [ ] Git working directory clean

     ## Build
     - [ ] Clean previous builds: `rm -rf dist/ build/ *.egg-info/`
     - [ ] Build package: `python3 -m build`
     - [ ] Verify outputs exist: `ls dist/`

     ## Validation
     - [ ] Run twine check: `twine check dist/*`
     - [ ] Run check-manifest: `check-manifest`
     - [ ] Test wheel installation in clean venv
     - [ ] Test source dist installation in clean venv
     - [ ] Verify CLI commands work: `automation --version`
     - [ ] Verify imports work: `python -c "import automation"`
     - [ ] Verify py.typed included: Check in wheel and installed package

     ## Metadata Verification
     - [ ] Extract METADATA: `unzip -p dist/*.whl */METADATA > metadata.txt`
     - [ ] Verify Name: Should be "repo-agent"
     - [ ] Verify Version: Should match automation.__version__
     - [ ] Verify License: Should be "MIT"
     - [ ] Verify dependencies: Only core deps in base, optionals separate

     ## Test PyPI (Recommended)
     - [ ] Upload to Test PyPI: `twine upload --repository testpypi dist/*`
     - [ ] Install from Test PyPI in clean venv
     - [ ] Verify package works

     ## Production PyPI
     - [ ] Tag release in git: `git tag v0.1.0`
     - [ ] Push tag: `git push origin v0.1.0`
     - [ ] Upload to PyPI: `twine upload dist/*`
     - [ ] Verify on PyPI: https://pypi.org/project/repo-agent/
     - [ ] Install from PyPI in clean venv: `pip install repo-agent`
     - [ ] Test installed package

     ## Post-Release
     - [ ] Create GitHub/Gitea release with changelog
     - [ ] Announce release (if applicable)
     - [ ] Monitor for issues
     ```
  3. **Save to repository**
- **Acceptance Criteria**:
  - Checklist file created
  - All critical steps documented
  - Clear, actionable items
  - Matches actual process from this plan
- **Estimated Complexity**: Simple
- **Technology Stack**: Markdown
- **Rollback Strategy**: N/A (new file)
- **Files Created**: `/home/ross/Workspace/repo-agent/PACKAGE_CHECKLIST.md`

#### Task 3.3: Document Rollback Strategy
**Parallel Status**: Can run in parallel with Tasks 3.1, 3.2

- **Objective**: Document how to handle broken releases
- **Prerequisites**: None (documentation task)
- **Technical Approach**:
  1. **Add Section to README or Create ROLLBACK.md**
  2. **Content**:
     ```markdown
     # Rollback Strategy for PyPI Releases

     ## Important: PyPI Deletions Are Not Allowed

     PyPI does not allow deletion of published releases. Once uploaded, a version
     is permanent. This prevents dependency confusion attacks and ensures
     reproducibility.

     ## If a Release is Broken

     ### Option 1: Yank the Release (Recommended)

     ```bash
     # Yank a broken version (makes it non-installable by default)
     twine upload --repository pypi --yank "Broken: <reason>" dist/*

     # Or via PyPI web interface:
     # 1. Go to https://pypi.org/project/repo-agent/
     # 2. Click on the broken version
     # 3. Click "Options" → "Yank release"
     # 4. Provide reason
     ```

     Yanked releases:
     - Won't be installed by `pip install repo-agent`
     - Can still be installed explicitly: `pip install repo-agent==0.1.0`
     - Show up as yanked on PyPI with reason

     ### Option 2: Release a Patch Version

     ```bash
     # Fix the issue in code
     # Bump version in automation/__version__.py
     __version__ = "0.1.1"

     # Update CHANGELOG.md
     ## [0.1.1] - 2025-12-23
     ### Fixed
     - Fixed critical bug in 0.1.0

     # Rebuild and release
     rm -rf dist/
     python3 -m build
     twine check dist/*
     twine upload dist/*
     ```

     ### Option 3: Emergency Contact

     For critical security issues:
     1. Contact PyPI support: https://pypi.org/help/
     2. Request takedown (only for security/legal issues)
     3. Provide detailed justification

     ## Prevention

     Always use Test PyPI before production:

     ```bash
     # Upload to Test PyPI first
     twine upload --repository testpypi dist/*

     # Test installation
     pip install --index-url https://test.pypi.org/simple/ repo-agent

     # If everything works, upload to production
     twine upload dist/*
     ```

     ## Version Number Guidelines

     - Never reuse a version number
     - Use semantic versioning: MAJOR.MINOR.PATCH
     - Broken release → patch bump (0.1.0 → 0.1.1)
     - Breaking changes → major bump (0.1.0 → 1.0.0)
     - New features → minor bump (0.1.0 → 0.2.0)
     ```
  3. **Add to Documentation**
- **Acceptance Criteria**:
  - Rollback strategy documented
  - PyPI yank process explained
  - Patch release process documented
  - Prevention strategies included
- **Estimated Complexity**: Simple
- **Technology Stack**: Markdown
- **Rollback Strategy**: N/A (documentation)
- **Files Created or Modified**: `/home/ross/Workspace/repo-agent/ROLLBACK.md` or update README

---

## QUALITY ASSURANCE PLAN

### Testing Strategy by Phase

#### Phase 0: Pre-Flight Checks
**Type**: Configuration Auditing
**Tests**:
- Manual inspection of pyproject.toml fields
- File existence checks (py.typed, __version__.py)
- Import tests for __version__

**Pass Criteria**:
- All required files present
- All configuration fields correct or documented for fixing
- Import of automation.__version__ succeeds

#### Phase 1: Critical Fixes
**Type**: Build Verification
**Tests**:
- Clean build test (no errors)
- Wheel content inspection
- Source distribution content inspection
- METADATA field verification

**Pass Criteria**:
- `python3 -m build` completes successfully
- Wheel contains automation/py.typed
- Source dist contains automation/py.typed
- Version extracted correctly (0.1.0)
- No build warnings

#### Phase 2: Validation and Testing
**Type**: Integration Testing
**Tests**:

1. **Virtual Environment Installation Tests**:
   - Clean venv creation
   - Wheel installation
   - Source dist installation
   - Import tests
   - CLI command tests
   - Type checking with mypy
   - Optional dependency tests

2. **Metadata Validation Tests**:
   - twine check (PyPI compliance)
   - check-manifest (MANIFEST.in completeness)
   - METADATA field extraction and verification
   - Classifier validation

3. **Functional Tests**:
   - CLI help text
   - CLI version reporting
   - Basic command execution (if applicable)

**Pass Criteria**:
- All installations succeed without errors
- Imports work correctly
- CLI commands execute
- twine check passes
- check-manifest passes
- Type hints recognized by mypy
- Optional dependencies install separately

#### Phase 3: Documentation
**Type**: Documentation Review
**Tests**:
- CHANGELOG.md format validation
- Checklist completeness
- Rollback documentation clarity

**Pass Criteria**:
- CHANGELOG follows Keep a Changelog format
- Checklist matches actual process
- Rollback strategy is actionable

### Edge Cases and Error Conditions

#### Edge Case 1: Version Import Failure
**Scenario**: setuptools cannot import automation.__version__
**Cause**: Syntax error in __version__.py or __init__.py
**Test**:
```bash
python3 -c "from automation import __version__"
```
**Expected**: Should print version without error
**Mitigation**: Validate Python syntax before building

#### Edge Case 2: py.typed Missing in Distribution
**Scenario**: py.typed not included in wheel or source dist
**Cause**: Missing from MANIFEST.in or package-data
**Test**:
```bash
unzip -l dist/*.whl | grep py.typed
tar -tzf dist/*.tar.gz | grep py.typed
```
**Expected**: Both should list automation/py.typed
**Mitigation**: Task 1.2 adds explicit MANIFEST.in entry

#### Edge Case 3: Optional Dependencies Install as Core
**Scenario**: Installing repo-agent installs fastapi/uvicorn
**Cause**: Dependencies not properly split in pyproject.toml
**Test**:
```bash
# In clean venv:
pip install repo-agent
pip list | grep fastapi
```
**Expected**: Should return empty (fastapi not installed)
**Mitigation**: Verify pyproject.toml structure in Task 0.1

#### Edge Case 4: CLI Commands Not Available
**Scenario**: `automation` or `builder` commands not found
**Cause**: Entry points not properly configured
**Test**:
```bash
which automation
automation --version
```
**Expected**: Should show path and version
**Mitigation**: Verify [project.scripts] in pyproject.toml

#### Edge Case 5: Type Hints Not Recognized
**Scenario**: mypy doesn't recognize package as typed
**Cause**: py.typed missing from installed package
**Test**:
```bash
# After installation:
python3 -c "import automation, os; print(os.path.exists(os.path.join(os.path.dirname(automation.__file__), 'py.typed')))"
```
**Expected**: Should print True
**Mitigation**: Tasks 1.2 and 1.3 verify py.typed inclusion

### Performance Benchmarks

Not applicable for packaging tasks. Focus is on correctness, not performance.

### Security Considerations

#### Security Check 1: No Secrets in Distribution
**What**: Verify no API keys, tokens, or credentials in package
**How**:
```bash
# Extract wheel:
unzip dist/*.whl -d /tmp/wheel-check
grep -r "api_key\|token\|secret\|password" /tmp/wheel-check/ || echo "No secrets found"
```
**Expected**: No hardcoded secrets

#### Security Check 2: Dependencies Have No Known Vulnerabilities
**What**: Scan dependencies for CVEs
**How**:
```bash
pip install safety
safety check --file <(pip freeze)
```
**Expected**: No critical vulnerabilities (Note: This is advisory; known issues should be evaluated)

#### Security Check 3: MANIFEST.in Doesn't Expose Sensitive Files
**What**: Verify no .env, credentials, or private keys in source dist
**How**:
```bash
tar -tzf dist/*.tar.gz | grep -E "\.env$|credentials|\.key$|\.pem$"
```
**Expected**: No sensitive files (should be excluded by MANIFEST.in)

---

## DEPLOYMENT STRATEGY

### Environment Setup

**Development Environment**:
- Location: `/home/ross/Workspace/repo-agent`
- Python Version: 3.11+
- Build Tools: python3-build, twine, check-manifest
- Virtual Environment: Recommended for testing

**Test PyPI**:
- URL: https://test.pypi.org
- Purpose: Staging environment for package validation
- Credentials: Stored in `~/.pypirc` or environment variables

**Production PyPI**:
- URL: https://pypi.org
- Purpose: Public package distribution
- Credentials: API token (never commit)

### Pre-Deployment Checklist

Before uploading to PyPI:

1. [ ] All Phase 1 tasks completed
2. [ ] All Phase 2 tests passed
3. [ ] Version number is correct and unique
4. [ ] CHANGELOG.md updated
5. [ ] Git working directory clean
6. [ ] Git tag created: `git tag v0.1.0`
7. [ ] Tag pushed: `git push origin v0.1.0`

### Deployment Steps

#### Step 1: Test PyPI Upload (RECOMMENDED)

```bash
# Ensure credentials configured for Test PyPI
python3 -m twine upload --repository testpypi dist/*

# Test installation from Test PyPI
python3 -m venv /tmp/test-pypi-install
source /tmp/test-pypi-install/bin/activate
pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ repo-agent
automation --version
deactivate
rm -rf /tmp/test-pypi-install
```

**Note**: `--extra-index-url https://pypi.org/simple/` is needed because dependencies (pydantic, httpx, etc.) are on production PyPI, not Test PyPI.

#### Step 2: Production PyPI Upload

```bash
# Upload to production PyPI
python3 -m twine upload dist/*

# Verify on PyPI
# Visit: https://pypi.org/project/repo-agent/

# Test installation from production
python3 -m venv /tmp/pypi-install
source /tmp/pypi-install/bin/activate
pip install repo-agent
automation --version
python3 -c "import automation; print(automation.__version__)"
deactivate
rm -rf /tmp/pypi-install
```

#### Step 3: Post-Deployment Verification

```bash
# Verify package page renders correctly
curl -s https://pypi.org/project/repo-agent/ | grep "repo-agent"

# Check metadata
curl -s https://pypi.org/pypi/repo-agent/json | jq '.info.version'

# Verify dependencies listed correctly
curl -s https://pypi.org/pypi/repo-agent/json | jq '.info.requires_dist'
```

### Rollback Procedures

**If Upload Succeeds But Package is Broken**:

1. **Immediately Yank the Release**:
   ```bash
   # Via PyPI web interface:
   # 1. Log in to https://pypi.org
   # 2. Go to project page
   # 3. Click on broken version
   # 4. Click "Options" → "Yank release"
   # 5. Enter reason: "Broken: <specific issue>"
   ```

2. **Fix the Issue Locally**:
   ```bash
   # Fix code
   # Bump version in automation/__version__.py
   __version__ = "0.1.1"

   # Update CHANGELOG.md
   # Rebuild
   rm -rf dist/
   python3 -m build

   # Test thoroughly
   twine check dist/*
   # ... run all Phase 2 tests ...
   ```

3. **Release Patch Version**:
   ```bash
   # Upload new version
   twine upload dist/*
   ```

4. **Notify Users**:
   - Update PyPI project description
   - Create GitHub/Gitea release notes
   - If critical, send announcement

**If Upload Fails**:

- Check error message from twine
- Common issues:
  - Invalid credentials: Update `~/.pypirc` or token
  - Version conflict: Version already exists, bump version
  - Metadata validation: Run `twine check dist/*`
  - Network issues: Retry upload

### Monitoring and Observability

**Post-Release Monitoring**:

1. **PyPI Download Stats**:
   - Check via PyPI web interface (limited)
   - Use pypistats: `pip install pypistats; pypistats overall repo-agent`

2. **Issue Tracking**:
   - Monitor GitHub/Gitea issues for installation problems
   - Search for "repo-agent" on Stack Overflow, forums

3. **Dependency Health**:
   - Use dependabot or similar to track dependency updates
   - Regularly run `safety check` for security vulnerabilities

4. **Installation Success Rate**:
   - If possible, add optional telemetry (opt-in)
   - Monitor error reports from users

**Logs and Diagnostics**:

Users experiencing issues should provide:
```bash
pip install --verbose repo-agent 2>&1 | tee install.log
python3 -c "import automation; print(automation.__version__)"
automation --version
pip list | grep repo-agent
```

---

## RISK ASSESSMENT

### Risk Matrix

| Risk ID | Risk Description | Severity | Probability | Impact | Mitigation |
|---------|------------------|----------|-------------|--------|------------|
| R1 | Version syntax error breaks build | HIGH | LOW | Build fails, cannot release | Task 1.1 fixes syntax, Task 1.3 validates |
| R2 | py.typed missing from distribution | MEDIUM | MEDIUM | Type checkers don't recognize types | Task 1.2 adds to MANIFEST.in, Task 2.3 validates |
| R3 | Package name confusion (repo-agent vs automation) | MEDIUM | MEDIUM | User confusion, support burden | Document clearly in README, accept as design decision |
| R4 | Optional dependencies install as core | MEDIUM | LOW | Large installation size, user complaints | Task 0.1 validates split, Task 2.1 tests |
| R5 | README doesn't render on PyPI | LOW | LOW | Poor first impression | twine check validates (Task 2.2) |
| R6 | CLI commands not available after install | MEDIUM | LOW | Unusable package | Task 2.1 tests CLI explicitly |
| R7 | Breaking existing users during rename | HIGH | LOW | Existing users break (if any) | Not applicable: Pre-1.0 release, no users yet |
| R8 | PyPI upload credentials leak | HIGH | LOW | Security breach | Never commit credentials, use tokens, rotate regularly |
| R9 | Yanked release confuses users | LOW | LOW | User confusion | Document rollback strategy (Task 3.3) |
| R10 | Cross-platform installation issues | MEDIUM | MEDIUM | Windows/Mac users cannot install | Not addressed in this plan; needs separate testing |

### Mitigation Strategies

**For R1 (Version Syntax Error)**:
- **Prevention**: Manual review of pyproject.toml changes
- **Detection**: Build test in Task 1.3
- **Recovery**: Fix syntax, rebuild

**For R2 (py.typed Missing)**:
- **Prevention**: Explicit MANIFEST.in entry (Task 1.2)
- **Detection**: Distribution inspection (Task 1.3), installation test (Task 2.3)
- **Recovery**: Fix MANIFEST.in, rebuild, release patch version

**For R3 (Package Name Confusion)**:
- **Prevention**: Clear documentation in README
- **Acceptance**: Document naming strategy:
  - PyPI: repo-agent (discoverable, descriptive)
  - Import: automation (existing codebase)
  - CLI: automation/builder (both work)
- **Future**: Consider renaming `automation/` → `repo_agent/` in 1.0 release

**For R4 (Optional Dependencies)**:
- **Prevention**: Validate pyproject.toml structure (Task 0.1)
- **Detection**: Clean venv installation test (Task 2.1)
- **Recovery**: Fix pyproject.toml, rebuild

**For R5 (README Rendering)**:
- **Prevention**: Use standard Markdown, avoid complex features
- **Detection**: twine check (Task 2.2)
- **Recovery**: Fix README, rebuild

**For R6 (CLI Not Available)**:
- **Prevention**: Verify [project.scripts] configuration
- **Detection**: CLI test in Task 2.1
- **Recovery**: Fix entry points in pyproject.toml, rebuild

**For R8 (Credential Leak)**:
- **Prevention**: Use `.env` for local credentials (gitignored), use PyPI tokens
- **Policy**: Never commit tokens, rotate tokens regularly
- **Recovery**: Immediately revoke leaked token, rotate, audit commits

**For R10 (Cross-Platform Issues)**:
- **Note**: Not addressed in this plan
- **Future Work**: Set up Windows/Mac test environments or CI/CD

---

## TIMELINE AND ESTIMATES

### Time Estimates by Phase

| Phase | Tasks | Estimated Time | Dependencies |
|-------|-------|----------------|--------------|
| Phase 0 | 4 tasks (parallel) | 30 minutes | None |
| Phase 1 | 3 tasks (sequential) | 45 minutes | Phase 0 |
| Phase 2 | 3 tasks (2 parallel after 1.3) | 1 hour | Phase 1 |
| Phase 3 | 3 tasks (parallel) | 45 minutes | Phase 1 (can overlap with Phase 2) |
| **Total** | **13 tasks** | **2.5 - 3 hours** | - |

### Detailed Task Timeline

```
Phase 0 (Parallel): Tasks 0.1, 0.2, 0.3, 0.4
├─ 00:00 - 00:30 | All tasks run simultaneously
└─ Deliverable: Audit report, current state documented

Phase 1 (Sequential):
├─ 00:30 - 00:45 | Task 1.1: Fix version syntax (15 min)
├─ 00:30 - 00:45 | Task 1.2: Update MANIFEST.in (15 min, parallel with 1.1)
└─ 00:45 - 01:00 | Task 1.3: Build and verify (15 min, after 1.1 & 1.2)
    └─ Deliverable: Built package (wheel + source dist)

Phase 2 (Mixed):
├─ 01:00 - 01:30 | Task 2.1: Venv installation tests (30 min)
├─ 01:00 - 01:15 | Task 2.2: Metadata validation (15 min, parallel with 2.1)
└─ 01:15 - 01:30 | Task 2.3: Source dist test (15 min, parallel with 2.1)
    └─ Deliverable: Test reports, validation passed

Phase 3 (Parallel):
├─ 01:00 - 02:00 | Task 3.1: Update CHANGELOG (15 min)
├─ 01:00 - 02:00 | Task 3.2: Create checklist (20 min)
└─ 01:00 - 02:00 | Task 3.3: Document rollback (10 min)
    └─ Deliverable: Updated documentation

Optional: Test PyPI Upload
└─ 02:00 - 02:30 | Upload, test install, verify (30 min)

Optional: Production PyPI Upload
└─ 02:30 - 03:00 | Upload, verify, announce (30 min)
```

### Critical Path

```
Start → Task 0.1 (audit) → Task 1.1 (fix version) → Task 1.3 (build) → Task 2.1 (test install) → Complete
```

All other tasks either run in parallel or are non-critical path documentation tasks.

### Buffered Timeline (Conservative)

For planning purposes, assume:
- **Phase 0-1**: 1 hour (includes learning, issues)
- **Phase 2**: 1.5 hours (includes thorough testing)
- **Phase 3**: 1 hour (documentation writing)
- **Buffer**: 30 minutes (unexpected issues)
- **Total**: 4 hours

---

## SUCCESS CRITERIA

### Phase 0 Success Criteria
- [ ] All 4 audit tasks completed
- [ ] Current state documented with issues identified
- [ ] List of required fixes created
- [ ] No blocking issues discovered

### Phase 1 Success Criteria
- [ ] pyproject.toml version syntax corrected
- [ ] MANIFEST.in includes py.typed
- [ ] Package builds without errors
- [ ] Wheel and source dist created
- [ ] Both distributions contain automation/py.typed
- [ ] METADATA shows correct Name, Version, License

### Phase 2 Success Criteria
- [ ] Package installs from wheel in clean venv
- [ ] Package installs from source dist in clean venv
- [ ] Import works: `import automation; print(automation.__version__)`
- [ ] CLI commands work: `automation --version`, `builder --version`
- [ ] Type hints recognized by mypy
- [ ] Optional dependencies install separately
- [ ] twine check passes
- [ ] check-manifest passes
- [ ] No unexpected dependencies in base install

### Phase 3 Success Criteria
- [ ] CHANGELOG.md updated with fixes
- [ ] PACKAGE_CHECKLIST.md created
- [ ] ROLLBACK.md or rollback section documented
- [ ] Documentation is clear and actionable

### Overall Project Success Criteria
- [ ] All 7 critical fixes implemented
- [ ] Package builds successfully
- [ ] Package passes all validation tests
- [ ] Package installs and works correctly
- [ ] Documentation complete
- [ ] Ready for PyPI publication

---

## APPENDICES

### Appendix A: Current State Summary

**What's Already Done** (from commits 507dfcb and b75ea8d):

1. ✅ LICENSE file created (MIT)
2. ✅ automation/__version__.py created with `__version__ = "0.1.0"`
3. ✅ automation/py.typed created (empty marker file)
4. ✅ automation/__init__.py exports __version__
5. ✅ pyproject.toml updated:
   - ✅ name = "repo-agent"
   - ✅ license = "MIT" (SPDX identifier)
   - ✅ dynamic = ["version"]
   - ✅ Dependencies split (core vs optional)
   - ✅ CLI scripts: automation and builder
   - ✅ package-data includes py.typed
6. ✅ CHANGELOG.md created
7. ✅ Package built successfully

**What Needs Verification/Fixing**:

1. ⚠️ Version syntax in pyproject.toml (may have double reference)
2. ⚠️ MANIFEST.in doesn't explicitly include py.typed
3. ⚠️ No formal validation tests run
4. ⚠️ Rollback strategy not documented

### Appendix B: File Locations Reference

| File | Path | Purpose |
|------|------|---------|
| pyproject.toml | /home/ross/Workspace/repo-agent/pyproject.toml | Project metadata and build config |
| __version__.py | /home/ross/Workspace/repo-agent/automation/__version__.py | Version single source of truth |
| __init__.py | /home/ross/Workspace/repo-agent/automation/__init__.py | Package initialization, exports __version__ |
| py.typed | /home/ross/Workspace/repo-agent/automation/py.typed | PEP 561 marker (empty file) |
| MANIFEST.in | /home/ross/Workspace/repo-agent/MANIFEST.in | Controls source distribution contents |
| LICENSE | /home/ross/Workspace/repo-agent/LICENSE | MIT license text |
| CHANGELOG.md | /home/ross/Workspace/repo-agent/CHANGELOG.md | Version history |
| README.md | /home/ross/Workspace/repo-agent/README.md | Project documentation, PyPI landing page |
| dist/ | /home/ross/Workspace/repo-agent/dist/ | Build artifacts (wheel, tar.gz) |

### Appendix C: Command Reference

**Build Commands**:
```bash
# Clean previous builds
rm -rf /home/ross/Workspace/repo-agent/dist/ /home/ross/Workspace/repo-agent/build/ /home/ross/Workspace/repo-agent/*.egg-info/

# Build package
cd /home/ross/Workspace/repo-agent
python3 -m build

# Check outputs
ls -lh /home/ross/Workspace/repo-agent/dist/
```

**Validation Commands**:
```bash
# Validate with twine
python3 -m twine check /home/ross/Workspace/repo-agent/dist/*

# Validate with check-manifest
cd /home/ross/Workspace/repo-agent
check-manifest

# Test import
python3 -c "from automation import __version__; print(__version__)"
```

**Testing Commands**:
```bash
# Create test venv
python3 -m venv /tmp/test-repo-agent
source /tmp/test-repo-agent/bin/activate

# Install from wheel
pip install /home/ross/Workspace/repo-agent/dist/repo_agent-0.1.0-py3-none-any.whl

# Test
python3 -c "import automation; print(automation.__version__)"
automation --version
builder --version

# Cleanup
deactivate
rm -rf /tmp/test-repo-agent
```

**Inspection Commands**:
```bash
# Inspect wheel contents
unzip -l /home/ross/Workspace/repo-agent/dist/repo_agent-0.1.0-py3-none-any.whl

# Extract and read METADATA
unzip -p /home/ross/Workspace/repo-agent/dist/repo_agent-0.1.0-py3-none-any.whl repo_agent-0.1.0.dist-info/METADATA

# Inspect source dist contents
tar -tzf /home/ross/Workspace/repo-agent/dist/repo_agent-0.1.0.tar.gz

# Check for py.typed
unzip -l /home/ross/Workspace/repo-agent/dist/repo_agent-0.1.0-py3-none-any.whl | grep py.typed
tar -tzf /home/ross/Workspace/repo-agent/dist/repo_agent-0.1.0.tar.gz | grep py.typed
```

### Appendix D: pyproject.toml Reference Configuration

**Correct [tool.setuptools.dynamic] Section**:
```toml
[tool.setuptools.dynamic]
version = {attr = "automation.__version__"}
```

**NOT**:
```toml
# WRONG - double reference:
version = {attr = "automation.__version__.__version__"}
```

**Explanation**:
- setuptools imports the `automation` package
- Looks for attribute `__version__` at package level
- `automation/__init__.py` does: `from automation.__version__ import __version__`
- This makes `__version__` available as `automation.__version__` (not `automation.__version__.__version__`)

### Appendix E: MANIFEST.in Best Practices

**Current MANIFEST.in**:
```
# Include package data
include README.md
include LICENSE
include QUICK_START.md
include CI_CD_GUIDE.md
include .env.example
include pyproject.toml

# Include automation package
recursive-include automation *.py
recursive-include automation/config *.yaml

# Exclude test files
recursive-exclude tests *
recursive-exclude automation/config playground_config.yaml

# Exclude development files
exclude test_*.py
exclude check_*.py
exclude *.sh
exclude docker-compose.yml
exclude Dockerfile
```

**Recommended Addition**:
```
# Include type checking marker (PEP 561)
include automation/py.typed
```

**Why Both pyproject.toml and MANIFEST.in?**:
- `pyproject.toml` [tool.setuptools.package-data]: Controls **wheel** (.whl) contents
- `MANIFEST.in`: Controls **source distribution** (.tar.gz) contents
- Need both to ensure py.typed in both distribution formats

### Appendix F: Testing Checklist Summary

Quick reference for validation:

```bash
# Phase 2.1: Installation Test
python3 -m venv /tmp/test && source /tmp/test/bin/activate
pip install /home/ross/Workspace/repo-agent/dist/repo_agent-0.1.0-py3-none-any.whl
python3 -c "import automation; print(automation.__version__)"
automation --version
pip list | grep fastapi  # Should be empty
pip install 'repo-agent[monitoring]'
pip list | grep fastapi  # Should show fastapi
deactivate && rm -rf /tmp/test

# Phase 2.2: Metadata Validation
cd /home/ross/Workspace/repo-agent
python3 -m twine check dist/*
check-manifest
unzip -p dist/repo_agent-0.1.0-py3-none-any.whl repo_agent-0.1.0.dist-info/METADATA | grep -E "^Name:|^Version:|^License:"

# Phase 2.3: Source Dist Test
python3 -m venv /tmp/sdist && source /tmp/sdist/bin/activate
pip install /home/ross/Workspace/repo-agent/dist/repo_agent-0.1.0.tar.gz
python3 -c "import automation; print(automation.__version__)"
automation --version
deactivate && rm -rf /tmp/sdist
```

### Appendix G: Package Naming Decision Rationale

**Why Keep "automation" as Import Name?**

1. **Existing Codebase**: All code already imports `automation`
2. **Breaking Changes**: Renaming would break all existing code
3. **Migration Cost**: High effort, low benefit for pre-1.0 release
4. **Precedent**: Many packages have different PyPI vs import names:
   - `pip install scikit-learn`, `import sklearn`
   - `pip install Pillow`, `import PIL`
   - `pip install beautifulsoup4`, `import bs4`

**Why "repo-agent" for PyPI?**

1. **Descriptive**: Clearly indicates purpose
2. **Availability**: Name was available on PyPI
3. **Generic**: Works for Gitea, GitHub, GitLab future support
4. **SEO**: More discoverable than "automation" (too generic)

**Future Consideration (Post 1.0)**:

Option to rename package directory `automation/` → `repo_agent/` in a future major version:
- Would align names across the board
- Requires migration guide
- Could provide `automation` as deprecated alias
- Major version (2.0) appropriate for this breaking change

---

## CONCLUSION

This plan provides a complete, executable roadmap for implementing all 7 critical PyPI packaging fixes identified in the technical review. Most work was already completed in previous commits; this plan focuses on verification, remaining fixes (version syntax, MANIFEST.in), and comprehensive testing.

**Immediate Next Steps**:

1. Execute Phase 0 to verify current state
2. Apply Phase 1 fixes if issues found
3. Run Phase 2 validation tests
4. Update Phase 3 documentation
5. Optionally upload to Test PyPI
6. Publish to production PyPI when ready

**Estimated Total Time**: 2.5 - 4 hours (including testing and documentation)

**Risk Level**: LOW - Most critical work already done, remaining tasks are verification and minor fixes

**Success Probability**: HIGH - Clear plan, most fixes already implemented, comprehensive testing strategy

---

## Quick Start Commands

For immediate execution, run these commands in sequence:

```bash
# Phase 0: Verify current state
cd /home/ross/Workspace/repo-agent
grep 'version = {attr' pyproject.toml  # Check syntax
ls -la automation/py.typed             # Verify exists
grep "py.typed" MANIFEST.in            # Check if included

# Phase 1: Apply fixes if needed
# If version syntax is wrong, fix it manually in pyproject.toml
# Add to MANIFEST.in if missing:
echo -e "\n# Include type checking marker (PEP 561)\ninclude automation/py.typed" >> MANIFEST.in

# Rebuild
rm -rf dist/ build/ *.egg-info/
python3 -m build

# Phase 2: Validate
python3 -m twine check dist/*
python3 -m venv /tmp/test-install
source /tmp/test-install/bin/activate
pip install dist/repo_agent-0.1.0-py3-none-any.whl
automation --version
python3 -c "import automation; print(automation.__version__)"
deactivate
rm -rf /tmp/test-install

# Phase 3: Document (update CHANGELOG.md manually)

# Ready for PyPI!
```

---

**Plan Version**: 1.0
**Last Updated**: 2025-12-22
**Maintainer**: repo-agent development team
**Status**: Ready for execution
