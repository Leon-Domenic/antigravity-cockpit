# Script to build cockpit_server_v3.py with Multi-Engine Agent Selection
# (Antigravity, Codex, Hermes Agent, Open Claw, Custom)
import re, json

with open("cockpit_server.py", "r", encoding="utf-8") as f:
    code = f.read()

# 1. Update DEFAULT_AGENTS and load_agents_config
old_agents_block = """DEFAULT_AGENTS = [
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
            print("Failed to load agents_config.json", e)"""

new_agents_block = """DEFAULT_AGENTS = [
    {"id": "agent-1", "vmid": 151, "name": "Agent 1", "type": "antigravity", "role": "Frontend Specialist", "ip": "192.168.178.169", "port": 8000, "vnc_port": 6080},
    {"id": "agent-2", "vmid": 152, "name": "Agent 2", "type": "antigravity", "role": "Backend Specialist",  "ip": "192.168.178.170", "port": 8000, "vnc_port": 6080},
    {"id": "agent-3", "vmid": 153, "name": "Codex",   "type": "codex",       "role": "Code Synthesis & Refactor", "ip": "192.168.178.171", "port": 8000, "vnc_port": 6080},
    {"id": "agent-4", "vmid": 154, "name": "Hermes Agent", "type": "hermes", "role": "Reasoning & Function Calling", "ip": "192.168.178.172", "port": 8000, "vnc_port": 6080},
    {"id": "agent-5", "vmid": 155, "name": "Open Claw", "type": "openclaw",  "role": "Autonomous Web Scraper & Crawler", "ip": "192.168.178.173", "port": 8000, "vnc_port": 6080}
]

AGENTS = list(DEFAULT_AGENTS)

def load_agents_config():
    global AGENTS
    if os.path.exists(AGENTS_CONFIG_FILE):
        try:
            with open(AGENTS_CONFIG_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
                if isinstance(saved, list) and len(saved) > 0:
                    for a in saved:
                        if "type" not in a:
                            a["type"] = "antigravity"
                    AGENTS = saved
        except Exception as e:
            print("Failed to load agents_config.json", e)
    for a in AGENTS:
        if "type" not in a:
            a["type"] = "antigravity" """

assert old_agents_block in code, "old_agents_block not found"
code = code.replace(old_agents_block, new_agents_block)

# 2. Update Dedicated Header: Add #agent-page-engine-badge
old_header_title = """                        <div class="flex items-center gap-3">
                            <h2 class="text-xl font-bold text-white tracking-tight" id="agent-page-title">Agent 1 (Frontend)</h2>
                            <button onclick="openRenameModal(currentView)" class="px-2 py-0.5 border rounded-lg text-xs font-semibold transition flex items-center gap-1.5 text-slate-400 hover:text-white" style="background-color: var(--bg-input); border-color: var(--border-base);" title="Rename Agent & Role">
                                <i class="fa-solid fa-pen-to-square text-slate-400"></i> Rename
                            </button>"""

new_header_title = """                        <div class="flex items-center gap-3">
                            <h2 class="text-xl font-bold text-white tracking-tight" id="agent-page-title">Agent 1 (Frontend)</h2>
                            <span id="agent-page-engine-badge" class="px-2.5 py-0.5 rounded-full text-xs font-semibold border flex items-center gap-1.5" style="background: rgba(99, 102, 241, 0.15); color: #a5b4fc; border-color: rgba(99, 102, 241, 0.35);">
                                <i class="fa-solid fa-atom"></i> Antigravity
                            </span>
                            <button onclick="openRenameModal(currentView)" class="px-2.5 py-0.5 border rounded-lg text-xs font-semibold transition flex items-center gap-1.5 text-slate-300 hover:text-white" style="background-color: var(--bg-input); border-color: var(--border-base);" title="Configure Agent & Engine">
                                <i class="fa-solid fa-pen-to-square text-amber-400"></i> Configure
                            </button>"""

assert old_header_title in code, "old_header_title not found"
code = code.replace(old_header_title, new_header_title)

# 3. Replace Modals HTML
modals_pattern = re.compile(r'<!-- =+\s+-->\s+<!-- RENAME AGENT MODAL.*?<!-- =+\s+-->\s+<!-- SPIN UP / ADD AGENT MODAL.*?</div>\s+</div>\s+</div>', re.DOTALL)

