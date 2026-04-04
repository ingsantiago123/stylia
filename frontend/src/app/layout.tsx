import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "STYLIA — La precision del estilo. El valor de tu tiempo.",
  description: "STYLIA redefine tu prosa, pule tu voz autoral y te devuelve las horas que perdias editando manualmente.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="es" className="dark">
      <body className="min-h-screen bg-carbon">
        {/* Header — glassmorphism */}
        <header className="fixed top-0 left-0 right-0 z-50 bg-carbon/70 backdrop-blur-2xl border-b border-border-subtle">
          <div className="max-w-[1400px] mx-auto px-6 h-14 flex items-center justify-between">
            <a href="/" className="flex items-center gap-1.5 group">
              <span className="text-xl font-bold tracking-tight text-bruma">
                STYL
              </span>
              <span className="text-xl font-bold tracking-tight text-bruma relative">
                <span className="relative">
                  I
                  <span className="absolute -top-0.5 left-1/2 -translate-x-1/2 w-1.5 h-1.5 bg-krypton rounded-sm group-hover:shadow-glow-sm transition-shadow" />
                </span>
                A
              </span>
              <span className="ml-2 text-[10px] font-medium tracking-[0.2em] uppercase text-plomo-dark hidden sm:block">
                Editor IA
              </span>
            </a>
            <nav className="flex items-center gap-1">
              <a
                href="/"
                className="px-3 py-1.5 text-sm text-plomo hover:text-bruma hover:bg-surface-hover rounded-lg transition-all"
              >
                Documentos
              </a>
              <a
                href="/costs"
                className="px-3 py-1.5 text-sm text-plomo hover:text-bruma hover:bg-surface-hover rounded-lg transition-all"
              >
                Costos
              </a>
              <div className="ml-2 flex items-center gap-2 pl-3 border-l border-border-subtle">
                <div className="w-1.5 h-1.5 rounded-full bg-krypton animate-pulse-slow" />
                <span className="text-[11px] text-plomo-dark font-medium hidden md:block">v0.2</span>
              </div>
            </nav>
          </div>
        </header>

        {/* Main content — offset for fixed header */}
        <main className="pt-14">
          <div className="max-w-[1400px] mx-auto px-6 py-8">
            {children}
          </div>
        </main>

        {/* Footer */}
        <footer className="border-t border-border-subtle mt-16">
          <div className="max-w-[1400px] mx-auto px-6 py-5 flex items-center justify-between">
            <span className="text-xs text-plomo-dark">STYLIA v0.2 — Arquitectura de estilo con IA</span>
            <span className="text-xs text-plomo-dark/50">El valor de tu tiempo.</span>
          </div>
        </footer>
      </body>
    </html>
  );
}
