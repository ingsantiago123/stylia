"use client";

interface Stage {
  key: string;
  label: string;
  description: string;
  icon: React.ReactNode;
}

const STAGES: Stage[] = [
  {
    key: "uploaded",
    label: "Ingesta",
    description: "Documento recibido y almacenado",
    icon: (
      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" />
      </svg>
    ),
  },
  {
    key: "converting",
    label: "Conversión",
    description: "DOCX → PDF con LibreOffice",
    icon: (
      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 12c0-1.232-.046-2.453-.138-3.662a4.006 4.006 0 00-3.7-3.7 48.678 48.678 0 00-7.324 0 4.006 4.006 0 00-3.7 3.7c-.017.22-.032.441-.046.662M19.5 12l3-3m-3 3l-3-3m-12 3c0 1.232.046 2.453.138 3.662a4.006 4.006 0 003.7 3.7 48.656 48.656 0 007.324 0 4.006 4.006 0 003.7-3.7c.017-.22.032-.441.046-.662M4.5 12l3 3m-3-3l-3 3" />
      </svg>
    ),
  },
  {
    key: "extracting",
    label: "Extracción",
    description: "Analizando layout y bloques de texto",
    icon: (
      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 6A2.25 2.25 0 016 3.75h2.25A2.25 2.25 0 0110.5 6v2.25a2.25 2.25 0 01-2.25 2.25H6a2.25 2.25 0 01-2.25-2.25V6zM3.75 15.75A2.25 2.25 0 016 13.5h2.25a2.25 2.25 0 012.25 2.25V18a2.25 2.25 0 01-2.25 2.25H6A2.25 2.25 0 013.75 18v-2.25zM13.5 6a2.25 2.25 0 012.25-2.25H18A2.25 2.25 0 0120.25 6v2.25A2.25 2.25 0 0118 10.5h-2.25a2.25 2.25 0 01-2.25-2.25V6zM13.5 15.75a2.25 2.25 0 012.25-2.25H18a2.25 2.25 0 012.25 2.25V18A2.25 2.25 0 0118 20.25h-2.25A2.25 2.25 0 0113.5 18v-2.25z" />
      </svg>
    ),
  },
  {
    key: "correcting",
    label: "Corrección",
    description: "LanguageTool + LLM corrigiendo estilo",
    icon: (
      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L10.582 16.07a4.5 4.5 0 01-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 011.13-1.897l8.932-8.931zm0 0L19.5 7.125M18 14v4.75A2.25 2.25 0 0115.75 21H5.25A2.25 2.25 0 013 18.75V8.25A2.25 2.25 0 015.25 6H10" />
      </svg>
    ),
  },
  {
    key: "rendering",
    label: "Renderizado",
    description: "Generando documento final",
    icon: (
      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
      </svg>
    ),
  },
  {
    key: "completed",
    label: "Completado",
    description: "Documento listo para descargar",
    icon: (
      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
    ),
  },
];

const STAGE_ORDER = STAGES.map((s) => s.key);

interface PipelineFlowProps {
  currentStatus: string;
  progress: number;
  errorMessage?: string | null;
}

