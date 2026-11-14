"use client";

import { Activity, ArrowRight, BarChart3, Database, ExternalLink, Globe, Radar, Search, ShieldAlert, Table2, Tag } from "lucide-react";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import ColumnChart, { type ColumnDatum } from "@/components/charts/ColumnChart";
import HBarList from "@/components/charts/HBarList";
import {
  Button,
  ButtonLink,
  Card,
  CategoryBadge,
  EmptyState,
  ErrorBanner,
  IconBox,
  PageHeader,
  Skeleton,
  StatTile,
} from "@/components/ui";
import { cn } from "@/lib/cn";
import { useFormat } from "@/lib/format";
import { MODULES } from "@/lib/modules";
import { getOverview, type Overview } from "@/lib/stats";
import { useCategories } from "@/lib/useCategories";

const DAYS = 14;

export default function DashboardPage() {
  const t = useTranslations("dashboard");
  const tc = useTranslations("common");
  const tk = useTranslations("checks");
  const f = useFormat();
  const cats = useCategories();

  const [ov, setOv] = useState<Overview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [view, setView] = useState<"chart" | "table">("chart");

  const load = useCallback(() => {
    getOverview(DAYS)
      .then((o) => {
        setOv(o);
        setError(null);
      })
      .catch((e) => setError(e instanceof Error ? e.message : tc("error")));
  }, [tc]);

  useEffect(() => {
    load();
    const id = setInterval(load, 60_000);
    return () => clearInterval(id);
  }, [load]);

  /** Kategoriya tartibi: bazadagi sort_order bo'yicha, faqat ma'lumoti borlari. */
  const order = useMemo(() => {
    if (!ov) return [] as string[];
    const present = new Set<string>(Object.keys(ov.by_category).filter((k) => ov.by_category[k] > 0));
    const known = cats.list.filter((c) => present.has(c.slug)).map((c) => c.slug);
    const rest = [...present].filter((s) => !known.includes(s)).sort();
    return [...known, ...rest];
  }, [ov, cats.list]);

  const chartData: ColumnDatum[] = useMemo(
    () =>
      (ov?.daily ?? []).map((d) => {
        const dt = new Date(`${d.day}T12:00:00`);
        return {
          key: d.day,
          label: String(dt.getDate()),
          fullLabel: f.date(dt),
          value: d.total,
          breakdown: order.filter((c) => d.by_category[c]).map((c) => ({ label: cats.bySlug(c).name, value: d.by_category[c] })),
        };
      }),
    [ov, order, cats, f],
  );

  const loading = !ov && !error;
  const hasEvents = (ov?.total_events ?? 0) > 0;
  const topCat = order[0] && ov ? [...order].sort((a, b) => ov.by_category[b] - ov.by_category[a])[0] : null;
  const moduleTitle = (kind: string, fallback: string) => (tk.has(`modules.${kind}.title`) ? tk(`modules.${kind}.title`) : fallback);

  return (
    <div className="animate-fade-in space-y-6">
      <PageHeader
        icon={Radar}
        title={t("title")}
        description={t("description")}
        actions={
          <ButtonLink href="/dashboard/events" icon={Radar}>
            {t("openEvents")}
          </ButtonLink>
        }
      />

      {error && (
        <ErrorBanner
          message={error}
          action={
            <Button size="sm" variant="secondary" onClick={load}>
              {tc("retry")}
            </Button>
          }
        />
      )}

      {/* KPI */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatTile label={t("kpi.total")} value={f.number(ov?.total_events ?? 0)} icon={Database} tone="blue" stacked loading={loading} hint={t("kpi.totalHint")} />
        <StatTile label={t("kpi.last24h")} value={f.number(ov?.new_24h ?? 0)} icon={Activity} tone="violet" stacked loading={loading} hint={t("kpi.last24hHint")} />
        <StatTile
          label={t("kpi.topCategory")}
          value={topCat ? cats.bySlug(topCat).name : "—"}
          icon={topCat ? cats.bySlug(topCat).Icon : Tag}
          tone={topCat ? cats.bySlug(topCat).tone : "slate"}
          stacked
          loading={loading}
          hint={topCat && ov ? t("kpi.topCategoryHint", { count: ov.by_category[topCat] }) : t("kpi.noData")}
        />
        <StatTile label={t("kpi.searches")} value={f.number(ov?.searches_total ?? 0)} icon={Search} tone="cyan" stacked loading={loading} hint={t("kpi.searchesHint")} />
      </div>

      {/* Grafiklar */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <Card className="p-5 lg:col-span-2">
          <div className="mb-4 flex items-start justify-between gap-3">
            <div className="min-w-0">
              <h2 className="font-semibold text-fg">{t("daily.title")}</h2>
              <p className="text-xs text-fg-muted">{t("daily.subtitle", { days: DAYS })}</p>
            </div>
            <div className="flex shrink-0 rounded-lg border border-border p-0.5" role="group" aria-label={t("view.label")}>
              {(
                [
                  ["chart", BarChart3, t("view.chart")],
                  ["table", Table2, t("view.table")],
                ] as const
              ).map(([v, Icon, label]) => (
                <button
                  key={v}
                  type="button"
                  onClick={() => setView(v)}
                  aria-pressed={view === v}
                  className={cn(
                    "focus-ring inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs transition-colors",
                    view === v ? "bg-primary-soft text-primary" : "text-fg-muted hover:text-fg",
                  )}
                >
                  <Icon className="h-3.5 w-3.5" aria-hidden /> {label}
                </button>
              ))}
            </div>
          </div>
          {loading ? (
            <Skeleton className="h-56 w-full" />
          ) : !hasEvents ? (
            <EmptyState icon={BarChart3} title={t("daily.emptyTitle")} description={t("daily.emptyText")} />
          ) : view === "chart" ? (
            <ColumnChart data={chartData} valueLabel={t("daily.unit")} ariaLabel={t("daily.title")} />
          ) : (
            <div className="max-h-56 overflow-auto">
              <table className="w-full text-sm">
                <thead className="sticky top-0 bg-surface text-left text-xs text-fg-muted">
                  <tr>
                    <th className="py-1.5 pr-3 font-medium">{t("table.date")}</th>
                    {order.map((c) => (
                      <th key={c} className="px-2 py-1.5 text-right font-medium">{cats.bySlug(c).name}</th>
                    ))}
                    <th className="py-1.5 pl-2 text-right font-medium">{t("table.total")}</th>
                  </tr>
                </thead>
                <tbody className="font-mono text-fg-muted">
                  {[...(ov?.daily ?? [])].reverse().map((d) => (
                    <tr key={d.day} className="border-t border-border">
                      <td className="whitespace-nowrap py-1.5 pr-3 font-sans">{f.date(new Date(`${d.day}T12:00:00`), { short: true })}</td>
                      {order.map((c) => (
                        <td key={c} className="px-2 py-1.5 text-right">{f.number(d.by_category[c] ?? 0)}</td>
                      ))}
                      <td className="py-1.5 pl-2 text-right text-fg">{f.number(d.total)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>

        <Card className="p-5">
          <h2 className="font-semibold text-fg">{t("categories.title")}</h2>
          <p className="mb-5 text-xs text-fg-muted">{t("categories.subtitle")}</p>
          {loading ? (
            <div className="space-y-4">
              {[0, 1, 2, 3, 4].map((i) => (
                <Skeleton key={i} className="h-8 w-full" />
              ))}
            </div>
          ) : !order.length ? (
            <EmptyState icon={Tag} title={t("categories.emptyTitle")} description={t("categories.emptyText")} />
          ) : (
            <HBarList
              total={ov?.total_events}
              data={[...order]
                .sort((a, b) => (ov?.by_category[b] ?? 0) - (ov?.by_category[a] ?? 0))
                .map((c) => ({
                  key: c,
                  label: cats.bySlug(c).name,
                  value: ov?.by_category[c] ?? 0,
                  icon: cats.bySlug(c).Icon,
                  href: `/dashboard/events?category=${encodeURIComponent(c)}`,
                }))}
            />
          )}
        </Card>
      </div>

      {/* Muhim hodisalar + manbalar */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <Card className="overflow-hidden lg:col-span-2">
          <div className="flex items-center justify-between gap-3 border-b border-border px-5 py-4">
            <div className="flex min-w-0 items-center gap-3">
              <IconBox icon={ShieldAlert} tone="red" size="sm" />
              <div className="min-w-0">
                <h2 className="font-semibold text-fg">{t("critical.title")}</h2>
                <p className="text-xs text-fg-muted">{t("critical.subtitle")}</p>
              </div>
            </div>
            <Link href="/dashboard/events" className="focus-ring inline-flex shrink-0 items-center gap-1 rounded text-xs text-primary hover:underline">
              {t("critical.all")} <ArrowRight className="h-3.5 w-3.5" aria-hidden />
            </Link>
          </div>
          {loading ? (
            <div className="space-y-3 p-5">
              {[0, 1, 2].map((i) => (
                <Skeleton key={i} className="h-14 w-full" />
              ))}
            </div>
          ) : !ov?.critical.length ? (
            <EmptyState icon={ShieldAlert} title={t("critical.emptyTitle")} description={t("critical.emptyText")} />
          ) : (
            <ul>
              {ov.critical.map((e) => (
                <li key={e.id}>
                  <a
                    href={e.url}
                    target="_blank"
                    rel="noreferrer"
                    className="focus-ring group flex flex-wrap items-start gap-x-4 gap-y-2 border-b border-border px-5 py-3.5 transition-colors last:border-0 hover:bg-surface-2 sm:flex-nowrap"
                  >
                    <div className="mt-0.5">
                      <CategoryBadge category={e.category} />
                    </div>
                    <div className="order-last min-w-0 basis-full sm:order-none sm:flex-1 sm:basis-0">
                      {/* TODO: API asl sarlavhani qaytaradi; tarjima keyingi bosqichda */}
                      <div className="truncate text-sm font-medium text-fg">{e.title}</div>
                      <div className="mt-0.5 line-clamp-1 text-xs text-fg-muted">{e.summary || e.source}</div>
                    </div>
                    <div className="ml-auto flex shrink-0 items-center gap-1.5 text-xs text-fg-muted sm:ml-0">
                      {f.ago(e.published ?? e.first_seen)}
                      <ExternalLink className="h-3.5 w-3.5" aria-hidden />
                      <span className="sr-only">{t("critical.external")}</span>
                    </div>
                  </a>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card className="p-5">
          <h2 className="font-semibold text-fg">{t("sources.title")}</h2>
          <p className="mb-5 text-xs text-fg-muted">{t("sources.subtitle")}</p>
          {loading ? (
            <div className="space-y-4">
              {[0, 1, 2, 3].map((i) => (
                <Skeleton key={i} className="h-8 w-full" />
              ))}
            </div>
          ) : !ov?.top_sources.length ? (
            <EmptyState icon={Globe} title={t("sources.emptyTitle")} description={t("sources.emptyText")} />
          ) : (
            <HBarList
              total={ov.total_events}
              data={ov.top_sources.map((s) => ({
                key: s.source,
                label: s.source.replace(/^TG: /, ""),
                value: s.count,
                icon: Globe,
              }))}
            />
          )}
        </Card>
      </div>

      {/* Tekshiruv modullari */}
      <section>
        <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
          <h2 className="font-semibold text-fg">{t("modules.title")}</h2>
          <Link href="/dashboard/history" className="focus-ring inline-flex items-center gap-1 rounded text-xs text-fg-muted transition-colors hover:text-primary">
            {t("modules.myChecks")}: <span className="font-mono text-fg">{f.number(ov?.searches_total ?? 0)}</span>
            <ArrowRight className="h-3.5 w-3.5" aria-hidden />
          </Link>
        </div>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {MODULES.map((m) => (
            <Link key={m.kind} href={m.href} className="focus-ring rounded-xl">
              <Card hover className="h-full p-5">
                <IconBox icon={m.icon} tone={m.tone} />
                <div className="mt-4 font-medium text-fg">{moduleTitle(m.kind, m.kind)}</div>
                <div className="mt-3 font-mono text-xs text-fg-subtle">
                  {t("modules.count", { count: ov?.searches_by_kind[m.kind] ?? 0 })}
                </div>
              </Card>
            </Link>
          ))}
        </div>
      </section>
    </div>
  );
}
