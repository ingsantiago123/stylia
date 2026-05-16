"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { listDocuments, DocumentListItem } from "@/lib/api";

function AuditDocCard({ doc }: { doc: DocumentListItem }) {
  const isCompleted = doc.status === "completed";
  return (
    <Link
      href={`/audit/${doc.id}`}
      className="group glass-card glass-card-hover rounded-2xl p-5 flex flex-col gap-3 transition-all duration-200 hover:shadow-card-hover"
    >
      {/* Header */}
      <div className="flex items-start gap-3">
        <div className="w-9 h-9 rounded-xl bg-krypton/10 border border-krypton/20 flex items-center justify-center shrink-0 group-hover:bg-krypton/20 transition-colors">
          <svg className="w-4.5 h-4.5 text-krypton" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h3.75M9 15h3.75M9 18h3.75m3 .75H18a2.25 2.25 0 002.25-2.25V6.108c0-1.135-.845-2.098-1.976-2.192a48.424 48.424 0 00-1.123-.08m-5.801 0c-.065.21-.1.433-.1.664 0 .414.336.75.75.75h4.5a.75.75 0 00.75-.75 2.25 2.25 0 00-.1-.664m-5.8 0A2.251 2.251 0 0113.5 2.25H15c1.012 0 1.867.668 2.15 1.586m-5.8 0c-.376.023-.75.05-1.124.08C9.095 4.01 8.25 4.973 8.25 6.108V8.25m0 0H4.875c-.621 0-1.125.504-1.125 1.125v11.25c0 .621.504 1.125 1.125 1.125h9.75c.621 0 1.125-.504 1.125-1.125V9.375c0-.621-.504-1.125-1.125-1.125H8.25zM6.75 12h.008v.008H6.75V12zm0 3h.008v.008H6.75V15zm0 3h.008v.008H6.75V18z" />
          </svg>
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-semibold text-bruma truncate group-hover:text-krypton transition-colors">
            {doc.filename}
          </p>
          <p className="text-[11px] text-plomo mt-0.5">
            {new Date(doc.created_at).toLocaleDateString("es", {
              day: "numeric", month: "short", year: "numeric",
            })}
          </p>
        </div>
        <svg className="w-4 h-4 text-plomo group-hover:text-krypton group-hover:translate-x-0.5 transition-all shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" />
        </svg>
      </div>

      {/* Meta */}
      <div className="flex items-center gap-2 flex-wrap">
        <span className={[
          "badge",
          isCompleted
            ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
            : "bg-krypton/10 text-krypton border border-krypton/20",
        ].join(" ")}>
          {isCompleted ? "Completado" : "Listo para revisión"}
        </span>
        {doc.total_pages != null && (
          <span className="badge bg-surface-elevated text-plomo border border-border">
            {doc.total_pages} pág.
          </span>
        )}
      </div>

      {/* CTA label */}
      <p className="text-[11px] text-plomo-dark group-hover:text-plomo transition-colors">
        Ver trazabilidad de llamadas LLM →
      </p>
    </Link>
  );
}

export default function AuditPage() {
  const [docs, setDocs] = useState<DocumentListItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    listDocuments()
      .then((d) =>
        setDocs(d.filter((doc) => ["completed", "candidate_ready"].includes(doc.status)))
      )
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="space-y-8 animate-fade-in">
      {/* Page header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-[10px] font-mono text-krypton uppercase tracking-widest mb-1">
            STYLIA / AUDIT
          </p>
          <h1 className="text-heading-2 text-bruma text-balance">Auditoría LLM</h1>
          <p className="text-sm text-plomo mt-2 max-w-lg leading-relaxed">
            Trazabilidad total de cada llamada al LLM: payload RAW, doble pasada,
            reversiones detectadas y ADN editorial por documento.
          </p>
        </div>

        {/* Capability pills */}
        <div className="hidden lg:flex flex-col gap-1.5 shrink-0">
          {["Payload RAW", "Doble pasada", "Reversiones", "ADN editorial"].map((cap) => (
            <span key={cap} className="badge bg-krypton/8 text-krypton border border-krypton/15 text-[10px]">
              {cap}
            </span>
          ))}
        </div>
      </div>

      {/* Loading */}
      {loading && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {[1, 2, 3].map((i) => (
            <div key={i} className="glass-card rounded-2xl p-5 space-y-3">
              <div className="shimmer-bg h-4 w-3/4 rounded" />
              <div className="shimmer-bg h-3 w-1/2 rounded" />
              <div className="shimmer-bg h-6 w-1/3 rounded" />
            </div>
          ))}
        </div>
      )}

      {/* Empty state */}
      {!loading && docs.length === 0 && (
        <div className="glass-card rounded-2xl p-12 text-center max-w-md mx-auto">
          <div className="w-14 h-14 mx-auto mb-4 rounded-2xl bg-surface-elevated border border-border flex items-center justify-center">
            <svg className="w-6 h-6 text-plomo" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h3.75M9 15h3.75M9 18h3.75m3 .75H18a2.25 2.25 0 002.25-2.25V6.108c0-1.135-.845-2.098-1.976-2.192a48.424 48.424 0 00-1.123-.08m-5.801 0c-.065.21-.1.433-.1.664 0 .414.336.75.75.75h4.5a.75.75 0 00.75-.75 2.25 2.25 0 00-.1-.664m-5.8 0A2.251 2.251 0 0113.5 2.25H15c1.012 0 1.867.668 2.15 1.586m-5.8 0c-.376.023-.75.05-1.124.08C9.095 4.01 8.25 4.973 8.25 6.108V8.25m0 0H4.875c-.621 0-1.125.504-1.125 1.125v11.25c0 .621.504 1.125 1.125 1.125h9.75c.621 0 1.125-.504 1.125-1.125V9.375c0-.621-.504-1.125-1.125-1.125H8.25zM6.75 12h.008v.008H6.75V12zm0 3h.008v.008H6.75V15zm0 3h.008v.008H6.75V18z" />
            </svg>
          </div>
          <p className="text-bruma font-semibold mb-1">Sin datos de auditoría</p>
          <p className="text-plomo text-sm mb-5">
            Procesa un documento con el pipeline actual para ver la trazabilidad LLM.
          </p>
          <Link
            href="/"
            className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-krypton text-carbon text-sm font-semibold shadow-glow-sm hover:bg-krypton-400 transition-all"
          >
            Subir documento
          </Link>
        </div>
      )}

      {/* Document grid */}
      {!loading && docs.length > 0 && (
        <div className="space-y-4">
          <div className="flex items-center gap-2">
            <div className="w-1 h-4 bg-krypton rounded-full" />
            <p className="text-xs font-semibold text-bruma uppercase tracking-wider">
              {docs.length} documento{docs.length !== 1 ? "s" : ""} con auditoría
            </p>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {docs.map((doc) => (
              <AuditDocCard key={doc.id} doc={doc} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
