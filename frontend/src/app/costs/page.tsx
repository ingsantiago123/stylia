"use client";

import { useEffect, useState, useMemo } from "react";
import {
  getCostSummary,
  getCostDocuments,
  getDocumentCosts,
  CostSummary,
  DocumentCostItem,
  ParagraphCostItem,
} from "@/lib/api";

// =============================================
// Helpers
// =============================================

function formatCost(usd: number): string {
  if (usd === 0) return "$0.00";
  if (usd < 0.01) return `$${usd.toFixed(6)}`;
  return `$${usd.toFixed(4)}`;
}

function formatTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return n.toLocaleString("es");
}

function formatTokensFull(n: number): string {
  return n.toLocaleString("es");
}

function pct(part: number, total: number): number {
  if (total === 0) return 0;
  return Math.round((part / total) * 100);
}

// =============================================
// Main Page
// =============================================

export default function CostsPage() {
  const [summary, setSummary] = useState<CostSummary | null>(null);
  const [documents, setDocuments] = useState<DocumentCostItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedDoc, setExpandedDoc] = useState<string | null>(null);
  const [paragraphCosts, setParagraphCosts] = useState<Record<string, ParagraphCostItem[]>>({});

  useEffect(() => {
    async function fetchData() {
      try {
        const [s, d] = await Promise.all([
          getCostSummary(),
          getCostDocuments(),
        ]);
        setSummary(s);
        setDocuments(d);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Error cargando datos");
      } finally {
        setLoading(false);
      }
    }
    fetchData();
  }, []);

  const maxDocCost = useMemo(() => {
    if (documents.length === 0) return 0;
    return Math.max(...documents.map((d) => d.total_cost_usd));
  }, [documents]);

  async function toggleExpand(docId: string) {
    if (expandedDoc === docId) {
      setExpandedDoc(null);
      return;
    }
    setExpandedDoc(docId);
    if (!paragraphCosts[docId]) {
      try {
        const costs = await getDocumentCosts(docId);
        setParagraphCosts((prev) => ({ ...prev, [docId]: costs }));
      } catch {
        setParagraphCosts((prev) => ({ ...prev, [docId]: [] }));
      }
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-32">
        <div className="flex flex-col items-center gap-4">
          <div className="relative">
            <div className="w-12 h-12 rounded-full border-2 border-carbon-50 border-t-krypton animate-spin" />
            <div className="absolute inset-0 w-12 h-12 rounded-full border-2 border-transparent border-t-krypton/30 animate-spin" style={{ animationDuration: "1.5s", animationDirection: "reverse" }} />
          </div>
          <span className="text-sm text-plomo">Cargando panel de costos...</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center py-24 gap-4">
        <div className="w-16 h-16 rounded-2xl bg-red-900/20 border border-red-500/30 flex items-center justify-center">
          <svg className="w-7 h-7 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
          </svg>
        </div>
        <p className="text-red-400 text-sm">{error}</p>
        <a href="/" className="text-krypton hover:text-krypton/80 text-xs transition-colors">
          ← Volver al inicio
        </a>
      </div>
    );
  }

  return (
    <div className="space-y-6 pb-8">
      {/* ============================================= */}
      {/* HEADER                                        */}
      {/* ============================================= */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <div className="w-10 h-10 rounded-xl bg-krypton/10 border border-krypton/20 flex items-center justify-center">
            <svg className="w-5 h-5 text-krypton" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 18.75a60.07 60.07 0 0115.797 2.101c.727.198 1.453-.342 1.453-1.096V18.75M3.75 4.5v.75A.75.75 0 013 6h-.75m0 0v-.375c0-.621.504-1.125 1.125-1.125H20.25M2.25 6v9m18-10.5v.75c0 .414.336.75.75.75h.75m-1.5-1.5h.375c.621 0 1.125.504 1.125 1.125v9.75c0 .621-.504 1.125-1.125 1.125h-.375m1.5-1.5H21a.75.75 0 00-.75.75v.75m0 0H3.75m0 0h-.375a1.125 1.125 0 01-1.125-1.125V15m1.5 1.5v-.75A.75.75 0 003 15h-.75M15 10.5a3 3 0 11-6 0 3 3 0 016 0zm3 0h.008v.008H18V10.5zm-12 0h.008v.008H6V10.5z" />
            </svg>
          </div>
          <div>
            <h1 className="text-xl font-bold text-bruma tracking-tight">Centro de costos</h1>
            <p className="text-xs text-plomo mt-0.5">Monitoreo de uso y gasto de la API LLM</p>
          </div>
        </div>
        <a
          href="/"
          className="inline-flex items-center gap-2 text-plomo hover:text-krypton text-xs transition-colors bg-carbon-100 border border-carbon-300 rounded-lg px-3 py-2"
        >
          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M10.5 19.5L3 12m0 0l7.5-7.5M3 12h18" />
          </svg>
          Panel
        </a>
      </div>

      {summary && (
        <>
          {/* ============================================= */}
          {/* HERO STATS ROW                                */}
          {/* ============================================= */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <HeroCard
              label="Gasto total"
              value={formatCost(summary.total_cost_usd)}
              icon={<path strokeLinecap="round" strokeLinejoin="round" d="M12 6v12m-3-2.818l.879.659c1.171.879 3.07.879 4.242 0 1.172-.879 1.172-2.303 0-3.182C13.536 12.219 12.768 12 12 12c-.725 0-1.45-.22-2.003-.659-1.106-.879-1.106-2.303 0-3.182s2.9-.879 4.006 0l.415.33M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />}
              gradient="from-krypton/15 to-krypton/5"
              glowColor="shadow-[0_0_30px_rgba(212,255,0,0.08)]"
              valueColor="text-krypton"
              borderColor="border-krypton/20"
            />
            <HeroCard
              label="Tokens procesados"
              value={formatTokens(summary.total_tokens)}
              subValue={formatTokensFull(summary.total_tokens)}
              icon={<path strokeLinecap="round" strokeLinejoin="round" d="M3.75 13.5l10.5-11.25L12 10.5h8.25L9.75 21.75 12 13.5H3.75z" />}
              gradient="from-blue-500/10 to-blue-500/5"
              glowColor=""
              valueColor="text-blue-400"
              borderColor="border-blue-500/20"
            />
            <HeroCard
              label="Documentos"
              value={summary.total_documents.toString()}
              icon={<path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />}
              gradient="from-purple-500/10 to-purple-500/5"
              glowColor=""
              valueColor="text-purple-400"
              borderColor="border-purple-500/20"
            />
            <HeroCard
              label="Llamadas API"
              value={formatTokensFull(summary.total_calls)}
              icon={<path strokeLinecap="round" strokeLinejoin="round" d="M7.5 21L3 16.5m0 0L7.5 12M3 16.5h13.5m0-13.5L21 7.5m0 0L16.5 12M21 7.5H7.5" />}
              gradient="from-emerald-500/10 to-emerald-500/5"
              glowColor=""
              valueColor="text-emerald-400"
              borderColor="border-emerald-500/20"
            />
          </div>

          {/* ============================================= */}
          {/* CHARTS ROW                                    */}
          {/* ============================================= */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {/* Token distribution donut */}
            <div className="bg-carbon-100 border border-carbon-300 rounded-xl p-5">
              <h3 className="text-[10px] font-semibold text-plomo uppercase tracking-wider mb-4">Distribución de tokens</h3>
              <div className="flex items-center gap-6">
                <DonutChart
                  inputPct={pct(summary.total_prompt_tokens, summary.total_tokens)}
                  outputPct={pct(summary.total_completion_tokens, summary.total_tokens)}
                />
                <div className="space-y-3 flex-1">
                  <div>
                    <div className="flex items-center gap-2 mb-1">
                      <div className="w-2.5 h-2.5 rounded-sm bg-blue-400" />
                      <span className="text-xs text-plomo">Entrada (prompt)</span>
                    </div>
                    <div className="flex items-baseline gap-2">
                      <span className="text-sm font-bold text-bruma">{formatTokens(summary.total_prompt_tokens)}</span>
                      <span className="text-[10px] text-plomo">{pct(summary.total_prompt_tokens, summary.total_tokens)}%</span>
                    </div>
                  </div>
                  <div>
                    <div className="flex items-center gap-2 mb-1">
                      <div className="w-2.5 h-2.5 rounded-sm bg-krypton" />
                      <span className="text-xs text-plomo">Salida (completion)</span>
                    </div>
                    <div className="flex items-baseline gap-2">
                      <span className="text-sm font-bold text-bruma">{formatTokens(summary.total_completion_tokens)}</span>
                      <span className="text-[10px] text-plomo">{pct(summary.total_completion_tokens, summary.total_tokens)}%</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* Cost efficiency */}
            <div className="bg-carbon-100 border border-carbon-300 rounded-xl p-5">
              <h3 className="text-[10px] font-semibold text-plomo uppercase tracking-wider mb-4">Eficiencia de costo</h3>
              <div className="space-y-4">
                <MetricRow
                  label="Por documento"
                  value={formatCost(summary.avg_cost_per_document)}
                  barPct={summary.total_documents > 0 ? Math.min(100, (summary.avg_cost_per_document / (summary.total_cost_usd || 1)) * 100 * summary.total_documents * 0.5) : 0}
                  barColor="bg-krypton/40"
                />
                <MetricRow
                  label="Por llamada API"
                  value={formatCost(summary.avg_cost_per_call)}
                  barPct={summary.total_calls > 0 ? Math.min(100, (summary.avg_cost_per_call / (summary.total_cost_usd || 1)) * 100 * summary.total_calls * 0.5) : 0}
                  barColor="bg-emerald-500/40"
                />
                <MetricRow
                  label="Por 1K tokens"
                  value={summary.total_tokens > 0 ? formatCost((summary.total_cost_usd / summary.total_tokens) * 1000) : "$0.00"}
                  barPct={60}
                  barColor="bg-blue-500/40"
                />
                <div className="pt-2 border-t border-carbon-300/50">
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] text-plomo uppercase tracking-wider">Ratio entrada/salida</span>
                    <span className="text-xs font-mono text-bruma">
                      {summary.total_completion_tokens > 0
                        ? `${(summary.total_prompt_tokens / summary.total_completion_tokens).toFixed(1)}:1`
                        : "—"}
                    </span>
                  </div>
                </div>
              </div>
            </div>

            {/* Model & pricing */}
            <div className="bg-carbon-100 border border-carbon-300 rounded-xl p-5">
              <h3 className="text-[10px] font-semibold text-plomo uppercase tracking-wider mb-4">Modelo y tarifa</h3>
              <div className="space-y-3">
                {/* Model badge */}
                <div className="flex items-center gap-3 bg-carbon-200 rounded-lg px-3 py-2.5">
                  <div className="w-8 h-8 rounded-lg bg-purple-900/30 flex items-center justify-center flex-shrink-0">
                    <svg className="w-4 h-4 text-purple-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" />
                    </svg>
                  </div>
                  <div>
                    <div className="text-xs font-semibold text-bruma">{summary.pricing.model}</div>
                    <div className="text-[10px] text-plomo">Modelo activo</div>
                  </div>
                </div>

                {/* Pricing */}
                <div className="grid grid-cols-2 gap-2">
                  <div className="bg-carbon-200 rounded-lg px-3 py-2 text-center">
                    <div className="text-[9px] text-plomo uppercase tracking-wider mb-0.5">Input / 1M tok</div>
                    <div className="text-sm font-bold text-blue-400 font-mono">${summary.pricing.input_per_1m}</div>
                  </div>
                  <div className="bg-carbon-200 rounded-lg px-3 py-2 text-center">
                    <div className="text-[9px] text-plomo uppercase tracking-wider mb-0.5">Output / 1M tok</div>
                    <div className="text-sm font-bold text-krypton font-mono">${summary.pricing.output_per_1m}</div>
                  </div>
                </div>

                {/* Model breakdown */}
                {summary.model_breakdown.length > 0 && (
                  <div className="space-y-2 pt-1">
                    {summary.model_breakdown.map((m) => {
                      const barW = summary.total_calls > 0 ? (m.calls / summary.total_calls) * 100 : 0;
                      return (
                        <div key={m.model}>
                          <div className="flex items-center justify-between text-[10px] mb-1">
                            <span className="text-plomo font-mono">{m.model}</span>
                            <span className="text-bruma">{formatCost(m.cost)}</span>
                          </div>
                          <div className="h-1.5 bg-carbon-200 rounded-full overflow-hidden">
                            <div
                              className="h-full bg-gradient-to-r from-purple-500 to-purple-400 rounded-full transition-all duration-700"
                              style={{ width: `${barW}%` }}
                            />
                          </div>
                          <div className="text-[9px] text-plomo mt-0.5">{m.calls} llamadas / {formatTokens(m.tokens)} tokens</div>
                        </div>
                      );
                    })}
                  </div>
                )}

                {/* OpenAI link */}
                <a
                  href="https://platform.openai.com/usage"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-2 text-[10px] text-krypton/70 hover:text-krypton transition-colors pt-1"
                >
                  <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 6H5.25A2.25 2.25 0 003 8.25v10.5A2.25 2.25 0 005.25 21h10.5A2.25 2.25 0 0018 18.75V10.5m-10.5 6L21 3m0 0h-5.25M21 3v5.25" />
                  </svg>
                  Verificar saldo en platform.openai.com
                </a>
              </div>
            </div>
          </div>

          {/* ============================================= */}
          {/* COST PER DOCUMENT — BAR CHART                 */}
          {/* ============================================= */}
          {documents.length > 0 && (
            <div className="bg-carbon-100 border border-carbon-300 rounded-xl p-5">
              <h3 className="text-[10px] font-semibold text-plomo uppercase tracking-wider mb-4">Costo por documento</h3>
              <div className="space-y-2">
                {documents.map((doc) => {
                  const barW = maxDocCost > 0 ? (doc.total_cost_usd / maxDocCost) * 100 : 0;
                  return (
                    <div key={doc.doc_id + "-bar"} className="group">
                      <div className="flex items-center gap-3">
                        <div className="w-28 lg:w-44 truncate text-xs text-plomo group-hover:text-bruma transition-colors" title={doc.filename}>
                          {doc.filename}
                        </div>
                        <div className="flex-1 h-5 bg-carbon-200 rounded overflow-hidden relative">
                          <div
                            className="h-full bg-gradient-to-r from-krypton/50 to-krypton/20 rounded transition-all duration-700"
                            style={{ width: `${Math.max(barW, 2)}%` }}
                          />
                          <div className="absolute inset-0 flex items-center px-2">
                            <span className="text-[10px] font-mono text-bruma/80 drop-shadow-sm">
                              {formatTokensFull(doc.total_tokens)} tok
                            </span>
                          </div>
                        </div>
                        <div className="w-20 text-right text-xs font-mono text-krypton font-semibold">
                          {formatCost(doc.total_cost_usd)}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </>
      )}

      {/* ============================================= */}
      {/* DOCUMENT TABLE WITH EXPANDABLE DETAILS         */}
      {/* ============================================= */}
      <div className="bg-carbon-100 border border-carbon-300 rounded-xl overflow-hidden">
        <div className="px-5 py-4 border-b border-carbon-300 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-7 h-7 rounded-lg bg-carbon-200 flex items-center justify-center">
              <svg className="w-3.5 h-3.5 text-plomo" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M3.375 19.5h17.25m-17.25 0a1.125 1.125 0 01-1.125-1.125M3.375 19.5h7.5c.621 0 1.125-.504 1.125-1.125m-9.75 0V5.625m0 12.75v-1.5c0-.621.504-1.125 1.125-1.125m18.375 2.625V5.625m0 12.75c0 .621-.504 1.125-1.125 1.125m1.125-1.125v-1.5c0-.621-.504-1.125-1.125-1.125m0 3.75h-7.5A1.125 1.125 0 0112 18.375m9.75-12.75c0-.621-.504-1.125-1.125-1.125H3.375c-.621 0-1.125.504-1.125 1.125m19.5 0v1.5c0 .621-.504 1.125-1.125 1.125M2.25 5.625v1.5c0 .621.504 1.125 1.125 1.125m0 0h17.25m-17.25 0h7.5c.621 0 1.125.504 1.125 1.125M3.375 8.25c-.621 0-1.125.504-1.125 1.125v1.5c0 .621.504 1.125 1.125 1.125m17.25-3.75h-7.5c-.621 0-1.125.504-1.125 1.125m8.625-1.125c.621 0 1.125.504 1.125 1.125v1.5c0 .621-.504 1.125-1.125 1.125m-17.25 0h7.5m-7.5 0c-.621 0-1.125.504-1.125 1.125v1.5c0 .621.504 1.125 1.125 1.125M12 10.875v-1.5m0 1.5c0 .621-.504 1.125-1.125 1.125M12 10.875c0 .621.504 1.125 1.125 1.125m-2.25 0c.621 0 1.125.504 1.125 1.125M13.125 12h7.5m-7.5 0c-.621 0-1.125.504-1.125 1.125M20.625 12c.621 0 1.125.504 1.125 1.125v1.5c0 .621-.504 1.125-1.125 1.125m-17.25 0h7.5M12 14.625v-1.5m0 1.5c0 .621-.504 1.125-1.125 1.125M12 14.625c0 .621.504 1.125 1.125 1.125m-2.25 0c.621 0 1.125.504 1.125 1.125m0 0v.375" />
              </svg>
            </div>
            <h3 className="text-sm font-semibold text-bruma tracking-tight">
              Desglose por documento
            </h3>
          </div>
          <span className="text-[10px] text-plomo bg-carbon-200 px-2.5 py-1 rounded-full">
            {documents.length} {documents.length === 1 ? "documento" : "documentos"}
          </span>
        </div>

        {documents.length === 0 ? (
          <div className="px-5 py-16 text-center">
            <div className="w-14 h-14 mx-auto mb-4 rounded-2xl bg-carbon-200 flex items-center justify-center">
              <svg className="w-6 h-6 text-plomo/50" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 13.5h3.86a2.25 2.25 0 012.012 1.244l.256.512a2.25 2.25 0 002.013 1.244h3.218a2.25 2.25 0 002.013-1.244l.256-.512a2.25 2.25 0 012.013-1.244h3.859M12 3v8.25m0 0l-3-3m3 3l3-3" />
              </svg>
            </div>
            <p className="text-sm text-plomo">No hay documentos con datos de costos</p>
            <p className="text-xs text-plomo/60 mt-1">Procesa un documento para ver el desglose</p>
          </div>
        ) : (
          <div>
            {documents.map((doc, i) => (
              <DocumentRow
                key={doc.doc_id}
                doc={doc}
                index={i}
                isExpanded={expandedDoc === doc.doc_id}
                onToggle={() => toggleExpand(doc.doc_id)}
                paragraphs={paragraphCosts[doc.doc_id]}
                maxCost={maxDocCost}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// =============================================
// Hero Card
// =============================================

function HeroCard({
  label,
  value,
  subValue,
  icon,
  gradient,
  glowColor,
  valueColor,
  borderColor,
}: {
  label: string;
  value: string;
  subValue?: string;
  icon: React.ReactNode;
  gradient: string;
  glowColor: string;
  valueColor: string;
  borderColor: string;
}) {
  return (
    <div className={`relative overflow-hidden bg-gradient-to-br ${gradient} border ${borderColor} rounded-xl p-5 ${glowColor}`}>
      {/* Background icon watermark */}
      <div className="absolute -right-2 -top-2 opacity-[0.04]">
        <svg className="w-20 h-20" fill="currentColor" viewBox="0 0 24 24">
          {icon}
        </svg>
      </div>
      <div className="relative">
        <div className="flex items-center gap-2 mb-3">
          <svg className={`w-4 h-4 ${valueColor}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
            {icon}
          </svg>
          <span className="text-[10px] text-plomo uppercase tracking-wider font-medium">{label}</span>
        </div>
        <div className={`text-2xl font-bold ${valueColor} font-mono tracking-tight`}>{value}</div>
        {subValue && (
          <div className="text-[10px] text-plomo mt-1 font-mono">{subValue} exactos</div>
        )}
      </div>
    </div>
  );
}

// =============================================
// Donut Chart (pure SVG)
// =============================================

function DonutChart({ inputPct, outputPct }: { inputPct: number; outputPct: number }) {
  const radius = 40;
  const circumference = 2 * Math.PI * radius;
  const inputLen = (inputPct / 100) * circumference;
  const outputLen = (outputPct / 100) * circumference;
  const gap = circumference * 0.01; // small gap between segments

  return (
    <div className="relative flex-shrink-0">
      <svg width="100" height="100" viewBox="0 0 100 100">
        {/* Background ring */}
        <circle
          cx="50" cy="50" r={radius}
          fill="none" stroke="#1A1A1A" strokeWidth="10"
        />
        {/* Input segment (blue) */}
        <circle
          cx="50" cy="50" r={radius}
          fill="none"
          stroke="#60A5FA"
          strokeWidth="10"
          strokeDasharray={`${inputLen - gap} ${circumference - inputLen + gap}`}
          strokeDashoffset={circumference * 0.25}
          strokeLinecap="round"
          className="transition-all duration-1000"
        />
        {/* Output segment (krypton) */}
        <circle
          cx="50" cy="50" r={radius}
          fill="none"
          stroke="#D4FF00"
          strokeWidth="10"
          strokeDasharray={`${outputLen - gap} ${circumference - outputLen + gap}`}
          strokeDashoffset={circumference * 0.25 - inputLen}
          strokeLinecap="round"
          className="transition-all duration-1000"
        />
      </svg>
      {/* Center text */}
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-xs font-bold text-bruma">{inputPct + outputPct > 0 ? "100" : "0"}%</span>
        <span className="text-[8px] text-plomo">total</span>
      </div>
    </div>
  );
}

// =============================================
// Metric Row with bar
// =============================================

function MetricRow({
  label,
  value,
  barPct,
  barColor,
}: {
  label: string;
  value: string;
  barPct: number;
  barColor: string;
}) {
  return (
    <div>
      <div className="flex items-center justify-between mb-1.5">
        <span className="text-xs text-plomo">{label}</span>
        <span className="text-xs font-mono font-semibold text-bruma">{value}</span>
      </div>
      <div className="h-1 bg-carbon-200 rounded-full overflow-hidden">
        <div
          className={`h-full ${barColor} rounded-full transition-all duration-700`}
          style={{ width: `${Math.max(Math.min(barPct, 100), 3)}%` }}
        />
      </div>
    </div>
  );
}

// =============================================
// Document Row (expandable)
// =============================================

function DocumentRow({
  doc,
  index,
  isExpanded,
  onToggle,
  paragraphs,
  maxCost,
}: {
  doc: DocumentCostItem;
  index: number;
  isExpanded: boolean;
  onToggle: () => void;
  paragraphs: ParagraphCostItem[] | undefined;
  maxCost: number;
}) {
  const costBarW = maxCost > 0 ? (doc.total_cost_usd / maxCost) * 100 : 0;
  const maxParagraphCost = useMemo(() => {
    if (!paragraphs || paragraphs.length === 0) return 0;
    return Math.max(...paragraphs.map((p) => p.cost_usd));
  }, [paragraphs]);

  return (
    <div className={`border-b border-carbon-300/50 last:border-b-0 transition-colors ${isExpanded ? "bg-carbon-200/20" : ""}`}>
      {/* Main row */}
      <button
        onClick={onToggle}
        className="w-full px-5 py-3.5 flex items-center gap-4 hover:bg-carbon-200/30 transition-all group"
      >
        {/* Expand icon */}
        <svg
          className={`w-3.5 h-3.5 text-plomo flex-shrink-0 transition-transform duration-200 ${isExpanded ? "rotate-90" : "group-hover:translate-x-0.5"}`}
          fill="currentColor"
          viewBox="0 0 20 20"
        >
          <path fillRule="evenodd" d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z" clipRule="evenodd" />
        </svg>

        {/* Index */}
        <span className="text-[10px] text-plomo w-5 flex-shrink-0 font-mono">{index + 1}</span>

        {/* Filename */}
        <div className="flex-1 min-w-0 text-left">
          <a
            href={`/documents/${doc.doc_id}`}
            onClick={(e) => e.stopPropagation()}
            className="text-sm text-bruma hover:text-krypton transition-colors truncate block"
          >
            {doc.filename}
          </a>
          <div className="flex items-center gap-3 mt-1">
            <span className="text-[10px] text-plomo">
              {doc.total_pages ?? "—"} pág
            </span>
            <span className="text-[10px] text-plomo">
              {doc.total_calls} calls
            </span>
            <span className="text-[10px] text-plomo font-mono">
              {formatTokensFull(doc.total_tokens)} tok
            </span>
          </div>
        </div>

        {/* Cost bar + value */}
        <div className="w-48 flex items-center gap-3 flex-shrink-0">
          <div className="flex-1 h-2 bg-carbon-200 rounded-full overflow-hidden">
            <div
              className="h-full bg-gradient-to-r from-krypton/60 to-krypton/30 rounded-full transition-all duration-500"
              style={{ width: `${Math.max(costBarW, 4)}%` }}
            />
          </div>
          <span className="text-xs font-mono text-krypton font-semibold w-20 text-right">
            {formatCost(doc.total_cost_usd)}
          </span>
        </div>
      </button>

      {/* Expanded: paragraph breakdown */}
      {isExpanded && (
        <div className="px-5 pb-4">
          <div className="ml-9 bg-carbon-200/50 rounded-xl border border-carbon-300/50 overflow-hidden">
            {!paragraphs ? (
              <div className="px-4 py-6 text-center">
                <div className="w-5 h-5 mx-auto border-2 border-carbon-50 border-t-krypton rounded-full animate-spin" />
                <p className="text-[10px] text-plomo mt-2">Cargando desglose...</p>
              </div>
            ) : paragraphs.length === 0 ? (
              <div className="px-4 py-6 text-center text-xs text-plomo">
                Sin registros detallados para este documento
              </div>
            ) : (
              <>
                {/* Summary mini-stats */}
                <div className="grid grid-cols-4 gap-px bg-carbon-300/30">
                  <MiniStat label="Llamadas" value={paragraphs.length.toString()} />
                  <MiniStat
                    label="Tokens total"
                    value={formatTokens(paragraphs.reduce((s, p) => s + p.total_tokens, 0))}
                  />
                  <MiniStat
                    label="Costo total"
                    value={formatCost(paragraphs.reduce((s, p) => s + p.cost_usd, 0))}
                    highlight
                  />
                  <MiniStat
                    label="Costo promedio"
                    value={formatCost(paragraphs.reduce((s, p) => s + p.cost_usd, 0) / paragraphs.length)}
                  />
                </div>

                {/* Paragraph rows */}
                <div className="divide-y divide-carbon-300/30">
                  {paragraphs.map((p) => {
                    const pBarW = maxParagraphCost > 0 ? (p.cost_usd / maxParagraphCost) * 100 : 0;
                    return (
                      <div key={p.id} className="px-4 py-2.5 flex items-center gap-3 hover:bg-carbon-200/30 transition-colors">
                        {/* Index */}
                        <span className="text-[10px] text-plomo font-mono w-6 flex-shrink-0 text-center">
                          {p.paragraph_index}
                        </span>

                        {/* Location */}
                        <span className="text-[10px] text-plomo font-mono w-24 truncate flex-shrink-0" title={p.location}>
                          {p.location}
                        </span>

                        {/* Type badge */}
                        <span className={`inline-flex px-1.5 py-0.5 rounded text-[9px] font-semibold flex-shrink-0 ${
                          p.call_type === "correction_editorial"
                            ? "bg-purple-900/30 text-purple-400"
                            : p.call_type === "correction_cheap"
                            ? "bg-blue-900/30 text-blue-400"
                            : p.call_type === "correction_skip"
                            ? "bg-carbon-300/30 text-plomo"
                            : p.call_type.startsWith("analysis")
                            ? "bg-teal-900/30 text-teal-400"
                            : "bg-blue-900/30 text-blue-400"
                        }`}>
                          {p.call_type === "correction_editorial" ? "Editorial"
                            : p.call_type === "correction_cheap" ? "Cheap"
                            : p.call_type === "correction_skip" ? "Skip"
                            : p.call_type.startsWith("analysis") ? "Análisis"
                            : "MVP1"}
                        </span>

                        {/* Model */}
                        <span className="text-[9px] text-plomo font-mono w-20 truncate flex-shrink-0">
                          {p.model_used}
                        </span>

                        {/* Cost bar */}
                        <div className="flex-1 h-1.5 bg-carbon-300/50 rounded-full overflow-hidden">
                          <div
                            className={`h-full rounded-full transition-all duration-500 ${
                              p.call_type === "correction_editorial"
                                ? "bg-gradient-to-r from-purple-500/60 to-purple-400/30"
                                : p.call_type === "correction_skip"
                                ? "bg-gradient-to-r from-gray-500/40 to-gray-400/20"
                                : "bg-gradient-to-r from-blue-500/60 to-blue-400/30"
                            }`}
                            style={{ width: `${Math.max(pBarW, 4)}%` }}
                          />
                        </div>

                        {/* Tokens */}
                        <span className="text-[10px] text-plomo font-mono w-14 text-right flex-shrink-0">
                          {formatTokens(p.total_tokens)}
                        </span>

                        {/* Cost */}
                        <span className="text-[10px] text-krypton font-mono font-semibold w-16 text-right flex-shrink-0">
                          {formatCost(p.cost_usd)}
                        </span>
                      </div>
                    );
                  })}
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// =============================================
// Mini stat (for expanded paragraph section)
// =============================================

function MiniStat({ label, value, highlight }: { label: string; value: string; highlight?: boolean }) {
  return (
    <div className="bg-carbon-200/50 px-3 py-2.5 text-center">
      <div className="text-[8px] text-plomo uppercase tracking-wider mb-0.5">{label}</div>
      <div className={`text-xs font-bold font-mono ${highlight ? "text-krypton" : "text-bruma"}`}>{value}</div>
    </div>
  );
}
