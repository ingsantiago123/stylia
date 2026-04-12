"use client";

import { useState, useMemo, useCallback } from "react";
import {
  PatchListItem,
  bulkReviewCorrections,
  finalizeDocument,
  reopenDocument,
  ReviewSummary,
} from "@/lib/api";
import { CorrectionActionPanel, FinalizeToolbar, ReviewStatusBadge } from "./CorrectionActionPanel";

interface CorrectionHistoryProps {
  corrections: PatchListItem[];
  docId: string;
  docStatus: string;
  reviewSummary?: ReviewSummary | null;
  onRefresh?: () => void;
}

type FilterSource = "all" | "languagetool" | "llm";
type FilterCategory = "all" | string;
type FilterSeverity = "all" | "critico" | "importante" | "sugerencia";

const CATEGORY_COLORS: Record<string, { bg: string; text: string }> = {
  redundancia: { bg: "bg-orange-900/30", text: "text-orange-400" },
  claridad: { bg: "bg-blue-900/30", text: "text-blue-400" },
  registro: { bg: "bg-indigo-900/30", text: "text-indigo-400" },
  cohesion: { bg: "bg-cyan-900/30", text: "text-cyan-400" },
  lexico: { bg: "bg-teal-900/30", text: "text-teal-400" },
  estructura: { bg: "bg-violet-900/30", text: "text-violet-400" },
  puntuacion: { bg: "bg-amber-900/30", text: "text-amber-400" },
  ritmo: { bg: "bg-pink-900/30", text: "text-pink-400" },
  muletilla: { bg: "bg-rose-900/30", text: "text-rose-400" },
};

const SEVERITY_COLORS: Record<string, { bg: string; text: string }> = {
  critico: { bg: "bg-red-900/30", text: "text-red-400" },
  importante: { bg: "bg-yellow-900/30", text: "text-yellow-400" },
  sugerencia: { bg: "bg-emerald-900/30", text: "text-emerald-400" },
};

const ROUTE_COLORS: Record<string, { bg: string; text: string; label: string }> = {
  skip: { bg: "bg-gray-900/30", text: "text-gray-400", label: "Skip" },
  cheap: { bg: "bg-blue-900/30", text: "text-blue-400", label: "Cheap" },
  editorial: { bg: "bg-purple-900/30", text: "text-purple-400", label: "Editorial" },
};

