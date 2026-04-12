"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import {
  reviewCorrection,
  manualEditCorrection,
  recorrectPatch,
  getSingleCorrection,
  PatchListItem,
} from "@/lib/api";

// =============================================
// Source of truth: estados de revisión y colores
// =============================================

export const REVIEW_STATES = {
  auto_accepted: { label: "Auto-aprobado", color: "text-emerald-400", bg: "bg-emerald-500/10", border: "border-emerald-500/30" },
  accepted: { label: "Aceptado", color: "text-emerald-400", bg: "bg-emerald-500/15", border: "border-emerald-500/40" },
  rejected: { label: "Rechazado", color: "text-red-400", bg: "bg-red-500/15", border: "border-red-500/40" },
  pending: { label: "Pendiente", color: "text-amber-400", bg: "bg-amber-500/15", border: "border-amber-500/40" },
  manual_review: { label: "Rev. Manual", color: "text-orange-400", bg: "bg-orange-500/15", border: "border-orange-500/40" },
  gate_rejected: { label: "Rechazado (gates)", color: "text-red-500", bg: "bg-red-500/10", border: "border-red-500/30" },
  bulk_finalized: { label: "Aprobado (global)", color: "text-blue-400", bg: "bg-blue-500/15", border: "border-blue-500/40" },
} as const;

export type ReviewStatus = keyof typeof REVIEW_STATES;

export const SEVERITY_STYLES = {
  critico: { label: "Critico", color: "text-red-400", bg: "bg-red-500/20", icon: "!" },
  importante: { label: "Importante", color: "text-amber-400", bg: "bg-amber-500/20", icon: "!" },
  sugerencia: { label: "Sugerencia", color: "text-blue-400", bg: "bg-blue-500/20", icon: "i" },
} as const;

// =============================================
// Props
// =============================================

interface CorrectionActionPanelProps {
  docId: string;
  patch: PatchListItem;
  isReviewMode: boolean;
  onActionComplete: () => void;       // refrescar datos del padre (correcciones, reviewSummary)
  onPatchUpdated?: (p: PatchListItem) => void;  // actualizar patch local sin cerrar panel
  onTextChanged?: () => void;         // avisa al padre que el texto cambió → re-renderizar imagen
  compact?: boolean;
}

// =============================================
// Component
// =============================================

