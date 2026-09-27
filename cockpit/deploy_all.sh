#!/bin/bash
set -e

echo ">>> 1. Deploying to CT 150 (Cockpit)..."
pct push 150 /tmp/deploy_paperclip/cockpit_server.py /usr/local/bin/cockpit_server.py --perms 0755
pct push 150 /tmp/deploy_paperclip/orchestrator.py /usr/local/bin/ceo/orchestrator.py --perms 0644
pct push 150 /tmp/deploy_paperclip/orchestrator.py /usr/local/share/cockpit/ceo/orchestrator.py --perms 0644 2>/dev/null || true
pct push 150 /tmp/deploy_paperclip/agent_bridge.py /usr/local/bin/agent_bridge.py --perms 0644
pct push 150 /tmp/deploy_paperclip/agent_bridge.py /usr/local/share/cockpit/agent_bridge.py --perms 0644 2>/dev/null || true

pct exec 150 -- mkdir -p /usr/local/share/cockpit/skills_library/paperclip-fleet/scripts
pct push 150 /tmp/deploy_paperclip/paperclip-fleet/SKILL.md /usr/local/share/cockpit/skills_library/paperclip-fleet/SKILL.md --perms 0644
pct push 150 /tmp/deploy_paperclip/paperclip-fleet/scripts/paperclip /usr/local/share/cockpit/skills_library/paperclip-fleet/scripts/paperclip --perms 0755
pct push 150 /tmp/deploy_paperclip/paperclip-fleet/scripts/paperclip_client.py /usr/local/share/cockpit/skills_library/paperclip-fleet/scripts/paperclip_client.py --perms 0644

echo ">>> Rebuilding skills library archive on CT 150..."
pct exec 150 -- bash -c "cd /usr/local/share/cockpit/skills_library && tar -czf /usr/local/share/cockpit/cockpit-skills-library.tar.gz *"

echo ">>> Restarting cockpit.service on CT 150..."
pct exec 150 -- systemctl restart cockpit.service
sleep 2
echo "Cockpit status: $(pct exec 150 -- systemctl is-active cockpit.service)"

for CT_ID in 151 152 153 154; do
    if pct status $CT_ID 2>/dev/null | grep -q running; then
        echo ">>> Deploying Paperclip logic to CT $CT_ID..."
        pct push $CT_ID /tmp/deploy_paperclip/agent_bridge.py /usr/local/bin/agent_bridge.py --perms 0755
        pct push $CT_ID /tmp/deploy_paperclip/paperclip-fleet/scripts/paperclip /usr/local/bin/paperclip --perms 0755
        pct push $CT_ID /tmp/deploy_paperclip/paperclip-fleet/scripts/paperclip_client.py /usr/local/bin/paperclip_client.py --perms 0644
        
        # Install skill directly to all gemini skill search paths
        for SKILL_BASE in /root/.gemini/skills /root/.gemini/config/skills /home/ubuntu/.gemini/skills; do
            pct exec $CT_ID -- mkdir -p $SKILL_BASE/paperclip-fleet/scripts
            pct push $CT_ID /tmp/deploy_paperclip/paperclip-fleet/SKILL.md $SKILL_BASE/paperclip-fleet/SKILL.md --perms 0644
            pct push $CT_ID /tmp/deploy_paperclip/paperclip-fleet/scripts/paperclip $SKILL_BASE/paperclip-fleet/scripts/paperclip --perms 0755
            pct push $CT_ID /tmp/deploy_paperclip/paperclip-fleet/scripts/paperclip_client.py $SKILL_BASE/paperclip-fleet/scripts/paperclip_client.py --perms 0644
            pct exec $CT_ID -- chown -R ubuntu:ubuntu /home/ubuntu/.gemini 2>/dev/null || true
        done
        
        # Restart agent-bridge
        echo ">>> Restarting agent-bridge.service on CT $CT_ID..."
        pct exec $CT_ID -- systemctl restart agent-bridge.service 2>/dev/null || true
        sleep 1
        echo "Agent bridge status on CT $CT_ID: $(pct exec $CT_ID -- systemctl is-active agent-bridge.service 2>/dev/null || echo 'N/A')"
    fi
done

echo ">>> ALL DEPLOYMENTS COMPLETE!"
