"use client";

import Link from "next/link";
import { DocumentListItem, downloadPdf, downloadDocx, deleteDocument } from "@/lib/api";
import { useState } from "react";

interface Props {
  documents: DocumentListItem[];
  onRefresh: () => void;
}

const PIPELINE_STAGES = ["uploaded", "converting", "extracting", "correcting", "rendering", "completed"];

const STATUS_CONFIG: Record<string, { label: string; icon: string; color: string }> = {
  uploaded:    { label: "Subido",        icon: "↑", color: "bg-carbon-200 text-plomo" },
  converting:  { label: "Convirtiendo",  icon: "⟳", color: "bg-krypton/15 text-krypton" },
  extracting:  { label: "Extrayendo",    icon: "◎", color: "bg-krypton/15 text-krypton" },
  correcting:  { label: "Corrigiendo",   icon: "✎", color: "bg-krypton/15 text-krypton" },
  rendering:   { label: "Renderizando",  icon: "▣", color: "bg-krypton/15 text-krypton" },
  completed:   { label: "Completado",    icon: "✓", color: "bg-krypton/20 text-krypton" },
  failed:      { label: "Error",         icon: "✕", color: "bg-red-900/30 text-red-400" },
};

export function DocumentList({ documents, onRefresh }: Props) {
  if (documents.length === 0) {
    return (
      <div className="text-center py-16 text-plomo">
        <div className="w-16 h-16 mx-auto mb-4 rounded-2xl bg-carbon-200 flex items-center justify-center">
          <svg className="w-7 h-7 text-plomo" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
          </svg>
        </div>
        <p className="font-medium text-bruma">Sin documentos</p>
        <p className="text-sm mt-1">Sube tu primer archivo para comenzar</p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {documents.map((doc) => (
        <DocumentCard key={doc.id} doc={doc} onRefresh={onRefresh} />
      ))}
    </div>
  );
}

function DocumentCard({
  doc,
  onRefresh,
}: {
  doc: DocumentListItem;
  onRefresh: () => void;
}) {
  const [deleting, setDeleting] = useState(false);

  const statusInfo = STATUS_CONFIG[doc.status] || {
    label: doc.status,
    icon: "?",
    color: "bg-carbon-200 text-plomo",
  };

  const isProcessing = !["completed", "failed", "uploaded"].includes(doc.status);
  const progressPercent = Math.round(doc.progress * 100);

  // Calculate stage index for mini pipeline
  const currentStageIndex = PIPELINE_STAGES.indexOf(doc.status);

  const handleDownloadPdf = () => {
    downloadPdf(doc.id);
  };

  const handleDownloadDocx = () => {
    downloadDocx(doc.id);
  };

  const handleDelete = async () => {
    if (!confirm(`¿Eliminar "${doc.filename}"?`)) return;
    setDeleting(true);
    try {
      await deleteDocument(doc.id);
      onRefresh();
    } catch {
      alert("Error al eliminar documento");
    } finally {
      setDeleting(false);
    }
  };

  return (
    <div className="bg-carbon-100 border border-carbon-300 rounded-xl px-5 py-4 hover:border-krypton/30 transition-all duration-300 group">
      <div className="flex items-center justify-between gap-4">
        {/* Info principal */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-3 mb-1.5">
            <Link
              href={`/documents/${doc.id}`}
              className="font-medium text-bruma truncate hover:text-krypton transition-colors"
            >
              {doc.filename}
            </Link>
            <span className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium ${statusInfo.color}`}>
              <span>{statusInfo.icon}</span>
              {statusInfo.label}
            </span>
          </div>
          <div className="flex items-center gap-4 text-sm text-plomo">
            <span className="uppercase text-xs font-medium tracking-wider">{doc.original_format}</span>
            {doc.total_pages && (
              <span className="flex items-center gap-1">
                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
                </svg>
                {doc.total_pages} págs.
              </span>
            )}
            <span>
              {new Date(doc.created_at).toLocaleDateString("es", {
                day: "numeric",
                month: "short",
                hour: "2-digit",
                minute: "2-digit",
              })}
            </span>
          </div>
        </div>

        {/* Acciones */}
        <div className="flex items-center gap-2 flex-shrink-0">
          {doc.status === "completed" && (
            <>
              <button
                onClick={handleDownloadPdf}
                className="px-3 py-1.5 bg-krypton text-carbon text-sm font-semibold rounded-lg hover:bg-krypton/90 transition-colors"
              >
                PDF
              </button>
              <button
                onClick={handleDownloadDocx}
                className="px-3 py-1.5 border border-krypton/40 text-krypton text-sm font-medium rounded-lg hover:bg-krypton/10 transition-colors"
              >
                DOCX
              </button>
            </>
          )}
          <button
            onClick={handleDelete}
            disabled={deleting}
            className="px-3 py-1.5 text-sm text-plomo hover:text-red-400 hover:bg-red-900/20 rounded-lg disabled:opacity-50 transition-colors"
          >
            Eliminar
          </button>
        </div>
      </div>

      {/* Mini pipeline progress */}
      {isProcessing && (
        <div className="mt-3">
          <div className="flex items-center justify-between text-xs text-plomo mb-2">
            <span>{statusInfo.label}...</span>
            <span className="text-krypton font-medium">{progressPercent}%</span>
          </div>
          {/* Stage dots */}
          <div className="flex items-center gap-1">
            {PIPELINE_STAGES.slice(0, -1).map((stage, i) => (
              <div key={stage} className="flex-1 flex items-center">
                <div className={`
                  h-1.5 w-full rounded-full transition-all duration-500
                  ${i < currentStageIndex ? "bg-krypton" : i === currentStageIndex ? "bg-krypton animate-pulse-slow" : "bg-carbon-300"}
                `} />
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Completed indicator */}
      {doc.status === "completed" && (
        <div className="mt-3 flex items-center gap-2 text-xs text-krypton/70">
          <div className="flex-1 h-1.5 bg-krypton/30 rounded-full">
            <div className="h-full bg-krypton rounded-full w-full" />
          </div>
          <span>Listo</span>
        </div>
      )}

      {/* Error */}
      {doc.status === "failed" && (
        <div className="mt-3 flex items-center gap-2 text-sm text-red-400 bg-red-900/20 border border-red-500/20 px-3 py-2 rounded-lg">
          <svg className="w-4 h-4 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
          </svg>
          Error en el procesamiento. Intenta de nuevo.
        </div>
      )}
    </div>
  );
}
