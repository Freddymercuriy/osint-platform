"use client";

import { Activity } from "lucide-react";
import Link from "next/link";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";
import SourceStatusBadge from "@/components/admin/SourceStatusBadge";
import { Badge, Button, ErrorBanner, Skeleton, useFormat } from "@/components/ui";
import { getCollectorAdmin, type CollectorAdmin } from "@/lib/adminApi";
import { Fact, SectionCard } from "./shared";

const REFRESH_MS = 30_000;

export default function CollectorCard() {
  const t = useTranslations("adminSystem");
  const tc = useTranslations("common");
  const f = useFormat();
  const [data, setData] = useState<CollectorAdmin | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setBusy(true);
    try {
      setData(await getCollectorAdmin());
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : tc("error"));
    } finally {
      setBusy(false);
    }
  }, [tc]);

  useEffect(() => {
    load();
    const tick = () => { if (document.visibilityState === "visible") load(); };
    const id = setInterval(tick, REFRESH_MS);
    document.addEventListener("visibilitychange", tick);
    return () => { clearInterval(id); document.removeEventListener("visibilitychange", tick); };
  }, [load]);

  const statuses = data ? Object.entries(data.by_status).filter(([, n]) => n > 0) : [];

  return (
    <SectionCard
      id="sys-collector"
      icon={Activity}
      title={t("collector.title")}
      hint={t("collector.hint")}
      actions={<Button variant="secondary" size="sm" onClick={load} loading={busy}>{tc("refresh")}</Button>}
    >
      {error && <div className="mb-3"><ErrorBanner message={error} /></div>}
      {!data && !error && <Skeleton className="h-40 w-full" />}
      {data && (
        <div className="space-y-4">
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone={data.running ? "green" : "red"}>{data.running ? t("collector.running") : t("collector.stopped")}</Badge>
            <Badge tone={data.lock_held ? "green" : "amber"}>{data.lock_held ? t("collector.lockHeld") : t("collector.lockFree")}</Badge>
            {!data.enabled && <Badge tone="slate">{t("collector.disabled")}</Badge>}
          </div>
          <p className="text-xs text-fg-muted">{t("collector.lockHelp")}</p>
          <dl className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
            <Fact label={t("collector.started")}>{data.started_at ? f.dateTime(data.started_at) : "—"}</Fact>
            <Fact label={t("collector.lastTick")}>{data.last_tick ? f.ago(data.last_tick) : "—"}</Fact>
            <Fact label={t("collector.active")}>{f.number(data.active.length)}</Fact>
            <Fact label={t("collector.runsSinceStart")}>{f.number(data.runs)}</Fact>
            <Fact label={t("collector.runs24h")}>{f.number(data.runs_24h)}</Fact>
            <Fact label={t("collector.failed24h")}>
              <span className={data.failed_runs_24h > 0 ? "text-danger" : undefined}>{f.number(data.failed_runs_24h)}</span>
            </Fact>
            <Fact label={t("collector.sourcesTotal")}>{f.number(data.sources_total)}</Fact>
            <Fact label={t("collector.sourcesEnabled")}>{f.number(data.sources_enabled)}</Fact>
          </dl>
          <div>
            <div className="mb-2 text-xs text-fg-muted">{t("collector.byStatus")}</div>
            {statuses.length === 0 ? (
              <p className="text-sm text-fg-muted">{t("collector.noSources")}</p>
            ) : (
              <ul className="flex flex-wrap gap-2">
                {statuses.map(([s, n]) => (
                  <li key={s}>
                    <Link
                      href={`/dashboard/admin/sources?status=${encodeURIComponent(s)}`}
                      className="focus-ring inline-flex items-center gap-1.5 rounded-full"
                      aria-label={t("collector.showStatus", { count: n })}
                    >
                      <SourceStatusBadge status={s} />
                      <span className="text-sm font-medium text-fg">{f.number(n)}</span>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </div>
          {data.last_error && (
            <div role="status" className="tone-red rounded-lg border border-tone-border bg-tone-bg px-3 py-2 text-sm text-tone-fg">
              <span className="font-medium">{t("collector.lastError")}: </span>
              <span className="break-words">{data.last_error}</span>
            </div>
          )}
        </div>
      )}
    </SectionCard>
  );
}
