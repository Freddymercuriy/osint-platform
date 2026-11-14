"use client";

import { ArrowDownRight, ArrowUpRight, ExternalLink, Minus } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import SourceStatusBadge from "@/components/admin/SourceStatusBadge";
import EChart, { type ChartClick } from "@/components/charts/EChart";
import { CategoryBadge, SeverityBadge } from "@/components/ui";
import type { EventItem } from "@/lib/api";
import type { ChartTokens } from "@/lib/chartTheme";
import { cn } from "@/lib/cn";
import { useFormat } from "@/lib/format";
import {
  NONE,
  OTHER,
  getBreakdown,
  getHeatmap,
  getKpis,
  getLatest,
  getSourceHealth,
  getTimeSeries,
  type Breakdown,
  type Heatmap,
  type Kpis,
  type SourceHealth,
  type StatsFilters,
  type TimeSeries,
} from "@/lib/statsApi";
import { useCategories } from "@/lib/useCategories";
import type { Dim } from "./useDashboardFilters";
import { Widget, type TableData } from "./Widget";

export type WidgetProps = {
  filters: StatsFilters;
  tick: number;
  onFilter: (dim: Dim, value: string) => void;
  onHide: () => void;
  eventsHref: string;
};

const SEVERITY_ORDER = ["critical", "high", "medium", "low", "info"] as const;

/* ------------------------------------------------------------------ yordamchilar */
function useStat<T>(fetcher: () => Promise<T>, key: string, tick: number) {
  const [state, setState] = useState<{ data: T | null; loading: boolean; error: string | null }>({
    data: null,
    loading: true,
    error: null,
  });
  useEffect(() => {
    let alive = true;
    setState((s) => ({ ...s, loading: s.data === null, error: null }));
    fetcher()
      .then((data) => alive && setState({ data, loading: false, error: null }))
      .catch((e: Error) => alive && setState({ data: null, loading: false, error: e.message }));
    return () => {
      alive = false;
    };
    // fetcher filtrlar kaliti (key) va tick o'zgarganda qayta chaqiriladi
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, tick]);
  return state;
}

/** Nom yorliqlari: kategoriya (bazadan), davlat, kanal, jiddiylik, "Boshqa", "Ko'rsatilmagan". */
export function useLabels() {
  const t = useTranslations("dashboard");
  const tco = useTranslations("country");
  const tch = useTranslations("channel");
  const tsev = useTranslations("severity");
  const { bySlug } = useCategories();
  return useCallback(
    (dim: string, key: string) => {
      if (key === OTHER) return t("other");
      if (key === NONE) return t("unspecified");
      if (dim === "category") return bySlug(key).name;
      if (dim === "country" && ["UZ", "KZ", "KG", "TJ", "TM"].includes(key)) return tco(key);
      if (dim === "channel" && ["news", "telegram_channel", "telegram_group", "api"].includes(key)) return tch(key);
      if (dim === "severity" && (SEVERITY_ORDER as readonly string[]).includes(key)) return tsev(key);
      if (dim === "sector" && t.has(`sector.${key}`)) return t(`sector.${key}`);
      return key;
    },
    [t, tco, tch, tsev, bySlug],
  );
}

/** Kategoriya ranglari uchun barqaror to'plam (≤ 7): tanlangan kategoriyalar, aks holda eng ko'p hodisali 7 tasi. */
function useCategoryColorKeys(filters: StatsFilters): string[] {
  const { list } = useCategories();
  return useMemo(() => {
    const sel = filters.category ?? [];
    if (sel.length && sel.length <= 7) return [...sel].sort();
    return [...list].filter((c) => c.slug !== "other").sort((a, b) => b.event_count - a.event_count || a.sort_order - b.sort_order)
      .slice(0, 7).map((c) => c.slug);
  }, [filters.category, list]);
}

function baseAxis(t: ChartTokens) {
  return {
    axisLine: { lineStyle: { color: t.border } },
    axisTick: { show: false },
    axisLabel: { color: t.fgSubtle, fontSize: 11 },
    splitLine: { lineStyle: { color: t.border, type: "dashed" as const } },
  };
}