new_modals_html = """    <!-- ============================================================ -->
    <!-- CONFIGURE / RENAME AGENT MODAL                               -->
    <!-- ============================================================ -->
    <div id="rename-agent-modal" class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md hidden">
        <div class="glass w-full max-w-lg rounded-3xl overflow-hidden shadow-2xl flex flex-col border" style="background-color: var(--bg-card); border-color: var(--border-base);">
            <div class="px-6 py-4 border-b flex items-center justify-between" style="background-color: var(--bg-sidebar); border-color: var(--border-base);">
                <div class="flex items-center space-x-3">
                    <div class="w-9 h-9 rounded-xl border flex items-center justify-center text-amber-400 text-base" style="background-color: var(--bg-input); border-color: var(--border-base);">
                        <i class="fa-solid fa-sliders"></i>
                    </div>
                    <div>
                        <h3 class="text-sm font-bold text-white">Configure & Rename Agent</h3>
                        <p class="text-[10px] text-slate-400 font-mono" id="rename-modal-vmid">CT 151</p>
                    </div>
                </div>
                <button onclick="closeRenameModal()" class="w-8 h-8 rounded-xl border flex items-center justify-center text-slate-400 hover:text-white transition" style="background-color: var(--bg-input); border-color: var(--border-base);">
                    <i class="fa-solid fa-xmark"></i>
                </button>
            </div>
            <div class="p-6 space-y-4">
                <!-- Engine Selector -->
                <div>
                    <label class="block text-[11px] font-bold text-slate-400 uppercase tracking-wider mb-2 flex items-center justify-between">
                        <span>Agent Engine / Framework</span>
                        <span class="text-[10px] text-amber-400 font-mono font-normal">Switch Runtime Stack</span>
                    </label>
                    <div class="grid grid-cols-5 gap-2" id="rename-engine-chips">
                        <!-- Populated by JS -->
                    </div>
                </div>
                <div>
                    <label class="block text-[11px] font-bold text-slate-400 uppercase tracking-wider mb-1.5">Agent Display Name</label>
                    <input id="rename-input-name" type="text" placeholder="e.g. Agent 1 or Codex Engine" class="w-full input-box rounded-xl px-3.5 py-2.5 text-xs text-white focus:outline-none focus:border-slate-400">
                </div>
                <div>
                    <label class="block text-[11px] font-bold text-slate-400 uppercase tracking-wider mb-1.5">Specialist Role</label>
                    <input id="rename-input-role" type="text" placeholder="e.g. Frontend Specialist or Code Synthesis" class="w-full input-box rounded-xl px-3.5 py-2.5 text-xs text-white focus:outline-none focus:border-slate-400">
                </div>
                <p class="text-[11px] text-slate-400 leading-relaxed">
                    Updates agent metadata, sidebar identity, and Proxmox description.
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
        <div class="glass w-full max-w-2xl rounded-3xl overflow-hidden shadow-2xl flex flex-col border max-h-[88vh]" style="background-color: var(--bg-card); border-color: var(--border-base);">
            <div class="px-6 py-4 border-b flex items-center justify-between" style="background-color: var(--bg-sidebar); border-color: var(--border-base);">
                <div class="flex items-center space-x-3">
                    <div class="w-9 h-9 rounded-xl border flex items-center justify-center text-emerald-400 text-base" style="background-color: var(--bg-input); border-color: var(--border-base);">
                        <i class="fa-solid fa-plus"></i>
                    </div>
                    <div>
                        <h3 class="text-sm font-bold text-white">Spin Up / Add Agent</h3>
                        <p class="text-[10px] text-slate-400">Choose persona & framework: Antigravity, Codex, Hermes Agent, Open Claw, or Custom</p>
                    </div>
                </div>
                <button onclick="closeAddAgentModal()" class="w-8 h-8 rounded-xl border flex items-center justify-center text-slate-400 hover:text-white transition" style="background-color: var(--bg-input); border-color: var(--border-base);">
                    <i class="fa-solid fa-xmark"></i>
                </button>
            </div>
            
            <div class="p-6 space-y-5 overflow-y-auto scrollbar-thin">
                <!-- STEP 1: Select Engine / Type -->
                <div>
                    <div class="flex justify-between items-center mb-2.5">
                        <h4 class="text-xs font-bold uppercase tracking-wider text-white flex items-center gap-2">
                            <i class="fa-solid fa-layer-group text-indigo-400"></i> Step 1: Select What It Will Be
                        </h4>
                        <span class="text-[10px] text-slate-300 font-mono font-medium" id="selected-engine-badge-preview">Selected: Antigravity</span>
                    </div>
                    <div class="grid grid-cols-2 sm:grid-cols-5 gap-2.5" id="add-engine-cards">
                        <!-- Populated by JS -->
                    </div>
                </div>

                <!-- STEP 2: Choose Target Deployment -->
                <div class="pt-4 border-t space-y-4" style="border-color: var(--border-base);">
                    <!-- Standby Containers Section -->
                    <div>
                        <div class="flex justify-between items-center mb-2.5">
                            <h4 class="text-xs font-bold uppercase tracking-wider text-white flex items-center gap-2">
                                <i class="fa-solid fa-server text-blue-400"></i> Option A: Launch Standby Fleet Container (PVE)
                            </h4>
                            <span class="text-[10px] text-emerald-400 font-mono font-semibold flex items-center gap-1">
                                <i class="fa-solid fa-bolt"></i> ~1.5s Fast Launch
                            </span>
                        </div>
                        <div id="standby-agents-list" class="space-y-2.5">
                            <!-- Populated dynamically with stopped containers -->
                        </div>
                    </div>

                    <!-- Connect New VM or Container Section -->
                    <div class="pt-4 border-t space-y-3" style="border-color: var(--border-base);">
                        <div class="flex justify-between items-center">
                            <h4 class="text-xs font-bold uppercase tracking-wider text-white flex items-center gap-2">
                                <i class="fa-solid fa-network-wired text-purple-400"></i> Option B: Connect Fresh Linux VM or Node
                            </h4>
                            <span class="text-[10px] text-slate-400 font-mono">Any Debian / Ubuntu</span>
                        </div>
                        <div class="p-3.5 rounded-xl border space-y-2" style="background-color: var(--bg-input); border-color: var(--border-base);">
                            <div class="text-[11px] text-slate-300">Run this command inside any fresh VM/container to install the agent stack configured for the chosen engine:</div>
                            <div class="flex items-center gap-2">
                                <input id="dynamic-install-cmd" readonly type="text" value="curl -sSL http://192.168.178.168:3000/install.sh | bash" class="flex-1 input-box rounded-lg px-3 py-2 text-xs font-mono text-amber-300 select-all border" style="background-color: var(--bg-base); border-color: var(--border-base);">
                                <button onclick="navigator.clipboard.writeText(document.getElementById('dynamic-install-cmd').value); alert('Command copied to clipboard!');" class="px-3 py-2 btn-action-primary rounded-lg text-xs font-semibold flex items-center gap-1.5 flex-shrink-0">
                                    <i class="fa-solid fa-copy"></i> Copy
                                </button>
                            </div>
                        </div>

                        <!-- Register Node Form -->
                        <div class="p-4 rounded-xl border space-y-3" style="background-color: var(--bg-sidebar); border-color: var(--border-base);">
                            <span class="text-xs font-semibold text-white">Register Node in Cockpit:</span>
                            <div class="grid grid-cols-1 sm:grid-cols-3 gap-2">
                                <input id="new-agent-name" type="text" placeholder="Agent Name (e.g. Codex-Node)" class="input-box rounded-lg px-3 py-1.5 text-xs text-white">
                                <input id="new-agent-role" type="text" placeholder="Role (e.g. Code Synthesis)" class="input-box rounded-lg px-3 py-1.5 text-xs text-white">
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
            </div>

            <div class="px-6 py-3 border-t flex justify-end" style="background-color: var(--bg-sidebar); border-color: var(--border-base);">
                <button onclick="closeAddAgentModal()" class="px-4 py-1.5 border rounded-xl text-xs font-medium transition" style="background-color: var(--bg-input); border-color: var(--border-base); color: var(--text-main);">
                    Close
                </button>
            </div>
        </div>
    </div>"""

