"use client";

import { useLocale, useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";
import { Badge, Button, ErrorBanner, Skeleton, useFormat } from "@/components/ui";
import { reclassify, type CategoryAdmin, type ReclassifyResult } from "@/lib/adminApi";
import { categoryText, invalidateCategories } from "@/lib/useCategories";
import Drawer from "./Drawer";

function Stat({ label, value, help }: { label: string; value: number; help?: string }) {
  const f = useFormat();
  return (
    <div className="rounded-lg border border-border bg-surface-2 p-3" title={help}>
      <div className="text-2xl font-semibold tabular-nums text-fg">{f.number(value)}</div>
      <div className="text-xs text-fg-muted">{label}</div>
    </div>
  );
}

export default function ReclassifyDrawer({
  categories,
  onClose,
  onApplied,
}: {
  categories: CategoryAdmin[];
  onClose: () => void;
  onApplied: () => void;
}) {
  const t = useTranslations("adminCategories");
  const locale = useLocale();
  const f = useFormat();
  const [preview, setPreview] = useState<ReclassifyResult | null>(null);
  const [applied, setApplied] = useState<ReclassifyResult | null>(null);
  const [busy, setBusy] = useState<"preview" | "apply" | null>("preview");
  const [error, setError] = useState<string | null>(null);

  const nameOf = useCallback(
    (slug: string) => {
      const c = categories.find((x) => x.slug === slug);
      return c ? categoryText(c, "name", locale) : slug;
    },
    [categories, locale],
  );

  const run = useCallback(async () => {
    setBusy("preview");
    setError(null);
    setApplied(null);
    try {
      setPreview(await reclassify(true));
    } catch (e) {
      setError(e instanceof Error ? e.message : t("reclass.failed"));
    } finally {
      setBusy(null);
    }
  }, [t]);

  useEffect(() => {
    void run();
  }, [run]);

  const apply = async () => {
    setBusy("apply");
    setError(null);
    try {
      const r = await reclassify(false);
      invalidateCategories();
      setApplied(r);
      setPreview(null);
      onApplied();
    } catch (e) {
      setError(e instanceof Error ? e.message : t("reclass.failed"));
    } finally {
      setBusy(null);
    }
  };

  const shown = applied ?? preview;
  const transitions = shown ? Object.entries(shown.transitions) : [];
  const nothing = shown ? shown.changed === 0 && shown.severity_changed === 0 : false;

  return (
    <Drawer title={t("reclass.title")} closeLabel={t("form.close")} onClose={onClose} wide>
      <div className="min-h-0 flex-1 space-y-5 overflow-y-auto px-4 py-5 sm:px-6">
        <p className="text-sm text-fg-muted">{t("reclass.intro")}</p>
        {error && <ErrorBanner message={error} />}
        {busy === "preview" && (
          <div role="status" aria-label={t("reclass.running")} className="space-y-3">
            <Skeleton className="h-16 w-full" />
            <Skeleton className="h-32 w-full" />
          </div>
        )}
        {applied && (
          <div role="status" className="rounded-lg border border-tone-border bg-tone-bg p-3 text-sm text-tone-fg tone-green">
            <div className="font-medium">{t("reclass.appliedTitle")}</div>
            <div>{t("reclass.appliedBody", { changed: f.number(applied.changed), severity: f.number(applied.severity_changed) })}</div>
          </div>
        )}
        {shown && busy !== "preview" && (
          <>
            {!applied && <Badge tone="amber">{t("reclass.dryRunLabel")}</Badge>}
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <Stat label={t("reclass.considered")} value={shown.considered} />
              <Stat label={t("reclass.changed")} value={shown.changed} />
              <Stat label={t("reclass.severityChanged")} value={shown.severity_changed} />
              <Stat label={t("reclass.locked")} value={shown.locked_skipped} help={t("reclass.lockedHelp")} />
            </div>
            <p className="-mt-2 text-xs text-fg-muted">{t("reclass.lockedHelp")}</p>
            {nothing && !applied && <p className="text-sm text-fg">{t("reclass.noChanges")}</p>}
            {transitions.length > 0 && (
              <section>
                <h3 className="mb-2 text-sm font-semibold text-fg">{t("reclass.transitions")}</h3>
                <div className="overflow-x-auto rounded-lg border border-border">
                  <table className="w-full text-sm">
                    <thead className="bg-surface-2 text-left text-xs text-fg-muted">
                      <tr>
                        <th scope="col" className="px-3 py-2 font-medium">{t("reclass.from")}</th>
                        <th scope="col" className="px-3 py-2 font-medium">{t("reclass.to")}</th>
                        <th scope="col" className="px-3 py-2 text-right font-medium">{t("reclass.count")}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {transitions.map(([key, n]) => {
                        const [from, to] = key.split("→");
                        return (
                          <tr key={key} className="border-t border-border">
                            <td className="px-3 py-2 text-fg">{nameOf(from)}</td>
                            <td className="px-3 py-2 text-fg">{nameOf(to)}</td>
                            <td className="px-3 py-2 text-right tabular-nums text-fg">{f.number(n)}</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </section>
            )}
            {shown.samples.length > 0 && (
              <section>
                <h3 className="mb-2 text-sm font-semibold text-fg">{t("reclass.samples")}</h3>
                <ul className="divide-y divide-border rounded-lg border border-border">
                  {shown.samples.map((s) => (
                    <li key={s.id} className="px-3 py-2 text-sm">
                      <div className="break-words text-fg">{s.title}</div>
                      <div className="mt-0.5 text-xs text-fg-muted">{nameOf(s.from)} → {nameOf(s.to)}</div>
                    </li>
                  ))}
                </ul>
              </section>
            )}
          </>
        )}
      </div>
      <div className="flex flex-wrap items-center justify-end gap-2 border-t border-border px-4 py-3 sm:px-6">
        {preview && !applied && !nothing && (
          <p className="mr-auto w-full text-xs text-fg-muted sm:w-auto sm:max-w-[60%]">{t("reclass.applyHelp")}</p>
        )}
        <Button variant="secondary" onClick={onClose}>{t("reclass.close")}</Button>
        {(applied || (preview && nothing)) && (
          <Button variant="secondary" onClick={run} loading={busy === "preview"}>{t("reclass.rerun")}</Button>
        )}
        {preview && !applied && !nothing && (
          <Button onClick={apply} loading={busy === "apply"}>
            {busy === "apply" ? t("reclass.applying") : t("reclass.apply")}
          </Button>
        )}
      </div>
    </Drawer>
  );
}
