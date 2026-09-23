"use client";

import { useState, useEffect } from "react";
import { useQuery } from "convex/react";
import { api } from "@/convex/_generated/api";
import { 
  Settings, 
  Key, 
  Database, 
  Server, 
  Users, 
  CheckCircle2, 
  AlertCircle, 
  Save, 
  ShieldAlert,
  GitBranch,
  Lock
} from "lucide-react";

export default function SettingsPage() {
  const gitConfig = useQuery(api.git.getGitConfig);
  const users = useQuery(api.users.listUsers) || [];

  const [provider, setProvider] = useState("github");
  const [token, setToken] = useState("");
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [savingGit, setSavingGit] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    if (gitConfig) {
      setProvider(gitConfig.provider || "github");
      setUsername(gitConfig.username || "");
      setEmail(gitConfig.email || "");
    }
  }, [gitConfig]);

  const handleSaveGit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSavingGit(true);
    setNotice(null);

    try {
      const res = await fetch("/api/git/config", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          provider,
          token: token.trim() || undefined,
          username: username.trim(),
          email: email.trim(),
        }),
      });

      if (!res.ok) throw new Error("Failed to save Git config");
      setNotice("Git credentials securely updated in ConvexDB!");
      setToken(""); // clear cleartext input
    } catch (err: any) {
      setNotice(`Error: ${err.message}`);
    } finally {
      setSavingGit(false);
      setTimeout(() => setNotice(null), 4000);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2.5">
          <Settings className="w-6 h-6 text-blue-500" />
          <span>Cluster & Service Settings</span>
        </h1>
        <p className="text-sm text-slate-400 mt-1">
          Cluster Topology • Git Credentials Vault • ConvexDB State
        </p>
      </div>

      {notice && (
        <div className="p-3.5 rounded-xl bg-blue-950/40 border border-blue-800/60 text-xs text-blue-300 flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 text-blue-400 flex-shrink-0" />
          <span>{notice}</span>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Proxmox VE Cluster Status */}
        <div className="glass-panel p-6 rounded-2xl border border-slate-800 shadow-xl space-y-4">
          <div className="flex items-center gap-2">
            <Server className="w-5 h-5 text-blue-400" />
            <h2 className="font-semibold text-slate-100 text-sm">Proxmox VE Cluster Target</h2>
          </div>

          <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800 space-y-2.5 text-xs font-mono">
            <div className="flex justify-between">
              <span className="text-slate-500">Host IP:</span>
              <span className="text-slate-200">192.168.178.105</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-500">API Port:</span>
              <span className="text-slate-200">:8006 (JSON API)</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-500">Cockpit Container:</span>
              <span className="text-blue-400">CT 150 (192.168.178.168:3000)</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-500">KVM QEMU Nodes:</span>
              <span className="text-purple-400">VM 154 (Hermes), VM 155 (Open Claw)</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-500">LXC Agent Nodes:</span>
              <span className="text-slate-200">CT 151, CT 152, CT 153</span>
            </div>
          </div>

          <div className="text-xs text-slate-400">
            Agents communicate via internal bridges on port <code>8000</code> and noVNC on port <code>6080</code>.
          </div>
        </div>

        {/* Local Convex DB Status */}
        <div className="glass-panel p-6 rounded-2xl border border-slate-800 shadow-xl space-y-4">
          <div className="flex items-center gap-2">
            <Database className="w-5 h-5 text-emerald-400" />
            <h2 className="font-semibold text-slate-100 text-sm">ConvexDB Local Backend</h2>
          </div>

          <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800 space-y-2.5 text-xs font-mono">
            <div className="flex justify-between">
              <span className="text-slate-500">Backend Endpoint:</span>
              <span className="text-emerald-400">http://127.0.0.1:3210</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-500">Storage Engine:</span>
              <span className="text-slate-200">Local RocksDB / SQLite (Zero Cloud)</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-500">Tables:</span>
              <span className="text-slate-200">users, workspaces, gitConfigs, agents, workOrders</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-500">Sync Mode:</span>
              <span className="text-emerald-400">Real-Time Reactive WebSocket</span>
            </div>
          </div>

          <div className="text-xs text-slate-400">
            All user accounts, private git configurations, and workspace records are stored exclusively on CT 150.
          </div>
        </div>
      </div>

      {/* Git Credentials & Private Repo Authentication */}
      <div className="glass-panel p-6 rounded-2xl border border-slate-800 shadow-xl space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Key className="w-5 h-5 text-purple-400" />
            <h2 className="font-semibold text-slate-100 text-sm">
              Git Authentication Vault (Personal Access Tokens)
            </h2>
          </div>
          {gitConfig?.hasToken && (
            <span className="text-xs font-mono text-emerald-400 flex items-center gap-1.5 bg-emerald-950/40 border border-emerald-800/60 px-2.5 py-1 rounded-lg">
              <Lock className="w-3 h-3" />
              <span>Token Configured ({gitConfig.token})</span>
            </span>
          )}
        </div>

        <form onSubmit={handleSaveGit} className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1">Provider</label>
              <select
                value={provider}
                onChange={(e) => setProvider(e.target.value)}
                className="w-full px-3 py-2 rounded-xl bg-slate-900 border border-slate-800 text-sm text-slate-200 focus:outline-none focus:border-purple-500 font-mono"
              >
                <option value="github">GitHub</option>
                <option value="gitlab">GitLab</option>
                <option value="gitea">Gitea / Forgejo</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1">Git Username / Author</label>
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="leon-domenic"
                className="w-full px-3 py-2 rounded-xl bg-slate-900 border border-slate-800 text-sm text-slate-200 focus:outline-none focus:border-purple-500 font-mono"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1">Git Email</label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="dev@webigo.ai"
                className="w-full px-3 py-2 rounded-xl bg-slate-900 border border-slate-800 text-sm text-slate-200 focus:outline-none focus:border-purple-500 font-mono"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-1">
              Personal Access Token (PAT)
            </label>
            <input
              type="password"
              value={token}
              onChange={(e) => setToken(e.target.value)}
              placeholder={gitConfig?.hasToken ? "Enter new token to overwrite existing PAT" : "ghp_xxxxxxxxxxxxxxxxxxxx"}
              className="w-full px-3 py-2 rounded-xl bg-slate-900 border border-slate-800 text-sm text-slate-200 focus:outline-none focus:border-purple-500 font-mono"
            />
            <p className="text-[11px] text-slate-500 mt-1">
              Required for cloning private repositories and performing Git Push actions across agent nodes.
            </p>
          </div>

          <div className="flex justify-end pt-2">
            <button
              type="submit"
              disabled={savingGit}
              className="px-4 py-2 rounded-xl bg-purple-600 hover:bg-purple-500 text-white font-medium text-xs shadow-lg shadow-purple-600/25 flex items-center gap-2 transition-all disabled:opacity-50"
            >
              <Save className="w-4 h-4" />
              <span>{savingGit ? "Storing Vault..." : "Save Git Credentials"}</span>
            </button>
          </div>
        </form>
      </div>

      {/* Cluster Users & Roles */}
      <div className="glass-panel p-6 rounded-2xl border border-slate-800 shadow-xl space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Users className="w-5 h-5 text-blue-400" />
            <h2 className="font-semibold text-slate-100 text-sm">Cluster Users & Role Management</h2>
          </div>
          <span className="text-xs font-mono text-slate-500">{users.length} Users</span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-xs font-mono">
            <thead>
              <tr className="border-b border-slate-800 text-slate-500 text-left">
                <th className="pb-2">User / Name</th>
                <th className="pb-2">Email</th>
                <th className="pb-2">Role</th>
                <th className="pb-2">Auth Method</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              <tr className="text-slate-300">
                <td className="py-2.5 font-medium text-white">Cockpit Administrator</td>
                <td className="py-2.5">admin@webigo.ai</td>
                <td className="py-2.5">
                  <span className="px-2 py-0.5 rounded bg-blue-950 text-blue-400 border border-blue-800 font-semibold uppercase text-[10px]">
                    Admin
                  </span>
                </td>
                <td className="py-2.5 text-slate-400">NextAuth Credentials (PBKDF2/Bcrypt)</td>
              </tr>
              {users.map((u: any) => (
                <tr key={u._id} className="text-slate-300">
                  <td className="py-2.5 font-medium text-white">{u.name}</td>
                  <td className="py-2.5">{u.email}</td>
                  <td className="py-2.5">
                    <span className="px-2 py-0.5 rounded bg-slate-900 text-slate-300 border border-slate-800 uppercase text-[10px]">
                      {u.role || "developer"}
                    </span>
                  </td>
                  <td className="py-2.5 text-slate-400">Convex DB</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
