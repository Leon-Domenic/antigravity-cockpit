# Build script for cockpit_server_v4: Adds Trash Icon & Agent Removal
import re, json

with open("cockpit_server.py", "r", encoding="utf-8") as f:
    code = f.read()

# 1. Dedicated Header: Add Remove Button
old_header_buttons = """                            <button onclick="openRenameModal(currentView)" class="px-2.5 py-0.5 border rounded-lg text-xs font-semibold transition flex items-center gap-1.5 text-slate-300 hover:text-white" style="background-color: var(--bg-input); border-color: var(--border-base);" title="Configure Agent & Engine">
                                <i class="fa-solid fa-pen-to-square text-amber-400"></i> Configure
                            </button>"""

new_header_buttons = """                            <button onclick="openRenameModal(currentView)" class="px-2.5 py-0.5 border rounded-lg text-xs font-semibold transition flex items-center gap-1.5 text-slate-300 hover:text-white" style="background-color: var(--bg-input); border-color: var(--border-base);" title="Configure Agent & Engine">
                                <i class="fa-solid fa-pen-to-square text-amber-400"></i> Configure
                            </button>
                            <button onclick="confirmRemoveAgent(currentView)" class="px-2.5 py-0.5 border rounded-lg text-xs font-semibold transition flex items-center gap-1.5 text-rose-400 hover:text-white hover:bg-rose-500/20" style="background-color: var(--bg-input); border-color: rgba(244, 63, 94, 0.3);" title="Remove Agent">
                                <i class="fa-solid fa-trash-can text-rose-400"></i> Remove
                            </button>"""

assert old_header_buttons in code, "old_header_buttons not found"
code = code.replace(old_header_buttons, new_header_buttons)

# 2. Rename Modal Footer: Add "Delete Agent" button on the left
old_rename_footer = """            <div class="px-6 py-3.5 border-t flex justify-end gap-2" style="background-color: var(--bg-sidebar); border-color: var(--border-base);">
                <button onclick="closeRenameModal()" class="px-4 py-2 border rounded-xl text-xs font-medium transition" style="background-color: var(--bg-input); border-color: var(--border-base); color: var(--text-main);">
                    Cancel
                </button>
                <button onclick="saveAgentRename()" class="px-5 py-2 btn-action-primary font-semibold rounded-xl text-xs transition shadow-lg flex items-center gap-2">
                    <i class="fa-solid fa-check"></i> Save Changes
                </button>
            </div>"""

new_rename_footer = """            <div class="px-6 py-3.5 border-t flex justify-between items-center" style="background-color: var(--bg-sidebar); border-color: var(--border-base);">
                <button onclick="confirmRemoveAgent(targetRenameId)" class="px-3 py-2 text-rose-400 hover:text-rose-200 hover:bg-rose-500/20 text-xs font-semibold rounded-xl border border-rose-500/30 transition flex items-center gap-1.5">
                    <i class="fa-solid fa-trash-can"></i> Delete Agent
                </button>
                <div class="flex gap-2">
                    <button onclick="closeRenameModal()" class="px-4 py-2 border rounded-xl text-xs font-medium transition" style="background-color: var(--bg-input); border-color: var(--border-base); color: var(--text-main);">
                        Cancel
                    </button>
                    <button onclick="saveAgentRename()" class="px-5 py-2 btn-action-primary font-semibold rounded-xl text-xs transition shadow-lg flex items-center gap-2">
                        <i class="fa-solid fa-check"></i> Save Changes
                    </button>
                </div>
            </div>"""

assert old_rename_footer in code, "old_rename_footer not found"
code = code.replace(old_rename_footer, new_rename_footer)

