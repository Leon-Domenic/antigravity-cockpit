"use client";

import { useState } from "react";
import { useQuery } from "convex/react";
import { useLanguage } from "@/contexts/LanguageContext";
import { api } from "@/convex/_generated/api";
import { 
  Server, 
  Tv, 
  RefreshCw, 
  Play, 
  Square, 
  ExternalLink, 
  CheckCircle2, 
  AlertCircle,
  Cpu,
  MonitorPlay,
  Terminal,
  X,
  LayoutGrid,
  Monitor,
  Maximize2,
  Send,
  Sparkles,
  Radio,
  Layers,
  FolderTree
} from "lucide-react";
import { QueryErrorBoundary } from "@/components/QueryErrorBoundary";

interface AgentDef {
  agentId: string;
  vmid: number;
  name: string;
  type: string;
  vmType: string;
  role: string;
  ip: string;
  port: number;
  vncPort: number;
  status: string;
}

const DEFAULT_AGENTS: AgentDef[] = [
  {
    agentId: "agent-1",
    vmid: 151,
    name: "Webigo Prime",
    type: "antigravity",
    vmType: "lxc",
    role: "Architecture & Core Logic",
    ip: "192.168.178.169",
    port: 8000,
    vncPort: 6080,
    status: "running",
  },
  {
    agentId: "agent-2",
    vmid: 152,
    name: "Webigo SecOps",
    type: "antigravity",
    vmType: "lxc",
    role: "Code Review & Security Audits",
    ip: "192.168.178.170",
    port: 8000,
    vncPort: 6080,
    status: "running",
  },
  {
    agentId: "agent-3",
    vmid: 153,
    name: "Codex Engine",
    type: "codex",
    vmType: "lxc",
    role: "API Integration & Test Automation",
    ip: "192.168.178.171",
    port: 8000,
    vncPort: 6080,
    status: "running",
  },
  {
    agentId: "agent-4",
    vmid: 154,
    name: "Hermes Autonomous (CT 154)",
    type: "hermes",
    vmType: "lxc",
    role: "End-to-End Execution & Self-Correction",
    ip: "192.168.178.172",
    port: 8000,
    vncPort: 6080,
    status: "running",
  },
  {
    agentId: "agent-5",
    vmid: 155,
    name: "Open Claw Research",
    type: "open-claw",
    vmType: "qemu",
    role: "Deep Research & Multi-Modal Browser",
    ip: "192.168.178.173",
    port: 8000,
    vncPort: 6080,
    status: "idle",
  },
];

function FleetWithQuery() {
  const convexAgents = useQuery(api.agents.listAgents);
  return <FleetView rawAgents={convexAgents} />;
}

export default function FleetPage() {
  return (
    <QueryErrorBoundary fallback={<FleetView rawAgents={null} />}>
      <FleetWithQuery />
    </QueryErrorBoundary>
  );
}

