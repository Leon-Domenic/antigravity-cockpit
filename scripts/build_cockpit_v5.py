# Build script for cockpit_server_v5: Send Screenshots & Pics to Agents
import re, json

with open("cockpit_server.py", "r", encoding="utf-8") as f:
    code = f.read()

# 1. Update Task Dispatcher Card HTML
old_dispatcher_input = """                        <!-- Prompt Input -->
                        <div>
                            <textarea id="dedicated-prompt-input" rows="3" placeholder="Enter instructions for this agent (e.g. Build the responsive navbar and test with Vitest)..." class="w-full input-box rounded-xl p-3 text-xs focus:outline-none focus:border-slate-400"></textarea>
                        </div>

                        <div class="flex justify-end">
                            <button onclick="dispatchDedicatedTask()" class="px-4 py-2 btn-action-primary font-semibold rounded-xl text-xs transition shadow-lg flex items-center gap-2">
                                <i class="fa-solid fa-bolt"></i> Dispatch Task
                            </button>
                        </div>"""

new_dispatcher_input = """                        <!-- Prompt Input & Attachment Drop Zone -->
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
                                
                                <span class="text-[10px] text-slate-500 font-mono hidden sm:inline">&bull; Ctrl+V to paste</span>
                            </div>

                            <button onclick="dispatchDedicatedTask()" id="btn-dispatch-task" class="px-4 py-2 btn-action-primary font-semibold rounded-xl text-xs transition shadow-lg flex items-center gap-2">
                                <i class="fa-solid fa-bolt"></i> Dispatch Task
                            </button>
                        </div>"""

assert old_dispatcher_input in code, "old_dispatcher_input not found"
code = code.replace(old_dispatcher_input, new_dispatcher_input)

# 2. Update Global Broadcast Dispatcher Card HTML
old_broadcast_input = """                <div class="flex gap-3">
                    <input id="broadcast-prompt-input" type="text" placeholder="Broadcast a task to all active agents simultaneously..." class="flex-1 input-box rounded-xl px-4 py-2.5 text-xs focus:outline-none focus:border-slate-400" onkeydown="if(event.key==='Enter') dispatchBroadcast()">
                    <button onclick="dispatchBroadcast()" class="px-5 py-2.5 btn-action-primary font-semibold rounded-xl text-xs transition shadow-lg flex items-center gap-2 flex-shrink-0">
                        <i class="fa-solid fa-tower-broadcast"></i> Broadcast
                    </button>
                </div>"""

new_broadcast_input = """                <!-- Broadcast Image Attachment Tray -->
                <div id="broadcast-images-tray" class="hidden px-2 py-2 flex flex-wrap gap-2 items-center rounded-xl border mb-2" style="background-color: var(--bg-input); border-color: var(--border-base);">
                </div>

                <div class="flex gap-2 items-center">
                    <input type="file" id="broadcast-image-file-input" accept="image/*" multiple class="hidden" onchange="handleBroadcastImageSelect(this.files)">
                    <button type="button" onclick="document.getElementById('broadcast-image-file-input').click()" class="px-3 py-2.5 border rounded-xl text-xs transition flex items-center gap-1.5 text-slate-300 hover:text-white flex-shrink-0" style="background-color: var(--bg-input); border-color: var(--border-base);" title="Attach screenshot or picture to broadcast">
                        <i class="fa-solid fa-paperclip text-amber-400"></i>
                    </button>
                    <input id="broadcast-prompt-input" type="text" placeholder="Broadcast a task to all active agents simultaneously (paste screenshots with Ctrl+V)..." class="flex-1 input-box rounded-xl px-4 py-2.5 text-xs focus:outline-none focus:border-slate-400" onkeydown="if(event.key==='Enter') dispatchBroadcast()">
                    <button onclick="dispatchBroadcast()" class="px-5 py-2.5 btn-action-primary font-semibold rounded-xl text-xs transition shadow-lg flex items-center gap-2 flex-shrink-0">
                        <i class="fa-solid fa-tower-broadcast"></i> Broadcast
                    </button>
                </div>"""

assert old_broadcast_input in code, "old_broadcast_input not found"
code = code.replace(old_broadcast_input, new_broadcast_input)

