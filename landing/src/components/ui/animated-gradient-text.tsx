"use client";

import { cn } from "@/lib/utils";
import { type ReactNode } from "react";

/**
 * 21st.dev — AnimatedGradientText
 * Badge/texto con gradiente animado.
 * Ref: https://21st.dev/components/animated-gradient-text
 */
interface AnimatedGradientTextProps {
  children: ReactNode;
  className?: string;
}

export function AnimatedGradientText({
  children,
  className,
}: AnimatedGradientTextProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-2 rounded-full",
        "border border-krypton/20 bg-krypton/[0.05] px-4 py-1.5",
        "text-sm font-medium text-krypton",
        "backdrop-blur-sm",
        "animate-shimmer bg-[length:200%_100%]",
        "bg-gradient-to-r from-krypton/80 via-krypton to-krypton/80 bg-clip-text text-transparent",
        className
      )}
    >
      {children}
    </span>
  );
}
