"use client";

import { DotPattern } from "@/components/backgrounds/DotPattern";
import { MagicCard } from "@/components/ui/magic-card";
import { SectionDivider } from "@/components/ui/section-divider";
import { BlurFade } from "@/components/ui/blur-fade";

const painPoints = [
  {
    icon: (
      <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
    ),
    title: "Horas revisando párrafo por párrafo",
    description:
      "Un documento de 100 páginas puede tomar días de revisión manual. Cada párrafo requiere atención a gramática, estilo, tono y coherencia simultáneamente.",
  },
  {
    icon: (
      <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M7.5 21L3 16.5m0 0L7.5 12M3 16.5h13.5m0-13.5L21 7.5m0 0L16.5 12M21 7.5H7.5" />
      </svg>
    ),
    title: "Correctores genéricos que ignoran el contexto",
    description:
      "Las herramientas estándar tratan igual una novela que un informe técnico. No entienden tu género, tu audiencia ni el nivel de intervención que necesitas.",
  },
  {
    icon: (
      <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
      </svg>
    ),
    title: "Formato destruido al corregir",
    description:
      "Copiar a Google Docs o Word Online para revisar rompe estilos, tipografías y maquetación. Horas de trabajo de diseño perdidas en cada iteración.",
  },
  {
    icon: (
      <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M3.98 8.223A10.477 10.477 0 001.934 12C3.226 16.338 7.244 19.5 12 19.5c.993 0 1.953-.138 2.863-.395M6.228 6.228A10.45 10.45 0 0112 4.5c4.756 0 8.773 3.162 10.065 7.498a10.523 10.523 0 01-4.293 5.774M6.228 6.228L3 3m3.228 3.228l3.65 3.65m7.894 7.894L21 21m-3.228-3.228l-3.65-3.65m0 0a3 3 0 10-4.243-4.243m4.242 4.242L9.88 9.88" />
      </svg>
    ),
    title: "Correcciones sin explicación ni transparencia",
    description:
      "Las herramientas cambian tu texto sin decirte por qué. Aceptas o rechazas a ciegas, sin aprender ni controlar el resultado final.",
  },
];

export function PainSection() {
  return (
    <section id="problema" className="relative section-padding overflow-hidden">
      <DotPattern className="opacity-40" />
      <SectionDivider variant="fade" className="absolute top-0 left-0 right-0" />

      <div className="container-landing relative z-10">
        <BlurFade>
          <div className="text-center max-w-3xl mx-auto mb-16">
            <p className="text-caption text-krypton font-medium uppercase tracking-widest mb-4">
              El problema
            </p>
            <h2 className="text-heading-1 text-bruma mb-6">
              Editar textos profesionales no debería ser{" "}
              <span className="text-gradient-krypton">tan lento ni tan ciego</span>
            </h2>
            <p className="text-body text-plomo-light">
              Los equipos editoriales pierden tiempo y calidad con herramientas
              que no fueron diseñadas para corrección de estilo real.
            </p>
          </div>
        </BlurFade>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 max-w-5xl mx-auto">
          {painPoints.map((pain, i) => (
            <BlurFade key={i} delay={i * 100}>
              <MagicCard className="h-full">
                <div className="text-krypton/60 mb-4">{pain.icon}</div>
                <h3 className="text-heading-3 text-bruma mb-3">{pain.title}</h3>
                <p className="text-body-sm text-plomo-light leading-relaxed">
                  {pain.description}
                </p>
              </MagicCard>
            </BlurFade>
          ))}
        </div>
      </div>
    </section>
  );
}
