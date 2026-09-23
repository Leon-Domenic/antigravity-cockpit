import os, sys, json, time, subprocess, threading, base64, shutil, tarfile, io, re, zipfile
from flask import Flask, request, jsonify, send_file

app = Flask(__name__)

CURRENT_TASK = None
LOG_HISTORY = []

SKILL_DIRS = [
    "/root/.gemini/skills",
    "/root/.gemini/config/skills",
    "/home/ubuntu/.gemini/skills",
    "/root/.gemini/antigravity/builtin/skills"
]
AGENT_TYPE_FILE = "/etc/antigravity/agent_type"

def get_engine_type():
    """Read the configured engine type from the marker file."""
    try:
        if os.path.exists(AGENT_TYPE_FILE):
            with open(AGENT_TYPE_FILE, "r") as f:
                engine = f.read().strip().lower()
                if engine:
                    return engine
    except Exception:
        pass
    return "antigravity"

def get_auth_status():
    paths = [
        "/root/.gemini/jetski-standalone-oauth-token",
        "/home/ubuntu/.gemini/jetski-standalone-oauth-token"
    ]
    for p in paths:
        if os.path.exists(p) and os.path.getsize(p) > 10:
            return True
    return False

def get_cdp_port():
    candidates = [
        "/root/.config/Antigravity/DevToolsActivePort",
        "/home/ubuntu/.config/Antigravity/DevToolsActivePort"
    ]
    for p in candidates:
        if os.path.exists(p):
            try:
                with open(p, "r") as f:
                    lines = [l.strip() for l in f.readlines() if l.strip()]
                    if lines and lines[0].isdigit():
                        return int(lines[0])
            except Exception:
                pass
    return None

async def cdp_inject(port, prompt_text, start_new_conversation=False):
    import urllib.request, websockets
    url = f"http://127.0.0.1:{port}/json/list"
    req = urllib.request.urlopen(url, timeout=3)
    targets = json.loads(req.read().decode())
    
    target = None
    for t in targets:
        if t.get("type") == "page" and ("Antigravity" in t.get("title", "") or "127.0.0.1" in t.get("url", "")):
            target = t
            break
    if not target and targets:
        target = targets[0]
    
    if not target or not target.get("webSocketDebuggerUrl"):
        raise RuntimeError("No suitable CDP page target found")
    
    ws_url = target["webSocketDebuggerUrl"]
    
    async with websockets.connect(ws_url, ping_interval=None) as ws:
        msg_id = 1
        
        # 1. Optionally start a new conversation
        if start_new_conversation:
            new_chat_js = """
            (function() {
                var btn = document.querySelector('button[aria-label="New Conversation"]');
                if (btn) {
                    btn.click();
                    return true;
                }
                return false;
            })()
            """
            await ws.send(json.dumps({"id": msg_id, "method": "Runtime.evaluate", "params": {"expression": new_chat_js, "returnByValue": True}}))
            msg_id += 1
            await ws.recv()
            await asyncio.sleep(0.5)

        # 2. Focus input combobox
        focus_js = """
        (function() {
            var box = document.querySelector('div[role="combobox"]');
            if (!box) {
                box = document.querySelector('[contenteditable="true"]') || document.querySelector('textarea');
            }
            if (box) {
                box.focus();
                var range = document.createRange();
                var sel = window.getSelection();
                range.selectNodeContents(box);
                range.collapse(false);
                sel.removeAllRanges();
                sel.addRange(range);
                return true;
            }
            return false;
        })()
        """
        await ws.send(json.dumps({"id": msg_id, "method": "Runtime.evaluate", "params": {"expression": focus_js, "returnByValue": True}}))
        msg_id += 1
        res = json.loads(await ws.recv())
        focused = res.get("result", {}).get("result", {}).get("value", False)
        if not focused:
            raise RuntimeError("Could not find or focus chat input field")
        
        await asyncio.sleep(0.3)
        
        # 3. Insert text via CDP Input.insertText
        insert_cmd = {"id": msg_id, "method": "Input.insertText", "params": {"text": prompt_text}}
        await ws.send(json.dumps(insert_cmd))
        msg_id += 1
        await ws.recv()
        
        await asyncio.sleep(0.4)
        
        # 4. Click Send Message button
        click_send_js = """
        (function() {
            var sendBtn = document.querySelector('button[aria-label="Send message"]');
            if (sendBtn && !sendBtn.disabled) {
                sendBtn.click();
                return "clicked";
            }
            return "not_clicked";
        })()
        """
        await ws.send(json.dumps({"id": msg_id, "method": "Runtime.evaluate", "params": {"expression": click_send_js, "returnByValue": True}}))
        msg_id += 1
        res = json.loads(await ws.recv())
        status = res.get("result", {}).get("result", {}).get("value", "")
        
        # If button couldn't be clicked directly, dispatch Enter key
        if status != "clicked":
            enter_down = {"id": msg_id, "method": "Input.dispatchKeyEvent", "params": {"type": "rawKeyDown", "windowsVirtualKeyCode": 13, "unmodifiedText": "\r", "text": "\r"}}
            await ws.send(json.dumps(enter_down))
            msg_id += 1
            await ws.recv()
            enter_up = {"id": msg_id, "method": "Input.dispatchKeyEvent", "params": {"type": "keyUp", "windowsVirtualKeyCode": 13, "unmodifiedText": "\r", "text": "\r"}}
            await ws.send(json.dumps(enter_up))
            msg_id += 1
            await ws.recv()
            
        return True

def x11_inject(prompt_text):
    env = dict(os.environ, DISPLAY=":1")
    res = subprocess.run(["xdotool", "search", "--onlyvisible", "--class", "Antigravity"], env=env, capture_output=True, text=True)
    wids = [w.strip() for w in res.stdout.splitlines() if w.strip()]
    if not wids:
        raise RuntimeError("Antigravity window not found on DISPLAY=:1")
    wid = wids[0]
    
    subprocess.run(["xdotool", "windowactivate", "--sync", wid], env=env, check=True)
    time.sleep(0.3)
    
    p = subprocess.Popen(["xclip", "-selection", "clipboard"], stdin=subprocess.PIPE, env=env)
    p.communicate(input=prompt_text.encode("utf-8"))
    
    subprocess.run(["xdotool", "key", "--clearmodifiers", "ctrl+v"], env=env, check=True)
    time.sleep(0.3)
    subprocess.run(["xdotool", "key", "Return"], env=env, check=True)
    return True

