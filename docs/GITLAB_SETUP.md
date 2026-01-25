# Setting Up repo-sapiens with GitLab

A complete guide for configuring repo-sapiens automation on a GitLab repository using CI/CD Components.

---

## Overview

GitLab uses a different approach than GitHub/Gitea:

- **CI/CD Components** instead of reusable workflows
- **Webhook handler required** for label-triggered automation
- **Pipeline triggers** instead of direct workflow calls

This guide covers:
- Setting up the GitLab CI/CD Component
- Configuring a webhook handler for label events
- Required CI/CD variables

---

## Prerequisites

- GitLab 16.0 or higher (for CI/CD Components)
- A GitLab project with CI/CD enabled
- Python 3.11+ for the webhook handler
- An AI provider API key (OpenRouter, etc.)

---

## Part 1: CI/CD Variables

### Required Variables

Navigate to **Settings** > **CI/CD** > **Variables** and add:

| Variable | Value | Protected | Masked |
|----------|-------|-----------|--------|
| `SAPIENS_GITLAB_TOKEN` | Your GitLab Personal Access Token | Yes | Yes |
| `SAPIENS_AI_API_KEY` | Your AI provider API key | Yes | Yes |

### Creating a GitLab Personal Access Token

1. Go to **User Settings** > **Access Tokens**
2. Create a token with these scopes:
   - `api` - Full API access
   - `read_repository` - Read repository
   - `write_repository` - Write repository
3. Copy the token and add it as `SAPIENS_GITLAB_TOKEN`

---

## Part 2: Configure `.gitlab-ci.yml`

Create or update your `.gitlab-ci.yml` to include the sapiens component:

```yaml
# .gitlab-ci.yml

include:
  - component: gitlab.com/savorywatt/repo-sapiens/gitlab/sapiens-dispatcher@v2
    inputs:
      label: $SAPIENS_LABEL
      issue_number: $SAPIENS_ISSUE
      event_type: "issues.labeled"
      ai_provider_type: openai-compatible
      ai_base_url: https://openrouter.ai/api/v1
      ai_model: anthropic/claude-3.5-sonnet
```

### Component Inputs

| Input | Type | Default | Description |
|-------|------|---------|-------------|
| `label` | string | required | Label that triggered the pipeline |
| `issue_number` | number | required | Issue or MR number |
| `event_type` | string | `issues.labeled` | Event type for sapiens CLI |
| `ai_provider_type` | string | `openai-compatible` | AI provider type |
| `ai_model` | string | *(empty)* | AI model to use |
| `ai_base_url` | string | *(empty)* | AI provider base URL |

### Using Ollama

```yaml
include:
  - component: gitlab.com/savorywatt/repo-sapiens/gitlab/sapiens-dispatcher@v2
    inputs:
      label: $SAPIENS_LABEL
      issue_number: $SAPIENS_ISSUE
      event_type: "issues.labeled"
      ai_provider_type: ollama
      ai_base_url: http://ollama.internal:11434
      ai_model: llama3.1:8b
```

---

## Part 3: Webhook Handler Setup

**Important:** GitLab does not have native label triggers like GitHub/Gitea. You need webhook handlers to trigger pipelines when:
- Labels are added to issues or merge requests
- Comments are posted with trigger keywords (e.g., `@sapiens`)

repo-sapiens provides ready-to-use webhook handlers in the `scripts/` directory.

---

### 3.1 Create a Pipeline Trigger Token

1. Go to **Settings** > **CI/CD** > **Pipeline trigger tokens**
2. Click **Add trigger**
3. Give it a description (e.g., "Sapiens webhook handler")
4. Copy the trigger token

---

### 3.2 Label Webhook Handler

This handler triggers pipelines when labels are added to issues or merge requests.

#### Simple Flask Handler

