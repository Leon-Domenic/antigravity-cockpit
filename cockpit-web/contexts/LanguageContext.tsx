"use client";

import React, { createContext, useState, useContext, ReactNode, useCallback, useEffect } from 'react';
import { locales, LocaleKey } from '@/lib/locales';

const get = (obj: any, path: string, defaultValue: any = undefined): string => {
  const keys = path.split('.');
  let result = obj;
  for (const key of keys) {
    result = result?.[key];
    if (result === undefined) break;
  }
  if (result !== undefined && result !== null) return result;
  // Fallback to English
  if (obj !== locales.en && locales.en) {
    let fallbackResult: any = locales.en;
    for (const key of keys) {
      fallbackResult = fallbackResult?.[key];
      if (fallbackResult === undefined) break;
    }
    if (fallbackResult !== undefined && fallbackResult !== null) return fallbackResult;
  }
  return defaultValue !== undefined ? defaultValue : path;
};

type LanguageContextType = {
  language: LocaleKey;
  setLanguage: (language: LocaleKey) => void;
  t: (key: string) => string;
  isRTL: boolean;
};

const LanguageContext = createContext<LanguageContextType | undefined>(undefined);

const RTL_LANGUAGES: LocaleKey[] = ['ar', 'ur'];

export const LanguageProvider = ({ children }: { children: ReactNode }) => {
  const [language, setLanguageState] = useState<LocaleKey>('en');

  useEffect(() => {
    if (typeof window !== 'undefined') {
      const saved = localStorage.getItem('webigo-language');
      if (saved && Object.keys(locales).includes(saved)) {
        setLanguageState(saved as LocaleKey);
        return;
      }
      const browserLang = navigator.language;
      const available = Object.keys(locales) as LocaleKey[];
      if (available.includes(browserLang as LocaleKey)) {
        setLanguageState(browserLang as LocaleKey);
        return;
      }
      const primary = browserLang.split('-')[0] as LocaleKey;
      if (available.includes(primary)) {
        setLanguageState(primary);
      }
    }
  }, []);

  const setLanguage = useCallback((lang: LocaleKey) => {
    setLanguageState(lang);
    if (typeof window !== 'undefined') {
      localStorage.setItem('webigo-language', lang);
      document.documentElement.lang = lang;
      document.documentElement.dir = RTL_LANGUAGES.includes(lang) ? 'rtl' : 'ltr';
    }
  }, []);

  const t = useCallback((key: string): string => {
    return get(locales[language], key);
  }, [language]);

  const isRTL = RTL_LANGUAGES.includes(language);

  return (
    <LanguageContext.Provider value={{ language, setLanguage, t, isRTL }}>
      {children}
    </LanguageContext.Provider>
  );
};

export const useLanguage = () => {
  const context = useContext(LanguageContext);
  if (context === undefined) {
    throw new Error('useLanguage must be used within a LanguageProvider');
  }
  return context;
};
