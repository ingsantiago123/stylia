"use client";

import { useState, useRef, useEffect } from "react";

interface TooltipConfig {
  humanLabel: string;
  explanation: string;
  example?: string;
}

interface HumanizedTooltipProps {
  config: TooltipConfig;
  children?: React.ReactNode;
  position?: "top" | "bottom" | "left" | "right";
}

export function HumanizedTooltip({ config, children, position = "top" }: HumanizedTooltipProps) {
  const [visible, setVisible] = useState(false);
  const [coords, setCoords] = useState({ x: 0, y: 0 });
  const triggerRef = useRef<HTMLSpanElement>(null);
  const tooltipRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!visible || !triggerRef.current || !tooltipRef.current) return;
    const tr = triggerRef.current.getBoundingClientRect();
    const tt = tooltipRef.current.getBoundingClientRect();
    let x = tr.left + tr.width / 2 - tt.width / 2;
    let y = tr.top - tt.height - 10;
    if (position === "bottom") y = tr.bottom + 10;
    if (position === "left") { x = tr.left - tt.width - 10; y = tr.top + tr.height / 2 - tt.height / 2; }
    if (position === "right") { x = tr.right + 10; y = tr.top + tr.height / 2 - tt.height / 2; }
    x = Math.max(8, Math.min(x, window.innerWidth - tt.width - 8));
    y = Math.max(8, y);
    setCoords({ x, y });
  }, [visible, position]);

  return (
    <>
      <span
        ref={triggerRef}
        className="inline-flex items-center gap-1 cursor-help"
        onMouseEnter={() => setVisible(true)}
        onMouseLeave={() => setVisible(false)}
        onFocus={() => setVisible(true)}
        onBlur={() => setVisible(false)}
        tabIndex={0}
        role="button"
        aria-label={`Más información: ${config.humanLabel}`}
      >
        {children ?? (
          <span className="text-bruma font-medium">{config.humanLabel}</span>
        )}
        <span className="inline-flex items-center justify-center w-3.5 h-3.5 rounded-full bg-plomo/20 text-plomo text-[9px] font-bold leading-none select-none hover:bg-krypton/20 hover:text-krypton transition-colors">
          ?
        </span>
      </span>

      {visible && (
        <div
          ref={tooltipRef}
          role="tooltip"
          style={{ position: "fixed", left: coords.x, top: coords.y, zIndex: 9999 }}
          className="w-64 bg-surface-elevated border border-border rounded-xl p-3 shadow-card pointer-events-none animate-scale-in"
        >
          <p className="text-xs font-semibold text-krypton mb-1">{config.humanLabel}</p>
          <p className="text-xs text-bruma/80 leading-relaxed">{config.explanation}</p>
          {config.example && (
            <p className="mt-2 text-[11px] text-plomo italic border-t border-border pt-2">
              Ej: {config.example}
            </p>
          )}
          <div
            className="absolute w-2 h-2 bg-surface-elevated border-border rotate-45"
            style={position === "top"
              ? { bottom: -5, left: "calc(50% - 4px)", borderRight: "1px solid", borderBottom: "1px solid" }
              : { top: -5, left: "calc(50% - 4px)", borderLeft: "1px solid", borderTop: "1px solid" }
            }
          />
        </div>
      )}
    </>
  );
}

// Glosario centralizado de métricas técnicas → lenguaje humano
export const METRIC_GLOSSARY = {
  max_expansion_ratio: {
    humanLabel: "Libertad de expansión",
    explanation: "Cuántas palabras extra puede añadir la IA por párrafo para mejorar la claridad. Un 10% significa que si tienes 100 palabras, puede llegar a 110.",
    example: "1.10 = hasta 10% más de palabras por párrafo",
  },
  max_rewrite_ratio: {
    humanLabel: "Profundidad de reescritura",
    explanation: "Qué porcentaje del texto puede reescribir la IA. Con 0.30, puede reformular hasta el 30% del párrafo, respetando el resto.",
    example: "0.30 = máximo el 30% del párrafo reformulado",
  },
  intervention_level: {
    humanLabel: "Nivel de intervención",
    explanation: "Cuánto puede modificar la IA tu texto. Desde correcciones mínimas (solo errores obvios) hasta una edición agresiva para mayor impacto.",
    example: "Sutil = toca poco; Agresiva = refactoriza activamente",
  },
  target_inflesz_min: {
    humanLabel: "Legibilidad mínima",
    explanation: "Puntuación INFLESZ mínima objetivo. Cuanto más alta, más fácil de leer es el texto. 0-40 es muy difícil, 80-100 es muy fácil.",
    example: "70 = legibilidad para público general",
  },
  preserve_author_voice: {
    humanLabel: "Preservar voz del autor",
    explanation: "Si está activado, la IA protege activamente el estilo personal del autor: sus giros, su ritmo y sus expresiones características.",
    example: "Activado = la IA no elimina tu idiolecto",
  },
  register_constraints: {
    humanLabel: "Restricciones de registro",
    explanation: "Reglas de estilo obligatorias, como usar lenguaje inclusivo, evitar anglicismos o mantener el tuteo en toda la obra.",
    example: "lenguaje_inclusivo = la IA usa siempre formas neutras",
  },
} as const satisfies Record<string, TooltipConfig>;