assert modals_pattern.search(code), "modals_pattern not found"
code = modals_pattern.sub(new_modals_html, code)

# 4. Replace DOM builders: from '// 1. Build Sidebar DOM Once' to '// Navigation Switching'
dom_builders_pattern = re.compile(r'// 1\. Build Sidebar DOM Once.*?// Navigation Switching', re.DOTALL)

new_dom_builders = """        // ============================================================
        // AGENT ENGINES & FRAMEWORKS PRESETS
        // ============================================================
        const AGENT_ENGINES = {
            antigravity: {
                id: "antigravity",
                name: "Antigravity",
                fullName: "Google Antigravity",
                icon: "fa-solid fa-atom",
                color: "#818cf8",
                badgeBg: "rgba(99, 102, 241, 0.15)",
                badgeBorder: "rgba(99, 102, 241, 0.35)",
                badgeText: "#a5b4fc",
                defaultRole: "Autonomous Pair Programmer",
                tag: "Google AGY",
                description: "Google Antigravity IDE agent with proactive coding, skills runner, and autonomous CLI workflows."
            },
            codex: {
                id: "codex",
                name: "Codex",
                fullName: "Codex Engine",
                icon: "fa-solid fa-code",
                color: "#10b981",
                badgeBg: "rgba(16, 185, 129, 0.15)",
                badgeBorder: "rgba(16, 185, 129, 0.35)",
                badgeText: "#6ee7b7",
                defaultRole: "Code Synthesis & Refactor",
                tag: "OpenAI Codex",
                description: "Code generation specialist for AST refactoring, unit test suites, and autonomous pull requests."
            },
            hermes: {
                id: "hermes",
                name: "Hermes Agent",
                fullName: "Hermes Agent",
                icon: "fa-solid fa-feather-pointed",
                color: "#f59e0b",
                badgeBg: "rgba(245, 158, 11, 0.15)",
                badgeBorder: "rgba(245, 158, 11, 0.35)",
                badgeText: "#fcd34d",
                defaultRole: "Reasoning & Function Calling",
                tag: "Nous Hermes",
                description: "Nous Research Hermes framework specializing in deep chain-of-thought, tool use, and agentic workflows."
            },
            openclaw: {
                id: "openclaw",
                name: "Open Claw",
                fullName: "Open Claw",
                icon: "fa-solid fa-shield-cat",
                color: "#f43f5e",
                badgeBg: "rgba(244, 63, 94, 0.15)",
                badgeBorder: "rgba(244, 63, 94, 0.35)",
                badgeText: "#fda4af",
                defaultRole: "Autonomous Web Scraper & Crawler",
                tag: "Web Crawler",
                description: "Autonomous browser crawler, DOM scraper, site monitor, and automated web task execution bot."
            },
            custom: {
                id: "custom",
                name: "Custom Node",
                fullName: "Custom Agent Node",
                icon: "fa-solid fa-microchip",
                color: "#38bdf8",
                badgeBg: "rgba(56, 189, 248, 0.15)",
                badgeBorder: "rgba(56, 189, 248, 0.35)",
                badgeText: "#7dd3fc",
                defaultRole: "Specialized Node",
                tag: "Custom VM",
                description: "Custom Linux container, external microservice, or standalone AI agent runner."
            }
        };

        function getAgentEngine(type) {
            if (!type) return AGENT_ENGINES["antigravity"];
            const key = String(type).toLowerCase();
            return AGENT_ENGINES[key] || {
                id: key,
                name: key.charAt(0).toUpperCase() + key.slice(1),
                fullName: key.toUpperCase(),
                icon: "fa-solid fa-microchip",
                color: "#38bdf8",
                badgeBg: "rgba(56, 189, 248, 0.15)",
                badgeBorder: "rgba(56, 189, 248, 0.35)",
                badgeText: "#7dd3fc",
                defaultRole: "Specialized Node",
                tag: "Custom",
                description: "Custom Agent Architecture"
            };
        }

        // 1. Build Sidebar DOM Once
        function buildSidebarDom() {
            const container = document.getElementById("agent-sidebar-list");
            container.innerHTML = "";

            agents.forEach(agent => {
                const eng = getAgentEngine(agent.type);
                const card = document.createElement("div");
                card.id = `side-card-${agent.id}`;
                card.className = "p-3 rounded-xl transition cursor-pointer border flex flex-col space-y-2.5";
                card.style.backgroundColor = "var(--bg-input)";
                card.style.borderColor = "var(--border-base)";
                card.onclick = () => selectView(agent.id);

                card.innerHTML = `
                    <div class="flex justify-between items-start">
                        <div class="flex items-center gap-2">
                            <span id="side-dot-${agent.id}" class="w-2 h-2 rounded-full bg-slate-600"></span>
                            <span class="text-xs font-bold text-white tracking-tight">${escapeHtml(agent.name)}</span>
                        </div>
                        <div class="flex items-center gap-1.5">
                            <span class="text-[9px] px-1.5 py-0.5 rounded font-semibold border flex items-center gap-1" style="background:${eng.badgeBg}; color:${eng.badgeText}; border-color:${eng.badgeBorder};">
                                <i class="${eng.icon} text-[8px]"></i> ${eng.name}
                            </span>
                            <span class="text-[9px] font-mono px-1.5 py-0.5 rounded bg-slate-800 text-slate-400">CT ${agent.vmid}</span>
                        </div>
                    </div>
                    <div class="text-[11px] text-slate-400 truncate">${escapeHtml(agent.role)}</div>
                    <div class="flex justify-between items-center pt-1 border-t text-[10px]" style="border-color: var(--border-base);">
                        <span id="side-ip-${agent.id}" class="text-slate-500 font-mono">${agent.ip}</span>
                        <div onclick="event.stopPropagation()" id="side-power-${agent.id}">
                            <button onclick="toggleAgentPower('${agent.id}', 'start')" class="px-2 py-0.5 rounded bg-emerald-500/10 hover:bg-emerald-500/25 text-emerald-400 border border-emerald-500/20 font-semibold transition" title="Start Container">
                                <i class="fa-solid fa-play mr-1"></i>Start
                            </button>
                        </div>
                    </div>
                `;
                container.appendChild(card);
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
                <span class="text-[9px] text-slate-400 font-mono mt-0.5">Antigravity &bull; Codex &bull; Hermes &bull; Open Claw</span>
            `;
            container.appendChild(addCard);
        }

        // 2. Build Dedicated Iframes Once
        function buildDedicatedIframes() {
            const container = document.getElementById("dedicated-iframes-container");
            container.innerHTML = "";

            agents.forEach(agent => {
                const iframe = document.createElement("iframe");
                iframe.id = `dedicated-frame-${agent.id}`;
                iframe.className = "w-full h-full border-0 hidden";
                iframe.allow = "clipboard-read; clipboard-write; fullscreen";
                iframe.src = `http://${agent.ip}:${agent.vnc_port}/vnc.html?autoconnect=true&resize=scale&reconnect=true`;
                container.appendChild(iframe);
            });
        }

        // 3. Build Overview Screen Cards Once (Strictly 16:9 Aspect Ratio)
        function buildOverviewScreensGrid() {
            const container = document.getElementById("active-screens-grid");
            container.innerHTML = "";

            agents.forEach(agent => {
                const eng = getAgentEngine(agent.type);
                const box = document.createElement("div");
                box.id = `overview-screen-${agent.id}`;
                box.className = "glass rounded-2xl overflow-hidden shadow-2xl flex flex-col hidden";
                box.innerHTML = `
                    <div class="px-4 py-2.5 flex justify-between items-center border-b" style="background-color: var(--bg-sidebar); border-color: var(--border-base);">
                        <div class="flex items-center space-x-2">
                            <span id="overview-dot-${agent.id}" class="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse"></span>
                            <span class="text-xs font-bold text-white">${escapeHtml(agent.name)}</span>
                            <span class="text-[9px] px-1.5 py-0.5 rounded font-semibold border flex items-center gap-1" style="background:${eng.badgeBg}; color:${eng.badgeText}; border-color:${eng.badgeBorder};">
                                <i class="${eng.icon} text-[8px]"></i> ${eng.name}
                            </span>
                            <span class="text-[10px] text-slate-400 font-mono">${agent.ip}</span>
                        </div>
                        <div class="flex items-center gap-2">
                            <span class="text-[10px] font-mono px-1.5 py-0.5 rounded border text-slate-400" style="border-color: var(--border-base);">16:9</span>
                            <button onclick="selectView('${agent.id}')" class="px-2.5 py-1 rounded-lg text-[11px] font-medium transition flex items-center gap-1 border" style="background: var(--badge-bg); color: var(--badge-text); border-color: var(--border-base);">
                                <i class="fa-solid fa-expand"></i> Open Page
                            </button>
                            <a href="http://${agent.ip}:${agent.vnc_port}/vnc.html?autoconnect=true&resize=scale" target="_blank" class="text-slate-400 hover:text-white p-1 text-xs" title="Pop out">
                                <i class="fa-solid fa-arrow-up-right-from-square"></i>
                            </a>
                        </div>
                    </div>
                    <div class="w-full aspect-16-9 bg-black overflow-hidden">
                        <iframe src="http://${agent.ip}:${agent.vnc_port}/vnc.html?autoconnect=true&resize=scale&reconnect=true" class="w-full h-full border-0" allow="clipboard-read; clipboard-write; fullscreen"></iframe>
                    </div>
                `;
                container.appendChild(box);
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
                <p class="text-xs text-slate-400 font-mono mt-1">Antigravity &bull; Codex &bull; Hermes Agent &bull; Open Claw</p>
            `;
            container.appendChild(addOverviewCard);
        }

        // 4. Build Fleet Status Table
        function buildFleetTableDom() {
            const tbody = document.getElementById("fleet-table-body");
            tbody.innerHTML = "";

            agents.forEach(agent => {
                const eng = getAgentEngine(agent.type);
                const tr = document.createElement("tr");
                tr.id = `table-row-${agent.id}`;
                tr.className = "hover:bg-white/5 transition cursor-pointer";
                tr.onclick = () => selectView(agent.id);

                tr.innerHTML = `
                    <td class="p-3.5 font-bold text-white">
                        <div class="flex items-center gap-2">
                            <span>${escapeHtml(agent.name)}</span>
                            <span class="text-[9px] px-1.5 py-0.5 rounded font-semibold border inline-flex items-center gap-1" style="background:${eng.badgeBg}; color:${eng.badgeText}; border-color:${eng.badgeBorder};">
                                <i class="${eng.icon} text-[8px]"></i> ${eng.name}
                            </span>
                        </div>
                        <div class="text-slate-400 text-[11px] font-normal">${escapeHtml(agent.role)}</div>
                    </td>
                    <td class="p-3.5 text-slate-300 font-mono">${agent.vmid}</td>
                    <td class="p-3.5 text-slate-300 font-mono">${agent.ip}</td>
                    <td class="p-3.5" id="table-power-${agent.id}">
                        <span class="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-slate-600/10 text-slate-400 border border-slate-600/20">
                            <span class="w-1.5 h-1.5 rounded-full bg-slate-500"></span> Stopped
                        </span>
                    </td>
                    <td class="p-3.5 text-slate-300 font-mono" id="table-metrics-${agent.id}">-- | --</td>
                    <td class="p-3.5" id="table-auth-${agent.id}">
                        <span class="text-[10px] px-2 py-0.5 rounded-full font-medium bg-amber-500/10 text-amber-400 border border-amber-500/20">
                            ⚠️ Needs Auth
                        </span>
                    </td>
                    <td class="p-3.5 text-right space-x-2" onclick="event.stopPropagation()">
                        <button onclick="openRenameModal('${agent.id}')" class="px-2 py-1 border rounded-lg text-xs transition text-slate-400 hover:text-white" style="background-color: var(--bg-input); border-color: var(--border-base);" title="Configure">
                            <i class="fa-solid fa-pen-to-square"></i>
                        </button>
                        <button onclick="selectView('${agent.id}')" class="px-2.5 py-1 border rounded-lg text-xs transition" style="background-color: var(--bg-input); border-color: var(--border-base); color: var(--text-main);">
                            Page
                        </button>
                        <span id="table-action-${agent.id}">
                            <button onclick="toggleAgentPower('${agent.id}', 'start')" class="px-2.5 py-1 bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 border border-emerald-500/20 rounded-lg text-xs transition">
                                Start
                            </button>
                        </span>
                    </td>
                `;
                tbody.appendChild(tr);
            });
        }

        // Navigation Switching"""

