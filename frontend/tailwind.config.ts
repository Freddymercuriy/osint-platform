import type { Config } from "tailwindcss";

/** Semantik tokenlar — qiymatlari `app/globals.css` da (light: :root, dark: .dark). Qo'llanma: docs/design-system.md */
const token = (name: string) => `rgb(var(--${name}) / <alpha-value>)`;

const config: Config = {
  darkMode: "class",
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./lib/**/*.{js,ts,jsx,tsx}",
  ],
  // Bazadan keladigan kategoriya ranglari (categories.color) — dinamik klass nomlari
  safelist: [
    {
      pattern:
        /^tone-(red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose|slate)$/,
    },
  ],
  theme: {
    extend: {
      colors: {
        bg: token("bg"),
        surface: { DEFAULT: token("surface"), 2: token("surface-2") },
        border: { DEFAULT: token("border"), strong: token("border-strong") },
        fg: { DEFAULT: token("fg"), muted: token("fg-muted"), subtle: token("fg-subtle") },
        primary: { DEFAULT: token("primary"), fg: token("primary-fg"), soft: token("primary-soft") },
        ring: token("ring"),
        success: token("success"),
        warning: token("warning"),
        danger: token("danger"),
        info: token("info"),
        tone: { fg: token("tone-fg"), bg: token("tone-bg"), border: token("tone-border"), solid: token("tone-solid") },
        chart: {
          1: token("chart-1"), 2: token("chart-2"), 3: token("chart-3"), 4: token("chart-4"),
          5: token("chart-5"), 6: token("chart-6"), 7: token("chart-7"), 8: token("chart-8"),
        },
      },
      fontFamily: {
        sans: ["var(--font-sans)", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["var(--font-mono)", "ui-monospace", "SFMono-Regular", "monospace"],
      },
      keyframes: {
        "fade-in": { from: { opacity: "0", transform: "translateY(4px)" }, to: { opacity: "1", transform: "none" } },
      },
      animation: {
        "fade-in": "fade-in .25s ease-out both",
      },
    },
  },
  plugins: [],
};

export default config;
