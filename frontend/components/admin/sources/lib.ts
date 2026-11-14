import type { SourceStatus } from "@/lib/adminApi";
import type { Tone } from "@/lib/categories";

export const LANGS = ["en", "ru", "uz", "kk", "ky", "tg"] as const;
export const KNOWN_OUTCOMES = ["ok", "not_modified", "blocked", "rate_limited", "auth_missing", "error", "config_error"];

type T = (key: string, values?: Record<string, string | number>) => string;

/** Soniyani o'qiladigan ko'rinishga: 600 → "10 min", 21600 → "6 h", 5400 → "1 h 30 min". */
export function humanInterval(sec: number, t: T): string {
  if (!Number.isFinite(sec) || sec <= 0) return "—";
  if (sec < 60) return t("duration.s", { count: Math.round(sec) });
  if (sec < 3600) {
    const m = Math.floor(sec / 60);
    const s = Math.round(sec % 60);
    return s ? `${t("duration.m", { count: m })} ${t("duration.s", { count: s })}` : t("duration.m", { count: m });
  }
  if (sec < 86400) {
    const h = Math.floor(sec / 3600);
    const m = Math.round((sec % 3600) / 60);
    return m ? `${t("duration.h", { count: h })} ${t("duration.m", { count: m })}` : t("duration.h", { count: h });
  }
  const d = Math.floor(sec / 86400);
  const h = Math.round((sec % 86400) / 3600);
  return h ? `${t("duration.d", { count: d })} ${t("duration.h", { count: h })}` : t("duration.d", { count: d });
}

export function msText(ms: number, f: { number: (n: number) => string }, t: T): string {
  return t("ms", { ms: f.number(Math.round(ms)) });
}

export const outcomeTone = (o: string, ok: boolean): Tone =>
  ok || o === "ok" || o === "not_modified" ? "green" : o === "blocked" || o === "rate_limited" ? "purple" : o === "auth_missing" ? "yellow" : "red";

export type { SourceStatus };
