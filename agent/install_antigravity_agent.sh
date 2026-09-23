#!/bin/bash
# ==============================================================================
# Multi-Engine Agent Node Automated Installer
# Supports: Ubuntu 22.04 / 24.04, Debian 12 (LXC Containers and KVM VMs)
# Engines: Antigravity, Codex, Hermes Agent, Open Claw, Custom
# ==============================================================================
set -e

COCKPIT_HOST="${COCKPIT_HOST:-192.168.178.168:3000}"
INSTALL_DIR="/home/ubuntu/opt"
AGENT_DIR="${INSTALL_DIR}/Antigravity-x64"

# Parse CLI arguments
ENGINE="antigravity"
while [ $# -gt 0 ]; do
    case "$1" in
        --engine|-e)
            ENGINE="$2"
            shift 2
            ;;
        --engine=*)
            ENGINE="${1#*=}"
            shift
            ;;
        *)
            shift
            ;;
    esac
done

ENGINE_LOWER="$(echo "$ENGINE" | tr '[:upper:]' '[:lower:]')"

echo "===================================================================="
echo ">>> Starting Agent Automated Installation..."
echo ">>> Selected Engine: ${ENGINE_LOWER} (Antigravity, Codex, Hermes, Open Claw, Custom)"
echo ">>> Source Cockpit:  http://${COCKPIT_HOST}"
echo "===================================================================="

# Persist configured engine type
mkdir -p /etc/antigravity
echo "${ENGINE_LOWER}" > /etc/antigravity/agent_type

# 1. Update package lists and install essential system dependencies
echo "[1/8] Installing core desktop, display, and python dependencies..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq \
    curl \
    wget \
    tar \
    gzip \
    unzip \
    git \
    xvfb \
    openbox \
    x11vnc \
    novnc \
    websockify \
    python3 \
    python3-flask \
    python3-requests \
    python3-pip \
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

# 2. Install Google Chrome (Official Debian Package)
echo "[2/8] Installing Google Chrome..."
if ! command -v google-chrome &>/dev/null; then
    wget -q -O /tmp/google-chrome-stable_current_amd64.deb https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
    dpkg -i /tmp/google-chrome-stable_current_amd64.deb >/dev/null 2>&1 || apt-get install -fy -qq >/dev/null 2>&1
    rm -f /tmp/google-chrome-stable_current_amd64.deb
fi

# 3. Apply Chrome Sandbox & AppArmor fixes
echo "[3/8] Applying Chrome container/VM optimizations & AppArmor patch..."
if [ -f "/opt/google/chrome/google-chrome" ]; then
    sed -i 's|exec -a "$0" "$HERE/chrome" "$@"|exec -a "$0" "$HERE/chrome" --no-sandbox "$@"|g' /opt/google/chrome/google-chrome || true
fi

# Disable Ubuntu 24.04 restricted AppArmor profile which causes ERR_INTERNET_DISCONNECTED
if command -v apparmor_parser &>/dev/null; then
    apparmor_parser -R /etc/apparmor.d/chrome 2>/dev/null || true
fi
rm -f /etc/apparmor.d/chrome
mkdir -p /etc/apparmor.d/disable
touch /etc/apparmor.d/disable/chrome

# Configure Chrome as default system browser
xdg-settings set default-web-browser google-chrome.desktop 2>/dev/null || true
xdg-mime default google-chrome.desktop x-scheme-handler/http 2>/dev/null || true
xdg-mime default google-chrome.desktop x-scheme-handler/https 2>/dev/null || true

# 4. Deploy Selected Agent Stack & Binaries
echo "[4/8] Configuring runtime environment for engine '${ENGINE_LOWER}'..."
mkdir -p "${INSTALL_DIR}"
if [ "${ENGINE_LOWER}" = "antigravity" ]; then
    if [ ! -f "${AGENT_DIR}/antigravity" ]; then
        echo "      Downloading Antigravity bundle from Cockpit repository..."
        wget -q --show-progress -O /tmp/antigravity-app.tar.gz "http://${COCKPIT_HOST}/packages/antigravity-app.tar.gz"
        tar -xzf /tmp/antigravity-app.tar.gz -C "${INSTALL_DIR}/"
        rm -f /tmp/antigravity-app.tar.gz
    fi
    chmod +x "${AGENT_DIR}/antigravity"
    ln -sf "${AGENT_DIR}/antigravity" /usr/local/bin/antigravity
elif [ "${ENGINE_LOWER}" = "codex" ]; then
    echo "      Setting up OpenAI Codex environment & coding tools..."
    apt-get install -y -qq git npm nodejs jq >/dev/null 2>&1 || true
    pip3 install --break-system-packages openai litellm astor black flake8 >/dev/null 2>&1 || true
