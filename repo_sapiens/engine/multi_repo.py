"""
Multi-repository orchestration and coordination.
Enables workflows across multiple repositories with dependency management.
"""

import asyncio
import time
from enum import Enum
from typing import Any

import structlog

log = structlog.get_logger(__name__)


class CoordinationMode(str, Enum):
    """Workflow coordination modes."""

    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"


class RepositoryStatus(str, Enum):
    """Repository workflow status."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class MultiRepoOrchestrator:
    """Orchestrate workflows across multiple repositories."""

    def __init__(self, repo_configs: list[dict[str, Any]]) -> None:
        self.repositories: dict[str, dict[str, Any]] = {}
        self.providers: dict[str, Any] = {}

        for config in repo_configs:
            repo_name = config["name"]
            self.repositories[repo_name] = {
                "config": config,
                "status": RepositoryStatus.PENDING,
                "issues": [],
            }

        log.info("multi_repo_orchestrator_initialized", repo_count=len(self.repositories))

    def register_provider(self, repo_name: str, provider: Any) -> None:
        """Register a git provider for a repository."""
        if repo_name not in self.repositories:
            raise ValueError(f"Unknown repository: {repo_name}")

        self.providers[repo_name] = provider
        log.info("provider_registered", repo=repo_name)

    async def execute_cross_repo_workflow(
        self, workflow_name: str, trigger_issue: Any, context: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Execute workflow across multiple repositories."""
        log.info("cross_repo_workflow_started", workflow=workflow_name)

        workflow_config = self._get_workflow_config(workflow_name)
        if not workflow_config:
            raise ValueError(f"Unknown workflow: {workflow_name}")

        coordination_mode = CoordinationMode(workflow_config.get("coordination", "sequential"))

        if coordination_mode == CoordinationMode.SEQUENTIAL:
            results = await self._execute_sequential(workflow_config, trigger_issue, context or {})
        else:
            results = await self._execute_parallel(workflow_config, trigger_issue, context or {})

        log.info("cross_repo_workflow_complete", workflow=workflow_name, results=results)
        return results

    async def _execute_sequential(
        self, workflow_config: dict[str, Any], trigger_issue: Any, context: dict[str, Any]
    ) -> dict[str, Any]:
        """Execute workflow sequentially across repos."""
        results: dict[str, Any] = {}

        for repo_name in workflow_config["repositories"]:
            if repo_name not in self.providers:
                log.warning("provider_not_registered", repo=repo_name)
                results[repo_name] = {"status": "skipped", "reason": "no_provider"}
                continue

            provider = self.providers[repo_name]

            try:
                log.info("executing_repo_workflow", repo=repo_name)
                self.repositories[repo_name]["status"] = RepositoryStatus.IN_PROGRESS

                # Create issue in target repo
                issue = await self._create_cross_repo_issue(
                    provider, trigger_issue, repo_name, context
                )

                # Wait for completion
                completed = await self._wait_for_completion(provider, issue.number, timeout=3600)

                if completed:
                    self.repositories[repo_name]["status"] = RepositoryStatus.COMPLETED
                    results[repo_name] = {
                        "status": "completed",
                        "issue_number": issue.number,
                    }
                else:
                    self.repositories[repo_name]["status"] = RepositoryStatus.FAILED
                    results[repo_name] = {"status": "timeout"}

            except Exception as e:
                log.error("repo_workflow_failed", repo=repo_name, error=str(e), exc_info=True)
                self.repositories[repo_name]["status"] = RepositoryStatus.FAILED
                results[repo_name] = {"status": "failed", "error": str(e)}

                # Stop execution on failure in sequential mode
                break

        return results

    async def _execute_parallel(
        self, workflow_config: dict[str, Any], trigger_issue: Any, context: dict[str, Any]
    ) -> dict[str, Any]:
        """Execute workflow in parallel across repos."""
        tasks = []
        repo_names = []

        for repo_name in workflow_config["repositories"]:
            if repo_name not in self.providers:
                log.warning("provider_not_registered", repo=repo_name)
                continue

            tasks.append(self._execute_repo_workflow(repo_name, trigger_issue, context))
            repo_names.append(repo_name)

        # Execute all in parallel
        results_list = await asyncio.gather(*tasks, return_exceptions=True)

        # Combine results
        results = {}
        for repo_name, result in zip(repo_names, results_list, strict=False):
            if isinstance(result, Exception):
                results[repo_name] = {"status": "failed", "error": str(result)}
            else:
                results[repo_name] = result

        return results

    async def _execute_repo_workflow(
        self, repo_name: str, trigger_issue: Any, context: dict[str, Any]
    ) -> dict[str, Any]:
        """Execute workflow for a single repository."""
        provider = self.providers[repo_name]

        try:
            log.info("executing_repo_workflow", repo=repo_name)
            self.repositories[repo_name]["status"] = RepositoryStatus.IN_PROGRESS

            # Create issue in target repo
            issue = await self._create_cross_repo_issue(provider, trigger_issue, repo_name, context)

            # Wait for completion
            completed = await self._wait_for_completion(provider, issue.number, timeout=3600)

            if completed:
                self.repositories[repo_name]["status"] = RepositoryStatus.COMPLETED
                return {"status": "completed", "issue_number": issue.number}
            else:
                self.repositories[repo_name]["status"] = RepositoryStatus.FAILED
                return {"status": "timeout"}

        except Exception as e:
            log.error("repo_workflow_failed", repo=repo_name, error=str(e), exc_info=True)
            self.repositories[repo_name]["status"] = RepositoryStatus.FAILED
            return {"status": "failed", "error": str(e)}

    async def _create_cross_repo_issue(
        self, provider: Any, trigger_issue: Any, repo_name: str, context: dict[str, Any]
    ) -> Any:
        """Create issue in target repository for cross-repo workflow."""
        body = self._create_cross_repo_issue_body(trigger_issue, repo_name, context)

        issue = await provider.create_issue(
            title=f"[Cross-Repo] {trigger_issue.title}",
            body=body,
            labels=["needs-planning", "cross-repo"],
        )

        log.info("cross_repo_issue_created", repo=repo_name, issue_number=issue.number)
        return issue

    def _create_cross_repo_issue_body(
        self, trigger_issue: Any, repo_name: str, context: dict[str, Any]
    ) -> str:
        """Create body for cross-repo issue."""
        return f"""# Cross-Repository Workflow

This issue is part of a multi-repository workflow triggered by:
- Original Issue: {trigger_issue.title} (#{trigger_issue.number})
- Original Repository: {context.get("source_repo", "unknown")}
- Target Repository: {repo_name}

## Context

{trigger_issue.body}

## Additional Context

{context.get("additional_context", "No additional context provided.")}

---
*This issue was automatically created by the multi-repository orchestrator.*
"""

    async def _wait_for_completion(
        self, provider: Any, issue_number: int, timeout: int = 3600
    ) -> bool:
        """Wait for issue workflow to complete."""
        start_time = time.time()
        check_interval = 30  # Check every 30 seconds

        while time.time() - start_time < timeout:
            try:
                issue = await provider.get_issue(issue_number)

                # Check if completed
                if self._is_workflow_complete(issue):
                    log.info("workflow_complete", issue_number=issue_number)
                    return True

                # Check if failed
                if self._is_workflow_failed(issue):
                    log.error("workflow_failed", issue_number=issue_number)
                    return False

            except Exception as e:
                log.warning("completion_check_error", issue_number=issue_number, error=str(e))

            await asyncio.sleep(check_interval)

        log.error("workflow_timeout", issue_number=issue_number, timeout=timeout)
        return False

    def _is_workflow_complete(self, issue: Any) -> bool:
        """Check if workflow is complete based on issue state and labels."""
        # Issue is completed if closed or has 'completed' label
        if hasattr(issue, "state") and issue.state == "closed":
            return True

        if hasattr(issue, "labels"):
            return "completed" in issue.labels or "merged" in issue.labels

        return False

    def _is_workflow_failed(self, issue: Any) -> bool:
        """Check if workflow has failed."""
        if hasattr(issue, "labels"):
            return "failed" in issue.labels or "needs-attention" in issue.labels

        return False

    def _get_workflow_config(self, workflow_name: str) -> dict[str, Any] | None:
        """Get workflow configuration by name."""
        # In a real implementation, would load from config file
        # For now, return None
        return None

    async def get_repository_status(self, repo_name: str) -> dict[str, Any]:
        """Get status of a repository in the multi-repo workflow."""
        if repo_name not in self.repositories:
            raise ValueError(f"Unknown repository: {repo_name}")

        repo = self.repositories[repo_name]
        return {
            "name": repo_name,
            "status": repo["status"].value,
            "config": repo["config"],
            "issues": repo["issues"],
        }

    async def get_overall_status(self) -> dict[str, Any]:
        """Get overall status of multi-repo orchestration."""
        statuses = {name: repo["status"].value for name, repo in self.repositories.items()}

        all_completed = all(
            status == RepositoryStatus.COMPLETED for status in self.repositories.values()
        )
        any_failed = any(status == RepositoryStatus.FAILED for status in self.repositories.values())

        overall = "completed" if all_completed else "failed" if any_failed else "in_progress"

        return {"overall_status": overall, "repositories": statuses}