# 3. Add Lightbox Image Preview Modal right before </main>
lightbox_html = """
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
"""

main_tag_search = "    </main>"
assert main_tag_search in code, "main_tag_search not found"
code = code.replace(main_tag_search, lightbox_html + "\n" + main_tag_search)

# 4. Replace dispatchDedicatedTask and dispatchBroadcast with image-capable versions
old_dispatch_funcs = """        async function dispatchDedicatedTask() {
            const prompt = document.getElementById("dedicated-prompt-input").value.trim();
            if (!prompt) return alert("Please enter a task description.");

            const res = await fetch("/api/dispatch", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ prompt, target: currentView })
            });
            const data = await res.json();
            document.getElementById("dedicated-prompt-input").value = "";
            fetchCurrentLogs();
            fetchAllStatus();
        }

        async function dispatchBroadcast() {
            const prompt = document.getElementById("broadcast-prompt-input").value.trim();
            if (!prompt) return alert("Please enter a prompt to broadcast.");

            const res = await fetch("/api/dispatch", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ prompt, target: "broadcast" })
            });
            const data = await res.json();
            alert("Broadcast sent to all active agents!");
            document.getElementById("broadcast-prompt-input").value = "";
            fetchAllStatus();
        }"""

new_dispatch_funcs = """        // ============================================================
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

            try {
                const res = await fetch("/api/dispatch", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ target: currentView, prompt, images: imagesPayload })
                });
                const data = await res.json();
                if (data.success) {
                    input.value = "";
                    attachedImages = [];
                    renderAttachedImages();
                    fetchCurrentLogs();
                    fetchAllStatus();
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

            try {
                const res = await fetch("/api/dispatch", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ target: "broadcast", prompt, images: imagesPayload })
                });
                const data = await res.json();
                if (data.success) {
                    input.value = "";
                    broadcastImages = [];
                    renderBroadcastImages();
                    alert("Broadcast with attachments sent to active agents!");
                    fetchAllStatus();
                } else {
                    alert(data.error || "Broadcast failed");
                }
            } catch (e) {
                alert("Broadcast error: " + e.message);
            }
        }"""

assert old_dispatch_funcs in code, "old_dispatch_funcs not found"
code = code.replace(old_dispatch_funcs, new_dispatch_funcs)

# 5. Update Backend Route /api/dispatch to forward images & Add /api/agent/screenshot
old_backend_dispatch = """@app.route("/api/dispatch", methods=["POST"])
def dispatch_task():
    data = request.json or {}
    target = data.get("target", "agent-1")
    prompt = data.get("prompt", "")
    
    targets = [a for a in AGENTS if (target == "broadcast" or a["id"] == target)]
    responses = []
    for a in targets:
        try:
            r = requests.post(f"http://{a['ip']}:{a['port']}/dispatch", json={"prompt": prompt}, timeout=3)
            responses.append({a["id"]: r.json()})
        except Exception as e:
            responses.append({a["id"]: {"error": str(e)}})
            
    return jsonify({"success": True, "message": f"Task dispatched", "responses": responses})"""

new_backend_dispatch = """@app.route("/api/agent/screenshot", methods=["GET"])
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

@app.route("/api/dispatch", methods=["POST"])
def dispatch_task():
    data = request.json or {}
    target = data.get("target", "agent-1")
    prompt = data.get("prompt", "")
    images = data.get("images", [])
    
    targets = [a for a in AGENTS if (target == "broadcast" or a["id"] == target)]
    responses = []
    for a in targets:
        try:
            payload = {"prompt": prompt, "images": images}
            r = requests.post(f"http://{a['ip']}:{a['port']}/dispatch", json=payload, timeout=8)
            responses.append({a["id"]: r.json()})
        except Exception as e:
            responses.append({a["id"]: {"error": str(e)}})
            
    return jsonify({"success": True, "message": f"Task dispatched", "responses": responses})"""

assert old_backend_dispatch in code, "old_backend_dispatch not found"
code = code.replace(old_backend_dispatch, new_backend_dispatch)

with open("cockpit_server_v5.py", "w", encoding="utf-8") as f:
    f.write(code)

print("cockpit_server_v5.py generated successfully!")
