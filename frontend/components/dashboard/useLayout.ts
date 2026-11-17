"use client";

import { useCallback, useEffect, useState } from "react";

export const WIDGET_IDS = [
  "kpis", "timeline", "categories", "countries", "severity", "heatmap", "sources", "ransomware", "sectors", "latest", "health",
] as const;
export type WidgetId = (typeof WIDGET_IDS)[number];
type Layout = { order: WidgetId[]; hidden: WidgetId[] };

const KEY = "osint.dashboard.layout.v2";
const DEFAULT: Layout = { order: [...WIDGET_IDS], hidden: [] };

/** Vidjetlar tartibi va ko'rinishi — brauzerda eslab qolinadi (localStorage). */
export function useLayout() {
  const [layout, setLayout] = useState<Layout>(DEFAULT);
  useEffect(() => {
    try {
      const saved = JSON.parse(localStorage.getItem(KEY) || "null") as Layout | null;
      if (saved?.order) {
        const order = [...saved.order.filter((id) => WIDGET_IDS.includes(id)), ...WIDGET_IDS.filter((id) => !saved.order.includes(id))];
        setLayout({ order, hidden: (saved.hidden ?? []).filter((id) => WIDGET_IDS.includes(id)) });
      }
    } catch {
      /* buzilgan qiymat — standart */
    }
  }, []);
  const save = useCallback((l: Layout) => {
    setLayout(l);
    try {
      localStorage.setItem(KEY, JSON.stringify(l));
    } catch {
      /* ignore */
    }
  }, []);
  const hide = useCallback((id: WidgetId) => save({ ...layout, hidden: [...new Set([...layout.hidden, id])] }), [layout, save]);
  const show = useCallback((id: WidgetId) => save({ ...layout, hidden: layout.hidden.filter((x) => x !== id) }), [layout, save]);
  const move = useCallback(
    (id: WidgetId, dir: -1 | 1) => {
      const order = [...layout.order];
      const i = order.indexOf(id);
      const j = i + dir;
      if (i < 0 || j < 0 || j >= order.length) return;
      [order[i], order[j]] = [order[j], order[i]];
      save({ ...layout, order });
    },
    [layout, save],
  );
  const resetLayout = useCallback(() => save(DEFAULT), [save]);
  return { layout, hide, show, move, resetLayout };
}
