"use client";

import { SessionProvider } from "next-auth/react";
import { ConvexProvider, ConvexReactClient } from "convex/react";
import { LanguageProvider } from "@/contexts/LanguageContext";

const convexUrl = process.env.NEXT_PUBLIC_CONVEX_URL || "http://127.0.0.1:3210";
const convex = new ConvexReactClient(convexUrl);

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <SessionProvider>
      <ConvexProvider client={convex}>
        <LanguageProvider>
          {children}
        </LanguageProvider>
      </ConvexProvider>
    </SessionProvider>
  );
}
