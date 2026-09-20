# Python script to inject Renaming and Big Plus Icon features into cockpit_server.py
import re, json

with open("cockpit_server.py", "r", encoding="utf-8") as f:
    code = f.read()

# 1. Config Persistence for AGENTS
agents_config_block = """
# Master configuration for Antigravity instances
AGENTS_CONFIG_FILE = "/usr/local/share/cockpit/agents_config.json"

DEFAULT_AGENTS = [
    {"id": "agent-1", "vmid": 151, "name": "Agent 1", "role": "Frontend Specialist", "ip": "192.168.178.169", "port": 8000, "vnc_port": 6080},
    {"id": "agent-2", "vmid": 152, "name": "Agent 2", "role": "Backend Specialist",  "ip": "192.168.178.170", "port": 8000, "vnc_port": 6080},
    {"id": "agent-3", "vmid": 153, "name": "Agent 3", "role": "Fullstack Dev",       "ip": "192.168.178.171", "port": 8000, "vnc_port": 6080},
    {"id": "agent-4", "vmid": 154, "name": "Agent 4", "role": "QA & Test Automation","ip": "192.168.178.172", "port": 8000, "vnc_port": 6080},
    {"id": "agent-5", "vmid": 155, "name": "Agent 5", "role": "System Architect",    "ip": "192.168.178.173", "port": 8000, "vnc_port": 6080}
]

AGENTS = list(DEFAULT_AGENTS)

def load_agents_config():
    global AGENTS
    if os.path.exists(AGENTS_CONFIG_FILE):
        try:
            with open(AGENTS_CONFIG_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
                if isinstance(saved, list) and len(saved) > 0:
                    AGENTS = saved
        except Exception as e:
            print("Failed to load agents_config.json", e)

def save_agents_config():
    try:
        os.makedirs(os.path.dirname(AGENTS_CONFIG_FILE), exist_ok=True)
        with open(AGENTS_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(AGENTS, f, indent=2)
    except Exception as e:
        print("Failed to save agents_config.json", e)

load_agents_config()
"""

agents_search = """# Master configuration for Antigravity instances
AGENTS = [
    {"id": "agent-1", "vmid": 151, "name": "Agent 1", "role": "Frontend Specialist", "ip": "192.168.178.169", "port": 8000, "vnc_port": 6080},
    {"id": "agent-2", "vmid": 152, "name": "Agent 2", "role": "Backend Specialist",  "ip": "192.168.178.170", "port": 8000, "vnc_port": 6080},
    {"id": "agent-3", "vmid": 153, "name": "Agent 3", "role": "Fullstack Dev",       "ip": "192.168.178.171", "port": 8000, "vnc_port": 6080},
    {"id": "agent-4", "vmid": 154, "name": "Agent 4", "role": "QA & Test Automation","ip": "192.168.178.172", "port": 8000, "vnc_port": 6080},
    {"id": "agent-5", "vmid": 155, "name": "Agent 5", "role": "System Architect",    "ip": "192.168.178.173", "port": 8000, "vnc_port": 6080}
]"""

assert agents_search in code, "agents_search not found"
code = code.replace(agents_search, agents_config_block.strip())

# 2. Add Rename Button next to Dedicated Agent Header Title
title_search = """                        <div class="flex items-center gap-3">
                            <h2 class="text-xl font-bold text-white tracking-tight" id="agent-page-title">Agent 1 (Frontend)</h2>"""

title_replace = """                        <div class="flex items-center gap-3">
                            <h2 class="text-xl font-bold text-white tracking-tight" id="agent-page-title">Agent 1 (Frontend)</h2>
                            <button onclick="openRenameModal(currentView)" class="px-2 py-0.5 border rounded-lg text-xs font-semibold transition flex items-center gap-1.5 text-slate-400 hover:text-white" style="background-color: var(--bg-input); border-color: var(--border-base);" title="Rename Agent & Role">
                                <i class="fa-solid fa-pen-to-square text-slate-400"></i> Rename
                            </button>"""

assert title_search in code, "title_search not found"
code = code.replace(title_search, title_replace)

