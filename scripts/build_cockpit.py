# Build script to cleanly inject Skills Manager into cockpit_server.py
import re

with open("cockpit_server.py", "r", encoding="utf-8") as f:
    code = f.read()

# 1. Update imports and add constants
top_import = """import os, sys, json, time, requests, subprocess, base64, io, tarfile
from flask import Flask, request, jsonify, render_template_string

app = Flask(__name__)

PROXMOX_HOST = "192.168.178.105"
PROXMOX_TOKEN = "PVEAPIToken=root@pam!cockpit-token=c58599c3-09ea-4d68-983e-0bfd1dcb212c"
PROXMOX_API = f"https://{PROXMOX_HOST}:8006/api2/json"

SKILLS_LIB_DIR = "/usr/local/share/cockpit/skills_library"
SKILLS_ARCHIVE_PATH = "/usr/local/share/cockpit/cockpit-skills-library.tar.gz"
CACHED_SKILLS = []

def get_library_skills():
    global CACHED_SKILLS
    if CACHED_SKILLS:
        return CACHED_SKILLS
    
    skills = []
    if os.path.exists(SKILLS_LIB_DIR):
        for d in sorted(os.listdir(SKILLS_LIB_DIR)):
            p = os.path.join(SKILLS_LIB_DIR, d)
            if os.path.isdir(p):
                md = os.path.join(p, 'SKILL.md')
                if os.path.exists(md):
                    desc = "No description available"
                    try:
                        with open(md, "r", encoding="utf-8", errors="ignore") as f:
                            lines = f.readlines()
                            for i, line in enumerate(lines[:35]):
                                if line.strip().startswith("description:"):
                                    val = line.split(":", 1)[1].strip().replace('"', '').replace("'", "")
                                    desc_lines = [val] if val else []
                                    for next_line in lines[i+1:i+10]:
                                        if next_line.startswith("  ") or next_line.startswith("\t"):
                                            desc_lines.append(next_line.strip().replace('"', '').replace("'", ""))
                                        elif next_line.strip().startswith("---") or (":" in next_line and not next_line.startswith(" ")):
                                            break
                                    desc = " ".join(desc_lines).strip()
                                    break
                    except Exception:
                        pass
                    
                    cat = "Core & Workflows"
                    if d.startswith("convex"):
                        cat = "Convex Backend"
                    elif d.startswith("clerk"):
                        cat = "Clerk Auth"
                    elif any(k in d for k in ["bigquery", "dataform", "dbt", "gcp", "spark", "composer", "ml", "notebook", "discovering-gcp", "building-data", "data-autocleaning", "developing-with"]):
                        cat = "Cloud & Data Pipelines"
                    elif any(k in d for k in ["test", "debugging", "chrome", "repair", "accidental", "gcloud-auth"]):
                        cat = "Testing & DevTools"

                    skills.append({
                        "id": d,
                        "name": d,
                        "category": cat,
                        "description": desc[:220] + ("..." if len(desc) > 220 else "")
                    })
    CACHED_SKILLS = skills
    return CACHED_SKILLS
"""

code = re.sub(
    r'import os, sys, json, time, requests, subprocess\s+from flask import Flask, request, jsonify, render_template_string\s+app = Flask\(__name__\)\s+PROXMOX_HOST = "192\.168\.178\.105"\s+PROXMOX_TOKEN = "PVEAPIToken=root@pam!cockpit-token=c58599c3-09ea-4d68-983e-0bfd1dcb212c"\s+PROXMOX_API = f"https://\{PROXMOX_HOST\}:8006/api2/json"',
    top_import.strip(),
    code
)

# 2. Add Skills Hub button in Sidebar
sidebar_search = """        <!-- Fleet Overview Tab Button -->
        <div class="p-3 border-b" style="border-color: var(--border-base);">
            <button onclick="selectView('overview')" id="nav-btn-overview" class="w-full flex items-center justify-between px-3.5 py-2.5 rounded-xl transition text-xs font-semibold border" style="border-color: var(--border-base); background-color: var(--bg-card); color: var(--text-main);">
                <div class="flex items-center gap-2.5">
                    <i class="fa-solid fa-network-wired" style="color: var(--highlight-text);"></i>
                    <span>Fleet Overview (All Active)</span>
                </div>
                <span id="active-count-badge" class="px-2 py-0.5 rounded-full text-[10px] font-bold font-mono" style="background: var(--badge-bg); color: var(--badge-text);">
                    -- Active
                </span>
            </button>
        </div>"""

sidebar_replace = """        <!-- Fleet Overview Tab Button -->
        <div class="p-3 border-b space-y-2" style="border-color: var(--border-base);">
            <button onclick="selectView('overview')" id="nav-btn-overview" class="w-full flex items-center justify-between px-3.5 py-2.5 rounded-xl transition text-xs font-semibold border" style="border-color: var(--border-base); background-color: var(--bg-card); color: var(--text-main);">
                <div class="flex items-center gap-2.5">
                    <i class="fa-solid fa-network-wired" style="color: var(--highlight-text);"></i>
                    <span>Fleet Overview (All Active)</span>
                </div>
                <span id="active-count-badge" class="px-2 py-0.5 rounded-full text-[10px] font-bold font-mono" style="background: var(--badge-bg); color: var(--badge-text);">
                    -- Active
                </span>
            </button>
            <button onclick="openSkillsModal()" id="nav-btn-skills" class="w-full flex items-center justify-between px-3.5 py-2 rounded-xl transition text-xs font-semibold border" style="border-color: var(--border-base); background-color: var(--bg-input); color: var(--text-main);" title="Manage & Inject Agent Skills">
                <div class="flex items-center gap-2.5">
                    <i class="fa-solid fa-boxes-stacked text-amber-400"></i>
                    <span>Skills Hub</span>
                </div>
                <span class="px-2 py-0.5 rounded-full text-[10px] font-bold font-mono border" style="background: var(--badge-bg); color: var(--badge-text); border-color: var(--border-base);">
                    72 Library
                </span>
            </button>
        </div>"""

assert sidebar_search in code, "Sidebar search string not found"
code = code.replace(sidebar_search, sidebar_replace)

