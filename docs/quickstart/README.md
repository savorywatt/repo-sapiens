# Quick Start Guides

Choose your Git provider to get started with repo-sapiens.

| Provider | Guide | Time | Notes |
|----------|-------|------|-------|
| [GitHub](GITHUB.md) | 5 min | Label-triggered workflows, individual workflow files |
| [Gitea](GITEA.md) | 5 min | Label-triggered workflows, Ollama default, self-hosted |
| [GitLab](GITLAB.md) | 10 min | Daemon mode (polling) or webhook mode |

---

## Which Provider Should I Choose?

All three providers are fully supported. Choose based on where your code lives:

- **GitHub** - Best developer experience, native label triggers, individual workflow files
- **Gitea** - Self-hosted, GitHub-compatible Actions, Ollama as default AI, full control
- **GitLab** - Enterprise features, remote CI/CD includes, daemon (polling) or webhook mode

---

## Common Setup Steps

Regardless of provider, you'll need:

1. **Install repo-sapiens**
   ```bash
   pip install repo-sapiens
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
