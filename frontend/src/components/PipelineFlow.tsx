"use client";

import { ProgressDetail, CorrectionBatchStatus } from "@/lib/api";

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
    description: "Documento recibido",
    icon: (
      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" />
      </svg>
    ),
  },
  {
    key: "converting",
    label: "Conversion",
    description: "DOCX → PDF",
    icon: (
      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 12c0-1.232-.046-2.453-.138-3.662a4.006 4.006 0 00-3.7-3.7 48.678 48.678 0 00-7.324 0 4.006 4.006 0 00-3.7 3.7c-.017.22-.032.441-.046.662M19.5 12l3-3m-3 3l-3-3m-12 3c0 1.232.046 2.453.138 3.662a4.006 4.006 0 003.7 3.7 48.656 48.656 0 007.324 0 4.006 4.006 0 003.7-3.7c.017-.22.032-.441.046-.662M4.5 12l3 3m-3-3l-3 3" />
      </svg>
    ),
  },
  {
    key: "extracting",
    label: "Extraccion",
    description: "Layout y bloques",
    icon: (
      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 6A2.25 2.25 0 016 3.75h2.25A2.25 2.25 0 0110.5 6v2.25a2.25 2.25 0 01-2.25 2.25H6a2.25 2.25 0 01-2.25-2.25V6zM3.75 15.75A2.25 2.25 0 016 13.5h2.25a2.25 2.25 0 012.25 2.25V18a2.25 2.25 0 01-2.25 2.25H6A2.25 2.25 0 013.75 18v-2.25zM13.5 6a2.25 2.25 0 012.25-2.25H18A2.25 2.25 0 0120.25 6v2.25A2.25 2.25 0 0118 10.5h-2.25a2.25 2.25 0 01-2.25-2.25V6zM13.5 15.75a2.25 2.25 0 012.25-2.25H18a2.25 2.25 0 012.25 2.25V18A2.25 2.25 0 0118 20.25h-2.25A2.25 2.25 0 0113.5 18v-2.25z" />
      </svg>
    ),
  },
  {
    key: "analyzing",
    label: "Analisis",
    description: "Perfil editorial",
    icon: (
      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M9.75 3.104v5.714a2.25 2.25 0 01-.659 1.591L5 14.5M9.75 3.104c-.251.023-.501.05-.75.082m.75-.082a24.301 24.301 0 014.5 0m0 0v5.714c0 .597.237 1.17.659 1.591L19.8 15.3M14.25 3.104c.251.023.501.05.75.082M19.8 15.3l-1.57.393A9.065 9.065 0 0112 15a9.065 9.065 0 00-6.23.693L5 14.5m14.8.8l1.402 1.402c1.232 1.232.65 3.318-1.067 3.611A48.309 48.309 0 0112 21c-2.773 0-5.491-.235-8.135-.687-1.718-.293-2.3-2.379-1.067-3.61L5 14.5" />
      </svg>
    ),
  },
  {
    key: "correcting",
    label: "Correccion",
    description: "LT + LLM",
    icon: (
      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L10.582 16.07a4.5 4.5 0 01-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 011.13-1.897l8.932-8.931zm0 0L19.5 7.125M18 14v4.75A2.25 2.25 0 0115.75 21H5.25A2.25 2.25 0 013 18.75V8.25A2.25 2.25 0 015.25 6H10" />
      </svg>
    ),
  },
  {
    key: "candidate_rendering",
    label: "Candidato",
    description: "Preview candidato",
    icon: (
      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M2.036 12.322a1.012 1.012 0 010-.639C3.423 7.51 7.36 4.5 12 4.5c4.638 0 8.573 3.007 9.963 7.178.07.207.07.431 0 .639C20.577 16.49 16.64 19.5 12 19.5c-4.638 0-8.573-3.007-9.963-7.178z" />
        <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
      </svg>
    ),
  },
  {
    key: "candidate_ready",
    label: "Revision",
    description: "Comparar y aprobar",
    icon: (
      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 6a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0zM4.501 20.118a7.5 7.5 0 0114.998 0A17.933 17.933 0 0112 21.75c-2.676 0-5.216-.584-7.499-1.632z" />
      </svg>
    ),
  },
  {
    key: "finalizing",
    label: "Finalizando",
    description: "Documento final",
    icon: (
      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
      </svg>
    ),
  },
  {
    key: "completed",
    label: "Listo",
    description: "Descargar",
    icon: (
      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
    ),
  },
];

const STAGE_ORDER = STAGES.map((s) => s.key);

function formatEta(seconds: number): string {
  if (seconds < 60) return `~${Math.round(seconds)}s`;
  const mins = Math.floor(seconds / 60);
  const secs = Math.round(seconds % 60);
  return secs > 0 ? `~${mins}m ${secs}s` : `~${mins}m`;
}

interface PipelineFlowProps {
  currentStatus: string;
  progress: number;
  errorMessage?: string | null;
  progressDetail?: ProgressDetail | null;
  correctionBatches?: CorrectionBatchStatus[];
}

