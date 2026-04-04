"use client";

import { useState, useMemo, useEffect, useCallback } from "react";
import {
  PatchListItem,
  PageAnnotation,
  getPagePreviewUrl,
  getCorrectedPagePreviewUrl,
  getPageAnnotations,
} from "@/lib/api";

// =============================================
// Types
// =============================================

interface DiffCompareViewProps {
  corrections: PatchListItem[];
  totalPages: number | null;
  docId: string;
  docStatus: string;
}

interface TooltipData {
  x: number;
  y: number;
  category: string;
  severity: string | null;
  explanation: string | null;
  confidence: number | null;
  source: string;
  original_snippet: string;
  corrected_snippet: string;
  cost_usd: number | null;
}

// =============================================
// Constants
// =============================================

const CATEGORY_COLORS: Record<string, { bg: string; text: string; border: string }> = {
  redundancia: { bg: "bg-orange-900/40", text: "text-orange-300", border: "border-orange-400/60" },
  claridad:    { bg: "bg-blue-900/40",   text: "text-blue-300",   border: "border-blue-400/60" },
  registro:    { bg: "bg-indigo-900/40",  text: "text-indigo-300", border: "border-indigo-400/60" },
  cohesion:    { bg: "bg-cyan-900/40",    text: "text-cyan-300",   border: "border-cyan-400/60" },
  lexico:      { bg: "bg-teal-900/40",    text: "text-teal-300",   border: "border-teal-400/60" },
  estructura:  { bg: "bg-violet-900/40",  text: "text-violet-300", border: "border-violet-400/60" },
  puntuacion:  { bg: "bg-amber-900/40",   text: "text-amber-300",  border: "border-amber-400/60" },
  ritmo:       { bg: "bg-pink-900/40",    text: "text-pink-300",   border: "border-pink-400/60" },
  muletilla:   { bg: "bg-rose-900/40",    text: "text-rose-300",   border: "border-rose-400/60" },
};

const SEVERITY_LABELS: Record<string, { label: string; color: string }> = {
  critico:     { label: "Critico",     color: "bg-red-900/50 text-red-300" },
  importante:  { label: "Importante",  color: "bg-yellow-900/50 text-yellow-300" },
  sugerencia:  { label: "Sugerencia",  color: "bg-emerald-900/50 text-emerald-300" },
};

// =============================================
// Page number buttons (smart windowing)
// =============================================

function getPageNumbers(current: number, total: number): (number | "...")[] {
  if (total <= 10) return Array.from({ length: total }, (_, i) => i + 1);

  const pages: (number | "...")[] = [1];
  const rangeStart = Math.max(2, current - 2);
  const rangeEnd = Math.min(total - 1, current + 2);

  if (rangeStart > 2) pages.push("...");
  for (let p = rangeStart; p <= rangeEnd; p++) pages.push(p);
  if (rangeEnd < total - 1) pages.push("...");
  if (total > 1) pages.push(total);

  return pages;
}

// =============================================
// Main Component
// =============================================

