"use client";

import { cn } from "@/lib/utils";

/**
 * 21st.dev — GridPattern (Background)
 * Grid retro con fade radial. Inspirado en retro-grid de 21st.dev.
 */
interface GridPatternProps {
  className?: string;
  cellSize?: number;
  strokeColor?: string;
}

export function GridPattern({
  className,
  cellSize = 60,
  strokeColor = "rgba(212, 255, 0, 0.06)",
}: GridPatternProps) {
  return (
    <div className={cn("pointer-events-none absolute inset-0 overflow-hidden", className)}>
      <svg
        aria-hidden="true"
        className="absolute inset-0 h-full w-full animate-grid-fade"
      >
        <defs>
          <pattern
            id="grid-pattern"
            x="0"
            y="0"
            width={cellSize}
            height={cellSize}
            patternUnits="userSpaceOnUse"
          >
            <path
              d={`M ${cellSize} 0 L 0 0 0 ${cellSize}`}
              fill="none"
              stroke={strokeColor}
              strokeWidth="1"
            />
          </pattern>
        </defs>
        <rect width="100%" height="100%" fill="url(#grid-pattern)" />
      </svg>
      {/* Radial fade mask */}
      <div
        className="absolute inset-0"
        style={{
          background:
            "radial-gradient(ellipse at center, transparent 30%, #0A0A0B 75%)",
        }}
      />
    </div>
  );
}
