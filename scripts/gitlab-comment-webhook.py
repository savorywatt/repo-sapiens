#!/usr/bin/env python3
"""
GitLab Comment Webhook Handler for Sapiens

This script receives GitLab webhook events for issue comments (notes) and triggers
the sapiens-comment pipeline job when a comment contains trigger keywords.

Usage:
    # Install dependencies
    pip install fastapi uvicorn httpx

    # Run the server
    python gitlab-comment-webhook.py

    # Or with environment variables
    GITLAB_URL=https://gitlab.example.com \
    GITLAB_API_TOKEN=glpat-xxx \
    GITLAB_WEBHOOK_SECRET=your-webhook-secret \
    LISTEN_PORT=8000 \
    python gitlab-comment-webhook.py

Environment Variables:
    GITLAB_WEBHOOK_SECRET: Secret token to validate webhook requests (required)
    GITLAB_API_TOKEN: GitLab API token with 'api' scope for triggering pipelines (required)
    GITLAB_URL: GitLab instance URL (default: http://localhost)
    LISTEN_PORT: Port to listen on (default: 8000)
    TRIGGER_REF: Git ref to trigger pipeline on (default: main)
    LOG_LEVEL: Logging level (default: INFO)

GitLab Webhook Setup:
    1. Go to Project > Settings > Webhooks
    2. URL: http://your-server:8000/webhook/gitlab/comment
    3. Secret Token: Set to match GITLAB_WEBHOOK_SECRET
    4. Trigger: Note events (Comments)
    5. Enable SSL verification if using HTTPS

Trigger Keywords:
    Comments containing any of these will trigger the sapiens-comment pipeline:
    - @sapiens
    - sapiens:

Docker Deployment:
    docker build -t gitlab-comment-webhook -f Dockerfile.gitlab-webhook .
    docker run -d --name gitlab-webhook \
        -e GITLAB_URL=https://gitlab.example.com \
        -e GITLAB_API_TOKEN=glpat-xxx \
        -e GITLAB_WEBHOOK_SECRET=your-secret \
        -p 8000:8000 \
        gitlab-comment-webhook
"""

import hmac
import logging
import os
import re
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

# Configuration from environment
GITLAB_URL = os.environ.get("GITLAB_URL", "http://localhost")
GITLAB_API_TOKEN = os.environ.get("GITLAB_API_TOKEN", "")
GITLAB_WEBHOOK_SECRET = os.environ.get("GITLAB_WEBHOOK_SECRET", "")
LISTEN_PORT = int(os.environ.get("LISTEN_PORT", "8000"))
TRIGGER_REF = os.environ.get("TRIGGER_REF", "main")
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")

# Trigger keywords - comments containing these will trigger the pipeline
# Uses lookbehind to prevent matching in email addresses like user@sapiens.com
TRIGGER_KEYWORDS = [
    r"(?<![a-zA-Z0-9])@sapiens\b",  # @sapiens mention (not preceded by alphanumeric)
    r"(?<![a-zA-Z0-9])sapiens:",  # sapiens: command prefix (not preceded by alphanumeric)
]

# Compile regex patterns
TRIGGER_PATTERN = re.compile("|".join(TRIGGER_KEYWORDS), re.IGNORECASE)

# Logging setup
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("gitlab-comment-webhook")

# FastAPI app
app = FastAPI(
    title="GitLab Comment Webhook Handler",
    description="Triggers sapiens-comment pipeline on GitLab issue comments",
    version="1.0.0",
)


def validate_config() -> list[str]:
    """Validate required configuration is present.

    Returns:
        List of missing configuration items.
    """
    missing = []
    if not GITLAB_API_TOKEN:
        missing.append("GITLAB_API_TOKEN")
    if not GITLAB_WEBHOOK_SECRET:
        missing.append("GITLAB_WEBHOOK_SECRET")
    return missing


