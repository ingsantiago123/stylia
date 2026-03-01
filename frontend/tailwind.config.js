/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./src/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        carbon: {
          DEFAULT: "#121212",
          50: "#2A2A2A",
          100: "#1E1E1E",
          200: "#1A1A1A",
          300: "#161616",
        },
        krypton: {
          DEFAULT: "#D4FF00",
          dim: "rgba(212, 255, 0, 0.15)",
          glow: "rgba(212, 255, 0, 0.3)",
        },
        bruma: "#F5F5F7",
        plomo: "#8E8E93",
      },
      fontFamily: {
        sans: ['"Inter"', 'system-ui', '-apple-system', 'sans-serif'],
      },
      animation: {
        "pulse-slow": "pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite",
        "glow": "glow 2s ease-in-out infinite alternate",
      },
      keyframes: {
        glow: {
          "0%": { boxShadow: "0 0 5px rgba(212, 255, 0, 0.2)" },
          "100%": { boxShadow: "0 0 20px rgba(212, 255, 0, 0.4)" },
        },
      },
    },
  },
  plugins: [],
};
