"use client";

import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import { EmptyState, ErrorBanner, Skeleton, useFormat } from "@/components/ui";
import { History } from "lucide-react";
import { sourceRuns, type Source, type SourceRun } from "@/lib/adminApi";
import Overlay from "./Overlay";
import { OutcomeBadge } from "./Results";
import { msText } from "./lib";

export default function RunsPanel({ source, onClose }: { source: Source; onClose: () => void }) {
  const t = useTranslations("adminSources");
  const f = useFormat();
  const [runs, setRuns] = useState<SourceRun[] | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    sourceRuns(source.id).then(setRuns).catch((e) => setErr((e as Error).message));
  }, [source.id]);

  return (
    <Overlay side title={`${t("runs.title")}: ${source.name}`} onClose={onClose}>
      {err ? (
        <ErrorBanner message={err} />
      ) : runs === null ? (
        <div className="space-y-2" aria-label={t("runs.loading")}>
          {[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-16 w-full" />)}
        </div>
      ) : runs.length === 0 ? (
        <EmptyState icon={History} title={t("runs.title")} description={t("runs.empty")} />
      ) : (
        <ul className="space-y-2">
          {runs.map((r) => (
            <li key={r.id} className="rounded-lg border border-border p-3 text-sm">
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-medium text-fg">{f.dateTime(r.started_at)}</span>
                <OutcomeBadge outcome={r.outcome} ok={r.ok} />
                <span className="text-xs text-fg-muted">{r.manual ? t("runs.manual") : t("runs.scheduled")}</span>
              </div>
              <dl className="mt-2 grid grid-cols-2 gap-x-3 gap-y-1 text-xs sm:grid-cols-4">
                {[
                  [t("runs.http"), r.http_status ?? "—"],
                  [t("runs.duration"), r.duration_ms == null ? "—" : msText(r.duration_ms, f, t)],
                  [t("runs.items"), f.number(r.items)],
                  [t("runs.newItems"), f.number(r.new_items)],
                ].map(([k, v]) => (
                  <div key={String(k)}>
                    <dt className="text-fg-muted">{k}</dt>
                    <dd className="font-medium tabular-nums text-fg">{v}</dd>
                  </div>
                ))}
              </dl>
              {r.error && (
                <p className="mt-2 whitespace-pre-wrap break-words rounded bg-surface-2 px-2 py-1.5 text-xs text-fg">
                  <span className="font-medium text-danger">{t("runs.error")}: </span>
                  {r.error}
                </p>
              )}
            </li>
          ))}
        </ul>
      )}
    </Overlay>
  );
}
