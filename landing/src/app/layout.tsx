import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "STYLIA — Corrección de estilo editorial con IA",
  description:
    "Corrige gramática, ortografía y estilo en documentos DOCX con inteligencia artificial. Pipeline editorial profesional que preserva el formato original.",
  keywords: [
    "corrector de estilo",
    "corrección editorial",
    "IA",
    "DOCX",
    "gramática español",
    "estilo literario",
    "editor de textos",
  ],
  openGraph: {
    title: "STYLIA — Corrección de estilo editorial con IA",
    description:
      "El corrector editorial inteligente que entiende tu texto, no solo tus errores.",
    type: "website",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="es" className="dark">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=JetBrains+Mono:wght@400;500;600&display=swap"
          rel="stylesheet"
        />
      </head>
      <body className="min-h-screen bg-carbon antialiased">{children}</body>
    </html>
  );
}
