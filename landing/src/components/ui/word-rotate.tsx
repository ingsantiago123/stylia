"use client";

import { useState, useEffect } from "react";
import { cn } from "@/lib/utils";

/**
 * 21st.dev — WordRotate
 * Rotación de palabras con animación fade.
 * Ref: https://21st.dev/components/word-rotate
 */
interface WordRotateProps {
  words: string[];
  className?: string;
  interval?: number;
}

export function WordRotate({
  words,
  className,
  interval = 3000,
}: WordRotateProps) {
  const [currentIndex, setCurrentIndex] = useState(0);
  const [isVisible, setIsVisible] = useState(true);

  useEffect(() => {
    const timer = setInterval(() => {
      setIsVisible(false);
      setTimeout(() => {
        setCurrentIndex((prev) => (prev + 1) % words.length);
        setIsVisible(true);
      }, 300);
    }, interval);
    return () => clearInterval(timer);
  }, [words, interval]);

  return (
    <span
      className={cn(
        "inline-block transition-all duration-300",
        isVisible ? "opacity-100 translate-y-0" : "opacity-0 translate-y-2",
        className
      )}
    >
      {words[currentIndex]}
    </span>
  );
}
