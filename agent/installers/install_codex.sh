#!/bin/bash
# ==============================================================================
# Codex Agent - Code Synthesis & Refactor Node Installer
# Optimized for: Proxmox LXC Containers or KVM VMs
# Hardware Recommended: 2-4 vCPUs, 4-8 GB RAM, 30 GB SSD
# ==============================================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/common.sh"

COCKPIT_HOST="${COCKPIT_HOST:-192.168.178.168:3000}"

echo "===================================================================="
echo ">>> Installing Codex Agent (Code Synthesis & Refactor Node)..."
echo "===================================================================="

# Persist engine marker
mkdir -p /etc/antigravity
echo "codex" > /etc/antigravity/agent_type

# 1. Pre-flight checks: 4096 MB min, 2 cores, LXC/VM OK
check_system_resources 4096 2 "Codex Agent" "lxc"

# 2. Core Dependencies
install_core_dependencies

# 3. Development Tools, Compilers, and Git Tooling
echo ">>> Installing compilers and developer toolchain..."
apt-get install -y -qq build-essential git jq ripgrep curl wget >/dev/null 2>&1

# 4. Install Node.js & Package Managers (pnpm, yarn)
echo ">>> Installing Node.js 20 LTS and package managers..."
if ! command -v node &>/dev/null; then
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - >/dev/null 2>&1
    apt-get install -y -qq nodejs >/dev/null 2>&1
fi
npm install -g pnpm yarn tsx typescript >/dev/null 2>&1 || true

# 5. Install Python Code Analysis & Synthesis Tools
echo ">>> Installing code analysis, formatting, and AST tools..."
pip3 install --break-system-packages \
    openai \
    litellm \
    black \
    flake8 \
    astor \
    tree-sitter \
    pydantic \
    requests >/dev/null 2>&1 || pip3 install openai black flake8 astor

# 6. Deploy Agent Bridge & Skills Library
deploy_agent_bridge "${COCKPIT_HOST}"
install_skills_library "${COCKPIT_HOST}"

echo "===================================================================="
echo ">>> Codex Agent Node Installed Successfully!"
echo ">>> Engine Type: codex (Code Synthesis & Refactor)"
echo ">>> Agent API Bridge: http://$(hostname -I | awk '{print $1}'):8000/status"
echo "===================================================================="
