#!/bin/bash
# ==============================================================================
# Antigravity Agent - Electron GUI Desktop Node Installer
# Optimized for: Proxmox LXC Containers or KVM VMs
# Hardware Recommended: 2-4 vCPUs, 4-8 GB RAM, 20 GB SSD
# ==============================================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/common.sh"

COCKPIT_HOST="${COCKPIT_HOST:-192.168.178.168:3000}"
INSTALL_DIR="/home/ubuntu/opt"
AGENT_DIR="${INSTALL_DIR}/Antigravity-x64"

echo "===================================================================="
echo ">>> Installing Antigravity Agent (Google AGY Desktop & IDE)..."
echo "===================================================================="

# Persist engine marker
mkdir -p /etc/antigravity
echo "antigravity" > /etc/antigravity/agent_type

# 1. Pre-flight checks: 4096 MB min, 2 cores, LXC/VM OK
check_system_resources 4096 2 "Antigravity Agent" "lxc"

# 2. Core Dependencies
install_core_dependencies

# 3. Desktop, X11 Display, Font, and Audio Libraries
echo ">>> Installing X11 desktop environment and window manager..."
apt-get install -y -qq \
    xvfb \
    openbox \
    x11vnc \
    novnc \
    websockify \
    scrot \
    xdg-utils \
    libnss3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2t64 \
    fonts-liberation \
    xdotool >/dev/null 2>&1 || apt-get install -y -qq libasound2 || true

# 4. Install Google Chrome (Official Debian Package)
echo ">>> Installing Google Chrome..."
if ! command -v google-chrome &>/dev/null; then
    wget -q -O /tmp/google-chrome-stable_current_amd64.deb https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
    dpkg -i /tmp/google-chrome-stable_current_amd64.deb >/dev/null 2>&1 || apt-get install -fy -qq >/dev/null 2>&1
    rm -f /tmp/google-chrome-stable_current_amd64.deb
fi

# Apply Chrome Sandbox & AppArmor fixes
if [ -f "/opt/google/chrome/google-chrome" ]; then
    sed -i 's|exec -a "$0" "$HERE/chrome" "$@"|exec -a "$0" "$HERE/chrome" --no-sandbox "$@"|g' /opt/google/chrome/google-chrome || true
fi

if command -v apparmor_parser &>/dev/null; then
    apparmor_parser -R /etc/apparmor.d/chrome 2>/dev/null || true
fi
rm -f /etc/apparmor.d/chrome
mkdir -p /etc/apparmor.d/disable
touch /etc/apparmor.d/disable/chrome

# 5. Deploy Antigravity Binary
echo ">>> Deploying Antigravity IDE application binary..."
mkdir -p "${INSTALL_DIR}"
if [ ! -f "${AGENT_DIR}/antigravity" ]; then
    echo "    Downloading Antigravity bundle from Cockpit..."
    wget -q --show-progress -O /tmp/antigravity-app.tar.gz "http://${COCKPIT_HOST}/packages/antigravity-app.tar.gz" || true
    if [ -f /tmp/antigravity-app.tar.gz ]; then
        tar -xzf /tmp/antigravity-app.tar.gz -C "${INSTALL_DIR}/" || true
        rm -f /tmp/antigravity-app.tar.gz
    fi
fi

if [ -f "${AGENT_DIR}/antigravity" ]; then
    chmod +x "${AGENT_DIR}/antigravity"
    ln -sf "${AGENT_DIR}/antigravity" /usr/local/bin/antigravity
fi

# 6. Configure Openbox Single-Desktop Mode
cat << 'EOF' > /etc/xdg/openbox/rc.xml
<?xml version="1.0" encoding="UTF-8"?>
<openbox_config xmlns="http://openbox.org/3.4/rc">
  <desktops><number>1</number><firstdesk>1</firstdesk><names><name>Antigravity</name></names></desktops>
</openbox_config>
EOF
mkdir -p /root/.config/openbox /home/ubuntu/.config/openbox
cp /etc/xdg/openbox/rc.xml /root/.config/openbox/rc.xml
cp /etc/xdg/openbox/rc.xml /home/ubuntu/.config/openbox/rc.xml 2>/dev/null || true

# 7. Configure Virtual Web Desktop (1920x1080) & noVNC
cat << 'EOF' > /usr/local/bin/start-webdesktop.sh
#!/bin/bash
export DISPLAY=:1
rm -f /tmp/.X1-lock /tmp/.X11-unix/X1

Xvfb :1 -screen 0 1920x1080x24 &
sleep 1

openbox-session &
sleep 1

x11vnc -display :1 -nopw -listen 0.0.0.0 -xkb -forever -shared &
sleep 1

websockify --web=/usr/share/novnc 6080 localhost:5900 &
sleep 1

if [ -f "/usr/local/bin/antigravity" ]; then
    /usr/local/bin/antigravity --no-sandbox &
fi

wait
EOF
chmod +x /usr/local/bin/start-webdesktop.sh

cat << 'EOF' > /etc/systemd/system/webdesktop.service
[Unit]
Description=Antigravity Web Desktop VNC Service
After=network.target

[Service]
Type=simple
ExecStart=/usr/local/bin/start-webdesktop.sh
Restart=always
RestartSec=3
KillMode=mixed

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now webdesktop.service
systemctl restart webdesktop.service || true

# 8. Deploy Agent Bridge & Skills Library
deploy_agent_bridge "${COCKPIT_HOST}"
install_skills_library "${COCKPIT_HOST}"

echo "===================================================================="
echo ">>> Antigravity Agent Desktop Installed Successfully!"
echo ">>> Engine Type: antigravity (Google AGY Electron IDE)"
echo ">>> noVNC Live Desktop: http://$(hostname -I | awk '{print $1}'):6080"
echo ">>> Agent API Bridge:   http://$(hostname -I | awk '{print $1}'):8000/status"
echo "===================================================================="