assert dom_builders_pattern.search(code), "dom_builders_pattern not found"
code = dom_builders_pattern.sub(new_dom_builders, code)

# 5. Update updateDedicatedAgentLabels in JavaScript
dedicated_labels_pattern = re.compile(r'function updateDedicatedAgentLabels\(agentId\) \{.*?document\.getElementById\("agent-page-title"\)\.innerText = `\$\{agent\.name\} \(\$\{agent\.role\}\)`;.*?document\.getElementById\("agent-page-vmid"\)\.innerText = agent\.vmid;', re.DOTALL)

new_dedicated_labels_prefix = """function updateDedicatedAgentLabels(agentId) {
            const agent = agents.find(a => a.id === agentId);
            if (!agent) return;

            const eng = getAgentEngine(agent.type);
            const info = fleetStatuses[agentId] || { power: "unknown", status: "checking", authenticated: false, metrics: {} };
            const isRunning = info.power === "running";

            document.getElementById("agent-page-title").innerText = `${agent.name} (${agent.role})`;
            
            const pageIcon = document.getElementById("agent-page-icon");
            if (pageIcon) {
                pageIcon.innerHTML = `<i class="${eng.icon}"></i>`;
                pageIcon.style.color = eng.color;
            }
            const engBadge = document.getElementById("agent-page-engine-badge");
            if (engBadge) {
                engBadge.style.backgroundColor = eng.badgeBg;
                engBadge.style.borderColor = eng.badgeBorder;
                engBadge.style.color = eng.badgeText;
                engBadge.innerHTML = `<i class="${eng.icon}"></i> ${eng.fullName || eng.name}`;
            }

            document.getElementById("agent-page-vmid").innerText = agent.vmid;"""

