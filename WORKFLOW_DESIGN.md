# Builder Workflow Design

## User-Controlled Incremental Execution

### Overview

Builder creates a granular, user-controlled workflow where each phase can be reviewed and executed independently.

## Workflow Steps

### 1. Initial Issue Created
```
User creates issue: "Build Flappy Bird game"
User adds label: `needs-planning`
```

### 2. Planning Stage
**Trigger:** `needs-planning` label

**Builder Actions:**
1. Generates development plan using AI
2. Creates **Proposal Issue**:
   - Title: `[PROPOSAL] Plan for #1: Build Flappy Bird game`
   - Body: Full markdown plan with tasks
   - Labels: `proposed`, `plan-for-#1`
   - References original issue
3. Comments on original issue:
   ```
   📋 Plan proposal created: #2
   Please review and comment "ok" to approve.
   ```

### 3. User Reviews Proposal
```
User reads proposal issue #2
User comments: "ok" (or "approve", "lgtm")
```

### 4. Plan Approval Stage
**Trigger:** Comment "ok" on issue with `proposed` label

**Builder Actions:**
1. Creates **Gitea Project**: "Project: Build Flappy Bird game (#1)"
2. Creates **Task Issues** (one per task in plan):
   ```
   Issue #3: [TASK 1/7] Create base HTML structure
   - Body: Task description, acceptance criteria
   - Labels: `task`, `ready`, `plan-#1`
   - Linked to project
   - Dependency: Blocks #1

   Issue #4: [TASK 2/7] Implement game engine
   - Labels: `task`, `ready`, `plan-#1`
   - Dependencies: Requires #3
   - Linked to project

   ... (one issue per task)
   ```
3. Updates original issue:
   ```
   ✅ Plan approved! Created 7 tasks in Project "Build Flappy Bird game"

   Tasks: #3, #4, #5, #6, #7, #8, #9

   Change any task label to `execute` when ready to build.
   ```
4. Closes proposal issue #2
5. Removes `needs-planning` from original issue

### 5. User Selects Tasks to Execute
```
User reviews task issues
User decides to start with task #3
User changes label: `ready` → `execute`
```

### 6. Task Execution Stage
**Trigger:** `execute` label on task issue

**Builder Actions:**
1. Comments on task issue:
   ```
   🔨 Starting implementation on branch `task-3-base-html`
   ```
2. Creates branch: `task-3-base-html`
3. Runs AI agent with task context:
   - Task description
   - Acceptance criteria
   - Dependencies (reads completed tasks)
   - Can ask questions via comments
4. Agent implements task
5. Commits changes to branch
6. Creates PR:
   - Title: `[Task #3] Create base HTML structure`
   - Links to task issue
   - Auto-assigns reviewers
7. Updates task issue:
   ```
   ✅ Implementation complete!
   Pull Request: #10
   Branch: task-3-base-html

   Please review and merge, or comment for changes.
   ```
8. Changes label: `execute` → `review`

### 7. User Reviews & Merges
```
User reviews PR #10
User merges PR (or comments for changes)
```

### 8. Post-Merge Cleanup
**Trigger:** PR merged

**Builder Actions:**
1. Closes task issue #3
2. Updates project board (moves to "Done")
3. Comments on original issue:
   ```
   ✅ Task 1/7 complete: Create base HTML structure (#3)

   Remaining: 6 tasks
   Ready to execute: #4 (dependencies met)
   ```

### 9. Rinse & Repeat
```
User changes #4 label to `execute`
Process repeats for each task...
```

### 10. Completion
**Trigger:** All task issues closed

**Builder Actions:**
1. Comments on original issue:
   ```
   🎉 All tasks complete!
   Project "Build Flappy Bird game" finished.

   7/7 tasks completed
   ```
2. Closes original issue
3. Archives project

## Workflow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│ Issue #1: "Build Flappy Bird"                               │
│ Label: needs-planning                                       │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────┐
│ Builder: Generate Plan                                      │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────┐
│ Issue #2: "[PROPOSAL] Plan for #1"                         │
│ Label: proposed                                             │
│ [User reviews and comments "ok"]                            │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────┐
│ Builder: Create Project + Task Issues                       │
│                                                              │
│ Project: "Build Flappy Bird"                                │
│ ├── Issue #3: [TASK 1/7] Base HTML (ready)                 │
│ ├── Issue #4: [TASK 2/7] Game Engine (ready)               │
│ ├── Issue #5: [TASK 3/7] Bird Classes (ready)              │
│ └── ... (7 tasks total)                                     │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────┐
│ User: Change #3 label to "execute"                         │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────┐
│ Builder: Execute Task #3                                    │
│ - Create branch                                             │
│ - Run AI agent                                              │
│ - Commit changes                                            │
│ - Create PR                                                 │
│ - Update label: execute → review                            │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────┐
│ User: Review PR, merge                                      │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────┐
│ Builder: Close task #3, update project                      │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ▼
         [Repeat for remaining tasks]
                   │
                   ▼
┌─────────────────────────────────────────────────────────────┐
│ Builder: All tasks done, close issue #1                    │
└─────────────────────────────────────────────────────────────┘
```

## Labels

- `needs-planning` - Triggers plan generation
- `proposed` - Plan waiting for approval
- `task` - Individual task issue
- `ready` - Task ready to execute (dependencies met)
- `execute` - User wants this task built NOW
- `review` - Task implementation done, awaiting review
- `blocked` - Task blocked by dependencies

## Issue Linking

- Proposal issue references original: `Plan for #1`
- Task issues reference original: `Implements #1`
- Task issues reference dependencies: `Requires #3, #4`
- PRs reference tasks: `Closes #3`

## Benefits

✅ **Granular Control** - Execute tasks one at a time or in batches
✅ **Clear Progress** - Project board shows status
✅ **Incremental Review** - Review each task's PR individually
✅ **Flexibility** - Change order, skip tasks, add new ones
✅ **Transparency** - Full audit trail in issues
✅ **Dependency Tracking** - Can't execute blocked tasks
✅ **Parallel Execution** - Multiple `execute` labels = parallel work

## Example Timeline

```
Day 1, 9am:  User creates issue #1, adds `needs-planning`
Day 1, 9:01: Builder creates proposal #2
Day 1, 9:15: User reviews, comments "ok"
Day 1, 9:16: Builder creates project + 7 task issues (#3-#9)
Day 1, 9:20: User sets #3 to `execute`
Day 1, 9:21: Builder starts work, creates PR
Day 1, 9:25: Builder posts "Implementation complete, PR #10"
Day 1, 10am: User reviews, merges PR #10
Day 1, 10:01: Builder closes #3, updates project
Day 1, 10:05: User sets #4 and #5 to `execute` (parallel)
... continues ...
```

## Configuration

```yaml
workflow:
  proposal_approval_keywords: ["ok", "approve", "lgtm", "approved"]
  task_labels:
    ready: "ready"
    execute: "execute"
    review: "review"
    blocked: "blocked"
  auto_close_proposal: true
  create_project_boards: true
```
