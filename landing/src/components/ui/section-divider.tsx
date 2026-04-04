"use client";

import { cn } from "@/lib/utils";

/**
 * 21st.dev — SectionDivider
 * Separador decorativo con gradiente krypton.
 */
interface SectionDividerProps {
  className?: string;
  variant?: "line" | "fade" | "dots";
}

export function SectionDivider({
  className,
  variant = "line",
}: SectionDividerProps) {
  if (variant === "dots") {
    return (
      <div className={cn("flex items-center justify-center gap-2 py-4", className)}>
        <div className="h-1.5 w-1.5 rounded-full bg-krypton/30" />
        <div className="h-1.5 w-1.5 rounded-full bg-krypton/50" />
        <div className="h-1.5 w-1.5 rounded-full bg-krypton/30" />
      </div>
    );
  }

  if (variant === "fade") {
    return (
      <div className={cn("py-4", className)}>
        <div className="h-px bg-gradient-to-r from-transparent via-krypton/20 to-transparent" />
      </div>
    );
  }

  return (
    <div className={cn("py-4", className)}>
      <div className="h-px bg-gradient-to-r from-transparent via-border to-transparent" />
    </div>
  );
}
