"use client";

import { cn } from "@/lib/utils";
import { type ReactNode } from "react";

/**
 * 21st.dev — Marquee
 * Scroll horizontal continuo de testimonios/logos.
 * Ref: https://21st.dev/components/marquee
 */
interface MarqueeProps {
  children: ReactNode;
  className?: string;
  reverse?: boolean;
  pauseOnHover?: boolean;
}

export function Marquee({
  children,
  className,
  reverse = false,
  pauseOnHover = true,
}: MarqueeProps) {
  return (
    <div
      className={cn(
        "group flex overflow-hidden [mask-image:linear-gradient(to_right,transparent,white_10%,white_90%,transparent)]",
        className
      )}
    >
      <div
        className={cn(
          "flex shrink-0 gap-6",
          reverse ? "animate-marquee-reverse" : "animate-marquee",
          pauseOnHover && "group-hover:[animation-play-state:paused]"
        )}
      >
        {children}
        {children}
      </div>
    </div>
  );
}
