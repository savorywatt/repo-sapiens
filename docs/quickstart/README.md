# Quick Start Guides

Choose your Git provider to get started with repo-sapiens.

| Provider | Guide | Time | Notes |
|----------|-------|------|-------|
| [GitHub](GITHUB.md) | 5 min | Uses reusable workflows, minimal setup |
| [Gitea](GITEA.md) | 5 min | Full workflows deployed to repo |
| [GitLab](GITLAB.md) | 10 min | Daemon mode (polling) or webhook mode |

---

## Which Provider Should I Choose?

All three providers are fully supported. Choose based on where your code lives:

- **GitHub** - Best developer experience, native label triggers, reusable workflows
- **Gitea** - Self-hosted, GitHub-compatible Actions, full control
- **GitLab** - Enterprise features, CI/CD Components, requires daemon or webhook

---

## Common Setup Steps

Regardless of provider, you'll need:

1. **Install repo-sapiens**
   ```bash
   pip install repo-sapiens==0.5.1
   ```

2. **Run the init wizard**
   ```bash
   cd your-repo
   sapiens init
   ```

3. **Configure secrets** in your provider's settings

4. **Create a labeled issue** to test

---

## After Setup

Once running, repo-sapiens responds to these labels:

| Label | What Happens |
|-------|--------------|
| `needs-planning` | AI generates a development plan |
| `approved` | AI implements the approved plan |
| `needs-review` | AI reviews the code changes |
| `needs-fix` | AI applies suggested fixes |
| `requires-qa` | AI runs QA validation |

---

## More Resources

- [Full Getting Started Guide](../GETTING_STARTED.md)
- [Agent Comparison](../AGENT_COMPARISON.md)
- [Workflow Reference](../WORKFLOW_REFERENCE.md)
- [Credentials Guide](../CREDENTIALS.md)