# 3. Add #delete-agent-modal HTML right after #rename-agent-modal
delete_modal_html = """

    <!-- ============================================================ -->
    <!-- REMOVE / DELETE AGENT CONFIRMATION MODAL                     -->
    <!-- ============================================================ -->
    <div id="delete-agent-modal" class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md hidden">
        <div class="glass w-full max-w-md rounded-3xl overflow-hidden shadow-2xl flex flex-col border" style="background-color: var(--bg-card); border-color: var(--border-base);">
            <div class="px-6 py-4 border-b flex items-center justify-between" style="background-color: var(--bg-sidebar); border-color: var(--border-base);">
                <div class="flex items-center space-x-3">
                    <div class="w-9 h-9 rounded-xl border flex items-center justify-center text-rose-400 text-base" style="background-color: var(--bg-input); border-color: rgba(244, 63, 94, 0.3);">
                        <i class="fa-solid fa-trash-can"></i>
                    </div>
                    <div>
                        <h3 class="text-sm font-bold text-white">Remove Agent</h3>
                        <p class="text-[10px] text-slate-400 font-mono" id="delete-modal-target-id">agent-1</p>
                    </div>
                </div>
                <button onclick="closeDeleteModal()" class="w-8 h-8 rounded-xl border flex items-center justify-center text-slate-400 hover:text-white transition" style="background-color: var(--bg-input); border-color: var(--border-base);">
                    <i class="fa-solid fa-xmark"></i>
                </button>
            </div>
            <div class="p-6 space-y-4">
                <div class="p-3.5 rounded-xl border flex items-center gap-3" style="background-color: rgba(244, 63, 94, 0.08); border-color: rgba(244, 63, 94, 0.25);">
                    <i class="fa-solid fa-triangle-exclamation text-rose-400 text-lg flex-shrink-0"></i>
                    <div class="text-xs text-slate-200">
                        Are you sure you want to remove <strong class="text-white" id="delete-modal-agent-name">Agent</strong>?
                        <div class="text-[11px] text-slate-400 mt-0.5" id="delete-modal-details">CT 151 &bull; 192.168.178.169</div>
                    </div>
                </div>
                <p class="text-xs text-slate-400 leading-relaxed">
                    This will stop the agent if it is currently running and remove it from your Cockpit dashboard.
                </p>
                <div class="pt-2 border-t" style="border-color: var(--border-base);">
                    <label class="flex items-center gap-2 cursor-pointer text-xs text-slate-300 select-none">
                        <input type="checkbox" id="delete-modal-purge-pve" class="w-4 h-4 rounded text-rose-500 focus:ring-rose-500">
                        <span>Also permanently purge LXC container from Proxmox storage</span>
                    </label>
                    <p class="text-[10px] text-slate-500 mt-1 pl-6">Leave unchecked if you only want to remove it from Cockpit (can be re-added anytime).</p>
                </div>
            </div>
            <div class="px-6 py-3.5 border-t flex justify-end gap-2" style="background-color: var(--bg-sidebar); border-color: var(--border-base);">
                <button onclick="closeDeleteModal()" class="px-4 py-2 border rounded-xl text-xs font-medium transition" style="background-color: var(--bg-input); border-color: var(--border-base); color: var(--text-main);">
                    Cancel
                </button>
                <button onclick="executeDeleteAgent()" class="px-5 py-2 bg-rose-600 hover:bg-rose-500 text-white font-semibold rounded-xl text-xs transition shadow-lg flex items-center gap-2">
                    <i class="fa-solid fa-trash-can"></i> Remove Agent
                </button>
            </div>
        </div>
    </div>
"""

rename_modal_end = "    </div>\n\n    <!-- ============================================================ -->\n    <!-- SPIN UP / ADD AGENT MODAL"
assert rename_modal_end in code, "rename_modal_end not found"
code = code.replace(rename_modal_end, "    </div>\n" + delete_modal_html + "\n    <!-- ============================================================ -->\n    <!-- SPIN UP / ADD AGENT MODAL")

# 4. Sidebar Card: Add small trash icon next to start/stop button
old_sidebar_card_footer = """                    <div class="flex justify-between items-center pt-1 border-t text-[10px]" style="border-color: var(--border-base);">
                        <span id="side-ip-${agent.id}" class="text-slate-500 font-mono">${agent.ip}</span>
                        <div onclick="event.stopPropagation()" id="side-power-${agent.id}">
                            <button onclick="toggleAgentPower('${agent.id}', 'start')" class="px-2 py-0.5 rounded bg-emerald-500/10 hover:bg-emerald-500/25 text-emerald-400 border border-emerald-500/20 font-semibold transition" title="Start Container">
                                <i class="fa-solid fa-play mr-1"></i>Start
                            </button>
                        </div>
                    </div>"""

