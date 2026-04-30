"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { listDocuments, DocumentListItem } from "@/lib/api";

export default function AuditPage() {
  const router = useRouter();
  const [docs, setDocs] = useState<DocumentListItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    listDocuments()
      .then((d) => setDocs(d.filter((doc) => ["completed", "candidate_ready"].includes(doc.status))))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="space-y-8 animate-fade-in">
      <div>
        <div className="flex items-center gap-2 mb-1">
          <span className="text-[10px] font-mono text-krypton uppercase tracking-widest">STYLIA / AUDIT</span>
        </div>
        <h1 className="text-2xl font-bold text-bruma">Auditoría LLM — Plan v4</h1>
        <p className="text-sm text-plomo mt-1">
          Trazabilidad total de cada llamada al LLM. Payload RAW · Doble pasada · Reversiones detectadas · ADN editorial.
        </p>
      </div>

      {loading && (
        <div className="flex items-center gap-3 py-12">
          <div className="w-5 h-5 border-2 border-krypton border-t-transparent rounded-full animate-spin" />
          <span className="text-plomo text-sm">Cargando documentos...</span>
        </div>
      )}

      {!loading && docs.length === 0 && (
        <div className="glass-card rounded-xl p-10 text-center">
          <div className="w-14 h-14 mx-auto mb-4 rounded-2xl bg-surface-elevated flex items-center justify-center">
            <svg className="w-6 h-6 text-plomo" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h3.75M9 15h3.75M9 18h3.75m3 .75H18a2.25 2.25 0 002.25-2.25V6.108c0-1.135-.845-2.098-1.976-2.192a48.424 48.424 0 00-1.123-.08m-5.801 0c-.065.21-.1.433-.1.664 0 .414.336.75.75.75h4.5a.75.75 0 00.75-.75 2.25 2.25 0 00-.1-.664m-5.8 0A2.251 2.251 0 0113.5 2.25H15c1.012 0 1.867.668 2.15 1.586m-5.8 0c-.376.023-.75.05-1.124.08C9.095 4.01 8.25 4.973 8.25 6.108V8.25m0 0H4.875c-.621 0-1.125.504-1.125 1.125v11.25c0 .621.504 1.125 1.125 1.125h9.75c.621 0 1.125-.504 1.125-1.125V9.375c0-.621-.504-1.125-1.125-1.125H8.25zM6.75 12h.008v.008H6.75V12zm0 3h.008v.008H6.75V15zm0 3h.008v.008H6.75V18z" />
            </svg>
          </div>
          <p className="text-plomo text-sm">No hay documentos completados con auditoría disponible.</p>
          <p className="text-plomo-dark text-xs mt-1">
            Procesa un documento con el pipeline Plan v4 para ver los datos de auditoría.
          </p>
          <button
            onClick={() => router.push("/")}
            className="mt-4 px-4 py-2 text-sm text-krypton border border-krypton/30 rounded-lg hover:bg-krypton/5 transition-colors"
          >
            Ir al inicio
          </button>
        </div>
      )}

      {!loading && docs.length > 0 && (
        <div className="space-y-3">
          <p className="text-xs text-plomo-dark uppercase tracking-wider font-medium">
            {docs.length} documento{docs.length !== 1 ? "s" : ""} disponibles para auditoría
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {docs.map((doc) => (
              <button
                key={doc.id}
                onClick={() => router.push(`/audit/${doc.id}`)}
                className="glass-card rounded-xl p-4 text-left hover:bg-surface-hover transition-all group"
              >
                <div className="flex items-start gap-3">
                  <div className="w-8 h-8 rounded-lg bg-krypton/10 flex items-center justify-center flex-shrink-0 group-hover:bg-krypton/20 transition-colors">
                    <svg className="w-4 h-4 text-krypton" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
                    </svg>
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium text-bruma truncate">{doc.filename}</p>
                    <p className="text-xs text-plomo-dark mt-0.5">
                      {doc.total_pages || 0} páginas
                    </p>
                    <div className="flex items-center gap-1.5 mt-1.5">
                      <span className={`text-[10px] px-1.5 py-0.5 rounded font-mono ${
                        doc.status === "completed"
                          ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                          : "bg-krypton/10 text-krypton border border-krypton/20"
                      }`}>
                        {doc.status}
                      </span>
                    </div>
                  </div>
                  <svg className="w-4 h-4 text-plomo group-hover:text-krypton transition-colors flex-shrink-0 mt-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M8.25 4.5l7.5 7.5-7.5 7.5" />
                  </svg>
                </div>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
