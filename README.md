# Antigravity Cockpit

A self-hosted multi-agent orchestration system for running and controlling [Antigravity AI](https://antigravity.dev) instances on **Proxmox LXC containers**.

Includes a web dashboard, a per-agent API bridge, and a CDP-based prompt injection engine that types directly into running Antigravity GUI sessions.

---

## Architecture

```
Proxmox PVE (192.168.178.105)
├── CT 150  agy-cockpit     :3000   ← Web dashboard (this)
├── CT 151  agy-agent-1     :8000   ← Antigravity instance + agent bridge
├── CT 152  agy-agent-2     :8000   ← Antigravity instance + agent bridge
└── CT 153+ agy-agent-N     :8000   ← Additional agents (Codex, Hermes, …)
```

Each **agent container** runs:
- `Xvfb :1` virtual display
- `openbox` window manager
- Antigravity Electron app (authenticated)
- `x11vnc` → `websockify` → noVNC (live desktop at `:6080`)
- `agent-bridge` Flask API (`:8000`)

The **cockpit** (CT 150) hosts the dashboard and talks to the Proxmox API and each agent bridge.

---

## Components

### `cockpit/cockpit_server.py`

Flask web dashboard — the main control plane.

**Features:**
- Fleet management: start / stop / rename / remove containers via Proxmox API
- Task Dispatcher: type a prompt (+ drag-and-drop screenshots) into any agent
- Broadcast Mode: send the same task to all running agents simultaneously  
- Skills Hub: two-way capability manager — push skills to any agent's `~/.gemini/skills/`, download/export skills to `.zip` / `.tar.gz`, or import new skills via drag & drop
- **Workspaces**: Import your project directly into the Cockpit, browse files in the built-in Code Inspector, deploy to any agent with one click, and pull agent changes back
- Add new agents — choose engine type: Antigravity, Codex, Hermes Agent, Open Claw
- Real-time status polling: CPU, RAM, auth state, busy/idle
- Three dark UI themes: **Onyx Stealth**, **Cobalt Hyperdrive**, **Tokyo Neon**

### `agent/agent_bridge.py`

Flask REST API running on each agent container.

| Endpoint | Description |
|---|---|
| `POST /dispatch` | Inject prompt + images into Antigravity via CDP |
| `GET /screenshot` | Capture the agent's X11 desktop |
| `GET /status` | Running/idle state, auth status |
| `POST /auth` | Push an OAuth token into `~/.gemini/` |
| `GET /logs` | Tail the Antigravity language_server log |
| `GET /skills` | List installed skills |
| `POST /skills/install` | Install a skill from the library |
| `GET /skills/<name>/export` | Export and download an installed skill from the agent |
| `POST /workspace/deploy` | Unpack a project archive into `/home/ubuntu/workspace` |
| `GET /workspace/status` | Report active workspace name, file count, and size |
| `GET /workspace/export` | Export current workspace as base64 tar.gz for Cockpit pull |
| `POST /workspace/clean` | Clear the agent workspace (preserves `/media`) |

### `agent/antigravity_injector.py`

Standalone CDP injection utility — connects to Antigravity's DevTools debugger
and types a prompt into the chat input, then clicks Send. Good for testing.

### `agent/install_antigravity_agent.sh`

One-shot bootstrap: installs all dependencies, creates `webdesktop` and
`agent-bridge` systemd services, sets up directories.

### `agent/start-webdesktop.sh`

Launches the full X11 virtual desktop stack:
`Xvfb → openbox → x11vnc → websockify → Antigravity`

---

## How CDP Injection Works

Antigravity is an Electron app. Each instance exposes a Chrome DevTools Protocol
debugger on a dynamic port stored in:

```
/root/.config/Antigravity/DevToolsActivePort
```

Injection sequence:
1. Read port from `DevToolsActivePort`
2. `GET /json/list` → find the page WebSocket URL
3. Focus `div[role="combobox"][contenteditable="true"]` (React chat input)
4. `Input.insertText` — triggers React's synthetic events correctly (`execCommand` does NOT)
5. Click `button[aria-label="Send message"]` via `Runtime.evaluate`
6. Fallback: `rawKeyDown` Enter if button isn't clickable
7. Auto-confirm tool permission dialogs (Submit / Allow) via CDP every 1.5s

---

## Deployment

### Cockpit (CT 150)

```bash
scp cockpit/cockpit_server.py root@<proxmox-host>:/tmp/
ssh root@<proxmox-host> "pct push 150 /tmp/cockpit_server.py /usr/local/bin/cockpit_server.py \
  && pct exec 150 -- systemctl restart cockpit.service"
```

### Agent Bridge (CT 151, 152, …)

```bash
scp agent/agent_bridge.py root@<proxmox-host>:/tmp/
ssh root@<proxmox-host> "
  pct push 151 /tmp/agent_bridge.py /usr/local/bin/agent_bridge.py
  pct push 152 /tmp/agent_bridge.py /usr/local/bin/agent_bridge.py
  pct exec 151 -- systemctl restart agent-bridge.service
  pct exec 152 -- systemctl restart agent-bridge.service
"
```

### Bootstrap a New Agent Container

```bash
# On the Proxmox host, inside a fresh LXC container:
bash install_antigravity_agent.sh
```

---

## `scripts/`

Diagnostic and setup utilities used during development:

| Script | Purpose |
|---|---|
| `test_dispatch.py` | End-to-end dispatch tester |
| `test_image_dispatch.py` | Tests image attachment via `/dispatch` |
| `test_cdp.py` | CDP DOM inspector / connection debugger |
| `test_skills.py` | Skills API tester |
| `finish_wizard.py` | Auto-completes Antigravity onboarding via CDP |
| `capture_screen.py` | Manual X11 screenshot grabber |
| `print_dom.py` | Dumps Antigravity DOM to stdout via CDP |
| `fix_openbox.py` | Patches openbox autostart config |
| `patch_chrome.py` | Chrome / Electron flags patcher |

---

## Notes

- **Flask 3.x**: all routes use `request.get_json(force=True, silent=True)` — `request.json` raises 400 in Flask 3+ when content-type is missing.
- **`scrot`**: use `-o` flag to overwrite existing files (`scrot -z -o /tmp/file.png`).
- **Auth tokens**: stored at `/root/.gemini/jetski-standalone-oauth-token` (JSON).
- **CDP port**: changes on every Antigravity restart — always re-read from `DevToolsActivePort`.

---

## Workspaces

The **Workspaces** feature lets you import any codebase directly into the Cockpit and push it live into your AI agent containers.

### How it works

```
Your Project (ZIP / Git Repo / Template)
   │
   ▼
Cockpit Workspaces Store (/usr/local/share/cockpit/workspaces/<ws-id>/)
   │  File tree browser, Code Inspector, tech stack detection, stats
   │
   ├── Deploy ──► Agent Bridge POST /workspace/deploy
   │              Unpacks to /home/ubuntu/workspace (ubuntu:ubuntu)
   │              Writes .cockpit_workspace.json manifest
   │
   ├── Pull  ◄── Agent Bridge GET /workspace/export
   │              Returns base64 tar.gz of agent workspace state
   │
   └── Task Dispatcher automatically prefixes prompt:
       "[Active Project Workspace]: /home/ubuntu/workspace
        (Project: <name>, Stack: <stack>, <N> files)"
```

### Import methods

| Method | How |
|---|---|
| **Upload archive** | Drag & drop a `.zip`, `.tar.gz`, or `.tar` file onto the drop zone. GitHub/GitLab zips (with single root folder) are auto-flattened. |
| **Git clone** | Paste any HTTPS/SSH repo URL (+ optional branch). Uses `git clone --depth 1`. |
| **Starter template** | Pick React/Vite+TS, Node.js/Express, Python/Flask, or Blank and the Cockpit scaffolds it instantly. |

### Cockpit API endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/api/workspaces` | `GET` | List all stored workspaces with stats |
| `/api/workspaces/upload` | `POST` | Upload a project archive (multipart or base64 JSON) |
| `/api/workspaces/git_clone` | `POST` | Clone a Git repository |
| `/api/workspaces/create_template` | `POST` | Scaffold a starter template |
| `/api/workspaces/<id>/tree` | `GET` | Return file-tree JSON for the Code Inspector |
| `/api/workspaces/<id>/file` | `GET` | Read a file's content (path-traversal protected) |
| `/api/workspaces/<id>/deploy` | `POST` | Package & deploy workspace to agent(s) |
| `/api/workspaces/<id>/pull` | `POST` | Pull updated files back from an agent |
| `/api/workspaces/<id>/download` | `GET` | Stream a `.zip` download to the browser |
| `/api/workspaces/<id>/rename` | `POST` | Rename/re-describe a workspace |
| `/api/workspaces/<id>` | `DELETE` | Remove workspace and all files |

### Agent Bridge workspace endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/workspace/deploy` | `POST` | Receives `{"archive": "<b64_tar_gz>", "workspace_name": "...", "workspace_id": "...", "clean_first": false}`. Extracts to `/home/ubuntu/workspace`, sets `ubuntu:ubuntu` ownership, writes `.cockpit_workspace.json`. |
| `/workspace/status` | `GET` | Returns active workspace ID, name, file count, size, deploy timestamp. |
| `/workspace/export` | `GET` | Streams back a base64 tar.gz of the current agent workspace (excludes `.git`, `node_modules`, `__pycache__`). |
| `/workspace/clean` | `POST` | Removes all items from the agent workspace (preserves the `media/` subfolder). |

### Tech stack detection

The Cockpit auto-detects the primary language/framework by inspecting:
- `package.json` → React, Vue, Next.js, Svelte, Express, or Node.js
- `requirements.txt` / `pyproject.toml` / `.py` files → Python
- `Cargo.toml` → Rust
- `go.mod` → Go
- `index.html` (fallback) → HTML5/Frontend

### Agent workspace path

Project files land at **`/home/ubuntu/workspace`** (symlinked / mirrored to `/root/workspace`) so both the `ubuntu` GUI desktop and root shell tools can reach them. The installer script (`agent/install_antigravity_agent.sh`) creates this directory and sets proper ownership automatically.

