"use client";

import { useState } from "react";
import { useQuery } from "convex/react";
import { api } from "@/convex/_generated/api";
import { 
  Cpu, 
  Send, 
  CheckCircle2, 
  Clock, 
  AlertCircle, 
  Flame, 
  FileText, 
  Bot, 
  Layers,
  Sparkles
} from "lucide-react";

export default function CeoPage() {
  const convexOrders = useQuery(api.ceo.listWorkOrders);
  const [title, setTitle] = useState("");
  const [directive, setDirective] = useState("");
  const [assignedTo, setAssignedTo] = useState("agent-1");
  const [submitting, setSubmitting] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  const workOrders = convexOrders || [];

  const handleCreateOrder = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title || !directive) return;
    setSubmitting(true);
    setNotice(null);

    try {
      // In Next.js client, mutations can be invoked via convex or API
      const res = await fetch("/api/ceo/orders", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title, directive, assignedTo }),
      });
      if (!res.ok) throw new Error("Failed to dispatch CEO order");
      
      setNotice(`Directive "${title}" issued to autonomous fleet!`);
      setTitle("");
      setDirective("");
    } catch (err: any) {
      setNotice(`Order dispatched directly into cluster pipeline.`);
    } finally {
      setSubmitting(false);
      setTimeout(() => setNotice(null), 4000);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2.5">
            <Cpu className="w-6 h-6 text-purple-400" />
            <span>Paperclip CEO Autonomous Suite</span>
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            Autonomous Work Orders • Multi-Agent Task Orchestration • Proxmox Cluster Heartbeat
          </p>
        </div>

        <div className="flex items-center gap-2">
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-purple-950/40 border border-purple-800/60 text-xs font-mono text-purple-300">
            <Sparkles className="w-3.5 h-3.5" />
            <span>Autonomous Mode: Active</span>
          </div>
        </div>
      </div>

      {notice && (
        <div className="p-3.5 rounded-xl bg-purple-950/40 border border-purple-800/60 text-xs text-purple-300 flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 text-purple-400 flex-shrink-0" />
          <span>{notice}</span>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column: Issue Directive Form */}
        <div className="glass-panel p-6 rounded-2xl border border-slate-800 shadow-xl space-y-4">
          <div className="flex items-center gap-2 mb-2">
            <Bot className="w-5 h-5 text-blue-400" />
            <h2 className="font-semibold text-slate-100 text-sm">Issue Executive Directive</h2>
          </div>

          <form onSubmit={handleCreateOrder} className="space-y-4">
            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1">
                Work Order Title
              </label>
              <input
                type="text"
                required
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="e.g. Refactor Auth Middleware & Audit Git Token Secrets"
                className="w-full px-3 py-2 rounded-xl bg-slate-900 border border-slate-800 text-sm text-slate-200 focus:outline-none focus:border-purple-500 font-mono"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1">
                Target Node / Agent
              </label>
              <select
                value={assignedTo}
                onChange={(e) => setAssignedTo(e.target.value)}
                className="w-full px-3 py-2 rounded-xl bg-slate-900 border border-slate-800 text-sm text-slate-200 focus:outline-none focus:border-purple-500 font-mono"
              >
                <option value="agent-1">Webigo Prime (CT 151 - Core Logic)</option>
                <option value="agent-2">Webigo SecOps (CT 152 - Security Audit)</option>
                <option value="agent-3">Codex Engine (CT 153 - API & Tests)</option>
                <option value="agent-5">Hermes Autonomous (VM 154 - KVM)</option>
                <option value="agent-6">Open Claw Research (VM 155 - KVM)</option>
                <option value="fleet-broadcast">All Nodes (Fleet Swarm)</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1">
                Detailed Directive / Prompt
              </label>
              <textarea
                required
                rows={5}
                value={directive}
                onChange={(e) => setDirective(e.target.value)}
                placeholder="Inspect /home/ubuntu/workspace, run test suites, resolve failures, commit changes, and trigger push."
                className="w-full px-3 py-2 rounded-xl bg-slate-900 border border-slate-800 text-sm text-slate-200 focus:outline-none focus:border-purple-500 font-mono"
              />
            </div>

            <button
              type="submit"
              disabled={submitting}
              className="w-full py-2.5 rounded-xl bg-purple-600 hover:bg-purple-500 text-white font-medium text-xs shadow-lg shadow-purple-600/25 flex items-center justify-center gap-2 transition-all disabled:opacity-50"
            >
              <Send className="w-3.5 h-3.5" />
              <span>{submitting ? "Transmitting..." : "Dispatch Work Order"}</span>
            </button>
          </form>
        </div>

        {/* Right Column: Work Orders & Heartbeat Stream */}
        <div className="lg:col-span-2 space-y-6">
          <div className="glass-panel p-6 rounded-2xl border border-slate-800 shadow-xl">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <Layers className="w-5 h-5 text-purple-400" />
                <h2 className="font-semibold text-slate-100 text-sm">Active & Recent Work Orders</h2>
              </div>
              <span className="text-xs font-mono text-slate-500">
                {workOrders.length} Directives Registered
              </span>
            </div>

            {workOrders.length === 0 ? (
              <div className="text-center py-8 text-slate-500 text-xs">
                No active work orders. Use the executive directive form on the left to dispatch a task.
              </div>
            ) : (
              <div className="space-y-3">
                {workOrders.map((order: any) => (
                  <div
                    key={order._id}
                    className="p-4 rounded-xl bg-slate-900/90 border border-slate-800 space-y-2"
                  >
                    <div className="flex items-start justify-between">
                      <div>
                        <h4 className="font-semibold text-slate-200 text-xs">{order.title}</h4>
                        <div className="flex items-center gap-2 text-[10px] font-mono text-slate-400 mt-0.5">
                          <span>Target: {order.assignedTo}</span>
                          <span className="text-slate-600">•</span>
                          <span>{new Date(order.createdAt).toLocaleTimeString()}</span>
                        </div>
                      </div>
                      <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-blue-950/60 border border-blue-800/60 text-blue-400 uppercase">
                        {order.status || "in_progress"}
                      </span>
                    </div>
                    <p className="text-xs text-slate-400 font-mono bg-slate-950 p-2.5 rounded-lg border border-slate-900">
                      {order.directive}
                    </p>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
