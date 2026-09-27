"""
Paperclip Python Client Library for Antigravity Agents
Allows programmatic agent-to-agent and agent-to-CEO communication,
inbox querying, task progress reporting, and subtask delegation.
"""

import os
import json
import urllib.request
import urllib.error

BRIDGE_URL = os.environ.get("AGENT_BRIDGE_URL", "http://127.0.0.1:8000")

def _request(path, method="GET", payload=None, timeout=8):
    url = f"{BRIDGE_URL.rstrip('/')}/{path.lstrip('/')}"
    try:
        data_bytes = json.dumps(payload).encode("utf-8") if payload is not None else None
        headers = {"Content-Type": "application/json"} if payload is not None else {}
        req = urllib.request.Request(url, data=data_bytes, headers=headers, method=method)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            content = resp.read().decode("utf-8")
            return resp.status, json.loads(content) if content else {}
    except urllib.error.HTTPError as he:
        body = he.read().decode("utf-8") if he.fp else ""
        try:
            return he.code, json.loads(body)
        except Exception:
            return he.code, {"error": body or str(he)}
    except Exception as e:
        return 500, {"error": f"Connection error: {e}"}

def whoami():
    """Returns local agent ID, status, engine type, and assigned cluster role."""
    code, status = _request("/status")
    code2, fleet = _request("/fleet")
    agent_id = status.get("agent_id", os.uname().nodename)
    role = "Specialist"
    ip = "127.0.0.1"
    if isinstance(fleet, dict) and "agents" in fleet:
        for a in fleet["agents"]:
            if a.get("id") == agent_id:
                role = a.get("role", role)
                ip = a.get("ip", ip)
                break
    return {
        "agent_id": agent_id,
        "engine_type": status.get("engine_type", "antigravity"),
        "role": role,
        "ip": ip,
        "status": status.get("status", "idle")
    }

def get_fleet():
    """Discovers all online agents, roles, IP addresses, and busy states."""
    code, data = _request("/fleet")
    if code == 200:
        return data.get("agents", [])
    return []

def get_inbox(unread_only=False, mark_read=False, limit=50):
    """Retrieves messages received by this agent from peers or the CEO."""
    params = []
    if unread_only:
        params.append("unread_only=true")
    if mark_read:
        params.append("mark_read=true")
    if limit:
        params.append(f"limit={limit}")
    query = "?" + "&".join(params) if params else ""
    code, data = _request(f"/inbox{query}")
    if code == 200:
        return data.get("messages", [])
    return []

def send_message(recipient, content, message_type="direct", order_id=None, urgent=False, metadata=None):
    """
    Sends a message to another agent (e.g. 'agent-2'), a role (e.g. 'secops'),
    the CEO ('ceo'), or all agents ('broadcast').
    """
    payload = {
        "recipient": recipient,
        "content": content,
        "type": message_type,
        "order_id": order_id,
        "urgent": urgent,
        "metadata": metadata or {}
    }
    code, data = _request("/communicate", method="POST", payload=payload)
    return code in [200, 201], data

def get_tasks(status=None):
    """Returns work orders currently assigned to this agent."""
    path = "/tasks" + (f"?status={status}" if status else "")
    code, data = _request(path)
    if code == 200:
        return data.get("tasks", [])
    return []

def report_task(order_id, status, note="", files_modified=None, acceptance_checks=None):
    """
    Reports progress on an assigned work order.
    status: 'in_progress' | 'done' | 'blocked' | 'in_review'
    """
    payload = {
        "order_id": order_id,
        "status": status,
        "note": note,
        "files_modified": files_modified or [],
        "acceptance_checks": acceptance_checks or []
    }
    code, data = _request("/task/report", method="POST", payload=payload)
    return code in [200, 201] and data.get("success", False), data

def delegate_subtask(order_id, to_role, title, instructions, acceptance_criteria=None, workspace_id=None):
    """
    Delegates a specialized subtask to another fleet role (e.g. 'qa', 'secops', 'backend').
    Registers a parent-child work order relationship in Paperclip CEO.
    """
    payload = {
        "order_id": order_id,
        "to_role": to_role,
        "title": title,
        "instructions": instructions,
        "acceptance_criteria": acceptance_criteria or [],
        "workspace_id": workspace_id
    }
    code, data = _request("/task/subtask", method="POST", payload=payload)
    return code in [200, 201] and data.get("success", False), data
