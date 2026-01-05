# Workflow Diagram

This document illustrates the complete automation workflow.

## High-Level Flow

```
Issue Created → [needs-planning] → Plan Proposal → [approved] →
Task Creation → [execute] → Implementation → [needs-review] →
Code Review → [requires-qa] → QA → Merge/PR
```

## Label-Driven Architecture

The system uses labels to drive workflow progression. Each label triggers a dedicated workflow file:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         LABEL-DRIVEN PIPELINE                           │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Issue Created                                                          │
│       │                                                                 │
│       ▼                                                                 │
│  [needs-planning] ──► needs-planning.yaml ──► Plan Proposal             │
│       │                                                                 │
│       ▼                                                                 │
│  [approved] ──► approved.yaml ──► Task Creation                         │
│       │                                                                 │
│       ▼                                                                 │
│  [execute] ──► execute-task.yaml ──► Implementation                     │
│       │                                                                 │
│       ▼                                                                 │
│  [needs-review] ──► needs-review.yaml ──► Code Review                   │
│       │                                                                 │
│       ├──► [requires-qa] ──► requires-qa.yaml ──► QA Testing            │
│       │                                                                 │
│       └──► [needs-fix] ──► needs-fix.yaml ──► Fix Issues                │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
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
│ needs-planning.yaml     │
│ triggers on label       │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│ CLI: sapiens            │
│ process-issue --issue N │
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
│ Issue updated with      │
│ proposed label and      │
│ plan comment            │
└─────────────────────────┘
```

### 2. Plan Review and Approval

```
┌─────────────────────────┐
│ Team reviews plan       │
│ in issue comments       │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│ Plan approved:          │
│ Add 'approved' label    │
│ to issue                │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│ approved.yaml triggers  │
│ (requires 'proposed'    │
│ label also present)     │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│ CLI: sapiens            │
│ process-issue --issue N │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│ Task issues created     │
│ with 'task' label       │
└─────────────────────────┘
```

### 3. Task Execution

```
┌─────────────────────────┐
│ Add 'execute' label     │
│ to task issue           │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│ execute-task.yaml       │
│ triggers (requires      │
│ 'task' label also)      │
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
│ State artifacts         │
│ uploaded for debugging  │
└─────────────────────────┘
```

### 4. Code Review

```
┌─────────────────────────┐
│ Add 'needs-review'      │
│ label to issue          │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│ needs-review.yaml       │
│ triggers                │
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
     │   │ Add 'needs-fix'  │
     │   │ label            │
     │   └──────────────────┘
     │
     ▼
┌─────────────────────────┐
│ Add 'requires-qa' label │
│ for QA testing          │
└─────────────────────────┘
```

### 5. QA and Merge

```
┌─────────────────────────┐
│ 'requires-qa' label     │
│ triggers QA workflow    │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│ requires-qa.yaml        │
│ runs QA checks          │
└────────┬────────────────┘
         │
         ▼
     ┌───┴───┐
     │       │
  Passed   Failed
     │       │
     │       ▼
     │   ┌──────────────────┐
     │   │ Add 'needs-fix'  │
     │   │ label            │
     │   └──────────────────┘
     │
     ▼
┌─────────────────────────┐
│ Create Pull Request     │
│ with implementation     │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│ Update related issues   │
│ with PR link            │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│ Mark plan as completed  │
│ in state                │
└─────────────────────────┘
```

### 6. Fix Flow (When Changes Needed)

```
┌─────────────────────────┐
│ 'needs-fix' label       │
│ added to issue          │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│ needs-fix.yaml          │
│ triggers                │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│ Agent addresses         │
│ review feedback         │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│ Commits fixes to        │
│ existing branch         │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│ Re-request review       │
│ (add 'needs-review')    │
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

### Internal Stage Tracking

The StateManager tracks these internal stages:

```
planning → plan_review → prompts → implementation → code_review → merge
```

## CI/CD Workflow Files

```
.gitea/workflows/
├── needs-planning.yaml     ──→ Triggered by 'needs-planning' label
├── approved.yaml           ──→ Triggered by 'approved' label
├── execute-task.yaml       ──→ Triggered by 'execute' label
├── needs-review.yaml       ──→ Triggered by 'needs-review' label
├── needs-fix.yaml          ──→ Triggered by 'needs-fix' label
├── requires-qa.yaml        ──→ Triggered by 'requires-qa' label
├── plan-merged.yaml        ──→ Triggered by push to main (plans/)
├── automation-daemon.yaml  ──→ Scheduled (cron: */5 * * * *)
├── monitor.yaml            ──→ Scheduled (cron: 0 */6 * * *)
├── test.yaml               ──→ Triggered by PR/push
└── build-artifacts.yaml    ──→ Builds wheel for faster installs
```

## File Structure Flow

```
Issue #42 created
    ↓
plans/42-feature-name.md created
    ↓
.automation/state/42.json created
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

## CLI Commands

| Command | Description |
|---------|-------------|
| `sapiens process-issue --issue N` | Process a single issue |
| `sapiens process-all` | Process all pending issues |
| `sapiens process-plan --plan-id N` | Process entire plan |
| `sapiens list-plans` | List active plans |
| `sapiens show-plan --plan-id N` | Show plan details |
| `sapiens check-stale` | Find stale workflows |
| `sapiens health-check` | Generate health report |
| `sapiens check-failures` | Find recent failures |
| `sapiens daemon` | Run continuous polling |
