"use client";

import { useState } from "react";
import { PatchListItem } from "@/lib/api";

// ── Phase metadata ─────────────────────────────────────────────────────────────

const PHASE_META: Record<string, { label: string; color: string; description: string }> = {
  substitution: {
    label: "Sustitución",
    color: "bg-purple-900/40 text-purple-300 border border-purple-700/40",
    description: "Regla de sustitución manual del usuario (Fase 0, antes de LanguageTool)",
  },
  lt: {
    label: "LanguageTool",
    color: "bg-blue-900/40 text-blue-300 border border-blue-700/40",
    description: "Corrección ortográfica y gramatical automática",
  },
  llm_micro: {
    label: "LLM Micro",
    color: "bg-krypton/10 text-krypton border border-krypton/30",
    description: "Corrección de estilo por párrafo (Pasada 1)",
  },
  audit: {
    label: "Auditoría",
    color: "bg-orange-900/40 text-orange-300 border border-orange-700/40",
    description: "Auditoría contextual post-corrección (Pasada 2 — revierte destrucciones)",
  },
  llm_macro: {
    label: "LLM Macro",
    color: "bg-teal-900/40 text-teal-300 border border-teal-700/40",
    description: "Corrección holística de coherencia por sección (S5)",
  },
  cheap: {
    label: "LLM Cheap",
    color: "bg-surface-elevated text-bruma-muted border border-border-subtle",
    description: "Corrección de estilo con modelo económico",
  },
  editorial: {
    label: "LLM Editorial",
    color: "bg-krypton/15 text-krypton border border-krypton/40",
    description: "Corrección editorial con modelo avanzado",
  },
};

