import os, sys, json, time, requests, subprocess, base64, io, tarfile, zipfile, shutil, re
from flask import Flask, request, jsonify, render_template_string, send_file, Response

app = Flask(__name__)

PROXMOX_HOST = "192.168.178.105"
PROXMOX_TOKEN = "PVEAPIToken=root@pam!cockpit-token=c58599c3-09ea-4d68-983e-0bfd1dcb212c"
PROXMOX_API = f"https://{PROXMOX_HOST}:8006/api2/json"

# SKILLS PATH & REPOSITORY RESOLUTION
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

try:
    from ceo import (
        ROLE_DEFINITIONS, ROLES_BY_ID, get_role_spec, match_role_for_task,
        get_chain_of_command, CeoOrchestrator, WorkOrder, CeoHeartbeatSupervisor
    )
except Exception as e:
    print(f"[Warning] Failed to import CEO module: {e}")
    ROLE_DEFINITIONS, ROLES_BY_ID = [], {}
    CeoOrchestrator, CeoHeartbeatSupervisor = None, None
LOCAL_SKILLS_DIR = os.path.join(SCRIPT_DIR, "skills_library")
SYSTEM_SKILLS_DIR = "/usr/local/share/cockpit/skills_library"

SKILLS_LIB_DIR = os.environ.get("COCKPIT_SKILLS_DIR") or (
    LOCAL_SKILLS_DIR if os.path.exists(LOCAL_SKILLS_DIR) else SYSTEM_SKILLS_DIR
)
SKILLS_ARCHIVE_PATH = os.path.join(os.path.dirname(SKILLS_LIB_DIR), "cockpit-skills-library.tar.gz")
CACHED_SKILLS = []

def ensure_skills_archive_bytes():
    """Returns the bytes of cockpit-skills-library.tar.gz, building it on-the-fly if missing."""
    if os.path.exists(SKILLS_ARCHIVE_PATH):
        try:
            with open(SKILLS_ARCHIVE_PATH, "rb") as f:
                return f.read()
        except Exception:
            pass

    buf = io.BytesIO()
    if os.path.exists(SKILLS_LIB_DIR):
        with tarfile.open(fileobj=buf, mode="w:gz") as tar:
            for item in sorted(os.listdir(SKILLS_LIB_DIR)):
                item_path = os.path.join(SKILLS_LIB_DIR, item)
                tar.add(item_path, arcname=item)
    buf.seek(0)
    data = buf.getvalue()
    try:
        os.makedirs(os.path.dirname(SKILLS_ARCHIVE_PATH), exist_ok=True)
        with open(SKILLS_ARCHIVE_PATH, "wb") as f:
            f.write(data)
    except Exception:
        pass
    return data

def get_library_skills(force_refresh=False):
    global CACHED_SKILLS
    if CACHED_SKILLS and not force_refresh:
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
                    d_lower = d.lower()
                    if d_lower.startswith("convex"):
                        cat = "Convex Backend"
                    elif d_lower.startswith("clerk"):
                        cat = "Clerk Auth"
                    elif any(k in d_lower for k in ["bigquery", "dataform", "dbt", "gcp", "spark", "composer", "ml", "notebook", "discovering-gcp", "building-data", "data-autocleaning", "developing-with"]):
                        cat = "Cloud & Data Pipelines"
                    elif any(k in d_lower for k in ["test", "debugging", "chrome", "repair", "accidental", "gcloud-auth", "vitest", "playwright", "tailwind", "git"]):
                        cat = "Testing & DevTools"

                    skills.append({
                        "id": d,
                        "name": d,
                        "category": cat,
                        "description": desc[:220] + ("..." if len(desc) > 220 else "")
                    })
    CACHED_SKILLS = skills
    return CACHED_SKILLS

# Master configuration for Antigravity instances
AGENTS_CONFIG_FILE = "/usr/local/share/cockpit/agents_config.json"

DEFAULT_AGENTS = [
    {"id": "agent-1", "vmid": 151, "name": "Agent 1", "type": "antigravity", "vm_type": "lxc",  "role": "Frontend Specialist", "ip": "192.168.178.169", "port": 8000, "vnc_port": 6080},
    {"id": "agent-2", "vmid": 152, "name": "Agent 2", "type": "antigravity", "vm_type": "lxc",  "role": "Backend Specialist",  "ip": "192.168.178.170", "port": 8000, "vnc_port": 6080},
    {"id": "agent-3", "vmid": 153, "name": "Codex",   "type": "codex",       "vm_type": "lxc",  "role": "Code Synthesis & Refactor", "ip": "192.168.178.171", "port": 8000, "vnc_port": 6080},
    {"id": "agent-4", "vmid": 154, "name": "Hermes Agent", "type": "hermes", "vm_type": "qemu", "role": "Reasoning & Function Calling", "ip": "192.168.178.172", "port": 8000, "vnc_port": 6080},
    {"id": "agent-5", "vmid": 155, "name": "Open Claw", "type": "openclaw",  "vm_type": "qemu", "role": "Autonomous Web Scraper & Crawler", "ip": "192.168.178.173", "port": 8000, "vnc_port": 6080}
]

AGENTS = list(DEFAULT_AGENTS)

