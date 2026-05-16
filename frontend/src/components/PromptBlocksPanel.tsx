"use client";

import { useState, useMemo } from "react";
import {
  PromptBlockKey,
  PromptBlocksConfig,
  StyleProfile,
} from "@/lib/api";

interface BlockDef {
  key: PromptBlockKey;
  label: string;
  description: string;
  defaultOn: boolean;
}

const BLOCKS: BlockDef[] = [
  {
    key: "global_context",
    label: "Contexto global del documento",
    description:
      "ADN editorial: tema principal, voz dominante, registro base, términos técnicos globales y huella estilística. Recomendado para textos largos donde la coherencia entre secciones importa.",
    defaultOn: true,
  },
  {
    key: "profile_header",
    label: "Cabecera de perfil editorial",
    description:
      "Resumen del perfil que va al LLM: registro, intervención, audiencia, tono, prioridades, términos protegidos. Si lo apagas, el LLM ignora el perfil de este documento.",
    defaultOn: true,
  },
  {
    key: "ubicacion",
    label: "Ubicación estructural del párrafo",
    description:
      "Sección actual, página, vecinos, términos activos. Útil para que el LLM entienda dónde está cada párrafo en el documento.",
    defaultOn: true,
  },
  {
    key: "structural_rules",
    label: "Reglas por tipo de elemento",
    description:
      "Reglas específicas para títulos, listas, celdas de tabla, citas, pies de figura, etc. (no añadir punto al título, paralelismo en listas, no modificar totales en tablas).",
    defaultOn: true,
  },
  {
    key: "context_prev",
    label: "Ventana de contexto previo",
    description:
      "Los N párrafos ya corregidos antes del actual. Sube la cohesión y permite detectar redundancias entre párrafos vecinos.",
    defaultOn: true,
  },
  {
    key: "substitution_rules",
    label: "Reglas de sustitución del usuario",
    description:
      "Cambios que ya se aplicaron por reglas del usuario antes del LLM. Si lo apagas, el LLM puede revertirlas.",
    defaultOn: true,
  },
  {
    key: "register_constraints",
    label: "Restricciones de registro",
    description:
      "Lenguaje inclusivo, sin anglicismos, tuteo/voseo exclusivo, sin imperativo, etc.",
    defaultOn: true,
  },
  {
    key: "idiolect_protections",
    label: "Idiolectos protegidos",
    description:
      "Patrones del autor o personajes que no deben corregirse aunque parezcan errores.",
    defaultOn: true,
  },
  {
    key: "protected_regions",
    label: "Regiones protegidas",
    description:
      "Citas, fórmulas, código, fragmentos marcados que el LLM no debe modificar.",
    defaultOn: true,
  },
];

interface Props {
  profile: StyleProfile | null;
  onSave: (updates: { prompt_blocks: PromptBlocksConfig }) => Promise<void> | void;
  locked?: boolean;
}

function effectiveValue(cfg: PromptBlocksConfig | null, key: PromptBlockKey, def: boolean): boolean {
  if (!cfg) return def;
  const v = cfg[key];
  return v === undefined ? def : v;
}

