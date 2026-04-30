import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

const prodFallbackAppUrl = "https://ingsantiago123.github.io/stylia-landing/";

export const APP_URL =
  process.env.NEXT_PUBLIC_APP_URL ||
  (process.env.NODE_ENV === "production" ? prodFallbackAppUrl : "http://localhost:3000");
