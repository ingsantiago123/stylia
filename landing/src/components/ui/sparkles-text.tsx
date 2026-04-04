"use client";

import { cn } from "@/lib/utils";
import { type ReactNode } from "react";

/**
 * 21st.dev — SparklesText
 * Texto con partículas brillantes alrededor.
 * Ref: https://21st.dev/components/sparkles-text
 */
interface SparklesTextProps {
  children: ReactNode;
  className?: string;
}

export function SparklesText({ children, className }: SparklesTextProps) {
  const sparkles = Array.from({ length: 6 }, (_, i) => ({
    id: i,
    top: `${Math.random() * 100}%`,
    left: `${Math.random() * 100}%`,
    delay: `${Math.random() * 2}s`,
    size: 4 + Math.random() * 6,
  }));

  return (
    <span className={cn("relative inline-block", className)}>
      {sparkles.map((s) => (
        <svg
          key={s.id}
          className="pointer-events-none absolute animate-sparkle"
          style={{
            top: s.top,
            left: s.left,
            animationDelay: s.delay,
            width: s.size,
            height: s.size,
          }}
          viewBox="0 0 24 24"
          fill="none"
          aria-hidden="true"
        >
          <path
            d="M12 0L14.5 9.5L24 12L14.5 14.5L12 24L9.5 14.5L0 12L9.5 9.5L12 0Z"
            fill="#D4FF00"
          />
        </svg>
      ))}
      {children}
    </span>
  );
}
