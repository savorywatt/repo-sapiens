# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed
- Rebranded package from "repo-agent" to "repo-sapiens"
- Updated all GitHub repository URLs to https://github.com/savorywatt/repo-sapiens
- Updated package maintainer to @savorywatt
- Published placeholder package to PyPI (v0.0.1 and v0.0.2)

## [0.1.0] - 2025-12-22

### Added
- PyPI packaging with proper metadata and structure
- PEP 561 type hints support via py.typed marker file
- Split dependencies (core vs optional: monitoring, analytics, dev)
- Initial public release
- CLI commands: `automation daemon`, `automation process-issue`, `automation process-all`
- Gitea integration via REST API
- AI agent support (Claude API, Ollama)
- Workflow orchestration with state management
- Label-based issue automation
- Daemon optimization with recent activity checking
- Support for multiple AI providers
- Comprehensive logging with structlog
- Docker support for containerized deployment
- Pydantic-based configuration system
- State persistence with atomic file operations
- HTTP client with retry logic

### Fixed
- Daemon now skips execution when no recent activity detected (10-minute window)
- Label-triggered workflows now properly execute from main branch
- Virtual environment usage to avoid externally-managed-environment errors
- Duplicate workflow triggering by organizing example workflows
- PyPI packaging: Added py.typed to MANIFEST.in for source distribution support
- PyPI packaging: Verified correct version dynamic reference syntax
- PyPI packaging: Ensured MIT license properly specified (SPDX identifier)

### Validated
- Package builds successfully with python-build (wheel + source distribution)
- Both wheel and source distribution include py.typed marker file (PEP 561)
- Package metadata passes twine validation (PyPI compliance verified)
- Clean virtual environment installations work correctly
- Core dependencies install without optional dependencies (correct split)
- Version extraction works: automation.__version__ = "0.1.0"

[0.1.0]: https://github.com/savorywatt/repo-sapiens/releases/tag/v0.1.0
