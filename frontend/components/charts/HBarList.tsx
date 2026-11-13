"use client";

import type { LucideIcon } from "lucide-react";
import { useState } from "react";
import { cn } from "@/lib/cn";

/**
 * Gorizontal chiziqli ro'yxat (kategoriya/manba hajmi).
 * Bitta rang (#3987e5), yorliq va qiymat matn bilan (rang yolg'iz ma'no tashimaydi), hover'da ulush (%).
 */
export type HBarDatum = { key: string; label: string; value: number; icon?: LucideIcon; href?: string };

const SERIES = "#3987e5";

export default function HBarList({ data, total }: { data: HBarDatum[]; total?: number }) {
  const [hover, setHover] = useState<string | null>(null);
  const max = Math.max(1, ...data.map((d) => d.value));
  const sum = total ?? data.reduce((a, d) => a + d.value, 0);

  return (
    <ul className="space-y-3">
      {data.map((d) => {
        const Icon = d.icon;
        const pct = sum ? Math.round((d.value / sum) * 100) : 0;
        const row = (
          <div
            className="group"
            onMouseEnter={() => setHover(d.key)}
            onMouseLeave={() => setHover(null)}
          >
            <div className="mb-1.5 flex items-center gap-2 text-sm">
              {Icon && <Icon className="h-3.5 w-3.5 text-slate-500 group-hover:text-slate-300" />}
              <span className="flex-1 truncate text-slate-300 group-hover:text-white">{d.label}</span>
              <span className={cn("font-mono text-xs transition", hover === d.key ? "text-slate-300" : "text-transparent")}>
                {pct}%
              </span>
              <span className="w-10 text-right font-mono text-sm tabular-nums text-slate-200">{d.value}</span>
            </div>
            <div className="h-2 overflow-hidden rounded-full bg-white/[0.04]">
              <div
                className="h-full rounded-full transition-all duration-700"
                style={{
                  width: `${Math.max(d.value ? 2 : 0, (d.value / max) * 100)}%`,
                  background: hover === d.key ? "#6da7ec" : SERIES,
                }}
              />
            </div>
          </div>
        );
        return <li key={d.key}>{d.href ? <a href={d.href}>{row}</a> : row}</li>;
      })}
    </ul>
  );
}