# 3. Add Skills button in Dedicated Header
header_search = """                    <button onclick="restartAgentDesktop()" class="px-3 py-2 border rounded-xl text-xs font-medium transition flex items-center gap-1.5" style="background-color: var(--bg-input); border-color: var(--border-base); color: var(--text-main);" title="Restart x11vnc & Antigravity">
                        <i class="fa-solid fa-window-restore"></i> Reset GUI
                    </button>"""

header_replace = """                    <button onclick="restartAgentDesktop()" class="px-3 py-2 border rounded-xl text-xs font-medium transition flex items-center gap-1.5" style="background-color: var(--bg-input); border-color: var(--border-base); color: var(--text-main);" title="Restart x11vnc & Antigravity">
                        <i class="fa-solid fa-window-restore"></i> Reset GUI
                    </button>
                    <button onclick="openSkillsModalForCurrentAgent()" class="px-3 py-2 border rounded-xl text-xs font-medium transition flex items-center gap-1.5" style="background-color: var(--bg-input); border-color: var(--border-base); color: var(--text-main);" title="Manage Agent Skills">
                        <i class="fa-solid fa-boxes-stacked text-amber-400"></i>
                        <span id="agent-page-skills-badge">Skills</span>
                    </button>"""

assert header_search in code, "Header search string not found"
code = code.replace(header_search, header_replace)

# 4. Add Active Skills card beneath Auth Manager
auth_box_search = """                    <!-- Auth Manager Box Beneath Screen -->
                    <div class="glass rounded-2xl p-4 space-y-3">
                        <div class="flex justify-between items-center">
                            <h3 class="text-xs font-semibold text-white uppercase tracking-wider flex items-center gap-2">
                                <i class="fa-solid fa-key text-amber-400"></i> Google AI Pro Auth Manager
                            </h3>
                            <span id="auth-status-pill" class="text-[10px] px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-400 font-mono">Active</span>
                        </div>
                        <p class="text-[11px] text-slate-400 leading-relaxed">
                            Sign in visually via Google in the desktop screen above, or paste an OAuth token JSON below to inject credentials into this agent's <code class="text-slate-300 font-mono">~/.gemini/</code>:
                        </p>
                        <div class="flex gap-2">
                            <input id="dedicated-token-input" type="text" placeholder='{"token": {"access_token": "ya29...", "refresh_token": "..."}}' class="flex-1 input-box rounded-xl px-3 py-2 text-xs font-mono focus:outline-none focus:border-amber-500">
                            <button onclick="saveDedicatedAuthToken()" class="px-4 py-2 bg-amber-600/20 hover:bg-amber-600/30 text-amber-300 border border-amber-500/30 font-semibold rounded-xl text-xs transition flex items-center gap-1.5 flex-shrink-0">
                                <i class="fa-solid fa-floppy-disk"></i> Apply Token
                            </button>
                        </div>
                    </div>
                </div>"""

auth_box_replace = """                    <!-- Auth Manager Box Beneath Screen -->
                    <div class="glass rounded-2xl p-4 space-y-3">
                        <div class="flex justify-between items-center">
                            <h3 class="text-xs font-semibold text-white uppercase tracking-wider flex items-center gap-2">
                                <i class="fa-solid fa-key text-amber-400"></i> Google AI Pro Auth Manager
                            </h3>
                            <span id="auth-status-pill" class="text-[10px] px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-400 font-mono">Active</span>
                        </div>
                        <p class="text-[11px] text-slate-400 leading-relaxed">
                            Sign in visually via Google in the desktop screen above, or paste an OAuth token JSON below to inject credentials into this agent's <code class="text-slate-300 font-mono">~/.gemini/</code>:
                        </p>
                        <div class="flex gap-2">
                            <input id="dedicated-token-input" type="text" placeholder='{"token": {"access_token": "ya29...", "refresh_token": "..."}}' class="flex-1 input-box rounded-xl px-3 py-2 text-xs font-mono focus:outline-none focus:border-amber-500">
                            <button onclick="saveDedicatedAuthToken()" class="px-4 py-2 bg-amber-600/20 hover:bg-amber-600/30 text-amber-300 border border-amber-500/30 font-semibold rounded-xl text-xs transition flex items-center gap-1.5 flex-shrink-0">
                                <i class="fa-solid fa-floppy-disk"></i> Apply Token
                            </button>
                        </div>
                    </div>

                    <!-- Skills & Capabilities Card Beneath Auth Manager -->
                    <div class="glass rounded-2xl p-4 space-y-3">
                        <div class="flex justify-between items-center">
                            <h3 class="text-xs font-semibold text-white uppercase tracking-wider flex items-center gap-2">
                                <i class="fa-solid fa-puzzle-piece text-amber-400"></i> Agent Capabilities & Skills
                            </h3>
                            <span id="dedicated-skills-pill" class="text-[10px] px-2 py-0.5 rounded font-mono border" style="background: var(--badge-bg); color: var(--badge-text); border-color: var(--border-base);">Loading...</span>
                        </div>
                        <p class="text-[11px] text-slate-400 leading-relaxed">
                            Active specialized capabilities loaded into this agent's environment (<code class="text-slate-300 font-mono">~/.gemini/skills/</code>):
                        </p>
                        <div id="dedicated-skills-preview-list" class="flex flex-wrap gap-1.5 min-h-[32px] items-center">
                            <span class="text-xs text-slate-500 italic">Checking installed capabilities...</span>
                        </div>
                        <div class="flex items-center justify-between pt-2 border-t" style="border-color: var(--border-base);">
                            <span class="text-[10px] text-slate-500 font-mono">72 Enterprise skills in library</span>
                            <div class="flex items-center gap-2">
                                <button onclick="syncAllSkillsToTarget(currentView)" class="px-3 py-1.5 rounded-xl text-xs font-semibold transition flex items-center gap-1.5 border" style="background-color: var(--bg-input); border-color: var(--border-base); color: var(--text-main);" title="Sync all 72 skills to this agent">
                                    <i class="fa-solid fa-bolt text-amber-400"></i> Sync Full Library
                                </button>
                                <button onclick="openSkillsModalForCurrentAgent()" class="px-3 py-1.5 btn-action-primary font-semibold rounded-xl text-xs transition shadow-lg flex items-center gap-1.5">
                                    <i class="fa-solid fa-boxes-stacked"></i> Manage Skills
                                </button>
                            </div>
                        </div>
                    </div>
                </div>"""

