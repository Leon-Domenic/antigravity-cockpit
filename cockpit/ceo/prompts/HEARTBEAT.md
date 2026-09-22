# HEARTBEAT.md -- CEO Heartbeat Checklist

Run this checklist on every heartbeat cycle to maintain the agent fleet and advance active work orders.

## 1. Fleet & Context Awareness
- Query fleet status (`/api/status`): inspect CPU, memory, running/idle state, and auth state for all containers.
- Check current active workspace context (files, tech stack, sync status).
- Review active chain of command: confirm assigned roles (CTO, Frontend, Backend, Codex, Hermes, Open Claw, QA).

## 2. Board Directive Triage
- Check for new directives from the Board (human operator).
- If a new directive is present:
  1. Decompose into concrete work orders with explicit deliverables.
  2. Map dependencies (`blocked_by`).
  3. Assign to the optimal specialist agents.
  4. Transition status: `todo` → `in_progress` upon dispatch.

## 3. Subagent Maintenance & Progress Supervision
- For each `in_progress` task:
  - Check the assigned agent's activity and logs (`/logs` or status).
  - If the agent has returned to `idle` and completed output:
    - Transition task to `in_review`.
    - Evaluate output against the acceptance criteria.
    - If criteria are met: mark `done`, unblock downstream dependent tasks, and dispatch them.
    - If criteria are not met: issue corrective instructions with feedback.
  - If the agent is stuck in an error loop or blocked:
    - Attempt self-healing (re-inject clarification or restart task).
    - If unresolvable, mark task `blocked` and generate an escalation report.

## 4. Downstream Pipeline Execution
- Check all `todo` tasks whose prerequisite `blocked_by` tasks are now `done`.
- Dispatch ready tasks to their assigned agents.

## 5. Board Status Update
- Compile executive summary: completed milestones, active work, blockers requiring human input.
