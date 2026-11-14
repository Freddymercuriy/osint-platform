"use client";

import { Languages } from "lucide-react";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";
import { Badge, Button, ErrorBanner, Skeleton, useFormat } from "@/components/ui";
import {
  getTranslationStatus,
  retryFailedTranslations,
  runTranslations,
  type TranslationStatus,
} from "@/lib/adminApi";
import { Fact, SectionCard } from "./shared";

const STATUSES = ["done", "pending", "failed", "skipped"] as const;
const LANGS = ["en", "ru", "uz"] as const;

export default function TranslationCard() {
  const t = useTranslations("adminSystem");
  const tc = useTranslations("common");
  const f = useFormat();
  const [data, setData] = useState<TranslationStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [action, setAction] = useState<"retry" | "run" | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const [stats, setStats] = useState<[string, string][] | null>(null);

  const load = useCallback(async () => {
    try {
      setData(await getTranslationStatus());
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : tc("error"));
    }
  }, [tc]);
  useEffect(() => { load(); }, [load]);

  const retry = async () => {
    setAction("retry"); setNote(null); setStats(null); setError(null);
    try {
      const r = await retryFailedTranslations();
      setNote(t("translation.requeued", { count: r.requeued }));
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : tc("error"));
    } finally { setAction(null); }
  };
  const run = async () => {
    setAction("run"); setNote(null); setStats(null); setError(null);
    try {
      const r = await runTranslations();
      setStats(Object.entries(r).map(([k, v]) => [k, typeof v === "number" ? f.number(v) : String(v)]));
      setNote(t("translation.runDone"));
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : tc("error"));
    } finally { setAction(null); }
  };

  const pct = data && data.char_limit > 0 ? Math.min(100, (data.chars_used / data.char_limit) * 100) : 0;
  const barTone = pct >= 100 ? "bg-danger" : pct >= 80 ? "bg-warning" : "bg-primary";

  return (
    <SectionCard
      id="sys-translation"
      icon={Languages}
      title={t("translation.title")}
      hint={t("translation.hint")}
      actions={
        data && (
          <>
            <Button variant="secondary" size="sm" onClick={retry} loading={action === "retry"} disabled={action !== null}>
              {t("translation.retry")}
            </Button>
            <Button size="sm" onClick={run} loading={action === "run"} disabled={action !== null || !data.configured}>
              {t("translation.run")}
            </Button>
          </>
        )
      }
    >
      {error && <div className="mb-3"><ErrorBanner message={error} /></div>}
      {!data && !error && <Skeleton className="h-48 w-full" />}
      {note && <p role="status" className="mb-3 text-sm text-success">{note}</p>}
      {stats && stats.length > 0 && (
        <dl className="mb-4 grid grid-cols-2 gap-3 rounded-lg border border-border bg-surface-2 p-3 sm:grid-cols-4">
          {stats.map(([k, v]) => <Fact key={k} label={k}>{v}</Fact>)}
        </dl>
      )}
      {data && (
        <div className="space-y-5">
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone={data.configured ? "green" : "amber"}>{data.configured ? t("translation.configured") : t("translation.notConfigured")}</Badge>
            <Badge tone={data.enabled ? "green" : "slate"}>{data.enabled ? t("translation.enabled") : t("translation.disabled")}</Badge>
            {data.budget_exhausted && <Badge tone="red">{t("translation.budgetExhausted")}</Badge>}
            {data.key_rejected && <Badge tone="red">{t("translation.keyRejected")}</Badge>}
          </div>
          {!data.configured && (
            <div role="note" className="tone-amber rounded-lg border border-tone-border bg-tone-bg px-3 py-2 text-sm text-tone-fg">
              {t.rich("translation.notConfiguredHelp", { code: (c) => <code className="font-mono">{c}</code> })}
            </div>
          )}
          {data.budget_exhausted && (
            <p className="text-sm text-fg-muted">{t("translation.budgetExhaustedHelp")}</p>
          )}
          {data.key_rejected && (
            <p className="text-sm text-fg-muted">{t("translation.keyRejectedHelp")}</p>
          )}
          {data.paused_until && (
            <p className="text-sm text-warning">{t("translation.pausedUntil", { when: f.dateTime(data.paused_until) })}</p>
          )}

          <div>
            <div className="mb-1 flex flex-wrap items-baseline justify-between gap-2 text-sm">
              <span className="font-medium text-fg">{t("translation.usage")}</span>
              <span className="text-fg-muted">
                {t("translation.usageOf", { used: f.number(data.chars_used), limit: f.number(data.char_limit) })}
              </span>
            </div>
            <div
              role="progressbar"
              aria-label={t("translation.usage")}
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={Math.round(pct)}
              className="h-2 overflow-hidden rounded-full bg-surface-2"
            >
              <div className={`h-full ${barTone}`} style={{ width: `${pct}%` }} />
            </div>
            <p className="mt-1 text-xs text-fg-muted">
              {t("translation.remaining", { count: f.number(data.remaining) })} · {t("translation.month", { month: f.date(data.month, { short: true }) })}
            </p>
          </div>

          <dl className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            <Fact label={t("translation.requests")}>{f.number(data.requests)}</Fact>
            <Fact label={t("translation.cache")}>{f.number(data.cache_entries)}</Fact>
            <Fact label={t("translation.lastRun")}>{data.last_run ? f.ago(data.last_run) : "—"}</Fact>
            <Fact label={t("translation.provider")}>{data.provider}</Fact>
          </dl>

          {data.last_error && (
            <div role="status" className="tone-red rounded-lg border border-tone-border bg-tone-bg px-3 py-2 text-sm text-tone-fg">
              <span className="font-medium">{t("translation.lastError")}: </span>
              <span className="break-words">{data.last_error}</span>
            </div>
          )}

          <div>
            <div className="mb-2 text-sm font-medium text-fg">{t("translation.queue")}</div>
            <div className="overflow-x-auto rounded-lg border border-border">
              <table className="w-full text-sm">
                <caption className="sr-only">{t("translation.queue")}</caption>
                <thead className="bg-surface-2 text-left text-xs text-fg-muted">
                  <tr>
                    <th scope="col" className="px-3 py-2 font-medium">{t("translation.statusCol")}</th>
                    {LANGS.map((l) => <th key={l} scope="col" className="px-3 py-2 text-right font-medium uppercase">{l}</th>)}
                  </tr>
                </thead>
                <tbody>
                  {STATUSES.map((s) => (
                    <tr key={s} className="border-t border-border">
                      <th scope="row" className="px-3 py-2 text-left font-medium text-fg">{t(`translation.status.${s}`)}</th>
                      {LANGS.map((l) => (
                        <td key={l} className="px-3 py-2 text-right tabular-nums text-fg">{f.number(data.counts[s]?.[l] ?? 0)}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {!data.configured && <p className="mt-2 text-xs text-fg-muted">{t("translation.pendingNote")}</p>}
          </div>

          <div>
            <div className="mb-2 text-sm font-medium text-fg">{t("translation.failedTitle")}</div>
            {data.failed.length === 0 ? (
              <p className="text-sm text-fg-muted">{t("translation.noFailed")}</p>
            ) : (
              <div className="overflow-x-auto rounded-lg border border-border">
                <table className="w-full text-sm">
                  <thead className="bg-surface-2 text-left text-xs text-fg-muted">
                    <tr>
                      <th scope="col" className="px-3 py-2 font-medium">{t("translation.eventId")}</th>
                      <th scope="col" className="px-3 py-2 font-medium">{t("translation.lang")}</th>
                      <th scope="col" className="px-3 py-2 font-medium">{t("translation.attempts")}</th>
                      <th scope="col" className="px-3 py-2 font-medium">{t("translation.error")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.failed.map((x) => (
                      <tr key={`${x.event_id}-${x.lang}`} className="border-t border-border align-top">
                        <td className="px-3 py-2 tabular-nums">#{x.event_id}</td>
                        <td className="px-3 py-2 uppercase">{x.lang}</td>
                        <td className="px-3 py-2 tabular-nums">{f.number(x.attempts)}</td>
                        <td className="min-w-[12rem] break-words px-3 py-2 text-fg-muted">{x.error ?? "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}
    </SectionCard>
  );
}
