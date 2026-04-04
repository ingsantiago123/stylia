/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: "class",
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        // STYLIA brand tokens
        carbon: {
          DEFAULT: "#0A0A0B",
          50: "#2A2A2E",
          100: "#1C1C1F",
          200: "#141416",
          300: "#101012",
        },
        krypton: {
          DEFAULT: "#D4FF00",
          50: "#F0FFB3",
          100: "#E8FF80",
          200: "#DFFF4D",
          300: "#D4FF00",
          400: "#BFEF00",
          dim: "rgba(212, 255, 0, 0.08)",
          glow: "rgba(212, 255, 0, 0.15)",
          bright: "rgba(212, 255, 0, 0.3)",
        },
        bruma: {
          DEFAULT: "#F5F5F7",
          muted: "#C7C7CC",
        },
        plomo: {
          DEFAULT: "#8E8E93",
          light: "#AEAEB2",
          dark: "#636366",
        },
        surface: {
          DEFAULT: "#141416",
          elevated: "#1C1C1F",
          hover: "#222225",
        },
        border: {
          DEFAULT: "#2A2A2E",
          subtle: "#1F1F23",
        },
      },
      fontFamily: {
        sans: ['"Inter"', "system-ui", "-apple-system", "sans-serif"],
        mono: ['"JetBrains Mono"', '"Fira Code"', "monospace"],
      },
      fontSize: {
        "display-1": ["4.5rem", { lineHeight: "1.1", letterSpacing: "-0.02em", fontWeight: "700" }],
        "display-2": ["3.5rem", { lineHeight: "1.15", letterSpacing: "-0.02em", fontWeight: "700" }],
        "heading-1": ["3rem", { lineHeight: "1.2", letterSpacing: "-0.01em", fontWeight: "700" }],
        "heading-2": ["2.25rem", { lineHeight: "1.25", letterSpacing: "-0.01em", fontWeight: "600" }],
        "heading-3": ["1.5rem", { lineHeight: "1.35", fontWeight: "600" }],
        "body-lg": ["1.25rem", { lineHeight: "1.7" }],
        "body": ["1.125rem", { lineHeight: "1.7" }],
        "body-sm": ["1rem", { lineHeight: "1.6" }],
        "caption": ["0.875rem", { lineHeight: "1.5" }],
      },
      spacing: {
        18: "4.5rem",
        22: "5.5rem",
        26: "6.5rem",
        30: "7.5rem",
      },
      borderRadius: {
        "4xl": "2rem",
      },
      boxShadow: {
        "glow-sm": "0 0 15px rgba(212, 255, 0, 0.15)",
        "glow-md": "0 0 30px rgba(212, 255, 0, 0.2)",
        "glow-lg": "0 0 60px rgba(212, 255, 0, 0.25)",
        "card": "0 1px 3px rgba(0,0,0,0.3), 0 4px 12px rgba(0,0,0,0.2)",
        "card-hover": "0 4px 12px rgba(0,0,0,0.4), 0 8px 24px rgba(0,0,0,0.3)",
      },
      animation: {
        "shimmer": "shimmer 2s linear infinite",
        "border-beam": "border-beam 4s linear infinite",
        "pulse-slow": "pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite",
        "float": "float 6s ease-in-out infinite",
        "glow": "glow 2s ease-in-out infinite alternate",
        "marquee": "marquee 40s linear infinite",
        "marquee-reverse": "marquee-reverse 40s linear infinite",
        "fade-in": "fade-in 0.6s ease-out forwards",
        "fade-in-up": "fade-in-up 0.6s ease-out forwards",
        "slide-in-left": "slide-in-left 0.6s ease-out forwards",
        "slide-in-right": "slide-in-right 0.6s ease-out forwards",
        "number-tick": "number-tick 1.5s ease-out forwards",
        "beam": "beam 3s ease-in-out infinite",
        "sparkle": "sparkle 2s ease-in-out infinite",
        "grid-fade": "grid-fade 3s ease-in-out infinite alternate",
      },
      keyframes: {
        shimmer: {
          "0%": { backgroundPosition: "-200% 0" },
          "100%": { backgroundPosition: "200% 0" },
        },
        "border-beam": {
          "0%": { offsetDistance: "0%" },
          "100%": { offsetDistance: "100%" },
        },
        float: {
          "0%, 100%": { transform: "translateY(0)" },
          "50%": { transform: "translateY(-10px)" },
        },
        glow: {
          "0%": { boxShadow: "0 0 5px rgba(212, 255, 0, 0.1)" },
          "100%": { boxShadow: "0 0 25px rgba(212, 255, 0, 0.3)" },
        },
        marquee: {
          "0%": { transform: "translateX(0%)" },
          "100%": { transform: "translateX(-50%)" },
        },
        "marquee-reverse": {
          "0%": { transform: "translateX(-50%)" },
          "100%": { transform: "translateX(0%)" },
        },
        "fade-in": {
          "0%": { opacity: "0" },
          "100%": { opacity: "1" },
        },
        "fade-in-up": {
          "0%": { opacity: "0", transform: "translateY(20px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        "slide-in-left": {
          "0%": { opacity: "0", transform: "translateX(-30px)" },
          "100%": { opacity: "1", transform: "translateX(0)" },
        },
        "slide-in-right": {
          "0%": { opacity: "0", transform: "translateX(30px)" },
          "100%": { opacity: "1", transform: "translateX(0)" },
        },
        "number-tick": {
          "0%": { transform: "translateY(100%)", opacity: "0" },
          "100%": { transform: "translateY(0)", opacity: "1" },
        },
        beam: {
          "0%, 100%": { opacity: "0.4", transform: "translateY(-5px)" },
          "50%": { opacity: "1", transform: "translateY(5px)" },
        },
        sparkle: {
          "0%, 100%": { opacity: "0.5", transform: "scale(0.8)" },
          "50%": { opacity: "1", transform: "scale(1.2)" },
        },
        "grid-fade": {
          "0%": { opacity: "0.3" },
          "100%": { opacity: "0.6" },
        },
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
};