export function PromptBlocksPanel({ profile, onSave, locked = false }: Props) {
  const initial = useMemo<PromptBlocksConfig>(() => profile?.prompt_blocks ?? {}, [profile?.prompt_blocks]);
  const [draft, setDraft] = useState<PromptBlocksConfig>(initial);
  const [saving, setSaving] = useState(false);
  const [savedAt, setSavedAt] = useState<number | null>(null);

  const dirty = useMemo(() => {
    return BLOCKS.some(b => effectiveValue(draft, b.key, b.defaultOn) !== effectiveValue(initial, b.key, b.defaultOn));
  }, [draft, initial]);

  const toggle = (key: PromptBlockKey) => {
    if (locked) return;
    setDraft(d => {
      const next = { ...d };
      const def = BLOCKS.find(b => b.key === key)?.defaultOn ?? true;
      const cur = effectiveValue(d, key, def);
      next[key] = !cur;
      return next;
    });
  };

  const handleSave = async () => {
    if (locked || !dirty) return;
    setSaving(true);
    try {
      await onSave({ prompt_blocks: draft });
      setSavedAt(Date.now());
    } finally {
      setSaving(false);
    }
  };

  const handleResetAll = () => {
    if (locked) return;
    setDraft({});
  };

  const enabledCount = BLOCKS.filter(b => effectiveValue(draft, b.key, b.defaultOn)).length;

  return (
    <div className="glass-card rounded-xl p-5 space-y-4">
      <div className="flex items-start justify-between gap-3 flex-wrap">
        <div>
          <h3 className="text-sm font-semibold text-bruma mb-1">
            Bloques del prompt
          </h3>
          <p className="text-xs text-plomo max-w-2xl">
            Decide qué información se envía al LLM en cada corrección. Lo que apagues aquí
            <span className="text-bruma/80"> no se incluye en el prompt</span>;
            ahorra tokens y elimina ruido si un bloque no aporta para este documento.
            Los filtros por <em>tipo</em> (título, lista, celda, etc.) se aplican
            <span className="text-bruma/80"> automáticamente encima</span> de tu selección.
          </p>
        </div>
        <div className="text-center flex-shrink-0">
          <div className="text-2xl font-bold text-krypton">
            {enabledCount}/{BLOCKS.length}
          </div>
          <div className="text-[10px] uppercase tracking-wider text-plomo">activos</div>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
        {BLOCKS.map(b => {
          const on = effectiveValue(draft, b.key, b.defaultOn);
          return (
            <button
              key={b.key}
              type="button"
              onClick={() => toggle(b.key)}
              disabled={locked}
              className={`
                text-left p-3 rounded-lg border transition-all
                ${on
                  ? "bg-krypton/5 border-krypton/30 hover:border-krypton/50"
                  : "bg-surface border-border hover:border-carbon-200"}
                ${locked ? "opacity-50 cursor-not-allowed" : "cursor-pointer"}
              `}
            >
              <div className="flex items-start gap-3">
                <span
                  className={`
                    mt-0.5 flex-shrink-0 w-10 h-5 rounded-full relative transition-colors
                    ${on ? "bg-krypton" : "bg-carbon-200"}
                  `}
                >
                  <span
                    className={`
                      absolute top-0.5 w-4 h-4 rounded-full bg-carbon transition-all
                      ${on ? "left-5" : "left-0.5"}
                    `}
                  />
                </span>
                <div className="min-w-0">
                  <div className={`text-xs font-semibold ${on ? "text-bruma" : "text-plomo"}`}>
                    {b.label}
                  </div>
                  <div className="text-[11px] text-plomo mt-1 leading-snug">
                    {b.description}
                  </div>
                </div>
              </div>
            </button>
          );
        })}
      </div>

      <div className="flex items-center justify-between gap-3 flex-wrap pt-2 border-t border-border">
        <button
          type="button"
          onClick={handleResetAll}
          disabled={locked}
          className="text-xs text-plomo hover:text-bruma transition-colors disabled:opacity-50"
        >
          Restaurar valores por defecto
        </button>
        <div className="flex items-center gap-2">
          {savedAt && Date.now() - savedAt < 4000 && (
            <span className="text-[11px] text-krypton">Guardado</span>
          )}
          <button
            type="button"
            onClick={handleSave}
            disabled={locked || !dirty || saving}
            className={`
              px-4 py-1.5 text-xs font-semibold rounded-lg transition-all
              ${dirty && !locked
                ? "bg-krypton text-carbon hover:brightness-110"
                : "bg-surface text-plomo border border-border cursor-not-allowed"}
            `}
          >
            {saving ? "Guardando…" : "Guardar cambios"}
          </button>
        </div>
      </div>
    </div>
  );
}