```python
# gitlab_webhook_handler.py
"""
GitLab webhook handler for repo-sapiens.

This handler receives webhook events from GitLab and triggers
the sapiens pipeline when labels are added to issues or MRs.

Deploy to: AWS Lambda, Google Cloud Functions, Vercel, or self-hosted.
"""

from flask import Flask, request, jsonify
import requests
import os

app = Flask(__name__)

# Configuration from environment variables
GITLAB_URL = os.environ.get("GITLAB_URL", "https://gitlab.com")
PROJECT_ID = os.environ.get("GITLAB_PROJECT_ID")
TRIGGER_TOKEN = os.environ.get("GITLAB_TRIGGER_TOKEN")
WEBHOOK_SECRET = os.environ.get("GITLAB_WEBHOOK_SECRET", "")


def verify_webhook_token(request_token: str) -> bool:
    """Verify the webhook secret token."""
    if not WEBHOOK_SECRET:
        return True  # No secret configured, allow all
    return request_token == WEBHOOK_SECRET


@app.route("/webhook", methods=["POST"])
def handle_webhook():
    """Handle GitLab webhook events."""
    # Verify webhook token if configured
    request_token = request.headers.get("X-Gitlab-Token", "")
    if not verify_webhook_token(request_token):
        return jsonify({"error": "Invalid webhook token"}), 403

    data = request.json
    if not data:
        return jsonify({"error": "No JSON payload"}), 400

    # Determine event type
    event_type = request.headers.get("X-Gitlab-Event", "")

    # Handle Issue events
    if event_type == "Issue Hook":
        return handle_issue_event(data)

    # Handle Merge Request events
    if event_type == "Merge Request Hook":
        return handle_merge_request_event(data)

    return jsonify({"message": "Event type not handled"}), 200


def handle_issue_event(data: dict):
    """Handle issue webhook events."""
    action = data.get("object_attributes", {}).get("action")

    # Only process label updates
    if action != "update":
        return jsonify({"message": "Not a label update"}), 200

    # Check if labels changed
    changes = data.get("changes", {})
    if "labels" not in changes:
        return jsonify({"message": "No label changes"}), 200

    # Get the newly added labels
    previous_labels = {l["title"] for l in changes["labels"].get("previous", [])}
    current_labels = {l["title"] for l in changes["labels"].get("current", [])}
    added_labels = current_labels - previous_labels

    if not added_labels:
        return jsonify({"message": "No new labels added"}), 200

    # Trigger pipeline for each new label
    issue_iid = data["object_attributes"]["iid"]
    for label in added_labels:
        trigger_pipeline(label, issue_iid, "issues.labeled")

    return jsonify({
        "message": f"Triggered pipelines for labels: {added_labels}",
        "issue": issue_iid
    }), 200


def handle_merge_request_event(data: dict):
    """Handle merge request webhook events."""
    action = data.get("object_attributes", {}).get("action")

    # Only process label updates
    if action != "update":
        return jsonify({"message": "Not a label update"}), 200

    # Check if labels changed
    changes = data.get("changes", {})
    if "labels" not in changes:
        return jsonify({"message": "No label changes"}), 200

    # Get the newly added labels
    previous_labels = {l["title"] for l in changes["labels"].get("previous", [])}
    current_labels = {l["title"] for l in changes["labels"].get("current", [])}
    added_labels = current_labels - previous_labels

    if not added_labels:
        return jsonify({"message": "No new labels added"}), 200

    # Trigger pipeline for each new label
    mr_iid = data["object_attributes"]["iid"]
    for label in added_labels:
        trigger_pipeline(label, mr_iid, "merge_request.labeled")

    return jsonify({
        "message": f"Triggered pipelines for labels: {added_labels}",
        "merge_request": mr_iid
    }), 200


def trigger_pipeline(label: str, issue_number: int, event_type: str):
    """Trigger a GitLab pipeline with sapiens variables."""
    url = f"{GITLAB_URL}/api/v4/projects/{PROJECT_ID}/trigger/pipeline"

    response = requests.post(
        url,
        data={
            "token": TRIGGER_TOKEN,
            "ref": "main",  # or your default branch
            "variables[SAPIENS_LABEL]": label,
            "variables[SAPIENS_ISSUE]": str(issue_number),
            "variables[SAPIENS_EVENT_TYPE]": event_type,
        }
    )

    if response.status_code == 201:
        print(f"Pipeline triggered for label '{label}' on #{issue_number}")
    else:
        print(f"Failed to trigger pipeline: {response.text}")

    return response


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
```

