import type { Metadata } from "next";
import "./globals.css";
import { Providers } from "@/components/Providers";
import { Navbar } from "@/components/Navbar";

export const metadata: Metadata = {
  title: "Webigo Workspaces | Multi-Agent Cloud OS",
  description: "Webigo AI autonomous multi-agent fleet management with ConvexDB and NextAuth",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-slate-950 text-slate-100 flex flex-col selection:bg-blue-600 selection:text-white">
        <Providers>
          <Navbar />
          <main className="flex-1 max-w-7xl w-full mx-auto p-6">{children}</main>
        </Providers>
      </body>
    </html>
  );
}
