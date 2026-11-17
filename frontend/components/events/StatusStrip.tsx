"use client";

import { AlertTriangle, CalendarDays, Clock, Database, Send, Sparkles } from "lucide-react";
import { useTranslations } from "next-intl";
import { Badge, Card, LiveDot, Skeleton, toneClass } from "@/components/ui";
import { useCategories } from "@/lib/useCategories";
import { useFormat } from "@/lib/format";
import { cn } from "@/lib/cn";
import type { CollectorStatus, FailingSource, TgStatus } from "@/lib/api";

/** Ishlamayotgan manbalar: nomi, sababi, sayt so'ragan kutish va qayta urinish vaqti (yig'uvchining o'zi ishlaydi). */
function FailingSources({ items, total }: { items: FailingSource[]; total: number }) {
  const t = useTranslations("events");
  const f = useFormat();
  const more = Math.max(0, total - items.length);
  return (
    <div role="status" className={cn("rounded-lg border px-4 py-3 text-sm", toneClass("amber"))}>
      <div className="flex items-start gap-2 font-medium">
        <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
        <span>{t("sourcesDown", { count: total })}</span>
      </div>
      <ul className="mt-1.5 space-y-1 pl-6">
        {items.map((s) => {
          const kind = s.outcome === "rate_limited" ? "rate_limited" : s.status === "blocked" ? "blocked" : "down";
          return (
            <li key={s.id} className="break-words">
              <span className="font-semibold">{s.name}</span> — {t(`failing.${kind}`)}
              {s.error ? `: ${s.error}` : ""}
              {s.retry_after_seconds != null && ` · ${t("failing.siteAsked", { min: Math.max(1, Math.ceil(s.retry_after_seconds / 60)) })}`}
              {s.next_run_at && (
                <span title={f.dateTime(s.next_run_at)}> · {t("failing.retry", { when: f.ago(s.next_run_at) })}</span>
              )}
            </li>
          );
        })}
      </ul>
      {more > 0 && <div className="mt-1 pl-6 text-xs">{t("sourcesDownMore", { count: more })}</div>}
    </div>
  );
}

export function StatusStrip({
  cs,
  tg,
  loading,
  lastNew,
}: {
  cs: CollectorStatus | null;
  tg: TgStatus | null;
  loading: boolean;
  lastNew: number | null;
}) {
  const t = useTranslations("events");
  const f = useFormat();
  const { bySlug } = useCategories();

  if (loading && !cs) {
    return (
      <Card className="flex flex-wrap items-center gap-4 px-5 py-3.5">
        <Skeleton className="h-4 w-56" />
        <Skeleton className="h-4 w-40" />
        <Skeleton className="h-4 w-32" />
      </Card>
    );
  }
  const minutes = cs ? Math.max(1, Math.round(cs.poll_seconds / 60)) : null;
  const item = "flex items-center gap-1.5 text-fg-muted";
  const num = "font-mono tabular-nums text-fg";
  return (
    <div className="space-y-3">
      <Card className="px-4 py-3.5 sm:px-5">
        <div className="flex flex-col gap-3 text-sm md:flex-row md:items-center md:justify-between">
          <div className="flex flex-wrap items-center gap-x-5 gap-y-2">
            <div className="flex items-center gap-2.5">
              <LiveDot tone={!cs ? "red" : cs.failing_total || cs.last_error || !cs.running ? "amber" : "emerald"} />
              <span className="font-medium text-fg">
                {!cs ? t("status.unknown") : cs.running ? t("status.live") : t("status.stopped")}
              </span>
            </div>
            {cs && (
              <>
                <span className={item}>
                  <Clock className="h-3.5 w-3.5" aria-hidden />
                  {t("status.every", { minutes: minutes ?? 0 })} · {t("status.last")}:{" "}
                  <span className="text-fg">{cs.last_run ? f.ago(cs.last_run) : t("status.never")}</span>
                </span>
                <span className={item}>
                  <Database className="h-3.5 w-3.5" aria-hidden />
                  {t("status.inDb")} <span className={num}>{f.number(cs.total_events)}</span>
                </span>
                {cs.since && (
                  <span className={item} title={t("status.sinceHint", { date: f.dateTime(cs.since) })}>
                    <CalendarDays className="h-3.5 w-3.5" aria-hidden />
                    {t("status.since", { date: f.date(cs.since, { short: true }) })}
                  </span>
                )}
                {cs.retention_days > 0 && (
                  <span
                    className={item}
                    title={
                      t("status.retentionHint", { days: cs.retention_days }) +
                      (cs.retention_keep.length
                        ? " " + t("status.keepHint", { list: cs.retention_keep.map((k) => bySlug(k).name).join(", ") })
                        : "")
                    }
                  >
                    <CalendarDays className="h-3.5 w-3.5" aria-hidden />
                    {t("status.retention", { days: cs.retention_days })}
                  </span>
                )}
                {cs.last_new > 0 && (
                  <span className="flex items-center gap-1.5 text-success">
                    <Sparkles className="h-3.5 w-3.5" aria-hidden />
                    {t("status.lastNew", { count: cs.last_new })}
                  </span>
                )}
              </>
            )}
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {lastNew !== null && (
              <Badge tone={lastNew > 0 ? "green" : "slate"} icon={Sparkles} className="animate-fade-in">
                {lastNew > 0 ? t("newEvents", { count: lastNew }) : t("noNew")}
              </Badge>
            )}
            {tg && (
              <Badge tone={tg.authorized ? "sky" : "amber"} icon={Send} title={tg.authorized ? undefined : tg.message}>
                {tg.authorized ? (
                  <span>
                    Telegram: <span className="font-mono">{tg.account}</span> ·{" "}
                    {tg.chats_filter.length ? t("tg.chats", { count: tg.chats_filter.length }) : t("tg.allChats")}
                    {tg.uz_filter ? ` · ${t("tg.regionFilter")}` : ""}
                  </span>
                ) : (
                  t("tg.notConnected")
                )}
              </Badge>
            )}
          </div>
        </div>
      </Card>
      {cs?.failing?.length ? (
        <FailingSources items={cs.failing} total={cs.failing_total ?? cs.failing.length} />
      ) : null}
    </div>
  );
}
