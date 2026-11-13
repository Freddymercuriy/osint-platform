import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        // Fon va sirtlar (chuqur "intelligence center" navy)
        ink: {
          950: "#05070d", // sahifa foni
          900: "#090d17", // panel/sidebar
          850: "#0d1220", // karta
          800: "#121a2b", // karta hover / input
          700: "#1b2538", // chegara (kuchli)
          600: "#26324a", // chegara
        },
        // Brend aksenti
        brand: {
          cyan: "#22d3ee",
          sky: "#38bdf8",
          violet: "#8b5cf6",
          fuchsia: "#d946ef",
        },
      },
      fontFamily: {
        sans: ["var(--font-sans)", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["var(--font-mono)", "ui-monospace", "SFMono-Regular", "monospace"],
      },
      backgroundImage: {
        "brand-gradient": "linear-gradient(135deg, #22d3ee 0%, #8b5cf6 55%, #d946ef 100%)",
        "brand-gradient-soft":
          "linear-gradient(135deg, rgba(34,211,238,.16) 0%, rgba(139,92,246,.16) 60%, rgba(217,70,239,.10) 100%)",
      },
      boxShadow: {
        glow: "0 0 0 1px rgba(34,211,238,.25), 0 8px 40px -8px rgba(34,211,238,.35)",
        "glow-violet": "0 0 0 1px rgba(139,92,246,.3), 0 8px 40px -8px rgba(139,92,246,.45)",
        card: "0 1px 0 0 rgba(255,255,255,.04) inset, 0 20px 50px -25px rgba(0,0,0,.8)",
      },
      keyframes: {
        "fade-in": {
          from: { opacity: "0", transform: "translateY(6px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
        "pulse-ring": {
          "0%": { transform: "scale(.8)", opacity: ".7" },
          "100%": { transform: "scale(2.4)", opacity: "0" },
        },
        scan: {
          "0%": { transform: "translateY(-100%)" },
          "100%": { transform: "translateY(100%)" },
        },
        shimmer: {
          "0%": { backgroundPosition: "-400px 0" },
          "100%": { backgroundPosition: "400px 0" },
        },
        "spin-slow": { to: { transform: "rotate(360deg)" } },
        float: {
          "0%,100%": { transform: "translateY(0)" },
          "50%": { transform: "translateY(-8px)" },
        },
      },
      animation: {
        "fade-in": "fade-in .45s cubic-bezier(.2,.7,.2,1) both",
        "pulse-ring": "pulse-ring 1.8s cubic-bezier(.2,.7,.2,1) infinite",
        scan: "scan 3.5s linear infinite",
        shimmer: "shimmer 1.4s linear infinite",
        "spin-slow": "spin-slow 14s linear infinite",
        float: "float 6s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};

export default config;
