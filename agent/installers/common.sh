#!/bin/bash
# ==============================================================================
# Common Helper & Pre-Flight Verification Library for Agent Nodes
# ==============================================================================
set -e

# Detect Virtualization Environment
detect_virt() {
    local virt="unknown"
    if command -v systemd-detect-virt &>/dev/null; then
        virt="$(systemd-detect-virt 2>/dev/null || echo 'unknown')"
    elif [ -f /proc/1/environ ]; then
        if tr '\0' '\n' < /proc/1/environ | grep -q "container=lxc"; then
            virt="lxc"
        fi
    fi

    if [ "$virt" = "unknown" ] || [ "$virt" = "none" ]; then
        if grep -qi "qemu\|kvm" /proc/cpuinfo /sys/class/dmi/id/sys_vendor 2>/dev/null; then
            virt="kvm"
        elif [ -f /.dockerenv ]; then
            virt="docker"
        fi
    fi
    echo "$virt"
}

# Check System Resources
check_system_resources() {
    local req_ram_mb="$1"
    local req_cores="$2"
    local engine_name="$3"
    local req_virt="$4"

    local current_virt="$(detect_virt)"
    local total_ram_mb="$(free -m | awk '/^Mem:/{print $2}')"
    local cpu_cores="$(nproc)"

    echo "--------------------------------------------------------------------"
    echo ">>> System Environment Diagnostics for [${engine_name}]:"
    echo "    - Detected Virtualization : ${current_virt}"
    echo "    - Available Memory (RAM)  : ${total_ram_mb} MB (Recommended: >= ${req_ram_mb} MB)"
    echo "    - CPU Processing Cores    : ${cpu_cores} cores (Recommended: >= ${req_cores} cores)"
    echo "--------------------------------------------------------------------"

    # Virtualization check & recommendation
    if [ "$req_virt" = "kvm" ] && [ "$current_virt" = "lxc" ]; then
        echo ""
        echo "⚠️  [VIRTUALIZATION NOTICE]:"
        echo "    ${engine_name} strongly recommends a dedicated Proxmox KVM Virtual Machine (VM)"
        echo "    rather than an unprivileged LXC container."
        echo "    Reasons: hardware virtualization / GPU passthrough, Docker container nesting,"
        echo "    and Chromium user-namespace sandboxing are restricted or fail in unprivileged LXCs."
        echo "    -> We will apply compatibility workarounds, but a KVM VM is recommended for production."
        echo ""
    fi

    if [ "$total_ram_mb" -lt "$((req_ram_mb * 7 / 10))" ]; then
        echo "⚠️  [RESOURCE WARNING]: Memory is below recommended ${req_ram_mb} MB."
    fi
}

# Install Core System Dependencies
install_core_dependencies() {
    echo ">>> Installing core networking, python, and system tools..."
    export DEBIAN_FRONTEND=noninteractive
    apt-get update -qq
    apt-get install -y -qq \
        curl \
        wget \
        tar \
        gzip \
        unzip \
        git \
        jq \
        ripgrep \
        ca-certificates \
        python3 \
        python3-flask \
        python3-requests \
        python3-pip >/dev/null 2>&1 || apt-get install -y -qq curl wget git python3 python3-pip
}

# Deploy Agent Bridge API (:8000)
deploy_agent_bridge() {
    local raw_host="$1"
    local cockpit_host="${raw_host#http://}"
    cockpit_host="${cockpit_host#https://}"
    cockpit_host="${cockpit_host%/}"

    echo ">>> Deploying Agent Bridge API (:8000)..."
    mkdir -p /usr/local/bin /home/ubuntu/workspace /root/workspace /tmp/agent_media
    chown -R ubuntu:ubuntu /home/ubuntu/workspace 2>/dev/null || true

    wget -q -O /usr/local/bin/agent_bridge.py "http://${cockpit_host}/packages/agent_bridge.py" || true
    chmod +x /usr/local/bin/agent_bridge.py

    cat << 'EOF' > /etc/systemd/system/agent-bridge.service
[Unit]
Description=Antigravity Agent API Bridge
After=network.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 /usr/local/bin/agent_bridge.py
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
    systemctl enable --now agent-bridge.service
    systemctl restart agent-bridge.service || true
}

