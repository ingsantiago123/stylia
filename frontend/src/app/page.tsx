"use client";

import { useState, useEffect, useCallback } from "react";
import { DocumentUploader } from "@/components/DocumentUploader";
import { DocumentList } from "@/components/DocumentList";
import { ProfileSelector } from "@/components/ProfileSelector";
import { listDocuments, DocumentListItem } from "@/lib/api";

export default function HomePage() {
  const [documents, setDocuments] = useState<DocumentListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [pendingDoc, setPendingDoc] = useState<{ id: string; filename: string } | null>(null);

  const fetchDocuments = useCallback(async () => {
    try {
      const docs = await listDocuments();
      setDocuments(docs);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error cargando documentos");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchDocuments();
    const getInterval = () => {
      const anyProcessing = documents.some(
        (d) => !["completed", "failed", "uploaded", "pending_review", "candidate_ready"].includes(d.status)
      );
      return anyProcessing ? 3000 : 15000;
    };
    let timer: ReturnType<typeof setTimeout>;
    const tick = () => {
      timer = setTimeout(async () => {
        await fetchDocuments();
        tick();
      }, getInterval());
    };
    tick();
    return () => clearTimeout(timer);
  }, [fetchDocuments, documents]);

  const handleUploadSuccess = () => fetchDocuments();
  const handleDocUploaded = (docId: string, filename: string) => {
    setPendingDoc({ id: docId, filename });
    fetchDocuments();
  };
  const handleProcessStarted = () => { setPendingDoc(null); fetchDocuments(); };
  const handleCancelProfile = () => { setPendingDoc(null); fetchDocuments(); };

  const processingCount = documents.filter(
    (d) => !["completed", "failed", "uploaded", "pending_review", "candidate_ready"].includes(d.status)
  ).length;
  const completedCount = documents.filter((d) => d.status === "completed").length;
  const failedCount = documents.filter((d) => d.status === "failed").length;
  const totalPages = documents.reduce((sum, d) => sum + (d.total_pages || 0), 0);

  return (
    <div className="space-y-8 animate-fade-in">
      {/* Stats bar */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="glass-card rounded-xl p-4 stat-card">
          <div className="flex items-center justify-between mb-2">
            <span className="text-[11px] font-medium uppercase tracking-wider text-plomo">Documentos</span>
            <div className="w-8 h-8 rounded-lg bg-krypton/10 flex items-center justify-center">
              <svg className="w-4 h-4 text-krypton" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
              </svg>
            </div>
          </div>
          <div className="text-2xl font-bold text-bruma">{documents.length}</div>
          <div className="text-xs text-plomo-dark mt-0.5">{totalPages} paginas total</div>
        </div>

        <div className="glass-card rounded-xl p-4 stat-card">
          <div className="flex items-center justify-between mb-2">
            <span className="text-[11px] font-medium uppercase tracking-wider text-plomo">En proceso</span>
            {processingCount > 0 && (
              <div className="w-2 h-2 rounded-full bg-krypton animate-pulse-slow" />
            )}
          </div>
          <div className={`text-2xl font-bold ${processingCount > 0 ? "text-krypton" : "text-bruma"}`}>
            {processingCount}
          </div>
          <div className="text-xs text-plomo-dark mt-0.5">
            {processingCount > 0 ? "procesando ahora" : "ninguno activo"}
          </div>
        </div>

        <div className="glass-card rounded-xl p-4 stat-card">
          <div className="flex items-center justify-between mb-2">
            <span className="text-[11px] font-medium uppercase tracking-wider text-plomo">Completados</span>
            <div className="w-8 h-8 rounded-lg bg-emerald-500/10 flex items-center justify-center">
              <svg className="w-4 h-4 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
          </div>
          <div className="text-2xl font-bold text-bruma">{completedCount}</div>
          <div className="text-xs text-plomo-dark mt-0.5">listos para descargar</div>
        </div>

        <div className="glass-card rounded-xl p-4 stat-card">
          <div className="flex items-center justify-between mb-2">
            <span className="text-[11px] font-medium uppercase tracking-wider text-plomo">Errores</span>
            {failedCount > 0 && (
              <div className="w-8 h-8 rounded-lg bg-red-500/10 flex items-center justify-center">
                <svg className="w-4 h-4 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
                </svg>
              </div>
            )}
          </div>
          <div className={`text-2xl font-bold ${failedCount > 0 ? "text-red-400" : "text-bruma"}`}>{failedCount}</div>
          <div className="text-xs text-plomo-dark mt-0.5">{failedCount > 0 ? "requieren atencion" : "sin errores"}</div>
        </div>
      </div>

      {/* Upload / Profile selector */}
      <section className="animate-fade-in-up" style={{ animationDelay: "0.1s" }}>
        <div className="flex items-center gap-3 mb-4">
          <div className="w-1 h-5 bg-krypton rounded-full" />
          <h2 className="text-sm font-semibold text-bruma uppercase tracking-wider">
            {pendingDoc ? "Configurar correccion" : "Nuevo documento"}
          </h2>
        </div>
        {pendingDoc ? (
          <ProfileSelector
            docId={pendingDoc.id}
            filename={pendingDoc.filename}
            onProcessStarted={handleProcessStarted}
            onCancel={handleCancelProfile}
          />
        ) : (
          <DocumentUploader
            onSuccess={handleUploadSuccess}
            onUploaded={handleDocUploaded}
          />
        )}
      </section>

      {/* Document list */}
      <section className="animate-fade-in-up" style={{ animationDelay: "0.2s" }}>
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <div className="w-1 h-5 bg-krypton rounded-full" />
            <h2 className="text-sm font-semibold text-bruma uppercase tracking-wider">Mis documentos</h2>
            {documents.length > 0 && (
              <span className="text-[11px] text-plomo bg-surface-elevated px-2 py-0.5 rounded-md font-mono">
                {documents.length}
              </span>
            )}
          </div>
          {processingCount > 0 && (
            <div className="flex items-center gap-2 text-xs text-krypton">
              <span className="w-1.5 h-1.5 rounded-full bg-krypton animate-pulse-slow" />
              {processingCount} en proceso
            </div>
          )}
        </div>

        {error && (
          <div className="glass-card rounded-xl px-4 py-3 mb-4 border-red-500/20 text-red-400 text-sm flex items-center gap-2">
            <svg className="w-4 h-4 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
            </svg>
            {error}
          </div>
        )}

        {loading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {[1, 2, 3].map((i) => (
              <div key={i} className="glass-card rounded-xl p-5 space-y-3">
                <div className="shimmer-bg h-4 w-3/4 rounded" />
                <div className="shimmer-bg h-3 w-1/2 rounded" />
                <div className="shimmer-bg h-24 w-full rounded-lg" />
              </div>
            ))}
          </div>
        ) : (
          <DocumentList documents={documents} onRefresh={fetchDocuments} />
        )}
      </section>
    </div>
  );
}
