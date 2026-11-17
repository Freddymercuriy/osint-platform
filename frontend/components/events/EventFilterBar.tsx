"use client";

import { Search, SlidersHorizontal, X } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { useMemo, useState } from "react";
import { Button, Input } from "@/components/ui";
import { MultiSelect, type Option } from "@/components/events/MultiSelect";
import { PRIORITY_BANDS, type EventFilters } from "@/lib/api";
import type { EventFacets } from "@/lib/adminApi";
import { useCategories } from "@/lib/useCategories";
import { useFormat } from "@/lib/format";
import { cn } from "@/lib/cn";

export type Scope = NonNullable<EventFilters["scope"]>;
export const SCOPES: Scope[] = ["regional", "global", "all"];
const COUNTRIES = ["UZ", "KZ", "KG", "TJ", "TM"];
const CHANNELS = ["news", "telegram_channel", "telegram_group", "api"];
const SEVERITIES = ["critical", "high", "medium", "low", "info"];
// Tez davrlar — nisbiy, hozirdan orqaga soat aniqligida (`range`), kalendar kuni emas
const PRESETS = [
  { key: "d1", range: "24h" },
  { key: "d7", range: "7d" },
  { key: "d30", range: "30d" },
  { key: "d90", range: "90d" },
] as const;

type ChipKey = "category" | "severity" | "band" | "country" | "channel" | "source" | "source_lang";

