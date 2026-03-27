"use client";

import { AnalysisResult } from "@/lib/api";

const TONE_LABELS: Record<string, string> = {
  reflexivo: "Reflexivo",
  didactico: "Didáctico",
  narrativo: "Narrativo",
  persuasivo: "Persuasivo",
  neutro: "Neutro",
  ludico: "Lúdico",
};

const PARAGRAPH_TYPE_CONFIG: Record<string, { label: string; color: string }> = {
  titulo: { label: "Título", color: "bg-violet-500" },
  subtitulo: { label: "Subtítulo", color: "bg-violet-400" },
  narrativo: { label: "Narrativo", color: "bg-blue-500" },
  explicacion_tecnica: { label: "Explicación técnica", color: "bg-amber-500" },
  dialogo: { label: "Diálogo", color: "bg-pink-500" },
  cita: { label: "Cita", color: "bg-indigo-400" },
  lista: { label: "Lista", color: "bg-cyan-500" },
  celda_tabla: { label: "Celda de tabla", color: "bg-orange-500" },
  encabezado: { label: "Encabezado", color: "bg-gray-500" },
  footer: { label: "Pie de página", color: "bg-gray-400" },
  pie_imagen: { label: "Pie de imagen", color: "bg-teal-500" },
  vacio: { label: "Vacío", color: "bg-gray-600" },
};

interface AnalysisViewProps {
  analysis: AnalysisResult | null;
}

