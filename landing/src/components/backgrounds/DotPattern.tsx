"use client";

import { cn } from "@/lib/utils";

/**
 * 21st.dev — DotPattern (Background)
 * Patrón de puntos SVG como fondo decorativo.
 * Inspirado en: https://21st.dev/components/dot-pattern
 */
interface DotPatternProps {
  className?: string;
  dotSize?: number;
  dotColor?: string;
  gap?: number;
}

export function DotPattern({
  className,
  dotSize = 1.2,
  dotColor = "rgba(212, 255, 0, 0.12)",
  gap = 24,
}: DotPatternProps) {
  return (
    <svg
      aria-hidden="true"
      className={cn(
        "pointer-events-none absolute inset-0 h-full w-full",
        className
      )}
    >
      <defs>
        <pattern
          id="dot-pattern"
          x="0"
          y="0"
          width={gap}
          height={gap}
          patternUnits="userSpaceOnUse"
        >
          <circle cx={dotSize} cy={dotSize} r={dotSize} fill={dotColor} />
        </pattern>
      </defs>
      <rect width="100%" height="100%" fill="url(#dot-pattern)" />
    </svg>
  );
}