def verify_webhook_signature(payload: bytes, signature: str | None) -> bool:
    """Verify GitLab webhook signature.

    GitLab uses a simple token comparison for webhook verification.
    The token is sent in the X-Gitlab-Token header.

    Args:
        payload: Raw request body (unused for GitLab, but kept for API consistency)
        signature: Token from X-Gitlab-Token header

    Returns:
        True if signature matches, False otherwise.
    """
    if not GITLAB_WEBHOOK_SECRET:
        logger.warning("No webhook secret configured, skipping verification")
        return True

    if not signature:
        logger.warning("No X-Gitlab-Token header in request")
        return False

    # GitLab uses simple token comparison
    return hmac.compare_digest(signature, GITLAB_WEBHOOK_SECRET)


def contains_trigger_keyword(text: str) -> bool:
    """Check if text contains any trigger keywords.

    Args:
        text: Comment body to check

    Returns:
        True if any trigger keyword is found.
    """
    return bool(TRIGGER_PATTERN.search(text))


async def trigger_pipeline(
    project_id: int,
    issue_iid: int,
    comment_id: int,
    comment_author: str,
    comment_body: str,
) -> dict[str, Any]:
    """Trigger the sapiens-comment pipeline via GitLab API.

    Args:
        project_id: GitLab project ID
        issue_iid: Issue internal ID (IID)
        comment_id: Note/comment ID
        comment_author: Username of comment author
        comment_body: Full text of the comment

    Returns:
        Pipeline creation response or error details.
    """
    # GitLab API endpoint to create a pipeline
    url = f"{GITLAB_URL}/api/v4/projects/{project_id}/pipeline"

    headers = {
        "PRIVATE-TOKEN": GITLAB_API_TOKEN,
        "Content-Type": "application/json",
    }

    # Pipeline variables for sapiens-comment job
    payload = {
        "ref": TRIGGER_REF,
        "variables": [
            {"key": "SAPIENS_ISSUE", "value": str(issue_iid)},
            {"key": "SAPIENS_COMMENT_ID", "value": str(comment_id)},
            {"key": "SAPIENS_COMMENT_AUTHOR", "value": comment_author},
            {"key": "SAPIENS_COMMENT_BODY", "value": comment_body},
        ],
    }

    logger.info(
        "Triggering pipeline",
        extra={
            "project_id": project_id,
            "issue_iid": issue_iid,
            "comment_id": comment_id,
            "author": comment_author,
        },
    )

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, headers=headers, json=payload, timeout=30.0)

            if response.status_code == 201:
                pipeline_data = response.json()
                logger.info(
                    "Pipeline triggered successfully",
                    extra={
                        "pipeline_id": pipeline_data.get("id"),
                        "web_url": pipeline_data.get("web_url"),
                    },
                )
                return {
                    "status": "triggered",
                    "pipeline_id": pipeline_data.get("id"),
                    "web_url": pipeline_data.get("web_url"),
                }
            else:
                logger.error(
                    "Failed to trigger pipeline",
                    extra={
                        "status_code": response.status_code,
                        "response": response.text[:500],
                    },
                )
                return {
                    "status": "error",
                    "error": f"GitLab API returned {response.status_code}",
                    "details": response.text[:500],
                }

        except httpx.RequestError as e:
            logger.error("HTTP request failed", extra={"error": str(e)})
            return {"status": "error", "error": str(e)}


@app.on_event("startup")
async def startup_event():
    """Validate configuration on startup."""
    missing = validate_config()
    if missing:
        logger.error(f"Missing required configuration: {', '.join(missing)}")
        logger.error("Set environment variables and restart")
        # Don't exit - allow health checks to report unhealthy status


@app.get("/")
async def root():
    """Root endpoint with basic info."""
    return {
        "service": "gitlab-comment-webhook",
        "version": "1.0.0",
        "endpoints": {
            "webhook": "/webhook/gitlab/comment",
            "health": "/health",
        },
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    missing = validate_config()
    if missing:
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "reason": f"Missing configuration: {', '.join(missing)}",
            },
        )
    return {"status": "healthy", "gitlab_url": GITLAB_URL}


