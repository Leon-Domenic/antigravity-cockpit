#!/bin/bash
# ==============================================================================
# Open Claw - Autonomous Web Scraper & Crawler Node Installer
# Optimized for: Proxmox KVM Virtual Machines (or privileged LXC with nesting)
# Hardware Recommended: 4-8 vCPUs, 8-16 GB RAM, 50 GB SSD
# ==============================================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/common.sh"

COCKPIT_HOST="${COCKPIT_HOST:-192.168.178.168:3000}"
COCKPIT_HOST="${COCKPIT_HOST#http://}"
COCKPIT_HOST="${COCKPIT_HOST#https://}"
COCKPIT_HOST="${COCKPIT_HOST%/}"

echo "===================================================================="
echo ">>> Installing Open Claw (Autonomous Web Intelligence & Crawler)..."
echo "===================================================================="

# Persist engine marker
mkdir -p /etc/antigravity
echo "openclaw" > /etc/antigravity/agent_type

# 1. Pre-flight checks: 8192 MB min (16384 recommended), 4 cores, KVM recommended
check_system_resources 8192 4 "Open Claw" "kvm"

# 2. Core Dependencies
install_core_dependencies

# 3. Desktop, X11 Display, and Visual Inspection Tools
echo ">>> Installing headless display and visual crawl inspection tools..."
apt-get install -y -qq \
    xvfb \
    openbox \
    x11vnc \
    novnc \
    websockify \
    scrot \
    fonts-liberation \
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
    libasound2t64 >/dev/null 2>&1 || apt-get install -y -qq libasound2 || true

# 4. Install Node.js & Playwright System Browsers
echo ">>> Setting up Playwright and browser automation engines..."
if ! command -v node &>/dev/null; then
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - >/dev/null 2>&1
    apt-get install -y -qq nodejs >/dev/null 2>&1
fi

# 5. Install Python Scraping, Stealth & Anti-Bot Libraries
echo ">>> Installing crawling and stealth extraction libraries..."
pip3 install --break-system-packages --ignore-installed \
    playwright \
    beautifulsoup4 \
    scrapy \
    curl_cffi \
    requests \
    lxml \
    tldextract \
    fake-useragent >/dev/null 2>&1 || pip3 install --break-system-packages playwright beautifulsoup4 requests

# Install Playwright browser binaries with all OS dependencies
echo ">>> Installing Playwright Chromium browser binaries..."
python3 -m playwright install --with-deps chromium >/dev/null 2>&1 || playwright install chromium >/dev/null 2>&1 || true

# 6. Apply Sandbox & Kernel Compatibility Adjustments
echo ">>> Tuning Chromium sandbox and kernel namespaces..."
sysctl -w kernel.unprivileged_userns_clone=1 2>/dev/null || true

# Configure Single-Desktop Openbox Window Manager
cat << 'EOF' > /etc/xdg/openbox/rc.xml
<?xml version="1.0" encoding="UTF-8"?>
<openbox_config xmlns="http://openbox.org/3.4/rc">
  <desktops><number>1</number><firstdesk>1</firstdesk><names><name>Crawl Desktop</name></names></desktops>
</openbox_config>
EOF
mkdir -p /root/.config/openbox /home/ubuntu/.config/openbox
cp /etc/xdg/openbox/rc.xml /root/.config/openbox/rc.xml
cp /etc/xdg/openbox/rc.xml /home/ubuntu/.config/openbox/rc.xml 2>/dev/null || true

# Configure Virtual Web Desktop (1920x1080) for Live Visual Crawling Audit
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
wait
EOF
chmod +x /usr/local/bin/start-webdesktop.sh

cat << 'EOF' > /etc/systemd/system/webdesktop.service
[Unit]
Description=Open Claw Visual Web Desktop
After=network.target

[Service]
Type=simple
ExecStart=/usr/local/bin/start-webdesktop.sh
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now webdesktop.service
systemctl restart webdesktop.service || true

# 7. Deploy Agent Bridge & Skills Library
deploy_agent_bridge "${COCKPIT_HOST}"
install_skills_library "${COCKPIT_HOST}"

echo "===================================================================="
echo ">>> Open Claw Crawler Node Installed Successfully!"
echo ">>> Engine Type: openclaw (Autonomous Web Scraper & Crawler)"
echo ">>> Visual Browser VNC: http://$(hostname -I | awk '{print $1}'):6080"
echo ">>> Agent API Bridge:   http://$(hostname -I | awk '{print $1}'):8000/status"
echo "===================================================================="
