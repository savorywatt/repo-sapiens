"""Webhook server for real-time Gitea event processing."""

import re

import structlog
from fastapi import FastAPI, HTTPException, Request

from repo_sapiens.config.settings import AutomationSettings
from repo_sapiens.exceptions import ConfigurationError, RepoSapiensError

log = structlog.get_logger(__name__)

app = FastAPI(title="Gitea Automation Webhook Server")

# Global state
settings: AutomationSettings = None
orchestrator = None


@app.on_event("startup")
async def startup():
    """Initialize on startup."""
    global settings
    try:
        settings = AutomationSettings.from_yaml("automation/config/automation_config.yaml")
        log.info("webhook_server_started")
    except ConfigurationError as e:
        log.error("webhook_startup_failed", error=e.message, exc_info=True)
        raise ConfigurationError(e.message) from e
    except Exception as e:
        log.error("webhook_startup_unexpected", error=str(e), exc_info=True)
        raise RuntimeError(f"Webhook startup failed: {e}") from e


@app.post("/webhook/gitea")
async def gitea_webhook(request: Request):
    """Handle Gitea webhook events."""
    event_type = request.headers.get("X-Gitea-Event")

    if not event_type:
        raise HTTPException(status_code=400, detail="Missing X-Gitea-Event header")

    payload = await request.json()

    log.info("webhook_received", event_type=event_type)

    try:
        if event_type == "issues":
            await handle_issue_event(payload)
        elif event_type == "push":
            await handle_push_event(payload)
        else:
            log.warning("unhandled_event_type", event_type=event_type)

        return {"status": "success", "event_type": event_type}

    except RepoSapiensError as e:
        log.error("webhook_processing_failed", error=e.message, exc_info=True)
        raise HTTPException(status_code=422, detail=e.message) from e
    except Exception as e:
        log.error("webhook_processing_unexpected", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error") from e


async def handle_issue_event(payload: dict):
    """Handle issue event from webhook."""
    action = payload.get("action")
    issue_data = payload.get("issue", {})
    issue_number = issue_data.get("number")

    log.info("issue_event_received", issue=issue_number, action=action)

    # In a full implementation, this would:
    # 1. Fetch full issue from git provider
    # 2. Process issue through orchestrator
    # 3. Update state

    log.info("issue_event_processed", issue=issue_number, action=action)


async def handle_push_event(payload: dict):
    """Handle push event from webhook."""
    ref = payload.get("ref")
    commits = payload.get("commits", [])

    log.info("push_event_received", ref=ref, commit_count=len(commits))

    # Check if any commits modified plan files
    for commit in commits:
        modified = commit.get("modified", [])
        for file_path in modified:
            if file_path.startswith("plans/") and file_path.endswith(".md"):
                plan_id = extract_plan_id(file_path)
                if plan_id:
                    log.info("plan_modified", plan_id=plan_id, file=file_path)
                    # In full implementation: generate prompts

    log.info("push_event_processed", ref=ref)


def extract_plan_id(file_path: str) -> str:
    """Extract plan ID from file path.

    Args:
        file_path: Path like 'plans/42-feature.md'

    Returns:
        Plan ID like '42' or None
    """
    match = re.search(r"plans/(\d+)-", file_path)
    return match.group(1) if match else None


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "automation-webhook"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)  # nosec B104 # Development server binding
