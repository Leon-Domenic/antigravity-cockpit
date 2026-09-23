"use client";

import { useLanguage } from "@/contexts/LanguageContext";
import { LocaleKey } from "@/lib/locales";
import { Globe } from "lucide-react";
import { useState, useRef, useEffect } from "react";

const languagesList: { code: LocaleKey; flag: string; name: string }[] = [
  { code: "en", flag: "🇺🇸", name: "English" },
  { code: "zh", flag: "🇨🇳", name: "中文" },
  { code: "hi", flag: "🇮🇳", name: "हिन्दी" },
  { code: "es", flag: "🇪🇸", name: "Español" },
  { code: "fr", flag: "🇫🇷", name: "Français" },
  { code: "ar", flag: "🇸🇦", name: "العربية" },
  { code: "bn", flag: "🇧🇩", name: "বাংলা" },
  { code: "pt", flag: "🇧🇷", name: "Português" },
  { code: "ru", flag: "🇷🇺", name: "Русский" },
  { code: "ur", flag: "🇵🇰", name: "اردو" },
  { code: "id", flag: "🇮🇩", name: "Indonesia" },
  { code: "de", flag: "🇩🇪", name: "Deutsch" },
  { code: "ja", flag: "🇯🇵", name: "日本語" },
  { code: "sw", flag: "🇰🇪", name: "Kiswahili" },
  { code: "mr", flag: "🇮🇳", name: "मराठी" },
  { code: "te", flag: "🇮🇳", name: "తెలుగు" },
  { code: "tr", flag: "🇹🇷", name: "Türkçe" },
  { code: "ko", flag: "🇰🇷", name: "한국어" },
  { code: "ta", flag: "🇮🇳", name: "தமிழ்" },
  { code: "vi", flag: "🇻🇳", name: "Tiếng Việt" },
  { code: "it", flag: "🇮🇹", name: "Italiano" },
];

export function LanguageSelector() {
  const { language, setLanguage } = useLanguage();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const current = languagesList.find((l) => l.code === language) || languagesList[0];

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-slate-900/90 border border-slate-800 text-xs text-slate-300 hover:text-white hover:border-slate-700 transition-colors"
        title="Change language"
      >
        <Globe className="w-3.5 h-3.5 text-indigo-400" />
        <span>{current.flag}</span>
        <span className="hidden sm:inline font-mono">{current.code.toUpperCase()}</span>
      </button>

      {open && (
        <div className="absolute right-0 top-full mt-1.5 w-48 max-h-72 overflow-y-auto rounded-xl bg-slate-900 border border-slate-700 shadow-2xl z-50 py-1">
          {languagesList.map((lang) => (
            <button
              key={lang.code}
              onClick={() => {
                setLanguage(lang.code);
                setOpen(false);
              }}
              className={`w-full text-left px-3 py-2 text-xs flex items-center gap-2.5 transition-colors ${
                language === lang.code
                  ? "bg-indigo-600/20 text-indigo-300"
                  : "text-slate-300 hover:bg-slate-800 hover:text-white"
              }`}
            >
              <span className="text-sm">{lang.flag}</span>
              <span className="font-medium">{lang.name}</span>
              {language === lang.code && (
                <span className="ml-auto text-indigo-400 text-[10px] font-mono">✓</span>
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
