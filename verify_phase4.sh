#!/bin/bash
# Verification script for Phase 4 implementation

echo "======================================"
echo "Phase 4: Advanced Features Verification"
echo "======================================"
echo ""

# Color codes
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

check_file() {
    if [ -f "$1" ]; then
        echo -e "${GREEN}✓${NC} $1"
        return 0
    else
        echo -e "${RED}✗${NC} $1"
        return 1
    fi
}

check_dir() {
    if [ -d "$1" ]; then
        echo -e "${GREEN}✓${NC} $1/"
        return 0
    else
        echo -e "${RED}✗${NC} $1/"
        return 1
    fi
}

echo "Checking Core Files..."
echo "-------------------------------------"
check_file "pyproject.toml"
check_file ".gitignore"
check_file "README.md"
check_file "PHASE_4_SUMMARY.md"
check_file "PHASE_4_QUICK_REFERENCE.md"
echo ""

echo "Checking Directory Structure..."
echo "-------------------------------------"
check_dir "automation/engine"
check_dir "automation/monitoring"
check_dir "automation/learning"
check_dir "automation/utils"
check_dir "tests/unit"
check_dir ".automation/checkpoints"
check_dir ".automation/feedback"
echo ""

echo "Checking Phase 4 Implementation Files..."
echo "-------------------------------------"
check_file "automation/engine/checkpointing.py"
check_file "automation/engine/recovery.py"
check_file "automation/engine/parallel_executor.py"
check_file "automation/engine/multi_repo.py"
check_file "automation/utils/caching.py"
check_file "automation/utils/connection_pool.py"
check_file "automation/utils/batch_operations.py"
check_file "automation/utils/cost_optimizer.py"
check_file "automation/monitoring/metrics.py"
check_file "automation/monitoring/dashboard.py"
check_file "automation/learning/feedback_loop.py"
echo ""

echo "Checking Configuration Files..."
echo "-------------------------------------"
check_file "automation/config/repositories.yaml"
echo ""

echo "Checking Test Files..."
echo "-------------------------------------"
check_file "tests/conftest.py"
check_file "tests/unit/test_checkpointing.py"
check_file "tests/unit/test_parallel_executor.py"
check_file "tests/unit/test_cost_optimizer.py"
check_file "tests/unit/test_caching.py"
echo ""

echo "Checking Documentation..."
echo "-------------------------------------"
check_file "docs/phase-4-features.md"
echo ""

echo "Testing Python Imports..."
echo "-------------------------------------"
python3 -c "from automation.engine.checkpointing import CheckpointManager; print('✓ checkpointing')" 2>/dev/null || echo -e "${RED}✗ checkpointing${NC}"
python3 -c "from automation.engine.recovery import AdvancedRecovery; print('✓ recovery')" 2>/dev/null || echo -e "${RED}✗ recovery${NC}"
python3 -c "from automation.engine.parallel_executor import ParallelExecutor; print('✓ parallel_executor')" 2>/dev/null || echo -e "${RED}✗ parallel_executor${NC}"
python3 -c "from automation.engine.multi_repo import MultiRepoOrchestrator; print('✓ multi_repo')" 2>/dev/null || echo -e "${RED}✗ multi_repo${NC}"
python3 -c "from automation.utils.caching import AsyncCache; print('✓ caching')" 2>/dev/null || echo -e "${RED}✗ caching${NC}"
python3 -c "from automation.utils.connection_pool import HTTPConnectionPool; print('✓ connection_pool')" 2>/dev/null || echo -e "${RED}✗ connection_pool${NC}"
python3 -c "from automation.utils.batch_operations import BatchOperations; print('✓ batch_operations')" 2>/dev/null || echo -e "${RED}✗ batch_operations${NC}"
python3 -c "from automation.utils.cost_optimizer import CostOptimizer; print('✓ cost_optimizer')" 2>/dev/null || echo -e "${RED}✗ cost_optimizer${NC}"
python3 -c "from automation.monitoring.metrics import MetricsCollector; print('✓ metrics')" 2>/dev/null || echo -e "${RED}✗ metrics${NC}"
python3 -c "from automation.monitoring.dashboard import app; print('✓ dashboard')" 2>/dev/null || echo -e "${RED}✗ dashboard${NC}"
python3 -c "from automation.learning.feedback_loop import FeedbackLoop; print('✓ feedback_loop')" 2>/dev/null || echo -e "${RED}✗ feedback_loop${NC}"
echo ""

echo "======================================"
echo "Verification Complete!"
echo "======================================"
echo ""
echo "Next Steps:"
echo "1. Install dependencies: pip install -e '.[dev]'"
echo "2. Run tests: pytest tests/ -v"
echo "3. Start dashboard: uvicorn automation.monitoring.dashboard:app"
echo "4. Read documentation: docs/phase-4-features.md"
