"use client";

import { ExternalLink, RotateCcw, X } from "lucide-react";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { useEffect, useState } from "react";
import { MultiSelect, type Option } from "@/components/events/MultiSelect";
import { Button, ButtonLink, Input, Select } from "@/components/ui";
import { getEventFacets, type EventFacets } from "@/lib/adminApi";
import type { RangeKey, StatsFilters } from "@/lib/statsApi";
import { useCategories } from "@/lib/useCategories";
import { DIMS, type Dim } from "./useDashboardFilters";
import { useLabels } from "./widgets";

const RANGES: RangeKey[] = ["24h", "7d", "30d", "90d", "custom"];

/** Bitta filtr paneli — hamma vidjetni boshqaradi; holat URL'da. */
export function DashboardFilters({
  filters,
  set,
  toggle,
  reset,
  activeCount,
  eventsHref,
}: {
  filters: StatsFilters;
  set: (p: Partial<StatsFilters>) => void;
  toggle: (d: Dim, v: string) => void;
  reset: () => void;
  activeCount: number;
  eventsHref: string;
}) {
  const t = useTranslations("dashboard.filters");
  const ts = useTranslations("scope");
  const tsev = useTranslations("severity");
  const tch = useTranslations("channel");
  const tco = useTranslations("country");
  const label = useLabels();
  const { list: categories } = useCategories();
  const [facets, setFacets] = useState<EventFacets | null>(null);
  useEffect(() => {
    getEventFacets().then(setFacets).catch(() => setFacets(null));
  }, []);
  const count = (arr: { value: string; count: number }[] | undefined, v: string) => arr?.find((x) => x.value === v)?.count;

  const opts: Record<Dim, Option[]> = {
    category: categories.map((c) => ({ value: c.slug, label: c.name, count: c.event_count })),
    country: ["UZ", "KZ", "KG", "TJ", "TM"].map((c) => ({ value: c, label: tco(c), count: count(facets?.countries, c) })),
    channel: ["news", "telegram_channel", "telegram_group", "api", "forum"].map((c) => ({ value: c, label: tch(c), count: count(facets?.channels, c) })),
    source: (facets?.sources ?? []).map((s) => ({ value: s.label ?? s.value, label: s.label ?? s.value, count: s.count })),
    severity: ["critical", "high", "medium", "low", "info"].map((c) => ({ value: c, label: tsev(c), count: count(facets?.severities, c) })),
  };

  return (
    <div className="card mb-4 space-y-3 p-3 sm:p-4">
      <div className="flex flex-wrap items-end gap-2">
        <label className="flex flex-col gap-1 text-xs text-fg-muted">
          {t("period")}
          <Select
            value={filters.range}
            onChange={(e) => set({ range: e.target.value as RangeKey, ...(e.target.value !== "custom" ? { date_from: undefined, date_to: undefined } : {}) })}
            className="h-9 w-40"
          >
            {RANGES.map((r) => (
              <option key={r} value={r}>
                {t(`range.${r}`)}
              </option>
            ))}
          </Select>
        </label>
        {filters.range === "custom" && (
          <>
            <label className="flex flex-col gap-1 text-xs text-fg-muted">
              {t("from")}
              <Input type="date" value={filters.date_from ?? ""} onChange={(e) => set({ date_from: e.target.value || undefined })} className="h-9 w-40" />
            </label>
            <label className="flex flex-col gap-1 text-xs text-fg-muted">
              {t("to")}
              <Input type="date" value={filters.date_to ?? ""} onChange={(e) => set({ date_to: e.target.value || undefined })} className="h-9 w-40" />
            </label>
          </>
        )}
        {DIMS.map((d) => (
          <MultiSelect key={d} label={t(`dim.${d}`)} options={opts[d]} value={filters[d] ?? []} searchable={d === "source" || d === "category"}
            onChange={(v) => set({ [d]: v } as Partial<StatsFilters>)} />
        ))}
        <div role="radiogroup" aria-label={ts("label")} className="inline-flex rounded-lg border border-border bg-surface p-0.5">
          {(["regional", "global", "all"] as const).map((s) => (
            <button key={s} type="button" role="radio" aria-checked={filters.scope === s} onClick={() => set({ scope: s })}
              className={`focus-ring rounded-md px-2.5 py-1 text-xs ${filters.scope === s ? "bg-primary-soft font-medium text-primary" : "text-fg-muted hover:text-fg"}`}>
              {ts(s)}
            </button>
          ))}
        </div>
        <div className="ml-auto flex flex-wrap items-center gap-2">
          <ButtonLink href={eventsHref} variant="secondary" size="sm" icon={ExternalLink}>
            {t("openInEvents")}
          </ButtonLink>
        </div>
      </div>

      {activeCount > 0 && (
        <div className="flex flex-wrap items-center gap-1.5" aria-label={t("active")}>
          {DIMS.flatMap((d) =>
            (filters[d] ?? []).map((v) => (
              <button key={`${d}:${v}`} type="button" onClick={() => toggle(d, v)} title={t("remove")}
                className="focus-ring inline-flex items-center gap-1 rounded-full border border-border bg-surface-2 px-2 py-0.5 text-xs text-fg hover:border-border-strong">
                <span className="text-fg-subtle">{t(`dim.${d}`)}:</span> {label(d, v)}
                <X className="h-3 w-3" aria-hidden />
              </button>
            )),
          )}
          {filters.scope !== "regional" && (
            <span className="inline-flex items-center gap-1 rounded-full border border-border bg-surface-2 px-2 py-0.5 text-xs text-fg">
              {ts("label")}: {ts(filters.scope ?? "regional")}
            </span>
          )}
          <Button variant="ghost" size="sm" icon={RotateCcw} onClick={reset}>
            {t("reset")}
          </Button>
        </div>
      )}
      <p className="text-xs text-fg-subtle">
        {t("hint")} <Link href="/dashboard/events" className="link">{t("eventsLink")}</Link>
      </p>
    </div>
  );
}
