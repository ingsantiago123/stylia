"use client";

import { useRef, useEffect, useState, type ReactNode } from "react";
import { cn } from "@/lib/utils";

/**
 * 21st.dev — BlurFade
 * Animación de entrada con blur + fade al hacer scroll.
 * Ref: https://21st.dev/components/blur-fade
 */
interface BlurFadeProps {
  children: ReactNode;
  className?: string;
  delay?: number;
  direction?: "up" | "down" | "left" | "right";
}

export function BlurFade({
  children,
  className,
  delay = 0,
  direction = "up",
}: BlurFadeProps) {
  const ref = useRef<HTMLDivElement>(null);
  const [isVisible, setIsVisible] = useState(false);

  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setIsVisible(true);
          observer.disconnect();
        }
      },
      { threshold: 0.1, rootMargin: "0px 0px -50px 0px" }
    );
    if (ref.current) observer.observe(ref.current);
    return () => observer.disconnect();
  }, []);

  const transforms = {
    up: "translate-y-6",
    down: "-translate-y-6",
    left: "translate-x-6",
    right: "-translate-x-6",
  };

  return (
    <div
      ref={ref}
      className={cn(
        "transition-all duration-700 ease-out",
        isVisible
          ? "opacity-100 blur-0 translate-x-0 translate-y-0"
          : `opacity-0 blur-[6px] ${transforms[direction]}`,
        className
      )}
      style={{ transitionDelay: `${delay}ms` }}
    >
      {children}
    </div>
  );
}
