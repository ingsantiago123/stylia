"use client";

import { useState, useEffect, useCallback } from "react";
import {
  getEditorialProfile,
  addEditorialRule,
  deleteEditorialRule,
  simulateImpact,
  patchEditorialProfile,
  EditorialProfileFull,
  SimulateImpactResult,
  SubstitutionRule,
  EntityNormalization,
  IdiolectProtection,
  RegisterConstraint,
  PromptBlocksConfig,
} from "@/lib/api";
import { PromptBlocksPanel } from "@/components/PromptBlocksPanel";

// ── Helpers ──────────────────────────────────────────────────────────────────

function Badge({ label, color = "bg-surface-elevated text-plomo" }: { label: string; color?: string }) {
  return (
    <span className={`inline-block px-2 py-0.5 rounded text-[11px] font-medium ${color}`}>
      {label}
    </span>
  );
}

function SectionCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="glass-card rounded-xl p-4 mb-4">
      <h3 className="text-xs font-semibold text-plomo uppercase tracking-wider mb-3">{title}</h3>
      {children}
    </div>
  );
}

// ── ADN Auto-detectado ────────────────────────────────────────────────────────

function AutoDetectedADN({ adn }: { adn: EditorialProfileFull["auto_detected"] }) {
  return (
    <SectionCard title="ADN auto-detectado por análisis editorial">
      <div className="grid grid-cols-2 gap-3 mb-3">
        {adn.dominant_voice && (
          <div>
            <span className="text-[10px] text-plomo uppercase tracking-wider block mb-1">Voz dominante</span>
            <span className="text-sm text-bruma">{adn.dominant_voice}</span>
          </div>
        )}
        {adn.dominant_register && (
          <div>
            <span className="text-[10px] text-plomo uppercase tracking-wider block mb-1">Registro</span>
            <span className="text-sm text-bruma">{adn.dominant_register}</span>
          </div>
        )}
      </div>

      {adn.global_summary && (
        <div className="mb-3">
          <span className="text-[10px] text-plomo uppercase tracking-wider block mb-1">Resumen global</span>
          <p className="text-sm text-bruma-muted leading-relaxed">{adn.global_summary}</p>
        </div>
      )}

      {adn.key_themes.length > 0 && (
        <div className="mb-3">
          <span className="text-[10px] text-plomo uppercase tracking-wider block mb-2">Temas clave</span>
          <div className="flex flex-wrap gap-1.5">
            {adn.key_themes.slice(0, 8).map((t, i) => (
              <span key={i} className="px-2 py-0.5 bg-surface-elevated rounded text-[11px] text-bruma-muted">
                {t.theme}
                {t.weight > 0 && (
                  <span className="ml-1 text-plomo">{Math.round(t.weight * 100)}%</span>
                )}
              </span>
            ))}
          </div>
        </div>
      )}

      {adn.protected_globals.length > 0 && (
        <div>
          <span className="text-[10px] text-plomo uppercase tracking-wider block mb-2">
            Términos protegidos globales ({adn.protected_globals.length})
          </span>
          <div className="space-y-1">
            {adn.protected_globals.map((pg, i) => (
              <div key={i} className="flex items-start gap-2 text-xs">
                <span className="font-mono text-krypton bg-carbon-400 px-1.5 py-0.5 rounded shrink-0">{pg.term}</span>
                <span className="text-plomo">{pg.reason}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </SectionCard>
  );
}

// ── Substitution Rules Editor ─────────────────────────────────────────────────

function SubstitutionRulesEditor({
  docId,
  rules,
  onRuleAdded,
  onRuleDeleted,
  isLocked,
}: {
  docId: string;
  rules: SubstitutionRule[];
  onRuleAdded: () => void;
  onRuleDeleted: (id: string) => void;
  isLocked: boolean;
}) {
  const [adding, setAdding] = useState(false);
  const [find, setFind] = useState("");
  const [replace, setReplace] = useState("");
  const [isRegex, setIsRegex] = useState(false);
  const [caseSensitive, setCaseSensitive] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleAdd = async () => {
    if (!find.trim()) return;
    setSaving(true);
    setError(null);
    try {
      await addEditorialRule(docId, "substitution", {
        find: find.trim(),
        replace: replace.trim(),
        is_regex: isRegex,
        case_sensitive: caseSensitive,
        scope: "all",
        enabled: true,
      });
      setFind("");
      setReplace("");
      setIsRegex(false);
      setCaseSensitive(false);
      setAdding(false);
      onRuleAdded();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Error al guardar la regla");
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await deleteEditorialRule(docId, id);
      onRuleDeleted(id);
    } catch {}
  };

  return (
    <SectionCard title={`Reglas de sustitución (${rules.length})`}>
      {rules.length === 0 && !adding && (
        <p className="text-sm text-plomo mb-3">Sin reglas configuradas. Las sustituciones se aplican antes de LanguageTool.</p>
      )}

      {rules.length > 0 && (
        <div className="space-y-2 mb-3">
          {rules.map((r) => (
            <div key={r.id} className="flex items-center gap-2 p-2 bg-carbon-400 rounded-lg text-xs">
              <span className={`w-2 h-2 rounded-full shrink-0 ${r.enabled ? "bg-krypton" : "bg-plomo"}`} />
              <span className="font-mono text-bruma shrink-0 max-w-[140px] truncate" title={r.find}>
                {r.find}
              </span>
              <span className="text-plomo shrink-0">→</span>
              <span className="font-mono text-krypton shrink-0 max-w-[140px] truncate" title={r.replace}>
                {r.replace || <em className="text-plomo">(eliminar)</em>}
              </span>
              <div className="flex gap-1 ml-1">
                {r.is_regex && <Badge label="regex" color="bg-surface-elevated text-plomo" />}
                {r.case_sensitive && <Badge label="case" color="bg-surface-elevated text-plomo" />}
              </div>
              {!isLocked && (
                <button
                  onClick={() => handleDelete(r.id)}
                  className="ml-auto text-plomo hover:text-red-400 transition-colors shrink-0 p-1"
                  title="Eliminar regla"
                >
                  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              )}
            </div>
          ))}
        </div>
      )}

      {!isLocked && (
        adding ? (
          <div className="space-y-2 p-3 bg-carbon-400 rounded-lg">
            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="text-[10px] text-plomo uppercase tracking-wider block mb-1">Buscar</label>
                <input
                  value={find}
                  onChange={(e) => setFind(e.target.value)}
                  placeholder={isRegex ? "Regex pattern" : "Texto a reemplazar"}
                  className="w-full bg-carbon-300 text-bruma text-xs px-2.5 py-1.5 rounded-md border border-border-subtle focus:border-krypton/50 outline-none font-mono"
                />
              </div>
              <div>
                <label className="text-[10px] text-plomo uppercase tracking-wider block mb-1">Reemplazar con</label>
                <input
                  value={replace}
                  onChange={(e) => setReplace(e.target.value)}
                  placeholder="Texto de reemplazo (vacío = eliminar)"
                  className="w-full bg-carbon-300 text-bruma text-xs px-2.5 py-1.5 rounded-md border border-border-subtle focus:border-krypton/50 outline-none font-mono"
                />
              </div>
            </div>
            <div className="flex gap-3 text-xs">
              <label className="flex items-center gap-1.5 cursor-pointer text-bruma-muted">
                <input
                  type="checkbox"
                  checked={isRegex}
                  onChange={(e) => setIsRegex(e.target.checked)}
                  className="accent-krypton"
                />
                Regex
              </label>
              <label className="flex items-center gap-1.5 cursor-pointer text-bruma-muted">
                <input
                  type="checkbox"
                  checked={caseSensitive}
                  onChange={(e) => setCaseSensitive(e.target.checked)}
                  className="accent-krypton"
                />
                Distinguir mayúsculas
              </label>
            </div>
            {error && <p className="text-red-400 text-xs">{error}</p>}
            <div className="flex gap-2">
              <button
                onClick={handleAdd}
                disabled={saving || !find.trim()}
                className="px-3 py-1.5 bg-krypton text-carbon text-xs font-semibold rounded-md disabled:opacity-50 hover:bg-krypton/90 transition-colors"
              >
                {saving ? "Guardando..." : "Guardar"}
              </button>
              <button
                onClick={() => { setAdding(false); setError(null); }}
                className="px-3 py-1.5 text-plomo hover:text-bruma text-xs transition-colors"
              >
                Cancelar
              </button>
            </div>
          </div>
        ) : (
          <button
            onClick={() => setAdding(true)}
            className="text-xs text-krypton hover:text-krypton/80 transition-colors flex items-center gap-1"
          >
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
            </svg>
            Agregar regla de sustitución
          </button>
        )
      )}
    </SectionCard>
  );
}

// ── Entity Normalizations Editor ──────────────────────────────────────────────

function EntityNormalizationsEditor({
  docId,
  norms,
  onNormAdded,
  onNormDeleted,
  isLocked,
}: {
  docId: string;
  norms: EntityNormalization[];
  onNormAdded: () => void;
  onNormDeleted: (id: string) => void;
  isLocked: boolean;
}) {
  const [adding, setAdding] = useState(false);
  const [canonical, setCanonical] = useState("");
  const [generic, setGeneric] = useState("");
  const [aliasesStr, setAliasesStr] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleAdd = async () => {
    if (!canonical.trim()) return;
    setSaving(true);
    setError(null);
    try {
      const aliases = aliasesStr.split(",").map((a) => a.trim()).filter(Boolean);
      await addEditorialRule(docId, "normalization", {
        canonical: canonical.trim(),
        generic: generic.trim(),
        aliases,
        enabled: true,
      });
      setCanonical("");
      setGeneric("");
      setAliasesStr("");
      setAdding(false);
      onNormAdded();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Error al guardar");
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await deleteEditorialRule(docId, id);
      onNormDeleted(id);
    } catch {}
  };

  return (
    <SectionCard title={`Normalizaciones de entidades (${norms.length})`}>
      {norms.length === 0 && !adding && (
        <p className="text-sm text-plomo mb-3">Sin normalizaciones. Garantiza que variantes de un nombre se unifiquen a la forma canónica.</p>
      )}

      {norms.length > 0 && (
        <div className="space-y-2 mb-3">
          {norms.map((n) => (
            <div key={n.id} className="flex items-start gap-2 p-2 bg-carbon-400 rounded-lg text-xs">
              <span className={`w-2 h-2 rounded-full shrink-0 mt-0.5 ${n.enabled ? "bg-krypton" : "bg-plomo"}`} />
              <div className="flex-1 min-w-0">
                <span className="font-mono text-krypton">{n.canonical}</span>
                {n.generic && <span className="text-plomo ml-2">← {n.generic}</span>}
                {n.aliases.length > 0 && (
                  <span className="text-plomo ml-2">+ {n.aliases.join(", ")}</span>
                )}
              </div>
              {!isLocked && (
                <button
                  onClick={() => handleDelete(n.id)}
                  className="text-plomo hover:text-red-400 transition-colors shrink-0 p-1"
                >
                  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              )}
            </div>
          ))}
        </div>
      )}

      {!isLocked && (
        adding ? (
          <div className="space-y-2 p-3 bg-carbon-400 rounded-lg">
            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="text-[10px] text-plomo uppercase tracking-wider block mb-1">Forma canónica</label>
                <input
                  value={canonical}
                  onChange={(e) => setCanonical(e.target.value)}
                  placeholder="ej. STYLIA"
                  className="w-full bg-carbon-300 text-bruma text-xs px-2.5 py-1.5 rounded-md border border-border-subtle focus:border-krypton/50 outline-none font-mono"
                />
              </div>
              <div>
                <label className="text-[10px] text-plomo uppercase tracking-wider block mb-1">Forma genérica</label>
                <input
                  value={generic}
                  onChange={(e) => setGeneric(e.target.value)}
                  placeholder="ej. stylia (opcional)"
                  className="w-full bg-carbon-300 text-bruma text-xs px-2.5 py-1.5 rounded-md border border-border-subtle focus:border-krypton/50 outline-none font-mono"
                />
              </div>
            </div>
            <div>
              <label className="text-[10px] text-plomo uppercase tracking-wider block mb-1">Alias (separados por coma)</label>
              <input
                value={aliasesStr}
                onChange={(e) => setAliasesStr(e.target.value)}
                placeholder="ej. Stylia, STYLA, S.T.Y.L.I.A."
                className="w-full bg-carbon-300 text-bruma text-xs px-2.5 py-1.5 rounded-md border border-border-subtle focus:border-krypton/50 outline-none"
              />
            </div>
            {error && <p className="text-red-400 text-xs">{error}</p>}
            <div className="flex gap-2">
              <button
                onClick={handleAdd}
                disabled={saving || !canonical.trim()}
                className="px-3 py-1.5 bg-krypton text-carbon text-xs font-semibold rounded-md disabled:opacity-50 hover:bg-krypton/90 transition-colors"
              >
                {saving ? "Guardando..." : "Guardar"}
              </button>
              <button
                onClick={() => { setAdding(false); setError(null); }}
                className="px-3 py-1.5 text-plomo hover:text-bruma text-xs transition-colors"
              >
                Cancelar
              </button>
            </div>
          </div>
        ) : (
          <button
            onClick={() => setAdding(true)}
            className="text-xs text-krypton hover:text-krypton/80 transition-colors flex items-center gap-1"
          >
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
            </svg>
            Agregar normalización
          </button>
        )
      )}
    </SectionCard>
  );
}

// ── Idiolect Protections Editor ───────────────────────────────────────────────

function IdiolectProtectionsEditor({
  docId,
  protections,
  onAdded,
  onDeleted,
  isLocked,
}: {
  docId: string;
  protections: IdiolectProtection[];
  onAdded: () => void;
  onDeleted: (id: string) => void;
  isLocked: boolean;
}) {
  const [adding, setAdding] = useState(false);
  const [description, setDescription] = useState("");
  const [scope, setScope] = useState("all");
  const [examplesStr, setExamplesStr] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleAdd = async () => {
    if (!description.trim()) return;
    setSaving(true);
    setError(null);
    try {
      const examples = examplesStr.split(",").map((e) => e.trim()).filter(Boolean);
      await addEditorialRule(docId, "idiolect", {
        description: description.trim(),
        scope,
        examples,
        enabled: true,
      });
      setDescription("");
      setScope("all");
      setExamplesStr("");
      setAdding(false);
      onAdded();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Error al guardar");
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await deleteEditorialRule(docId, id);
      onDeleted(id);
    } catch {}
  };

  return (
    <SectionCard title={`Idiolectos protegidos (${protections.length})`}>
      {protections.length === 0 && !adding && (
        <p className="text-sm text-plomo mb-3">Sin idiolectos. Protege rasgos de voz propios del autor que el LLM no debe "corregir".</p>
      )}

      {protections.length > 0 && (
        <div className="space-y-2 mb-3">
          {protections.map((p) => (
            <div key={p.id} className="flex items-start gap-2 p-2 bg-carbon-400 rounded-lg text-xs">
              <span className={`w-2 h-2 rounded-full shrink-0 mt-0.5 ${p.enabled ? "bg-krypton" : "bg-plomo"}`} />
              <div className="flex-1 min-w-0">
                <p className="text-bruma">{p.description}</p>
                {p.examples.length > 0 && (
                  <p className="text-plomo mt-0.5 font-mono">{p.examples.join(", ")}</p>
                )}
              </div>
              <Badge label={p.scope} />
              {!isLocked && (
                <button
                  onClick={() => handleDelete(p.id)}
                  className="text-plomo hover:text-red-400 transition-colors shrink-0 p-1"
                >
                  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              )}
            </div>
          ))}
        </div>
      )}

      {!isLocked && (
        adding ? (
          <div className="space-y-2 p-3 bg-carbon-400 rounded-lg">
            <div>
              <label className="text-[10px] text-plomo uppercase tracking-wider block mb-1">Descripción del idiolecto</label>
              <input
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="ej. El autor omite artículos en frases nominales"
                className="w-full bg-carbon-300 text-bruma text-xs px-2.5 py-1.5 rounded-md border border-border-subtle focus:border-krypton/50 outline-none"
              />
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="text-[10px] text-plomo uppercase tracking-wider block mb-1">Alcance</label>
                <select
                  value={scope}
                  onChange={(e) => setScope(e.target.value)}
                  className="w-full bg-carbon-300 text-bruma text-xs px-2.5 py-1.5 rounded-md border border-border-subtle outline-none"
                >
                  <option value="all">Todo el documento</option>
                  <option value="narrative">Narración</option>
                  <option value="dialogue">Diálogos</option>
                </select>
              </div>
              <div>
                <label className="text-[10px] text-plomo uppercase tracking-wider block mb-1">Ejemplos (separados por coma)</label>
                <input
                  value={examplesStr}
                  onChange={(e) => setExamplesStr(e.target.value)}
                  placeholder="ej. Ciudad desierta, Tarde gris"
                  className="w-full bg-carbon-300 text-bruma text-xs px-2.5 py-1.5 rounded-md border border-border-subtle focus:border-krypton/50 outline-none"
                />
              </div>
            </div>
            {error && <p className="text-red-400 text-xs">{error}</p>}
            <div className="flex gap-2">
              <button
                onClick={handleAdd}
                disabled={saving || !description.trim()}
                className="px-3 py-1.5 bg-krypton text-carbon text-xs font-semibold rounded-md disabled:opacity-50 hover:bg-krypton/90 transition-colors"
              >
                {saving ? "Guardando..." : "Guardar"}
              </button>
              <button
                onClick={() => { setAdding(false); setError(null); }}
                className="px-3 py-1.5 text-plomo hover:text-bruma text-xs transition-colors"
              >
                Cancelar
              </button>
            </div>
          </div>
        ) : (
          <button
            onClick={() => setAdding(true)}
            className="text-xs text-krypton hover:text-krypton/80 transition-colors flex items-center gap-1"
          >
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
            </svg>
            Agregar protección de idiolecto
          </button>
        )
      )}
    </SectionCard>
  );
}

// ── Register Constraints Selector ─────────────────────────────────────────────

const REGISTER_OPTIONS: { value: RegisterConstraint; label: string; description: string }[] = [
  { value: "lenguaje_inclusivo", label: "Lenguaje inclusivo", description: "Usar formas no binarias cuando sea posible" },
  { value: "sin_anglicismos", label: "Sin anglicismos", description: "Evitar préstamos del inglés sin adaptar" },
  { value: "tuteo_exclusivo", label: "Tuteo exclusivo", description: "Tratar siempre de tú, nunca de usted" },
  { value: "sin_imperativo", label: "Sin imperativo", description: "Evitar el modo imperativo en textos expositivos" },
  { value: "voseo_rioplatense", label: "Voseo rioplatense", description: "Usar vos en lugar de tú (Argentina/Uruguay)" },
];

function RegisterConstraintsSelector({
  docId,
  constraints,
  onUpdated,
  isLocked,
}: {
  docId: string;
  constraints: RegisterConstraint[];
  onUpdated: () => void;
  isLocked: boolean;
}) {
  const [saving, setSaving] = useState(false);
  const current = new Set(constraints);

  const toggle = async (value: RegisterConstraint) => {
    if (isLocked || saving) return;
    setSaving(true);
    try {
      const next = new Set(current);
      if (next.has(value)) next.delete(value);
      else next.add(value);
      await patchEditorialProfile(docId, { register_constraints: Array.from(next) });
      onUpdated();
    } catch {}
    finally { setSaving(false); }
  };

  return (
    <SectionCard title="Restricciones de registro">
      <div className="space-y-2">
        {REGISTER_OPTIONS.map((opt) => (
          <button
            key={opt.value}
            onClick={() => toggle(opt.value)}
            disabled={isLocked || saving}
            className={`w-full text-left flex items-start gap-2.5 p-2.5 rounded-lg border transition-all text-xs ${
              current.has(opt.value)
                ? "border-krypton/40 bg-krypton/5 text-bruma"
                : "border-border-subtle bg-carbon-400 text-bruma-muted"
            } ${!isLocked ? "hover:border-krypton/30 cursor-pointer" : "cursor-default opacity-70"}`}
          >
            <span className={`w-4 h-4 rounded flex items-center justify-center shrink-0 mt-0.5 border ${
              current.has(opt.value) ? "bg-krypton border-krypton text-carbon" : "border-border-subtle"
            }`}>
              {current.has(opt.value) && (
                <svg className="w-2.5 h-2.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
                </svg>
              )}
            </span>
            <div>
              <span className="font-medium">{opt.label}</span>
              <p className="text-plomo mt-0.5">{opt.description}</p>
            </div>
          </button>
        ))}
      </div>
    </SectionCard>
  );
}

// ── Impact Estimate Panel ─────────────────────────────────────────────────────

function ImpactEstimatePanel({ docId }: { docId: string }) {
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<SimulateImpactResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const run = async () => {
    setRunning(true);
    setError(null);
    try {
      const r = await simulateImpact(docId);
      setResult(r);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Error al simular");
    } finally {
      setRunning(false);
    }
  };

  return (
    <SectionCard title="Impacto estimado del perfil">
      {!result && (
        <div className="flex items-center gap-3">
          <button
            onClick={run}
            disabled={running}
            className="px-4 py-2 bg-krypton text-carbon text-xs font-semibold rounded-lg disabled:opacity-50 hover:bg-krypton/90 transition-colors flex items-center gap-2"
          >
            {running ? (
              <>
                <svg className="w-3.5 h-3.5 animate-spin" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                Analizando...
              </>
            ) : (
              <>
                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                </svg>
                Simular impacto
              </>
            )}
          </button>
          <p className="text-xs text-plomo">Estima sustituciones, routing y costo sin procesar el documento.</p>
        </div>
      )}

      {error && <p className="text-red-400 text-xs mt-2">{error}</p>}

      {result && (
        <div className="space-y-3">
          <div className="grid grid-cols-3 gap-3">
            <div className="bg-carbon-400 rounded-lg p-3 text-center">
              <div className="text-xl font-bold text-krypton">{result.substitution_matches}</div>
              <div className="text-[10px] text-plomo uppercase tracking-wider mt-1">Sustituciones</div>
            </div>
            <div className="bg-carbon-400 rounded-lg p-3 text-center">
              <div className="text-xl font-bold text-bruma">${result.estimated_cost_usd.toFixed(4)}</div>
              <div className="text-[10px] text-plomo uppercase tracking-wider mt-1">Costo estimado</div>
            </div>
            <div className="bg-carbon-400 rounded-lg p-3 text-center">
              <div className="text-xl font-bold text-bruma">
                {result.estimated_duration_seconds < 60
                  ? `${result.estimated_duration_seconds}s`
                  : `${Math.round(result.estimated_duration_seconds / 60)}min`}
              </div>
              <div className="text-[10px] text-plomo uppercase tracking-wider mt-1">Duración est.</div>
            </div>
          </div>

          {/* Routing distribution */}
          <div>
            <span className="text-[10px] text-plomo uppercase tracking-wider block mb-2">
              Distribución de routing ({result.paragraph_routing.total} párrafos)
            </span>
            <div className="flex rounded-full overflow-hidden h-3">
              {result.paragraph_routing.total > 0 && (
                <>
                  <div
                    className="bg-plomo"
                    style={{ width: `${(result.paragraph_routing.skip / result.paragraph_routing.total) * 100}%` }}
                    title={`SKIP: ${result.paragraph_routing.skip}`}
                  />
                  <div
                    className="bg-krypton/60"
                    style={{ width: `${(result.paragraph_routing.micro / result.paragraph_routing.total) * 100}%` }}
                    title={`MICRO: ${result.paragraph_routing.micro}`}
                  />
                  <div
                    className="bg-krypton"
                    style={{ width: `${(result.paragraph_routing.macro / result.paragraph_routing.total) * 100}%` }}
                    title={`MACRO: ${result.paragraph_routing.macro}`}
                  />
                </>
              )}
            </div>
            <div className="flex gap-3 mt-1.5 text-[10px] text-plomo">
              <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-plomo inline-block" />SKIP {result.paragraph_routing.skip}</span>
              <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-krypton/60 inline-block" />MICRO {result.paragraph_routing.micro}</span>
              <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-krypton inline-block" />MACRO {result.paragraph_routing.macro}</span>
            </div>
          </div>

          {result.warnings.length > 0 && (
            <div className="p-2 bg-yellow-900/20 border border-yellow-700/30 rounded-lg">
              {result.warnings.map((w, i) => (
                <p key={i} className="text-xs text-yellow-400">{w}</p>
              ))}
            </div>
          )}

          <button
            onClick={() => setResult(null)}
            className="text-xs text-plomo hover:text-bruma transition-colors"
          >
            Volver a simular
          </button>
        </div>
      )}
    </SectionCard>
  );
}

// ── Main Panel ────────────────────────────────────────────────────────────────

export function EditorialProfilePanel({ docId }: { docId: string }) {
  const [data, setData] = useState<EditorialProfileFull | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const d = await getEditorialProfile(docId);
      setData(d);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Error al cargar el perfil editorial");
    } finally {
      setLoading(false);
    }
  }, [docId]);

  useEffect(() => { load(); }, [load]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-16 text-plomo text-sm">
        <svg className="w-4 h-4 animate-spin mr-2" fill="none" viewBox="0 0 24 24">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
        </svg>
        Cargando perfil editorial...
      </div>
    );
  }

  if (error) {
    return (
      <div className="text-center py-12 text-plomo">
        <p className="text-sm mb-2">{error}</p>
        <p className="text-xs text-plomo/60">El perfil editorial completo estará disponible cuando el análisis termine.</p>
      </div>
    );
  }

  if (!data) return null;

  const { profile, auto_detected: adn, is_locked } = data;

  return (
    <div className="space-y-0">
      {is_locked && (
        <div className="mb-4 p-3 bg-yellow-900/20 border border-yellow-700/30 rounded-xl flex items-center gap-2 text-xs text-yellow-400">
          <svg className="w-4 h-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" />
          </svg>
          Perfil bloqueado — el documento está en procesamiento. Usa "Reabrir revisión" para editar.
        </div>
      )}

      {/* ADN auto-detectado */}
      <AutoDetectedADN adn={adn} />

      {/* Substitution rules */}
      <SubstitutionRulesEditor
        docId={docId}
        rules={profile.substitution_rules || []}
        onRuleAdded={load}
        onRuleDeleted={load}
        isLocked={is_locked}
      />

      {/* Entity normalizations */}
      <EntityNormalizationsEditor
        docId={docId}
        norms={profile.entity_normalizations || []}
        onNormAdded={load}
        onNormDeleted={load}
        isLocked={is_locked}
      />

      {/* Idiolect protections */}
      <IdiolectProtectionsEditor
        docId={docId}
        protections={profile.idiolect_protections || []}
        onAdded={load}
        onDeleted={load}
        isLocked={is_locked}
      />

      {/* Register constraints */}
      <RegisterConstraintsSelector
        docId={docId}
        constraints={profile.register_constraints || []}
        onUpdated={load}
        isLocked={is_locked}
      />

      {/* Bloques del prompt — sólo visible cuando el documento se puede editar
         (ya pasó el setup inicial). La selección principal va en ProfileEditor. */}
      {!is_locked && (
        <PromptBlocksPanel
          profile={profile}
          locked={is_locked}
          onSave={async (updates: { prompt_blocks: PromptBlocksConfig }) => {
            await patchEditorialProfile(docId, updates);
            await load();
          }}
        />
      )}

      {/* Impact simulation */}
      <ImpactEstimatePanel docId={docId} />
    </div>
  );
}
