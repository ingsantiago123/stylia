"use client";

import { DotPattern } from "@/components/backgrounds/DotPattern";
import { Marquee } from "@/components/ui/marquee";
import { SectionDivider } from "@/components/ui/section-divider";
import { BlurFade } from "@/components/ui/blur-fade";

const testimonials = [
  {
    name: "Ana Martínez",
    role: "Editora de ficción, Editorial Horizonte",
    quote:
      "Antes tardaba 3 días en revisar un manuscrito de 200 páginas. Con STYLIA lo reduzco a una tarde de revisión final. La IA entiende la diferencia entre narración y diálogo.",
    avatar: "/images/placeholders/avatar-1.png",
  },
  {
    name: "Carlos Vega",
    role: "Director de contenidos, Agencia Redacta",
    quote:
      "Lo que más valoro es la explicación de cada corrección. Mi equipo está aprendiendo mientras trabaja. Es formación continua integrada en el flujo de producción.",
    avatar: "/images/placeholders/avatar-2.png",
  },
  {
    name: "Laura Domínguez",
    role: "Correctora freelance",
    quote:
      "Los perfiles editoriales son un cambio total. No corrijo igual una novela juvenil que un ensayo académico, y STYLIA entiende esa diferencia desde el primer párrafo.",
    avatar: "/images/placeholders/avatar-3.png",
  },
  {
    name: "Miguel Ángel Ruiz",
    role: "Profesor universitario, Dpto. de Lingüística",
    quote:
      "Uso STYLIA para revisar las tesis de mis estudiantes antes de la defensa. Los quality gates garantizan que el texto no pierda integridad académica.",
    avatar: "/images/placeholders/avatar-4.png",
  },
  {
    name: "Patricia Sánchez",
    role: "Responsable editorial, Grupo Texto Vivo",
    quote:
      "El router inteligente nos ahorra un 40% en costos de API. Los párrafos simples se resuelven sin IA y los complejos reciben la atención que merecen.",
    avatar: "/images/placeholders/avatar-5.png",
  },
  {
    name: "Diego Herrera",
    role: "Escritor y blogger",
    quote:
      "Subí mi novela de 300 páginas y STYLIA la procesó sin destruir mi estilo personal. Las correcciones respetaron mi voz narrativa en cada capítulo.",
    avatar: "/images/placeholders/avatar-6.png",
  },
];

function TestimonialCard({ testimonial }: { testimonial: (typeof testimonials)[0] }) {
  return (
    <div className="w-[350px] flex-shrink-0 rounded-2xl border border-border bg-surface p-6 mx-3">
      <p className="text-body-sm text-plomo-light mb-6 leading-relaxed italic">
        &ldquo;{testimonial.quote}&rdquo;
      </p>
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-full bg-surface-elevated border border-border overflow-hidden flex items-center justify-center">
          <img
            src={testimonial.avatar}
            alt={testimonial.name}
            className="w-full h-full object-cover"
            onError={(e) => {
              const target = e.target as HTMLImageElement;
              target.style.display = "none";
              target.parentElement!.innerHTML = `<span class="text-krypton font-bold text-sm">${testimonial.name.split(" ").map(n => n[0]).join("")}</span>`;
            }}
          />
        </div>
        <div>
          <p className="text-body-sm text-bruma font-medium">{testimonial.name}</p>
          <p className="text-caption text-plomo">{testimonial.role}</p>
        </div>
      </div>
    </div>
  );
}

export function Testimonials() {
  return (
    <section className="relative section-padding overflow-hidden">
      <DotPattern className="opacity-30" dotColor="rgba(212, 255, 0, 0.06)" />
      <SectionDivider variant="line" className="absolute top-0 left-0 right-0" />

      <div className="relative z-10">
        <BlurFade>
          <div className="text-center max-w-3xl mx-auto mb-16 container-landing">
            <p className="text-caption text-krypton font-medium uppercase tracking-widest mb-4">
              Testimonios
            </p>
            <h2 className="text-heading-1 text-bruma mb-6">
              Profesionales que ya confían en{" "}
              <span className="text-gradient-krypton">STYLIA</span>
            </h2>
            <p className="text-body text-plomo-light">
              Editores, correctores, escritores y equipos de contenido que han
              integrado STYLIA en su flujo de trabajo.
            </p>
          </div>
        </BlurFade>

        <BlurFade delay={200}>
          <Marquee className="mb-6">
            {testimonials.slice(0, 3).map((t, i) => (
              <TestimonialCard key={i} testimonial={t} />
            ))}
          </Marquee>
          <Marquee reverse>
            {testimonials.slice(3).map((t, i) => (
              <TestimonialCard key={i} testimonial={t} />
            ))}
          </Marquee>
        </BlurFade>
      </div>
    </section>
  );
}
