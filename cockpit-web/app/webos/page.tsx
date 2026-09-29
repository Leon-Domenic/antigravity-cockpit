"use client";

import { useState, useEffect } from "react";
import { 
  AppWindow, 
  Maximize2, 
  Minimize2, 
  ExternalLink, 
  RefreshCw, 
  Sliders, 
  ShieldCheck, 
  Terminal, 
  FolderGit2, 
  Code2, 
  Sparkles, 
  Cpu, 
  Server,
  Layers, 
  CheckCircle2,
  HardDrive
} from "lucide-react";

export default function WebOSPage() {
  const [webosUrl, setWebosUrl] = useState<string>("https://webos.webigo.ai");
  const [customUrl, setCustomUrl] = useState<string>("");
  const [showConfig, setShowConfig] = useState<boolean>(false);
  const [isFullscreen, setIsFullscreen] = useState<boolean>(false);
  const [reloadKey, setReloadKey] = useState<number>(0);
  const [isOnline, setIsOnline] = useState<boolean>(true);

  // Load custom URL from localStorage if saved
  useEffect(() => {
    const saved = localStorage.getItem("webigo-webos-url");
    if (saved) {
      setWebosUrl(saved);
    }
  }, []);

  const handleSelectUrl = (url: string) => {
    setWebosUrl(url);
    localStorage.setItem("webigo-webos-url", url);
    setReloadKey(prev => prev + 1);
  };

  const handleSaveCustomUrl = (e: React.FormEvent) => {
    e.preventDefault();
    if (!customUrl.trim()) return;
    let formatted = customUrl.trim();
    if (!formatted.startsWith("http://") && !formatted.startsWith("https://")) {
      formatted = "https://" + formatted;
    }
    handleSelectUrl(formatted);
    setShowConfig(false);
  };

  const handleReload = () => {
    setReloadKey(prev => prev + 1);
  };

  return (
    <div className={`space-y-4 ${isFullscreen ? "fixed inset-0 z-50 bg-slate-950 p-2 sm:p-4 overflow-hidden flex flex-col" : "pb-12"}`}>
      {/* WebOS Top Control Bar */}
      <div className="glass-panel p-3.5 rounded-2xl border border-slate-800 shadow-xl flex flex-wrap items-center justify-between gap-3">
        {/* Left Title & Status */}
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-cyan-500 to-blue-600 flex items-center justify-center text-white shadow-lg shadow-blue-500/20">
            <AppWindow className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-base font-bold text-white tracking-tight">WebOS Environment</h1>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded-md bg-blue-950 text-blue-400 border border-blue-800 font-semibold">
                Puter Core
              </span>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded-md bg-emerald-950/80 text-emerald-400 border border-emerald-800/60 flex items-center gap-1">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
                <span>Self-Hosted</span>
              </span>
            </div>
            <p className="text-[11px] text-slate-400 font-mono flex items-center gap-2 mt-0.5">
              <span>Proxmox Host (192.168.178.105:4100)</span>
              <span className="text-slate-600">•</span>
              <span className="text-slate-300 truncate max-w-[200px] sm:max-w-none">{webosUrl}</span>
            </p>
          </div>
        </div>

        {/* Center / Right Action Buttons */}
        <div className="flex flex-wrap items-center gap-2">
          {/* Quick Preset Selector */}
          <div className="flex items-center p-1 rounded-xl bg-slate-900 border border-slate-800 text-xs font-mono">
            <button
              onClick={() => handleSelectUrl("https://webos.webigo.ai")}
              className={`px-2.5 py-1 rounded-lg transition-all ${
                webosUrl === "https://webos.webigo.ai"
                  ? "bg-blue-600 text-white shadow-md shadow-blue-600/30"
                  : "text-slate-400 hover:text-white"
              }`}
              title="Proxmox Self-Hosted Puter Cluster Node"
            >
              Cluster OS
            </button>
            <button
              onClick={() => handleSelectUrl("https://puter.com")}
              className={`px-2.5 py-1 rounded-lg transition-all ${
                webosUrl === "https://puter.com"
                  ? "bg-blue-600 text-white shadow-md shadow-blue-600/30"
                  : "text-slate-400 hover:text-white"
              }`}
              title="Official Puter Cloud"
            >
              Puter Cloud
            </button>
          </div>

          {/* Custom URL config button */}
          <button
            onClick={() => setShowConfig(!showConfig)}
            className={`p-2 rounded-xl border text-xs transition-colors ${
              showConfig 
                ? "bg-blue-600/20 text-blue-400 border-blue-500/40" 
                : "bg-slate-900 border-slate-800 text-slate-400 hover:text-white"
            }`}
            title="Configure Custom WebOS Endpoint"
          >
            <Sliders className="w-4 h-4" />
          </button>

          {/* Reload Frame Button */}
          <button
            onClick={handleReload}
            className="p-2 rounded-xl bg-slate-900 border border-slate-800 text-slate-400 hover:text-white transition-colors"
            title="Reload WebOS Desktop"
          >
            <RefreshCw className="w-4 h-4" />
          </button>

          {/* Fullscreen Expand */}
          <button
            onClick={() => setIsFullscreen(!isFullscreen)}
            className="px-3 py-1.5 rounded-xl bg-slate-900 border border-slate-800 text-slate-300 hover:text-white text-xs font-medium flex items-center gap-1.5 transition-colors"
            title={isFullscreen ? "Exit Fullscreen" : "Fullscreen WebOS"}
          >
            {isFullscreen ? <Minimize2 className="w-3.5 h-3.5 text-blue-400" /> : <Maximize2 className="w-3.5 h-3.5 text-blue-400" />}
            <span className="hidden sm:inline">{isFullscreen ? "Exit Fullscreen" : "Fullscreen"}</span>
          </button>

          {/* Pop-out external tab */}
          <a
            href={webosUrl}
            target="_blank"
            rel="noreferrer"
            className="px-3 py-1.5 rounded-xl bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white text-xs font-semibold flex items-center gap-1.5 shadow-md shadow-blue-600/20 transition-all"
            title="Open WebOS in a new browser tab"
          >
            <ExternalLink className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Open Tab</span>
          </a>
        </div>
      </div>

      {/* Custom URL Drawer */}
      {showConfig && (
        <form 
          onSubmit={handleSaveCustomUrl}
          className="glass-panel p-3.5 rounded-xl border border-slate-800 flex flex-wrap items-center gap-2 animate-in fade-in slide-in-from-top-2 duration-150"
        >
          <span className="text-xs font-mono text-slate-400">Custom WebOS URL:</span>
          <input
            type="url"
            value={customUrl}
            onChange={(e) => setCustomUrl(e.target.value)}
            placeholder="e.g. https://puter.webigo.ai or http://192.168.178.105:4100"
            className="flex-1 min-w-[240px] bg-slate-900 border border-slate-800 rounded-lg px-3 py-1.5 text-xs text-slate-200 font-mono focus:outline-none focus:border-blue-500"
          />
          <button
            type="submit"
            className="px-3 py-1.5 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-xs font-semibold transition"
          >
            Apply URL
          </button>
          <button
            type="button"
            onClick={() => {
              handleSelectUrl("https://webos.webigo.ai");
              setShowConfig(false);
            }}
            className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-xs transition"
          >
            Reset Default
          </button>
        </form>
      )}

      {/* Main WebOS Desktop Viewport */}
      <div className={`glass-panel rounded-2xl border border-slate-800 shadow-2xl overflow-hidden bg-black flex-1 relative ${
        isFullscreen ? "h-full w-full" : "h-[calc(100vh-210px)] min-h-[640px]"
      }`}>
        <iframe
          key={`${webosUrl}-${reloadKey}`}
          src={webosUrl}
          className="w-full h-full border-0 absolute inset-0"
          allow="clipboard-read; clipboard-write; fullscreen; camera; microphone; geolocation"
          title="Puter WebOS Cloud Operating System"
        />
      </div>

      {/* Bottom Node & Workspace Information Bar (hidden in fullscreen) */}
      {!isFullscreen && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-3 text-xs">
          <div className="glass-panel p-3 rounded-xl border border-slate-800 flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400">
              <CheckCircle2 className="w-4 h-4" />
            </div>
            <div>
              <div className="font-semibold text-slate-200">Cluster Status</div>
              <div className="text-[11px] font-mono text-emerald-400">Live & Proxied via CT 250</div>
            </div>
          </div>

          <div className="glass-panel p-3 rounded-xl border border-slate-800 flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-blue-500/10 border border-blue-500/20 flex items-center justify-center text-blue-400">
              <Server className="w-4 h-4" />
            </div>
            <div>
              <div className="font-semibold text-slate-200">Proxmox Host</div>
              <div className="text-[11px] font-mono text-slate-400">192.168.178.105:4100</div>
            </div>
          </div>

          <div className="glass-panel p-3 rounded-xl border border-slate-800 flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-purple-500/10 border border-purple-500/20 flex items-center justify-center text-purple-400">
              <HardDrive className="w-4 h-4" />
            </div>
            <div>
              <div className="font-semibold text-slate-200">Storage & SQLite</div>
              <div className="text-[11px] font-mono text-purple-400">Fauxqs S3 • DB v81</div>
            </div>
          </div>

          <div className="glass-panel p-3 rounded-xl border border-slate-800 flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-amber-500/10 border border-amber-500/20 flex items-center justify-center text-amber-400">
              <Sparkles className="w-4 h-4" />
            </div>
            <div>
              <div className="font-semibold text-slate-200">Admin Account</div>
              <div className="text-[11px] font-mono text-slate-400">Username: admin</div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