new_sidebar_card_footer = """                    <div class="flex justify-between items-center pt-1 border-t text-[10px]" style="border-color: var(--border-base);">
                        <span id="side-ip-${agent.id}" class="text-slate-500 font-mono">${agent.ip}</span>
                        <div class="flex items-center gap-1.5" onclick="event.stopPropagation()">
                            <span id="side-power-${agent.id}">
                                <button onclick="toggleAgentPower('${agent.id}', 'start')" class="px-2 py-0.5 rounded bg-emerald-500/10 hover:bg-emerald-500/25 text-emerald-400 border border-emerald-500/20 font-semibold transition" title="Start Container">
                                    <i class="fa-solid fa-play mr-1"></i>Start
                                </button>
                            </span>
                            <button onclick="confirmRemoveAgent('${agent.id}')" class="px-1.5 py-0.5 rounded text-slate-500 hover:text-rose-400 hover:bg-rose-500/10 border border-transparent hover:border-rose-500/20 transition" title="Remove Agent">
                                <i class="fa-solid fa-trash-can text-[10px]"></i>
                            </button>
                        </div>
                    </div>"""

assert old_sidebar_card_footer in code, "old_sidebar_card_footer not found"
code = code.replace(old_sidebar_card_footer, new_sidebar_card_footer)

# 5. Fleet Table: Add trash icon to actions column
old_table_actions = """                    <td class="p-3.5 text-right space-x-2" onclick="event.stopPropagation()">
                        <button onclick="openRenameModal('${agent.id}')" class="px-2 py-1 border rounded-lg text-xs transition text-slate-400 hover:text-white" style="background-color: var(--bg-input); border-color: var(--border-base);" title="Configure">
                            <i class="fa-solid fa-pen-to-square"></i>
                        </button>
                        <button onclick="selectView('${agent.id}')" class="px-2.5 py-1 border rounded-lg text-xs transition" style="background-color: var(--bg-input); border-color: var(--border-base); color: var(--text-main);">
                            Page
                        </button>"""

new_table_actions = """                    <td class="p-3.5 text-right space-x-2" onclick="event.stopPropagation()">
                        <button onclick="openRenameModal('${agent.id}')" class="px-2 py-1 border rounded-lg text-xs transition text-slate-400 hover:text-white" style="background-color: var(--bg-input); border-color: var(--border-base);" title="Configure">
                            <i class="fa-solid fa-pen-to-square"></i>
                        </button>
                        <button onclick="confirmRemoveAgent('${agent.id}')" class="px-2 py-1 border rounded-lg text-xs transition text-rose-400 hover:text-rose-200 hover:bg-rose-500/10" style="background-color: var(--bg-input); border-color: rgba(244, 63, 94, 0.25);" title="Remove Agent">
                            <i class="fa-solid fa-trash-can"></i>
                        </button>
                        <button onclick="selectView('${agent.id}')" class="px-2.5 py-1 border rounded-lg text-xs transition" style="background-color: var(--bg-input); border-color: var(--border-base); color: var(--text-main);">
                            Page
                        </button>"""

assert old_table_actions in code, "old_table_actions not found"
code = code.replace(old_table_actions, new_table_actions)

# 6. Client Logic: Add confirmRemoveAgent, closeDeleteModal, executeDeleteAgent, and update standby logic
old_rename_modal_func = "        function closeRenameModal() {\n            document.getElementById(\"rename-agent-modal\").classList.add(\"hidden\");\n            targetRenameId = null;\n        }"