@app.post("/webhook/gitlab/comment")
async def handle_gitlab_webhook(request: Request):
    """Handle GitLab webhook for note (comment) events.

    This endpoint receives GitLab webhook payloads for note events,
    filters for issue comments containing trigger keywords, and
    triggers the sapiens-comment pipeline.

    Headers expected:
        X-Gitlab-Event: Note Hook
        X-Gitlab-Token: Webhook secret token
    """
    # Get raw body for signature verification
    body = await request.body()

    # Verify webhook token
    gitlab_token = request.headers.get("X-Gitlab-Token")
    if not verify_webhook_signature(body, gitlab_token):
        logger.warning("Invalid webhook signature")
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    # Check event type
    event_type = request.headers.get("X-Gitlab-Event")
    if event_type != "Note Hook":
        logger.info(f"Ignoring non-note event: {event_type}")
        return {"status": "ignored", "reason": f"Event type '{event_type}' not handled"}

    # Parse payload
    try:
        payload = await request.json()
    except Exception as e:
        logger.error(f"Failed to parse JSON payload: {e}")
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    # Extract note details
    object_kind = payload.get("object_kind")
    if object_kind != "note":
        return {"status": "ignored", "reason": f"Object kind '{object_kind}' not handled"}

    object_attributes = payload.get("object_attributes", {})
    noteable_type = object_attributes.get("noteable_type")

    # Only handle issue comments
    if noteable_type != "Issue":
        logger.info(f"Ignoring note on {noteable_type}")
        return {"status": "ignored", "reason": f"Note on '{noteable_type}' not handled"}

    # Extract required fields
    project_id = payload.get("project", {}).get("id")
    issue = payload.get("issue", {})
    issue_iid = issue.get("iid")
    comment_id = object_attributes.get("id")
    comment_body = object_attributes.get("note", "")
    comment_author = payload.get("user", {}).get("username", "unknown")

    # Validate required fields
    if not all([project_id, issue_iid, comment_id]):
        logger.error("Missing required fields in payload")
        raise HTTPException(status_code=400, detail="Missing required fields")

    logger.info(
        "Received issue comment",
        extra={
            "project_id": project_id,
            "issue_iid": issue_iid,
            "comment_id": comment_id,
            "author": comment_author,
            "body_preview": comment_body[:100] if comment_body else "",
        },
    )

    # Check for trigger keywords
    if not contains_trigger_keyword(comment_body):
        logger.info("Comment does not contain trigger keywords")
        return {
            "status": "ignored",
            "reason": "No trigger keywords found",
            "keywords_checked": ["@sapiens", "sapiens:"],
        }

    # Validate configuration before triggering
    missing = validate_config()
    if missing:
        logger.error(f"Cannot trigger pipeline - missing config: {missing}")
        raise HTTPException(
            status_code=503,
            detail=f"Service not configured: missing {', '.join(missing)}",
        )

    # Trigger the pipeline
    result = await trigger_pipeline(
        project_id=project_id,
        issue_iid=issue_iid,
        comment_id=comment_id,
        comment_author=comment_author,
        comment_body=comment_body,
    )

    return result


if __name__ == "__main__":
    import uvicorn

    # Validate config on startup
    missing = validate_config()
    if missing:
        logger.warning(f"Missing configuration: {', '.join(missing)}")
        logger.warning("Server will start but pipeline triggers will fail")

    logger.info(f"Starting GitLab Comment Webhook Handler on port {LISTEN_PORT}")
    logger.info(f"GitLab URL: {GITLAB_URL}")
    logger.info(f"Trigger ref: {TRIGGER_REF}")

    uvicorn.run(
        app,
        host="0.0.0.0",  # nosec B104 - intentional bind to all interfaces for container deployment
        port=LISTEN_PORT,
        log_level=LOG_LEVEL.lower(),
    )