def inject_into_antigravity(prompt_text, start_new_conversation=False):
    port = get_cdp_port()
    if port:
        try:
            import asyncio
            return asyncio.run(cdp_inject(port, prompt_text, start_new_conversation))
        except Exception as e:
            LOG_HISTORY.append({"type": "stream", "time": time.strftime("%H:%M:%S"), "text": f"CDP inject error: {e}, falling back to X11"})
    return x11_inject(prompt_text)

def auto_confirm_permissions():
    """Auto-click Submit/Allow in Antigravity permission dialogs via CDP."""
    port = get_cdp_port()
    if not port:
        return False
    try:
        import asyncio
        async def _confirm():
            import urllib.request, websockets
            url = f"http://127.0.0.1:{port}/json/list"
            req = urllib.request.urlopen(url, timeout=2)
            targets = json.loads(req.read().decode())
            target = None
            for t in targets:
                if t.get("type") == "page":
                    target = t
                    break
            if not target or not target.get("webSocketDebuggerUrl"):
                return False
            async with websockets.connect(target["webSocketDebuggerUrl"], ping_interval=None) as ws:
                click_js = """
                (function() {
                    // Look for Submit / Allow / Continue buttons in modals/dialogs
                    var selectors = [
                        'button[data-testid="tool-confirm-submit"]',
                        'button[aria-label="Submit"]',
                        'button[aria-label="Allow"]',
                        'dialog button',
                        '[role="dialog"] button'
                    ];
                    for (var s of selectors) {
                        var btns = document.querySelectorAll(s);
                        for (var b of btns) {
                            var txt = b.textContent.trim().toLowerCase();
                            if (txt === 'submit' || txt === 'allow' || txt === 'continue' || txt === 'confirm') {
                                b.click();
                                return txt;
                            }
                        }
                    }
                    // Broader search: any visible button with text "Submit"
                    var allBtns = document.querySelectorAll('button');
                    for (var b of allBtns) {
                        var txt = b.textContent.trim().toLowerCase();
                        if ((txt === 'submit' || txt === 'allow') && b.offsetParent !== null) {
                            b.click();
                            return txt;
                        }
                    }
                    return null;
                })()
                """
                await ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate",
                                          "params": {"expression": click_js, "returnByValue": True}}))
                res = json.loads(await ws.recv())
                val = res.get("result", {}).get("result", {}).get("value")
                return bool(val)
        return asyncio.run(_confirm())
    except Exception:
        return False

QUOTA_CACHE = {"timestamp": 0, "data": None}

def fetch_model_quota(force_refresh=False):
    global QUOTA_CACHE
    now = time.time()
    if not force_refresh and QUOTA_CACHE["data"] and (now - QUOTA_CACHE["timestamp"] < 60):
        return QUOTA_CACHE["data"]

    token_paths = [
        "/root/.gemini/jetski-standalone-oauth-token",
        "/home/ubuntu/.gemini/jetski-standalone-oauth-token"
    ]
    token = None
    for p in token_paths:
        if os.path.exists(p) and os.path.getsize(p) > 10:
            try:
                with open(p, "r", encoding="utf-8") as f:
                    tdata = json.load(f)
                    if isinstance(tdata, dict):
                        tok = tdata.get("token", {})
                        if isinstance(tok, dict) and "access_token" in tok:
                            token = tok["access_token"]
                        elif "access_token" in tdata:
                            token = tdata["access_token"]
                        if token:
                            break
            except Exception:
                pass

    if not token:
        return {"error": "Not authenticated (missing jetski token)", "authenticated": False, "models": {}}

    import urllib.request
    models_url = "https://daily-cloudcode-pa.googleapis.com/v1internal:fetchAvailableModels"
    tier_url = "https://daily-cloudcode-pa.googleapis.com/v1internal:loadCodeAssist"

    result = {
        "authenticated": True,
        "timestamp": now,
        "tier": {},
        "models": {},
        "summary": {}
    }

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "User-Agent": "antigravity/2.12.0"
    }

    try:
        req = urllib.request.Request(models_url, data=b"{}", headers=headers)
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode())
            all_models = data.get("models", {})
            for m_id, m_info in all_models.items():
                quota = m_info.get("quotaInfo")
                display_name = m_info.get("displayName") or m_id
                max_tokens = m_info.get("maxTokens")
                remaining_frac = quota.get("remainingFraction", 1.0) if quota else 1.0
                reset_time = quota.get("resetTime") if quota else None
                
                result["models"][m_id] = {
                    "id": m_id,
                    "name": display_name,
                    "remaining_pct": round(remaining_frac * 100, 1),
                    "remaining_fraction": remaining_frac,
                    "reset_time": reset_time,
                    "max_tokens": max_tokens,
                    "recommended": bool(m_info.get("recommended", False))
                }

            def find_best_quota(prefixes):
                matches = [v for k, v in result["models"].items() if any(k.startswith(p) or p in k for p in prefixes)]
                if not matches:
                    return None
                rec = [m for m in matches if m.get("recommended")]
                return rec[0] if rec else matches[0]

            result["summary"] = {
                "gemini_flash": find_best_quota(["gemini-3.8-flash", "gemini-3.7-flash", "gemini-3-flash"]),
                "gemini_pro": find_best_quota(["gemini-3.1-pro", "gemini-pro-agent", "gemini-2.5-pro"]),
                "claude": find_best_quota(["claude-opus", "claude-sonnet"]),
                "gpt_oss": find_best_quota(["gpt-oss"])
            }
    except Exception as e:
        result["error"] = f"Failed to fetch models: {str(e)}"

    try:
        req_tier = urllib.request.Request(tier_url, data=b"{}", headers=headers)
        with urllib.request.urlopen(req_tier, timeout=8) as resp:
            tier_data = json.loads(resp.read().decode())
            cur_tier = tier_data.get("currentTier", {})
            result["tier"] = {
                "id": cur_tier.get("id", "free-tier"),
                "name": cur_tier.get("name", "Antigravity"),
                "description": cur_tier.get("description", ""),
                "subscription_type": tier_data.get("upgradeSubscriptionType", ""),
                "project_id": tier_data.get("cloudaicompanionProject", "")
            }
    except Exception as e:
        result["tier_error"] = str(e)

    QUOTA_CACHE["timestamp"] = now
    QUOTA_CACHE["data"] = result
    return result

