#!/bin/bash
set -e

echo ">>> Backing up previous cockpit_server.py..."
pct exec 150 -- cp /usr/local/bin/cockpit_server.py /usr/local/bin/cockpit_server.py.bak 2>/dev/null || true

echo ">>> Pushing new cockpit_server.py to CT 150..."
pct push 150 /tmp/cockpit_server.py /usr/local/bin/cockpit_server.py
pct exec 150 -- chmod +x /usr/local/bin/cockpit_server.py

echo ">>> Pushing CEO Orchestration suite to CT 150..."
pct exec 150 -- rm -rf /usr/local/bin/ceo /usr/local/share/cockpit/ceo
pct push 150 /tmp/ceo /usr/local/bin/ceo
pct push 150 /tmp/ceo /usr/local/share/cockpit/ceo

echo ">>> Setting up directory structure..."
pct exec 150 -- mkdir -p /usr/local/share/cockpit/installers /usr/local/share/cockpit/scripts /usr/local/share/cockpit/workspaces

echo ">>> Pushing install.sh & pve_provision_agent.sh..."
pct push 150 /tmp/install.sh /usr/local/share/cockpit/install.sh
pct push 150 /tmp/pve_provision_agent.sh /usr/local/share/cockpit/scripts/pve_provision_agent.sh
cp /tmp/pve_provision_agent.sh /usr/local/bin/pve_provision_agent.sh
chmod +x /usr/local/bin/pve_provision_agent.sh

echo ">>> Pushing engine installer packages..."
if [ -d /tmp/installers ]; then
    for f in /tmp/installers/*; do
        if [ -f "$f" ]; then
            base=$(basename "$f")
            pct push 150 "$f" "/usr/local/share/cockpit/installers/$base"
            pct push 150 "$f" "/usr/local/share/cockpit/$base"
        fi
    done
fi

echo ">>> Restarting cockpit.service on CT 150..."
pct exec 150 -- systemctl restart cockpit.service

echo ">>> Checking cockpit status on CT 150..."
sleep 2
pct exec 150 -- systemctl is-active cockpit.service

echo ">>> Deploy to CT 150 completed successfully!"