# 3. Add Rename & Add Agent Modals before </main>
modals_html = """
    <!-- ============================================================ -->
    <!-- RENAME AGENT MODAL                                           -->
    <!-- ============================================================ -->
    <div id="rename-agent-modal" class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md hidden">
        <div class="glass w-full max-w-md rounded-3xl overflow-hidden shadow-2xl flex flex-col border" style="background-color: var(--bg-card); border-color: var(--border-base);">
            <div class="px-6 py-4 border-b flex items-center justify-between" style="background-color: var(--bg-sidebar); border-color: var(--border-base);">
                <div class="flex items-center space-x-3">
                    <div class="w-9 h-9 rounded-xl border flex items-center justify-center text-amber-400 text-base" style="background-color: var(--bg-input); border-color: var(--border-base);">
                        <i class="fa-solid fa-pen-to-square"></i>
                    </div>
                    <div>
                        <h3 class="text-sm font-bold text-white">Rename Agent Container</h3>
                        <p class="text-[10px] text-slate-400 font-mono" id="rename-modal-vmid">CT 151</p>
                    </div>
                </div>
                <button onclick="closeRenameModal()" class="w-8 h-8 rounded-xl border flex items-center justify-center text-slate-400 hover:text-white transition" style="background-color: var(--bg-input); border-color: var(--border-base);">
                    <i class="fa-solid fa-xmark"></i>
                </button>
            </div>
            <div class="p-6 space-y-4">
                <div>
                    <label class="block text-[11px] font-bold text-slate-400 uppercase tracking-wider mb-1.5">Agent Display Name</label>
                    <input id="rename-input-name" type="text" placeholder="e.g. Agent 1 or DevOps Lead" class="w-full input-box rounded-xl px-3.5 py-2.5 text-xs text-white focus:outline-none focus:border-slate-400">
                </div>
                <div>
                    <label class="block text-[11px] font-bold text-slate-400 uppercase tracking-wider mb-1.5">Specialist Role</label>
                    <input id="rename-input-role" type="text" placeholder="e.g. Frontend Specialist or Fullstack Architect" class="w-full input-box rounded-xl px-3.5 py-2.5 text-xs text-white focus:outline-none focus:border-slate-400">
                </div>
                <p class="text-[11px] text-slate-400 leading-relaxed">
                    Changes are saved in Cockpit and updated dynamically across all views.
                </p>
            </div>
            <div class="px-6 py-3.5 border-t flex justify-end gap-2" style="background-color: var(--bg-sidebar); border-color: var(--border-base);">
                <button onclick="closeRenameModal()" class="px-4 py-2 border rounded-xl text-xs font-medium transition" style="background-color: var(--bg-input); border-color: var(--border-base); color: var(--text-main);">
                    Cancel
                </button>
                <button onclick="saveAgentRename()" class="px-5 py-2 btn-action-primary font-semibold rounded-xl text-xs transition shadow-lg flex items-center gap-2">
                    <i class="fa-solid fa-check"></i> Save Changes
                </button>
            </div>
        </div>
    </div>

    <!-- ============================================================ -->
    <!-- SPIN UP / ADD AGENT MODAL                                    -->
    <!-- ============================================================ -->
    <div id="add-agent-modal" class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md hidden">
        <div class="glass w-full max-w-2xl rounded-3xl overflow-hidden shadow-2xl flex flex-col border max-h-[85vh]" style="background-color: var(--bg-card); border-color: var(--border-base);">
            <div class="px-6 py-4 border-b flex items-center justify-between" style="background-color: var(--bg-sidebar); border-color: var(--border-base);">
                <div class="flex items-center space-x-3">
                    <div class="w-9 h-9 rounded-xl border flex items-center justify-center text-emerald-400 text-base" style="background-color: var(--bg-input); border-color: var(--border-base);">
                        <i class="fa-solid fa-plus"></i>
                    </div>
                    <div>
                        <h3 class="text-sm font-bold text-white">Spin Up / Add Antigravity Agent</h3>
                        <p class="text-[10px] text-slate-400">Launch standby Proxmox containers or connect a fresh VM</p>
                    </div>
                </div>
                <button onclick="closeAddAgentModal()" class="w-8 h-8 rounded-xl border flex items-center justify-center text-slate-400 hover:text-white transition" style="background-color: var(--bg-input); border-color: var(--border-base);">
                    <i class="fa-solid fa-xmark"></i>
                </button>
            </div>
            
            <div class="p-6 space-y-5 overflow-y-auto scrollbar-thin">
                <!-- Standby Containers Section -->
                <div>
                    <div class="flex justify-between items-center mb-2.5">
                        <h4 class="text-xs font-bold uppercase tracking-wider text-white flex items-center gap-2">
                            <i class="fa-solid fa-server text-blue-400"></i> Standby Fleet Containers (PVE)
                        </h4>
                        <span class="text-[10px] text-slate-400 font-mono">1.5s Fast Launch</span>
                    </div>
                    <div id="standby-agents-list" class="space-y-2">
                        <!-- Populated dynamically with stopped containers -->
                    </div>
                </div>

                <!-- Connect New VM or Container Section -->
                <div class="pt-4 border-t space-y-3" style="border-color: var(--border-base);">
                    <div class="flex justify-between items-center">
                        <h4 class="text-xs font-bold uppercase tracking-wider text-white flex items-center gap-2">
                            <i class="fa-solid fa-network-wired text-purple-400"></i> Connect Fresh Linux VM or Node
                        </h4>
                        <span class="text-[10px] text-slate-400 font-mono">Any Debian / Ubuntu</span>
                    </div>
                    <div class="p-3.5 rounded-xl border space-y-2" style="background-color: var(--bg-input); border-color: var(--border-base);">
                        <div class="text-[11px] text-slate-300">Run this command inside any fresh VM or container to automatically install the full Antigravity agent stack:</div>
                        <div class="flex items-center gap-2">
                            <input readonly type="text" value="curl -sSL http://192.168.178.168:3000/install.sh | bash" class="flex-1 input-box rounded-lg px-3 py-2 text-xs font-mono text-amber-300 select-all border" style="background-color: var(--bg-base); border-color: var(--border-base);">
                            <button onclick="navigator.clipboard.writeText('curl -sSL http://192.168.178.168:3000/install.sh | bash'); alert('Command copied to clipboard!');" class="px-3 py-2 btn-action-primary rounded-lg text-xs font-semibold flex items-center gap-1.5 flex-shrink-0">
                                <i class="fa-solid fa-copy"></i> Copy
                            </button>
                        </div>
                    </div>

                    <!-- Register Node Form -->
                    <div class="p-4 rounded-xl border space-y-3" style="background-color: var(--bg-sidebar); border-color: var(--border-base);">
                        <span class="text-xs font-semibold text-white">Register Node in Cockpit:</span>
                        <div class="grid grid-cols-1 sm:grid-cols-3 gap-2">
                            <input id="new-agent-name" type="text" placeholder="Agent Name (e.g. Agent 6)" class="input-box rounded-lg px-3 py-1.5 text-xs text-white">
                            <input id="new-agent-role" type="text" placeholder="Role (e.g. Auditor)" class="input-box rounded-lg px-3 py-1.5 text-xs text-white">
                            <input id="new-agent-ip" type="text" placeholder="IP (e.g. 192.168.178.174)" class="input-box rounded-lg px-3 py-1.5 text-xs text-white font-mono">
                        </div>
                        <div class="flex justify-end">
                            <button onclick="registerNewCustomAgent()" class="px-4 py-1.5 btn-action-primary font-semibold rounded-xl text-xs transition shadow-lg flex items-center gap-1.5">
                                <i class="fa-solid fa-plus"></i> Add to Cockpit
                            </button>
                        </div>
                    </div>
                </div>
            </div>

            <div class="px-6 py-3 border-t flex justify-end" style="background-color: var(--bg-sidebar); border-color: var(--border-base);">
                <button onclick="closeAddAgentModal()" class="px-4 py-1.5 border rounded-xl text-xs font-medium transition" style="background-color: var(--bg-input); border-color: var(--border-base); color: var(--text-main);">
                    Close
                </button>
            </div>
        </div>
    </div>
"""