### 3.3 Deployment Options

#### Option A: Vercel (Serverless)

1. Create a `vercel.json`:
```json
{
  "builds": [
    { "src": "gitlab_webhook_handler.py", "use": "@vercel/python" }
  ],
  "routes": [
    { "src": "/webhook", "dest": "gitlab_webhook_handler.py" }
  ]
}
```

2. Create `requirements.txt`:
```
flask
requests
```

3. Deploy:
```bash
vercel --prod
```

4. Set environment variables in Vercel dashboard.

#### Option B: AWS Lambda

1. Package the handler with dependencies
2. Create a Lambda function with API Gateway
3. Set environment variables in Lambda configuration

#### Option C: Self-Hosted

1. Install dependencies:
```bash
pip install flask requests gunicorn
```

2. Run with gunicorn:
```bash
gunicorn gitlab_webhook_handler:app -b 0.0.0.0:8080
```

3. Put behind a reverse proxy (nginx) with HTTPS.

### 3.4 Configure GitLab Webhook

1. Go to **Settings** > **Webhooks**
2. Add a new webhook:
   - **URL**: `https://your-handler-url/webhook`
   - **Secret token**: Set a secure token (optional but recommended)
   - **Trigger**: Select "Issues events" and "Merge request events"
   - **Enable SSL verification**: Yes (if using HTTPS)
3. Click **Add webhook**
4. Test the webhook with the "Test" button

---

### 3.5 Comment Webhook Handler (for @sapiens mentions)

This handler enables the **comment-response workflow** - allowing users to interact with sapiens by mentioning `@sapiens` in issue comments.

repo-sapiens includes a production-ready comment webhook handler at `scripts/gitlab-comment-webhook.py`.

#### Deploy with Docker (Recommended)

```bash
# Build the image
cd scripts/
docker build -t gitlab-comment-webhook -f Dockerfile.gitlab-webhook .

# Run the container
docker run -d --name gitlab-webhook \
    -e GITLAB_URL=https://gitlab.example.com \
    -e GITLAB_API_TOKEN=glpat-xxxxxxxxxxxx \
    -e GITLAB_WEBHOOK_SECRET=your-secure-secret \
    -e TRIGGER_REF=main \
    -p 8000:8000 \
    gitlab-comment-webhook
```

#### Deploy Standalone

```bash
# Install dependencies
pip install fastapi uvicorn httpx

# Run the server
GITLAB_URL=https://gitlab.example.com \
GITLAB_API_TOKEN=glpat-xxxxxxxxxxxx \
GITLAB_WEBHOOK_SECRET=your-secure-secret \
python scripts/gitlab-comment-webhook.py
```

#### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GITLAB_API_TOKEN` | Yes | - | GitLab PAT with `api` scope |
| `GITLAB_WEBHOOK_SECRET` | Yes | - | Secret token for webhook verification |
| `GITLAB_URL` | No | `http://localhost` | GitLab instance URL |
| `LISTEN_PORT` | No | `8000` | Port to listen on |
| `TRIGGER_REF` | No | `main` | Git ref for pipeline triggers |
| `LOG_LEVEL` | No | `INFO` | Logging level |

#### Configure GitLab Webhook for Comments

1. Go to **Settings** > **Webhooks**
2. Add a new webhook:
   - **URL**: `https://your-handler-url/webhook/gitlab/comment`
   - **Secret token**: Match `GITLAB_WEBHOOK_SECRET`
   - **Trigger**: Select **"Comments"** (Note events)
   - **Enable SSL verification**: Yes (if using HTTPS)
3. Click **Add webhook**

#### Trigger Keywords

