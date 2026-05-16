import type { Metadata } from "next";
import "./globals.css";
import { ClientNav } from "@/components/ui/ClientNav";

export const metadata: Metadata = {
  title: "STYLIA — La precisión del estilo. El valor de tu tiempo.",
  description: "STYLIA redefine tu prosa, pule tu voz autoral y te devuelve las horas que perdías editando manualmente.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="es" className="dark">
      <body className="min-h-screen bg-carbon antialiased">
        {/* ── Header ── */}
        <header className="fixed top-0 left-0 right-0 z-50 bg-carbon/80 backdrop-blur-2xl border-b border-border-subtle">
          <div className="max-w-[1400px] mx-auto px-5 h-14 flex items-center justify-between gap-4">

            {/* Logo */}
            <a href="/" className="flex items-center gap-2 shrink-0 group" aria-label="STYLIA – inicio">
              <span className="flex items-center text-xl font-bold tracking-tight text-bruma select-none">
                STYL
                <span className="relative inline-block mx-px">
                  I
                  <span
                    aria-hidden="true"
                    className="absolute -top-0.5 left-1/2 -translate-x-1/2 w-1.5 h-1.5 rounded-sm bg-krypton group-hover:shadow-glow-sm transition-shadow duration-300"
                  />
                </span>
                A
              </span>
              <span className="hidden sm:block text-[10px] font-medium tracking-[0.18em] uppercase text-plomo-dark border-l border-border-subtle pl-2 ml-0.5">
                Editor IA
              </span>
            </a>

            {/* Navigation */}
            <ClientNav />

            {/* Right badge */}
            <div className="flex items-center gap-2 shrink-0">
              <span className="w-1.5 h-1.5 rounded-full bg-krypton animate-pulse-slow" aria-hidden="true" />
              <span className="text-[11px] text-plomo-dark font-medium hidden md:block tabular-nums">
                v0.2
              </span>
            </div>
          </div>
        </header>

        {/* ── Main ── */}
        <main className="pt-14 min-h-[calc(100vh-56px)]">
          <div className="max-w-[1400px] mx-auto px-5 py-8">
            {children}
          </div>
        </main>

        {/* ── Footer ── */}
        <footer className="border-t border-border-subtle mt-8">
          <div className="max-w-[1400px] mx-auto px-5 py-4 flex items-center justify-between gap-4">
            <span className="text-[11px] text-plomo-dark">
              STYLIA v0.2 — Arquitectura de estilo con IA
            </span>
            <span className="text-[11px] text-plomo-dark/40 hidden sm:block">
              El valor de tu tiempo.
            </span>
          </div>
        </footer>
      </body>
    </html>
  );
}