new_delete_and_rename_funcs = """        function closeRenameModal() {
            document.getElementById("rename-agent-modal").classList.add("hidden");
            targetRenameId = null;
        }

        // ============================================================
        // REMOVE / DELETE AGENT CLIENT LOGIC
        // ============================================================
        let targetDeleteId = null;

        function confirmRemoveAgent(agentId) {
            const agent = agents.find(a => a.id === agentId);
            if (!agent) return;
            targetDeleteId = agentId;
            closeRenameModal();

            document.getElementById("delete-modal-target-id").innerText = `${agent.id} (CT ${agent.vmid})`;
            document.getElementById("delete-modal-agent-name").innerText = agent.name;
            document.getElementById("delete-modal-details").innerText = `Engine: ${getAgentEngine(agent.type).name} | Role: ${agent.role} | IP: ${agent.ip}`;
            document.getElementById("delete-modal-purge-pve").checked = false;
            document.getElementById("delete-agent-modal").classList.remove("hidden");
        }

        function closeDeleteModal() {
            document.getElementById("delete-agent-modal").classList.add("hidden");
            targetDeleteId = null;
        }

        async function executeDeleteAgent() {
            if (!targetDeleteId) return;
            const purgePve = document.getElementById("delete-modal-purge-pve").checked;
            const agentToRemove = targetDeleteId;

            try {
                const res = await fetch("/api/agents/remove", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        agent_id: agentToRemove,
                        purge_pve: purgePve
                    })
                });
                const data = await res.json();
                if (data.success) {
                    agents = agents.filter(a => a.id !== agentToRemove);
                    
                    if (currentView === agentToRemove) {
                        selectView("overview");
                    }

                    buildSidebarDom();
                    buildDedicatedIframes();
                    buildOverviewScreensGrid();
                    buildFleetTableDom();
                    fetchAllStatus();
                    closeDeleteModal();
                } else {
                    alert(data.error || "Failed to remove agent");
                }
            } catch (e) {
                alert("Network error: " + e.message);
            }
        }"""

assert old_rename_modal_func in code, "old_rename_modal_func not found"
code = code.replace(old_rename_modal_func, new_delete_and_rename_funcs)

# 7. Update renderStandbyList and quickSpinUpStandby so removed fleet containers can be re-added
old_standby_logic = """        function renderStandbyList() {
            const standbyList = document.getElementById("standby-agents-list");
            if (!standbyList) return;

            const stoppedAgents = agents.filter(a => {
                const st = fleetStatuses[a.id];
                return !st || st.power === "stopped" || st.power === "unknown";
            });

            if (stoppedAgents.length === 0) {
                standbyList.innerHTML = `
                    <div class="p-4 rounded-xl border text-center text-slate-400 text-xs" style="background-color: var(--bg-input); border-color: var(--border-base);">
                        <i class="fa-solid fa-circle-check text-emerald-400 mr-1.5"></i> All 5 provisioned fleet containers are currently running!
                    </div>
                `;
                return;
            }

            const curEngine = getAgentEngine(selectedAddEngine);

            standbyList.innerHTML = stoppedAgents.map(a => {
                const suggestedName = `${curEngine.name} (CT ${a.vmid})`;
                const suggestedRole = curEngine.defaultRole;

                return `
                    <div class="p-3.5 rounded-xl border flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3" style="background-color: var(--bg-input); border-color: var(--border-base);">
                        <div class="flex items-center space-x-3">
                            <div class="w-10 h-10 rounded-xl border flex items-center justify-center text-sm flex-shrink-0" style="background-color: var(--bg-sidebar); border-color: var(--border-base); color: ${curEngine.color};">
                                <i class="${curEngine.icon}"></i>
                            </div>
                            <div>
                                <div class="flex items-center gap-2">
                                    <span class="text-xs font-bold text-white">CT ${a.vmid}</span>
                                    <span class="text-[9px] px-1.5 py-0.2 rounded font-semibold border" style="background:${curEngine.badgeBg}; color:${curEngine.badgeText}; border-color:${curEngine.badgeBorder};">
                                        ${curEngine.name}
                                    </span>
                                </div>
                                <div class="text-[11px] text-slate-300 font-medium">${suggestedRole}</div>
                                <div class="text-[10px] text-slate-400 font-mono">${a.ip} &bull; 6 GB RAM &bull; 4 vCPU</div>
                            </div>
                        </div>
                        <div class="flex items-center gap-2 w-full sm:w-auto justify-end">
                            <button onclick="quickSpinUpStandby('${a.id}', '${curEngine.id}', '${suggestedName}', '${suggestedRole}')" class="px-4 py-2 btn-action-primary font-semibold rounded-xl text-xs transition shadow-lg flex items-center gap-1.5 flex-shrink-0">
                                <i class="fa-solid fa-bolt"></i> Spin Up as ${curEngine.name}
                            </button>
                        </div>
                    </div>
                `;
            }).join("");
        }"""

