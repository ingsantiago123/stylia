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
              <a
                href="/audit"
                className="px-3 py-1.5 text-sm text-plomo hover:text-bruma hover:bg-surface-hover rounded-lg transition-all flex items-center gap-1.5"
              >
                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h3.75M9 15h3.75M9 18h3.75m3 .75H18a2.25 2.25 0 002.25-2.25V6.108c0-1.135-.845-2.098-1.976-2.192a48.424 48.424 0 00-1.123-.08m-5.801 0c-.065.21-.1.433-.1.664 0 .414.336.75.75.75h4.5a.75.75 0 00.75-.75 2.25 2.25 0 00-.1-.664m-5.8 0A2.251 2.251 0 0113.5 2.25H15c1.012 0 1.867.668 2.15 1.586m-5.8 0c-.376.023-.75.05-1.124.08C9.095 4.01 8.25 4.973 8.25 6.108V8.25m0 0H4.875c-.621 0-1.125.504-1.125 1.125v11.25c0 .621.504 1.125 1.125 1.125h9.75c.621 0 1.125-.504 1.125-1.125V9.375c0-.621-.504-1.125-1.125-1.125H8.25zM6.75 12h.008v.008H6.75V12zm0 3h.008v.008H6.75V15zm0 3h.008v.008H6.75V18z" />
                </svg>
                Auditoría
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
