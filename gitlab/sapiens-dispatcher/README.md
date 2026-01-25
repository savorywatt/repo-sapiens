# Sapiens Dispatcher - GitLab CI/CD Component

A reusable GitLab CI/CD Component for label-triggered sapiens automation.

## Requirements

- GitLab 16.0 or later (CI/CD Components support)
- A webhook handler to trigger pipelines on label events (see below)

## Usage

Include the component in your `.gitlab-ci.yml`:

```yaml
include:
  - component: gitlab.com/savorywatt/repo-sapiens/gitlab/sapiens-dispatcher@v0.5.1
    inputs:
      label: $SAPIENS_LABEL
      issue_number: $SAPIENS_ISSUE
      event_type: "issues.labeled"
      ai_provider_type: openai-compatible
      ai_base_url: https://openrouter.ai/api/v1
      ai_model: anthropic/claude-3.5-sonnet
```

## Inputs

| Input | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `label` | string | Yes | - | Label that triggered the pipeline |
| `issue_number` | number | Yes | - | Issue or MR number |
| `event_type` | string | No | `issues.labeled` | Event type for sapiens CLI |
| `ai_provider_type` | string | No | `openai-compatible` | AI provider type (`openai-compatible`, `ollama`) |
| `ai_model` | string | No | `""` | AI model to use |
| `ai_base_url` | string | No | `""` | AI provider base URL |

## Required CI/CD Variables

Configure these variables in your GitLab project under **Settings > CI/CD > Variables**:

| Variable | Required | Description |
|----------|----------|-------------|
| `SAPIENS_GITLAB_TOKEN` | Yes | GitLab personal access token with `api` scope |
| `SAPIENS_AI_API_KEY` | Conditional | AI provider API key (not required for Ollama) |

## Webhook Handler Requirement

GitLab does not have native label triggers like GitHub or Gitea. To automate pipeline triggering on label events, you need to set up a webhook handler.

### Setup Steps

1. **Create a Pipeline Trigger Token**
   - Go to **Settings > CI/CD > Pipeline triggers**
   - Create a new trigger token

2. **Configure a Webhook**
   - Go to **Settings > Webhooks**
   - Add a webhook URL pointing to your handler
   - Enable "Issue events" and "Merge request events"

3. **Deploy a Webhook Handler**

   The handler receives GitLab webhook payloads, extracts label information, and triggers pipelines via the GitLab API.

   Example Python handler:

   ```python
   from flask import Flask, request
   import requests

   app = Flask(__name__)

   GITLAB_URL = "https://gitlab.com"
   PROJECT_ID = "your-project-id"
   TRIGGER_TOKEN = "your-trigger-token"

   @app.route("/webhook", methods=["POST"])
   def handle_webhook():
       data = request.json

       # Check if this is a label event
       if "labels" not in data.get("changes", {}):
           return "Not a label event", 200

       # Extract info
       labels = data.get("labels", {}).get("current", [])
       label_name = labels[0]["title"] if labels else None
       issue_number = data["object_attributes"]["iid"]

       if not label_name:
           return "No label", 200

       # Trigger pipeline
       requests.post(
           f"{GITLAB_URL}/api/v4/projects/{PROJECT_ID}/trigger/pipeline",
           data={
               "token": TRIGGER_TOKEN,
               "ref": "main",
               "variables[SAPIENS_LABEL]": label_name,
               "variables[SAPIENS_ISSUE]": str(issue_number),
           }
       )

       return "Pipeline triggered", 200
   ```

### Deployment Options

- **Serverless**: AWS Lambda, Google Cloud Functions, Vercel
- **Self-hosted**: Any server with Flask/FastAPI
- **GitLab itself**: Use GitLab's built-in serverless (if available)

## Manual Pipeline Triggering

For testing, you can manually trigger pipelines with variables:

1. Go to **CI/CD > Pipelines > Run pipeline**
2. Set variables:
   - `SAPIENS_LABEL`: The label name (e.g., `needs-planning`)
   - `SAPIENS_ISSUE`: The issue number (e.g., `42`)
3. Run the pipeline

## AI Provider Examples

### OpenRouter (Recommended)

```yaml
include:
  - component: gitlab.com/savorywatt/repo-sapiens/gitlab/sapiens-dispatcher@v0.5.1
    inputs:
      label: $SAPIENS_LABEL
      issue_number: $SAPIENS_ISSUE
      ai_provider_type: openai-compatible
      ai_base_url: https://openrouter.ai/api/v1
      ai_model: anthropic/claude-3.5-sonnet
```

### Ollama (Self-hosted)

```yaml
include:
  - component: gitlab.com/savorywatt/repo-sapiens/gitlab/sapiens-dispatcher@v0.5.1
    inputs:
      label: $SAPIENS_LABEL
      issue_number: $SAPIENS_ISSUE
      ai_provider_type: ollama
      ai_base_url: http://ollama.internal:11434
      ai_model: llama3.1:8b
```

## Troubleshooting

### Pipeline not triggering

- Verify webhook is configured correctly
- Check webhook delivery logs in GitLab
- Ensure trigger token has correct permissions

### Authentication errors

- Verify `SAPIENS_GITLAB_TOKEN` has `api` scope
- Check token is not expired
- Ensure variable is not masked if it needs to be used in logs

### AI provider errors

- Verify `SAPIENS_AI_API_KEY` is set (unless using Ollama)
- Check `ai_base_url` is correct and accessible
- Verify model name is valid for your provider