export function EventFilterBar({
  filters,
  scope,
  qInput,
  onQInput,
  onChange,
  onReset,
  facets,
}: {
  filters: EventFilters;
  scope: Scope;
  qInput: string;
  onQInput: (v: string) => void;
  onChange: (patch: Partial<EventFilters>) => void;
  onReset: () => void;
  facets: EventFacets | null;
}) {
  const t = useTranslations("events");
  const tf = useTranslations("events.filters");
  const ts = useTranslations("scope");
  const tsev = useTranslations("severity");
  const tband = useTranslations("events.priority.band");
  const tch = useTranslations("channel");
  const tco = useTranslations("country");
  const locale = useLocale();
  const f = useFormat();
  const { list: categories } = useCategories();
  const [open, setOpen] = useState(false);

  const langName = useMemo(() => {
    let dn: Intl.DisplayNames | null = null;
    try {
      dn = new Intl.DisplayNames([locale], { type: "language" });
    } catch {
      dn = null;
    }
    return (code: string) => {
      try {
        return dn?.of(code) ?? code;
      } catch {
        return code;
      }
    };
  }, [locale]);

  const count = (list: { value: string; count: number }[] | undefined, v: string) =>
    list?.find((x) => x.value === v)?.count ?? 0;

  const opts = useMemo(() => {
    const catOpts: Option[] = categories.map((c) => ({ value: c.slug, label: c.name, count: c.event_count }));
    const sevOpts: Option[] = SEVERITIES.map((v) => ({
      value: v,
      label: tsev(v),
      count: facets ? count(facets.severities, v) : undefined,
    }));
    const bandOpts: Option[] = PRIORITY_BANDS.map((v) => ({ value: v, label: tband(v) }));
    const coOpts: Option[] = COUNTRIES.map((v) => ({
      value: v,
      label: tco(v),
      count: facets ? count(facets.countries, v) : undefined,
    }));
    const chOpts: Option[] = CHANNELS.map((v) => ({
      value: v,
      label: tch(v),
      count: facets ? count(facets.channels, v) : undefined,
    }));
    const srcOpts: Option[] = (facets?.sources ?? []).map((s) => ({
      value: s.value,
      label: s.label || s.value,
      count: s.count,
    }));
    const langOpts: Option[] = (facets?.source_langs ?? []).map((s) => ({
      value: s.value,
      label: langName(s.value),
      count: s.count,
    }));
    return { catOpts, sevOpts, bandOpts, coOpts, chOpts, srcOpts, langOpts };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [categories, facets, tsev, tband, tco, tch, langName]);

  const groups: { key: ChipKey; label: string; options: Option[]; searchable?: boolean }[] = [
    { key: "category", label: tf("category"), options: opts.catOpts },
    { key: "severity", label: tf("severity"), options: opts.sevOpts },
    { key: "band", label: tf("band"), options: opts.bandOpts },
    { key: "country", label: tf("country"), options: opts.coOpts },
    { key: "channel", label: tf("channel"), options: opts.chOpts },
    { key: "source", label: tf("source"), options: opts.srcOpts, searchable: true },
    { key: "source_lang", label: tf("language"), options: opts.langOpts },
  ];

  const labelOf = (g: (typeof groups)[number], v: string) => g.options.find((o) => o.value === v)?.label ?? v;

  type Chip = { id: string; text: string; remove: () => void };
  const chips: Chip[] = [];
  for (const g of groups) {
    for (const v of filters[g.key] ?? []) {
      chips.push({
        id: `${g.key}:${v}`,
        text: `${g.label}: ${labelOf(g, v)}`,
        remove: () => onChange({ [g.key]: (filters[g.key] ?? []).filter((x) => x !== v) }),
      });
    }
  }
  if (scope !== "regional") {
    chips.push({ id: "scope", text: `${tf("scope")}: ${ts(scope)}`, remove: () => onChange({ scope: "regional" }) });
  }
  const preset = PRESETS.find((p) => p.range === filters.range);
  if (preset) {
    chips.push({ id: "range", text: `${tf("date")}: ${tf(`presets.${preset.key}`)}`, remove: () => onChange({ range: undefined }) });
  }
  if (filters.date_from) {
    chips.push({
      id: "from",
      text: tf("from_chip", { date: f.date(filters.date_from + "T00:00:00", { year: true }) }),
      remove: () => onChange({ date_from: undefined }),
    });
  }
  if (filters.date_to) {
    chips.push({
      id: "to",
      text: tf("to_chip", { date: f.date(filters.date_to + "T00:00:00", { year: true }) }),
      remove: () => onChange({ date_to: undefined }),
    });
  }
  const filterCount = chips.length;
  const anyActive = filterCount > 0 || !!filters.q;
  if (filters.q) {
    chips.push({
      id: "q",
      text: tf("q_chip", { q: filters.q }),
      remove: () => {
        onQInput("");
        onChange({ q: undefined });
      },
    });
  }

  return (
    <section aria-label={tf("panel")} className="space-y-3">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <div role="search" className="relative min-w-0 flex-1">
          <Input
            icon={Search}
            type="search"
            value={qInput}
            onChange={(ev) => onQInput(ev.target.value)}
            placeholder={t("searchPlaceholder")}
            className="!pr-10"
            aria-label={t("searchAria")}
          />
          {qInput && (
            <button
              type="button"
              onClick={() => onQInput("")}
              className="focus-ring absolute right-2.5 top-1/2 grid h-6 w-6 -translate-y-1/2 place-items-center rounded-md text-fg-muted hover:bg-surface-2 hover:text-fg"
              aria-label={t("clear")}
            >
              <X className="h-4 w-4" aria-hidden />
            </button>
          )}
        </div>
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
          <div
            role="group"
            aria-label={ts("label")}
            className="inline-flex min-w-0 overflow-hidden rounded-lg border border-border bg-surface sm:shrink-0"
          >
            {SCOPES.map((s) => (
              <button
                key={s}
                type="button"
                aria-pressed={scope === s}
                onClick={() => onChange({ scope: s })}
                className={cn(
                  "focus-ring h-10 flex-1 whitespace-nowrap px-3 text-sm font-medium transition-colors",
                  scope === s ? "bg-primary text-primary-fg" : "text-fg-muted hover:bg-surface-2 hover:text-fg",
                )}
              >
                {ts(s)}
              </button>
            ))}
          </div>
          <Button
            variant="secondary"
            icon={SlidersHorizontal}
            className="w-full shrink-0 sm:w-auto lg:hidden"
            aria-expanded={open}
            aria-controls="event-filter-panel"
            onClick={() => setOpen((v) => !v)}
          >
            {filterCount ? tf("button", { count: filterCount }) : tf("buttonNone")}
          </Button>
        </div>
      </div>

      <div id="event-filter-panel" className={cn("space-y-3", open ? "block" : "hidden", "lg:block")}>
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
          {groups.map((g) => (
            <MultiSelect
              key={g.key}
              label={g.label}
              options={g.options}
              searchable={g.searchable}
              value={filters[g.key] ?? []}
              onChange={(next) => onChange({ [g.key]: next.length ? next : undefined })}
            />
          ))}
        </div>

        <fieldset className="flex min-w-0 flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-center">
          <legend className="sr-only">{tf("date")}</legend>
          <div role="group" aria-label={tf("date")} className="inline-flex overflow-hidden rounded-lg border border-border bg-surface">
            {PRESETS.map((p) => (
              <button
                key={p.key}
                type="button"
                aria-pressed={filters.range === p.range}
                onClick={() =>
                  onChange(
                    filters.range === p.range
                      ? { range: undefined }
                      : { range: p.range, date_from: undefined, date_to: undefined },
                  )
                }
                className={cn(
                  "focus-ring h-10 flex-1 whitespace-nowrap px-3 text-sm font-medium transition-colors",
                  filters.range === p.range ? "bg-primary text-primary-fg" : "text-fg-muted hover:bg-surface-2 hover:text-fg",
                )}
              >
                {tf(`presets.${p.key}`)}
              </button>
            ))}
          </div>
          <label className="flex items-center gap-2 text-sm text-fg-muted">
            <span className="w-8 shrink-0 sm:w-auto">{tf("from")}</span>
            <input
              type="date"
              value={filters.date_from ?? ""}
              max={filters.date_to || undefined}
              onChange={(ev) => onChange({ date_from: ev.target.value || undefined, range: undefined })}
              className="focus-ring h-10 min-w-0 flex-1 rounded-lg border border-border bg-surface px-3 text-sm text-fg"
            />
          </label>
          <label className="flex items-center gap-2 text-sm text-fg-muted">
            <span className="w-8 shrink-0 sm:w-auto">{tf("to")}</span>
            <input
              type="date"
              value={filters.date_to ?? ""}
              min={filters.date_from || undefined}
              onChange={(ev) => onChange({ date_to: ev.target.value || undefined, range: undefined })}
              className="focus-ring h-10 min-w-0 flex-1 rounded-lg border border-border bg-surface px-3 text-sm text-fg"
            />
          </label>
        </fieldset>
      </div>

      {anyActive && (
        <div className="flex flex-wrap items-center gap-2" aria-label={tf("active")} role="group">
          {chips.map((c) => (
            <button
              key={c.id}
              type="button"
              onClick={c.remove}
              aria-label={tf("remove", { label: c.text })}
              className="focus-ring inline-flex max-w-full items-center gap-1.5 rounded-full border border-border bg-primary-soft px-2.5 py-1 text-xs font-medium text-primary hover:border-border-strong"
            >
              <span className="truncate">{c.text}</span>
              <X className="h-3 w-3 shrink-0" aria-hidden />
            </button>
          ))}
          <button
            type="button"
            onClick={onReset}
            className="focus-ring rounded-md px-2 py-1 text-xs font-medium text-fg-muted underline-offset-2 hover:text-fg hover:underline"
          >
            {tf("resetAll")}
          </button>
        </div>
      )}
    </section>
  );
}
