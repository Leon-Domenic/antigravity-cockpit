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
  Lock,
  Sparkles,
  RefreshCw,
  Radio,
  ExternalLink,
  Code2,
  Trash2
} from "lucide-react";
import { QueryErrorBoundary } from "@/components/QueryErrorBoundary";

function SettingsWithQuery() {
  const gitConfig = useQuery(api.git.getGitConfig);
  const users = useQuery(api.users.listUsers) || [];
  return <SettingsView gitConfig={gitConfig} users={users} />;
}

export default function SettingsPage() {
  return (
    <QueryErrorBoundary fallback={<SettingsView gitConfig={null} users={[]} />}>
      <SettingsWithQuery />
    </QueryErrorBoundary>
  );
}

function SettingsView({ gitConfig, users }: { gitConfig: any; users: any[] }) {

  const [provider, setProvider] = useState("github");
  const [token, setToken] = useState("");
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [savingGit, setSavingGit] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  // Google AI & Workspace Auth Vault State
  const [googleAuth, setGoogleAuth] = useState<any>(null);
  const [loadingGoogle, setLoadingGoogle] = useState(false);
  const [syncingGoogle, setSyncingGoogle] = useState(false);
  const [manualToken, setManualToken] = useState("");
  const [showManualGoogle, setShowManualGoogle] = useState(false);

  // Google Cloud OAuth App (Option 3)
  const [showOAuthConfig, setShowOAuthConfig] = useState(false);
  const [oauthClientId, setOauthClientId] = useState("");
  const [oauthClientSecret, setOauthClientSecret] = useState("");
  const [savingOAuthConfig, setSavingOAuthConfig] = useState(false);
  const [hasCustomSecret, setHasCustomSecret] = useState(false);

  const fetchGoogleAuth = async () => {
    try {
      const res = await fetch("/api/google/auth");
      if (res.ok) {
        const data = await res.json();
        setGoogleAuth(data);
      }
    } catch (e) {
      console.warn("Failed to load Google Auth", e);
    }
  };

  const fetchOAuthConfig = async () => {
    try {
      const res = await fetch("/api/google/auth", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "get_oauth_config" }),
      });
      if (res.ok) {
        const data = await res.json();
        if (data.client_id) setOauthClientId(data.client_id);
        setHasCustomSecret(Boolean(data.has_secret));
      }
    } catch (e) {}
  };

  useEffect(() => {
    fetchGoogleAuth();
    fetchOAuthConfig();
    const interval = setInterval(fetchGoogleAuth, 10000);

    const onMessage = (e: MessageEvent) => {
      if (e.data && e.data.type === "GOOGLE_AUTH_SUCCESS") {
        fetchGoogleAuth();
        setNotice("Google Account successfully connected and synced across cluster!");
      }
    };
    window.addEventListener("message", onMessage);
    return () => {
      clearInterval(interval);
      window.removeEventListener("message", onMessage);
    };
  }, []);

  const handleConnectGoogle = async () => {
    setLoadingGoogle(true);
    try {
      const res = await fetch("/api/google/auth", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "login_url" }),
      });
      const data = await res.json();
      if (data.auth_url) {
        const width = 600, height = 700;
        const left = (window.screen.width - width) / 2;
        const top = (window.screen.height - height) / 2;
        const authPopup = window.open(
          data.auth_url,
          "GoogleAuthLogin",
          `width=${width},height=${height},top=${top},left=${left},status=yes,resizable=yes`
        );
        if (!authPopup || authPopup.closed || typeof authPopup.closed === "undefined") {
          window.location.href = data.auth_url;
        }
      } else {
        alert("Failed to get Google login URL: " + (data.error || "Unknown"));
      }
    } catch (err: any) {
      alert("Error starting Google OAuth: " + err.message);
    } finally {
      setLoadingGoogle(false);
    }
  };

  const handleSyncFleet = async () => {
    setSyncingGoogle(true);
    try {
      const res = await fetch("/api/google/auth", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "sync" }),
      });
      const data = await res.json();
      if (data.success) {
        setNotice(data.message || "Fleet agents synchronized with active Google token!");
      } else {
        setNotice("Sync notice: " + (data.error || data.message || "Failed"));
      }
      fetchGoogleAuth();
    } catch (err: any) {
      setNotice("Sync failed: " + err.message);
    } finally {
      setSyncingGoogle(false);
    }
  };

  const handleSaveManualToken = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!manualToken.trim()) return;
    setLoadingGoogle(true);
    try {
      const res = await fetch("/api/google/auth", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token_json: manualToken.trim() }),
      });
      const data = await res.json();
      if (data.success) {
        setNotice(data.message || "Google OAuth token saved and pushed to fleet!");
        setManualToken("");
        setShowManualGoogle(false);
      } else {
        setNotice("Error: " + (data.error || "Failed to save token"));
      }
      fetchGoogleAuth();
    } catch (err: any) {
      setNotice("Error: " + err.message);
    } finally {
      setLoadingGoogle(false);
    }
  };

  const handleDisconnectGoogle = async () => {
    if (!confirm("Are you sure you want to disconnect Google AI credentials from all workspace agents?")) return;
    try {
      const res = await fetch("/api/google/auth", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "disconnect" }),
      });
      const data = await res.json();
      setNotice(data.message || "Google Account Disconnected");
      fetchGoogleAuth();
    } catch (err: any) {
      setNotice("Failed: " + err.message);
    }
  };

  const handleSaveOAuthConfig = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!oauthClientId.trim()) return;
    setSavingOAuthConfig(true);
    try {
      const res = await fetch("/api/google/auth", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action: "save_oauth_config",
          client_id: oauthClientId.trim(),
          client_secret: oauthClientSecret.trim() || undefined,
        }),
      });
      const data = await res.json();
      if (data.success) {
        setNotice("Google Cloud OAuth Client credentials saved! Redirect URI is ready.");
        setHasCustomSecret(Boolean(data.has_secret));
        setShowOAuthConfig(false);
      } else {
        setNotice("Error: " + (data.error || "Failed to save OAuth credentials"));
      }
    } catch (err: any) {
      setNotice("Error: " + err.message);
    } finally {
      setSavingOAuthConfig(false);
    }
  };

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
      {/* Google AI & Workspace Authentication Vault */}
      <div className="glass-panel p-6 rounded-2xl border border-slate-800 shadow-xl space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Sparkles className="w-5 h-5 text-indigo-400" />
            <h2 className="font-semibold text-slate-100 text-sm">
              Google AI & Workspace Authentication Vault
            </h2>
          </div>
          {googleAuth?.authenticated ? (
            <span className="text-xs font-mono text-emerald-400 flex items-center gap-1.5 bg-emerald-950/40 border border-emerald-800/60 px-2.5 py-1 rounded-lg">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
              <span>Active ({googleAuth.email || "Fleet Synced"})</span>
            </span>
          ) : (
            <span className="text-xs font-mono text-slate-400 flex items-center gap-1.5 bg-slate-900 border border-slate-800 px-2.5 py-1 rounded-lg">
              <span>Not Connected</span>
            </span>
          )}
        </div>

        <p className="text-xs text-slate-400 leading-relaxed">
          Authenticate your Google account once at the workspace level. Credentials and Gemini model quotas are automatically pushed to all active agents (CT 151, CT 152, CT 153, etc.) and auto-injected into newly provisioned containers with background token auto-refresh.
        </p>

        {googleAuth?.authenticated && (
          <div className="p-3.5 rounded-xl bg-slate-900/80 border border-slate-800 space-y-2 text-xs font-mono">
            <div className="flex justify-between items-center">
              <span className="text-slate-500">Connected Account:</span>
              <span className="text-slate-200 font-semibold">{googleAuth.email || "Workspace Token"}</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-slate-500">Quota Tier:</span>
              <span className="text-indigo-400 font-semibold">{googleAuth.tier || "Google AI Pro"}</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-slate-500">Fleet Status:</span>
              <span className="text-emerald-400">
                {googleAuth.last_synced ? `Synced at ${new Date(googleAuth.last_synced * 1000).toLocaleTimeString()}` : "Active on cluster"}
              </span>
            </div>
          </div>
        )}

        <div className="flex flex-wrap items-center gap-2.5 pt-1">
          <button
            type="button"
            onClick={handleConnectGoogle}
            disabled={loadingGoogle}
            className="px-4 py-2 rounded-xl bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white font-medium text-xs shadow-lg shadow-blue-600/25 flex items-center gap-2 transition-all disabled:opacity-50"
          >
            <Sparkles className="w-4 h-4" />
            <span>{googleAuth?.authenticated ? "Reconnect / Switch Google Account" : "Connect Google Account"}</span>
          </button>

          <button
            type="button"
            onClick={handleSyncFleet}
            disabled={syncingGoogle}
            className="px-3.5 py-2 rounded-xl bg-slate-900 hover:bg-slate-800 text-slate-200 border border-slate-800 font-medium text-xs flex items-center gap-2 transition-all disabled:opacity-50"
            title="Push workspace credentials to all active container nodes"
          >
            <RefreshCw className={`w-3.5 h-3.5 text-blue-400 ${syncingGoogle ? "animate-spin" : ""}`} />
            <span>{syncingGoogle ? "Syncing Fleet..." : "Sync All Agents"}</span>
          </button>

          <button
            type="button"
            onClick={() => setShowManualGoogle(!showManualGoogle)}
            className="px-3 py-2 rounded-xl bg-slate-900 hover:bg-slate-800 text-slate-400 border border-slate-800 font-medium text-xs flex items-center gap-1.5 transition-all"
          >
            <Code2 className="w-3.5 h-3.5" />
            <span>Paste Token JSON</span>
          </button>

          <button
            type="button"
            onClick={() => setShowOAuthConfig(!showOAuthConfig)}
            className="px-3 py-2 rounded-xl bg-slate-900 hover:bg-slate-800 text-indigo-400 border border-slate-800 font-medium text-xs flex items-center gap-1.5 transition-all"
            title="Configure Google Cloud OAuth Client ID & Secret for 1-click web popup"
          >
            <Key className="w-3.5 h-3.5" />
            <span>Google Cloud App (Option 3)</span>
          </button>

          {googleAuth?.authenticated && (
            <button
              type="button"
              onClick={handleDisconnectGoogle}
              className="px-3 py-2 rounded-xl hover:bg-red-950/40 text-red-400 border border-transparent hover:border-red-800/60 font-medium text-xs flex items-center gap-1.5 transition-all ml-auto"
            >
              <Trash2 className="w-3.5 h-3.5" />
              <span>Disconnect</span>
            </button>
          )}
        </div>

        {showOAuthConfig && (
          <form onSubmit={handleSaveOAuthConfig} className="pt-3 space-y-3.5 border-t border-slate-800/80">
            <div className="p-3 rounded-xl bg-indigo-950/30 border border-indigo-800/50 space-y-1.5">
              <div className="flex items-center gap-1.5 text-xs font-semibold text-indigo-300">
                <ExternalLink className="w-3.5 h-3.5" />
                <span>Google Cloud Console Setup (Option 3)</span>
              </div>
              <p className="text-[11px] text-slate-400 leading-relaxed">
                Create an <strong>OAuth 2.0 Client ID</strong> (Application type: <em>Web application</em>) in your Google Cloud Console. Add the following Authorized Redirect URI:
              </p>
              <div className="flex items-center gap-2 p-2 rounded-lg bg-slate-950/80 border border-slate-800 font-mono text-[11px] text-emerald-400 select-all">
                <span>https://workspace.webigo.ai/api/google/auth/callback</span>
              </div>
            </div>

            <div className="space-y-2">
              <div>
                <label className="text-[11px] font-mono text-slate-400 block mb-1">
                  Google Client ID (.apps.googleusercontent.com)
                </label>
                <input
                  type="text"
                  value={oauthClientId}
                  onChange={(e) => setOauthClientId(e.target.value)}
                  placeholder="123456789-abcdef.apps.googleusercontent.com"
                  className="w-full px-3 py-2 rounded-xl bg-slate-900 border border-slate-800 text-xs font-mono text-slate-200 focus:outline-none focus:border-indigo-500"
                />
              </div>

              <div>
                <label className="text-[11px] font-mono text-slate-400 block mb-1">
                  Google Client Secret {hasCustomSecret && <span className="text-emerald-400 text-[10px]">(Configured)</span>}
                </label>
                <input
                  type="password"
                  value={oauthClientSecret}
                  onChange={(e) => setOauthClientSecret(e.target.value)}
                  placeholder={hasCustomSecret ? "••••••••••••••••••••••••••••••••" : "GOCSPX-..."}
                  className="w-full px-3 py-2 rounded-xl bg-slate-900 border border-slate-800 text-xs font-mono text-slate-200 focus:outline-none focus:border-indigo-500"
                />
              </div>
            </div>

            <div className="flex justify-end pt-1">
              <button
                type="submit"
                disabled={savingOAuthConfig || !oauthClientId.trim()}
                className="px-4 py-1.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-medium text-xs shadow-lg shadow-indigo-600/25 flex items-center gap-1.5 transition-all disabled:opacity-50"
              >
                <Save className="w-3.5 h-3.5" />
                <span>{savingOAuthConfig ? "Saving..." : "Save OAuth App Credentials"}</span>
              </button>
            </div>
          </form>
        )}

        {showManualGoogle && (
          <form onSubmit={handleSaveManualToken} className="pt-2 space-y-3 border-t border-slate-800/80">
            <p className="text-[11px] text-slate-400">
              Paste an OAuth Token JSON below. It will be stored in the workspace vault and broadcasted across all cluster nodes:
            </p>
            <textarea
              rows={3}
              value={manualToken}
              onChange={(e) => setManualToken(e.target.value)}
              placeholder='{"token": {"access_token": "ya29...", "token_type": "Bearer", "refresh_token": "..."}}'
              className="w-full px-3 py-2 rounded-xl bg-slate-900 border border-slate-800 text-xs font-mono text-slate-200 focus:outline-none focus:border-indigo-500 resize-none"
            />
            <div className="flex justify-end">
              <button
                type="submit"
                disabled={loadingGoogle || !manualToken.trim()}
                className="px-4 py-1.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-medium text-xs shadow-lg shadow-indigo-600/25 flex items-center gap-1.5 transition-all disabled:opacity-50"
              >
                <Save className="w-3.5 h-3.5" />
                <span>Save & Broadcast to Fleet</span>
              </button>
            </div>
          </form>
        )}
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
