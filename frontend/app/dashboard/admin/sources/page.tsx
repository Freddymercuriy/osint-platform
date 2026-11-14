"use client";

import {
  Database, Download, FlaskConical, History, KeyRound, Pencil, Play, Plus, Power, PowerOff, Search, Trash2, Upload,
} from "lucide-react";
import { useTranslations } from "next-intl";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import SourceStatusBadge, { SOURCE_STATUS_TONE } from "@/components/admin/SourceStatusBadge";
import Overlay from "@/components/admin/sources/Overlay";
import { RunResultView, TestResultView } from "@/components/admin/sources/Results";
import RunsPanel from "@/components/admin/sources/RunsPanel";
import SourceForm from "@/components/admin/sources/SourceForm";
import { humanInterval, msText } from "@/components/admin/sources/lib";
import { Button, CategoryBadge, Card, EmptyState, ErrorBanner, Input, Select, Skeleton, Label, useFormat } from "@/components/ui";
import {
  SOURCE_STATUSES, deleteSource, disableSource, enableSource, exportSources, getSource, importSources, listConnectors,
  listSources, runSource, testSource,
  type ConnectorInfo, type Source, type SourceInput, type SourceRunNow, type SourceTest,
} from "@/lib/adminApi";
import { cn } from "@/lib/cn";
import { toneClass } from "@/components/ui";

type Result =
  | { type: "test"; source: Source; res?: SourceTest; err?: string }
  | { type: "run"; source: Source; res?: SourceRunNow; err?: string };

type Confirm = { type: "delete" | "disable"; source: Source; busy?: boolean; err?: string };

function validateImport(data: unknown): { ok: true; sources: SourceInput[] } | { ok: false; key: string; n?: number } {
  const list = Array.isArray(data) ? data : (data as { sources?: unknown } | null)?.sources;
  if (!Array.isArray(list)) return { ok: false, key: "importBadShape" };
  if (list.length === 0) return { ok: false, key: "importEmpty" };
  for (let i = 0; i < list.length; i++) {
    const s = list[i] as Record<string, unknown> | null;
    if (
      !s || typeof s !== "object" || typeof s.name !== "string" || !s.name.trim() || typeof s.kind !== "string" || !s.kind ||
      !s.config || typeof s.config !== "object" || Array.isArray(s.config)
    )
      return { ok: false, key: "importBadItem", n: i + 1 };
  }
  return { ok: true, sources: list as SourceInput[] };
}

