# Agent Execution Tracking

This directory tracks the state of autonomous agents executing implementation plans.

## Directory Structure

Each subdirectory represents an agent working on a specific job:

- **pypi-fixes/** - Critical PyPI packaging fixes (prerequisite)
- **pypi-distribution/** - PyPI publishing workflow (TestPyPI → Production)
- **cli-foundation/** - CLI redesign Phase 1-2 foundation
- **credential-mgmt/** - Secure credential management system
- **git-discovery/** - Git repository discovery and parsing
- **template-system/** - Jinja2 workflow template system

## State Files

Each agent directory contains:
- `state.json` - Current execution state (task progress, status)
- `log.md` - Execution log with timestamps
- `errors.md` - Error tracking and resolution
- `output/` - Generated files and artifacts

## Usage

Agents can be restarted from their last checkpoint by reading the state.json file.
All state is preserved to allow recovery from failures.

## Execution Order

1. **pypi-fixes** (CRITICAL) - Must complete first
2. **pypi-distribution** - Depends on pypi-fixes
3. **cli-foundation**, **credential-mgmt**, **git-discovery**, **template-system** - Can run in parallel

Last updated: 2025-12-22
