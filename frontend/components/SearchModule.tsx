"use client";

import {
  ArrowRight,
  Check,
  CheckCircle2,
  CircleHelp,
  Clock,
  Copy,
  ExternalLink,
  History,
  Layers,
  Radar,
  RotateCcw,
  Search,
  ShieldCheck,
  Sparkles,
  XCircle,
  type LucideIcon,
} from "lucide-react";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Badge,
  Button,
  Card,
  EmptyState,
  ErrorBanner,
  IconBox,
  Input,
  PageHeader,
  Skeleton,
  StatTile,
  StatusBadge,
  useFormat,
} from "@/components/ui";
import { getHistory, type CollectResult, type SearchJob, type SearchResponse } from "@/lib/api";
import type { Tone } from "@/lib/categories";
import ExportButtons from "@/components/ExportButtons";
import { cn } from "@/lib/cn";

export type SearchKind = "username" | "email" | "phone" | "domain";

type Filter = "all" | "found" | "not_found" | "error";

const ORDER: Record<string, number> = { found: 0, error: 1, not_found: 2 };

const FILTERS: { id: Filter; labelKey: string; icon: LucideIcon }[] = [
  { id: "all", labelKey: "all", icon: Layers },
  { id: "found", labelKey: "status_found", icon: CheckCircle2 },
  { id: "not_found", labelKey: "status_not_found", icon: XCircle },
  { id: "error", labelKey: "status_unclear", icon: CircleHelp },
];

function normStatus(s: string): Exclude<Filter, "all"> {
  return s === "found" || s === "not_found" ? s : "error";
}

/* ------------------------------------------------------------------ CopyButton */
function CopyButton({ text }: { text: string }) {
  const t = useTranslations("common");
  const [copied, setCopied] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => () => {
    if (timer.current) clearTimeout(timer.current);
  }, []);

  async function copy() {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      if (timer.current) clearTimeout(timer.current);
      timer.current = setTimeout(() => setCopied(false), 1500);
    } catch {
      /* clipboard mavjud emas */
    }
  }

  return (
    <button
      type="button"
      onClick={copy}
      title={copied ? t("copied") : t("copy")}
      aria-label={t("copy")}
      className={cn(
        "focus-ring grid h-8 w-8 shrink-0 place-items-center rounded-lg border transition-colors",
        copied
          ? "tone-green border-tone-border bg-tone-bg text-tone-fg"
          : "border-border bg-surface text-fg-muted hover:bg-surface-2 hover:text-fg",
      )}
    >
      {copied ? <Check className="h-3.5 w-3.5" aria-hidden /> : <Copy className="h-3.5 w-3.5" aria-hidden />}
    </button>
  );
}