// Map legacy statuses to new pipeline stages
const STATUS_ALIAS: Record<string, string> = {
  pending_review: "candidate_ready",
  rendering: "finalizing",
};

export function PipelineFlow({ currentStatus, progress, errorMessage, progressDetail, correctionBatches }: PipelineFlowProps) {
  const mappedStatus = STATUS_ALIAS[currentStatus] || currentStatus;
  const currentIndex = STAGE_ORDER.indexOf(mappedStatus);
  const isFailed = currentStatus === "failed";
  const isStalled = progressDetail?.is_stalled ?? false;
  const progressPercent = Math.round(progress * 100);

  const hasIntraStage = progressDetail?.stage_current != null && progressDetail?.stage_total != null && progressDetail.stage_total > 0;
  const intraPercent = hasIntraStage
    ? Math.round((progressDetail!.stage_current! / progressDetail!.stage_total!) * 100)
    : 0;

  return (
    <div className="glass-card rounded-xl p-5">
      {/* Header */}
      <div className="flex items-center justify-between mb-5">
        <div className="flex items-center gap-2.5">
          <h3 className="text-xs font-semibold text-bruma uppercase tracking-wider">Pipeline</h3>
          {!isFailed && currentStatus !== "completed" && currentStatus !== "uploaded" && mappedStatus !== "candidate_ready" && !isStalled && (
            <span className="inline-flex items-center gap-1.5 text-[10px] text-krypton bg-krypton/8 px-2 py-0.5 rounded-md">
              <span className="w-1 h-1 rounded-full bg-krypton animate-pulse-slow" />
              En proceso
            </span>
          )}
          {isStalled && (
            <span className="inline-flex items-center gap-1.5 text-[10px] text-amber-400 bg-amber-500/10 px-2 py-0.5 rounded-md font-medium">
              <span className="w-1 h-1 rounded-full bg-amber-400" />
              Detenido
            </span>
          )}
          {currentStatus === "completed" && (
            <span className="inline-flex items-center gap-1.5 text-[10px] text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded-md font-medium">
              Finalizado
            </span>
          )}
          {isFailed && (
            <span className="inline-flex items-center gap-1.5 text-[10px] text-red-400 bg-red-500/10 px-2 py-0.5 rounded-md">
              Error
            </span>
          )}
        </div>
        <span className={`text-xs font-mono ${isFailed ? "text-red-400" : isStalled ? "text-amber-400" : "text-krypton"}`}>
          {progressPercent}%
        </span>
      </div>

      {/* Stages — horizontal compact */}
      <div className="relative">
        {/* Connection line bg */}
        <div className="absolute top-5 left-5 right-5 h-[2px] bg-border z-0" />
        {/* Connection line fill */}
        <div
          className={`absolute top-5 left-5 h-[2px] z-0 transition-all duration-1000 ease-out rounded-full ${
            isFailed ? "bg-red-500" : isStalled ? "bg-amber-400" : "bg-krypton"
          }`}
          style={{
            width: currentStatus === "completed"
              ? "calc(100% - 40px)"
              : `calc(${(Math.max(0, currentIndex) / (STAGES.length - 1)) * 100}% - ${currentIndex > 0 ? 40 * (1 - currentIndex / (STAGES.length - 1)) : 0}px)`,
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
                <div
                  className={`
                    w-10 h-10 rounded-xl flex items-center justify-center transition-all duration-500
                    ${isCompleted ? "bg-krypton text-carbon shadow-glow-sm" : ""}
                    ${isCurrent && !isStalled ? "bg-krypton/15 text-krypton ring-2 ring-krypton/50 ring-offset-1 ring-offset-carbon animate-pulse-slow" : ""}
                    ${isCurrent && isStalled ? "bg-amber-500/15 text-amber-400 ring-2 ring-amber-500/30 ring-offset-1 ring-offset-carbon" : ""}
                    ${isPending ? "bg-surface-elevated text-plomo-dark" : ""}
                    ${isFailedStage ? "bg-red-500/15 text-red-400 ring-2 ring-red-500/30 ring-offset-1 ring-offset-carbon" : ""}
                  `}
                >
                  {isCompleted ? (
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
                    </svg>
                  ) : isFailedStage ? (
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  ) : (
                    stage.icon
                  )}
                </div>

                <span
                  className={`
                    mt-2 text-[10px] font-medium text-center transition-colors leading-tight
                    ${isCompleted || (isCurrent && !isStalled) ? "text-krypton" : ""}
                    ${isCurrent && isStalled ? "text-amber-400" : ""}
                    ${isPending ? "text-plomo-dark" : ""}
                    ${isFailedStage ? "text-red-400" : ""}
                  `}
                >
                  {stage.label}
                </span>
              </div>
            );
          })}
        </div>
      </div>

      {/* Intra-stage detail panel */}
      {progressDetail && currentStatus !== "completed" && currentStatus !== "uploaded" && !isFailed && (
        <div className="mt-4 bg-surface border border-border-subtle rounded-lg px-4 py-3">
          <div className="flex items-center justify-between mb-1.5">
            <div className="flex items-center gap-2">
              <span className="text-xs font-medium text-bruma">
                {progressDetail.stage_label || progressDetail.stage}
              </span>
              {hasIntraStage && (
                <span className="text-[10px] text-plomo font-mono">
                  {progressDetail.stage_current}/{progressDetail.stage_total}
                </span>
              )}
            </div>
            <div className="flex items-center gap-3">
              {progressDetail.eta_seconds != null && progressDetail.eta_seconds > 0 && (
                <span className="text-[10px] text-plomo-dark">
                  ETA: {formatEta(progressDetail.eta_seconds)}
                </span>
              )}
              {hasIntraStage && (
                <span className="text-[10px] font-mono text-krypton">{intraPercent}%</span>
              )}
            </div>
          </div>
          {hasIntraStage && (
            <div className="h-1 bg-surface-elevated rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full transition-all duration-500 ease-out ${isStalled ? "bg-amber-400" : "bg-krypton"}`}
                style={{ width: `${intraPercent}%` }}
              />
            </div>
          )}
          {progressDetail.message && (
            <p className="mt-1.5 text-[11px] text-plomo">{progressDetail.message}</p>
          )}
        </div>
      )}

      {/* Parallel correction batches */}
      {currentStatus === "correcting" && correctionBatches && correctionBatches.length > 1 && (
        <div className="mt-4 bg-surface border border-border-subtle rounded-lg px-4 py-3">
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-medium text-bruma">
              Correccion paralela — {correctionBatches.length} lotes
            </span>
            <span className="text-[10px] text-plomo font-mono">
              {correctionBatches.filter(b => b.status === "completed").length}/{correctionBatches.length}
            </span>
          </div>
          <div className="space-y-2">
            {correctionBatches.map((batch) => {
              const batchPct = batch.paragraphs_total > 0
                ? Math.round((batch.paragraphs_corrected / batch.paragraphs_total) * 100)
                : (batch.status === "completed" ? 100 : 0);
              const isRunning = batch.status === "running";
              const isDone = batch.status === "completed";
              const isFail = batch.status === "failed";
              return (
                <div key={batch.batch_index}>
                  <div className="flex items-center justify-between mb-1">
                    <div className="flex items-center gap-2">
                      <span className="text-[10px] text-plomo font-mono">
                        Lote {batch.batch_index + 1}
                      </span>
                      <div className="flex items-center gap-0.5">
                        <span className={`text-[9px] px-1.5 py-0.5 rounded font-medium ${batch.lt_pass_completed ? "bg-blue-500/15 text-blue-400" : "bg-surface-elevated text-plomo-dark"}`}>LT</span>
                        <span className={`text-[9px] px-1.5 py-0.5 rounded font-medium ${batch.llm_pass_completed ? "bg-purple-500/15 text-purple-400" : "bg-surface-elevated text-plomo-dark"}`}>LLM</span>
                      </div>
                    </div>
                    <span className={`text-[10px] font-mono ${isDone ? "text-emerald-400" : isFail ? "text-red-400" : isRunning ? "text-krypton" : "text-plomo-dark"}`}>
                      {isFail ? "error" : `${batchPct}%`}
                    </span>
                  </div>
                  <div className="h-1 bg-surface-elevated rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all duration-500 ${
                        isFail ? "bg-red-500" : isDone ? "bg-emerald-400" : isRunning ? "bg-krypton/60 animate-pulse-slow" : "bg-border"
                      }`}
                      style={{ width: `${batchPct}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Error message */}
      {isFailed && errorMessage && (
        <div className="mt-4 flex items-start gap-3 bg-red-500/8 border border-red-500/15 text-red-400 px-4 py-3 rounded-lg text-sm">
          <svg className="w-4 h-4 flex-shrink-0 mt-0.5" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
          </svg>
          <div>
            <p className="font-medium text-sm">Error en el procesamiento</p>
            <p className="mt-1 text-red-400/80 text-xs">{errorMessage}</p>
          </div>
        </div>
      )}

      {/* Stalled warning */}
      {isStalled && !isFailed && (
        <div className="mt-4 flex items-start gap-3 bg-amber-500/8 border border-amber-500/15 text-amber-400 px-4 py-3 rounded-lg text-sm">
          <svg className="w-4 h-4 flex-shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
          </svg>
          <div>
            <p className="font-medium text-sm">Procesamiento detenido</p>
            <p className="mt-1 text-amber-400/80 text-xs">
              Sin heartbeat en los ultimos 2 minutos. El worker puede estar colgado.
            </p>
          </div>
        </div>
      )}

      {/* Overall progress bar */}
      <div className="mt-4">
        <div className="h-1 bg-surface-elevated rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full transition-all duration-1000 ease-out ${
              isFailed ? "bg-red-500" : isStalled ? "bg-amber-400" : "bg-krypton"
            }`}
            style={{ width: `${progressPercent}%` }}
          />
        </div>
      </div>
    </div>
  );
}