function SourcesView() {
  const t = useTranslations("adminSources");
  const tc = useTranslations("common");
  const ta = useTranslations("admin");
  const f = useFormat();
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();

  const [sources, setSources] = useState<Source[] | null>(null);
  const [connectors, setConnectors] = useState<ConnectorInfo[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<{ tone: "ok" | "err"; text: string } | null>(null);
  const [form, setForm] = useState<{ source: Source | null } | null>(null);
  const [runsFor, setRunsFor] = useState<Source | null>(null);
  const [result, setResult] = useState<Result | null>(null);
  const [confirm, setConfirm] = useState<Confirm | null>(null);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [exporting, setExporting] = useState(false);
  const [importing, setImporting] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  const status = params.get("status") ?? "";
  const kind = params.get("kind") ?? "";
  const enabled = params.get("enabled") ?? "";
  const q = params.get("q") ?? "";

  const setParam = useCallback(
    (patch: Record<string, string>) => {
      const p = new URLSearchParams(params.toString());
      for (const [k, v] of Object.entries(patch)) {
        if (v) p.set(k, v);
        else p.delete(k);
      }
      const s = p.toString();
      router.replace(s ? `${pathname}?${s}` : pathname, { scroll: false });
    },
    [params, pathname, router],
  );

  const load = useCallback(async () => {
    setError(null);
    try {
      const [s, c] = await Promise.all([listSources(), listConnectors()]);
      setSources(s);
      setConnectors(c);
    } catch (e) {
      setError((e as Error).message || t("loadError"));
    }
  }, [t]);
  useEffect(() => {
    load();
  }, [load]);

  const replaceRow = (s: Source) => setSources((cur) => (cur ? cur.map((x) => (x.id === s.id ? s : x)) : cur));
  const refreshRow = async (id: number) => {
    try {
      replaceRow(await getSource(id));
    } catch {
      /* satr eskirgan holda qoladi */
    }
  };

  const counts = useMemo(() => {
    const c: Record<string, number> = {};
    for (const s of sources ?? []) c[s.status] = (c[s.status] ?? 0) + 1;
    return c;
  }, [sources]);

  const filtered = useMemo(() => {
    const needle = q.trim().toLowerCase();
    return (sources ?? []).filter(
      (s) =>
        (!status || s.status === status) &&
        (!kind || s.kind === kind) &&
        (!enabled || (enabled === "on" ? s.enabled : !s.enabled)) &&
        (!needle || s.name.toLowerCase().includes(needle)),
    );
  }, [sources, status, kind, enabled, q]);

  const kindTitle = (k: string) => connectors.find((c) => c.kind === k)?.title ?? k;
  const hasFilter = !!(status || kind || enabled || q);

  /* ---- amallar ---- */
  const doTest = async (s: Source) => {
    setResult({ type: "test", source: s });
    try {
      setResult({ type: "test", source: s, res: await testSource(s.id) });
    } catch (e) {
      setResult({ type: "test", source: s, err: (e as Error).message });
    }
  };
  const doRun = async (s: Source) => {
    setResult({ type: "run", source: s });
    try {
      const res = await runSource(s.id);
      setResult({ type: "run", source: s, res });
      refreshRow(s.id);
    } catch (e) {
      setResult({ type: "run", source: s, err: (e as Error).message });
    }
  };
  const doEnable = async (s: Source) => {
    setBusyId(s.id);
    try {
      replaceRow(await enableSource(s.id));
    } catch (e) {
      setNotice({ tone: "err", text: (e as Error).message });
    } finally {
      setBusyId(null);
    }
  };
  const doConfirm = async () => {
    if (!confirm) return;
    const { type, source } = confirm;
    setConfirm({ ...confirm, busy: true, err: undefined });
    try {
      if (type === "delete") {
        await deleteSource(source.id);
        setSources((cur) => (cur ? cur.filter((x) => x.id !== source.id) : cur));
        setNotice({ tone: "ok", text: t("deletedNotice", { name: source.name }) });
      } else {
        replaceRow(await disableSource(source.id));
      }
      setConfirm(null);
    } catch (e) {
      setConfirm({ type, source, err: (e as Error).message });
    }
  };

  const doExport = async () => {
    setExporting(true);
    setNotice(null);
    try {
      const data = await exportSources();
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `sources-${new Date().toISOString().slice(0, 10)}.json`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (e) {
      setNotice({ tone: "err", text: (e as Error).message });
    } finally {
      setExporting(false);
    }
  };

  const onFile = async (file: File | undefined) => {
    if (!file) return;
    setNotice(null);
    let data: unknown;
    try {
      data = JSON.parse(await file.text());
    } catch {
      setNotice({ tone: "err", text: t("importBadJson") });
      return;
    }
    const v = validateImport(data);
    if (!v.ok) {
      setNotice({ tone: "err", text: t(v.key, { n: v.n ?? 0 }) });
      return;
    }
    setImporting(true);
    try {
      const r = await importSources(v.sources);
      setNotice({ tone: "ok", text: t("importDone", { created: r.created, updated: r.updated }) });
      load();
    } catch (e) {
      setNotice({ tone: "err", text: (e as Error).message });
    } finally {
      setImporting(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  const iconBtn =
    "focus-ring grid h-8 w-8 place-items-center rounded-lg text-fg-muted transition-colors hover:bg-surface-2 hover:text-fg disabled:opacity-50";

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <p className="max-w-2xl text-sm text-fg-muted">{t("intro")}</p>
        <div className="flex flex-wrap items-center gap-2">
          <Button variant="secondary" size="sm" icon={Download} loading={exporting} onClick={doExport}>{t("export")}</Button>
          <Button variant="secondary" size="sm" icon={Upload} loading={importing} onClick={() => fileRef.current?.click()}>
            {t("import")}
          </Button>
          <input
            ref={fileRef}
            type="file"
            accept="application/json,.json"
            className="hidden"
            tabIndex={-1}
            aria-label={t("import")}
            onChange={(e) => onFile(e.target.files?.[0])}
          />
          <Button icon={Plus} onClick={() => setForm({ source: null })}>{t("add")}</Button>
        </div>
      </div>

      {notice && (
        <div role={notice.tone === "err" ? "alert" : "status"}>
          {notice.tone === "err" ? (
            <ErrorBanner message={notice.text} />
          ) : (
            <div className={cn("rounded-lg border px-4 py-3 text-sm", toneClass("green"))}>{notice.text}</div>
          )}
        </div>
      )}

      {error ? (
        <ErrorBanner
          message={error}
          action={<Button size="sm" variant="secondary" onClick={load}>{tc("retry")}</Button>}
        />
      ) : sources === null ? (
        <div className="space-y-3">
          <Skeleton className="h-16 w-full" />
          <Skeleton className="h-12 w-full" />
          <Skeleton className="h-64 w-full" />
        </div>
      ) : (
        <>
          {/* holat bo'yicha xulosa */}
          <div role="group" aria-label={t("summaryLabel")} className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => setParam({ status: "" })}
              aria-pressed={!status}
              className={cn(
                "focus-ring inline-flex items-center gap-2 rounded-lg border px-3 py-1.5 text-sm transition-colors",
                !status ? "border-primary bg-primary-soft text-primary" : "border-border bg-surface text-fg hover:bg-surface-2",
              )}
            >
              {t("summaryAll")}
              <span className="font-semibold tabular-nums">{f.number(sources.length)}</span>
            </button>
            {SOURCE_STATUSES.map((st) => (
              <button
                key={st}
                type="button"
                onClick={() => setParam({ status: status === st ? "" : st })}
                aria-pressed={status === st}
                title={t("summaryFilter", { status: ta(`status.${st}`) })}
                className={cn(
                  "focus-ring inline-flex items-center gap-2 rounded-lg border px-3 py-1.5 text-sm transition-colors",
                  status === st ? "border-primary ring-1 ring-primary" : "hover:brightness-95",
                  toneClass(SOURCE_STATUS_TONE[st]),
                  (counts[st] ?? 0) === 0 && status !== st && "opacity-70",
                )}
              >
                {ta(`status.${st}`)}
                <span className="font-semibold tabular-nums">{f.number(counts[st] ?? 0)}</span>
              </button>
            ))}
          </div>

          {/* filtrlar */}
          <Card className="grid gap-3 p-3 sm:grid-cols-2 lg:grid-cols-4">
            <div>
              <Label htmlFor="flt-q">{t("filters.search")}</Label>
              <Input
                id="flt-q"
                icon={Search}
                type="search"
                value={q}
                onChange={(e) => setParam({ q: e.target.value })}
                placeholder={t("filters.searchPlaceholder")}
              />
            </div>
            <div>
              <Label htmlFor="flt-status">{t("filters.status")}</Label>
              <Select id="flt-status" value={status} onChange={(e) => setParam({ status: e.target.value })}>
                <option value="">{t("filters.allStatuses")}</option>
                {SOURCE_STATUSES.map((s) => <option key={s} value={s}>{ta(`status.${s}`)}</option>)}
              </Select>
            </div>
            <div>
              <Label htmlFor="flt-kind">{t("filters.kind")}</Label>
              <Select id="flt-kind" value={kind} onChange={(e) => setParam({ kind: e.target.value })}>
                <option value="">{t("filters.allKinds")}</option>
                {connectors.map((c) => <option key={c.kind} value={c.kind}>{c.title}</option>)}
              </Select>
            </div>
            <div>
              <Label htmlFor="flt-en">{t("filters.enabled")}</Label>
              <Select id="flt-en" value={enabled} onChange={(e) => setParam({ enabled: e.target.value })}>
                <option value="">{t("filters.enabledAll")}</option>
                <option value="on">{t("filters.enabledOn")}</option>
                <option value="off">{t("filters.enabledOff")}</option>
              </Select>
            </div>
          </Card>

          <div className="flex items-center justify-between gap-2 text-sm text-fg-muted">
            <span aria-live="polite">{t("count", { shown: f.number(filtered.length), total: f.number(sources.length) })}</span>
            {hasFilter && (
              <Button variant="ghost" size="sm" onClick={() => router.replace(pathname, { scroll: false })}>
                {t("filters.reset")}
              </Button>
            )}
          </div>

          {sources.length === 0 ? (
            <Card>
              <EmptyState
                icon={Database}
                title={t("emptyTitle")}
                description={t("emptyText")}
                action={<Button icon={Plus} onClick={() => setForm({ source: null })}>{t("add")}</Button>}
              />
            </Card>
          ) : filtered.length === 0 ? (
            <Card>
              <EmptyState
                icon={Search}
                title={t("emptyFilterTitle")}
                description={t("emptyFilterText")}
                action={<Button variant="secondary" onClick={() => router.replace(pathname, { scroll: false })}>{t("filters.reset")}</Button>}
              />
            </Card>
          ) : (
            <Card className="overflow-hidden">
              <div className="overflow-x-auto">
                <table className="w-full min-w-[1100px] text-left text-sm">
                  <thead className="border-b border-border bg-surface-2 text-xs text-fg-muted">
                    <tr>
                      {["name", "category", "lang", "interval", "status", "lastSuccess", "latency", "items24h", "uptime", "nextRun", "actions"].map((c) => (
                        <th key={c} scope="col" className={cn("px-3 py-2 font-medium", c === "actions" && "text-right")}>
                          {t(`cols.${c}`)}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {filtered.map((s) => {
                      const busy = busyId === s.id;
                      const label = (k: string) => `${t(`actions.${k}`)}: ${s.name}`;
                      return (
                        <tr key={s.id} className={cn("align-top", !s.enabled && "bg-surface-2/50")}>
                          <td className="max-w-[18rem] px-3 py-2.5">
                            <div className="break-words font-medium text-fg">{s.name}</div>
                            <div className="text-xs text-fg-muted">{kindTitle(s.kind)}</div>
                            {s.key_configured === false && (
                              <div className="mt-1 inline-flex items-start gap-1 text-xs text-warning">
                                <KeyRound className="mt-0.5 h-3 w-3 shrink-0" aria-hidden />
                                {s.api_key_env ? t("keyMissing", { env: s.api_key_env }) : t("keyMissingGeneric")}
                              </div>
                            )}
                          </td>
                          <td className="px-3 py-2.5">
                            {s.category ? (
                              <CategoryBadge category={s.category} />
                            ) : (
                              <span className="text-fg-muted" title={t("classifierHelp")}>{t("classifier")}</span>
                            )}
                          </td>
                          <td className="px-3 py-2.5 uppercase text-fg-muted">{s.lang}</td>
                          <td className="whitespace-nowrap px-3 py-2.5 tabular-nums">{humanInterval(s.interval_seconds, t)}</td>
                          <td className="px-3 py-2.5"><SourceStatusBadge status={s.status} /></td>
                          <td className="whitespace-nowrap px-3 py-2.5 text-fg-muted" title={s.last_success_at ? f.dateTime(s.last_success_at) : undefined}>
                            {s.last_success_at ? f.ago(s.last_success_at) : t("never")}
                          </td>
                          <td className="whitespace-nowrap px-3 py-2.5 tabular-nums">
                            {s.last_latency_ms == null ? "—" : msText(s.last_latency_ms, f, t)}
                          </td>
                          <td className="px-3 py-2.5 tabular-nums">{f.number(s.items_24h)}</td>
                          <td className="px-3 py-2.5 tabular-nums">{s.uptime_7d == null ? "—" : f.percent(s.uptime_7d)}</td>
                          <td className="whitespace-nowrap px-3 py-2.5 text-fg-muted" title={s.next_run_at ? f.dateTime(s.next_run_at) : undefined}>
                            {s.enabled && s.next_run_at ? f.ago(s.next_run_at) : "—"}
                          </td>
                          <td className="px-3 py-2">
                            <div className="flex items-center justify-end gap-0.5">
                              <button type="button" className={iconBtn} aria-label={label("test")} title={t("actions.test")} onClick={() => doTest(s)}>
                                <FlaskConical className="h-4 w-4" aria-hidden />
                              </button>
                              <button type="button" className={iconBtn} aria-label={label("run")} title={t("actions.run")} onClick={() => doRun(s)}>
                                <Play className="h-4 w-4" aria-hidden />
                              </button>
                              {s.enabled ? (
                                <button type="button" className={iconBtn} disabled={busy} aria-label={label("disable")} title={t("actions.disable")}
                                  onClick={() => setConfirm({ type: "disable", source: s })}>
                                  <PowerOff className="h-4 w-4" aria-hidden />
                                </button>
                              ) : (
                                <button type="button" className={iconBtn} disabled={busy} aria-label={label("enable")} title={t("actions.enable")}
                                  onClick={() => doEnable(s)}>
                                  <Power className="h-4 w-4" aria-hidden />
                                </button>
                              )}
                              <button type="button" className={iconBtn} aria-label={label("edit")} title={t("actions.edit")} onClick={() => setForm({ source: s })}>
                                <Pencil className="h-4 w-4" aria-hidden />
                              </button>
                              <button type="button" className={iconBtn} aria-label={label("history")} title={t("actions.history")} onClick={() => setRunsFor(s)}>
                                <History className="h-4 w-4" aria-hidden />
                              </button>
                              <button type="button" className={cn(iconBtn, "hover:text-danger")} aria-label={label("delete")} title={t("actions.delete")}
                                onClick={() => setConfirm({ type: "delete", source: s })}>
                                <Trash2 className="h-4 w-4" aria-hidden />
                              </button>
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </Card>
          )}
        </>
      )}

      {form && (
        <SourceForm
          source={form.source}
          connectors={connectors}
          onClose={() => setForm(null)}
          onSaved={(s, created) => {
            setForm(null);
            setNotice({ tone: "ok", text: t(created ? "createdNotice" : "savedNotice", { name: s.name }) });
            if (created) setSources((cur) => (cur ? [...cur, s] : cur));
            else replaceRow(s);
          }}
        />
      )}

      {runsFor && <RunsPanel source={runsFor} onClose={() => setRunsFor(null)} />}

      {result && (
        <Overlay
          title={`${result.type === "test" ? t("test.title") : t("run.title")}: ${result.source.name}`}
          onClose={() => setResult(null)}
          footer={<Button variant="secondary" onClick={() => setResult(null)}>{tc("close")}</Button>}
        >
          {result.err ? (
            <ErrorBanner message={result.err} />
          ) : !result.res ? (
            <p className="text-sm text-fg-muted" role="status">{result.type === "test" ? t("test.running") : t("run.running")}</p>
          ) : result.type === "test" ? (
            <TestResultView r={result.res as SourceTest} />
          ) : (
            <RunResultView r={result.res as SourceRunNow} />
          )}
        </Overlay>
      )}

      {confirm && (
        <Overlay
          title={t(`${confirm.type}.title`, { name: confirm.source.name })}
          onClose={() => !confirm.busy && setConfirm(null)}
          footer={
            <>
              <Button variant="ghost" data-autofocus onClick={() => setConfirm(null)} disabled={confirm.busy}>{tc("cancel")}</Button>
              <Button variant="danger" loading={confirm.busy} onClick={doConfirm}>{t(`${confirm.type}.confirm`)}</Button>
            </>
          }
        >
          <p className="text-sm text-fg-muted">{t(`${confirm.type}.body`)}</p>
          {confirm.err && <div className="mt-3"><ErrorBanner message={confirm.err} /></div>}
        </Overlay>
      )}
    </div>
  );
}

export default function Page() {
  return (
    <Suspense fallback={<Skeleton className="h-64 w-full" />}>
      <SourcesView />
    </Suspense>
  );
}