new_standby_logic = """        function renderStandbyList() {
            const standbyList = document.getElementById("standby-agents-list");
            if (!standbyList) return;

            const registeredStopped = agents.filter(a => {
                const st = fleetStatuses[a.id];
                return !st || st.power === "stopped" || st.power === "unknown";
            });

            const standardVms = [
                { vmid: 151, ip: "192.168.178.169" },
                { vmid: 152, ip: "192.168.178.170" },
                { vmid: 153, ip: "192.168.178.171" },
                { vmid: 154, ip: "192.168.178.172" },
                { vmid: 155, ip: "192.168.178.173" }
            ];
            const unregisteredFleet = standardVms.filter(v => !agents.some(a => a.vmid === v.vmid));

            const totalStandby = [
                ...registeredStopped.map(a => ({ id: a.id, vmid: a.vmid, ip: a.ip, isNew: false })),
                ...unregisteredFleet.map(u => ({ id: `agent-${u.vmid-150}`, vmid: u.vmid, ip: u.ip, isNew: true }))
            ];

            if (totalStandby.length === 0) {
                standbyList.innerHTML = `
                    <div class="p-4 rounded-xl border text-center text-slate-400 text-xs" style="background-color: var(--bg-input); border-color: var(--border-base);">
                        <i class="fa-solid fa-circle-check text-emerald-400 mr-1.5"></i> All provisioned fleet containers are currently running!
                    </div>
                `;
                return;
            }

            const curEngine = getAgentEngine(selectedAddEngine);

            standbyList.innerHTML = totalStandby.map(a => {
                const suggestedName = `${curEngine.name} (CT ${a.vmid})`;
                const suggestedRole = curEngine.defaultRole;

                return `
                    <div class="p-3.5 rounded-xl border flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3" style="background-color: var(--bg-input); border-color: var(--border-base);">
                        <div class="flex items-center space-x-3">
                            <div class="w-10 h-10 rounded-xl border flex items-center justify-center text-sm flex-shrink-0" style="background-color: var(--bg-sidebar); border-color: var(--border-base); color: ${curEngine.color};">
                                <i class="${curEngine.icon}"></i>
                            </div>
                            <div>
                                <div class="flex items-center gap-2">
                                    <span class="text-xs font-bold text-white">CT ${a.vmid}</span>
                                    <span class="text-[9px] px-1.5 py-0.2 rounded font-semibold border" style="background:${curEngine.badgeBg}; color:${curEngine.badgeText}; border-color:${curEngine.badgeBorder};">
                                        ${curEngine.name}
                                    </span>
                                </div>
                                <div class="text-[11px] text-slate-300 font-medium">${suggestedRole}</div>
                                <div class="text-[10px] text-slate-400 font-mono">${a.ip} &bull; 6 GB RAM &bull; 4 vCPU</div>
                            </div>
                        </div>
                        <div class="flex items-center gap-2 w-full sm:w-auto justify-end">
                            <button onclick="quickSpinUpStandby('${a.id}', '${curEngine.id}', '${suggestedName}', '${suggestedRole}', ${a.vmid}, '${a.ip}', ${a.isNew})" class="px-4 py-2 btn-action-primary font-semibold rounded-xl text-xs transition shadow-lg flex items-center gap-1.5 flex-shrink-0">
                                <i class="fa-solid fa-bolt"></i> Spin Up as ${curEngine.name}
                            </button>
                        </div>
                    </div>
                `;
            }).join("");
        }"""

