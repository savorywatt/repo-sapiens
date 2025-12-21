#!/bin/bash
# Validation script for builder automation package

set -e

echo "🔍 Validating builder automation package"
echo "========================================"
echo

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check Python version
echo -n "Checking Python version... "
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
    MAJOR=$(python3 -c 'import sys; print(sys.version_info.major)')
    MINOR=$(python3 -c 'import sys; print(sys.version_info.minor)')

    if [ "$MAJOR" -ge 3 ] && [ "$MINOR" -ge 11 ]; then
        echo -e "${GREEN}✓${NC} Python $PYTHON_VERSION"
    else
        echo -e "${RED}✗${NC} Python $PYTHON_VERSION (need 3.11+)"
        exit 1
    fi
else
    echo -e "${RED}✗${NC} Python not found"
    exit 1
fi

# Check if package is installed
echo -n "Checking package installation... "
if python3 -c "import automation" 2>/dev/null; then
    echo -e "${GREEN}✓${NC} Package installed"
else
    echo -e "${RED}✗${NC} Package not installed"
    echo "Run: pip install -e ."
    exit 1
fi

# Check CLI command
echo -n "Checking CLI command... "
if command -v automation &> /dev/null; then
    echo -e "${GREEN}✓${NC} CLI available"
else
    echo -e "${RED}✗${NC} CLI not found"
    exit 1
fi

# Check dependencies
echo -n "Checking dependencies... "
python3 -c "
import sys
try:
    import pydantic
    import httpx
    import structlog
    import click
    import yaml
    print('OK')
except ImportError as e:
    print(f'Missing: {e}')
    sys.exit(1)
" && echo -e "${GREEN}✓${NC} All dependencies installed" || echo -e "${RED}✗${NC} Missing dependencies"

# Check configuration template
echo -n "Checking configuration template... "
if [ -f "automation/config/automation_config.yaml" ]; then
    echo -e "${GREEN}✓${NC} Config template exists"
else
    echo -e "${YELLOW}⚠${NC} Config template not found"
fi

# Check Docker files
echo -n "Checking Docker files... "
if [ -f "Dockerfile" ] && [ -f "docker-compose.yml" ]; then
    echo -e "${GREEN}✓${NC} Docker files present"
else
    echo -e "${YELLOW}⚠${NC} Docker files missing"
fi

# Check documentation
echo -n "Checking documentation... "
if [ -f "QUICK_START.md" ] && [ -f "CI_CD_GUIDE.md" ]; then
    echo -e "${GREEN}✓${NC} Documentation complete"
else
    echo -e "${YELLOW}⚠${NC} Some documentation missing"
fi

# Test CLI help
echo -n "Testing CLI help command... "
if automation --help &>/dev/null; then
    echo -e "${GREEN}✓${NC} CLI working"
else
    echo -e "${RED}✗${NC} CLI error"
    exit 1
fi

# Test import of main modules
echo -n "Testing module imports... "
python3 <<EOF
import sys
try:
    from automation.config.settings import AutomationSettings
    from automation.engine.orchestrator import WorkflowOrchestrator
    from automation.providers.gitea_rest import GiteaRestProvider
    from automation.providers.external_agent import ExternalAgentProvider
    print("OK")
except Exception as e:
    print(f"Error: {e}")
    sys.exit(1)
EOF
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓${NC} All modules importable"
else
    echo -e "${RED}✗${NC} Import errors"
    exit 1
fi

echo
echo -e "${GREEN}✅ Validation complete!${NC}"
echo
echo "Package is ready for deployment."
echo
echo "Next steps:"
echo "1. Configure .env file: cp .env.example .env"
echo "2. Docker: docker-compose up -d"
echo "3. Or run directly: automation daemon --interval 60"
echo
echo "See QUICK_START.md for more information."