main_search = "    </main>"
assert main_search in code, "main_search not found"
code = code.replace(main_search, modals_html + "\n" + main_search)

# 4. Change const agents to let agents in JS
agents_js_search = 'const agents = """ + json.dumps(AGENTS) + """;'
agents_js_replace = 'let agents = """ + json.dumps(AGENTS) + """;'
assert agents_js_search in code, "agents_js_search not found"
code = code.replace(agents_js_search, agents_js_replace)

# 5. In buildSidebarDom, append big plus card
sidebar_append_search = """                container.appendChild(card);
            });
        }"""

sidebar_append_replace = """                container.appendChild(card);
            });

            // Big Plus Card Below Agents in Sidebar
            const addCard = document.createElement("div");
            addCard.id = "side-add-agent-card";
            addCard.className = "w-full border-2 border-dashed rounded-xl p-3.5 flex flex-col items-center justify-center cursor-pointer transition-all duration-200 group hover:border-slate-300 hover:scale-[1.01]";
            addCard.style.borderColor = "var(--border-highlight)";
            addCard.style.backgroundColor = "rgba(255,255,255,0.02)";
            addCard.onclick = () => openAddAgentModal();
            addCard.innerHTML = `
                <div class="w-8 h-8 rounded-full flex items-center justify-center text-sm mb-1 group-hover:scale-110 transition shadow-inner" style="background-color: var(--bg-input); color: var(--highlight-text); border: 1px solid var(--border-base);">
                    <i class="fa-solid fa-plus"></i>
                </div>
                <span class="text-xs font-bold text-white group-hover:text-amber-300 transition">Spin Up / Add Agent</span>
                <span class="text-[9px] text-slate-400 font-mono mt-0.5">Standby CT 153-155 or New Node</span>
            `;
            container.appendChild(addCard);
        }"""

