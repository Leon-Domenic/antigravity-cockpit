"use client";

import { useState } from "react";
import { useQuery } from "convex/react";
import { api } from "@/convex/_generated/api";
import { 
  FolderGit2, 
  GitBranch, 
  GitCommit, 
  GitPullRequest, 
  Upload, 
  Plus, 
  Download, 
  Share2, 
  Trash2, 
  CheckCircle2, 
  AlertCircle,
  FileCode,
  Lock,
  ExternalLink,
  X,
  Send
} from "lucide-react";

export default function WorkspacesPage() {
  const convexWorkspaces = useQuery(api.workspaces.listWorkspaces);
  const gitConfig = useQuery(api.git.getGitConfig);

  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showCommitModal, setShowCommitModal] = useState<any | null>(null);

  // Form states for create
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [gitUrl, setGitUrl] = useState("");
  const [gitBranch, setGitBranch] = useState("main");
  const [loading, setLoading] = useState(false);

  // Form states for commit
  const [commitMsg, setCommitMsg] = useState("");
  const [authorName, setAuthorName] = useState("Cockpit Developer");
  const [commitLoading, setCommitLoading] = useState(false);

  // Feedback notifications
  const [notice, setNotice] = useState<{ type: "success" | "error"; text: string } | null>(null);

  const workspaces = convexWorkspaces || [];

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setNotice(null);
    try {
      const res = await fetch("/api/workspaces", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, description, gitUrl, gitBranch }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Failed to create workspace");
      
      setNotice({ type: "success", text: `Workspace "${name}" ready with ${data.fileCount || 0} files!` });
      setShowCreateModal(false);
      setName("");
      setDescription("");
      setGitUrl("");
    } catch (err: any) {
      setNotice({ type: "error", text: err.message });
    } finally {
      setLoading(false);
    }
  };

  const handleGitPull = async (ws: any) => {
    setNotice(null);
    try {
      const res = await fetch(`/api/workspaces/${ws._id}/git`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "pull", branch: ws.gitBranch || "main" }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Git pull failed");
      setNotice({ type: "success", text: `Pulled latest changes! HEAD is now ${data.commit}` });
    } catch (err: any) {
      setNotice({ type: "error", text: `Pull error: ${err.message}` });
    }
  };

  const handleCommitSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!showCommitModal) return;
    setCommitLoading(true);
    setNotice(null);
    try {
      const res = await fetch(`/api/workspaces/${showCommitModal._id}/git`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action: "commit",
          commitMessage: commitMsg,
          authorName,
          branch: showCommitModal.gitBranch || "main",
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Git commit failed");

      setNotice({ type: "success", text: `Committed: "${commitMsg}" (${data.commit})` });
      setShowCommitModal(null);
      setCommitMsg("");
    } catch (err: any) {
      setNotice({ type: "error", text: `Commit error: ${err.message}` });
    } finally {
      setCommitLoading(false);
    }
  };

  const handleGitPush = async (ws: any) => {
    setNotice(null);
    try {
      const res = await fetch(`/api/workspaces/${ws._id}/git`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "push", branch: ws.gitBranch || "main" }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Git push failed");
      setNotice({ type: "success", text: `Pushed commits to remote origin/${ws.gitBranch || "main"}!` });
    } catch (err: any) {
      setNotice({ type: "error", text: `Push error: ${err.message}` });
    }
  };

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2.5">
            <FolderGit2 className="w-6 h-6 text-blue-500" />
            <span>Workspaces & Git Repositories</span>
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            ConvexDB State Persistence • Private Git PAT Authentication • Multi-Agent Target
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowCreateModal(true)}
            className="flex items-center gap-2 px-4 py-2 rounded-xl bg-blue-600 hover:bg-blue-500 text-white font-medium text-xs shadow-lg shadow-blue-600/25 transition-all"
          >
            <Plus className="w-4 h-4" />
            <span>Import Repository / Workspace</span>
          </button>
        </div>
      </div>

      {notice && (
        <div
          className={`p-3.5 rounded-xl border flex items-center gap-2.5 text-xs ${
            notice.type === "success"
              ? "bg-emerald-950/40 border-emerald-800/60 text-emerald-300"
              : "bg-rose-950/40 border-rose-800/60 text-rose-300"
          }`}
        >
          {notice.type === "success" ? (
            <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0" />
          ) : (
            <AlertCircle className="w-4 h-4 text-rose-400 flex-shrink-0" />
          )}
          <span>{notice.text}</span>
        </div>
      )}

      {/* Workspaces List / Grid */}
      {workspaces.length === 0 ? (
        <div className="glass-panel p-12 rounded-2xl border border-slate-800 text-center">
          <div className="w-12 h-12 rounded-xl bg-slate-900 border border-slate-800 flex items-center justify-center text-slate-500 mx-auto mb-3">
            <FolderGit2 className="w-6 h-6" />
          </div>
          <h3 className="text-base font-semibold text-slate-200">No Workspaces Registered</h3>
          <p className="text-xs text-slate-400 max-w-md mx-auto mt-1 mb-5">
            Import a public or private GitHub repository, or create a clean project scaffold for autonomous agent execution.
          </p>
          <button
            onClick={() => setShowCreateModal(true)}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-blue-600 hover:bg-blue-500 text-white text-xs font-medium"
          >
            <Plus className="w-4 h-4" />
            <span>Import First Repository</span>
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {workspaces.map((ws: any) => (
            <div
              key={ws._id}
              className="glass-panel rounded-2xl border border-slate-800 p-5 flex flex-col justify-between hover:border-slate-700 transition-all shadow-xl group"
            >
              <div>
                <div className="flex items-start justify-between mb-2">
                  <div className="flex items-center gap-2.5">
                    <div className="w-9 h-9 rounded-xl bg-blue-950/50 border border-blue-800/50 flex items-center justify-center text-blue-400">
                      <FileCode className="w-4 h-4" />
                    </div>
                    <div>
                      <h3 className="font-semibold text-slate-100 text-sm">{ws.name}</h3>
                      <div className="flex items-center gap-1.5 text-[11px] font-mono text-slate-400">
                        <GitBranch className="w-3 h-3 text-blue-400" />
                        <span>{ws.gitBranch || "main"}</span>
                        {ws.gitCommit && (
                          <>
                            <span className="text-slate-600">•</span>
                            <span className="text-slate-300">{ws.gitCommit.slice(0, 7)}</span>
                          </>
                        )}
                      </div>
                    </div>
                  </div>

                  <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-900 border border-slate-800 text-slate-400 uppercase">
                    {ws.primaryLanguage || "TypeScript"}
                  </span>
                </div>

                <p className="text-xs text-slate-400 line-clamp-2 mt-2 mb-3">
                  {ws.description || "Workspace target on Proxmox agent cluster."}
                </p>

                {ws.gitCommitMsg && (
                  <div className="p-2.5 rounded-xl bg-slate-900/80 border border-slate-800/80 text-[11px] font-mono text-slate-400 space-y-1 mb-4">
                    <div className="flex items-center gap-1.5 text-slate-300 truncate">
                      <GitCommit className="w-3.5 h-3.5 text-blue-400 flex-shrink-0" />
                      <span className="truncate">{ws.gitCommitMsg}</span>
                    </div>
                    <div className="text-[10px] text-slate-500">
                      by {ws.gitCommitAuthor || "system"}
                    </div>
                  </div>
                )}
              </div>

              {/* Action Toolbar */}
              <div className="space-y-2 pt-2 border-t border-slate-800/60">
                <div className="grid grid-cols-3 gap-1.5">
                  <button
                    onClick={() => handleGitPull(ws)}
                    className="py-1.5 px-2 rounded-lg bg-slate-900 hover:bg-slate-800 border border-slate-800 text-slate-300 text-[11px] font-medium flex items-center justify-center gap-1 transition-colors"
                  >
                    <Download className="w-3 h-3 text-blue-400" />
                    <span>Pull</span>
                  </button>

                  <button
                    onClick={() => setShowCommitModal(ws)}
                    className="py-1.5 px-2 rounded-lg bg-slate-900 hover:bg-slate-800 border border-slate-800 text-slate-300 text-[11px] font-medium flex items-center justify-center gap-1 transition-colors"
                  >
                    <GitCommit className="w-3 h-3 text-emerald-400" />
                    <span>Commit</span>
                  </button>

                  <button
                    onClick={() => handleGitPush(ws)}
                    className="py-1.5 px-2 rounded-lg bg-slate-900 hover:bg-slate-800 border border-slate-800 text-slate-300 text-[11px] font-medium flex items-center justify-center gap-1 transition-colors"
                  >
                    <Send className="w-3 h-3 text-purple-400" />
                    <span>Push</span>
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Modal: Import / Create Workspace */}
      {showCreateModal && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="w-full max-w-lg glass-panel rounded-2xl border border-slate-700 p-6 shadow-2xl relative">
            <button
              onClick={() => setShowCreateModal(false)}
              className="absolute top-4 right-4 text-slate-400 hover:text-white"
            >
              <X className="w-4 h-4" />
            </button>

            <div className="flex items-center gap-2.5 mb-4">
              <div className="w-8 h-8 rounded-lg bg-blue-600/20 border border-blue-500/30 flex items-center justify-center text-blue-400">
                <FolderGit2 className="w-4 h-4" />
              </div>
              <div>
                <h3 className="font-semibold text-slate-100 text-base">Import Git Workspace</h3>
                <p className="text-xs text-slate-400">Clones to /home/ubuntu/workspace across agent fleet</p>
              </div>
            </div>

            <form onSubmit={handleCreate} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">Project Name</label>
                <input
                  type="text"
                  required
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="e.g. backend-core or ai-platform"
                  className="w-full px-3 py-2 rounded-xl bg-slate-900 border border-slate-800 text-sm text-slate-200 focus:outline-none focus:border-blue-500 font-mono"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">Description (Optional)</label>
                <input
                  type="text"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="Target repository for autonomous agent execution"
                  className="w-full px-3 py-2 rounded-xl bg-slate-900 border border-slate-800 text-sm text-slate-200 focus:outline-none focus:border-blue-500"
                />
              </div>

              <div>
                <div className="flex items-center justify-between mb-1">
                  <label className="block text-xs font-semibold text-slate-300">Git Clone URL (Public or Private)</label>
                  {gitConfig?.hasToken && (
                    <span className="text-[10px] text-emerald-400 flex items-center gap-1 font-mono">
                      <Lock className="w-2.5 h-2.5" /> PAT Configured
                    </span>
                  )}
                </div>
                <input
                  type="text"
                  value={gitUrl}
                  onChange={(e) => setGitUrl(e.target.value)}
                  placeholder="https://github.com/organization/repo.git"
                  className="w-full px-3 py-2 rounded-xl bg-slate-900 border border-slate-800 text-sm text-slate-200 focus:outline-none focus:border-blue-500 font-mono"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">Branch</label>
                <input
                  type="text"
                  value={gitBranch}
                  onChange={(e) => setGitBranch(e.target.value)}
                  placeholder="main"
                  className="w-full px-3 py-2 rounded-xl bg-slate-900 border border-slate-800 text-sm text-slate-200 focus:outline-none focus:border-blue-500 font-mono"
                />
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  className="px-4 py-2 rounded-xl bg-slate-900 hover:bg-slate-800 border border-slate-800 text-slate-300 text-xs font-medium"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={loading}
                  className="px-4 py-2 rounded-xl bg-blue-600 hover:bg-blue-500 text-white text-xs font-medium disabled:opacity-50"
                >
                  {loading ? "Cloning & Provisioning..." : "Create Workspace"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal: Git Commit */}
      {showCommitModal && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="w-full max-w-md glass-panel rounded-2xl border border-slate-700 p-6 shadow-2xl relative">
            <button
              onClick={() => setShowCommitModal(null)}
              className="absolute top-4 right-4 text-slate-400 hover:text-white"
            >
              <X className="w-4 h-4" />
            </button>

            <div className="flex items-center gap-2 mb-4">
              <GitCommit className="w-5 h-5 text-emerald-400" />
              <h3 className="font-semibold text-slate-100 text-base">
                Commit Changes: {showCommitModal.name}
              </h3>
            </div>

            <form onSubmit={handleCommitSubmit} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">Commit Message</label>
                <textarea
                  required
                  rows={3}
                  value={commitMsg}
                  onChange={(e) => setCommitMsg(e.target.value)}
                  placeholder="feat: implement autonomous agent orchestration loop"
                  className="w-full px-3 py-2 rounded-xl bg-slate-900 border border-slate-800 text-sm text-slate-200 focus:outline-none focus:border-blue-500 font-mono"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">Author Name</label>
                <input
                  type="text"
                  value={authorName}
                  onChange={(e) => setAuthorName(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl bg-slate-900 border border-slate-800 text-sm text-slate-200 font-mono"
                />
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowCommitModal(null)}
                  className="px-4 py-2 rounded-xl bg-slate-900 hover:bg-slate-800 border border-slate-800 text-slate-300 text-xs font-medium"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={commitLoading}
                  className="px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-medium disabled:opacity-50"
                >
                  {commitLoading ? "Committing..." : "Commit Changes"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
