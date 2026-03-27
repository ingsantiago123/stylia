import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "STYLIA — La precisión del estilo. El valor de tu tiempo.",
  description: "STYLIA redefine tu prosa, pule tu voz autoral y te devuelve las horas que perdías editando manualmente.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="es" className="dark">
      <body className="min-h-screen bg-carbon">
        {/* Header */}
        <header className="border-b border-carbon-50 px-6 py-4 bg-carbon-200/80 backdrop-blur-md sticky top-0 z-50">
          <div className="max-w-7xl mx-auto flex items-center justify-between">
            <a href="/" className="flex items-center gap-1 group">
              <span className="text-2xl font-bold tracking-tight text-bruma">
                STYL
              </span>
              <span className="text-2xl font-bold tracking-tight text-bruma relative">
                <span className="relative">
                  I
                  <span className="absolute -top-0.5 left-1/2 -translate-x-1/2 w-1.5 h-1.5 bg-krypton rounded-sm" />
                </span>
                A
              </span>
            </a>
            <div className="flex items-center gap-4">
              <a href="/costs" className="text-xs text-plomo hover:text-krypton transition-colors">
                Costos
              </a>
              <span className="text-xs text-plomo font-light tracking-widest uppercase">
                La precisión del estilo
              </span>
              <div className="w-2 h-2 rounded-full bg-krypton animate-pulse-slow" />
            </div>
          </div>
        </header>

        {/* Main content */}
        <main className="max-w-7xl mx-auto px-6 py-8">{children}</main>

        {/* Footer */}
        <footer className="border-t border-carbon-50 px-6 py-6 mt-12">
          <div className="max-w-7xl mx-auto flex items-center justify-between text-xs text-plomo">
            <span>STYLIA v0.1 — Arquitectura de estilo con IA</span>
            <span className="text-carbon-50">El valor de tu tiempo.</span>
          </div>
        </footer>
      </body>
    </html>
  );
}
