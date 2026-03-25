"use client";

import { useState } from "react";
import { PresetInfo } from "@/lib/api";

interface ProfileEditorProps {
  presetKey: string | null;
  presets: PresetInfo[];
  onSave: (data: Record<string, unknown>) => void;
  onBack: () => void;
  processing: boolean;
  error: string | null;
}

const INTERVENTION_LEVELS = [
  { value: "minima", label: "Minima", description: "Solo errores claros" },
  { value: "sutil", label: "Sutil", description: "Mejoras conservadoras" },
  { value: "moderada", label: "Moderada", description: "Equilibrio correccion/preservacion" },
  { value: "agresiva", label: "Agresiva", description: "Reescritura significativa" },
];

const REGISTERS = [
  { value: "informal_claro", label: "Informal claro" },
  { value: "neutro_claro", label: "Neutro claro" },
  { value: "neutro", label: "Neutro" },
  { value: "formal_claro", label: "Formal claro" },
  { value: "formal_tecnico", label: "Formal tecnico" },
  { value: "persuasivo", label: "Persuasivo" },
];

const TONES = [
  { value: "neutro", label: "Neutro" },
  { value: "reflexivo", label: "Reflexivo" },
  { value: "didactico", label: "Didactico" },
  { value: "narrativo", label: "Narrativo" },
  { value: "persuasivo", label: "Persuasivo" },
];

const EXPERTISE_LEVELS = [
  { value: "bajo", label: "Bajo" },
  { value: "medio", label: "Medio" },
  { value: "alto", label: "Alto" },
  { value: "experto", label: "Experto" },
];

const STYLE_PRIORITY_OPTIONS = [
  "claridad", "fluidez", "cohesion", "precision_lexica", "ritmo",
];