export function DiffCompareView({ corrections, totalPages, docId, docStatus }: DiffCompareViewProps) {
  const [currentPage, setCurrentPage] = useState(1);
  const [tooltip, setTooltip] = useState<TooltipData | null>(null);
  const [annotations, setAnnotations] = useState<PageAnnotation[]>([]);

  // Image loading states
  const [leftLoaded, setLeftLoaded] = useState(false);
  const [rightLoaded, setRightLoaded] = useState(false);
  const [leftError, setLeftError] = useState(false);
  const [rightError, setRightError] = useState(false);

  const maxPage = totalPages || 1;
  const isCompleted = docStatus === "completed";
  const pageNumbers = useMemo(() => getPageNumbers(currentPage, maxPage), [currentPage, maxPage]);

  // Reset states when page changes
  useEffect(() => {
    setLeftLoaded(false);
    setRightLoaded(false);
    setLeftError(false);
    setRightError(false);
    setAnnotations([]);
    setTooltip(null);
  }, [currentPage]);

  // Fetch annotations for current page
  useEffect(() => {
    if (!isCompleted) return;
    getPageAnnotations(docId, currentPage).then(setAnnotations).catch(() => setAnnotations([]));
  }, [docId, currentPage, isCompleted]);

  const handleAnnotationHover = useCallback((e: React.MouseEvent, ann: PageAnnotation) => {
    const rect = (e.currentTarget as HTMLElement).getBoundingClientRect();
    // Match annotation to correction to get cost
    const match = corrections.find(
      (c) => c.original_text === ann.original_snippet && c.corrected_text === ann.corrected_snippet
    );
    setTooltip({
      x: rect.left + rect.width / 2,
      y: rect.top - 8,
      category: ann.category,
      severity: ann.severity,
      explanation: ann.explanation,
      confidence: ann.confidence,
      source: ann.source,
      original_snippet: ann.original_snippet,
      corrected_snippet: ann.corrected_snippet,
      cost_usd: match?.cost_usd ?? null,
    });
  }, [corrections]);

  const handleAnnotationLeave = useCallback(() => {
    setTooltip(null);
  }, []);

  // Stats
  const correctionStats = useMemo(() => {
    const cats: Record<string, number> = {};
    for (const c of corrections) {
      if (c.category) cats[c.category] = (cats[c.category] || 0) + 1;
    }
    return { total: corrections.length, categories: cats };
  }, [corrections]);

  // No pages
  if (!totalPages || totalPages === 0) {
    return (
      <div className="glass-card rounded-xl p-12 text-center">
        <div className="w-16 h-16 mx-auto mb-4 rounded-2xl bg-surface flex items-center justify-center">
          <svg className="w-7 h-7 text-plomo" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
          </svg>
        </div>
        <p className="text-bruma font-medium">Sin paginas disponibles</p>
        <p className="text-plomo text-sm mt-1">El documento aun no tiene paginas extraidas</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* ============================================= */}
      {/* PAGE NAVIGATOR                                */}
      {/* ============================================= */}
      <div className="glass-card rounded-xl p-4">
        <div className="flex items-center justify-between flex-wrap gap-3">
          {/* Prev / page buttons / Next */}
          <div className="flex items-center gap-2">
            <button
              onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
              disabled={currentPage === 1}
              className="w-8 h-8 flex items-center justify-center rounded-lg bg-surface text-plomo hover:text-bruma hover:bg-carbon-300 disabled:opacity-30 disabled:cursor-not-allowed transition-all"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 19.5L8.25 12l7.5-7.5" />
              </svg>
            </button>

            <div className="flex items-center gap-1">
              {pageNumbers.map((p, idx) =>
                p === "..." ? (
                  <span key={`e-${idx}`} className="w-8 h-8 flex items-center justify-center text-xs text-plomo">...</span>
                ) : (
                  <button
                    key={p}
                    onClick={() => setCurrentPage(p)}
                    className={`w-8 h-8 flex items-center justify-center rounded-lg text-xs font-semibold transition-all ${
                      currentPage === p
                        ? "bg-krypton text-carbon shadow-[0_0_10px_rgba(212,255,0,0.2)]"
                        : "bg-surface text-plomo hover:text-bruma hover:bg-carbon-300"
                    }`}
                  >
                    {p}
                  </button>
                )
              )}
            </div>

            <button
              onClick={() => setCurrentPage((p) => Math.min(maxPage, p + 1))}
              disabled={currentPage === maxPage}
              className="w-8 h-8 flex items-center justify-center rounded-lg bg-surface text-plomo hover:text-bruma hover:bg-carbon-300 disabled:opacity-30 disabled:cursor-not-allowed transition-all"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" />
              </svg>
            </button>

            <span className="text-xs text-plomo ml-2">
              Pagina {currentPage} de {maxPage}
            </span>
          </div>

          {/* Status + stats */}
          <div className="flex items-center gap-3 text-xs">
            {correctionStats.total > 0 && (
              <span className="text-plomo">
                <span className="text-krypton font-semibold">{correctionStats.total}</span> correcciones
              </span>
            )}
            {(() => {
              const totalCost = corrections.reduce((sum, c) => sum + (c.cost_usd || 0), 0);
              return totalCost > 0 ? (
                <span className="text-emerald-400 font-mono">
                  ${totalCost < 0.01 ? totalCost.toFixed(6) : totalCost.toFixed(4)}
                </span>
              ) : null;
            })()}
            {Object.entries(correctionStats.categories).length > 0 && (
              <div className="flex items-center gap-1">
                {Object.entries(correctionStats.categories)
                  .sort(([, a], [, b]) => b - a)
                  .slice(0, 4)
                  .map(([cat, count]) => {
                    const cc = CATEGORY_COLORS[cat];
                    return (
                      <span
                        key={cat}
                        className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium ${cc?.bg || "bg-surface"} ${cc?.text || "text-plomo"}`}
                      >
                        {cat} {count}
                      </span>
                    );
                  })}
              </div>
            )}
            {isCompleted ? (
              <span className="inline-flex items-center gap-1.5 px-2 py-1 rounded-lg bg-krypton/10 text-krypton font-medium">
                <span className="w-1.5 h-1.5 rounded-full bg-krypton" />
                Completado
              </span>
            ) : (
              <span className="inline-flex items-center gap-1.5 px-2 py-1 rounded-lg bg-yellow-900/20 text-yellow-400 font-medium">
                <span className="w-1.5 h-1.5 rounded-full bg-yellow-400 animate-pulse" />
                Procesando
              </span>
            )}
          </div>
        </div>

        {/* Column headers */}
        <div className="grid grid-cols-2 gap-4 mt-4 pt-3 border-t border-border">
          <div className="flex items-center gap-2">
            <div className="w-2.5 h-2.5 rounded-full bg-plomo/50" />
            <span className="text-xs uppercase tracking-wider font-semibold text-plomo">Original</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-2.5 h-2.5 rounded-full bg-krypton" />
            <span className="text-xs uppercase tracking-wider font-semibold text-plomo">Corregido</span>
            {annotations.length > 0 && (
              <span className="text-[10px] text-plomo/60">— {annotations.length} marcas en esta pagina</span>
            )}
          </div>
        </div>
      </div>

      {/* ============================================= */}
      {/* SIDE-BY-SIDE PAGE IMAGES                      */}
      {/* ============================================= */}
      <div className="grid grid-cols-2 gap-4">
        {/* LEFT: Original page */}
        <div className="glass-card rounded-xl overflow-hidden">
          <div className="max-h-[80vh] overflow-auto">
            {!leftLoaded && !leftError && <ImageSkeleton />}
            {leftError ? (
              <ImagePlaceholder text="Preview no disponible" />
            ) : (
              <img
                src={getPagePreviewUrl(docId, currentPage)}
                alt={`Pagina ${currentPage} original`}
                className={`w-full h-auto ${leftLoaded ? "block" : "hidden"}`}
                onLoad={() => setLeftLoaded(true)}
                onError={() => { setLeftError(true); setLeftLoaded(true); }}
              />
            )}
          </div>
        </div>

        {/* RIGHT: Corrected page with annotation overlays */}
        <div className="glass-card rounded-xl overflow-hidden">
          <div className="max-h-[80vh] overflow-auto">
            {isCompleted ? (
              <>
                {!rightLoaded && !rightError && <ImageSkeleton />}
                {rightError ? (
                  <ImagePlaceholder text="Preview corregido no disponible" sub="Re-procesa el documento para generarlo" />
                ) : (
                  <div className="relative">
                    <img
                      src={getCorrectedPagePreviewUrl(docId, currentPage)}
                      alt={`Pagina ${currentPage} corregida`}
                      className={`w-full h-auto ${rightLoaded ? "block" : "hidden"}`}
                      onLoad={() => setRightLoaded(true)}
                      onError={() => { setRightError(true); setRightLoaded(true); }}
                    />
                    {/* Invisible hover overlays on annotation positions */}
                    {rightLoaded && annotations.map((ann, i) => (
                      <div
                        key={i}
                        className="absolute cursor-pointer transition-all hover:bg-white/10"
                        style={{
                          left: `${ann.x_pct}%`,
                          top: `${ann.y_pct}%`,
                          width: `${ann.w_pct}%`,
                          height: `${ann.h_pct}%`,
                        }}
                        onMouseEnter={(e) => handleAnnotationHover(e, ann)}
                        onMouseLeave={handleAnnotationLeave}
                      />
                    ))}
                  </div>
                )}
              </>
            ) : (
              <div className="flex items-center justify-center h-96 bg-surface/20">
                <div className="text-center">
                  <svg className="w-12 h-12 mx-auto text-yellow-400/40 mb-3 animate-pulse" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  <p className="text-sm text-plomo font-medium">Documento en proceso</p>
                  <p className="text-xs text-plomo/60 mt-1">La version corregida estara disponible al completar</p>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Floating tooltip */}
      {tooltip && <AnnotationTooltip data={tooltip} />}
    </div>
  );
}

// =============================================
// Sub-components
// =============================================

function ImageSkeleton() {
  return (
    <div className="flex items-center justify-center h-96 bg-surface/30 animate-pulse">
      <div className="text-center">
        <svg className="w-10 h-10 mx-auto text-plomo/40 mb-2 animate-spin" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182M2.985 19.644l3.181 3.182" />
        </svg>
        <p className="text-xs text-plomo">Cargando pagina...</p>
      </div>
    </div>
  );
}

function ImagePlaceholder({ text, sub }: { text: string; sub?: string }) {
  return (
    <div className="flex items-center justify-center h-96 bg-surface/20">
      <div className="text-center">
        <svg className="w-10 h-10 mx-auto text-plomo/40 mb-2" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 15.75l5.159-5.159a2.25 2.25 0 013.182 0l5.159 5.159m-1.5-1.5l1.409-1.41a2.25 2.25 0 013.182 0l2.909 2.91M3.75 21h16.5a1.5 1.5 0 001.5-1.5V5.25a1.5 1.5 0 00-1.5-1.5H3.75a1.5 1.5 0 00-1.5 1.5v14.25a1.5 1.5 0 001.5 1.5z" />
        </svg>
        <p className="text-xs text-plomo">{text}</p>
        {sub && <p className="text-[10px] text-plomo/60 mt-1">{sub}</p>}
      </div>
    </div>
  );
}

function AnnotationTooltip({ data }: { data: TooltipData }) {
  const catColor = CATEGORY_COLORS[data.category];
  const sevLabel = data.severity ? SEVERITY_LABELS[data.severity] : null;

  return (
    <div
      className="fixed z-50 pointer-events-none"
      style={{
        left: `${data.x}px`,
        top: `${data.y}px`,
        transform: "translate(-50%, -100%)",
      }}
    >
      <div className="glass-card rounded-lg shadow-2xl shadow-black/50 px-3 py-2.5 max-w-sm">
        {/* Category + Severity + Confidence */}
        <div className="flex items-center gap-1.5 mb-2">
          {data.category && (
            <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold ${catColor?.bg || "bg-surface"} ${catColor?.text || "text-plomo"}`}>
              {data.category}
            </span>
          )}
          {data.severity && sevLabel && (
            <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold ${sevLabel.color}`}>
              {sevLabel.label}
            </span>
          )}
          <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold ${
            data.source === "languagetool" ? "bg-blue-900/30 text-blue-400" : "bg-purple-900/30 text-purple-400"
          }`}>
            {data.source === "languagetool" ? "LT" : "LLM"}
          </span>
          {data.confidence != null && (
            <span className={`text-[10px] font-medium ml-auto ${
              data.confidence >= 0.8 ? "text-krypton" : data.confidence >= 0.5 ? "text-yellow-400" : "text-red-400"
            }`}>
              {Math.round(data.confidence * 100)}%
            </span>
          )}
        </div>

        {/* Explanation */}
        {data.explanation ? (
          <p className="text-xs text-bruma/80 leading-relaxed mb-2">{data.explanation}</p>
        ) : (
          <p className="text-xs text-plomo italic mb-2">
            {data.source === "languagetool" ? "Correccion ortografica/gramatical" : "Mejora de estilo"}
          </p>
        )}

        {/* Original → Corrected snippet */}
        <div className="border-t border-border/50 pt-2 space-y-1">
          <div className="flex items-start gap-2">
            <span className="text-[10px] text-red-400 font-semibold shrink-0 mt-0.5">ANT</span>
            <p className="text-[11px] text-red-300/70 line-through leading-snug">{data.original_snippet}</p>
          </div>
          <div className="flex items-start gap-2">
            <span className="text-[10px] text-krypton font-semibold shrink-0 mt-0.5">NUE</span>
            <p className="text-[11px] text-krypton/80 leading-snug">{data.corrected_snippet}</p>
          </div>
        </div>

        {/* Cost */}
        {data.cost_usd != null && data.cost_usd > 0 && (
          <div className="border-t border-border/50 pt-1.5 mt-1.5 flex items-center justify-end">
            <span className="text-[10px] text-emerald-400 font-mono">
              Costo: ${data.cost_usd < 0.001 ? data.cost_usd.toFixed(6) : data.cost_usd.toFixed(4)}
            </span>
          </div>
        )}

        {/* Arrow */}
        <div className="absolute left-1/2 -translate-x-1/2 -bottom-1 w-2 h-2 bg-surface-elevated border-r border-b border-border rotate-45" />
      </div>
    </div>
  );
}
