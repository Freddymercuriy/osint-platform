"use client";

import { ArrowDown, ArrowUp, LayoutGrid, RotateCcw } from "lucide-react";
import { useTranslations } from "next-intl";
import { Suspense, useEffect, useState } from "react";
import { DashboardFilters } from "@/components/dashboard/DashboardFilters";
import { useDashboardFilters } from "@/components/dashboard/useDashboardFilters";
import { useLayout, type WidgetId } from "@/components/dashboard/useLayout";
import {
  CategoriesWidget,
  CountriesWidget,
  HealthWidget,
  HeatmapWidget,
  KpiRow,
  LatestWidget,
  RansomwareWidget,
  SectorsWidget,
  SeverityWidget,
  SourcesWidget,
  TimelineWidget,
  type WidgetProps,
} from "@/components/dashboard/widgets";
import { Button, PageHeader, Skeleton } from "@/components/ui";
import { useFormat } from "@/lib/format";

const WIDGETS: Record<WidgetId, (p: WidgetProps) => JSX.Element> = {
  kpis: KpiRow,
  timeline: TimelineWidget,
  categories: CategoriesWidget,
  countries: CountriesWidget,
  severity: SeverityWidget,
  heatmap: HeatmapWidget,
  sources: SourcesWidget,
  ransomware: RansomwareWidget,
  sectors: SectorsWidget,
  latest: LatestWidget,
  health: HealthWidget,
};

const REFRESH_MS = 60_000;

/** Har 60 s yangilanadi; tab yashirin bo'lsa to'xtaydi va qaytganda darhol yangilanadi. */
function useTick() {
  const [tick, setTick] = useState(0);
  const [at, setAt] = useState(() => new Date());
  useEffect(() => {
    const bump = () => {
      setTick((n) => n + 1);
      setAt(new Date());
    };
    const id = setInterval(() => document.visibilityState === "visible" && bump(), REFRESH_MS);
    const onVis = () => document.visibilityState === "visible" && bump();
    document.addEventListener("visibilitychange", onVis);
    return () => {
      clearInterval(id);
      document.removeEventListener("visibilitychange", onVis);
    };
  }, []);
  return { tick, at };
}

function Dashboard() {
  const t = useTranslations("dashboard");
  const f = useFormat();
  const df = useDashboardFilters();
  const { layout, hide, show, move, resetLayout } = useLayout();
  const { tick, at } = useTick();
  const [customize, setCustomize] = useState(false);

  return (
    <div>
      <PageHeader
        title={t("title")}
        description={t("description")}
        actions={
          <Button variant="secondary" icon={LayoutGrid} onClick={() => setCustomize((v) => !v)} aria-expanded={customize}>
            {t("customize.button")}
          </Button>
        }
      />

      {customize && (
        <div className="card mb-4 p-4">
          <div className="mb-2 flex items-center justify-between gap-2">
            <h2 className="text-sm font-semibold text-fg">{t("customize.title")}</h2>
            <Button variant="ghost" size="sm" icon={RotateCcw} onClick={resetLayout}>
              {t("customize.reset")}
            </Button>
          </div>
          <p className="mb-3 text-xs text-fg-muted">{t("customize.hint")}</p>
          <ul className="grid gap-1 sm:grid-cols-2">
            {layout.order.map((id, i) => {
              const visible = !layout.hidden.includes(id);
              return (
                <li key={id} className="flex items-center gap-2 rounded-lg border border-border px-2 py-1.5">
                  <label className="flex min-w-0 flex-1 items-center gap-2 text-sm text-fg">
                    <input type="checkbox" checked={visible} onChange={() => (visible ? hide(id) : show(id))} className="h-4 w-4 accent-[rgb(var(--primary))]" />
                    <span className="truncate">{t(`widgets.${id}`)}</span>
                  </label>
                  <button type="button" onClick={() => move(id, -1)} disabled={i === 0} aria-label={t("customize.up", { name: t(`widgets.${id}`) })}
                    className="focus-ring grid h-7 w-7 place-items-center rounded-md text-fg-muted hover:bg-surface-2 disabled:opacity-40">
                    <ArrowUp className="h-4 w-4" />
                  </button>
                  <button type="button" onClick={() => move(id, 1)} disabled={i === layout.order.length - 1} aria-label={t("customize.down", { name: t(`widgets.${id}`) })}
                    className="focus-ring grid h-7 w-7 place-items-center rounded-md text-fg-muted hover:bg-surface-2 disabled:opacity-40">
                    <ArrowDown className="h-4 w-4" />
                  </button>
                </li>
              );
            })}
          </ul>
        </div>
      )}

      <DashboardFilters {...df} />
      <p className="mb-3 text-xs text-fg-subtle" aria-live="polite">
        {t("updated", { time: f.time(at) })}
      </p>

      <div className="grid grid-cols-1 items-start gap-4 lg:grid-cols-2">
        {layout.order
          .filter((id) => !layout.hidden.includes(id))
          .map((id) => {
            const W = WIDGETS[id];
            return (
              <W key={id} filters={df.filters} tick={tick} onFilter={df.toggle} onHide={() => hide(id)} eventsHref={df.eventsHref} />
            );
          })}
      </div>
      {layout.hidden.length === layout.order.length && (
        <p className="card p-6 text-center text-sm text-fg-muted">{t("customize.allHidden")}</p>
      )}
    </div>
  );
}

export default function DashboardPage() {
  return (
    <Suspense fallback={<Skeleton className="h-96 w-full" />}>
      <Dashboard />
    </Suspense>
  );
}