export function ProfileEditor({ presetKey, presets, onSave, onBack, processing, error }: ProfileEditorProps) {
  const selectedPreset = presets.find((p) => p.key === presetKey);

  const [register, setRegister] = useState(selectedPreset?.register || "neutro");
  const [tone, setTone] = useState("neutro");
  const [interventionLevel, setInterventionLevel] = useState(
    selectedPreset?.intervention_level || "moderada"
  );
  const [audienceExpertise, setAudienceExpertise] = useState("medio");
  const [preserveVoice, setPreserveVoice] = useState(true);
  const [maxRewriteRatio, setMaxRewriteRatio] = useState(0.30);
  const [maxExpansionRatio, setMaxExpansionRatio] = useState(1.10);
  const [protectedTermsInput, setProtectedTermsInput] = useState("");
  const [protectedTerms, setProtectedTerms] = useState<string[]>([]);
  const [priorities, setPriorities] = useState<string[]>(["claridad", "fluidez", "cohesion", "precision_lexica"]);

  const addProtectedTerm = () => {
    const term = protectedTermsInput.trim();
    if (term && !protectedTerms.includes(term)) {
      setProtectedTerms([...protectedTerms, term]);
      setProtectedTermsInput("");
    }
  };

  const removeProtectedTerm = (term: string) => {
    setProtectedTerms(protectedTerms.filter((t) => t !== term));
  };

  const togglePriority = (p: string) => {
    if (priorities.includes(p)) {
      setPriorities(priorities.filter((x) => x !== p));
    } else {
      setPriorities([...priorities, p]);
    }
  };

  const handleSave = () => {
    onSave({
      register,
      tone,
      intervention_level: interventionLevel,
      audience_expertise: audienceExpertise,
      preserve_author_voice: preserveVoice,
      max_rewrite_ratio: maxRewriteRatio,
      max_expansion_ratio: maxExpansionRatio,
      protected_terms: protectedTerms,
      style_priorities: priorities,
    });
  };

  return (
    <div className="bg-carbon-100 border border-carbon-300 rounded-xl p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <button
          onClick={onBack}
          className="text-plomo hover:text-bruma transition-colors p-1"
        >
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M10.5 19.5L3 12m0 0l7.5-7.5M3 12h18" />
          </svg>
        </button>
        <div>
          <h3 className="text-lg font-semibold text-bruma">Personalizar perfil</h3>
          {selectedPreset && (
            <p className="text-sm text-plomo">Base: {selectedPreset.name}</p>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Columna 1: Estilo */}
        <div className="space-y-5">
          <h4 className="text-sm font-semibold text-krypton uppercase tracking-wider">Estilo</h4>

          {/* Registro */}
          <div>
            <label className="block text-sm text-bruma mb-2">Registro</label>
            <select
              value={register}
              onChange={(e) => setRegister(e.target.value)}
              className="w-full bg-carbon-50 border border-carbon-300 rounded-lg px-3 py-2 text-sm text-bruma focus:border-krypton focus:outline-none"
            >
              {REGISTERS.map((r) => (
                <option key={r.value} value={r.value}>{r.label}</option>
              ))}
            </select>
          </div>

          {/* Tono */}
          <div>
            <label className="block text-sm text-bruma mb-2">Tono</label>
            <select
              value={tone}
              onChange={(e) => setTone(e.target.value)}
              className="w-full bg-carbon-50 border border-carbon-300 rounded-lg px-3 py-2 text-sm text-bruma focus:border-krypton focus:outline-none"
            >
              {TONES.map((t) => (
                <option key={t.value} value={t.value}>{t.label}</option>
              ))}
            </select>
          </div>

          {/* Nivel de intervencion */}
          <div>
            <label className="block text-sm text-bruma mb-2">Nivel de intervencion</label>
            <div className="space-y-2">
              {INTERVENTION_LEVELS.map((level) => (
                <label
                  key={level.value}
                  className={`flex items-center gap-3 p-3 rounded-lg border cursor-pointer transition-all ${
                    interventionLevel === level.value
                      ? "border-krypton bg-krypton/5"
                      : "border-carbon-300 hover:border-carbon-200"
                  }`}
                >
                  <input
                    type="radio"
                    name="intervention"
                    value={level.value}
                    checked={interventionLevel === level.value}
                    onChange={() => setInterventionLevel(level.value)}
                    className="sr-only"
                  />
                  <div className={`w-3 h-3 rounded-full border-2 ${
                    interventionLevel === level.value
                      ? "border-krypton bg-krypton"
                      : "border-plomo"
                  }`} />
                  <div>
                    <span className="text-sm text-bruma font-medium">{level.label}</span>
                    <span className="text-xs text-plomo ml-2">{level.description}</span>
                  </div>
                </label>
              ))}
            </div>
          </div>

          {/* Audiencia expertise */}
          <div>
            <label className="block text-sm text-bruma mb-2">Nivel de expertise de la audiencia</label>
            <select
              value={audienceExpertise}
              onChange={(e) => setAudienceExpertise(e.target.value)}
              className="w-full bg-carbon-50 border border-carbon-300 rounded-lg px-3 py-2 text-sm text-bruma focus:border-krypton focus:outline-none"
            >
              {EXPERTISE_LEVELS.map((e) => (
                <option key={e.value} value={e.value}>{e.label}</option>
              ))}
            </select>
          </div>
        </div>

        {/* Columna 2: Limites y protecciones */}
        <div className="space-y-5">
          <h4 className="text-sm font-semibold text-krypton uppercase tracking-wider">Limites y protecciones</h4>

          {/* Preservar voz */}
          <div className="flex items-center justify-between p-3 rounded-lg border border-carbon-300">
            <div>
              <span className="text-sm text-bruma">Preservar voz del autor</span>
              <p className="text-xs text-plomo mt-0.5">Limita cambios que alteren el estilo personal</p>
            </div>
            <button
              onClick={() => setPreserveVoice(!preserveVoice)}
              className={`relative w-11 h-6 rounded-full transition-colors ${
                preserveVoice ? "bg-krypton" : "bg-carbon-300"
              }`}
            >
              <span className={`absolute top-0.5 left-0.5 w-5 h-5 rounded-full bg-white transition-transform ${
                preserveVoice ? "translate-x-5" : ""
              }`} />
            </button>
          </div>

          {/* Max rewrite ratio */}
          <div>
            <label className="block text-sm text-bruma mb-2">
              Ratio max. de reescritura: <span className="text-krypton">{Math.round(maxRewriteRatio * 100)}%</span>
            </label>
            <input
              type="range"
              min="0.05"
              max="0.60"
              step="0.05"
              value={maxRewriteRatio}
              onChange={(e) => setMaxRewriteRatio(parseFloat(e.target.value))}
              className="w-full accent-krypton"
            />
            <div className="flex justify-between text-xs text-plomo mt-1">
              <span>5%</span>
              <span>60%</span>
            </div>
          </div>

          {/* Max expansion */}
          <div>
            <label className="block text-sm text-bruma mb-2">
              Expansion max. del texto: <span className="text-krypton">{Math.round(maxExpansionRatio * 100)}%</span>
            </label>
            <input
              type="range"
              min="1.00"
              max="1.30"
              step="0.05"
              value={maxExpansionRatio}
              onChange={(e) => setMaxExpansionRatio(parseFloat(e.target.value))}
              className="w-full accent-krypton"
            />
            <div className="flex justify-between text-xs text-plomo mt-1">
              <span>100%</span>
              <span>130%</span>
            </div>
          </div>

          {/* Terminos protegidos */}
          <div>
            <label className="block text-sm text-bruma mb-2">Terminos protegidos</label>
            <div className="flex gap-2">
              <input
                type="text"
                value={protectedTermsInput}
                onChange={(e) => setProtectedTermsInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), addProtectedTerm())}
                placeholder="Agregar termino..."
                className="flex-1 bg-carbon-50 border border-carbon-300 rounded-lg px-3 py-2 text-sm text-bruma placeholder:text-plomo focus:border-krypton focus:outline-none"
              />
              <button
                onClick={addProtectedTerm}
                className="px-3 py-2 bg-carbon-200 text-bruma rounded-lg text-sm hover:bg-carbon-300 transition-colors"
              >
                +
              </button>
            </div>
            {protectedTerms.length > 0 && (
              <div className="flex flex-wrap gap-2 mt-2">
                {protectedTerms.map((term) => (
                  <span
                    key={term}
                    className="inline-flex items-center gap-1 bg-krypton/10 text-krypton px-2.5 py-1 rounded-full text-xs"
                  >
                    {term}
                    <button
                      onClick={() => removeProtectedTerm(term)}
                      className="hover:text-red-400 transition-colors"
                    >
                      x
                    </button>
                  </span>
                ))}
              </div>
            )}
          </div>

          {/* Prioridades de estilo */}
          <div>
            <label className="block text-sm text-bruma mb-2">Prioridades de estilo</label>
            <div className="flex flex-wrap gap-2">
              {STYLE_PRIORITY_OPTIONS.map((p) => (
                <button
                  key={p}
                  onClick={() => togglePriority(p)}
                  className={`px-3 py-1.5 rounded-full text-xs font-medium transition-all ${
                    priorities.includes(p)
                      ? "bg-krypton/20 text-krypton border border-krypton/30"
                      : "bg-carbon-200 text-plomo border border-carbon-300 hover:border-carbon-200"
                  }`}
                >
                  {p.replace("_", " ")}
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Actions */}
      <div className="flex items-center gap-3 pt-2 border-t border-carbon-300">
        <button
          onClick={handleSave}
          disabled={processing}
          className={`
            px-6 py-2.5 rounded-lg font-medium text-sm transition-all
            ${!processing
              ? "bg-krypton text-carbon hover:bg-krypton/90 shadow-lg shadow-krypton/20"
              : "bg-carbon-200 text-plomo cursor-wait"
            }
          `}
        >
          {processing ? (
            <span className="flex items-center gap-2">
              <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
              Procesando...
            </span>
          ) : (
            "Guardar y procesar"
          )}
        </button>

        <button
          onClick={onBack}
          disabled={processing}
          className="px-4 py-2.5 rounded-lg text-sm text-plomo hover:text-bruma transition-colors"
        >
          Volver a perfiles
        </button>
      </div>

      {/* Error */}
      {error && (
        <div className="flex items-center gap-2 bg-red-900/20 border border-red-500/30 text-red-400 px-4 py-2.5 rounded-lg text-sm">
          <svg className="w-4 h-4 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
          </svg>
          {error}
        </div>
      )}
    </div>
  );
}
