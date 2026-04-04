"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  getDocument,
  getDocumentCorrections,
  listPages,
  getProfile,
  getDocumentAnalysis,
  getCorrectionBatches,
  getPagePreviewUrl,
  downloadPdf,
  downloadDocx,
  DocumentDetail,
  PatchListItem,
  PageListItem,
  StyleProfile,
  AnalysisResult,
  CorrectionBatchStatus,
} from "@/lib/api";
import { PipelineFlow } from "@/components/PipelineFlow";
import { CorrectionHistory } from "@/components/CorrectionHistory";
import { CorrectionFlowViewer } from "@/components/CorrectionFlowViewer";
import { DiffCompareView } from "@/components/DiffCompareView";
import { AnalysisView } from "@/components/AnalysisView";

type Tab = "pipeline" | "analysis" | "corrections" | "pages" | "api-flow";

export default function DocumentDetailPage() {
  const params = useParams();
  const router = useRouter();
  const docId = params.id as string;

  const [doc, setDoc] = useState<DocumentDetail | null>(null);
  const [corrections, setCorrections] = useState<PatchListItem[]>([]);
  const [pages, setPages] = useState<PageListItem[]>([]);
  const [profile, setProfile] = useState<StyleProfile | null>(null);
  const [analysis, setAnalysis] = useState<AnalysisResult | null>(null);
  const [correctionBatches, setCorrectionBatches] = useState<CorrectionBatchStatus[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<Tab>("pipeline");
  const [previewPage, setPreviewPage] = useState(1);
  const [previewOpen, setPreviewOpen] = useState(false);

  const fetchData = useCallback(async () => {
    try {
      const docData = await getDocument(docId);
      setDoc(docData);

      const isCorrecting = docData.status === "correcting";
      const [correctionsData, pagesData, profileData, analysisData, batchesData] = await Promise.all([
        getDocumentCorrections(docId).catch(() => [] as PatchListItem[]),
        listPages(docId).catch(() => [] as PageListItem[]),
        getProfile(docId).catch(() => null),
        getDocumentAnalysis(docId).catch(() => null),
        isCorrecting ? getCorrectionBatches(docId).catch(() => [] as CorrectionBatchStatus[]) : Promise.resolve([] as CorrectionBatchStatus[]),
      ]);
      setCorrections(correctionsData);
      setPages(pagesData);
      setProfile(profileData);
      setAnalysis(analysisData);
      setCorrectionBatches(batchesData);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error");
    } finally {
      setLoading(false);
    }
  }, [docId]);

  useEffect(() => {
    fetchData();
    const getInterval = () => {
      if (!doc) return 2000;
      const isActive = !["completed", "failed", "uploaded"].includes(doc.status);
      return isActive ? 2000 : 10000;
    };
    let timer: ReturnType<typeof setTimeout>;
    const tick = () => {
      timer = setTimeout(async () => {
        await fetchData();
        tick();
      }, getInterval());
    };
    tick();
    return () => clearTimeout(timer);
  }, [fetchData, doc?.status]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24 animate-fade-in">
        <div className="flex flex-col items-center gap-4">
          <div className="w-12 h-12 rounded-2xl bg-surface-elevated flex items-center justify-center">
            <svg className="animate-spin h-5 w-5 text-krypton" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
          </div>
          <span className="text-plomo text-sm">Cargando documento...</span>
        </div>
      </div>
    );
  }

  if (error || !doc) {
    return (
      <div className="text-center py-20 animate-fade-in">
        <div className="w-16 h-16 mx-auto mb-5 rounded-2xl bg-red-500/10 flex items-center justify-center">
          <svg className="w-7 h-7 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" />
          </svg>
        </div>
        <p className="text-red-400 mb-4 font-medium">{error || "Documento no encontrado"}</p>
        <button
          onClick={() => router.push("/")}
          className="text-krypton hover:text-krypton/80 text-sm font-medium transition-colors"
        >
          Volver al inicio
        </button>
      </div>
    );
  }

  const isProcessing = !["completed", "failed", "uploaded"].includes(doc.status);
  const isCompleted = doc.status === "completed";
  const pagesWithCorrections = pages.filter((p) => p.has_corrections).length;
  const hasPreview = doc.total_pages && doc.total_pages > 0;
  const progressPercent = Math.round(doc.progress * 100);

  const TABS: { key: Tab; label: string; count?: number }[] = [
    { key: "pipeline", label: "Resumen" },
    { key: "analysis", label: "Analisis", count: analysis?.sections?.length },
    { key: "corrections", label: "Correcciones", count: corrections.length },
    { key: "api-flow", label: "Flujo API" },
    { key: "pages", label: "Comparar", count: corrections.length },
  ];

  return (
    <div className="animate-fade-in">
      {/* Back navigation */}
      <button
        onClick={() => router.push("/")}
        className="inline-flex items-center gap-1.5 text-plomo hover:text-krypton text-sm transition-colors group mb-6"
      >
        <svg className="w-4 h-4 group-hover:-translate-x-0.5 transition-transform" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M10.5 19.5L3 12m0 0l7.5-7.5M3 12h18" />
        </svg>
        Documentos
      </button>

      {/* Document header — glass card with preview */}
      <div className="glass-card rounded-2xl overflow-hidden mb-6">
        <div className="flex flex-col lg:flex-row">
          {/* Preview thumbnail (left side on desktop) */}
          {hasPreview && (
            <div className="lg:w-56 flex-shrink-0 relative bg-carbon-400">
              <button
                onClick={() => setPreviewOpen(!previewOpen)}
                className="w-full h-40 lg:h-full relative group/preview cursor-pointer"
              >
                <img
                  src={getPagePreviewUrl(doc.id, previewPage)}
                  alt={`Preview pagina ${previewPage}`}
                  className="w-full h-full object-contain bg-carbon-300 group-hover/preview:brightness-110 transition-all"
                  onError={(e) => {
                    (e.target as HTMLImageElement).style.display = "none";
                  }}
                />
                <div className="absolute inset-0 bg-gradient-to-t from-carbon/80 via-transparent to-transparent opacity-0 group-hover/preview:opacity-100 transition-opacity flex items-end justify-center pb-3">
                  <span className="text-[11px] text-bruma-muted font-medium bg-carbon/60 backdrop-blur-sm px-2.5 py-1 rounded-md">
                    Ver preview
                  </span>
                </div>
                {doc.total_pages && doc.total_pages > 1 && (
                  <div className="absolute bottom-2 right-2 flex items-center gap-1 text-[10px] text-bruma-muted bg-carbon/70 backdrop-blur-sm px-2 py-0.5 rounded">
                    {previewPage}/{doc.total_pages}
                  </div>
                )}
              </button>
            </div>
          )}

          {/* Document info */}
          <div className="flex-1 p-6">
            <div className="flex items-start justify-between gap-4">
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-3 mb-2">
                  <h1 className="text-xl font-bold text-bruma truncate">{doc.filename}</h1>
                  <span className={`
                    inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-md text-[11px] font-medium flex-shrink-0
                    ${isCompleted ? "bg-emerald-500/15 text-emerald-400" :
                      doc.status === "failed" ? "bg-red-500/15 text-red-400" :
                      isProcessing ? "bg-krypton/10 text-krypton" :
                      "bg-surface-hover text-plomo"}
                  `}>
                    {isProcessing && <span className="w-1.5 h-1.5 rounded-full bg-current animate-pulse-slow" />}
                    {doc.status === "completed" ? "Completado" :
                     doc.status === "failed" ? "Error" :
                     doc.status === "uploaded" ? "Subido" :
                     `${progressPercent}%`}
                  </span>
                </div>

                <div className="flex items-center gap-4 text-sm text-plomo">
                  <span className="uppercase text-[10px] font-semibold tracking-wider bg-surface-elevated px-2 py-0.5 rounded">
                    {doc.original_format}
                  </span>
                  {doc.total_pages && <span>{doc.total_pages} paginas</span>}
                  <span className="text-plomo-dark">
                    {new Date(doc.created_at).toLocaleDateString("es", {
                      day: "numeric",
                      month: "long",
                      year: "numeric",
                    })}
                  </span>
                </div>
              </div>

              {/* Download buttons */}
              {isCompleted && (
                <div className="flex items-center gap-2 flex-shrink-0">
                  <button
                    onClick={() => downloadPdf(doc.id)}
                    className="px-4 py-2 bg-krypton text-carbon font-semibold text-sm rounded-lg hover:bg-krypton-200 transition-colors shadow-glow-sm"
                  >
                    Descargar PDF
                  </button>
                  <button
                    onClick={() => downloadDocx(doc.id)}
                    className="px-4 py-2 border border-krypton/30 text-krypton font-medium text-sm rounded-lg hover:bg-krypton/10 transition-colors"
                  >
                    DOCX
                  </button>
                </div>
              )}
            </div>

            {/* Quick stats */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-5 pt-5 border-t border-border-subtle">
              <QuickStat
                label="Progreso"
                value={`${progressPercent}%`}
                color={isCompleted ? "text-emerald-400" : isProcessing ? "text-krypton" : "text-plomo"}
              />
              <QuickStat label="Paginas" value={doc.total_pages?.toString() || "—"} />
              <QuickStat label="Correcciones" value={corrections.length.toString()} color="text-krypton" />
              <QuickStat label="Con cambios" value={`${pagesWithCorrections}/${pages.length || "—"}`} />
            </div>
          </div>
        </div>
      </div>

      {/* Preview gallery (expandable) */}
      {previewOpen && hasPreview && (
        <div className="glass-card rounded-xl p-4 mb-6 animate-scale-in">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold text-bruma">Preview de paginas</h3>
            <button onClick={() => setPreviewOpen(false)} className="text-plomo hover:text-bruma p-1">
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
          <div className="flex gap-2 overflow-x-auto pb-2">
            {Array.from({ length: Math.min(doc.total_pages || 0, 20) }, (_, i) => i + 1).map((pageNo) => (
              <button
                key={pageNo}
                onClick={() => setPreviewPage(pageNo)}
                className={`
                  flex-shrink-0 w-20 h-28 rounded-lg overflow-hidden border-2 transition-all
                  ${previewPage === pageNo ? "border-krypton shadow-glow-sm" : "border-transparent hover:border-border"}
                `}
              >
                <img
                  src={getPagePreviewUrl(doc.id, pageNo)}
                  alt={`Pagina ${pageNo}`}
                  className="w-full h-full object-cover object-top bg-carbon-300"
                  onError={(e) => {
                    const target = e.target as HTMLImageElement;
                    target.style.display = "none";
                    target.parentElement!.innerHTML = `<div class="w-full h-full flex items-center justify-center bg-carbon-300 text-plomo-dark text-xs">${pageNo}</div>`;
                  }}
                />
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Pipeline Flow */}
      <PipelineFlow
        currentStatus={doc.status}
        progress={doc.progress}
        errorMessage={doc.error_message}
        progressDetail={doc.progress_detail}
        correctionBatches={correctionBatches}
      />

      {/* Tab navigation */}
      <div className="flex items-center gap-0.5 glass-card rounded-xl p-1 mt-6 mb-6">
        {TABS.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`
              flex-1 flex items-center justify-center gap-1.5 px-3 py-2 text-sm font-medium rounded-lg transition-all tab-indicator
              ${activeTab === tab.key
                ? "bg-krypton text-carbon shadow-glow-sm"
                : "text-plomo hover:text-bruma hover:bg-surface-hover"
              }
            `}
          >
            {tab.label}
            {tab.count != null && tab.count > 0 && (
              <span className={`
                text-[10px] px-1.5 py-0.5 rounded font-mono
                ${activeTab === tab.key ? "bg-carbon/20 text-carbon" : "bg-surface-elevated text-plomo"}
              `}>
                {tab.count}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div className="animate-fade-in">
        {activeTab === "pipeline" && (
          <SummaryTab doc={doc} corrections={corrections} pages={pages} isProcessing={isProcessing} profile={profile} />
        )}

        {activeTab === "analysis" && (
          <AnalysisView analysis={analysis} />
        )}

        {activeTab === "corrections" && (
          <CorrectionHistory corrections={corrections} />
        )}

        {activeTab === "api-flow" && (
          <div className="space-y-4">
            <div className="glass-card rounded-xl p-4">
              <div className="flex items-start gap-3">
                <div className="w-8 h-8 rounded-lg bg-krypton/10 flex items-center justify-center flex-shrink-0">
                  <svg className="w-4 h-4 text-krypton" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 13.5l10.5-11.25L12 10.5h8.25L9.75 21.75 12 13.5H3.75z" />
                  </svg>
                </div>
                <div>
                  <h3 className="text-sm font-semibold text-bruma mb-1">Flujo de correccion</h3>
                  <p className="text-xs text-plomo">
                    Muestra como se proceso cada parrafo: LanguageTool (ortografia) → LLM (estilo con contexto acumulado).
                    {profile ? " Cada peticion al LLM usa el perfil editorial para parametrizar el prompt." : " Sin perfil editorial — prompt generico."}
                  </p>
                </div>
              </div>
            </div>

            {profile && (
              <div className="glass-card rounded-xl p-5" style={{ borderColor: "rgba(212,255,0,0.1)" }}>
                <h3 className="text-sm font-semibold text-bruma uppercase tracking-wider mb-3">Configuracion del prompt LLM</h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <span className="text-[10px] text-plomo uppercase tracking-wider block mb-2">Parametros del perfil enviados al LLM</span>
                    <div className="bg-surface rounded-lg border border-border-subtle px-4 py-3 text-xs font-mono text-bruma-muted space-y-1">
                      <div>PERFIL: <span className="text-krypton">{profile.register}</span> | Intervencion: <span className="text-krypton">{profile.intervention_level}</span></div>
                      <div>Audiencia: <span className="text-krypton">{profile.audience_type || "general"}</span> ({profile.audience_expertise})</div>
                      <div>Tono: <span className="text-krypton">{profile.tone || "neutro"}</span></div>
                      <div>Preservar voz: <span className="text-krypton">{profile.preserve_author_voice ? "si" : "no"}</span></div>
                      <div>Max reescritura: <span className="text-krypton">{Math.round(profile.max_rewrite_ratio * 100)}%</span></div>
                      {profile.style_priorities.length > 0 && (
                        <div>Prioridades: <span className="text-krypton">{profile.style_priorities.join(", ")}</span></div>
                      )}
                      {profile.protected_terms.length > 0 && (
                        <div>Proteger: <span className="text-purple-400">{profile.protected_terms.join(", ")}</span></div>
                      )}
                    </div>
                  </div>
                  <div>
                    <span className="text-[10px] text-plomo uppercase tracking-wider block mb-2">System prompt (resumen)</span>
                    <div className="bg-surface rounded-lg border border-border-subtle px-4 py-3 text-xs text-bruma-muted space-y-1">
                      <p>El LLM recibe un system prompt estatico con:</p>
                      <ul className="list-disc list-inside space-y-0.5 text-plomo">
                        <li>Reglas de correccion (no cambiar significado, respetar intervencion)</li>
                        <li>9 categorias de cambios (redundancia, claridad, lexico...)</li>
                        <li>3 niveles de severidad (critico, importante, sugerencia)</li>
                        <li>Schema JSON de respuesta estructurada</li>
                        <li>Ejemplos de correccion y de no-correccion</li>
                      </ul>
                      <p className="mt-2 text-plomo">Cada parrafo se envia con el perfil codificado + contexto del parrafo anterior.</p>
                    </div>
                  </div>
                </div>
              </div>
            )}

            <CorrectionFlowViewer docId={doc.id} />
          </div>
        )}

        {activeTab === "pages" && (
          <DiffCompareView
            corrections={corrections}
            totalPages={doc.total_pages}
            docId={doc.id}
            docStatus={doc.status}
          />
        )}
      </div>
    </div>
  );
}

// =============================================
// Sub-components
// =============================================

function QuickStat({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div className="text-center">
      <div className="text-[10px] uppercase tracking-wider text-plomo-dark mb-1">{label}</div>
      <div className={`text-lg font-bold ${color || "text-bruma"}`}>{value}</div>
    </div>
  );
}

const CATEGORY_LABELS: Record<string, string> = {
  redundancia: "Redundancia",
  claridad: "Claridad",
  registro: "Registro",
  cohesion: "Cohesion",
  lexico: "Lexico",
  estructura: "Estructura",
  puntuacion: "Puntuacion",
  ritmo: "Ritmo",
  muletilla: "Muletilla",
};

const CATEGORY_COLORS: Record<string, string> = {
  redundancia: "bg-orange-500",
  claridad: "bg-blue-500",
  registro: "bg-indigo-500",
  cohesion: "bg-cyan-500",
  lexico: "bg-teal-500",
  estructura: "bg-violet-500",
  puntuacion: "bg-amber-500",
  ritmo: "bg-pink-500",
  muletilla: "bg-rose-500",
};

const INTERVENTION_LABELS: Record<string, { label: string; color: string }> = {
  minima: { label: "Minima", color: "bg-emerald-500/15 text-emerald-400" },
  sutil: { label: "Sutil", color: "bg-blue-500/15 text-blue-400" },
  moderada: { label: "Moderada", color: "bg-yellow-500/15 text-yellow-400" },
  agresiva: { label: "Agresiva", color: "bg-red-500/15 text-red-400" },
};

function SummaryTab({ doc, corrections, pages, isProcessing, profile }: {
  doc: DocumentDetail;
  corrections: PatchListItem[];
  pages: PageListItem[];
  isProcessing: boolean;
  profile: StyleProfile | null;
}) {
  const ltCount = corrections.filter((c) => c.source === "languagetool").length;
  const llmCount = corrections.filter((c) => c.source.includes("chatgpt") || c.source === "llm").length;

  const categoryBreakdown = corrections.reduce<Record<string, number>>((acc, c) => {
    if (c.category) acc[c.category] = (acc[c.category] || 0) + 1;
    return acc;
  }, {});
  const hasCategories = Object.keys(categoryBreakdown).length > 0;

  const severityBreakdown = corrections.reduce<Record<string, number>>((acc, c) => {
    if (c.severity) acc[c.severity] = (acc[c.severity] || 0) + 1;
    return acc;
  }, {});

  const confidences = corrections.filter((c) => c.confidence != null).map((c) => c.confidence!);
  const avgConfidence = confidences.length > 0
    ? Math.round((confidences.reduce((a, b) => a + b, 0) / confidences.length) * 100)
    : null;

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      {/* Profile card */}
      {profile ? (
        <div className="glass-card rounded-xl p-5 md:col-span-2" style={{ borderColor: "rgba(212,255,0,0.1)" }}>
          <h3 className="text-sm font-semibold text-bruma uppercase tracking-wider mb-4">Perfil editorial</h3>
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-6 gap-4">
            <div>
              <span className="text-plomo-dark text-[10px] uppercase tracking-wider block mb-1">Preset</span>
              <span className="text-krypton font-semibold text-sm">{profile.preset_name || "Custom"}</span>
            </div>
            <div>
              <span className="text-plomo-dark text-[10px] uppercase tracking-wider block mb-1">Intervencion</span>
              <span className={`inline-flex px-2 py-0.5 rounded text-xs font-medium ${INTERVENTION_LABELS[profile.intervention_level]?.color || "bg-surface-elevated text-plomo"}`}>
                {INTERVENTION_LABELS[profile.intervention_level]?.label || profile.intervention_level}
              </span>
            </div>
            <div>
              <span className="text-plomo-dark text-[10px] uppercase tracking-wider block mb-1">Registro</span>
              <span className="text-bruma text-sm capitalize">{profile.register}</span>
            </div>
            <div>
              <span className="text-plomo-dark text-[10px] uppercase tracking-wider block mb-1">Tono</span>
              <span className="text-bruma text-sm capitalize">{profile.tone || "neutro"}</span>
            </div>
            <div>
              <span className="text-plomo-dark text-[10px] uppercase tracking-wider block mb-1">Audiencia</span>
              <span className="text-bruma text-sm capitalize">{profile.audience_type || "general"}</span>
            </div>
            <div>
              <span className="text-plomo-dark text-[10px] uppercase tracking-wider block mb-1">Max reescritura</span>
              <span className="text-bruma text-sm">{Math.round(profile.max_rewrite_ratio * 100)}%</span>
            </div>
          </div>
          {/* Protected terms & priorities */}
          <div className="mt-4 pt-3 border-t border-border-subtle flex flex-wrap gap-4">
            {profile.style_priorities && profile.style_priorities.length > 0 && (
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-plomo-dark text-[10px] uppercase tracking-wider">Prioridades:</span>
                {profile.style_priorities.map((p) => (
                  <span key={p} className="text-[10px] bg-krypton/10 text-krypton px-2 py-0.5 rounded">{p}</span>
                ))}
              </div>
            )}
            {profile.protected_terms && profile.protected_terms.length > 0 && (
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-plomo-dark text-[10px] uppercase tracking-wider">Protegidos:</span>
                {profile.protected_terms.map((t) => (
                  <span key={t} className="text-[10px] bg-purple-500/15 text-purple-400 px-2 py-0.5 rounded">{t}</span>
                ))}
              </div>
            )}
            {profile.preserve_author_voice && (
              <span className="text-[10px] bg-emerald-500/15 text-emerald-400 px-2 py-0.5 rounded">Preservar voz del autor</span>
            )}
          </div>
        </div>
      ) : (
        <div className="glass-card rounded-xl p-5 md:col-span-2">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-surface-hover flex items-center justify-center">
              <span className="text-plomo text-sm">—</span>
            </div>
            <div>
              <h3 className="text-sm font-semibold text-bruma">Sin perfil editorial</h3>
              <p className="text-xs text-plomo">Correccion generica (MVP1).</p>
            </div>
          </div>
        </div>
      )}

      {/* Processing status */}
      <div className="glass-card rounded-xl p-5">
        <h3 className="text-sm font-semibold text-bruma uppercase tracking-wider mb-4">Estado del proceso</h3>
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-sm text-plomo">Progreso general</span>
            <span className="text-sm font-mono text-krypton">{Math.round(doc.progress * 100)}%</span>
          </div>
          <div className="h-2 bg-surface-elevated rounded-full overflow-hidden">
            <div
              className="h-full bg-krypton rounded-full transition-all duration-500"
              style={{ width: `${Math.round(doc.progress * 100)}%` }}
            />
          </div>

          {isProcessing && (
            <div className="flex items-center gap-2 text-xs text-krypton mt-2">
              <span className="w-1.5 h-1.5 rounded-full bg-krypton animate-pulse-slow" />
              {doc.progress_detail?.message || "Procesando..."}
              {doc.progress_detail?.eta_seconds != null && doc.progress_detail.eta_seconds > 0 && (
                <span className="text-plomo ml-2">
                  ~{doc.progress_detail.eta_seconds < 60
                    ? `${Math.round(doc.progress_detail.eta_seconds)}s`
                    : `${Math.floor(doc.progress_detail.eta_seconds / 60)}m`}
                </span>
              )}
            </div>
          )}

          {doc.pages_summary && Object.keys(doc.pages_summary).length > 0 && (
            <div className="mt-4 pt-4 border-t border-border-subtle space-y-2">
              <span className="text-xs text-plomo-dark uppercase tracking-wider">Resumen de paginas</span>
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
      <div className="glass-card rounded-xl p-5">
        <h3 className="text-sm font-semibold text-bruma uppercase tracking-wider mb-4">Correcciones</h3>
        {corrections.length === 0 ? (
          <div className="text-center py-6 text-plomo text-sm">
            {isProcessing ? "Esperando correcciones..." : "Sin correcciones"}
          </div>
        ) : (
          <div className="space-y-4">
            <div className="flex gap-1 h-3 rounded-full overflow-hidden">
              {ltCount > 0 && (
                <div
                  className="bg-blue-500 transition-all duration-500 rounded-full"
                  style={{ width: `${(ltCount / corrections.length) * 100}%` }}
                />
              )}
              {llmCount > 0 && (
                <div
                  className="bg-purple-500 transition-all duration-500 rounded-full"
                  style={{ width: `${(llmCount / corrections.length) * 100}%` }}
                />
              )}
            </div>

            <div className="space-y-1.5">
              <div className="flex items-center justify-between text-sm">
                <div className="flex items-center gap-2">
                  <div className="w-2.5 h-2.5 rounded bg-blue-500" />
                  <span className="text-plomo">LanguageTool</span>
                </div>
                <span className="text-bruma font-medium">{ltCount}</span>
              </div>
              <div className="flex items-center justify-between text-sm">
                <div className="flex items-center gap-2">
                  <div className="w-2.5 h-2.5 rounded bg-purple-500" />
                  <span className="text-plomo">LLM (estilo)</span>
                </div>
                <span className="text-bruma font-medium">{llmCount}</span>
              </div>
            </div>

            {Object.keys(severityBreakdown).length > 0 && (
              <div className="pt-3 border-t border-border-subtle space-y-1.5">
                <span className="text-xs text-plomo-dark uppercase tracking-wider">Por severidad</span>
                {severityBreakdown.critico && (
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-red-400 text-xs">Critico</span>
                    <span className="text-bruma font-medium">{severityBreakdown.critico}</span>
                  </div>
                )}
                {severityBreakdown.importante && (
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-yellow-400 text-xs">Importante</span>
                    <span className="text-bruma font-medium">{severityBreakdown.importante}</span>
                  </div>
                )}
                {severityBreakdown.sugerencia && (
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-emerald-400 text-xs">Sugerencia</span>
                    <span className="text-bruma font-medium">{severityBreakdown.sugerencia}</span>
                  </div>
                )}
              </div>
            )}

            {avgConfidence != null && (
              <div className="pt-3 border-t border-border-subtle">
                <div className="flex items-center justify-between">
                  <span className="text-xs text-plomo-dark uppercase tracking-wider">Confianza promedio</span>
                  <span className={`text-sm font-semibold ${avgConfidence >= 80 ? "text-krypton" : avgConfidence >= 50 ? "text-yellow-400" : "text-red-400"}`}>
                    {avgConfidence}%
                  </span>
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Category breakdown */}
      {hasCategories && (
        <div className="glass-card rounded-xl p-5 md:col-span-2">
          <h3 className="text-sm font-semibold text-bruma uppercase tracking-wider mb-4">Correcciones por categoria</h3>
          <div className="grid grid-cols-3 sm:grid-cols-5 gap-3">
            {Object.entries(categoryBreakdown)
              .sort(([, a], [, b]) => b - a)
              .map(([cat, count]) => (
                <div key={cat} className="text-center bg-surface rounded-lg p-3 stat-card border border-border-subtle">
                  <div className={`w-3 h-3 rounded-full mx-auto mb-2 ${CATEGORY_COLORS[cat] || "bg-plomo"}`} />
                  <div className="text-lg font-bold text-bruma">{count}</div>
                  <div className="text-[10px] text-plomo-dark uppercase tracking-wider">{CATEGORY_LABELS[cat] || cat}</div>
                </div>
              ))}
          </div>
        </div>
      )}

      {/* Cost tracking */}
      {doc.total_tokens != null && doc.total_tokens > 0 && (
        <div className="glass-card rounded-xl p-5 md:col-span-2">
          <h3 className="text-sm font-semibold text-bruma uppercase tracking-wider mb-4">Costos de procesamiento</h3>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div className="bg-surface rounded-lg p-4 text-center border border-border-subtle stat-card">
              <div className="text-[10px] text-plomo-dark uppercase tracking-wider mb-1">Tokens entrada</div>
              <div className="text-lg font-bold text-bruma">{(doc.prompt_tokens ?? 0).toLocaleString("es")}</div>
            </div>
            <div className="bg-surface rounded-lg p-4 text-center border border-border-subtle stat-card">
              <div className="text-[10px] text-plomo-dark uppercase tracking-wider mb-1">Tokens salida</div>
              <div className="text-lg font-bold text-bruma">{(doc.completion_tokens ?? 0).toLocaleString("es")}</div>
            </div>
            <div className="bg-surface rounded-lg p-4 text-center border border-border-subtle stat-card">
              <div className="text-[10px] text-plomo-dark uppercase tracking-wider mb-1">Tokens total</div>
              <div className="text-lg font-bold text-krypton">{(doc.total_tokens ?? 0).toLocaleString("es")}</div>
            </div>
            <div className="bg-surface rounded-lg p-4 text-center border border-border-subtle stat-card">
              <div className="text-[10px] text-plomo-dark uppercase tracking-wider mb-1">Costo total</div>
              <div className="text-lg font-bold text-krypton">
                ${doc.llm_cost_usd != null ? doc.llm_cost_usd < 0.01 ? doc.llm_cost_usd.toFixed(6) : doc.llm_cost_usd.toFixed(4) : "0.00"}
              </div>
              <div className="text-[10px] text-plomo-dark mt-0.5">USD</div>
            </div>
          </div>
          {doc.total_pages != null && doc.total_pages > 0 && (
            <div className="mt-4 pt-3 border-t border-border-subtle flex items-center justify-between text-sm">
              <span className="text-plomo">Costo por pagina</span>
              <span className="text-bruma font-mono text-xs">
                ${doc.llm_cost_usd != null ? (doc.llm_cost_usd / doc.total_pages).toFixed(6) : "0.000000"} USD
              </span>
            </div>
          )}
          {corrections.length > 0 && (
            <div className="flex items-center justify-between text-sm mt-1">
              <span className="text-plomo">Costo por correccion</span>
              <span className="text-bruma font-mono text-xs">
                ${doc.llm_cost_usd != null ? (doc.llm_cost_usd / corrections.length).toFixed(6) : "0.000000"} USD
              </span>
            </div>
          )}
          <div className="mt-3 pt-3 border-t border-border-subtle">
            <a href="/costs" className="text-xs text-krypton hover:text-krypton/80 transition-colors">
              Ver detalle por parrafo en el panel de costos →
            </a>
          </div>
        </div>
      )}

      {/* Processing time */}
      {doc.processing_started_at && (
        <ProcessingTimeCard doc={doc} isProcessing={isProcessing} />
      )}

      {/* Document info */}
      <div className="glass-card rounded-xl p-5 md:col-span-2">
        <h3 className="text-sm font-semibold text-bruma uppercase tracking-wider mb-4">Informacion del documento</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
          <div>
            <span className="text-plomo-dark text-xs block mb-0.5">ID</span>
            <span className="text-bruma font-mono text-xs">{doc.id.slice(0, 8)}...</span>
          </div>
          <div>
            <span className="text-plomo-dark text-xs block mb-0.5">Formato</span>
            <span className="text-bruma">{doc.original_format.toUpperCase()}</span>
          </div>
          <div>
            <span className="text-plomo-dark text-xs block mb-0.5">Creado</span>
            <span className="text-bruma">
              {new Date(doc.created_at).toLocaleDateString("es", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" })}
            </span>
          </div>
          <div>
            <span className="text-plomo-dark text-xs block mb-0.5">Actualizado</span>
            <span className="text-bruma">
              {new Date(doc.updated_at).toLocaleDateString("es", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" })}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}

function formatDuration(seconds: number): string {
  if (seconds < 60) return `${Math.round(seconds)}s`;
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  return s > 0 ? `${m}m ${s}s` : `${m}m`;
}

const STAGE_LABELS: Record<string, string> = {
  A: "Conversion",
  B: "Extraccion",
  C: "Analisis",
  D: "Correccion",
  D_dispatch: "Despacho lotes",
  D_parallel: "Correccion paralela",
  E: "Renderizado",
};

const STAGE_COLORS: Record<string, string> = {
  A: "bg-blue-500",
  B: "bg-cyan-500",
  C: "bg-violet-500",
  D: "bg-krypton",
  D_dispatch: "bg-krypton/70",
  D_parallel: "bg-krypton",
  E: "bg-emerald-500",
};

function ProcessingTimeCard({ doc, isProcessing }: { doc: DocumentDetail; isProcessing: boolean }) {
  const startMs = doc.processing_started_at ? new Date(doc.processing_started_at).getTime() : null;
  const endMs = doc.processing_completed_at ? new Date(doc.processing_completed_at).getTime() : null;
  const totalSeconds = startMs && endMs ? (endMs - startMs) / 1000 : null;

  const timings = doc.stage_timings ?? {};
  const stageEntries = Object.entries(timings).filter(([, v]) => typeof v === "number" && v > 0);
  const maxTime = stageEntries.length > 0 ? Math.max(...stageEntries.map(([, v]) => v)) : 1;

  return (
    <div className="glass-card rounded-xl p-5 md:col-span-2">
      <h3 className="text-sm font-semibold text-bruma uppercase tracking-wider mb-4">Tiempos de procesamiento</h3>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-4">
        <div className="bg-surface rounded-lg p-3 text-center border border-border-subtle">
          <div className="text-[10px] text-plomo-dark uppercase tracking-wider mb-1">Tiempo total</div>
          <div className="text-xl font-bold text-krypton">
            {totalSeconds != null ? formatDuration(totalSeconds) : isProcessing ? "En curso..." : "—"}
          </div>
          {isProcessing && startMs && (
            <div className="text-[10px] text-plomo-dark mt-0.5">
              {formatDuration((Date.now() - startMs) / 1000)} transcurridos
            </div>
          )}
        </div>

        <div className="bg-surface rounded-lg p-3 text-center border border-border-subtle">
          <div className="text-[10px] text-plomo-dark uppercase tracking-wider mb-1">Worker</div>
          <div className="text-sm font-mono text-bruma truncate" title={doc.worker_hostname ?? undefined}>
            {doc.worker_hostname ?? "—"}
          </div>
        </div>

        <div className="bg-surface rounded-lg p-3 text-center border border-border-subtle">
          <div className="text-[10px] text-plomo-dark uppercase tracking-wider mb-1">Etapas</div>
          <div className="text-xl font-bold text-bruma">{stageEntries.length} / 5</div>
        </div>
      </div>

      {stageEntries.length > 0 && (
        <div className="space-y-2 pt-3 border-t border-border-subtle">
          <span className="text-xs text-plomo-dark uppercase tracking-wider">Desglose por etapa</span>
          {stageEntries
            .sort(([a], [b]) => {
              const order = ["A", "B", "C", "D", "D_dispatch", "D_parallel", "E"];
              return (order.indexOf(a) ?? 99) - (order.indexOf(b) ?? 99);
            })
            .map(([stage, secs]) => (
              <div key={stage} className="flex items-center gap-3">
                <span className="text-xs text-plomo w-32 flex-shrink-0">{STAGE_LABELS[stage] ?? stage}</span>
                <div className="flex-1 h-2 bg-surface-elevated rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full transition-all duration-700 ${STAGE_COLORS[stage] ?? "bg-bruma/40"}`}
                    style={{ width: `${Math.max(2, (secs / maxTime) * 100)}%` }}
                  />
                </div>
                <span className="text-xs font-mono text-bruma w-14 text-right flex-shrink-0">
                  {formatDuration(secs)}
                </span>
              </div>
            ))}
        </div>
      )}
    </div>
  );
}
