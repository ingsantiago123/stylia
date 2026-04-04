"use client";

import { GridPattern } from "@/components/backgrounds/GridPattern";
import { BentoGrid, BentoCard } from "@/components/ui/bento-grid";
import { BorderBeam } from "@/components/ui/border-beam";
import { SectionDivider } from "@/components/ui/section-divider";
import { BlurFade } from "@/components/ui/blur-fade";

const features = [
  {
    title: "10 perfiles editoriales",
    description:
      "Novela, ensayo, infantil, juvenil, psicología, marketing, académico, periodismo, técnico y legal. O crea el tuyo propio con tono, audiencia y términos protegidos.",
    icon: (
      <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M15 19.128a9.38 9.38 0 002.625.372 9.337 9.337 0 004.121-.952 4.125 4.125 0 00-7.533-2.493M15 19.128v-.003c0-1.113-.285-2.16-.786-3.07M15 19.128v.106A12.318 12.318 0 018.624 21c-2.331 0-4.512-.645-6.374-1.766l-.001-.109a6.375 6.375 0 0111.964-3.07M12 6.375a3.375 3.375 0 11-6.75 0 3.375 3.375 0 016.75 0zm8.25 2.25a2.625 2.625 0 11-5.25 0 2.625 2.625 0 015.25 0z" />
      </svg>
    ),
    colSpan: 2 as const,
    highlight: true,
  },
  {
    title: "Doble motor de corrección",
    description:
      "LanguageTool para reglas gramaticales y ortográficas. GPT-4o-mini para estilo, claridad y fluidez. Dos capas complementarias, no redundantes.",
    icon: (
      <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 13.5l10.5-11.25L12 10.5h8.25L9.75 21.75 12 13.5H3.75z" />
      </svg>
    ),
    colSpan: 1 as const,
  },
  {
    title: "Formato 100% preservado",
    description:
      "STYLIA corrige directamente sobre el DOCX original. Tipografías, estilos, tablas, encabezados y pies de página se mantienen intactos.",
    icon: (
      <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
      </svg>
    ),
    colSpan: 1 as const,
  },
  {
    title: "Correcciones explicadas",
    description:
      "Cada cambio incluye categoría (ortografía, gramática, estilo, claridad), severidad, explicación detallada y nivel de confianza. Aprende mientras corriges.",
    icon: (
      <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M7.5 8.25h9m-9 3H12m-9.75 1.51c0 1.6 1.123 2.994 2.707 3.227 1.129.166 2.27.293 3.423.379.35.026.67.21.865.501L12 21l2.755-4.133a1.14 1.14 0 01.865-.501 48.172 48.172 0 003.423-.379c1.584-.233 2.707-1.626 2.707-3.228V6.741c0-1.602-1.123-2.995-2.707-3.228A48.394 48.394 0 0012 3c-2.392 0-4.744.175-7.043.513C3.373 3.746 2.25 5.14 2.25 6.741v6.018z" />
      </svg>
    ),
    colSpan: 1 as const,
  },
  {
    title: "Router inteligente de complejidad",
    description:
      "No todos los párrafos necesitan IA. STYLIA clasifica cada uno: SKIP (sin cambios), CHEAP (corrección ligera) o EDITORIAL (revisión profunda). Ahorra tokens y dinero.",
    icon: (
      <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M7.5 21L3 16.5m0 0L7.5 12M3 16.5h13.5m0-13.5L21 7.5m0 0L16.5 12M21 7.5H7.5" />
      </svg>
    ),
    colSpan: 1 as const,
  },
  {
    title: "Quality gates automáticos",
    description:
      "5 validaciones post-corrección: texto no vacío, ratio de expansión, ratio de reescritura, términos protegidos y legibilidad INFLESZ. Si un gate falla, se preserva el original.",
    icon: (
      <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75m-3-7.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285z" />
      </svg>
    ),
    colSpan: 2 as const,
    highlight: true,
  },
  {
    title: "Contexto acumulado entre párrafos",
    description:
      "La IA recuerda los últimos párrafos corregidos y el resumen de la sección actual. Mantiene coherencia de estilo, terminología y tono a lo largo de todo el documento.",
    icon: (
      <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M13.19 8.688a4.5 4.5 0 011.242 7.244l-4.5 4.5a4.5 4.5 0 01-6.364-6.364l1.757-1.757m9.87-9.87a4.5 4.5 0 016.364 6.364l-4.5 4.5a4.5 4.5 0 01-7.244-1.242" />
      </svg>
    ),
    colSpan: 1 as const,
  },
  {
    title: "Análisis editorial previo",
    description:
      "Antes de corregir, STYLIA detecta secciones, extrae un glosario de términos, clasifica cada párrafo por tipo (diálogo, narración, cita...) e infiere el perfil ideal.",
    icon: (
      <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 3v11.25A2.25 2.25 0 006 16.5h2.25M3.75 3h-1.5m1.5 0h16.5m0 0h1.5m-1.5 0v11.25A2.25 2.25 0 0118 16.5h-2.25m-7.5 0h7.5m-7.5 0l-1 3m8.5-3l1 3m0 0l.5 1.5m-.5-1.5h-9.5m0 0l-.5 1.5m.75-9l3-3 2.148 2.148A12.061 12.061 0 0116.5 7.605" />
      </svg>
    ),
    colSpan: 1 as const,
  },
  {
    title: "Pipeline visual en tiempo real",
    description:
      "Observa cada etapa del proceso: ingesta, extracción, análisis, corrección y renderizado. Progreso página por página con previews.",
    icon: (
      <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M2.036 12.322a1.012 1.012 0 010-.639C3.423 7.51 7.36 4.5 12 4.5c4.638 0 8.573 3.007 9.963 7.178.07.207.07.431 0 .639C20.577 16.49 16.64 19.5 12 19.5c-4.638 0-8.573-3.007-9.963-7.178z" />
        <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
      </svg>
    ),
    colSpan: 1 as const,
  },
];

