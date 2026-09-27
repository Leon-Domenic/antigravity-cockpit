---
name: paperclip-fleet
description: Native inter-agent communication, CEO coordination, fleet discovery, work order progress reporting, subtask delegation, and peer messaging across the Webigo Workspaces cluster.
---

# Paperclip Fleet Communication & Coordination

This skill equips you with native inter-agent communication and task orchestration across the Webigo Workspaces cluster.
Use this skill whenever you need to:
1. Discover peer agents and their assigned specialties (Frontend, Backend, SecOps, QA, DevOps).
2. Send messages, handovers, technical questions, or status updates to other agents or to the CEO Orchestrator.
3. Check your incoming message inbox for directives, feedback, questions, or handovers from peer agents.
4. Report progress, blockers, or completion on active work orders.
5. Delegate subtasks to specialized roles in the cluster.

---

## 1. Quick CLI Reference

The `paperclip` CLI tool is available in your shell environment (`/usr/local/bin/paperclip`).

### Identify Self & Cluster Status
```bash
# Check your local agent identity, role, and bridge connection
paperclip whoami

# Discover all active agents across the cluster, their roles, IPs, and busy/idle states
paperclip fleet
```

### Checking Your Inbox
```bash
# Read all incoming messages
paperclip msg inbox

# Read only unread messages and mark them as read
paperclip msg inbox --unread --mark-read

# Fetch up to 10 latest messages
paperclip msg inbox --limit 10
```

### Sending Messages
```bash
# Send a direct message or technical question to a specific peer agent
paperclip msg send agent-2 "Hey Agent 2, could you verify if the PostgreSQL migration on port 5432 completed?"

# Send a message to a specific role (will route to the online agent filling that role)
paperclip msg send secops "Please review the new JWT verification middleware for security flaws."

# Send a status report or update directly to the CEO Orchestrator
paperclip msg send ceo "Frontend dashboard components have been converted to responsive Tailwind CSS." --type status_report

# Send a handover message to the next agent in a sequential workflow
paperclip msg send agent-2 "Database schema has been migrated and seed data created. Ready for API endpoint implementation." --type handover --order-id WO-1

# Send an URGENT alert (triggers immediate high-priority notification in recipient's IDE)
paperclip msg send agent-1 "Critical test failure detected in auth flow on CT 151!" --urgent

# Broadcast an announcement to all online agents in the cluster
paperclip msg send broadcast "Cluster-wide repository sync complete. Please pull latest main."
```

### Task Progress Reporting
When executing a work order assigned by the CEO Orchestrator, report progress so the supervisor can monitor status and automatically unblock dependent tasks:

```bash
# View all work orders assigned to you
paperclip task list

# Report that work is actively in progress
paperclip task report --order-id WO-1 --status in_progress --note "Refactoring auth controller"

# Report task completion (automatically unblocks downstream dependent tasks!)
paperclip task report --order-id WO-1 --status done --note "Auth controller refactored, all 14 tests passing" --files "src/auth.ts,tests/auth.test.ts"

# Report a blocker (automatically alerts CEO Orchestrator for escalation)
paperclip task report --order-id WO-1 --status blocked --note "Requires database credentials for Convex deployment"
```

### Subtask Delegation
When your current work order requires assistance from another specialist (e.g. QA testing, backend database provisioning, SecOps vulnerability scan):

```bash
# Delegate a subtask to the QA specialist role
paperclip task delegate --order-id WO-1 --role qa --title "Verify End-to-End User Login Flow" --instructions "Run Playwright tests against http://192.168.178.169:3000 and ensure session token persists across reloads." --criteria "All tests pass,No console errors logged"
```

---

## 2. Python Client Library

If writing automation scripts or Python workflows, you can import `paperclip_client`:

```python
import sys
sys.path.append("/usr/local/bin")
import paperclip_client as paperclip

# Discover identity & fleet
identity = paperclip.whoami()
print(f"I am {identity['agent_id']} ({identity['role']})")

fleet = paperclip.get_fleet()
for agent in fleet:
    print(f"Agent {agent['id']}: {agent['role']} at {agent['ip']}")

# Check unread messages
messages = paperclip.get_inbox(unread_only=True, mark_read=True)
for msg in messages:
    print(f"Message from {msg['sender_id']}: {msg['content']}")

# Send peer message
paperclip.send_message(
    recipient="agent-2",
    content="Migration files ready at /home/ubuntu/workspace/migrations",
    message_type="direct"
)

# Report task completion
paperclip.report_task(
    order_id="WO-1",
    status="done",
    note="Frontend UI implemented and validated with responsive viewport checks.",
    files_modified=["app/page.tsx", "components/Header.tsx"]
)
```

---

## 3. Communication Protocols & Best Practices

1. **Self-Identification**: Use `paperclip whoami` at the start of a task if you are unsure of your role in the fleet.
2. **Clear Handovers**: When completing a task that unblocks another specialist, always call `paperclip task report --status done` and optionally send a `handover` message with context (file locations, ports, test results).
3. **Escalate Blockers Promptly**: If an external dependency, missing secret, or environment error prevents progress, mark the task as `blocked` using `paperclip task report --status blocked --note "<reason>"`. This alerts the CEO to resolve the blockage.
4. **Use Appropriate Message Types**:
   - `direct`: 1-on-1 coordination or questions.
   - `status_report`: progress summaries sent to `ceo`.
   - `handover`: passing completed context to downstream workers.
   - `question`: seeking specific domain expertise.
   - `escalation`: urgent obstacles requiring supervisor intervention.
