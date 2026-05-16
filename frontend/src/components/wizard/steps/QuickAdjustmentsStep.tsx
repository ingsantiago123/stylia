"use client";

import { useState, KeyboardEvent } from "react";
import { StyleProfileCreate, RegisterConstraint } from "@/lib/api";
import { HumanizedTooltip, METRIC_GLOSSARY } from "@/components/ui/HumanizedTooltip";
import { SafePromptInput } from "@/components/ui/SafePromptInput";

interface QuickAdjustmentsStepProps {
  presetKey: string;
  adjustments: Partial<StyleProfileCreate>;
  onChange: (adj: Partial<StyleProfileCreate>) => void;
  onConfirm: () => void;
  onBack: () => void;
  loading: boolean;
}

function ToggleSwitch({
  checked,
  onChange,
  id,
}: { checked: boolean; onChange: (v: boolean) => void; id: string }) {
  return (
    <button
      type="button"
      role="switch"
      id={id}
      aria-checked={checked}
      onClick={() => onChange(!checked)}
      className={[
        "relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent",
        "transition-colors duration-200 focus:outline-none focus:ring-2 focus:ring-krypton/30 focus:ring-offset-2 focus:ring-offset-carbon",
        checked ? "bg-krypton" : "bg-surface-elevated border border-border",
      ].join(" ")}
    >
      <span
        className={[
          "inline-block h-5 w-5 transform rounded-full shadow transition-transform duration-200",
          checked ? "translate-x-5 bg-carbon" : "translate-x-0 bg-plomo",
        ].join(" ")}
      />
    </button>
  );
}

const REGISTER_CONSTRAINT_LABELS: Record<RegisterConstraint, string> = {
  lenguaje_inclusivo: "Lenguaje inclusivo",
  sin_anglicismos: "Sin anglicismos",
  tuteo_exclusivo: "Tuteo exclusivo (tú)",
  sin_imperativo: "Sin imperativo",
  voseo_rioplatense: "Voseo rioplatense",
};

