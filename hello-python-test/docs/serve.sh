#!/bin/bash
# Serve repo-sapiens documentation with live reload

set -e

# Check if sphinx-autobuild is available
if ! command -v sphinx-autobuild &> /dev/null; then
    echo "sphinx-autobuild not found. Installing documentation dependencies..."
    pip install -r requirements.txt
fi

echo "Starting documentation server with live reload..."
echo "View documentation at: http://localhost:8000"
echo "Press Ctrl+C to stop the server"

sphinx-autobuild source _build/html --port 8000
