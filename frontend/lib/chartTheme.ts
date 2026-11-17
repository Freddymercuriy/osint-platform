"use client";

/**
 * Grafik ranglari CSS tokenlaridan (globals.css: --chart-*, --seq-*, --sev-*, --fg ...). Tema almashganda qayta o'qiladi.
 * Kategorial palitra dataviz validatoridan o'tgan; tartib — CVD xavfsizligi mexanizmi, rang entity'ga bog'lanadi.
 */
export type ChartTokens = {
  categorical: string[]; // 8 ta (tartib qat'iy)
  other: string;
  seq: string[]; // 7 ta, kichikdan kattaga
  severity: Record<"critical" | "high" | "medium" | "low" | "info", string>;
  fg: string;
  fgMuted: string;
  fgSubtle: string;
  border: string;
  surface: string;
  surface2: string;
  primary: string;
};

function v(style: CSSStyleDeclaration, name: string): string {
  const raw = style.getPropertyValue(`--${name}`).trim();
  const parts = raw.split(/\s+/).map(Number);
  return parts.length === 3 && parts.every((n) => !Number.isNaN(n)) ? `rgb(${parts.join(",")})` : "rgb(128,128,128)";
}

export function readChartTokens(): ChartTokens {
  const s = getComputedStyle(document.documentElement);
  return {
    categorical: Array.from({ length: 8 }, (_, i) => v(s, `chart-${i + 1}`)),
    other: v(s, "chart-other"),
    seq: Array.from({ length: 7 }, (_, i) => v(s, `seq-${i + 1}`)),
    severity: {
      critical: v(s, "sev-critical"),
      high: v(s, "sev-high"),
      medium: v(s, "sev-medium"),
      low: v(s, "sev-low"),
      info: v(s, "sev-info"),
    },
    fg: v(s, "fg"),
    fgMuted: v(s, "fg-muted"),
    fgSubtle: v(s, "fg-subtle"),
    border: v(s, "border"),
    surface: v(s, "surface"),
    surface2: v(s, "surface-2"),
    primary: v(s, "primary"),
  };
}

/**
 * Entity → rang: kalitlar ro'yxatidagi tartib bo'yicha (masalan kategoriyalar sort_order), filtr natijani o'zgartirsa ham
 * qolganlar rangini saqlaydi. "Other" — neytral kulrang. 8 tadan ortiq kalit bo'lmasligi kerak (API top=7 + Other).
 */
export function colorFor(key: string, stableOrder: string[], t: ChartTokens): string {
  if (key === "__other__") return t.other;
  const i = stableOrder.indexOf(key);
  return t.categorical[(i >= 0 ? i : stableOrder.length) % t.categorical.length];
}