function tooltip(t: ChartTokens, trigger: "axis" | "item" = "axis") {
  return {
    trigger,
    confine: true,
    backgroundColor: t.surface,
    borderColor: t.border,
    textStyle: { color: t.fg, fontSize: 12 },
    axisPointer: { type: "shadow" as const, shadowStyle: { color: t.surface2, opacity: 0.6 } },
  };
}

function legend(t: ChartTokens) {
  return {
    type: "scroll" as const,
    top: 0,
    icon: "roundRect",
    itemWidth: 10,
    itemHeight: 10,
    textStyle: { color: t.fgMuted, fontSize: 12 },
    pageTextStyle: { color: t.fgMuted },
  };
}

function useBucketLabel(bucket: TimeSeries["bucket"] | undefined) {
  const f = useFormat();
  return useCallback(
    (iso: string) => {
      const d = new Date(`${iso}+05:00`);
      if (bucket === "hour") return `${iso.slice(11, 13)}:00`;
      if (bucket === "month") return f.date(d, { short: true }).replace(/^\d+\s/, "");
      return f.date(d, { short: true, year: false });
    },
    [bucket, f],
  );
}

/** Seriyalarni barqaror to'plamga yig'ish: to'plamdagilar alohida, qolgani "Other". */
function fold(series: TimeSeries["series"], keys: string[] | null, n: number) {
  if (!keys) return series;
  const out = keys.map((k) => series.find((s) => s.key === k)).filter((s): s is TimeSeries["series"][number] => !!s && s.total > 0);
  const rest = series.filter((s) => !keys.includes(s.key));
  if (rest.length) {
    const values = Array.from({ length: n }, (_, i) => rest.reduce((a, s) => a + s.values[i], 0));
    const total = values.reduce((a, b) => a + b, 0);
    if (total) out.push({ key: OTHER, total, values });
  }
  return out;
}

/* ------------------------------------------------------------------ KPI */
function Delta({ cur, prev, pct }: { cur: number; prev: number; pct?: number | null }) {
  const t = useTranslations("dashboard.kpi");
  const f = useFormat();
  const p = pct === undefined ? (prev === 0 ? null : ((cur - prev) / prev) * 100) : pct;
  if (p === null) return <span className="text-xs text-fg-subtle">{t("noPrevious")}</span>;
  const Icon = p > 0 ? ArrowUpRight : p < 0 ? ArrowDownRight : Minus;
  return (
    <span className="inline-flex items-center gap-0.5 text-xs text-fg-muted" title={t("previousValue", { value: f.number(prev) })}>
      <Icon className="h-3.5 w-3.5" aria-hidden />
      {t("change", { pct: `${p > 0 ? "+" : ""}${f.number(Math.round(p * 10) / 10)}` })}
    </span>
  );
}

export function KpiRow({ filters, tick, onHide }: WidgetProps) {
  const t = useTranslations("dashboard.kpi");
  const f = useFormat();
  const key = JSON.stringify(filters);
  const { data, loading, error } = useStat<Kpis>(() => getKpis(filters), key, tick);
  const tiles = data
    ? [
        { label: t("total"), value: data.total, delta: <Delta cur={data.total} prev={data.previous_total} pct={data.change_pct} />, help: t("totalHelp") },
        { label: t("criticalHigh"), value: data.critical_high, delta: <Delta cur={data.critical_high} prev={data.critical_high_previous} />, help: t("criticalHighHelp") },
        { label: t("ransomware"), value: data.ransomware, delta: <Delta cur={data.ransomware} prev={data.ransomware_previous} />, help: t("ransomwareHelp") },
        { label: t("countries"), value: data.countries_affected, delta: null, help: t("countriesHelp") },
        { label: t("sources"), value: data.sources_reporting, delta: null, help: t("sourcesHelp") },
        { label: t("multiSource"), value: data.multi_source, delta: null, help: t("multiSourceHelp") },
      ]
    : [];
  const table: TableData = { header: [t("metric"), t("value"), t("previous")], rows: data ? [
    [t("total"), data.total, data.previous_total],
    [t("criticalHigh"), data.critical_high, data.critical_high_previous],
    [t("ransomware"), data.ransomware, data.ransomware_previous],
    [t("countries"), data.countries_affected, null],
    [t("sources"), data.sources_reporting, null],
    [t("multiSource"), data.multi_source, null],
  ] : [] };
  return (
    <Widget id="kpis" title={t("title")} help={t("help")} loading={loading} error={error} empty={false} table={table} onHide={onHide} noChart className="lg:col-span-2">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
        {tiles.map((x) => (
          <div key={x.label} className="min-w-0 rounded-lg border border-border bg-surface-2/50 p-3" title={x.help}>
            <div className="truncate text-xs text-fg-muted">{x.label}</div>
            <div className="mt-1 text-2xl font-semibold tabular-nums text-fg">{f.number(x.value)}</div>
            <div className="mt-0.5 min-h-4">{x.delta}</div>
          </div>
        ))}
      </div>
    </Widget>
  );
}