assert auth_box_search in code, "Auth box search string not found"
code = code.replace(auth_box_search, auth_box_replace)

# 5. Add Modal before </main>
modal_html = """    <!-- ============================================================ -->
    <!-- SKILLS HUB MODAL                                             -->
    <!-- ============================================================ -->
    <div id="skills-hub-modal" class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md hidden">
        <div class="glass w-full max-w-5xl rounded-3xl overflow-hidden shadow-2xl flex flex-col max-h-[90vh] border" style="background-color: var(--bg-card); border-color: var(--border-base);">
            
            <!-- Modal Header -->
            <div class="px-6 py-4 border-b flex flex-wrap items-center justify-between gap-3 flex-shrink-0" style="background-color: var(--bg-sidebar); border-color: var(--border-base);">
                <div class="flex items-center space-x-3">
                    <div class="w-10 h-10 rounded-xl border flex items-center justify-center text-amber-400 text-lg shadow-inner" style="background-color: var(--bg-input); border-color: var(--border-base);">
                        <i class="fa-solid fa-boxes-stacked"></i>
                    </div>
                    <div>
                        <h2 class="text-base font-bold text-white tracking-tight flex items-center gap-2">
                            Skills Hub & Capability Matrix
                            <span class="px-2 py-0.5 rounded-full text-[10px] font-mono border" style="background: var(--badge-bg); color: var(--badge-text); border-color: var(--border-base);">72 Pre-Packaged</span>
                        </h2>
                        <p class="text-xs text-slate-400">Load backend frameworks, auth providers, cloud pipelines, and custom capabilities into Antigravity agents</p>
                    </div>
                </div>

                <!-- Target Agent Selector & Close Button -->
                <div class="flex items-center gap-3">
                    <div class="flex items-center gap-2 px-3 py-1.5 rounded-xl border" style="background-color: var(--bg-input); border-color: var(--border-base);">
                        <span class="text-[11px] font-semibold text-slate-400"><i class="fa-solid fa-robot mr-1 text-slate-500"></i> Target:</span>
                        <select id="skills-target-select" onchange="onSkillsTargetChanged()" class="bg-transparent text-xs font-semibold text-white focus:outline-none cursor-pointer">
                            <option value="agent-1" class="bg-slate-900 text-white">Agent 1 (Frontend)</option>
                            <option value="agent-2" class="bg-slate-900 text-white">Agent 2 (Backend)</option>
                            <option value="agent-3" class="bg-slate-900 text-white">Agent 3 (Fullstack)</option>
                            <option value="agent-4" class="bg-slate-900 text-white">Agent 4 (QA Automation)</option>
                            <option value="agent-5" class="bg-slate-900 text-white">Agent 5 (Architect)</option>
                            <option value="broadcast" class="bg-slate-900 text-amber-300 font-bold">⚡ All Active Agents (Fleet)</option>
                        </select>
                    </div>
                    <button onclick="closeSkillsModal()" class="w-8 h-8 rounded-xl border flex items-center justify-center text-slate-400 hover:text-white transition" style="background-color: var(--bg-input); border-color: var(--border-base);">
                        <i class="fa-solid fa-xmark"></i>
                    </button>
                </div>
            </div>

            <!-- Modal Subheader / Quick Actions Banner -->
            <div class="px-6 py-3 border-b flex flex-wrap items-center justify-between gap-3 text-xs flex-shrink-0" style="border-color: var(--border-base); background-color: rgba(0,0,0,0.25);">
                <div class="flex items-center gap-4 text-slate-400 font-mono text-[11px]">
                    <span><i class="fa-solid fa-database text-cyan-400 mr-1"></i> Convex: <span class="text-white">30</span></span>
                    <span><i class="fa-solid fa-shield-halved text-emerald-400 mr-1"></i> Clerk: <span class="text-white">20</span></span>
                    <span><i class="fa-solid fa-cloud text-blue-400 mr-1"></i> Cloud & GCP: <span class="text-white">12</span></span>
                    <span><i class="fa-solid fa-vial text-purple-400 mr-1"></i> DevTools: <span class="text-white">5</span></span>
                    <span><i class="fa-solid fa-gears text-amber-400 mr-1"></i> Core: <span class="text-white">5</span></span>
                </div>
                <div class="flex items-center gap-2">
                    <button onclick="syncAllSkillsToTarget()" id="btn-sync-all-modal" class="px-3.5 py-1.5 btn-action-primary rounded-xl text-xs font-semibold flex items-center gap-1.5 shadow-lg transition">
                        <i class="fa-solid fa-bolt text-amber-300"></i> Sync Entire 72-Skill Library
                    </button>
                </div>
            </div>

            <!-- Tabs Navigation -->
            <div class="px-6 pt-3 border-b flex items-center gap-2 flex-shrink-0" style="border-color: var(--border-base);">
                <button onclick="switchSkillsTab('library')" id="tab-btn-library" class="px-4 py-2 border-b-2 text-xs font-bold transition flex items-center gap-2" style="border-color: var(--accent-primary); color: var(--highlight-text);">
                    <i class="fa-solid fa-book-bookmark"></i> Skills Library (72)
                </button>
                <button onclick="switchSkillsTab('installed')" id="tab-btn-installed" class="px-4 py-2 border-b-2 border-transparent text-xs font-bold transition text-slate-400 hover:text-white flex items-center gap-2">
                    <i class="fa-solid fa-circle-check"></i> Active on Agent <span id="installed-count-pill" class="px-1.5 py-0.2 rounded-full text-[10px] font-mono bg-slate-800 text-slate-300">0</span>
                </button>
                <button onclick="switchSkillsTab('custom')" id="tab-btn-custom" class="px-4 py-2 border-b-2 border-transparent text-xs font-bold transition text-slate-400 hover:text-white flex items-center gap-2">
                    <i class="fa-solid fa-pen-nib"></i> Create Custom Skill
                </button>
            </div>

            <!-- Tab 1: Library Content -->
            <div id="skills-tab-library" class="flex-1 overflow-y-auto p-6 space-y-4 scrollbar-thin">
                <!-- Search & Filters -->
                <div class="flex flex-col sm:flex-row gap-3 items-stretch sm:items-center justify-between">
                    <div class="relative flex-1">
                        <i class="fa-solid fa-magnifying-glass absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400 text-xs"></i>
                        <input id="skills-search-input" oninput="filterSkillsDisplay()" type="text" placeholder="Search skills by keyword, framework, or title (e.g. clerk, convex, oauth, bigquery, stripe)..." class="w-full input-box rounded-xl pl-9 pr-4 py-2 text-xs focus:outline-none focus:border-slate-400">
                    </div>
                    <div class="flex flex-wrap gap-1.5" id="skills-cat-pills">
                        <!-- Populated by JS -->
                    </div>
                </div>

                <!-- Skills Cards Grid -->
                <div id="skills-cards-grid" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3.5 pt-1">
                    <!-- Populated dynamically -->
                </div>
            </div>

            <!-- Tab 2: Installed on Agent Content -->
            <div id="skills-tab-installed" class="flex-1 overflow-y-auto p-6 space-y-4 scrollbar-thin hidden">
                <div class="flex justify-between items-center pb-2 border-b" style="border-color: var(--border-base);">
                    <div>
                        <h3 class="text-xs font-bold uppercase tracking-wider text-white flex items-center gap-2">
                            Capabilities Installed on <span id="installed-agent-label" class="text-amber-400">Agent 1</span>
                        </h3>
                        <p class="text-[11px] text-slate-400">All skills detected in the agent's <code class="text-slate-300 font-mono">~/.gemini/skills/</code> and builtin environments</p>
                    </div>
                    <button onclick="refreshTargetInstalledSkills(true)" class="px-3 py-1.5 border rounded-xl text-xs font-medium transition flex items-center gap-1.5" style="background-color: var(--bg-input); border-color: var(--border-base); color: var(--text-main);">
                        <i class="fa-solid fa-rotate-right" id="installed-refresh-icon"></i> Refresh
                    </button>
                </div>

                <div id="installed-skills-list" class="grid grid-cols-1 md:grid-cols-2 gap-3 pt-1">
                    <!-- Populated dynamically -->
                </div>
            </div>

            <!-- Tab 3: Create Custom Skill Content -->
            <div id="skills-tab-custom" class="flex-1 overflow-y-auto p-6 space-y-4 scrollbar-thin hidden">
                <div class="space-y-1 pb-2 border-b" style="border-color: var(--border-base);">
                    <h3 class="text-xs font-bold uppercase tracking-wider text-white">Create & Inject Custom Capability</h3>
                    <p class="text-[11px] text-slate-400">Define custom instructions, system rules, workflows, or project conventions to inject into Antigravity agents</p>
                </div>

                <div class="space-y-3">
                    <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
                        <div>
                            <label class="block text-[11px] font-bold text-slate-400 uppercase tracking-wider mb-1">Skill Identifier (Slug)</label>
                            <input id="custom-skill-name" type="text" placeholder="e.g. monorepo-deployment-guard" class="w-full input-box rounded-xl px-3.5 py-2 text-xs font-mono focus:outline-none focus:border-slate-400">
                        </div>
                        <div>
                            <label class="block text-[11px] font-bold text-slate-400 uppercase tracking-wider mb-1">Brief Description</label>
                            <input id="custom-skill-desc" type="text" placeholder="e.g. Specialized workflows for monorepo staging and deploy verification" class="w-full input-box rounded-xl px-3.5 py-2 text-xs focus:outline-none focus:border-slate-400">
                        </div>
                    </div>

                    <div>
                        <div class="flex justify-between items-center mb-1">
                            <label class="block text-[11px] font-bold text-slate-400 uppercase tracking-wider">SKILL.md Markdown Content</label>
                            <button onclick="insertSkillTemplate()" class="text-[10px] text-amber-400 hover:underline">Insert Standard Template</button>
                        </div>
                        <textarea id="custom-skill-content" rows="10" class="w-full input-box rounded-xl p-3 text-xs font-mono focus:outline-none focus:border-slate-400 scrollbar-thin" placeholder="# My Custom Skill&#10;&#10;Instructions for the Antigravity agent..."></textarea>
                    </div>

                    <div class="flex justify-end gap-2 pt-2">
                        <button onclick="createAndInjectCustomSkill()" class="px-5 py-2.5 btn-action-primary font-semibold rounded-xl text-xs transition shadow-lg flex items-center gap-2">
                            <i class="fa-solid fa-rocket"></i> Inject Custom Skill to Target Agent
                        </button>
                    </div>
                </div>
            </div>

            <!-- Modal Footer -->
            <div class="px-6 py-3 border-t flex justify-between items-center text-xs flex-shrink-0" style="background-color: var(--bg-sidebar); border-color: var(--border-base);">
                <div class="text-[11px] text-slate-400 font-mono flex items-center gap-2">
                    <i class="fa-solid fa-shield-check text-emerald-400"></i>
                    <span>Antigravity Dynamic Runtime Loader</span>
                </div>
                <button onclick="closeSkillsModal()" class="px-4 py-1.5 border rounded-xl text-xs font-medium transition" style="background-color: var(--bg-input); border-color: var(--border-base); color: var(--text-main);">
                    Close
                </button>
            </div>

        </div>
    </div>
"""

