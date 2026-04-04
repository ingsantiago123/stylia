"use client";

import { cn } from "@/lib/utils";

/**
 * 21st.dev — BorderBeam
 * Borde animado con un "rayo" que recorre el perímetro.
 * Ref: https://21st.dev/components/border-beam
 */
interface BorderBeamProps {
  className?: string;
  size?: number;
  duration?: number;
  delay?: number;
  color?: string;
}

export function BorderBeam({
  className,
  size = 200,
  duration = 4,
  delay = 0,
  color = "#D4FF00",
}: BorderBeamProps) {
  return (
    <div className={cn("pointer-events-none absolute inset-0 overflow-hidden rounded-[inherit]", className)}>
      <div
        className="absolute inset-0"
        style={{
          mask: "linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0)",
          maskComposite: "exclude",
          WebkitMaskComposite: "xor",
          padding: "1px",
          borderRadius: "inherit",
        }}
      >
        <div
          className="absolute"
          style={{
            width: `${size}px`,
            height: `${size}px`,
            background: `radial-gradient(circle, ${color} 0%, transparent 70%)`,
            animation: `border-beam ${duration}s linear ${delay}s infinite`,
            offsetPath: "rect(0 auto auto 0 round 1px)",
            offsetAnchor: "center center",
          }}
        />
      </div>
    </div>
  );
}