assert old_standby_logic in code, "old_standby_logic not found"
code = code.replace(old_standby_logic, new_standby_logic)

# Update quickSpinUpStandby
old_quick_spinup = """        async function quickSpinUpStandby(agentId, engineId, name, role) {
            closeAddAgentModal();
            try {
                await fetch("/api/agents/rename", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        agent_id: agentId,
                        name: name,
                        role: role,
                        type: engineId
                    })
                });
                const agent = agents.find(a => a.id === agentId);
                if (agent) {
                    agent.name = name;
                    agent.role = role;
                    agent.type = engineId;
                }
                buildSidebarDom();
                buildOverviewScreensGrid();
                buildFleetTableDom();
            } catch (e) {
                console.error("Config update error", e);
            }

            await toggleAgentPower(agentId, 'start');
            selectView(agentId);
        }"""

new_quick_spinup = """        async function quickSpinUpStandby(agentId, engineId, name, role, vmid, ip, isNew) {
            closeAddAgentModal();
            try {
                if (isNew) {
                    const res = await fetch("/api/agents/add", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({
                            name: name,
                            role: role,
                            ip: ip,
                            vmid: vmid,
                            type: engineId
                        })
                    });
                    const data = await res.json();
                    if (data.success) {
                        agents = data.agents;
                    }
                } else {
                    await fetch("/api/agents/rename", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({
                            agent_id: agentId,
                            name: name,
                            role: role,
                            type: engineId
                        })
                    });
                    const agent = agents.find(a => a.id === agentId);
                    if (agent) {
                        agent.name = name;
                        agent.role = role;
                        agent.type = engineId;
                    }
                }
                buildSidebarDom();
                buildDedicatedIframes();
                buildOverviewScreensGrid();
                buildFleetTableDom();
            } catch (e) {
                console.error("Config update error", e);
            }

            await toggleAgentPower(agentId, 'start');
            selectView(agentId);
        }"""

assert old_quick_spinup in code, "old_quick_spinup not found"
code = code.replace(old_quick_spinup, new_quick_spinup)

# 8. Backend: Add /api/agents/remove endpoint
backend_remove_route = """@app.route("/api/agents/remove", methods=["POST", "DELETE"])
def remove_agent_route():
    data = request.json or {}
    agent_id = data.get("agent_id") or data.get("id") or request.args.get("agent_id")
    purge_pve = bool(data.get("purge_pve", False))
    
    agent = next((a for a in AGENTS if a["id"] == agent_id), None)
    if not agent:
        return jsonify({"error": "Agent not found"}), 404
    
    # 1. Stop container if running
    vmid = agent.get("vmid")
    if vmid:
        try:
            requests.post(
                f"{PROXMOX_API}/nodes/pve/lxc/{vmid}/status/stop",
                headers={"Authorization": PROXMOX_TOKEN},
                verify=False,
                timeout=5
            )
        except Exception:
            pass

        # 2. If purge_pve is explicitly requested
        if purge_pve:
            try:
                time.sleep(1)
                requests.delete(
                    f"{PROXMOX_API}/nodes/pve/lxc/{vmid}",
                    headers={"Authorization": PROXMOX_TOKEN},
                    verify=False,
                    timeout=8
                )
            except Exception as pe:
                print(f"Failed to purge container {vmid} on PVE:", pe)
    
    # 3. Remove from AGENTS list and save
    AGENTS.remove(agent)
    save_agents_config()
    
    return jsonify({"success": True, "removed_id": agent_id, "agents": AGENTS})
"""

add_route_search = '@app.route("/api/agents/add", methods=["POST"])'
assert add_route_search in code, "add_route_search not found"
code = code.replace(add_route_search, backend_remove_route + "\n" + add_route_search)

with open("cockpit_server_v4.py", "w", encoding="utf-8") as f:
    f.write(code)

print("cockpit_server_v4.py generated successfully!")