assert dedicated_labels_pattern.search(code), "dedicated_labels_pattern not found"
code = dedicated_labels_pattern.sub(new_dedicated_labels_prefix, code)

# 6. Replace Rename & Add Client Logic: from '// ============================================================\n        // RENAME & ADD AGENT CLIENT LOGIC' to 'window.onload = init;'
rename_add_client_pattern = re.compile(r'// =+\s+// RENAME & ADD AGENT CLIENT LOGIC.*?window\.onload = init;', re.DOTALL)

new_rename_add_client_code = """        // ============================================================
        // RENAME & CONFIGURE CLIENT LOGIC
        // ============================================================
        let targetRenameId = null;
        let selectedRenameEngine = "antigravity";

        function renderRenameEngineChips() {
            const container = document.getElementById("rename-engine-chips");
            if (!container) return;

            container.innerHTML = Object.values(AGENT_ENGINES).map(eng => {
                const isSel = selectedRenameEngine === eng.id;
                const borderStyle = isSel ? `border: 2px solid #f59e0b;` : `border: 1px solid var(--border-base); opacity: 0.7;`;
                const bgStyle = isSel ? `background-color: rgba(245, 158, 11, 0.1);` : `background-color: var(--bg-input);`;

                return `
                    <div onclick="selectRenameEngine('${eng.id}')" class="p-2 rounded-xl cursor-pointer transition flex flex-col items-center text-center hover:opacity-100" style="${borderStyle} ${bgStyle}">
                        <div class="w-6 h-6 rounded-lg flex items-center justify-center text-xs mb-1" style="background-color: ${eng.badgeBg}; color: ${eng.color}; border: 1px solid ${eng.badgeBorder};">
                            <i class="${eng.icon}"></i>
                        </div>
                        <span class="text-[10px] font-bold text-white truncate w-full">${eng.name}</span>
                    </div>
                `;
            }).join("");
        }

        function selectRenameEngine(engineId) {
            selectedRenameEngine = engineId;
            renderRenameEngineChips();
            const eng = getAgentEngine(engineId);
            const roleInput = document.getElementById("rename-input-role");
            if (roleInput && (!roleInput.value || Object.values(AGENT_ENGINES).some(e => e.defaultRole === roleInput.value))) {
                roleInput.value = eng.defaultRole;
            }
        }

        function openRenameModal(agentId) {
            const agent = agents.find(a => a.id === agentId);
            if (!agent) return;
            targetRenameId = agentId;
            selectedRenameEngine = agent.type || "antigravity";
            document.getElementById("rename-modal-vmid").innerText = `CT ${agent.vmid} (${agent.ip})`;
            document.getElementById("rename-input-name").value = agent.name;
            document.getElementById("rename-input-role").value = agent.role;
            renderRenameEngineChips();
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
                        role: newRole,
                        type: selectedRenameEngine
                    })
                });
                const data = await res.json();
                if (data.success) {
                    const agent = agents.find(a => a.id === targetRenameId);
                    if (agent) {
                        agent.name = newName;
                        agent.role = newRole;
                        agent.type = selectedRenameEngine;
                    }

                    if (currentView === targetRenameId) {
                        updateDedicatedAgentLabels(targetRenameId);
                    }
                    
                    buildSidebarDom();
                    buildOverviewScreensGrid();
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

        // ============================================================
        // ADD / SPIN UP AGENT CLIENT LOGIC (MULTI-ENGINE)
        // ============================================================
        let selectedAddEngine = "antigravity";

        function renderAddEngineCards() {
            const container = document.getElementById("add-engine-cards");
            if (!container) return;

            container.innerHTML = Object.values(AGENT_ENGINES).map(eng => {
                const isSel = selectedAddEngine === eng.id;
                const borderStyle = isSel ? `border: 2px solid #f59e0b; box-shadow: 0 0 15px rgba(245, 158, 11, 0.2);` : `border: 1px solid var(--border-base); opacity: 0.75;`;
                const bgStyle = isSel ? `background-color: var(--bg-card);` : `background-color: var(--bg-input);`;

                return `
                    <div onclick="selectAddEngine('${eng.id}')" class="p-2.5 rounded-xl cursor-pointer transition flex flex-col items-center text-center hover:opacity-100 group" style="${borderStyle} ${bgStyle}">
                        <div class="w-9 h-9 rounded-xl flex items-center justify-center text-sm mb-1.5 group-hover:scale-110 transition" style="background-color: ${eng.badgeBg}; color: ${eng.color}; border: 1px solid ${eng.badgeBorder};">
                            <i class="${eng.icon}"></i>
                        </div>
                        <span class="text-xs font-bold text-white">${eng.name}</span>
                        <span class="text-[9px] text-slate-400 font-mono mt-0.5">${eng.tag}</span>
                    </div>
                `;
            }).join("");

            const preview = document.getElementById("selected-engine-badge-preview");
            if (preview) {
                const eng = getAgentEngine(selectedAddEngine);
                preview.innerHTML = `Selected: <span class="font-bold text-amber-400">${eng.name}</span> (${eng.defaultRole})`;
            }

            const cmdInput = document.getElementById("dynamic-install-cmd");
            if (cmdInput) {
                cmdInput.value = `curl -sSL http://192.168.178.168:3000/install.sh | bash -s -- --engine ${selectedAddEngine}`;
            }

            const nameInput = document.getElementById("new-agent-name");
            const roleInput = document.getElementById("new-agent-role");
            if (nameInput && roleInput) {
                const eng = getAgentEngine(selectedAddEngine);
                nameInput.placeholder = `e.g. ${eng.name}-Node`;
                roleInput.placeholder = `e.g. ${eng.defaultRole}`;
            }

            renderStandbyList();
        }

        function selectAddEngine(engineId) {
            selectedAddEngine = engineId;
            renderAddEngineCards();
        }

        function renderStandbyList() {
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
        }

        function openAddAgentModal() {
            const modal = document.getElementById("add-agent-modal");
            if (!modal) return;
            renderAddEngineCards();
            modal.classList.remove("hidden");
        }

        function closeAddAgentModal() {
            document.getElementById("add-agent-modal").classList.add("hidden");
        }

        async function quickSpinUpStandby(agentId, engineId, name, role) {
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
        }

        async function registerNewCustomAgent() {
            const name = document.getElementById("new-agent-name").value.trim();
            const curEngine = getAgentEngine(selectedAddEngine);
            const role = document.getElementById("new-agent-role").value.trim() || curEngine.defaultRole;
            const ip = document.getElementById("new-agent-ip").value.trim();

            if (!name || !ip) return alert("Please provide Agent Name and IP address");

            try {
                const res = await fetch("/api/agents/add", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        name: name,
                        role: role,
                        ip: ip,
                        type: selectedAddEngine
                    })
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

        window.onload = init;"""

