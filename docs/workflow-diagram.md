# Workflow Diagram

This document illustrates the complete automation workflow.

## High-Level Flow

```
Issue Created → Planning → Plan Review → Prompt Generation →
Implementation → Code Review → Merge → Pull Request
```

## Detailed Workflow

### 1. Issue Creation and Planning

```
┌─────────────────┐
│ User creates    │
│ issue with      │
│ needs-planning  │
│ label           │
└────────┬────────┘
         │
         ▼
┌─────────────────────────┐
│ Gitea Actions Trigger   │
│ (automation-trigger)    │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│ CLI: process-issue      │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│ Agent generates plan    │
│ from issue description  │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│ Plan saved to           │
│ plans/{id}-{slug}.md    │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│ Plan review issue       │
│ created with            │
│ plan-review label       │
└─────────────────────────┘
```

### 2. Plan Review and Approval

```
┌─────────────────────────┐
│ Team reviews plan       │
│ Comments on review      │
│ issue                   │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│ Plan approved           │
│ (close review issue or  │
│ add approved label)     │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│ Plan merged to main     │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│ Plan ready for          │
│ implementation          │
└─────────────────────────┘
```

### 3. Prompt Generation

```
┌─────────────────────────┐
│ Agent parses plan       │
│ markdown to extract     │
│ tasks                   │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│ For each task:          │
│ Create issue with       │
│ implement label         │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│ Task dependencies       │
│ tracked in state        │
└─────────────────────────┘
```

### 4. Task Implementation

```
┌─────────────────────────┐
│ Issue with implement    │
│ label detected          │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│ Check dependencies      │
│ are complete            │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│ Create/checkout branch  │
│ (based on strategy)     │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│ Agent executes task     │
│ (writes code, tests)    │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│ Commit changes to       │
│ task branch             │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│ Add code-review label   │
│ to task issue           │
└─────────────────────────┘
```

### 5. Code Review

```
┌─────────────────────────┐
│ Issue with code-review  │
│ label detected          │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│ Get diff from branch    │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│ Agent reviews code      │
│ (quality, tests, style) │
└────────┬────────────────┘
         │
         ▼
     ┌───┴───┐
     │       │
 Approved  Changes
     │     Needed
     │       │
     │       ▼
     │   ┌──────────────────┐
     │   │ Post review      │
     │   │ comments         │
     │   └──────────────────┘
     │
     ▼
┌─────────────────────────┐
│ Add merge-ready label   │
└─────────────────────────┘
```

### 6. Merge and Pull Request

```
┌─────────────────────────┐
│ All tasks in plan       │
│ have merge-ready label  │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│ Branching strategy:     │
│ - Per-plan: Use plan    │
│   branch                │
│ - Per-agent: Merge all  │
│   task branches         │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│ Create Pull Request     │
│ with summary of all     │
│ tasks                   │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│ Update all related      │
│ issues with PR link     │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│ Mark plan as completed  │
│ in state                │
└─────────────────────────┘
```

## Parallel Execution

Tasks with no dependencies can execute in parallel:

```
Task 1 (no deps) ─────┐
                      │
Task 2 (no deps) ─────┼──→ Execute in parallel
                      │
Task 3 (no deps) ─────┘

         │
         ▼
Task 4 (depends on 1,2,3) ──→ Execute after all deps complete
```

## State Transitions

```
pending → in_progress → completed
   │                        ▲
   │                        │
   └──→ failed ─────────────┘
         (recovery)
```

## CI/CD Triggers

```
Issue Event         →  automation-trigger.yaml
Cron Schedule       →  automation-daemon.yaml
PR/Push             →  test.yaml
```

## File Structure Flow

```
Issue #42 created
    ↓
plans/42-feature-name.md created
    ↓
.sapiens/state/42.json created
    ↓
Task issues created (#43, #44, #45)
    ↓
Branches created:
  - task/42-task-1
  - task/42-task-2
  - task/42-task-3
    ↓
Integration branch: integration/plan-42
    ↓
Pull Request created
```
