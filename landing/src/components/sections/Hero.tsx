"use client";

import { useEffect, useState } from "react";
import { GradientBlur } from "@/components/backgrounds/GradientBlur";
import { ParticleTextEffect } from "@/components/backgrounds/ParticleTextEffect";
import { AnimatedGradientText } from "@/components/ui/animated-gradient-text";
import { ShimmerButton } from "@/components/ui/shimmer-button";
import { WordRotate } from "@/components/ui/word-rotate";
import { BlurFade } from "@/components/ui/blur-fade";
import { APP_URL } from "@/lib/utils";

export function Hero() {
  const [enableParticles, setEnableParticles] = useState(true);

  useEffect(() => {
    const mediaQuery = window.matchMedia("(prefers-reduced-motion: reduce)");

    const updateParticles = () => {
      setEnableParticles(!mediaQuery.matches);
    };

    updateParticles();
    mediaQuery.addEventListener("change", updateParticles);

    return () => {
      mediaQuery.removeEventListener("change", updateParticles);
    };
  }, []);

  return (
    <section className="relative min-h-screen flex items-center justify-center overflow-hidden pt-16">
      {/* Backgrounds: ParticleTextEffect (21st.dev) + GradientBlur */}
      {enableParticles && (
        <ParticleTextEffect
          words={["STYLIA", "CORRIGE", "EDITA", "ESTILO", "FLUYE"]}
          opacity={0.28}
        />
      )}
      <GradientBlur variant="hero" />

      <div className="container-landing relative z-10 text-center max-w-5xl py-20">
        {/* Badge */}
        <BlurFade delay={0}>
          <div className="flex justify-center mb-8">
            <AnimatedGradientText>
              <span className="mr-1">&#9889;</span>
              Pipeline editorial con IA &mdash; Doble motor de corrección
            </AnimatedGradientText>
          </div>
        </BlurFade>

        {/* Headline */}
        <BlurFade delay={100}>
          <h1 className="text-display-1 text-bruma mb-6 max-w-4xl mx-auto">
            Tu texto merece más que un{" "}
            <span className="text-gradient-krypton">corrector ortográfico</span>
          </h1>
        </BlurFade>

        {/* Subheadline with WordRotate */}
        <BlurFade delay={200}>
          <p className="text-body-lg text-plomo-light max-w-2xl mx-auto mb-4">
            STYLIA analiza gramática, ortografía y estilo editorial en
            documentos DOCX. Un pipeline profesional que corrige{" "}
            <WordRotate
              words={[
                "novelas",
                "ensayos",
                "artículos",
                "tesis",
                "manuales",
                "contenido web",
              ]}
              className="text-krypton font-semibold"
            />{" "}
            preservando tu formato original.
          </p>
        </BlurFade>

        <BlurFade delay={250}>
          <p className="text-body-sm text-plomo max-w-xl mx-auto mb-10">
            Sube tu documento. Elige un perfil editorial. Recibe correcciones
            explicadas párrafo por párrafo en minutos.
          </p>
        </BlurFade>

        {/* CTAs */}
        <BlurFade delay={350}>
          <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
            <ShimmerButton href={APP_URL} size="lg">
              Corregir mi primer documento
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
              href="#como-funciona"
              className="inline-flex items-center gap-2 px-8 py-3.5 rounded-xl text-base font-medium text-bruma border border-border hover:border-krypton/30 hover:bg-surface/50 transition-all duration-200"
            >
              Ver cómo funciona
              <svg
                className="w-4 h-4"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                strokeWidth={2}
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M19 14l-7 7m0 0l-7-7m7 7V3"
                />
              </svg>
            </a>
          </div>
        </BlurFade>

        {/* Anti-friction microcopy */}
        <BlurFade delay={450}>
          <p className="mt-6 text-caption text-plomo">
            Sin registro obligatorio &middot; Gratis para documentos cortos
            &middot; Tu archivo nunca se comparte
          </p>
        </BlurFade>

      </div>
    </section>
  );
}