/* ------------------------------------------------------------------ ResultCard */
function ResultCard({ r }: { r: CollectResult }) {
  const t = useTranslations("common");
  const status = normStatus(r.status);
  const found = status === "found";
  const copyText = r.url || r.value;
  const letter = (r.source.trim()[0] || "?").toUpperCase();
  // Uzun izoh (masalan WHOIS) 3 qatorga qisqartiriladi — bosilsa to'liq ochiladi
  const [expanded, setExpanded] = useState(false);
  const longDetail = (r.detail?.length ?? 0) > 90;

  return (
    <Card
      hover
      className={cn(
        "flex h-full animate-fade-in flex-col gap-3 p-4",
        found && "border-success/40",
        status === "not_found" && "bg-surface-2/50",
      )}
    >
      <div className="flex items-start gap-3">
        <div
          className={cn(
            "grid h-10 w-10 shrink-0 place-items-center rounded-lg border border-border bg-surface-2 font-semibold",
            found ? "text-success" : "text-fg-muted",
          )}
          aria-hidden
        >
          {letter}
        </div>
        <div className="min-w-0 flex-1">
          <div className="line-clamp-2 break-words font-medium leading-snug text-fg" title={r.source}>
            {r.source}
          </div>
          <div className="truncate font-mono text-[11px] uppercase tracking-wider text-fg-subtle">{r.type}</div>
        </div>
        <StatusBadge status={r.status} />
      </div>

      {r.detail &&
        (longDetail ? (
          <button
            type="button"
            onClick={() => setExpanded((v) => !v)}
            aria-expanded={expanded}
            title={expanded ? t("showLess") : t("showMore")}
            className={cn(
              "focus-ring break-words rounded text-left text-sm leading-relaxed text-fg-muted transition-colors hover:text-fg",
              !expanded && "line-clamp-3",
            )}
          >
            {r.detail}
          </button>
        ) : (
          <p className="break-words text-sm leading-relaxed text-fg-muted">{r.detail}</p>
        ))}

      <div className="mt-auto flex items-center gap-2 border-t border-border pt-3">
        {r.url ? (
          <a
            href={r.url}
            target="_blank"
            rel="noreferrer"
            className="focus-ring flex min-w-0 flex-1 items-center gap-1.5 rounded font-mono text-xs text-primary hover:underline"
          >
            <ExternalLink className="h-3.5 w-3.5 shrink-0" aria-hidden />
            <span className="truncate">{r.url.replace(/^https?:\/\//, "")}</span>
          </a>
        ) : (
          <span className="min-w-0 flex-1 truncate font-mono text-xs text-fg-subtle">{r.value || "—"}</span>
        )}
        {copyText && <CopyButton text={copyText} />}
      </div>
    </Card>
  );
}

/* ------------------------------------------------------------------ Scanning */
function ScanningState({ query, tone }: { query: string; tone: Tone }) {
  const t = useTranslations("checks.search");
  const [elapsed, setElapsed] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setElapsed((s) => s + 1), 1000);
    return () => clearInterval(id);
  }, []);

  return (
    <div className="animate-fade-in space-y-4" role="status" aria-live="polite">
      <Card className="p-5 sm:p-6">
        <div className="flex flex-col items-center gap-4 text-center sm:flex-row sm:text-left">
          <IconBox icon={Radar} tone={tone} size="lg" />
          <div className="min-w-0 flex-1">
            <div className="font-medium text-fg">{t("scanning")}</div>
            <div className="mt-1 truncate text-sm text-fg-muted">
              {t("target")}: <span className="font-mono text-fg">{query}</span>
            </div>
          </div>
          <div className="font-mono text-2xl tabular-nums text-fg-muted">
            {String(Math.floor(elapsed / 60)).padStart(2, "0")}:{String(elapsed % 60).padStart(2, "0")}
          </div>
        </div>
        <Skeleton className="mt-5 h-1.5 w-full rounded-full" />
      </Card>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {Array.from({ length: 6 }).map((_, i) => (
          <Card key={i} className="p-4">
            <div className="flex items-center gap-3">
              <Skeleton className="h-10 w-10 rounded-lg" />
              <div className="flex-1 space-y-2">
                <Skeleton className="h-3.5 w-2/3" />
                <Skeleton className="h-2.5 w-1/3" />
              </div>
            </div>
            <Skeleton className="mt-4 h-3 w-full" />
            <Skeleton className="mt-2 h-3 w-4/5" />
          </Card>
        ))}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ SearchModule */
export default function SearchModule({
  title,
  description,
  placeholder,
  search,
  kind,
  icon = Search,
  tone = "blue",
  examples = [],
  checks = [],
  inputMono,
}: {
  title: string;
  description: string;
  placeholder: string;
  search: (query: string) => Promise<SearchResponse>;
  kind: SearchKind;
  icon?: LucideIcon;
  tone?: Tone;
  examples?: string[];
  /** Modul nimalarni tekshirishi (bo'sh holat va yon panel uchun) — tarjima qilingan matnlar. */
  checks?: string[];
  inputMono?: boolean;
}) {
  const t = useTranslations("checks.search");
  const tc = useTranslations("common");
  const f = useFormat();
  const [query, setQuery] = useState("");
  const [running, setRunning] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<SearchResponse | null>(null);
  const [filter, setFilter] = useState<Filter>("all");
  const [exportError, setExportError] = useState<string | null>(null);
  const [history, setHistory] = useState<SearchJob[] | null>(null);
  const [historyError, setHistoryError] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const loadHistory = useCallback(() => {
    getHistory({ kind, limit: 8 })
      .then((jobs) => {
        setHistory(jobs);
        setHistoryError(false);
      })
      .catch(() => setHistoryError(true));
  }, [kind]);

  useEffect(() => {
    loadHistory();
  }, [loadHistory]);

  // Tarix sahifasidan "?q=..." bilan kelinsa — so'rovni oldindan to'ldiramiz (avtomatik ishga tushirmaymiz)
  useEffect(() => {
    const q = new URLSearchParams(window.location.search).get("q");
    if (q) setQuery(q.slice(0, 256));
  }, []);

  const run = useCallback(
    async (raw: string) => {
      const q = raw.trim();
      if (!q || running) return;
      setQuery(q);
      setError(null);
      setData(null);
      setFilter("all");
      setExportError(null);
      setRunning(q);
      try {
        setData(await search(q));
      } catch (err) {
        setError(err instanceof Error ? err.message : tc("error"));
      } finally {
        setRunning(null);
        loadHistory();
      }
    },
    [running, search, loadHistory],
  );

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    run(query);
  }

  const counts = useMemo(() => {
    const c = { all: 0, found: 0, not_found: 0, error: 0 };
    for (const r of data?.results ?? []) {
      c.all++;
      c[normStatus(r.status)]++;
    }
    return c;
  }, [data]);

  const visible = useMemo(() => {
    if (!data) return [];
    return [...data.results]
      .filter((r) => filter === "all" || normStatus(r.status) === filter)
      .sort((a, b) => (ORDER[a.status] ?? 3) - (ORDER[b.status] ?? 3));
  }, [data, filter]);

  const checked = data?.checked ?? counts.all;
  const found = data?.found ?? counts.found;
  const ratio = checked > 0 ? Math.round((found / checked) * 100) : 0;

  return (
    <div>
      <PageHeader icon={icon} tone={tone} title={title} description={description} />

      {/* ---------------- Qidiruv paneli */}
      <Card className="mb-6 animate-fade-in p-4 sm:p-5">
        <form onSubmit={onSubmit} className="flex flex-col gap-3 sm:flex-row">
          <Input
            ref={inputRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={placeholder}
            icon={icon}
            mono={inputMono}
            inputSize="lg"
            required
            autoFocus
            spellCheck={false}
            autoComplete="off"
            aria-label={title}
          />
          <Button type="submit" size="lg" icon={Search} loading={!!running} className="sm:w-44">
            {running ? t("searching") : tc("search")}
          </Button>
        </form>
        {examples.length > 0 && (
          <div className="mt-4 flex flex-wrap items-center gap-2">
            <span className="flex items-center gap-1 text-xs text-fg-muted">
              <Sparkles className="h-3.5 w-3.5" aria-hidden /> {t("examples")}:
            </span>
            {examples.map((ex) => (
              <button
                key={ex}
                type="button"
                onClick={() => {
                  setQuery(ex);
                  inputRef.current?.focus();
                }}
                className="focus-ring rounded-full border border-border bg-surface px-3 py-1 font-mono text-xs text-fg-muted transition-colors hover:bg-primary-soft hover:text-primary"
              >
                {ex}
              </button>
            ))}
          </div>
        )}
      </Card>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_300px]">
        {/* ---------------- Asosiy ustun */}
        <div className="min-w-0 space-y-6">
          {error && (
            <div className="animate-fade-in space-y-3">
              <ErrorBanner message={error} />
              <Button variant="secondary" size="sm" icon={RotateCcw} onClick={() => run(query)}>
                {tc("retry")}
              </Button>
            </div>
          )}

          {running && <ScanningState query={running} tone={tone} />}

          {!running && !data && !error && (
            <Card className="animate-fade-in">
              <EmptyState
                icon={Radar}
                title={t("emptyTitle")}
                description={`${description} ${t("publicOnly")}`}
              />
              {checks.length > 0 && (
                <div className="grid gap-2 border-t border-border p-5 sm:grid-cols-2">
                  {checks.map((c) => (
                    <div
                      key={c}
                      className="flex items-center gap-2.5 rounded-lg border border-border bg-surface-2 px-3 py-2.5 text-sm text-fg"
                    >
                      <ShieldCheck className="h-4 w-4 shrink-0 text-success" aria-hidden />
                      {c}
                    </div>
                  ))}
                </div>
              )}
            </Card>
          )}

          {!running && data && (
            <div className="animate-fade-in space-y-6">
              {/* Xulosa */}
              <div className="grid gap-4 sm:grid-cols-3">
                <StatTile label={t("checked")} value={f.number(checked)} icon={Layers} tone="blue" hint={t("checkedHint")} />
                <StatTile label={tc("status_found")} value={f.number(found)} icon={CheckCircle2} tone="green" hint={t("foundHint")} />
                <StatTile label={tc("status_unclear")} value={f.number(counts.error)} icon={CircleHelp} tone="amber" hint={t("unclearHint")} />
              </div>

              <Card className="p-5">
                <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
                  <div className="min-w-0 text-fg-muted">
                    {t("target")}: <span className="break-all font-mono text-fg">{data.query}</span>
                  </div>
                  <div className="font-mono tabular-nums text-fg-muted">
                    <span className="text-success">{found}</span> / {checked} ·{" "}
                    <span className="text-fg">{ratio}%</span>
                  </div>
                </div>
                <div
                  className="mt-3 h-2 overflow-hidden rounded-full bg-surface-2"
                  role="progressbar"
                  aria-label={t("foundRatio")}
                  aria-valuenow={ratio}
                  aria-valuemin={0}
                  aria-valuemax={100}
                >
                  <div className="h-full rounded-full bg-success transition-[width] duration-500" style={{ width: `${ratio}%` }} />
                </div>
                <div className="mt-4 flex flex-wrap items-center justify-between gap-2 border-t border-border pt-3">
                  <span className="text-xs text-fg-muted">{t("exportReport")}</span>
                  <ExportButtons jobId={data.job_id} labels="always" onError={setExportError} />
                </div>
                {exportError && (
                  <div className="mt-3">
                    <ErrorBanner message={exportError} />
                  </div>
                )}
              </Card>

              {/* Filtrlar */}
              <div className="flex flex-wrap gap-2" role="group" aria-label={t("filters")}>
                {FILTERS.map((fl) => {
                  const active = filter === fl.id;
                  return (
                    <button
                      key={fl.id}
                      type="button"
                      onClick={() => setFilter(fl.id)}
                      aria-pressed={active}
                      className={cn(
                        "focus-ring inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-medium transition-colors",
                        active
                          ? "border-primary bg-primary-soft text-primary"
                          : "border-border bg-surface text-fg-muted hover:bg-surface-2 hover:text-fg",
                      )}
                    >
                      <fl.icon className="h-3.5 w-3.5" aria-hidden />
                      <span>{tc(fl.labelKey)}</span>
                      <span className="rounded-full bg-surface-2 px-1.5 font-mono text-[10px] tabular-nums text-fg-muted">
                        {counts[fl.id]}
                      </span>
                    </button>
                  );
                })}
              </div>

              {visible.length === 0 ? (
                <Card>
                  <EmptyState icon={Search} title={t("noFilterTitle")} description={t("noFilterDesc")} />
                </Card>
              ) : (
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
                  {visible.map((r) => (
                    <ResultCard key={`${r.source}-${r.value}`} r={r} />
                  ))}
                </div>
              )}
            </div>
          )}
        </div>

        {/* ---------------- Yon panel */}
        <aside className="space-y-6">
          <Card className="p-5">
            <div className="mb-4 flex items-center justify-between">
              <div className="flex items-center gap-2 text-sm font-medium text-fg">
                <History className="h-4 w-4 text-primary" aria-hidden />
                {t("recent")}
              </div>
              {history && history.length > 0 && <Badge tone="slate">{f.number(history.length)}</Badge>}
            </div>

            {history === null && !historyError && (
              <div className="space-y-2">
                {Array.from({ length: 4 }).map((_, i) => (
                  <Skeleton key={i} className="h-11 w-full rounded-lg" />
                ))}
              </div>
            )}

            {historyError && <p className="text-xs text-fg-muted">{t("historyError")}</p>}

            {history && history.length === 0 && (
              <div className="flex flex-col items-center gap-2 py-6 text-center">
                <Clock className="h-5 w-5 text-fg-subtle" aria-hidden />
                <p className="text-xs text-fg-muted">{t("historyEmpty")}</p>
              </div>
            )}

            {history && history.length > 0 && (
              <ul className="space-y-1.5">
                {history.map((h) => (
                  <li key={h.id}>
                    <button
                      type="button"
                      disabled={!!running}
                      onClick={() => run(h.query)}
                      className="focus-ring group flex w-full items-center gap-3 rounded-lg border border-transparent px-3 py-2 text-left transition-colors hover:border-border hover:bg-surface-2 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      <div className="min-w-0 flex-1">
                        <div className="truncate font-mono text-sm text-fg">{h.query}</div>
                        <div className="text-[11px] text-fg-muted">{f.ago(h.created_at)}</div>
                      </div>
                      <ArrowRight className="h-4 w-4 shrink-0 text-fg-subtle group-hover:text-primary" aria-hidden />
                    </button>
                  </li>
                ))}
              </ul>
            )}

            {history && history.length > 0 && (
              <Link
                href="/dashboard/history"
                className="focus-ring mt-3 flex items-center justify-center gap-1.5 rounded-lg border border-border py-2 text-xs text-fg-muted transition-colors hover:bg-surface-2 hover:text-primary"
              >
                {t("fullHistory")} <ArrowRight className="h-3.5 w-3.5" aria-hidden />
              </Link>
            )}
          </Card>

          {checks.length > 0 && (
            <Card className="p-5">
              <div className="mb-3 flex items-center gap-2 text-sm font-medium text-fg">
                <ShieldCheck className="h-4 w-4 text-success" aria-hidden />
                {t("whatChecked")}
              </div>
              <ul className="space-y-2">
                {checks.map((c) => (
                  <li key={c} className="flex items-start gap-2 text-xs text-fg-muted">
                    <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-primary" aria-hidden />
                    {c}
                  </li>
                ))}
              </ul>
              <p className="mt-4 border-t border-border pt-3 text-[11px] leading-relaxed text-fg-muted">{t("disclaimer")}</p>
            </Card>
          )}
        </aside>
      </div>
    </div>
  );
}
