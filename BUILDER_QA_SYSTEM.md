# Builder Interactive Q&A System

## Overview

Builder now supports **interactive communication** between the automation agent (Claude/Goose) and users via GitHub/Gitea issue comments.

## How It Works

### 1. **Status Updates** 
Builder automatically posts comments at key points:

```
🚀 **Builder Starting**

I'm starting to work on this issue. 
I'll generate a development plan and post it for review.

🤖 Posted by Builder Automation
```

```
🔨 **Implementation Starting**

I'm starting implementation on branch `feature/issue-42`.

I'll work through the tasks and keep you updated on progress.

🤖 Posted by Builder Automation
```

### 2. **Agent Questions**
When the agent (Claude/Goose) needs clarification during implementation, it can ask questions by outputting:

```
BUILDER_QUESTION: Should I use PostgreSQL or MySQL for the database?
```

Builder will:
1. **Post the question as an issue comment**:
   ```
   ## 🤔 Builder Question
   
   The automation agent needs clarification:
   
   **Question:** Should I use PostgreSQL or MySQL for the database?
   
   **Context:** Task: Implement database layer
   
   ---
   *Please reply to this comment with your answer. The agent will continue once you respond.*
   ```

2. **Monitor for responses** (polls every 30 seconds)
3. **Pass the answer back** to the agent
4. **Continue execution** with the provided information

### 3. **Progress Reports**
Builder posts updates as it works:

```
🔄 **Task Progress**

**Task:** Implement user authentication
**Status:** In Progress

**Details:** Created login endpoint, working on JWT generation

🤖 Posted by Builder Automation
```

## For Agents (Claude/Goose)

When working on a task, you can ask questions by outputting:

```
BUILDER_QUESTION: Your question here
```

Builder will:
- Post your question to the issue  
- Wait up to 30 minutes for a response
- Pass the answer back to you
- You can then continue with the updated context

## For Users

### Responding to Questions

When you see a "Builder Question" comment:
1. Simply **reply to that comment** with your answer
2. Builder polls every 30 seconds and will detect your response
3. The agent continues automatically with your input

### Manual Status Checks

You can always check progress by:
- Reading the issue comments (Builder posts updates)
- Checking the branch mentioned in the comments
- Looking at commits on that branch

## Configuration

In `automation/config/your_config.yaml`:

```yaml
# Default poll interval is 30 seconds
# Default question timeout is 30 minutes
```

## Architecture

```
┌─────────────────┐
│   Gitea Issue   │
└────────┬────────┘
         │
    ┌────▼────────────────────────┐
    │  Builder Orchestrator      │
    │                             │
    │  ┌──────────────────────┐   │
    │  │ InteractiveQAHandler │   │
    │  │ - Post questions     │   │
    │  │ - Monitor responses  │   │
    │  │ - Post progress      │   │
    │  └──────────────────────┘   │
    └────────┬────────────────────┘
             │
    ┌────────▼────────────┐
    │  External Agent     │
    │  (Claude/Goose CLI) │
    │                     │
    │  - Executes tasks   │
    │  - Can ask questions│
    │  - Makes commits    │
    └─────────────────────┘
```

## Files

- `automation/utils/interactive.py` - Q&A handler implementation
- `automation/providers/external_agent.py` - Agent Q&A integration
- `automation/engine/stages/planning.py` - Planning stage notifications
- `automation/engine/stages/implementation.py` - Implementation notifications

## Example Workflow

1. User creates issue: "Add user authentication"
2. User adds `needs-planning` label
3. Builder posts: "🚀 Builder Starting..."
4. Builder runs Claude to generate plan (posts plan to issue)
5. User approves plan
6. Builder posts: "🔨 Implementation Starting on branch feature/issue-1"
7. Claude starts working, gets confused about encryption algorithm
8. Claude outputs: `BUILDER_QUESTION: Should I use bcrypt or argon2?`
9. Builder posts question to issue
10. User replies: "Use argon2, it's more secure"
11. Builder passes answer to Claude
12. Claude continues with argon2
13. Builder posts: "✅ Task Progress - Completed: Authentication module"
14. Process continues until done

## Benefits

- ✅ **No context loss** - Agents can clarify requirements mid-task
- ✅ **Transparency** - All communication visible in issue
- ✅ **Asynchronous** - User can respond when available
- ✅ **Audit trail** - Full history of decisions in comments
- ✅ **Flexibility** - Works with any question the agent needs answered
