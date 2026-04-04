"use client";

import { useState, useEffect } from "react";
import { getCorrectionFlow } from "@/lib/api";

interface CorrectionRequest {
  step: number;
  type: "languagetool" | "chatgpt_style";
  block_no: number;
  original_text: string;
  context_blocks_count: number;
  context_preview?: Array<{
    block_no: number;
    corrected_text: string;
  }>;
  prompt: string;
  timestamp: string;
  // Costos (solo para chatgpt_style)
  prompt_tokens?: number | null;
  completion_tokens?: number | null;
  total_tokens?: number | null;
  cost_usd?: number | null;
}

interface FlowData {
  document_id: string;
  flow_type: "simulation" | "real";
  summary: {
    total_blocks: number;
    total_requests: number;
    languagetool_requests: number;
    chatgpt_requests: number;
    total_cost_usd?: number;
  };
  requests: CorrectionRequest[];
}

interface CorrectionFlowViewerProps {
  docId: string;
}

export function CorrectionFlowViewer({ docId }: CorrectionFlowViewerProps) {
  const [flowData, setFlowData] = useState<FlowData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedStep, setExpandedStep] = useState<number | null>(null);

  useEffect(() => {
    const fetchFlow = async () => {
      try {
        setLoading(true);
        const data = await getCorrectionFlow(docId === "new" ? "demo" : docId);
        setFlowData(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Error cargando flujo");
      } finally {
        setLoading(false);
      }
    };

    fetchFlow();
  }, [docId]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="flex items-center gap-2 text-plomo">
          <svg className="animate-spin h-4 w-4 text-krypton" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
          Cargando flujo de corrección...
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="glass-card rounded-xl p-6 text-center">
        <p className="text-red-400 mb-3">Error al cargar el flujo</p>
        <p className="text-plomo text-sm">{error}</p>
      </div>
    );
  }

  if (!flowData) {
    return (
      <div className="glass-card rounded-xl p-6 text-center">
        <p className="text-plomo">Sin datos de flujo disponibles</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Header con estadísticas */}
      <div className="glass-card rounded-xl p-5">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-semibold text-bruma uppercase tracking-wider">
            Flujo de peticiones a ChatGPT API
          </h3>
          <span className={`text-xs px-2.5 py-1 rounded-full font-medium ${
            flowData.flow_type === "simulation" 
              ? "bg-purple-900/20 text-purple-400" 
              : "bg-krypton/15 text-krypton"
          }`}>
            {flowData.flow_type === "simulation" ? "Simulación" : "Datos reales"}
          </span>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
          <StatCard label="Bloques" value={flowData.summary.total_blocks.toString()} />
          <StatCard label="LanguageTool" value={flowData.summary.languagetool_requests.toString()} />
          <StatCard label="ChatGPT" value={flowData.summary.chatgpt_requests.toString()} highlight />
          <StatCard label="Total calls" value={flowData.summary.total_requests.toString()} />
          {flowData.summary.total_cost_usd != null && flowData.summary.total_cost_usd > 0 && (
            <StatCard
              label="Costo total"
              value={`$${flowData.summary.total_cost_usd < 0.01 ? flowData.summary.total_cost_usd.toFixed(6) : flowData.summary.total_cost_usd.toFixed(4)}`}
              highlight
            />
          )}
        </div>

        {flowData.flow_type === "simulation" && (
          <div className="mt-4 p-3 bg-purple-900/10 border border-purple-500/20 rounded-lg">
            <p className="text-purple-400 text-sm">
              🔍 <strong>Flujo de demostración</strong> — Este ejemplo muestra cómo sería el contexto 
              acumulado real cuando integres ChatGPT API.
            </p>
          </div>
        )}
      </div>

      {/* Timeline de peticiones */}
      <div className="space-y-3">
        {flowData.requests.map((request) => (
          <RequestCard
            key={request.step}
            request={request}
            isExpanded={expandedStep === request.step}
            onToggle={() => setExpandedStep(expandedStep === request.step ? null : request.step)}
          />
        ))}
      </div>
    </div>
  );
}

function StatCard({ label, value, highlight }: { label: string; value: string; highlight?: boolean }) {
  return (
    <div className="text-center">
      <div className="text-[10px] uppercase tracking-wider text-plomo mb-0.5">{label}</div>
      <div className={`text-lg font-semibold ${highlight ? "text-krypton" : "text-bruma"}`}>
        {value}
      </div>
    </div>
  );
}