export function PipelineFlow({ currentStatus, progress, errorMessage }: PipelineFlowProps) {
  const currentIndex = STAGE_ORDER.indexOf(currentStatus);
  const isFailed = currentStatus === "failed";
  const progressPercent = Math.round(progress * 100);

  return (
    <div className="bg-carbon-100 border border-carbon-300 rounded-xl p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <h3 className="text-sm font-semibold text-bruma uppercase tracking-wider">Pipeline de procesamiento</h3>
          {!isFailed && currentStatus !== "completed" && (
            <span className="inline-flex items-center gap-1.5 text-xs text-krypton bg-krypton/10 px-2.5 py-1 rounded-full">
              <span className="w-1.5 h-1.5 rounded-full bg-krypton animate-pulse-slow" />
              En proceso
            </span>
          )}
          {currentStatus === "completed" && (
            <span className="inline-flex items-center gap-1.5 text-xs text-krypton bg-krypton/15 px-2.5 py-1 rounded-full font-medium">
              ✓ Finalizado
            </span>
          )}
          {isFailed && (
            <span className="inline-flex items-center gap-1.5 text-xs text-red-400 bg-red-900/20 px-2.5 py-1 rounded-full">
              ✕ Error
            </span>
          )}
        </div>
        <span className="text-sm font-mono text-krypton">{progressPercent}%</span>
      </div>

      {/* Stages */}
      <div className="relative">
        {/* Connection line */}
        <div className="absolute top-6 left-6 right-6 h-px bg-carbon-300 z-0" />
        <div
          className="absolute top-6 left-6 h-px bg-krypton z-0 transition-all duration-1000 ease-out"
          style={{
            width: currentStatus === "completed"
              ? "calc(100% - 48px)"
              : `calc(${(Math.max(0, currentIndex) / (STAGES.length - 1)) * 100}% - ${currentIndex > 0 ? 48 * (1 - currentIndex / (STAGES.length - 1)) : 0}px)`,
          }}
        />

        <div className="relative z-10 flex justify-between">
          {STAGES.map((stage, i) => {
            const isCompleted = currentIndex > i || currentStatus === "completed";
            const isCurrent = currentIndex === i && !isFailed;
            const isPending = currentIndex < i && currentStatus !== "completed";
            const isFailedStage = isFailed && currentIndex === i;

            return (
              <div key={stage.key} className="flex flex-col items-center" style={{ width: `${100 / STAGES.length}%` }}>
                {/* Circle */}
                <div
                  className={`
                    w-12 h-12 rounded-full flex items-center justify-center transition-all duration-500
                    ${isCompleted ? "bg-krypton text-carbon shadow-[0_0_15px_rgba(212,255,0,0.3)]" : ""}
                    ${isCurrent ? "bg-krypton/20 text-krypton ring-2 ring-krypton ring-offset-2 ring-offset-carbon-100 animate-pulse-slow" : ""}
                    ${isPending ? "bg-carbon-200 text-plomo" : ""}
                    ${isFailedStage ? "bg-red-900/30 text-red-400 ring-2 ring-red-500/50 ring-offset-2 ring-offset-carbon-100" : ""}
                  `}
                >
                  {isCompleted ? (
                    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
                    </svg>
                  ) : isFailedStage ? (
                    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  ) : (
                    stage.icon
                  )}
                </div>

                {/* Label */}
                <span
                  className={`
                    mt-3 text-xs font-medium text-center transition-colors
                    ${isCompleted || isCurrent ? "text-krypton" : ""}
                    ${isPending ? "text-plomo" : ""}
                    ${isFailedStage ? "text-red-400" : ""}
                  `}
                >
                  {stage.label}
                </span>

                {/* Description - only for current stage */}
                {(isCurrent || isFailedStage) && (
                  <span className={`mt-1 text-[10px] text-center max-w-[100px] ${isFailedStage ? "text-red-400/70" : "text-plomo"}`}>
                    {isFailedStage ? "Proceso detenido" : stage.description}
                  </span>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Error message */}
      {isFailed && errorMessage && (
        <div className="mt-6 flex items-start gap-3 bg-red-900/15 border border-red-500/20 text-red-400 px-4 py-3 rounded-lg text-sm">
          <svg className="w-5 h-5 flex-shrink-0 mt-0.5" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
          </svg>
          <div>
            <p className="font-medium">Error en el procesamiento</p>
            <p className="mt-1 text-red-400/80">{errorMessage}</p>
          </div>
        </div>
      )}

      {/* Overall progress bar */}
      <div className="mt-6">
        <div className="h-1 bg-carbon-300 rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full transition-all duration-1000 ease-out ${isFailed ? "bg-red-500" : "bg-krypton"}`}
            style={{ width: `${progressPercent}%` }}
          />
        </div>
      </div>
    </div>
  );
}
