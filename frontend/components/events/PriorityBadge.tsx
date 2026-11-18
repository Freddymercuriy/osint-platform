"use client";

import { Gauge } from "lucide-react";
import { useTranslations } from "next-intl";
import { useEffect, useId, useRef, useState } from "react";
import { Badge } from "@/components/ui";
import type { EventItem, PriorityReason } from "@/lib/api";
import type { Tone } from "@/lib/categories";
import { cn } from "@/lib/cn";

const BAND_TONE: Record<string, Tone> = { critical: "red", high: "orange", medium: "amber", low: "slate" };

/** Sabab matni (kod → tarjima; parametr — davlat, soha, nom, son). */
export function useReasonText() {
  const t = useTranslations("events.priority.reasons");
  const tsev = useTranslations("severity");
  const tco = useTranslations("country");
  const tsec = useTranslations("dashboard.sector");
  return (r: PriorityReason): string => {
    const arg = r.arg === undefined || r.arg === null ? "" : String(r.arg);
    if (r.code.startsWith("sev_")) {
      const level = r.code.slice(4);
      return t("sev", { level: tsev.has(level) ? tsev(level) : level });
    }
    switch (r.code) {
      case "country_ca":
        return t("country_ca", { country: tco.has(arg) ? tco(arg) : arg });
      case "sector":
        return t("sector", { sector: tsec.has(arg) ? tsec(arg) : arg });
      case "watch_org":
      case "watch_product":
      case "watch_person":
        return t(r.code, { name: arg });
      case "multi_source":
        return t("multi_source", { count: Number(arg) || 0 });
      case "records_100k":
      case "records_1m":
        return t(r.code, { count: (Number(arg) || 0).toLocaleString() });
      case "stale":
        return t("stale", { hours: Number(arg) || 0 });
      default:
        return t.has(r.code) ? t(r.code) : r.code;
    }
  };
}

/** Ustuvorlik belgisi: band va ball; bosilganda / ustiga kelganda — sabablar ro'yxati (telefonda ham). */
export function PriorityBadge({
  e,
  align = "left",
}: {
  e: Pick<EventItem, "priority" | "priority_band" | "priority_reasons">;
  align?: "left" | "right";
}) {
  const t = useTranslations("events.priority");
  const reasonText = useReasonText();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLSpanElement>(null);
  const id = useId();

  useEffect(() => {
    if (!open) return;
    const close = (ev: MouseEvent | KeyboardEvent) => {
      if (ev instanceof KeyboardEvent ? ev.key === "Escape" : !ref.current?.contains(ev.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", close);
    return () => {
      document.removeEventListener("mousedown", close);
      document.removeEventListener("keydown", close);
    };
  }, [open]);

  if (e.priority === null || e.priority === undefined || !e.priority_band) return null;
  const band = e.priority_band;
  const reasons = e.priority_reasons ?? [];
  const label = `${t(`band.${band}`)} · ${e.priority}`;
  return (
    <span ref={ref} className="group relative inline-flex">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-controls={id}
        aria-label={t("aria", { label })}
        className="focus-ring rounded-full"
      >
        <Badge tone={BAND_TONE[band] ?? "slate"} icon={Gauge}>
          {label}
        </Badge>
      </button>
      <span
        id={id}
        role="tooltip"
        className={cn(
          align === "right" ? "right-0" : "left-0",
          "absolute top-full z-30 mt-1.5 w-64 max-w-[calc(100vw-2rem)] rounded-lg border border-border bg-surface p-3 text-xs shadow-lg",
          open ? "block" : "hidden group-hover:block",
        )}
      >
        <span className="mb-1.5 block font-medium text-fg">{t("reasonsTitle")}</span>
        <span className="block space-y-1">
          {reasons.map((r, i) => (
            <span key={`${r.code}-${i}`} className="flex items-start justify-between gap-3 text-fg-muted">
              <span>{reasonText(r)}</span>
              <span className={cn("font-mono tabular-nums", r.points < 0 ? "text-danger" : "text-fg")}>
                {r.points > 0 ? `+${r.points}` : r.points}
              </span>
            </span>
          ))}
        </span>
        <span className="mt-2 flex justify-between border-t border-border pt-1.5 font-medium text-fg">
          <span>{t("total")}</span>
          <span className="font-mono tabular-nums">{e.priority}/100</span>
        </span>
      </span>
    </span>
  );
}