export function CorrectionActionPanel({
  docId,
  patch,
  isReviewMode,
  onActionComplete,
  onPatchUpdated,
  onTextChanged,
  compact = false,
}: CorrectionActionPanelProps) {
  const [actionLoading, setActionLoading] = useState(false);
  const [editMode, setEditMode] = useState(false);
  const [editText, setEditText] = useState(patch.edited_text || patch.corrected_text);
  const [recorrectMode, setRecorrectMode] = useState(false);
  const [feedback, setFeedback] = useState("");
  const [error, setError] = useState<string | null>(null);

  // Post-action states
  const [editSaved, setEditSaved] = useState(false);
  const [recorrecting, setRecorrecting] = useState(false);
  const [recorrectResult, setRecorrectResult] = useState<{
    previousText: string;
    newText: string;
    newExplanation: string | null;
  } | null>(null);

  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const pollingCountRef = useRef(0);

  // Limpiar polling on unmount
  useEffect(() => {
    return () => {
      if (pollingRef.current) clearInterval(pollingRef.current);
    };
  }, []);

  // Sincronizar editText cuando el patch cambia externamente
  useEffect(() => {
    if (!editMode && !editSaved) {
      setEditText(patch.edited_text || patch.corrected_text);
    }
  }, [patch.corrected_text, patch.edited_text, editMode, editSaved]);

  const stateConfig = REVIEW_STATES[patch.review_status as ReviewStatus] || REVIEW_STATES.pending;
  const sevConfig = patch.severity ? SEVERITY_STYLES[patch.severity as keyof typeof SEVERITY_STYLES] : null;
  const effectiveText = patch.edited_text || patch.corrected_text;

  const handleReview = async (action: "accepted" | "rejected") => {
    setActionLoading(true);
    setError(null);
    try {
      await reviewCorrection(docId, patch.id, action);
      onActionComplete();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error");
    } finally {
      setActionLoading(false);
    }
  };

  const handleSaveEdit = async () => {
    if (!editText.trim()) return;
    setActionLoading(true);
    setError(null);
    try {
      await manualEditCorrection(docId, patch.id, editText.trim());
      setEditMode(false);
      setEditSaved(true);
      // Refrescar datos del padre para que se actualice el texto en la lista
      onActionComplete();
      // Notificar que el texto cambió → el padre dispara re-render de imagen
      onTextChanged?.();
      // Auto-limpiar el indicador de guardado después de 4s
      setTimeout(() => setEditSaved(false), 4000);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error");
    } finally {
      setActionLoading(false);
    }
  };

  // Polling: esperar a que el Celery task termine y el patch tenga nuevo corrected_text
  const pollForRecorrection = useCallback((previousCorrectedText: string, previousCount: number) => {
    pollingCountRef.current = 0;
    setRecorrecting(true);
    setRecorrectResult(null);

    pollingRef.current = setInterval(async () => {
      pollingCountRef.current++;
      // Max 60 intentos × 2s = 120s timeout
      if (pollingCountRef.current > 60) {
        if (pollingRef.current) clearInterval(pollingRef.current);
        setRecorrecting(false);
        setError("La recorrección tardó más de 2 minutos. Verifica que el worker esté activo e inténtalo de nuevo.");
        return;
      }

      try {
        const updated = await getSingleCorrection(docId, patch.id);
        const newCount = updated.recorrection_count || 0;
        // La recorrección terminó cuando el contador subió
        if (newCount > previousCount) {
          if (pollingRef.current) clearInterval(pollingRef.current);
          setRecorrecting(false);

          const newText = updated.edited_text || updated.corrected_text;
          setRecorrectResult({
            previousText: previousCorrectedText,
            newText,
            newExplanation: updated.explanation,
          });

          // Notificar al padre: actualizar lista y re-renderizar imagen
          onPatchUpdated?.(updated);
          onActionComplete();
          onTextChanged?.();
        }
      } catch {
        // Ignorar errores de red temporales durante polling
      }
    }, 2000);
  }, [docId, patch.id, onActionComplete, onPatchUpdated]);

  const handleRecorrect = async () => {
    if (!feedback.trim() || feedback.trim().length < 3) return;
    setActionLoading(true);
    setError(null);
    try {
      const previousText = effectiveText;
      const previousCount = patch.recorrection_count || 0;
      await recorrectPatch(docId, patch.id, feedback.trim());
      // No cerrar el modo, no limpiar feedback — iniciar polling
      setRecorrectMode(false);
      setFeedback("");
      pollForRecorrection(previousText, previousCount);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error");
    } finally {
      setActionLoading(false);
    }
  };

  // Aceptar resultado de recorrección IA
  const handleAcceptRecorrection = async () => {
    setActionLoading(true);
    setError(null);
    try {
      await reviewCorrection(docId, patch.id, "accepted");
      setRecorrectResult(null);
      onActionComplete();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error");
    } finally {
      setActionLoading(false);
    }
  };

  const maxRecorrections = 3;
  const canRecorrect = (patch.recorrection_count || 0) < maxRecorrections;

  // ── Spinner de recorrección en progreso ──
  const RecorrectingSpinner = () => (
    <div className="flex items-center gap-2 px-3 py-2 bg-violet-500/10 border border-violet-500/20 rounded-lg">
      <svg className="w-4 h-4 text-violet-400 animate-spin" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182M2.985 19.644l3.181 3.182" />
      </svg>
      <span className="text-xs text-violet-400 font-medium">IA recorrigiendo...</span>
    </div>
  );

  // ── Resultado de recorrección con diff ──
  const RecorrectResultView = ({ result }: { result: NonNullable<typeof recorrectResult> }) => (
    <div className="space-y-2 border border-violet-500/20 rounded-lg p-3 bg-violet-500/5">
      <div className="flex items-center gap-2">
        <span className="text-[10px] uppercase tracking-wider text-violet-400 font-medium">Resultado IA</span>
        <span className="text-[10px] text-emerald-400 bg-emerald-500/10 px-1.5 py-0.5 rounded">Listo</span>
      </div>

      {/* Texto anterior (tachado) */}
      <div>
        <span className="text-[10px] text-plomo uppercase">Anterior</span>
        <p className="text-xs text-red-300/60 line-through leading-relaxed mt-0.5 bg-red-500/5 rounded p-2 border border-red-500/10">
          {result.previousText.length > 300 ? result.previousText.slice(0, 300) + "..." : result.previousText}
        </p>
      </div>

      {/* Texto nuevo */}
      <div>
        <span className="text-[10px] text-krypton uppercase">Nueva corrección</span>
        <p className="text-xs text-krypton/90 leading-relaxed mt-0.5 bg-krypton/5 rounded p-2 border border-krypton/15">
          {result.newText.length > 300 ? result.newText.slice(0, 300) + "..." : result.newText}
        </p>
      </div>

      {result.newExplanation && (
        <p className="text-[10px] text-plomo italic bg-surface-elevated rounded p-1.5">
          {result.newExplanation}
        </p>
      )}

      {/* Acciones sobre el resultado */}
      <div className="flex gap-2 pt-1">
        <button onClick={handleAcceptRecorrection} disabled={actionLoading}
          className="flex-1 px-3 py-1.5 text-xs bg-emerald-500/15 text-emerald-400 rounded-lg hover:bg-emerald-500/25 border border-emerald-500/20 disabled:opacity-50 font-medium">
          Aceptar resultado
        </button>
        <button onClick={() => handleReview("rejected")} disabled={actionLoading}
          className="px-3 py-1.5 text-xs bg-red-500/10 text-red-400 rounded-lg hover:bg-red-500/20 border border-red-500/15 disabled:opacity-50">
          Rechazar
        </button>
        {canRecorrect && (
          <button onClick={() => { setRecorrectResult(null); setRecorrectMode(true); }} disabled={actionLoading}
            className="px-3 py-1.5 text-xs bg-violet-500/10 text-violet-400 rounded-lg hover:bg-violet-500/20 border border-violet-500/15 disabled:opacity-50">
            Reintentar
          </button>
        )}
      </div>
    </div>
  );

  // ── Indicador de edición guardada ──
  const EditSavedIndicator = () => (
    <div className="flex items-center gap-2 px-3 py-2 bg-emerald-500/10 border border-emerald-500/20 rounded-lg animate-in fade-in">
      <svg className="w-4 h-4 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
      <span className="text-xs text-emerald-400 font-medium">Edición guardada y aplicada</span>
    </div>
  );

  if (compact) {
    // ── Vista compacta (para CorrectionHistory) ──
    return (
      <div className="flex flex-col gap-2">
        {/* Status badge */}
        <div className="flex items-center gap-2 flex-wrap">
          <span className={`text-xs px-2 py-0.5 rounded-full ${stateConfig.bg} ${stateConfig.color} ${stateConfig.border} border`}>
            {stateConfig.label}
          </span>
          {sevConfig && (
            <span className={`text-xs px-2 py-0.5 rounded-full ${sevConfig.bg} ${sevConfig.color}`}>
              {sevConfig.label}
            </span>
          )}
          {patch.decision_source && patch.decision_source !== "system" && (
            <span className="text-[10px] text-plomo">
              {patch.decision_source === "human" ? "Decisión humana" :
               patch.decision_source === "bulk_finalize" ? "Finalización global" :
               patch.decision_source === "manual_edit" ? "Editado manual" :
               patch.decision_source === "ai_recorrection" ? "Recorrección IA" : ""}
            </span>
          )}
        </div>

        {error && <p className="text-xs text-red-400">{error}</p>}

        {/* Indicador de guardado */}
        {editSaved && <EditSavedIndicator />}

        {/* Recorrección en progreso */}
        {recorrecting && <RecorrectingSpinner />}

        {/* Resultado de recorrección */}
        {recorrectResult && <RecorrectResultView result={recorrectResult} />}

        {/* Edit mode inline */}
        {editMode && (
          <div className="space-y-2">
            <textarea
              value={editText}
              onChange={(e) => setEditText(e.target.value)}
              className="w-full bg-carbon border border-plomo/30 rounded-lg p-2 text-sm text-bruma resize-y min-h-[60px] focus:border-krypton/50 focus:outline-none"
              maxLength={10000}
            />
            <div className="flex gap-2">
              <button onClick={handleSaveEdit} disabled={actionLoading}
                className="px-3 py-1 text-xs bg-krypton/20 text-krypton rounded-lg hover:bg-krypton/30 disabled:opacity-50">
                Guardar
              </button>
              <button onClick={() => setEditMode(false)}
                className="px-3 py-1 text-xs bg-surface-elevated text-plomo rounded-lg hover:bg-plomo/20">
                Cancelar
              </button>
            </div>
          </div>
        )}

        {/* Recorrect mode inline */}
        {recorrectMode && (
          <div className="space-y-2">
            <textarea
              value={feedback}
              onChange={(e) => setFeedback(e.target.value)}
              placeholder="Describe qué debe cambiar la IA..."
              className="w-full bg-carbon border border-plomo/30 rounded-lg p-2 text-sm text-bruma resize-y min-h-[50px] focus:border-krypton/50 focus:outline-none"
              maxLength={1000}
            />
            <div className="flex gap-2">
              <button onClick={handleRecorrect} disabled={actionLoading || feedback.trim().length < 3}
                className="px-3 py-1 text-xs bg-violet-500/20 text-violet-400 rounded-lg hover:bg-violet-500/30 disabled:opacity-50">
                Enviar feedback
              </button>
              <button onClick={() => { setRecorrectMode(false); setFeedback(""); }}
                className="px-3 py-1 text-xs bg-surface-elevated text-plomo rounded-lg hover:bg-plomo/20">
                Cancelar
              </button>
            </div>
          </div>
        )}

        {/* Action buttons — ocultar si hay spinner o resultado pendiente */}
        {isReviewMode && !editMode && !recorrectMode && !recorrecting && !recorrectResult && (
          <div className="flex gap-1.5 flex-wrap">
            <button onClick={() => handleReview("accepted")} disabled={actionLoading}
              className="px-2.5 py-1 text-xs bg-emerald-500/15 text-emerald-400 rounded-lg hover:bg-emerald-500/25 border border-emerald-500/20 disabled:opacity-50">
              Aceptar
            </button>
            <button onClick={() => handleReview("rejected")} disabled={actionLoading}
              className="px-2.5 py-1 text-xs bg-red-500/15 text-red-400 rounded-lg hover:bg-red-500/25 border border-red-500/20 disabled:opacity-50">
              Rechazar
            </button>
            <button onClick={() => { setEditMode(true); setEditText(patch.edited_text || patch.corrected_text); }}
              disabled={actionLoading}
              className="px-2.5 py-1 text-xs bg-blue-500/15 text-blue-400 rounded-lg hover:bg-blue-500/25 border border-blue-500/20 disabled:opacity-50">
              Editar
            </button>
            {canRecorrect && (
              <button onClick={() => setRecorrectMode(true)} disabled={actionLoading}
                className="px-2.5 py-1 text-xs bg-violet-500/15 text-violet-400 rounded-lg hover:bg-violet-500/25 border border-violet-500/20 disabled:opacity-50">
                Recorregir IA {patch.recorrection_count > 0 ? `(${patch.recorrection_count}/${maxRecorrections})` : ""}
              </button>
            )}
          </div>
        )}
      </div>
    );
  }

  // ── Vista expandida (para panel lateral en Compare) ──
  return (
    <div className="space-y-4">
      {/* Header con status */}
      <div className="flex items-center justify-between">
        <span className={`text-xs px-2.5 py-1 rounded-full font-medium ${stateConfig.bg} ${stateConfig.color} ${stateConfig.border} border`}>
          {stateConfig.label}
        </span>
        {patch.decision_source && patch.decision_source !== "system" && (
          <span className="text-[10px] text-plomo italic">
            {patch.decision_source === "human" ? "Decisión humana" :
             patch.decision_source === "bulk_finalize" ? "Finalización global" :
             patch.decision_source === "manual_edit" ? "Editado manualmente" :
             patch.decision_source === "ai_recorrection" ? `Recorrección IA #${patch.recorrection_count}` : ""}
          </span>
        )}
      </div>

      {/* Severity indicator */}
      {sevConfig && (
        <div className={`flex items-center gap-2 text-xs ${sevConfig.color}`}>
          <span className={`w-5 h-5 rounded-full ${sevConfig.bg} flex items-center justify-center font-bold text-[10px]`}>
            {sevConfig.icon}
          </span>
          Severidad: {sevConfig.label}
        </div>
      )}

      {/* Original vs corrected */}
      <div className="space-y-2">
        <div>
          <span className="text-[10px] uppercase tracking-wider text-plomo font-medium">Original</span>
          <p className="text-sm text-bruma/80 mt-1 leading-relaxed bg-carbon/50 rounded-lg p-2 border border-plomo/10">
            {patch.original_text.length > 300 ? patch.original_text.slice(0, 300) + "..." : patch.original_text}
          </p>
        </div>
        <div>
          <span className="text-[10px] uppercase tracking-wider text-plomo font-medium">
            {patch.edited_text ? "Editado" : "Corregido"}
          </span>
          <p className="text-sm text-bruma mt-1 leading-relaxed bg-krypton/5 rounded-lg p-2 border border-krypton/10">
            {effectiveText.length > 300 ? effectiveText.slice(0, 300) + "..." : effectiveText}
          </p>
        </div>
      </div>

      {/* Explanation */}
      {patch.explanation && (
        <div className="text-xs text-plomo-dark bg-surface-elevated rounded-lg p-2">
          <span className="text-plomo font-medium">Explicación: </span>
          {patch.explanation}
        </div>
      )}

      {/* Metrics bar */}
      <div className="flex gap-3 text-[10px] text-plomo">
        {patch.confidence != null && (
          <div className="flex items-center gap-1">
            <div className="w-12 h-1.5 bg-carbon rounded-full overflow-hidden">
              <div className="h-full bg-krypton/60 rounded-full" style={{ width: `${patch.confidence * 100}%` }} />
            </div>
            <span>{Math.round(patch.confidence * 100)}% conf</span>
          </div>
        )}
        {patch.rewrite_ratio != null && (
          <div className="flex items-center gap-1">
            <div className="w-12 h-1.5 bg-carbon rounded-full overflow-hidden">
              <div className={`h-full rounded-full ${patch.rewrite_ratio > 0.5 ? "bg-amber-500/60" : "bg-emerald-500/60"}`}
                style={{ width: `${Math.min(patch.rewrite_ratio * 100, 100)}%` }} />
            </div>
            <span>{Math.round(patch.rewrite_ratio * 100)}% reescr</span>
          </div>
        )}
      </div>

      {/* Gate results */}
      {patch.gate_results && patch.gate_results.length > 0 && (
        <div className="space-y-1">
          <span className="text-[10px] uppercase tracking-wider text-plomo font-medium">Quality Gates</span>
          <div className="grid gap-1">
            {patch.gate_results.map((g, i) => (
              <div key={i} className={`flex items-center gap-2 text-[10px] px-2 py-1 rounded ${g.passed ? "text-emerald-400 bg-emerald-500/5" : "text-red-400 bg-red-500/5"}`}>
                <span>{g.passed ? "✓" : "✗"}</span>
                <span className="truncate">{g.gate_name}</span>
                {g.critical && !g.passed && <span className="text-red-500 font-bold">CRITICO</span>}
              </div>
            ))}
          </div>
        </div>
      )}

      {error && <p className="text-xs text-red-400 bg-red-500/10 rounded-lg px-3 py-2">{error}</p>}

      {/* Indicador de edición guardada */}
      {editSaved && <EditSavedIndicator />}

      {/* Recorrección en progreso */}
      {recorrecting && <RecorrectingSpinner />}

      {/* Resultado de recorrección con diff */}
      {recorrectResult && <RecorrectResultView result={recorrectResult} />}

      {/* Edit mode */}
      {editMode && (
        <div className="space-y-2 border border-blue-500/20 rounded-lg p-3 bg-blue-500/5">
          <span className="text-[10px] uppercase tracking-wider text-blue-400 font-medium">Editar texto corregido</span>
          <textarea
            value={editText}
            onChange={(e) => setEditText(e.target.value)}
            className="w-full bg-carbon border border-plomo/30 rounded-lg p-2.5 text-sm text-bruma resize-y min-h-[80px] focus:border-krypton/50 focus:outline-none"
            maxLength={10000}
          />
          <div className="flex gap-2">
            <button onClick={handleSaveEdit} disabled={actionLoading || !editText.trim()}
              className="flex-1 px-3 py-1.5 text-xs bg-krypton/20 text-krypton rounded-lg hover:bg-krypton/30 disabled:opacity-50 font-medium">
              Guardar edicion
            </button>
            <button onClick={() => setEditMode(false)}
              className="px-3 py-1.5 text-xs bg-surface-elevated text-plomo rounded-lg hover:bg-plomo/20">
              Cancelar
            </button>
          </div>
        </div>
      )}

      {/* Recorrect mode */}
      {recorrectMode && (
        <div className="space-y-2 border border-violet-500/20 rounded-lg p-3 bg-violet-500/5">
          <span className="text-[10px] uppercase tracking-wider text-violet-400 font-medium">
            Feedback para recorrección IA ({patch.recorrection_count}/{maxRecorrections})
          </span>
          <textarea
            value={feedback}
            onChange={(e) => setFeedback(e.target.value)}
            placeholder="Ej: Mantén el tono formal del autor. No cambies la palabra 'paradigma'..."
            className="w-full bg-carbon border border-plomo/30 rounded-lg p-2.5 text-sm text-bruma resize-y min-h-[60px] focus:border-violet-500/50 focus:outline-none"
            maxLength={1000}
          />
          <div className="flex gap-2">
            <button onClick={handleRecorrect} disabled={actionLoading || feedback.trim().length < 3}
              className="flex-1 px-3 py-1.5 text-xs bg-violet-500/20 text-violet-400 rounded-lg hover:bg-violet-500/30 disabled:opacity-50 font-medium">
              Enviar a IA
            </button>
            <button onClick={() => { setRecorrectMode(false); setFeedback(""); }}
              className="px-3 py-1.5 text-xs bg-surface-elevated text-plomo rounded-lg hover:bg-plomo/20">
              Cancelar
            </button>
          </div>
        </div>
      )}

      {/* Main action buttons — ocultar si hay spinner o resultado pendiente */}
      {isReviewMode && !editMode && !recorrectMode && !recorrecting && !recorrectResult && (
        <div className="space-y-2">
          <div className="grid grid-cols-2 gap-2">
            <button onClick={() => handleReview("accepted")} disabled={actionLoading}
              className="px-3 py-2 text-xs bg-emerald-500/15 text-emerald-400 rounded-lg hover:bg-emerald-500/25 border border-emerald-500/20 disabled:opacity-50 font-medium transition-colors">
              Aceptar
            </button>
            <button onClick={() => handleReview("rejected")} disabled={actionLoading}
              className="px-3 py-2 text-xs bg-red-500/15 text-red-400 rounded-lg hover:bg-red-500/25 border border-red-500/20 disabled:opacity-50 font-medium transition-colors">
              Rechazar
            </button>
          </div>
          <div className="grid grid-cols-2 gap-2">
            <button onClick={() => { setEditMode(true); setEditText(patch.edited_text || patch.corrected_text); }}
              disabled={actionLoading}
              className="px-3 py-2 text-xs bg-blue-500/10 text-blue-400 rounded-lg hover:bg-blue-500/20 border border-blue-500/15 disabled:opacity-50 transition-colors">
              Editar manual
            </button>
            {canRecorrect ? (
              <button onClick={() => setRecorrectMode(true)} disabled={actionLoading}
                className="px-3 py-2 text-xs bg-violet-500/10 text-violet-400 rounded-lg hover:bg-violet-500/20 border border-violet-500/15 disabled:opacity-50 transition-colors">
                Recorregir IA
              </button>
            ) : (
              <div className="px-3 py-2 text-xs text-plomo/50 rounded-lg border border-plomo/10 text-center">
                Limite IA ({maxRecorrections}/{maxRecorrections})
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}


// =============================================
// ReviewStatusBadge — Badge reutilizable
// =============================================

export function ReviewStatusBadge({ status }: { status: string }) {
  const config = REVIEW_STATES[status as ReviewStatus] || REVIEW_STATES.pending;
  return (
    <span className={`inline-flex items-center text-[10px] px-2 py-0.5 rounded-full font-medium ${config.bg} ${config.color} ${config.border} border`}>
      {config.label}
    </span>
  );
}


// =============================================
// FinalizeToolbar — Barra de finalización unificada
// =============================================

interface FinalizeToolbarProps {
  reviewSummary: {
    total_patches: number;
    pending: number;
    manual_review: number;
    accepted: number;
    rejected: number;
    auto_accepted: number;
    bulk_finalized: number;
    can_finalize_strict: boolean;
    can_finalize_quick: boolean;
    render_version: number;
  };
  onFinalize: (mode: "quick" | "strict") => void;
  onReopen?: () => void;
  isCompleted: boolean;
  loading?: boolean;
}

export function FinalizeToolbar({
  reviewSummary,
  onFinalize,
  onReopen,
  isCompleted,
  loading = false,
}: FinalizeToolbarProps) {
  const { pending, manual_review, accepted, rejected, auto_accepted, bulk_finalized, total_patches } = reviewSummary;
  const unresolvedCount = pending + manual_review;
  const resolvedCount = accepted + auto_accepted + rejected + bulk_finalized;

  return (
    <div className="glass-card rounded-xl p-3 border border-plomo/10">
      {/* Summary counters */}
      <div className="flex items-center gap-3 flex-wrap mb-3">
        <div className="flex items-center gap-1.5 text-xs">
          <span className="w-2 h-2 rounded-full bg-emerald-400" />
          <span className="text-emerald-400 font-medium">{accepted + auto_accepted + bulk_finalized}</span>
          <span className="text-plomo">aprobados</span>
        </div>
        <div className="flex items-center gap-1.5 text-xs">
          <span className="w-2 h-2 rounded-full bg-red-400" />
          <span className="text-red-400 font-medium">{rejected}</span>
          <span className="text-plomo">rechazados</span>
        </div>
        {unresolvedCount > 0 && (
          <div className="flex items-center gap-1.5 text-xs">
            <span className="w-2 h-2 rounded-full bg-amber-400 animate-pulse" />
            <span className="text-amber-400 font-bold">{unresolvedCount}</span>
            <span className="text-amber-400">pendientes</span>
          </div>
        )}
        <div className="ml-auto text-[10px] text-plomo">
          v{reviewSummary.render_version} | {resolvedCount}/{total_patches} resueltos
        </div>
      </div>

      {/* Action buttons */}
      <div className="flex gap-2 flex-wrap">
        {!isCompleted && (
          <>
            {unresolvedCount > 0 ? (
              <>
                <button
                  onClick={() => onFinalize("quick")}
                  disabled={loading}
                  className="px-4 py-2 text-xs bg-krypton/20 text-krypton rounded-lg hover:bg-krypton/30 border border-krypton/20 disabled:opacity-50 font-medium transition-colors"
                >
                  Finalizar rapido ({unresolvedCount} pendientes se aprueban)
                </button>
                <button
                  onClick={() => onFinalize("strict")}
                  disabled={loading || !reviewSummary.can_finalize_strict}
                  className="px-4 py-2 text-xs bg-surface-elevated text-plomo rounded-lg hover:bg-plomo/20 border border-plomo/15 disabled:opacity-30 transition-colors"
                  title={!reviewSummary.can_finalize_strict ? `Resuelve ${unresolvedCount} pendientes primero` : ""}
                >
                  Finalizar estricto
                </button>
              </>
            ) : (
              <button
                onClick={() => onFinalize("strict")}
                disabled={loading}
                className="px-4 py-2 text-xs bg-krypton/20 text-krypton rounded-lg hover:bg-krypton/30 border border-krypton/20 disabled:opacity-50 font-medium transition-colors"
              >
                Finalizar y renderizar
              </button>
            )}
          </>
        )}
        {isCompleted && onReopen && (
          <button
            onClick={onReopen}
            disabled={loading}
            className="px-4 py-2 text-xs bg-blue-500/15 text-blue-400 rounded-lg hover:bg-blue-500/25 border border-blue-500/20 disabled:opacity-50 font-medium transition-colors"
          >
            Reabrir revision
          </button>
        )}
      </div>
    </div>
  );
}
