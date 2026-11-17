/** Statistika API (`/api/stats/*`) — dashboard vidjetlari. Filtrlar `/api/events` bilan bir xil nomlarda + davr. */
import { apiFetch, eventFiltersToParams, getToken, handle, type EventFilters, type EventItem } from "@/lib/api";

import { API_URL } from "@/lib/config";

export type RangeKey = "24h" | "7d" | "30d" | "90d" | "custom";
export type StatsFilters = Omit<EventFilters, "q" | "source_lang" | "range"> & { range?: RangeKey };
export const OTHER = "__other__";
export const NONE = "__none__";

function params(f: StatsFilters, extra: Record<string, string | number | boolean | undefined> = {}) {
  const { range, ...rest } = f;
  const p = eventFiltersToParams(rest);
  if (range && !(rest.date_from || rest.date_to)) p.set("range", range);
  if (rest.date_from || rest.date_to) p.set("range", "custom");
  for (const [k, v] of Object.entries(extra)) if (v !== undefined) p.set(k, String(v));
  return p.toString();
}

async function get<T>(path: string, f: StatsFilters, extra?: Record<string, string | number | boolean | undefined>) {
  const res = await apiFetch(`${API_URL}/api/stats/${path}?${params(f, extra)}`, {
    headers: { Authorization: `Bearer ${getToken()}` },
  });
  return handle<T>(res);
}

export type Period = { start: string; end: string; range: string };
export type Kpis = {
  period: Period;
  total: number;
  previous_total: number;
  change_pct: number | null;
  critical_high: number;
  critical_high_previous: number;
  by_severity: Record<string, number>;
  countries_affected: number;
  sources_reporting: number;
  multi_source: number;
  ransomware: number;
  ransomware_previous: number;
};
export type Series = { key: string; total: number; values: number[] };
export type TimeSeries = {
  period: Period;
  bucket: "hour" | "day" | "week" | "month";
  group_by: string | null;
  buckets: string[];
  totals: number[];
  series: Series[];
};
export type Breakdown = { period: Period; by: string; total: number; items: { key: string; count: number }[]; other: number };
export type Heatmap = { period: Period; timezone: string; cells: [number, number, number][]; max: number };
export type SourceHealth = {
  total: number;
  enabled: number;
  by_status: Record<string, number>;
  runs_24h: number;
  failed_runs_24h: number;
  failing: { id: number; name: string; status: string; since: string | null; last_error: string | null }[];
};

export const getKpis = (f: StatsFilters) => get<Kpis>("kpis", f);
export const getTimeSeries = (
  f: StatsFilters,
  groupBy?: "category" | "country" | "source" | "channel" | "severity",
  bucket?: string,
  top = 7,
) => get<TimeSeries>("timeseries", f, { group_by: groupBy, bucket, top });
export const getBreakdown = (
  f: StatsFilters,
  by: "category" | "country" | "source" | "channel" | "severity" | "actor" | "sector",
  limit = 10,
  includeNone = false,
) => get<Breakdown>("breakdown", f, { by, limit, include_none: includeNone || undefined });
export const getHeatmap = (f: StatsFilters) => get<Heatmap>("heatmap", f);
export const getLatest = (f: StatsFilters, lang: string, limit = 8) =>
  get<EventItem[]>("latest", f, { min_severity: "high", limit, lang });
export async function getSourceHealth(): Promise<SourceHealth> {
  const res = await apiFetch(`${API_URL}/api/stats/source-health`, { headers: { Authorization: `Bearer ${getToken()}` } });
  return handle<SourceHealth>(res);
}

/** Jadval → CSV (Excel uchun BOM bilan) va yuklab olish. */
export function downloadCsv(filename: string, header: string[], rows: (string | number | null | undefined)[][]) {
  const esc = (v: string | number | null | undefined) => {
    let s = v === null || v === undefined ? "" : String(v);
    // CSV formula injection: manba nomi kabi tashqi matn "=", "+", "-", "@" bilan boshlansa Excel uni bajaradi
    if (typeof v === "string" && /^[=+\-@\t\r]/.test(s)) s = "'" + s;
    return /[",\n;]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  const csv = "﻿" + [header, ...rows].map((r) => r.map(esc).join(",")).join("\n");
  const url = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
