"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useSession, signOut } from "next-auth/react";
import { useLanguage } from "@/contexts/LanguageContext";
import { LanguageSelector } from "@/components/LanguageSelector";
import { 
  Server, 
  FolderGit2, 
  Cpu, 
  Settings, 
  LogOut, 
  Activity,
  Zap
} from "lucide-react";

export function Navbar() {
  const pathname = usePathname();
  const { data: session } = useSession();
  const { t } = useLanguage();

  if (pathname === "/login") return null;

  const navLinks = [
    { href: "/fleet", label: t("nav.fleet"), icon: Server },
    { href: "/workspaces", label: t("nav.workspaces"), icon: FolderGit2 },
    { href: "/ceo", label: t("nav.ceo"), icon: Cpu },
    { href: "/settings", label: t("nav.settings"), icon: Settings },
  ];

  return (
    <header className="sticky top-0 z-50 glass-panel border-b border-slate-800/80 px-6 py-3">
      <div className="max-w-7xl mx-auto flex items-center justify-between">
        {/* Brand / Logo */}
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-gradient-to-tr from-sky-500 to-indigo-500 flex items-center justify-center shadow-lg shadow-indigo-500/20">
            <Zap className="w-5 h-5 text-white" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-bold tracking-tight text-white text-base">{t("brand.name")}</span>
              <span className="text-xs px-2 py-0.5 rounded bg-indigo-950 text-indigo-400 border border-indigo-800 font-mono">
                {t("brand.tag")}
              </span>
            </div>
            <div className="text-[11px] text-slate-400 font-mono flex items-center gap-1.5">
              <span>{t("brand.subtitle")}</span>
              <span className="text-slate-600">•</span>
              <span className="text-emerald-400 flex items-center gap-1">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
                {t("brand.dbStatus")}
              </span>
            </div>
          </div>
        </div>

        {/* Navigation Tabs */}
        <nav className="flex items-center gap-1">
          {navLinks.map((link) => {
            const Icon = link.icon;
            const isActive = pathname.startsWith(link.href);
            return (
              <Link
                key={link.href}
                href={link.href}
                className={`flex items-center gap-2 px-3.5 py-2 rounded-lg text-sm font-medium transition-all ${
                  isActive
                    ? "bg-indigo-600/20 text-indigo-400 border border-indigo-500/30"
                    : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/50"
                }`}
              >
                <Icon className="w-4 h-4" />
                <span>{link.label}</span>
              </Link>
            );
          })}
        </nav>

        {/* User Session, Language & Status */}
        <div className="flex items-center gap-3">
          <LanguageSelector />

          <div className="hidden lg:flex items-center gap-2 text-xs font-mono px-3 py-1.5 rounded-lg bg-slate-900/90 border border-slate-800 text-slate-400">
            <Activity className="w-3.5 h-3.5 text-indigo-400" />
            <span>{t("nav.node")}: pve</span>
            <span className="text-slate-600">|</span>
            <span className="text-slate-300">192.168.178.105</span>
          </div>

          {session?.user ? (
            <div className="flex items-center gap-2 pl-2 border-l border-slate-800">
              <div className="flex flex-col text-right">
                <span className="text-xs font-medium text-slate-200">
                  {session.user.name || session.user.email}
                </span>
                <span className="text-[10px] text-indigo-400 font-mono capitalize">
                  {(session.user as any).role || "admin"}
                </span>
              </div>
              <button
                onClick={() => signOut({ callbackUrl: "/login" })}
                title={t("common.signOut")}
                className="p-2 rounded-lg text-slate-400 hover:text-rose-400 hover:bg-rose-950/20 transition-colors"
              >
                <LogOut className="w-4 h-4" />
              </button>
            </div>
          ) : (
            <Link
              href="/login"
              className="text-xs font-medium px-3.5 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white transition-all shadow-md shadow-indigo-600/20"
            >
              {t("common.signIn")}
            </Link>
          )}
        </div>
      </div>
    </header>
  );
}
