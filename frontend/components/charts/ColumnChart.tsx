"use client";

import { useMemo, useState } from "react";
import { useFormat } from "@/lib/format";

/** Bitta qatorli ustunli grafik. Ranglar tokenlardan (--chart-1), tema bilan almashadi. */

export type ColumnDatum = {
  key: string;
  label: string; // o'q yorlig'i (qisqa)
  fullLabel: string; // tooltip sarlavhasi
  value: number;
  breakdown?: { label: string; value: number }[];
};

/** Eng katta qiymatdan sal yuqori "chiroyli" shkala cho'qqisi. */
function niceMax(v: number): number {
  if (v <= 4) return 4;
  const p = Math.pow(10, Math.floor(Math.log10(v)));
  const n = v / p;
  const step = [1, 1.2, 1.6, 2, 3, 4, 5, 6, 8, 10].find((s) => n <= s) ?? 10;
  return Math.round(step * p);
}

export default function ColumnChart({
  data,
  height = 220,
  valueLabel,
  ariaLabel,
}: {
  data: ColumnDatum[];
  height?: number;
  valueLabel: string;
  ariaLabel: string;
}) {
  const f = useFormat();
  const [hover, setHover] = useState<number | null>(null);

  const W = 640;
  const pad = { top: 12, right: 8, bottom: 26, left: 36 };
  const innerW = W - pad.left - pad.right;
  const innerH = height - pad.top - pad.bottom;

  const max = useMemo(() => niceMax(Math.max(0, ...data.map((d) => d.value))), [data]);
  const ticks = [0, max / 2, max];
  const slot = innerW / Math.max(1, data.length);
  const gap = Math.max(2, slot * 0.28);
  const barW = Math.max(3, slot - gap);
  const labelEvery = data.length > 16 ? 3 : data.length > 10 ? 2 : 1;
  const y = (v: number) => pad.top + innerH - (v / max) * innerH;

  const h = hover !== null ? data[hover] : null;
  const tipLeftPct = hover !== null ? ((pad.left + slot * hover + slot / 2) / W) * 100 : 0;

  return (
    <div className="relative w-full" onMouseLeave={() => setHover(null)}>
      <svg viewBox={`0 0 ${W} ${height}`} className="h-auto w-full" role="img" aria-label={ariaLabel}>
        {ticks.map((t) => (
          <g key={t}>
            <line
              x1={pad.left}
              x2={W - pad.right}
              y1={y(t)}
              y2={y(t)}
              className="stroke-border"
              strokeDasharray={t === 0 ? undefined : "3 4"}
            />
            <text x={pad.left - 8} y={y(t) + 4} textAnchor="end" className="fill-fg-muted font-mono" fontSize="10">
              {f.number(Math.round(t))}
            </text>
          </g>
        ))}

        {data.map((d, i) => {
          const x = pad.left + slot * i + gap / 2;
          const top = y(d.value);
          const bh = pad.top + innerH - top;
          const r = Math.min(4, barW / 2, bh);
          const active = hover === i;
          return (
            <g key={d.key}>
              <rect
                x={pad.left + slot * i}
                y={pad.top}
                width={slot}
                height={innerH}
                className={active ? "fill-surface-2" : "fill-transparent"}
                onMouseEnter={() => setHover(i)}
                onFocus={() => setHover(i)}
                onBlur={() => setHover(null)}
                tabIndex={0}
                aria-label={`${d.fullLabel}: ${f.number(d.value)} ${valueLabel}`}
              />
              {d.value > 0 && (
                <path
                  pointerEvents="none"
                  className="fill-[rgb(var(--chart-1))]"
                  style={{ opacity: hover === null || active ? 1 : 0.6, transition: "opacity .15s" }}
                  d={`M${x},${top + bh} V${top + r} Q${x},${top} ${x + r},${top} H${x + barW - r} Q${x + barW},${top} ${x + barW},${top + r} V${top + bh} Z`}
                />
              )}
              {i % labelEvery === 0 && (
                <text
                  x={x + barW / 2}
                  y={height - 8}
                  textAnchor="middle"
                  className={active ? "fill-fg" : "fill-fg-muted"}
                  fontSize="10"
                >
                  {d.label}
                </text>
              )}
            </g>
          );
        })}
      </svg>

      {h && (
        <div
          className="pointer-events-none absolute top-0 z-10 w-48 -translate-x-1/2 rounded-lg border border-border-strong bg-surface px-3 py-2.5 text-xs shadow-lg"
          style={{ left: `clamp(6rem, ${tipLeftPct}%, calc(100% - 6rem))` }}
        >
          <div className="text-fg-muted">{h.fullLabel}</div>
          <div className="mt-0.5 flex items-baseline gap-1.5">
            <span className="h-2 w-2 rounded-sm bg-[rgb(var(--chart-1))]" />
            <span className="font-mono text-base font-semibold text-fg">{f.number(h.value)}</span>
            <span className="text-fg-muted">{valueLabel}</span>
          </div>
          {h.breakdown && h.breakdown.length > 0 && (
            <div className="mt-1.5 space-y-0.5 border-t border-border pt-1.5">
              {h.breakdown.map((b) => (
                <div key={b.label} className="flex justify-between gap-2 text-fg-muted">
                  <span className="truncate">{b.label}</span>
                  <span className="font-mono text-fg">{f.number(b.value)}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
