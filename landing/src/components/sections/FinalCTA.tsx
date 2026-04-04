"use client";

import { GradientBlur } from "@/components/backgrounds/GradientBlur";
import { DotPattern } from "@/components/backgrounds/DotPattern";
import { ShimmerButton } from "@/components/ui/shimmer-button";
import { SparklesText } from "@/components/ui/sparkles-text";
import { SectionDivider } from "@/components/ui/section-divider";
import { BlurFade } from "@/components/ui/blur-fade";
import { APP_URL } from "@/lib/utils";

export function FinalCTA() {
  return (
    <section className="relative section-padding overflow-hidden">
      <GradientBlur variant="cta" />
      <DotPattern className="opacity-20" dotColor="rgba(212, 255, 0, 0.08)" />
      <SectionDivider variant="fade" className="absolute top-0 left-0 right-0" />

      <div className="container-landing relative z-10 text-center max-w-3xl mx-auto">
        <BlurFade>
          <p className="text-caption text-krypton font-medium uppercase tracking-widest mb-6">
            Empieza ahora
          </p>
          <h2 className="text-display-2 text-bruma mb-6">
            Tu próximo documento merece{" "}
            <SparklesText>
              <span className="text-gradient-krypton">corrección profesional</span>
            </SparklesText>
          </h2>
          <p className="text-body-lg text-plomo-light mb-10 max-w-2xl mx-auto">
            Sube tu primer DOCX, elige un perfil editorial y recibe
            correcciones explicadas en minutos. Sin registro obligatorio para
            documentos cortos.
          </p>
        </BlurFade>

        <BlurFade delay={200}>
          <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
            <ShimmerButton href={APP_URL} size="lg">
              Abrir STYLIA
              <svg
                className="w-5 h-5"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                strokeWidth={2}
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M13 7l5 5m0 0l-5 5m5-5H6"
                />
              </svg>
            </ShimmerButton>
            <a
              href="#precios"
              className="inline-flex items-center gap-2 px-8 py-3.5 rounded-xl text-base font-medium text-bruma border border-border hover:border-krypton/30 hover:bg-surface/50 transition-all duration-200"
            >
              Ver planes y precios
            </a>
          </div>
        </BlurFade>

        <BlurFade delay={300}>
          <div className="mt-10 flex flex-wrap items-center justify-center gap-6 text-caption text-plomo">
            <span className="flex items-center gap-2">
              <svg className="w-4 h-4 text-krypton" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
              </svg>
              Sin tarjeta de crédito
            </span>
            <span className="flex items-center gap-2">
              <svg className="w-4 h-4 text-krypton" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
              </svg>
              Formato preservado
            </span>
            <span className="flex items-center gap-2">
              <svg className="w-4 h-4 text-krypton" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
              </svg>
              Correcciones explicadas
            </span>
          </div>
        </BlurFade>
      </div>
    </section>
  );
}