assert sidebar_append_search in code, "sidebar_append_search not found"
code = code.replace(sidebar_append_search, sidebar_append_replace)

# 6. In buildOverviewScreensGrid, append big plus card
overview_append_search = """                container.appendChild(box);
            });
        }"""

overview_append_replace = """                container.appendChild(box);
            });

            // Big Plus Card in Overview Screens Grid
            const addOverviewCard = document.createElement("div");
            addOverviewCard.id = "overview-add-card";
            addOverviewCard.className = "glass rounded-2xl border-2 border-dashed overflow-hidden shadow-xl flex flex-col items-center justify-center aspect-16-9 cursor-pointer transition-all duration-200 group hover:border-slate-300 hover:scale-[1.01]";
            addOverviewCard.style.borderColor = "var(--border-highlight)";
            addOverviewCard.style.backgroundColor = "rgba(255,255,255,0.02)";
            addOverviewCard.onclick = () => openAddAgentModal();
            addOverviewCard.innerHTML = `
                <div class="w-14 h-14 rounded-2xl flex items-center justify-center text-2xl mb-2 group-hover:scale-110 transition shadow-inner" style="background-color: var(--bg-input); color: var(--highlight-text); border: 1px solid var(--border-base);">
                    <i class="fa-solid fa-plus"></i>
                </div>
                <h3 class="text-sm font-bold text-white group-hover:text-amber-300 transition">Launch Another Agent Screen</h3>
                <p class="text-xs text-slate-400 font-mono mt-1">Spin up standby CT 153–155 or connect fresh VM</p>
            `;
            container.appendChild(addOverviewCard);
        }"""

assert overview_append_search in code, "overview_append_search not found"
code = code.replace(overview_append_search, overview_append_replace)

# 7. Add Rename button in Fleet Table DOM
table_action_search = """                        <button onclick="selectView('${agent.id}')" class="px-2.5 py-1 border rounded-lg text-xs transition" style="background-color: var(--bg-input); border-color: var(--border-base); color: var(--text-main);">
                            Page
                        </button>"""

table_action_replace = """                        <button onclick="openRenameModal('${agent.id}')" class="px-2 py-1 border rounded-lg text-xs transition text-slate-400 hover:text-white" style="background-color: var(--bg-input); border-color: var(--border-base);" title="Rename">
                            <i class="fa-solid fa-pen-to-square"></i>
                        </button>
                        <button onclick="selectView('${agent.id}')" class="px-2.5 py-1 border rounded-lg text-xs transition" style="background-color: var(--bg-input); border-color: var(--border-base); color: var(--text-main);">
                            Page
                        </button>"""

