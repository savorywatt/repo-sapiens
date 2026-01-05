"""Tests for repo_sapiens/utils/batch_operations.py - Batch processing utilities."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from repo_sapiens.utils.batch_operations import (
    BatchOperations,
    BatchProcessor,
    ParallelBatchProcessor,
)


# =============================================================================
# Tests for BatchProcessor
# =============================================================================


class TestBatchProcessor:
    """Tests for BatchProcessor class."""

    def test_init_defaults(self):
        """Test BatchProcessor initialization with defaults."""
        processor = BatchProcessor()
        assert processor.batch_size == 10
        assert processor.delay_between_batches == 1.0

    def test_init_custom_values(self):
        """Test BatchProcessor initialization with custom values."""
        processor = BatchProcessor(batch_size=5, delay_between_batches=0.5)
        assert processor.batch_size == 5
        assert processor.delay_between_batches == 0.5

    @pytest.mark.asyncio
    async def test_process_batches_empty_list(self):
        """Test processing empty list returns empty results."""
        processor = BatchProcessor(batch_size=3)
        mock_processor = AsyncMock(return_value=[])

        results = await processor.process_batches([], mock_processor)

        assert results == []
        mock_processor.assert_not_called()

    @pytest.mark.asyncio
    async def test_process_batches_single_batch(self):
        """Test processing items that fit in single batch."""
        processor = BatchProcessor(batch_size=5)
        items = [1, 2, 3]

        async def double_items(batch):
            return [x * 2 for x in batch]

        results = await processor.process_batches(items, double_items)

        assert results == [2, 4, 6]

    @pytest.mark.asyncio
    async def test_process_batches_multiple_batches(self):
        """Test processing items across multiple batches."""
        processor = BatchProcessor(batch_size=2, delay_between_batches=0.01)
        items = [1, 2, 3, 4, 5]

        async def identity(batch):
            return batch

        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            results = await processor.process_batches(items, identity)

        assert results == [1, 2, 3, 4, 5]
        # Should sleep between batches (2 times for 3 batches)
        assert mock_sleep.call_count == 2

    @pytest.mark.asyncio
    async def test_process_batches_exact_batch_size(self):
        """Test processing when items exactly fill batches."""
        processor = BatchProcessor(batch_size=2, delay_between_batches=0.01)
        items = [1, 2, 3, 4]

        async def identity(batch):
            return batch

        with patch("asyncio.sleep", new_callable=AsyncMock):
            results = await processor.process_batches(items, identity)

        assert results == [1, 2, 3, 4]

    @pytest.mark.asyncio
    async def test_process_batches_non_list_result(self):
        """Test processing when processor returns non-list result."""
        processor = BatchProcessor(batch_size=2)
        items = [1, 2]

        async def sum_batch(batch):
            return sum(batch)  # Returns single value, not list

        results = await processor.process_batches(items, sum_batch)

        # Non-list result should be appended
        assert results == [3]

    @pytest.mark.asyncio
    async def test_process_batches_processor_error(self):
        """Test that processor errors are propagated."""
        processor = BatchProcessor(batch_size=2)
        items = [1, 2, 3, 4]

        async def failing_processor(batch):
            if 3 in batch:
                raise ValueError("Processing failed")
            return batch

        with patch("asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(ValueError, match="Processing failed"):
                await processor.process_batches(items, failing_processor)

    @pytest.mark.asyncio
    async def test_process_batches_no_delay_after_last_batch(self):
        """Test that no delay occurs after the last batch."""
        sleep_calls = []
        processor = BatchProcessor(batch_size=2, delay_between_batches=0.1)
        items = [1, 2, 3]  # Will be 2 batches

        async def identity(batch):
            return batch

        async def track_sleep(delay):
            sleep_calls.append(delay)

        with patch("asyncio.sleep", side_effect=track_sleep):
            await processor.process_batches(items, identity)

        # Only 1 sleep call (between batch 1 and 2, not after batch 2)
        assert len(sleep_calls) == 1


# =============================================================================
# Tests for ParallelBatchProcessor
# =============================================================================


class TestParallelBatchProcessor:
    """Tests for ParallelBatchProcessor class."""

    def test_init_defaults(self):
        """Test ParallelBatchProcessor initialization with defaults."""
        processor = ParallelBatchProcessor()
        assert processor.batch_size == 10
        assert processor.max_concurrent_batches == 3

    def test_init_custom_values(self):
        """Test ParallelBatchProcessor initialization with custom values."""
        processor = ParallelBatchProcessor(batch_size=5, max_concurrent_batches=2)
        assert processor.batch_size == 5
        assert processor.max_concurrent_batches == 2

    @pytest.mark.asyncio
    async def test_process_batches_empty_list(self):
        """Test processing empty list returns empty results."""
        processor = ParallelBatchProcessor(batch_size=3)
        mock_processor = AsyncMock(return_value=[])

        results = await processor.process_batches([], mock_processor)

        assert results == []

    @pytest.mark.asyncio
    async def test_process_batches_single_batch(self):
        """Test processing items that fit in single batch."""
        processor = ParallelBatchProcessor(batch_size=5)
        items = [1, 2, 3]

        async def double_items(batch):
            return [x * 2 for x in batch]

        results = await processor.process_batches(items, double_items)

        assert results == [2, 4, 6]

    @pytest.mark.asyncio
    async def test_process_batches_parallel_execution(self):
        """Test that batches are processed in parallel."""
        processor = ParallelBatchProcessor(batch_size=2, max_concurrent_batches=3)
        items = [1, 2, 3, 4, 5, 6]
        execution_order = []

        async def track_execution(batch):
            execution_order.append(f"start-{batch[0]}")
            await asyncio.sleep(0.01)  # Small delay
            execution_order.append(f"end-{batch[0]}")
            return batch

        results = await processor.process_batches(items, track_execution)

        assert results == [1, 2, 3, 4, 5, 6]
        # With parallel execution, starts should happen before all ends
        starts = [e for e in execution_order if e.startswith("start")]
        assert len(starts) == 3

    @pytest.mark.asyncio
    async def test_process_batches_concurrency_limit(self):
        """Test that concurrency is limited by max_concurrent_batches."""
        processor = ParallelBatchProcessor(batch_size=1, max_concurrent_batches=2)
        items = [1, 2, 3, 4]
        concurrent_count = []
        current_concurrent = 0
        lock = asyncio.Lock()

        async def track_concurrency(batch):
            nonlocal current_concurrent
            async with lock:
                current_concurrent += 1
                concurrent_count.append(current_concurrent)
            await asyncio.sleep(0.05)
            async with lock:
                current_concurrent -= 1
            return batch

        await processor.process_batches(items, track_concurrency)

        # Max concurrent should never exceed 2
        assert max(concurrent_count) <= 2

    @pytest.mark.asyncio
    async def test_process_batches_non_list_result(self):
        """Test processing when processor returns non-list result."""
        processor = ParallelBatchProcessor(batch_size=2)
        items = [1, 2]

        async def sum_batch(batch):
            return sum(batch)

        results = await processor.process_batches(items, sum_batch)

        assert results == [3]

    @pytest.mark.asyncio
    async def test_process_batches_exception_handling(self):
        """Test that exceptions from any batch are propagated."""
        processor = ParallelBatchProcessor(batch_size=2, max_concurrent_batches=3)
        items = [1, 2, 3, 4, 5, 6]

        async def failing_processor(batch):
            if 3 in batch:
                raise RuntimeError("Batch 2 failed")
            await asyncio.sleep(0.1)  # Delay to ensure parallel execution
            return batch

        with pytest.raises(RuntimeError, match="Batch 2 failed"):
            await processor.process_batches(items, failing_processor)

    @pytest.mark.asyncio
    async def test_process_batches_preserves_order(self):
        """Test that results maintain batch order."""
        processor = ParallelBatchProcessor(batch_size=2, max_concurrent_batches=3)
        items = [1, 2, 3, 4, 5, 6]

        async def add_ten(batch):
            # Different delays to potentially reorder
            await asyncio.sleep(0.01 * batch[0])
            return [x + 10 for x in batch]

        results = await processor.process_batches(items, add_ten)

        # Results should be in order: [11, 12, 13, 14, 15, 16]
        assert results == [11, 12, 13, 14, 15, 16]


# =============================================================================
# Tests for BatchOperations
# =============================================================================


class TestBatchOperations:
    """Tests for BatchOperations class."""

    @pytest.fixture
    def mock_git_provider(self):
        """Create mock git provider."""
        mock = MagicMock()
        mock.create_issue = AsyncMock(
            side_effect=lambda **kwargs: {"number": 1, **kwargs}
        )
        mock.update_issue = AsyncMock(
            side_effect=lambda num, **kwargs: {"number": num, **kwargs}
        )
        mock.add_comment = AsyncMock(
            side_effect=lambda num, body: {"issue": num, "body": body}
        )
        mock.get_issue = AsyncMock(side_effect=lambda num: {"number": num})
        return mock

    def test_init(self, mock_git_provider):
        """Test BatchOperations initialization."""
        ops = BatchOperations(mock_git_provider, batch_size=5, max_concurrent=2)
        assert ops.git is mock_git_provider
        assert ops.batch_processor.batch_size == 5
        assert ops.batch_processor.max_concurrent_batches == 2

    @pytest.mark.asyncio
    async def test_create_issues_batch_empty(self, mock_git_provider):
        """Test creating empty list of issues."""
        ops = BatchOperations(mock_git_provider)

        results = await ops.create_issues_batch([])

        assert results == []
        mock_git_provider.create_issue.assert_not_called()

    @pytest.mark.asyncio
    async def test_create_issues_batch_single(self, mock_git_provider):
        """Test creating single issue."""
        ops = BatchOperations(mock_git_provider, batch_size=5)
        issues_data = [{"title": "Issue 1", "body": "Body 1"}]

        results = await ops.create_issues_batch(issues_data)

        assert len(results) == 1
        assert results[0]["title"] == "Issue 1"
        mock_git_provider.create_issue.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_issues_batch_multiple(self, mock_git_provider):
        """Test creating multiple issues in batches."""
        ops = BatchOperations(mock_git_provider, batch_size=2, max_concurrent=2)
        issues_data = [
            {"title": f"Issue {i}", "body": f"Body {i}"} for i in range(5)
        ]

        results = await ops.create_issues_batch(issues_data)

        assert len(results) == 5
        assert mock_git_provider.create_issue.call_count == 5

    @pytest.mark.asyncio
    async def test_update_issues_batch_empty(self, mock_git_provider):
        """Test updating empty list of issues."""
        ops = BatchOperations(mock_git_provider)

        results = await ops.update_issues_batch([])

        assert results == []
        mock_git_provider.update_issue.assert_not_called()

    @pytest.mark.asyncio
    async def test_update_issues_batch_single(self, mock_git_provider):
        """Test updating single issue."""
        ops = BatchOperations(mock_git_provider, batch_size=5)
        updates = [{"issue_number": 42, "fields": {"title": "Updated"}}]

        results = await ops.update_issues_batch(updates)

        assert len(results) == 1
        mock_git_provider.update_issue.assert_called_once_with(
            42, title="Updated"
        )

    @pytest.mark.asyncio
    async def test_update_issues_batch_multiple(self, mock_git_provider):
        """Test updating multiple issues in batches."""
        ops = BatchOperations(mock_git_provider, batch_size=2, max_concurrent=2)
        updates = [
            {"issue_number": i, "fields": {"state": "closed"}} for i in range(5)
        ]

        results = await ops.update_issues_batch(updates)

        assert len(results) == 5
        assert mock_git_provider.update_issue.call_count == 5

    @pytest.mark.asyncio
    async def test_add_comments_batch_empty(self, mock_git_provider):
        """Test adding comments to empty list."""
        ops = BatchOperations(mock_git_provider)

        results = await ops.add_comments_batch([])

        assert results == []
        mock_git_provider.add_comment.assert_not_called()

    @pytest.mark.asyncio
    async def test_add_comments_batch_single(self, mock_git_provider):
        """Test adding single comment."""
        ops = BatchOperations(mock_git_provider, batch_size=5)
        comments = [{"issue_number": 42, "body": "Test comment"}]

        results = await ops.add_comments_batch(comments)

        assert len(results) == 1
        mock_git_provider.add_comment.assert_called_once_with(42, "Test comment")

    @pytest.mark.asyncio
    async def test_add_comments_batch_multiple(self, mock_git_provider):
        """Test adding multiple comments in batches."""
        ops = BatchOperations(mock_git_provider, batch_size=2, max_concurrent=2)
        comments = [
            {"issue_number": i, "body": f"Comment {i}"} for i in range(5)
        ]

        results = await ops.add_comments_batch(comments)

        assert len(results) == 5
        assert mock_git_provider.add_comment.call_count == 5

    @pytest.mark.asyncio
    async def test_get_issues_batch_empty(self, mock_git_provider):
        """Test getting empty list of issues."""
        ops = BatchOperations(mock_git_provider)

        results = await ops.get_issues_batch([])

        assert results == []
        mock_git_provider.get_issue.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_issues_batch_single(self, mock_git_provider):
        """Test getting single issue."""
        ops = BatchOperations(mock_git_provider, batch_size=5)
        issue_numbers = [42]

        results = await ops.get_issues_batch(issue_numbers)

        assert len(results) == 1
        assert results[0]["number"] == 42
        mock_git_provider.get_issue.assert_called_once_with(42)

    @pytest.mark.asyncio
    async def test_get_issues_batch_multiple(self, mock_git_provider):
        """Test getting multiple issues in batches."""
        ops = BatchOperations(mock_git_provider, batch_size=2, max_concurrent=2)
        issue_numbers = [1, 2, 3, 4, 5]

        results = await ops.get_issues_batch(issue_numbers)

        assert len(results) == 5
        assert mock_git_provider.get_issue.call_count == 5

    @pytest.mark.asyncio
    async def test_create_issues_batch_with_error(self, mock_git_provider):
        """Test that errors in batch creation are propagated."""
        mock_git_provider.create_issue = AsyncMock(
            side_effect=RuntimeError("API error")
        )
        ops = BatchOperations(mock_git_provider, batch_size=2)
        issues_data = [{"title": "Issue 1"}]

        with pytest.raises(RuntimeError, match="API error"):
            await ops.create_issues_batch(issues_data)


# =============================================================================
# Edge Cases and Integration Tests
# =============================================================================


class TestBatchOperationsEdgeCases:
    """Edge case tests for batch operations."""

    @pytest.mark.asyncio
    async def test_large_batch_processing(self):
        """Test processing large number of items."""
        processor = ParallelBatchProcessor(batch_size=100, max_concurrent_batches=5)
        items = list(range(1000))

        async def identity(batch):
            return batch

        results = await processor.process_batches(items, identity)

        assert results == items
        assert len(results) == 1000

    @pytest.mark.asyncio
    async def test_batch_size_larger_than_items(self):
        """Test when batch size is larger than item count."""
        processor = BatchProcessor(batch_size=100)
        items = [1, 2, 3]

        async def identity(batch):
            return batch

        results = await processor.process_batches(items, identity)

        assert results == [1, 2, 3]

    @pytest.mark.asyncio
    async def test_batch_size_of_one(self):
        """Test with batch size of 1."""
        processor = BatchProcessor(batch_size=1, delay_between_batches=0)
        items = [1, 2, 3]

        async def double(batch):
            return [x * 2 for x in batch]

        with patch("asyncio.sleep", new_callable=AsyncMock):
            results = await processor.process_batches(items, double)

        assert results == [2, 4, 6]

    @pytest.mark.asyncio
    async def test_processor_returns_none_in_list(self):
        """Test handling of None values in results."""
        processor = ParallelBatchProcessor(batch_size=2)
        items = [1, 2, 3, 4]

        async def sometimes_none(batch):
            return [x if x % 2 == 0 else None for x in batch]

        results = await processor.process_batches(items, sometimes_none)

        assert results == [None, 2, None, 4]

    @pytest.mark.asyncio
    async def test_concurrent_modification_safety(self):
        """Test that concurrent processing doesn't cause race conditions."""
        processor = ParallelBatchProcessor(batch_size=1, max_concurrent_batches=10)
        items = list(range(100))
        results_set = set()
        lock = asyncio.Lock()

        async def track_and_return(batch):
            async with lock:
                for item in batch:
                    if item in results_set:
                        raise ValueError(f"Duplicate processing: {item}")
                    results_set.add(item)
            return batch

        results = await processor.process_batches(items, track_and_return)

        assert len(results) == 100
        assert set(results) == set(items)
