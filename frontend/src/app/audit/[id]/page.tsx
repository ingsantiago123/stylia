"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  getLlmAudit,
  getLlmAuditDiff,
  getGlobalContext,
  getDocument,
  LlmAuditEntry,
  LlmAuditStats,
  LlmAuditDiff,
  GlobalDocumentContext,
  DocumentDetail,
} from "@/lib/api";

// ─────────────────────────────────────────────────────────────────────────────
// Page
// ─────────────────────────────────────────────────────────────────────────────
export default function AuditDetailPage() {
  const { id: docId } = useParams<{ id: string }>();
  const router = useRouter();

  const [doc, setDoc] = useState<DocumentDetail | null>(null);
  const [stats, setStats] = useState<LlmAuditStats | null>(null);
  const [entries, setEntries] = useState<LlmAuditEntry[]>([]);
  const [globalCtx, setGlobalCtx] = useState<GlobalDocumentContext | null>(null);
  const [loading, setLoading] = useState(true);

  // Filters
  const [filterPass, setFilterPass] = useState<number | null>(null);
  const [filterErrors, setFilterErrors] = useState(false);
  const [filterReversions, setFilterReversions] = useState(false);
  const [search, setSearch] = useState("");

  // Per-paragraph diffs (lazy loaded)
  const [diffs, setDiffs] = useState<Record<number, LlmAuditDiff>>({});
  const [expanded, setExpanded] = useState<Set<number>>(new Set());
  const [loadingDiff, setLoadingDiff] = useState<number | null>(null);

  // Context panel toggle
  const [showContext, setShowContext] = useState(true);

  useEffect(() => {
    if (!docId) return;
    Promise.all([
      getDocument(docId).catch(() => null),
      getLlmAudit(docId, { pass_number: undefined }).catch(() => null),
      getGlobalContext(docId).catch(() => null),
    ]).then(([docData, auditData, ctx]) => {
      setDoc(docData);
      if (auditData) {
        setStats(auditData.stats);
        setEntries(auditData.entries);
      }
      setGlobalCtx(ctx);
      setLoading(false);
    });
  }, [docId]);

  // Reload with pass filter
  useEffect(() => {
    if (!docId || loading) return;
    getLlmAudit(docId, {
      pass_number: filterPass ?? undefined,
      has_error: filterErrors ? true : undefined,
    })
      .then((d) => { setStats(d.stats); setEntries(d.entries); })
      .catch(() => {});
  }, [docId, filterPass, filterErrors]); // eslint-disable-line react-hooks/exhaustive-deps

  const grouped = entries.reduce<Record<number, LlmAuditEntry[]>>((acc, e) => {
    const k = e.paragraph_index ?? -1;
    if (!acc[k]) acc[k] = [];
    acc[k].push(e);
    return acc;
  }, {});

  const paraIndices = Object.keys(grouped).map(Number).sort((a, b) => a - b);

  const filteredIndices = paraIndices.filter((idx) => {
    if (filterReversions) {
      const d = diffs[idx];
      const hasRev = (d?.pass2_audit?.reverted_destructions?.length ?? 0) > 0;
      const hasP2 = grouped[idx]?.some((c) => c.pass_number === 2);
      if (!hasRev && !hasP2) return false;
    }
    if (search.trim()) {
      const calls = grouped[idx] || [];
      const loc = calls[0]?.location || "";
      if (!loc.includes(search.trim()) && !String(idx).includes(search.trim())) return false;
    }
    return true;
  });

  const toggleExpand = useCallback(async (paraIdx: number) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(paraIdx)) { next.delete(paraIdx); return next; }
      next.add(paraIdx);
      return next;
    });
    if (!diffs[paraIdx]) {
      setLoadingDiff(paraIdx);
      try {
        const diff = await getLlmAuditDiff(docId, paraIdx);
        setDiffs((prev) => ({ ...prev, [paraIdx]: diff }));
      } catch (_) { /* silent */ }
      finally { setLoadingDiff(null); }
    }
  }, [docId, diffs]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[60vh] gap-3">
        <div className="w-5 h-5 border-2 border-krypton border-t-transparent rounded-full animate-spin" />
        <span className="text-plomo text-sm">Cargando auditoría...</span>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      {/* ── Header ── */}
      <div className="flex items-center gap-3">
        <button
          onClick={() => router.push("/audit")}
          className="flex items-center gap-1.5 text-plomo hover:text-krypton text-sm transition-colors group"
        >
          <svg className="w-4 h-4 group-hover:-translate-x-0.5 transition-transform" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M10.5 19.5L3 12m0 0l7.5-7.5M3 12h18" />
          </svg>
          Auditoría
        </button>
        <span className="text-plomo-dark">/</span>
        <span className="text-sm text-bruma font-medium truncate max-w-xs">{doc?.filename ?? docId}</span>
        <span className="ml-auto text-[11px] font-mono text-plomo-dark bg-surface-elevated px-2 py-0.5 rounded">
          Plan v4 — Doble Pasada
        </span>
      </div>

      {/* ── Stats bar ── */}
      {stats && (
        <div className="grid grid-cols-3 sm:grid-cols-6 gap-2">
          <StatCard label="Llamadas LLM" value={stats.total_calls} color="text-bruma" />
          <StatCard label="Pasada 1" value={stats.pass1_calls} color="text-blue-400" />
          <StatCard label="Pasada 2" value={stats.pass2_calls} color="text-krypton" />
          <StatCard label="Párrafos auditados" value={stats.paragraphs_with_audit} color="text-bruma" />
          <StatCard label="Reversiones" value={stats.total_reversions_detected} color="text-amber-400" />
          <StatCard label="Errores" value={stats.errors} color={stats.errors > 0 ? "text-red-400" : "text-plomo-dark"} />
        </div>
      )}

      {/* ── Global context panel ── */}
      {globalCtx && (
        <div className="glass-card rounded-xl overflow-hidden">
          <button
            onClick={() => setShowContext(!showContext)}
            className="w-full px-4 py-3 flex items-center gap-2 hover:bg-surface-hover transition-colors text-left"
          >
            <span className="text-[10px] font-mono text-krypton uppercase tracking-widest">ADN EDITORIAL</span>
            <span className="text-xs text-plomo ml-2">{globalCtx.dominant_register} · {globalCtx.total_paragraphs} párrafos</span>
            <svg className={`w-4 h-4 text-plomo ml-auto transition-transform ${showContext ? "rotate-180" : ""}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19.5 8.25l-7.5 7.5-7.5-7.5" />
            </svg>
          </button>
          {showContext && (
            <div className="border-t border-border-subtle px-4 py-4 space-y-4">
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                {/* Summary + voice */}
                <div className="space-y-3">
                  <Field label="RESUMEN GLOBAL" value={globalCtx.global_summary} mono={false} />
                  <Field label="VOZ DEL AUTOR" value={globalCtx.dominant_voice} mono={false} />
                  <div className="grid grid-cols-2 gap-3">
                    <Field label="REGISTRO" value={globalCtx.dominant_register} />
                    {globalCtx.style_fingerprint && (
                      <div>
                        <p className="text-[9px] text-plomo-dark uppercase tracking-wider mb-1">HUELLA DE ESTILO</p>
                        <div className="space-y-0.5">
                          {Object.entries(globalCtx.style_fingerprint).map(([k, v]) => (
                            <div key={k} className="flex gap-2 text-[11px]">
                              <span className="text-plomo-dark font-mono w-32 shrink-0">{k}</span>
                              <span className="text-bruma font-mono">{String(v)}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                </div>

                {/* Themes + protected terms */}
                <div className="space-y-3">
                  {globalCtx.key_themes?.length > 0 && (
                    <div>
                      <p className="text-[9px] text-plomo-dark uppercase tracking-wider mb-1.5">TEMAS CLAVE</p>
                      <div className="space-y-1">
                        {globalCtx.key_themes.map((t, i) => (
                          <div key={i} className="flex items-center gap-2">
                            <div className="flex-1 bg-surface-elevated rounded-full h-1.5">
                              <div className="bg-krypton rounded-full h-1.5" style={{ width: `${Math.round(t.weight * 100)}%` }} />
                            </div>
                            <span className="text-[11px] text-bruma w-48 truncate">{t.theme}</span>
                            <span className="text-[10px] text-plomo-dark font-mono w-8 text-right">{Math.round(t.weight * 100)}%</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                  {globalCtx.protected_globals?.length > 0 && (
                    <div>
                      <p className="text-[9px] text-plomo-dark uppercase tracking-wider mb-1.5">TÉRMINOS PROTEGIDOS GLOBALES</p>
                      <div className="flex flex-wrap gap-1.5">
                        {globalCtx.protected_globals.map((t, i) => (
                          <span key={i} title={t.reason} className="text-[11px] px-2 py-0.5 bg-amber-500/10 border border-amber-500/30 text-amber-300 rounded font-mono">
                            {t.term}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── Filters ── */}
      <div className="glass-card rounded-xl p-3 flex flex-wrap gap-2 items-center">
        <span className="text-[10px] text-plomo-dark uppercase tracking-wider font-medium">Filtros</span>
        <FilterBtn active={filterPass === null} onClick={() => setFilterPass(null)} label="Todas las pasadas" />
        <FilterBtn active={filterPass === 1} onClick={() => setFilterPass(1)} label="Solo Pasada 1" />
        <FilterBtn active={filterPass === 2} onClick={() => setFilterPass(2)} label="Solo Pasada 2" />
        <FilterBtn active={filterErrors} onClick={() => setFilterErrors(!filterErrors)} label="Con errores" accent="border-red-500/50 text-red-400" />
        <FilterBtn active={filterReversions} onClick={() => setFilterReversions(!filterReversions)} label="Con reversiones" accent="border-amber-500/50 text-amber-400" />
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Buscar por índice o location…"
          className="ml-auto text-xs bg-surface-elevated border border-border-subtle rounded-lg px-3 py-1.5 text-bruma placeholder:text-plomo-dark focus:outline-none focus:border-krypton/40 w-56"
        />
        <span className="text-[10px] text-plomo-dark font-mono">{filteredIndices.length} / {paraIndices.length} párrafos</span>
      </div>

      {/* ── Expand / Collapse all ── */}
      {filteredIndices.length > 0 && (
        <div className="flex gap-2">
          <button
            onClick={() => filteredIndices.forEach((idx) => { if (!expanded.has(idx)) toggleExpand(idx); })}
            className="text-[11px] px-3 py-1 border border-border-subtle text-plomo hover:text-bruma rounded-lg transition-colors"
          >
            Expandir todos
          </button>
          <button
            onClick={() => setExpanded(new Set())}
            className="text-[11px] px-3 py-1 border border-border-subtle text-plomo hover:text-bruma rounded-lg transition-colors"
          >
            Colapsar todos
          </button>
        </div>
      )}

      {/* ── Paragraph list ── */}
      {filteredIndices.length === 0 && (
        <div className="text-center py-16 text-plomo text-sm glass-card rounded-xl">
          No hay datos de auditoría.
        </div>
      )}

      <div className="space-y-2">
        {filteredIndices.map((paraIdx) => {
          const calls = grouped[paraIdx] || [];
          const hasP1 = calls.some((c) => c.pass_number === 1);
          const hasP2 = calls.some((c) => c.pass_number === 2);
          const hasErr = calls.some((c) => c.has_error);
          const diff = diffs[paraIdx];
          const reverted = diff?.pass2_audit?.reverted_destructions ?? [];
          const improvements = diff?.pass2_audit?.style_improvements ?? [];
          const isExp = expanded.has(paraIdx);
          const isLoadingThis = loadingDiff === paraIdx;
          const location = calls[0]?.location ?? `body:${paraIdx}`;
          const totalTokens = calls.reduce((s, c) => s + (c.total_tokens ?? 0), 0);

          return (
            <div key={paraIdx} className="glass-card rounded-xl overflow-hidden">
              {/* Row header */}
              <button
                onClick={() => toggleExpand(paraIdx)}
                className="w-full px-4 py-3 flex items-center gap-3 hover:bg-surface-hover transition-colors text-left"
              >
                <span className="text-xs font-mono text-plomo-dark w-10 shrink-0">#{paraIdx}</span>
                <span className="text-xs font-mono text-plomo shrink-0">{location}</span>
                <div className="flex items-center gap-1 ml-2 flex-wrap">
                  {hasP1 && <Badge label="P1" color="bg-blue-500/15 text-blue-300 border-blue-500/20" />}
                  {hasP2 && <Badge label="P2" color="bg-krypton/15 text-krypton border-krypton/20" />}
                  {hasErr && <Badge label="Error" color="bg-red-500/15 text-red-400 border-red-500/20" />}
                  {reverted.length > 0 && <Badge label={`${reverted.length} reversión${reverted.length > 1 ? "es" : ""}`} color="bg-amber-500/15 text-amber-300 border-amber-500/20" />}
                  {improvements.length > 0 && <Badge label={`${improvements.length} mejora${improvements.length > 1 ? "s" : ""}`} color="bg-emerald-500/15 text-emerald-400 border-emerald-500/20" />}
                </div>
                <div className="ml-auto flex items-center gap-3 shrink-0">
                  {totalTokens > 0 && (
                    <span className="text-[10px] font-mono text-plomo-dark">{totalTokens.toLocaleString()} tok</span>
                  )}
                  <svg className={`w-4 h-4 text-plomo transition-transform ${isExp ? "rotate-180" : ""}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19.5 8.25l-7.5 7.5-7.5-7.5" />
                  </svg>
                </div>
              </button>

              {/* Expanded body */}
              {isExp && (
                <div className="border-t border-border-subtle">
                  {isLoadingThis && (
                    <div className="flex items-center gap-2 px-4 py-4 text-sm text-plomo">
                      <div className="w-4 h-4 border border-krypton border-t-transparent rounded-full animate-spin" />
                      Cargando detalle...
                    </div>
                  )}

                  {diff && (
                    <div className="px-4 py-4 space-y-5">
                      {/* Triple-column diff */}
                      <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
                        <DiffBlock label="ORIGINAL" text={diff.original_text} badge={null} accent="text-plomo" />
                        <DiffBlock
                          label="PASADA 1 — MECÁNICA"
                          text={diff.corrected_pass1_text || diff.original_text}
                          badge={diff.corrected_pass1_text !== diff.original_text ? "Modificado" : "Sin cambios"}
                          accent={diff.corrected_pass1_text !== diff.original_text ? "text-blue-300" : "text-plomo-dark"}
                        />
                        <DiffBlock
                          label="FINAL AUDITADO (P2)"
                          text={diff.corrected_final_text}
                          badge={diff.has_pass2 ? "Auditado" : "Sin P2"}
                          accent="text-krypton"
                        />
                      </div>

                      {/* Reversions */}
                      {reverted.length > 0 && (
                        <div className="rounded-lg bg-amber-500/8 border border-amber-500/25 p-3 space-y-2">
                          <p className="text-[11px] font-semibold text-amber-400 uppercase tracking-wider">
                            Reversiones detectadas por Pasada 2 ({reverted.length})
                          </p>
                          {reverted.map((r, i) => (
                            <div key={i} className="flex items-start gap-3 text-xs">
                              <span className="mt-0.5 w-4 h-4 rounded-full bg-amber-500/20 text-amber-400 flex items-center justify-center text-[10px] shrink-0 font-bold">!</span>
                              <div>
                                <span className="text-amber-200 font-mono">{r.original_term}</span>
                                <span className="text-plomo-dark mx-1.5">→ (P1 lo cambió a)</span>
                                <span className="text-red-400 font-mono line-through">{r.pass1_changed_to}</span>
                                <span className="ml-2 text-[10px] px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-400 border border-amber-500/20">{r.severity}</span>
                                <p className="text-plomo-dark mt-0.5">{r.reason}</p>
                              </div>
                            </div>
                          ))}
                        </div>
                      )}

                      {/* Style improvements */}
                      {improvements.length > 0 && (
                        <div className="rounded-lg bg-emerald-500/8 border border-emerald-500/25 p-3 space-y-2">
                          <p className="text-[11px] font-semibold text-emerald-400 uppercase tracking-wider">
                            Mejoras de estilo aplicadas ({improvements.length})
                          </p>
                          {improvements.map((imp, i) => (
                            <div key={i} className="flex items-start gap-3 text-xs">
                              <span className="mt-0.5 w-4 h-4 rounded-full bg-emerald-500/20 text-emerald-400 flex items-center justify-center text-[10px] shrink-0">✓</span>
                              <div>
                                <span className="text-plomo font-mono">{imp.original_fragment}</span>
                                <span className="text-plomo-dark mx-1.5">→</span>
                                <span className="text-emerald-300 font-mono">{imp.improved_fragment}</span>
                                <span className="ml-2 text-[10px] px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">{imp.category}</span>
                                <p className="text-plomo-dark mt-0.5">{imp.explanation}</p>
                              </div>
                            </div>
                          ))}
                        </div>
                      )}

                      {/* Pass 1 raw */}
                      {diff.pass1 && (
                        <FullCallViewer
                          label="PASADA 1 — CORRECCIÓN MECÁNICA"
                          accent="text-blue-300"
                          req={diff.pass1.request_payload}
                          res={diff.pass1.response_payload}
                          tokens={diff.pass1.tokens}
                          latency={diff.pass1.latency_ms}
                          model={diff.pass1.model_used}
                        />
                      )}

                      {/* Pass 2 raw */}
                      {diff.pass2 && (
                        <FullCallViewer
                          label="PASADA 2 — AUDITORÍA CONTEXTUAL"
                          accent="text-krypton"
                          req={diff.pass2.request_payload}
                          res={diff.pass2.response_payload}
                          tokens={diff.pass2.tokens}
                          latency={diff.pass2.latency_ms}
                          model={diff.pass2.model_used}
                        />
                      )}

                      {/* Confidence */}
                      {diff.pass2_audit?.confidence != null && (
                        <div className="flex items-center gap-2">
                          <span className="text-[10px] text-plomo-dark uppercase tracking-wider">Confianza P2</span>
                          <div className="flex-1 bg-surface-elevated rounded-full h-1.5 max-w-32">
                            <div
                              className="bg-krypton rounded-full h-1.5"
                              style={{ width: `${Math.round(diff.pass2_audit.confidence * 100)}%` }}
                            />
                          </div>
                          <span className="text-[11px] font-mono text-krypton">
                            {Math.round(diff.pass2_audit.confidence * 100)}%
                          </span>
                          {diff.pass2_audit.pass1_quality && (
                            <span className={`text-[10px] px-2 py-0.5 rounded border font-mono ${
                              diff.pass2_audit.pass1_quality === "ok"
                                ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
                                : diff.pass2_audit.pass1_quality === "minor_issues"
                                ? "bg-amber-500/10 text-amber-400 border-amber-500/20"
                                : "bg-red-500/10 text-red-400 border-red-500/20"
                            }`}>
                              P1: {diff.pass2_audit.pass1_quality}
                            </span>
                          )}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// FullCallViewer — shows full system + user prompts and response
// ─────────────────────────────────────────────────────────────────────────────
interface FullCallViewerProps {
  label: string;
  accent: string;
  req: Record<string, unknown> | null | undefined;
  res: Record<string, unknown> | null | undefined;
  tokens: number | null | undefined;
  latency: number | null | undefined;
  model: string | null | undefined;
}

function FullCallViewer({ label, accent, req, res, tokens, latency, model }: FullCallViewerProps) {
  const [showRaw, setShowRaw] = useState(false);

  const messages = (req as { messages?: Array<{ role: string; content: string }> })?.messages ?? [];
  const systemMsg = messages.find((m) => m.role === "system");
  const userMsg = messages.find((m) => m.role === "user");
  const assistantContent = (() => {
    try {
      const choices = (res as { choices?: Array<{ message: { content: string } }> })?.choices ?? [];
      return choices[0]?.message?.content ?? null;
    } catch { return null; }
  })();

  return (
    <div className="rounded-xl border border-border-subtle overflow-hidden">
      {/* Header */}
      <div className="px-4 py-2.5 bg-surface-elevated flex items-center gap-2 border-b border-border-subtle">
        <span className={`text-[11px] font-semibold uppercase tracking-wider ${accent}`}>{label}</span>
        {model && <span className="text-[10px] font-mono text-plomo-dark ml-1">{model}</span>}
        <div className="ml-auto flex items-center gap-3">
          {tokens != null && <span className="text-[10px] font-mono text-plomo-dark">{tokens.toLocaleString()} tokens</span>}
          {latency != null && <span className="text-[10px] font-mono text-plomo-dark">{latency}ms</span>}
          <button
            onClick={() => setShowRaw(!showRaw)}
            className={`text-[10px] px-2 py-0.5 border rounded transition-all ${showRaw ? "border-krypton text-krypton" : "border-border-subtle text-plomo hover:border-plomo"}`}
          >
            {showRaw ? "Ocultar RAW" : "Ver RAW JSON"}
          </button>
        </div>
      </div>

      <div className="divide-y divide-border-subtle">
        {/* System prompt */}
        {systemMsg && (
          <PromptBlock role="SYSTEM" content={systemMsg.content} />
        )}
        {/* User prompt */}
        {userMsg && (
          <PromptBlock role="USER" content={userMsg.content} />
        )}
        {/* Response */}
        {assistantContent && (
          <PromptBlock role="RESPUESTA" content={assistantContent} accent="text-krypton" />
        )}
      </div>

      {/* RAW JSON (optional) */}
      {showRaw && (
        <div className="border-t border-border-subtle bg-carbon/50 divide-y divide-border-subtle">
          {req && <RawJsonBlock label="REQUEST JSON" data={req} />}
          {res && <RawJsonBlock label="RESPONSE JSON" data={res} />}
        </div>
      )}
    </div>
  );
}

function PromptBlock({ role, content, accent = "text-bruma" }: { role: string; content: string; accent?: string }) {
  const [hidden, setHidden] = useState(false);
  const lines = content.split("\n").length;

  return (
    <div className="px-4 py-3 space-y-1.5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-[9px] font-mono uppercase tracking-widest text-plomo-dark">{role}</span>
          <span className="text-[9px] font-mono text-plomo-dark/50">{lines} líneas · {content.length} chars</span>
        </div>
        <div className="flex items-center gap-2">
          <CopyBtn text={content} />
          <button
            onClick={() => setHidden(!hidden)}
            className="text-[10px] px-2 py-0.5 border border-border-subtle text-plomo rounded hover:border-plomo transition-colors"
          >
            {hidden ? "▼ Mostrar" : "▲ Ocultar"}
          </button>
        </div>
      </div>
      {!hidden && (
        <pre className={`text-[11px] font-mono leading-relaxed whitespace-pre-wrap break-words ${accent} overflow-y-auto max-h-[600px] overflow-x-auto bg-carbon/30 rounded-lg p-3 border border-border-subtle/40`}>
          {content}
        </pre>
      )}
    </div>
  );
}

function RawJsonBlock({ label, data }: { label: string; data: object }) {
  return (
    <div className="px-4 py-3">
      <div className="flex items-center justify-between mb-1.5">
        <span className="text-[9px] font-mono uppercase tracking-widest text-plomo-dark">{label}</span>
        <CopyBtn text={JSON.stringify(data, null, 2)} />
      </div>
      <pre className="text-[10px] font-mono text-bruma/70 whitespace-pre-wrap break-all overflow-x-auto leading-relaxed">
        {JSON.stringify(data, null, 2)}
      </pre>
    </div>
  );
}

function CopyBtn({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      onClick={() => { navigator.clipboard.writeText(text); setCopied(true); setTimeout(() => setCopied(false), 1500); }}
      className="text-[10px] px-2 py-0.5 border border-border-subtle text-plomo rounded hover:text-krypton hover:border-krypton/40 transition-colors"
    >
      {copied ? "✓ Copiado" : "Copiar"}
    </button>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Primitives
// ─────────────────────────────────────────────────────────────────────────────
function StatCard({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div className="glass-card rounded-xl p-3 text-center">
      <div className={`text-2xl font-bold ${color}`}>{value.toLocaleString()}</div>
      <div className="text-[9px] text-plomo-dark uppercase tracking-wider mt-0.5">{label}</div>
    </div>
  );
}

function FilterBtn({ active, onClick, label, accent }: { active: boolean; onClick: () => void; label: string; accent?: string }) {
  return (
    <button
      onClick={onClick}
      className={`px-2.5 py-1 text-xs rounded-lg border transition-all ${
        active
          ? "border-krypton bg-krypton/10 text-krypton"
          : `border-border-subtle text-plomo hover:border-plomo ${accent ?? ""}`
      }`}
    >
      {label}
    </button>
  );
}

function Badge({ label, color }: { label: string; color: string }) {
  return (
    <span className={`px-1.5 py-0.5 text-[10px] font-medium rounded border ${color}`}>{label}</span>
  );
}

function DiffBlock({ label, text, badge, accent }: { label: string; text: string | null | undefined; badge: string | null; accent: string }) {
  return (
    <div className="rounded-lg bg-surface-hover/40 border border-border-subtle/50 p-3 flex flex-col gap-2">
      <div className="flex items-center justify-between">
        <span className="text-[9px] font-mono uppercase tracking-widest text-plomo-dark">{label}</span>
        {badge && (
          <span className="text-[9px] px-1.5 py-0.5 rounded bg-surface text-plomo-dark border border-border-subtle">{badge}</span>
        )}
      </div>
      <p className={`text-xs font-mono leading-relaxed whitespace-pre-wrap break-words ${accent}`}>
        {text ?? <span className="text-plomo-dark italic">—</span>}
      </p>
    </div>
  );
}

function Field({ label, value, mono = true }: { label: string; value: string | null | undefined; mono?: boolean }) {
  return (
    <div>
      <p className="text-[9px] text-plomo-dark uppercase tracking-wider mb-1">{label}</p>
      <p className={`text-xs text-bruma leading-relaxed ${mono ? "font-mono" : ""}`}>{value ?? "—"}</p>
    </div>
  );
}
