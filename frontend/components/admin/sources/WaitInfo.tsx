"use client";

import { Hourglass } from "lucide-react";
import { useTranslations } from "next-intl";
import { useEffect, useRef, useState } from "react";
import { useFormat } from "@/components/ui";
import type { Source } from "@/lib/adminApi";
import { cn } from "@/lib/cn";
import { KNOWN_OUTCOMES, humanInterval } from "./lib";

const FAILED = (o: string | null) => !!o && o !== "ok" && o !== "not_modified";
const OVERDUE_REFRESH_MS = 45_000; // rejalashtiruvchi tiki 15–30 s + so'rov vaqti

/** Soniyada yangilanadigan "hozir" (faqat shu komponent qayta chiziladi). */
function useNow(active: boolean): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!active) return;
    const id = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(id);
  }, [active]);
  return now;
}

/**
 * Manba bloklangan / so'rovlari cheklangan / xato bersa — nega (natija + HTTP kodi), sayt qancha kutishni so'ragani
 * (Retry-After) va qayta urinishgacha qolgan vaqt (jonli). Vaqt o'tib ketsa `onDue` bilan satr qayta o'qiladi.
 */
export default function WaitInfo({ s, onDue, className }: { s: Source; onDue?: () => void; className?: string }) {
  const t = useTranslations("adminSources");
  const f = useFormat();
  const show = s.enabled && FAILED(s.last_outcome) && s.status !== "ok" && s.status !== "never_run";
  const now = useNow(show && !!s.next_run_at);
  const due = useRef(0);

  const left = s.next_run_at ? Date.parse(s.next_run_at) - now : null;
  useEffect(() => {
    if (!show || left == null || left > -OVERDUE_REFRESH_MS || !onDue) return;
    if (now - due.current < OVERDUE_REFRESH_MS) return;
    due.current = now;
    onDue();
  }, [show, left, now, onDue]);

  if (!show || !s.last_outcome) return null;
  const outcome = KNOWN_OUTCOMES.includes(s.last_outcome) ? t(`outcomes.${s.last_outcome}`) : s.last_outcome;
  const limited = s.last_outcome === "rate_limited" || s.last_outcome === "blocked";
  return (
    <div className={cn("mt-1 space-y-0.5 text-xs", className)}>
      <div className={cn("font-medium", limited ? "text-warning" : "text-danger")}>
        {outcome}
        {s.last_http_status ? ` · HTTP ${s.last_http_status}` : ""}
      </div>
      {s.retry_after_seconds != null && (
        <div className="text-fg-muted">{t("wait.siteAsked", { d: humanInterval(s.retry_after_seconds, t), header: s.kind.startsWith("telegram") ? "FloodWait" : "Retry-After" })}</div>
      )}
      {left != null && (
        <div
          className="inline-flex items-center gap-1 tabular-nums text-fg"
          title={s.next_run_at ? t("wait.retryAt", { time: f.dateTime(s.next_run_at) }) : undefined}
        >
          <Hourglass className="h-3 w-3 shrink-0" aria-hidden />
          {left > 1000 ? t("wait.retryIn", { d: humanInterval(Math.ceil(left / 1000), t) }) : t("wait.retryNow")}
        </div>
      )}
    </div>
  );
}
