"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useMemo } from "react";
import type { RangeKey, StatsFilters } from "@/lib/statsApi";

export type Dim = "category" | "country" | "channel" | "source" | "severity";
export const DIMS: Dim[] = ["category", "country", "channel", "source", "severity"];
const RANGES: RangeKey[] = ["24h", "7d", "30d", "90d", "custom"];

const list = (v: string | null) => (v ? v.split(",").filter(Boolean) : []);

/** Dashboard filtrlari — to'liq URL'da (bookmark/ulashish mumkin). Nomlar /api/stats va /api/events bilan bir xil. */
export function useDashboardFilters() {
  const sp = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();

  const filters: StatsFilters = useMemo(() => {
    const range = sp.get("range") as RangeKey | null;
    const scope = sp.get("scope");
    return {
      range: range && RANGES.includes(range) ? range : "7d",
      date_from: sp.get("date_from") || undefined,
      date_to: sp.get("date_to") || undefined,
      category: list(sp.get("category")),
      country: list(sp.get("country")),
      channel: list(sp.get("channel")),
      source: list(sp.get("source")),
      severity: list(sp.get("severity")),
      scope: scope === "global" || scope === "all" ? scope : "regional",
    };
  }, [sp]);

  const write = useCallback(
    (next: StatsFilters) => {
      const p = new URLSearchParams();
      if (next.range && next.range !== "7d") p.set("range", next.range);
      if (next.range === "custom") {
        if (next.date_from) p.set("date_from", next.date_from);
        if (next.date_to) p.set("date_to", next.date_to);
      }
      for (const d of DIMS) {
        const v = next[d];
        if (v && v.length) p.set(d, v.join(","));
      }
      if (next.scope && next.scope !== "regional") p.set("scope", next.scope);
      const qs = p.toString();
      router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
    },
    [router, pathname],
  );

  const set = useCallback((patch: Partial<StatsFilters>) => write({ ...filters, ...patch }), [filters, write]);

  /** Kesishma filtr: grafikdagi element bosilganda qo'shadi (bor bo'lsa olib tashlaydi). */
  const toggle = useCallback(
    (dim: Dim, value: string) => {
      const cur = filters[dim] ?? [];
      set({ [dim]: cur.includes(value) ? cur.filter((x) => x !== value) : [...cur, value] } as Partial<StatsFilters>);
    },
    [filters, set],
  );

  const reset = useCallback(() => write({ range: filters.range, scope: "regional" }), [filters.range, write]);

  const activeCount = DIMS.reduce((n, d) => n + (filters[d]?.length ?? 0), 0) + (filters.scope !== "regional" ? 1 : 0);

  /** Xuddi shu filtrlar bilan Events sahifasi (davr ham xuddi shunday: nisbiy `range` yoki aniq sanalar). */
  const eventsHref = useMemo(() => {
    const p = new URLSearchParams();
    for (const d of DIMS) if (filters[d]?.length) p.set(d, filters[d]!.join(","));
    if (filters.scope && filters.scope !== "regional") p.set("scope", filters.scope);
    if (filters.range === "custom") {
      if (filters.date_from) p.set("date_from", filters.date_from);
      if (filters.date_to) p.set("date_to", filters.date_to);
    } else {
      p.set("range", filters.range ?? "7d");
    }
    return `/dashboard/events?${p.toString()}`;
  }, [filters]);

  return { filters, set, toggle, reset, activeCount, eventsHref };
}
