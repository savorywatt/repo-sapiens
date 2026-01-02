"""
Learning system for continuous improvement.
Learns from past executions to improve prompts and task selection.
"""

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import structlog

log = structlog.get_logger(__name__)


class FeedbackLoop:
    """Learn from past executions to improve prompts and strategies."""

    def __init__(self, feedback_dir: str = ".automation/feedback") -> None:
        self.feedback_dir = Path(feedback_dir)
        self.feedback_dir.mkdir(parents=True, exist_ok=True)
        self._lock = asyncio.Lock()

    async def record_execution(
        self,
        task_id: str,
        prompt: str,
        result: Any,
        review: Any | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """
        Record task execution for learning.

        Args:
            task_id: Unique task identifier
            prompt: Prompt used for execution
            result: Task execution result
            review: Optional review result
            metadata: Additional metadata
        """
        feedback = {
            "task_id": task_id,
            "prompt": prompt,
            "success": getattr(result, "success", False),
            "execution_time": getattr(result, "execution_time", 0.0),
            "review_score": getattr(review, "confidence_score", 0.0) if review else 0.0,
            "issues_found": len(getattr(review, "issues_found", [])) if review else 0,
            "timestamp": datetime.now(UTC).isoformat(),
            "metadata": metadata or {},
        }

        async with self._lock:
            feedback_file = self.feedback_dir / f"{task_id}.json"
            feedback_file.write_text(json.dumps(feedback, indent=2))

        log.info("feedback_recorded", task_id=task_id, success=feedback["success"])

    async def improve_prompt(self, task: Any, base_prompt: str) -> str:
        """
        Improve prompt based on historical data.

        Args:
            task: Task to generate prompt for
            base_prompt: Base prompt template

        Returns:
            Improved prompt
        """
        # Find similar past tasks
        similar_tasks = await self._find_similar_tasks(task)

        if not similar_tasks:
            log.debug("no_similar_tasks_found", task_id=getattr(task, "id", "unknown"))
            return self._build_default_prompt(task, base_prompt)

        # Analyze what worked well
        successful_patterns = self._extract_successful_patterns(similar_tasks)

        if not successful_patterns:
            return self._build_default_prompt(task, base_prompt)

        # Build improved prompt with learned patterns
        improved_prompt = self._build_prompt_with_patterns(task, base_prompt, successful_patterns)

        log.info(
            "prompt_improved",
            task_id=getattr(task, "id", "unknown"),
            similar_tasks=len(similar_tasks),
            patterns=len(successful_patterns),
        )

        return improved_prompt

    async def _find_similar_tasks(
        self, task: Any, similarity_threshold: float = 0.7
    ) -> list[dict[str, Any]]:
        """Find similar historical tasks."""
        similar: list[dict[str, Any]] = []

        for feedback_file in self.feedback_dir.glob("*.json"):
            try:
                feedback = json.loads(feedback_file.read_text())

                # Calculate similarity based on task characteristics
                similarity = self._calculate_similarity(task, feedback)

                if similarity > similarity_threshold:
                    feedback["similarity"] = similarity
                    similar.append(feedback)

            except (json.JSONDecodeError, KeyError) as e:
                log.warning("invalid_feedback_file", file=str(feedback_file), error=str(e))
                continue

        # Sort by similarity (descending) and recency
        similar.sort(key=lambda x: (x["similarity"], x.get("timestamp", "")), reverse=True)

        return similar[:10]  # Return top 10 most similar

    def _calculate_similarity(self, task: Any, feedback: dict[str, Any]) -> float:
        """
        Calculate similarity between task and historical feedback.

        Simple implementation - in production would use embeddings or more sophisticated matching.
        """
        score = 0.0
        task_description = (getattr(task, "description", "") or "").lower()
        task_title = (getattr(task, "title", "") or "").lower()

        # Check for keyword overlap
        prompt = feedback.get("prompt", "").lower()

        # Extract keywords (simple word matching)
        task_words = set(task_description.split())
        task_words.update(task_title.split())
        prompt_words = set(prompt.split())

        # Calculate Jaccard similarity
        if task_words and prompt_words:
            intersection = len(task_words & prompt_words)
            union = len(task_words | prompt_words)
            score = intersection / union if union > 0 else 0.0

        # Bonus for same task type
        task_type = getattr(task, "type", None)
        feedback_type = feedback.get("metadata", {}).get("task_type")

        if task_type and feedback_type and task_type == feedback_type:
            score += 0.2

        return min(score, 1.0)

    def _extract_successful_patterns(
        self, similar_tasks: list[dict[str, Any]], success_threshold: float = 0.8
    ) -> list[str]:
        """Extract patterns from successful executions."""
        patterns: list[str] = []

        for task in similar_tasks:
            # Only consider highly successful tasks
            if task.get("success") and task.get("review_score", 0) > success_threshold:
                prompt = task.get("prompt", "")

                # Extract useful patterns from successful prompts
                # In a real implementation, would use NLP to extract structured patterns
                if prompt:
                    patterns.append(prompt)

        log.debug("successful_patterns_extracted", count=len(patterns))
        return patterns[:5]  # Top 5 patterns

    def _build_default_prompt(self, task: Any, base_prompt: str) -> str:
        """Build default prompt without learning."""
        task_description = getattr(task, "description", "")
        task_title = getattr(task, "title", "")

        return f"""{base_prompt}

Task: {task_title}

Description:
{task_description}

Please implement this task following best practices.
"""

    def _build_prompt_with_patterns(self, task: Any, base_prompt: str, patterns: list[str]) -> str:
        """Build prompt incorporating learned patterns."""
        task_description = getattr(task, "description", "")
        task_title = getattr(task, "title", "")

        # Analyze patterns to extract common successful elements
        common_elements = self._analyze_patterns(patterns)

        enhanced_instructions = "\n".join(f"- {element}" for element in common_elements)

        return f"""{base_prompt}

Task: {task_title}

Description:
{task_description}

Based on successful past executions, please ensure:
{enhanced_instructions}

Please implement this task following these learned best practices.
"""

    def _analyze_patterns(self, patterns: list[str]) -> list[str]:
        """
        Analyze patterns to extract common successful elements.

        Simple implementation - in production would use NLP/ML.
        """
        elements = []

        # Look for common phrases in successful patterns
        common_phrases = [
            "test coverage",
            "error handling",
            "documentation",
            "type hints",
            "logging",
            "validation",
        ]

        for phrase in common_phrases:
            if any(phrase in pattern.lower() for pattern in patterns):
                elements.append(f"Include {phrase}")

        return elements[:5]  # Top 5 elements

    async def get_learning_stats(self) -> dict[str, Any]:
        """Get statistics about the learning system."""
        total_executions = 0
        successful_executions = 0
        average_review_score = 0.0
        total_review_score = 0.0

        for feedback_file in self.feedback_dir.glob("*.json"):
            try:
                feedback = json.loads(feedback_file.read_text())
                total_executions += 1

                if feedback.get("success"):
                    successful_executions += 1

                review_score = feedback.get("review_score", 0.0)
                total_review_score += review_score

            except (json.JSONDecodeError, KeyError):
                continue

        if total_executions > 0:
            average_review_score = total_review_score / total_executions

        return {
            "total_executions": total_executions,
            "successful_executions": successful_executions,
            "success_rate": (
                successful_executions / total_executions if total_executions > 0 else 0.0
            ),
            "average_review_score": average_review_score,
        }

    async def cleanup_old_feedback(self, max_age_days: int = 90) -> int:
        """
        Clean up feedback older than max_age_days.

        Args:
            max_age_days: Maximum age in days

        Returns:
            Number of feedback files deleted
        """
        cutoff = datetime.now(UTC).timestamp() - (max_age_days * 24 * 3600)
        deleted = 0

        async with self._lock:
            for feedback_file in self.feedback_dir.glob("*.json"):
                try:
                    feedback = json.loads(feedback_file.read_text())
                    timestamp = datetime.fromisoformat(feedback["timestamp"])

                    if timestamp.timestamp() < cutoff:
                        feedback_file.unlink()
                        deleted += 1

                except (json.JSONDecodeError, KeyError, ValueError):
                    continue

        if deleted > 0:
            log.info("old_feedback_cleaned", count=deleted, max_age_days=max_age_days)

        return deleted
