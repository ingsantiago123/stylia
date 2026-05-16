"use client";

import { PresetInfo } from "@/lib/api";

// Enriquecimiento editorial de cada preset
const PRESET_META: Record<string, {
  useCase: string;
  tags: string[];
  audienceEmoji: string;
  interventionLevel: 1 | 2 | 3 | 4;
  interventionLabel: string;
  gradient: string;
}> = {
  infantil_6_8: {
    useCase: "Ideal para cuentos ilustrados, libros-álbum y lecturas guiadas por adultos.",
    tags: ["Vocabulario simple", "Oraciones cortas", "Ritmo oral"],
    audienceEmoji: "🧒",
    interventionLevel: 3,
    interventionLabel: "Moderada",
    gradient: "from-amber-500/10 to-orange-500/5",
  },
  infantil_9_12: {
    useCase: "Ideal para novelas de aventuras, series de misterio y lecturas escolares.",
    tags: ["Claridad narrativa", "Sin tecnicismos", "Cohesión"],
    audienceEmoji: "📚",
    interventionLevel: 3,
    interventionLabel: "Moderada",
    gradient: "from-sky-500/10 to-blue-500/5",
  },
  juvenil: {
    useCase: "Ideal para distopías, romance juvenil y novelas de formación.",
    tags: ["Tono equilibrado", "Voz del autor", "Fluidez"],
    audienceEmoji: "🎧",
    interventionLevel: 3,
    interventionLabel: "Moderada",
    gradient: "from-violet-500/10 to-purple-500/5",
  },
  novela_literaria: {
    useCase: "Ideal para narrativa literaria donde el estilo personal es intocable.",
    tags: ["Mínima intervención", "Preserva ritmo", "Solo errores claros"],
    audienceEmoji: "🪶",
    interventionLevel: 1,
    interventionLabel: "Sutil",
    gradient: "from-emerald-500/10 to-teal-500/5",
  },
  ensayo: {
    useCase: "Ideal para ensayos académicos, columnas de opinión y crónicas argumentativas.",
    tags: ["Formal claro", "Cohesión", "Precisión léxica"],
    audienceEmoji: "✍️",
    interventionLevel: 1,
    interventionLabel: "Sutil",
    gradient: "from-indigo-500/10 to-blue-500/5",
  },
  psicologia_academica: {
    useCase: "Ideal para artículos en revistas indexadas y tesis doctorales.",
    tags: ["Términos protegidos", "Mínima intervención", "Rigor técnico"],
    audienceEmoji: "🧠",
    interventionLevel: 1,
    interventionLabel: "Mínima",
    gradient: "from-cyan-500/10 to-sky-500/5",
  },
  psicologia_divulgativa: {
    useCase: "Ideal para libros de autoayuda, blogs de salud mental y contenido educativo.",
    tags: ["Claridad", "Fluidez", "Rigor accesible"],
    audienceEmoji: "💡",
    interventionLevel: 1,
    interventionLabel: "Sutil",
    gradient: "from-yellow-500/10 to-amber-500/5",
  },
  manual_tecnico: {
    useCase: "Ideal para documentación de software, manuales de usuario y guías de procedimiento.",
    tags: ["Precisión máxima", "Sin ornamentación", "Orden instruccional"],
    audienceEmoji: "⚙️",
    interventionLevel: 1,
    interventionLabel: "Mínima",
    gradient: "from-slate-500/10 to-zinc-500/5",
  },
  texto_marketing: {
    useCase: "Ideal para anuncios, landing pages, emails de venta y copy publicitario.",
    tags: ["Alto impacto", "Oraciones cortas", "Call to action"],
    audienceEmoji: "📣",
    interventionLevel: 4,
    interventionLabel: "Agresiva",
    gradient: "from-rose-500/10 to-pink-500/5",
  },
  no_ficcion_general: {
    useCase: "Ideal para libros de viajes, biografías, periodismo narrativo y divulgación.",
    tags: ["Registro neutro", "Claridad", "Fluidez"],
    audienceEmoji: "📰",
    interventionLevel: 3,
    interventionLabel: "Moderada",
    gradient: "from-krypton/5 to-green-500/5",
  },
};

function InterventionThermometer({ level, label }: { level: 1 | 2 | 3 | 4; label: string }) {
  const colors = ["bg-emerald-400", "bg-sky-400", "bg-amber-400", "bg-rose-400"];
  return (
    <div className="flex items-center gap-2" title={`Nivel de intervención: ${label}`}>
      <div className="flex gap-0.5">
        {[1, 2, 3, 4].map((i) => (
          <div
            key={i}
            className={[
              "h-1.5 rounded-full transition-all",
              i <= level ? colors[level - 1] : "bg-border",
              i === 1 ? "w-3" : i === 2 ? "w-4" : i === 3 ? "w-5" : "w-6",
            ].join(" ")}
          />
        ))}
      </div>
      <span className="text-[10px] text-plomo">{label}</span>
    </div>
  );
}

interface RichProfileCardProps {
  preset: PresetInfo;
  selected: boolean;
  onSelect: (key: string) => void;
}

export function RichProfileCard({ preset, selected, onSelect }: RichProfileCardProps) {
  const meta = PRESET_META[preset.key] ?? {
    useCase: preset.description,
    tags: [],
    audienceEmoji: "📄",
    interventionLevel: 2 as const,
    interventionLabel: preset.intervention_level,
    gradient: "from-krypton/5 to-transparent",
  };

  return (
    <button
      type="button"
      onClick={() => onSelect(preset.key)}
      aria-pressed={selected}
      className={[
        "relative w-full text-left rounded-2xl border p-5 transition-all duration-200 group",
        "bg-gradient-to-br", meta.gradient,
        selected
          ? "border-krypton shadow-glow-sm ring-1 ring-krypton/30"
          : "border-border hover:border-krypton/40 hover:shadow-card-hover",
      ].join(" ")}
    >
      {/* Selected indicator */}
      {selected && (
        <span className="absolute top-3 right-3 flex h-5 w-5 items-center justify-center rounded-full bg-krypton">
          <svg className="w-3 h-3 text-carbon" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
          </svg>
        </span>
      )}

      {/* Header */}
      <div className="flex items-start gap-3 mb-3">
        <span className="text-2xl leading-none" aria-hidden="true">{meta.audienceEmoji}</span>
        <div className="flex-1 min-w-0">
          <h3 className="text-sm font-semibold text-bruma leading-tight">{preset.name}</h3>
          <p className="text-[11px] text-plomo mt-0.5 capitalize">{preset.register?.replace(/_/g, " ")}</p>
        </div>
      </div>

      {/* Use case */}
      <p className="text-xs text-bruma/70 leading-relaxed mb-3">{meta.useCase}</p>

      {/* Tags */}
      {meta.tags.length > 0 && (
        <div className="flex flex-wrap gap-1 mb-3">
          {meta.tags.map((tag) => (
            <span
              key={tag}
              className="text-[10px] px-2 py-0.5 rounded-full bg-surface-elevated text-plomo border border-border"
            >
              {tag}
            </span>
          ))}
        </div>
      )}

      {/* Thermometer */}
      <InterventionThermometer level={meta.interventionLevel} label={meta.interventionLabel} />
    </button>
  );
}
