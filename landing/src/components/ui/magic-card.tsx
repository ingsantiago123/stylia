"use client";

import { cn } from "@/lib/utils";
import { useRef, useState, type ReactNode } from "react";

/**
 * 21st.dev — MagicCard
 * Card con efecto spotlight que sigue el cursor.
 * Ref: https://21st.dev/components/magic-card
 */
interface MagicCardProps {
  children: ReactNode;
  className?: string;
  spotlightColor?: string;
}

export function MagicCard({
  children,
  className,
  spotlightColor = "rgba(212, 255, 0, 0.08)",
}: MagicCardProps) {
  const ref = useRef<HTMLDivElement>(null);
  const [position, setPosition] = useState({ x: 0, y: 0 });
  const [opacity, setOpacity] = useState(0);

  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!ref.current) return;
    const rect = ref.current.getBoundingClientRect();
    setPosition({ x: e.clientX - rect.left, y: e.clientY - rect.top });
  };

  return (
    <div
      ref={ref}
      onMouseMove={handleMouseMove}
      onMouseEnter={() => setOpacity(1)}
      onMouseLeave={() => setOpacity(0)}
      className={cn(
        "relative overflow-hidden rounded-2xl border border-border bg-surface p-6",
        "transition-shadow duration-300 hover:shadow-card-hover hover:border-border/80",
        className
      )}
    >
      {/* Spotlight effect */}
      <div
        className="pointer-events-none absolute inset-0 transition-opacity duration-300"
        style={{
          opacity,
          background: `radial-gradient(400px circle at ${position.x}px ${position.y}px, ${spotlightColor}, transparent 60%)`,
        }}
      />
      <div className="relative z-10">{children}</div>
    </div>
  );
}
