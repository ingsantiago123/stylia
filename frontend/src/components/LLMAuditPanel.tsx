"use client";

import { useState, useEffect } from "react";
import { getLlmAudit, getLlmAuditDiff, LlmAuditEntry, LlmAuditStats, LlmAuditDiff } from "@/lib/api";

interface Props {
  docId: string;
}

export function LLMAuditPanel({ docId }: Props) {
  const [entries, setEntries] = useState<LlmAuditEntry[]>([]);
  const [stats, setStats] = useState<LlmAuditStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [filterPass, setFilterPass] = useState<number | null>(null);
  const [filterOnlyReversions, setFilterOnlyReversions] = useState(false);
  const [filterErrors, setFilterErrors] = useState(false);
  const [expandedPara, setExpandedPara] = useState<number | null>(null);
  const [diffData, setDiffData] = useState<Record<number, LlmAuditDiff>>({});
  const [loadingDiff, setLoadingDiff] = useState<number | null>(null);

  useEffect(() => {
    setLoading(true);
    getLlmAudit(docId, {
      pass_number: filterPass ?? undefined,
      has_error: filterErrors ? true : undefined,
    })
      .then((data) => {
        setEntries(data.entries);
        setStats(data.stats);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [docId, filterPass, filterErrors]);

  const grouped = entries.reduce<Record<number, LlmAuditEntry[]>>((acc, e) => {
    const k = e.paragraph_index ?? -1;
    if (!acc[k]) acc[k] = [];
    acc[k].push(e);
    return acc;
  }, {});

  const paraIndices = Object.keys(grouped)
    .map(Number)
    .sort((a, b) => a - b);

  async function handleExpand(paraIdx: number) {
    if (expandedPara === paraIdx) {
      setExpandedPara(null);
      return;
    }
    setExpandedPara(paraIdx);
    if (!diffData[paraIdx]) {
      setLoadingDiff(paraIdx);
      try {
        const diff = await getLlmAuditDiff(docId, paraIdx);
        setDiffData((prev) => ({ ...prev, [paraIdx]: diff }));
      } catch (_e) {
        // silencioso
      } finally {
        setLoadingDiff(null);
      }
    }
  }

  function hasRevertion(paraIdx: number): boolean {
    const d = diffData[paraIdx];
    if (!d?.pass2_audit) return false;
    return (d.pass2_audit.reverted_destructions?.length ?? 0) > 0;
  }

  const filteredIndices = paraIndices.filter((idx) => {
    if (filterOnlyReversions && !hasRevertion(idx)) {
      const calls = grouped[idx] || [];
      const hasP2 = calls.some((c) => c.pass_number === 2);
      if (!hasP2) return false;
    }
    return true;
  });

  if (loading) {
    return (
      <div className="flex items-center justify-center py-16">
        <div className="w-6 h-6 border-2 border-krypton border-t-transparent rounded-full animate-spin" />
        <span className="ml-3 text-plomo text-sm">Cargando auditoría...</span>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Stats globales */}
      {stats && (
        <div className="glass-card rounded-xl p-4">
          <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
            <StatBadge label="Llamadas LLM" value={stats.total_calls} />
            <StatBadge label="Pasada 1" value={stats.pass1_calls} color="text-bruma" />
            <StatBadge label="Pasada 2" value={stats.pass2_calls} color="text-krypton" />
            <StatBadge label="Párrafos auditados" value={stats.paragraphs_with_audit} />
            <StatBadge label="Reversiones detectadas" value={stats.total_reversions_detected} color="text-amber-400" />
          </div>
        </div>
      )}

      {/* Filtros */}
      <div className="glass-card rounded-xl p-3 flex flex-wrap gap-2 items-center">
        <span className="text-[11px] text-plomo uppercase tracking-wider font-medium">Filtros</span>
        <FilterBtn active={filterPass === null} onClick={() => setFilterPass(null)} label="Todas las pasadas" />
        <FilterBtn active={filterPass === 1} onClick={() => setFilterPass(1)} label="Solo Pasada 1" />
        <FilterBtn active={filterPass === 2} onClick={() => setFilterPass(2)} label="Solo Pasada 2" />
        <FilterBtn active={filterErrors} onClick={() => setFilterErrors(!filterErrors)} label="Con errores" color="text-red-400" />
        <FilterBtn active={filterOnlyReversions} onClick={() => setFilterOnlyReversions(!filterOnlyReversions)} label="Con reversiones" color="text-amber-400" />
      </div>

      {filteredIndices.length === 0 && (
        <div className="text-center py-12 text-plomo text-sm">
          No hay datos de auditoría LLM para este documento.
          {!stats?.total_calls && (
            <p className="text-xs mt-2 text-plomo-dark">El pipeline con doble pasada genera estos datos automáticamente.</p>
          )}
        </div>
      )}

      {/* Lista de párrafos */}
      <div className="space-y-1">
        {filteredIndices.map((paraIdx) => {
          const calls = grouped[paraIdx] || [];
          const hasP1 = calls.some((c) => c.pass_number === 1);
          const hasP2 = calls.some((c) => c.pass_number === 2);
          const hasErr = calls.some((c) => c.has_error);
          const diff = diffData[paraIdx];
          const reverted = diff?.pass2_audit?.reverted_destructions ?? [];
          const isExpanded = expandedPara === paraIdx;
          const isLoadingThis = loadingDiff === paraIdx;
          const location = calls[0]?.location || `body:${paraIdx}`;
          const totalTokens = calls.reduce((s, c) => s + (c.total_tokens ?? 0), 0);

          return (
            <div key={paraIdx} className="glass-card rounded-xl overflow-hidden">
              <button
                onClick={() => handleExpand(paraIdx)}
                className="w-full px-4 py-3 flex items-center gap-3 hover:bg-surface-hover transition-colors text-left"
              >
                <span className="text-xs font-mono text-plomo w-8">#{paraIdx}</span>
                <span className="text-xs text-plomo-dark font-mono">{location}</span>
                <div className="flex items-center gap-1.5 ml-2">
                  {hasP1 && <Badge color="bg-bruma/20 text-bruma" label="P1" />}
                  {hasP2 && <Badge color="bg-krypton/20 text-krypton" label="P2" />}
                  {hasErr && <Badge color="bg-red-500/20 text-red-400" label="Error" />}
                  {reverted.length > 0 && (
                    <Badge color="bg-amber-500/20 text-amber-400" label={`${reverted.length} revertido${reverted.length > 1 ? "s" : ""}`} />
                  )}
                </div>
                <div className="ml-auto flex items-center gap-3">
                  {totalTokens > 0 && (
                    <span className="text-[11px] text-plomo-dark">{totalTokens.toLocaleString()} tokens</span>
                  )}
                  <svg
                    className={`w-4 h-4 text-plomo transition-transform ${isExpanded ? "rotate-180" : ""}`}
                    fill="none" viewBox="0 0 24 24" stroke="currentColor"
                  >
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19.5 8.25l-7.5 7.5-7.5-7.5" />
                  </svg>
                </div>
              </button>

              {isExpanded && (
                <div className="border-t border-border-subtle px-4 py-4 space-y-4">
                  {isLoadingThis && (
                    <div className="flex items-center gap-2 text-sm text-plomo py-4">
                      <div className="w-4 h-4 border border-krypton border-t-transparent rounded-full animate-spin" />
                      Cargando detalle...
                    </div>
                  )}

                  {diff && (
                    <>
                      {/* Textos comparativos */}
                      <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
                        <TextBlock label="ORIGINAL" text={diff.original_text} color="text-plomo" />
                        <TextBlock
                          label="PASADA 1 (Mecánica)"
                          text={diff.corrected_pass1_text || diff.original_text}
                          color={diff.corrected_pass1_text ? "text-bruma" : "text-plomo-dark"}
                          badge={diff.corrected_pass1_text !== diff.original_text ? "Modificado" : "Sin cambios"}
                        />
                        <TextBlock
                          label="PASADA 2 / FINAL"
                          text={diff.corrected_final_text}
                          color="text-krypton"
                          badge={diff.has_pass2 ? "Auditado" : undefined}
                        />
                      </div>

                      {/* Reversiones */}
                      {reverted.length > 0 && (
                        <div className="rounded-lg bg-amber-500/10 border border-amber-500/30 p-3">
                          <p className="text-xs font-medium text-amber-400 mb-2">Reversiones detectadas en Pasada 2</p>
                          {reverted.map((r: {original_term: string; pass1_changed_to: string; reason: string; severity: string}, i: number) => (
                            <div key={i} className="flex items-start gap-2 text-xs text-amber-300 mt-1">
                              <span className="text-amber-500">✕</span>
                              <span>
                                <strong>{r.original_term}</strong> → <em>{r.pass1_changed_to}</em>
                                <span className="text-amber-400/70 ml-1">({r.reason})</span>
                              </span>
                            </div>
                          ))}
                        </div>
                      )}
                    </>
                  )}

                  {/* Prompts RAW colapsables por pasada */}
                  {calls.map((call) => (
                    <RawCallViewer key={call.id} call={call} />
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function StatBadge({ label, value, color = "text-bruma" }: { label: string; value: number; color?: string }) {
  return (
    <div className="text-center">
      <div className={`text-xl font-bold ${color}`}>{value.toLocaleString()}</div>
      <div className="text-[10px] text-plomo-dark uppercase tracking-wider mt-0.5">{label}</div>
    </div>
  );
}

function FilterBtn({
  active, onClick, label, color = "text-bruma"
}: { active: boolean; onClick: () => void; label: string; color?: string }) {
  return (
    <button
      onClick={onClick}
      className={`px-2.5 py-1 text-xs rounded-lg border transition-all ${
        active
          ? "border-krypton bg-krypton/10 text-krypton"
          : "border-border-subtle text-plomo hover:border-plomo"
      }`}
    >
      {label}
    </button>
  );
}

function Badge({ color, label }: { color: string; label: string }) {
  return (
    <span className={`px-1.5 py-0.5 text-[10px] font-medium rounded ${color}`}>{label}</span>
  );
}

function TextBlock({
  label, text, color, badge
}: { label: string; text: string | null | undefined; color: string; badge?: string }) {
  return (
    <div className="rounded-lg bg-surface-hover/50 p-3">
      <div className="flex items-center justify-between mb-2">
        <span className="text-[10px] font-medium uppercase tracking-wider text-plomo">{label}</span>
        {badge && <span className="text-[10px] px-1.5 py-0.5 rounded bg-surface text-plomo-dark">{badge}</span>}
      </div>
      <p className={`text-xs leading-relaxed ${color} font-mono whitespace-pre-wrap break-words`}>
        {text ?? <span className="text-plomo-dark italic">—</span>}
      </p>
    </div>
  );
}

function RawCallViewer({ call }: { call: LlmAuditEntry & { request_payload?: object; response_payload?: object } }) {
  const [showReq, setShowReq] = useState(false);
  const [showRes, setShowRes] = useState(false);

  return (
    <div className="rounded-lg border border-border-subtle p-3 space-y-2">
      <div className="flex items-center gap-2">
        <span className={`text-[11px] font-medium px-2 py-0.5 rounded ${
          call.pass_number === 2 ? "bg-krypton/20 text-krypton" : "bg-bruma/10 text-bruma"
        }`}>
          Pasada {call.pass_number} — {call.call_purpose}
        </span>
        <span className="text-[10px] text-plomo-dark">{call.model_used}</span>
        {call.total_tokens != null && (
          <span className="text-[10px] text-plomo-dark ml-auto">{call.total_tokens.toLocaleString()} tokens · {call.latency_ms}ms</span>
        )}
        {call.has_error && (
          <span className="text-[10px] text-red-400 ml-1">Error</span>
        )}
      </div>

      <div className="flex gap-2">
        <CollapseBtn active={showReq} onClick={() => setShowReq(!showReq)} label="Prompt enviado" />
        <CollapseBtn active={showRes} onClick={() => setShowRes(!showRes)} label="Respuesta OpenAI" />
      </div>

      {showReq && call.request_payload && (
        <JsonViewer data={call.request_payload} label="Request payload" />
      )}
      {showRes && call.response_payload && (
        <JsonViewer data={call.response_payload} label="Response payload" />
      )}
      {call.has_error && call.error_text && (
        <div className="text-xs text-red-400 bg-red-500/10 rounded p-2 font-mono">{call.error_text}</div>
      )}
    </div>
  );
}

function CollapseBtn({ active, onClick, label }: { active: boolean; onClick: () => void; label: string }) {
  return (
    <button
      onClick={onClick}
      className={`text-[10px] px-2 py-1 rounded border transition-all ${
        active ? "border-krypton text-krypton" : "border-border-subtle text-plomo hover:border-plomo"
      }`}
    >
      {active ? "▲" : "▼"} {label}
    </button>
  );
}

function JsonViewer({ data, label }: { data: object; label: string }) {
  return (
    <div className="rounded bg-surface-hover/60 p-2">
      <p className="text-[9px] text-plomo-dark uppercase tracking-wider mb-1">{label}</p>
      <pre className="text-[10px] text-bruma/80 overflow-x-auto max-h-64 font-mono leading-relaxed whitespace-pre-wrap break-all">
        {JSON.stringify(data, null, 2)}
      </pre>
    </div>
  );
}