function PhaseBadge({ phase }: { phase: string | null }) {
  const meta = PHASE_META[phase || "lt"] || {
    label: phase || "—",
    color: "bg-surface-elevated text-plomo border border-border-subtle",
    description: "",
  };
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded text-[10px] font-medium ${meta.color}`}
      title={meta.description}
    >
      {meta.label}
    </span>
  );
}

// ── Phase summary bar ─────────────────────────────────────────────────────────

function PhaseSummaryBar({ corrections }: { corrections: PatchListItem[] }) {
  const phaseCounts: Record<string, number> = {};
  for (const c of corrections) {
    const phase = c.correction_phase || "lt";
    phaseCounts[phase] = (phaseCounts[phase] || 0) + 1;
  }

  const phases = Object.entries(phaseCounts).sort(([a], [b]) => {
    const order = ["substitution", "lt", "llm_micro", "audit", "llm_macro", "cheap", "editorial"];
    return order.indexOf(a) - order.indexOf(b);
  });

  return (
    <div className="glass-card rounded-xl p-4 mb-4">
      <h3 className="text-xs font-semibold text-plomo uppercase tracking-wider mb-3">
        Distribución por fase de corrección
      </h3>
      <div className="space-y-2">
        {phases.map(([phase, count]) => {
          const meta = PHASE_META[phase] || { label: phase, color: "bg-surface-elevated text-plomo border border-border-subtle", description: "" };
          const pct = Math.round((count / corrections.length) * 100);
          return (
            <div key={phase} className="flex items-center gap-3">
              <span className={`shrink-0 inline-flex items-center px-2 py-0.5 rounded text-[10px] font-medium ${meta.color}`} style={{ minWidth: "90px", justifyContent: "center" }}>
                {meta.label}
              </span>
              <div className="flex-1 bg-carbon-400 rounded-full h-2 overflow-hidden">
                <div
                  className="h-full bg-krypton/40 rounded-full"
                  style={{ width: `${pct}%` }}
                />
              </div>
              <span className="text-xs text-plomo shrink-0 w-16 text-right">
                {count} ({pct}%)
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── Correction row ─────────────────────────────────────────────────────────────

function CorrectionPhaseRow({ patch }: { patch: PatchListItem }) {
  const [expanded, setExpanded] = useState(false);

  const hasChange = patch.original_text !== patch.corrected_text;
  if (!hasChange) return null;

  return (
    <div className="border border-border-subtle rounded-lg overflow-hidden">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-3 px-3 py-2.5 hover:bg-surface-elevated/30 transition-colors text-left"
      >
        <PhaseBadge phase={patch.correction_phase} />
        <div className="flex-1 min-w-0">
          <p className="text-xs text-bruma truncate">{patch.corrected_text}</p>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {patch.category && (
            <span className="text-[10px] text-plomo bg-carbon-400 px-1.5 py-0.5 rounded">
              {patch.category}
            </span>
          )}
          {patch.confidence != null && (
            <span className="text-[10px] text-plomo w-8 text-right">
              {Math.round(patch.confidence * 100)}%
            </span>
          )}
          <svg
            className={`w-3.5 h-3.5 text-plomo transition-transform ${expanded ? "rotate-180" : ""}`}
            fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
          </svg>
        </div>
      </button>

      {expanded && (
        <div className="px-3 py-2.5 border-t border-border-subtle bg-carbon-400/50 space-y-2 text-xs">
          <div className="grid grid-cols-2 gap-2">
            <div>
              <span className="text-[10px] text-plomo uppercase tracking-wider block mb-1">Original</span>
              <p className="text-bruma-muted font-mono">{patch.original_text}</p>
            </div>
            <div>
              <span className="text-[10px] text-plomo uppercase tracking-wider block mb-1">Corregido</span>
              <p className="text-bruma font-mono">{patch.corrected_text}</p>
            </div>
          </div>
          {patch.explanation && (
            <div>
              <span className="text-[10px] text-plomo uppercase tracking-wider block mb-1">Explicación</span>
              <p className="text-bruma-muted">{patch.explanation}</p>
            </div>
          )}
          {patch.block_no != null && (
            <p className="text-plomo font-mono">Bloque {patch.block_no}</p>
          )}
        </div>
      )}
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

interface Props {
  corrections: PatchListItem[];
}

export function MacroCorrectionView({ corrections }: Props) {
  const [activePhase, setActivePhase] = useState<string | null>(null);

  const availablePhases = Array.from(
    new Set(corrections.map((c) => c.correction_phase || "lt"))
  ).sort((a, b) => {
    const order = ["substitution", "lt", "llm_micro", "audit", "llm_macro", "cheap", "editorial"];
    return order.indexOf(a) - order.indexOf(b);
  });

  const filtered = activePhase
    ? corrections.filter((c) => (c.correction_phase || "lt") === activePhase)
    : corrections;

  if (corrections.length === 0) {
    return (
      <div className="glass-card rounded-xl p-8 text-center text-plomo">
        <p className="text-sm">Sin correcciones para mostrar.</p>
      </div>
    );
  }

  const hasMacro = corrections.some((c) => c.correction_phase === "llm_macro");

  return (
    <div className="space-y-4">
      {hasMacro && (
        <div className="p-3 bg-teal-900/20 border border-teal-700/30 rounded-xl flex items-center gap-2 text-xs text-teal-300">
          <svg className="w-4 h-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          Este documento incluye correcciones de pase macro (coherencia y fluidez entre secciones).
        </div>
      )}

      <PhaseSummaryBar corrections={corrections} />

      {/* Phase filter tabs */}
      <div className="flex flex-wrap gap-2">
        <button
          onClick={() => setActivePhase(null)}
          className={`px-3 py-1 rounded-lg text-xs font-medium transition-all ${
            activePhase === null
              ? "bg-krypton text-carbon"
              : "bg-surface-elevated text-plomo hover:text-bruma"
          }`}
        >
          Todas ({corrections.length})
        </button>
        {availablePhases.map((phase) => {
          const meta = PHASE_META[phase] || { label: phase };
          const count = corrections.filter((c) => (c.correction_phase || "lt") === phase).length;
          return (
            <button
              key={phase}
              onClick={() => setActivePhase(phase === activePhase ? null : phase)}
              className={`px-3 py-1 rounded-lg text-xs font-medium transition-all ${
                activePhase === phase
                  ? "bg-krypton text-carbon"
                  : "bg-surface-elevated text-plomo hover:text-bruma"
              }`}
            >
              {meta.label} ({count})
            </button>
          );
        })}
      </div>

      {/* Correction list */}
      <div className="space-y-1.5">
        {filtered.map((patch) => (
          <CorrectionPhaseRow key={patch.id} patch={patch} />
        ))}
      </div>

      {filtered.length === 0 && (
        <p className="text-sm text-plomo text-center py-8">
          Sin correcciones en esta fase.
        </p>
      )}
    </div>
  );
}
