"use client";

import { GradientBlur } from "@/components/backgrounds/GradientBlur";
import { MagicCard } from "@/components/ui/magic-card";
import { BorderBeam } from "@/components/ui/border-beam";
import { ShimmerButton } from "@/components/ui/shimmer-button";
import { SectionDivider } from "@/components/ui/section-divider";
import { BlurFade } from "@/components/ui/blur-fade";
import { APP_URL } from "@/lib/utils";

const plans = [
  {
    name: "Explorar",
    price: "Gratis",
    period: "",
    description: "Para probar STYLIA con documentos cortos.",
    features: [
      "Hasta 10 páginas por documento",
      "3 documentos al mes",
      "Perfil editorial genérico",
      "Corrección LanguageTool + GPT",
      "Descarga DOCX corregido",
    ],
    cta: "Empezar gratis",
    ctaVariant: "outline" as const,
    highlight: false,
  },
  {
    name: "Profesional",
    price: "$29",
    period: "/mes",
    description: "Para editores, correctores y escritores activos.",
    features: [
      "Hasta 500 páginas por documento",
      "Documentos ilimitados",
      "10 perfiles editoriales + custom",
      "Router inteligente de complejidad",
      "Quality gates y validación INFLESZ",
      "Análisis editorial previo (secciones, glosario)",
      "Descarga DOCX + PDF corregido",
      "Diff word-level con explicaciones",
    ],
    cta: "Comenzar prueba de 14 días",
    ctaVariant: "primary" as const,
    highlight: true,
    badge: "Más popular",
  },
  {
    name: "Editorial",
    price: "$89",
    period: "/mes",
    description: "Para equipos editoriales y agencias de contenido.",
    features: [
      "Hasta 1000 páginas por documento",
      "Documentos ilimitados",
      "Todo lo de Profesional",
      "5 usuarios del equipo",
      "Perfiles compartidos entre equipo",
      "API de integración",
      "Soporte prioritario",
      "Reportes de costos por documento",
    ],
    cta: "Contactar ventas",
    ctaVariant: "outline" as const,
    highlight: false,
  },
];

export function Pricing() {
  return (
    <section id="precios" className="relative section-padding overflow-hidden">
      <GradientBlur variant="section" />
      <SectionDivider variant="fade" className="absolute top-0 left-0 right-0" />

      <div className="container-landing relative z-10">
        <BlurFade>
          <div className="text-center max-w-3xl mx-auto mb-16">
            <p className="text-caption text-krypton font-medium uppercase tracking-widest mb-4">
              Precios
            </p>
            <h2 className="text-heading-1 text-bruma mb-6">
              Un plan para cada{" "}
              <span className="text-gradient-krypton">nivel editorial</span>
            </h2>
            <p className="text-body text-plomo-light">
              Empieza gratis. Escala cuando tu flujo de trabajo lo necesite.
              Sin compromisos, cancela cuando quieras.
            </p>
          </div>
        </BlurFade>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 max-w-6xl mx-auto items-start">
          {plans.map((plan, i) => (
            <BlurFade key={i} delay={i * 120}>
              <MagicCard
                className={`h-full relative ${
                  plan.highlight
                    ? "border-krypton/30 scale-[1.02] md:scale-105"
                    : ""
                }`}
              >
                {plan.highlight && <BorderBeam size={180} duration={5} />}

                {/* Badge */}
                {plan.badge && (
                  <div className="absolute -top-3 left-1/2 -translate-x-1/2">
                    <span className="inline-block px-4 py-1 rounded-full bg-krypton text-carbon text-xs font-bold uppercase tracking-wider">
                      {plan.badge}
                    </span>
                  </div>
                )}

                <div className="p-2">
                  <h3 className="text-heading-3 text-bruma mb-2">{plan.name}</h3>
                  <p className="text-caption text-plomo mb-4">{plan.description}</p>

                  <div className="flex items-baseline gap-1 mb-6">
                    <span className="text-display-2 text-bruma">{plan.price}</span>
                    {plan.period && (
                      <span className="text-body-sm text-plomo">{plan.period}</span>
                    )}
                  </div>

                  {/* Features */}
                  <ul className="space-y-3 mb-8">
                    {plan.features.map((feature, j) => (
                      <li key={j} className="flex items-start gap-2.5 text-body-sm text-plomo-light">
                        <svg
                          className="w-5 h-5 text-krypton flex-shrink-0 mt-0.5"
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
                        {feature}
                      </li>
                    ))}
                  </ul>

                  {/* CTA */}
                  {plan.ctaVariant === "primary" ? (
                    <ShimmerButton href={APP_URL} size="md" className="w-full">
                      {plan.cta}
                    </ShimmerButton>
                  ) : (
                    <a
                      href={APP_URL}
                      className="inline-flex items-center justify-center w-full px-6 py-3.5 rounded-xl text-base font-semibold text-bruma border border-border hover:border-krypton/30 hover:bg-surface-hover transition-all duration-200"
                    >
                      {plan.cta}
                    </a>
                  )}

                  <p className="mt-3 text-center text-caption text-plomo">
                    {plan.highlight
                      ? "14 días gratis, sin tarjeta de crédito"
                      : "Sin compromiso"}
                  </p>
                </div>
              </MagicCard>
            </BlurFade>
          ))}
        </div>
      </div>
    </section>
  );
}
