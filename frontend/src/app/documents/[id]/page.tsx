"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  getDocument,
  getDocumentCorrections,
  listPages,
  getProfile,
  downloadPdf,
  downloadDocx,
  DocumentDetail,
  PatchListItem,
  PageListItem,
  StyleProfile,
} from "@/lib/api";
import { PipelineFlow } from "@/components/PipelineFlow";
import { CorrectionHistory } from "@/components/CorrectionHistory";
import { CorrectionFlowViewer } from "@/components/CorrectionFlowViewer";
import { DiffCompareView } from "@/components/DiffCompareView";

type Tab = "pipeline" | "corrections" | "pages" | "api-flow";

export default function DocumentDetailPage() {
  const params = useParams();
  const router = useRouter();
  const docId = params.id as string;

  const [doc, setDoc] = useState<DocumentDetail | null>(null);
  const [corrections, setCorrections] = useState<PatchListItem[]>([]);
  const [pages, setPages] = useState<PageListItem[]>([]);
  const [profile, setProfile] = useState<StyleProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<Tab>("pipeline");

  const fetchData = useCallback(async () => {
    try {
      const [docData, correctionsData, pagesData, profileData] = await Promise.all([
        getDocument(docId),
        getDocumentCorrections(docId).catch(() => []),
        listPages(docId).catch(() => []),
        getProfile(docId).catch(() => null),
      ]);
      setDoc(docData);
      setCorrections(correctionsData);
      setPages(pagesData);
      setProfile(profileData);
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
          { key: "pages" as Tab, label: `Comparar (${corrections.length})`, icon: "▣" },
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
        <SummaryTab doc={doc} corrections={corrections} pages={pages} isProcessing={isProcessing} profile={profile} />
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
                <h3 className="text-sm font-semibold text-bruma mb-1">Flujo de corrección</h3>
                <p className="text-xs text-plomo">
                  Muestra cómo se procesó cada párrafo: LanguageTool (ortografía) → LLM (estilo con contexto acumulado).
                  {profile ? " Cada petición al LLM usa el perfil editorial para parametrizar el prompt." : " Sin perfil editorial — prompt genérico."}
                </p>
              </div>
            </div>
          </div>

          {/* Profile prompt preview */}
          {profile && (
            <div className="bg-carbon-100 border border-krypton/20 rounded-xl p-5">
              <h3 className="text-sm font-semibold text-bruma uppercase tracking-wider mb-3">Configuración del prompt LLM</h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <span className="text-[10px] text-plomo uppercase tracking-wider block mb-2">Parámetros del perfil enviados al LLM</span>
                  <div className="bg-carbon-200 border border-carbon-300 rounded-lg px-4 py-3 text-xs font-mono text-bruma/80 space-y-1">
                    <div>PERFIL: <span className="text-krypton">{profile.register}</span> | Intervención: <span className="text-krypton">{profile.intervention_level}</span></div>
                    <div>Audiencia: <span className="text-krypton">{profile.audience_type || "general"}</span> ({profile.audience_expertise})</div>
                    <div>Tono: <span className="text-krypton">{profile.tone || "neutro"}</span></div>
                    <div>Preservar voz: <span className="text-krypton">{profile.preserve_author_voice ? "sí" : "no"}</span></div>
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
                  <div className="bg-carbon-200 border border-carbon-300 rounded-lg px-4 py-3 text-xs text-bruma/70 space-y-1">
                    <p>El LLM recibe un system prompt estático con:</p>
                    <ul className="list-disc list-inside space-y-0.5 text-plomo">
                      <li>Reglas de corrección (no cambiar significado, respetar intervención)</li>
                      <li>9 categorías de cambios (redundancia, claridad, léxico...)</li>
                      <li>3 niveles de severidad (crítico, importante, sugerencia)</li>
                      <li>Schema JSON de respuesta estructurada</li>
                      <li>Ejemplos de corrección y de no-corrección</li>
                    </ul>
                    <p className="mt-2 text-plomo">Cada párrafo se envía con el perfil codificado + contexto del párrafo anterior.</p>
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

const CATEGORY_LABELS: Record<string, string> = {
  redundancia: "Redundancia",
  claridad: "Claridad",
  registro: "Registro",
  cohesion: "Cohesión",
  lexico: "Léxico",
  estructura: "Estructura",
  puntuacion: "Puntuación",
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
  minima: { label: "Mínima", color: "bg-emerald-900/30 text-emerald-400" },
  sutil: { label: "Sutil", color: "bg-blue-900/30 text-blue-400" },
  moderada: { label: "Moderada", color: "bg-yellow-900/30 text-yellow-400" },
  agresiva: { label: "Agresiva", color: "bg-red-900/30 text-red-400" },
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

  // Category breakdown
  const categoryBreakdown = corrections.reduce<Record<string, number>>((acc, c) => {
    if (c.category) {
      acc[c.category] = (acc[c.category] || 0) + 1;
    }
    return acc;
  }, {});
  const hasCategories = Object.keys(categoryBreakdown).length > 0;

  // Severity breakdown
  const severityBreakdown = corrections.reduce<Record<string, number>>((acc, c) => {
    if (c.severity) {
      acc[c.severity] = (acc[c.severity] || 0) + 1;
    }
    return acc;
  }, {});

  // Average confidence
  const confidences = corrections.filter((c) => c.confidence != null).map((c) => c.confidence!);
  const avgConfidence = confidences.length > 0
    ? Math.round((confidences.reduce((a, b) => a + b, 0) / confidences.length) * 100)
    : null;

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      {/* Profile card */}
      {profile ? (
        <div className="bg-carbon-100 border border-krypton/20 rounded-xl p-5 md:col-span-2">
          <h3 className="text-sm font-semibold text-bruma uppercase tracking-wider mb-4">Perfil editorial</h3>
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-6 gap-4">
            <div>
              <span className="text-plomo text-[10px] uppercase tracking-wider block mb-1">Preset</span>
              <span className="text-krypton font-semibold text-sm">{profile.preset_name || "Custom"}</span>
            </div>
            <div>
              <span className="text-plomo text-[10px] uppercase tracking-wider block mb-1">Intervención</span>
              <span className={`inline-flex px-2 py-0.5 rounded text-xs font-medium ${INTERVENTION_LABELS[profile.intervention_level]?.color || "bg-carbon-200 text-plomo"}`}>
                {INTERVENTION_LABELS[profile.intervention_level]?.label || profile.intervention_level}
              </span>
            </div>
            <div>
              <span className="text-plomo text-[10px] uppercase tracking-wider block mb-1">Registro</span>
              <span className="text-bruma text-sm capitalize">{profile.register}</span>
            </div>
            <div>
              <span className="text-plomo text-[10px] uppercase tracking-wider block mb-1">Tono</span>
              <span className="text-bruma text-sm capitalize">{profile.tone || "neutro"}</span>
            </div>
            <div>
              <span className="text-plomo text-[10px] uppercase tracking-wider block mb-1">Audiencia</span>
              <span className="text-bruma text-sm capitalize">{profile.audience_type || "general"}</span>
            </div>
            <div>
              <span className="text-plomo text-[10px] uppercase tracking-wider block mb-1">Max reescritura</span>
              <span className="text-bruma text-sm">{Math.round(profile.max_rewrite_ratio * 100)}%</span>
            </div>
          </div>
          {/* Protected terms & priorities */}
          <div className="mt-4 pt-3 border-t border-carbon-300 flex flex-wrap gap-4">
            {profile.style_priorities && profile.style_priorities.length > 0 && (
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-plomo text-[10px] uppercase tracking-wider">Prioridades:</span>
                {profile.style_priorities.map((p) => (
                  <span key={p} className="text-[10px] bg-krypton/10 text-krypton px-2 py-0.5 rounded">{p}</span>
                ))}
              </div>
            )}
            {profile.protected_terms && profile.protected_terms.length > 0 && (
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-plomo text-[10px] uppercase tracking-wider">Protegidos:</span>
                {profile.protected_terms.map((t) => (
                  <span key={t} className="text-[10px] bg-purple-900/20 text-purple-400 px-2 py-0.5 rounded">{t}</span>
                ))}
              </div>
            )}
            {profile.preserve_author_voice && (
              <span className="text-[10px] bg-emerald-900/20 text-emerald-400 px-2 py-0.5 rounded">Preservar voz del autor</span>
            )}
          </div>
        </div>
      ) : (
        <div className="bg-carbon-100 border border-carbon-300 rounded-xl p-5 md:col-span-2">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-carbon-200 flex items-center justify-center">
              <span className="text-plomo text-sm">—</span>
            </div>
            <div>
              <h3 className="text-sm font-semibold text-bruma">Sin perfil editorial</h3>
              <p className="text-xs text-plomo">Corrección genérica (MVP1). Selecciona un perfil para obtener correcciones categorizadas.</p>
            </div>
          </div>
        </div>
      )}

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
            {/* Source breakdown bar */}
            <div className="flex gap-1 h-3 rounded-full overflow-hidden">
              {ltCount > 0 && (
                <div
                  className="bg-blue-500 transition-all duration-500"
                  style={{ width: `${(ltCount / corrections.length) * 100}%` }}
                  title={`LanguageTool: ${ltCount}`}
                />
              )}
              {llmCount > 0 && (
                <div
                  className="bg-purple-500 transition-all duration-500"
                  style={{ width: `${(llmCount / corrections.length) * 100}%` }}
                  title={`LLM: ${llmCount}`}
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

            {/* Severity breakdown */}
            {Object.keys(severityBreakdown).length > 0 && (
              <div className="pt-3 border-t border-carbon-300 space-y-1.5">
                <span className="text-xs text-plomo uppercase tracking-wider">Por severidad</span>
                {severityBreakdown.critico && (
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-red-400 text-xs">Crítico</span>
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

            {/* Confidence */}
            {avgConfidence != null && (
              <div className="pt-3 border-t border-carbon-300">
                <div className="flex items-center justify-between">
                  <span className="text-xs text-plomo uppercase tracking-wider">Confianza promedio</span>
                  <span className={`text-sm font-semibold ${avgConfidence >= 80 ? "text-krypton" : avgConfidence >= 50 ? "text-yellow-400" : "text-red-400"}`}>
                    {avgConfidence}%
                  </span>
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Category breakdown — full width */}
      {hasCategories && (
        <div className="bg-carbon-100 border border-carbon-300 rounded-xl p-5 md:col-span-2">
          <h3 className="text-sm font-semibold text-bruma uppercase tracking-wider mb-4">Correcciones por categoría</h3>
          <div className="grid grid-cols-3 sm:grid-cols-5 gap-3">
            {Object.entries(categoryBreakdown)
              .sort(([, a], [, b]) => b - a)
              .map(([cat, count]) => (
                <div key={cat} className="text-center bg-carbon-200 rounded-lg p-3">
                  <div className={`w-3 h-3 rounded-full mx-auto mb-2 ${CATEGORY_COLORS[cat] || "bg-plomo"}`} />
                  <div className="text-lg font-bold text-bruma">{count}</div>
                  <div className="text-[10px] text-plomo uppercase tracking-wider">{CATEGORY_LABELS[cat] || cat}</div>
                </div>
              ))}
          </div>
        </div>
      )}

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