/* ------------------------------------------------------------------ vaqt bo'yicha (kategoriya) */
export function TimelineWidget({ filters, tick, onFilter, onHide }: WidgetProps) {
  const t = useTranslations("dashboard");
  const label = useLabels();
  const colorKeys = useCategoryColorKeys(filters);
  const key = JSON.stringify(filters);
  const { data, loading, error } = useStat<TimeSeries>(() => getTimeSeries(filters, "category", undefined, 50), key, tick);
  const bucketLabel = useBucketLabel(data?.bucket);
  const series = useMemo(() => (data ? fold(data.series, colorKeys, data.buckets.length) : []), [data, colorKeys]);
  const names = useMemo(() => Object.fromEntries(series.map((s) => [label("category", s.key), s.key])), [series, label]);

  const build = useCallback(
    (tk: ChartTokens) => ({
      aria: { enabled: true },
      grid: { left: 8, right: 12, top: 36, bottom: 44, containLabel: true },
      legend: legend(tk),
      tooltip: tooltip(tk),
      xAxis: { type: "category", data: (data?.buckets ?? []).map(bucketLabel), ...baseAxis(tk), splitLine: { show: false } },
      yAxis: { type: "value", minInterval: 1, ...baseAxis(tk), axisLine: { show: false } },
      dataZoom: [
        { type: "inside" },
        { type: "slider", height: 16, bottom: 6, borderColor: tk.border, fillerColor: "rgba(128,128,128,0.15)", textStyle: { color: tk.fgSubtle }, handleStyle: { color: tk.surface2, borderColor: tk.border } },
      ],
      series: series.map((s) => ({
        name: label("category", s.key),
        type: "bar",
        stack: "total",
        barMaxWidth: 28,
        data: s.values,
        emphasis: { focus: "series" },
        itemStyle: {
          color: s.key === OTHER ? tk.other : tk.categorical[colorKeys.indexOf(s.key) % 8],
          borderColor: tk.surface,
          borderWidth: 1,
        },
      })),
    }),
    [data, series, label, colorKeys, bucketLabel],
  );

  const click = (p: ChartClick) => {
    const k = p.seriesName ? names[p.seriesName] : undefined;
    if (k && k !== OTHER) onFilter("category", k);
  };
  const table: TableData = {
    header: [t("period"), ...series.map((s) => label("category", s.key)), t("total")],
    rows: (data?.buckets ?? []).map((b, i) => [bucketLabel(b), ...series.map((s) => s.values[i]), data!.totals[i]]),
  };
  return (
    <Widget id="timeline" title={t("timeline.title")} help={t("timeline.help")} loading={loading} error={error}
      empty={!data || data.totals.every((x) => x === 0)} table={table} onHide={onHide} className="lg:col-span-2">
      <EChart build={build} height={300} ariaLabel={t("timeline.title")} onClick={click}
        onLegendToggle={(n) => names[n] && names[n] !== OTHER && onFilter("category", names[n])} />
    </Widget>
  );
}

