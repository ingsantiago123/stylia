"use client";

import { cn } from "@/lib/utils";
import { type ReactNode } from "react";

/**
 * 21st.dev — BentoGrid
 * Layout estilo bento box para features.
 * Ref: https://21st.dev/components/bento-grid
 */
interface BentoGridProps {
  children: ReactNode;
  className?: string;
}

export function BentoGrid({ children, className }: BentoGridProps) {
  return (
    <div
      className={cn(
        "grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4",
        className
      )}
    >
      {children}
    </div>
  );
}

interface BentoCardProps {
  children: ReactNode;
  className?: string;
  colSpan?: 1 | 2 | 3;
  rowSpan?: 1 | 2;
}

export function BentoCard({
  children,
  className,
  colSpan = 1,
  rowSpan = 1,
}: BentoCardProps) {
  return (
    <div
      className={cn(
        "group relative overflow-hidden rounded-2xl border border-border bg-surface p-6",
        "transition-all duration-300 hover:border-krypton/20 hover:shadow-card-hover",
        colSpan === 2 && "md:col-span-2",
        colSpan === 3 && "lg:col-span-3",
        rowSpan === 2 && "row-span-2",
        className
      )}
    >
      {children}
    </div>
  );
}