export function AnalysisView({ analysis }: AnalysisViewProps) {
  if (!analysis || analysis.status === "pending") {
    return (
      <div className="bg-carbon-100 border border-carbon-300 rounded-xl p-8 text-center">
        <div className="w-14 h-14 mx-auto mb-4 rounded-2xl bg-carbon-200 flex items-center justify-center">
          <svg className="w-7 h-7 text-plomo" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M9.75 3.104v5.714a2.25 2.25 0 01-.659 1.591L5 14.5M9.75 3.104c-.251.023-.501.05-.75.082m.75-.082a24.301 24.301 0 014.5 0m0 0v5.714c0 .597.237 1.17.659 1.591L19.8 15.3M14.25 3.104c.251.023.501.05.75.082M19.8 15.3l-1.57.393A9.065 9.065 0 0112 15a9.065 9.065 0 00-6.23.693L5 14.5" />
          </svg>
        </div>
        <p className="text-plomo text-sm">El análisis editorial se genera durante el procesamiento del documento.</p>
        <p className="text-plomo/60 text-xs mt-1">Procesa el documento para ver secciones, glosario y clasificaciones.</p>
      </div>
    );
  }

  const { sections, terms, stats, inferred_profile } = analysis;
  const paragraphTypes = (stats?.paragraph_types || {}) as Record<string, number>;
  const totalClassified = Object.values(paragraphTypes).reduce((a, b) => a + b, 0);

  return (
    <div className="space-y-4">
      {/* Header stats */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <MiniStat label="Secciones" value={sections.length.toString()} />
        <MiniStat label="Términos" value={terms.length.toString()} />
        <MiniStat
          label="Protegidos"
          value={(stats?.terms_protected as number || 0).toString()}
          accent
        />
        <MiniStat
          label="Párrafos con LLM"
          value={`${stats?.paragraphs_needing_llm || 0}/${stats?.non_empty_paragraphs || 0}`}
        />
      </div>

      {/* Inferred profile */}
      {inferred_profile && (
        <div className="bg-carbon-100 border border-krypton/20 rounded-xl p-5">
          <h3 className="text-sm font-semibold text-bruma uppercase tracking-wider mb-4">
            Perfil detectado por análisis
          </h3>
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-4">
            {inferred_profile.genre && (
              <ProfileField label="Género" value={inferred_profile.genre} />
            )}
            {inferred_profile.audience_type && (
              <ProfileField label="Audiencia" value={inferred_profile.audience_type} />
            )}
            {inferred_profile.register && (
              <ProfileField label="Registro" value={inferred_profile.register} />
            )}
            {inferred_profile.tone && (
              <ProfileField label="Tono" value={TONE_LABELS[inferred_profile.tone] || inferred_profile.tone} />
            )}
            {inferred_profile.spanish_variant && (
              <ProfileField label="Variante" value={inferred_profile.spanish_variant} />
            )}
          </div>
          {inferred_profile.key_terms && inferred_profile.key_terms.length > 0 && (
            <div className="mt-3 pt-3 border-t border-carbon-300 flex items-center gap-2 flex-wrap">
              <span className="text-plomo text-[10px] uppercase tracking-wider">Términos clave:</span>
              {inferred_profile.key_terms.map((t) => (
                <span key={t} className="text-[10px] bg-krypton/10 text-krypton px-2 py-0.5 rounded">{t}</span>
              ))}
            </div>
          )}
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Sections */}
        <div className="bg-carbon-100 border border-carbon-300 rounded-xl p-5">
          <h3 className="text-sm font-semibold text-bruma uppercase tracking-wider mb-4">
            Secciones detectadas ({sections.length})
          </h3>
          {sections.length === 0 ? (
            <p className="text-plomo text-xs">No se detectaron secciones.</p>
          ) : (
            <div className="space-y-3 max-h-[400px] overflow-y-auto pr-1">
              {sections.map((sec) => (
                <div
                  key={sec.section_index}
                  className="bg-carbon-200 border border-carbon-300 rounded-lg p-3"
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-[10px] font-mono text-plomo bg-carbon-300 px-1.5 py-0.5 rounded">
                          S{sec.section_index + 1}
                        </span>
                        <span className="text-sm font-medium text-bruma truncate">
                          {sec.section_title || `Sección ${sec.section_index + 1}`}
                        </span>
                      </div>
                      {sec.topic && sec.topic !== sec.section_title && (
                        <p className="text-xs text-krypton/80 mt-1">{sec.topic}</p>
                      )}
                      {sec.summary_text && (
                        <p className="text-xs text-plomo mt-1.5 leading-relaxed">{sec.summary_text}</p>
                      )}
                    </div>
                    {sec.local_tone && (
                      <span className="text-[10px] bg-carbon-300 text-plomo px-1.5 py-0.5 rounded flex-shrink-0">
                        {TONE_LABELS[sec.local_tone] || sec.local_tone}
                      </span>
                    )}
                  </div>
                  {sec.active_terms && sec.active_terms.length > 0 && (
                    <div className="flex flex-wrap gap-1 mt-2">
                      {sec.active_terms.map((t) => (
                        <span key={t} className="text-[9px] bg-purple-900/20 text-purple-400 px-1.5 py-0.5 rounded">
                          {t}
                        </span>
                      ))}
                    </div>
                  )}
                  {sec.transition_from_previous && (
                    <p className="text-[10px] text-plomo/60 mt-2 italic">
                      Transición: {sec.transition_from_previous}
                    </p>
                  )}
                  <div className="text-[9px] text-plomo/50 mt-1.5">
                    Párrafos {sec.start_paragraph}–{sec.end_paragraph}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Terms */}
        <div className="bg-carbon-100 border border-carbon-300 rounded-xl p-5">
          <h3 className="text-sm font-semibold text-bruma uppercase tracking-wider mb-4">
            Glosario de términos ({terms.length})
          </h3>
          {terms.length === 0 ? (
            <p className="text-plomo text-xs">No se extrajeron términos.</p>
          ) : (
            <div className="space-y-1.5 max-h-[400px] overflow-y-auto pr-1">
              {terms.map((t, i) => (
                <div
                  key={i}
                  className="flex items-center justify-between gap-2 py-1.5 px-2.5 rounded-lg hover:bg-carbon-200 transition-colors"
                >
                  <div className="flex items-center gap-2 min-w-0">
                    {t.is_protected && (
                      <svg className="w-3.5 h-3.5 text-purple-400 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75m-3-7.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285z" />
                      </svg>
                    )}
                    <span className={`text-xs truncate ${t.is_protected ? "text-purple-300 font-medium" : "text-bruma/80"}`}>
                      {t.term}
                    </span>
                  </div>
                  <div className="flex items-center gap-2 flex-shrink-0">
                    <span className="text-[10px] text-plomo font-mono">{t.frequency}x</span>
                    {t.is_protected && (
                      <span className="text-[9px] bg-purple-900/30 text-purple-400 px-1.5 py-0.5 rounded">
                        protegido
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Paragraph type distribution */}
      {totalClassified > 0 && (
        <div className="bg-carbon-100 border border-carbon-300 rounded-xl p-5">
          <h3 className="text-sm font-semibold text-bruma uppercase tracking-wider mb-4">
            Distribución de tipos de párrafo
          </h3>
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-2">
            {Object.entries(paragraphTypes)
              .sort(([, a], [, b]) => b - a)
              .map(([type, count]) => {
                const config = PARAGRAPH_TYPE_CONFIG[type] || { label: type, color: "bg-gray-500" };
                const pct = Math.round((count / totalClassified) * 100);
                return (
                  <div key={type} className="bg-carbon-200 rounded-lg p-3">
                    <div className="flex items-center gap-2 mb-2">
                      <div className={`w-2.5 h-2.5 rounded-full ${config.color}`} />
                      <span className="text-xs text-bruma font-medium">{config.label}</span>
                    </div>
                    <div className="flex items-end justify-between">
                      <span className="text-lg font-semibold text-bruma">{count}</span>
                      <span className="text-[10px] text-plomo">{pct}%</span>
                    </div>
                    <div className="h-1 bg-carbon-300 rounded-full mt-1.5 overflow-hidden">
                      <div
                        className={`h-full rounded-full ${config.color}`}
                        style={{ width: `${pct}%`, opacity: 0.7 }}
                      />
                    </div>
                  </div>
                );
              })}
          </div>
        </div>
      )}

      {/* Analysis cost */}
      {stats?.analysis_total_cost != null && (stats.analysis_total_cost as number) > 0 && (
        <div className="flex items-center justify-end gap-4 text-[10px] text-plomo">
          <span>
            Análisis: {stats.analysis_llm_calls as number} llamadas LLM |{" "}
            {(stats.analysis_total_tokens as number).toLocaleString()} tokens |{" "}
            ${(stats.analysis_total_cost as number).toFixed(6)} USD
          </span>
        </div>
      )}
    </div>
  );
}

function MiniStat({ label, value, accent }: { label: string; value: string; accent?: boolean }) {
  return (
    <div className="bg-carbon-100 border border-carbon-300 rounded-xl p-4 text-center">
      <div className="text-[10px] uppercase tracking-wider text-plomo mb-1">{label}</div>
      <div className={`text-xl font-semibold ${accent ? "text-purple-400" : "text-bruma"}`}>{value}</div>
    </div>
  );
}

function ProfileField({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <span className="text-plomo text-[10px] uppercase tracking-wider block mb-1">{label}</span>
      <span className="text-krypton font-semibold text-sm capitalize">{value.replace(/_/g, " ")}</span>
    </div>
  );
}