function RequestCard({
  request,
  isExpanded,
  onToggle,
}: {
  request: CorrectionRequest;
  isExpanded: boolean;
  onToggle: () => void;
}) {
  const isLanguageTool = request.type === "languagetool";
  const isChatGPT = request.type === "chatgpt_style";

  return (
    <div
      className={`
        bg-surface-elevated border rounded-xl transition-all duration-300 cursor-pointer
        ${isExpanded ? "border-krypton/40" : "border-border hover:border-carbon-200"}
      `}
      onClick={onToggle}
    >
      {/* Header */}
      <div className="px-5 py-4 flex items-center justify-between">
        <div className="flex items-center gap-4">
          {/* Step indicator */}
          <div className={`
            w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold
            ${isLanguageTool ? "bg-blue-900/30 text-blue-400" : "bg-purple-900/30 text-purple-400"}
          `}>
            {request.step}
          </div>

          {/* Request info */}
          <div>
            <div className="flex items-center gap-2">
              <span className={`
                text-xs font-semibold uppercase tracking-wider px-2 py-0.5 rounded
                ${isLanguageTool ? "bg-blue-900/20 text-blue-400" : "bg-purple-900/20 text-purple-400"}
              `}>
                {isLanguageTool ? "LanguageTool" : "ChatGPT API"}
              </span>
              <span className="text-sm text-bruma font-medium">
                Párrafo #{request.block_no}
              </span>
              {isChatGPT && (
                <span className="text-xs text-krypton bg-krypton/10 px-2 py-0.5 rounded-full">
                  +{request.context_blocks_count} contexto
                </span>
              )}
              {request.total_tokens != null && request.total_tokens > 0 && (
                <span className="text-xs text-plomo">
                  {request.total_tokens.toLocaleString("es")} tok
                </span>
              )}
              {request.cost_usd != null && request.cost_usd > 0 && (
                <span className="text-xs text-emerald-400 font-mono">
                  ${request.cost_usd < 0.001 ? request.cost_usd.toFixed(6) : request.cost_usd.toFixed(4)}
                </span>
              )}
            </div>
            <div className="text-xs text-plomo mt-0.5 truncate max-w-md">
              {request.original_text.slice(0, 80)}...
            </div>
          </div>
        </div>

        {/* Toggle icon */}
        <svg
          className={`w-5 h-5 text-plomo transition-transform duration-200 ${isExpanded ? "rotate-180" : ""}`}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={2}
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 8.25l-7.5 7.5-7.5-7.5" />
        </svg>
      </div>

      {/* Expanded content */}
      {isExpanded && (
        <div className="px-5 pb-4 space-y-4" onClick={(e) => e.stopPropagation()}>
          <div className="h-px bg-carbon-300" />

          {/* Texto original */}
          <div>
            <div className="text-xs text-plomo uppercase tracking-wider font-medium mb-2">
              Texto a corregir
            </div>
            <div className="bg-surface border border-border rounded-lg px-4 py-3 text-sm text-bruma">
              {request.original_text}
            </div>
          </div>

          {/* Context preview para ChatGPT */}
          {isChatGPT && request.context_preview && request.context_preview.length > 0 && (
            <div>
              <div className="text-xs text-plomo uppercase tracking-wider font-medium mb-2">
                Contexto previo ({request.context_blocks_count} párrafos)
              </div>
              <div className="space-y-2">
                {request.context_preview.map((ctx) => (
                  <div key={ctx.block_no} className="bg-krypton/5 border border-krypton/20 rounded-lg px-3 py-2">
                    <div className="text-[10px] text-krypton font-medium mb-1">
                      Párrafo #{ctx.block_no} (ya corregido)
                    </div>
                    <div className="text-xs text-bruma/80">
                      {ctx.corrected_text}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Prompt completo */}
          <div>
            <div className="text-xs text-plomo uppercase tracking-wider font-medium mb-2">
              {isLanguageTool ? "Llamada API LanguageTool" : "Prompt ChatGPT"}
            </div>
            <div className="bg-surface border border-border rounded-lg px-4 py-3 text-xs font-mono text-bruma whitespace-pre-wrap">
              {request.prompt}
            </div>
          </div>

          {/* Metadata */}
          <div className="flex items-center justify-between text-[11px] text-plomo pt-2 border-t border-border">
            <span>{new Date(request.timestamp).toLocaleString("es")}</span>
            <span>{isLanguageTool ? "Corrección determinista" : "Corrección de estilo con IA"}</span>
          </div>
        </div>
      )}
    </div>
  );
}