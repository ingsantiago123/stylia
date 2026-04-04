"use client";

import Link from "next/link";
import { DocumentListItem, downloadPdf, downloadDocx, deleteDocument, getPagePreviewUrl } from "@/lib/api";
import { useState } from "react";

interface Props {
  documents: DocumentListItem[];
  onRefresh: () => void;
}

const PIPELINE_STAGES = ["uploaded", "converting", "extracting", "analyzing", "correcting", "rendering", "completed"];

const STATUS_CONFIG: Record<string, { label: string; color: string; iconColor: string }> = {
  uploaded:    { label: "Subido",        color: "text-plomo",   iconColor: "text-plomo" },
  converting:  { label: "Convirtiendo",  color: "text-krypton", iconColor: "text-krypton" },
  extracting:  { label: "Extrayendo",    color: "text-krypton", iconColor: "text-krypton" },
  analyzing:   { label: "Analizando",    color: "text-krypton", iconColor: "text-krypton" },
  correcting:  { label: "Corrigiendo",   color: "text-krypton", iconColor: "text-krypton" },
  rendering:   { label: "Renderizando",  color: "text-krypton", iconColor: "text-krypton" },
  completed:   { label: "Completado",    color: "text-emerald-400", iconColor: "text-emerald-400" },
  failed:      { label: "Error",         color: "text-red-400", iconColor: "text-red-400" },
};

// SVG circular progress ring component
function ProgressRing({ progress, size = 44, strokeWidth = 3, status }: {
  progress: number;
  size?: number;
  strokeWidth?: number;
  status: string;
}) {
  const radius = (size - strokeWidth) / 2;
  const circumference = radius * 2 * Math.PI;
  const offset = circumference - (progress * circumference);
  const isFailed = status === "failed";
  const isCompleted = status === "completed";

  return (
    <div className="relative flex items-center justify-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="absolute">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          className="progress-ring-track"
          strokeWidth={strokeWidth}
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          className={isFailed ? "progress-ring-fill-error" : "progress-ring-fill"}
          strokeWidth={strokeWidth}
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          strokeLinecap="round"
        />
      </svg>
      <span className={`text-[10px] font-bold ${isFailed ? "text-red-400" : isCompleted ? "text-emerald-400" : "text-krypton"}`}>
        {isFailed ? "!" : isCompleted ? (
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
          </svg>
        ) : `${Math.round(progress * 100)}%`}
      </span>
    </div>
  );
}