# Install Cockpit Skills Library
install_skills_library() {
    local raw_host="$1"
    local cockpit_host="${raw_host#http://}"
    cockpit_host="${cockpit_host#https://}"
    cockpit_host="${cockpit_host%/}"

    echo ">>> Pre-loading Cockpit Skills Library..."
    mkdir -p /root/.gemini/skills /root/.gemini/config/skills /home/ubuntu/.gemini/skills
    wget -q -O /tmp/cockpit-skills-library.tar.gz "http://${cockpit_host}/packages/cockpit-skills-library.tar.gz" || true
    if [ -f "/tmp/cockpit-skills-library.tar.gz" ]; then
        tar -xzf /tmp/cockpit-skills-library.tar.gz -C /root/.gemini/skills/ 2>/dev/null || true
        tar -xzf /tmp/cockpit-skills-library.tar.gz -C /root/.gemini/config/skills/ 2>/dev/null || true
        tar -xzf /tmp/cockpit-skills-library.tar.gz -C /home/ubuntu/.gemini/skills/ 2>/dev/null || true
        rm -f /tmp/cockpit-skills-library.tar.gz
    fi
}

# Setup Web Desktop / noVNC Terminal for CLI and Specialized Nodes
setup_novnc_terminal() {
    local node_title="$1"
    local node_subtitle="$2"
    local custom_cmd="$3"

    echo ">>> Setting up Web Desktop & noVNC Terminal on port 6080..."
    export DEBIAN_FRONTEND=noninteractive
    apt-get install -y -qq xvfb openbox x11vnc novnc websockify xterm >/dev/null 2>&1 || true

    mkdir -p /root/.config/openbox /home/ubuntu/.config/openbox /etc/xdg/openbox
    cat << 'EOF_OB' > /etc/xdg/openbox/rc.xml
<?xml version="1.0" encoding="UTF-8"?>
<openbox_config xmlns="http://openbox.org/3.4/rc">
  <desktops><number>1</number><firstdesk>1</firstdesk><names><name>Node Console</name></names></desktops>
  <applications>
    <application class="*">
      <maximized>yes</maximized>
      <decor>no</decor>
    </application>
  </applications>
</openbox_config>
EOF_OB
    cp /etc/xdg/openbox/rc.xml /root/.config/openbox/rc.xml
    cp /etc/xdg/openbox/rc.xml /home/ubuntu/.config/openbox/rc.xml 2>/dev/null || true

    # Create terminal startup banner script
    cat << EOF_BANNER > /usr/local/bin/node-terminal-banner.sh
#!/bin/bash
clear
cat << "BANNER"
╔══════════════════════════════════════════════════════════════════╗
║   ${node_title}
║   ${node_subtitle}
║   Workspace: /home/ubuntu/workspace  •  API Bridge: Port 8000   
╚══════════════════════════════════════════════════════════════════╝
BANNER
echo ""
cd /home/ubuntu/workspace 2>/dev/null || cd /root
${custom_cmd:-exec bash}
EOF_BANNER
    chmod +x /usr/local/bin/node-terminal-banner.sh

    cat << 'EOF_DESK' > /usr/local/bin/start-webdesktop.sh
#!/bin/bash
export DISPLAY=:1
rm -f /tmp/.X1-lock /tmp/.X11-unix/X1

Xvfb :1 -screen 0 1920x1080x24 -listen tcp -ac &
sleep 1

openbox &
sleep 1

x11vnc -display :1 -nopw -listen 0.0.0.0 -xkb -forever -shared &
sleep 1

websockify --web=/usr/share/novnc 6080 localhost:5900 &
sleep 1

mkdir -p /home/ubuntu/workspace
xterm -fa 'Monospace' -fs 14 -bg '#0d1117' -fg '#58a6ff' -geometry 160x50+10+10 -e /usr/local/bin/node-terminal-banner.sh &

wait
EOF_DESK
    chmod +x /usr/local/bin/start-webdesktop.sh

    cat << 'EOF_SERV' > /etc/systemd/system/webdesktop.service
[Unit]
Description=Web Desktop VNC Service
After=network.target

[Service]
Type=simple
ExecStart=/usr/local/bin/start-webdesktop.sh
Restart=always
RestartSec=3
KillMode=mixed

[Install]
WantedBy=multi-user.target
EOF_SERV

    systemctl daemon-reload
    systemctl enable --now webdesktop.service
    systemctl restart webdesktop.service || true
}
