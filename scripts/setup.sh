#!/bin/bash
# Setup script for Gitea automation system

set -e

echo "======================================"
echo "Gitea Automation System - Setup"
echo "======================================"
echo ""

# Check Python version
echo "Checking Python version..."
python_version=$(python3 --version 2>&1 | awk '{print $2}')
required_version="3.11"

if [ "$(printf '%s\n' "$required_version" "$python_version" | sort -V | head -n1)" != "$required_version" ]; then
    echo "Error: Python 3.11 or higher required (found $python_version)"
    exit 1
fi
echo "✓ Python $python_version"
echo ""

# Create virtual environment
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
    echo "✓ Virtual environment created"
else
    echo "✓ Virtual environment exists"
fi
echo ""

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Install package
echo "Installing automation package..."
pip install -q -e .
echo "✓ Package installed"
echo ""

# Install development dependencies
read -p "Install development dependencies? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Installing development dependencies..."
    pip install -q -e ".[dev]"
    echo "✓ Development dependencies installed"
fi
echo ""

# Create necessary directories
echo "Creating directories..."
mkdir -p .automation/state
mkdir -p plans
echo "✓ Directories created"
echo ""

# Check for configuration
echo "Checking configuration..."
if [ ! -f "automation/config/automation_config.yaml" ]; then
    echo "Warning: automation_config.yaml not found"
    echo "Please configure automation/config/automation_config.yaml"
else
    echo "✓ Configuration file exists"
fi
echo ""

# Check for environment variables
echo "Checking environment variables..."
missing_vars=()

if [ -z "$GITEA_TOKEN" ]; then
    missing_vars+=("GITEA_TOKEN")
fi

if [ -z "$CLAUDE_API_KEY" ]; then
    missing_vars+=("CLAUDE_API_KEY")
fi

if [ ${#missing_vars[@]} -gt 0 ]; then
    echo "Warning: Missing environment variables:"
    for var in "${missing_vars[@]}"; do
        echo "  - $var"
    done
    echo ""
    echo "Set these variables or configure them in automation_config.yaml"
else
    echo "✓ Environment variables set"
fi
echo ""

# Test CLI
echo "Testing CLI..."
if automation --help > /dev/null 2>&1; then
    echo "✓ CLI working"
else
    echo "Error: CLI test failed"
    exit 1
fi
echo ""

# Run tests if pytest available
if command -v pytest &> /dev/null; then
    read -p "Run tests? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "Running tests..."
        pytest tests/ -v
    fi
fi
echo ""

echo "======================================"
echo "Setup Complete!"
echo "======================================"
echo ""
echo "Next steps:"
echo "1. Configure secrets (see docs/secrets-setup.md)"
echo "2. Review automation_config.yaml"
echo "3. Set up Gitea Actions workflows"
echo "4. Create your first issue with 'needs-planning' label"
echo ""
echo "Useful commands:"
echo "  automation --help                    # Show all commands"
echo "  automation list-active-plans         # List active workflows"
echo "  automation health-check              # Check system health"
echo ""