export function CorrectionHistory({ corrections, docId, docStatus, reviewSummary, onRefresh }: CorrectionHistoryProps) {
  const [filterSource, setFilterSource] = useState<FilterSource>("all");
  const [filterCategory, setFilterCategory] = useState<FilterCategory>("all");
  const [filterSeverity, setFilterSeverity] = useState<FilterSeverity>("all");
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState("");
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [actionLoading, setActionLoading] = useState(false);
  const [finalizeLoading, setFinalizeLoading] = useState(false);

  // Review mode: same rules as Compare — active in candidate_ready, completed, pending_review
  const isReviewMode = docStatus === "pending_review" || docStatus === "candidate_ready" || docStatus === "completed";
  const isCompleted = docStatus === "completed";

  const handleBulkAction = useCallback(async (action: "accepted" | "rejected") => {
    if (selectedIds.size === 0) return;
    setActionLoading(true);
    try {
      await bulkReviewCorrections(docId, Array.from(selectedIds), action);
      setSelectedIds(new Set());
      onRefresh?.();
    } catch (err) {
      console.error("Error bulk reviewing:", err);
    } finally {
      setActionLoading(false);
    }
  }, [docId, selectedIds, onRefresh]);

  const handleFinalize = useCallback(async (mode: "quick" | "strict") => {
    setFinalizeLoading(true);
    try {
      await finalizeDocument(docId, mode, "accepted_and_auto");
      onRefresh?.();
    } catch (err) {
      console.error("Error finalizing:", err);
    } finally {
      setFinalizeLoading(false);
    }
  }, [docId, onRefresh]);

  const handleReopen = useCallback(async () => {
    setFinalizeLoading(true);
    try {
      await reopenDocument(docId);
      onRefresh?.();
    } catch (err) {
      console.error("Error reopening:", err);
    } finally {
      setFinalizeLoading(false);
    }
  }, [docId, onRefresh]);

  const toggleSelect = useCallback((id: string) => {
    setSelectedIds(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  const selectAllFiltered = useCallback(() => {
    setSelectedIds(prev => {
      const all = new Set(prev);
      filtered.forEach(c => all.add(c.id));
      return all;
    });
  }, []);  // filtered dependency added via useMemo below

  const categories = useMemo(() => {
    const cats = new Set<string>();
    corrections.forEach((c) => { if (c.category) cats.add(c.category); });
    return Array.from(cats).sort();
  }, [corrections]);

  const filtered = useMemo(() => {
    let result = corrections;
    if (filterSource !== "all") {
      result = result.filter((c) =>
        filterSource === "languagetool"
          ? c.source === "languagetool"
          : c.source.includes("chatgpt") || c.source === "llm"
      );
    }
    if (filterCategory !== "all") {
      result = result.filter((c) => c.category === filterCategory);
    }
    if (filterSeverity !== "all") {
      result = result.filter((c) => c.severity === filterSeverity);
    }
    if (searchTerm.trim()) {
      const term = searchTerm.toLowerCase();
      result = result.filter(
        (c) =>
          c.original_text.toLowerCase().includes(term) ||
          c.corrected_text.toLowerCase().includes(term)
      );
    }
    return result;
  }, [corrections, filterSource, filterCategory, filterSeverity, searchTerm]);

  const stats = useMemo(() => {
    const lt = corrections.filter((c) => c.source === "languagetool").length;
    const llm = corrections.filter((c) => c.source.includes("chatgpt") || c.source === "llm").length;
    const routeSkip = corrections.filter((c) => c.route_taken === "skip").length;
    const routeCheap = corrections.filter((c) => c.route_taken === "cheap").length;
    const routeEditorial = corrections.filter((c) => c.route_taken === "editorial").length;
    const validated = corrections.filter((c) => c.review_status === "auto_accepted").length;
    const flagged = corrections.filter((c) => c.review_status === "manual_review").length;
    const rejected = corrections.filter((c) => c.review_status === "gate_rejected").length;
    return { total: corrections.length, languagetool: lt, llm, routeSkip, routeCheap, routeEditorial, validated, flagged, rejected };
  }, [corrections]);

  if (corrections.length === 0) {
    return (
      <div className="glass-card rounded-xl p-8 text-center">
        <div className="w-14 h-14 mx-auto mb-4 rounded-2xl bg-surface flex items-center justify-center">
          <svg className="w-6 h-6 text-plomo" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        </div>
        <p className="text-bruma font-medium">Sin correcciones</p>
        <p className="text-plomo text-sm mt-1">El documento no necesitó correcciones o aún se está procesando</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Stats bar */}
      <div className="glass-card rounded-xl p-4">
        <div className="flex items-center justify-between flex-wrap gap-4">
          {/* Counters */}
          <div className="flex items-center gap-6">
            <div className="text-center">
              <div className="text-2xl font-bold text-krypton">{stats.total}</div>
              <div className="text-[10px] uppercase tracking-wider text-plomo">Total</div>
            </div>
            <div className="h-8 w-px bg-carbon-300" />
            <div className="text-center">
              <div className="text-lg font-semibold text-bruma">{stats.languagetool}</div>
              <div className="text-[10px] uppercase tracking-wider text-plomo">LanguageTool</div>
            </div>
            <div className="text-center">
              <div className="text-lg font-semibold text-bruma">{stats.llm}</div>
              <div className="text-[10px] uppercase tracking-wider text-plomo">LLM</div>
            </div>
            {(stats.routeSkip > 0 || stats.routeCheap > 0 || stats.routeEditorial > 0) && (
              <>
                <div className="h-8 w-px bg-carbon-300" />
                {stats.routeSkip > 0 && (
                  <div className="text-center">
                    <div className="text-lg font-semibold text-gray-400">{stats.routeSkip}</div>
                    <div className="text-[10px] uppercase tracking-wider text-plomo">Skip</div>
                  </div>
                )}
                <div className="text-center">
                  <div className="text-lg font-semibold text-blue-400">{stats.routeCheap}</div>
                  <div className="text-[10px] uppercase tracking-wider text-plomo">Cheap</div>
                </div>
                {stats.routeEditorial > 0 && (
                  <div className="text-center">
                    <div className="text-lg font-semibold text-purple-400">{stats.routeEditorial}</div>
                    <div className="text-[10px] uppercase tracking-wider text-plomo">Editorial</div>
                  </div>
                )}
              </>
            )}
            {(stats.flagged > 0 || stats.rejected > 0) && (
              <>
                <div className="h-8 w-px bg-carbon-300" />
                <div className="text-center">
                  <div className="text-lg font-semibold text-krypton">{stats.validated}</div>
                  <div className="text-[10px] uppercase tracking-wider text-plomo">Validados</div>
                </div>
                {stats.flagged > 0 && (
                  <div className="text-center">
                    <div className="text-lg font-semibold text-orange-400">{stats.flagged}</div>
                    <div className="text-[10px] uppercase tracking-wider text-plomo">Revisión</div>
                  </div>
                )}
                {stats.rejected > 0 && (
                  <div className="text-center">
                    <div className="text-lg font-semibold text-red-400">{stats.rejected}</div>
                    <div className="text-[10px] uppercase tracking-wider text-plomo">Rechazados</div>
                  </div>
                )}
              </>
            )}
          </div>

          {/* Filters */}
          <div className="flex items-center gap-2 flex-wrap">
            {(["all", "languagetool", "llm"] as FilterSource[]).map((f) => (
              <button
                key={f}
                onClick={() => setFilterSource(f)}
                className={`
                  px-3 py-1.5 text-xs font-medium rounded-lg transition-all
                  ${filterSource === f
                    ? "bg-krypton text-carbon"
                    : "bg-surface text-plomo hover:text-bruma hover:bg-carbon-300"
                  }
                `}
              >
                {f === "all" ? "Todas" : f === "languagetool" ? "LanguageTool" : "LLM"}
              </button>
            ))}

            {/* Category filter */}
            {categories.length > 0 && (
              <select
                value={filterCategory}
                onChange={(e) => setFilterCategory(e.target.value)}
                className="px-2 py-1.5 text-xs font-medium rounded-lg bg-surface text-plomo border border-border focus:outline-none focus:border-krypton/50 cursor-pointer"
              >
                <option value="all">Categoría: todas</option>
                {categories.map((cat) => (
                  <option key={cat} value={cat}>{cat}</option>
                ))}
              </select>
            )}

            {/* Severity filter */}
            {corrections.some((c) => c.severity) && (
              <select
                value={filterSeverity}
                onChange={(e) => setFilterSeverity(e.target.value as FilterSeverity)}
                className="px-2 py-1.5 text-xs font-medium rounded-lg bg-surface text-plomo border border-border focus:outline-none focus:border-krypton/50 cursor-pointer"
              >
                <option value="all">Severidad: todas</option>
                <option value="critico">Crítico</option>
                <option value="importante">Importante</option>
                <option value="sugerencia">Sugerencia</option>
              </select>
            )}
          </div>
        </div>

        {/* Search */}
        <div className="mt-3 relative">
          <svg className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-plomo" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
          </svg>
          <input
            type="text"
            placeholder="Buscar en correcciones..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full bg-surface border border-border rounded-lg pl-10 pr-4 py-2 text-sm text-bruma placeholder:text-plomo focus:outline-none focus:border-krypton/50 focus:ring-1 focus:ring-krypton/20 transition-colors"
          />
        </div>
      </div>

      {/* Review toolbar — unified FinalizeToolbar + bulk actions */}
      {isReviewMode && reviewSummary && (
        <div className="space-y-3">
          <FinalizeToolbar
            reviewSummary={reviewSummary}
            onFinalize={handleFinalize}
            onReopen={isCompleted ? handleReopen : undefined}
            isCompleted={isCompleted}
            loading={finalizeLoading}
          />
          {/* Bulk selection bar */}
          <div className="glass-card rounded-xl p-3 flex items-center justify-between flex-wrap gap-2">
            <div className="flex items-center gap-2">
              <button
                onClick={selectAllFiltered}
                className="px-3 py-1.5 text-xs font-medium rounded-lg bg-surface text-plomo hover:text-bruma transition-colors"
              >
                Seleccionar todo ({filtered.length})
              </button>
              {selectedIds.size > 0 && (
                <button
                  onClick={() => setSelectedIds(new Set())}
                  className="px-2 py-1.5 text-xs text-plomo hover:text-bruma transition-colors"
                >
                  Deseleccionar ({selectedIds.size})
                </button>
              )}
            </div>
            {selectedIds.size > 0 && (
              <div className="flex items-center gap-2">
                <span className="text-xs text-plomo">{selectedIds.size} seleccionados</span>
                <button
                  onClick={() => handleBulkAction("accepted")}
                  disabled={actionLoading}
                  className="px-3 py-1.5 text-xs font-medium rounded-lg bg-emerald-500/15 text-emerald-400 hover:bg-emerald-500/25 border border-emerald-500/20 transition-colors disabled:opacity-50"
                >
                  Aceptar sel.
                </button>
                <button
                  onClick={() => handleBulkAction("rejected")}
                  disabled={actionLoading}
                  className="px-3 py-1.5 text-xs font-medium rounded-lg bg-red-500/15 text-red-400 hover:bg-red-500/25 border border-red-500/20 transition-colors disabled:opacity-50"
                >
                  Rechazar sel.
                </button>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Corrections list */}
      <div className="space-y-2">
        {filtered.length === 0 ? (
          <div className="text-center py-8 text-plomo text-sm">
            No se encontraron correcciones con ese filtro
          </div>
        ) : (
          filtered.map((patch, index) => (
            <CorrectionCard
              key={patch.id}
              patch={patch}
              index={index + 1}
              isExpanded={expandedId === patch.id}
              onToggle={() => setExpandedId(expandedId === patch.id ? null : patch.id)}
              isReviewMode={isReviewMode}
              isSelected={selectedIds.has(patch.id)}
              onSelect={() => toggleSelect(patch.id)}
              docId={docId}
              onRefresh={() => onRefresh?.()}
            />
          ))
        )}
      </div>
    </div>
  );
}

function CorrectionCard({
  patch,
  index,
  isExpanded,
  onToggle,
  isReviewMode,
  isSelected,
  onSelect,
  docId,
  onRefresh,
}: {
  patch: PatchListItem;
  index: number;
  isExpanded: boolean;
  onToggle: () => void;
  isReviewMode: boolean;
  isSelected: boolean;
  onSelect: () => void;
  docId: string;
  onRefresh: () => void;
}) {
  // Simple word-level diff
  const diffWords = useMemo(() => {
    const origWords = patch.original_text.split(/(\s+)/);
    const corrWords = patch.corrected_text.split(/(\s+)/);

    const maxLen = Math.max(origWords.length, corrWords.length);
    const origDiff: { text: string; changed: boolean }[] = [];
    const corrDiff: { text: string; changed: boolean }[] = [];

    for (let i = 0; i < maxLen; i++) {
      const ow = origWords[i] || "";
      const cw = corrWords[i] || "";
      const changed = ow !== cw;
      if (ow) origDiff.push({ text: ow, changed });
      if (cw) corrDiff.push({ text: cw, changed });
    }

    return { origDiff, corrDiff };
  }, [patch.original_text, patch.corrected_text]);

  return (
    <div
      className={`
        bg-surface-elevated border rounded-xl transition-all duration-300 overflow-hidden cursor-pointer
        ${isExpanded ? "border-krypton/40 shadow-[0_0_20px_rgba(212,255,0,0.05)]" : "border-border hover:border-carbon-200"}
      `}
      onClick={onToggle}
    >
      {/* Header */}
      <div className="px-4 py-3 flex items-center justify-between gap-3">
        <div className="flex items-center gap-3 min-w-0">
          {isReviewMode && (
            <input
              type="checkbox"
              checked={isSelected}
              onChange={(e) => { e.stopPropagation(); onSelect(); }}
              className="w-4 h-4 rounded border-border bg-surface text-krypton focus:ring-krypton/30 cursor-pointer flex-shrink-0"
            />
          )}
          <span className="text-xs font-mono text-plomo w-6 text-right flex-shrink-0">
            #{index}
          </span>
          <span
            className={`
              inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] uppercase tracking-wider font-semibold flex-shrink-0
              ${patch.source === "languagetool"
                ? "bg-blue-900/30 text-blue-400"
                : "bg-purple-900/30 text-purple-400"
              }
            `}
          >
            {patch.source === "languagetool" ? "LT" : "LLM"}
          </span>
          <span className="text-sm text-plomo truncate">
            Bloque #{patch.block_no || "?"}
          </span>
          {patch.category && (
            <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium flex-shrink-0 ${CATEGORY_COLORS[patch.category]?.bg || "bg-surface"} ${CATEGORY_COLORS[patch.category]?.text || "text-plomo"}`}>
              {patch.category}
            </span>
          )}
          {patch.severity && (
            <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium flex-shrink-0 ${SEVERITY_COLORS[patch.severity]?.bg || "bg-surface"} ${SEVERITY_COLORS[patch.severity]?.text || "text-plomo"}`}>
              {patch.severity}
            </span>
          )}
          {patch.route_taken && ROUTE_COLORS[patch.route_taken] && (
            <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium flex-shrink-0 ${ROUTE_COLORS[patch.route_taken].bg} ${ROUTE_COLORS[patch.route_taken].text}`}>
              {ROUTE_COLORS[patch.route_taken].label}
            </span>
          )}
          {patch.overflow_flag && (
            <span className="inline-flex items-center px-1.5 py-0.5 rounded bg-yellow-900/30 text-yellow-500 text-[10px] font-medium flex-shrink-0">
              OVERFLOW
            </span>
          )}
          {patch.cost_usd != null && patch.cost_usd > 0 && (
            <span className="inline-flex items-center px-1.5 py-0.5 rounded bg-emerald-900/20 text-emerald-400 text-[10px] font-medium flex-shrink-0">
              ${patch.cost_usd < 0.001 ? patch.cost_usd.toFixed(6) : patch.cost_usd.toFixed(4)}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          <ReviewStatusBadge status={patch.review_status} />
          <svg
            className={`w-4 h-4 text-plomo transition-transform duration-200 ${isExpanded ? "rotate-180" : ""}`}
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2}
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 8.25l-7.5 7.5-7.5-7.5" />
          </svg>
        </div>
      </div>

      {/* Expanded content */}
      {isExpanded && (
        <div className="px-4 pb-4 space-y-3" onClick={(e) => e.stopPropagation()}>
          <div className="h-px bg-carbon-300" />

          {/* Diff view */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {/* Original */}
            <div>
              <div className="flex items-center gap-2 mb-2">
                <div className="w-2 h-2 rounded-full bg-red-500" />
                <span className="text-[10px] uppercase tracking-wider font-semibold text-plomo">Original</span>
              </div>
              <div className="bg-surface rounded-lg px-3 py-2.5 text-sm leading-relaxed whitespace-pre-wrap break-words border border-border">
                {diffWords.origDiff.map((w, i) => (
                  <span
                    key={i}
                    className={w.changed ? "bg-red-900/40 text-red-300 rounded px-0.5" : "text-bruma/80"}
                  >
                    {w.text}
                  </span>
                ))}
              </div>
            </div>

            {/* Corrected */}
            <div>
              <div className="flex items-center gap-2 mb-2">
                <div className="w-2 h-2 rounded-full bg-krypton" />
                <span className="text-[10px] uppercase tracking-wider font-semibold text-plomo">Corregido</span>
              </div>
              <div className="bg-surface rounded-lg px-3 py-2.5 text-sm leading-relaxed whitespace-pre-wrap break-words border border-krypton/20">
                {diffWords.corrDiff.map((w, i) => (
                  <span
                    key={i}
                    className={w.changed ? "bg-krypton/20 text-krypton rounded px-0.5" : "text-bruma/80"}
                  >
                    {w.text}
                  </span>
                ))}
              </div>
            </div>
          </div>

          {/* Explanation (MVP2) */}
          {patch.explanation && (
            <div className="bg-surface/50 border border-border rounded-lg px-3 py-2">
              <div className="text-[10px] uppercase tracking-wider font-semibold text-plomo mb-1">Explicación</div>
              <p className="text-sm text-bruma/80">{patch.explanation}</p>
            </div>
          )}

          {/* Quality indicators (Lote 5) */}
          {(patch.rewrite_ratio != null || patch.confidence != null) && (
            <div className="bg-surface/50 border border-border rounded-lg px-3 py-2 space-y-2">
              <div className="text-[10px] uppercase tracking-wider font-semibold text-plomo">Control de calidad</div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {patch.rewrite_ratio != null && (
                  <div>
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-[11px] text-plomo">Reescritura</span>
                      <span className={`text-[11px] font-mono ${patch.rewrite_ratio > 0.35 ? "text-red-400" : patch.rewrite_ratio > 0.2 ? "text-yellow-400" : "text-krypton/70"}`}>
                        {Math.round(patch.rewrite_ratio * 100)}%
                      </span>
                    </div>
                    <div className="h-1.5 bg-carbon-300 rounded-full overflow-hidden">
                      <div
                        className={`h-full rounded-full transition-all ${patch.rewrite_ratio > 0.35 ? "bg-red-400" : patch.rewrite_ratio > 0.2 ? "bg-yellow-400" : "bg-krypton/60"}`}
                        style={{ width: `${Math.min(patch.rewrite_ratio * 100, 100)}%` }}
                      />
                    </div>
                  </div>
                )}
                {patch.confidence != null && (
                  <div>
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-[11px] text-plomo">Confianza</span>
                      <span className={`text-[11px] font-mono ${patch.confidence >= 0.8 ? "text-krypton/70" : patch.confidence >= 0.5 ? "text-yellow-400" : "text-red-400"}`}>
                        {Math.round(patch.confidence * 100)}%
                      </span>
                    </div>
                    <div className="h-1.5 bg-carbon-300 rounded-full overflow-hidden">
                      <div
                        className={`h-full rounded-full transition-all ${patch.confidence >= 0.8 ? "bg-krypton/60" : patch.confidence >= 0.5 ? "bg-yellow-400" : "bg-red-400"}`}
                        style={{ width: `${Math.min(patch.confidence * 100, 100)}%` }}
                      />
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Review reason (Lote 5) */}
          {patch.review_reason && (
            <div className={`border rounded-lg px-3 py-2 ${patch.review_status === "gate_rejected" ? "bg-red-900/10 border-red-900/30" : "bg-orange-900/10 border-orange-900/30"}`}>
              <div className={`text-[10px] uppercase tracking-wider font-semibold mb-1 ${patch.review_status === "gate_rejected" ? "text-red-400" : "text-orange-400"}`}>
                {patch.review_status === "gate_rejected" ? "Gate rechazó corrección" : "Requiere revisión manual"}
              </div>
              <p className="text-sm text-bruma/70">{patch.review_reason}</p>
            </div>
          )}

          {/* Gate details (Lote 5) */}
          {patch.gate_results && patch.gate_results.length > 0 && (
            <div className="bg-surface/30 border border-border rounded-lg px-3 py-2">
              <div className="text-[10px] uppercase tracking-wider font-semibold text-plomo mb-1.5">Gates de calidad</div>
              <div className="flex flex-wrap gap-1.5">
                {patch.gate_results.map((g, i) => (
                  <span
                    key={i}
                    className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium ${g.passed ? "bg-emerald-900/20 text-emerald-400" : g.critical ? "bg-red-900/20 text-red-400" : "bg-orange-900/20 text-orange-400"}`}
                    title={g.message || `${g.gate_name}: ${g.value} / ${g.threshold}`}
                  >
                    {g.passed ? "✓" : "✕"} {g.gate_name.replace(/_/g, " ")}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Metadata */}
          <div className="flex items-center gap-4 text-[11px] text-plomo pt-1 flex-wrap">
            <span>Versión {patch.version}</span>
            <span>·</span>
            <span>
              {new Date(patch.created_at).toLocaleDateString("es", {
                day: "numeric",
                month: "short",
                hour: "2-digit",
                minute: "2-digit",
              })}
            </span>
            {patch.confidence != null && (
              <>
                <span>·</span>
                <span className={patch.confidence >= 0.8 ? "text-krypton/70" : patch.confidence >= 0.5 ? "text-yellow-500/70" : "text-red-400/70"}>
                  Confianza: {Math.round(patch.confidence * 100)}%
                </span>
              </>
            )}
            {patch.model_used && (
              <>
                <span>·</span>
                <span>{patch.model_used}</span>
              </>
            )}
            {patch.cost_usd != null && patch.cost_usd > 0 && (
              <>
                <span>·</span>
                <span className="text-emerald-400/70">
                  Costo: ${patch.cost_usd < 0.001 ? patch.cost_usd.toFixed(6) : patch.cost_usd.toFixed(4)}
                </span>
              </>
            )}
          </div>

          {/* Review actions — unified CorrectionActionPanel */}
          {isReviewMode && (
            <div className="pt-2 border-t border-border mt-2" onClick={(e) => e.stopPropagation()}>
              <CorrectionActionPanel
                docId={docId}
                patch={patch}
                isReviewMode={isReviewMode}
                onActionComplete={onRefresh}
                compact={true}
              />
            </div>
          )}
        </div>
      )}
    </div>
  );
}
