"use client";

import { ExternalLink } from "lucide-react";
import { useTranslations } from "next-intl";
import { Badge, useFormat } from "@/components/ui";
import SourceStatusBadge from "@/components/admin/SourceStatusBadge";
import type { SourceRunNow, SourceTest } from "@/lib/adminApi";
import { KNOWN_OUTCOMES, humanInterval, msText, outcomeTone } from "./lib";

export function OutcomeBadge({ outcome, ok }: { outcome: string; ok?: boolean }) {
  const t = useTranslations("adminSources");
  return (
    <Badge tone={outcomeTone(outcome, !!ok)}>
      {KNOWN_OUTCOMES.includes(outcome) ? t(`outcomes.${outcome}`) : outcome}
    </Badge>
  );
}

function Stat({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="min-w-0 rounded-lg border border-border bg-surface-2 px-3 py-2">
      <dt className="text-xs text-fg-muted">{label}</dt>
      <dd className="mt-0.5 break-words text-sm font-medium tabular-nums text-fg">{children}</dd>
    </div>
  );
}

/** "Sinash" natijasi (quruq yurgizish). */
export function TestResultView({ r }: { r: SourceTest }) {
  const t = useTranslations("adminSources");
  const f = useFormat();
  return (
    <div className="space-y-3" role="status">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-sm font-medium text-fg">{r.ok ? t("test.okHeadline") : t("test.failHeadline")}</span>
        <OutcomeBadge outcome={r.outcome} ok={r.ok} />
      </div>
      <p className="text-xs text-fg-muted">{t("test.dryRun")}</p>
      <dl className="grid grid-cols-2 gap-2">
        <Stat label={t("test.http")}>{r.http_status ?? "—"}</Stat>
        <Stat label={t("test.latency")}>{msText(r.latency_ms, f, t)}</Stat>
        <Stat label={t("test.parsed")}>{f.number(r.items)}</Stat>
        <Stat label={t("test.passed")}>{f.number(r.passed)}</Stat>
        {r.retry_after_seconds != null && (
          <Stat label={t("runs.retryAfter")}>{humanInterval(r.retry_after_seconds, t)}</Stat>
        )}
      </dl>
      {r.error && (
        <div className="rounded-lg border border-border bg-surface-2 px-3 py-2 text-sm">
          <div className="text-xs font-medium text-danger">{t("test.error")}</div>
          <div className="mt-0.5 whitespace-pre-wrap break-words text-fg">{r.error}</div>
        </div>
      )}
      {r.note && <p className="break-words text-sm text-fg-muted">{r.note}</p>}
      <div>
        <div className="mb-1.5 text-sm font-medium text-fg">{t("test.samples")}</div>
        {r.samples.length === 0 ? (
          <p className="text-sm text-fg-muted">{t("test.noSamples")}</p>
        ) : (
          <ul className="space-y-1.5">
            {r.samples.slice(0, 3).map((s, i) => (
              <li key={i} className="min-w-0 text-sm">
                <a
                  href={s.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="focus-ring inline-flex max-w-full items-start gap-1 rounded text-primary hover:underline"
                >
                  <span className="min-w-0 break-words">{s.title}</span>
                  <ExternalLink className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden />
                </a>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

/** "Hozir ishga tushirish" natijasi. */
export function RunResultView({ r }: { r: SourceRunNow }) {
  const t = useTranslations("adminSources");
  const f = useFormat();
  return (
    <div className="space-y-3" role="status">
      <div className="flex flex-wrap items-center gap-2">
        <OutcomeBadge outcome={r.outcome} ok={r.ok} />
        <SourceStatusBadge status={r.status} />
      </div>
      <dl className="grid grid-cols-2 gap-2">
        <Stat label={t("test.http")}>{r.http_status ?? "—"}</Stat>
        <Stat label={t("run.duration")}>{msText(r.duration_ms, f, t)}</Stat>
        <Stat label={t("run.items")}>{f.number(r.items)}</Stat>
        <Stat label={t("run.passed")}>{f.number(r.passed)}</Stat>
        <Stat label={t("run.newItems")}>{f.number(r.new)}</Stat>
        <Stat label={t("run.merged")}>{f.number(r.merged)}</Stat>
        <Stat label={t("run.nextRun")}>{r.next_run_at ? f.ago(r.next_run_at) : "—"}</Stat>
        {r.retry_after_seconds != null && (
          <Stat label={t("runs.retryAfter")}>{humanInterval(r.retry_after_seconds, t)}</Stat>
        )}
        {!r.ok && r.wait_seconds != null && <Stat label={t("runs.wait")}>{humanInterval(r.wait_seconds, t)}</Stat>}
      </dl>
      {r.error && (
        <div className="rounded-lg border border-border bg-surface-2 px-3 py-2 text-sm">
          <div className="text-xs font-medium text-danger">{t("test.error")}</div>
          <div className="mt-0.5 whitespace-pre-wrap break-words text-fg">{r.error}</div>
        </div>
      )}
    </div>
  );
}
