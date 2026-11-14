"use client";

import type { LucideIcon } from "lucide-react";
import Link from "next/link";
import { useFormat } from "@/lib/format";

/** Gorizontal chiziqli ro'yxat. Rang tokendan; yorliq, qiymat va ulush matn bilan beriladi. */
export type HBarDatum = { key: string; label: string; value: number; icon?: LucideIcon; href?: string };

export default function HBarList({ data, total }: { data: HBarDatum[]; total?: number }) {
  const f = useFormat();
  const max = Math.max(1, ...data.map((d) => d.value));
  const sum = total ?? data.reduce((a, d) => a + d.value, 0);

  return (
    <ul className="space-y-3">
      {data.map((d) => {
        const Icon = d.icon;
        const pct = sum ? d.value / sum : 0;
        const row = (
          <div className="group">
            <div className="mb-1.5 flex items-center gap-2 text-sm">
              {Icon && <Icon className="h-3.5 w-3.5 shrink-0 text-fg-subtle" aria-hidden />}
              <span className="flex-1 truncate text-fg">{d.label}</span>
              <span className="font-mono text-xs text-fg-muted">{f.percent(pct)}</span>
              <span className="min-w-10 text-right font-mono text-sm tabular-nums text-fg">{f.number(d.value)}</span>
            </div>
            <div className="h-2 overflow-hidden rounded-full bg-surface-2">
              <div
                className="h-full rounded-full bg-[rgb(var(--chart-1))]"
                style={{ width: `${Math.max(d.value ? 2 : 0, (d.value / max) * 100)}%` }}
              />
            </div>
          </div>
        );
        return (
          <li key={d.key}>
            {d.href ? (
              <Link href={d.href} className="focus-ring block rounded-md">
                {row}
              </Link>
            ) : (
              row
            )}
          </li>
        );
      })}
    </ul>
  );
}
