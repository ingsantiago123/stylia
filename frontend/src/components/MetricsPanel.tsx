"use client";

/**
 * MetricsPanel — Fase 7 (observabilidad).
 *
 * Muestra las métricas operativas reales del documento:
 * - Patches: total, aplicados DE VERDAD en el render (H4), aprobados que el
 *   render NO pudo aplicar (mismatch/no_paragraph — antes invisibles), y
 *   desglose por ruta de corrección.
 * - LLM: costo/tokens por tipo de llamada.
 * - Pipeline runs (Fase 4): checkpoints completados, reintentos, costo por
 *   run y kill-switch de costo.
 */

import { useEffect, useState } from "react";
import { getDocumentMetrics, DocumentMetrics } from "@/lib/api";

const ROUTE_LABELS: Record<string, string> = {
  skip: "Omitido",
  cheap: "Rápida",
  editorial: "Editorial",
  group_list: "Grupo lista",
  group_table: "Grupo tabla",
  desconocida: "Sin ruta",
};

const RUN_STATUS_STYLE: Record<string, string> = {
  completed: "bg-emerald-500/15 text-emerald-400",
  running: "bg-krypton/10 text-krypton",
  failed: "bg-red-500/15 text-red-400",
  cost_limit: "bg-orange-500/15 text-orange-400",
};

const RUN_STATUS_LABEL: Record<string, string> = {
  completed: "Completado",
  running: "En curso",
  failed: "Fallido",
  cost_limit: "Tope de costo",
};

export function MetricsPanel({ docId }: { docId: string }) {
  const [metrics, setMetrics] = useState<DocumentMetrics | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getDocumentMetrics(docId)
      .then((m) => {
        if (!cancelled) setMetrics(m);
      })
      .catch((e) => {
        if (!cancelled) setError(e instanceof Error ? e.message : "Error");
      });
    return () => {
      cancelled = true;
    };
  }, [docId]);

  if (error) return null;
  if (!metrics) return null;

  const { patches, llm, pipeline_runs } = metrics;
  const appliedPct =
    patches.total > 0 ? Math.round((patches.applied / patches.total) * 100) : 0;
  const routeEntries = Object.entries(patches.by_route).sort(([, a], [, b]) => b - a);

  return (
    <div className="glass-card rounded-xl p-5 md:col-span-2">
      <h3 className="text-sm font-semibold text-bruma uppercase tracking-wider mb-4">
        Métricas del pipeline
      </h3>

      {/* Fila 1: veracidad de aplicación (H4) */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-4">
        <div className="bg-surface rounded-lg p-3 text-center border border-border-subtle">
          <div className="text-[10px] text-plomo-dark uppercase tracking-wider mb-1">Patches</div>
          <div className="text-lg font-bold text-bruma">{patches.total}</div>
        </div>
        <div className="bg-surface rounded-lg p-3 text-center border border-border-subtle">
          <div className="text-[10px] text-plomo-dark uppercase tracking-wider mb-1">
            Aplicados (real)
          </div>
          <div className="text-lg font-bold text-krypton">
            {patches.applied}
            {patches.total > 0 && (
              <span className="text-[10px] text-plomo ml-1">({appliedPct}%)</span>
            )}
          </div>
        </div>
        <div className="bg-surface rounded-lg p-3 text-center border border-border-subtle">
          <div className="text-[10px] text-plomo-dark uppercase tracking-wider mb-1">
            Aprobados sin aplicar
          </div>
          <div
            className={`text-lg font-bold ${
              patches.approved_not_applied > 0 ? "text-orange-400" : "text-bruma"
            }`}
            title="Aprobados que el render no pudo aplicar (mismatch / párrafo no encontrado)"
          >
            {patches.approved_not_applied}
          </div>
        </div>
        <div className="bg-surface rounded-lg p-3 text-center border border-border-subtle">
          <div className="text-[10px] text-plomo-dark uppercase tracking-wider mb-1">
            Grupales (listas/tablas)
          </div>
          <div className="text-lg font-bold text-bruma">{patches.group_patches}</div>
        </div>
      </div>

      {/* Fila 2: rutas de corrección + costo LLM por tipo de llamada */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {routeEntries.length > 0 && (
          <div>
            <span className="text-[10px] text-plomo-dark uppercase tracking-wider block mb-2">
              Por ruta de corrección
            </span>
            <div className="space-y-1.5">
              {routeEntries.map(([route, count]) => (
                <div key={route} className="flex items-center justify-between text-sm">
                  <span className="text-plomo">{ROUTE_LABELS[route] || route}</span>
                  <span className="text-bruma font-medium">{count}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {llm.by_call_type.length > 0 && (
          <div>
            <span className="text-[10px] text-plomo-dark uppercase tracking-wider block mb-2">
              Costo LLM por tipo de llamada
            </span>
            <div className="space-y-1.5">
              {llm.by_call_type.map((ct) => (
                <div key={ct.call_type} className="flex items-center justify-between text-sm">
                  <span className="text-plomo">
                    {ct.call_type}
                    <span className="text-plomo-dark text-xs ml-1.5">×{ct.calls}</span>
                  </span>
                  <span className="text-bruma font-mono text-xs">
                    ${ct.cost_usd < 0.01 ? ct.cost_usd.toFixed(6) : ct.cost_usd.toFixed(4)}
                  </span>
                </div>
              ))}
              <div className="flex items-center justify-between text-sm pt-1.5 border-t border-border-subtle">
                <span className="text-bruma font-medium">Total</span>
                <span className="text-krypton font-mono text-xs font-semibold">
                  $
                  {llm.total_cost_usd < 0.01
                    ? llm.total_cost_usd.toFixed(6)
                    : llm.total_cost_usd.toFixed(4)}{" "}
                  USD
                </span>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Fila 3: runs del pipeline (Fase 4) */}
      {pipeline_runs.length > 0 && (
        <div className="mt-4 pt-4 border-t border-border-subtle">
          <span className="text-[10px] text-plomo-dark uppercase tracking-wider block mb-2">
            Ejecuciones del pipeline (checkpoints Fase 4)
          </span>
          <div className="space-y-2">
            {pipeline_runs.map((run) => (
              <div
                key={run.run_no}
                className="flex items-center gap-3 bg-surface rounded-lg px-3 py-2 border border-border-subtle text-sm"
              >
                <span className="text-plomo font-mono text-xs shrink-0">#{run.run_no}</span>
                <span
                  className={`px-2 py-0.5 rounded text-[10px] font-medium shrink-0 ${
                    RUN_STATUS_STYLE[run.status] || "bg-surface-hover text-plomo"
                  }`}
                >
                  {RUN_STATUS_LABEL[run.status] || run.status}
                </span>
                <span className="text-plomo-dark text-xs flex-1 truncate">
                  {run.stages_done.length > 0
                    ? `Etapas: ${run.stages_done.join(" → ")}`
                    : "Sin checkpoints"}
                  {run.retries > 0 && ` · ${run.retries} reintento(s)`}
                </span>
                <span className="text-bruma font-mono text-xs shrink-0">
                  ${run.cost_usd < 0.01 ? run.cost_usd.toFixed(6) : run.cost_usd.toFixed(4)}
                </span>
              </div>
            ))}
          </div>
          {pipeline_runs.some((r) => r.error_message) && (
            <p className="text-xs text-red-400/80 mt-2">
              {pipeline_runs.find((r) => r.error_message)?.error_message}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
