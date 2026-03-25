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

  // MVP2: documento pendiente de asignar perfil
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
    const interval = setInterval(() => {
      fetchDocuments();
    }, 5000);
    return () => clearInterval(interval);
  }, [fetchDocuments]);

  const handleUploadSuccess = () => {
    fetchDocuments();
  };

  const handleDocUploaded = (docId: string, filename: string) => {
    setPendingDoc({ id: docId, filename });
    fetchDocuments();
  };

  const handleProcessStarted = () => {
    setPendingDoc(null);
    fetchDocuments();
  };

  const handleCancelProfile = () => {
    setPendingDoc(null);
    fetchDocuments();
  };

  const processingCount = documents.filter(
    (d) => !["completed", "failed", "uploaded"].includes(d.status)
  ).length;

  return (
    <div className="space-y-10">
      {/* Hero section */}
      <section className="text-center py-4">
        <h1 className="text-3xl font-bold text-bruma tracking-tight">
          Panel de control
        </h1>
        <p className="text-plomo mt-2 text-sm">
          Sube documentos, monitorea el proceso de corrección en tiempo real
        </p>
        {processingCount > 0 && (
          <div className="mt-4 inline-flex items-center gap-2 bg-krypton/10 text-krypton px-4 py-2 rounded-full text-sm font-medium">
            <span className="w-2 h-2 rounded-full bg-krypton animate-pulse-slow" />
            {processingCount} documento{processingCount > 1 ? "s" : ""} en proceso
          </div>
        )}
      </section>

      {/* Sección de subida / selector de perfil */}
      <section>
        <div className="flex items-center gap-3 mb-4">
          <div className="w-1 h-6 bg-krypton rounded-full" />
          <h2 className="text-lg font-semibold text-bruma">
            {pendingDoc ? "Configurar correccion" : "Subir documento"}
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

      {/* Lista de documentos */}
      <section>
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <div className="w-1 h-6 bg-krypton rounded-full" />
            <h2 className="text-lg font-semibold text-bruma">Documentos</h2>
            {documents.length > 0 && (
              <span className="text-xs text-plomo bg-carbon-200 px-2.5 py-1 rounded-full">
                {documents.length}
              </span>
            )}
          </div>
        </div>
        {error && (
          <div className="bg-red-900/30 border border-red-500/30 text-red-400 px-4 py-3 rounded-lg mb-4 text-sm">
            {error}
          </div>
        )}
        {loading ? (
          <div className="text-plomo text-sm py-12 text-center">
            <div className="inline-flex items-center gap-2">
              <svg className="animate-spin h-4 w-4 text-krypton" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
              Cargando documentos...
            </div>
          </div>
        ) : (
          <DocumentList
            documents={documents}
            onRefresh={fetchDocuments}
          />
        )}
      </section>
    </div>
  );
}
