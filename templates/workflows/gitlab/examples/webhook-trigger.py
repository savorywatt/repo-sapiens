#!/usr/bin/env python3
"""
GitLab Webhook to Pipeline Trigger Bridge

NOTE: This is only needed if you're using sapiens-dispatcher.yaml for
      real-time label responses. For most setups, use automation-daemon.yaml
      instead - it polls on a schedule and requires no webhook setup.

This script receives GitLab webhooks for label events and triggers
the sapiens-dispatcher pipeline with the appropriate variables.

Deploy as a simple webhook endpoint (Flask, FastAPI, or serverless function).

Environment Variables:
    GITLAB_URL: GitLab instance URL (e.g., https://gitlab.example.com)
    GITLAB_API_TOKEN: GitLab API token with 'api' scope (note: GITLAB_TOKEN prefix is reserved)
    TRIGGER_TOKEN: Pipeline trigger token for target projects
    SAPIENS_LABELS: Comma-separated list of labels to handle (default: all sapiens/* labels)

Example deployment with Flask:
    pip install flask requests
    GITLAB_URL=https://gitlab.example.com \
    GITLAB_API_TOKEN=glpat-xxx \
    TRIGGER_TOKEN=xxx \
    python webhook-trigger.py

GitLab Webhook Setup:
    1. Go to Project > Settings > Webhooks
    2. URL: https://your-webhook-server/gitlab-webhook
    3. Secret Token: (optional, for verification)
    4. Trigger: Issues events, Merge request events
"""

import logging
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
GITLAB_URL = os.environ.get("GITLAB_URL", "https://gitlab.com")
# Note: GITLAB_TOKEN prefix is reserved by GitLab, so we use GITLAB_API_TOKEN
GITLAB_API_TOKEN = os.environ.get("GITLAB_API_TOKEN", os.environ.get("SAPIENS_GITLAB_TOKEN", ""))
TRIGGER_TOKEN = os.environ.get("TRIGGER_TOKEN", "")
SAPIENS_LABELS = os.environ.get("SAPIENS_LABELS", "").split(",") if os.environ.get("SAPIENS_LABELS") else None

# Labels that trigger sapiens workflows
DEFAULT_SAPIENS_LABELS = [
    "sapiens/needs-planning",
    "sapiens/needs-review",
    "sapiens/needs-fix",
    "sapiens/requires-qa",
    "approved",
    "execute",
]


def is_sapiens_label(label: str) -> bool:
    """Check if a label should trigger sapiens."""
    labels_to_check = SAPIENS_LABELS or DEFAULT_SAPIENS_LABELS
    return label in labels_to_check or label.startswith("sapiens/")


def get_added_labels(payload: dict) -> list[str]:
    """Extract newly added labels from webhook payload."""
    changes = payload.get("changes", {})
    labels_change = changes.get("labels", {})

    previous = {lbl["title"] for lbl in labels_change.get("previous", [])}
    current = {lbl["title"] for lbl in labels_change.get("current", [])}

    return list(current - previous)


def trigger_pipeline(project_id: int, ref: str, label: str, issue_number: int, event_type: str) -> bool:
    """Trigger the sapiens-dispatcher pipeline."""
    import requests

    url = f"{GITLAB_URL}/api/v4/projects/{project_id}/trigger/pipeline"

    data = {
        "token": TRIGGER_TOKEN,
        "ref": ref,
        "variables[SAPIENS_LABEL]": label,
        "variables[SAPIENS_ISSUE_NUMBER]": str(issue_number),
        "variables[SAPIENS_EVENT_TYPE]": event_type,
    }

    logger.info(f"Triggering pipeline for project {project_id}: {label} on #{issue_number}")

    response = requests.post(url, data=data)

    if response.status_code == 201:
        pipeline = response.json()
        logger.info(f"Pipeline created: {pipeline.get('web_url')}")
        return True
    else:
        logger.error(f"Failed to trigger pipeline: {response.status_code} - {response.text}")
        return False


def handle_webhook(payload: dict) -> dict:
    """Process GitLab webhook payload."""
    object_kind = payload.get("object_kind")

    if object_kind == "issue":
        project_id = payload["project"]["id"]
        issue_number = payload["object_attributes"]["iid"]
        ref = payload["project"].get("default_branch", "main")
        event_type = "issues.labeled"

    elif object_kind == "merge_request":
        project_id = payload["project"]["id"]
        issue_number = payload["object_attributes"]["iid"]
        ref = payload["object_attributes"].get("source_branch", "main")
        event_type = "merge_request.labeled"

    else:
        return {"status": "ignored", "reason": f"Unsupported object_kind: {object_kind}"}

    # Check for label changes
    added_labels = get_added_labels(payload)
    sapiens_labels = [lbl for lbl in added_labels if is_sapiens_label(lbl)]

    if not sapiens_labels:
        return {"status": "ignored", "reason": "No sapiens labels added"}

    # Trigger pipeline for each sapiens label
    results = []
    for label in sapiens_labels:
        success = trigger_pipeline(project_id, ref, label, issue_number, event_type)
        results.append({"label": label, "triggered": success})

    return {"status": "processed", "triggers": results}


# Flask app (if running standalone)
if __name__ == "__main__":
    try:
        from flask import Flask, jsonify, request
    except ImportError:
        print("Flask not installed. Install with: pip install flask requests")
        print("\nAlternatively, use this module's handle_webhook() function in your own server.")
        exit(1)

    app = Flask(__name__)

    @app.route("/gitlab-webhook", methods=["POST"])
    def webhook():
        payload = request.json
        result = handle_webhook(payload)
        return jsonify(result)

    @app.route("/health", methods=["GET"])
    def health():
        return jsonify({"status": "ok"})

    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
