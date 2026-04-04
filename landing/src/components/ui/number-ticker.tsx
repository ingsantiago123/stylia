"use client";

import { useEffect, useRef, useState } from "react";
import { cn } from "@/lib/utils";

/**
 * 21st.dev — NumberTicker
 * Animación de números que incrementan hacia el valor final.
 * Ref: https://21st.dev/components/number-ticker
 */
interface NumberTickerProps {
  value: number;
  suffix?: string;
  prefix?: string;
  decimals?: number;
  duration?: number;
  className?: string;
}

export function NumberTicker({
  value,
  suffix = "",
  prefix = "",
  decimals = 0,
  duration = 2000,
  className,
}: NumberTickerProps) {
  const [displayValue, setDisplayValue] = useState(0);
  const [hasAnimated, setHasAnimated] = useState(false);
  const ref = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting && !hasAnimated) {
          setHasAnimated(true);
          const startTime = Date.now();
          const animate = () => {
            const elapsed = Date.now() - startTime;
            const progress = Math.min(elapsed / duration, 1);
            // Ease out cubic
            const eased = 1 - Math.pow(1 - progress, 3);
            setDisplayValue(eased * value);
            if (progress < 1) requestAnimationFrame(animate);
          };
          requestAnimationFrame(animate);
        }
      },
      { threshold: 0.3 }
    );
    if (ref.current) observer.observe(ref.current);
    return () => observer.disconnect();
  }, [value, duration, hasAnimated]);

  return (
    <span ref={ref} className={cn("tabular-nums", className)}>
      {prefix}
      {displayValue.toFixed(decimals)}
      {suffix}
    </span>
  );
}
