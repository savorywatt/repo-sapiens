#!/bin/bash
# Build script for repo-sapiens documentation

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Building repo-sapiens documentation...${NC}"

# Check if sphinx-build is available
if ! command -v sphinx-build &> /dev/null; then
    echo -e "${YELLOW}Sphinx not found. Installing documentation dependencies...${NC}"
    pip install -r requirements.txt
fi

# Clean previous builds
echo -e "${YELLOW}Cleaning previous builds...${NC}"
rm -rf _build/

# Build HTML documentation
echo -e "${YELLOW}Building HTML documentation...${NC}"
make html

# Check if build was successful
if [ $? -eq 0 ]; then
    echo -e "${GREEN}Documentation built successfully!${NC}"
    echo -e "${GREEN}View documentation at: _build/html/index.html${NC}"
    echo -e "\nTo view documentation locally, run:"
    echo -e "  ${YELLOW}cd _build/html && python -m http.server${NC}"
    exit 0
else
    echo -e "${RED}Documentation build failed!${NC}"
    exit 1
fi
