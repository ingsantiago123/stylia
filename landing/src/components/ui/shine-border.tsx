"use client";

import { cn } from "@/lib/utils";
import { type ReactNode } from "react";

/**
 * 21st.dev — ShineBorder
 * Contenedor con borde brillante animado.
 * Ref: https://21st.dev/components/shine-border
 */
interface ShineBorderProps {
  children: ReactNode;
  className?: string;
  borderWidth?: number;
  duration?: number;
  color?: string[];
}

export function ShineBorder({
  children,
  className,
  borderWidth = 1,
  duration = 6,
  color = ["#D4FF00", "transparent", "#D4FF00"],
}: ShineBorderProps) {
  return (
    <div
      className={cn("relative overflow-hidden rounded-2xl p-[1px]", className)}
      style={{
        background: `linear-gradient(var(--shine-angle, 0deg), ${color.join(", ")})`,
        animation: `shine-rotate ${duration}s linear infinite`,
      }}
    >
      <style jsx>{`
        @keyframes shine-rotate {
          0% { --shine-angle: 0deg; }
          100% { --shine-angle: 360deg; }
        }
        @property --shine-angle {
          syntax: '<angle>';
          initial-value: 0deg;
          inherits: false;
        }
      `}</style>
      <div
        className="relative rounded-2xl bg-carbon"
        style={{ padding: borderWidth > 1 ? "0" : undefined }}
      >
        {children}
      </div>
    </div>
  );
}