assert table_action_search in code, "table_action_search not found"
code = code.replace(table_action_search, table_action_replace)

# 8. Add JS functions for Rename and Add Agent
js_rename_add_logic = """
        // ============================================================
        // RENAME & ADD AGENT CLIENT LOGIC
        // ============================================================
        let targetRenameId = null;

        function openRenameModal(agentId) {
            const agent = agents.find(a => a.id === agentId);
            if (!agent) return;
            targetRenameId = agentId;
            document.getElementById("rename-modal-vmid").innerText = `CT ${agent.vmid} (${agent.ip})`;
            document.getElementById("rename-input-name").value = agent.name;
            document.getElementById("rename-input-role").value = agent.role;
            document.getElementById("rename-agent-modal").classList.remove("hidden");
        }

        function closeRenameModal() {
            document.getElementById("rename-agent-modal").classList.add("hidden");
            targetRenameId = null;
        }

        async function saveAgentRename() {
            if (!targetRenameId) return;
            const newName = document.getElementById("rename-input-name").value.trim();
            const newRole = document.getElementById("rename-input-role").value.trim();
            if (!newName) return alert("Please enter an agent name");

            try {
                const res = await fetch("/api/agents/rename", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        agent_id: targetRenameId,
                        name: newName,
                        role: newRole
                    })
                });
                const data = await res.json();
                if (data.success) {
                    const agent = agents.find(a => a.id === targetRenameId);
                    if (agent) {
                        agent.name = newName;
                        agent.role = newRole;
                    }

                    // Update UI in-place
                    const titleElem = document.getElementById("agent-page-title");
                    if (titleElem && currentView === targetRenameId) {
                        titleElem.innerText = `${newName} (${newRole})`;
                    }
                    
                    // Rebuild sidebar and table to reflect new names
                    buildSidebarDom();
                    buildFleetTableDom();
                    fetchAllStatus();
                    closeRenameModal();
                } else {
                    alert(data.error || "Failed to rename agent");
                }
            } catch (e) {
                alert("Network error: " + e.message);
            }
        }

        function openAddAgentModal() {
            const modal = document.getElementById("add-agent-modal");
            if (!modal) return;
            const standbyList = document.getElementById("standby-agents-list");
            
            // Find stopped agents
            const stoppedAgents = agents.filter(a => {
                const st = fleetStatuses[a.id];
                return !st || st.power === "stopped" || st.power === "unknown";
            });

            if (stoppedAgents.length === 0) {
                standbyList.innerHTML = `
                    <div class="p-4 rounded-xl border text-center text-slate-400 text-xs" style="background-color: var(--bg-input); border-color: var(--border-base);">
                        <i class="fa-solid fa-circle-check text-emerald-400 mr-1.5"></i> All 5 provisioned fleet agents are currently running!
                    </div>
                `;
            } else {
                standbyList.innerHTML = stoppedAgents.map(a => `
                    <div class="p-3.5 rounded-xl border flex items-center justify-between gap-3" style="background-color: var(--bg-input); border-color: var(--border-base);">
                        <div class="flex items-center space-x-3">
                            <div class="w-8 h-8 rounded-xl border flex items-center justify-center text-slate-400 text-xs" style="background-color: var(--bg-sidebar); border-color: var(--border-base);">
                                <i class="fa-solid fa-server"></i>
                            </div>
                            <div>
                                <div class="text-xs font-bold text-white">${escapeHtml(a.name)} <span class="text-slate-400 font-normal">(${escapeHtml(a.role)})</span></div>
                                <div class="text-[10px] text-slate-400 font-mono">CT ${a.vmid} &bull; ${a.ip} &bull; 6 GB RAM &bull; 4 vCPU</div>
                            </div>
                        </div>
                        <button onclick="spinUpStandbyAgent('${a.id}')" class="px-3 py-1.5 bg-emerald-600/20 hover:bg-emerald-600/30 text-emerald-300 border border-emerald-500/30 font-semibold rounded-xl text-xs transition flex items-center gap-1.5">
                            <i class="fa-solid fa-bolt"></i> Spin Up
                        </button>
                    </div>
                `).join("");
            }

            modal.classList.remove("hidden");
        }

        function closeAddAgentModal() {
            document.getElementById("add-agent-modal").classList.add("hidden");
        }

        async function spinUpStandbyAgent(agentId) {
            closeAddAgentModal();
            await toggleAgentPower(agentId, 'start');
            selectView(agentId);
        }

        async function registerNewCustomAgent() {
            const name = document.getElementById("new-agent-name").value.trim();
            const role = document.getElementById("new-agent-role").value.trim() || "Specialist";
            const ip = document.getElementById("new-agent-ip").value.trim();

            if (!name || !ip) return alert("Please provide Agent Name and IP address");

            try {
                const res = await fetch("/api/agents/add", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ name, role, ip })
                });
                const data = await res.json();
                if (data.success) {
                    agents = data.agents;
                    buildSidebarDom();
                    buildDedicatedIframes();
                    buildOverviewScreensGrid();
                    buildFleetTableDom();
                    closeAddAgentModal();
                    fetchAllStatus();
                    selectView(data.agent.id);
                    alert(`Agent '${name}' successfully added to Cockpit!`);
                } else {
                    alert(data.error || "Failed to add agent");
                }
            } catch (e) {
                alert("Network error: " + e.message);
            }
        }
"""

