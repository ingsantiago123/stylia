"use client";

import { SectionDivider } from "@/components/ui/section-divider";
import { APP_URL } from "@/lib/utils";

export function Footer() {
  return (
    <footer className="relative pt-16 pb-8 overflow-hidden">
      <SectionDivider variant="fade" className="absolute top-0 left-0 right-0" />

      <div className="container-landing relative z-10">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-10 mb-12">
          {/* Brand */}
          <div className="md:col-span-1">
            <a href="#" className="flex items-center gap-2 mb-4">
              <div className="relative w-8 h-8 flex items-center justify-center">
                <div className="absolute inset-0 bg-krypton/20 rounded-lg blur-sm" />
                <span className="relative font-bold text-krypton text-lg">S</span>
              </div>
              <span className="font-bold text-bruma text-lg tracking-tight">STYLIA</span>
            </a>
            <p className="text-body-sm text-plomo leading-relaxed">
              Corrección de estilo editorial con inteligencia artificial.
              Pipeline profesional para documentos DOCX en español.
            </p>
          </div>

          {/* Producto */}
          <div>
            <h4 className="text-body-sm text-bruma font-semibold mb-4">Producto</h4>
            <ul className="space-y-2.5">
              <li>
                <a href="#como-funciona" className="text-body-sm text-plomo hover:text-bruma transition-colors">
                  Cómo funciona
                </a>
              </li>
              <li>
                <a href="#funcionalidades" className="text-body-sm text-plomo hover:text-bruma transition-colors">
                  Funcionalidades
                </a>
              </li>
              <li>
                <a href="#precios" className="text-body-sm text-plomo hover:text-bruma transition-colors">
                  Precios
                </a>
              </li>
              <li>
                <a href="#faq" className="text-body-sm text-plomo hover:text-bruma transition-colors">
                  FAQ
                </a>
              </li>
            </ul>
          </div>

          {/* Recursos */}
          <div>
            <h4 className="text-body-sm text-bruma font-semibold mb-4">Recursos</h4>
            <ul className="space-y-2.5">
              <li>
                <a href={`${APP_URL}/docs`} className="text-body-sm text-plomo hover:text-bruma transition-colors">
                  Documentación API
                </a>
              </li>
              <li>
                <a href="#" className="text-body-sm text-plomo hover:text-bruma transition-colors">
                  Guía de perfiles editoriales
                </a>
              </li>
              <li>
                <a href="#" className="text-body-sm text-plomo hover:text-bruma transition-colors">
                  Changelog
                </a>
              </li>
              <li>
                <a href="#" className="text-body-sm text-plomo hover:text-bruma transition-colors">
                  Blog
                </a>
              </li>
            </ul>
          </div>

          {/* Legal */}
          <div>
            <h4 className="text-body-sm text-bruma font-semibold mb-4">Legal</h4>
            <ul className="space-y-2.5">
              <li>
                <a href="#" className="text-body-sm text-plomo hover:text-bruma transition-colors">
                  Términos de servicio
                </a>
              </li>
              <li>
                <a href="#" className="text-body-sm text-plomo hover:text-bruma transition-colors">
                  Política de privacidad
                </a>
              </li>
              <li>
                <a href="#" className="text-body-sm text-plomo hover:text-bruma transition-colors">
                  Política de cookies
                </a>
              </li>
            </ul>
          </div>
        </div>

        {/* Bottom bar */}
        <div className="pt-8 border-t border-border flex flex-col sm:flex-row items-center justify-between gap-4">
          <p className="text-caption text-plomo">
            &copy; {new Date().getFullYear()} STYLIA. Todos los derechos reservados.
          </p>
          <div className="flex items-center gap-4">
            <a
              href={APP_URL}
              className="inline-flex items-center gap-2 text-caption text-krypton hover:text-krypton-100 font-medium transition-colors"
            >
              Abrir aplicación
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 6H5.25A2.25 2.25 0 003 8.25v10.5A2.25 2.25 0 005.25 21h10.5A2.25 2.25 0 0018 18.75V10.5m-10.5 6L21 3m0 0h-5.25M21 3v5.25" />
              </svg>
            </a>
          </div>
        </div>
      </div>
    </footer>
  );
}
