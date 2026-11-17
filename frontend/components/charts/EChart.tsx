"use client";

import type { EChartsCoreOption } from "echarts/core";
import { useTheme } from "next-themes";
import { useEffect, useRef, useState } from "react";
import { readChartTokens, type ChartTokens } from "@/lib/chartTheme";
import type { EChartsType } from "@/lib/echarts";

export type ChartClick = { seriesName?: string; name?: string; value?: unknown; data?: unknown; componentType?: string };

/**
 * Yagona ECharts o'rami: kutubxona dinamik yuklanadi, ranglar tokenlardan, tema almashganda qayta chiziladi,
 * konteyner o'lchami o'zgarsa moslashadi. `build(tokens)` — option yasovchi funksiya.
 */
export default function EChart({
  build,
  height = 280,
  ariaLabel,
  onClick,
  onLegendToggle,
}: {
  build: (t: ChartTokens) => EChartsCoreOption;
  height?: number;
  ariaLabel: string;
  onClick?: (p: ChartClick) => void;
  /** Legenda elementi bosilganda (o'chirish o'rniga filtr qo'shish uchun) */
  onLegendToggle?: (name: string) => void;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const chart = useRef<EChartsType | null>(null);
  const handlers = useRef({ onClick, onLegendToggle });
  handlers.current = { onClick, onLegendToggle };
  const { resolvedTheme } = useTheme();
  const [ready, setReady] = useState(false);

  // Bir marta: kutubxonani yuklash va instance yaratish
  useEffect(() => {
    let disposed = false;
    let ro: ResizeObserver | null = null;
    import("@/lib/echarts").then(({ default: echarts }) => {
      if (disposed || !ref.current) return;
      const inst = echarts.init(ref.current, undefined, { renderer: "svg" });
      chart.current = inst;
      inst.on("click", (p) => handlers.current.onClick?.(p as ChartClick));
      inst.on("legendselectchanged", (p) => {
        const e = p as { name: string; selected: Record<string, boolean> };
        if (handlers.current.onLegendToggle) {
          // legenda filtr vazifasini bajaradi: seriyani yashirmaymiz
          inst.dispatchAction({ type: "legendSelect", name: e.name });
          handlers.current.onLegendToggle(e.name);
        }
      });
      ro = new ResizeObserver(() => inst.resize());
      ro.observe(ref.current);
      setReady(true);
    });
    return () => {
      disposed = true;
      ro?.disconnect();
      chart.current?.dispose();
      chart.current = null;
    };
  }, []);

  // Ma'lumot yoki tema o'zgarsa — qayta chizish (tokenlar <html class> qo'yilgandan keyin o'qiladi)
  useEffect(() => {
    if (!ready || !chart.current) return;
    const id = requestAnimationFrame(() => {
      chart.current?.setOption({ animationDuration: 250, ...build(readChartTokens()) }, { notMerge: true });
    });
    return () => cancelAnimationFrame(id);
  }, [ready, build, resolvedTheme]);

  return <div ref={ref} role="img" aria-label={ariaLabel} style={{ height, width: "100%" }} />;
}