function FleetView({ rawAgents }: { rawAgents: any[] | undefined | null }) {
  const { t } = useLanguage();
  const [viewMode, setViewMode] = useState<"matrix" | "focus" | "cards">("matrix");
  const [selectedFocusAgentId, setSelectedFocusAgentId] = useState<string>("agent-1");
  const [theaterAgent, setTheaterAgent] = useState<any | null>(null);
  const [useDirectLan, setUseDirectLan] = useState(false);
  const [statusNotice, setStatusNotice] = useState<string | null>(null);
  const [reloadKeys, setReloadKeys] = useState<{ [key: string]: number }>({});

  // Global Broadcast Dispatcher State
  const [broadcastPrompt, setBroadcastPrompt] = useState("");
  const [broadcasting, setBroadcasting] = useState(false);
  const [selectedWorkspace, setSelectedWorkspace] = useState("");

  // Individual agent prompt inputs
  const [agentPrompts, setAgentPrompts] = useState<{ [key: string]: string }>({});
  const [dispatchingId, setDispatchingId] = useState<string | null>(null);
  const [syncingId, setSyncingId] = useState<string | null>(null);

  const agents: AgentDef[] = (rawAgents && rawAgents.length > 0) ? rawAgents : DEFAULT_AGENTS;

  const getVncUrl = (ag: any, direct = false) => {
    if (!ag) return "";
    const vmid = ag.vmid || (ag.id && ag.id.includes("15") ? parseInt(ag.id.replace(/\D/g, "")) : 151);
    const aid = (ag.agentId || ag.id || (ag.vmid ? `agent-${ag.vmid - 150}` : "agent-1")).toLowerCase();

    if (direct || useDirectLan) {
      return `http://${ag.ip || "192.168.178.169"}:${ag.vncPort || 6080}/vnc.html?autoconnect=true&resize=scale`;
    }

    // Proxmox cluster ingress gateway with Cloudflare SSL & WSS
    const routePath = vmid ? `${vmid}` : aid;
    return `https://vnc.webigo.ai/${routePath}/vnc.html?autoconnect=true&resize=scale&path=${routePath}/websockify`;
  };

  const handleReloadStream = (agentId: string) => {
    setReloadKeys(prev => ({ ...prev, [agentId]: (prev[agentId] || 0) + 1 }));
    setStatusNotice(`Reloaded video feed for ${agentId}`);
    setTimeout(() => setStatusNotice(null), 3000);
  };

  const handleBroadcast = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!broadcastPrompt.trim()) return;

    setBroadcasting(true);
    setStatusNotice(null);

    try {
      const res = await fetch("/api/dispatch", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          target: "broadcast",
          prompt: broadcastPrompt.trim(),
          workspace_id: selectedWorkspace || undefined,
        }),
      });
      const data = await res.json();
      setStatusNotice(data.message || "Broadcast dispatched to all active cluster agent bridges!");
      setBroadcastPrompt("");
    } catch (err: any) {
      setStatusNotice(`Broadcast error: ${err.message}`);
    } finally {
      setBroadcasting(false);
      setTimeout(() => setStatusNotice(null), 5000);
    }
  };

  const handleDispatchAgentPrompt = async (agent: AgentDef) => {
    const prompt = agentPrompts[agent.agentId]?.trim();
    if (!prompt) return;

    setDispatchingId(agent.agentId);
    try {
      const res = await fetch("/api/dispatch", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          target: agent.agentId,
          prompt,
          workspace_id: selectedWorkspace || undefined,
        }),
      });
      const data = await res.json();
      setStatusNotice(data.message || `Task dispatched to ${agent.name}`);
      setAgentPrompts(prev => ({ ...prev, [agent.agentId]: "" }));
    } catch (err: any) {
      setStatusNotice(`Dispatch error: ${err.message}`);
    } finally {
      setDispatchingId(null);
      setTimeout(() => setStatusNotice(null), 4000);
    }
  };

  const handleEnsureWorkspace = async (ag: any) => {
    setSyncingId(ag.agentId);
    setStatusNotice(null);
    try {
      const res = await fetch("/api/agents", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action: "bind_workspace",
          agentId: ag.agentId,
          workspaceId: "active-workspace",
        }),
      });
      const data = await res.json();
      setStatusNotice(`Workspace bound to ${ag.name} at /home/ubuntu/workspace`);
    } catch (err: any) {
      setStatusNotice(`Sync status: Bridge responded (${err.message})`);
    } finally {
      setSyncingId(null);
      setTimeout(() => setStatusNotice(null), 4000);
    }
  };

  const focusAgent = agents.find(a => a.agentId === selectedFocusAgentId) || agents[0];

  return (
    <div className="space-y-6 pb-12">
      {/* Top Header & View Switcher */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2.5">
            <Server className="w-6 h-6 text-blue-500" />
            <span>Autonomous Agent Fleet</span>
          </h1>
          <p className="text-xs text-slate-400 mt-1">
            Proxmox VE Cluster (192.168.178.105) • Live Multi-Agent Vision Matrix & Video Passthrough
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2.5">
          {/* View Mode Switcher */}
          <div className="flex items-center p-1 rounded-xl bg-slate-900 border border-slate-800 text-xs">
            <button
              onClick={() => setViewMode("matrix")}
              className={`px-3 py-1.5 rounded-lg font-medium flex items-center gap-1.5 transition-all ${
                viewMode === "matrix"
                  ? "bg-blue-600 text-white shadow-md shadow-blue-600/30"
                  : "text-slate-400 hover:text-white"
              }`}
              title="All agents shown live simultaneously with permanent video passthrough"
            >
              <LayoutGrid className="w-3.5 h-3.5" />
              <span>Live Matrix</span>
            </button>
            <button
              onClick={() => setViewMode("focus")}
              className={`px-3 py-1.5 rounded-lg font-medium flex items-center gap-1.5 transition-all ${
                viewMode === "focus"
                  ? "bg-blue-600 text-white shadow-md shadow-blue-600/30"
                  : "text-slate-400 hover:text-white"
              }`}
              title="Single focused hero stream"
            >
              <Monitor className="w-3.5 h-3.5" />
              <span>Hero Stream</span>
            </button>
            <button
              onClick={() => setViewMode("cards")}
              className={`px-3 py-1.5 rounded-lg font-medium flex items-center gap-1.5 transition-all ${
                viewMode === "cards"
                  ? "bg-blue-600 text-white shadow-md shadow-blue-600/30"
                  : "text-slate-400 hover:text-white"
              }`}
              title="Compact node cards & specs"
            >
              <Layers className="w-3.5 h-3.5" />
              <span>Node Specs</span>
            </button>
          </div>

          {/* Direct LAN vs SSL Gateway Toggle */}
          <button
            onClick={() => setUseDirectLan(!useDirectLan)}
            className={`px-3 py-1.5 rounded-xl border text-xs font-mono transition-all flex items-center gap-1.5 ${
              useDirectLan
                ? "bg-amber-950/40 text-amber-300 border-amber-800/60"
                : "bg-slate-900 text-slate-300 border-slate-800 hover:border-slate-700"
            }`}
            title="Toggle between Cloudflare SSL Gateway (vnc.webigo.ai) and direct local IP"
          >
            <Radio className={`w-3.5 h-3.5 ${useDirectLan ? "text-amber-400" : "text-emerald-400"}`} />
            <span>{useDirectLan ? "LAN Direct Mode" : "SSL Gateway"}</span>
          </button>

          <div className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-slate-900 border border-slate-800 text-xs font-mono text-slate-300">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
            <span>Cluster Healthy (4 Active LXC / 1 KVM)</span>
          </div>
        </div>
      </div>

      {statusNotice && (
        <div className="p-3.5 rounded-xl bg-blue-950/40 border border-blue-800/60 text-xs text-blue-300 flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 text-blue-400 flex-shrink-0" />
          <span>{statusNotice}</span>
        </div>
      )}

      {/* Global Broadcast Dispatcher */}
      <div className="glass-panel p-4 rounded-2xl border border-slate-800/90 shadow-xl space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-lg bg-blue-600/20 border border-blue-500/30 flex items-center justify-center text-blue-400">
              <Radio className="w-4 h-4" />
            </div>
            <h2 className="text-xs font-bold text-white uppercase tracking-wider">
              Global Fleet Broadcast Dispatcher
            </h2>
          </div>
          <span className="text-[11px] font-mono text-slate-500">
            Transmits real-time prompts & context to all running agent bridges simultaneously
          </span>
        </div>

        <form onSubmit={handleBroadcast} className="flex flex-wrap sm:flex-nowrap gap-2 items-center">
          <div className="flex items-center gap-1.5 px-3 py-2 rounded-xl bg-slate-900 border border-slate-800 text-xs text-slate-300 flex-shrink-0">
            <FolderTree className="w-3.5 h-3.5 text-emerald-400" />
            <select
              value={selectedWorkspace}
              onChange={(e) => setSelectedWorkspace(e.target.value)}
              className="bg-transparent text-xs text-slate-200 focus:outline-none cursor-pointer"
            >
              <option value="" className="bg-slate-900 text-slate-400">Default Workspace (/home/ubuntu/workspace)</option>
              <option value="monorepowebigo" className="bg-slate-900 text-slate-200">monorepowebigo</option>
              <option value="antigravity-cockpit" className="bg-slate-900 text-slate-200">antigravity-cockpit</option>
            </select>
          </div>

          <input
            type="text"
            value={broadcastPrompt}
            onChange={(e) => setBroadcastPrompt(e.target.value)}
            placeholder="Broadcast a command, instruction, or goal to all running agents simultaneously..."
            className="flex-1 px-4 py-2 rounded-xl bg-slate-900 border border-slate-800 text-xs text-slate-200 focus:outline-none focus:border-blue-500 font-mono"
          />

          <button
            type="submit"
            disabled={broadcasting || !broadcastPrompt.trim()}
            className="px-4 py-2 rounded-xl bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white font-medium text-xs shadow-lg shadow-blue-600/25 flex items-center gap-1.5 transition-all disabled:opacity-50 flex-shrink-0"
          >
            <Send className="w-3.5 h-3.5" />
            <span>{broadcasting ? "Broadcasting..." : "Broadcast to Fleet"}</span>
          </button>
        </form>
      </div>

      {/* ============================================================ */}
      {/* VIEW 1: LIVE MULTI-AGENT VIDEO MATRIX (PERMANENT STREAMS)    */}
      {/* ============================================================ */}
      {viewMode === "matrix" && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Tv className="w-4 h-4 text-cyan-400" />
              <h3 className="text-xs font-bold text-white uppercase tracking-wider">
                Permanent Live Video Passthrough Matrix
              </h3>
            </div>
            <span className="text-[11px] font-mono text-slate-400">
              Interactive 16:9 Canvas Streams • Encrypted WebSocket Bridge (WSS)
            </span>
          </div>

          <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
            {agents.map((ag) => {
              const isKvm = ag.vmType === "qemu";
              const isRunning = ag.status === "running" || ag.status === "idle";
              const streamUrl = getVncUrl(ag);
              const reloadKey = reloadKeys[ag.agentId] || 0;

              return (
                <div
                  key={ag.agentId}
                  className="glass-panel rounded-2xl overflow-hidden border border-slate-800 shadow-2xl flex flex-col group hover:border-slate-700 transition-all"
                >
                  {/* Stream Card Header */}
                  <div className="px-4 py-2.5 bg-slate-900/90 border-b border-slate-800 flex items-center justify-between">
                    <div className="flex items-center space-x-2.5">
                      <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-pulse"></span>
                      <span className="text-xs font-bold text-white">{ag.name}</span>
                      <span className={`text-[10px] font-mono uppercase px-1.5 py-0.5 rounded font-semibold ${
                        isKvm
                          ? "bg-purple-950/80 text-purple-400 border border-purple-800/60"
                          : "bg-blue-950/80 text-blue-400 border border-blue-800/60"
                      }`}>
                        VMID {ag.vmid} • {isKvm ? "KVM QEMU" : "LXC"}
                      </span>
                      <span className="text-[10px] text-slate-400 font-mono hidden sm:inline">
                        {ag.ip}:{ag.vncPort || 6080}
                      </span>
                    </div>

                    <div className="flex items-center gap-1.5">
                      <span className="text-[10px] font-mono px-1.5 py-0.5 rounded border border-slate-800 text-slate-400">
                        16:9
                      </span>

                      {/* Reload Stream Button */}
                      <button
                        onClick={() => handleReloadStream(ag.agentId)}
                        className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition"
                        title="Reload stream canvas"
                      >
                        <RefreshCw className="w-3.5 h-3.5" />
                      </button>

                      {/* Expand / Theater Fullscreen */}
                      <button
                        onClick={() => setTheaterAgent(ag)}
                        className="px-2 py-1 rounded-lg text-[11px] font-medium text-slate-200 bg-slate-800 hover:bg-slate-700 transition flex items-center gap-1"
                        title="Expand to Fullscreen Theater Mode"
                      >
                        <Maximize2 className="w-3 h-3 text-blue-400" />
                        <span className="hidden sm:inline">Expand</span>
                      </button>

                      {/* Pop-out external tab */}
                      <a
                        href={streamUrl}
                        target="_blank"
                        rel="noreferrer"
                        className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition"
                        title="Open in new independent browser tab"
                      >
                        <ExternalLink className="w-3.5 h-3.5" />
                      </a>
                    </div>
                  </div>

                  {/* Permanent Live Visual Screen (Aspect 16:9) */}
                  <div className="w-full aspect-video bg-black overflow-hidden relative">
                    <iframe
                      key={`${ag.agentId}-${reloadKey}`}
                      src={streamUrl}
                      className="w-full h-full border-0"
                      allow="clipboard-read; clipboard-write; fullscreen"
                    />
                  </div>

                  {/* Stream Card Bottom Command Bar */}
                  <div className="p-3 bg-slate-900/60 border-t border-slate-800/80 flex items-center justify-between gap-3">
                    <div className="flex-1 flex items-center gap-2">
                      <Terminal className="w-3.5 h-3.5 text-blue-400 flex-shrink-0" />
                      <input
                        type="text"
                        value={agentPrompts[ag.agentId] || ""}
                        onChange={(e) => setAgentPrompts({ ...agentPrompts, [ag.agentId]: e.target.value })}
                        onKeyDown={(e) => { if (e.key === "Enter") handleDispatchAgentPrompt(ag); }}
                        placeholder={`Direct task for ${ag.name}...`}
                        className="w-full bg-slate-950/80 border border-slate-800 rounded-lg px-2.5 py-1 text-[11px] font-mono text-slate-200 focus:outline-none focus:border-blue-500"
                      />
                      <button
                        onClick={() => handleDispatchAgentPrompt(ag)}
                        disabled={dispatchingId === ag.agentId || !agentPrompts[ag.agentId]?.trim()}
                        className="px-2.5 py-1 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-[11px] font-semibold transition disabled:opacity-50"
                      >
                        {dispatchingId === ag.agentId ? "..." : "Send"}
                      </button>
                    </div>

                    <button
                      onClick={() => handleEnsureWorkspace(ag)}
                      disabled={syncingId === ag.agentId}
                      className="px-2.5 py-1 rounded-lg bg-slate-900 hover:bg-slate-800 text-slate-400 hover:text-slate-200 border border-slate-800 text-[10px] font-mono flex items-center gap-1 flex-shrink-0"
                      title="Ensure /home/ubuntu/workspace binding"
                    >
                      <FolderTree className="w-3 h-3 text-emerald-400" />
                      <span>{syncingId === ag.agentId ? "Binding..." : "Sync WS"}</span>
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* ============================================================ */}
      {/* VIEW 2: FOCUSED HERO STREAM WITH AGENT SELECTOR              */}
      {/* ============================================================ */}
      {viewMode === "focus" && (
        <div className="space-y-4">
          {/* Agent Switcher Tabs */}
          <div className="flex items-center gap-2 overflow-x-auto pb-1">
            {agents.map((ag) => (
              <button
                key={ag.agentId}
                onClick={() => setSelectedFocusAgentId(ag.agentId)}
                className={`px-4 py-2 rounded-xl text-xs font-semibold flex items-center gap-2 transition-all flex-shrink-0 ${
                  selectedFocusAgentId === ag.agentId
                    ? "bg-blue-600 text-white shadow-lg shadow-blue-600/30"
                    : "bg-slate-900 border border-slate-800 text-slate-400 hover:text-white"
                }`}
              >
                <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
                <span>{ag.name}</span>
                <span className="text-[10px] font-mono opacity-80">VMID {ag.vmid}</span>
              </button>
            ))}
          </div>

          {/* Large Hero Stream */}
          <div className="glass-panel rounded-2xl overflow-hidden border border-slate-800 shadow-2xl flex flex-col">
            <div className="px-5 py-3 bg-slate-900/90 border-b border-slate-800 flex items-center justify-between">
              <div className="flex items-center space-x-3">
                <span className="w-3 h-3 rounded-full bg-emerald-400 animate-pulse"></span>
                <div>
                  <h3 className="text-sm font-bold text-white flex items-center gap-2">
                    <span>{focusAgent.name}</span>
                    <span className="text-xs font-mono text-slate-400">({focusAgent.role})</span>
                  </h3>
                  <p className="text-[11px] font-mono text-slate-400">
                    Host: {focusAgent.ip} • Port :{focusAgent.vncPort || 6080} • VMID {focusAgent.vmid}
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-2">
                <button
                  onClick={() => handleReloadStream(focusAgent.agentId)}
                  className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-xs text-slate-200 flex items-center gap-1.5 transition"
                >
                  <RefreshCw className="w-3.5 h-3.5" />
                  <span>Reload Feed</span>
                </button>
                <button
                  onClick={() => setTheaterAgent(focusAgent)}
                  className="px-3 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-xs text-white font-medium flex items-center gap-1.5 transition shadow"
                >
                  <Maximize2 className="w-3.5 h-3.5" />
                  <span>Theater Mode</span>
                </button>
                <a
                  href={getVncUrl(focusAgent)}
                  target="_blank"
                  rel="noreferrer"
                  className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-xs text-slate-200 flex items-center gap-1.5 transition"
                >
                  <ExternalLink className="w-3.5 h-3.5" />
                  <span>Pop-out</span>
                </a>
              </div>
            </div>

            <div className="w-full aspect-video bg-black overflow-hidden relative">
              <iframe
                key={`${focusAgent.agentId}-${reloadKeys[focusAgent.agentId] || 0}`}
                src={getVncUrl(focusAgent)}
                className="w-full h-full border-0"
                allow="clipboard-read; clipboard-write; fullscreen"
              />
            </div>
          </div>
        </div>
      )}

      {/* ============================================================ */}
      {/* VIEW 3: COMPACT NODE CARDS & SPECIFICATIONS                  */}
      {/* ============================================================ */}
      {viewMode === "cards" && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {agents.map((ag: any) => {
            const isKvm = ag.vmType === "qemu";
            const isRunning = ag.status === "running" || ag.status === "idle";

            return (
              <div
                key={ag.agentId}
                className="glass-panel rounded-2xl border border-slate-800/80 p-5 flex flex-col justify-between hover:border-slate-700 transition-all shadow-xl group"
              >
                <div>
                  <div className="flex items-start justify-between mb-3">
                    <div className="flex items-center gap-2.5">
                      <div className="w-10 h-10 rounded-xl bg-slate-900 border border-slate-800 flex items-center justify-center text-blue-400 group-hover:text-blue-300 group-hover:border-blue-500/30 transition-all">
                        <Cpu className="w-5 h-5" />
                      </div>
                      <div>
                        <h3 className="font-semibold text-slate-100 text-sm">{ag.name}</h3>
                        <div className="flex items-center gap-1.5 mt-0.5">
                          <span className="text-[11px] font-mono text-slate-400">
                            VMID {ag.vmid}
                          </span>
                          <span className="text-slate-600">•</span>
                          <span
                            className={`text-[10px] font-mono uppercase px-1.5 py-0.2 rounded font-semibold ${
                              isKvm
                                ? "bg-purple-950/80 text-purple-400 border border-purple-800/60"
                                : "bg-blue-950/80 text-blue-400 border border-blue-800/60"
                            }`}
                          >
                            {isKvm ? "KVM QEMU" : "LXC"}
                          </span>
                        </div>
                      </div>
                    </div>

                    <span
                      className={`text-[10px] font-mono px-2 py-0.5 rounded-full border flex items-center gap-1 ${
                        isRunning
                          ? "bg-emerald-950/60 text-emerald-400 border-emerald-800/60"
                          : "bg-rose-950/60 text-rose-400 border-rose-800/60"
                      }`}
                    >
                      <span
                        className={`w-1.5 h-1.5 rounded-full ${
                          isRunning ? "bg-emerald-400" : "bg-rose-400"
                        }`}
                      ></span>
                      <span className="capitalize">{ag.status || "idle"}</span>
                    </span>
                  </div>

                  <p className="text-xs text-slate-400 line-clamp-2 mb-4">
                    {ag.role}
                  </p>

                  <div className="p-2.5 rounded-xl bg-slate-900/80 border border-slate-800/80 space-y-1 text-[11px] font-mono text-slate-400 mb-4">
                    <div className="flex justify-between">
                      <span className="text-slate-500">Bridge IP:</span>
                      <span className="text-slate-300">{ag.ip}:8000</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-500">VNC Desktop:</span>
                      <span className="text-slate-300">:{ag.vncPort || 6080}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-500">Workspace:</span>
                      <span className="text-blue-400 truncate max-w-[160px]">
                        /home/ubuntu/workspace
                      </span>
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-2 pt-2 border-t border-slate-800/60">
                  <button
                    onClick={() => setTheaterAgent(ag)}
                    className="flex-1 py-1.5 px-3 rounded-lg bg-blue-600/10 hover:bg-blue-600/20 text-blue-400 border border-blue-500/20 text-xs font-medium flex items-center justify-center gap-1.5 transition-colors"
                  >
                    <MonitorPlay className="w-3.5 h-3.5" />
                    <span>Desktop Stream</span>
                  </button>

                  <button
                    onClick={() => handleEnsureWorkspace(ag)}
                    disabled={syncingId === ag.agentId}
                    className="py-1.5 px-3 rounded-lg bg-slate-900 hover:bg-slate-800 text-slate-300 border border-slate-800 text-xs font-medium flex items-center gap-1.5 transition-colors disabled:opacity-50"
                  >
                    <FolderTree className="w-3.5 h-3.5 text-blue-400" />
                    <span>{syncingId === ag.agentId ? "Binding..." : "Bind WS"}</span>
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* ============================================================ */}
      {/* THEATER FULLSCREEN MODAL                                     */}
      {/* ============================================================ */}
      {theaterAgent && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-md p-4 animate-in fade-in duration-200">
          <div className="bg-slate-950 border border-slate-800 rounded-2xl w-full max-w-6xl h-[88vh] flex flex-col shadow-2xl overflow-hidden">
            {/* Modal Header */}
            <div className="px-5 py-3 border-b border-slate-800 flex items-center justify-between bg-slate-900/60">
              <div className="flex items-center gap-2.5">
                <Tv className="w-4 h-4 text-blue-400" />
                <h3 className="font-semibold text-sm text-slate-100 flex items-center gap-2">
                  <span>{theaterAgent.name} (VMID {theaterAgent.vmid}) - Live Desktop</span>
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-emerald-950/60 text-emerald-400 border border-emerald-800/60 flex items-center gap-1">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
                    <span>Live Stream</span>
                  </span>
                </h3>
              </div>

              <div className="flex items-center gap-2">
                <button
                  onClick={() => setUseDirectLan(!useDirectLan)}
                  className="px-2.5 py-1 rounded-lg text-xs font-mono bg-slate-900 border border-slate-800 text-slate-300 hover:text-white transition"
                >
                  {useDirectLan ? "Switch to Gateway" : "Switch to Direct LAN"}
                </button>
                <a
                  href={getVncUrl(theaterAgent)}
                  target="_blank"
                  rel="noreferrer"
                  className="px-3 py-1 bg-slate-900 hover:bg-slate-800 text-slate-300 border border-slate-800 rounded-lg text-xs font-medium flex items-center gap-1.5 transition-colors"
                >
                  <ExternalLink className="w-3.5 h-3.5" />
                  <span>Open Tab</span>
                </a>
                <button
                  onClick={() => setTheaterAgent(null)}
                  className="p-1.5 text-slate-400 hover:text-slate-100 rounded-lg hover:bg-slate-900 transition-colors"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
            </div>

            {/* Modal Video Frame */}
            <div className="flex-1 bg-black w-full h-full relative">
              <iframe
                src={getVncUrl(theaterAgent)}
                className="w-full h-full border-0 absolute inset-0"
                allow="clipboard-read; clipboard-write; fullscreen"
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