def load_agents_config():
    global AGENTS
    if os.path.exists(AGENTS_CONFIG_FILE):
        try:
            with open(AGENTS_CONFIG_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
                if isinstance(saved, list):
                    for a in saved:
                        if "type" not in a:
                            a["type"] = "antigravity"
                        if "vm_type" not in a:
                            a["vm_type"] = "qemu" if a.get("type") in ["hermes", "openclaw"] else "lxc"
                    AGENTS = saved
        except Exception as e:
            print("Failed to load agents_config.json", e)
    for a in AGENTS:
        if "type" not in a:
            a["type"] = "antigravity"
        if "vm_type" not in a:
            a["vm_type"] = "qemu" if a.get("type") in ["hermes", "openclaw"] else "lxc" 

def save_agents_config():
    try:
        os.makedirs(os.path.dirname(AGENTS_CONFIG_FILE), exist_ok=True)
        with open(AGENTS_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(AGENTS, f, indent=2)
    except Exception as e:
        print("Failed to save agents_config.json", e)

load_agents_config()

# ------------------------------------------------------------------
# WORKSPACES STORAGE & METADATA CONFIGURATION
# ------------------------------------------------------------------
DEFAULT_SYSTEM_WORKSPACES_DIR = "/usr/local/share/cockpit/workspaces"
LOCAL_WORKSPACES_DIR = os.path.join(SCRIPT_DIR, "workspaces")

WORKSPACES_DIR = os.environ.get("COCKPIT_WORKSPACES_DIR") or (
    DEFAULT_SYSTEM_WORKSPACES_DIR if os.path.exists("/usr/local/share/cockpit")
    else LOCAL_WORKSPACES_DIR
)
try:
    os.makedirs(WORKSPACES_DIR, exist_ok=True)
except Exception:
    WORKSPACES_DIR = LOCAL_WORKSPACES_DIR
    os.makedirs(WORKSPACES_DIR, exist_ok=True)

WORKSPACES_META_FILE = os.path.join(WORKSPACES_DIR, "workspaces_meta.json")
WORKSPACES = {}

def detect_tech_stack(ws_path):
    indicators = []
    if os.path.exists(os.path.join(ws_path, "package.json")):
        try:
            with open(os.path.join(ws_path, "package.json"), "r", errors="ignore") as f:
                pj = json.load(f)
                deps = {**pj.get("dependencies", {}), **pj.get("devDependencies", {})}
                if "next" in deps: indicators.append("Next.js")
                elif "react" in deps: indicators.append("React")
                elif "vue" in deps: indicators.append("Vue")
                elif "svelte" in deps: indicators.append("Svelte")
                elif "express" in deps: indicators.append("Express")
                else: indicators.append("Node.js")
        except Exception:
            indicators.append("Node.js")
    if os.path.exists(os.path.join(ws_path, "requirements.txt")) or os.path.exists(os.path.join(ws_path, "pyproject.toml")) or any(f.endswith(".py") for f in os.listdir(ws_path) if os.path.isfile(os.path.join(ws_path, f))):
        indicators.append("Python")
    if os.path.exists(os.path.join(ws_path, "Cargo.toml")):
        indicators.append("Rust")
    if os.path.exists(os.path.join(ws_path, "go.mod")):
        indicators.append("Go")
    if os.path.exists(os.path.join(ws_path, "index.html")):
        if not indicators: indicators.append("HTML5/Frontend")
    return " / ".join(indicators) if indicators else "Generic Codebase"

def scan_workspace_stats(ws_path):
    file_count = 0
    dir_count = 0
    size_bytes = 0
    for root, dirs, files in os.walk(ws_path):
        dirs[:] = [d for d in dirs if d not in [".git", "node_modules", "__pycache__", ".next", "dist", "build"]]
        dir_count += len(dirs)
        file_count += len(files)
        for f in files:
            fp = os.path.join(root, f)
            try:
                size_bytes += os.path.getsize(fp)
            except Exception:
                pass
    return {
        "file_count": file_count,
        "dir_count": dir_count,
        "size_bytes": size_bytes,
        "primary_language": detect_tech_stack(ws_path)
    }

def save_workspaces():
    try:
        os.makedirs(WORKSPACES_DIR, exist_ok=True)
        with open(WORKSPACES_META_FILE, "w", encoding="utf-8") as f:
            json.dump(WORKSPACES, f, indent=2)
    except Exception as e:
        print("Failed to save workspaces_meta.json", e)

def load_workspaces():
    global WORKSPACES
    WORKSPACES = {}
    if os.path.exists(WORKSPACES_META_FILE):
        try:
            with open(WORKSPACES_META_FILE, "r", encoding="utf-8") as f:
                WORKSPACES = json.load(f)
        except Exception as e:
            print("Failed to read workspaces_meta.json", e)
    
    if os.path.exists(WORKSPACES_DIR):
        for item in os.listdir(WORKSPACES_DIR):
            p = os.path.join(WORKSPACES_DIR, item)
            if os.path.isdir(p) and not item.startswith("."):
                if item not in WORKSPACES:
                    stats = scan_workspace_stats(p)
                    WORKSPACES[item] = {
                        "id": item,
                        "name": item,
                        "description": "Auto-discovered workspace directory",
                        "source": "local",
                        "created_at": time.time(),
                        "updated_at": time.time(),
                        "file_count": stats["file_count"],
                        "dir_count": stats["dir_count"],
                        "size_bytes": stats["size_bytes"],
                        "primary_language": stats["primary_language"],
                        "synced_agents": []
                    }
    save_workspaces()
    return WORKSPACES

def normalize_git_url(raw_url, token=None):
    url = (raw_url or "").strip()
    extracted_branch = None

    if "#" in url:
        url, extracted_branch = url.split("#", 1)
        url = url.strip()
        extracted_branch = extracted_branch.strip()
    elif "@" in url and not url.startswith("git@") and not ("http://" in url or "https://" in url):
        parts = url.split("@", 1)
        url = parts[0].strip()
        extracted_branch = parts[1].strip()

    if not (url.startswith("http://") or url.startswith("https://") or url.startswith("git@") or url.startswith("ssh://")):
        parts = url.split("/")
        if len(parts) == 2 and "." not in parts[0]:
            url = f"https://github.com/{parts[0]}/{parts[1]}.git"
        elif len(parts) >= 2 and ("github.com" in parts[0] or "gitlab.com" in parts[0] or "bitbucket.org" in parts[0]):
            url = f"https://{url}"

    if url.startswith("http://") or url.startswith("https://"):
        if not url.endswith(".git") and not url.endswith("/"):
            url = url + ".git"

    safe_url = url
    clone_url = url

    if token and token.strip():
        tok = token.strip()
        if "github.com" in url:
            clean = re.sub(r'https?://([^@]+@)?github\.com/', '', url)
            clone_url = f"https://{tok}@github.com/{clean}"
            safe_url = f"https://github.com/{clean}"
        elif "gitlab.com" in url:
            clean = re.sub(r'https?://([^@]+@)?gitlab\.com/', '', url)
            clone_url = f"https://oauth2:{tok}@gitlab.com/{clean}"
            safe_url = f"https://gitlab.com/{clean}"
        elif url.startswith("https://"):
            match = re.match(r'https://([^/]+)/(.*)', url)
            if match:
                host, path = match.group(1), match.group(2)
                host_clean = host.split("@")[-1]
                clone_url = f"https://{tok}@{host_clean}/{path}"
                safe_url = f"https://{host_clean}/{path}"

    return clone_url, safe_url, extracted_branch

def build_workspace_tree(ws_path, current_rel="", max_depth=4, current_depth=0):
    if current_depth > max_depth:
        return []
    target_dir = os.path.join(ws_path, current_rel) if current_rel else ws_path
    if not os.path.exists(target_dir):
        return []
    
    entries = []
    try:
        items = sorted(os.listdir(target_dir))
    except Exception:
        return []

    ignored = [".git", "node_modules", "__pycache__", ".next", "dist", "build", ".cache"]
    dirs = []
    files = []

    for it in items:
        if it in ignored:
            continue
        full_p = os.path.join(target_dir, it)
        rel_p = os.path.join(current_rel, it).replace("\\", "/") if current_rel else it
        if os.path.isdir(full_p):
            dirs.append((it, rel_p, full_p))
        else:
            files.append((it, rel_p, full_p))

    for name, rel_p, full_p in dirs:
        entries.append({
            "name": name,
            "path": rel_p,
            "is_dir": True,
            "children": build_workspace_tree(ws_path, rel_p, max_depth, current_depth + 1)
        })

    for name, rel_p, full_p in files:
        sz = 0
        try:
            sz = os.path.getsize(full_p)
        except Exception:
            pass
        entries.append({
            "name": name,
            "path": rel_p,
            "is_dir": False,
            "size": sz
        })

    return entries

def create_workspace_tar_gz(ws_path):
    tar_buf = io.BytesIO()
    with tarfile.open(fileobj=tar_buf, mode="w:gz") as tar:
        for item in sorted(os.listdir(ws_path)):
            if item in [".git", "node_modules", "__pycache__", ".next"]:
                continue
            full_p = os.path.join(ws_path, item)
            tar.add(full_p, arcname=item)
    tar_buf.seek(0)
    return tar_buf.read()

def create_workspace_zip(ws_path):
    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(ws_path):
            dirs[:] = [d for d in dirs if d not in [".git", "node_modules", "__pycache__", ".next"]]
            for file in files:
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, ws_path)
                zf.write(full_path, arcname=rel_path)
    zip_buf.seek(0)
    return zip_buf.read()

load_workspaces()

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en" class="dark" data-theme="onyx-stealth">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Antigravity Multi-Agent Cockpit</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        /* ---------------------------------------------------- */
        /* THEME DEFINITIONS                                    */
        /* ---------------------------------------------------- */
        :root, [data-theme="onyx-stealth"] {
            --bg-base: #08090d;
            --bg-sidebar: #0d0f16;
            --bg-card: rgba(17, 20, 29, 0.85);
            --bg-input: #0a0c12;
            --bg-terminal: #050608;
            --border-base: rgba(45, 52, 70, 0.65);
            --border-highlight: #52525b;
            --accent-primary: #e4e4e7;
            --accent-btn: #27272a;
            --accent-btn-hover: #3f3f46;
            --accent-btn-text: #f4f4f5;
            --nav-active-bg: #27272a;
            --nav-active-border: #71717a;
            --card-active-bg: rgba(39, 39, 42, 0.45);
            --card-active-border: #a1a1aa;
            --badge-bg: rgba(39, 39, 42, 0.7);
            --badge-text: #f4f4f5;
            --text-main: #f4f4f5;
            --text-muted: #9ca3af;
            --screen-border: rgba(63, 63, 70, 0.5);
            --brand-gradient: linear-gradient(135deg, #27272a 0%, #18181b 100%);
            --highlight-text: #ffffff;
        }

        [data-theme="cobalt-hyperdrive"] {
            --bg-base: #070a13;
            --bg-sidebar: #0a0f1d;
            --bg-card: rgba(13, 19, 34, 0.85);
            --bg-input: #080c18;
            --bg-terminal: #04060d;
            --border-base: rgba(30, 44, 77, 0.7);
            --border-highlight: rgba(59, 130, 246, 0.5);
            --accent-primary: #3b82f6;
            --accent-btn: #2563eb;
            --accent-btn-hover: #1d4ed8;
            --accent-btn-text: #ffffff;
            --nav-active-bg: #2563eb;
            --nav-active-border: #3b82f6;
            --card-active-bg: rgba(30, 58, 138, 0.35);
            --card-active-border: #3b82f6;
            --badge-bg: rgba(59, 130, 246, 0.2);
            --badge-text: #93c5fd;
            --text-main: #e2e8f0;
            --text-muted: #94a3b8;
            --screen-border: rgba(59, 130, 246, 0.35);
            --brand-gradient: linear-gradient(135deg, #2563eb 0%, #4f46e5 100%);
            --highlight-text: #60a5fa;
        }

        [data-theme="tokyo-neon"] {
            --bg-base: #090812;
            --bg-sidebar: #0e0d1c;
            --bg-card: rgba(18, 16, 33, 0.85);
            --bg-input: #0c0a18;
            --bg-terminal: #05040a;
            --border-base: rgba(55, 45, 84, 0.7);
            --border-highlight: rgba(168, 85, 247, 0.5);
            --accent-primary: #a855f7;
            --accent-btn: #9333ea;
            --accent-btn-hover: #7e22ce;
            --accent-btn-text: #ffffff;
            --nav-active-bg: #9333ea;
            --nav-active-border: #a855f7;
            --card-active-bg: rgba(88, 28, 135, 0.35);
            --card-active-border: #a855f7;
            --badge-bg: rgba(168, 85, 247, 0.2);
            --badge-text: #d8b4fe;
            --text-main: #f5f3ff;
            --text-muted: #a78bfa;
            --screen-border: rgba(168, 85, 247, 0.35);
            --brand-gradient: linear-gradient(135deg, #9333ea 0%, #ec4899 100%);
            --highlight-text: #c084fc;
        }

        /* ---------------------------------------------------- */
        /* GENERAL STYLES                                       */
        /* ---------------------------------------------------- */
        body { 
            background-color: var(--bg-base); 
            color: var(--text-main); 
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; 
            overflow: hidden; 
            height: 100vh; 
            transition: background-color 0.25s ease, color 0.25s ease; 
        }
        aside { background-color: var(--bg-sidebar); border-color: var(--border-base); }
        .glass { background: var(--bg-card); backdrop-filter: blur(12px); border: 1px solid var(--border-base); }
        .terminal { background-color: var(--bg-terminal); border: 1px solid var(--border-base); font-family: 'Consolas', 'Fira Code', monospace; }
        .scrollbar-thin::-webkit-scrollbar { width: 6px; height: 6px; }
        .scrollbar-thin::-webkit-scrollbar-track { background: var(--bg-base); }
        .scrollbar-thin::-webkit-scrollbar-thumb { background: var(--border-base); border-radius: 3px; }
        .screen-frame { border: 1px solid var(--screen-border); box-shadow: 0 0 25px rgba(0,0,0,0.8); }
        .input-box { background-color: var(--bg-input); border: 1px solid var(--border-base); color: var(--text-main); }
        .btn-action-primary { background: var(--accent-btn); color: var(--accent-btn-text); transition: all 0.2s; }
        .btn-action-primary:hover { filter: brightness(1.15); }
        .aspect-16-9 { aspect-ratio: 16 / 9; width: 100%; }
    </style>
</head>
<body class="flex h-screen w-screen">

    <!-- ============================================================ -->
    <!-- SIDE TASKBAR (LEFT NAVIGATION PANEL)                         -->
    <!-- ============================================================ -->
    <aside class="w-80 border-r flex flex-col flex-shrink-0 z-20">
        <!-- Brand Header -->
        <div class="p-4 border-b flex items-center justify-between" style="border-color: var(--border-base);">
            <div class="flex items-center space-x-3">
                <div class="w-9 h-9 rounded-xl flex items-center justify-center text-white text-base shadow-lg" style="background: var(--brand-gradient);">
                    <i class="fa-solid fa-brain"></i>
                </div>
                <div>
                    <h1 class="text-sm font-bold tracking-tight text-white flex items-center gap-1.5">
                        Antigravity Cockpit
                    </h1>
                    <p class="text-[10px] text-slate-400 font-mono">Proxmox PVE Fleet</p>
                </div>
            </div>
            <button onclick="fetchAllStatus()" class="p-2 text-slate-400 hover:text-white hover:bg-white/10 rounded-lg transition text-xs" title="Refresh Fleet Status">
                <i class="fa-solid fa-rotate" id="refresh-icon"></i>
            </button>
        </div>

        <!-- Theme Switcher Selector -->
        <div class="px-3.5 py-2.5 border-b flex items-center justify-between text-xs" style="border-color: var(--border-base);">
            <span class="text-[10px] uppercase font-bold text-slate-400 tracking-wider flex items-center gap-1.5">
                <i class="fa-solid fa-palette text-slate-400"></i> Theme
            </span>
            <div class="flex items-center gap-1 p-0.5 rounded-lg border" style="background-color: var(--bg-input); border-color: var(--border-base);">
                <button onclick="setTheme('onyx-stealth')" id="btn-theme-onyx" class="px-2 py-0.5 rounded text-[10px] font-semibold transition flex items-center gap-1" title="Onyx Stealth (Clean Dark)">
                    <i class="fa-solid fa-moon text-zinc-300"></i> Onyx
                </button>
                <button onclick="setTheme('cobalt-hyperdrive')" id="btn-theme-cobalt" class="px-2 py-0.5 rounded text-[10px] font-semibold transition flex items-center gap-1" title="Cobalt Hyperdrive (Original Blue)">
                    <i class="fa-solid fa-bolt text-blue-400"></i> Cobalt
                </button>
                <button onclick="setTheme('tokyo-neon')" id="btn-theme-tokyo" class="px-2 py-0.5 rounded text-[10px] font-semibold transition flex items-center gap-1" title="Tokyo Neon (Cyber Violet)">
                    <i class="fa-solid fa-wand-magic-sparkles text-purple-400"></i> Neon
                </button>
            </div>
        </div>

        <!-- Fleet Overview Tab Button -->
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
                <span id="nav-skills-badge" class="px-2 py-0.5 rounded-full text-[10px] font-bold font-mono border" style="background: var(--badge-bg); color: var(--badge-text); border-color: var(--border-base);">
                    Library
                </span>
            </button>
            <button onclick="openWorkspacesModal()" id="nav-btn-workspaces" class="w-full flex items-center justify-between px-3.5 py-2 rounded-xl transition text-xs font-semibold border" style="border-color: var(--border-base); background-color: var(--bg-input); color: var(--text-main);" title="Import & Manage Project Workspaces">
                <div class="flex items-center gap-2.5">
                    <i class="fa-solid fa-folder-tree text-emerald-400"></i>
                    <span>Workspaces</span>
                </div>
                <span id="nav-workspaces-badge" class="px-2 py-0.5 rounded-full text-[10px] font-bold font-mono border" style="background: var(--badge-bg); color: var(--badge-text); border-color: var(--border-base);">
                    0 Projects
                </span>
            </button>
            <button onclick="openCeoModal()" id="nav-btn-ceo" class="w-full flex items-center justify-between px-3.5 py-2 rounded-xl transition text-xs font-semibold border" style="border-color: var(--border-base); background-color: var(--bg-input); color: var(--text-main);" title="CEO Executive Suite & Fleet Orchestration">
                <div class="flex items-center gap-2.5">
                    <span class="text-sm">👑</span>
                    <span>Executive Suite</span>
                </div>
                <span id="nav-ceo-badge" class="px-2 py-0.5 rounded-full text-[10px] font-bold font-mono border" style="background: rgba(245, 158, 11, 0.15); color: #f59e0b; border-color: rgba(245, 158, 11, 0.3);">
                    CEO
                </span>
            </button>
        </div>

        <!-- Section Label -->
        <div class="px-4 pt-3 pb-1 flex justify-between items-center text-[10px] uppercase font-bold text-slate-400 tracking-wider">
            <span>Agents Taskbar (1-5)</span>
            <span class="text-slate-500 font-mono">Click to open</span>
        </div>

        <!-- Agent Cards Stack in Side Taskbar -->
        <div class="flex-1 overflow-y-auto p-3 space-y-2.5 scrollbar-thin" id="agent-sidebar-list">
            <!-- Built ONCE by JS init -->
        </div>

        <!-- Sidebar Footer Controls & Quick Presets -->
        <div class="p-3 border-t space-y-2" style="border-color: var(--border-base); background-color: rgba(0,0,0,0.3);">
            <div class="text-[10px] font-bold text-slate-400 uppercase tracking-wider flex items-center justify-between">
                <span>Fleet Presets</span>
                <span class="text-slate-500 text-[9px]">PVE 192.168.178.105</span>
            </div>
            <div class="grid grid-cols-2 gap-2">
                <button onclick="powerPreset('preset-2')" class="px-2.5 py-1.5 border rounded-lg text-left transition group" style="background-color: var(--bg-input); border-color: var(--border-base);">
                    <div class="text-[11px] font-semibold text-slate-200 group-hover:text-blue-400">Dual Mode</div>
                    <div class="text-[9px] text-slate-400">Agent 1 & 2</div>
                </button>
                <button onclick="powerPreset('preset-5')" class="px-2.5 py-1.5 border rounded-lg text-left transition group" style="background-color: var(--bg-input); border-color: var(--border-base);">
                    <div class="text-[11px] font-semibold text-slate-200 group-hover:text-cyan-400">Full Fleet</div>
                    <div class="text-[9px] text-slate-400">All 5 Agents</div>
                </button>
            </div>
        </div>
    </aside>

    <!-- ============================================================ -->
    <!-- MAIN CONTENT VIEW AREA                                       -->
    <!-- ============================================================ -->
    <main class="flex-1 flex flex-col min-w-0 overflow-y-auto scrollbar-thin" style="background-color: var(--bg-base);">

        <!-- ============================================================ -->
        <!-- VIEW 1: DEDICATED AGENT PAGE                                 -->
        <!-- ============================================================ -->
        <div id="dedicated-agent-view" class="flex-1 flex flex-col p-6 space-y-5">
            <!-- Dedicated Agent Header -->
            <div class="glass rounded-2xl p-4 flex flex-wrap items-center justify-between gap-4 shadow-xl">
                <div class="flex items-center space-x-4">
                    <div class="w-12 h-12 rounded-xl border flex items-center justify-center text-xl shadow-inner" style="background-color: var(--bg-input); border-color: var(--border-base); color: var(--highlight-text);" id="agent-page-icon">
                        <i class="fa-solid fa-robot"></i>
                    </div>
                    <div>
                        <div class="flex items-center gap-3">
                            <h2 class="text-xl font-bold text-white tracking-tight" id="agent-page-title">Agent 1 (Frontend)</h2>
                            <span id="agent-page-engine-badge" class="px-2.5 py-0.5 rounded-full text-xs font-semibold border flex items-center gap-1.5" style="background: rgba(99, 102, 241, 0.15); color: #a5b4fc; border-color: rgba(99, 102, 241, 0.35);">
                                <i class="fa-solid fa-atom"></i> Antigravity
                            </span>
                            <button onclick="openRenameModal(currentView)" class="px-2.5 py-0.5 border rounded-lg text-xs font-semibold transition flex items-center gap-1.5 text-slate-300 hover:text-white" style="background-color: var(--bg-input); border-color: var(--border-base);" title="Configure Agent & Engine">
                                <i class="fa-solid fa-pen-to-square text-amber-400"></i> Configure
                            </button>
                            <button onclick="confirmRemoveAgent(currentView)" class="px-2.5 py-0.5 border rounded-lg text-xs font-semibold transition flex items-center gap-1.5 text-rose-400 hover:text-white hover:bg-rose-500/20" style="background-color: var(--bg-input); border-color: rgba(244, 63, 94, 0.3);" title="Remove Agent">
                                <i class="fa-solid fa-trash-can text-rose-400"></i> Remove
                            </button>
                            <span id="agent-page-power-badge" class="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 flex items-center gap-1.5">
                                <span class="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span> Running
                            </span>
                            <span id="agent-page-auth-badge" class="px-2.5 py-0.5 rounded-full text-xs font-semibold border" style="background: var(--badge-bg); color: var(--badge-text); border-color: var(--border-base);">
                                ≡ƒöæ Authenticated
                            </span>
                        </div>
                        <div class="flex items-center gap-4 text-xs text-slate-400 font-mono mt-1">
                            <span><i class="fa-solid fa-server text-slate-500 mr-1"></i> CT <span id="agent-page-vmid" class="text-slate-200">151</span></span>
                            <span><i class="fa-solid fa-network-wired text-slate-500 mr-1"></i> <span id="agent-page-ip" class="text-slate-200">192.168.178.169</span></span>
                            <span><i class="fa-solid fa-microchip text-slate-500 mr-1"></i> CPU: <span id="agent-page-cpu" class="text-slate-200">--%</span></span>
                            <span><i class="fa-solid fa-memory text-slate-500 mr-1"></i> RAM: <span id="agent-page-ram" class="text-slate-200">-- MB</span></span>
                            <span><i class="fa-solid fa-clock text-slate-500 mr-1"></i> Uptime: <span id="agent-page-uptime" class="text-slate-200">--</span></span>
                            <span><i class="fa-solid fa-folder-tree text-emerald-400 mr-1"></i> Workspace: <span id="agent-page-ws-badge" class="text-emerald-400 font-semibold cursor-pointer hover:underline" onclick="openWorkspacesModal(currentView)" title="Click to manage or deploy project workspace">Default (None)</span></span>
                            <span><i class="fa-solid fa-bolt text-amber-400 mr-1"></i> Quota: <span id="agent-page-quota-badge" class="text-emerald-400 font-semibold cursor-pointer hover:underline" onclick="refreshAgentQuota(true)" title="Click to refresh model quota">--%</span></span>
                        </div>
                    </div>
                </div>

                <!-- Action Controls for this specific agent -->
                <div class="flex items-center gap-2">
                    <button onclick="toggleLayoutMode()" id="layout-toggle-btn" class="px-3 py-2 border rounded-xl text-xs font-medium transition flex items-center gap-1.5" style="background-color: var(--bg-input); border-color: var(--border-base); color: var(--text-main);" title="Toggle Split vs Theater Layout">
                        <i class="fa-solid fa-table-columns" id="layout-icon"></i>
                        <span id="layout-text">Theater Mode</span>
                    </button>
                    <button onclick="reloadScreenIframe()" class="px-3 py-2 border rounded-xl text-xs font-medium transition flex items-center gap-1.5" style="background-color: var(--bg-input); border-color: var(--border-base); color: var(--text-main);" title="Reload Video Stream">
                        <i class="fa-solid fa-rotate-right"></i> Reload
                    </button>
                    <button onclick="restartAgentDesktop()" class="px-3 py-2 border rounded-xl text-xs font-medium transition flex items-center gap-1.5" style="background-color: var(--bg-input); border-color: var(--border-base); color: var(--text-main);" title="Restart x11vnc & Antigravity">
                        <i class="fa-solid fa-window-restore"></i> Reset GUI
                    </button>
                    <button onclick="openSkillsModalForCurrentAgent()" class="px-3 py-2 border rounded-xl text-xs font-medium transition flex items-center gap-1.5" style="background-color: var(--bg-input); border-color: var(--border-base); color: var(--text-main);" title="Manage Agent Skills">
                        <i class="fa-solid fa-boxes-stacked text-amber-400"></i>
                        <span id="agent-page-skills-badge">Skills</span>
                    </button>
                    <button onclick="openWorkspacesModal(currentView)" class="px-3 py-2 border rounded-xl text-xs font-medium transition flex items-center gap-1.5" style="background-color: var(--bg-input); border-color: var(--border-base); color: var(--text-main);" title="Manage & Deploy Project Workspaces">
                        <i class="fa-solid fa-folder-tree text-emerald-400"></i>
                        <span>Workspaces</span>
                    </button>
                    <button onclick="toggleDedicatedFullscreen()" class="px-3 py-2 border rounded-xl text-xs font-medium transition flex items-center gap-1.5" style="background-color: var(--bg-input); border-color: var(--border-base); color: var(--text-main);" title="Toggle Fullscreen">
                        <i class="fa-solid fa-expand"></i> Fullscreen
                    </button>
                    <a id="agent-page-popout" href="#" target="_blank" class="px-3 py-2 rounded-xl text-xs font-medium transition flex items-center gap-1.5 btn-action-primary shadow-lg" title="Open Desktop in Dedicated Browser Tab">
                        <i class="fa-solid fa-arrow-up-right-from-square"></i> Pop-out
                    </a>
                    <button id="agent-page-power-btn" onclick="toggleCurrentAgentPower()" class="px-3.5 py-2 bg-red-500/20 hover:bg-red-500/30 text-red-300 border border-red-500/30 rounded-xl text-xs font-medium transition flex items-center gap-1.5">
                        <i class="fa-solid fa-power-off"></i> Stop
                    </button>
                </div>
            </div>

            <!-- REARRANGED WORKSPACE: 16:9 Display Card + Panels -->
            <div id="dedicated-workspace-container" class="grid grid-cols-1 xl:grid-cols-12 gap-5 items-start pb-6">
                
                <!-- Left Section: 16:9 Display Card + In-Cockpit Auth Manager (7 cols in Split) -->
                <div id="workspace-left-col" class="xl:col-span-7 2xl:col-span-8 flex flex-col space-y-4">
                    <!-- Dedicated Live Visual Passthrough Window CAPPED AT 16:9 -->
                    <div class="glass rounded-2xl overflow-hidden shadow-2xl flex flex-col screen-frame">
                        <div class="px-4 py-2.5 flex justify-between items-center border-b" style="background-color: var(--bg-sidebar); border-color: var(--border-base);">
                            <div class="flex items-center space-x-2">
                                <span class="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse"></span>
                                <span class="text-xs font-semibold text-white">Live Visual Desktop</span>
                                <span class="text-[10px] font-mono px-2 py-0.5 rounded border" style="background-color: var(--bg-input); border-color: var(--border-base); color: var(--text-muted);">16:9 Native (1920x1080)</span>
                            </div>
                            <div class="text-[11px] text-slate-400 flex items-center gap-3">
                                <span><i class="fa-solid fa-shield-halved text-emerald-400 mr-1"></i> Multi-Client Shared</span>
                                <span class="text-slate-600">|</span>
                                <span>Interactive Canvas</span>
                            </div>
                        </div>

                        <!-- 16:9 Aspect Ratio Capped Viewport -->
                        <div class="relative w-full aspect-16-9 bg-black overflow-hidden flex items-center justify-center">
                            <!-- Stopped Container Placeholder -->
                            <div id="screen-stopped-overlay" class="absolute inset-0 bg-slate-950/90 backdrop-blur-sm hidden flex-col items-center justify-center space-y-4 z-10">
                                <div class="w-16 h-16 rounded-2xl border flex items-center justify-center text-3xl text-slate-500" style="background-color: var(--bg-input); border-color: var(--border-base);">
                                    <i class="fa-solid fa-power-off"></i>
                                </div>
                                <div class="text-center">
                                    <h3 class="text-base font-bold text-white">Agent Container is Stopped</h3>
                                    <p class="text-xs text-slate-400 mt-1">Spin up this instance to connect to its visual desktop and Antigravity workspace.</p>
                                </div>
                                <button onclick="toggleCurrentAgentPower()" class="px-5 py-2.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded-xl text-xs font-semibold transition flex items-center gap-2 shadow-lg shadow-emerald-600/20">
                                    <i class="fa-solid fa-play"></i> Spin Up Container
                                </button>
                            </div>

                            <!-- Persistent Dedicated Screen Iframes -->
                            <div id="dedicated-iframes-container" class="w-full h-full">
                                <!-- Populated ONCE at init -->
                            </div>
                        </div>
                    </div>

                    <!-- Auth Manager Box Beneath Screen -->
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

                    <!-- Model Quotas & Token Headroom Tracker Card -->
                    <div class="glass rounded-2xl p-4 space-y-3.5" id="agent-quota-card">
                        <div class="flex justify-between items-center">
                            <div class="flex items-center gap-2.5">
                                <div class="w-8 h-8 rounded-xl bg-amber-500/10 border border-amber-500/30 flex items-center justify-center text-amber-400 text-sm shadow-inner">
                                    <i class="fa-solid fa-bolt-lightning"></i>
                                </div>
                                <div>
                                    <h3 class="text-xs font-semibold text-white uppercase tracking-wider flex items-center gap-2">
                                        Model Quotas & Token Headroom
                                    </h3>
                                    <div class="text-[10px] text-slate-400 flex items-center gap-2 mt-0.5">
                                        <span id="quota-tier-name" class="font-mono text-slate-300">Google AI Pro (Helium)</span>
                                        <span class="text-slate-600">•</span>
                                        <span id="quota-updated-time" class="text-slate-500 font-mono">Checking quotas...</span>
                                    </div>
                                </div>
                            </div>
                            <div class="flex items-center gap-2">
                                <button onclick="refreshAgentQuota(true)" id="quota-refresh-btn" class="px-3 py-1.5 rounded-xl text-xs font-semibold transition flex items-center gap-1.5 border hover:bg-white/5 text-slate-300" style="background-color: var(--bg-input); border-color: var(--border-base);" title="Refresh live quota from Google Cloud Code API">
                                    <i class="fa-solid fa-rotate-right" id="quota-refresh-icon"></i> Refresh Quotas
                                </button>
                            </div>
                        </div>

                        <!-- 4 Core Model Progress Meters -->
                        <div class="grid grid-cols-1 md:grid-cols-2 gap-3" id="quota-meters-grid">
                            <!-- Gemini 3.8 Flash -->
                            <div class="p-3 rounded-xl border bg-black/25 flex flex-col justify-between space-y-2" style="border-color: var(--border-base);">
                                <div class="flex justify-between items-center text-xs">
                                    <span class="font-semibold text-slate-200 flex items-center gap-1.5">
                                        <i class="fa-solid fa-atom text-indigo-400 text-[11px]"></i> Gemini 3.8 Flash
                                    </span>
                                    <span id="quota-val-gemini-flash" class="font-mono font-bold text-emerald-400">--%</span>
                                </div>
                                <div class="w-full bg-slate-800/80 rounded-full h-2 overflow-hidden">
                                    <div id="quota-bar-gemini-flash" class="bg-gradient-to-r from-emerald-500 to-teal-400 h-2 rounded-full transition-all duration-500" style="width: 0%"></div>
                                </div>
                                <div class="flex justify-between items-center text-[10px] text-slate-400 font-mono">
                                    <span>1,048,576 Context</span>
                                    <span id="quota-reset-gemini-flash" class="text-slate-500">Daily reset</span>
                                </div>
                            </div>

                            <!-- Gemini 3.1 Pro -->
                            <div class="p-3 rounded-xl border bg-black/25 flex flex-col justify-between space-y-2" style="border-color: var(--border-base);">
                                <div class="flex justify-between items-center text-xs">
                                    <span class="font-semibold text-slate-200 flex items-center gap-1.5">
                                        <i class="fa-solid fa-brain text-purple-400 text-[11px]"></i> Gemini 3.1 Pro
                                    </span>
                                    <span id="quota-val-gemini-pro" class="font-mono font-bold text-emerald-400">--%</span>
                                </div>
                                <div class="w-full bg-slate-800/80 rounded-full h-2 overflow-hidden">
                                    <div id="quota-bar-gemini-pro" class="bg-gradient-to-r from-emerald-500 to-purple-400 h-2 rounded-full transition-all duration-500" style="width: 0%"></div>
                                </div>
                                <div class="flex justify-between items-center text-[10px] text-slate-400 font-mono">
                                    <span>1,048,576 Context</span>
                                    <span id="quota-reset-gemini-pro" class="text-slate-500">Daily reset</span>
                                </div>
                            </div>

                            <!-- Claude 4.6 Thinking / Sonnet -->
                            <div class="p-3 rounded-xl border bg-black/25 flex flex-col justify-between space-y-2" style="border-color: var(--border-base);">
                                <div class="flex justify-between items-center text-xs">
                                    <span class="font-semibold text-slate-200 flex items-center gap-1.5">
                                        <i class="fa-solid fa-feather-pointed text-amber-400 text-[11px]"></i> Claude Opus/Sonnet 4.6
                                    </span>
                                    <span id="quota-val-claude" class="font-mono font-bold text-amber-400">--%</span>
                                </div>
                                <div class="w-full bg-slate-800/80 rounded-full h-2 overflow-hidden">
                                    <div id="quota-bar-claude" class="bg-gradient-to-r from-amber-500 to-orange-400 h-2 rounded-full transition-all duration-500" style="width: 0%"></div>
                                </div>
                                <div class="flex justify-between items-center text-[10px] text-slate-400 font-mono">
                                    <span>250,000 Context</span>
                                    <span id="quota-reset-claude" class="text-slate-500">Weekly reset</span>
                                </div>
                            </div>

                            <!-- GPT-OSS 120B -->
                            <div class="p-3 rounded-xl border bg-black/25 flex flex-col justify-between space-y-2" style="border-color: var(--border-base);">
                                <div class="flex justify-between items-center text-xs">
                                    <span class="font-semibold text-slate-200 flex items-center gap-1.5">
                                        <i class="fa-solid fa-code text-cyan-400 text-[11px]"></i> GPT-OSS 120B
                                    </span>
                                    <span id="quota-val-gpt" class="font-mono font-bold text-cyan-400">--%</span>
                                </div>
                                <div class="w-full bg-slate-800/80 rounded-full h-2 overflow-hidden">
                                    <div id="quota-bar-gpt" class="bg-gradient-to-r from-cyan-500 to-blue-400 h-2 rounded-full transition-all duration-500" style="width: 0%"></div>
                                </div>
                                <div class="flex justify-between items-center text-[10px] text-slate-400 font-mono">
                                    <span>131,072 Context</span>
                                    <span id="quota-reset-gpt" class="text-slate-500">Weekly reset</span>
                                </div>
                            </div>
                        </div>

                        <!-- All Models Toggle Button & Collapsible List -->
                        <div class="pt-2 border-t flex flex-col space-y-2" style="border-color: var(--border-base);">
                            <button onclick="toggleAllModelsList()" class="text-[11px] text-slate-400 hover:text-slate-200 flex items-center justify-between py-1 transition">
                                <span class="flex items-center gap-1.5"><i class="fa-solid fa-list-check text-slate-500"></i> Full Model Quota Registry (<span id="all-models-count">33</span>)</span>
                                <i class="fa-solid fa-chevron-down transition-transform duration-200" id="all-models-chevron"></i>
                            </button>
                            <div id="all-models-container" class="hidden max-h-48 overflow-y-auto space-y-1 scrollbar-thin pr-1">
                                <!-- Populated dynamically by JS -->
                            </div>
                        </div>
                    </div>
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
                            <span id="card-skills-lib-info" class="text-[10px] text-slate-500 font-mono">Enterprise skills library</span>
                            <div class="flex items-center gap-2">
                                <button onclick="syncAllSkillsToTarget(currentView)" class="px-3 py-1.5 rounded-xl text-xs font-semibold transition flex items-center gap-1.5 border" style="background-color: var(--bg-input); border-color: var(--border-base); color: var(--text-main);" title="Sync library to this agent">
                                    <i class="fa-solid fa-bolt text-amber-400"></i> Sync Full Library
                                </button>
                                <button onclick="openSkillsModalForCurrentAgent()" class="px-3 py-1.5 btn-action-primary font-semibold rounded-xl text-xs transition shadow-lg flex items-center gap-1.5">
                                    <i class="fa-solid fa-boxes-stacked"></i> Manage Skills
                                </button>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Right Section: Task Dispatcher + Antigravity Message Output (5 cols in Split) -->
                <div id="workspace-right-col" class="xl:col-span-5 2xl:col-span-4 flex flex-col space-y-4">
                    <!-- Task Dispatcher Card -->
                    <div class="glass rounded-2xl p-4 space-y-3.5">
                        <div class="flex justify-between items-center">
                            <h3 class="text-xs font-semibold text-white uppercase tracking-wider flex items-center gap-2">
                                <i class="fa-solid fa-paper-plane" style="color: var(--highlight-text);"></i> Task Dispatcher
                            </h3>
                            <span id="dispatcher-target-tag" class="text-[10px] px-2 py-0.5 rounded-full font-mono border" style="background: var(--badge-bg); color: var(--badge-text); border-color: var(--border-base);">Agent 1</span>
                        </div>

                        <!-- Quick Action Prompts -->
                        <div>
                            <div class="text-[9px] uppercase font-bold text-slate-400 tracking-wider mb-1.5">Quick Commands</div>
                            <div class="flex flex-wrap gap-1.5">
                                <button onclick="setPrompt('Analyze repository status and verify clean build')" class="px-2 py-0.5 text-slate-300 border rounded-lg text-[11px] transition" style="background-color: var(--bg-input); border-color: var(--border-base);">
                                    ≡ƒöì Check Build
                                </button>
                                <button onclick="setPrompt('Run automated unit and integration tests with coverage report')" class="px-2 py-0.5 text-slate-300 border rounded-lg text-[11px] transition" style="background-color: var(--bg-input); border-color: var(--border-base);">
                                    ≡ƒº¬ Tests
                                </button>
                                <button onclick="setPrompt('Review latest git commits and prepare shipping changelog')" class="px-2 py-0.5 text-slate-300 border rounded-lg text-[11px] transition" style="background-color: var(--bg-input); border-color: var(--border-base);">
                                    ≡ƒôï Diff
                                </button>
                                <button onclick="setPrompt('Start dev server and report listening ports and endpoints')" class="px-2 py-0.5 text-slate-300 border rounded-lg text-[11px] transition" style="background-color: var(--bg-input); border-color: var(--border-base);">
                                    ΓÜí Dev Server
                                </button>
                            </div>
                        </div>

                        <!-- Prompt Input & Attachment Drop Zone -->
                        <div id="dispatcher-drop-zone" class="relative rounded-xl border border-dashed border-transparent transition-all">
                            <textarea id="dedicated-prompt-input" rows="3" placeholder="Enter instructions, paste screenshots (Ctrl+V), or drag & drop pictures here..." class="w-full input-box rounded-xl p-3 text-xs focus:outline-none focus:border-slate-400"></textarea>
                            
                            <!-- Image Attachment Tray -->
                            <div id="attached-images-tray" class="hidden px-2 py-2 flex flex-wrap gap-2 items-center rounded-xl border mt-1.5" style="background-color: var(--bg-input); border-color: var(--border-base);">
                                <!-- Populated dynamically with thumbnails -->
                            </div>
                        </div>

                        <!-- Controls & Attachment Toolbar -->
                        <div class="flex flex-wrap justify-between items-center gap-2 pt-1">
                            <div class="flex items-center gap-1.5">
                                <input type="file" id="task-image-file-input" accept="image/*" multiple class="hidden" onchange="handleTaskImageSelect(this.files)">
                                
                                <button type="button" onclick="document.getElementById('task-image-file-input').click()" class="px-2.5 py-1.5 border rounded-xl text-xs transition flex items-center gap-1.5 text-slate-300 hover:text-white" style="background-color: var(--bg-input); border-color: var(--border-base);" title="Attach screenshot or picture from your device">
                                    <i class="fa-solid fa-paperclip text-amber-400"></i> Attach Pic
                                </button>
                                
                                <button type="button" onclick="captureCurrentAgentScreen()" id="btn-capture-agent-screen" class="px-2.5 py-1.5 border rounded-xl text-xs transition flex items-center gap-1.5 text-slate-300 hover:text-white" style="background-color: var(--bg-input); border-color: var(--border-base);" title="Capture live screenshot of this agent's desktop">
                                    <i class="fa-solid fa-camera text-sky-400"></i> Capture Screen
                                </button>
                                
                                <!-- Workspace selector in Task Dispatcher -->
                                <div class="flex items-center gap-1.5 px-2.5 py-1.5 border rounded-xl text-xs" style="background-color: var(--bg-input); border-color: var(--border-base);">
                                    <i class="fa-solid fa-folder-tree text-emerald-400"></i>
                                    <select id="dedicated-workspace-select" onchange="onDedicatedWorkspaceChanged()" class="bg-transparent text-xs text-slate-200 focus:outline-none cursor-pointer max-w-[150px] sm:max-w-[200px] truncate" title="Select attached project workspace">
                                        <option value="" class="bg-slate-900 text-slate-400">No Workspace</option>
                                    </select>
                                    <span id="dedicated-workspace-sync-badge" class="hidden px-1.5 py-0.2 rounded text-[9px] font-mono border"></span>
                                </div>

                                <span class="text-[10px] text-slate-500 font-mono hidden sm:inline">&bull; Ctrl+V to paste</span>
                            </div>

                            <button onclick="dispatchDedicatedTask()" id="btn-dispatch-task" class="px-4 py-2 btn-action-primary font-semibold rounded-xl text-xs transition shadow-lg flex items-center gap-2">
                                <i class="fa-solid fa-bolt"></i> Dispatch Task
                            </button>
                        </div>
                    </div>

                    <!-- Real-time Messages & Agent Output Terminal -->
                    <div class="glass rounded-2xl p-4 flex flex-col h-[460px]">
                        <div class="flex justify-between items-center pb-2.5 border-b" style="border-color: var(--border-base);">
                            <div class="flex items-center space-x-2">
                                <span class="w-2 h-2 rounded-full bg-cyan-400 animate-pulse"></span>
                                <h3 class="text-xs font-semibold text-white uppercase tracking-wider">Antigravity Stream & Output</h3>
                            </div>
                            <button onclick="clearDedicatedTerminal()" class="px-2 py-0.5 border rounded-lg text-[11px] transition" style="background-color: var(--bg-input); border-color: var(--border-base); color: var(--text-muted);">
                                Clear
                            </button>
                        </div>
                        <div id="dedicated-terminal-logs" class="terminal flex-1 p-3.5 rounded-xl mt-2.5 overflow-y-auto space-y-1.5 text-xs text-slate-300 scrollbar-thin">
                            <div class="text-slate-500 italic">Streaming Antigravity output and language_server events...</div>
                        </div>
                    </div>
                </div>

            </div>
        </div>

        <!-- ============================================================ -->
        <!-- VIEW 2: FLEET OVERVIEW (ALL ACTIVE AGENTS)                   -->
        <!-- ============================================================ -->
        <div id="fleet-overview-view" class="flex-1 flex flex-col p-6 space-y-6 hidden">
            <!-- Fleet Top Bar -->
            <div class="glass rounded-2xl p-5 shadow-xl flex flex-wrap justify-between items-center gap-4">
                <div>
                    <h2 class="text-xl font-bold text-white tracking-tight flex items-center gap-2.5">
                        <i class="fa-solid fa-network-wired" style="color: var(--highlight-text);"></i> Proxmox Multi-Agent Fleet
                    </h2>
                    <p class="text-xs text-slate-400 mt-1">
                        High-density overview of all 5 Antigravity agents running on Proxmox VE (192.168.178.105)
                    </p>
                </div>
                <div class="flex items-center gap-3">
                    <button onclick="powerPreset('preset-2')" class="px-4 py-2 border rounded-xl text-xs font-semibold transition flex items-center gap-2" style="background-color: var(--bg-input); border-color: var(--border-base); color: var(--text-main);">
                        <i class="fa-solid fa-users"></i> Dual-Agent Preset
                    </button>
                    <button onclick="powerPreset('preset-5')" class="px-4 py-2 btn-action-primary rounded-xl text-xs font-semibold transition shadow-lg flex items-center gap-2">
                        <i class="fa-solid fa-bolt"></i> Spin Up All 5
                    </button>
                </div>
            </div>

            <!-- Broadcast Dispatcher Card -->
            <div class="glass rounded-2xl p-5 space-y-3 shadow-xl">
                <div class="flex justify-between items-center">
                    <h3 class="text-sm font-semibold text-white uppercase tracking-wider flex items-center gap-2">
                        <i class="fa-solid fa-bullhorn" style="color: var(--highlight-text);"></i> Global Broadcast Dispatcher
                    </h3>
                    <span class="text-xs font-mono px-2.5 py-0.5 rounded-full border" style="background: var(--badge-bg); color: var(--badge-text); border-color: var(--border-base);">Sends to all running instances</span>
                </div>
                <!-- Broadcast Image Attachment Tray -->
                <div id="broadcast-images-tray" class="hidden px-2 py-2 flex flex-wrap gap-2 items-center rounded-xl border mb-2" style="background-color: var(--bg-input); border-color: var(--border-base);">
                </div>

                <div class="flex gap-2 items-center flex-wrap sm:flex-nowrap">
                    <input type="file" id="broadcast-image-file-input" accept="image/*" multiple class="hidden" onchange="handleBroadcastImageSelect(this.files)">
                    <button type="button" onclick="document.getElementById('broadcast-image-file-input').click()" class="px-3 py-2.5 border rounded-xl text-xs transition flex items-center gap-1.5 text-slate-300 hover:text-white flex-shrink-0" style="background-color: var(--bg-input); border-color: var(--border-base);" title="Attach screenshot or picture to broadcast">
                        <i class="fa-solid fa-paperclip text-amber-400"></i>
                    </button>
                    <div class="flex items-center gap-1.5 px-2.5 py-2 border rounded-xl text-xs flex-shrink-0" style="background-color: var(--bg-input); border-color: var(--border-base);">
                        <i class="fa-solid fa-folder-tree text-emerald-400"></i>
                        <select id="broadcast-workspace-select" class="bg-transparent text-xs text-slate-200 focus:outline-none cursor-pointer max-w-[130px] sm:max-w-[180px] truncate" title="Select attached project workspace">
                            <option value="" class="bg-slate-900 text-slate-400">No Workspace</option>
                        </select>
                    </div>
                    <input id="broadcast-prompt-input" type="text" placeholder="Broadcast a task to all active agents simultaneously (paste screenshots with Ctrl+V)..." class="flex-1 input-box rounded-xl px-4 py-2.5 text-xs focus:outline-none focus:border-slate-400" onkeydown="if(event.key==='Enter') dispatchBroadcast()">
                    <button onclick="dispatchBroadcast()" class="px-5 py-2.5 btn-action-primary font-semibold rounded-xl text-xs transition shadow-lg flex items-center gap-2 flex-shrink-0">
                        <i class="fa-solid fa-tower-broadcast"></i> Broadcast
                    </button>
                </div>
            </div>

            <!-- Active Agents Live Screens Grid (Permanent Iframes Capped at 16:9) -->
            <div>
                <div class="flex justify-between items-center mb-3">
                    <h3 class="text-sm font-bold text-white uppercase tracking-wider flex items-center gap-2">
                        <i class="fa-solid fa-desktop text-cyan-400"></i> Active Visual Screens
                    </h3>
                    <span class="text-xs text-slate-400 font-mono">16:9 Interactive Displays</span>
                </div>
                <div id="overview-empty-notice" class="glass p-8 rounded-2xl text-center space-y-3 hidden">
                    <div class="text-slate-500 text-3xl"><i class="fa-solid fa-power-off"></i></div>
                    <h4 class="text-base font-semibold text-white">All Agent Instances are Currently Stopped</h4>
                    <p class="text-xs text-slate-400">Click "Dual-Agent Preset" or "Spin Up All 5" to launch your agents.</p>
                </div>
                <div class="grid grid-cols-1 md:grid-cols-2 gap-5" id="active-screens-grid">
                    <!-- Populated ONCE at init with 16:9 aspect-video ratio -->
                </div>
            </div>

            <!-- Fleet Status Table -->
            <div class="glass rounded-2xl overflow-hidden shadow-xl">
                <div class="p-4 border-b flex justify-between items-center" style="background-color: var(--bg-sidebar); border-color: var(--border-base);">
                    <h3 class="text-xs font-bold uppercase tracking-wider" style="color: var(--text-muted);">Fleet Instance Directory</h3>
                    <span class="text-[11px] text-slate-500 font-mono">5 Containers Provisioned</span>
                </div>
                <div class="overflow-x-auto">
                    <table class="w-full text-left text-xs text-slate-300">
                        <thead class="uppercase text-[10px] font-bold border-b" style="background-color: var(--bg-input); border-color: var(--border-base); color: var(--text-muted);">
                            <tr>
                                <th class="p-3.5">Agent</th>
                                <th class="p-3.5">CT VMID</th>
                                <th class="p-3.5">IP Address</th>
                                <th class="p-3.5">Power</th>
                                <th class="p-3.5">CPU / RAM</th>
                                <th class="p-3.5">Auth Status</th>
                                <th class="p-3.5 text-right">Actions</th>
                            </tr>
                        </thead>
                        <tbody id="fleet-table-body" class="divide-y font-mono" style="border-color: var(--border-base);">
                            <!-- Populated ONCE at init, updated in-place -->
                        </tbody>
                    </table>
                </div>
            </div>
        </div>

    <!-- ============================================================ -->
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
                            <span id="skills-lib-total-badge" class="px-2 py-0.5 rounded-full text-[10px] font-mono border" style="background: var(--badge-bg); color: var(--badge-text); border-color: var(--border-base);">Loaded</span>
                        </h2>
                        <p class="text-xs text-slate-400">Manage, export, import, and inject specialized agent capabilities and workflows</p>
                    </div>
                </div>

                <!-- Target Agent Selector & Close Button -->
                <div class="flex items-center gap-3">
                    <div class="flex items-center gap-2 px-3 py-1.5 rounded-xl border" style="background-color: var(--bg-input); border-color: var(--border-base);">
                        <span class="text-[11px] font-semibold text-slate-400"><i class="fa-solid fa-robot mr-1 text-slate-500"></i> Target:</span>
                        <select id="skills-target-select" onchange="onSkillsTargetChanged()" class="bg-transparent text-xs font-semibold text-white focus:outline-none cursor-pointer">
                            <!-- Populated dynamically from active agents -->
                            <option value="agent-1" class="bg-slate-900 text-white">Agent 1</option>
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
                <div class="flex flex-wrap items-center gap-4 text-slate-400 font-mono text-[11px]" id="skills-category-stats">
                    <span><i class="fa-solid fa-database text-cyan-400 mr-1"></i> Convex</span>
                    <span><i class="fa-solid fa-shield-halved text-emerald-400 mr-1"></i> Clerk</span>
                    <span><i class="fa-solid fa-cloud text-blue-400 mr-1"></i> Cloud & GCP</span>
                    <span><i class="fa-solid fa-vial text-purple-400 mr-1"></i> DevTools</span>
                    <span><i class="fa-solid fa-gears text-amber-400 mr-1"></i> Core</span>
                </div>
                <div class="flex items-center gap-2">
                    <a href="/api/skills/download_all" target="_blank" class="px-3 py-1.5 border rounded-xl text-xs font-semibold flex items-center gap-1.5 transition text-slate-300 hover:text-white" style="background-color: var(--bg-input); border-color: var(--border-base);" title="Download complete library archive (.tar.gz)">
                        <i class="fa-solid fa-download text-sky-400"></i> Download Library
                    </a>
                    <button onclick="fetchSkillsLibrary(true)" class="px-3 py-1.5 border rounded-xl text-xs font-medium transition flex items-center gap-1.5 text-slate-300 hover:text-white" style="background-color: var(--bg-input); border-color: var(--border-base);" title="Reload library from disk">
                        <i class="fa-solid fa-rotate-right text-xs"></i> Reload
                    </button>
                    <button onclick="syncAllSkillsToTarget()" id="btn-sync-all-modal" class="px-3.5 py-1.5 btn-action-primary rounded-xl text-xs font-semibold flex items-center gap-1.5 shadow-lg transition">
                        <i class="fa-solid fa-bolt text-amber-300"></i> Sync to Agent
                    </button>
                </div>
            </div>

            <!-- Tabs Navigation -->
            <div class="px-6 pt-3 border-b flex items-center gap-2 flex-shrink-0" style="border-color: var(--border-base);">
                <button onclick="switchSkillsTab('library')" id="tab-btn-library" class="px-4 py-2 border-b-2 text-xs font-bold transition flex items-center gap-2" style="border-color: var(--accent-primary); color: var(--highlight-text);">
                    <i class="fa-solid fa-book-bookmark"></i> Skills Library (<span id="tab-lib-count">0</span>)
                </button>
                <button onclick="switchSkillsTab('installed')" id="tab-btn-installed" class="px-4 py-2 border-b-2 border-transparent text-xs font-bold transition text-slate-400 hover:text-white flex items-center gap-2">
                    <i class="fa-solid fa-circle-check"></i> Active on Agent <span id="installed-count-pill" class="px-1.5 py-0.2 rounded-full text-[10px] font-mono bg-slate-800 text-slate-300">0</span>
                </button>
                <button onclick="switchSkillsTab('import')" id="tab-btn-import" class="px-4 py-2 border-b-2 border-transparent text-xs font-bold transition text-slate-400 hover:text-white flex items-center gap-2">
                    <i class="fa-solid fa-file-arrow-up"></i> Import & Upload
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
                        <input id="skills-search-input" oninput="filterSkillsDisplay()" type="text" placeholder="Search skills by keyword, framework, or title (e.g. clerk, convex, oauth, bigquery, vitest)..." class="w-full input-box rounded-xl pl-9 pr-4 py-2 text-xs focus:outline-none focus:border-slate-400">
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

            <!-- Tab 3: Import & Upload Skill Content -->
            <div id="skills-tab-import" class="flex-1 overflow-y-auto p-6 space-y-4 scrollbar-thin hidden">
                <div class="space-y-1 pb-2 border-b" style="border-color: var(--border-base);">
                    <h3 class="text-xs font-bold uppercase tracking-wider text-white flex items-center gap-2">
                        <i class="fa-solid fa-file-arrow-up text-sky-400"></i> Import Skill Packages into Cockpit Library
                    </h3>
                    <p class="text-[11px] text-slate-400">Upload standalone <code>SKILL.md</code> files or compressed archives (<code>.zip</code>, <code>.tar.gz</code>) to permanently add them to Cockpit's central library</p>
                </div>

                <div id="skill-upload-dropzone" onclick="document.getElementById('skill-file-upload-input').click()" class="border-2 border-dashed rounded-3xl p-10 text-center cursor-pointer transition flex flex-col items-center justify-center gap-3 hover:border-sky-400/60" style="background-color: var(--bg-input); border-color: var(--border-base);">
                    <input type="file" id="skill-file-upload-input" accept=".zip,.tar.gz,.tgz,.md" class="hidden" onchange="handleSkillFileUpload(this.files)">
                    <div class="w-14 h-14 rounded-2xl flex items-center justify-center text-2xl text-sky-400 border shadow-inner" style="background-color: var(--bg-sidebar); border-color: var(--border-base);">
                        <i class="fa-solid fa-cloud-arrow-up"></i>
                    </div>
                    <div>
                        <p class="text-sm font-bold text-white">Click to browse or drag & drop skill files here</p>
                        <p class="text-xs text-slate-400 mt-1">Supports <code class="text-slate-300 font-mono">.zip</code>, <code class="text-slate-300 font-mono">.tar.gz</code>, or single <code class="text-slate-300 font-mono">SKILL.md</code> files</p>
                    </div>
                    <div id="skill-upload-status" class="text-xs font-mono text-amber-300 mt-2 hidden"></div>
                </div>

                <div class="p-4 rounded-2xl border text-xs space-y-2" style="background-color: var(--bg-sidebar); border-color: var(--border-base);">
                    <h4 class="font-bold text-white flex items-center gap-1.5"><i class="fa-solid fa-circle-info text-amber-400"></i> Packaging Best Practices</h4>
                    <p class="text-slate-400 leading-relaxed">
                        - <strong>Zip / Tar archive</strong>: Include a <code>SKILL.md</code> in the root or top directory of the archive along with any scripts, templates, or references.<br>
                        - <strong>Markdown file</strong>: Ensure the file begins with standard frontmatter (e.g. <code>name: my-skill</code> and <code>description: ...</code>).
                    </p>
                </div>
            </div>

            <!-- Tab 4: Create Custom Skill Content -->
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


        <!-- ============================================================ -->
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
            <div class="px-6 py-3.5 border-t flex justify-between items-center" style="background-color: var(--bg-sidebar); border-color: var(--border-base);">
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
            </div>
        </div>
    </div>


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
                            <i class="fa-solid fa-layer-group text-indigo-400"></i> Step 1: Select Engine Architecture
                        </h4>
                        <span class="text-[10px] text-slate-300 font-mono font-medium" id="selected-engine-badge-preview">Selected: Antigravity</span>
                    </div>
                    <div class="grid grid-cols-2 sm:grid-cols-6 gap-2.5" id="add-engine-cards">
                        <!-- Populated by JS -->
                    </div>

                    <!-- DYNAMIC REQUIREMENTS & HARDWARE SPECS CARD -->
                    <div id="engine-specs-card" class="mt-3 p-3.5 rounded-xl border transition-all" style="background-color: var(--bg-card); border-color: var(--border-base);">
                        <!-- Populated by JS -->
                    </div>
                </div>

                <!-- STEP 2: Choose Target Deployment -->
                <div class="pt-4 border-t space-y-4" style="border-color: var(--border-base);">
                    <!-- Standby Containers Section -->
                    <div>
                        <div class="flex justify-between items-center mb-2.5">
                            <h4 class="text-xs font-bold uppercase tracking-wider text-white flex items-center gap-2">
                                <i class="fa-solid fa-server text-blue-400"></i> Option A: Launch Standby Fleet Node (PVE)
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
                                <i class="fa-solid fa-network-wired text-purple-400"></i> Option B: Deploy New Agent Node
                            </h4>
                            <span class="text-[10px] text-slate-400 font-mono">Proxmox VE 8.x / Debian 12 / Ubuntu 22.04+</span>
                        </div>

                        <!-- Proxmox Host 1-Click Provisioning Command -->
                        <div class="p-3.5 rounded-xl border space-y-2" style="background-color: rgba(99, 102, 241, 0.06); border-color: rgba(99, 102, 241, 0.25);">
                            <div class="flex items-center justify-between">
                                <div class="text-[11px] font-semibold text-indigo-300 flex items-center gap-1.5">
                                    <i class="fa-solid fa-terminal text-indigo-400"></i> Proxmox Host 1-Click Provisioner (Auto-Creates VM or LXC):
                                </div>
                                <span class="text-[10px] font-mono text-indigo-400/80">root@pve (192.168.178.105)</span>
                            </div>
                            <div class="flex items-center gap-2">
                                <input id="pve-provision-cmd" readonly type="text" value="" class="flex-1 input-box rounded-lg px-3 py-2 text-xs font-mono text-indigo-200 select-all border" style="background-color: var(--bg-base); border-color: var(--border-base);">
                                <button onclick="navigator.clipboard.writeText(document.getElementById('pve-provision-cmd').value); alert('Proxmox provision command copied to clipboard!');" class="px-3 py-2 btn-action-primary rounded-lg text-xs font-semibold flex items-center gap-1.5 flex-shrink-0">
                                    <i class="fa-solid fa-copy"></i> Copy PVE Command
                                </button>
                            </div>
                        </div>

                        <!-- Inside Guest Installer -->
                        <div class="p-3.5 rounded-xl border space-y-2" style="background-color: var(--bg-input); border-color: var(--border-base);">
                            <div class="text-[11px] text-slate-300 flex items-center gap-1.5">
                                <i class="fa-solid fa-download text-amber-400"></i> Or run inside guest terminal (Self-installs dependencies, engine & bridge):
                            </div>
                            <div class="flex items-center gap-2">
                                <input id="dynamic-install-cmd" readonly type="text" value="curl -sSL http://192.168.178.168:3000/install.sh | bash" class="flex-1 input-box rounded-lg px-3 py-2 text-xs font-mono text-amber-300 select-all border" style="background-color: var(--bg-base); border-color: var(--border-base);">
                                <button onclick="navigator.clipboard.writeText(document.getElementById('dynamic-install-cmd').value); alert('Installer command copied to clipboard!');" class="px-3 py-2 btn-action-primary rounded-lg text-xs font-semibold flex items-center gap-1.5 flex-shrink-0">
                                    <i class="fa-solid fa-copy"></i> Copy Guest Command
                                </button>
                            </div>
                        </div>

                        <!-- Register Node Form -->
                        <div class="p-4 rounded-xl border space-y-3" style="background-color: var(--bg-sidebar); border-color: var(--border-base);">
                            <span class="text-xs font-semibold text-white">Register Node in Cockpit:</span>
                            <div class="grid grid-cols-1 sm:grid-cols-4 gap-2">
                                <input id="new-agent-name" type="text" placeholder="Agent Name (e.g. Codex-Node)" class="input-box rounded-lg px-3 py-1.5 text-xs text-white">
                                <input id="new-agent-role" type="text" placeholder="Role (e.g. Code Synthesis)" class="input-box rounded-lg px-3 py-1.5 text-xs text-white">
                                <input id="new-agent-ip" type="text" placeholder="IP (e.g. 192.168.178.174)" class="input-box rounded-lg px-3 py-1.5 text-xs text-white font-mono">
                                <select id="new-agent-virt-type" class="input-box rounded-lg px-3 py-1.5 text-xs text-white font-mono bg-slate-900 border border-slate-700">
                                    <option value="lxc">Proxmox LXC Container (lxc)</option>
                                    <option value="qemu">KVM Virtual Machine (qemu)</option>
                                </select>
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
    </div>

    <!-- ============================================================ -->
    <!-- IMAGE PREVIEW LIGHTBOX MODAL                                 -->
    <!-- ============================================================ -->
    <div id="image-preview-modal" class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/90 backdrop-blur-md hidden" onclick="closeImagePreview()">
        <div class="relative max-w-4xl max-h-[90vh] flex flex-col items-center" onclick="event.stopPropagation()">
            <button onclick="closeImagePreview()" class="absolute -top-10 right-0 w-8 h-8 rounded-full bg-slate-800/80 border border-slate-700 text-white flex items-center justify-center hover:bg-slate-700 transition">
                <i class="fa-solid fa-xmark"></i>
            </button>
            <img id="lightbox-img" src="" class="max-w-full max-h-[82vh] rounded-2xl border border-slate-700 shadow-2xl object-contain">
            <div id="lightbox-caption" class="text-xs text-slate-300 font-mono mt-2 text-center"></div>
        </div>
    </div>
    <!-- ============================================================ -->
    <!-- WORKSPACES HUB MODAL                                         -->
    <!-- ============================================================ -->
    <div id="workspaces-modal" class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md hidden">
        <div class="glass w-full max-w-5xl rounded-3xl overflow-hidden shadow-2xl flex flex-col max-h-[90vh] border" style="background-color: var(--bg-card); border-color: var(--border-base);">
            
            <!-- Modal Header -->
            <div class="px-6 py-4 border-b flex flex-wrap items-center justify-between gap-3 flex-shrink-0" style="background-color: var(--bg-sidebar); border-color: var(--border-base);">
                <div class="flex items-center space-x-3">
                    <div class="w-10 h-10 rounded-xl border flex items-center justify-center text-emerald-400 text-lg shadow-inner" style="background-color: var(--bg-input); border-color: var(--border-base);">
                        <i class="fa-solid fa-folder-tree"></i>
                    </div>
                    <div>
                        <h2 class="text-base font-bold text-white tracking-tight flex items-center gap-2">
                            Project Workspaces Hub
                            <span id="ws-hub-badge" class="px-2 py-0.5 rounded-full text-[10px] font-mono border" style="background: var(--badge-bg); color: var(--badge-text); border-color: var(--border-base);">0 Projects</span>
                        </h2>
                        <p class="text-xs text-slate-400">Import codebases directly into Cockpit, inspect files, and pass projects to AI agents</p>
                    </div>
                </div>

                <!-- Quick Target Agent Selector & Close Button -->
                <div class="flex items-center gap-3">
                    <div class="flex items-center gap-2 px-3 py-1.5 rounded-xl border" style="background-color: var(--bg-input); border-color: var(--border-base);">
                        <span class="text-[11px] font-semibold text-slate-400"><i class="fa-solid fa-robot mr-1 text-slate-500"></i> Target Agent:</span>
                        <select id="ws-target-agent-select" class="bg-transparent text-xs font-semibold text-white focus:outline-none cursor-pointer">
                            <option value="agent-1" class="bg-slate-900 text-white">Agent 1 (Frontend)</option>
                            <option value="agent-2" class="bg-slate-900 text-white">Agent 2 (Backend)</option>
                            <option value="agent-3" class="bg-slate-900 text-white">Agent 3 (Codex)</option>
                            <option value="agent-4" class="bg-slate-900 text-white">Agent 4 (Hermes)</option>
                            <option value="agent-5" class="bg-slate-900 text-white">Agent 5 (Open Claw)</option>
                            <option value="broadcast" class="bg-slate-900 text-amber-300 font-bold">⚡ All Active Agents (Fleet)</option>
                        </select>
                    </div>
                    <button onclick="closeWorkspacesModal()" class="w-8 h-8 rounded-xl border flex items-center justify-center text-slate-400 hover:text-white transition" style="background-color: var(--bg-input); border-color: var(--border-base);">
                        <i class="fa-solid fa-xmark"></i>
                    </button>
                </div>
            </div>

            <!-- Modal Subheader / Quick Metrics Banner -->
            <div class="px-6 py-2.5 border-b flex flex-wrap items-center justify-between gap-3 text-xs flex-shrink-0" style="border-color: var(--border-base); background-color: rgba(0,0,0,0.25);">
                <div class="flex items-center gap-4 text-slate-400 font-mono text-[11px]">
                    <span><i class="fa-solid fa-folder-open text-emerald-400 mr-1"></i> Total: <span id="ws-stats-projects" class="text-white font-bold">0</span></span>
                    <span><i class="fa-solid fa-file-code text-cyan-400 mr-1"></i> Files: <span id="ws-stats-files" class="text-white font-bold">0</span></span>
                    <span><i class="fa-solid fa-hard-drive text-amber-400 mr-1"></i> Size: <span id="ws-stats-size" class="text-white font-bold">0 KB</span></span>
                    <span><i class="fa-solid fa-bolt text-purple-400 mr-1"></i> Deployed: <span id="ws-stats-deployments" class="text-emerald-400 font-bold">0 Agents</span></span>
                </div>
                <div class="flex items-center gap-2">
                    <button onclick="switchWorkspacesTab('git')" id="btn-quick-git" class="px-3.5 py-1 rounded-xl text-xs font-semibold flex items-center gap-1.5 transition text-sky-300 border border-sky-500/30 hover:bg-sky-500/10 shadow">
                        <i class="fa-brands fa-git-alt"></i> Git Import
                    </button>
                    <button onclick="switchWorkspacesTab('upload')" id="btn-quick-upload" class="px-3.5 py-1 rounded-xl text-xs font-semibold flex items-center gap-1.5 transition text-amber-300 border border-amber-500/30 hover:bg-amber-500/10 shadow">
                        <i class="fa-solid fa-cloud-arrow-up"></i> Upload ZIP
                    </button>
                    <button onclick="switchWorkspacesTab('templates')" id="btn-quick-templates" class="px-3.5 py-1 rounded-xl text-xs font-semibold flex items-center gap-1.5 transition text-purple-300 border border-purple-500/30 hover:bg-purple-500/10 shadow">
                        <i class="fa-solid fa-wand-magic-sparkles"></i> Templates
                    </button>
                </div>
            </div>

            <!-- Tabs Navigation -->
            <div class="px-6 pt-3 border-b flex items-center gap-2 flex-shrink-0" style="border-color: var(--border-base);">
                <button onclick="switchWorkspacesTab('library')" id="ws-tab-btn-library" class="px-4 py-2 border-b-2 text-xs font-bold transition flex items-center gap-2" style="border-color: var(--accent-primary); color: var(--highlight-text);">
                    <i class="fa-solid fa-boxes-stacked"></i> Projects Library (<span id="ws-tab-count">0</span>)
                </button>
                <button onclick="switchWorkspacesTab('git')" id="ws-tab-btn-git" class="px-4 py-2 border-b-2 border-transparent text-xs font-bold transition text-slate-400 hover:text-white flex items-center gap-2">
                    <i class="fa-brands fa-git-alt text-sky-400"></i> Git Import
                </button>
                <button onclick="switchWorkspacesTab('upload')" id="ws-tab-btn-upload" class="px-4 py-2 border-b-2 border-transparent text-xs font-bold transition text-slate-400 hover:text-white flex items-center gap-2">
                    <i class="fa-solid fa-cloud-arrow-up text-amber-400"></i> Upload Archive
                </button>
                <button onclick="switchWorkspacesTab('templates')" id="ws-tab-btn-templates" class="px-4 py-2 border-b-2 border-transparent text-xs font-bold transition text-slate-400 hover:text-white flex items-center gap-2">
                    <i class="fa-solid fa-wand-magic-sparkles text-purple-400"></i> Starter Templates
                </button>
                <button onclick="switchWorkspacesTab('matrix')" id="ws-tab-btn-matrix" class="px-4 py-2 border-b-2 border-transparent text-xs font-bold transition text-slate-400 hover:text-white flex items-center gap-2">
                    <i class="fa-solid fa-network-wired text-emerald-400"></i> Agent Mount Matrix
                </button>
            </div>

            <!-- Tab 1: Projects Library Content -->
            <div id="ws-tab-library" class="flex-1 overflow-y-auto p-6 space-y-4 scrollbar-thin">
                <div class="flex flex-col sm:flex-row gap-3 items-stretch sm:items-center justify-between">
                    <div class="relative flex-1">
                        <i class="fa-solid fa-magnifying-glass absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400 text-xs"></i>
                        <input id="ws-search-input" oninput="filterWorkspacesDisplay()" type="text" placeholder="Search imported projects by name, language, or stack (e.g. react, python, next, api)..." class="w-full input-box rounded-xl pl-9 pr-4 py-2 text-xs focus:outline-none focus:border-slate-400">
                    </div>
                    <div class="flex items-center gap-2">
                        <button onclick="switchWorkspacesTab('git')" class="px-3 py-2 rounded-xl border text-xs font-semibold text-sky-400 hover:text-white hover:bg-sky-500/10 transition flex items-center gap-1.5" style="background-color: var(--bg-input); border-color: var(--border-base);">
                            <i class="fa-brands fa-git-alt"></i> Import from Git
                        </button>
                        <button onclick="switchWorkspacesTab('upload')" class="px-3 py-2 rounded-xl border text-xs font-semibold text-amber-400 hover:text-white hover:bg-amber-500/10 transition flex items-center gap-1.5" style="background-color: var(--bg-input); border-color: var(--border-base);">
                            <i class="fa-solid fa-file-zipper"></i> Upload ZIP
                        </button>
                    </div>
                </div>

                <!-- Projects Cards Grid -->
                <div id="workspaces-cards-grid" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3.5 pt-1">
                    <!-- Populated dynamically -->
                </div>
            </div>

            <!-- Tab 2: Dedicated Git Import Content -->
            <div id="ws-tab-git" class="flex-1 overflow-y-auto p-6 space-y-6 scrollbar-thin hidden">
                <div class="grid grid-cols-1 lg:grid-cols-12 gap-6">
                    
                    <!-- Left 7 cols: Git Clone Form -->
                    <div class="lg:col-span-7 space-y-4">
                        <div class="glass p-5 rounded-2xl border space-y-4" style="background-color: var(--bg-input); border-color: var(--border-base);">
                            <div class="flex items-center justify-between">
                                <div class="flex items-center gap-3">
                                    <div class="w-10 h-10 rounded-xl flex items-center justify-center text-sky-400 bg-sky-500/10 border border-sky-500/30 text-xl shadow-inner">
                                        <i class="fa-brands fa-git-alt"></i>
                                    </div>
                                    <div>
                                        <h3 class="text-sm font-bold text-white">Import from Git Repository</h3>
                                        <p class="text-xs text-slate-400">Clone and ingest any repository from GitHub, GitLab, Bitbucket, or private Git servers</p>
                                    </div>
                                </div>
                                <span class="px-2.5 py-0.5 rounded-full text-[10px] font-mono border bg-sky-500/10 text-sky-400 border-sky-500/30 font-bold">git clone --depth 1</span>
                            </div>

                            <div class="space-y-3.5 pt-2">
                                <!-- Repo URL -->
                                <div>
                                    <div class="flex justify-between items-center mb-1">
                                        <label class="text-[10px] uppercase font-bold text-slate-300">Repository URL or Shorthand *</label>
                                        <span class="text-[10px] text-sky-400 font-mono">e.g. owner/repo or full HTTPS</span>
                                    </div>
                                    <div class="relative">
                                        <i class="fa-brands fa-github absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400 text-sm"></i>
                                        <input id="ws-git-url-input" type="text" placeholder="https://github.com/username/repository or owner/repo (e.g. facebook/react)" class="w-full input-box rounded-xl pl-9 pr-4 py-2.5 text-xs font-mono text-white focus:border-sky-400 focus:outline-none">
                                    </div>
                                </div>

                                <!-- Branch & Token Row -->
                                <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
                                    <div>
                                        <label class="block text-[10px] uppercase font-bold text-slate-300 mb-1">Branch (Optional)</label>
                                        <div class="relative">
                                            <i class="fa-solid fa-code-branch absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400 text-xs"></i>
                                            <input id="ws-git-branch-input" type="text" placeholder="main (default)" class="w-full input-box rounded-xl pl-9 pr-3 py-2 text-xs font-mono text-white focus:border-sky-400 focus:outline-none">
                                        </div>
                                    </div>

                                    <div>
                                        <div class="flex justify-between items-center mb-1">
                                            <label class="text-[10px] uppercase font-bold text-slate-300">Personal Access Token</label>
                                            <span class="text-[10px] text-slate-500">Private repos</span>
                                        </div>
                                        <div class="relative">
                                            <i class="fa-solid fa-key absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400 text-xs"></i>
                                            <input id="ws-git-token-input" type="password" placeholder="ghp_xxxxxxxxxxxx" class="w-full input-box rounded-xl pl-9 pr-9 py-2 text-xs font-mono text-white focus:border-sky-400 focus:outline-none">
                                            <button type="button" onclick="toggleGitTokenVisibility()" class="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-white transition">
                                                <i id="ws-git-token-eye" class="fa-solid fa-eye text-xs"></i>
                                            </button>
                                        </div>
                                    </div>
                                </div>

                                <!-- Project Name & Description -->
                                <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
                                    <div>
                                        <label class="block text-[10px] uppercase font-bold text-slate-300 mb-1">Project Name (Optional)</label>
                                        <input id="ws-git-name-input" type="text" placeholder="Defaults to repository name" class="w-full input-box rounded-xl px-3 py-2 text-xs text-white focus:border-sky-400 focus:outline-none">
                                    </div>
                                    <div>
                                        <label class="block text-[10px] uppercase font-bold text-slate-300 mb-1">Description</label>
                                        <input id="ws-git-desc-input" type="text" placeholder="Short description" class="w-full input-box rounded-xl px-3 py-2 text-xs text-white focus:border-sky-400 focus:outline-none">
                                    </div>
                                </div>

                                <!-- Target Agent & Auto Deploy -->
                                <div class="p-3 rounded-xl border flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3" style="background-color: var(--bg-base); border-color: var(--border-base);">
                                    <div class="flex items-center gap-2">
                                        <input type="checkbox" id="ws-git-auto-deploy" checked class="w-4 h-4 rounded text-sky-500">
                                        <label for="ws-git-auto-deploy" class="text-xs text-slate-200 cursor-pointer font-medium">Mount to agent immediately after clone</label>
                                    </div>
                                    <div class="flex items-center gap-2 w-full sm:w-auto">
                                        <span class="text-[11px] text-slate-400 font-semibold">Agent:</span>
                                        <select id="ws-git-target-agent-select" class="input-box rounded-lg px-2.5 py-1 text-xs text-white focus:outline-none cursor-pointer">
                                            <option value="agent-1">Agent 1</option>
                                            <option value="agent-2">Agent 2</option>
                                            <option value="agent-3">Agent 3</option>
                                            <option value="agent-4">Agent 4</option>
                                            <option value="agent-5">Agent 5</option>
                                            <option value="broadcast">⚡ All Active Agents</option>
                                        </select>
                                    </div>
                                </div>
                            </div>

                            <button onclick="submitGitClone()" id="btn-submit-ws-clone" class="w-full py-3 btn-action-primary font-bold rounded-xl text-xs transition shadow-xl flex items-center justify-center gap-2 tracking-wide">
                                <i class="fa-brands fa-git-alt text-base"></i> Clone Repository & Ingest Workspace
                            </button>
                        </div>
                    </div>

                    <!-- Right 5 cols: Presets & Guides -->
                    <div class="lg:col-span-5 space-y-4">
                        <!-- 1-Click Popular Starters -->
                        <div class="glass p-5 rounded-2xl border space-y-3.5" style="background-color: var(--bg-input); border-color: var(--border-base);">
                            <div class="flex items-center justify-between">
                                <h4 class="text-xs font-bold uppercase tracking-wider text-white flex items-center gap-2">
                                    <i class="fa-solid fa-fire text-amber-400"></i> Popular Starters & Demos
                                </h4>
                                <span class="text-[10px] text-slate-400">1-click fill</span>
                            </div>
                            <div class="space-y-2">
                                <div onclick="applyGitPreset('https://github.com/vercel/next-learn', 'main', 'nextjs_demo', 'Next.js Official Learn & Demo App')" class="p-2.5 rounded-xl border cursor-pointer hover:border-sky-400 transition flex items-center justify-between group" style="background-color: var(--bg-base); border-color: var(--border-base);">
                                    <div class="flex items-center gap-2.5 min-w-0">
                                        <i class="fa-solid fa-n text-white text-base"></i>
                                        <div class="min-w-0">
                                            <div class="text-xs font-bold text-white group-hover:text-sky-400 transition">Next.js App Router Demo</div>
                                            <div class="text-[10px] text-slate-400 font-mono truncate">vercel/next-learn</div>
                                        </div>
                                    </div>
                                    <i class="fa-solid fa-arrow-turn-down text-slate-500 group-hover:text-sky-400 text-xs"></i>
                                </div>

                                <div onclick="applyGitPreset('https://github.com/vitejs/vite', 'main', 'vite_core', 'Vite Next Generation Frontend Tooling')" class="p-2.5 rounded-xl border cursor-pointer hover:border-purple-400 transition flex items-center justify-between group" style="background-color: var(--bg-base); border-color: var(--border-base);">
                                    <div class="flex items-center gap-2.5 min-w-0">
                                        <i class="fa-solid fa-bolt text-purple-400 text-base"></i>
                                        <div class="min-w-0">
                                            <div class="text-xs font-bold text-white group-hover:text-purple-400 transition">Vite Frontend Project</div>
                                            <div class="text-[10px] text-slate-400 font-mono truncate">vitejs/vite</div>
                                        </div>
                                    </div>
                                    <i class="fa-solid fa-arrow-turn-down text-slate-500 group-hover:text-purple-400 text-xs"></i>
                                </div>

                                <div onclick="applyGitPreset('https://github.com/tiangolo/full-stack-fastapi-template', 'master', 'fastapi_template', 'FastAPI Full Stack Project Template')" class="p-2.5 rounded-xl border cursor-pointer hover:border-teal-400 transition flex items-center justify-between group" style="background-color: var(--bg-base); border-color: var(--border-base);">
                                    <div class="flex items-center gap-2.5 min-w-0">
                                        <i class="fa-brands fa-python text-teal-400 text-base"></i>
                                        <div class="min-w-0">
                                            <div class="text-xs font-bold text-white group-hover:text-teal-400 transition">FastAPI Python Template</div>
                                            <div class="text-[10px] text-slate-400 font-mono truncate">tiangolo/full-stack-fastapi-template</div>
                                        </div>
                                    </div>
                                    <i class="fa-solid fa-arrow-turn-down text-slate-500 group-hover:text-teal-400 text-xs"></i>
                                </div>

                                <div onclick="applyGitPreset('https://github.com/expressjs/express', 'master', 'express_api', 'Express.js Fast, unopinionated minimalist web framework')" class="p-2.5 rounded-xl border cursor-pointer hover:border-emerald-400 transition flex items-center justify-between group" style="background-color: var(--bg-base); border-color: var(--border-base);">
                                    <div class="flex items-center gap-2.5 min-w-0">
                                        <i class="fa-brands fa-node-js text-emerald-400 text-base"></i>
                                        <div class="min-w-0">
                                            <div class="text-xs font-bold text-white group-hover:text-emerald-400 transition">Express.js API Framework</div>
                                            <div class="text-[10px] text-slate-400 font-mono truncate">expressjs/express</div>
                                        </div>
                                    </div>
                                    <i class="fa-solid fa-arrow-turn-down text-slate-500 group-hover:text-emerald-400 text-xs"></i>
                                </div>
                            </div>
                        </div>

                        <!-- Git Capabilities Summary Card -->
                        <div class="glass p-4 rounded-2xl border space-y-2 text-xs" style="background-color: var(--bg-input); border-color: var(--border-base);">
                            <span class="text-[10px] uppercase font-bold text-slate-400 tracking-wider flex items-center gap-1.5">
                                <i class="fa-solid fa-circle-check text-sky-400"></i> Git Engine Highlights
                            </span>
                            <ul class="space-y-1.5 text-[11px] text-slate-300">
                                <li class="flex items-center gap-2"><i class="fa-solid fa-check text-emerald-400 text-[10px]"></i> Shallow clone (<code>--depth 1</code>) for blazing speed</li>
                                <li class="flex items-center gap-2"><i class="fa-solid fa-check text-emerald-400 text-[10px]"></i> Shorthand <code>org/repo</code> expanded automatically</li>
                                <li class="flex items-center gap-2"><i class="fa-solid fa-check text-emerald-400 text-[10px]"></i> Token masked and never logged</li>
                                <li class="flex items-center gap-2"><i class="fa-solid fa-check text-emerald-400 text-[10px]"></i> 1-click <code>Git Pull</code> sync directly from project cards</li>
                            </ul>
                        </div>
                    </div>

                </div>
            </div>

            <!-- Tab 3: Upload Archive Content -->
            <div id="ws-tab-upload" class="flex-1 overflow-y-auto p-6 space-y-5 scrollbar-thin hidden">
                <div class="max-w-2xl mx-auto glass p-6 rounded-2xl border space-y-4" style="background-color: var(--bg-input); border-color: var(--border-base);">
                    <div class="flex items-center gap-3 text-white font-bold text-sm">
                        <div class="w-10 h-10 rounded-xl flex items-center justify-center text-amber-400 bg-amber-500/10 border border-amber-500/30 text-lg">
                            <i class="fa-solid fa-file-zipper"></i>
                        </div>
                        <div>
                            <h3 class="text-sm font-bold text-white">Upload Project Archive</h3>
                            <p class="text-xs text-slate-400">Upload a <code>.zip</code>, <code>.tar.gz</code>, or <code>.tar</code> bundle from your computer</p>
                        </div>
                    </div>
                    
                    <!-- Drag & Drop Zone -->
                    <div id="ws-drop-zone" onclick="document.getElementById('ws-archive-file-input').click()" class="border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition hover:border-emerald-400" style="border-color: var(--border-base); background-color: var(--bg-base);">
                        <input type="file" id="ws-archive-file-input" accept=".zip,.tar,.gz,.tgz" class="hidden" onchange="handleWsFileSelect(this.files)">
                        <i class="fa-solid fa-cloud-arrow-up text-3xl text-slate-400 mb-2"></i>
                        <div class="text-xs font-semibold text-slate-200" id="ws-dropzone-label">Drop ZIP or Tar file here, or click to browse</div>
                        <div class="text-[10px] text-slate-500 mt-1">Supports GitHub ZIP exports & local bundles (auto-flattens root folder)</div>
                    </div>

                    <div class="space-y-2.5 pt-1">
                        <input id="ws-upload-name-input" type="text" placeholder="Project Name (optional, defaults to file name)" class="w-full input-box rounded-xl px-3 py-2 text-xs text-white">
                        <input id="ws-upload-desc-input" type="text" placeholder="Short description (e.g. Next.js storefront)" class="w-full input-box rounded-xl px-3 py-2 text-xs text-white">
                        <div class="flex items-center gap-2 text-xs text-slate-300 pt-1">
                            <input type="checkbox" id="ws-upload-auto-deploy" checked class="w-4 h-4 rounded text-emerald-500">
                            <label for="ws-upload-auto-deploy" class="cursor-pointer">Pass directly to target agent after import</label>
                        </div>
                    </div>

                    <button onclick="submitWorkspaceArchiveUpload()" id="btn-submit-ws-upload" class="w-full py-3 btn-action-primary font-bold rounded-xl text-xs transition shadow-lg flex items-center justify-center gap-2">
                        <i class="fa-solid fa-upload"></i> Import & Unpack Archive
                    </button>
                </div>
            </div>

            <!-- Tab 4: Starter Templates Content -->
            <div id="ws-tab-templates" class="flex-1 overflow-y-auto p-6 space-y-5 scrollbar-thin hidden">
                <div class="max-w-4xl mx-auto space-y-4">
                    <div class="text-center space-y-1">
                        <h3 class="text-base font-bold text-white">Initialize Starter Template</h3>
                        <p class="text-xs text-slate-400">Scaffold a structured starter project ready for immediate agent coding and execution.</p>
                    </div>

                    <div class="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2">
                        <div onclick="createWorkspaceTemplate('react')" class="glass p-5 rounded-2xl border cursor-pointer transition hover:border-cyan-400 hover:bg-cyan-500/5 group" style="background-color: var(--bg-input); border-color: var(--border-base);">
                            <div class="flex items-start justify-between">
                                <div class="w-10 h-10 rounded-xl flex items-center justify-center text-cyan-400 bg-cyan-500/10 border border-cyan-500/30 text-xl">
                                    <i class="fa-brands fa-react"></i>
                                </div>
                                <span class="text-[10px] font-mono font-bold px-2 py-0.5 rounded-full border bg-cyan-500/10 text-cyan-400 border-cyan-500/30">Vite + TS</span>
                            </div>
                            <h4 class="text-sm font-bold text-white mt-3 group-hover:text-cyan-400 transition">React + Vite + TypeScript</h4>
                            <p class="text-xs text-slate-400 mt-1">Preconfigured modern React app with Vitest test runner, Tailwind support, and TypeScript.</p>
                        </div>

                        <div onclick="createWorkspaceTemplate('node')" class="glass p-5 rounded-2xl border cursor-pointer transition hover:border-emerald-400 hover:bg-emerald-500/5 group" style="background-color: var(--bg-input); border-color: var(--border-base);">
                            <div class="flex items-start justify-between">
                                <div class="w-10 h-10 rounded-xl flex items-center justify-center text-emerald-400 bg-emerald-500/10 border border-emerald-500/30 text-xl">
                                    <i class="fa-brands fa-node-js"></i>
                                </div>
                                <span class="text-[10px] font-mono font-bold px-2 py-0.5 rounded-full border bg-emerald-500/10 text-emerald-400 border-emerald-500/30">Node.js</span>
                            </div>
                            <h4 class="text-sm font-bold text-white mt-3 group-hover:text-emerald-400 transition">Node.js + Express API</h4>
                            <p class="text-xs text-slate-400 mt-1">Lightweight REST API service with JSON routing, CORS headers, and NPM start script.</p>
                        </div>

                        <div onclick="createWorkspaceTemplate('python')" class="glass p-5 rounded-2xl border cursor-pointer transition hover:border-amber-400 hover:bg-amber-500/5 group" style="background-color: var(--bg-input); border-color: var(--border-base);">
                            <div class="flex items-start justify-between">
                                <div class="w-10 h-10 rounded-xl flex items-center justify-center text-amber-400 bg-amber-500/10 border border-amber-500/30 text-xl">
                                    <i class="fa-brands fa-python"></i>
                                </div>
                                <span class="text-[10px] font-mono font-bold px-2 py-0.5 rounded-full border bg-amber-500/10 text-amber-400 border-amber-500/30">Python 3</span>
                            </div>
                            <h4 class="text-sm font-bold text-white mt-3 group-hover:text-amber-400 transition">Python Flask Service</h4>
                            <p class="text-xs text-slate-400 mt-1">Clean microservice backend with `app.py`, `requirements.txt`, and pytest test suite.</p>
                        </div>

                        <div onclick="createWorkspaceTemplate('blank')" class="glass p-5 rounded-2xl border cursor-pointer transition hover:border-slate-300 hover:bg-white/5 group" style="background-color: var(--bg-input); border-color: var(--border-base);">
                            <div class="flex items-start justify-between">
                                <div class="w-10 h-10 rounded-xl flex items-center justify-center text-slate-300 bg-slate-500/10 border border-slate-500/30 text-xl">
                                    <i class="fa-solid fa-file-lines"></i>
                                </div>
                                <span class="text-[10px] font-mono font-bold px-2 py-0.5 rounded-full border bg-slate-500/10 text-slate-300 border-slate-500/30">Blank</span>
                            </div>
                            <h4 class="text-sm font-bold text-white mt-3 group-hover:text-slate-200 transition">Clean Blank Workspace</h4>
                            <p class="text-xs text-slate-400 mt-1">Empty directory structure with standard `.gitignore` and starter `README.md`.</p>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Tab 3: Agent Mount Matrix Content -->
            <div id="ws-tab-matrix" class="flex-1 overflow-y-auto p-6 space-y-4 scrollbar-thin hidden">
                <div class="glass rounded-2xl overflow-hidden shadow-xl border" style="border-color: var(--border-base);">
                    <div class="p-4 border-b flex justify-between items-center" style="background-color: var(--bg-sidebar); border-color: var(--border-base);">
                        <h3 class="text-xs font-bold uppercase tracking-wider text-white flex items-center gap-2">
                            <i class="fa-solid fa-network-wired text-emerald-400"></i> Active Workspaces on Agent Containers
                        </h3>
                        <span class="text-[11px] text-slate-400 font-mono">Mounted at /home/ubuntu/workspace</span>
                    </div>
                    <div class="overflow-x-auto">
                        <table class="w-full text-left text-xs text-slate-300">
                            <thead class="uppercase text-[10px] font-bold border-b" style="background-color: var(--bg-input); border-color: var(--border-base); color: var(--text-muted);">
                                <tr>
                                    <th class="p-3.5">Agent</th>
                                    <th class="p-3.5">Container</th>
                                    <th class="p-3.5">Current Project</th>
                                    <th class="p-3.5">Path & Files</th>
                                    <th class="p-3.5">Status</th>
                                    <th class="p-3.5 text-right">Actions</th>
                                </tr>
                            </thead>
                            <tbody id="ws-matrix-table-body" class="divide-y font-mono" style="border-color: var(--border-base);">
                                <!-- Populated dynamically -->
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>

            <!-- Modal Footer -->
            <div class="px-6 py-3 border-t flex justify-between items-center" style="background-color: var(--bg-sidebar); border-color: var(--border-base);">
                <div class="text-[11px] text-slate-400 flex items-center gap-2">
                    <i class="fa-solid fa-shield-halved text-emerald-400"></i>
                    <span>Mounted to agents via tar.gz stream • Native /home/ubuntu/workspace</span>
                </div>
                <button onclick="closeWorkspacesModal()" class="px-4 py-1.5 border rounded-xl text-xs font-medium transition" style="background-color: var(--bg-input); border-color: var(--border-base); color: var(--text-main);">
                    Close
                </button>
            </div>
        </div>
    </div>


    <!-- ============================================================ -->
    <!-- WORKSPACE CODE EXPLORER & FILE TREE MODAL                    -->
    <!-- ============================================================ -->
    <div id="workspace-explorer-modal" class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/85 backdrop-blur-md hidden">
        <div class="glass w-full max-w-6xl rounded-3xl overflow-hidden shadow-2xl flex flex-col h-[90vh] border" style="background-color: var(--bg-card); border-color: var(--border-base);">
            
            <!-- Explorer Header -->
            <div class="px-6 py-3.5 border-b flex flex-wrap items-center justify-between gap-3 flex-shrink-0" style="background-color: var(--bg-sidebar); border-color: var(--border-base);">
                <div class="flex items-center space-x-3 min-w-0">
                    <div class="w-9 h-9 rounded-xl border flex items-center justify-center text-cyan-400 text-base" style="background-color: var(--bg-input); border-color: var(--border-base);">
                        <i class="fa-solid fa-code-compare"></i>
                    </div>
                    <div class="min-w-0">
                        <div class="flex items-center gap-2">
                            <h3 class="text-sm font-bold text-white truncate" id="explorer-ws-title">Project Code Explorer</h3>
                            <span id="explorer-stack-badge" class="px-2 py-0.2 rounded-full text-[10px] font-mono border" style="background: var(--badge-bg); color: var(--badge-text); border-color: var(--border-base);">Stack</span>
                        </div>
                        <p class="text-[11px] text-slate-400 font-mono truncate" id="explorer-ws-path">/usr/local/share/cockpit/workspaces/...</p>
                    </div>
                </div>

                <!-- Action buttons -->
                <div class="flex items-center gap-2">
                    <div class="flex items-center gap-1.5 px-2.5 py-1.5 border rounded-xl text-xs" style="background-color: var(--bg-input); border-color: var(--border-base);">
                        <span class="text-[11px] text-slate-400">Deploy to:</span>
                        <select id="explorer-deploy-target-select" class="bg-transparent text-xs text-slate-200 focus:outline-none cursor-pointer">
                            <option value="agent-1" class="bg-slate-900 text-white">Agent 1</option>
                            <option value="agent-2" class="bg-slate-900 text-white">Agent 2</option>
                            <option value="agent-3" class="bg-slate-900 text-white">Agent 3</option>
                            <option value="agent-4" class="bg-slate-900 text-white">Agent 4</option>
                            <option value="agent-5" class="bg-slate-900 text-white">Agent 5</option>
                            <option value="broadcast" class="bg-slate-900 text-amber-300 font-bold">All Agents</option>
                        </select>
                        <button onclick="deployFromExplorer()" class="px-2.5 py-0.5 btn-action-primary rounded-lg text-xs font-semibold flex items-center gap-1">
                            <i class="fa-solid fa-bolt"></i> Deploy
                        </button>
                    </div>

                    <button id="explorer-git-pull-btn" onclick="pullGitFromExplorer()" class="px-3 py-1.5 border rounded-xl text-xs font-semibold transition flex items-center gap-1.5 text-sky-300 hover:text-white hover:bg-sky-500/20 hidden" style="background-color: var(--bg-input); border-color: var(--border-base);" title="Pull latest commits from remote Git repository">
                        <i class="fa-brands fa-git-alt text-sky-400"></i> Git Pull
                    </button>

                    <button onclick="downloadFromExplorer()" class="px-3 py-1.5 border rounded-xl text-xs font-semibold transition flex items-center gap-1.5 text-slate-300 hover:text-white" style="background-color: var(--bg-input); border-color: var(--border-base);" title="Download project ZIP archive">
                        <i class="fa-solid fa-download text-emerald-400"></i> ZIP
                    </button>

                    <button onclick="closeWorkspaceExplorer()" class="w-8 h-8 rounded-xl border flex items-center justify-center text-slate-400 hover:text-white transition" style="background-color: var(--bg-input); border-color: var(--border-base);">
                        <i class="fa-solid fa-xmark"></i>
                    </button>
                </div>
            </div>

            <!-- Explorer Split Pane -->
            <div class="flex-1 flex min-h-0 overflow-hidden">
                <!-- Left: File Tree Directory -->
                <div class="w-72 sm:w-80 border-r flex flex-col flex-shrink-0 overflow-hidden" style="background-color: var(--bg-sidebar); border-color: var(--border-base);">
                    <div class="p-3 border-b" style="border-color: var(--border-base);">
                        <div class="relative">
                            <i class="fa-solid fa-filter absolute left-3 top-1/2 -translate-y-1/2 text-slate-500 text-[10px]"></i>
                            <input id="explorer-filter-input" oninput="filterExplorerTree(this.value)" type="text" placeholder="Filter files..." class="w-full input-box rounded-xl pl-8 pr-3 py-1.5 text-xs focus:outline-none">
                        </div>
                    </div>
                    <div class="flex-1 overflow-y-auto p-3 space-y-1 font-mono text-xs scrollbar-thin" id="explorer-tree-container">
                        <!-- Tree nodes populated dynamically -->
                    </div>
                </div>

                <!-- Right: Code Viewer Pane -->
                <div class="flex-1 flex flex-col min-w-0 bg-terminal overflow-hidden">
                    <!-- File Toolbar -->
                    <div class="px-4 py-2 border-b flex items-center justify-between text-xs" style="background-color: rgba(0,0,0,0.3); border-color: var(--border-base);">
                        <div class="flex items-center gap-2 truncate">
                            <i class="fa-regular fa-file-code text-cyan-400" id="explorer-file-icon"></i>
                            <span class="font-mono text-slate-200 truncate" id="explorer-active-filename">Select a file to preview</span>
                            <span class="text-[10px] text-slate-500 font-mono" id="explorer-file-metrics"></span>
                        </div>
                        <div class="flex items-center gap-2">
                            <button onclick="copyExplorerCode()" id="btn-copy-code" class="px-2.5 py-1 border rounded-lg text-xs transition flex items-center gap-1 text-slate-400 hover:text-white" style="background-color: var(--bg-input); border-color: var(--border-base);">
                                <i class="fa-regular fa-copy"></i> Copy
                            </button>
                        </div>
                    </div>

                    <!-- Code Display Area -->
                    <div class="flex-1 overflow-auto p-4 font-mono text-xs leading-relaxed text-slate-300 scrollbar-thin select-text" id="explorer-code-container">
                        <div class="h-full flex flex-col items-center justify-center text-slate-500 italic space-y-2">
                            <i class="fa-regular fa-folder-open text-3xl"></i>
                            <span>Select any file from the project tree to inspect its code</span>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Explorer Footer -->
            <div class="px-6 py-2 border-t flex justify-between items-center text-xs" style="background-color: var(--bg-sidebar); border-color: var(--border-base);">
                <span class="text-[11px] text-slate-400 font-mono" id="explorer-footer-path">Ready</span>
                <span class="text-[11px] text-slate-500 font-mono">Antigravity Cockpit Code Inspector</span>
            </div>
        </div>
    </div>
    <!-- ============================================================ -->
    <!-- CEO EXECUTIVE SUITE & FLEET ORCHESTRATOR MODAL (PAPERCLIP)     -->
    <!-- ============================================================ -->
    <div id="ceo-modal" class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/85 backdrop-blur-md hidden">
        <div class="glass w-full max-w-6xl rounded-3xl overflow-hidden shadow-2xl flex flex-col max-h-[92vh] border" style="background-color: var(--bg-card); border-color: var(--border-base);">
            
            <!-- Modal Header -->
            <div class="px-6 py-4 border-b flex flex-wrap items-center justify-between gap-3 flex-shrink-0" style="background-color: var(--bg-sidebar); border-color: var(--border-base);">
                <div class="flex items-center space-x-3">
                    <div class="w-10 h-10 rounded-xl border flex items-center justify-center text-xl shadow-inner" style="background-color: var(--bg-input); border-color: var(--border-base);">
                        👑
                    </div>
                    <div>
                        <h2 class="text-base font-bold text-white tracking-tight flex items-center gap-2">
                            Executive Suite & Fleet Orchestrator
                            <span class="px-2 py-0.5 rounded-full text-[10px] font-mono border" style="background: rgba(245, 158, 11, 0.15); color: #f59e0b; border-color: rgba(245, 158, 11, 0.3);">
                                Paperclip Architecture
                            </span>
                        </h2>
                        <p class="text-xs text-slate-400">Hierarchical task delegation, role-based subagent routing & autonomous heartbeat maintenance</p>
                    </div>
                </div>

                <!-- Heartbeat Controls & Close Button -->
                <div class="flex items-center gap-3">
                    <span id="ceo-heartbeat-badge" class="flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-mono font-bold border" style="background: rgba(16, 185, 129, 0.12); color: #10b981; border-color: rgba(16, 185, 129, 0.3);">
                        <span class="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
                        Heartbeat #<span id="ceo-pulse-counter">1</span>
                    </span>
                    <button onclick="triggerCeoPulse()" id="btn-ceo-pulse" class="px-3 py-1.5 rounded-xl text-xs font-bold transition flex items-center gap-1.5 border hover:border-rose-400/50" style="background-color: var(--bg-input); border-color: var(--border-base); color: var(--text-main);" title="Trigger immediate CEO Heartbeat checklist">
                        <i class="fa-solid fa-heart-pulse text-rose-400"></i>
                        <span>Pulse Now</span>
                    </button>
                    <button onclick="closeCeoModal()" class="w-8 h-8 rounded-full flex items-center justify-center transition border hover:opacity-80" style="background-color: var(--bg-input); border-color: var(--border-base); color: var(--text-main);">
                        <i class="fa-solid fa-xmark text-sm"></i>
                    </button>
                </div>
            </div>

            <!-- Executive Summary Alert Banner -->
            <div class="px-6 py-2.5 border-b flex items-center justify-between text-xs flex-shrink-0" style="background: rgba(245, 158, 11, 0.05); border-color: var(--border-base);">
                <div class="flex items-center gap-2.5 overflow-hidden">
                    <span class="px-2 py-0.5 rounded text-[10px] font-bold font-mono uppercase bg-amber-500/20 text-amber-300 border border-amber-500/30">CEO Memo</span>
                    <span id="ceo-summary-banner" class="text-slate-300 font-medium truncate">CEO Orchestrator active. Standing by for Board Directives.</span>
                </div>
                <div class="text-[11px] text-slate-500 font-mono flex-shrink-0 ml-4 flex items-center gap-2">
                    <span id="ceo-last-pulse-time">Updated just now</span>
                </div>
            </div>

            <!-- Navigation Tabs & P&L Velocity Metrics -->
            <div class="px-6 pt-3 border-b flex flex-wrap items-center justify-between gap-4 flex-shrink-0" style="background-color: var(--bg-sidebar); border-color: var(--border-base);">
                <div class="flex space-x-1" id="ceo-tab-nav">
                    <button onclick="switchCeoTab('kanban')" id="ceo-tab-btn-kanban" class="px-4 py-2 border-b-2 text-xs font-bold transition flex items-center gap-2" style="border-color: var(--accent-primary); color: var(--highlight-text);">
                        <i class="fa-solid fa-table-columns"></i>
                        <span>Work Orders Kanban</span>
                        <span id="badge-total-tasks" class="px-1.5 py-0.2 rounded-full text-[10px] bg-white/10">0</span>
                    </button>
                    <button onclick="switchCeoTab('org')" id="ceo-tab-btn-org" class="px-4 py-2 border-b-2 border-transparent text-xs font-bold transition text-slate-400 hover:text-white flex items-center gap-2">
                        <i class="fa-solid fa-sitemap"></i>
                        <span>Org Chart & Roles</span>
                    </button>
                    <button onclick="switchCeoTab('heartbeat')" id="ceo-tab-btn-heartbeat" class="px-4 py-2 border-b-2 border-transparent text-xs font-bold transition text-slate-400 hover:text-white flex items-center gap-2">
                        <i class="fa-solid fa-clipboard-check"></i>
                        <span>Heartbeat & Audit</span>
                    </button>
                    <button onclick="switchCeoTab('charter')" id="ceo-tab-btn-charter" class="px-4 py-2 border-b-2 border-transparent text-xs font-bold transition text-slate-400 hover:text-white flex items-center gap-2">
                        <i class="fa-solid fa-scroll"></i>
                        <span>CEO Operating Charter</span>
                    </button>
                </div>

                <!-- High-level Velocity Counters -->
                <div class="flex items-center gap-2 pb-2">
                    <div class="flex items-center gap-1.5 px-2.5 py-1 rounded-lg border text-[11px] font-mono" style="background-color: var(--bg-input); border-color: var(--border-base);">
                        <span class="text-slate-400">Velocity:</span>
                        <span id="metric-velocity" class="font-bold text-emerald-400">100%</span>
                    </div>
                    <div class="flex items-center gap-1.5 px-2.5 py-1 rounded-lg border text-[11px] font-mono" style="background-color: var(--bg-input); border-color: var(--border-base);">
                        <span class="text-blue-400 font-bold" id="metric-in-progress">0</span> <span class="text-slate-400">active</span>
                    </div>
                    <div class="flex items-center gap-1.5 px-2.5 py-1 rounded-lg border text-[11px] font-mono" style="background-color: var(--bg-input); border-color: var(--border-base);">
                        <span class="text-rose-400 font-bold" id="metric-blocked">0</span> <span class="text-slate-400">blocked</span>
                    </div>
                </div>
            </div>

            <!-- Modal Body (Scrollable Tab Contents) -->
            <div class="flex-1 overflow-y-auto p-6 space-y-6 scrollbar-thin" style="background-color: var(--bg-card);">

                <!-- BOARD DIRECTIVE CONSOLE (Always Visible at Top) -->
                <div class="p-4 rounded-2xl border space-y-3 relative overflow-hidden shadow-sm" style="background-color: var(--bg-input); border-color: var(--border-base);">
                    <div class="flex items-center justify-between">
                        <span class="text-xs font-bold uppercase tracking-wider text-slate-400 flex items-center gap-2">
                            <span class="text-amber-400 font-normal">👑</span> Board Directive Console (Give Orders to CEO)
                        </span>
                        <span class="text-[11px] text-slate-500 font-mono">CEO decomposes & delegates to specialized agents</span>
                    </div>
                    
                    <div class="flex flex-col md:flex-row gap-3">
                        <div class="flex-1 relative">
                            <textarea id="ceo-directive-input" rows="2" placeholder="e.g. Build an authentication system with Convex backend and Clerk auth, design modern responsive UI with Tailwind, and test with Vitest..." class="w-full px-3.5 py-2.5 rounded-xl border text-xs font-sans text-slate-100 focus:outline-none focus:ring-1 focus:ring-amber-400 scrollbar-thin resize-none" style="background-color: var(--bg-card); border-color: var(--border-base);"></textarea>
                        </div>
                        <div class="flex flex-row md:flex-col justify-between gap-2 md:w-56 flex-shrink-0">
                            <select id="ceo-ws-select" class="w-full px-2.5 py-1.5 rounded-lg border text-xs font-sans text-slate-200 focus:outline-none" style="background-color: var(--bg-card); border-color: var(--border-base);">
                                <option value="">Target Workspace: None</option>
                            </select>
                            <div class="flex gap-2">
                                <select id="ceo-priority-select" class="w-1/2 px-2 py-1.5 rounded-lg border text-xs font-sans text-slate-200 focus:outline-none" style="background-color: var(--bg-card); border-color: var(--border-base);">
                                    <option value="urgent">Urgent</option>
                                    <option value="high" selected>High</option>
                                    <option value="medium">Medium</option>
                                    <option value="low">Low</option>
                                </select>
                                <button onclick="submitBoardDirective()" id="btn-submit-directive" class="w-1/2 px-3 py-1.5 rounded-lg text-xs font-bold text-white transition flex items-center justify-center gap-1.5 shadow-md hover:brightness-110" style="background: linear-gradient(135deg, #f59e0b, #d97706);">
                                    <i class="fa-solid fa-bolt"></i>
                                    <span>Delegate</span>
                                </button>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- TAB 1: WORK ORDERS KANBAN -->
                <div id="ceo-view-kanban" class="space-y-4">
                    <div class="grid grid-cols-1 md:grid-cols-5 gap-3.5">
                        
                        <!-- Col 1: Todo / Queued -->
                        <div class="flex flex-col rounded-2xl border p-3 min-h-[360px]" style="background-color: var(--bg-sidebar); border-color: var(--border-base);">
                            <div class="flex items-center justify-between pb-2 mb-2 border-b" style="border-color: var(--border-base);">
                                <span class="text-xs font-bold text-slate-300 flex items-center gap-1.5">
                                    <span class="w-2 h-2 rounded-full bg-slate-400"></span> Queued / Todo
                                </span>
                                <span id="col-count-todo" class="px-2 py-0.5 rounded-full text-[10px] font-mono font-bold bg-white/10 text-slate-300">0</span>
                            </div>
                            <div id="kanban-col-todo" class="flex-1 space-y-2.5 overflow-y-auto scrollbar-thin"></div>
                        </div>

                        <!-- Col 2: In Progress -->
                        <div class="flex flex-col rounded-2xl border p-3 min-h-[360px]" style="background-color: var(--bg-sidebar); border-color: var(--border-base);">
                            <div class="flex items-center justify-between pb-2 mb-2 border-b" style="border-color: var(--border-base);">
                                <span class="text-xs font-bold text-blue-400 flex items-center gap-1.5">
                                    <span class="w-2 h-2 rounded-full bg-blue-500 animate-pulse"></span> In Progress
                                </span>
                                <span id="col-count-in_progress" class="px-2 py-0.5 rounded-full text-[10px] font-mono font-bold bg-blue-500/20 text-blue-300 border border-blue-500/30">0</span>
                            </div>
                            <div id="kanban-col-in_progress" class="flex-1 space-y-2.5 overflow-y-auto scrollbar-thin"></div>
                        </div>

                        <!-- Col 3: In Review (Acceptance Gate) -->
                        <div class="flex flex-col rounded-2xl border p-3 min-h-[360px]" style="background-color: var(--bg-sidebar); border-color: var(--border-base);">
                            <div class="flex items-center justify-between pb-2 mb-2 border-b" style="border-color: var(--border-base);">
                                <span class="text-xs font-bold text-purple-400 flex items-center gap-1.5">
                                    <span class="w-2 h-2 rounded-full bg-purple-500"></span> In Review
                                </span>
                                <span id="col-count-in_review" class="px-2 py-0.5 rounded-full text-[10px] font-mono font-bold bg-purple-500/20 text-purple-300 border border-purple-500/30">0</span>
                            </div>
                            <div id="kanban-col-in_review" class="flex-1 space-y-2.5 overflow-y-auto scrollbar-thin"></div>
                        </div>

                        <!-- Col 4: Blocked / Escalated -->
                        <div class="flex flex-col rounded-2xl border p-3 min-h-[360px]" style="background-color: var(--bg-sidebar); border-color: var(--border-base);">
                            <div class="flex items-center justify-between pb-2 mb-2 border-b" style="border-color: var(--border-base);">
                                <span class="text-xs font-bold text-rose-400 flex items-center gap-1.5">
                                    <span class="w-2 h-2 rounded-full bg-rose-500"></span> Blocked / Board
                                </span>
                                <span id="col-count-blocked" class="px-2 py-0.5 rounded-full text-[10px] font-mono font-bold bg-rose-500/20 text-rose-300 border border-rose-500/30">0</span>
                            </div>
                            <div id="kanban-col-blocked" class="flex-1 space-y-2.5 overflow-y-auto scrollbar-thin"></div>
                        </div>

                        <!-- Col 5: Done -->
                        <div class="flex flex-col rounded-2xl border p-3 min-h-[360px]" style="background-color: var(--bg-sidebar); border-color: var(--border-base);">
                            <div class="flex items-center justify-between pb-2 mb-2 border-b" style="border-color: var(--border-base);">
                                <span class="text-xs font-bold text-emerald-400 flex items-center gap-1.5">
                                    <span class="w-2 h-2 rounded-full bg-emerald-500"></span> Done
                                </span>
                                <span id="col-count-done" class="px-2 py-0.5 rounded-full text-[10px] font-mono font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">0</span>
                            </div>
                            <div id="kanban-col-done" class="flex-1 space-y-2.5 overflow-y-auto scrollbar-thin"></div>
                        </div>

                    </div>
                </div>

                <!-- TAB 2: ORG CHART & FLEET ROLES -->
                <div id="ceo-view-org" class="space-y-6 hidden">
                    
                    <!-- Hierarchy Tree Visualizer -->
                    <div class="p-5 rounded-2xl border space-y-4" style="background-color: var(--bg-sidebar); border-color: var(--border-base);">
                        <div class="flex justify-between items-center">
                            <h3 class="text-xs font-bold uppercase tracking-wider text-slate-400 flex items-center gap-2">
                                <i class="fa-solid fa-sitemap text-amber-400"></i> Chain of Command & Reporting Hierarchy
                            </h3>
                            <span class="text-[11px] text-slate-500">Paperclip Leadership Doctrine</span>
                        </div>

                        <div class="flex flex-col items-center space-y-3 py-2 font-sans">
                            <!-- Board Level -->
                            <div class="px-5 py-2.5 rounded-xl border flex items-center gap-3 shadow-md" style="background-color: var(--bg-input); border-color: var(--border-base);">
                                <span class="text-lg">👤</span>
                                <div>
                                    <div class="text-xs font-bold text-white">Human Board of Directors</div>
                                    <div class="text-[10px] text-slate-400">Sets high-level company goals, budget & approvals</div>
                                </div>
                            </div>
                            <div class="w-0.5 h-6 bg-slate-600"></div>

                            <!-- CEO Level -->
                            <div class="px-5 py-2.5 rounded-xl border flex items-center gap-3 shadow-md border-amber-500/40 bg-amber-500/10">
                                <span class="text-lg">👑</span>
                                <div>
                                    <div class="text-xs font-bold text-amber-300">CEO (Antigravity Fleet Orchestrator)</div>
                                    <div class="text-[10px] text-amber-200/80">Never codes. Owns triage, decomposition, delegation & heartbeat maintenance</div>
                                </div>
                            </div>
                            <div class="w-0.5 h-6 bg-slate-600"></div>

                            <!-- Department Leads & Specialists -->
                            <div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2.5 w-full pt-1">
                                <div class="p-3 rounded-xl border text-center space-y-1" style="background-color: var(--bg-input); border-color: var(--border-base);">
                                    <div class="text-base">🏛️</div>
                                    <div class="text-[11px] font-bold text-white">CTO</div>
                                    <div class="text-[9px] text-slate-400">Architecture & Standards</div>
                                </div>
                                <div class="p-3 rounded-xl border text-center space-y-1" style="background-color: var(--bg-input); border-color: var(--border-base);">
                                    <div class="text-base">🎨</div>
                                    <div class="text-[11px] font-bold text-white">Frontend</div>
                                    <div class="text-[9px] text-slate-400">React, Tailwind, UI/UX</div>
                                </div>
                                <div class="p-3 rounded-xl border text-center space-y-1" style="background-color: var(--bg-input); border-color: var(--border-base);">
                                    <div class="text-base">⚡</div>
                                    <div class="text-[11px] font-bold text-white">Backend</div>
                                    <div class="text-[9px] text-slate-400">Convex, APIs, Auth</div>
                                </div>
                                <div class="p-3 rounded-xl border text-center space-y-1" style="background-color: var(--bg-input); border-color: var(--border-base);">
                                    <div class="text-base">💻</div>
                                    <div class="text-[11px] font-bold text-white">Codex</div>
                                    <div class="text-[9px] text-slate-400">Refactoring & Synthesis</div>
                                </div>
                                <div class="p-3 rounded-xl border text-center space-y-1" style="background-color: var(--bg-input); border-color: var(--border-base);">
                                    <div class="text-base">🧠</div>
                                    <div class="text-[11px] font-bold text-white">Hermes</div>
                                    <div class="text-[9px] text-slate-400">Reasoning & Multi-Tool</div>
                                </div>
                                <div class="p-3 rounded-xl border text-center space-y-1" style="background-color: var(--bg-input); border-color: var(--border-base);">
                                    <div class="text-base">🛡️</div>
                                    <div class="text-[11px] font-bold text-white">QA Lead</div>
                                    <div class="text-[9px] text-slate-400">Tests & Verification</div>
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- Fleet Agent Role Assignment Table -->
                    <div class="p-5 rounded-2xl border space-y-4" style="background-color: var(--bg-sidebar); border-color: var(--border-base);">
                        <div class="flex justify-between items-center">
                            <div>
                                <h3 class="text-xs font-bold uppercase tracking-wider text-slate-400 flex items-center gap-2">
                                    <i class="fa-solid fa-users-gear text-blue-400"></i> Fleet Containers & Assigned Roles
                                </h3>
                                <p class="text-[11px] text-slate-500">Configure organizational assignments for your Proxmox agent containers</p>
                            </div>
                        </div>

                        <div class="overflow-x-auto">
                            <table class="w-full text-left text-xs border-collapse">
                                <thead>
                                    <tr class="border-b text-[10px] uppercase font-bold text-slate-400 tracking-wider" style="border-color: var(--border-base);">
                                        <th class="py-2.5 px-3">Agent</th>
                                        <th class="py-2.5 px-3">Container</th>
                                        <th class="py-2.5 px-3">IP / Engine</th>
                                        <th class="py-2.5 px-3">Assigned Role</th>
                                        <th class="py-2.5 px-3">Live Status</th>
                                        <th class="py-2.5 px-3">Action</th>
                                    </tr>
                                </thead>
                                <tbody id="ceo-fleet-roles-tbody" class="divide-y divide-white/5"></tbody>
                            </table>
                        </div>
                    </div>
                </div>

                <!-- TAB 3: HEARTBEAT & AUDIT -->
                <div id="ceo-view-heartbeat" class="space-y-4 hidden">
                    <div class="p-4 rounded-2xl border space-y-3" style="background-color: var(--bg-sidebar); border-color: var(--border-base);">
                        <div class="flex justify-between items-center">
                            <div class="flex items-center gap-2">
                                <i class="fa-solid fa-heart-pulse text-rose-400"></i>
                                <span class="text-xs font-bold uppercase tracking-wider text-slate-300">Autonomous Heartbeat Supervisor Feed</span>
                            </div>
                            <span class="text-[11px] font-mono text-slate-500">Every 30s pulse</span>
                        </div>
                        <div class="p-3 rounded-xl border font-mono text-xs text-slate-300 h-64 overflow-y-auto scrollbar-thin space-y-1 select-text" style="background-color: var(--bg-input); border-color: var(--border-base);" id="ceo-heartbeat-log-container">
                            <div class="text-slate-500 italic">Waiting for heartbeat pulses...</div>
                        </div>
                    </div>

                    <div class="p-4 rounded-2xl border space-y-3" style="background-color: var(--bg-sidebar); border-color: var(--border-base);">
                        <div class="flex justify-between items-center">
                            <span class="text-xs font-bold uppercase tracking-wider text-slate-400 flex items-center gap-2">
                                <i class="fa-solid fa-clock-rotate-left text-amber-400"></i> Executive Audit Trail
                            </span>
                            <span class="text-[11px] text-slate-500 font-mono">Recent delegation events</span>
                        </div>
                        <div class="p-3 rounded-xl border font-mono text-xs text-slate-300 h-48 overflow-y-auto scrollbar-thin space-y-1.5 select-text" style="background-color: var(--bg-input); border-color: var(--border-base);" id="ceo-audit-log-container">
                        </div>
                    </div>
                </div>

                <!-- TAB 4: CEO OPERATING CHARTER -->
                <div id="ceo-view-charter" class="space-y-4 hidden">
                    <div class="flex space-x-2 border-b pb-2" style="border-color: var(--border-base);">
                        <button onclick="loadCeoCharterPrompt('AGENTS.md')" id="charter-btn-agents" class="px-3 py-1.5 rounded-lg text-xs font-bold border" style="background: var(--bg-input); border-color: var(--border-base); color: var(--highlight-text);">AGENTS.md (Operational Rules)</button>
                        <button onclick="loadCeoCharterPrompt('SOUL.md')" id="charter-btn-soul" class="px-3 py-1.5 rounded-lg text-xs font-bold border text-slate-400 hover:text-white" style="background: var(--bg-card); border-color: var(--border-base);">SOUL.md (Executive Posture)</button>
                        <button onclick="loadCeoCharterPrompt('HEARTBEAT.md')" id="charter-btn-heartbeat" class="px-3 py-1.5 rounded-lg text-xs font-bold border text-slate-400 hover:text-white" style="background: var(--bg-card); border-color: var(--border-base);">HEARTBEAT.md (Checklist)</button>
                    </div>
                    <div class="p-4 rounded-xl border font-mono text-xs text-slate-300 whitespace-pre-wrap h-96 overflow-y-auto scrollbar-thin select-text" style="background-color: var(--bg-input); border-color: var(--border-base);" id="ceo-charter-text-container">
                        Loading charter document...
                    </div>
                </div>

            </div>

            <!-- Modal Footer -->
            <div class="px-6 py-2.5 border-t flex justify-between items-center text-xs flex-shrink-0" style="background-color: var(--bg-sidebar); border-color: var(--border-base);">
                <div class="flex items-center gap-2 text-[11px] text-slate-400 font-mono">
                    <span>👑 Antigravity Executive OS</span>
                    <span>•</span>
                    <span class="text-amber-400/80">Autonomous Fleet Delegation</span>
                </div>
                <button onclick="closeCeoModal()" class="px-4 py-1.5 rounded-xl border text-xs font-bold transition hover:bg-white/5" style="border-color: var(--border-base); color: var(--text-main);">
                    Close Suite
                </button>
            </div>
        </div>
    </div>

    </main>

    <!-- ============================================================ -->
    <!-- JAVASCRIPT COCKPIT CLIENT LOGIC                              -->
    <!-- ============================================================ -->
    <script>
        let agents = __AGENTS_JSON_PLACEHOLDER__;
        let currentView = "agent-1"; // "overview" or "agent-1" ... "agent-5"
        let fleetStatuses = {};
        let lastLogsHash = "";
        let layoutMode = localStorage.getItem("cockpit_layout") || "split"; // "split" or "theater"

        // Theme management
        function setTheme(theme) {
            document.documentElement.setAttribute("data-theme", theme);
            localStorage.setItem("cockpit_theme", theme);

            const themes = ["onyx-stealth", "cobalt-hyperdrive", "tokyo-neon"];
            const btnIds = {
                "onyx-stealth": "btn-theme-onyx",
                "cobalt-hyperdrive": "btn-theme-cobalt",
                "tokyo-neon": "btn-theme-tokyo"
            };

            themes.forEach(t => {
                const b = document.getElementById(btnIds[t]);
                if (b) {
                    if (t === theme) {
                        b.className = "px-2 py-0.5 rounded text-[10px] font-semibold bg-white/20 text-white shadow-sm border border-white/20";
                    } else {
                        b.className = "px-2 py-0.5 rounded text-[10px] font-semibold text-slate-400 hover:text-slate-200";
                    }
                }
            });

            selectView(currentView);
        }

        // Layout Toggle (Split vs Theater)
        function toggleLayoutMode() {
            layoutMode = (layoutMode === "split") ? "theater" : "split";
            localStorage.setItem("cockpit_layout", layoutMode);
            applyLayoutMode();
        }

        function applyLayoutMode() {
            const container = document.getElementById("dedicated-workspace-container");
            const leftCol = document.getElementById("workspace-left-col");
            const rightCol = document.getElementById("workspace-right-col");
            const layoutIcon = document.getElementById("layout-icon");
            const layoutText = document.getElementById("layout-text");

            if (layoutMode === "theater") {
                container.className = "flex flex-col space-y-5 items-center w-full max-w-6xl mx-auto pb-6";
                leftCol.className = "w-full flex flex-col space-y-4";
                rightCol.className = "w-full grid grid-cols-1 md:grid-cols-2 gap-5";
                layoutIcon.className = "fa-solid fa-columns";
                layoutText.innerText = "Split Mode";
            } else {
                container.className = "grid grid-cols-1 xl:grid-cols-12 gap-5 items-start pb-6";
                leftCol.className = "xl:col-span-7 2xl:col-span-8 flex flex-col space-y-4";
                rightCol.className = "xl:col-span-5 2xl:col-span-4 flex flex-col space-y-4";
                layoutIcon.className = "fa-solid fa-table-columns";
                layoutText.innerText = "Theater Mode";
            }
        }

        // Build DOM structure ONCE at startup
        async function init() {
            const savedTheme = localStorage.getItem("cockpit_theme") || "onyx-stealth";
            setTheme(savedTheme);
            applyLayoutMode();

            try {
                const res = await fetch("/api/agents");
                if (res.ok) {
                    const data = await res.json();
                    if (Array.isArray(data.agents)) {
                        agents = data.agents;
                    }
                }
            } catch (e) {
                console.warn("Using embedded agents:", e);
            }

            buildSidebarDom();
            buildDedicatedIframes();
            buildOverviewScreensGrid();
            buildFleetTableDom();

            if (!agents.some(a => a.id === currentView)) {
                currentView = agents.length > 0 ? agents[0].id : "overview";
            }
            selectView(currentView);
            fetchSkillsLibrary();
            fetchWorkspaces();
            fetchAllStatus();
            setInterval(fetchAllStatus, 6000);
            setInterval(fetchCurrentLogs, 2500);
        }

                // ============================================================
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
                recommendedVirt: "LXC Container (or VM)",
                virtType: "lxc",
                virtBadge: "LXC SUPPORTED",
                virtBadgeClass: "text-indigo-400 bg-indigo-500/10 border-indigo-500/30",
                minCpu: "2 - 4 vCPUs",
                minRam: "4 - 8 GB RAM",
                minDisk: "20 GB SSD",
                virtReason: "Runs lightweight Xvfb + Openbox GUI desktop, Chromium browser, noVNC display server, and Antigravity Skills runner.",
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
                recommendedVirt: "LXC Container (or VM)",
                virtType: "lxc",
                virtBadge: "LXC SUPPORTED",
                virtBadgeClass: "text-emerald-400 bg-emerald-500/10 border-emerald-500/30",
                minCpu: "2 - 4 vCPUs",
                minRam: "4 - 8 GB RAM",
                minDisk: "30 GB SSD",
                virtReason: "Runs Node.js 20 LTS, pnpm, Python AST analyzers, code linters, and headless autonomous development toolchain.",
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
                recommendedVirt: "KVM Virtual Machine (Required)",
                virtType: "qemu",
                virtBadge: "⚡ KVM VM REQUIRED",
                virtBadgeClass: "text-amber-400 bg-amber-500/10 border-amber-500/30",
                minCpu: "4 - 8 vCPUs (host flags)",
                minRam: "16 - 32 GB RAM",
                minDisk: "60 GB SSD",
                virtReason: "Requires hardware AVX-512 flags, nested Docker runtime without LXC cgroup limits, and optional PCIe GPU passthrough for local LLMs (Ollama/Hermes-3).",
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
                recommendedVirt: "KVM Virtual Machine (Required)",
                virtType: "qemu",
                virtBadge: "⚡ KVM VM REQUIRED",
                virtBadgeClass: "text-rose-400 bg-rose-500/10 border-rose-500/30",
                minCpu: "4 - 8 vCPUs",
                minRam: "8 - 16 GB RAM",
                minDisk: "50 GB SSD",
                virtReason: "Requires full user namespaces (clone3) and AppArmor/seccomp enforcement for Playwright/Chromium sandboxing, plus isolated network stack for rotating proxies/WireGuard.",
                description: "Autonomous browser crawler, DOM scraper, site monitor, and automated web task execution bot."
            },
            ceo: {
                id: "ceo",
                name: "Paperclip CEO",
                fullName: "Chief Executive Agent",
                icon: "fa-solid fa-crown",
                color: "#a855f7",
                badgeBg: "rgba(168, 85, 247, 0.15)",
                badgeBorder: "rgba(168, 85, 247, 0.35)",
                badgeText: "#d8b4fe",
                defaultRole: "Chief Executive Officer",
                tag: "Paperclip CEO",
                recommendedVirt: "LXC Container (or Cockpit Host)",
                virtType: "lxc",
                virtBadge: "LXC SUPPORTED",
                virtBadgeClass: "text-purple-400 bg-purple-500/10 border-purple-500/30",
                minCpu: "2 vCPUs",
                minRam: "2 - 4 GB RAM",
                minDisk: "15 GB SSD",
                virtReason: "Paperclip executive governance, heartbeat supervisor, strategic work order generation, and cross-agent delegation.",
                description: "Paperclip CEO governance agent orchestrating cross-agent tasks, delegation, and strategic oversight."
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
                tag: "Custom Node",
                recommendedVirt: "Any VM or Container",
                virtType: "lxc",
                virtBadge: "CUSTOM NODE",
                virtBadgeClass: "text-sky-400 bg-sky-500/10 border-sky-500/30",
                minCpu: "2+ vCPUs",
                minRam: "4+ GB RAM",
                minDisk: "20+ GB SSD",
                virtReason: "Custom Linux container, external microservice, physical machine, or standalone AI agent runner.",
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
                recommendedVirt: "VM or LXC",
                virtType: "lxc",
                virtBadge: "CUSTOM",
                virtBadgeClass: "text-slate-400 bg-slate-500/10 border-slate-500/30",
                minCpu: "2+ vCPUs",
                minRam: "4+ GB RAM",
                minDisk: "20+ GB SSD",
                virtReason: "User configured custom execution environment.",
                description: "Custom Agent Architecture"
            };
        }

        function isAgentVm(agent) {
            if (!agent) return false;
            if (agent.vm_type === "qemu") return true;
            if (agent.vm_type === "lxc") return false;
            return ["hermes", "openclaw"].includes(String(agent.type || "").toLowerCase());
        }

        function getAgentVirtLabel(agent) {
            return `${isAgentVm(agent) ? 'VM' : 'CT'} ${agent.vmid}`;
        }

        function getAgentVirtBadge(agent) {
            return isAgentVm(agent)
                ? `<span class="text-[9px] font-mono px-1.5 py-0.5 rounded font-semibold border flex items-center gap-1 text-amber-300 bg-amber-500/10 border-amber-500/30"><i class="fa-solid fa-microchip text-[8px]"></i> VM ${agent.vmid}</span>`
                : `<span class="text-[9px] font-mono px-1.5 py-0.5 rounded font-semibold border flex items-center gap-1 text-slate-300 bg-slate-800 border-slate-700"><i class="fa-solid fa-cube text-[8px]"></i> CT ${agent.vmid}</span>`;
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
                            ${getAgentVirtBadge(agent)}
                        </div>
                    </div>
                    <div class="text-[11px] text-slate-400 truncate">${escapeHtml(agent.role)}</div>
                    <div class="flex justify-between items-center pt-1 border-t text-[10px]" style="border-color: var(--border-base);">
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
                    <td class="p-3.5 text-slate-300 font-mono">
                        <span class="font-bold">${getAgentVirtLabel(agent)}</span>
                    </td>
                    <td class="p-3.5 text-slate-300 font-mono">${agent.ip}</td>
                    <td class="p-3.5" id="table-power-${agent.id}">
                        <span class="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-slate-600/10 text-slate-400 border border-slate-600/20">
                            <span class="w-1.5 h-1.5 rounded-full bg-slate-500"></span> Stopped
                        </span>
                    </td>
                    <td class="p-3.5 text-slate-300 font-mono" id="table-metrics-${agent.id}">-- | --</td>
                    <td class="p-3.5" id="table-auth-${agent.id}">
                        <span class="text-[10px] px-2 py-0.5 rounded-full font-medium bg-amber-500/10 text-amber-400 border border-amber-500/20">
                            <i class="fa-solid fa-triangle-exclamation mr-1"></i> Needs Auth
                        </span>
                    </td>
                    <td class="p-3.5 text-right space-x-2" onclick="event.stopPropagation()">
                        <button onclick="openRenameModal('${agent.id}')" class="px-2 py-1 border rounded-lg text-xs transition text-slate-400 hover:text-white" style="background-color: var(--bg-input); border-color: var(--border-base);" title="Configure">
                            <i class="fa-solid fa-pen-to-square"></i>
                        </button>
                        <button onclick="confirmRemoveAgent('${agent.id}')" class="px-2 py-1 border rounded-lg text-xs transition text-rose-400 hover:text-rose-200 hover:bg-rose-500/10" style="background-color: var(--bg-input); border-color: rgba(244, 63, 94, 0.25);" title="Remove Agent">
                            <i class="fa-solid fa-trash-can"></i>
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

        // Navigation Switching
        function selectView(viewId) {
            currentView = viewId;
            const dedicatedView = document.getElementById("dedicated-agent-view");
            const overviewView = document.getElementById("fleet-overview-view");
            const navOverviewBtn = document.getElementById("nav-btn-overview");

            agents.forEach(a => {
                const card = document.getElementById(`side-card-${a.id}`);
                if (card) {
                    if (a.id === viewId) {
                        card.style.backgroundColor = "var(--card-active-bg)";
                        card.style.borderColor = "var(--card-active-border)";
                        card.classList.add("shadow-lg");
                    } else {
                        card.style.backgroundColor = "var(--bg-input)";
                        card.style.borderColor = "var(--border-base)";
                        card.classList.remove("shadow-lg");
                    }
                }
            });

            if (viewId === "overview") {
                dedicatedView.classList.add("hidden");
                overviewView.classList.remove("hidden");
                navOverviewBtn.style.backgroundColor = "var(--nav-active-bg)";
                navOverviewBtn.style.borderColor = "var(--nav-active-border)";
                navOverviewBtn.classList.add("shadow-lg");
            } else {
                overviewView.classList.add("hidden");
                dedicatedView.classList.remove("hidden");
                navOverviewBtn.style.backgroundColor = "var(--bg-card)";
                navOverviewBtn.style.borderColor = "var(--border-base)";
                navOverviewBtn.classList.remove("shadow-lg");

                agents.forEach(a => {
                    const f = document.getElementById(`dedicated-frame-${a.id}`);
                    if (f) {
                        if (a.id === viewId) f.classList.remove("hidden");
                        else f.classList.add("hidden");
                    }
                });

                updateDedicatedAgentLabels(viewId);
                fetchCurrentLogs();
                fetchAgentQuota(viewId);
            }
        }

        // Update Dedicated Page Labels In-Place
        function updateDedicatedAgentLabels(agentId) {
            const agent = agents.find(a => a.id === agentId);
            if (!agent) return;

            const eng = getAgentEngine(agent.type);
            const info = fleetStatuses[agentId] || { power: "unknown", status: "checking", authenticated: false, metrics: {} };
            const isRunning = info.power === "running";

            const titleEl = document.getElementById("agent-page-title");
            if (titleEl) titleEl.innerText = `${agent.name} (${agent.role})`;
            
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

            const vmidEl = document.getElementById("agent-page-vmid");
            if (vmidEl) vmidEl.innerText = agent.vmid;
            const ipEl = document.getElementById("agent-page-ip");
            if (ipEl) ipEl.innerText = agent.ip;
            const targetEl = document.getElementById("dispatcher-target-tag");
            if (targetEl) targetEl.innerText = agent.name;

            const m = info.metrics || {};
            const cpuEl = document.getElementById("agent-page-cpu");
            if (cpuEl) cpuEl.innerText = m.cpu !== undefined ? (m.cpu * 100).toFixed(1) + "%" : "--%";
            const ramEl = document.getElementById("agent-page-ram");
            if (ramEl) ramEl.innerText = m.mem !== undefined ? Math.round(m.mem / (1024 * 1024)) + " MB" : "-- MB";
            const upEl = document.getElementById("agent-page-uptime");
            if (upEl) upEl.innerText = m.uptime ? Math.round(m.uptime / 60) + "m" : "--";

            const powerBadge = document.getElementById("agent-page-power-badge");
            if (powerBadge) {
                if (isRunning) {
                    powerBadge.className = "px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 flex items-center gap-1.5";
                    powerBadge.innerHTML = `<span class="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span> ${info.status === 'busy' ? 'Busy' : 'Running'}`;
                } else {
                    powerBadge.className = "px-2.5 py-0.5 rounded-full text-xs font-semibold bg-slate-600/20 text-slate-400 border border-slate-600/30 flex items-center gap-1.5";
                    powerBadge.innerHTML = `<span class="w-2 h-2 rounded-full bg-slate-500"></span> Stopped`;
                }
            }

            const authBadge = document.getElementById("agent-page-auth-badge");
            const authPill = document.getElementById("auth-status-pill");
            if (info.authenticated) {
                if (authBadge) {
                    authBadge.className = "px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30";
                    authBadge.innerHTML = `<i class="fa-solid fa-key mr-1"></i> Auth Active`;
                }
                if (authPill) {
                    authPill.className = "text-[11px] px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-400 font-mono";
                    authPill.innerText = "Active";
                }
            } else {
                if (authBadge) {
                    authBadge.className = "px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-500/20 text-amber-300 border border-amber-500/30";
                    authBadge.innerHTML = `<i class="fa-solid fa-triangle-exclamation mr-1"></i> Needs Auth`;
                }
                if (authPill) {
                    authPill.className = "text-[11px] px-2 py-0.5 rounded bg-amber-500/20 text-amber-400 font-mono";
                    authPill.innerText = "Needs Auth";
                }
            }

            const powerBtn = document.getElementById("agent-page-power-btn");
            if (powerBtn) {
                if (isRunning) {
                    powerBtn.className = "px-3.5 py-2 bg-red-500/20 hover:bg-red-500/30 text-red-300 border border-red-500/30 rounded-xl text-xs font-medium transition flex items-center gap-1.5";
                    powerBtn.innerHTML = `<i class="fa-solid fa-power-off"></i> Stop`;
                } else {
                    powerBtn.className = "px-3.5 py-2 bg-emerald-500/20 hover:bg-emerald-500/30 text-emerald-300 border border-emerald-500/30 rounded-xl text-xs font-medium transition flex items-center gap-1.5";
                    powerBtn.innerHTML = `<i class="fa-solid fa-play"></i> Start`;
                }
            }

            const popout = document.getElementById("agent-page-popout");
            if (popout) {
                popout.href = `http://${agent.ip}:${agent.vnc_port}/vnc.html?autoconnect=true&resize=scale&reconnect=true`;
            }

            const overlay = document.getElementById("screen-stopped-overlay");
            if (overlay) {
                if (isRunning) overlay.classList.add("hidden");
                else overlay.classList.remove("hidden");
            }

            updateAgentSkillsPreview(agentId);
            updateDedicatedWorkspaceBadge(agentId);
        }

        // Fetch Status and Update Existing DOM In-Place
        async function fetchAllStatus() {
            try {
                const icon = document.getElementById("refresh-icon");
                if (icon) icon.classList.add("fa-spin");

                const res = await fetch("/api/status");
                const data = await res.json();
                fleetStatuses = data;

                let activeCount = 0;

                agents.forEach(agent => {
                    const info = fleetStatuses[agent.id] || { power: "unknown", status: "offline", authenticated: false, metrics: {} };
                    const isRunning = info.power === "running";
                    if (isRunning) activeCount++;

                    const dot = document.getElementById(`side-dot-${agent.id}`);
                    if (dot) {
                        if (isRunning) {
                            dot.className = `w-2 h-2 rounded-full ${info.status === 'busy' ? 'bg-amber-400 animate-pulse' : 'bg-emerald-400'}`;
                        } else {
                            dot.className = "w-2 h-2 rounded-full bg-slate-600";
                        }
                    }

                    const authSide = document.getElementById(`side-auth-${agent.id}`);
                    if (authSide) {
                        authSide.className = `text-[9px] font-medium px-1.5 py-0.5 rounded ${info.authenticated ? 'bg-emerald-500/20 text-emerald-300' : 'bg-amber-500/20 text-amber-300'}`;
                        authSide.innerText = info.authenticated ? "≡ƒöæ" : "ΓÜá∩╕Å";
                    }

                    const sidePower = document.getElementById(`side-power-${agent.id}`);
                    if (sidePower) {
                        if (isRunning) {
                            sidePower.innerHTML = `
                                <button onclick="toggleAgentPower('${agent.id}', 'stop')" class="px-2 py-0.5 rounded bg-red-500/10 hover:bg-red-500/25 text-red-400 border border-red-500/20 font-semibold transition" title="Stop Container">
                                    <i class="fa-solid fa-power-off mr-1"></i>Stop
                                </button>
                            `;
                        } else {
                            sidePower.innerHTML = `
                                <button onclick="toggleAgentPower('${agent.id}', 'start')" class="px-2 py-0.5 rounded bg-emerald-500/10 hover:bg-emerald-500/25 text-emerald-400 border border-emerald-500/20 font-semibold transition" title="Start Container">
                                    <i class="fa-solid fa-play mr-1"></i>Start
                                </button>
                            `;
                        }
                    }

                    const ovScreen = document.getElementById(`overview-screen-${agent.id}`);
                    if (ovScreen) {
                        if (isRunning) ovScreen.classList.remove("hidden");
                        else ovScreen.classList.add("hidden");
                    }

                    const tPower = document.getElementById(`table-power-${agent.id}`);
                    if (tPower) {
                        tPower.innerHTML = `
                            <span class="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-semibold ${isRunning ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : 'bg-slate-600/10 text-slate-400 border border-slate-600/20'}">
                                <span class="w-1.5 h-1.5 rounded-full ${isRunning ? 'bg-emerald-400' : 'bg-slate-500'}"></span>
                                ${isRunning ? info.status : 'Stopped'}
                            </span>
                        `;
                    }

                    const tMetrics = document.getElementById(`table-metrics-${agent.id}`);
                    if (tMetrics) {
                        const m = info.metrics || {};
                        const cpu = m.cpu !== undefined ? (m.cpu * 100).toFixed(1) + "%" : "--";
                        const ram = m.mem !== undefined ? Math.round(m.mem / (1024 * 1024)) + " MB" : "--";
                        tMetrics.innerText = `${cpu} | ${ram}`;
                    }

                    const tAuth = document.getElementById(`table-auth-${agent.id}`);
                    if (tAuth) {
                        tAuth.innerHTML = `
                            <span class="text-[10px] px-2 py-0.5 rounded-full font-medium ${info.authenticated ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : 'bg-amber-500/10 text-amber-400 border border-amber-500/20'}">
                                ${info.authenticated ? '≡ƒöæ Authenticated' : 'ΓÜá∩╕Å Needs Auth'}
                            </span>
                        `;
                    }

                    const tAction = document.getElementById(`table-action-${agent.id}`);
                    if (tAction) {
                        if (isRunning) {
                            tAction.innerHTML = `
                                <button onclick="toggleAgentPower('${agent.id}', 'stop')" class="px-2.5 py-1 bg-red-500/10 hover:bg-red-500/20 text-red-400 border border-red-500/20 rounded-lg text-xs transition">
                                    Stop
                                </button>
                            `;
                        } else {
                            tAction.innerHTML = `
                                <button onclick="toggleAgentPower('${agent.id}', 'start')" class="px-2.5 py-1 bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 border border-emerald-500/20 rounded-lg text-xs transition">
                                    Start
                                </button>
                            `;
                        }
                    }
                });

                document.getElementById("active-count-badge").innerText = `${activeCount} / 5 Active`;

                const emptyNotice = document.getElementById("overview-empty-notice");
                if (emptyNotice) {
                    if (activeCount === 0) emptyNotice.classList.remove("hidden");
                    else emptyNotice.classList.add("hidden");
                }

                if (currentView !== "overview") {
                    updateDedicatedAgentLabels(currentView);
                }

                if (icon) setTimeout(() => icon.classList.remove("fa-spin"), 400);
            } catch (e) {
                console.error("Status fetch error", e);
            }
        }

        // Fetch Logs and Append without Full Redraw
        async function fetchCurrentLogs() {
            if (currentView === "overview") return;
            try {
                const res = await fetch(`/api/logs?agent_id=${currentView}`);
                const data = await res.json();
                const term = document.getElementById("dedicated-terminal-logs");
                
                if (data.logs && data.logs.length > 0) {
                    const hash = data.logs.length + "-" + data.logs[data.logs.length - 1].text;
                    if (hash !== lastLogsHash) {
                        lastLogsHash = hash;
                        const isScrolledToBottom = term.scrollHeight - term.clientHeight <= term.scrollTop + 40;

                        term.innerHTML = data.logs.map(log => {
                            let color = "text-slate-300";
                            if (log.type === "info") color = "text-blue-400 font-semibold";
                            if (log.type === "output") color = "text-cyan-300";
                            if (log.type === "error") color = "text-red-400";
                            if (log.type === "stream") color = "text-emerald-300/80";
                            return `<div class="${color}">[${log.time || ''}] ${escapeHtml(log.text)}</div>`;
                        }).join("");

                        if (isScrolledToBottom) {
                            term.scrollTop = term.scrollHeight;
                        }
                    }
                }
            } catch (e) {
                console.error("Logs fetch error", e);
            }
        }

        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }

        function setPrompt(p) {
            document.getElementById("dedicated-prompt-input").value = p;
        }

        // ============================================================
        // SCREENSHOT & IMAGE ATTACHMENT CLIENT LOGIC
        // ============================================================
        let attachedImages = [];
        let broadcastImages = [];

        function handleTaskImageSelect(files) {
            if (!files || files.length === 0) return;
            Array.from(files).forEach(file => {
                if (!file.type.startsWith("image/")) return;
                const reader = new FileReader();
                reader.onload = (e) => {
                    attachedImages.push({
                        name: file.name || `image_${Date.now()}.png`,
                        data: e.target.result,
                        size: file.size
                    });
                    renderAttachedImages();
                };
                reader.readAsDataURL(file);
            });
        }

        function handleBroadcastImageSelect(files) {
            if (!files || files.length === 0) return;
            Array.from(files).forEach(file => {
                if (!file.type.startsWith("image/")) return;
                const reader = new FileReader();
                reader.onload = (e) => {
                    broadcastImages.push({
                        name: file.name || `image_${Date.now()}.png`,
                        data: e.target.result,
                        size: file.size
                    });
                    renderBroadcastImages();
                };
                reader.readAsDataURL(file);
            });
        }

        function renderAttachedImages() {
            const tray = document.getElementById("attached-images-tray");
            if (!tray) return;

            if (attachedImages.length === 0) {
                tray.classList.add("hidden");
                tray.innerHTML = "";
                return;
            }

            tray.classList.remove("hidden");
            tray.innerHTML = attachedImages.map((img, idx) => `
                <div class="relative group flex items-center gap-2 p-1.5 rounded-lg border bg-black/40 border-slate-700 max-w-[210px]">
                    <img src="${img.data}" class="w-9 h-9 rounded object-cover cursor-pointer hover:opacity-80 transition" onclick="openImagePreview('${img.data}', '${escapeHtml(img.name)}')">
                    <div class="flex-1 min-w-0">
                        <div class="text-[10px] font-bold text-white truncate">${escapeHtml(img.name)}</div>
                        <div class="text-[9px] text-slate-400 font-mono">${Math.round(img.size / 1024)} KB</div>
                    </div>
                    <button onclick="removeAttachedImage(${idx})" class="w-5 h-5 rounded-full bg-rose-500/20 hover:bg-rose-500 text-rose-300 hover:text-white flex items-center justify-center text-[10px] transition" title="Remove">
                        <i class="fa-solid fa-xmark"></i>
                    </button>
                </div>
            `).join("");
        }

        function removeAttachedImage(idx) {
            attachedImages.splice(idx, 1);
            renderAttachedImages();
        }

        function renderBroadcastImages() {
            const tray = document.getElementById("broadcast-images-tray");
            if (!tray) return;

            if (broadcastImages.length === 0) {
                tray.classList.add("hidden");
                tray.innerHTML = "";
                return;
            }

            tray.classList.remove("hidden");
            tray.innerHTML = broadcastImages.map((img, idx) => `
                <div class="relative group flex items-center gap-2 p-1.5 rounded-lg border bg-black/40 border-slate-700 max-w-[210px]">
                    <img src="${img.data}" class="w-9 h-9 rounded object-cover cursor-pointer hover:opacity-80 transition" onclick="openImagePreview('${img.data}', '${escapeHtml(img.name)}')">
                    <div class="flex-1 min-w-0">
                        <div class="text-[10px] font-bold text-white truncate">${escapeHtml(img.name)}</div>
                        <div class="text-[9px] text-slate-400 font-mono">${Math.round(img.size / 1024)} KB</div>
                    </div>
                    <button onclick="removeBroadcastImage(${idx})" class="w-5 h-5 rounded-full bg-rose-500/20 hover:bg-rose-500 text-rose-300 hover:text-white flex items-center justify-center text-[10px] transition" title="Remove">
                        <i class="fa-solid fa-xmark"></i>
                    </button>
                </div>
            `).join("");
        }

        function removeBroadcastImage(idx) {
            broadcastImages.splice(idx, 1);
            renderBroadcastImages();
        }

        function openImagePreview(dataUrl, caption) {
            document.getElementById("lightbox-img").src = dataUrl;
            document.getElementById("lightbox-caption").innerText = caption || "";
            document.getElementById("image-preview-modal").classList.remove("hidden");
        }

        function closeImagePreview() {
            document.getElementById("image-preview-modal").classList.add("hidden");
        }

        // Paste Event Listener for Screenshots (Ctrl+V)
        window.addEventListener("paste", (e) => {
            const items = (e.clipboardData || e.originalEvent.clipboardData).items;
            for (const item of items) {
                if (item.type.indexOf("image") !== -1) {
                    const blob = item.getAsFile();
                    const reader = new FileReader();
                    reader.onload = (event) => {
                        attachedImages.push({
                            name: `screenshot_${Date.now()}.png`,
                            data: event.target.result,
                            size: blob.size
                        });
                        renderAttachedImages();
                    };
                    reader.readAsDataURL(blob);
                }
            }
        });

        // Capture live screen of current agent desktop
        async function captureCurrentAgentScreen() {
            if (!currentView || currentView === "overview") return alert("Please select an agent first");
            const btn = document.getElementById("btn-capture-agent-screen");
            const origHtml = btn.innerHTML;
            btn.innerHTML = `<i class="fa-solid fa-spinner fa-spin text-sky-400"></i> Capturing...`;
            btn.disabled = true;

            try {
                const res = await fetch(`/api/agent/screenshot?agent_id=${currentView}`);
                if (!res.ok) throw new Error("Agent desktop screenshot returned " + res.status);
                const blob = await res.blob();
                const reader = new FileReader();
                reader.onload = (e) => {
                    attachedImages.push({
                        name: `${currentView}_screen_${Date.now()}.png`,
                        data: e.target.result,
                        size: blob.size
                    });
                    renderAttachedImages();
                };
                reader.readAsDataURL(blob);
            } catch (e) {
                alert("Failed to capture agent screenshot: " + e.message);
            } finally {
                btn.innerHTML = origHtml;
                btn.disabled = false;
            }
        }

        async function dispatchDedicatedTask() {
            const input = document.getElementById("dedicated-prompt-input");
            const prompt = input.value.trim();
            if (!prompt && attachedImages.length === 0) return alert("Please enter instructions or attach a picture/screenshot.");

            const btn = document.getElementById("btn-dispatch-task");
            const origHtml = btn.innerHTML;
            btn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Dispatching...`;
            btn.disabled = true;

            const imagesPayload = attachedImages.map(img => ({ name: img.name, data: img.data }));
            const wsSelect = document.getElementById("dedicated-workspace-select");
            const wsId = wsSelect ? wsSelect.value : "";

            try {
                const res = await fetch("/api/dispatch", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ target: currentView, prompt, images: imagesPayload, workspace_id: wsId })
                });
                const data = await res.json();
                if (data.success) {
                    input.value = "";
                    attachedImages = [];
                    renderAttachedImages();
                    fetchCurrentLogs();
                    fetchAllStatus();
                    fetchWorkspaces();
                } else {
                    alert(data.error || "Dispatch failed");
                }
            } catch (e) {
                alert("Dispatch error: " + e.message);
            } finally {
                btn.innerHTML = origHtml;
                btn.disabled = false;
            }
        }

        async function dispatchBroadcast() {
            const input = document.getElementById("broadcast-prompt-input");
            const prompt = input.value.trim();
            if (!prompt && broadcastImages.length === 0) return alert("Please enter instructions or attach a picture/screenshot.");

            const imagesPayload = broadcastImages.map(img => ({ name: img.name, data: img.data }));
            const wsSelect = document.getElementById("broadcast-workspace-select");
            const wsId = wsSelect ? wsSelect.value : "";

            try {
                const res = await fetch("/api/dispatch", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ target: "broadcast", prompt, images: imagesPayload, workspace_id: wsId })
                });
                const data = await res.json();
                if (data.success) {
                    input.value = "";
                    broadcastImages = [];
                    renderBroadcastImages();
                    alert("Broadcast with attachments sent to active agents!");
                    fetchAllStatus();
                    fetchWorkspaces();
                } else {
                    alert(data.error || "Broadcast failed");
                }
            } catch (e) {
                alert("Broadcast error: " + e.message);
            }
        }

        async function toggleAgentPower(agentId, action) {
            const res = await fetch("/api/power", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ agent_id: agentId, action })
            });
            const data = await res.json();
            setTimeout(fetchAllStatus, 1500);
        }

        function toggleCurrentAgentPower() {
            if (currentView === "overview") return;
            const info = fleetStatuses[currentView] || {};
            const action = info.power === "running" ? "stop" : "start";
            toggleAgentPower(currentView, action);
        }

        async function powerPreset(preset) {
            if (preset === 'preset-2') {
                await toggleAgentPower('agent-1', 'start');
                await toggleAgentPower('agent-2', 'start');
                await toggleAgentPower('agent-3', 'stop');
                await toggleAgentPower('agent-4', 'stop');
                await toggleAgentPower('agent-5', 'stop');
            } else if (preset === 'preset-5') {
                for (let a of agents) {
                    await toggleAgentPower(a.id, 'start');
                }
            }
            setTimeout(fetchAllStatus, 2000);
        }

        async function saveDedicatedAuthToken() {
            const tokenJson = document.getElementById("dedicated-token-input").value.trim();
            if (!tokenJson) return alert("Please paste the OAuth token JSON.");

            const res = await fetch("/api/auth", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ token_json: tokenJson, target: currentView })
            });
            const data = await res.json();
            alert(data.message || data.error || "Token applied");
            document.getElementById("dedicated-token-input").value = "";
            fetchAllStatus();
        }

        // ============================================================
        // MODEL QUOTAS & TOKEN TRACKER LOGIC
        // ============================================================
        let currentAgentQuota = null;

        async function fetchAgentQuota(agentId, forceRefresh = false) {
            if (!agentId || agentId === "overview") return;
            const refreshIcon = document.getElementById("quota-refresh-icon");
            if (forceRefresh && refreshIcon) refreshIcon.classList.add("fa-spin");

            try {
                const url = `/api/agents/${agentId}/quota${forceRefresh ? '?force_refresh=true' : ''}`;
                const res = await fetch(url);
                if (res.ok) {
                    const data = await res.json();
                    if (currentView === agentId) {
                        renderAgentQuota(data);
                    }
                }
            } catch (e) {
                console.warn("Failed to fetch quota:", e);
            } finally {
                if (refreshIcon) refreshIcon.classList.remove("fa-spin");
            }
        }

        function refreshAgentQuota(force = true) {
            fetchAgentQuota(currentView, force);
        }

        function renderAgentQuota(data) {
            currentAgentQuota = data;
            if (!data || !data.authenticated) {
                const subBadge = document.getElementById("agent-page-quota-badge");
                if (subBadge) {
                    subBadge.innerText = "No Auth";
                    subBadge.className = "text-slate-500 font-semibold cursor-pointer hover:underline";
                }
                const tierEl = document.getElementById("quota-tier-name");
                if (tierEl) tierEl.innerText = "Authentication Required";
                return;
            }

            const tierEl = document.getElementById("quota-tier-name");
            if (tierEl && data.tier) {
                tierEl.innerText = `${data.tier.name || 'Antigravity'} (${data.tier.id || 'Active'})`;
            }

            const timeEl = document.getElementById("quota-updated-time");
            if (timeEl && data.timestamp) {
                const d = new Date(data.timestamp * 1000);
                timeEl.innerText = `Updated ${d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`;
            }

            const summary = data.summary || {};

            function updateMeter(key, obj) {
                const valEl = document.getElementById(`quota-val-${key}`);
                const barEl = document.getElementById(`quota-bar-${key}`);
                const resetEl = document.getElementById(`quota-reset-${key}`);

                if (!obj) {
                    if (valEl) valEl.innerText = "N/A";
                    if (barEl) barEl.style.width = "0%";
                    return;
                }

                const pct = obj.remaining_pct != null ? obj.remaining_pct : 100;
                if (valEl) {
                    valEl.innerText = `${pct}%`;
                    valEl.className = pct > 50 ? "font-mono font-bold text-emerald-400" : (pct > 20 ? "font-mono font-bold text-amber-400" : "font-mono font-bold text-rose-400");
                }
                if (barEl) {
                    barEl.style.width = `${Math.min(100, Math.max(0, pct))}%`;
                    if (pct <= 20) {
                        barEl.className = "bg-gradient-to-r from-rose-500 to-red-400 h-2 rounded-full transition-all duration-500";
                    }
                }
                if (resetEl && obj.reset_time) {
                    const rDate = new Date(obj.reset_time);
                    const now = new Date();
                    const diffHours = Math.round((rDate - now) / (1000 * 60 * 60));
                    resetEl.innerText = diffHours > 0 ? `Resets in ~${diffHours}h` : `Reset: ${rDate.toLocaleDateString()}`;
                }
            }

            updateMeter("gemini-flash", summary.gemini_flash);
            updateMeter("gemini-pro", summary.gemini_pro);
            updateMeter("claude", summary.claude);
            updateMeter("gpt", summary.gpt_oss);

            const subBadge = document.getElementById("agent-page-quota-badge");
            if (subBadge) {
                const best = summary.gemini_flash || summary.gemini_pro || summary.claude;
                if (best) {
                    const bp = best.remaining_pct;
                    subBadge.innerText = `${bp}%`;
                    subBadge.className = bp > 50 ? "text-emerald-400 font-semibold cursor-pointer hover:underline" : (bp > 20 ? "text-amber-400 font-semibold cursor-pointer hover:underline" : "text-rose-400 font-semibold cursor-pointer hover:underline");
                }
            }

            const allModels = data.models || {};
            const countEl = document.getElementById("all-models-count");
            if (countEl) countEl.innerText = Object.keys(allModels).length;

            const allContainer = document.getElementById("all-models-container");
            if (allContainer) {
                allContainer.innerHTML = Object.values(allModels).map(m => {
                    const p = m.remaining_pct != null ? m.remaining_pct : 100;
                    const pColor = p > 50 ? "text-emerald-400" : (p > 20 ? "text-amber-400" : "text-rose-400");
                    return `
                        <div class="flex items-center justify-between text-[11px] p-1.5 rounded hover:bg-white/5 border border-transparent hover:border-white/10 font-mono">
                            <span class="text-slate-300 truncate max-w-[200px]" title="${m.name}">${m.name}</span>
                            <div class="flex items-center gap-3 flex-shrink-0">
                                <span class="text-[10px] text-slate-500">${m.max_tokens ? (m.max_tokens >= 1000000 ? Math.round(m.max_tokens/1000000) + 'M' : Math.round(m.max_tokens/1000) + 'k') : ''}</span>
                                <span class="${pColor} font-bold w-12 text-right">${p}%</span>
                            </div>
                        </div>
                    `;
                }).join("");
            }
        }

        function toggleAllModelsList() {
            const c = document.getElementById("all-models-container");
            const chev = document.getElementById("all-models-chevron");
            if (c) {
                c.classList.toggle("hidden");
                if (chev) chev.classList.toggle("rotate-180");
            }
        }

        function reloadScreenIframe() {
            const iframe = document.getElementById(`dedicated-frame-${currentView}`);
            if (iframe) iframe.src = iframe.src;
        }

        async function restartAgentDesktop() {
            const res = await fetch(`/api/restart_desktop?agent_id=${currentView}`, { method: "POST" });
            const data = await res.json();
            alert(data.message || "Restarting desktop GUI...");
            setTimeout(reloadScreenIframe, 3000);
        }

        function toggleDedicatedFullscreen() {
            const iframe = document.getElementById(`dedicated-frame-${currentView}`);
            if (!iframe) return;
            if (iframe.requestFullscreen) iframe.requestFullscreen();
            else if (iframe.webkitRequestFullscreen) iframe.webkitRequestFullscreen();
        }

        function clearDedicatedTerminal() {
            document.getElementById("dedicated-terminal-logs").innerHTML = "<div class='text-slate-500 italic'>Terminal cleared.</div>";
            lastLogsHash = "";
        }


        // ============================================================
        // ============================================================
        // SKILLS HUB MANAGER CLIENT LOGIC
        // ============================================================
        let skillsLibrary = [];
        let installedSkillsMap = {};
        let currentSkillsCategory = "All";
        let activeSkillsTab = "library";

        async function fetchSkillsLibrary(forceRefresh = false) {
            try {
                const url = forceRefresh ? "/api/skills/library?refresh=1" : "/api/skills/library";
                const res = await fetch(url);
                const data = await res.json();
                skillsLibrary = data.skills || [];
                
                const totalBadge = document.getElementById("skills-lib-total-badge");
                if (totalBadge) totalBadge.innerText = `${skillsLibrary.length} Capabilities`;
                
                const tabLibCount = document.getElementById("tab-lib-count");
                if (tabLibCount) tabLibCount.innerText = skillsLibrary.length;

                const navBadge = document.getElementById("nav-skills-badge");
                if (navBadge) navBadge.innerText = `${skillsLibrary.length} Library`;

                const cardLibInfo = document.getElementById("card-skills-lib-info");
                if (cardLibInfo) cardLibInfo.innerText = `${skillsLibrary.length} Enterprise skills in library`;

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
                            <div class="flex items-center gap-1.5">
                                <a href="/api/skills/download?skill_id=${encodeURIComponent(s.name)}" download class="p-1.5 rounded-lg border text-slate-400 hover:text-white transition flex items-center justify-center" style="background-color: var(--bg-sidebar); border-color: var(--border-base);" title="Download ${escapeHtml(s.name)} package (.zip)">
                                    <i class="fa-solid fa-download text-xs text-sky-400"></i>
                                </a>
                                <button id="btn-load-${s.name}" onclick="loadSkillToTarget('${s.name}', this)" class="px-2.5 py-1 rounded-lg text-xs font-semibold transition flex items-center gap-1.5 ${isInstalled ? 'border text-slate-300 hover:text-white' : 'btn-action-primary shadow-sm'}" style="${isInstalled ? 'background-color: var(--bg-sidebar); border-color: var(--border-base);' : ''}">
                                    <i class="fa-solid ${isInstalled ? 'fa-arrows-rotate' : 'fa-plus'}"></i>
                                    ${isInstalled ? 'Reload' : 'Load Skill'}
                                </button>
                            </div>
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
                    <div class="flex items-center gap-1.5">
                        <a href="/api/skills/download_from_agent?agent_id=${encodeURIComponent(target)}&skill_name=${encodeURIComponent(s.name)}" download class="px-2 py-1 border text-slate-300 hover:text-white rounded-lg text-xs font-medium transition flex items-center gap-1" style="background-color: var(--bg-sidebar); border-color: var(--border-base);" title="Download skill package from agent (.zip)">
                            <i class="fa-solid fa-download text-[10px] text-sky-400"></i> Export
                        </a>
                        ${s.is_builtin ? `
                            <span class="text-[10px] text-slate-500 font-mono italic px-1">System</span>
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
            if (!confirm(`Synchronize entire skills library (${skillsLibrary.length} capabilities) to ${targetName}?\n\nThis injects all Convex, Clerk, Cloud & DevOps capabilities into ~/.gemini/skills.`)) {
                return;
            }

            const btn = document.getElementById("btn-sync-all-modal");
            if (btn) {
                btn.disabled = true;
                btn.innerHTML = `<i class="fa-solid fa-circle-notch fa-spin"></i> Syncing ${skillsLibrary.length} Skills...`;
            }

            try {
                const res = await fetch("/api/skills/sync_all", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ target })
                });
                const data = await res.json();
                if (data.success) {
                    alert(`Successfully synchronized entire skills library to ${targetName}!`);
                    await refreshTargetInstalledSkills();
                } else {
                    alert("Error: " + (data.error || "Failed to sync skills archive"));
                }
            } catch (e) {
                alert("Sync failed: " + e.message);
            } finally {
                if (btn) {
                    btn.disabled = false;
                    btn.innerHTML = `<i class="fa-solid fa-bolt text-amber-300"></i> Sync to Agent`;
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

        async function handleSkillFileUpload(files) {
            if (!files || files.length === 0) return;
            const file = files[0];
            const statusEl = document.getElementById("skill-upload-status");
            if (statusEl) {
                statusEl.classList.remove("hidden");
                statusEl.innerHTML = `<i class="fa-solid fa-circle-notch fa-spin"></i> Uploading and importing '${escapeHtml(file.name)}'...`;
            }

            const formData = new FormData();
            formData.append("file", file);

            try {
                const res = await fetch("/api/skills/upload", {
                    method: "POST",
                    body: formData
                });
                const data = await res.json();
                if (data.success) {
                    if (statusEl) {
                        statusEl.innerHTML = `<span class="text-emerald-400"><i class="fa-solid fa-circle-check"></i> ${escapeHtml(data.message)}</span>`;
                    }
                    await fetchSkillsLibrary(true);
                    setTimeout(() => {
                        switchSkillsTab("library");
                        if (statusEl) statusEl.classList.add("hidden");
                    }, 1400);
                } else {
                    if (statusEl) {
                        statusEl.innerHTML = `<span class="text-red-400"><i class="fa-solid fa-triangle-exclamation"></i> ${escapeHtml(data.error || "Upload failed")}</span>`;
                    }
                }
            } catch (e) {
                if (statusEl) {
                    statusEl.innerHTML = `<span class="text-red-400">Network error: ${escapeHtml(e.message)}</span>`;
                }
            }
        }

        function initSkillUploadDropzone() {
            const dropzone = document.getElementById("skill-upload-dropzone");
            if (!dropzone || dropzone.dataset.initialized) return;
            dropzone.dataset.initialized = "true";

            ['dragenter', 'dragover'].forEach(eventName => {
                dropzone.addEventListener(eventName, (e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    dropzone.style.borderColor = "var(--accent-primary)";
                    dropzone.style.backgroundColor = "rgba(245, 158, 11, 0.05)";
                }, false);
            });

            ['dragleave', 'drop'].forEach(eventName => {
                dropzone.addEventListener(eventName, (e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    dropzone.style.borderColor = "var(--border-base)";
                    dropzone.style.backgroundColor = "var(--bg-input)";
                }, false);
            });

            dropzone.addEventListener('drop', (e) => {
                const dt = e.dataTransfer;
                const files = dt.files;
                handleSkillFileUpload(files);
            }, false);
        }

        function populateSkillsTargetSelect() {
            const select = document.getElementById("skills-target-select");
            if (!select) return;
            const prevVal = select.value;
            select.innerHTML = agents.map(a => `
                <option value="${a.id}" class="bg-slate-900 text-white">${escapeHtml(a.name)} (CT ${a.vmid} - ${getAgentEngine(a.type).name})</option>
            `).join("") + `
                <option value="broadcast" class="bg-slate-900 text-amber-300 font-bold">⚡ All Active Agents (Fleet)</option>
            `;
            if (prevVal && (agents.some(a => a.id === prevVal) || prevVal === "broadcast")) {
                select.value = prevVal;
            } else if (agents.length > 0) {
                select.value = agents[0].id;
            }
        }

        function openSkillsModal(targetAgentId, tab = "library") {
            const modal = document.getElementById("skills-hub-modal");
            if (!modal) return;
            populateSkillsTargetSelect();
            const select = document.getElementById("skills-target-select");
            if (select) {
                if (targetAgentId) select.value = targetAgentId;
                else if (currentView !== "overview") select.value = currentView;
                else if (agents.length > 0) select.value = agents[0].id;
            }
            modal.classList.remove("hidden");
            fetchSkillsLibrary();
            switchSkillsTab(tab);
            refreshTargetInstalledSkills();
            initSkillUploadDropzone();
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
            const tabs = ["library", "installed", "import", "custom"];
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
            if (tab === "import") initSkillUploadDropzone();
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


                // ============================================================
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
                    if (Array.isArray(data.agents)) {
                        agents = data.agents;
                    } else {
                        agents = agents.filter(a => a.id !== agentToRemove);
                    }
                    
                    if (currentView === agentToRemove) {
                        currentView = agents.length > 0 ? agents[0].id : "overview";
                        selectView(currentView);
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
            const eng = getAgentEngine(selectedAddEngine);
            if (preview) {
                preview.innerHTML = `Selected: <span class="font-bold text-amber-400">${eng.name}</span> (${eng.defaultRole})`;
            }

            const specsCard = document.getElementById("engine-specs-card");
            if (specsCard) {
                specsCard.innerHTML = `
                    <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-2.5 border-b" style="border-color: var(--border-base);">
                        <div class="flex items-center gap-2">
                            <div class="w-7 h-7 rounded-lg flex items-center justify-center text-xs flex-shrink-0" style="background-color: ${eng.badgeBg}; color: ${eng.color}; border: 1px solid ${eng.badgeBorder};">
                                <i class="${eng.icon}"></i>
                            </div>
                            <div>
                                <span class="text-xs font-bold text-white">${eng.fullName}</span>
                                <span class="text-[10px] text-slate-400 ml-1 font-mono">(${eng.tag})</span>
                            </div>
                        </div>
                        <span class="text-[10px] font-mono px-2.5 py-1 rounded-full font-bold border self-start sm:self-auto ${eng.virtBadgeClass}">
                            ${eng.virtBadge}
                        </span>
                    </div>

                    <div class="grid grid-cols-2 sm:grid-cols-4 gap-2 my-2.5">
                        <div class="p-2 rounded-lg border flex flex-col" style="background-color: var(--bg-input); border-color: var(--border-base);">
                            <span class="text-[9px] uppercase font-bold text-slate-400">Environment</span>
                            <span class="text-xs font-bold text-white mt-0.5">${eng.recommendedVirt}</span>
                        </div>
                        <div class="p-2 rounded-lg border flex flex-col" style="background-color: var(--bg-input); border-color: var(--border-base);">
                            <span class="text-[9px] uppercase font-bold text-slate-400">CPU Compute</span>
                            <span class="text-xs font-bold text-amber-300 mt-0.5">${eng.minCpu}</span>
                        </div>
                        <div class="p-2 rounded-lg border flex flex-col" style="background-color: var(--bg-input); border-color: var(--border-base);">
                            <span class="text-[9px] uppercase font-bold text-slate-400">RAM Allocation</span>
                            <span class="text-xs font-bold text-emerald-300 mt-0.5">${eng.minRam}</span>
                        </div>
                        <div class="p-2 rounded-lg border flex flex-col" style="background-color: var(--bg-input); border-color: var(--border-base);">
                            <span class="text-[9px] uppercase font-bold text-slate-400">Storage Required</span>
                            <span class="text-xs font-bold text-sky-300 mt-0.5">${eng.minDisk}</span>
                        </div>
                    </div>

                    <div class="text-[11px] text-slate-300 flex items-start gap-2 pt-2 border-t" style="border-color: var(--border-base);">
                        <i class="fa-solid fa-circle-info text-slate-400 mt-0.5 flex-shrink-0"></i>
                        <span><strong class="text-white">Architecture Rationale:</strong> ${eng.virtReason}</span>
                    </div>
                `;
            }

            const host = window.location.host || "192.168.178.168:3000";
            const pveInput = document.getElementById("pve-provision-cmd");
            if (pveInput) {
                pveInput.value = `curl -sSL http://${host}/packages/scripts/pve_provision_agent.sh | bash -s -- --engine ${selectedAddEngine}`;
            }

            const cmdInput = document.getElementById("dynamic-install-cmd");
            if (cmdInput) {
                cmdInput.value = `curl -sSL http://${host}/install.sh | bash -s -- --engine ${selectedAddEngine}`;
            }

            const virtSelect = document.getElementById("new-agent-virt-type");
            if (virtSelect) {
                virtSelect.value = eng.virtType || "lxc";
            }

            const nameInput = document.getElementById("new-agent-name");
            const roleInput = document.getElementById("new-agent-role");
            if (nameInput && roleInput) {
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

            const standardVms = [
                { vmid: 151, ip: "192.168.178.169" },
                { vmid: 152, ip: "192.168.178.170" },
                { vmid: 153, ip: "192.168.178.171" },
                { vmid: 154, ip: "192.168.178.172" },
                { vmid: 155, ip: "192.168.178.173" }
            ];

            // Only show containers that are NOT already registered (by vmid OR ip)
            const registeredVmids = new Set(agents.map(a => a.vmid));
            const registeredIps = new Set(agents.map(a => a.ip));
            const totalStandby = standardVms
                .filter(v => !registeredVmids.has(v.vmid) && !registeredIps.has(v.ip))
                .map(u => ({ id: `agent-${u.vmid-150}`, vmid: u.vmid, ip: u.ip, isNew: true }));

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

        let _spinUpLock = false;
        async function quickSpinUpStandby(agentId, engineId, name, role, vmid, ip, isNew) {
            if (_spinUpLock) return;
            _spinUpLock = true;

            // Disable all spin-up buttons immediately to prevent double-clicks
            document.querySelectorAll('#standby-agents-list button').forEach(b => {
                b.disabled = true;
                b.classList.add('opacity-50', 'cursor-not-allowed');
                b.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Spinning Up...';
            });

            closeAddAgentModal();
            let newAgentId = agentId;
            try {
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
                    newAgentId = data.agent.id;  // Use server-assigned ID
                }
                buildSidebarDom();
                buildDedicatedIframes();
                buildOverviewScreensGrid();
                buildFleetTableDom();
            } catch (e) {
                console.error("Config update error", e);
                _spinUpLock = false;
                return;
            }

            await toggleAgentPower(newAgentId, 'start');
            selectView(newAgentId);

            // Push engine type to the container once it's online
            if (engineId !== 'antigravity') {
                const agent = agents.find(a => a.id === newAgentId);
                if (agent) {
                    const pushEngine = async () => {
                        const bridgeUrl = `http://${agent.ip}:${agent.port || 8000}`;
                        for (let attempt = 0; attempt < 10; attempt++) {
                            await new Promise(r => setTimeout(r, 3000));
                            try {
                                const res = await fetch(`${bridgeUrl}/configure_engine`, {
                                    method: 'POST',
                                    headers: { 'Content-Type': 'application/json' },
                                    body: JSON.stringify({ engine_type: engineId, restart_desktop: true })
                                });
                                if (res.ok) {
                                    console.log(`Engine type '${engineId}' pushed to container ${agent.vmid}`);
                                    return;
                                }
                            } catch (e) {}
                        }
                    };
                    pushEngine();
                }
            }

            _spinUpLock = false;
        }

        let _registerLock = false;
        async function registerNewCustomAgent() {
            if (_registerLock) return;
            _registerLock = true;

            const name = document.getElementById("new-agent-name").value.trim();
            const curEngine = getAgentEngine(selectedAddEngine);
            const role = document.getElementById("new-agent-role").value.trim() || curEngine.defaultRole;
            const ip = document.getElementById("new-agent-ip").value.trim();

            if (!name || !ip) { _registerLock = false; return alert("Please provide Agent Name and IP address"); }

            const virtType = (document.getElementById("new-agent-virt-type")?.value) || (['hermes', 'openclaw'].includes(selectedAddEngine) ? 'qemu' : 'lxc');

            try {
                const res = await fetch("/api/agents/add", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        name: name,
                        role: role,
                        ip: ip,
                        type: selectedAddEngine,
                        vm_type: virtType
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
                    if (!data.note) alert(`Agent '${name}' successfully added to Cockpit!`);
                } else {
                    alert(data.error || "Failed to add agent");
                }
            } catch (e) {
                alert("Network error: " + e.message);
            } finally {
                _registerLock = false;
            }
        }

        // ============================================================
        // WORKSPACES CLIENT LOGIC
        // ============================================================
        let workspaces = [];
        let activeWorkspacesTab = "library";
        let selectedUploadFile = null;
        let currentExplorerWsId = null;
        let currentExplorerTree = [];
        let currentExplorerActiveFile = null;

        async function fetchWorkspaces() {
            try {
                const res = await fetch("/api/workspaces");
                const data = await res.json();
                workspaces = data.workspaces || [];
                updateWorkspacesCounters();
                renderWorkspacesCards();
                populateWorkspaceDropdowns();
                renderWorkspaceMatrix();
                if (currentView && currentView !== "overview") {
                    updateDedicatedWorkspaceBadge(currentView);
                }
            } catch (e) {
                console.error("Failed to fetch workspaces:", e);
            }
        }

        function updateWorkspacesCounters() {
            const count = workspaces.length;
            const navBadge = document.getElementById("nav-workspaces-badge");
            if (navBadge) navBadge.innerText = `${count} Project${count === 1 ? '' : 's'}`;

            const hubBadge = document.getElementById("ws-hub-badge");
            if (hubBadge) hubBadge.innerText = `${count} Project${count === 1 ? '' : 's'}`;

            const tabCount = document.getElementById("ws-tab-count");
            if (tabCount) tabCount.innerText = count;

            const totalFiles = workspaces.reduce((sum, w) => sum + (w.file_count || 0), 0);
            const totalBytes = workspaces.reduce((sum, w) => sum + (w.size_bytes || 0), 0);
            const activeDeployments = new Set(workspaces.flatMap(w => w.synced_agents || [])).size;

            const elProjects = document.getElementById("ws-stats-projects");
            if (elProjects) elProjects.innerText = count;
            const elFiles = document.getElementById("ws-stats-files");
            if (elFiles) elFiles.innerText = totalFiles;
            const elSize = document.getElementById("ws-stats-size");
            if (elSize) elSize.innerText = totalBytes > 1024 * 1024 ? `${(totalBytes / (1024 * 1024)).toFixed(1)} MB` : `${Math.round(totalBytes / 1024)} KB`;
            const elDeployments = document.getElementById("ws-stats-deployments");
            if (elDeployments) elDeployments.innerText = `${activeDeployments} Agent${activeDeployments === 1 ? '' : 's'}`;
        }

        function openWorkspacesModal(targetAgentId, tab = "library") {
            const modal = document.getElementById("workspaces-modal");
            if (!modal) return;
            const select = document.getElementById("ws-target-agent-select");
            if (select) {
                if (targetAgentId && targetAgentId !== "overview") select.value = targetAgentId;
                else if (currentView !== "overview") select.value = currentView;
                else select.value = "agent-1";
            }
            modal.classList.remove("hidden");
            fetchWorkspaces();
            switchWorkspacesTab(tab);
        }

        function closeWorkspacesModal() {
            const modal = document.getElementById("workspaces-modal");
            if (modal) modal.classList.add("hidden");
            if (currentView && currentView !== "overview") {
                updateDedicatedWorkspaceBadge(currentView);
            }
        }

        function switchWorkspacesTab(tab) {
            if (tab === "import") tab = "git";
            activeWorkspacesTab = tab;
            const tabs = ["library", "git", "upload", "templates", "matrix"];
            tabs.forEach(t => {
                const view = document.getElementById(`ws-tab-${t}`);
                const btn = document.getElementById(`ws-tab-btn-${t}`);
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
            if (tab === "matrix") renderWorkspaceMatrix();
        }

        function handleWsFileSelect(files) {
            if (!files || files.length === 0) return;
            selectedUploadFile = files[0];
            const dropLabel = document.getElementById("ws-dropzone-label");
            if (dropLabel) {
                dropLabel.innerHTML = `<span class="text-emerald-400 font-bold"><i class="fa-solid fa-file-zipper mr-1"></i> ${escapeHtml(selectedUploadFile.name)}</span> (${Math.round(selectedUploadFile.size / 1024)} KB)`;
            }
            const nameInput = document.getElementById("ws-upload-name-input");
            if (nameInput && !nameInput.value.trim()) {
                let clean = selectedUploadFile.name.replace(/\\.(zip|tar\\.gz|tgz|tar)$/i, "");
                nameInput.value = clean.replace(/[^a-zA-Z0-9_\\-]/g, "_");
            }
        }

        async function submitWorkspaceArchiveUpload() {
            if (!selectedUploadFile) return alert("Please select a project ZIP or Tar archive first.");
            const btn = document.getElementById("btn-submit-ws-upload");
            const origHtml = btn.innerHTML;
            btn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Uploading & Unpacking...`;
            btn.disabled = true;

            const nameInput = document.getElementById("ws-upload-name-input");
            const descInput = document.getElementById("ws-upload-desc-input");
            const autoDeploy = document.getElementById("ws-upload-auto-deploy").checked;
            const targetSelect = document.getElementById("ws-target-agent-select");
            const targetAgent = autoDeploy ? (targetSelect ? targetSelect.value : "agent-1") : "none";

            const formData = new FormData();
            formData.append("file", selectedUploadFile);
            formData.append("name", nameInput ? nameInput.value.trim() : "");
            formData.append("description", descInput ? descInput.value.trim() : "");
            formData.append("target_agent", targetAgent);

            try {
                const res = await fetch("/api/workspaces/upload", {
                    method: "POST",
                    body: formData
                });
                const data = await res.json();
                if (data.success) {
                    selectedUploadFile = null;
                    const dropLabel = document.getElementById("ws-dropzone-label");
                    if (dropLabel) dropLabel.innerText = "Drop ZIP or Tar file here, or click to browse";
                    if (nameInput) nameInput.value = "";
                    if (descInput) descInput.value = "";
                    await fetchWorkspaces();
                    switchWorkspacesTab("library");
                    alert(`Project '${data.workspace.name}' successfully imported!${targetAgent !== 'none' ? ' Passed to ' + targetAgent : ''}`);
                } else {
                    alert(data.error || "Upload failed");
                }
            } catch (e) {
                alert("Upload error: " + e.message);
            } finally {
                btn.innerHTML = origHtml;
                btn.disabled = false;
            }
        }

        async function submitGitClone() {
            const urlInput = document.getElementById("ws-git-url-input");
            const branchInput = document.getElementById("ws-git-branch-input");
            const tokenInput = document.getElementById("ws-git-token-input");
            const nameInput = document.getElementById("ws-git-name-input");
            const descInput = document.getElementById("ws-git-desc-input");
            const autoDeploy = document.getElementById("ws-git-auto-deploy") ? document.getElementById("ws-git-auto-deploy").checked : true;
            const targetSelect = document.getElementById("ws-git-target-agent-select") || document.getElementById("ws-target-agent-select");
            const targetAgent = autoDeploy ? (targetSelect ? targetSelect.value : "agent-1") : "none";

            const repoUrl = urlInput ? urlInput.value.trim() : "";
            if (!repoUrl) return alert("Please enter a Git repository URL or owner/repo shorthand.");

            const btn = document.getElementById("btn-submit-ws-clone");
            const origHtml = btn.innerHTML;
            btn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Cloning & Ingesting Repository...`;
            btn.disabled = true;

            try {
                const res = await fetch("/api/workspaces/git_clone", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        repo_url: repoUrl,
                        branch: branchInput ? branchInput.value.trim() : "",
                        token: tokenInput ? tokenInput.value.trim() : "",
                        name: nameInput ? nameInput.value.trim() : "",
                        description: descInput ? descInput.value.trim() : "",
                        target_agent: targetAgent
                    })
                });
                const data = await res.json();
                if (data.success) {
                    urlInput.value = "";
                    if (branchInput) branchInput.value = "";
                    if (tokenInput) tokenInput.value = "";
                    if (nameInput) nameInput.value = "";
                    if (descInput) descInput.value = "";
                    await fetchWorkspaces();
                    switchWorkspacesTab("library");
                    alert(`Git repository '${data.workspace.name}' successfully cloned!${targetAgent !== 'none' ? ' Mounted to ' + targetAgent : ''}`);
                } else {
                    alert(data.error || "Git clone failed");
                }
            } catch (e) {
                alert("Git clone error: " + e.message);
            } finally {
                btn.innerHTML = origHtml;
                btn.disabled = false;
            }
        }

        function applyGitPreset(url, branch, name, desc) {
            const urlInput = document.getElementById("ws-git-url-input");
            const branchInput = document.getElementById("ws-git-branch-input");
            const nameInput = document.getElementById("ws-git-name-input");
            const descInput = document.getElementById("ws-git-desc-input");
            if (urlInput) urlInput.value = url;
            if (branchInput) branchInput.value = branch || "main";
            if (nameInput) nameInput.value = name;
            if (descInput) descInput.value = desc;
        }

        function toggleGitTokenVisibility() {
            const input = document.getElementById("ws-git-token-input");
            const icon = document.getElementById("ws-git-token-eye");
            if (!input) return;
            if (input.type === "password") {
                input.type = "text";
                if (icon) icon.className = "fa-solid fa-eye-slash text-sky-400";
            } else {
                input.type = "password";
                if (icon) icon.className = "fa-solid fa-eye text-slate-400";
            }
        }

        async function pullWorkspaceGit(wsId) {
            const btn = document.getElementById(`btn-gitpull-${wsId}`);
            let origHtml = "";
            if (btn) {
                origHtml = btn.innerHTML;
                btn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i>`;
                btn.disabled = true;
            }

            try {
                const res = await fetch(`/api/workspaces/${wsId}/git_pull`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ auto_redeploy: true })
                });
                const data = await res.json();
                if (data.success) {
                    await fetchWorkspaces();
                    alert(`Git repository '${data.workspace.name}' successfully pulled and updated!${data.redeploy ? '\\nAuto-redeployed to mounted agents.' : ''}`);
                } else {
                    alert(data.error || "Git pull failed");
                }
            } catch (e) {
                alert("Git pull error: " + e.message);
            } finally {
                if (btn) {
                    btn.innerHTML = origHtml;
                    btn.disabled = false;
                }
            }
        }

        async function createWorkspaceTemplate(template) {
            const defaultNames = {
                react: "react_vite_app",
                node: "express_api",
                python: "flask_service",
                blank: "my_project"
            };
            const name = prompt(`Enter project name for ${template} workspace:`, defaultNames[template] || "my_project");
            if (!name) return;

            try {
                const res = await fetch("/api/workspaces/create_template", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ template, name: name.trim() })
                });
                const data = await res.json();
                if (data.success) {
                    await fetchWorkspaces();
                    switchWorkspacesTab("library");
                    alert(`Workspace '${data.workspace.name}' created!`);
                } else {
                    alert(data.error || "Failed to create template");
                }
            } catch (e) {
                alert("Error: " + e.message);
            }
        }

        function renderWorkspacesCards(filter = "") {
            const container = document.getElementById("workspaces-cards-grid");
            if (!container) return;

            const search = (filter || document.getElementById("ws-search-input")?.value || "").toLowerCase().trim();
            const filtered = workspaces.filter(w => {
                if (!search) return true;
                return (w.name || "").toLowerCase().includes(search) ||
                       (w.description || "").toLowerCase().includes(search) ||
                       (w.primary_language || "").toLowerCase().includes(search) ||
                       (w.source || "").toLowerCase().includes(search);
            });

            if (filtered.length === 0) {
                container.innerHTML = `
                    <div class="col-span-full p-10 glass rounded-3xl border text-center space-y-4" style="border-color: var(--border-base);">
                        <div class="w-14 h-14 rounded-2xl mx-auto flex items-center justify-center text-2xl text-emerald-400 bg-emerald-500/10 border border-emerald-500/30">
                            <i class="fa-solid fa-folder-open"></i>
                        </div>
                        <div>
                            <h4 class="text-base font-bold text-white">${search ? "No matching projects found" : "No project workspaces imported yet"}</h4>
                            <p class="text-xs text-slate-400 max-w-md mx-auto mt-1">
                                ${search ? "Try searching with a different term or clear the filter." : "Import your code directly into Cockpit via ZIP upload, Git clone, or starter templates to pass codebases to AI agents."}
                            </p>
                        </div>
                        ${!search ? `
                            <button onclick="switchWorkspacesTab('import')" class="px-4 py-2 btn-action-primary rounded-xl text-xs font-semibold inline-flex items-center gap-2 shadow-lg">
                                <i class="fa-solid fa-cloud-arrow-up"></i> Import Your First Project
                            </button>
                        ` : ''}
                    </div>
                `;
                return;
            }

            container.innerHTML = filtered.map(w => {
                const sizeStr = (w.size_bytes || 0) > 1024 * 1024 ? `${((w.size_bytes || 0) / (1024 * 1024)).toFixed(1)} MB` : `${Math.round((w.size_bytes || 0) / 1024)} KB`;
                const synced = w.synced_agents || [];
                const syncedPills = synced.length > 0 ? synced.map(aid => {
                    const ag = agents.find(a => a.id === aid);
                    const label = ag ? ag.name : aid;
                    return `<span class="px-2 py-0.5 rounded-lg text-[10px] font-mono border bg-emerald-500/10 text-emerald-400 border-emerald-500/30 flex items-center gap-1"><span class="w-1.5 h-1.5 rounded-full bg-emerald-400"></span> ${escapeHtml(label)}</span>`;
                }).join("") : `<span class="text-[10px] text-slate-500 italic">Not deployed to any agent</span>`;

                let iconClass = "fa-brands fa-js text-yellow-400";
                const lang = (w.primary_language || "").toLowerCase();
                if (lang.includes("react") || lang.includes("next")) iconClass = "fa-brands fa-react text-cyan-400";
                else if (lang.includes("python")) iconClass = "fa-brands fa-python text-amber-400";
                else if (lang.includes("rust")) iconClass = "fa-brands fa-rust text-orange-400";
                else if (lang.includes("go")) iconClass = "fa-brands fa-golang text-sky-400";
                else if (lang.includes("node")) iconClass = "fa-brands fa-node-js text-emerald-400";
                else if (lang.includes("html")) iconClass = "fa-brands fa-html5 text-rose-400";

                return `
                    <div class="glass p-4 rounded-2xl border flex flex-col justify-between space-y-3.5 hover:border-slate-500 transition group shadow-lg" style="background-color: var(--bg-card); border-color: var(--border-base);">
                        <div class="space-y-2">
                            <!-- Card Top: Name & Badges -->
                            <div class="flex items-start justify-between gap-2">
                                <div class="flex items-center space-x-2.5 min-w-0">
                                    <div class="w-9 h-9 rounded-xl border flex items-center justify-center text-base flex-shrink-0" style="background-color: var(--bg-input); border-color: var(--border-base);">
                                        <i class="${iconClass}"></i>
                                    </div>
                                    <div class="min-w-0">
                                        <h4 class="text-sm font-bold text-white truncate group-hover:text-emerald-400 transition" title="${escapeHtml(w.name)}">${escapeHtml(w.name)}</h4>
                                        <span class="text-[10px] font-mono text-slate-400">${escapeHtml(w.primary_language || 'Generic')}</span>
                                    </div>
                                </div>
                                ${w.source === 'git' || w.git_url ? `
                                    <span class="px-2 py-0.5 rounded-full text-[9px] font-mono font-bold uppercase border bg-sky-500/10 text-sky-400 border-sky-500/30 flex items-center gap-1 flex-shrink-0">
                                        <i class="fa-brands fa-git-alt"></i> Git
                                    </span>
                                ` : `
                                    <span class="px-2 py-0.5 rounded-full text-[9px] font-mono font-bold uppercase border flex-shrink-0" style="background: var(--badge-bg); color: var(--badge-text); border-color: var(--border-base);">
                                        ${w.source || 'upload'}
                                    </span>
                                `}
                            </div>

                            <!-- Description -->
                            <p class="text-xs text-slate-300 line-clamp-2 min-h-[32px]">${escapeHtml(w.description || 'No description')}</p>

                            <!-- Metrics Strip -->
                            <div class="flex items-center flex-wrap gap-3 text-[11px] text-slate-400 font-mono pt-1 border-t" style="border-color: var(--border-base);">
                                <span><i class="fa-regular fa-file-code text-cyan-400 mr-1"></i> ${w.file_count || 0} files</span>
                                <span><i class="fa-regular fa-hard-drive text-amber-400 mr-1"></i> ${sizeStr}</span>
                                ${w.git_branch ? `<span title="${escapeHtml(w.git_commit_msg || '')}"><i class="fa-brands fa-git-alt text-sky-400 mr-1"></i> ${escapeHtml(w.git_branch)}${w.git_commit ? ' @ ' + escapeHtml(w.git_commit) : ''}</span>` : ''}
                            </div>

                            <!-- Deployed Agents Pills -->
                            <div class="pt-1.5 space-y-1">
                                <span class="text-[10px] uppercase font-bold text-slate-500 tracking-wider">Mounted Agents:</span>
                                <div class="flex flex-wrap gap-1.5 items-center">
                                    ${syncedPills}
                                </div>
                            </div>
                        </div>

                        <!-- Card Action Toolbar -->
                        <div class="pt-2 border-t flex flex-wrap items-center justify-between gap-2" style="border-color: var(--border-base);">
                            <div class="flex items-center gap-1.5">
                                <select id="ws-card-target-${w.id}" class="px-2 py-1 border rounded-lg text-xs font-semibold cursor-pointer" style="background-color: var(--bg-input); border-color: var(--border-base); color: var(--text-main);">
                                    ${agents.map(a => `<option value="${a.id}">${escapeHtml(a.name)}</option>`).join("")}
                                    <option value="broadcast">⚡ All Active</option>
                                </select>
                                <button onclick="deployWorkspaceFromCard('${w.id}')" id="btn-deploy-${w.id}" class="px-2.5 py-1 btn-action-primary rounded-lg text-xs font-semibold flex items-center gap-1 shadow" title="Pass workspace directly to selected agent">
                                    <i class="fa-solid fa-bolt text-emerald-300"></i> Deploy
                                </button>
                            </div>

                            <div class="flex items-center gap-1">
                                ${w.source === 'git' || w.git_url ? `
                                    <button onclick="pullWorkspaceGit('${w.id}')" id="btn-gitpull-${w.id}" class="p-1.5 border rounded-lg text-xs text-sky-400 hover:text-white hover:bg-sky-500/20 transition" style="background-color: var(--bg-input); border-color: var(--border-base);" title="Pull latest changes from remote Git repository (git pull)">
                                        <i class="fa-solid fa-code-pull-request"></i>
                                    </button>
                                ` : ''}
                                ${w.git_url ? `
                                    <a href="${escapeHtml(w.git_url)}" target="_blank" class="p-1.5 border rounded-lg text-xs text-slate-400 hover:text-white transition" style="background-color: var(--bg-input); border-color: var(--border-base);" title="Open remote repository on web">
                                        <i class="fa-solid fa-arrow-up-right-from-square"></i>
                                    </a>
                                ` : ''}
                                <button onclick="openWorkspaceExplorer('${w.id}')" class="p-1.5 border rounded-lg text-xs text-cyan-400 hover:text-white transition" style="background-color: var(--bg-input); border-color: var(--border-base);" title="Browse code & directory tree">
                                    <i class="fa-solid fa-code"></i>
                                </button>
                                <button onclick="pullWorkspaceChanges('${w.id}')" class="p-1.5 border rounded-lg text-xs text-amber-400 hover:text-white transition" style="background-color: var(--bg-input); border-color: var(--border-base);" title="Pull changes written by agent back to Cockpit">
                                    <i class="fa-solid fa-rotate"></i>
                                </button>
                                <button onclick="downloadWorkspaceArchive('${w.id}')" class="p-1.5 border rounded-lg text-xs text-emerald-400 hover:text-white transition" style="background-color: var(--bg-input); border-color: var(--border-base);" title="Download as ZIP">
                                    <i class="fa-solid fa-download"></i>
                                </button>
                                <button onclick="confirmDeleteWorkspace('${w.id}', '${escapeHtml(w.name)}')" class="p-1.5 border rounded-lg text-xs text-rose-400 hover:text-white hover:bg-rose-500/20 transition" style="background-color: var(--bg-input); border-color: var(--border-base);" title="Delete workspace">
                                    <i class="fa-solid fa-trash-can"></i>
                                </button>
                            </div>
                        </div>
                    </div>
                `;
            }).join("");
        }

        function filterWorkspacesDisplay() {
            renderWorkspacesCards();
        }

        async function deployWorkspace(wsId, targetAgentId) {
            const btn = document.getElementById(`btn-deploy-${wsId}`);
            let origHtml = "";
            if (btn) {
                origHtml = btn.innerHTML;
                btn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i>`;
                btn.disabled = true;
            }

            try {
                const res = await fetch(`/api/workspaces/${wsId}/deploy`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ target: targetAgentId, clean_first: false })
                });
                const data = await res.json();
                if (data.success) {
                    await fetchWorkspaces();
                    alert(`Workspace successfully mounted to ${targetAgentId === 'broadcast' ? 'all active agents' : targetAgentId}!`);
                } else {
                    alert(data.error || "Deploy failed");
                }
            } catch (e) {
                alert("Deploy error: " + e.message);
            } finally {
                if (btn) {
                    btn.innerHTML = origHtml;
                    btn.disabled = false;
                }
            }
        }

        function deployWorkspaceFromCard(wsId) {
            const select = document.getElementById(`ws-card-target-${wsId}`);
            const target = select ? select.value : "agent-1";
            deployWorkspace(wsId, target);
        }

        async function pullWorkspaceChanges(wsId) {
            const ws = workspaces.find(w => w.id === wsId);
            const agentId = (ws && ws.synced_agents && ws.synced_agents.length > 0) ? ws.synced_agents[0] : (currentView !== "overview" ? currentView : "agent-1");
            const conf = confirm(`Pull changes from ${agentId} into Cockpit workspace '${ws ? ws.name : wsId}'? This will update the Cockpit copy with files written by the agent.`);
            if (!conf) return;

            try {
                const res = await fetch(`/api/workspaces/${wsId}/pull`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ agent_id: agentId })
                });
                const data = await res.json();
                if (data.success) {
                    await fetchWorkspaces();
                    alert(`Successfully pulled updated code from ${agentId}! (${data.workspace.file_count} files)`);
                } else {
                    alert(data.error || "Pull failed");
                }
            } catch (e) {
                alert("Pull error: " + e.message);
            }
        }

        function downloadWorkspaceArchive(wsId) {
            window.location.href = `/api/workspaces/${wsId}/download`;
        }

        async function confirmDeleteWorkspace(wsId, wsName) {
            if (!confirm(`Are you sure you want to delete workspace '${wsName}'? Files stored on Cockpit will be removed.`)) return;
            try {
                const res = await fetch(`/api/workspaces/${wsId}`, { method: "DELETE" });
                const data = await res.json();
                if (data.success) {
                    await fetchWorkspaces();
                } else {
                    alert(data.error || "Delete failed");
                }
            } catch (e) {
                alert("Delete error: " + e.message);
            }
        }

        function populateWorkspaceDropdowns() {
            const dedicatedSel = document.getElementById("dedicated-workspace-select");
            const broadcastSel = document.getElementById("broadcast-workspace-select");

            const currentDedVal = dedicatedSel ? dedicatedSel.value : "";
            const currentBrdVal = broadcastSel ? broadcastSel.value : "";

            const optionsHtml = `<option value="" class="bg-slate-900 text-slate-400">No Workspace</option>` +
                workspaces.map(w => `<option value="${w.id}" class="bg-slate-900 text-white">${escapeHtml(w.name)} (${w.file_count} files)</option>`).join("");

            if (dedicatedSel) {
                dedicatedSel.innerHTML = optionsHtml;
                if (currentDedVal && workspaces.some(w => w.id === currentDedVal)) {
                    dedicatedSel.value = currentDedVal;
                }
                onDedicatedWorkspaceChanged();
            }

            if (broadcastSel) {
                broadcastSel.innerHTML = optionsHtml;
                if (currentBrdVal && workspaces.some(w => w.id === currentBrdVal)) {
                    broadcastSel.value = currentBrdVal;
                }
            }
        }

        function onDedicatedWorkspaceChanged() {
            const select = document.getElementById("dedicated-workspace-select");
            const badge = document.getElementById("dedicated-workspace-sync-badge");
            if (!select || !badge) return;

            const wsId = select.value;
            if (!wsId) {
                badge.classList.add("hidden");
                return;
            }

            const ws = workspaces.find(w => w.id === wsId);
            if (!ws) {
                badge.classList.add("hidden");
                return;
            }

            const isSynced = (ws.synced_agents || []).includes(currentView);
            badge.classList.remove("hidden");
            if (isSynced) {
                badge.className = "px-1.5 py-0.2 rounded text-[9px] font-mono border bg-emerald-500/20 text-emerald-400 border-emerald-500/30";
                badge.innerHTML = `<i class="fa-solid fa-check mr-0.5"></i> Synced`;
            } else {
                badge.className = "px-1.5 py-0.2 rounded text-[9px] font-mono border bg-amber-500/20 text-amber-300 border-amber-500/30 cursor-pointer";
                badge.innerHTML = `Deploy on dispatch`;
                badge.title = "Workspace will be automatically deployed when task is dispatched";
            }
        }

        function updateDedicatedWorkspaceBadge(agentId) {
            const badge = document.getElementById("agent-page-ws-badge");
            if (!badge) return;

            const mountedWs = workspaces.filter(w => (w.synced_agents || []).includes(agentId));
            if (mountedWs.length > 0) {
                badge.innerText = mountedWs.map(w => w.name).join(", ");
                badge.className = "text-emerald-400 font-semibold cursor-pointer hover:underline";
            } else {
                badge.innerText = "Default (None)";
                badge.className = "text-slate-400 font-normal cursor-pointer hover:underline";
            }
        }

        function renderWorkspaceMatrix() {
            const tbody = document.getElementById("ws-matrix-table-body");
            if (!tbody) return;

            tbody.innerHTML = agents.map(agent => {
                const mounted = workspaces.filter(w => (w.synced_agents || []).includes(agent.id));
                const wsNames = mounted.length > 0 ? mounted.map(w => `<span class="px-2 py-0.5 rounded font-bold border bg-emerald-500/10 text-emerald-400 border-emerald-500/30">${escapeHtml(w.name)}</span>`).join(" ") : `<span class="text-slate-500 italic">None mounted</span>`;
                const totalFiles = mounted.reduce((s, w) => s + (w.file_count || 0), 0);

                return `
                    <tr class="border-b hover:bg-white/5 transition" style="border-color: var(--border-base);">
                        <td class="p-3.5 font-bold text-white flex items-center gap-2">
                            <span class="w-2 h-2 rounded-full ${mounted.length > 0 ? 'bg-emerald-400' : 'bg-slate-500'}"></span>
                            ${escapeHtml(agent.name)}
                        </td>
                        <td class="p-3.5 text-slate-400 font-mono">CT ${agent.vmid} (${agent.ip})</td>
                        <td class="p-3.5">${wsNames}</td>
                        <td class="p-3.5 text-slate-300 font-mono">/home/ubuntu/workspace (${totalFiles} files)</td>
                        <td class="p-3.5">
                            <span class="px-2 py-0.5 rounded text-[10px] font-bold ${mounted.length > 0 ? 'bg-emerald-500/20 text-emerald-400' : 'bg-slate-500/20 text-slate-400'}">
                                ${mounted.length > 0 ? 'Active Mount' : 'Idle'}
                            </span>
                        </td>
                        <td class="p-3.5 text-right">
                            <button onclick="openWorkspacesModal('${agent.id}', 'library')" class="px-2.5 py-1 btn-action-primary rounded-lg text-xs font-semibold shadow">
                                Mount Project...
                            </button>
                        </td>
                    </tr>
                `;
            }).join("");
        }

        // ============================================================
        // CODE EXPLORER & FILE TREE CLIENT LOGIC
        // ============================================================
        async function openWorkspaceExplorer(wsId, initialPath = null) {
            const modal = document.getElementById("workspace-explorer-modal");
            if (!modal) return;
            currentExplorerWsId = wsId;
            currentExplorerActiveFile = null;

            const ws = workspaces.find(w => w.id === wsId);
            const gitPullBtn = document.getElementById("explorer-git-pull-btn");
            if (ws) {
                document.getElementById("explorer-ws-title").innerText = ws.name;
                document.getElementById("explorer-stack-badge").innerText = ws.primary_language || "Codebase";
                document.getElementById("explorer-ws-path").innerText = `/usr/local/share/cockpit/workspaces/${ws.id}${ws.git_branch ? ' • Git: ' + ws.git_branch + (ws.git_commit ? ' @ ' + ws.git_commit : '') : ''}`;
                if (gitPullBtn) {
                    if (ws.source === "git" || ws.git_url) {
                        gitPullBtn.classList.remove("hidden");
                    } else {
                        gitPullBtn.classList.add("hidden");
                    }
                }
            }

            modal.classList.remove("hidden");
            document.getElementById("explorer-code-container").innerHTML = `
                <div class="h-full flex items-center justify-center text-slate-500 italic">
                    <i class="fa-solid fa-spinner fa-spin mr-2"></i> Loading project file tree...
                </div>
            `;

            try {
                const res = await fetch(`/api/workspaces/${wsId}/tree`);
                const data = await res.json();
                currentExplorerTree = data.tree || [];
                renderExplorerTree(currentExplorerTree, document.getElementById("explorer-tree-container"));

                const candidate = findFirstFile(currentExplorerTree);
                if (initialPath) {
                    loadWorkspaceFileContent(wsId, initialPath);
                } else if (candidate) {
                    loadWorkspaceFileContent(wsId, candidate);
                }
            } catch (e) {
                document.getElementById("explorer-tree-container").innerHTML = `<div class="text-rose-400 text-xs p-2">Failed to load tree: ${e.message}</div>`;
            }
        }

        async function pullGitFromExplorer() {
            if (!currentExplorerWsId) return;
            await pullWorkspaceGit(currentExplorerWsId);
            openWorkspaceExplorer(currentExplorerWsId, currentExplorerActiveFile);
        }

        function closeWorkspaceExplorer() {
            const modal = document.getElementById("workspace-explorer-modal");
            if (modal) modal.classList.add("hidden");
            currentExplorerWsId = null;
        }

        function findFirstFile(nodes) {
            if (!nodes) return null;
            for (const n of nodes) {
                if (!n.is_dir && (n.name.toLowerCase() === "readme.md" || n.name.toLowerCase() === "package.json")) {
                    return n.path;
                }
            }
            for (const n of nodes) {
                if (!n.is_dir) return n.path;
                if (n.children) {
                    const sub = findFirstFile(n.children);
                    if (sub) return sub;
                }
            }
            return null;
        }

        function renderExplorerTree(nodes, container, filter = "") {
            if (!container) return;
            if (!nodes || nodes.length === 0) {
                container.innerHTML = `<div class="text-slate-500 text-xs italic p-2">Empty directory</div>`;
                return;
            }

            const search = (filter || "").toLowerCase().trim();

            function buildNodesHtml(list, indent = 0) {
                return list.map(item => {
                    if (search && !item.name.toLowerCase().includes(search) && (!item.is_dir || !itemMatchesSearch(item, search))) {
                        return "";
                    }

                    const pl = indent * 14;
                    if (item.is_dir) {
                        return `
                            <div class="tree-dir-node">
                                <div onclick="toggleTreeDir(this)" class="px-2 py-1 rounded-lg cursor-pointer hover:bg-white/10 flex items-center justify-between text-slate-300 hover:text-white transition" style="padding-left: ${pl + 8}px;">
                                    <div class="flex items-center gap-1.5 truncate">
                                        <i class="fa-solid fa-folder-open text-amber-400 text-xs tree-folder-icon"></i>
                                        <span class="truncate font-semibold">${escapeHtml(item.name)}</span>
                                    </div>
                                    <span class="text-[10px] text-slate-500">${(item.children || []).length}</span>
                                </div>
                                <div class="tree-children space-y-0.5">
                                    ${buildNodesHtml(item.children || [], indent + 1)}
                                </div>
                            </div>
                        `;
                    } else {
                        let fIcon = "fa-regular fa-file-code text-cyan-400";
                        const ext = item.name.split('.').pop().toLowerCase();
                        if (["ts", "tsx"].includes(ext)) fIcon = "fa-solid fa-code text-blue-400";
                        else if (["js", "jsx"].includes(ext)) fIcon = "fa-brands fa-js text-yellow-400";
                        else if (["py"].includes(ext)) fIcon = "fa-brands fa-python text-amber-400";
                        else if (["json"].includes(ext)) fIcon = "fa-solid fa-brackets-curly text-emerald-400";
                        else if (["md"].includes(ext)) fIcon = "fa-brands fa-markdown text-purple-400";
                        else if (["css", "scss"].includes(ext)) fIcon = "fa-brands fa-css3-alt text-sky-400";
                        else if (["html"].includes(ext)) fIcon = "fa-brands fa-html5 text-orange-400";

                        const isActive = currentExplorerActiveFile === item.path;
                        const activeClass = isActive ? "bg-white/20 text-white font-bold" : "text-slate-400 hover:text-slate-200 hover:bg-white/5";

                        return `
                            <div onclick="loadWorkspaceFileContent('${currentExplorerWsId}', '${escapeHtml(item.path)}')" class="px-2 py-1 rounded-lg cursor-pointer transition flex items-center justify-between truncate ${activeClass}" style="padding-left: ${pl + 8}px;" title="${escapeHtml(item.path)}">
                                <div class="flex items-center gap-1.5 truncate">
                                    <i class="${fIcon} text-xs"></i>
                                    <span class="truncate">${escapeHtml(item.name)}</span>
                                </div>
                                <span class="text-[9px] text-slate-500 font-mono">${Math.round((item.size || 0) / 1024)}k</span>
                            </div>
                        `;
                    }
                }).join("");
            }

            container.innerHTML = buildNodesHtml(nodes, 0);
        }

        function itemMatchesSearch(dirNode, search) {
            if (!dirNode.children) return false;
            for (const c of dirNode.children) {
                if (c.name.toLowerCase().includes(search)) return true;
                if (c.is_dir && itemMatchesSearch(c, search)) return true;
            }
            return false;
        }

        function toggleTreeDir(el) {
            const container = el.parentElement.querySelector(".tree-children");
            const icon = el.querySelector(".tree-folder-icon");
            if (container) {
                if (container.classList.contains("hidden")) {
                    container.classList.remove("hidden");
                    if (icon) {
                        icon.classList.remove("fa-folder");
                        icon.classList.add("fa-folder-open");
                    }
                } else {
                    container.classList.add("hidden");
                    if (icon) {
                        icon.classList.remove("fa-folder-open");
                        icon.classList.add("fa-folder");
                    }
                }
            }
        }

        function filterExplorerTree(val) {
            renderExplorerTree(currentExplorerTree, document.getElementById("explorer-tree-container"), val);
        }

        async function loadWorkspaceFileContent(wsId, filePath) {
            currentExplorerActiveFile = filePath;
            renderExplorerTree(currentExplorerTree, document.getElementById("explorer-tree-container"));

            const fnEl = document.getElementById("explorer-active-filename");
            const metricsEl = document.getElementById("explorer-file-metrics");
            const codeEl = document.getElementById("explorer-code-container");
            const footerEl = document.getElementById("explorer-footer-path");

            if (fnEl) fnEl.innerText = filePath;
            if (footerEl) footerEl.innerText = filePath;

            codeEl.innerHTML = `<div class="p-8 text-center text-slate-500 italic"><i class="fa-solid fa-spinner fa-spin mr-2"></i> Loading file...</div>`;

            try {
                const res = await fetch(`/api/workspaces/${wsId}/file?path=${encodeURIComponent(filePath)}`);
                const data = await res.json();
                if (res.ok) {
                    if (metricsEl) metricsEl.innerText = `• ${data.lines || 0} lines • ${Math.round((data.size || 0) / 1024)} KB`;
                    
                    const lines = (data.content || "").split(String.fromCharCode(10));
                    const linesHtml = lines.map((line, idx) => `
                        <div class="table-row hover:bg-white/5">
                            <span class="table-cell text-right pr-4 select-none text-slate-600 text-[11px]">${idx + 1}</span>
                            <span class="table-cell whitespace-pre font-mono text-slate-200 text-xs">${escapeHtml(line) || ' '}</span>
                        </div>
                    `).join("");

                    codeEl.innerHTML = `<div class="table w-full">${linesHtml}</div>`;
                } else {
                    codeEl.innerHTML = `<div class="p-8 text-center text-rose-400 text-xs">${data.error || "Failed to load file"}</div>`;
                }
            } catch (e) {
                codeEl.innerHTML = `<div class="p-8 text-center text-rose-400 text-xs">Error loading file: ${e.message}</div>`;
            }
        }

        function copyExplorerCode() {
            const container = document.getElementById("explorer-code-container");
            if (!container) return;
            const text = container.innerText;
            navigator.clipboard.writeText(text);
            const btn = document.getElementById("btn-copy-code");
            if (btn) {
                const orig = btn.innerHTML;
                btn.innerHTML = `<i class="fa-solid fa-check text-emerald-400"></i> Copied!`;
                setTimeout(() => { btn.innerHTML = orig; }, 1500);
            }
        }

        function deployFromExplorer() {
            if (!currentExplorerWsId) return;
            const targetSelect = document.getElementById("explorer-deploy-target-select");
            const target = targetSelect ? targetSelect.value : "agent-1";
            deployWorkspace(currentExplorerWsId, target);
        }

        function downloadFromExplorer() {
            if (!currentExplorerWsId) return;
            downloadWorkspaceArchive(currentExplorerWsId);
        }

        // ============================================================
        // CEO EXECUTIVE SUITE CLIENT CONTROLLER (PAPERCLIP PATTERN)
        // ============================================================
        let ceoPollTimer = null;
        let currentCeoTab = "kanban";
        let ceoRoleList = [];

        function openCeoModal() {
            const modal = document.getElementById("ceo-modal");
            if (!modal) return;
            modal.classList.remove("hidden");
            
            // Populate workspace dropdown
            populateCeoWorkspaceSelect();
            refreshCeoData();
            switchCeoTab(currentCeoTab);

            if (ceoPollTimer) clearInterval(ceoPollTimer);
            ceoPollTimer = setInterval(refreshCeoData, 4000);
        }

        function closeCeoModal() {
            const modal = document.getElementById("ceo-modal");
            if (modal) modal.classList.add("hidden");
            if (ceoPollTimer) {
                clearInterval(ceoPollTimer);
                ceoPollTimer = null;
            }
        }

        function populateCeoWorkspaceSelect() {
            const select = document.getElementById("ceo-ws-select");
            if (!select) return;
            fetch("/api/workspaces")
                .then(r => r.json())
                .then(res => {
                    const wsList = res.workspaces || [];
                    const currentVal = select.value;
                    select.innerHTML = '<option value="">Target Workspace: None</option>' +
                        wsList.map(w => `<option value="${w.id}">${w.name} (${w.primary_language || 'Codebase'})</option>`).join("");
                    if (currentVal) select.value = currentVal;
                })
                .catch(err => console.error("Failed to load workspaces for CEO select", err));
        }

        function switchCeoTab(tabId) {
            currentCeoTab = tabId;
            const tabs = ["kanban", "org", "heartbeat", "charter"];
            tabs.forEach(t => {
                const view = document.getElementById(`ceo-view-${t}`);
                const btn = document.getElementById(`ceo-tab-btn-${t}`);
                if (view) {
                    if (t === tabId) view.classList.remove("hidden");
                    else view.classList.add("hidden");
                }
                if (btn) {
                    if (t === tabId) {
                        btn.style.borderColor = "var(--accent-primary)";
                        btn.style.color = "var(--highlight-text)";
                    } else {
                        btn.style.borderColor = "transparent";
                        btn.style.color = "#94a3b8";
                    }
                }
            });

            if (tabId === "charter") {
                loadCeoCharterPrompt("AGENTS.md");
            }
        }

        function refreshCeoData() {
            // 1. Fetch Executive Status & Metrics
            fetch("/api/ceo/status")
                .then(r => r.json())
                .then(data => {
                    if (!data) return;
                    
                    // Update pulse badge and summary
                    const pulseCounter = document.getElementById("ceo-pulse-counter");
                    if (pulseCounter && data.heartbeat) {
                        pulseCounter.innerText = data.heartbeat.count || 1;
                    }
                    const summaryBanner = document.getElementById("ceo-summary-banner");
                    if (summaryBanner) {
                        summaryBanner.innerText = data.executive_summary || "Standing by.";
                    }
                    const lastPulseTime = document.getElementById("ceo-last-pulse-time");
                    if (lastPulseTime && data.heartbeat && data.heartbeat.timestamp) {
                        const elapsed = Math.max(0, Math.floor(Date.now() / 1000 - data.heartbeat.timestamp));
                        lastPulseTime.innerText = `Last pulse ${elapsed}s ago`;
                    }

                    // Update metrics
                    if (data.metrics) {
                        const m = data.metrics;
                        const vEl = document.getElementById("metric-velocity");
                        if (vEl) vEl.innerText = `${m.velocity_pct || 100}%`;
                        const ipEl = document.getElementById("metric-in-progress");
                        if (ipEl) ipEl.innerText = m.in_progress || 0;
                        const bEl = document.getElementById("metric-blocked");
                        if (bEl) bEl.innerText = m.blocked || 0;
                        const tEl = document.getElementById("badge-total-tasks");
                        if (tEl) tEl.innerText = m.total_tasks || 0;
                    }

                    // Store roles
                    if (data.roles) ceoRoleList = data.roles;

                    // Render Heartbeat & Audit logs
                    renderHeartbeatLogs(data.heartbeat?.log || [], data.audit_log || []);
                })
                .catch(err => console.error("Failed fetching CEO status", err));

            // 2. Fetch Work Orders for Kanban
            fetch("/api/ceo/tasks")
                .then(r => r.json())
                .then(res => {
                    renderKanbanCards(res.tasks || []);
                })
                .catch(err => console.error("Failed fetching CEO tasks", err));

            // 3. Fetch Org Chart & Fleet Roles
            fetch("/api/ceo/org")
                .then(r => r.json())
                .then(res => {
                    renderFleetRolesTable(res.agents || [], res.roles || []);
                })
                .catch(err => console.error("Failed fetching CEO org", err));
        }

        function submitBoardDirective() {
            const input = document.getElementById("ceo-directive-input");
            const wsSelect = document.getElementById("ceo-ws-select");
            const prioSelect = document.getElementById("ceo-priority-select");
            const btn = document.getElementById("btn-submit-directive");

            const text = (input ? input.value : "").trim();
            if (!text) {
                alert("Please enter a directive for the CEO to decompose.");
                return;
            }

            if (btn) btn.disabled = true;
            fetch("/api/ceo/order", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    directive: text,
                    workspace_id: wsSelect ? wsSelect.value : null,
                    priority: prioSelect ? prioSelect.value : "high"
                })
            })
            .then(r => r.json())
            .then(res => {
                if (btn) btn.disabled = false;
                if (res.success) {
                    if (input) input.value = "";
                    refreshCeoData();
                    triggerCeoPulse();
                } else {
                    alert("Directive Error: " + (res.error || "Failed to submit"));
                }
            })
            .catch(err => {
                if (btn) btn.disabled = false;
                alert("Request failed: " + err);
            });
        }

        function triggerCeoPulse() {
            const btn = document.getElementById("btn-ceo-pulse");
            if (btn) btn.classList.add("opacity-50");
            fetch("/api/ceo/heartbeat", { method: "POST" })
                .then(r => r.json())
                .then(() => {
                    if (btn) btn.classList.remove("opacity-50");
                    refreshCeoData();
                })
                .catch(err => {
                    if (btn) btn.classList.remove("opacity-50");
                    console.error("Pulse trigger error", err);
                });
        }

        function renderKanbanCards(tasks) {
            const cols = {
                todo: document.getElementById("kanban-col-todo"),
                in_progress: document.getElementById("kanban-col-in_progress"),
                in_review: document.getElementById("kanban-col-in_review"),
                blocked: document.getElementById("kanban-col-blocked"),
                done: document.getElementById("kanban-col-done")
            };

            const counts = { todo: 0, in_progress: 0, in_review: 0, blocked: 0, done: 0 };

            // Clear columns
            Object.values(cols).forEach(c => { if (c) c.innerHTML = ""; });

            tasks.forEach(t => {
                const status = t.status || "todo";
                counts[status] = (counts[status] || 0) + 1;
                const col = cols[status];
                if (!col) return;

                const roleBadgeColor = getRoleBadgeColor(t.role);
                const roleIcon = getRoleIcon(t.role);

                const card = document.createElement("div");
                card.className = "p-3 rounded-xl border space-y-2 text-xs transition hover:border-slate-500 shadow-sm relative overflow-hidden";
                card.style.backgroundColor = "var(--bg-input)";
                card.style.borderColor = "var(--border-base)";

                let blockedInfo = "";
                if (t.blocked_by && t.blocked_by.length > 0 && status !== "done") {
                    blockedInfo = `<div class="text-[10px] font-mono text-rose-400/90 flex items-center gap-1">
                        <i class="fa-solid fa-lock text-[9px]"></i> Blocked by: ${t.blocked_by.join(", ")}
                    </div>`;
                }

                let criteriaList = "";
                if (t.acceptance_criteria && t.acceptance_criteria.length > 0) {
                    criteriaList = `<div class="space-y-0.5 pt-1 border-t border-white/5">
                        ${t.acceptance_criteria.slice(0, 2).map(c => `<div class="text-[10px] text-slate-400 flex items-start gap-1">
                            <span class="text-slate-500">•</span> <span class="truncate">${c}</span>
                        </div>`).join("")}
                    </div>`;
                }

                let actions = "";
                if (status === "todo") {
                    actions = `<button onclick="taskAction('${t.id}', 'dispatch')" class="px-2 py-1 rounded bg-blue-500/20 text-blue-300 border border-blue-500/30 hover:bg-blue-500/30 font-bold text-[10px] flex items-center gap-1">
                        <i class="fa-solid fa-paper-plane text-[9px]"></i> Dispatch
                    </button>`;
                } else if (status === "in_progress") {
                    actions = `<button onclick="taskAction('${t.id}', 'approve')" class="px-2 py-1 rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 hover:bg-emerald-500/30 font-bold text-[10px] flex items-center gap-1">
                        <i class="fa-solid fa-check text-[9px]"></i> Mark Done
                    </button>`;
                } else if (status === "in_review") {
                    actions = `<div class="flex gap-1">
                        <button onclick="taskAction('${t.id}', 'approve')" class="px-2 py-1 rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 hover:bg-emerald-500/30 font-bold text-[10px]">Approve</button>
                        <button onclick="taskAction('${t.id}', 'reject')" class="px-2 py-1 rounded bg-amber-500/20 text-amber-300 border border-amber-500/30 hover:bg-amber-500/30 font-bold text-[10px]">Revision</button>
                    </div>`;
                } else if (status === "blocked") {
                    actions = `<button onclick="taskAction('${t.id}', 'dispatch')" class="px-2 py-1 rounded bg-rose-500/20 text-rose-300 border border-rose-500/30 hover:bg-rose-500/30 font-bold text-[10px] flex items-center gap-1">
                        <i class="fa-solid fa-rotate text-[9px]"></i> Retry Dispatch
                    </button>`;
                }

                card.innerHTML = `
                    <div class="flex items-center justify-between">
                        <span class="text-[10px] font-mono font-bold text-slate-400">${t.id}</span>
                        <span class="px-2 py-0.5 rounded text-[9px] font-bold uppercase tracking-wider" style="${roleBadgeColor}">
                            ${roleIcon} ${t.role}
                        </span>
                    </div>
                    <div class="font-semibold text-slate-100 text-xs leading-snug line-clamp-2">${t.title}</div>
                    <div class="flex items-center justify-between text-[11px] text-slate-400">
                        <span class="flex items-center gap-1"><i class="fa-solid fa-robot text-slate-500"></i> ${t.assigned_agent_id || 'Unassigned'}</span>
                        <span class="text-[10px] font-mono capitalize px-1.5 py-0.2 rounded bg-white/5">${t.priority}</span>
                    </div>
                    ${blockedInfo}
                    ${criteriaList}
                    ${actions ? `<div class="pt-1.5 flex justify-end border-t border-white/5">${actions}</div>` : ''}
                `;
                col.appendChild(card);
            });

            // Update column badges
            Object.keys(counts).forEach(s => {
                const badge = document.getElementById(`col-count-${s}`);
                if (badge) badge.innerText = counts[s];
            });
        }

        function getRoleIcon(role) {
            const map = { ceo: "👑", cto: "🏛️", frontend: "🎨", backend: "⚡", codex: "💻", hermes: "🧠", openclaw: "🌐", qa: "🛡️" };
            return map[role] || "🤖";
        }

        function getRoleBadgeColor(role) {
            const map = {
                ceo: "background: rgba(245,158,11,0.2); color: #fbbf24; border: 1px solid rgba(245,158,11,0.3);",
                cto: "background: rgba(59,130,246,0.2); color: #60a5fa; border: 1px solid rgba(59,130,246,0.3);",
                frontend: "background: rgba(236,72,153,0.2); color: #f472b6; border: 1px solid rgba(236,72,153,0.3);",
                backend: "background: rgba(16,185,129,0.2); color: #34d399; border: 1px solid rgba(16,185,129,0.3);",
                codex: "background: rgba(99,102,241,0.2); color: #818cf8; border: 1px solid rgba(99,102,241,0.3);",
                hermes: "background: rgba(168,85,247,0.2); color: #c084fc; border: 1px solid rgba(168,85,247,0.3);",
                openclaw: "background: rgba(14,165,233,0.2); color: #38bdf8; border: 1px solid rgba(14,165,233,0.3);",
                qa: "background: rgba(244,63,94,0.2); color: #fb7185; border: 1px solid rgba(244,63,94,0.3);"
            };
            return map[role] || "background: rgba(255,255,255,0.1); color: #cbd5e1;";
        }

        function taskAction(orderId, action) {
            fetch(`/api/ceo/tasks/${orderId}/action`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ action: action })
            })
            .then(r => r.json())
            .then(res => {
                if (res.success) {
                    refreshCeoData();
                } else {
                    alert("Task action failed: " + (res.error || "Unknown"));
                }
            })
            .catch(err => alert("Request error: " + err));
        }

        function renderFleetRolesTable(agentList, roleList) {
            const tbody = document.getElementById("ceo-fleet-roles-tbody");
            if (!tbody) return;

            const roles = roleList.length > 0 ? roleList : ceoRoleList;
            tbody.innerHTML = agentList.map(a => {
                const currentRole = a.role || "Frontend Specialist";
                const isOnline = a.status && a.status !== "offline";
                const statusColor = isOnline ? "text-emerald-400" : "text-slate-500";
                const statusDot = isOnline ? "bg-emerald-400" : "bg-slate-500";

                const roleOptions = roles.map(r => {
                    const isSelected = (r.id.toLowerCase() === currentRole.toLowerCase() ||
                                        r.name.toLowerCase() === currentRole.toLowerCase() ||
                                        currentRole.toLowerCase().includes(r.id.toLowerCase()));
                    return `<option value="${r.id}" ${isSelected ? 'selected' : ''}>${r.icon} ${r.name} (${r.title})</option>`;
                }).join("");

                return `
                    <tr class="hover:bg-white/5 transition">
                        <td class="py-3 px-3 font-semibold text-white flex items-center gap-2">
                            <span>${a.name}</span>
                            <span class="text-[10px] text-slate-500 font-mono">(${a.id})</span>
                        </td>
                        <td class="py-3 px-3 font-mono text-slate-400">CT ${a.vmid}</td>
                        <td class="py-3 px-3 font-mono text-slate-400">${a.ip}:${a.port} <span class="px-1.5 py-0.2 rounded bg-white/5 text-[10px] uppercase">${a.type || 'antigravity'}</span></td>
                        <td class="py-3 px-3">
                            <select onchange="updateAgentFleetRole('${a.id}', this.value)" class="px-2.5 py-1.5 rounded-lg border text-xs text-slate-200 focus:outline-none" style="background-color: var(--bg-card); border-color: var(--border-base);">
                                ${roleOptions}
                            </select>
                        </td>
                        <td class="py-3 px-3">
                            <span class="flex items-center gap-1.5 ${statusColor} font-mono font-medium">
                                <span class="w-2 h-2 rounded-full ${statusDot}"></span>
                                ${a.status || 'offline'}
                            </span>
                        </td>
                        <td class="py-3 px-3">
                            <button onclick="dispatchDirectTaskToAgent('${a.id}')" class="px-2.5 py-1 rounded-lg bg-blue-500/20 text-blue-300 border border-blue-500/30 hover:bg-blue-500/30 font-semibold text-[11px] flex items-center gap-1">
                                <i class="fa-solid fa-paper-plane text-[10px]"></i> Dispatch
                            </button>
                        </td>
                    </tr>
                `;
            }).join("");
        }

        function updateAgentFleetRole(agentId, roleId) {
            fetch("/api/ceo/role", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ agent_id: agentId, role: roleId })
            })
            .then(r => r.json())
            .then(res => {
                if (res.success) {
                    refreshCeoData();
                } else {
                    alert("Failed to update role: " + res.error);
                }
            })
            .catch(err => alert("Error updating role: " + err));
        }

        function dispatchDirectTaskToAgent(agentId) {
            closeCeoModal();
            selectView(agentId);
        }

        function renderHeartbeatLogs(pulseLogs, auditEvents) {
            const hbContainer = document.getElementById("ceo-heartbeat-log-container");
            if (hbContainer && pulseLogs && pulseLogs.length > 0) {
                hbContainer.innerHTML = pulseLogs.map(l => {
                    let color = "text-slate-300";
                    if (l.includes("[DISPATCH_OK]") || l.includes("[VERIFIED]")) color = "text-emerald-400";
                    else if (l.includes("[ESCALATION]") || l.includes("[DISPATCH_WARN]")) color = "text-rose-400";
                    else if (l.includes("[REVIEW_GATE]")) color = "text-purple-400";
                    else if (l.includes("[FLEET_CHECK]")) color = "text-blue-400";
                    return `<div class="${color}">${l}</div>`;
                }).join("");
                hbContainer.scrollTop = hbContainer.scrollHeight;
            }

            const auditContainer = document.getElementById("ceo-audit-log-container");
            if (auditContainer && auditEvents && auditEvents.length > 0) {
                auditContainer.innerHTML = auditEvents.slice(-25).reverse().map(e => {
                    return `<div class="flex items-start gap-2 border-b border-white/5 pb-1">
                        <span class="text-slate-500 text-[10px] flex-shrink-0">${e.time_iso?.split(' ')[1] || ''}</span>
                        <span class="px-1.5 py-0.2 rounded text-[9px] uppercase font-bold bg-white/5 text-amber-300 flex-shrink-0">${e.type}</span>
                        <span class="text-slate-300 flex-1 truncate">${e.message}</span>
                    </div>`;
                }).join("");
            }
        }

        function loadCeoCharterPrompt(promptName) {
            const container = document.getElementById("ceo-charter-text-container");
            const btns = {
                "AGENTS.md": document.getElementById("charter-btn-agents"),
                "SOUL.md": document.getElementById("charter-btn-soul"),
                "HEARTBEAT.md": document.getElementById("charter-btn-heartbeat")
            };

            Object.entries(btns).forEach(([k, b]) => {
                if (!b) return;
                if (k === promptName) {
                    b.style.background = "var(--bg-input)";
                    b.style.color = "var(--highlight-text)";
                } else {
                    b.style.background = "var(--bg-card)";
                    b.style.color = "#94a3b8";
                }
            });

            if (container) container.innerText = "Loading " + promptName + "...";

            fetch(`/api/ceo/prompts/${promptName}`)
                .then(r => r.json())
                .then(res => {
                    if (container) container.innerText = res.content || "Empty content.";
                })
                .catch(err => {
                    if (container) container.innerText = "Failed loading prompt: " + err;
                });
        }

        window.onload = init;
    </script>