/* ------------------------------------------------------------------ jiddiylik trendi */
export function SeverityWidget({ filters, tick, onFilter, onHide }: WidgetProps) {
  const t = useTranslations("dashboard");
  const label = useLabels();
  const key = JSON.stringify(filters);
  const { data, loading, error } = useStat<TimeSeries>(() => getTimeSeries(filters, "severity"), key, tick);
  const bucketLabel = useBucketLabel(data?.bucket);
  const series = useMemo(
    () => SEVERITY_ORDER.map((sv) => data?.series.find((s) => s.key === sv)).filter((s): s is TimeSeries["series"][number] => !!s),
    [data],
  );
  const names = useMemo(() => Object.fromEntries(series.map((s) => [label("severity", s.key), s.key])), [series, label]);
  const build = useCallback(
    (tk: ChartTokens) => ({
      aria: { enabled: true },
      grid: { left: 8, right: 12, top: 36, bottom: 8, containLabel: true },
      legend: legend(tk),
      tooltip: tooltip(tk),
      xAxis: { type: "category", data: (data?.buckets ?? []).map(bucketLabel), ...baseAxis(tk), splitLine: { show: false } },
      yAxis: { type: "value", minInterval: 1, ...baseAxis(tk), axisLine: { show: false } },
      series: series.map((s) => ({
        name: label("severity", s.key),
        type: "bar",
        stack: "sev",
        barMaxWidth: 28,
        data: s.values,
        emphasis: { focus: "series" },
        itemStyle: { color: tk.severity[s.key as keyof ChartTokens["severity"]], borderColor: tk.surface, borderWidth: 1 },
      })),
    }),
    [data, series, label, bucketLabel],
  );
  const table: TableData = {
    header: [t("period"), ...series.map((s) => label("severity", s.key))],
    rows: (data?.buckets ?? []).map((b, i) => [bucketLabel(b), ...series.map((s) => s.values[i])]),
  };
  return (
    <Widget id="severity" title={t("severityTrend.title")} help={t("severityTrend.help")} loading={loading} error={error}
      empty={!data || data.totals.every((x) => x === 0)} table={table} onHide={onHide}>
      <EChart build={build} height={260} ariaLabel={t("severityTrend.title")}
        onClick={(p) => p.seriesName && names[p.seriesName] && onFilter("severity", names[p.seriesName])}
        onLegendToggle={(n) => names[n] && onFilter("severity", names[n])} />
    </Widget>
  );
}

/* ------------------------------------------------------------------ top-N gorizontal ustunlar */
function BarList({
  id, dim, by, filters, tick, onFilter, onHide, extra, limit = 10, includeNone, clickable = true, linkFor,
}: WidgetProps & {
  id: string;
  dim: string;
  by: "category" | "country" | "source" | "actor" | "sector";
  extra?: Partial<StatsFilters>;
  limit?: number;
  includeNone?: boolean;
  clickable?: boolean;
  linkFor?: (key: string) => string;
}) {
  const t = useTranslations("dashboard");
  const f = useFormat();
  const label = useLabels();
  const merged = useMemo(() => ({ ...filters, ...extra }), [filters, extra]);
  const key = JSON.stringify(merged) + by;
  const { data, loading, error } = useStat<Breakdown>(() => getBreakdown(merged, by, limit, includeNone), key, tick);
  // "Ko'rsatilmagan" har doim oxirida (u eng katta bo'lsa ham asosiy ma'lumot emas)
  const items = [...(data?.items ?? [])].sort((a, b) => Number(a.key === NONE) - Number(b.key === NONE));
  const max = Math.max(1, ...items.map((i) => i.count));
  const table: TableData = {
    header: [t(`${id}.column`), t("count")],
    rows: [...items.map((i) => [label(dim, i.key), i.count]), ...(data?.other ? [[t("other"), data.other]] : [])],
  };
  return (
    <Widget id={id} title={t(`${id}.title`)} help={t(`${id}.help`)} loading={loading} error={error} empty={!items.length}
      emptyHint={t(`${id}.empty`)} table={table} onHide={onHide} noChart>
      <ul className="space-y-1.5">
        {items.map((i) => {
          const name = label(dim, i.key);
          const canClick = clickable && i.key !== NONE;
          const inner = (
            <>
              <span className="flex items-baseline justify-between gap-2 text-sm">
                <span className="truncate text-fg">{name}</span>
                <span className="shrink-0 tabular-nums text-fg-muted">{f.number(i.count)}</span>
              </span>
              <span className="mt-1 block h-1.5 rounded-full bg-surface-2" aria-hidden>
                <span className="block h-full rounded-full bg-chart-1" style={{ width: `${(i.count / max) * 100}%` }} />
              </span>
            </>
          );
          return (
            <li key={i.key}>
              {linkFor && i.key !== NONE ? (
                <Link href={linkFor(i.key)} className="focus-ring block rounded-md px-1 py-0.5 hover:bg-surface-2" title={t("openInEvents")}>
                  {inner}
                </Link>
              ) : canClick ? (
                <button type="button" onClick={() => onFilter(dim as Dim, i.key)} title={t("addFilter", { name })}
                  className="focus-ring block w-full rounded-md px-1 py-0.5 text-left hover:bg-surface-2">
                  {inner}
                </button>
              ) : (
                <div className="px-1 py-0.5">{inner}</div>
              )}
            </li>
          );
        })}
      </ul>
      {!!data?.other && <p className="mt-2 text-xs text-fg-subtle">{t("otherCount", { count: data.other })}</p>}
    </Widget>
  );
}

