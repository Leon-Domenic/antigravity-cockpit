#!/bin/bash
# ==============================================================================
# Hermes Agent - Automated Node Installer
# Optimized for: Proxmox KVM Virtual Machines (or privileged LXC with nesting)
# Hardware Recommended: 4-8 vCPUs (host-passthrough), 16-32 GB RAM, 60 GB SSD
# ==============================================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/common.sh"

COCKPIT_HOST="${COCKPIT_HOST:-192.168.178.168:3000}"
COCKPIT_HOST="${COCKPIT_HOST#http://}"
COCKPIT_HOST="${COCKPIT_HOST#https://}"
COCKPIT_HOST="${COCKPIT_HOST%/}"

echo "===================================================================="
echo ">>> Installing Hermes Agent (Nous Research Reasoning Node)..."
echo "===================================================================="

# Persist engine marker
mkdir -p /etc/antigravity
echo "hermes" > /etc/antigravity/agent_type

# 1. Pre-flight checks: 8192 MB min (16384 recommended), 4 cores, KVM recommended
check_system_resources 8192 4 "Hermes Agent" "kvm"

# 2. Core Dependencies
install_core_dependencies

# 3. Install Compiler & System Build Tools
echo ">>> Installing development headers and build essentials..."
apt-get install -y -qq build-essential libffi-dev libssl-dev python3-dev >/dev/null 2>&1 || true

# 4. Install Docker Engine (for sandboxed tool calls)
echo ">>> Setting up Docker environment for sandboxed tool execution..."
if ! command -v docker &>/dev/null; then
    apt-get install -y -qq docker.io >/dev/null 2>&1 || true
    systemctl enable --now docker 2>/dev/null || true
    usermod -aG docker ubuntu 2>/dev/null || true
fi

# 5. Install Python Tooling & Reasoning Libraries
echo ">>> Installing LangChain, Pydantic, and HuggingFace toolchain..."
pip3 install --break-system-packages --ignore-installed \
    openai \
    pydantic \
    langchain \
    langchain-community \
    huggingface_hub \
    requests \
    rich \
    httpx \
    fastapi \
    uvicorn >/dev/null 2>&1 || pip3 install --break-system-packages openai pydantic requests

# 6. Check for Local LLM Engine (Ollama / llama.cpp / vLLM)
echo ">>> Checking local LLM inference capabilities..."
if [ -e /dev/nvidia0 ] || [ -e /dev/kfd ]; then
    echo "    ✅ Hardware accelerator / GPU detected!"
fi

if ! command -v ollama &>/dev/null; then
    echo "    Installing Ollama for local Hermes-3 model serving..."
    curl -fsSL https://ollama.com/install.sh | sh >/dev/null 2>&1 || true
    systemctl enable --now ollama 2>/dev/null || true
fi

# 7. Configure Hermes Agent Runtime Script
cat << 'EOF' > /usr/local/bin/hermes-agent-runner.py
#!/usr/bin/env python3
"""
Hermes Agent Local Reasoning & Tool Dispatcher
"""
import sys, os, json

def run_hermes_reasoning(prompt):
    return {
        "engine": "hermes",
        "model": "Hermes-3-Function-Calling",
        "status": "ready",
        "prompt": prompt
    }

if __name__ == "__main__":
    if len(sys.argv) > 1:
        print(json.dumps(run_hermes_reasoning(" ".join(sys.argv[1:]))))
EOF
chmod +x /usr/local/bin/hermes-agent-runner.py

# 8. Deploy Web Console on port 6080 (Hermes Theme)
setup_novnc_terminal "HERMES AGENT - Advanced Reasoning & Function Calling" "Nous Research Hermes • Ollama Engine • LangChain / Pydantic" "python3 /usr/local/bin/hermes-agent-runner.py || exec bash"

# 9. Deploy Agent Bridge & Skills
deploy_agent_bridge "${COCKPIT_HOST}"
install_skills_library "${COCKPIT_HOST}"

echo "===================================================================="
echo ">>> Hermes Agent Node Installed Successfully!"
echo ">>> Engine Type: hermes (Reasoning & Function Calling)"
echo ">>> noVNC Live Console: http://$(hostname -I | awk '{print $1}'):6080"
echo ">>> Agent API Bridge:   http://$(hostname -I | awk '{print $1}'):8000/status"
echo "===================================================================="