export function Features() {
  return (
    <section id="funcionalidades" className="relative section-padding overflow-hidden">
      <GridPattern strokeColor="rgba(212, 255, 0, 0.04)" />
      <SectionDivider variant="dots" className="absolute top-0 left-0 right-0" />

      <div className="container-landing relative z-10">
        <BlurFade>
          <div className="text-center max-w-3xl mx-auto mb-16">
            <p className="text-caption text-krypton font-medium uppercase tracking-widest mb-4">
              Funcionalidades
            </p>
            <h2 className="text-heading-1 text-bruma mb-6">
              Todo lo que necesitas para{" "}
              <span className="text-gradient-krypton">edición profesional</span>
            </h2>
            <p className="text-body text-plomo-light">
              Más que un corrector: un pipeline editorial completo con
              inteligencia artificial contextual.
            </p>
          </div>
        </BlurFade>

        <BentoGrid className="max-w-6xl mx-auto">
          {features.map((feature, i) => (
            <BlurFade key={i} delay={i * 80}>
              <BentoCard colSpan={feature.colSpan} className="h-full relative">
                {feature.highlight && <BorderBeam size={150} duration={6} />}
                <div className="flex items-start gap-4">
                  <div className="flex-shrink-0 w-10 h-10 rounded-lg bg-krypton/10 flex items-center justify-center text-krypton">
                    {feature.icon}
                  </div>
                  <div>
                    <h3 className="text-heading-3 text-bruma mb-2">
                      {feature.title}
                    </h3>
                    <p className="text-body-sm text-plomo-light leading-relaxed">
                      {feature.description}
                    </p>
                  </div>
                </div>
              </BentoCard>
            </BlurFade>
          ))}
        </BentoGrid>
      </div>
    </section>
  );
}