export const CategoriesWidget = (p: WidgetProps) => <BarList {...p} id="categories" dim="category" by="category" limit={15} />;
export const CountriesWidget = (p: WidgetProps) => <BarList {...p} id="countries" dim="country" by="country" includeNone />;
export const SourcesWidget = (p: WidgetProps) => <BarList {...p} id="sources" dim="source" by="source" />;

const RANSOM = { category: ["ransomware"] } as Partial<StatsFilters>;
export function RansomwareWidget(p: WidgetProps) {
  return (
    <BarList {...p} id="ransomware" dim="actor" by="actor" extra={RANSOM}
      linkFor={(k) => `/dashboard/events?category=ransomware&q=${encodeURIComponent(k)}`} />
  );
}
export function SectorsWidget(p: WidgetProps) {
  return <BarList {...p} id="sectors" dim="sector" by="sector" clickable={false} />;
}

/* ------------------------------------------------------------------ issiqlik xaritasi */
const UZ_DAYS = ["Du", "Se", "Ch", "Pa", "Ju", "Sh", "Ya"];

export function HeatmapWidget({ filters, tick, onHide }: WidgetProps) {
  const t = useTranslations("dashboard");
  const locale = useLocale();
  const key = JSON.stringify(filters);
  const { data, loading, error } = useStat<Heatmap>(() => getHeatmap(filters), key, tick);
  const days = useMemo(() => {
    if (locale === "uz") return UZ_DAYS;
    const fmt = new Intl.DateTimeFormat(locale === "ru" ? "ru-RU" : "en-GB", { weekday: "short", timeZone: "UTC" });
    return Array.from({ length: 7 }, (_, i) => fmt.format(new Date(Date.UTC(2024, 0, 1 + i)))); // 2024-01-01 — dushanba
  }, [locale]);
  const hours = Array.from({ length: 24 }, (_, h) => String(h).padStart(2, "0"));
  const build = useCallback(
    (tk: ChartTokens) => ({
      aria: { enabled: true },
      grid: { left: 8, right: 8, top: 8, bottom: 40, containLabel: true },
      tooltip: {
        ...tooltip(tk, "item"),
        formatter: (p: { value: [number, number, number] }) =>
          `${days[p.value[1]]}, ${hours[p.value[0]]}:00–${hours[(p.value[0] + 1) % 24]}:00<br/><b>${p.value[2]}</b>`,
      },
      xAxis: { type: "category", data: hours, ...baseAxis(tk), splitArea: { show: false }, splitLine: { show: false } },
      yAxis: { type: "category", data: days, ...baseAxis(tk), inverse: true, splitLine: { show: false } },
      visualMap: {
        min: 0, max: Math.max(1, data?.max ?? 1), calculable: false, orient: "horizontal", left: "center", bottom: 0,
        itemHeight: 120, itemWidth: 10, textStyle: { color: tk.fgSubtle }, inRange: { color: tk.seq },
      },
      series: [{
        type: "heatmap",
        data: (data?.cells ?? []).map(([d, h, n]) => [h, d, n]),
        itemStyle: { borderColor: tk.surface, borderWidth: 2, borderRadius: 2 },
        emphasis: { itemStyle: { borderColor: tk.fg, borderWidth: 1 } },
      }],
    }),
    [data, days, hours],
  );
  const table: TableData = {
    header: [t("heatmap.day"), ...hours],
    rows: days.map((d, di) => [d, ...hours.map((_, h) => data?.cells.find((c) => c[0] === di && c[1] === h)?.[2] ?? 0)]),
  };
  return (
    <Widget id="heatmap" title={t("heatmap.title")} help={t("heatmap.help", { tz: data?.timezone ?? "Asia/Tashkent" })}
      loading={loading} error={error} empty={!data?.cells.length} table={table} onHide={onHide}>
      <EChart build={build} height={260} ariaLabel={t("heatmap.title")} />
    </Widget>
  );
}