export function QuickAdjustmentsStep({
  adjustments,
  onChange,
  onConfirm,
  onBack,
  loading,
}: QuickAdjustmentsStepProps) {
  const [termInput, setTermInput] = useState("");
  const [extraRule, setExtraRule] = useState("");
  const [extraRuleValid, setExtraRuleValid] = useState(true);

  const protectedTerms: string[] = adjustments.protected_terms ?? [];
  const registerConstraints: RegisterConstraint[] = (adjustments.register_constraints ?? []) as RegisterConstraint[];
  const preserveAuthorVoice = adjustments.preserve_author_voice ?? true;

  const addTerm = () => {
    const t = termInput.trim();
    if (!t || protectedTerms.includes(t)) { setTermInput(""); return; }
    onChange({ ...adjustments, protected_terms: [...protectedTerms, t] });
    setTermInput("");
  };

  const removeTerm = (term: string) => {
    onChange({ ...adjustments, protected_terms: protectedTerms.filter((t) => t !== term) });
  };

  const handleTermKey = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" || e.key === ",") { e.preventDefault(); addTerm(); }
  };

  const toggleConstraint = (constraint: RegisterConstraint) => {
    const next = registerConstraints.includes(constraint)
      ? registerConstraints.filter((c) => c !== constraint)
      : [...registerConstraints, constraint];
    onChange({ ...adjustments, register_constraints: next });
  };

  const allConstraints = Object.keys(REGISTER_CONSTRAINT_LABELS) as RegisterConstraint[];

  return (
    <div className="flex flex-col h-full">
      <div className="text-center mb-8">
        <h2 className="text-heading-3 text-bruma mb-2">Ajustes rápidos</h2>
        <p className="text-sm text-plomo">
          Personaliza cómo la IA intervendrá en tu texto.
          Puedes dejar todo como está y simplemente confirmar.
        </p>
      </div>

      <div className="space-y-6 flex-1 overflow-y-auto pr-1">
        {/* Preserve voice */}
        <div className="glass-card rounded-2xl p-5">
          <div className="flex items-center justify-between">
            <div className="flex-1">
              <HumanizedTooltip config={METRIC_GLOSSARY.preserve_author_voice}>
                <span className="text-sm font-semibold text-bruma">Preservar tu voz</span>
              </HumanizedTooltip>
              <p className="text-xs text-plomo mt-1">
                La IA protegerá tus giros, ritmo y expresiones características.
              </p>
            </div>
            <ToggleSwitch
              id="preserve-author-voice"
              checked={preserveAuthorVoice}
              onChange={(v) => onChange({ ...adjustments, preserve_author_voice: v })}
            />
          </div>
        </div>

        {/* Register constraints */}
        <div className="glass-card rounded-2xl p-5 space-y-3">
          <div>
            <HumanizedTooltip config={METRIC_GLOSSARY.register_constraints}>
              <span className="text-sm font-semibold text-bruma">Restricciones de estilo</span>
            </HumanizedTooltip>
            <p className="text-xs text-plomo mt-1">Activa reglas obligatorias para toda la corrección.</p>
          </div>
          <div className="flex flex-wrap gap-2">
            {allConstraints.map((c) => {
              const active = registerConstraints.includes(c);
              return (
                <button
                  key={c}
                  type="button"
                  onClick={() => toggleConstraint(c)}
                  aria-pressed={active}
                  className={[
                    "px-3 py-1.5 rounded-lg text-xs font-medium border transition-all duration-150",
                    active
                      ? "bg-krypton/15 border-krypton/50 text-krypton"
                      : "bg-surface border-border text-plomo hover:border-krypton/30 hover:text-bruma",
                  ].join(" ")}
                >
                  {REGISTER_CONSTRAINT_LABELS[c]}
                </button>
              );
            })}
          </div>
        </div>

        {/* Protected terms */}
        <div className="glass-card rounded-2xl p-5 space-y-3">
          <div>
            <span className="text-sm font-semibold text-bruma">Términos protegidos</span>
            <p className="text-xs text-plomo mt-1">
              Palabras o frases que la IA no puede modificar ni eliminar bajo ninguna circunstancia.
            </p>
          </div>

          {/* Tags */}
          <div className="flex flex-wrap gap-1.5 min-h-6">
            {protectedTerms.map((term) => (
              <span
                key={term}
                className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-surface-elevated border border-border text-xs text-bruma"
              >
                {term}
                <button
                  type="button"
                  onClick={() => removeTerm(term)}
                  aria-label={`Eliminar término ${term}`}
                  className="text-plomo hover:text-red-400 transition-colors ml-0.5"
                >
                  ×
                </button>
              </span>
            ))}
          </div>

          {/* Input */}
          <div className="flex gap-2">
            <input
              type="text"
              value={termInput}
              onChange={(e) => setTermInput(e.target.value)}
              onKeyDown={handleTermKey}
              placeholder="Añadir término y pulsar Enter"
              className="flex-1 rounded-lg bg-surface border border-border px-3 py-2 text-sm text-bruma placeholder:text-plomo-dark focus:outline-none focus:border-krypton/60 focus:ring-1 focus:ring-krypton/30 transition-all"
            />
            <button
              type="button"
              onClick={addTerm}
              className="px-3 py-2 rounded-lg bg-surface-elevated border border-border text-sm text-bruma hover:border-krypton/40 transition-all"
            >
              +
            </button>
          </div>
        </div>

        {/* Safe prompt rule */}
        <div className="glass-card rounded-2xl p-5">
          <SafePromptInput
            value={extraRule}
            onChange={(val, isValid) => {
              setExtraRule(val);
              setExtraRuleValid(isValid);
            }}
            label="Regla editorial adicional (opcional)"
            hint={"Ej: \"Usar siempre la forma 'usted' en los diálogos formales.\" Máx. 250 caracteres."}
          />
        </div>
      </div>

      {/* Actions */}
      <div className="flex items-center justify-between mt-6 pt-6 border-t border-border">
        <button
          type="button"
          onClick={onBack}
          className="flex items-center gap-2 text-sm text-plomo hover:text-bruma transition-colors"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
          </svg>
          Cambiar perfil
        </button>

        <button
          type="button"
          onClick={onConfirm}
          disabled={loading || !extraRuleValid}
          className={[
            "flex items-center gap-2 px-6 py-2.5 rounded-xl text-sm font-semibold transition-all duration-200",
            loading || !extraRuleValid
              ? "bg-surface-elevated text-plomo cursor-not-allowed"
              : "bg-krypton text-carbon hover:bg-krypton-400 shadow-glow-sm",
          ].join(" ")}
        >
          {loading ? (
            <>
              <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
              Iniciando corrección…
            </>
          ) : (
            <>
              Iniciar corrección
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
            </>
          )}
        </button>
      </div>
    </div>
  );
}
