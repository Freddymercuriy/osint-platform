"use client";

import { useMemo, useRef, useState } from "react";

/**
 * Bitta qatorli ustunli grafik (vaqt bo'yicha).
 * dataviz qoidalari: bitta rang (#3987e5, dark surface'da validatsiyadan o'tgan), ingichka ustunlar,
 * baseline'ga tayangan 4px yumaloq uch, ustunlar orasida bo'shliq, sokin grid, hover tooltip.
 * Bitta qator — legend yo'q, sarlavha nomlaydi.
 */

export type ColumnDatum = {
  key: string; // noyob kalit (sana)
  label: string; // o'q yorlig'i (qisqa)
  fullLabel: string; // tooltip sarlavhasi
  value: number;
  breakdown?: { label: string; value: number }[]; // tooltip ichidagi tafsilot
};

const SERIES = "#3987e5";
const SERIES_HOVER = "#6da7ec";

function niceMax(v: number): number {
  if (v <= 4) return 4;
  const p = Math.pow(10, Math.floor(Math.log10(v)));
  const n = v / p;
  const step = n <= 2 ? 2 : n <= 5 ? 5 : 10;
  return step * p;
}

export default function ColumnChart({
  data,
  height = 220,
  valueLabel = "hodisa",
}: {
  data: ColumnDatum[];
  height?: number;
  valueLabel?: string;
}) {
  const [hover, setHover] = useState<number | null>(null);
  const wrapRef = useRef<HTMLDivElement>(null);

  const W = 640; // viewBox kengligi (responsive — SVG 100% ga cho'ziladi)
  const pad = { top: 12, right: 8, bottom: 26, left: 32 };
  const innerW = W - pad.left - pad.right;
  const innerH = height - pad.top - pad.bottom;

  const max = useMemo(() => niceMax(Math.max(0, ...data.map((d) => d.value))), [data]);
  const ticks = [0, max / 2, max];
  const slot = innerW / Math.max(1, data.length);
  const gap = Math.max(2, slot * 0.28); // ustunlar orasida bo'shliq
  const barW = Math.max(3, slot - gap);
  const labelEvery = data.length > 16 ? 3 : data.length > 10 ? 2 : 1;

  const y = (v: number) => pad.top + innerH - (v / max) * innerH;

  const h = hover !== null ? data[hover] : null;
  const tipLeftPct = hover !== null ? ((pad.left + slot * hover + slot / 2) / W) * 100 : 0;

  return (
    <div ref={wrapRef} className="relative w-full" onMouseLeave={() => setHover(null)}>
      <svg viewBox={`0 0 ${W} ${height}`} className="h-auto w-full" role="img" aria-label="Kunlik hodisalar grafigi">
        {/* Grid + y o'qi */}
        {ticks.map((t) => (
          <g key={t}>
            <line
              x1={pad.left}
              x2={W - pad.right}
              y1={y(t)}
              y2={y(t)}
              stroke="rgba(148,163,184,0.12)"
              strokeDasharray={t === 0 ? undefined : "3 4"}
            />
            <text x={pad.left - 8} y={y(t) + 4} textAnchor="end" className="fill-slate-500 font-mono" fontSize="10">
              {Math.round(t)}
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
              {/* Hover maydoni — ustundan kattaroq */}
              <rect
                x={pad.left + slot * i}
                y={pad.top}
                width={slot}
                height={innerH}
                fill={active ? "rgba(148,163,184,0.06)" : "transparent"}
                onMouseEnter={() => setHover(i)}
                onFocus={() => setHover(i)}
                tabIndex={0}
                aria-label={`${d.fullLabel}: ${d.value} ${valueLabel}`}
              />
              {d.value > 0 && (
                <path
                  pointerEvents="none"
                  fill={active ? SERIES_HOVER : SERIES}
                  // Faqat yuqori burchaklar yumaloq — pastki qismi baseline'ga tayanadi
                  d={`M${x},${top + bh} V${top + r} Q${x},${top} ${x + r},${top} H${x + barW - r} Q${x + barW},${top} ${x + barW},${top + r} V${top + bh} Z`}
                />
              )}
              {i % labelEvery === 0 && (
                <text
                  x={x + barW / 2}
                  y={height - 8}
                  textAnchor="middle"
                  className={active ? "fill-slate-200" : "fill-slate-500"}
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
          className="pointer-events-none absolute top-0 z-10 w-48 -translate-x-1/2 rounded-xl border border-white/10 bg-ink-900/95 px-3 py-2.5 text-xs shadow-2xl backdrop-blur"
          style={{ left: `clamp(6rem, ${tipLeftPct}%, calc(100% - 6rem))` }}
        >
          <div className="text-slate-400">{h.fullLabel}</div>
          <div className="mt-0.5 flex items-baseline gap-1.5">
            <span className="h-2 w-2 rounded-sm" style={{ background: SERIES }} />
            <span className="font-mono text-base font-semibold text-white">{h.value}</span>
            <span className="text-slate-400">{valueLabel}</span>
          </div>
          {h.breakdown && h.breakdown.length > 0 && (
            <div className="mt-1.5 space-y-0.5 border-t border-white/[0.06] pt-1.5">
              {h.breakdown.map((b) => (
                <div key={b.label} className="flex justify-between text-slate-400">
                  <span>{b.label}</span>
                  <span className="font-mono text-slate-200">{b.value}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
