"""Dependency audit stage - audits dependencies for vulnerabilities and updates."""

from pathlib import Path
from typing import Any

import structlog

from repo_sapiens.engine.stages.base import WorkflowStage
from repo_sapiens.models.domain import Issue
from repo_sapiens.utils.async_subprocess import run_command

log = structlog.get_logger(__name__)


class DependencyAuditStage(WorkflowStage):
    """Audit dependencies when 'dependency-audit' label is present.

    This stage:
    1. Detects issues with 'dependency-audit' or 'sapiens/dependency-audit' label
    2. Runs dependency audit tools (npm audit, pip-audit, cargo audit, etc.)
    3. Checks for outdated dependencies
    4. Reports vulnerabilities found
    5. Suggests updates
    6. Updates label to 'audit-complete'
    """

    async def execute(self, issue: Issue) -> None:
        """Execute dependency audit.

        Args:
            issue: Issue with 'dependency-audit' label
        """
        log.info("dependency_audit_stage_start", issue=issue.number)

        # Check if already audited
        if "audit-complete" in issue.labels:
            log.debug("already_audited", issue=issue.number)
            return

        try:
            # Notify start
            await self.git.add_comment(
                issue.number,
                f"🔍 **Starting Dependency Audit**\n\n"
                f"Issue #{issue.number}: {issue.title}\n\n"
                f"I'll scan dependencies for vulnerabilities and outdated packages.\n\n"
                f"◆ Posted by Sapiens Automation",
            )

            # Determine project directory
            playground_dir = Path(__file__).parent.parent.parent.parent.parent / "playground"
            if not playground_dir.exists():
                await self._provide_audit_guidance(issue)
                return

            # Run audits
            audit_results = await self._run_audits(playground_dir)

            # Post results
            await self._post_audit_results(issue, audit_results)

            log.info("dependency_audit_stage_complete", issue=issue.number)

        except Exception as e:
            log.error("dependency_audit_failed", issue=issue.number, error=str(e), exc_info=True)
            await self.git.add_comment(
                issue.number,
                f"❌ **Dependency Audit Failed**\n\n"
                f"Error: {str(e)}\n\n"
                f"Please try again.\n\n"
                f"◆ Posted by Sapiens Automation",
            )
            raise

    async def _run_audits(self, project_dir: Path) -> dict[str, Any]:
        """Run dependency audit commands for detected package managers."""
        log.info("running_dependency_audits", dir=str(project_dir))

        results: dict[str, Any] = {
            "audits": [],
            "outdated": [],
            "has_vulnerabilities": False,
            "vulnerability_count": 0,
        }

        # Python: pip-audit
        if (project_dir / "requirements.txt").exists() or (project_dir / "pyproject.toml").exists():
            audit_result = await self._run_python_audit(project_dir)
            results["audits"].append(audit_result)
            if audit_result.get("vulnerabilities", 0) > 0:
                results["has_vulnerabilities"] = True
                results["vulnerability_count"] += audit_result.get("vulnerabilities", 0)

            outdated = await self._run_python_outdated(project_dir)
            results["outdated"].append(outdated)

        # Node.js: npm audit
        if (project_dir / "package.json").exists():
            audit_result = await self._run_npm_audit(project_dir)
            results["audits"].append(audit_result)
            if audit_result.get("vulnerabilities", 0) > 0:
                results["has_vulnerabilities"] = True
                results["vulnerability_count"] += audit_result.get("vulnerabilities", 0)

            outdated = await self._run_npm_outdated(project_dir)
            results["outdated"].append(outdated)

        # Rust: cargo audit
        if (project_dir / "Cargo.toml").exists():
            audit_result = await self._run_cargo_audit(project_dir)
            results["audits"].append(audit_result)
            if audit_result.get("vulnerabilities", 0) > 0:
                results["has_vulnerabilities"] = True
                results["vulnerability_count"] += audit_result.get("vulnerabilities", 0)

            outdated = await self._run_cargo_outdated(project_dir)
            results["outdated"].append(outdated)

        # Go: govulncheck
        if (project_dir / "go.mod").exists():
            audit_result = await self._run_go_audit(project_dir)
            results["audits"].append(audit_result)
            if audit_result.get("vulnerabilities", 0) > 0:
                results["has_vulnerabilities"] = True
                results["vulnerability_count"] += audit_result.get("vulnerabilities", 0)

        if not results["audits"]:
            results["audits"].append(
                {
                    "tool": "none",
                    "success": False,
                    "output": "No supported package manager detected",
                    "vulnerabilities": 0,
                }
            )

        return results

    async def _run_python_audit(self, project_dir: Path) -> dict[str, Any]:
        """Run pip-audit."""
        try:
            stdout, stderr, returncode = await run_command(
                "pip-audit",
                "--format=json",
                cwd=project_dir,
                check=False,
                timeout=300,
            )
            output = stdout + stderr

            # Try to count vulnerabilities from JSON output
            import json

            vuln_count = 0
            try:
                data = json.loads(stdout)
                vuln_count = len(data.get("vulnerabilities", data) if isinstance(data, dict) else data)
            except (json.JSONDecodeError, TypeError):
                if returncode != 0:
                    vuln_count = output.count("PYSEC-")

            return {
                "tool": "pip-audit",
                "success": returncode == 0,
                "output": output,
                "vulnerabilities": vuln_count,
            }
        except FileNotFoundError:
            return {
                "tool": "pip-audit",
                "success": False,
                "output": "pip-audit not installed. Install with: pip install pip-audit",
                "vulnerabilities": 0,
            }

    async def _run_python_outdated(self, project_dir: Path) -> dict[str, Any]:
        """Check for outdated Python packages."""
        try:
            stdout, stderr, returncode = await run_command(
                "pip",
                "list",
                "--outdated",
                "--format=json",
                cwd=project_dir,
                check=False,
                timeout=120,
            )
            return {
                "tool": "pip outdated",
                "success": True,
                "output": stdout,
            }
        except FileNotFoundError:
            return {
                "tool": "pip outdated",
                "success": False,
                "output": "pip not found",
            }

    async def _run_npm_audit(self, project_dir: Path) -> dict[str, Any]:
        """Run npm audit."""
        try:
            stdout, stderr, returncode = await run_command(
                "npm",
                "audit",
                "--json",
                cwd=project_dir,
                check=False,
                timeout=300,
            )
            output = stdout + stderr

            # Try to count vulnerabilities
            import json

            vuln_count = 0
            try:
                data = json.loads(stdout)
                metadata = data.get("metadata", {})
                vulnerabilities = metadata.get("vulnerabilities", {})
                vuln_count = sum(vulnerabilities.values()) if isinstance(vulnerabilities, dict) else 0
            except (json.JSONDecodeError, TypeError):
                if returncode != 0:
                    vuln_count = 1  # At least one if audit failed

            return {
                "tool": "npm audit",
                "success": returncode == 0,
                "output": output,
                "vulnerabilities": vuln_count,
            }
        except FileNotFoundError:
            return {
                "tool": "npm audit",
                "success": False,
                "output": "npm not found",
                "vulnerabilities": 0,
            }

    async def _run_npm_outdated(self, project_dir: Path) -> dict[str, Any]:
        """Check for outdated npm packages."""
        try:
            stdout, stderr, returncode = await run_command(
                "npm",
                "outdated",
                "--json",
                cwd=project_dir,
                check=False,
                timeout=120,
            )
            return {
                "tool": "npm outdated",
                "success": True,  # npm outdated exits non-zero if packages are outdated
                "output": stdout,
            }
        except FileNotFoundError:
            return {
                "tool": "npm outdated",
                "success": False,
                "output": "npm not found",
            }

    async def _run_cargo_audit(self, project_dir: Path) -> dict[str, Any]:
        """Run cargo audit."""
        try:
            stdout, stderr, returncode = await run_command(
                "cargo",
                "audit",
                cwd=project_dir,
                check=False,
                timeout=300,
            )
            output = stdout + stderr

            # Count vulnerabilities from output
            vuln_count = output.count("Vulnerability found")

            return {
                "tool": "cargo audit",
                "success": returncode == 0,
                "output": output,
                "vulnerabilities": vuln_count,
            }
        except FileNotFoundError:
            return {
                "tool": "cargo audit",
                "success": False,
                "output": "cargo audit not installed. Install with: cargo install cargo-audit",
                "vulnerabilities": 0,
            }

    async def _run_cargo_outdated(self, project_dir: Path) -> dict[str, Any]:
        """Check for outdated Rust packages."""
        try:
            stdout, stderr, returncode = await run_command(
                "cargo",
                "outdated",
                cwd=project_dir,
                check=False,
                timeout=120,
            )
            return {
                "tool": "cargo outdated",
                "success": True,
                "output": stdout + stderr,
            }
        except FileNotFoundError:
            return {
                "tool": "cargo outdated",
                "success": False,
                "output": "cargo outdated not installed. Install with: cargo install cargo-outdated",
            }

    async def _run_go_audit(self, project_dir: Path) -> dict[str, Any]:
        """Run govulncheck."""
        try:
            stdout, stderr, returncode = await run_command(
                "govulncheck",
                "./...",
                cwd=project_dir,
                check=False,
                timeout=300,
            )
            output = stdout + stderr

            # Count vulnerabilities
            vuln_count = output.count("Vulnerability")

            return {
                "tool": "govulncheck",
                "success": returncode == 0,
                "output": output,
                "vulnerabilities": vuln_count,
            }
        except FileNotFoundError:
            return {
                "tool": "govulncheck",
                "success": False,
                "output": "govulncheck not installed. "
                "Install with: go install golang.org/x/vuln/cmd/govulncheck@latest",
                "vulnerabilities": 0,
            }

    async def _post_audit_results(self, issue: Issue, results: dict[str, Any]) -> None:
        """Post audit results as a comment."""
        severity_emoji = "🔴" if results["has_vulnerabilities"] else "🟢"

        parts = [
            f"{severity_emoji} **Dependency Audit Complete**\n",
            "",
        ]

        # Summary
        if results["has_vulnerabilities"]:
            parts.extend(
                [
                    f"⚠️ **{results['vulnerability_count']} vulnerabilities found!**",
                    "",
                ]
            )
        else:
            parts.extend(
                [
                    "✅ **No vulnerabilities detected.**",
                    "",
                ]
            )

        # Audit details
        parts.extend(["## Security Audit Results", ""])

        for audit in results["audits"]:
            status = "✅" if audit.get("success") else "⚠️"
            vuln = audit.get("vulnerabilities", 0)
            parts.extend(
                [
                    f"### {audit['tool']} {status}",
                    "",
                ]
            )

            if vuln > 0:
                parts.append(f"**Vulnerabilities found**: {vuln}")

            if audit.get("output"):
                output = audit["output"][:2000]
                parts.extend(
                    [
                        "",
                        "<details>",
                        "<summary>Output</summary>",
                        "",
                        f"```\n{output}\n```",
                        "</details>",
                        "",
                    ]
                )

        # Outdated packages
        if results["outdated"]:
            has_outdated = any(r.get("output", "").strip() and r.get("output") != "{}" for r in results["outdated"])
            if has_outdated:
                parts.extend(["## Outdated Packages", ""])

                for outdated in results["outdated"]:
                    if outdated.get("output") and outdated["output"].strip() and outdated["output"] != "{}":
                        parts.extend(
                            [
                                f"### {outdated['tool']}",
                                "",
                                "<details>",
                                "<summary>Outdated packages</summary>",
                                "",
                                f"```\n{outdated['output'][:1500]}\n```",
                                "</details>",
                                "",
                            ]
                        )

        # Recommendations
        parts.extend(
            [
                "## Recommendations",
                "",
            ]
        )

        if results["has_vulnerabilities"]:
            parts.extend(
                [
                    "1. Review the vulnerabilities above",
                    "2. Update affected packages where fixes are available",
                    "3. Consider removing unused dependencies",
                    "4. Run audits again after updates",
                    "",
                ]
            )
        else:
            parts.extend(
                [
                    "1. Keep dependencies up to date",
                    "2. Run dependency audits regularly",
                    "3. Consider setting up automated audits in CI",
                    "",
                ]
            )

        parts.extend(["---", "", "◆ Posted by Sapiens Automation"])

        await self.git.add_comment(issue.number, "\n".join(parts))

        # Update labels
        updated_labels = [
            label for label in issue.labels if label not in ["dependency-audit", "sapiens/dependency-audit"]
        ]
        updated_labels.append("audit-complete")

        if results["has_vulnerabilities"]:
            updated_labels.append("security-alert")

        await self.git.update_issue(issue.number, labels=updated_labels)

    async def _provide_audit_guidance(self, issue: Issue) -> None:
        """Provide guidance when playground doesn't exist."""
        await self.git.add_comment(
            issue.number,
            "📋 **Dependency Audit Guidance**\n\n"
            "Unable to run audits directly. Please run these commands locally:\n\n"
            "**Python**:\n"
            "```bash\n"
            "pip install pip-audit\n"
            "pip-audit\n"
            "```\n\n"
            "**Node.js**:\n"
            "```bash\n"
            "npm audit\n"
            "npm outdated\n"
            "```\n\n"
            "**Rust**:\n"
            "```bash\n"
            "cargo install cargo-audit cargo-outdated\n"
            "cargo audit\n"
            "cargo outdated\n"
            "```\n\n"
            "**Go**:\n"
            "```bash\n"
            "go install golang.org/x/vuln/cmd/govulncheck@latest\n"
            "govulncheck ./...\n"
            "```\n\n"
            "◆ Posted by Sapiens Automation",
        )

        # Update labels
        updated_labels = [
            label for label in issue.labels if label not in ["dependency-audit", "sapiens/dependency-audit"]
        ]
        updated_labels.append("audit-complete")
        await self.git.update_issue(issue.number, labels=updated_labels)
