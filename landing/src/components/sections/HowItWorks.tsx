"use client";

import { GradientBlur } from "@/components/backgrounds/GradientBlur";
import { ShineBorder } from "@/components/ui/shine-border";
import { SectionDivider } from "@/components/ui/section-divider";
import { BlurFade } from "@/components/ui/blur-fade";

const steps = [
  {
    number: "01",
    title: "Sube tu documento DOCX",
    description:
      "Arrastra y suelta tu archivo. STYLIA lo ingesta, convierte a PDF para preview y extrae cada párrafo con su posición exacta en el documento.",
    detail: "Formatos: DOCX hasta 500 MB y 1000 páginas. Tu archivo original se preserva intacto.",
    icon: (
      <svg className="w-10 h-10" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" />
      </svg>
    ),
  },
  {
    number: "02",
    title: "Elige tu perfil editorial",
    description:
      "Selecciona entre 10 perfiles predeterminados (novela, ensayo, infantil, marketing...) o personaliza tono, audiencia, nivel de intervención y términos protegidos.",
    detail: "El perfil guía a la IA para que corrija según tu contexto, no con reglas genéricas.",
    icon: (
      <svg className="w-10 h-10" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M9.594 3.94c.09-.542.56-.94 1.11-.94h2.593c.55 0 1.02.398 1.11.94l.213 1.281c.063.374.313.686.645.87.074.04.147.083.22.127.324.196.72.257 1.075.124l1.217-.456a1.125 1.125 0 011.37.49l1.296 2.247a1.125 1.125 0 01-.26 1.431l-1.003.827c-.293.24-.438.613-.431.992a6.759 6.759 0 010 .255c-.007.378.138.75.43.99l1.005.828c.424.35.534.954.26 1.43l-1.298 2.247a1.125 1.125 0 01-1.369.491l-1.217-.456c-.355-.133-.75-.072-1.076.124a6.57 6.57 0 01-.22.128c-.331.183-.581.495-.644.869l-.213 1.28c-.09.543-.56.941-1.11.941h-2.594c-.55 0-1.02-.398-1.11-.94l-.213-1.281c-.062-.374-.312-.686-.644-.87a6.52 6.52 0 01-.22-.127c-.325-.196-.72-.257-1.076-.124l-1.217.456a1.125 1.125 0 01-1.369-.49l-1.297-2.247a1.125 1.125 0 01.26-1.431l1.004-.827c.292-.24.437-.613.43-.992a6.932 6.932 0 010-.255c.007-.378-.138-.75-.43-.99l-1.004-.828a1.125 1.125 0 01-.26-1.43l1.297-2.247a1.125 1.125 0 011.37-.491l1.216.456c.356.133.751.072 1.076-.124.072-.044.146-.087.22-.128.332-.183.582-.495.644-.869l.214-1.281z" />
        <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
      </svg>
    ),
  },
  {
    number: "03",
    title: "Pipeline de doble motor",
    description:
      "Cada párrafo pasa por LanguageTool (gramática y ortografía) y luego por GPT-4o-mini (estilo, claridad, fluidez) con contexto de los párrafos anteriores.",
    detail: "Router inteligente: los párrafos simples se saltan la IA; los complejos reciben corrección editorial profunda.",
    icon: (
      <svg className="w-10 h-10" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M9.75 3.104v5.714a2.25 2.25 0 01-.659 1.591L5 14.5M9.75 3.104c-.251.023-.501.05-.75.082m.75-.082a24.301 24.301 0 014.5 0m0 0v5.714c0 .597.237 1.17.659 1.591L19.8 15.3M14.25 3.104c.251.023.501.05.75.082M19.8 15.3l-1.57.393A9.065 9.065 0 0112 15a9.065 9.065 0 00-6.23.693L5 14.5m14.8.8l1.402 1.402c1.232 1.232.65 3.318-1.067 3.611A48.309 48.309 0 0112 21c-2.773 0-5.491-.235-8.135-.687-1.718-.293-2.3-2.379-1.067-3.61L5 14.5" />
      </svg>
    ),
  },
  {
    number: "04",
    title: "Recibe correcciones explicadas",
    description:
      "Cada cambio incluye categoría, severidad, explicación y nivel de confianza. Validación automática con quality gates para garantizar la integridad del texto.",
    detail: "Descarga tu DOCX o PDF corregido con el formato original intacto.",
    icon: (
      <svg className="w-10 h-10" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12c0 1.268-.63 2.39-1.593 3.068a3.745 3.745 0 01-1.043 3.296 3.745 3.745 0 01-3.296 1.043A3.745 3.745 0 0112 21c-1.268 0-2.39-.63-3.068-1.593a3.746 3.746 0 01-3.296-1.043 3.745 3.745 0 01-1.043-3.296A3.745 3.745 0 013 12c0-1.268.63-2.39 1.593-3.068a3.745 3.745 0 011.043-3.296 3.746 3.746 0 013.296-1.043A3.746 3.746 0 0112 3c1.268 0 2.39.63 3.068 1.593a3.746 3.746 0 013.296 1.043 3.746 3.746 0 011.043 3.296A3.745 3.745 0 0121 12z" />
      </svg>
    ),
  },
];

export function HowItWorks() {
  return (
    <section id="como-funciona" className="relative section-padding overflow-hidden">
      <GradientBlur variant="section" />
      <SectionDivider variant="fade" className="absolute top-0 left-0 right-0" />

      <div className="container-landing relative z-10">
        <BlurFade>
          <div className="text-center max-w-3xl mx-auto mb-20">
            <p className="text-caption text-krypton font-medium uppercase tracking-widest mb-4">
              Cómo funciona
            </p>
            <h2 className="text-heading-1 text-bruma mb-6">
              De documento sin revisar a{" "}
              <span className="text-gradient-krypton">texto editorial</span> en 4 pasos
            </h2>
            <p className="text-body text-plomo-light">
              Un pipeline profesional que combina reglas lingüísticas con
              inteligencia artificial contextual.
            </p>
          </div>
        </BlurFade>

        <div className="max-w-4xl mx-auto">
          {steps.map((step, i) => (
            <BlurFade key={i} delay={i * 120} direction={i % 2 === 0 ? "left" : "right"}>
              <div className="relative flex gap-6 md:gap-10 mb-12 last:mb-0">
                {/* Vertical connector line */}
                {i < steps.length - 1 && (
                  <div className="absolute left-6 md:left-8 top-20 bottom-0 w-px bg-gradient-to-b from-krypton/30 to-transparent" />
                )}

                {/* Step number circle */}
                <div className="flex-shrink-0">
                  <ShineBorder className="!rounded-xl">
                    <div className="w-12 h-12 md:w-16 md:h-16 flex items-center justify-center rounded-xl bg-carbon">
                      <span className="text-krypton font-bold text-lg md:text-xl font-mono">
                        {step.number}
                      </span>
                    </div>
                  </ShineBorder>
                </div>

                {/* Content */}
                <div className="flex-1 pb-8">
                  <div className="flex items-start gap-4 mb-3">
                    <div className="text-krypton/50 hidden sm:block">{step.icon}</div>
                    <div>
                      <h3 className="text-heading-3 text-bruma mb-2">{step.title}</h3>
                      <p className="text-body-sm text-plomo-light mb-3">{step.description}</p>
                      <p className="text-caption text-plomo bg-surface/50 rounded-lg px-4 py-2 border border-border/50 inline-block">
                        {step.detail}
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            </BlurFade>
          ))}
        </div>
      </div>
    </section>
  );
}