Comments containing these keywords will trigger the sapiens pipeline:
- `@sapiens` - Mention sapiens
- `sapiens:` - Command prefix

Example comment:
```
@sapiens can you analyze this bug and suggest a fix?
```

#### Health Check

The webhook handler exposes a health endpoint:
```bash
curl http://localhost:8000/health
# {"status": "healthy", "gitlab_url": "https://gitlab.example.com"}
```

---

## Part 4: Create Labels

Create the standard sapiens labels in your GitLab project:

1. Go to **Project information** > **Labels**
2. Create these labels:

| Label | Color | Description |
|-------|-------|-------------|
| `needs-planning` | `#0052CC` | Issue needs a development plan |
| `proposed` | `#36B37E` | Plan has been proposed |
| `approved` | `#00875A` | Plan approved, ready for tasks |
| `task` | `#6554C0` | This is a task issue |
| `execute` | `#FF5630` | Task ready to execute |
| `needs-review` | `#FFAB00` | MR needs code review |
| `needs-fix` | `#FF8B00` | Changes needed based on review |
| `requires-qa` | `#00B8D9` | Ready for QA/testing |
| `qa-passed` | `#36B37E` | QA passed |
| `qa-failed` | `#FF5630` | QA failed |
| `completed` | `#6B778C` | Work completed |

---

## Part 5: Test Your Setup

### Manual Pipeline Test

1. Go to **CI/CD** > **Pipelines**
2. Click **Run pipeline**
3. Add variables:
   - `SAPIENS_LABEL`: `needs-planning`
   - `SAPIENS_ISSUE`: `1`
4. Click **Run pipeline**

### Webhook Test

1. Create a test issue
2. Add the `needs-planning` label
3. Check your webhook handler logs
4. Verify pipeline was triggered in **CI/CD** > **Pipelines**

---

## Troubleshooting

### Pipeline not triggering

1. Check webhook handler logs for errors
2. Verify the trigger token is correct
3. Check GitLab webhook delivery history (**Settings** > **Webhooks** > click webhook > **Recent deliveries**)

### Authentication errors

1. Verify `SAPIENS_GITLAB_TOKEN` has correct permissions
2. Check the token hasn't expired
3. Ensure the variable is marked as "Protected" only if running on protected branches

### Webhook errors

1. Check the webhook URL is accessible from GitLab
2. Verify SSL certificate if using HTTPS
3. Check the webhook secret token matches

### Component not found

1. Ensure you're using GitLab 16.0 or higher
2. Verify the component path is correct
3. Check if the component repository is accessible

---

## Quick Reference

### Required CI/CD Variables

| Variable | Description |
|----------|-------------|
| `SAPIENS_GITLAB_TOKEN` | GitLab PAT with api, read_repository, write_repository |
| `SAPIENS_AI_API_KEY` | AI provider API key (OpenRouter, etc.) |

### Webhook Handler Environment Variables

| Variable | Description |
|----------|-------------|
| `GITLAB_URL` | Your GitLab instance URL |
| `GITLAB_PROJECT_ID` | Your project's numeric ID |
| `GITLAB_TRIGGER_TOKEN` | Pipeline trigger token |
| `GITLAB_WEBHOOK_SECRET` | Optional webhook secret |

### Pipeline Variables (Set by Webhook Handler)

| Variable | Description |
|----------|-------------|
| `SAPIENS_LABEL` | Label that triggered the pipeline |
| `SAPIENS_ISSUE` | Issue or MR IID |
| `SAPIENS_EVENT_TYPE` | Event type (`issues.labeled` or `merge_request.labeled`) |

---

## Related Documentation

- [WORKFLOW_REFERENCE.md](WORKFLOW_REFERENCE.md) - Complete input/secret reference
- [GITHUB_OPENROUTER_SETUP.md](GITHUB_OPENROUTER_SETUP.md) - GitHub setup guide
- [GITEA_NEW_REPO_TUTORIAL.md](GITEA_NEW_REPO_TUTORIAL.md) - Gitea setup guide
