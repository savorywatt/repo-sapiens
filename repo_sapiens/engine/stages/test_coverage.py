"""Test coverage stage - analyzes and reports on test coverage."""

from pathlib import Path
from typing import Any

import structlog

from repo_sapiens.engine.stages.base import WorkflowStage
from repo_sapiens.models.domain import Issue
from repo_sapiens.utils.async_subprocess import run_command

log = structlog.get_logger(__name__)


class TestCoverageStage(WorkflowStage):
    """Analyze test coverage when 'test-coverage' label is present.

    This stage:
    1. Detects issues/PRs with 'test-coverage' or 'sapiens/test-coverage' label
    2. Runs coverage tools (pytest-cov, nyc, go test -cover, etc.)
    3. Generates a coverage report
    4. Posts coverage summary as a comment
    5. Suggests areas needing more tests
    6. Updates label to 'coverage-analyzed'
    """

    async def execute(self, issue: Issue) -> None:
        """Execute test coverage analysis.

        Args:
            issue: Issue with 'test-coverage' label
        """
        log.info("test_coverage_stage_start", issue=issue.number)

        # Check if already processed
        if "coverage-analyzed" in issue.labels:
            log.debug("already_coverage_analyzed", issue=issue.number)
            return

        try:
            # Notify start
            await self.git.add_comment(
                issue.number,
                f"📊 **Starting Test Coverage Analysis**\n\n"
                f"Issue #{issue.number}: {issue.title}\n\n"
                f"I'll run tests with coverage and generate a report.\n\n"
                f"◆ Posted by Sapiens Automation",
            )

            # Try to get PR to determine which branch to analyze
            pr = await self._get_pr_for_issue(issue)

            if pr:
                await self._analyze_pr_coverage(issue, pr)
            else:
                await self._analyze_repo_coverage(issue)

            log.info("test_coverage_stage_complete", issue=issue.number)

        except Exception as e:
            log.error("test_coverage_failed", issue=issue.number, error=str(e), exc_info=True)
            await self.git.add_comment(
                issue.number,
                f"❌ **Test Coverage Analysis Failed**\n\n"
                f"Error: {str(e)}\n\n"
                f"Please try again.\n\n"
                f"◆ Posted by Sapiens Automation",
            )
            raise

    async def _get_pr_for_issue(self, issue: Issue) -> Any:
        """Try to find a PR associated with this issue."""
        try:
            pr = await self.git.get_pull_request(issue.number)
            return pr
        except Exception as e:
            log.debug("pr_lookup_failed", issue=issue.number, error=str(e))
            return None

    async def _analyze_pr_coverage(self, issue: Issue, pr: Any) -> None:
        """Analyze test coverage for a specific PR."""
        log.info("analyzing_pr_coverage", pr=pr.number)

        playground_dir = Path(__file__).parent.parent.parent.parent.parent / "playground"
        if not playground_dir.exists():
            raise Exception(f"Playground repo not found at {playground_dir}")

        # Checkout the PR branch
        await run_command("git", "fetch", "origin", cwd=playground_dir, check=True)
        await run_command(
            "git",
            "checkout",
            "-B",
            pr.head,
            f"origin/{pr.head}",
            cwd=playground_dir,
            check=True,
        )

        # Run coverage analysis
        coverage_result = await self._run_coverage(playground_dir)

        # Generate report
        await self._post_coverage_report(issue, coverage_result, pr=pr)

    async def _analyze_repo_coverage(self, issue: Issue) -> None:
        """Analyze test coverage for the main repository branch."""
        log.info("analyzing_repo_coverage", issue=issue.number)

        playground_dir = Path(__file__).parent.parent.parent.parent.parent / "playground"
        if not playground_dir.exists():
            # Fallback: provide guidance on running coverage
            await self._provide_coverage_guidance(issue)
            return

        # Run coverage on current branch
        coverage_result = await self._run_coverage(playground_dir)

        # Generate report
        await self._post_coverage_report(issue, coverage_result)

    async def _run_coverage(self, project_dir: Path) -> dict[str, Any]:
        """Run coverage commands and return results."""
        log.info("running_coverage", dir=str(project_dir))

        # Try different coverage tools
        coverage_commands = [
            # Python with pytest-cov
            (
                ["pytest", "--cov=.", "--cov-report=term-missing", "--cov-report=json"],
                "pyproject.toml",
                "python",
            ),
            (
                ["python", "-m", "pytest", "--cov=.", "--cov-report=term-missing"],
                "pytest.ini",
                "python",
            ),
            # Node.js with nyc/istanbul
            (["npm", "run", "test:coverage"], "package.json", "node"),
            (["npx", "nyc", "--reporter=text", "npm", "test"], "package.json", "node"),
            # Go
            (["go", "test", "-cover", "-coverprofile=coverage.out", "./..."], "go.mod", "go"),
            # Rust
            (["cargo", "tarpaulin", "--out", "Stdout"], "Cargo.toml", "rust"),
        ]

        for cmd, indicator_file, lang in coverage_commands:
            if (project_dir / indicator_file).exists():
                log.info("running_coverage_command", cmd=cmd, lang=lang)
                try:
                    stdout, stderr, returncode = await run_command(
                        *cmd,
                        cwd=project_dir,
                        check=False,
                        timeout=600,  # 10 minute timeout for coverage
                    )
                    return {
                        "success": returncode == 0,
                        "output": stdout + stderr,
                        "command": " ".join(cmd),
                        "language": lang,
                    }
                except TimeoutError:
                    return {
                        "success": False,
                        "output": "Coverage analysis timed out after 10 minutes",
                        "command": " ".join(cmd),
                        "language": lang,
                    }
                except FileNotFoundError:
                    log.debug("coverage_command_not_found", cmd=cmd[0])
                    continue

        return {
            "success": False,
            "output": "No supported test/coverage framework detected",
            "command": "none",
            "language": "unknown",
        }

    async def _post_coverage_report(self, issue: Issue, coverage_result: dict[str, Any], pr: Any = None) -> None:
        """Post coverage report as a comment."""
        context_str = f"PR #{pr.number}" if pr else f"Issue #{issue.number}"

        if coverage_result["success"]:
            # Parse coverage output for summary (language-specific)
            summary = self._parse_coverage_summary(coverage_result)

            # Use agent to analyze coverage and suggest improvements
            prompt = f"""Analyze this test coverage report and provide suggestions.

**Context**: {context_str}
**Language**: {coverage_result.get('language', 'unknown')}

**Coverage Output**:
```
{coverage_result['output'][-4000:]}
```

**Instructions**:
1. Summarize the overall coverage percentage
2. Identify files/modules with low coverage (< 60%)
3. Suggest specific areas that need more tests
4. Provide actionable recommendations for improving coverage

Format your response clearly with sections for:
- Coverage Summary
- Low Coverage Areas
- Recommendations
"""

            result = await self.agent.execute_prompt(
                prompt, {"coverage": coverage_result}, f"coverage-analysis-{issue.number}"
            )

            analysis = result.get("output", summary) if result.get("success") else summary

            await self.git.add_comment(
                issue.number,
                f"📊 **Test Coverage Report**\n\n"
                f"Context: {context_str}\n\n"
                f"{analysis}\n\n"
                f"---\n"
                f"<details>\n"
                f"<summary>Raw Coverage Output</summary>\n\n"
                f"```\n{coverage_result['output'][-2000:]}\n```\n"
                f"</details>\n\n"
                f"◆ Posted by Sapiens Automation",
            )
        else:
            await self.git.add_comment(
                issue.number,
                f"⚠️ **Coverage Analysis Incomplete**\n\n"
                f"Context: {context_str}\n\n"
                f"**Issue**: {coverage_result['output']}\n\n"
                f"**Suggestions**:\n"
                f"- Ensure test dependencies are installed (pytest-cov, nyc, etc.)\n"
                f"- Check that tests are configured correctly\n"
                f"- Verify the test command works locally\n\n"
                f"◆ Posted by Sapiens Automation",
            )

        # Update labels
        updated_labels = [label for label in issue.labels if label not in ["test-coverage", "sapiens/test-coverage"]]
        updated_labels.append("coverage-analyzed")
        await self.git.update_issue(issue.number, labels=updated_labels)

    async def _provide_coverage_guidance(self, issue: Issue) -> None:
        """Provide guidance on setting up coverage when no playground exists."""
        context = {
            "issue_number": issue.number,
            "issue_title": issue.title,
            "issue_body": issue.body,
        }

        prompt = f"""Generate a test coverage improvement plan for this issue.

**Issue Title**: {issue.title}

**Issue Description**:
{issue.body or "(No description)"}

**Instructions**:
Since we can't run coverage directly, provide:

1. **Recommended Coverage Tools** based on likely project stack
2. **Setup Instructions** for integrating coverage
3. **CI Integration** suggestions for automated coverage reporting
4. **Coverage Goals** - recommended targets (e.g., 80% overall)
5. **Best Practices** for maintaining test coverage

Be specific and actionable.
"""

        result = await self.agent.execute_prompt(prompt, context, f"coverage-plan-{issue.number}")

        output = (
            result.get("output", "Unable to generate coverage plan.")
            if result.get("success")
            else ("Unable to analyze. Please run coverage tools locally and share results.")
        )

        await self.git.add_comment(
            issue.number,
            f"📊 **Test Coverage Guidance**\n\n" f"{output}\n\n" f"---\n" f"◆ Posted by Sapiens Automation",
        )

        # Update labels
        updated_labels = [label for label in issue.labels if label not in ["test-coverage", "sapiens/test-coverage"]]
        updated_labels.append("coverage-analyzed")
        await self.git.update_issue(issue.number, labels=updated_labels)

    def _parse_coverage_summary(self, coverage_result: dict[str, Any]) -> str:
        """Parse coverage output to extract summary statistics."""
        output = coverage_result.get("output", "")

        # Try to find common coverage percentage patterns
        import re

        # Python pytest-cov format: "TOTAL    X    Y    Z%"
        python_match = re.search(r"TOTAL\s+\d+\s+\d+\s+(\d+)%", output)
        if python_match:
            return f"Overall Coverage: {python_match.group(1)}%"

        # Node.js nyc format: "All files  |   X   |"
        node_match = re.search(r"All files\s*\|\s*([\d.]+)", output)
        if node_match:
            return f"Overall Coverage: {node_match.group(1)}%"

        # Go format: "coverage: X% of statements"
        go_match = re.search(r"coverage:\s*([\d.]+)%", output)
        if go_match:
            return f"Overall Coverage: {go_match.group(1)}%"

        return "Coverage analysis completed. See details below."
