"use client";

import { GradientBlur } from "@/components/backgrounds/GradientBlur";
import { NumberTicker } from "@/components/ui/number-ticker";
import { ShineBorder } from "@/components/ui/shine-border";
import { SectionDivider } from "@/components/ui/section-divider";
import { BlurFade } from "@/components/ui/blur-fade";

const stats = [
  {
    value: 6,
    suffix: "",
    label: "Etapas del pipeline",
    description: "Ingesta, extracción, análisis, corrección, validación, renderizado",
  },
  {
    value: 10,
    suffix: "+",
    label: "Perfiles editoriales",
    description: "Presets para cada género y audiencia, más perfiles custom",
  },
  {
    value: 5,
    suffix: "",
    label: "Quality gates",
    description: "Validaciones automáticas post-corrección para cada párrafo",
  },
  {
    value: 110,
    suffix: "%",
    label: "Límite de expansión",
    description: "El texto corregido nunca excede el 110% del original",
  },
];

const capabilities = [
  "Corrección ortográfica con LanguageTool",
  "Corrección gramatical contextual",
  "Mejora de estilo editorial con IA",
  "Detección automática de secciones",
  "Glosario de términos extraído del texto",
  "Clasificación de párrafos por tipo",
  "Diff word-level de cada corrección",
  "Router SKIP / CHEAP / EDITORIAL",
  "Índice de legibilidad INFLESZ",
  "Descarga DOCX y PDF corregidos",
];

export function Stats() {
  return (
    <section id="resultados" className="relative section-padding overflow-hidden">
      <GradientBlur variant="section" />
      <SectionDivider variant="fade" className="absolute top-0 left-0 right-0" />

      <div className="container-landing relative z-10">
        <BlurFade>
          <div className="text-center max-w-3xl mx-auto mb-16">
            <p className="text-caption text-krypton font-medium uppercase tracking-widest mb-4">
              Capacidades
            </p>
            <h2 className="text-heading-1 text-bruma mb-6">
              Un sistema diseñado para{" "}
              <span className="text-gradient-krypton">calidad editorial real</span>
            </h2>
          </div>
        </BlurFade>

        {/* Stats grid */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 max-w-5xl mx-auto mb-20">
          {stats.map((stat, i) => (
            <BlurFade key={i} delay={i * 100}>
              <ShineBorder>
                <div className="p-6 text-center">
                  <div className="text-display-2 text-krypton font-bold mb-2">
                    <NumberTicker value={stat.value} suffix={stat.suffix} />
                  </div>
                  <p className="text-body-sm text-bruma font-medium mb-1">{stat.label}</p>
                  <p className="text-caption text-plomo">{stat.description}</p>
                </div>
              </ShineBorder>
            </BlurFade>
          ))}
        </div>

        {/* Capabilities list */}
        <BlurFade delay={200}>
          <div className="max-w-3xl mx-auto">
            <h3 className="text-heading-3 text-bruma text-center mb-8">
              Todo incluido en cada corrección
            </h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {capabilities.map((cap, i) => (
                <div
                  key={i}
                  className="flex items-center gap-3 text-body-sm text-plomo-light"
                >
                  <svg
                    className="w-5 h-5 text-krypton flex-shrink-0"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                    strokeWidth={2}
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d="M4.5 12.75l6 6 9-13.5"
                    />
                  </svg>
                  {cap}
                </div>
              ))}
            </div>
          </div>
        </BlurFade>
      </div>
    </section>
  );
}