window_onload_search = "        window.onload = init;"
assert window_onload_search in code, "window_onload_search not found"
code = code.replace(window_onload_search, js_rename_add_logic + "\n" + window_onload_search)

# 9. Add Backend Endpoints for Rename and Add Agent
backend_agents_routes = """
# ------------------------------------------------------------------
# AGENTS MANAGEMENT API (RENAME & ADD)
# ------------------------------------------------------------------
@app.route("/api/agents", methods=["GET"])
def get_agents_list():
    return jsonify({"agents": AGENTS})

@app.route("/api/agents/rename", methods=["POST"])
def rename_agent_route():
    data = request.json or {}
    agent_id = data.get("agent_id")
    new_name = (data.get("name") or "").strip()
    new_role = (data.get("role") or "").strip()
    agent = next((a for a in AGENTS if a["id"] == agent_id), None)
    if not agent:
        return jsonify({"error": "Agent not found"}), 404
    if new_name:
        agent["name"] = new_name
    if new_role:
        agent["role"] = new_role
    save_agents_config()
    
    # Optionally update Proxmox LXC description
    try:
        requests.put(
            f"{PROXMOX_API}/nodes/pve/lxc/{agent['vmid']}/config",
            headers={"Authorization": PROXMOX_TOKEN},
            json={"description": f"Antigravity Agent: {agent['name']} ({agent['role']})"},
            verify=False,
            timeout=3
        )
    except Exception:
        pass
    
    return jsonify({"success": True, "agent": agent})

@app.route("/api/agents/add", methods=["POST"])
def add_agent_route():
    data = request.json or {}
    name = (data.get("name") or "").strip()
    role = (data.get("role") or "Specialist").strip()
    ip = (data.get("ip") or "").strip()
    vmid = int(data.get("vmid") or (150 + len(AGENTS) + 1))
    port = int(data.get("port") or 8000)
    vnc_port = int(data.get("vnc_port") or 6080)
    
    if not name or not ip:
        return jsonify({"error": "Name and IP required"}), 400
    
    new_id = f"agent-{len(AGENTS)+1}"
    new_agent = {
        "id": new_id,
        "vmid": vmid,
        "name": name,
        "role": role,
        "ip": ip,
        "port": port,
        "vnc_port": vnc_port
    }
    AGENTS.append(new_agent)
    save_agents_config()
    return jsonify({"success": True, "agent": new_agent, "agents": AGENTS})
"""

app_run_search = 'if __name__ == "__main__":'
assert app_run_search in code, "app_run_search not found"
code = code.replace(app_run_search, backend_agents_routes + "\n" + app_run_search)

with open("cockpit_server_v2.py", "w", encoding="utf-8") as f:
    f.write(code)

print("cockpit_server_v2.py generated successfully!")
