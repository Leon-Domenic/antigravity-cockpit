"""
CEO Orchestration & Work Order Decomposition Engine for Antigravity Cockpit.
Implements Paperclip-style hierarchical task delegation, dependency resolution, and subagent management.
"""

import os
import sys
import json
import time
import uuid
import re
try:
    import requests
except ImportError:
    requests = None
from .roles import ROLE_DEFINITIONS, ROLES_BY_ID, get_role_spec, match_role_for_task

STATE_FILE = "/usr/local/share/cockpit/ceo_state.json"
LOCAL_STATE_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ceo_state.json")

_task_seq = 100

def generate_id(prefix="WO"):
    global _task_seq
    _task_seq += 1
    return f"{prefix}-{int(time.time()) % 10000:04d}-{_task_seq:03d}"

def resolve_state_file():
    if os.path.exists("/usr/local/share/cockpit"):
        return STATE_FILE
    return LOCAL_STATE_FILE

class WorkOrder:
    """Represents a discrete delegated unit of work assigned to a subagent."""
    def __init__(self, task_id, title, role, goal="", parent_id=None,
                 assigned_agent_id=None, priority="medium", instructions="",
                 acceptance_criteria=None, blocked_by=None, workspace_id=None):
        self.id = task_id or generate_id("WO")
        self.parent_id = parent_id
        self.title = title
        self.goal = goal or title
        self.role = role
        self.assigned_agent_id = assigned_agent_id
        self.priority = priority  # urgent, high, medium, low
        self.instructions = instructions
        self.acceptance_criteria = acceptance_criteria or []
        self.blocked_by = blocked_by or []
        self.workspace_id = workspace_id
        self.status = "todo"  # todo, in_progress, in_review, blocked, done, cancelled
        self.created_at = time.time()
        self.updated_at = time.time()
        self.completed_at = None
        self.execution_notes = []

    def to_dict(self):
        return {
            "id": self.id,
            "parent_id": self.parent_id,
            "title": self.title,
            "goal": self.goal,
            "role": self.role,
            "assigned_agent_id": self.assigned_agent_id,
            "priority": self.priority,
            "instructions": self.instructions,
            "acceptance_criteria": self.acceptance_criteria,
            "blocked_by": self.blocked_by,
            "workspace_id": self.workspace_id,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "completed_at": self.completed_at,
            "execution_notes": self.execution_notes
        }

    @classmethod
    def from_dict(cls, data):
        wo = cls(
            task_id=data.get("id"),
            title=data.get("title", "Untitled Task"),
            role=data.get("role", "frontend"),
            goal=data.get("goal", ""),
            parent_id=data.get("parent_id"),
            assigned_agent_id=data.get("assigned_agent_id"),
            priority=data.get("priority", "medium"),
            instructions=data.get("instructions", ""),
            acceptance_criteria=data.get("acceptance_criteria", []),
            blocked_by=data.get("blocked_by", []),
            workspace_id=data.get("workspace_id")
        )
        wo.status = data.get("status", "todo")
        wo.created_at = data.get("created_at", time.time())
        wo.updated_at = data.get("updated_at", time.time())
        wo.completed_at = data.get("completed_at")
        wo.execution_notes = data.get("execution_notes", [])
        return wo


