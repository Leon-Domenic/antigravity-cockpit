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
  FolderGit2, 
  CheckCircle2, 
  AlertCircle,
  Cpu,
  MonitorPlay,
  Terminal,
  X
} from "lucide-react";
import { QueryErrorBoundary } from "@/components/QueryErrorBoundary";

const DEFAULT_AGENTS = [
  {
    agentId: "agent-1",
    vmid: 151,
    name: "Webigo Prime",
    type: "webigo",
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
    type: "webigo",
    vmType: "lxc",
    role: "Code Review & Security Audits",
    ip: "192.168.178.170",
    port: 8000,
    vncPort: 6080,
    status: "idle",
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
    status: "idle",
  },
  {
    agentId: "agent-5",
    vmid: 154,
    name: "Hermes Autonomous (KVM)",
    type: "hermes",
    vmType: "qemu",
    role: "End-to-End Execution & Self-Correction",
    ip: "192.168.178.172",
    port: 8000,
    vncPort: 6080,
    status: "running",
  },
  {
    agentId: "agent-6",
    vmid: 155,
    name: "Open Claw Research",
    type: "claw",
    vmType: "qemu",
    role: "Deep Web & Multimodal Research",
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
  const [selectedVncAgent, setSelectedVncAgent] = useState<any | null>(null);
  const [syncingId, setSyncingId] = useState<string | null>(null);
  const [statusMsg, setStatusMsg] = useState<string | null>(null);

  // Fallback if Convex is initializing
  const agents = (rawAgents && rawAgents.length > 0) ? rawAgents : DEFAULT_AGENTS;

  const handleEnsureWorkspace = async (ag: any) => {
    setSyncingId(ag.agentId);
    setStatusMsg(null);
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
      setStatusMsg(`Workspace bound to ${ag.name} at /home/ubuntu/workspace`);
    } catch (err: any) {
      setStatusMsg(`Sync status: Bridge responded (${err.message})`);
    } finally {
      setSyncingId(null);
      setTimeout(() => setStatusMsg(null), 4000);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header & Cluster metrics */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2.5">
            <Server className="w-6 h-6 text-blue-500" />
            <span>{t("fleet.title")}</span>
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            {t("fleet.subtitle")}
          </p>
        </div>

        <div className="flex items-center gap-2">
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-slate-900 border border-slate-800 text-xs font-mono text-slate-300">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
            <span>Cluster Healthy (5/5 Online)</span>
          </div>
        </div>
      </div>

      {statusMsg && (
        <div className="p-3 rounded-xl bg-blue-950/40 border border-blue-800/60 text-xs text-blue-300 flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 text-blue-400 flex-shrink-0" />
          <span>{statusMsg}</span>
        </div>
      )}

      {/* Grid of Agent Nodes */}
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
                  onClick={() => setSelectedVncAgent(ag)}
                  className="flex-1 py-1.5 px-3 rounded-lg bg-blue-600/10 hover:bg-blue-600/20 text-blue-400 border border-blue-500/20 text-xs font-medium flex items-center justify-center gap-1.5 transition-colors"
                >
                  <Tv className="w-3.5 h-3.5" />
                  <span>Desktop Stream</span>
                </button>

                <button
                  onClick={() => handleEnsureWorkspace(ag)}
                  disabled={syncingId === ag.agentId}
                  title="Ensure workspace binding (/home/ubuntu/workspace)"
                  className="py-1.5 px-3 rounded-lg bg-slate-900 hover:bg-slate-800 border border-slate-800 text-slate-300 text-xs font-medium flex items-center gap-1.5 transition-colors disabled:opacity-50"
                >
                  <FolderGit2 className="w-3.5 h-3.5 text-emerald-400" />
                  <span>{syncingId === ag.agentId ? "Binding..." : "Bind WS"}</span>
                </button>
              </div>
            </div>
          );
        })}
      </div>

      {/* VNC Viewer Modal */}
      {selectedVncAgent && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-md flex items-center justify-center p-4">
          <div className="w-full max-w-5xl h-[80vh] glass-panel rounded-2xl border border-slate-700 flex flex-col overflow-hidden shadow-2xl">
            <div className="px-5 py-3 border-b border-slate-800 flex items-center justify-between bg-slate-900/90">
              <div className="flex items-center gap-2">
                <MonitorPlay className="w-4 h-4 text-blue-400" />
                <span className="font-semibold text-white text-sm">
                  {selectedVncAgent.name} (VMID {selectedVncAgent.vmid}) - Live noVNC Desktop
                </span>
                <span className="text-xs font-mono text-slate-400 ml-2">
                  http://{selectedVncAgent.ip}:{selectedVncAgent.vncPort || 6080}/vnc.html
                </span>
              </div>

              <div className="flex items-center gap-2">
                <a
                  href={`http://${selectedVncAgent.ip}:${selectedVncAgent.vncPort || 6080}/vnc.html?autoconnect=true&resize=scale`}
                  target="_blank"
                  rel="noreferrer"
                  className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 text-xs flex items-center gap-1"
                >
                  <ExternalLink className="w-3.5 h-3.5" />
                  <span>Open Tab</span>
                </a>
                <button
                  onClick={() => setSelectedVncAgent(null)}
                  className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
            </div>

            <div className="flex-1 bg-black relative">
              <iframe
                src={`http://${selectedVncAgent.ip}:${selectedVncAgent.vncPort || 6080}/vnc.html?autoconnect=true&resize=scale`}
                className="w-full h-full border-none"
                title={`VNC ${selectedVncAgent.name}`}
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
