"""Example: Async code using structured logging with repo-sapiens.

This example demonstrates best practices for using structured logging in
asynchronous code.
"""

import asyncio
from typing import List

from repo_sapiens import bind_context, clear_context, configure_logging, get_logger


async def process_issue(issue_id: int, delay: float = 0.1) -> dict:
    """Process a single issue asynchronously.

    Args:
        issue_id: The ID of the issue to process
        delay: Simulated processing delay in seconds

    Returns:
        Dictionary with processing result
    """
    logger = get_logger(__name__)

    # Bind context for this specific operation
    bind_context(issue_id=issue_id)

    logger.debug("processing_started")

    try:
        # Simulate async work
        logger.debug("fetching_issue")
        await asyncio.sleep(delay)

        # Simulate analysis
        logger.debug("analyzing_issue")
        await asyncio.sleep(delay)

        # Simulate implementation
        logger.debug("implementing_solution")
        await asyncio.sleep(delay)

        result = {
            "issue_id": issue_id,
            "status": "completed",
            "changes_made": 3,
        }

        logger.info("processing_completed", status="success", changes=3)
        return result

    except Exception as e:
        logger.error("processing_failed", error=str(e), exc_info=True)
        raise
    finally:
        # Clean up context for this operation
        clear_context()


async def process_issues_concurrent(issue_ids: List[int], max_concurrent: int = 3) -> dict:
    """Process multiple issues concurrently with limited concurrency.

    Args:
        issue_ids: List of issue IDs to process
        max_concurrent: Maximum number of concurrent operations

    Returns:
        Dictionary with aggregated results
    """
    logger = get_logger(__name__)

    # Bind operation-level context
    bind_context(operation="batch_processing")

    logger.info("batch_processing_started", total_issues=len(issue_ids), max_concurrent=max_concurrent)

    try:
        results = []
        semaphore = asyncio.Semaphore(max_concurrent)

        async def process_with_semaphore(issue_id: int) -> dict:
            async with semaphore:
                return await process_issue(issue_id)

        # Create all tasks
        tasks = [process_with_semaphore(issue_id) for issue_id in issue_ids]

        # Process with limited concurrency
        completed = 0
        failed = 0

        for task in asyncio.as_completed(tasks):
            try:
                result = await task
                results.append(result)
                completed += 1
                logger.debug("task_completed", total_completed=completed)
            except Exception as e:
                failed += 1
                logger.warning("task_failed", error=str(e), total_failed=failed)

        logger.info(
            "batch_processing_completed",
            total_issues=len(issue_ids),
            completed=completed,
            failed=failed,
        )

        return {
            "total": len(issue_ids),
            "completed": completed,
            "failed": failed,
            "results": results,
        }

    finally:
        clear_context()


async def pipeline_with_stages(issues: List[int]) -> None:
    """Process issues through a multi-stage pipeline.

    Args:
        issues: List of issue IDs
    """
    logger = get_logger(__name__)

    bind_context(operation="pipeline_processing", total_issues=len(issues))

    logger.info("pipeline_started", stages=3)

    try:
        # Stage 1: Fetch and analyze
        logger.info("stage_1_fetch_analyze_started", issue_count=len(issues))

        analyzed = []
        for issue_id in issues:
            bind_context(stage="fetch_analyze", issue_id=issue_id)
            logger.debug("analyzing", issue_id=issue_id)
            await asyncio.sleep(0.05)
            analyzed.append({"id": issue_id, "severity": "high" if issue_id % 2 == 0 else "low"})
            clear_context()

        logger.info("stage_1_fetch_analyze_completed", analyzed_count=len(analyzed))

        # Stage 2: Plan solutions
        logger.info("stage_2_planning_started", issue_count=len(analyzed))

        planned = []
        for item in analyzed:
            bind_context(stage="planning", issue_id=item["id"])
            logger.debug("creating_plan", severity=item["severity"])
            await asyncio.sleep(0.05)
            planned.append({**item, "plan": f"Fix for {item['id']}"})
            clear_context()

        logger.info("stage_2_planning_completed", planned_count=len(planned))

        # Stage 3: Implement in parallel
        logger.info("stage_3_implementation_started", issue_count=len(planned))

        tasks = [process_issue(item["id"], delay=0.05) for item in planned]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        successful = sum(1 for r in results if not isinstance(r, Exception))
        failed = sum(1 for r in results if isinstance(r, Exception))

        logger.info(
            "stage_3_implementation_completed",
            successful=successful,
            failed=failed,
        )

        logger.info("pipeline_completed", total_stages=3, status="success")

    except Exception as e:
        logger.error("pipeline_failed", error=str(e), exc_info=True)
        raise
    finally:
        clear_context()


async def main() -> None:
    """Main entry point demonstrating various async logging patterns."""
    # Configure logging
    configure_logging(level="DEBUG", json_logs=False)

    logger = get_logger(__name__)
    logger.info("app_started")

    try:
        # Example 1: Sequential processing with logging
        logger.info("example_1_starting", name="sequential")

        result = await process_issue(42)
        logger.info("example_1_completed", result=result)

        # Example 2: Concurrent processing with limited concurrency
        logger.info("example_2_starting", name="concurrent_limited")

        batch_result = await process_issues_concurrent(
            list(range(1, 11)),
            max_concurrent=3,
        )
        logger.info(
            "example_2_completed",
            completed=batch_result["completed"],
            failed=batch_result["failed"],
        )

        # Example 3: Multi-stage pipeline
        logger.info("example_3_starting", name="pipeline")

        await pipeline_with_stages(list(range(1, 6)))
        logger.info("example_3_completed")

        logger.info("app_completed", status="success")

    except Exception as e:
        logger.error("app_failed", error=str(e), exc_info=True)
        raise


if __name__ == "__main__":
    asyncio.run(main())