assert rename_add_client_pattern.search(code), "rename_add_client_pattern not found"
code = rename_add_client_pattern.sub(new_rename_add_client_code, code)

# 7. Update backend routes /api/agents/rename and /api/agents/add
backend_routes_search = """@app.route("/api/agents/rename", methods=["POST"])
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
    return jsonify({"success": True, "agent": new_agent, "agents": AGENTS})"""

backend_routes_replace = """@app.route("/api/agents/rename", methods=["POST"])
def rename_agent_route():
    data = request.json or {}
    agent_id = data.get("agent_id") or data.get("id")
    new_name = (data.get("name") or "").strip()
    new_role = (data.get("role") or "").strip()
    new_type = (data.get("type") or data.get("engine") or "").strip().lower()
    agent = next((a for a in AGENTS if a["id"] == agent_id), None)
    if not agent:
        return jsonify({"error": "Agent not found"}), 404
    if new_name:
        agent["name"] = new_name
    if new_role:
        agent["role"] = new_role
    if new_type:
        agent["type"] = new_type
    save_agents_config()
    
    # Optionally update Proxmox LXC description
    try:
        eng_label = agent.get("type", "antigravity").title()
        requests.put(
            f"{PROXMOX_API}/nodes/pve/lxc/{agent['vmid']}/config",
            headers={"Authorization": PROXMOX_TOKEN},
            json={"description": f"{eng_label} Agent: {agent['name']} ({agent['role']})"},
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
    agent_type = (data.get("type") or data.get("engine") or "antigravity").strip().lower()
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
        "type": agent_type,
        "role": role,
        "ip": ip,
        "port": port,
        "vnc_port": vnc_port
    }
    AGENTS.append(new_agent)
    save_agents_config()
    return jsonify({"success": True, "agent": new_agent, "agents": AGENTS})"""

assert backend_routes_search in code, "backend_routes_search not found"
code = code.replace(backend_routes_search, backend_routes_replace)

with open("cockpit_server_v3.py", "w", encoding="utf-8") as f:
    f.write(code)

print("cockpit_server_v3.py generated successfully!")
