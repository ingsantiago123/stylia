"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  getDocument,
  getDocumentCorrections,
  listPages,
  downloadPdf,
  downloadDocx,
  DocumentDetail,
  PatchListItem,
  PageListItem,
} from "@/lib/api";
import { PipelineFlow } from "@/components/PipelineFlow";
import { CorrectionHistory } from "@/components/CorrectionHistory";
import { CorrectionFlowViewer } from "@/components/CorrectionFlowViewer";

type Tab = "pipeline" | "corrections" | "pages" | "api-flow";

export default function DocumentDetailPage() {
  const params = useParams();
  const router = useRouter();
  const docId = params.id as string;

  const [doc, setDoc] = useState<DocumentDetail | null>(null);
  const [corrections, setCorrections] = useState<PatchListItem[]>([]);
  const [pages, setPages] = useState<PageListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<Tab>("pipeline");

  const fetchData = useCallback(async () => {
    try {
      const [docData, correctionsData, pagesData] = await Promise.all([
        getDocument(docId),
        getDocumentCorrections(docId).catch(() => []),
        listPages(docId).catch(() => []),
      ]);
      setDoc(docData);
      setCorrections(correctionsData);
      setPages(pagesData);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error");
    } finally {
      setLoading(false);
    }
  }, [docId]);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 4000);
    return () => clearInterval(interval);
  }, [fetchData]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="flex items-center gap-3 text-plomo">
          <svg className="animate-spin h-5 w-5 text-krypton" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
          Cargando documento...
        </div>
      </div>
    );
  }

  if (error || !doc) {
    return (
      <div className="text-center py-16">
        <div className="w-16 h-16 mx-auto mb-4 rounded-2xl bg-red-900/20 flex items-center justify-center">
          <svg className="w-7 h-7 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" />
          </svg>
        </div>
        <p className="text-red-400 mb-4 font-medium">{error || "Documento no encontrado"}</p>
        <button
          onClick={() => router.push("/")}
          className="text-krypton hover:text-krypton/80 text-sm font-medium transition-colors"
        >
          ← Volver al inicio
        </button>
      </div>
    );
  }

  const isProcessing = !["completed", "failed", "uploaded"].includes(doc.status);
  const pagesWithCorrections = pages.filter((p) => p.has_corrections).length;

  return (
    <div className="space-y-6">
      {/* Navigation */}
      <button
        onClick={() => router.push("/")}
        className="inline-flex items-center gap-2 text-plomo hover:text-krypton text-sm transition-colors group"
      >
        <svg className="w-4 h-4 group-hover:-translate-x-0.5 transition-transform" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M10.5 19.5L3 12m0 0l7.5-7.5M3 12h18" />
        </svg>
        Panel de control
      </button>

      {/* Document header */}
      <div className="bg-carbon-100 border border-carbon-300 rounded-xl p-6">
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0">
            <h1 className="text-xl font-bold text-bruma truncate">{doc.filename}</h1>
            <div className="flex items-center gap-4 mt-2 text-sm text-plomo">
              <span className="uppercase text-xs font-medium tracking-wider bg-carbon-200 px-2 py-0.5 rounded">
                {doc.original_format}
              </span>
              {doc.total_pages && (
                <span>{doc.total_pages} páginas</span>
              )}
              <span>
                {new Date(doc.created_at).toLocaleDateString("es", {
                  day: "numeric",
                  month: "long",
                  year: "numeric",
                  hour: "2-digit",
                  minute: "2-digit",
                })}
              </span>
            </div>
          </div>

          {/* Download actions */}
          {doc.status === "completed" && (
            <div className="flex items-center gap-2 flex-shrink-0">
              <button
                onClick={() => downloadPdf(doc.id)}
                className="px-4 py-2 bg-krypton text-carbon font-semibold text-sm rounded-lg hover:bg-krypton/90 transition-colors shadow-[0_0_15px_rgba(212,255,0,0.2)]"
              >
                Descargar PDF
              </button>
              <button
                onClick={() => downloadDocx(doc.id)}
                className="px-4 py-2 border border-krypton/40 text-krypton font-medium text-sm rounded-lg hover:bg-krypton/10 transition-colors"
              >
                Descargar DOCX
              </button>
            </div>
          )}
        </div>

        {/* Quick stats */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mt-5 pt-5 border-t border-carbon-300">
          <StatCard label="Estado" value={doc.status} isStatus />
          <StatCard label="Páginas" value={doc.total_pages?.toString() || "—"} />
          <StatCard label="Correcciones" value={corrections.length.toString()} highlight />
          <StatCard label="Págs. con cambios" value={`${pagesWithCorrections}/${pages.length || "—"}`} />
        </div>
      </div>

      {/* Pipeline Flow */}
      <PipelineFlow
        currentStatus={doc.status}
        progress={doc.progress}
        errorMessage={doc.error_message}
      />

      {/* Tab navigation */}
      <div className="flex items-center gap-1 bg-carbon-100 border border-carbon-300 rounded-xl p-1">
        {([
          { key: "pipeline" as Tab, label: "Resumen", icon: "◎" },
          { key: "corrections" as Tab, label: `Correcciones (${corrections.length})`, icon: "✎" },
          { key: "api-flow" as Tab, label: "Flujo API", icon: "⚡" },
          { key: "pages" as Tab, label: `Páginas (${pages.length})`, icon: "▣" },
        ]).map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`
              flex-1 flex items-center justify-center gap-2 px-4 py-2.5 text-sm font-medium rounded-lg transition-all
              ${activeTab === tab.key
                ? "bg-krypton text-carbon shadow-[0_0_10px_rgba(212,255,0,0.15)]"
                : "text-plomo hover:text-bruma hover:bg-carbon-200"
              }
            `}
          >
            <span>{tab.icon}</span>
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {activeTab === "pipeline" && (
        <SummaryTab doc={doc} corrections={corrections} pages={pages} isProcessing={isProcessing} />
      )}

      {activeTab === "corrections" && (
        <CorrectionHistory corrections={corrections} />
      )}

      {activeTab === "api-flow" && (
        <div className="space-y-4">
          <div className="bg-carbon-100 border border-carbon-300 rounded-xl p-4">
            <div className="flex items-start gap-3">
              <div className="w-8 h-8 rounded-lg bg-krypton/20 flex items-center justify-center flex-shrink-0">
                <span className="text-krypton text-sm">⚡</span>
              </div>
              <div>
                <h3 className="text-sm font-semibold text-bruma mb-1">Diseño del flujo ChatGPT API</h3>
                <p className="text-xs text-plomo">
                  Esta vista muestra cómo se enviará cada bloque de texto a ChatGPT con contexto acumulado 
                  para mantener consistencia de estilo. Cada petición incluye los párrafos anteriores ya corregidos.
                </p>
              </div>
            </div>
          </div>
          <CorrectionFlowViewer docId={doc.id} />
        </div>
      )}

      {activeTab === "pages" && (
        <PagesTab pages={pages} docId={doc.id} />
      )}
    </div>
  );
}