main_end = "    </main>"
assert main_end in code, "</main> tag not found"
code = code.replace(main_end, modal_html + "\n" + main_end)

# 6. Update init() to fetch skills
init_search = """            selectView("agent-1");
            fetchAllStatus();
            setInterval(fetchAllStatus, 6000);
            setInterval(fetchCurrentLogs, 2500);"""

init_replace = """            selectView("agent-1");
            fetchSkillsLibrary();
            fetchAllStatus();
            setInterval(fetchAllStatus, 6000);
            setInterval(fetchCurrentLogs, 2500);"""

assert init_search in code, "Init search string not found"
code = code.replace(init_search, init_replace)

# 7. Update updateDedicatedAgentLabels to also update skills preview
update_agent_search = """            if (isRunning) overlay.classList.add("hidden");
            else overlay.classList.remove("hidden");
        }"""

update_agent_replace = """            if (isRunning) overlay.classList.add("hidden");
            else overlay.classList.remove("hidden");

            updateAgentSkillsPreview(agentId);
        }"""

assert update_agent_search in code, "updateDedicatedAgentLabels search not found"
code = code.replace(update_agent_search, update_agent_replace)

# 8. Add JS logic for Skills Hub
js_skills_logic = """
        // ============================================================
        // SKILLS HUB MANAGER CLIENT LOGIC
        // ============================================================
        let skillsLibrary = [];
        let installedSkillsMap = {};
        let currentSkillsCategory = "All";
        let activeSkillsTab = "library";

        async function fetchSkillsLibrary() {
            try {
                const res = await fetch("/api/skills/library");
                const data = await res.json();
                skillsLibrary = data.skills || [];
                renderSkillsCategories(data.categories || []);
                renderSkillsLibrary();
            } catch (e) {
                console.error("Failed to load skills library", e);
            }
        }

        function renderSkillsCategories(cats) {
            const container = document.getElementById("skills-cat-pills");
            if (!container) return;
            container.innerHTML = cats.map(cat => `
                <button onclick="setSkillsCategoryFilter('${cat}')" id="pill-cat-${cat.replace(/ /g, '-')}" class="px-2.5 py-1 rounded-lg text-[11px] font-semibold transition border ${cat === currentSkillsCategory ? 'bg-amber-500/20 text-amber-300 border-amber-500/40' : 'text-slate-400 hover:text-white'}" style="${cat !== currentSkillsCategory ? 'background-color: var(--bg-input); border-color: var(--border-base);' : ''}">
                    ${cat}
                </button>
            `).join("");
        }

        function setSkillsCategoryFilter(cat) {
            currentSkillsCategory = cat;
            const pills = document.querySelectorAll("#skills-cat-pills button");
            pills.forEach(p => {
                p.className = "px-2.5 py-1 rounded-lg text-[11px] font-semibold transition border text-slate-400 hover:text-white";
                p.style.backgroundColor = "var(--bg-input)";
                p.style.borderColor = "var(--border-base)";
            });
            const activePill = document.getElementById(`pill-cat-${cat.replace(/ /g, '-')}`);
            if (activePill) {
                activePill.className = "px-2.5 py-1 rounded-lg text-[11px] font-semibold transition border bg-amber-500/20 text-amber-300 border-amber-500/40";
                activePill.style.backgroundColor = "";
                activePill.style.borderColor = "";
            }
            renderSkillsLibrary();
        }

        function filterSkillsDisplay() {
            renderSkillsLibrary();
        }

        function renderSkillsLibrary() {
            const container = document.getElementById("skills-cards-grid");
            if (!container) return;
            const search = (document.getElementById("skills-search-input")?.value || "").toLowerCase().trim();
            const target = document.getElementById("skills-target-select")?.value || "agent-1";
            const targetInstalled = (installedSkillsMap[target] || []).map(s => s.name);

            const filtered = skillsLibrary.filter(s => {
                const matchesCat = (currentSkillsCategory === "All" || s.category === currentSkillsCategory);
                const matchesSearch = !search || s.name.toLowerCase().includes(search) || (s.description || "").toLowerCase().includes(search) || s.category.toLowerCase().includes(search);
                return matchesCat && matchesSearch;
            });

            if (filtered.length === 0) {
                container.innerHTML = `
                    <div class="col-span-full py-12 text-center text-slate-500 space-y-2">
                        <i class="fa-solid fa-folder-open text-3xl"></i>
                        <p class="text-xs">No skills found matching "${escapeHtml(search)}" in category "${escapeHtml(currentSkillsCategory)}".</p>
                    </div>
                `;
                return;
            }

            container.innerHTML = filtered.map(s => {
                const isInstalled = targetInstalled.includes(s.name);
                let catBadgeColor = "bg-blue-500/20 text-blue-300 border-blue-500/30";
                if (s.category.includes("Convex")) catBadgeColor = "bg-cyan-500/20 text-cyan-300 border-cyan-500/30";
                if (s.category.includes("Clerk")) catBadgeColor = "bg-emerald-500/20 text-emerald-300 border-emerald-500/30";
                if (s.category.includes("Testing")) catBadgeColor = "bg-purple-500/20 text-purple-300 border-purple-500/30";

                return `
                    <div class="p-3.5 rounded-2xl border transition flex flex-col justify-between space-y-3 group hover:border-slate-400/50" style="background-color: var(--bg-input); border-color: var(--border-base);">
                        <div class="space-y-1.5">
                            <div class="flex items-start justify-between gap-2">
                                <span class="font-bold text-xs text-white tracking-tight group-hover:text-amber-300 transition">${escapeHtml(s.name)}</span>
                                <span class="text-[9px] font-mono px-2 py-0.5 rounded-full border flex-shrink-0 ${catBadgeColor}">
                                    ${escapeHtml(s.category.replace(" Backend", "").replace(" Pipelines", ""))}
                                </span>
                            </div>
                            <p class="text-[11px] text-slate-400 line-clamp-3 leading-relaxed">${escapeHtml(s.description || 'No description provided')}</p>
                        </div>
                        <div class="flex items-center justify-between pt-2 border-t" style="border-color: var(--border-base);">
                            <span class="text-[10px] font-mono ${isInstalled ? 'text-emerald-400 flex items-center gap-1' : 'text-slate-500'}">
                                ${isInstalled ? '<i class="fa-solid fa-circle-check"></i> Installed' : '<i class="fa-solid fa-circle-minus"></i> Ready'}
                            </span>
                            <button id="btn-load-${s.name}" onclick="loadSkillToTarget('${s.name}', this)" class="px-2.5 py-1 rounded-lg text-xs font-semibold transition flex items-center gap-1.5 ${isInstalled ? 'border text-slate-300 hover:text-white' : 'btn-action-primary shadow-sm'}" style="${isInstalled ? 'background-color: var(--bg-sidebar); border-color: var(--border-base);' : ''}">
                                <i class="fa-solid ${isInstalled ? 'fa-arrows-rotate' : 'fa-plus'}"></i>
                                ${isInstalled ? 'Reload' : 'Load Skill'}
                            </button>
                        </div>
                    </div>
                `;
            }).join("");
        }

        async function refreshTargetInstalledSkills(forceSpinner = false) {
            const target = document.getElementById("skills-target-select")?.value || "agent-1";
            const targetAgent = agents.find(a => a.id === target);
            const label = document.getElementById("installed-agent-label");
            if (label) label.innerText = target === "broadcast" ? "All Agents (Fleet)" : (targetAgent ? `${targetAgent.name} (CT ${targetAgent.vmid})` : target);

            const icon = document.getElementById("installed-refresh-icon");
            if (forceSpinner && icon) icon.classList.add("fa-spin");

            try {
                if (target === "broadcast") {
                    const res = await fetch(`/api/skills/installed?agent_id=agent-1`);
                    const data = await res.json();
                    installedSkillsMap["broadcast"] = data.skills || [];
                } else {
                    const res = await fetch(`/api/skills/installed?agent_id=${target}`);
                    const data = await res.json();
                    installedSkillsMap[target] = data.skills || [];
                }
            } catch (e) {
                console.error("Failed to load installed skills", e);
            } finally {
                if (icon) setTimeout(() => icon.classList.remove("fa-spin"), 400);
            }

            const currentInstalled = installedSkillsMap[target] || [];
            const pill = document.getElementById("installed-count-pill");
            if (pill) pill.innerText = currentInstalled.length;

            renderInstalledSkills();
            renderSkillsLibrary();
            updateAgentSkillsPreview(currentView);
        }

        function renderInstalledSkills() {
            const container = document.getElementById("installed-skills-list");
            if (!container) return;
            const target = document.getElementById("skills-target-select")?.value || "agent-1";
            const list = installedSkillsMap[target] || [];

            if (list.length === 0) {
                container.innerHTML = `
                    <div class="col-span-full py-12 text-center text-slate-500 space-y-3">
                        <i class="fa-solid fa-boxes-stacked text-3xl"></i>
                        <p class="text-xs">No skills currently detected on this agent.</p>
                        <button onclick="switchSkillsTab('library')" class="px-3.5 py-1.5 btn-action-primary rounded-xl text-xs font-semibold inline-flex items-center gap-1.5">
                            <i class="fa-solid fa-plus"></i> Browse Skills Library
                        </button>
                    </div>
                `;
                return;
            }

            container.innerHTML = list.map(s => `
                <div class="p-3.5 rounded-2xl border flex items-center justify-between gap-3" style="background-color: var(--bg-input); border-color: var(--border-base);">
                    <div class="flex items-center space-x-3 min-w-0">
                        <div class="w-8 h-8 rounded-xl border flex items-center justify-center text-xs flex-shrink-0" style="background-color: var(--bg-sidebar); border-color: var(--border-base); color: ${s.is_builtin ? 'var(--text-muted)' : '#f59e0b'};">
                            <i class="fa-solid ${s.is_builtin ? 'fa-lock' : 'fa-puzzle-piece'}"></i>
                        </div>
                        <div class="min-w-0">
                            <div class="flex items-center gap-2">
                                <span class="text-xs font-bold text-white truncate">${escapeHtml(s.name)}</span>
                                <span class="text-[9px] font-mono px-1.5 py-0.2 rounded border ${s.is_builtin ? 'bg-slate-800 text-slate-400 border-slate-700' : 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30'}">
                                    ${s.is_builtin ? 'Built-in' : 'Active'}
                                </span>
                            </div>
                            <p class="text-[11px] text-slate-400 truncate mt-0.5">${escapeHtml(s.description || 'Active capability')}</p>
                        </div>
                    </div>
                    <div>
                        ${s.is_builtin ? `
                            <span class="text-[10px] text-slate-500 font-mono italic">System</span>
                        ` : `
                            <button onclick="removeSkillFromTarget('${s.name}')" class="px-2.5 py-1 bg-red-500/10 hover:bg-red-500/20 text-red-400 border border-red-500/20 rounded-lg text-xs font-medium transition flex items-center gap-1" title="Remove this skill">
                                <i class="fa-solid fa-trash text-[10px]"></i> Unload
                            </button>
                        `}
                    </div>
                </div>
            `).join("");
        }

        async function loadSkillToTarget(skillId, btn) {
            const target = document.getElementById("skills-target-select")?.value || "agent-1";
            const originalHtml = btn ? btn.innerHTML : "";
            if (btn) {
                btn.disabled = true;
                btn.innerHTML = `<i class="fa-solid fa-circle-notch fa-spin"></i> Loading...`;
            }

            try {
                const res = await fetch("/api/skills/load", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ target, skill_id: skillId })
                });
                const data = await res.json();
                if (data.success) {
                    if (btn) btn.innerHTML = `<i class="fa-solid fa-check text-emerald-400"></i> Loaded!`;
                    await refreshTargetInstalledSkills();
                    setTimeout(() => {
                        if (btn) {
                            btn.disabled = false;
                            renderSkillsLibrary();
                        }
                    }, 1200);
                } else {
                    alert(data.error || "Failed to load skill");
                    if (btn) {
                        btn.disabled = false;
                        btn.innerHTML = originalHtml;
                    }
                }
            } catch (e) {
                alert("Network error: " + e.message);
                if (btn) {
                    btn.disabled = false;
                    btn.innerHTML = originalHtml;
                }
            }
        }

        async function syncAllSkillsToTarget(targetOverride) {
            const target = targetOverride || (document.getElementById("skills-target-select")?.value || "agent-1");
            const targetName = target === "broadcast" ? "All Active Agents" : (agents.find(a => a.id === target)?.name || target);
            if (!confirm(`Synchronize the complete 72-skill library to ${targetName}?\\n\\nThis injects all Convex, Clerk, Cloud & DevOps capabilities into ~/.gemini/skills.`)) {
                return;
            }

            const btn = document.getElementById("btn-sync-all-modal");
            if (btn) {
                btn.disabled = true;
                btn.innerHTML = `<i class="fa-solid fa-circle-notch fa-spin"></i> Syncing 72 Skills...`;
            }

            try {
                const res = await fetch("/api/skills/sync_all", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ target })
                });
                const data = await res.json();
                if (data.success) {
                    alert(`Successfully synchronized entire 72-skill library to ${targetName}!`);
                    await refreshTargetInstalledSkills();
                } else {
                    alert("Error: " + (data.error || "Failed to sync skills archive"));
                }
            } catch (e) {
                alert("Sync failed: " + e.message);
            } finally {
                if (btn) {
                    btn.disabled = false;
                    btn.innerHTML = `<i class="fa-solid fa-bolt text-amber-300"></i> Sync Entire 72-Skill Library`;
                }
            }
        }

        async function removeSkillFromTarget(skillName) {
            const target = document.getElementById("skills-target-select")?.value || "agent-1";
            if (!confirm(`Are you sure you want to unload '${skillName}' from this agent?`)) return;

            try {
                const res = await fetch(`/api/skills/remove?agent_id=${target}&name=${encodeURIComponent(skillName)}`, {
                    method: "DELETE"
                });
                const data = await res.json();
                if (data.success) {
                    await refreshTargetInstalledSkills();
                } else {
                    alert(data.error || "Failed to remove skill");
                }
            } catch (e) {
                alert("Error: " + e.message);
            }
        }

        function insertSkillTemplate() {
            const name = document.getElementById("custom-skill-name").value.trim() || "custom-capability";
            const desc = document.getElementById("custom-skill-desc").value.trim() || "Instructions and workflow rules for this capability.";
            const template = `---
name: ${name}
description: ${desc}
---

# ${name}

## Objective
Describe the main objective of this capability.

## Guidelines & Rules
1. Adhere strictly to project conventions and coding patterns.
2. Verify all modifications using tests before completion.
3. Keep changes minimal, maintainable, and well-documented.

## Context & Commands
- Dev command: npm run dev
- Test command: npm test
`;
            document.getElementById("custom-skill-content").value = template;
        }

        async function createAndInjectCustomSkill() {
            const name = document.getElementById("custom-skill-name").value.trim().toLowerCase().replace(/[^a-z0-9-_]/g, '-');
            const desc = document.getElementById("custom-skill-desc").value.trim();
            const content = document.getElementById("custom-skill-content").value.trim();
            const target = document.getElementById("skills-target-select")?.value || "agent-1";

            if (!name) return alert("Please enter a skill slug name (e.g. monorepo-helper)");
            if (!content) return alert("Please provide SKILL.md content");

            try {
                const res = await fetch("/api/skills/load", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        target,
                        custom_name: name,
                        custom_content: content
                    })
                });
                const data = await res.json();
                if (data.success) {
                    alert(`Custom skill '${name}' successfully injected into target agent!`);
                    document.getElementById("custom-skill-name").value = "";
                    document.getElementById("custom-skill-desc").value = "";
                    document.getElementById("custom-skill-content").value = "";
                    switchSkillsTab("installed");
                    await refreshTargetInstalledSkills();
                } else {
                    alert(data.error || "Failed to inject custom skill");
                }
            } catch (e) {
                alert("Error: " + e.message);
            }
        }

        function openSkillsModal(targetAgentId, tab = "library") {
            const modal = document.getElementById("skills-hub-modal");
            if (!modal) return;
            const select = document.getElementById("skills-target-select");
            if (select) {
                if (targetAgentId) select.value = targetAgentId;
                else if (currentView !== "overview") select.value = currentView;
                else select.value = "agent-1";
            }
            modal.classList.remove("hidden");
            if (skillsLibrary.length === 0) fetchSkillsLibrary();
            switchSkillsTab(tab);
            refreshTargetInstalledSkills();
        }

        function openSkillsModalForCurrentAgent(tab = "library") {
            const target = currentView === "overview" ? "agent-1" : currentView;
            openSkillsModal(target, tab);
        }

        function closeSkillsModal() {
            const modal = document.getElementById("skills-hub-modal");
            if (modal) modal.classList.add("hidden");
            updateAgentSkillsPreview(currentView);
        }

        function onSkillsTargetChanged() {
            refreshTargetInstalledSkills();
        }

        function switchSkillsTab(tab) {
            activeSkillsTab = tab;
            const tabs = ["library", "installed", "custom"];
            tabs.forEach(t => {
                const view = document.getElementById(`skills-tab-${t}`);
                const btn = document.getElementById(`tab-btn-${t}`);
                if (view && btn) {
                    if (t === tab) {
                        view.classList.remove("hidden");
                        btn.style.borderColor = "var(--accent-primary)";
                        btn.style.color = "var(--highlight-text)";
                        btn.className = "px-4 py-2 border-b-2 text-xs font-bold transition flex items-center gap-2";
                    } else {
                        view.classList.add("hidden");
                        btn.style.borderColor = "transparent";
                        btn.style.color = "";
                        btn.className = "px-4 py-2 border-b-2 border-transparent text-xs font-bold transition text-slate-400 hover:text-white flex items-center gap-2";
                    }
                }
            });
            if (tab === "installed") refreshTargetInstalledSkills();
        }

        async function updateAgentSkillsPreview(agentId) {
            if (!agentId || agentId === "overview") return;
            const previewList = document.getElementById("dedicated-skills-preview-list");
            const countPill = document.getElementById("dedicated-skills-pill");
            const headerBadge = document.getElementById("agent-page-skills-badge");

            let skills = installedSkillsMap[agentId];
            if (!skills) {
                try {
                    const res = await fetch(`/api/skills/installed?agent_id=${agentId}`);
                    const data = await res.json();
                    skills = data.skills || [];
                    installedSkillsMap[agentId] = skills;
                } catch (e) {
                    skills = [];
                }
            }

            if (countPill) countPill.innerText = `${skills.length} Capabilities Active`;
            if (headerBadge) headerBadge.innerText = `Skills (${skills.length})`;

            if (previewList) {
                if (skills.length === 0) {
                    previewList.innerHTML = `<span class="text-xs text-slate-500 italic">No custom skills loaded yet. Click 'Manage Skills' to inject.</span>`;
                } else {
                    const displaySkills = skills.slice(0, 8);
                    const extraCount = skills.length - displaySkills.length;
                    previewList.innerHTML = displaySkills.map(s => `
                        <span class="px-2 py-0.5 rounded-lg text-[10px] font-mono border flex items-center gap-1 transition hover:border-amber-400/50 cursor-pointer" onclick="openSkillsModalForCurrentAgent('installed')" style="background-color: var(--bg-input); border-color: var(--border-base); color: var(--text-main);" title="${escapeHtml(s.description || '')}">
                            <span class="w-1.5 h-1.5 rounded-full ${s.is_builtin ? 'bg-slate-400' : 'bg-amber-400'}"></span>
                            ${escapeHtml(s.name)}
                        </span>
                    `).join("") + (extraCount > 0 ? `
                        <span class="px-2 py-0.5 rounded-lg text-[10px] font-mono border text-amber-400 cursor-pointer hover:underline" onclick="openSkillsModalForCurrentAgent('installed')" style="background-color: var(--bg-input); border-color: var(--border-base);">
                            +${extraCount} more
                        </span>
                    ` : "");
                }
            }
        }
"""

