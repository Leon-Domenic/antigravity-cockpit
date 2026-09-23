#!/bin/bash
# ==============================================================================
# CEO Executive Orchestrator Node Installer
# Optimized for: Proxmox LXC Containers or Standalone Nodes
# Hardware Recommended: 2 vCPUs, 2-4 GB RAM, 15 GB SSD
# ==============================================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/common.sh"

COCKPIT_HOST="${COCKPIT_HOST:-192.168.178.168:3000}"
COCKPIT_HOST="${COCKPIT_HOST#http://}"
COCKPIT_HOST="${COCKPIT_HOST#https://}"
COCKPIT_HOST="${COCKPIT_HOST%/}"

echo "===================================================================="
echo ">>> Installing CEO Executive Orchestrator Node..."
echo "===================================================================="

# Persist engine marker
mkdir -p /etc/antigravity
echo "ceo" > /etc/antigravity/agent_type

# 1. Pre-flight checks: 2048 MB min, 2 cores, LXC OK
check_system_resources 2048 2 "CEO Executive Node" "lxc"

# 2. Core Dependencies
install_core_dependencies

# 3. Download & Install Paperclip CEO Operating Prompts
echo ">>> Installing Paperclip CEO prompts (AGENTS.md, SOUL.md, HEARTBEAT.md)..."
mkdir -p /etc/antigravity/ceo
for doc in "AGENTS.md" "SOUL.md" "HEARTBEAT.md"; do
    wget -q -O "/etc/antigravity/ceo/${doc}" "http://${COCKPIT_HOST}/api/ceo/prompts/${doc}" || true
done

# 4. Deploy Web Console on port 6080 (CEO Theme)
setup_novnc_terminal "CEO EXECUTIVE NODE - Fleet Leader & Autonomous Orchestrator" "Paperclip Protocol • Charter: AGENTS.md / SOUL.md / HEARTBEAT.md" "cat /etc/antigravity/ceo/SOUL.md 2>/dev/null; exec bash"

# 5. Deploy Agent Bridge & Skills Library
deploy_agent_bridge "${COCKPIT_HOST}"
install_skills_library "${COCKPIT_HOST}"

echo "===================================================================="
echo ">>> CEO Executive Orchestrator Node Installed Successfully!"
echo ">>> Engine Type: ceo (Fleet Leader & Directive Orchestrator)"
echo ">>> noVNC Live Console: http://$(hostname -I | awk '{print $1}'):6080"
echo ">>> Agent API Bridge:   http://$(hostname -I | awk '{print $1}'):8000/status"
echo "===================================================================="
