"use client";

import { cn } from "@/lib/utils";
import { type ReactNode } from "react";

/**
 * 21st.dev — ShimmerButton
 * Botón con efecto shimmer/brillo deslizante.
 * Ref: https://21st.dev/components/shimmer-button
 */
interface ShimmerButtonProps {
  children: ReactNode;
  className?: string;
  onClick?: () => void;
  href?: string;
  size?: "sm" | "md" | "lg";
}

export function ShimmerButton({
  children,
  className,
  onClick,
  href,
  size = "md",
}: ShimmerButtonProps) {
  const sizes = {
    sm: "px-5 py-2.5 text-sm",
    md: "px-8 py-3.5 text-base",
    lg: "px-10 py-4.5 text-lg",
  };

  const inner = (
    <>
      {/* Shimmer overlay */}
      <div className="absolute inset-0 overflow-hidden rounded-xl">
        <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/10 to-transparent animate-shimmer bg-[length:200%_100%]" />
      </div>
      {/* Glow */}
      <div className="absolute inset-0 rounded-xl bg-krypton/20 blur-xl opacity-0 group-hover:opacity-100 transition-opacity duration-500" />
      {/* Content */}
      <span className="relative z-10 flex items-center gap-2 font-semibold">
        {children}
      </span>
    </>
  );

  const baseClass = cn(
    "group relative inline-flex items-center justify-center overflow-hidden rounded-xl",
    "bg-krypton text-carbon font-semibold",
    "transition-all duration-300 ease-out",
    "hover:shadow-glow-md hover:scale-[1.02] active:scale-[0.98]",
    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-krypton focus-visible:ring-offset-2 focus-visible:ring-offset-carbon",
    sizes[size],
    className
  );

  if (href) {
    return (
      <a href={href} className={baseClass} target="_blank" rel="noopener noreferrer">
        {inner}
      </a>
    );
  }

  return (
    <button onClick={onClick} className={baseClass}>
      {inner}
    </button>
  );
}