export function DocumentList({ documents, onRefresh }: Props) {
  if (documents.length === 0) {
    return (
      <div className="glass-card rounded-2xl text-center py-20 px-6">
        <div className="w-16 h-16 mx-auto mb-5 rounded-2xl bg-surface-hover flex items-center justify-center">
          <svg className="w-7 h-7 text-plomo" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
          </svg>
        </div>
        <p className="font-semibold text-bruma text-lg">Sin documentos</p>
        <p className="text-sm text-plomo mt-2 max-w-xs mx-auto">
          Sube tu primer archivo .docx para comenzar a corregir con IA
        </p>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      {documents.map((doc, i) => (
        <DocumentCard key={doc.id} doc={doc} onRefresh={onRefresh} index={i} />
      ))}
    </div>
  );
}

function DocumentCard({ doc, onRefresh, index }: {
  doc: DocumentListItem;
  onRefresh: () => void;
  index: number;
}) {
  const [deleting, setDeleting] = useState(false);
  const [showActions, setShowActions] = useState(false);
  const [imgError, setImgError] = useState(false);

  const statusInfo = STATUS_CONFIG[doc.status] || { label: doc.status, color: "text-plomo", iconColor: "text-plomo" };
  const isProcessing = !["completed", "failed", "uploaded"].includes(doc.status);
  const isCompleted = doc.status === "completed";
  const isFailed = doc.status === "failed";
  const currentStageIndex = PIPELINE_STAGES.indexOf(doc.status);
  const hasPreview = doc.total_pages && doc.total_pages > 0 && (isCompleted || doc.status === "rendering" || doc.status === "correcting" || doc.status === "analyzing");

  const handleDelete = async () => {
    if (!confirm(`Eliminar "${doc.filename}"?`)) return;
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
    <div
      className="glass-card glass-card-hover rounded-xl overflow-hidden transition-all duration-300 group animate-fade-in-up relative"
      style={{ animationDelay: `${index * 0.05}s` }}
      onMouseEnter={() => setShowActions(true)}
      onMouseLeave={() => setShowActions(false)}
    >
      {/* Document preview thumbnail */}
      <Link href={`/documents/${doc.id}`} className="block">
        <div className="relative h-36 bg-carbon-300 overflow-hidden">
          {hasPreview && !imgError ? (
            <img
              src={getPagePreviewUrl(doc.id, 1)}
              alt={`Preview ${doc.filename}`}
              className="w-full h-full object-cover object-top opacity-60 group-hover:opacity-80 transition-opacity duration-300"
              onError={() => setImgError(true)}
            />
          ) : (
            <div className="w-full h-full flex items-center justify-center">
              <div className="text-center">
                <svg className="w-10 h-10 text-plomo-dark/50 mx-auto" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
                </svg>
                <span className="text-[10px] text-plomo-dark/40 uppercase tracking-wider mt-1 block">
                  {doc.original_format}
                </span>
              </div>
            </div>
          )}

          {/* Gradient overlay */}
          <div className="absolute inset-0 bg-gradient-to-t from-carbon-300 via-transparent to-transparent" />

          {/* Status badge overlay */}
          <div className="absolute top-3 left-3">
            <span className={`
              inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[11px] font-medium backdrop-blur-md
              ${isCompleted ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/20" :
                isFailed ? "bg-red-500/20 text-red-300 border border-red-500/20" :
                isProcessing ? "bg-krypton/15 text-krypton border border-krypton/20" :
                "bg-surface/60 text-plomo border border-border"}
            `}>
              {isProcessing && <span className="w-1.5 h-1.5 rounded-full bg-current animate-pulse-slow" />}
              {statusInfo.label}
            </span>
          </div>

          {/* Progress ring overlay */}
          {(isProcessing || isCompleted || isFailed) && doc.status !== "uploaded" && (
            <div className="absolute top-3 right-3">
              <div className="bg-carbon/60 backdrop-blur-md rounded-full p-0.5">
                <ProgressRing progress={doc.progress} size={38} strokeWidth={2.5} status={doc.status} />
              </div>
            </div>
          )}

          {/* Page count */}
          {doc.total_pages && (
            <div className="absolute bottom-3 right-3 flex items-center gap-1 text-[10px] text-bruma-muted bg-carbon/50 backdrop-blur-sm px-2 py-0.5 rounded">
              <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
              </svg>
              {doc.total_pages} pag.
            </div>
          )}
        </div>
      </Link>

      {/* Card body */}
      <div className="p-4">
        <Link href={`/documents/${doc.id}`} className="block group/title">
          <h3 className="font-semibold text-sm text-bruma truncate group-hover/title:text-krypton transition-colors">
            {doc.filename}
          </h3>
        </Link>

        <div className="flex items-center gap-3 mt-1.5 text-[11px] text-plomo">
          <span className="uppercase font-medium tracking-wider">{doc.original_format}</span>
          <span className="text-plomo-dark">
            {new Date(doc.created_at).toLocaleDateString("es", {
              day: "numeric",
              month: "short",
              hour: "2-digit",
              minute: "2-digit",
            })}
          </span>
        </div>

        {/* Mini pipeline stages */}
        {isProcessing && (
          <div className="mt-3 space-y-1.5">
            <div className="flex items-center justify-between text-[10px]">
              <span className="text-plomo">
                {doc.progress_detail?.message || `${statusInfo.label}...`}
              </span>
              {doc.progress_detail?.eta_seconds != null && doc.progress_detail.eta_seconds > 0 && (
                <span className="text-plomo-dark">
                  ~{doc.progress_detail.eta_seconds < 60
                    ? `${Math.round(doc.progress_detail.eta_seconds)}s`
                    : `${Math.floor(doc.progress_detail.eta_seconds / 60)}m`}
                </span>
              )}
            </div>
            <div className="flex items-center gap-0.5">
              {PIPELINE_STAGES.slice(0, -1).map((stage, i) => (
                <div key={stage} className="flex-1">
                  <div className={`
                    h-1 rounded-full transition-all duration-500
                    ${i < currentStageIndex ? "bg-krypton" :
                      i === currentStageIndex
                        ? doc.progress_detail?.is_stalled ? "bg-amber-400" : "bg-krypton/60 animate-pulse-slow"
                        : "bg-border"}
                  `} />
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Completed — download actions */}
        {isCompleted && (
          <div className="mt-3 flex items-center gap-2">
            <button
              onClick={() => downloadPdf(doc.id)}
              className="flex-1 flex items-center justify-center gap-1.5 px-3 py-1.5 bg-krypton text-carbon text-xs font-semibold rounded-lg hover:bg-krypton-200 transition-colors"
            >
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3" />
              </svg>
              PDF
            </button>
            <button
              onClick={() => downloadDocx(doc.id)}
              className="flex-1 flex items-center justify-center gap-1.5 px-3 py-1.5 border border-krypton/30 text-krypton text-xs font-medium rounded-lg hover:bg-krypton/10 transition-colors"
            >
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3" />
              </svg>
              DOCX
            </button>
          </div>
        )}

        {/* Error message */}
        {isFailed && (
          <div className="mt-3 flex items-center gap-2 text-[11px] text-red-400 bg-red-500/10 border border-red-500/10 px-2.5 py-1.5 rounded-lg">
            <svg className="w-3.5 h-3.5 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
            </svg>
            Error en procesamiento
          </div>
        )}
      </div>

      {/* Hover delete action */}
      <button
        onClick={handleDelete}
        disabled={deleting}
        className={`
          absolute top-3 right-3 p-1.5 rounded-lg bg-carbon/60 backdrop-blur-md text-plomo-dark hover:text-red-400 hover:bg-red-500/20
          transition-all duration-200 disabled:opacity-50
          ${showActions && !isProcessing && doc.status !== "uploaded" ? "opacity-0 group-hover:opacity-100" : "opacity-0 pointer-events-none"}
        `}
        title="Eliminar"
        style={{ zIndex: 10 }}
      >
        <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0" />
        </svg>
      </button>
    </div>
  );
}