elif [ "${ENGINE_LOWER}" = "hermes" ]; then
    echo "      Setting up Nous Hermes Agent reasoning & tool environment..."
    apt-get install -y -qq git jq >/dev/null 2>&1 || true
    pip3 install --break-system-packages huggingface_hub langchain pydantic requests >/dev/null 2>&1 || true
elif [ "${ENGINE_LOWER}" = "openclaw" ]; then
    echo "      Setting up Open Claw autonomous scraper & browser automation..."
    apt-get install -y -qq git curl jq >/dev/null 2>&1 || true
    pip3 install --break-system-packages playwright beautifulsoup4 scrapy curl_cffi >/dev/null 2>&1 || true
fi

# Ensure workspace directories exist for Antigravity & Agent Workspaces
mkdir -p /home/ubuntu/workspace /root/workspace /tmp/agent_media
chown -R ubuntu:ubuntu /home/ubuntu/workspace 2>/dev/null || true
chmod -R u+rw /home/ubuntu/workspace 2>/dev/null || true

# 5. Lock Openbox to single-desktop mode (eliminates 4-desktop switching bug)
echo "[5/8] Configuring single-desktop Openbox window manager..."
mkdir -p /etc/xdg/openbox
cat << 'EOF' > /etc/xdg/openbox/rc.xml
<?xml version="1.0" encoding="UTF-8"?>
<openbox_config xmlns="http://openbox.org/3.4/rc" xmlns:xi="http://www.w3.org/2001/XInclude">
  <desktops>
    <number>1</number>
    <firstdesk>1</firstdesk>
    <names>
      <name>Desktop 1</name>
    </names>
    <popupTime>0</popupTime>
  </desktops>
  <mouse>
    <context name="Root">
      <mousebind button="Right" action="Press">
        <action name="ShowMenu"><menu>root-menu</menu></action>
      </mousebind>
    </context>
  </mouse>
  <keyboard>
    <keybind key="C-A-Left"><action name="GoToDesktop"><to>current</to></action></keybind>
    <keybind key="C-A-Right"><action name="GoToDesktop"><to>current</to></action></keybind>
    <keybind key="W-Left"><action name="GoToDesktop"><to>current</to></action></keybind>
    <keybind key="W-Right"><action name="GoToDesktop"><to>current</to></action></keybind>
  </keyboard>
</openbox_config>
EOF

mkdir -p /root/.config/openbox /home/ubuntu/.config/openbox
cp /etc/xdg/openbox/rc.xml /root/.config/openbox/rc.xml
cp /etc/xdg/openbox/rc.xml /home/ubuntu/.config/openbox/rc.xml

# 6. Configure noVNC and X11 Startup
echo "[6/8] Configuring 16:9 X11 display (1920x1080) and noVNC service..."
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
    /usr/local/bin/antigravity --no-sandbox /home/ubuntu/workspace &
fi

wait
EOF
chmod +x /usr/local/bin/start-webdesktop.sh

cat << 'EOF' > /etc/systemd/system/webdesktop.service
[Unit]
Description=Web Desktop VNC and noVNC Service
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

# 7. Deploy Agent Bridge API (:8000)
echo "[7/8] Deploying Agent Bridge API (:8000)..."
wget -q -O /usr/local/bin/agent_bridge.py "http://${COCKPIT_HOST}/packages/agent_bridge.py" || true
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

# 8. Pre-load Master Skills Library
echo "[8/8] Installing Master Skills Library..."
mkdir -p /root/.gemini/skills /root/.gemini/config/skills /home/ubuntu/.gemini/skills
wget -q -O /tmp/cockpit-skills-library.tar.gz "http://${COCKPIT_HOST}/packages/cockpit-skills-library.tar.gz" || true
if [ -f "/tmp/cockpit-skills-library.tar.gz" ]; then
    tar -xzf /tmp/cockpit-skills-library.tar.gz -C /root/.gemini/skills/ || true
    tar -xzf /tmp/cockpit-skills-library.tar.gz -C /root/.gemini/config/skills/ || true
    tar -xzf /tmp/cockpit-skills-library.tar.gz -C /home/ubuntu/.gemini/skills/ || true
    rm -f /tmp/cockpit-skills-library.tar.gz
fi

# Enable and Start System Services
echo ">>> Starting system services..."
systemctl daemon-reload
systemctl enable --now webdesktop.service
systemctl enable --now agent-bridge.service
systemctl restart webdesktop.service || true
systemctl restart agent-bridge.service || true

echo "===================================================================="
echo ">>> Installation Complete for Engine: ${ENGINE_LOWER}!"
echo ">>> noVNC Live Desktop: http://$(hostname -I | awk '{print $1}'):6080"
echo ">>> Agent API Bridge:   http://$(hostname -I | awk '{print $1}'):8000/status"
echo "===================================================================="