</body>
</html>
"""

def get_agent_vm_type(agent):
    if not agent:
        return "lxc"
    return agent.get("vm_type") or ("qemu" if agent.get("type") in ["hermes", "openclaw"] else "lxc")

def pve_api_request(method, agent, path_suffix, **kwargs):
    """Executes a Proxmox API call, auto-resolving between QEMU VM and LXC endpoints."""
    vm_type = get_agent_vm_type(agent)
    vmid = agent.get("vmid") if isinstance(agent, dict) else agent
    if not vmid:
        return None
    
    headers = {"Authorization": PROXMOX_TOKEN}
    if "headers" in kwargs:
        headers.update(kwargs.pop("headers"))
    
    fn = getattr(requests, method.lower())
    clean_suffix = f"/{path_suffix.strip('/')}" if path_suffix.strip('/') else ""
    primary_url = f"{PROXMOX_API}/nodes/pve/{vm_type}/{vmid}{clean_suffix}"
    
    try:
        r = fn(primary_url, headers=headers, verify=False, **kwargs)
        if r.status_code == 200:
            return r
        if r.status_code in [400, 404, 500]:
            # Auto-fallback between QEMU VM and LXC container
            alt_type = "lxc" if vm_type == "qemu" else "qemu"
            alt_url = f"{PROXMOX_API}/nodes/pve/{alt_type}/{vmid}{clean_suffix}"
            r_alt = fn(alt_url, headers=headers, verify=False, **kwargs)
            if r_alt.status_code == 200:
                if isinstance(agent, dict):
                    agent["vm_type"] = alt_type
                return r_alt
        return r
    except Exception:
        return None

@app.route("/")
def index():
    load_agents_config()
    rendered = HTML_TEMPLATE.replace("__AGENTS_JSON_PLACEHOLDER__", json.dumps(AGENTS))
    return Response(rendered, mimetype="text/html")

@app.route("/api/status")
def get_all_status():
    results = {}
    for agent in AGENTS:
        power = "unknown"
        metrics = {}
        try:
            r = pve_api_request("get", agent, "status/current", timeout=1.5)
            if r and r.status_code == 200:
                d = r.json().get("data", {})
                power = d.get("status", "stopped")
                metrics = {
                    "cpu": d.get("cpu", 0),
                    "mem": d.get("mem", 0),
                    "maxmem": d.get("maxmem", 0),
                    "uptime": d.get("uptime", 0)
                }
        except Exception:
            pass

        agent_status = "offline"
        auth_status = False
        quota_summary = None
        if power == "running":
            try:
                r_agent = requests.get(f"http://{agent['ip']}:{agent['port']}/status", timeout=1.2)
                if r_agent.status_code == 200:
                    d = r_agent.json()
                    agent_status = d.get("status", "idle")
                    auth_status = d.get("authenticated", False)
                    quota_summary = d.get("quota_summary")
            except Exception:
                agent_status = "booting"

        results[agent["id"]] = {
            "power": power,
            "status": agent_status,
            "authenticated": auth_status,
            "metrics": metrics,
            "quota_summary": quota_summary,
            "vm_type": agent.get("vm_type") or get_agent_vm_type(agent)
        }
    return jsonify(results)

@app.route("/api/power", methods=["POST"])
def power_control():
    data = request.get_json(force=True, silent=True) or {}
    agent_id = data.get("agent_id")
    action = data.get("action")
    agent = next((a for a in AGENTS if a["id"] == agent_id), None)
    if not agent:
        return jsonify({"error": "Invalid agent"}), 400
    
    try:
        r = pve_api_request("post", agent, f"status/{action}", timeout=5)
        if r and r.status_code < 400:
            target_type = (agent.get("vm_type") or get_agent_vm_type(agent)).upper()
            return jsonify({"success": True, "message": f"{agent['name']} ({target_type}) {action} initiated"})
        err_msg = r.text if r else "Proxmox API communication failed"
        return jsonify({"error": f"Failed to {action}: {err_msg}"}), (r.status_code if r else 500)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/logs")
def get_agent_logs():
    agent_id = request.args.get("agent_id", "agent-1")
    agent = next((a for a in AGENTS if a["id"] == agent_id), AGENTS[0])
    try:
        r = requests.get(f"http://{agent['ip']}:{agent['port']}/logs", timeout=2)
        return jsonify(r.json())
    except Exception as e:
        return jsonify({"logs": [{"type": "error", "text": f"Agent {agent['name']} is currently offline or stopped."}]})

@app.route("/api/agent/screenshot", methods=["GET"])
def grab_agent_screenshot():
    agent_id = request.args.get("agent_id", "agent-1")
    agent = next((a for a in AGENTS if a["id"] == agent_id), None)
    if not agent:
        return jsonify({"error": "Agent not found"}), 404
    try:
        r = requests.get(f"http://{agent['ip']}:{agent['port']}/screenshot", timeout=6)
        if r.status_code == 200:
            return r.content, 200, {"Content-Type": "image/png"}
        return jsonify({"error": "Screenshot failed on agent"}), r.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def get_single_agent_status(agent_id):
    agent = next((a for a in AGENTS if a["id"] == agent_id), None)
    if not agent:
        return {"running": False, "busy": False, "authenticated": False}
    try:
        r_agent = requests.get(f"http://{agent['ip']}:{agent['port']}/status", timeout=1.2)
        if r_agent.status_code == 200:
            d = r_agent.json()
            return {
                "running": True,
                "busy": d.get("status") == "busy",
                "status": d.get("status", "idle"),
                "authenticated": d.get("authenticated", False)
            }
    except Exception:
        pass
    return {"running": False, "busy": False, "status": "offline", "authenticated": False}

def dispatch_task_internal(target="agent-1", prompt="", images=None, ws_id=None, auto_deploy=True):
    images = images or []
    targets = [a for a in AGENTS if (target == "broadcast" or a["id"] == target)]
    
    # Auto-deploy workspace to target agents if specified and not yet synced
    ws = None
    if ws_id:
        if ws_id not in WORKSPACES:
            load_workspaces()
        ws = WORKSPACES.get(ws_id)
        if ws and auto_deploy:
            try:
                unsynced = [a for a in targets if a["id"] not in ws.get("synced_agents", [])]
                if unsynced:
                    deploy_workspace_to_targets(ws_id, target=[a["id"] for a in unsynced])
            except Exception as de:
                print(f"Auto-deploy workspace warning: {de}")

    # Prefix workspace context to prompt if workspace is active
    effective_prompt = prompt
    if ws:
        ws_name = ws.get("name", "Project")
        lang = ws.get("primary_language", "Codebase")
        files_cnt = ws.get("file_count", 0)
        ws_context = f"[Active Project Workspace]: /home/ubuntu/workspace (Project: {ws_name}, Stack: {lang}, {files_cnt} files)\n"
        if "[Active Project Workspace]" not in prompt:
            effective_prompt = f"{ws_context}\n{prompt}" if prompt else f"{ws_context}\nTask: Inspect the active project workspace and report findings."

    responses = []
    for a in targets:
        try:
            payload = {"prompt": effective_prompt, "images": images}
            r = requests.post(f"http://{a['ip']}:{a['port']}/dispatch", json=payload, timeout=8)
            responses.append({a["id"]: r.json()})
        except Exception as e:
            responses.append({a["id"]: {"error": str(e)}})
            
    return {"success": True, "message": "Task dispatched", "responses": responses, "workspace_id": ws_id}

@app.route("/api/dispatch", methods=["POST"])
def dispatch_task():
    data = request.get_json(force=True, silent=True) or {}
    res = dispatch_task_internal(
        target=data.get("target", "agent-1"),
        prompt=data.get("prompt", ""),
        images=data.get("images", []),
        ws_id=data.get("workspace_id"),
        auto_deploy=bool(data.get("auto_deploy", True))
    )
    return jsonify(res)

@app.route("/api/auth", methods=["POST"])
def save_auth():
    data = request.get_json(force=True, silent=True) or {}
    target = data.get("target", "agent-1")
    token_json = data.get("token_json")
    
    agent = next((a for a in AGENTS if a["id"] == target), None)
    if not agent:
        return jsonify({"error": "Invalid target agent"}), 400
    try:
        r = requests.post(f"http://{agent['ip']}:{agent['port']}/auth", json={"token_json": token_json}, timeout=3)
        return jsonify(r.json())
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/restart_desktop", methods=["POST"])
def restart_desktop():
    agent_id = request.args.get("agent_id", "agent-1")
    agent = next((a for a in AGENTS if a["id"] == agent_id), None)
    if not agent:
        return jsonify({"error": "Invalid agent"}), 400
    try:
        r = requests.post(f"http://{agent['ip']}:{agent['port']}/restart_desktop", timeout=3)
        return jsonify(r.json())
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ------------------------------------------------------------------
# SKILLS HUB API ENDPOINTS
# ------------------------------------------------------------------
@app.route("/api/skills/library", methods=["GET"])
def get_skills_library_route():
    force_refresh = request.args.get("refresh") in ["1", "true", "yes"]
    skills = get_library_skills(force_refresh=force_refresh)
    cats = ["All", "Convex Backend", "Clerk Auth", "Cloud & Data Pipelines", "Testing & DevTools", "Core & Workflows"]
    return jsonify({"skills": skills, "categories": cats, "count": len(skills), "lib_dir": SKILLS_LIB_DIR})

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
    data = request.get_json(force=True, silent=True) or {}
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
    data = request.get_json(force=True, silent=True) or {}
    target = data.get("target", "agent-1")
    targets = [a for a in AGENTS if (target == "broadcast" or a["id"] == target)]
    if not targets:
        return jsonify({"error": "No valid target agents"}), 400

    archive_bytes = ensure_skills_archive_bytes()
    if not archive_bytes:
        return jsonify({"error": "Skills library archive could not be generated"}), 500

    archive_b64 = base64.b64encode(archive_bytes).decode("utf-8")

    results = {}
    for a in targets:
        try:
            r = requests.post(f"http://{a['ip']}:{a['port']}/skills/install_archive", json={"archive": archive_b64}, timeout=15)
            results[a["id"]] = r.json()
        except Exception as e:
            results[a["id"]] = {"error": str(e)}

    return jsonify({"success": True, "message": "Synchronized entire skills library", "results": results})

@app.route("/api/skills/download", methods=["GET"])
def download_skill_route():
    skill_id = request.args.get("skill_id", "").strip()
    if not skill_id:
        return jsonify({"error": "Missing skill_id parameter"}), 400
    
    skill_dir = os.path.join(SKILLS_LIB_DIR, skill_id)
    if not os.path.exists(skill_dir) or not os.path.isdir(skill_dir):
        return jsonify({"error": f"Skill '{skill_id}' not found in library"}), 404
    
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(skill_dir):
            for fn in files:
                fp = os.path.join(root, fn)
                rel = os.path.relpath(fp, skill_dir)
                zf.write(fp, arcname=rel)
    buf.seek(0)
    return send_file(
        buf,
        mimetype="application/zip",
        as_attachment=True,
        download_name=f"{skill_id}.zip"
    )

@app.route("/api/skills/download_all", methods=["GET"])
def download_all_skills_route():
    archive_bytes = ensure_skills_archive_bytes()
    if not archive_bytes:
        return jsonify({"error": "Skills archive unavailable"}), 500
    buf = io.BytesIO(archive_bytes)
    return send_file(
        buf,
        mimetype="application/gzip",
        as_attachment=True,
        download_name="cockpit-skills-library.tar.gz"
    )

@app.route("/api/skills/download_from_agent", methods=["GET"])
def download_skill_from_agent_route():
    agent_id = request.args.get("agent_id", "agent-1")
    skill_name = request.args.get("skill_name", "").strip()
    if not skill_name:
        return jsonify({"error": "Missing skill_name parameter"}), 400
    
    agent = next((a for a in AGENTS if a["id"] == agent_id), None)
    if not agent:
        return jsonify({"error": f"Agent '{agent_id}' not found"}), 404
    
    try:
        r = requests.get(f"http://{agent['ip']}:{agent['port']}/skills/{skill_name}/export", timeout=6)
        if r.status_code != 200:
            return jsonify({"error": f"Agent returned status {r.status_code}: {r.text}"}), r.status_code
        data = r.json()
        files = data.get("files", {})
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for rel_path, b64_content in files.items():
                try:
                    raw = base64.b64decode(b64_content)
                    zf.writestr(rel_path, raw)
                except Exception:
                    zf.writestr(rel_path, b64_content)
        buf.seek(0)
        return send_file(
            buf,
            mimetype="application/zip",
            as_attachment=True,
            download_name=f"{skill_name}.zip"
        )
    except Exception as e:
        return jsonify({"error": f"Failed to export skill from agent: {str(e)}"}), 500

@app.route("/api/skills/upload", methods=["POST"])
def upload_skill_to_library():
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded. Form field 'file' required."}), 400
    
    f = request.files["file"]
    filename = (f.filename or "").strip()
    if not filename:
        return jsonify({"error": "No file selected."}), 400

    os.makedirs(SKILLS_LIB_DIR, exist_ok=True)
    imported_names = []

    try:
        lower_name = filename.lower()
        if lower_name.endswith(".zip"):
            stream = io.BytesIO(f.read())
            with zipfile.ZipFile(stream, "r") as zf:
                slug = os.path.splitext(filename)[0].lower().replace(" ", "-")
                target_folder = os.path.join(SKILLS_LIB_DIR, slug)
                os.makedirs(target_folder, exist_ok=True)
                zf.extractall(target_folder)
                imported_names.append(slug)

        elif lower_name.endswith(".tar.gz") or lower_name.endswith(".tgz"):
            stream = io.BytesIO(f.read())
            with tarfile.open(fileobj=stream, mode="r:gz") as tf:
                slug = filename.split(".")[0].lower().replace(" ", "-")
                target_folder = os.path.join(SKILLS_LIB_DIR, slug)
                os.makedirs(target_folder, exist_ok=True)
                tf.extractall(target_folder)
                imported_names.append(slug)

        elif lower_name.endswith(".md"):
            content = f.read().decode("utf-8", errors="ignore")
            slug = os.path.splitext(filename)[0].lower().replace(" ", "-")
            for line in content.splitlines()[:25]:
                if line.strip().startswith("name:"):
                    slug = line.split(":", 1)[1].strip().strip("\"'").lower().replace(" ", "-")
                    break
            target_folder = os.path.join(SKILLS_LIB_DIR, slug)
            os.makedirs(target_folder, exist_ok=True)
            with open(os.path.join(target_folder, "SKILL.md"), "w", encoding="utf-8") as out:
                out.write(content)
            imported_names.append(slug)
        else:
            return jsonify({"error": "Unsupported file format. Please upload a .zip, .tar.gz, or .md file."}), 400

        # Invalidate cache and update archive
        get_library_skills(force_refresh=True)
        if os.path.exists(SKILLS_ARCHIVE_PATH):
            try:
                os.remove(SKILLS_ARCHIVE_PATH)
            except Exception:
                pass
        ensure_skills_archive_bytes()

        return jsonify({
            "success": True,
            "message": f"Successfully imported '{imported_names[0]}' into Cockpit library!",
            "imported": imported_names,
            "skills": get_library_skills()
        })
    except Exception as e:
        return jsonify({"error": f"Import failed: {str(e)}"}), 500

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

# ------------------------------------------------------------------
# AGENT INSTALLER & PACKAGE REPOSITORY
# ------------------------------------------------------------------
# ------------------------------------------------------------------
# AGENT INSTALLER & PACKAGE REPOSITORY
# ------------------------------------------------------------------
@app.route("/install.sh", methods=["GET"])
def get_installer_script():
    installer_candidates = [
        "/usr/local/share/cockpit/install.sh",
        os.path.join(os.path.dirname(SCRIPT_DIR), "agent", "install.sh"),
        os.path.join(SCRIPT_DIR, "agent", "install.sh"),
        "/usr/local/share/cockpit/install_antigravity_agent.sh",
        os.path.join(os.path.dirname(SCRIPT_DIR), "agent", "install_antigravity_agent.sh")
    ]
    installer_path = None
    for c in installer_candidates:
        if os.path.exists(c):
            installer_path = c
            break
    if not installer_path:
        return "#!/bin/bash\necho 'Error: installer script not found on Cockpit server.'\nexit 1\n", 404, {"Content-Type": "text/plain; charset=utf-8"}
    
    with open(installer_path, "r", encoding="utf-8") as f:
        script = f.read()
    host_header = request.host
    script = script.replace('COCKPIT_HOST="${COCKPIT_HOST:-http://192.168.178.168:3000}"', f'COCKPIT_HOST="${{COCKPIT_HOST:-http://{host_header}}}"')
    script = script.replace('COCKPIT_HOST="${COCKPIT_HOST:-192.168.178.168:3000}"', f'COCKPIT_HOST="${{COCKPIT_HOST:-http://{host_header}}}"')
    return script, 200, {"Content-Type": "text/plain; charset=utf-8"}

@app.route("/packages/installers/<filename>", methods=["GET"])
def get_installer_file(filename):
    safe_filename = os.path.basename(filename)
    candidates = [
        os.path.join("/usr/local/share/cockpit/installers", safe_filename),
        os.path.join(os.path.dirname(SCRIPT_DIR), "agent", "installers", safe_filename),
        os.path.join(SCRIPT_DIR, "agent", "installers", safe_filename)
    ]
    for c in candidates:
        if os.path.exists(c):
            with open(c, "r", encoding="utf-8") as f:
                script = f.read()
            host_header = request.host
            script = script.replace('COCKPIT_HOST="${COCKPIT_HOST:-http://192.168.178.168:3000}"', f'COCKPIT_HOST="${{COCKPIT_HOST:-http://{host_header}}}"')
            return script, 200, {"Content-Type": "text/plain; charset=utf-8"}
    return f"Installer {safe_filename} not found", 404

@app.route("/packages/scripts/<filename>", methods=["GET"])
def get_script_file(filename):
    safe_filename = os.path.basename(filename)
    candidates = [
        os.path.join("/usr/local/share/cockpit/scripts", safe_filename),
        os.path.join(os.path.dirname(SCRIPT_DIR), "scripts", safe_filename),
        os.path.join(SCRIPT_DIR, "scripts", safe_filename)
    ]
    for c in candidates:
        if os.path.exists(c):
            with open(c, "r", encoding="utf-8") as f:
                script = f.read()
            host_header = request.host
            script = script.replace('COCKPIT_HOST="${COCKPIT_HOST:-http://192.168.178.168:3000}"', f'COCKPIT_HOST="${{COCKPIT_HOST:-http://{host_header}}}"')
            return script, 200, {"Content-Type": "text/plain; charset=utf-8"}
    return f"Script {safe_filename} not found", 404

@app.route("/packages/<filename>", methods=["GET"])
def get_package_file(filename):
    if filename.startswith("install_") and filename.endswith(".sh"):
        return get_installer_file(filename)
    if filename == "common.sh":
        return get_installer_file("common.sh")
    if filename.endswith(".sh"):
        return get_script_file(filename)

    if filename == "agent_bridge.py":
        agent_bridge_candidates = [
            "/usr/local/bin/agent_bridge.py",
            os.path.join(os.path.dirname(SCRIPT_DIR), "agent", "agent_bridge.py"),
            os.path.join(SCRIPT_DIR, "agent", "agent_bridge.py")
        ]
        for c in agent_bridge_candidates:
            if os.path.exists(c):
                return send_file(c, mimetype="text/x-python")
    
    if filename == "cockpit-skills-library.tar.gz":
        archive_bytes = ensure_skills_archive_bytes()
        if archive_bytes:
            return send_file(io.BytesIO(archive_bytes), mimetype="application/gzip", as_attachment=True, download_name=filename)
        
    allowed = ["antigravity-app.tar.gz", "cockpit-skills-library.tar.gz"]
    if filename in allowed:
        for p in ["/usr/local/share/cockpit", SCRIPT_DIR]:
            fp = os.path.join(p, filename)
            if os.path.exists(fp):
                return send_file(fp, mimetype="application/gzip")
    return "File not found", 404


# ------------------------------------------------------------------
# AGENTS MANAGEMENT API (RENAME & ADD)
# ------------------------------------------------------------------
@app.route("/api/agents", methods=["GET"])
def get_agents_list():
    load_agents_config()
    return jsonify({"agents": AGENTS})

@app.route("/api/agents/<agent_id>/quota", methods=["GET", "POST"])
def get_agent_quota_route(agent_id):
    load_agents_config()
    agent = next((a for a in AGENTS if a["id"] == agent_id), None)
    if not agent:
        return jsonify({"error": "Agent not found"}), 404
    
    force = request.args.get("force_refresh", "false").lower() in ["true", "1", "yes"]
    try:
        agent_ip = agent.get("ip")
        agent_port = agent.get("port", 8000)
        url = f"http://{agent_ip}:{agent_port}/quota"
        if force:
            url += "?force_refresh=true"
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            return jsonify(r.json())
        return jsonify({"error": f"Agent bridge returned status {r.status_code}"}), r.status_code
    except Exception as e:
        return jsonify({"error": f"Failed to connect to agent bridge: {str(e)}"}), 502

@app.route("/api/agents/rename", methods=["POST"])
def rename_agent_route():
    data = request.get_json(force=True, silent=True) or {}
    agent_id = data.get("agent_id") or data.get("id")
    new_name = (data.get("name") or "").strip()
    new_role = (data.get("role") or "").strip()
    new_type = (data.get("type") or data.get("engine") or "").strip().lower()
    new_virt = (data.get("vm_type") or "").strip().lower()
    
    agent = next((a for a in AGENTS if a["id"] == agent_id), None)
    if not agent:
        return jsonify({"error": "Agent not found"}), 404
    if new_name:
        agent["name"] = new_name
    if new_role:
        agent["role"] = new_role
    if new_type:
        agent["type"] = new_type
        if not new_virt and "vm_type" not in agent:
            agent["vm_type"] = "qemu" if new_type in ["hermes", "openclaw"] else "lxc"
    if new_virt in ["qemu", "lxc"]:
        agent["vm_type"] = new_virt
        
    save_agents_config()
    
    # Optionally update Proxmox VM / LXC description
    try:
        eng_label = agent.get("type", "antigravity").title()
        pve_api_request("put", agent, "config", json={"description": f"{eng_label} Agent: {agent['name']} ({agent['role']})"}, timeout=3)
    except Exception:
        pass
    
    # Push engine type change to the running container/VM
    if new_type:
        try:
            agent_port = agent.get("port", 8000)
            requests.post(
                f"http://{agent['ip']}:{agent_port}/configure_engine",
                json={"engine_type": new_type, "restart_desktop": True},
                timeout=5
            )
        except Exception:
            pass  # Node may be offline — engine will apply on next boot via marker file
    
    return jsonify({"success": True, "agent": agent})

@app.route("/api/agents/remove", methods=["POST", "DELETE"])
def remove_agent_route():
    data = request.get_json(force=True, silent=True) or {}
    agent_id = data.get("agent_id") or data.get("id") or request.args.get("agent_id")
    purge_pve = bool(data.get("purge_pve", False))
    
    agent = next((a for a in AGENTS if a["id"] == agent_id), None)
    if not agent:
        return jsonify({"error": "Agent not found"}), 404
    
    # 1. Stop container/VM if running
    vmid = agent.get("vmid")
    if vmid:
        try:
            pve_api_request("post", agent, "status/stop", timeout=5)
        except Exception:
            pass

        # 2. If purge_pve is explicitly requested
        if purge_pve:
            try:
                time.sleep(1)
                pve_api_request("delete", agent, "", timeout=8)
            except Exception as pe:
                print(f"Failed to purge node {vmid} on PVE:", pe)
    
    # 3. Remove from AGENTS list and save
    AGENTS.remove(agent)
    save_agents_config()
    
    return jsonify({"success": True, "removed_id": agent_id, "agents": AGENTS})

@app.route("/api/agents/add", methods=["POST"])
def add_agent_route():
    data = request.get_json(force=True, silent=True) or {}
    name = (data.get("name") or "").strip()
    role = (data.get("role") or "Specialist").strip()
    agent_type = (data.get("type") or data.get("engine") or "antigravity").strip().lower()
    vm_type = (data.get("vm_type") or "").strip().lower()
    if vm_type not in ["qemu", "lxc"]:
        vm_type = "qemu" if agent_type in ["hermes", "openclaw"] else "lxc"
        
    ip = (data.get("ip") or "").strip()
    vmid = int(data.get("vmid") or (150 + len(AGENTS) + 1))
    port = int(data.get("port") or 8000)
    vnc_port = int(data.get("vnc_port") or 6080)
    
    if not name or not ip:
        return jsonify({"error": "Name and IP required"}), 400
    
    # Prevent duplicate registrations (same VMID or IP)
    existing_vmid = next((a for a in AGENTS if a.get("vmid") == vmid), None)
    if existing_vmid:
        return jsonify({"success": True, "agent": existing_vmid, "agents": AGENTS, "note": "Agent with this VMID already registered"})
    
    existing_ip = next((a for a in AGENTS if a.get("ip") == ip), None)
    if existing_ip:
        return jsonify({"success": True, "agent": existing_ip, "agents": AGENTS, "note": "Agent with this IP already registered"})
    
    # Generate unique agent ID (avoid collisions with existing IDs)
    existing_ids = {a["id"] for a in AGENTS}
    counter = len(AGENTS) + 1
    new_id = f"agent-{counter}"
    while new_id in existing_ids:
        counter += 1
        new_id = f"agent-{counter}"
    
    new_agent = {
        "id": new_id,
        "vmid": vmid,
        "name": name,
        "type": agent_type,
        "vm_type": vm_type,
        "role": role,
        "ip": ip,
        "port": port,
        "vnc_port": vnc_port
    }
    AGENTS.append(new_agent)
    save_agents_config()
    return jsonify({"success": True, "agent": new_agent, "agents": AGENTS})


# ------------------------------------------------------------------
# WORKSPACES MANAGEMENT API
# ------------------------------------------------------------------
@app.route("/api/workspaces", methods=["GET"])
def get_workspaces_list():
    load_workspaces()
    return jsonify({"workspaces": list(WORKSPACES.values())})

@app.route("/api/workspaces/upload", methods=["POST"])
def upload_workspace():
    ws_name = ""
    ws_desc = ""
    target_agent = ""
    file_bytes = None
    filename = ""

    if request.is_json:
        data = request.get_json(force=True, silent=True) or {}
        ws_name = (data.get("name") or "").strip()
        ws_desc = (data.get("description") or "").strip()
        target_agent = data.get("target_agent", "")
        filename = data.get("filename", "project.zip")
        b64_data = data.get("archive_b64") or data.get("data")
        if b64_data:
            if "," in b64_data:
                b64_data = b64_data.split(",", 1)[1]
            try:
                file_bytes = base64.b64decode(b64_data)
            except Exception as e:
                return jsonify({"error": f"Base64 decode error: {e}"}), 400
    else:
        ws_name = (request.form.get("name") or "").strip()
        ws_desc = (request.form.get("description") or "").strip()
        target_agent = request.form.get("target_agent", "")
        if "file" in request.files:
            file_obj = request.files["file"]
            filename = file_obj.filename or "project.zip"
            file_bytes = file_obj.read()

    if not file_bytes:
        return jsonify({"error": "No file content or archive provided"}), 400

    if not ws_name:
        clean_name = os.path.splitext(filename)[0]
        if clean_name.endswith(".tar"):
            clean_name = os.path.splitext(clean_name)[0]
        ws_name = re.sub(r'[^a-zA-Z0-9_\-]', '_', clean_name).strip("_") or f"project_{int(time.time())}"

    slug_id = f"ws_{int(time.time())}_{re.sub(r'[^a-zA-Z0-9]', '', ws_name.lower())[:15]}"
    dest_dir = os.path.join(WORKSPACES_DIR, slug_id)
    os.makedirs(dest_dir, exist_ok=True)

    try:
        if filename.endswith(".zip") or file_bytes[:4] == b"PK\x03\x04":
            with zipfile.ZipFile(io.BytesIO(file_bytes)) as zf:
                zf.extractall(dest_dir)
        elif filename.endswith((".tar.gz", ".tgz")) or file_bytes[:2] == b"\x1f\x8b":
            with tarfile.open(fileobj=io.BytesIO(file_bytes), mode="r:gz") as tf:
                tf.extractall(dest_dir)
        elif filename.endswith(".tar"):
            with tarfile.open(fileobj=io.BytesIO(file_bytes), mode="r:") as tf:
                tf.extractall(dest_dir)
        else:
            try:
                with zipfile.ZipFile(io.BytesIO(file_bytes)) as zf:
                    zf.extractall(dest_dir)
            except Exception:
                with tarfile.open(fileobj=io.BytesIO(file_bytes), mode="r:*") as tf:
                    tf.extractall(dest_dir)

        # Flatten single root directory if present (e.g. repo-main/ -> root)
        extracted_items = [i for i in os.listdir(dest_dir) if not i.startswith(".")]
        if len(extracted_items) == 1:
            single_inner = os.path.join(dest_dir, extracted_items[0])
            if os.path.isdir(single_inner):
                for sub in os.listdir(single_inner):
                    shutil.move(os.path.join(single_inner, sub), dest_dir)
                os.rmdir(single_inner)

        stats = scan_workspace_stats(dest_dir)
        ws_obj = {
            "id": slug_id,
            "name": ws_name,
            "description": ws_desc or f"Imported from {filename}",
            "source": "upload",
            "filename": filename,
            "created_at": time.time(),
            "updated_at": time.time(),
            "file_count": stats["file_count"],
            "dir_count": stats["dir_count"],
            "size_bytes": stats["size_bytes"],
            "primary_language": stats["primary_language"],
            "synced_agents": []
        }
        WORKSPACES[slug_id] = ws_obj
        save_workspaces()

        deploy_res = None
        if target_agent and target_agent != "none":
            deploy_res = deploy_workspace_to_targets(slug_id, target_agent)

        return jsonify({
            "success": True,
            "workspace": ws_obj,
            "deployed": deploy_res
        })
    except Exception as e:
        shutil.rmtree(dest_dir, ignore_errors=True)
        return jsonify({"error": f"Failed to extract project archive: {e}"}), 500

@app.route("/api/workspaces/git_clone", methods=["POST"])
def git_clone_workspace():
    data = request.get_json(force=True, silent=True) or {}
    raw_repo_url = (data.get("repo_url") or "").strip()
    branch = (data.get("branch") or "").strip()
    ws_name = (data.get("name") or "").strip()
    ws_desc = (data.get("description") or "").strip()
    target_agent = data.get("target_agent", "")
    token = (data.get("token") or "").strip()

    if not raw_repo_url:
        return jsonify({"error": "Repository URL or 'owner/repo' shorthand is required"}), 400

    clone_url, safe_url, auto_branch = normalize_git_url(raw_repo_url, token)
    effective_branch = branch or auto_branch or ""

    if not ws_name:
        clean = safe_url.rstrip("/").split("/")[-1]
        if clean.endswith(".git"):
            clean = clean[:-4]
        ws_name = re.sub(r'[^a-zA-Z0-9_\-]', '_', clean) or f"repo_{int(time.time())}"

    slug_id = f"ws_{int(time.time())}_{re.sub(r'[^a-zA-Z0-9]', '', ws_name.lower())[:15]}"
    dest_dir = os.path.join(WORKSPACES_DIR, slug_id)

    cmd = ["git", "clone", "--depth", "1"]
    if effective_branch:
        cmd.extend(["--branch", effective_branch])
    cmd.extend([clone_url, dest_dir])

    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
        if res.returncode != 0:
            shutil.rmtree(dest_dir, ignore_errors=True)
            err_msg = res.stderr or res.stdout
            if token:
                err_msg = err_msg.replace(token, "******")
            return jsonify({"error": f"Git clone failed: {err_msg}"}), 400

        git_branch = effective_branch or "main"
        git_commit = ""
        git_commit_full = ""
        git_commit_msg = ""
        git_commit_author = ""
        git_commit_date = ""

        try:
            b_res = subprocess.run(["git", "-C", dest_dir, "rev-parse", "--abbrev-ref", "HEAD"], capture_output=True, text=True, timeout=5)
            if b_res.returncode == 0 and b_res.stdout.strip():
                git_branch = b_res.stdout.strip()
        except Exception:
            pass

        try:
            log_res = subprocess.run(["git", "-C", dest_dir, "log", "-1", "--format=%h|%H|%s|%an|%ci"], capture_output=True, text=True, timeout=5)
            if log_res.returncode == 0 and log_res.stdout.strip():
                parts = log_res.stdout.strip().split("|")
                if len(parts) >= 5:
                    git_commit, git_commit_full, git_commit_msg, git_commit_author, git_commit_date = parts[0], parts[1], parts[2], parts[3], parts[4]
        except Exception:
            pass

        stats = scan_workspace_stats(dest_dir)
        ws_obj = {
            "id": slug_id,
            "name": ws_name,
            "description": ws_desc or f"Cloned from {safe_url} ({git_branch})",
            "source": "git",
            "git_url": safe_url,
            "git_branch": git_branch,
            "git_commit": git_commit,
            "git_commit_full": git_commit_full,
            "git_commit_msg": git_commit_msg,
            "git_commit_author": git_commit_author,
            "git_commit_date": git_commit_date,
            "created_at": time.time(),
            "updated_at": time.time(),
            "file_count": stats["file_count"],
            "dir_count": stats["dir_count"],
            "size_bytes": stats["size_bytes"],
            "primary_language": stats["primary_language"],
            "synced_agents": []
        }
        WORKSPACES[slug_id] = ws_obj
        save_workspaces()

        deploy_res = None
        if target_agent and target_agent != "none":
            deploy_res = deploy_workspace_to_targets(slug_id, target_agent)

        return jsonify({"success": True, "workspace": ws_obj, "deployed": deploy_res})
    except subprocess.TimeoutExpired:
        shutil.rmtree(dest_dir, ignore_errors=True)
        return jsonify({"error": "Git clone timed out after 90s"}), 504
    except Exception as e:
        shutil.rmtree(dest_dir, ignore_errors=True)
        err_msg = str(e)
        if token:
            err_msg = err_msg.replace(token, "******")
        return jsonify({"error": err_msg}), 500

@app.route("/api/workspaces/<ws_id>/git_pull", methods=["POST"])
def git_pull_workspace(ws_id):
    if ws_id not in WORKSPACES:
        load_workspaces()
    ws = WORKSPACES.get(ws_id)
    if not ws:
        return jsonify({"error": "Workspace not found"}), 404

    dest_dir = os.path.join(WORKSPACES_DIR, ws_id)
    if not os.path.exists(dest_dir) or not os.path.exists(os.path.join(dest_dir, ".git")):
        return jsonify({"error": "Workspace is not a valid Git repository"}), 400

    data = request.get_json(force=True, silent=True) or {}
    auto_redeploy = bool(data.get("auto_redeploy", True))

    try:
        res = subprocess.run(["git", "-C", dest_dir, "pull"], capture_output=True, text=True, timeout=60)
        if res.returncode != 0:
            return jsonify({"error": f"Git pull failed: {res.stderr or res.stdout}"}), 400

        try:
            log_res = subprocess.run(["git", "-C", dest_dir, "log", "-1", "--format=%h|%H|%s|%an|%ci"], capture_output=True, text=True, timeout=5)
            if log_res.returncode == 0 and log_res.stdout.strip():
                parts = log_res.stdout.strip().split("|")
                if len(parts) >= 5:
                    ws["git_commit"] = parts[0]
                    ws["git_commit_full"] = parts[1]
                    ws["git_commit_msg"] = parts[2]
                    ws["git_commit_author"] = parts[3]
                    ws["git_commit_date"] = parts[4]
        except Exception:
            pass

        stats = scan_workspace_stats(dest_dir)
        ws["file_count"] = stats["file_count"]
        ws["dir_count"] = stats["dir_count"]
        ws["size_bytes"] = stats["size_bytes"]
        ws["primary_language"] = stats["primary_language"]
        ws["updated_at"] = time.time()
        save_workspaces()

        redeploy_res = None
        if auto_redeploy and ws.get("synced_agents"):
            try:
                redeploy_res = deploy_workspace_to_targets(ws_id, target=ws["synced_agents"])
            except Exception as de:
                redeploy_res = {"warning": f"Could not auto-redeploy to agents: {de}"}

        return jsonify({
            "success": True,
            "message": "Git repository successfully updated",
            "git_output": res.stdout.strip(),
            "workspace": ws,
            "redeploy": redeploy_res
        })
    except subprocess.TimeoutExpired:
        return jsonify({"error": "Git pull timed out after 60s"}), 504
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/workspaces/<ws_id>/git_status", methods=["GET"])
def git_status_workspace(ws_id):
    if ws_id not in WORKSPACES:
        load_workspaces()
    ws = WORKSPACES.get(ws_id)
    if not ws:
        return jsonify({"error": "Workspace not found"}), 404

    dest_dir = os.path.join(WORKSPACES_DIR, ws_id)
    if not os.path.exists(dest_dir) or not os.path.exists(os.path.join(dest_dir, ".git")):
        return jsonify({"is_git": False})

    status_out = ""
    try:
        s_res = subprocess.run(["git", "-C", dest_dir, "status", "-s"], capture_output=True, text=True, timeout=5)
        status_out = s_res.stdout.strip()
    except Exception:
        pass

    return jsonify({
        "is_git": True,
        "branch": ws.get("git_branch", "main"),
        "commit": ws.get("git_commit", ""),
        "commit_msg": ws.get("git_commit_msg", ""),
        "commit_author": ws.get("git_commit_author", ""),
        "git_url": ws.get("git_url", ""),
        "has_changes": bool(status_out),
        "status_summary": status_out
    })

@app.route("/api/workspaces/create_template", methods=["POST"])
def create_workspace_template():
    data = request.get_json(force=True, silent=True) or {}
    template_type = data.get("template", "blank")
    ws_name = (data.get("name") or "").strip() or f"{template_type}_project"
    ws_desc = (data.get("description") or "").strip()

    slug_id = f"ws_{int(time.time())}_{re.sub(r'[^a-zA-Z0-9]', '', ws_name.lower())[:15]}"
    dest_dir = os.path.join(WORKSPACES_DIR, slug_id)
    os.makedirs(dest_dir, exist_ok=True)

    try:
        if template_type == "react":
            os.makedirs(os.path.join(dest_dir, "src"), exist_ok=True)
            with open(os.path.join(dest_dir, "package.json"), "w", encoding="utf-8") as f:
                json.dump({
                    "name": ws_name.lower(),
                    "private": True,
                    "version": "0.1.0",
                    "type": "module",
                    "scripts": {"dev": "vite", "build": "tsc && vite build", "test": "vitest"},
                    "dependencies": {"react": "^18.3.1", "react-dom": "^18.3.1"},
                    "devDependencies": {"typescript": "^5.4.5", "vite": "^5.2.11", "vitest": "^1.6.0"}
                }, f, indent=2)
            with open(os.path.join(dest_dir, "src", "App.tsx"), "w", encoding="utf-8") as f:
                f.write("export default function App() {\n  return (\n    <main className='p-8'>\n      <h1 className='text-2xl font-bold'>Hello Antigravity</h1>\n      <p>Workspace ready for AI Pair Programming.</p>\n    </main>\n  );\n}\n")
            with open(os.path.join(dest_dir, "README.md"), "w", encoding="utf-8") as f:
                f.write(f"# {ws_name}\n\nReact + TypeScript + Vite project initialized in Antigravity Cockpit.\n")
        elif template_type == "node":
            os.makedirs(os.path.join(dest_dir, "src"), exist_ok=True)
            with open(os.path.join(dest_dir, "package.json"), "w", encoding="utf-8") as f:
                json.dump({
                    "name": ws_name.lower(),
                    "version": "1.0.0",
                    "type": "module",
                    "main": "src/index.js",
                    "scripts": {"start": "node src/index.js", "dev": "node --watch src/index.js"},
                    "dependencies": {"express": "^4.19.2", "cors": "^2.8.5"}
                }, f, indent=2)
            with open(os.path.join(dest_dir, "src", "index.js"), "w", encoding="utf-8") as f:
                f.write("import express from 'express';\nconst app = express();\napp.use(express.json());\napp.get('/', (req, res) => res.json({ status: 'ok', project: '" + ws_name + "' }));\nconst PORT = process.env.PORT || 3000;\napp.listen(PORT, () => console.log(`Server listening on ${PORT}`));\n")
            with open(os.path.join(dest_dir, "README.md"), "w", encoding="utf-8") as f:
                f.write(f"# {ws_name}\n\nNode.js Express API initialized in Antigravity Cockpit.\n")
        elif template_type == "python":
            with open(os.path.join(dest_dir, "app.py"), "w", encoding="utf-8") as f:
                f.write("from flask import Flask, jsonify\n\napp = Flask(__name__)\n\n@app.route('/')\ndef home():\n    return jsonify({'message': 'Hello from " + ws_name + "', 'status': 'ready'})\n\nif __name__ == '__main__':\n    app.run(host='0.0.0.0', port=5000, debug=True)\n")
            with open(os.path.join(dest_dir, "requirements.txt"), "w", encoding="utf-8") as f:
                f.write("flask>=3.0.0\nrequests>=2.31.0\npytest>=8.0.0\n")
            with open(os.path.join(dest_dir, "README.md"), "w", encoding="utf-8") as f:
                f.write(f"# {ws_name}\n\nPython service created in Antigravity Cockpit.\n")
        else:
            with open(os.path.join(dest_dir, "README.md"), "w", encoding="utf-8") as f:
                f.write(f"# {ws_name}\n\nWorkspace created in Antigravity Cockpit.\n")
            with open(os.path.join(dest_dir, ".gitignore"), "w", encoding="utf-8") as f:
                f.write("node_modules/\n__pycache__/\n.env\n*.log\n")

        stats = scan_workspace_stats(dest_dir)
        ws_obj = {
            "id": slug_id,
            "name": ws_name,
            "description": ws_desc or f"Starter template: {template_type.title()}",
            "source": "template",
            "template_type": template_type,
            "created_at": time.time(),
            "updated_at": time.time(),
            "file_count": stats["file_count"],
            "dir_count": stats["dir_count"],
            "size_bytes": stats["size_bytes"],
            "primary_language": stats["primary_language"],
            "synced_agents": []
        }
        WORKSPACES[slug_id] = ws_obj
        save_workspaces()
        return jsonify({"success": True, "workspace": ws_obj})
    except Exception as e:
        shutil.rmtree(dest_dir, ignore_errors=True)
        return jsonify({"error": str(e)}), 500

@app.route("/api/workspaces/<ws_id>/tree", methods=["GET"])
def get_workspace_tree_route(ws_id):
    if ws_id not in WORKSPACES:
        load_workspaces()
    ws = WORKSPACES.get(ws_id)
    if not ws:
        return jsonify({"error": "Workspace not found"}), 404

    ws_dir = os.path.join(WORKSPACES_DIR, ws_id)
    if not os.path.exists(ws_dir):
        return jsonify({"error": "Workspace directory missing"}), 404

    tree = build_workspace_tree(ws_dir, max_depth=5)
    return jsonify({"workspace": ws, "tree": tree})

@app.route("/api/workspaces/<ws_id>/file", methods=["GET"])
def get_workspace_file_content(ws_id):
    if ws_id not in WORKSPACES:
        load_workspaces()
    if ws_id not in WORKSPACES:
        return jsonify({"error": "Workspace not found"}), 404

    rel_path = request.args.get("path", "").strip()
    if not rel_path:
        return jsonify({"error": "Path parameter is required"}), 400

    norm = os.path.normpath(rel_path)
    if norm.startswith("..") or os.path.isabs(norm):
        return jsonify({"error": "Invalid file path"}), 400

    full_p = os.path.join(WORKSPACES_DIR, ws_id, norm)
    if not os.path.exists(full_p) or os.path.isdir(full_p):
        return jsonify({"error": "File not found"}), 404

    size = os.path.getsize(full_p)
    if size > 1024 * 1024:
        return jsonify({"error": "File too large to preview (> 1MB)", "size": size}), 400

    try:
        with open(full_p, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        return jsonify({
            "path": rel_path,
            "filename": os.path.basename(full_p),
            "size": size,
            "lines": len(content.splitlines()),
            "content": content
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def deploy_workspace_to_targets(ws_id, target="agent-1", clean_first=False):
    if ws_id not in WORKSPACES:
        load_workspaces()
    ws = WORKSPACES.get(ws_id)
    if not ws:
        raise ValueError(f"Workspace {ws_id} not found")

    ws_dir = os.path.join(WORKSPACES_DIR, ws_id)
    if not os.path.exists(ws_dir):
        raise ValueError(f"Workspace directory {ws_dir} missing")

    targets = [a for a in AGENTS if (target in ["broadcast", "all"] or a["id"] == target or (isinstance(target, list) and a["id"] in target))]
    if not targets:
        raise ValueError("No valid target agents selected")

    tar_bytes = create_workspace_tar_gz(ws_dir)
    b64_archive = base64.b64encode(tar_bytes).decode("utf-8")

    payload = {
        "archive": b64_archive,
        "workspace_name": ws.get("name"),
        "workspace_id": ws_id,
        "clean_first": clean_first
    }

    results = {}
    synced = set(ws.get("synced_agents", []))

    for a in targets:
        try:
            r = requests.post(f"http://{a['ip']}:{a['port']}/workspace/deploy", json=payload, timeout=20)
            res = r.json()
            results[a["id"]] = res
            if res.get("success"):
                synced.add(a["id"])
        except Exception as e:
            results[a["id"]] = {"error": str(e)}

    ws["synced_agents"] = list(synced)
    ws["updated_at"] = time.time()
    save_workspaces()
    return results

@app.route("/api/workspaces/<ws_id>/deploy", methods=["POST"])
def deploy_workspace_route(ws_id):
    data = request.get_json(force=True, silent=True) or {}
    target = data.get("target", "agent-1")
    clean_first = bool(data.get("clean_first", False))

    try:
        results = deploy_workspace_to_targets(ws_id, target, clean_first)
        return jsonify({"success": True, "results": results, "workspace": WORKSPACES.get(ws_id)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/workspaces/<ws_id>/pull", methods=["POST"])
def pull_workspace_route(ws_id):
    data = request.get_json(force=True, silent=True) or {}
    agent_id = data.get("agent_id", "agent-1")
    agent = next((a for a in AGENTS if a["id"] == agent_id), None)
    if not agent:
        return jsonify({"error": "Invalid agent"}), 400

    ws = WORKSPACES.get(ws_id)
    if not ws:
        return jsonify({"error": "Workspace not found"}), 404

    ws_dir = os.path.join(WORKSPACES_DIR, ws_id)

    try:
        r = requests.get(f"http://{agent['ip']}:{agent['port']}/workspace/export", timeout=30)
        if r.status_code != 200:
            return jsonify({"error": "Failed to pull workspace from agent"}), 500

        res_data = r.json()
        b64_tar = res_data.get("archive")
        if not b64_tar:
            return jsonify({"error": "Agent returned empty archive"}), 500

        raw_tar = base64.b64decode(b64_tar)
        with tarfile.open(fileobj=io.BytesIO(raw_tar), mode="r:gz") as tf:
            tf.extractall(ws_dir)

        stats = scan_workspace_stats(ws_dir)
        ws["file_count"] = stats["file_count"]
        ws["dir_count"] = stats["dir_count"]
        ws["size_bytes"] = stats["size_bytes"]
        ws["updated_at"] = time.time()
        save_workspaces()

        return jsonify({
            "success": True,
            "message": f"Successfully pulled latest code from {agent['name']}",
            "workspace": ws
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/workspaces/<ws_id>/download", methods=["GET"])
def download_workspace_route(ws_id):
    ws = WORKSPACES.get(ws_id)
    if not ws:
        load_workspaces()
        ws = WORKSPACES.get(ws_id)
    if not ws:
        return "Workspace not found", 404

    ws_dir = os.path.join(WORKSPACES_DIR, ws_id)
    if not os.path.exists(ws_dir):
        return "Workspace directory missing", 404

    try:
        zip_bytes = create_workspace_zip(ws_dir)
        filename = f"{re.sub(r'[^a-zA-Z0-9_\-]', '_', ws.get('name', 'project'))}.zip"
        return Response(
            zip_bytes,
            mimetype="application/zip",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/workspaces/<ws_id>", methods=["DELETE"])
def delete_workspace_route(ws_id):
    if ws_id not in WORKSPACES:
        load_workspaces()
    if ws_id not in WORKSPACES:
        return jsonify({"error": "Workspace not found"}), 404

    ws_dir = os.path.join(WORKSPACES_DIR, ws_id)
    shutil.rmtree(ws_dir, ignore_errors=True)
    del WORKSPACES[ws_id]
    save_workspaces()
    return jsonify({"success": True, "deleted_id": ws_id})

@app.route("/api/workspaces/<ws_id>/rename", methods=["POST"])
def rename_workspace_route(ws_id):
    if ws_id not in WORKSPACES:
        load_workspaces()
    ws = WORKSPACES.get(ws_id)
    if not ws:
        return jsonify({"error": "Workspace not found"}), 404

    data = request.get_json(force=True, silent=True) or {}
    new_name = (data.get("name") or "").strip()
    new_desc = (data.get("description") or "").strip()

    if new_name:
        ws["name"] = new_name
    if new_desc is not None:
        ws["description"] = new_desc
    ws["updated_at"] = time.time()
    save_workspaces()
    return jsonify({"success": True, "workspace": ws})

# ==================================================================
# CEO ORCHESTRATOR & AUTONOMOUS HEARTBEAT SUPERVISOR (PAPERCLIP)
# ==================================================================
ceo_orchestrator = None
ceo_supervisor = None

if CeoOrchestrator:
    try:
        ceo_orchestrator = CeoOrchestrator(
            get_agents_fn=lambda: AGENTS,
            dispatch_fn=lambda target, prompt, workspace_id: dispatch_task_internal(target=target, prompt=prompt, ws_id=workspace_id)
        )
        ceo_supervisor = CeoHeartbeatSupervisor(
            orchestrator=ceo_orchestrator,
            get_agents_fn=lambda: AGENTS,
            get_agent_status_fn=get_single_agent_status,
            interval_seconds=30
        )
        ceo_supervisor.start()
        print("[CEO Engine] Autonomous Heartbeat Supervisor active (30s cadence)")
    except Exception as e:
        print(f"[CEO Engine] Warning: Failed to start CEO supervisor: {e}")

@app.route("/api/ceo/order", methods=["POST"])
def ceo_post_directive():
    if not ceo_orchestrator:
        return jsonify({"error": "CEO Orchestrator engine not initialized"}), 503
    data = request.get_json(force=True, silent=True) or {}
    text = (data.get("directive") or "").strip()
    if not text:
        return jsonify({"error": "Directive text is required"}), 400
        
    ws_id = data.get("workspace_id")
    prio = data.get("priority", "high")
    
    directive_entry, created_orders = ceo_orchestrator.receive_board_directive(
        directive_text=text,
        workspace_id=ws_id,
        priority=prio
    )
    
    # Run immediate heartbeat pulse to kick off ready tasks
    if ceo_supervisor:
        try:
            ceo_supervisor.pulse()
        except Exception:
            pass
            
    return jsonify({
        "success": True,
        "directive": directive_entry,
        "tasks": [wo.to_dict() for wo in created_orders]
    })

@app.route("/api/ceo/status", methods=["GET"])
def ceo_get_status():
    if not ceo_orchestrator:
        return jsonify({"error": "CEO Orchestrator engine not initialized"}), 503
        
    metrics = ceo_orchestrator.get_summary_metrics()
    chain = get_chain_of_command() if get_chain_of_command else {}
    
    hb_info = {
        "count": ceo_supervisor.heartbeat_count if ceo_supervisor else 0,
        "timestamp": ceo_supervisor.last_heartbeat_time if ceo_supervisor else 0,
        "log": ceo_supervisor.last_heartbeat_log if ceo_supervisor else [],
        "escalations": ceo_supervisor.active_escalations if ceo_supervisor else []
    }
    
    return jsonify({
        "executive_summary": ceo_orchestrator.executive_summary,
        "metrics": metrics,
        "heartbeat": hb_info,
        "audit_log": ceo_orchestrator.audit_log[-50:],
        "chain_of_command": chain,
        "roles": ROLE_DEFINITIONS
    })

@app.route("/api/ceo/heartbeat", methods=["POST"])
def ceo_trigger_heartbeat():
    if not ceo_supervisor:
        return jsonify({"error": "CEO Heartbeat supervisor not initialized"}), 503
    pulse_res = ceo_supervisor.pulse()
    return jsonify({"success": True, "pulse": pulse_res})

@app.route("/api/ceo/tasks", methods=["GET"])
def ceo_get_tasks():
    if not ceo_orchestrator:
        return jsonify({"error": "CEO Orchestrator engine not initialized"}), 503
        
    status_filter = request.args.get("status")
    role_filter = request.args.get("role")
    agent_filter = request.args.get("agent_id")
    
    tasks = list(ceo_orchestrator.work_orders.values())
    if status_filter:
        tasks = [t for t in tasks if t.status == status_filter]
    if role_filter:
        tasks = [t for t in tasks if t.role == role_filter]
    if agent_filter:
        tasks = [t for t in tasks if t.assigned_agent_id == agent_filter]
        
    tasks.sort(key=lambda t: t.created_at, reverse=True)
    return jsonify({"tasks": [t.to_dict() for t in tasks]})

@app.route("/api/ceo/tasks/<order_id>/action", methods=["POST"])
def ceo_task_action(order_id):
    if not ceo_orchestrator:
        return jsonify({"error": "CEO Orchestrator engine not initialized"}), 503
        
    data = request.get_json(force=True, silent=True) or {}
    action = data.get("action")
    note = data.get("note")
    
    if action == "dispatch":
        success, msg = ceo_orchestrator.dispatch_work_order(order_id)
        return jsonify({"success": success, "message": str(msg)})
    elif action == "approve":
        success, msg = ceo_orchestrator.update_task_status(order_id, "done", note=note or "Manually approved by Board/CEO")
        return jsonify({"success": success, "message": msg})
    elif action == "reject":
        success, msg = ceo_orchestrator.update_task_status(order_id, "todo", note=note or "Returned for revision")
        return jsonify({"success": success, "message": msg})
    elif action == "block":
        success, msg = ceo_orchestrator.update_task_status(order_id, "blocked", note=note or "Blocked by Board/CEO")
        return jsonify({"success": success, "message": msg})
    elif action == "reassign":
        new_agent = data.get("agent_id")
        wo = ceo_orchestrator.work_orders.get(order_id)
        if not wo:
            return jsonify({"error": "Task not found"}), 404
        wo.assigned_agent_id = new_agent
        ceo_orchestrator.save_state()
        return jsonify({"success": True, "message": f"Task reassigned to {new_agent}"})
        
    return jsonify({"error": f"Unknown action: {action}"}), 400

@app.route("/api/ceo/role", methods=["POST"])
def ceo_update_role():
    data = request.get_json(force=True, silent=True) or {}
    agent_id = data.get("agent_id")
    role_id = data.get("role")
    
    agent = next((a for a in AGENTS if a["id"] == agent_id), None)
    if not agent:
        return jsonify({"error": "Agent not found"}), 404
        
    role_spec = get_role_spec(role_id) if get_role_spec else None
    role_name = role_spec["name"] if role_spec else role_id
    
    agent["role"] = role_name
    save_agents_config()
    
    if ceo_orchestrator:
        ceo_orchestrator.log_event("agent_role_updated", f"Agent {agent['name']} ({agent_id}) reassigned to role {role_name}", {
            "agent_id": agent_id,
            "role": role_name
        })
        
    return jsonify({"success": True, "agent": agent})

@app.route("/api/ceo/org", methods=["GET"])
def ceo_get_org():
    roles = ROLE_DEFINITIONS if ROLE_DEFINITIONS else []
    enriched_agents = []
    for a in AGENTS:
        status_info = get_single_agent_status(a["id"])
        enriched_agents.append({
            "id": a["id"],
            "vmid": a.get("vmid"),
            "name": a.get("name"),
            "type": a.get("type", "antigravity"),
            "role": a.get("role", "Frontend Specialist"),
            "ip": a.get("ip"),
            "port": a.get("port"),
            "status": status_info.get("status", "offline"),
            "busy": status_info.get("busy", False)
        })
        
    chain = get_chain_of_command() if get_chain_of_command else {}
    return jsonify({
        "chain_of_command": chain,
        "agents": enriched_agents,
        "roles": roles
    })

@app.route("/api/ceo/prompts/<prompt_name>", methods=["GET"])
def ceo_get_prompt(prompt_name):
    allowed = ["AGENTS.md", "SOUL.md", "HEARTBEAT.md"]
    if prompt_name not in allowed:
        return jsonify({"error": "Invalid prompt name"}), 400
        
    prompt_path = os.path.join(SCRIPT_DIR, "ceo", "prompts", prompt_name)
    if not os.path.exists(prompt_path):
        prompt_path = os.path.join("/usr/local/share/cockpit/ceo/prompts", prompt_name)
        
    if os.path.exists(prompt_path):
        try:
            with open(prompt_path, "r", encoding="utf-8") as f:
                return jsonify({"name": prompt_name, "content": f.read()})
        except Exception as e:
            return jsonify({"error": str(e)}), 500
            
    return jsonify({"error": f"Prompt file {prompt_name} not found"}), 404

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=3000)
