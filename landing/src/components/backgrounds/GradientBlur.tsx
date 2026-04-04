"use client";

import { cn } from "@/lib/utils";

/**
 * 21st.dev — GradientBlur / Ambient Background
 * Manchas de color difuminadas (ambient gradient).
 */
interface GradientBlurProps {
  className?: string;
  variant?: "hero" | "section" | "cta";
}

export function GradientBlur({ className, variant = "hero" }: GradientBlurProps) {
  const variants = {
    hero: (
      <>
        <div className="absolute -top-40 -left-40 w-[600px] h-[600px] rounded-full bg-krypton/[0.07] blur-[120px]" />
        <div className="absolute -top-20 right-0 w-[500px] h-[500px] rounded-full bg-krypton/[0.04] blur-[100px]" />
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[400px] rounded-full bg-krypton/[0.03] blur-[150px]" />
      </>
    ),
    section: (
      <>
        <div className="absolute top-0 left-1/4 w-[400px] h-[400px] rounded-full bg-krypton/[0.04] blur-[100px]" />
        <div className="absolute bottom-0 right-1/4 w-[300px] h-[300px] rounded-full bg-krypton/[0.03] blur-[80px]" />
      </>
    ),
    cta: (
      <>
        <div className="absolute inset-0 bg-gradient-to-b from-krypton/[0.05] via-transparent to-transparent" />
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[300px] rounded-full bg-krypton/[0.08] blur-[120px]" />
      </>
    ),
  };

  return (
    <div
      className={cn("pointer-events-none absolute inset-0 overflow-hidden", className)}
      aria-hidden="true"
    >
      {variants[variant]}
    </div>
  );
}
