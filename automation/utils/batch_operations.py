"""
Batch operations for reducing API calls.
Provides utilities for batching multiple operations efficiently.
"""

import asyncio
from collections.abc import Callable
from typing import Any, TypeVar

import structlog

log = structlog.get_logger(__name__)

T = TypeVar("T")
R = TypeVar("R")


class BatchProcessor:
    """Process items in batches with rate limiting."""

    def __init__(self, batch_size: int = 10, delay_between_batches: float = 1.0) -> None:
        self.batch_size = batch_size
        self.delay_between_batches = delay_between_batches

    async def process_batches(self, items: list[T], processor: Callable[[list[T]], Any]) -> list[R]:
        """
        Process items in batches.

        Args:
            items: Items to process
            processor: Async function to process a batch of items

        Returns:
            List of results from all batches
        """
        results: list[R] = []
        total_batches = (len(items) + self.batch_size - 1) // self.batch_size

        log.info(
            "batch_processing_started",
            total_items=len(items),
            batch_size=self.batch_size,
            total_batches=total_batches,
        )

        for i in range(0, len(items), self.batch_size):
            batch_num = i // self.batch_size + 1
            batch = items[i : i + self.batch_size]

            log.debug(
                "processing_batch",
                batch_num=batch_num,
                batch_size=len(batch),
                total_batches=total_batches,
            )

            try:
                batch_results = await processor(batch)

                if isinstance(batch_results, list):
                    results.extend(batch_results)
                else:
                    results.append(batch_results)

            except Exception as e:
                log.error("batch_processing_error", batch_num=batch_num, error=str(e))
                raise

            # Rate limiting: wait between batches (except for last batch)
            if i + self.batch_size < len(items):
                await asyncio.sleep(self.delay_between_batches)

        log.info("batch_processing_complete", total_results=len(results))
        return results


class ParallelBatchProcessor:
    """Process batches in parallel with concurrency control."""

    def __init__(
        self,
        batch_size: int = 10,
        max_concurrent_batches: int = 3,
    ) -> None:
        self.batch_size = batch_size
        self.max_concurrent_batches = max_concurrent_batches
        self.semaphore = asyncio.Semaphore(max_concurrent_batches)

    async def process_batches(self, items: list[T], processor: Callable[[list[T]], Any]) -> list[R]:
        """
        Process items in parallel batches.

        Args:
            items: Items to process
            processor: Async function to process a batch of items

        Returns:
            List of results from all batches
        """
        batches = [items[i : i + self.batch_size] for i in range(0, len(items), self.batch_size)]

        log.info(
            "parallel_batch_processing_started",
            total_items=len(items),
            batch_size=self.batch_size,
            total_batches=len(batches),
            max_concurrent=self.max_concurrent_batches,
        )

        tasks = [self._process_batch(batch, processor) for batch in batches]
        batch_results = await asyncio.gather(*tasks, return_exceptions=True)

        # Flatten results and handle errors
        results: list[R] = []
        for i, batch_result in enumerate(batch_results):
            if isinstance(batch_result, Exception):
                log.error("batch_failed", batch_num=i + 1, error=str(batch_result))
                raise batch_result
            elif isinstance(batch_result, list):
                results.extend(batch_result)
            else:
                results.append(batch_result)

        log.info("parallel_batch_processing_complete", total_results=len(results))
        return results

    async def _process_batch(self, batch: list[T], processor: Callable[[list[T]], Any]) -> Any:
        """Process a single batch with semaphore control."""
        async with self.semaphore:
            return await processor(batch)


class BatchOperations:
    """High-level batch operations for common tasks."""

    def __init__(self, git_provider: Any, batch_size: int = 10, max_concurrent: int = 3) -> None:
        self.git = git_provider
        self.batch_processor = ParallelBatchProcessor(batch_size, max_concurrent)

    async def create_issues_batch(self, issues_data: list[dict[str, Any]]) -> list[Any]:
        """Create multiple issues in batches."""
        log.info("creating_issues_batch", count=len(issues_data))

        async def create_batch(batch: list[dict[str, Any]]) -> list[Any]:
            tasks = [self.git.create_issue(**issue_data) for issue_data in batch]
            return await asyncio.gather(*tasks)

        results = await self.batch_processor.process_batches(issues_data, create_batch)

        log.info("issues_created", count=len(results))
        return results

    async def update_issues_batch(self, updates: list[dict[str, Any]]) -> list[Any]:
        """Update multiple issues in batches."""
        log.info("updating_issues_batch", count=len(updates))

        async def update_batch(batch: list[dict[str, Any]]) -> list[Any]:
            tasks = [
                self.git.update_issue(update["issue_number"], **update["fields"])
                for update in batch
            ]
            return await asyncio.gather(*tasks)

        results = await self.batch_processor.process_batches(updates, update_batch)

        log.info("issues_updated", count=len(results))
        return results

    async def add_comments_batch(self, comments: list[dict[str, Any]]) -> list[Any]:
        """Add comments to multiple issues in batches."""
        log.info("adding_comments_batch", count=len(comments))

        async def comment_batch(batch: list[dict[str, Any]]) -> list[Any]:
            tasks = [
                self.git.add_comment(comment["issue_number"], comment["body"]) for comment in batch
            ]
            return await asyncio.gather(*tasks)

        results = await self.batch_processor.process_batches(comments, comment_batch)

        log.info("comments_added", count=len(results))
        return results

    async def get_issues_batch(self, issue_numbers: list[int]) -> list[Any]:
        """Get multiple issues in batches."""
        log.info("getting_issues_batch", count=len(issue_numbers))

        async def get_batch(batch: list[int]) -> list[Any]:
            tasks = [self.git.get_issue(issue_num) for issue_num in batch]
            return await asyncio.gather(*tasks)

        results = await self.batch_processor.process_batches(issue_numbers, get_batch)

        log.info("issues_retrieved", count=len(results))
        return results
