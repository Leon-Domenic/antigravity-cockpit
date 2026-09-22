"""CEO Orchestration & Subagent Management Engine for Antigravity Cockpit."""

from .roles import ROLE_DEFINITIONS, get_role_spec, match_role_for_task, ROLES_BY_ID, get_chain_of_command
from .orchestrator import CeoOrchestrator, WorkOrder
from .heartbeat import CeoHeartbeatSupervisor

__all__ = [
    "ROLE_DEFINITIONS",
    "get_role_spec",
    "match_role_for_task",
    "ROLES_BY_ID",
    "get_chain_of_command",
    "CeoOrchestrator",
    "WorkOrder",
    "CeoHeartbeatSupervisor",
]