/* ------------------------------------------------------------------ so'nggi muhim hodisalar */
export function LatestWidget({ filters, tick, onHide, eventsHref }: WidgetProps) {
  const t = useTranslations("dashboard");
  const locale = useLocale();
  const f = useFormat();
  const key = JSON.stringify(filters) + locale;
  const { data, loading, error } = useStat<EventItem[]>(() => getLatest(filters, locale, 8), key, tick);
  const items = data ?? [];
  const table: TableData = {
    header: [t("latest.when"), t("latest.severity"), t("latest.event"), t("latest.source")],
    rows: items.map((e) => [f.dateTime(e.published ?? e.first_seen), e.severity ?? "", e.title, e.source]),
  };
  return (
    <Widget id="latest" title={t("latest.title")} help={t("latest.help")} loading={loading} error={error}
      empty={!items.length} emptyHint={t("latest.empty")} table={table} onHide={onHide} noChart
      actions={<Link href={`${eventsHref}&severity=critical,high`} className="focus-ring mr-1 rounded-md px-1.5 py-1 text-xs text-primary hover:bg-surface-2">{t("openInEvents")}</Link>}>
      <ul className="divide-y divide-border">
        {items.map((e) => (
          <li key={e.id} className="py-2.5">
            <div className="flex flex-wrap items-center gap-1.5">
              <SeverityBadge severity={e.severity ?? "info"} />
              <CategoryBadge category={e.category} />
              <span className="ml-auto text-xs text-fg-subtle">{f.ago(e.published ?? e.first_seen)}</span>
            </div>
            <a href={e.url} target="_blank" rel="noreferrer" className="focus-ring mt-1 flex items-start gap-1.5 rounded text-sm text-fg hover:text-primary">
              <span className="line-clamp-2 flex-1">{e.title}</span>
              <ExternalLink className="mt-0.5 h-3.5 w-3.5 shrink-0 text-fg-subtle" aria-hidden />
            </a>
            <div className="mt-0.5 truncate text-xs text-fg-subtle">{e.source}</div>
          </li>
        ))}
      </ul>
    </Widget>
  );
}

/* ------------------------------------------------------------------ manbalar sog'lig'i */
export function HealthWidget({ tick, onHide }: WidgetProps) {
  const t = useTranslations("dashboard");
  const f = useFormat();
  const { data, loading, error } = useStat<SourceHealth>(() => getSourceHealth(), "health", tick);
  const order = ["ok", "degraded", "down", "blocked", "auth_missing", "disabled", "never_run"];
  const table: TableData = {
    header: [t("health.status"), t("count")],
    rows: order.filter((s) => data?.by_status[s]).map((s) => [s, data!.by_status[s]]),
  };
  return (
    <Widget id="health" title={t("health.title")} help={t("health.help")} loading={loading} error={error} empty={!data?.total}
      table={table} onHide={onHide} noChart>
      {data && (
        <div className="space-y-3">
          <div className="flex flex-wrap gap-1.5">
            {order.filter((s) => data.by_status[s]).map((s) => (
              <span key={s} className="inline-flex items-center gap-1">
                <SourceStatusBadge status={s} />
                <span className="text-sm tabular-nums text-fg">{f.number(data.by_status[s])}</span>
              </span>
            ))}
          </div>
          <p className="text-xs text-fg-muted">
            {t("health.summary", { enabled: data.enabled, total: data.total, runs: data.runs_24h, failed: data.failed_runs_24h })}
          </p>
          {data.failing.length > 0 && (
            <ul className="divide-y divide-border rounded-lg border border-border">
              {data.failing.map((s) => (
                <li key={s.id} className="flex items-start gap-2 px-3 py-2 text-sm">
                  <SourceStatusBadge status={s.status} />
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-fg">{s.name}</div>
                    {s.last_error && <div className={cn("truncate text-xs text-fg-subtle")} title={s.last_error}>{s.last_error}</div>}
                  </div>
                  {s.since && <span className="shrink-0 text-xs text-fg-subtle">{f.ago(s.since)}</span>}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </Widget>
  );
}