// =============================================
// Sub-components
// =============================================

function StatCard({ label, value, isStatus, highlight }: {
  label: string;
  value: string;
  isStatus?: boolean;
  highlight?: boolean;
}) {
  const statusColors: Record<string, string> = {
    uploaded: "text-plomo",
    converting: "text-krypton",
    extracting: "text-krypton",
    correcting: "text-krypton",
    rendering: "text-krypton",
    completed: "text-krypton",
    failed: "text-red-400",
  };

  return (
    <div className="text-center">
      <div className="text-[10px] uppercase tracking-wider text-plomo mb-1">{label}</div>
      <div className={`text-lg font-semibold ${
        isStatus ? (statusColors[value] || "text-bruma") :
        highlight ? "text-krypton" : "text-bruma"
      }`}>
        {isStatus ? value.charAt(0).toUpperCase() + value.slice(1) : value}
      </div>
    </div>
  );
}

function SummaryTab({ doc, corrections, pages, isProcessing }: {
  doc: DocumentDetail;
  corrections: PatchListItem[];
  pages: PageListItem[];
  isProcessing: boolean;
}) {
  const ltCount = corrections.filter((c) => c.source === "languagetool").length;
  const llmCount = corrections.filter((c) => c.source === "llm").length;

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      {/* Processing status */}
      <div className="bg-carbon-100 border border-carbon-300 rounded-xl p-5">
        <h3 className="text-sm font-semibold text-bruma uppercase tracking-wider mb-4">Estado del proceso</h3>
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-sm text-plomo">Progreso general</span>
            <span className="text-sm font-mono text-krypton">{Math.round(doc.progress * 100)}%</span>
          </div>
          <div className="h-2 bg-carbon-300 rounded-full overflow-hidden">
            <div
              className="h-full bg-krypton rounded-full transition-all duration-500"
              style={{ width: `${Math.round(doc.progress * 100)}%` }}
            />
          </div>

          {isProcessing && (
            <div className="flex items-center gap-2 text-xs text-krypton mt-2">
              <span className="w-1.5 h-1.5 rounded-full bg-krypton animate-pulse-slow" />
              Procesando en tiempo real...
            </div>
          )}

          {/* Pages summary */}
          {doc.pages_summary && Object.keys(doc.pages_summary).length > 0 && (
            <div className="mt-4 pt-4 border-t border-carbon-300 space-y-2">
              <span className="text-xs text-plomo uppercase tracking-wider">Resumen de páginas</span>
              {Object.entries(doc.pages_summary).map(([status, count]) => (
                <div key={status} className="flex items-center justify-between text-sm">
                  <span className="text-plomo capitalize">{status}</span>
                  <span className="text-bruma font-medium">{count as number}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Corrections breakdown */}
      <div className="bg-carbon-100 border border-carbon-300 rounded-xl p-5">
        <h3 className="text-sm font-semibold text-bruma uppercase tracking-wider mb-4">Correcciones</h3>
        {corrections.length === 0 ? (
          <div className="text-center py-6 text-plomo text-sm">
            {isProcessing ? "Esperando correcciones..." : "Sin correcciones"}
          </div>
        ) : (
          <div className="space-y-4">
            {/* Breakdown chart */}
            <div className="flex gap-2 h-4 rounded-full overflow-hidden">
              {ltCount > 0 && (
                <div
                  className="bg-blue-500 rounded-full transition-all duration-500"
                  style={{ width: `${(ltCount / corrections.length) * 100}%` }}
                  title={`LanguageTool: ${ltCount}`}
                />
              )}
              {llmCount > 0 && (
                <div
                  className="bg-purple-500 rounded-full transition-all duration-500"
                  style={{ width: `${(llmCount / corrections.length) * 100}%` }}
                  title={`LLM: ${llmCount}`}
                />
              )}
            </div>

            <div className="space-y-2">
              <div className="flex items-center justify-between text-sm">
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 rounded bg-blue-500" />
                  <span className="text-plomo">LanguageTool</span>
                </div>
                <span className="text-bruma font-medium">{ltCount}</span>
              </div>
              <div className="flex items-center justify-between text-sm">
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 rounded bg-purple-500" />
                  <span className="text-plomo">LLM (estilo)</span>
                </div>
                <span className="text-bruma font-medium">{llmCount}</span>
              </div>
            </div>

            {/* Recent corrections preview */}
            <div className="pt-3 border-t border-carbon-300">
              <span className="text-xs text-plomo uppercase tracking-wider">Últimas correcciones</span>
              <div className="mt-2 space-y-1.5">
                {corrections.slice(0, 3).map((c) => (
                  <div key={c.id} className="text-xs text-plomo truncate">
                    <span className="text-red-400/80 line-through">{c.original_text.slice(0, 40)}</span>
                    {" → "}
                    <span className="text-krypton/80">{c.corrected_text.slice(0, 40)}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Document info */}
      <div className="bg-carbon-100 border border-carbon-300 rounded-xl p-5 md:col-span-2">
        <h3 className="text-sm font-semibold text-bruma uppercase tracking-wider mb-4">Información del documento</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
          <div>
            <span className="text-plomo text-xs block mb-0.5">ID</span>
            <span className="text-bruma font-mono text-xs">{doc.id.slice(0, 8)}...</span>
          </div>
          <div>
            <span className="text-plomo text-xs block mb-0.5">Formato</span>
            <span className="text-bruma">{doc.original_format.toUpperCase()}</span>
          </div>
          <div>
            <span className="text-plomo text-xs block mb-0.5">Creado</span>
            <span className="text-bruma">
              {new Date(doc.created_at).toLocaleDateString("es", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" })}
            </span>
          </div>
          <div>
            <span className="text-plomo text-xs block mb-0.5">Actualizado</span>
            <span className="text-bruma">
              {new Date(doc.updated_at).toLocaleDateString("es", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" })}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}

function PagesTab({ pages, docId }: { pages: PageListItem[]; docId: string }) {
  const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

  if (pages.length === 0) {
    return (
      <div className="bg-carbon-100 border border-carbon-300 rounded-xl p-8 text-center">
        <p className="text-plomo">No hay páginas disponibles aún</p>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
      {pages.map((page) => {
        const statusColors: Record<string, string> = {
          pending: "bg-carbon-200 text-plomo",
          extracting: "bg-krypton/15 text-krypton",
          correcting: "bg-krypton/15 text-krypton",
          rendering: "bg-krypton/15 text-krypton",
          completed: "bg-krypton/20 text-krypton",
          failed: "bg-red-900/30 text-red-400",
        };

        return (
          <div
            key={page.id}
            className="bg-carbon-100 border border-carbon-300 rounded-xl p-4 hover:border-krypton/30 transition-all"
          >
            <div className="flex items-center justify-between mb-3">
              <span className="text-sm font-semibold text-bruma">Página {page.page_no}</span>
              <span className={`text-[10px] uppercase tracking-wider font-medium px-2 py-0.5 rounded-full ${statusColors[page.status] || "bg-carbon-200 text-plomo"}`}>
                {page.status}
              </span>
            </div>

            {/* Preview thumbnail */}
            {page.preview_uri && page.status !== "pending" && (
              <div className="mb-3 rounded-lg overflow-hidden bg-carbon-200 aspect-[3/4] flex items-center justify-center">
                <img
                  src={`${API_BASE}/documents/${docId}/pages/${page.page_no}/preview`}
                  alt={`Página ${page.page_no}`}
                  className="w-full h-full object-contain"
                  loading="lazy"
                />
              </div>
            )}

            <div className="flex items-center justify-between text-xs text-plomo">
              <span>{page.page_type || "—"}</span>
              {page.has_corrections && (
                <span className="text-krypton flex items-center gap-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-krypton" />
                  {page.patches_count} correcciones
                </span>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
