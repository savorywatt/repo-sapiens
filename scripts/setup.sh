#!/bin/bash
# Quick setup script for builder automation

set -e

echo "🚀 Sapiens Automation Setup"
echo "=========================="
echo

# Check Python version
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed. Please install Python 3.11 or later."
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
echo "✓ Found Python $PYTHON_VERSION"

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv .venv
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source .venv/bin/activate

# Upgrade pip
echo "📦 Upgrading pip..."
pip install --upgrade pip setuptools wheel

# Install package
echo "📦 Installing builder automation..."
pip install -e .

echo
echo "✅ Installation complete!"
echo
echo "Next steps:"
echo "1. Copy .env.example to .env and configure:"
echo "   cp .env.example .env"
echo "   nano .env"
echo
echo "2. Activate the virtual environment:"
echo "   source .venv/bin/activate"
echo
echo "3. Run the automation:"
echo "   automation --help"
echo
echo "For CI/CD integration, see CI_CD_GUIDE.md"