@app.route("/quota", methods=["GET"])
def get_quota():
    force = request.args.get("force_refresh", "false").lower() in ["true", "1", "yes"]
    q = fetch_model_quota(force_refresh=force)
    return jsonify(q)

@app.route("/status", methods=["GET"])
def status():
    cached_summary = QUOTA_CACHE["data"].get("summary") if QUOTA_CACHE.get("data") else None
    return jsonify({
        "agent_id": os.uname().nodename,
        "engine_type": get_engine_type(),
        "authenticated": get_auth_status(),
        "status": "busy" if (CURRENT_TASK and CURRENT_TASK.get("running")) else "idle",
        "current_task": CURRENT_TASK,
        "quota_summary": cached_summary
    })

@app.route("/auth", methods=["POST"])
def update_auth():
    data = request.json or {}
    token_str = data.get("token_json")
    if not token_str:
        return jsonify({"error": "Missing token_json"}), 400
    try:
        token_obj = json.loads(token_str) if isinstance(token_str, str) else token_str
        for path in ["/root/.gemini", "/home/ubuntu/.gemini"]:
            os.makedirs(path, exist_ok=True)
            token_file = os.path.join(path, "jetski-standalone-oauth-token")
            with open(token_file, "w") as f:
                json.dump(token_obj, f, indent=2)
            os.chmod(token_file, 0o600)
        QUOTA_CACHE["timestamp"] = 0
        QUOTA_CACHE["data"] = None
        LOG_HISTORY.append({"type": "info", "time": time.strftime("%H:%M:%S"), "text": "OAuth credentials updated successfully."})
        return jsonify({"success": True, "message": "Auth token saved and applied successfully!"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/logs", methods=["GET"])
def logs():
    combined = list(LOG_HISTORY)
    ls_log_path = "/root/.config/Antigravity/logs/language_server.log"
    if os.path.exists(ls_log_path):
        try:
            with open(ls_log_path, "r", errors="ignore") as f:
                lines = f.readlines()
                for l in lines[-35:]:
                    clean = l.strip()
                    if clean and not any(clean in x.get("text", "") for x in combined):
                        combined.append({
                            "type": "stream",
                            "time": time.strftime("%H:%M:%S"),
                            "text": clean
                        })
        except Exception:
            pass
    return jsonify({"logs": combined[-100:]})

@app.route("/screenshot", methods=["GET"])
def screenshot():
    tmp_path = f"/tmp/screenshot_{int(time.time())}.png"
    try:
        env = dict(os.environ, DISPLAY=":1")
        # Ensure fresh paint by activating Antigravity window
        try:
            res = subprocess.run(["xdotool", "search", "--onlyvisible", "--class", "Antigravity"], env=env, capture_output=True, text=True, timeout=1)
            wids = [w.strip() for w in res.stdout.splitlines() if w.strip()]
            if wids:
                subprocess.run(["xdotool", "windowactivate", wids[0]], env=env, timeout=1)
        except Exception:
            pass
        
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        subprocess.run(["scrot", "-z", "-o", tmp_path], env=env, timeout=4)
        if os.path.exists(tmp_path):
            return send_file(tmp_path, mimetype="image/png")
        return jsonify({"error": "Failed to generate screenshot"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/upload", methods=["POST"])
def upload_media():
    data = request.json or {}
    images = data.get("images", [])
    if not images and "data" in data:
        images = [data]
    
    saved = []
    media_dirs = ["/home/ubuntu/workspace/media", "/root/workspace/media", "/tmp/agent_media"]
    for d in media_dirs:
        os.makedirs(d, exist_ok=True)
        
    for idx, img in enumerate(images):
        try:
            name = img.get("name") or f"screenshot_{int(time.time())}_{idx}.png"
            name = re.sub(r'[^a-zA-Z0-9_.-]', '_', name)
            b64_data = img.get("data", "")
            if "," in b64_data:
                b64_data = b64_data.split(",", 1)[1]
            raw_bytes = base64.b64decode(b64_data)
            
            for d in media_dirs:
                dest = os.path.join(d, name)
                with open(dest, "wb") as f:
                    f.write(raw_bytes)
            saved.append(f"/home/ubuntu/workspace/media/{name}")
            LOG_HISTORY.append({
                "type": "info",
                "time": time.strftime("%H:%M:%S"),
                "text": f"≡ƒô╖ Received image attachment: {name} ({len(raw_bytes)//1024} KB) saved to /home/ubuntu/workspace/media/{name}"
            })
        except Exception as e:
            LOG_HISTORY.append({"type": "error", "time": time.strftime("%H:%M:%S"), "text": f"Error saving image: {e}"})

    return jsonify({"success": True, "saved": saved})

@app.route("/dispatch", methods=["POST"])
def dispatch():
    global CURRENT_TASK, LOG_HISTORY
    data = request.json or {}
    prompt = data.get("prompt", "")
    images = data.get("images", [])
    
    if not prompt and not images:
        return jsonify({"error": "Prompt or image required"}), 400
    
    saved_images_paths = []
    if images:
        media_dirs = ["/home/ubuntu/workspace/media", "/root/workspace/media", "/tmp/agent_media"]
        for d in media_dirs:
            os.makedirs(d, exist_ok=True)
            
        for idx, img in enumerate(images):
            try:
                name = img.get("name") or f"screenshot_{int(time.time())}_{idx}.png"
                name = re.sub(r'[^a-zA-Z0-9_.-]', '_', name)
                b64_data = img.get("data", "")
                if "," in b64_data:
                    b64_data = b64_data.split(",", 1)[1]
                raw_bytes = base64.b64decode(b64_data)
                
                for d in media_dirs:
                    dest_file = os.path.join(d, name)
                    with open(dest_file, "wb") as f:
                        f.write(raw_bytes)
                saved_images_paths.append(f"/home/ubuntu/workspace/media/{name}")
                LOG_HISTORY.append({
                    "type": "info",
                    "time": time.strftime("%H:%M:%S"),
                    "text": f"≡ƒô╖ Image received: {name} ({len(raw_bytes)//1024} KB) saved to /home/ubuntu/workspace/media/{name}"
                })
            except Exception as ie:
                LOG_HISTORY.append({
                    "type": "error",
                    "time": time.strftime("%H:%M:%S"),
                    "text": f"Failed to save image: {ie}"
                })

    effective_prompt = prompt
    if saved_images_paths:
        img_refs = "\n".join([f"- {p}" for p in saved_images_paths])
        if prompt:
            effective_prompt = f"[Attached Screenshots/Images]:\n{img_refs}\n\nTask:\n{prompt}"
        else:
            effective_prompt = f"[Attached Screenshots/Images]:\n{img_refs}\n\nTask: Analyze the attached image."

    timestamp = time.strftime("%H:%M:%S")
    CURRENT_TASK = {"prompt": effective_prompt, "start_time": time.time(), "running": True, "images": saved_images_paths}
    LOG_HISTORY.append({"type": "info", "time": timestamp, "text": f">>> Dispatched Task: {effective_prompt}"})
    
    def run_agent():
        global CURRENT_TASK
        engine = get_engine_type()
        try:
            start_new = data.get("new_conversation", False)
            if engine == "antigravity":
                # Antigravity engine: use CDP injection into the Electron app
                inject_into_antigravity(effective_prompt, start_new_conversation=start_new)
                LOG_HISTORY.append({"type": "info", "time": time.strftime("%H:%M:%S"), "text": "Prompt successfully delivered to Antigravity GUI"})
                
                # Monitor language_server.log to track response activity
                log_path = "/root/.config/Antigravity/logs/language_server.log"
                start_offset = os.path.getsize(log_path) if os.path.exists(log_path) else 0
                
                end_time = time.time() + 35
                last_activity = time.time()
                
                while time.time() < end_time:
                    time.sleep(1.5)
                    # Auto-confirm any permission modals (e.g. read access to attached files)
                    confirmed = auto_confirm_permissions()
                    if confirmed:
                        LOG_HISTORY.append({"type": "info", "time": time.strftime("%H:%M:%S"), "text": "Auto-confirmed tool/file permission dialog"})
                        last_activity = time.time()

                    if os.path.exists(log_path):
                        current_size = os.path.getsize(log_path)
                        if current_size > start_offset:
                            with open(log_path, "r", errors="ignore") as f:
                                f.seek(start_offset)
                                new_data = f.read()
                                start_offset = current_size
                                for line in new_data.splitlines():
                                    line_str = line.strip()
                                    if line_str and ("streamGenerateContent" in line_str or "SEND_USER" in line_str or "latency" in line_str):
                                        LOG_HISTORY.append({"type": "output", "time": time.strftime("%H:%M:%S"), "text": line_str[-120:]})
                                        last_activity = time.time()
                    if time.time() - last_activity > 10:
                        break
            else:
                # Non-Antigravity engines: use generic X11 keyboard injection
                x11_inject(effective_prompt)
                LOG_HISTORY.append({"type": "info", "time": time.strftime("%H:%M:%S"), "text": f"Prompt delivered via X11 injection (engine: {engine})"})
        except Exception as err:
            LOG_HISTORY.append({"type": "error", "time": time.strftime("%H:%M:%S"), "text": f"Error during injection: {err}"})
        finally:
            CURRENT_TASK["running"] = False
            LOG_HISTORY.append({"type": "info", "time": time.strftime("%H:%M:%S"), "text": "Task execution completed."})
    
    engine = get_engine_type()
    threading.Thread(target=run_agent, daemon=True).start()
    return jsonify({"success": True, "engine_type": engine, "message": f"Task dispatched (engine: {engine})", "saved_images": saved_images_paths})

@app.route("/restart_desktop", methods=["POST"])
def restart_desktop():
    try:
        subprocess.Popen(["systemctl", "restart", "webdesktop"])
        return jsonify({"success": True, "message": "Desktop service restarting..."})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/configure_engine", methods=["POST"])
def configure_engine():
    """Push a new engine type to this container and optionally restart desktop."""
    data = request.json or {}
    engine = (data.get("engine_type") or data.get("engine") or "").strip().lower()
    restart = data.get("restart_desktop", True)

    if not engine:
        return jsonify({"error": "engine_type is required"}), 400

    valid_engines = ["antigravity", "codex", "hermes", "openclaw", "custom"]
    if engine not in valid_engines:
        return jsonify({"error": f"Unknown engine '{engine}'. Valid: {valid_engines}"}), 400

    try:
        os.makedirs(os.path.dirname(AGENT_TYPE_FILE), exist_ok=True)
        with open(AGENT_TYPE_FILE, "w") as f:
            f.write(engine)
        LOG_HISTORY.append({
            "type": "info",
            "time": time.strftime("%H:%M:%S"),
            "text": f"Engine type updated to '{engine}'"
        })
    except Exception as e:
        return jsonify({"error": f"Failed to write engine type: {e}"}), 500

    if restart:
        try:
            subprocess.Popen(["systemctl", "restart", "webdesktop"])
            LOG_HISTORY.append({
                "type": "info",
                "time": time.strftime("%H:%M:%S"),
                "text": "Restarting webdesktop service for engine change..."
            })
        except Exception as e:
            LOG_HISTORY.append({
                "type": "error",
                "time": time.strftime("%H:%M:%S"),
                "text": f"Failed to restart webdesktop: {e}"
            })

    return jsonify({"success": True, "engine_type": engine, "restarted": restart})

# ------------------------------------------------------------------
# SKILLS MANAGEMENT API
# ------------------------------------------------------------------
@app.route("/skills", methods=["GET"])
def list_skills():
    installed = {}
    for base_dir in SKILL_DIRS:
        if os.path.exists(base_dir):
            for item in os.listdir(base_dir):
                item_path = os.path.join(base_dir, item)
                if os.path.isdir(item_path):
                    skill_md = os.path.join(item_path, "SKILL.md")
                    if os.path.exists(skill_md):
                        desc = "Custom skill loaded"
                        try:
                            with open(skill_md, "r", encoding="utf-8", errors="ignore") as f:
                                for line in f:
                                    if line.strip().startswith("description:"):
                                        desc = line.split(":", 1)[1].strip().strip("\"'")
                                        break
                        except Exception:
                            pass
                        
                        installed[item] = {
                            "name": item,
                            "path": item_path,
                            "description": desc[:160] + ("..." if len(desc) > 160 else ""),
                            "is_builtin": "builtin" in base_dir
                        }
    return jsonify({"skills": list(installed.values())})

@app.route("/skills/install", methods=["POST"])
def install_skill():
    data = request.json or {}
    skill_name = data.get("name", "").strip()
    files = data.get("files", {}) # {"relpath": "content_b64_or_str"}
    content = data.get("content", "") # direct SKILL.md content
    
    if not skill_name:
        return jsonify({"error": "Skill name required"}), 400

    try:
        target_dirs = [
            f"/root/.gemini/skills/{skill_name}",
            f"/root/.gemini/config/skills/{skill_name}",
            f"/home/ubuntu/.gemini/skills/{skill_name}"
        ]

        for tdir in target_dirs:
            os.makedirs(tdir, exist_ok=True)
            if files:
                for rel_path, f_content in files.items():
                    dest_file = os.path.join(tdir, rel_path)
                    os.makedirs(os.path.dirname(dest_file), exist_ok=True)
                    if isinstance(f_content, str):
                        try:
                            decoded = base64.b64decode(f_content)
                            with open(dest_file, "wb") as f:
                                f.write(decoded)
                        except Exception:
                            with open(dest_file, "w", encoding="utf-8") as f:
                                f.write(f_content)
            elif content:
                with open(os.path.join(tdir, "SKILL.md"), "w", encoding="utf-8") as f:
                    f.write(content)

        LOG_HISTORY.append({
            "type": "info",
            "time": time.strftime("%H:%M:%S"),
            "text": f"Skill '{skill_name}' successfully loaded into agent environment!"
        })
        return jsonify({"success": True, "message": f"Skill '{skill_name}' installed successfully"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/skills/install_archive", methods=["POST"])
def install_skills_archive():
    data = request.json or {}
    b64_archive = data.get("archive")
    if not b64_archive:
        return jsonify({"error": "Missing archive data"}), 400
    try:
        raw_tar = base64.b64decode(b64_archive)
        tar_stream = io.BytesIO(raw_tar)
        with tarfile.open(fileobj=tar_stream, mode="r:gz") as tar:
            for dest_root in ["/root/.gemini/skills", "/root/.gemini/config/skills", "/home/ubuntu/.gemini/skills"]:
                os.makedirs(dest_root, exist_ok=True)
                tar.extractall(dest_root)

        LOG_HISTORY.append({
            "type": "info",
            "time": time.strftime("%H:%M:%S"),
            "text": "Master skills library batch installed successfully!"
        })
        return jsonify({"success": True, "message": "Skills library installed successfully"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/skills/<name>", methods=["DELETE"])
def remove_skill(name):
    target_dirs = [
        f"/root/.gemini/skills/{name}",
        f"/root/.gemini/config/skills/{name}",
        f"/home/ubuntu/.gemini/skills/{name}"
    ]
    removed = False
    for tdir in target_dirs:
        if os.path.exists(tdir):
            shutil.rmtree(tdir, ignore_errors=True)
            removed = True
    if removed:
        LOG_HISTORY.append({
            "type": "info",
            "time": time.strftime("%H:%M:%S"),
            "text": f"Skill '{name}' uninstalled."
        })
        return jsonify({"success": True, "message": f"Skill '{name}' removed"})
    return jsonify({"error": f"Skill '{name}' not found"}), 404

@app.route("/skills/<name>/export", methods=["GET"])
def export_skill(name):
    # Find skill directory
    skill_path = None
    for base_dir in SKILL_DIRS:
        cand = os.path.join(base_dir, name)
        if os.path.isdir(cand) and os.path.exists(os.path.join(cand, "SKILL.md")):
            skill_path = cand
            break

    if not skill_path:
        return jsonify({"error": f"Skill '{name}' not found on agent"}), 404

    files = {}
    for root, dirs, filenames in os.walk(skill_path):
        for fn in filenames:
            fp = os.path.join(root, fn)
            rel = os.path.relpath(fp, skill_path)
            try:
                with open(fp, "rb") as f:
                    files[rel] = base64.b64encode(f.read()).decode("utf-8")
            except Exception:
                pass

    return jsonify({"name": name, "files": files})

# ------------------------------------------------------------------
# WORKSPACE MANAGEMENT API
# ------------------------------------------------------------------
AGENT_WORKSPACE_PATHS = ["/home/ubuntu/workspace", "/root/workspace"]

def get_primary_workspace():
    for p in AGENT_WORKSPACE_PATHS:
        if os.path.exists(os.path.dirname(p)):
            return p
    return "/home/ubuntu/workspace"

def ensure_workspace_agent_binding(primary_ws, ws_name="Active Project"):
    """
    Ensure the active workspace is properly bound to Antigravity and agent tools:
    1. Write .agents/rules/cockpit_workspace.md (Antigravity Customization System)
    2. Write AGENTS.md and PROJECT.md if missing
    3. Trigger Antigravity IDE to open/focus /home/ubuntu/workspace
    """
    try:
        rules_dir = os.path.join(primary_ws, ".agents", "rules")
        os.makedirs(rules_dir, exist_ok=True)
        rule_file = os.path.join(rules_dir, "cockpit_workspace.md")
        rule_content = f"""---
name: cockpit-workspace-context
description: Enforces that the agent acts within the active Cockpit workspace directory.
---

# Active Workspace Environment
- **Workspace Name**: {ws_name}
- **Workspace Root**: {primary_ws}

## Operational Directives
1. **Root Directory**: All file creations, edits, linting, tests, and terminal commands must operate inside `{primary_ws}`.
2. **Relative Paths**: Always resolve relative file references against `{primary_ws}`.
3. **No Unrelated Modifications**: Do not modify files outside `{primary_ws}` unless explicitly requested.
"""
        with open(rule_file, "w", encoding="utf-8") as f:
            f.write(rule_content)

        agents_md = os.path.join(primary_ws, "AGENTS.md")
        if not os.path.exists(agents_md):
            with open(agents_md, "w", encoding="utf-8") as f:
                f.write(f"# Project Instructions for AI Agents\\n\\nActive workspace: {ws_name}\\nRoot: {primary_ws}\\nExecute all tools and tests inside this workspace directory.\\n")
    except Exception as e:
        print(f"[Warning] Failed to write workspace agent rules: {e}")

    try:
        if os.path.exists("/usr/local/bin/antigravity") or os.path.exists("/home/ubuntu/opt/Antigravity-x64/antigravity"):
            subprocess.run(
                ["su", "-", "ubuntu", "-c", f"DISPLAY=:1 /usr/local/bin/antigravity -r {primary_ws}"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5, check=False
            )
    except Exception:
        pass

@app.route("/workspace/deploy", methods=["POST"])
def deploy_workspace():
    data = request.get_json(force=True, silent=True) or {}
    b64_archive = data.get("archive")
    ws_name = data.get("workspace_name", "unnamed_workspace")
    ws_id = data.get("workspace_id", "ws_default")
    clean_first = bool(data.get("clean_first", False))

    if not b64_archive:
        return jsonify({"error": "Missing archive data"}), 400

    try:
        raw_tar = base64.b64decode(b64_archive)
        tar_stream = io.BytesIO(raw_tar)

        primary_ws = get_primary_workspace()
        
        for ws_dir in AGENT_WORKSPACE_PATHS:
            try:
                os.makedirs(ws_dir, exist_ok=True)
                if clean_first:
                    for item in os.listdir(ws_dir):
                        if item == "media":
                            continue
                        ipath = os.path.join(ws_dir, item)
                        if os.path.isdir(ipath):
                            shutil.rmtree(ipath, ignore_errors=True)
                        else:
                            try:
                                os.remove(ipath)
                            except Exception:
                                pass
            except Exception:
                pass

        # Extract archive into primary workspace
        tar_stream.seek(0)
        with tarfile.open(fileobj=tar_stream, mode="r:gz") as tar:
            tar.extractall(primary_ws)

        # Also mirror or copy to secondary if separate
        for ws_dir in AGENT_WORKSPACE_PATHS:
            if ws_dir != primary_ws and os.path.exists(os.path.dirname(ws_dir)):
                try:
                    tar_stream.seek(0)
                    with tarfile.open(fileobj=tar_stream, mode="r:gz") as tar:
                        tar.extractall(ws_dir)
                except Exception:
                    pass

        # Write workspace manifest
        meta = {
            "workspace_id": ws_id,
            "workspace_name": ws_name,
            "deployed_at": time.time(),
            "deployed_time": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        for ws_dir in AGENT_WORKSPACE_PATHS:
            try:
                meta_file = os.path.join(ws_dir, ".cockpit_workspace.json")
                with open(meta_file, "w", encoding="utf-8") as f:
                    json.dump(meta, f, indent=2)
            except Exception:
                pass

        # Try adjusting permissions for ubuntu user
        try:
            subprocess.run(["chown", "-R", "ubuntu:ubuntu", "/home/ubuntu/workspace"], check=False)
            subprocess.run(["chmod", "-R", "u+rw", "/home/ubuntu/workspace"], check=False)
        except Exception:
            pass

        # Bind workspace to Antigravity and agent configuration
        ensure_workspace_agent_binding(primary_ws, ws_name)

        # Count extracted files
        file_count = 0
        total_size = 0
        for root, dirs, files in os.walk(primary_ws):
            dirs[:] = [d for d in dirs if d not in [".git", "node_modules", "__pycache__"]]
            file_count += len(files)
            for f in files:
                try:
                    total_size += os.path.getsize(os.path.join(root, f))
                except Exception:
                    pass

        LOG_HISTORY.append({
            "type": "info",
            "time": time.strftime("%H:%M:%S"),
            "text": f"💼 Project workspace '{ws_name}' ({file_count} files, {total_size // 1024} KB) deployed to {primary_ws}"
        })

        return jsonify({
            "success": True,
            "message": f"Workspace '{ws_name}' deployed successfully",
            "workspace_id": ws_id,
            "workspace_name": ws_name,
            "file_count": file_count,
            "size_bytes": total_size,
            "path": primary_ws
        })
    except Exception as e:
        LOG_HISTORY.append({
            "type": "error",
            "time": time.strftime("%H:%M:%S"),
            "text": f"Failed to deploy workspace '{ws_name}': {e}"
        })
        return jsonify({"error": str(e)}), 500

@app.route("/workspace/status", methods=["GET"])
def workspace_status():
    primary_ws = get_primary_workspace()
    meta_path = os.path.join(primary_ws, ".cockpit_workspace.json")
    meta = {}
    if os.path.exists(meta_path):
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
        except Exception:
            pass

    file_count = 0
    total_size = 0
    if os.path.exists(primary_ws):
        for root, dirs, files in os.walk(primary_ws):
            dirs[:] = [d for d in dirs if d not in [".git", "node_modules", "__pycache__"]]
            file_count += len(files)
            for f in files:
                try:
                    total_size += os.path.getsize(os.path.join(root, f))
                except Exception:
                    pass

    return jsonify({
        "active": bool(meta.get("workspace_id")),
        "workspace_id": meta.get("workspace_id"),
        "workspace_name": meta.get("workspace_name", "Default Workspace"),
        "deployed_at": meta.get("deployed_at"),
        "deployed_time": meta.get("deployed_time"),
        "file_count": file_count,
        "size_bytes": total_size,
        "path": primary_ws
    })

@app.route("/workspace/export", methods=["GET"])
def export_workspace():
    primary_ws = get_primary_workspace()
    if not os.path.exists(primary_ws):
        return jsonify({"error": "Workspace directory not found"}), 404

    try:
        tar_buf = io.BytesIO()
        with tarfile.open(fileobj=tar_buf, mode="w:gz") as tar:
            for item in os.listdir(primary_ws):
                if item in [".git", "node_modules", "__pycache__"]:
                    continue
                ipath = os.path.join(primary_ws, item)
                tar.add(ipath, arcname=item)
        
        tar_buf.seek(0)
        b64_data = base64.b64encode(tar_buf.read()).decode("utf-8")
        return jsonify({
            "success": True,
            "archive": b64_data,
            "path": primary_ws
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/workspace/clean", methods=["POST"])
def clean_workspace():
    primary_ws = get_primary_workspace()
    cleaned = 0
    if os.path.exists(primary_ws):
        for item in os.listdir(primary_ws):
            if item == "media":
                continue
            ipath = os.path.join(primary_ws, item)
            try:
                if os.path.isdir(ipath):
                    shutil.rmtree(ipath, ignore_errors=True)
                else:
                    os.remove(ipath)
                cleaned += 1
            except Exception:
                pass
    LOG_HISTORY.append({
        "type": "info",
        "time": time.strftime("%H:%M:%S"),
        "text": f"🧹 Workspace cleaned ({cleaned} items removed)"
    })
    return jsonify({"success": True, "cleaned_items": cleaned})

@app.route("/workspace/git_clone", methods=["POST"])
def workspace_git_clone():
    data = request.get_json(force=True, silent=True) or {}
    raw_repo_url = (data.get("repo_url") or "").strip()
    branch = (data.get("branch") or "").strip()
    ws_name = (data.get("workspace_name") or "").strip()
    ws_id = data.get("workspace_id") or f"ws_git_{int(time.time())}"
    token = (data.get("token") or "").strip()
    clean_first = bool(data.get("clean_first", True))

    if not raw_repo_url:
        return jsonify({"error": "Repository URL is required"}), 400

    repo_url = raw_repo_url
    if not (repo_url.startswith("http://") or repo_url.startswith("https://") or repo_url.startswith("git@") or repo_url.startswith("ssh://")):
        parts = repo_url.split("/")
        if len(parts) == 2 and "." not in parts[0]:
            repo_url = f"https://github.com/{parts[0]}/{parts[1]}.git"

    clone_url = repo_url
    safe_url = repo_url
    if token:
        if "github.com" in repo_url:
            clean = re.sub(r'https?://([^@]+@)?github\.com/', '', repo_url)
            clone_url = f"https://{token}@github.com/{clean}"
        elif "gitlab.com" in repo_url:
            clean = re.sub(r'https?://([^@]+@)?gitlab\.com/', '', repo_url)
            clone_url = f"https://oauth2:{token}@gitlab.com/{clean}"

    if not ws_name:
        clean = safe_url.rstrip("/").split("/")[-1]
        if clean.endswith(".git"):
            clean = clean[:-4]
        ws_name = clean or f"git_repo_{int(time.time())}"

    primary_ws = get_primary_workspace()

    try:
        for ws_dir in AGENT_WORKSPACE_PATHS:
            os.makedirs(ws_dir, exist_ok=True)
            if clean_first:
                for item in os.listdir(ws_dir):
                    if item == "media":
                        continue
                    ipath = os.path.join(ws_dir, item)
                    if os.path.isdir(ipath):
                        shutil.rmtree(ipath, ignore_errors=True)
                    else:
                        try:
                            os.remove(ipath)
                        except Exception:
                            pass

        cmd = ["git", "clone", "--depth", "1"]
        if branch:
            cmd.extend(["--branch", branch])
        cmd.extend([clone_url, primary_ws])

        res = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if res.returncode != 0:
            err_msg = res.stderr or res.stdout
            if token:
                err_msg = err_msg.replace(token, "******")
            return jsonify({"error": f"Agent Git clone failed: {err_msg}"}), 400

        try:
            subprocess.run(["chown", "-R", "ubuntu:ubuntu", "/home/ubuntu/workspace"], check=False)
            subprocess.run(["chmod", "-R", "u+rw", "/home/ubuntu/workspace"], check=False)
        except Exception:
            pass

        # Bind workspace to Antigravity and agent configuration
        ensure_workspace_agent_binding(primary_ws, ws_name)

        manifest = {
            "workspace_id": ws_id,
            "workspace_name": ws_name,
            "source": "git",
            "git_url": safe_url,
            "deployed_at": time.time(),
            "deployed_time": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        for ws_dir in AGENT_WORKSPACE_PATHS:
            try:
                with open(os.path.join(ws_dir, ".cockpit_workspace.json"), "w", encoding="utf-8") as mf:
                    json.dump(manifest, mf, indent=2)
            except Exception:
                pass

        file_count = 0
        total_size = 0
        for root, dirs, files in os.walk(primary_ws):
            dirs[:] = [d for d in dirs if d not in [".git", "node_modules", "__pycache__"]]
            file_count += len(files)
            for f in files:
                try:
                    total_size += os.path.getsize(os.path.join(root, f))
                except Exception:
                    pass

        LOG_HISTORY.append({
            "type": "info",
            "time": time.strftime("%H:%M:%S"),
            "text": f"🌿 Git repository '{ws_name}' ({file_count} files) cloned into {primary_ws}"
        })

        return jsonify({
            "success": True,
            "message": f"Git repository '{ws_name}' cloned successfully into agent",
            "workspace_id": ws_id,
            "workspace_name": ws_name,
            "file_count": file_count,
            "size_bytes": total_size,
            "path": primary_ws
        })
    except Exception as e:
        err_msg = str(e)
        if token:
            err_msg = err_msg.replace(token, "******")
        LOG_HISTORY.append({
            "type": "error",
            "time": time.strftime("%H:%M:%S"),
            "text": f"Failed to git clone into workspace: {err_msg}"
        })
        return jsonify({"error": err_msg}), 500

@app.route("/workspace/git_pull", methods=["POST"])
def workspace_git_pull():
    primary_ws = get_primary_workspace()
    if not os.path.exists(os.path.join(primary_ws, ".git")):
        return jsonify({"error": "Active workspace is not a Git repository"}), 400

    try:
        res = subprocess.run(["git", "-C", primary_ws, "pull"], capture_output=True, text=True, timeout=60)
        if res.returncode != 0:
            return jsonify({"error": f"Agent Git pull failed: {res.stderr or res.stdout}"}), 400

        try:
            subprocess.run(["chown", "-R", "ubuntu:ubuntu", "/home/ubuntu/workspace"], check=False)
            subprocess.run(["chmod", "-R", "u+rw", "/home/ubuntu/workspace"], check=False)
        except Exception:
            pass

        LOG_HISTORY.append({
            "type": "info",
            "time": time.strftime("%H:%M:%S"),
            "text": "🌿 Pulled latest changes from remote Git repository"
        })

        return jsonify({"success": True, "output": res.stdout.strip()})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/git/credentials", methods=["POST"])
def set_git_credentials():
    data = request.get_json(force=True, silent=True) or {}
    token = (data.get("token") or "").strip()
    username = (data.get("username") or "").strip() or "Antigravity Agent"
    email = (data.get("email") or "").strip() or "agent@antigravity.cockpit"
    provider = (data.get("provider") or "github.com").strip()

    errors = []
    for user in ["root", "ubuntu"]:
        try:
            home = "/root" if user == "root" else "/home/ubuntu"
            if not os.path.exists(home):
                continue

            if user == "root":
                subprocess.run(["git", "config", "--global", "user.name", username], check=False)
                subprocess.run(["git", "config", "--global", "user.email", email], check=False)
                subprocess.run(["git", "config", "--global", "credential.helper", "store"], check=False)
            else:
                subprocess.run(["su", "-", "ubuntu", "-c", f"git config --global user.name '{username}'"], check=False)
                subprocess.run(["su", "-", "ubuntu", "-c", f"git config --global user.email '{email}'"], check=False)
                subprocess.run(["su", "-", "ubuntu", "-c", "git config --global credential.helper store"], check=False)

            if token:
                cred_file = os.path.join(home, ".git-credentials")
                cred_line = f"https://{username}:{token}@{provider}\n"
                existing = ""
                if os.path.exists(cred_file):
                    with open(cred_file, "r", encoding="utf-8", errors="ignore") as f:
                        existing = f.read()
                if f"@{provider}" not in existing:
                    with open(cred_file, "a+", encoding="utf-8") as f:
                        f.write(cred_line)
                try:
                    os.chmod(cred_file, 0o600)
                    if user == "ubuntu":
                        subprocess.run(["chown", "ubuntu:ubuntu", cred_file], check=False)
                except Exception:
                    pass
        except Exception as e:
            errors.append(f"{user}: {e}")

    LOG_HISTORY.append({
        "type": "info",
        "time": time.strftime("%H:%M:%S"),
        "text": f"🔑 Configured Git credentials for author '{username}' <{email}>"
    })

    if errors:
        return jsonify({"success": False, "errors": errors}), 500
    return jsonify({"success": True, "username": username, "email": email})

@app.route("/workspace/git_commit", methods=["POST"])
def workspace_git_commit():
    primary_ws = get_primary_workspace()
    if not os.path.exists(os.path.join(primary_ws, ".git")):
        return jsonify({"error": "Active workspace is not a Git repository"}), 400

    data = request.get_json(force=True, silent=True) or {}
    message = (data.get("message") or "").strip() or f"Update from agent at {time.strftime('%Y-%m-%d %H:%M:%S')}"
    author_name = (data.get("author_name") or "").strip()
    author_email = (data.get("author_email") or "").strip()

    try:
        s_res = subprocess.run(["git", "-C", primary_ws, "status", "--porcelain"], capture_output=True, text=True, timeout=10)
        if not s_res.stdout.strip():
            return jsonify({"success": True, "message": "No changes to commit", "committed": False})

        subprocess.run(["git", "-C", primary_ws, "add", "-A"], check=True, timeout=15)

        cmd = ["git", "-C", primary_ws, "commit", "-m", message]
        if author_name and author_email:
            cmd.append(f"--author={author_name} <{author_email}>")

        res = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
        if res.returncode != 0:
            return jsonify({"error": f"Git commit failed: {res.stderr or res.stdout}"}), 400

        log_res = subprocess.run(["git", "-C", primary_ws, "log", "-1", "--format=%h|%s"], capture_output=True, text=True, timeout=5)
        commit_info = log_res.stdout.strip()

        LOG_HISTORY.append({
            "type": "info",
            "time": time.strftime("%H:%M:%S"),
            "text": f"🌿 Git commit created: {commit_info}"
        })

        return jsonify({"success": True, "committed": True, "commit": commit_info, "output": res.stdout.strip()})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/workspace/git_push", methods=["POST"])
def workspace_git_push():
    primary_ws = get_primary_workspace()
    if not os.path.exists(os.path.join(primary_ws, ".git")):
        return jsonify({"error": "Active workspace is not a Git repository"}), 400

    data = request.get_json(force=True, silent=True) or {}
    branch = (data.get("branch") or "").strip()
    remote = (data.get("remote") or "origin").strip()

    try:
        if not branch:
            b_res = subprocess.run(["git", "-C", primary_ws, "rev-parse", "--abbrev-ref", "HEAD"], capture_output=True, text=True, timeout=5)
            branch = b_res.stdout.strip() if b_res.returncode == 0 else "main"

        cmd = ["git", "-C", primary_ws, "push", remote, branch]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if res.returncode != 0:
            return jsonify({"error": f"Agent Git push failed: {res.stderr or res.stdout}"}), 400

        LOG_HISTORY.append({
            "type": "info",
            "time": time.strftime("%H:%M:%S"),
            "text": f"🌿 Pushed workspace commits to {remote}/{branch}"
        })

        return jsonify({"success": True, "remote": remote, "branch": branch, "output": res.stdout.strip()})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/workspace/git_status", methods=["GET"])
def workspace_git_status():
    primary_ws = get_primary_workspace()
    if not os.path.exists(os.path.join(primary_ws, ".git")):
        return jsonify({"is_git": False})

    try:
        b_res = subprocess.run(["git", "-C", primary_ws, "rev-parse", "--abbrev-ref", "HEAD"], capture_output=True, text=True, timeout=5)
        branch = b_res.stdout.strip() if b_res.returncode == 0 else "main"

        s_res = subprocess.run(["git", "-C", primary_ws, "status", "-s"], capture_output=True, text=True, timeout=5)
        status_text = s_res.stdout.strip()

        log_res = subprocess.run(["git", "-C", primary_ws, "log", "-1", "--format=%h|%s|%an|%ci"], capture_output=True, text=True, timeout=5)
        last_commit = log_res.stdout.strip()

        return jsonify({
            "is_git": True,
            "branch": branch,
            "has_changes": bool(status_text),
            "status_summary": status_text,
            "last_commit": last_commit
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)

