"""
Unit tests for CEO Orchestration Engine in Antigravity Cockpit.
"""

import os
import sys
import unittest
import time

# Ensure cockpit directory is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ceo.roles import ROLE_DEFINITIONS, ROLES_BY_ID, get_role_spec, match_role_for_task, get_chain_of_command
from ceo.orchestrator import CeoOrchestrator, WorkOrder
from ceo.heartbeat import CeoHeartbeatSupervisor

class TestCeoOrchestration(unittest.TestCase):
    def setUp(self):
        self.mock_agents = [
            {"id": "agent-1", "name": "Agent 1", "role": "Frontend Specialist", "type": "antigravity"},
            {"id": "agent-2", "name": "Agent 2", "role": "Backend Specialist", "type": "antigravity"},
            {"id": "agent-3", "name": "Codex", "role": "Codex Specialist", "type": "codex"},
            {"id": "agent-4", "name": "Hermes Agent", "role": "Hermes Specialist", "type": "hermes"},
            {"id": "agent-5", "name": "Open Claw", "role": "Open Claw Specialist", "type": "openclaw"},
        ]
        self.dispatched_tasks = []

        def mock_dispatch(target, prompt, workspace_id):
            self.dispatched_tasks.append({
                "target": target,
                "prompt": prompt,
                "workspace_id": workspace_id
            })
            return {"status": "ok", "target": target}

        self.mock_dispatch = mock_dispatch
        self.orchestrator = CeoOrchestrator(
            get_agents_fn=lambda: self.mock_agents,
            dispatch_fn=self.mock_dispatch
        )
        self.orchestrator.work_orders = {}
        self.orchestrator.board_directives = []

        self.agent_states = {a["id"]: {"running": True, "busy": False, "status": "idle"} for a in self.mock_agents}
        self.supervisor = CeoHeartbeatSupervisor(
            orchestrator=self.orchestrator,
            get_agents_fn=lambda: self.mock_agents,
            get_agent_status_fn=lambda aid: self.agent_states.get(aid, {"running": False}),
            interval_seconds=30
        )

    def test_roles_registry(self):
        self.assertGreaterEqual(len(ROLE_DEFINITIONS), 7)
        self.assertIn("ceo", ROLES_BY_ID)
        self.assertIn("cto", ROLES_BY_ID)
        self.assertIn("frontend", ROLES_BY_ID)
        self.assertIn("backend", ROLES_BY_ID)
        self.assertIn("qa", ROLES_BY_ID)

        spec = get_role_spec("backend")
        self.assertEqual(spec["name"], "Backend Specialist")
        self.assertTrue(spec["can_execute_code"])

        ceo_spec = get_role_spec("ceo")
        self.assertFalse(ceo_spec["can_execute_code"])

    def test_role_matching(self):
        role_fe = match_role_for_task(title="Create React Navbar", description="Use tailwind and components")
        self.assertEqual(role_fe, "frontend")

        role_be = match_role_for_task(title="Setup Convex schema", description="Define database tables and api mutations")
        self.assertEqual(role_be, "backend")

        role_qa = match_role_for_task(title="Run test suite", description="Vitest coverage and acceptance criteria")
        self.assertEqual(role_qa, "qa")

    def test_board_directive_decomposition(self):
        directive, tasks = self.orchestrator.receive_board_directive(
            directive_text="Create a real-time messaging dashboard with Convex database backend, Clerk auth, and Tailwind React frontend UI. Also run Vitest tests.",
            workspace_id="chat-project"
        )
        self.assertEqual(directive["status"], "triaged")
        self.assertGreaterEqual(len(tasks), 3)

        roles = [t.role for t in tasks]
        self.assertIn("backend", roles)
        self.assertIn("frontend", roles)
        self.assertIn("qa", roles)

        # Verify dependencies
        qa_task = next(t for t in tasks if t.role == "qa")
        self.assertGreater(len(qa_task.blocked_by), 0)

    def test_heartbeat_dispatch_and_cascade(self):
        directive, tasks = self.orchestrator.receive_board_directive(
            directive_text="Build api endpoints and design page layout, then run tests"
        )
        
        # 1st pulse: Should dispatch ready tasks (backend/frontend)
        res1 = self.supervisor.pulse()
        self.assertGreater(len(self.dispatched_tasks), 0)

        # Upstream tasks are now in_progress
        backend_task = next((t for t in tasks if t.role == "backend"), None)
        qa_task = next((t for t in tasks if t.role == "qa"), None)

        if backend_task:
            self.assertEqual(backend_task.status, "in_progress")

        # Mark non-QA tasks as done to unblock QA
        for t in tasks:
            if t.role != "qa":
                self.orchestrator.update_task_status(t.id, "done")

        if qa_task:
            self.assertEqual(qa_task.status, "todo")

        # 2nd pulse: Should dispatch QA now that blockers are done
        dispatched_count_before = len(self.dispatched_tasks)
        self.supervisor.pulse()
        if qa_task:
            self.assertEqual(qa_task.status, "in_progress")
            self.assertGreater(len(self.dispatched_tasks), dispatched_count_before)

    def test_charter_prompts_exist(self):
        prompts_dir = os.path.join(os.path.dirname(__file__), "prompts")
        for filename in ["AGENTS.md", "SOUL.md", "HEARTBEAT.md"]:
            fp = os.path.join(prompts_dir, filename)
            self.assertTrue(os.path.exists(fp), f"Missing prompt file: {filename}")
            with open(fp, "r", encoding="utf-8") as f:
                content = f.read()
                self.assertGreater(len(content), 100)

if __name__ == "__main__":
    unittest.main()