window_onload = "        window.onload = init;"
assert window_onload in code, "window.onload not found"
code = code.replace(window_onload, js_skills_logic + "\n" + window_onload)

# 9. Add Flask API Endpoints
backend_skills_routes = """
# ------------------------------------------------------------------
# SKILLS HUB API ENDPOINTS
# ------------------------------------------------------------------
@app.route("/api/skills/library", methods=["GET"])
def get_skills_library_route():
    skills = get_library_skills()
    cats = ["All", "Convex Backend", "Clerk Auth", "Cloud & Data Pipelines", "Testing & DevTools", "Core & Workflows"]
    return jsonify({"skills": skills, "categories": cats})

@app.route("/api/skills/installed", methods=["GET"])
def get_agent_installed_skills():
    agent_id = request.args.get("agent_id", "agent-1")
    agent = next((a for a in AGENTS if a["id"] == agent_id), None)
    if not agent:
        return jsonify({"error": "Invalid agent"}), 400
    try:
        r = requests.get(f"http://{agent['ip']}:{agent['port']}/skills", timeout=2.5)
        return jsonify(r.json())
    except Exception as e:
        return jsonify({"error": str(e), "skills": []})

@app.route("/api/skills/load", methods=["POST"])
def load_skill_to_agent():
    data = request.json or {}
    target = data.get("target", "agent-1")
    skill_id = data.get("skill_id")
    custom_name = data.get("custom_name")
    custom_content = data.get("custom_content")

    targets = [a for a in AGENTS if (target == "broadcast" or a["id"] == target)]
    if not targets:
        return jsonify({"error": "No valid target agents"}), 400

    payload = {}
    if skill_id:
        skill_dir = os.path.join(SKILLS_LIB_DIR, skill_id)
        if not os.path.exists(skill_dir):
            return jsonify({"error": f"Skill '{skill_id}' not found in library"}), 404
        
        files = {}
        for root, dirs, filenames in os.walk(skill_dir):
            for fn in filenames:
                fp = os.path.join(root, fn)
                rel = os.path.relpath(fp, skill_dir)
                with open(fp, "rb") as f:
                    files[rel] = base64.b64encode(f.read()).decode("utf-8")
        payload = {"name": skill_id, "files": files}
    elif custom_name:
        payload = {"name": custom_name, "content": custom_content or ""}
    else:
        return jsonify({"error": "Missing skill_id or custom_name"}), 400

    results = {}
    for a in targets:
        try:
            r = requests.post(f"http://{a['ip']}:{a['port']}/skills/install", json=payload, timeout=5)
            results[a["id"]] = r.json()
        except Exception as e:
            results[a["id"]] = {"error": str(e)}

    return jsonify({"success": True, "results": results})

@app.route("/api/skills/sync_all", methods=["POST"])
def sync_all_skills():
    data = request.json or {}
    target = data.get("target", "agent-1")
    targets = [a for a in AGENTS if (target == "broadcast" or a["id"] == target)]
    if not targets:
        return jsonify({"error": "No valid target agents"}), 400

    if not os.path.exists(SKILLS_ARCHIVE_PATH):
        return jsonify({"error": "Skills library archive not found on server"}), 404

    with open(SKILLS_ARCHIVE_PATH, "rb") as f:
        archive_b64 = base64.b64encode(f.read()).decode("utf-8")

    results = {}
    for a in targets:
        try:
            r = requests.post(f"http://{a['ip']}:{a['port']}/skills/install_archive", json={"archive": archive_b64}, timeout=10)
            results[a["id"]] = r.json()
        except Exception as e:
            results[a["id"]] = {"error": str(e)}

    return jsonify({"success": True, "message": "Synchronized entire skills library", "results": results})

@app.route("/api/skills/remove", methods=["DELETE"])
def remove_skill():
    agent_id = request.args.get("agent_id", "agent-1")
    skill_name = request.args.get("name")
    if not skill_name:
        return jsonify({"error": "Missing skill name"}), 400

    agent = next((a for a in AGENTS if a["id"] == agent_id), None)
    if not agent:
        return jsonify({"error": "Invalid agent"}), 400

    try:
        r = requests.delete(f"http://{agent['ip']}:{agent['port']}/skills/{skill_name}", timeout=3)
        return jsonify(r.json())
    except Exception as e:
        return jsonify({"error": str(e)}), 500
"""

app_run = 'if __name__ == "__main__":'
assert app_run in code, "if __name__ == '__main__': not found"
code = code.replace(app_run, backend_skills_routes + "\n" + app_run)

with open("cockpit_server_new.py", "w", encoding="utf-8") as f:
    f.write(code)

print("Updated cockpit_server_new.py written successfully!")
