"use client";

import { useState, useEffect } from "react";
import { cn } from "@/lib/utils";
import { APP_URL } from "@/lib/utils";

export function Navbar() {
  const [scrolled, setScrolled] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(() => {
    let ticking = false;

    const onScroll = () => {
      if (ticking) return;

      ticking = true;
      requestAnimationFrame(() => {
        const nextScrolled = window.scrollY > 20;
        setScrolled((prev) => (prev === nextScrolled ? prev : nextScrolled));
        ticking = false;
      });
    };

    window.addEventListener("scroll", onScroll, { passive: true });
    onScroll();

    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  const navLinks = [
    { label: "El viaje", href: "#journey" },
    { label: "Cargar", href: "#stage-1" },
    { label: "Análisis", href: "#stage-2" },
    { label: "Edición", href: "#stage-4" },
    { label: "Revisión", href: "#stage-5" },
    { label: "Entregar", href: "#stage-6" },
  ];

  return (
    <nav
      className={cn(
        "fixed top-0 left-0 right-0 z-50 transition-all duration-300",
        scrolled
          ? "bg-carbon/80 backdrop-blur-xl border-b border-border shadow-lg"
          : "bg-transparent"
      )}
    >
      <div className="container-landing flex items-center justify-between h-16 md:h-18">
        {/* Logo */}
        <a href="#" className="flex items-center gap-2 group">
          <div className="relative w-8 h-8 flex items-center justify-center">
            <div className="absolute inset-0 bg-krypton/20 rounded-lg blur-sm group-hover:bg-krypton/30 transition-colors" />
            <span className="relative font-bold text-krypton text-lg">S</span>
          </div>
          <span className="font-bold text-bruma text-lg tracking-tight">
            STYLIA
          </span>
        </a>

        {/* Desktop nav */}
        <div className="hidden lg:flex items-center gap-8">
          {navLinks.map((link) => (
            <a
              key={link.href}
              href={link.href}
              className="text-sm text-plomo hover:text-bruma transition-colors duration-200"
            >
              {link.label}
            </a>
          ))}
        </div>

        {/* CTA */}
        <div className="hidden lg:flex items-center gap-3">
          <a
            href={APP_URL}
            className={cn(
              "inline-flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-semibold",
              "bg-krypton text-carbon",
              "hover:shadow-glow-sm hover:scale-[1.02] active:scale-[0.98]",
              "transition-all duration-200"
            )}
          >
            Abrir STYLIA
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M13 7l5 5m0 0l-5 5m5-5H6" />
            </svg>
          </a>
        </div>

        {/* Mobile toggle */}
        <button
          onClick={() => setMobileOpen(!mobileOpen)}
          className="lg:hidden p-2 text-plomo hover:text-bruma"
          aria-label="Menu"
        >
          <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            {mobileOpen ? (
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            ) : (
              <path strokeLinecap="round" strokeLinejoin="round" d="M4 6h16M4 12h16M4 18h16" />
            )}
          </svg>
        </button>
      </div>

      {/* Mobile menu */}
      {mobileOpen && (
        <div className="lg:hidden bg-carbon/95 backdrop-blur-xl border-b border-border">
          <div className="container-landing py-4 flex flex-col gap-3">
            {navLinks.map((link) => (
              <a
                key={link.href}
                href={link.href}
                onClick={() => setMobileOpen(false)}
                className="text-sm text-plomo hover:text-bruma py-2 transition-colors"
              >
                {link.label}
              </a>
            ))}
            <a
              href={APP_URL}
              className="inline-flex items-center justify-center gap-2 px-5 py-3 rounded-xl text-sm font-semibold bg-krypton text-carbon mt-2"
            >
              Abrir STYLIA
            </a>
          </div>
        </div>
      )}
    </nav>
  );
}