class CeoOrchestrator:
    """
    CEO Orchestrator maintains company goals, decomposes Board directives,
    assigns work orders to direct reports based on their roles, and supervises progress.
    """
    def __init__(self, get_agents_fn=None, dispatch_fn=None):
        self.get_agents_fn = get_agents_fn or (lambda: [])
        self.dispatch_fn = dispatch_fn
        self.state_file = resolve_state_file()
        self.board_directives = []
        self.work_orders = {}
        self.audit_log = []
        self.executive_summary = "CEO Orchestrator initialized. Standing by for Board Directives."
        self.load_state()

    def log_event(self, event_type, message, details=None):
        entry = {
            "timestamp": time.time(),
            "time_iso": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
            "type": event_type,
            "message": message,
            "details": details or {}
        }
        self.audit_log.append(entry)
        if len(self.audit_log) > 250:
            self.audit_log = self.audit_log[-250:]
        self.save_state()

    def save_state(self):
        try:
            os.makedirs(os.path.dirname(self.state_file), exist_ok=True)
            data = {
                "executive_summary": self.executive_summary,
                "board_directives": self.board_directives,
                "work_orders": {k: v.to_dict() for k, v in self.work_orders.items()},
                "audit_log": self.audit_log[-150:],
                "updated_at": time.time()
            }
            with open(self.state_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"[CEO Orchestrator] Warning: Failed to save state: {e}")

    def load_state(self):
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.executive_summary = data.get("executive_summary", self.executive_summary)
                    self.board_directives = data.get("board_directives", [])
                    raw_wo = data.get("work_orders", {})
                    self.work_orders = {k: WorkOrder.from_dict(v) for k, v in raw_wo.items()}
                    self.audit_log = data.get("audit_log", [])
            except Exception as e:
                print(f"[CEO Orchestrator] Warning: Failed to load state: {e}")

    def get_agent_for_role(self, role_id):
        """Find the best available running agent matching a required role."""
        agents = self.get_agents_fn()
        # 1. Exact role match
        for a in agents:
            r = a.get("role", "").lower()
            if role_id.lower() in r or r in role_id.lower():
                return a["id"]
        
        # 2. Engine match
        role_spec = get_role_spec(role_id)
        default_engine = role_spec.get("default_engine", "antigravity")
        for a in agents:
            if a.get("type") == default_engine:
                return a["id"]
                
        # 3. Fallback to any non-CEO agent
        non_ceo = [a for a in agents if "ceo" not in a.get("role", "").lower()]
        if non_ceo:
            return non_ceo[0]["id"]
            
        return agents[0]["id"] if agents else "agent-1"

    def receive_board_directive(self, directive_text, workspace_id=None, priority="high"):
        """
        Receives a high-level instruction from the human Board (user),
        logs it, and triggers smart goal decomposition into specialized work orders.
        """
        directive_id = generate_id("DIR")
        directive_entry = {
            "id": directive_id,
            "text": directive_text,
            "workspace_id": workspace_id,
            "priority": priority,
            "timestamp": time.time(),
            "status": "triaged",
            "decomposed_tasks": []
        }
        self.board_directives.append(directive_entry)
        self.log_event("board_directive", f"Received Board Directive {directive_id}: {directive_text[:80]}...", {"directive_id": directive_id})
        
        # Decompose into atomic work orders
        created_orders = self.decompose_directive(directive_entry)
        directive_entry["decomposed_tasks"] = [wo.id for wo in created_orders]
        self.save_state()
        
        return directive_entry, created_orders

    def decompose_directive(self, directive):
        """
        Analyzes a high-level directive and decomposes it into role-based Work Orders
        with explicit dependencies, acceptance criteria, and assigned subagents.
        """
        text = directive["text"]
        text_lower = text.lower()
        ws_id = directive.get("workspace_id")
        created_orders = []
        
        # Detect sub-components required
        needs_backend = any(k in text_lower for k in [
            "backend", "api", "database", "convex", "postgres", "auth", "endpoint",
            "model", "schema", "crud", "server", "clerk", "jwt", "route"
        ])
        needs_frontend = any(k in text_lower for k in [
            "frontend", "ui", "ux", "page", "react", "next", "component", "tailwind",
            "css", "view", "theme", "modal", "button", "landing", "style"
        ])
        needs_qa = any(k in text_lower for k in [
            "test", "qa", "verify", "vitest", "playwright", "coverage", "validate", "check"
        ])
        needs_research = any(k in text_lower for k in [
            "scrape", "research", "crawl", "docs", "external", "investigate api", "claw"
        ])
        needs_refactor = any(k in text_lower for k in [
            "refactor", "optimize", "rewrite", "performance", "types", "algorithm", "codex"
        ])

        # If user gave a simple single-domain prompt without explicit multi-tier keywords
        if not (needs_backend or needs_frontend or needs_qa or needs_research or needs_refactor):
            target_role = match_role_for_task(title=text, description=text)
            assigned_agent = self.get_agent_for_role(target_role)
            wo = WorkOrder(
                task_id=generate_id("WO"),
                title=f"Execute: {text[:60]}",
                role=target_role,
                goal=text,
                parent_id=directive["id"],
                assigned_agent_id=assigned_agent,
                priority=directive.get("priority", "medium"),
                instructions=text,
                acceptance_criteria=[
                    "Implement the requested functionality cleanly in the workspace",
                    "Verify implementation contains no syntax or runtime errors",
                    "Report all modified files and results to the CEO"
                ],
                blocked_by=[],
                workspace_id=ws_id
            )
            self.work_orders[wo.id] = wo
            created_orders.append(wo)
            self.log_event("task_created", f"Created Work Order {wo.id} [{target_role}] -> {assigned_agent}", {"order_id": wo.id})
            return created_orders

        backend_order = None
        frontend_order = None
        research_order = None

        # 1. Research / Intelligence Order (if needed)
        if needs_research:
            r_agent = self.get_agent_for_role("openclaw")
            research_order = WorkOrder(
                task_id=generate_id("WO"),
                title=f"Research & Documentation Extraction: {text[:50]}",
                role="openclaw",
                goal="Gather required documentation, external API specifications, or intelligence",
                parent_id=directive["id"],
                assigned_agent_id=r_agent,
                priority="high",
                instructions=f"Analyze documentation and gather required technical references for: {text}",
                acceptance_criteria=[
                    "Extract relevant API schemas and code snippets",
                    "Document required endpoints, payload shapes, or data models"
                ],
                blocked_by=[],
                workspace_id=ws_id
            )
            self.work_orders[research_order.id] = research_order
            created_orders.append(research_order)

        # 2. Backend / System Architecture Order
        if needs_backend:
            b_agent = self.get_agent_for_role("backend")
            blocked_by = [research_order.id] if research_order else []
            backend_order = WorkOrder(
                task_id=generate_id("WO"),
                title=f"Backend Services & Data Architecture: {text[:50]}",
                role="backend",
                goal="Implement database models, API routes, authentication, and core server logic",
                parent_id=directive["id"],
                assigned_agent_id=b_agent,
                priority="high",
                instructions=(
                    f"Implement the backend components required for the directive: {text}\n"
                    f"Define clean database schemas, secure API endpoints/functions, and strict validation."
                ),
                acceptance_criteria=[
                    "Database schema and models are properly defined",
                    "API routes/mutations/queries handle valid and invalid inputs gracefully",
                    "Security rules, authentication, and error handling are verified"
                ],
                blocked_by=blocked_by,
                workspace_id=ws_id
            )
            self.work_orders[backend_order.id] = backend_order
            created_orders.append(backend_order)

        # 3. Frontend / UI Implementation Order
        if needs_frontend:
            f_agent = self.get_agent_for_role("frontend")
            # If both backend and frontend are being created, frontend can either run in parallel or reference backend
            blocked_by = [backend_order.id] if (backend_order and "api" in text_lower) else []
            frontend_order = WorkOrder(
                task_id=generate_id("WO"),
                title=f"UI Components & Frontend Flow: {text[:50]}",
                role="frontend",
                goal="Build responsive, interactive user interface and client integration",
                parent_id=directive["id"],
                assigned_agent_id=f_agent,
                priority="high",
                instructions=(
                    f"Build the user interface and frontend components for: {text}\n"
                    f"Use Tailwind CSS, responsive layouts, clear state management, and seamless UX."
                ),
                acceptance_criteria=[
                    "All visual components and interactive controls are rendered correctly",
                    "Responsive styling across mobile and desktop viewports",
                    "Proper client-side error states and loading spinners included"
                ],
                blocked_by=blocked_by,
                workspace_id=ws_id
            )
            self.work_orders[frontend_order.id] = frontend_order
            created_orders.append(frontend_order)

        # 4. Heavy Code Synthesis / Refactoring (if needed)
        if needs_refactor:
            c_agent = self.get_agent_for_role("codex")
            codex_order = WorkOrder(
                task_id=generate_id("WO"),
                title=f"Code Synthesis & Optimization: {text[:50]}",
                role="codex",
                goal="High-throughput code refactoring, algorithmic implementation, or performance tuning",
                parent_id=directive["id"],
                assigned_agent_id=c_agent,
                priority="medium",
                instructions=f"Refactor and optimize code implementation for: {text}",
                acceptance_criteria=[
                    "Clean code structure conforming to project conventions",
                    "Performance optimization and type safety verified"
                ],
                blocked_by=[],
                workspace_id=ws_id
            )
            self.work_orders[codex_order.id] = codex_order
            created_orders.append(codex_order)

        # 5. QA & Verification Order
        if needs_qa or (backend_order and frontend_order):
            qa_agent = self.get_agent_for_role("qa")
            upstream = [o.id for o in created_orders]
            qa_order = WorkOrder(
                task_id=generate_id("WO"),
                title=f"QA Verification & Acceptance Testing: {text[:50]}",
                role="qa",
                goal="Validate entire deliverable against acceptance criteria with automated tests",
                parent_id=directive["id"],
                assigned_agent_id=qa_agent,
                priority="medium",
                instructions=(
                    f"Perform end-to-end verification for the completed feature: {text}\n"
                    f"Write or execute tests, verify that all acceptance criteria are satisfied, and check for edge case errors."
                ),
                acceptance_criteria=[
                    "Run test suite or validation script; ensure 0 regressions",
                    "Verify acceptance criteria for each upstream component",
                    "Provide a clean sign-off report for the CEO"
                ],
                blocked_by=upstream,
                workspace_id=ws_id
            )
            self.work_orders[qa_order.id] = qa_order
            created_orders.append(qa_order)

        for wo in created_orders:
            self.log_event("task_created", f"Created Work Order {wo.id} [{wo.role}] -> {wo.assigned_agent_id}", {"order_id": wo.id})

        return created_orders

    def dispatch_work_order(self, order_id):
        """
        Dispatches an active work order to the assigned subagent via the agent bridge.
        Formats a Paperclip-style formal work briefing.
        """
        wo = self.work_orders.get(order_id)
        if not wo:
            return False, "Work order not found"

        # Check dependencies
        for blocker_id in wo.blocked_by:
            b = self.work_orders.get(blocker_id)
            if b and b.status != "done":
                wo.status = "blocked"
                self.save_state()
                return False, f"Blocked by dependency {blocker_id} (status: {b.status})"

        target_agent = wo.assigned_agent_id or self.get_agent_for_role(wo.role)
        role_spec = get_role_spec(wo.role)
        
        # Build Paperclip-style formal prompt packet
        briefing = (
            f"====================================================\n"
            f"[OFFICIAL WORK ORDER]: {wo.id}\n"
            f"TITLE: {wo.title}\n"
            f"ROLE: {role_spec['name']} ({role_spec['title']})\n"
            f"PRIORITY: {wo.priority.upper()}\n"
            f"====================================================\n\n"
            f"EXECUTIVE OBJECTIVE:\n{wo.instructions}\n\n"
            f"ACCEPTANCE CRITERIA:\n" +
            "\n".join([f"  [ ] {crit}" for crit in wo.acceptance_criteria]) +
            f"\n\nREPORTING REQUIREMENT:\n"
            f"Execute this task in the workspace. When complete, provide a concise summary of changes, "
            f"files modified, and verification results for the CEO review checklist.\n"
        )

        if self.dispatch_fn:
            try:
                res = self.dispatch_fn(target=target_agent, prompt=briefing, workspace_id=wo.workspace_id)
                wo.status = "in_progress"
                wo.updated_at = time.time()
                wo.execution_notes.append({
                    "time": time.time(),
                    "note": f"Dispatched to {target_agent} by CEO Orchestrator"
                })
                self.log_event("task_dispatched", f"Dispatched {wo.id} to {target_agent}", {"order_id": wo.id, "target": target_agent})
                self.save_state()
                return True, res
            except Exception as e:
                wo.status = "blocked"
                self.log_event("dispatch_error", f"Failed dispatching {wo.id} to {target_agent}: {e}", {"order_id": wo.id})
                self.save_state()
                return False, str(e)
                
        wo.status = "in_progress"
        self.save_state()
        return True, "Dispatched (dry-run)"

    def update_task_status(self, order_id, new_status, note=None):
        """Update task status with validation and dependency cascading."""
        wo = self.work_orders.get(order_id)
        if not wo:
            return False, "Work order not found"

        old_status = wo.status
        wo.status = new_status
        wo.updated_at = time.time()
        if new_status == "done":
            wo.completed_at = time.time()
            
        if note:
            wo.execution_notes.append({
                "time": time.time(),
                "note": note
            })
            
        self.log_event("task_status_change", f"Task {wo.id} transitioned from {old_status} -> {new_status}", {
            "order_id": wo.id,
            "old_status": old_status,
            "new_status": new_status,
            "note": note
        })

        # If completed, check downstream blocked tasks
        if new_status == "done":
            for other_id, other_wo in self.work_orders.items():
                if other_wo.status == "blocked" and order_id in other_wo.blocked_by:
                    all_resolved = all(
                        self.work_orders.get(dep) and self.work_orders.get(dep).status == "done"
                        for dep in other_wo.blocked_by
                    )
                    if all_resolved:
                        other_wo.status = "todo"
                        self.log_event("dependency_unblocked", f"Task {other_id} unblocked by completion of {order_id}", {"order_id": other_id})

        self.save_state()
        return True, f"Status updated to {new_status}"

    def get_summary_metrics(self):
        """Calculates executive metrics for the Board overview."""
        total = len(self.work_orders)
        todo = sum(1 for w in self.work_orders.values() if w.status == "todo")
        in_progress = sum(1 for w in self.work_orders.values() if w.status == "in_progress")
        in_review = sum(1 for w in self.work_orders.values() if w.status == "in_review")
        blocked = sum(1 for w in self.work_orders.values() if w.status == "blocked")
        done = sum(1 for w in self.work_orders.values() if w.status == "done")

        return {
            "total_tasks": total,
            "todo": todo,
            "in_progress": in_progress,
            "in_review": in_review,
            "blocked": blocked,
            "done": done,
            "velocity_pct": round((done / total * 100) if total > 0 else 100.0, 1),
            "directives_count": len(self.board_directives)
        }
