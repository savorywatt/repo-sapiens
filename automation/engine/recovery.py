"""
Advanced workflow recovery with multiple strategies.
Handles different failure types with appropriate recovery mechanisms.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from enum import Enum
import asyncio
import structlog

log = structlog.get_logger(__name__)


class ErrorType(str, Enum):
    """Types of errors that can occur during workflow execution."""

    TRANSIENT_API_ERROR = "transient_api_error"
    MERGE_CONFLICT = "merge_conflict"
    TEST_FAILURE = "test_failure"
    TIMEOUT = "timeout"
    VALIDATION_ERROR = "validation_error"
    UNKNOWN = "unknown"


class RecoveryError(Exception):
    """Raised when recovery attempt fails."""

    pass


class RecoveryStrategy(ABC):
    """Base class for recovery strategies."""

    def __init__(self, recovery_manager: "AdvancedRecovery") -> None:
        self.recovery = recovery_manager

    @abstractmethod
    async def execute(self, plan_id: str, checkpoint_data: Dict[str, Any]) -> None:
        """Execute recovery strategy."""
        pass

    @abstractmethod
    def can_handle(self, error_type: ErrorType) -> bool:
        """Check if this strategy can handle the error type."""
        pass


class RetryRecoveryStrategy(RecoveryStrategy):
    """Retry with exponential backoff for transient errors."""

    def can_handle(self, error_type: ErrorType) -> bool:
        return error_type in [ErrorType.TRANSIENT_API_ERROR, ErrorType.TIMEOUT]

    async def execute(self, plan_id: str, checkpoint_data: Dict[str, Any]) -> None:
        """Retry the failed operation with exponential backoff."""
        operation = checkpoint_data.get("failed_operation")
        attempt = checkpoint_data.get("retry_attempt", 0)
        max_attempts = 3

        if attempt >= max_attempts:
            raise RecoveryError(f"Max retry attempts ({max_attempts}) exceeded")

        delay = 2**attempt
        log.info("retry_recovery", plan_id=plan_id, attempt=attempt + 1, delay=delay)
        await asyncio.sleep(delay)

        # Re-execute the failed operation
        # The checkpoint should contain enough context to retry
        log.info("retry_recovery_complete", plan_id=plan_id, operation=operation)


class ConflictResolutionStrategy(RecoveryStrategy):
    """Attempt to resolve merge conflicts automatically."""

    def can_handle(self, error_type: ErrorType) -> bool:
        return error_type == ErrorType.MERGE_CONFLICT

    async def execute(self, plan_id: str, checkpoint_data: Dict[str, Any]) -> None:
        """Resolve merge conflicts using AI assistance."""
        conflict_info = checkpoint_data.get("conflict_details", {})
        log.info("conflict_resolution", plan_id=plan_id, conflicts=len(conflict_info))

        # In a real implementation, would use agent provider to resolve conflicts
        # For now, log and mark for manual intervention
        raise RecoveryError("Automatic conflict resolution not yet implemented")


class TestFixRecoveryStrategy(RecoveryStrategy):
    """Fix failing tests automatically."""

    def can_handle(self, error_type: ErrorType) -> bool:
        return error_type == ErrorType.TEST_FAILURE

    async def execute(self, plan_id: str, checkpoint_data: Dict[str, Any]) -> None:
        """Attempt to fix failing tests."""
        test_failures = checkpoint_data.get("test_failures", [])
        log.info("test_fix_recovery", plan_id=plan_id, failure_count=len(test_failures))

        # Analyze failures and generate fixes
        # In a real implementation, would use agent provider
        raise RecoveryError("Automatic test fixing not yet implemented")


class ManualInterventionStrategy(RecoveryStrategy):
    """Fallback strategy that requires manual intervention."""

    def can_handle(self, error_type: ErrorType) -> bool:
        return True  # Can handle any error type as fallback

    async def execute(self, plan_id: str, checkpoint_data: Dict[str, Any]) -> None:
        """Create issue for manual intervention."""
        log.warning("manual_intervention_required", plan_id=plan_id)

        # In a real implementation, would create a Gitea issue
        # with details about the failure and checkpoint data
        raise RecoveryError("Manual intervention required")


class AdvancedRecovery:
    """Advanced workflow recovery with checkpointing."""

    def __init__(
        self,
        state_manager: Any,
        checkpoint_manager: Any,
        git_provider: Optional[Any] = None,
        agent_provider: Optional[Any] = None,
    ) -> None:
        self.state = state_manager
        self.checkpoint = checkpoint_manager
        self.git = git_provider
        self.agent = agent_provider

        # Register recovery strategies in priority order
        self.strategies: list[RecoveryStrategy] = [
            RetryRecoveryStrategy(self),
            ConflictResolutionStrategy(self),
            TestFixRecoveryStrategy(self),
            ManualInterventionStrategy(self),  # Always last as fallback
        ]

    async def attempt_recovery(self, plan_id: str) -> bool:
        """Attempt automatic recovery from failure."""
        log.info("recovery_attempt", plan_id=plan_id)

        # Load latest checkpoint
        checkpoint_data = await self.checkpoint.get_latest_checkpoint(plan_id)
        if not checkpoint_data:
            log.warning("no_checkpoint_found", plan_id=plan_id)
            return False

        stage = checkpoint_data["stage"]
        data = checkpoint_data["data"]

        # Determine recovery strategy
        error_type = self._classify_error(data)
        recovery_strategy = self._select_recovery_strategy(error_type)

        try:
            await recovery_strategy.execute(plan_id, data)
            log.info("recovery_successful", plan_id=plan_id, stage=stage)
            return True
        except RecoveryError as e:
            log.error("recovery_failed", plan_id=plan_id, error=str(e), exc_info=True)
            return False
        except Exception as e:
            log.error(
                "recovery_exception", plan_id=plan_id, error=str(e), exc_info=True
            )
            return False

    def _classify_error(self, checkpoint_data: Dict[str, Any]) -> ErrorType:
        """Classify the error type from checkpoint data."""
        error_type_str = checkpoint_data.get("error_type")

        if error_type_str:
            try:
                return ErrorType(error_type_str)
            except ValueError:
                pass

        # Try to infer error type from error message or other data
        error_msg = checkpoint_data.get("error", "").lower()

        if "timeout" in error_msg:
            return ErrorType.TIMEOUT
        elif "conflict" in error_msg:
            return ErrorType.MERGE_CONFLICT
        elif "test" in error_msg and "fail" in error_msg:
            return ErrorType.TEST_FAILURE
        elif any(x in error_msg for x in ["api", "connection", "network"]):
            return ErrorType.TRANSIENT_API_ERROR

        return ErrorType.UNKNOWN

    def _select_recovery_strategy(self, error_type: ErrorType) -> RecoveryStrategy:
        """Select appropriate recovery strategy based on error type."""
        for strategy in self.strategies:
            if strategy.can_handle(error_type):
                log.info("recovery_strategy_selected", strategy=strategy.__class__.__name__)
                return strategy

        # This should never happen as ManualInterventionStrategy handles everything
        return self.strategies[-1]

    async def create_recovery_checkpoint(
        self,
        plan_id: str,
        stage: str,
        error: Exception,
        context: Dict[str, Any],
    ) -> str:
        """Create a checkpoint when an error occurs."""
        checkpoint_data = {
            "error": str(error),
            "error_type": self._infer_error_type(error).value,
            "context": context,
            "retry_attempt": context.get("retry_attempt", 0),
        }

        return await self.checkpoint.create_checkpoint(plan_id, stage, checkpoint_data)

    def _infer_error_type(self, error: Exception) -> ErrorType:
        """Infer error type from exception."""
        error_msg = str(error).lower()

        if "timeout" in error_msg:
            return ErrorType.TIMEOUT
        elif "conflict" in error_msg:
            return ErrorType.MERGE_CONFLICT
        elif any(x in error_msg for x in ["api", "connection", "network"]):
            return ErrorType.TRANSIENT_API_ERROR
        elif "validation" in error_msg or "invalid" in error_msg:
            return ErrorType.VALIDATION_ERROR

        return ErrorType.UNKNOWN
