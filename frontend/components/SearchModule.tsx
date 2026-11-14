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
  timeAgo,
} from "@/components/ui";
import { getHistory, type CollectResult, type SearchJob, type SearchResponse } from "@/lib/api";
import type { Tone } from "@/lib/categories";
import { AnimatePresence, EASE, SPRING, motion } from "@/components/motion";
import { cn } from "@/lib/cn";

export type SearchKind = "username" | "email" | "phone" | "domain";

type Filter = "all" | "found" | "not_found" | "error";

const ORDER: Record<string, number> = { found: 0, error: 1, not_found: 2 };

const FILTERS: { id: Filter; label: string; icon: LucideIcon }[] = [
  { id: "all", label: "Hammasi", icon: Layers },
  { id: "found", label: "Topildi", icon: CheckCircle2 },
  { id: "not_found", label: "Yo'q", icon: XCircle },
  { id: "error", label: "Noaniq", icon: CircleHelp },
];

/** Manba nomi uchun barqaror gradient (tashqi rasmsiz avatar). */
const AVATAR_GRADIENTS = [
  "from-cyan-400 to-violet-500",
  "from-violet-500 to-fuchsia-500",
  "from-sky-400 to-cyan-400",
  "from-fuchsia-500 to-violet-500",
  "from-emerald-400 to-cyan-500",
  "from-sky-500 to-violet-500",
];

function gradientFor(name: string) {
  let h = 0;
  for (let i = 0; i < name.length; i++) h = (h * 31 + name.charCodeAt(i)) >>> 0;
  return AVATAR_GRADIENTS[h % AVATAR_GRADIENTS.length];
}

function normStatus(s: string): Exclude<Filter, "all"> {
  return s === "found" || s === "not_found" ? s : "error";
}

/* ------------------------------------------------------------------ CopyButton */
function CopyButton({ text }: { text: string }) {
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
      title={copied ? "Nusxalandi" : "Nusxalash"}
      aria-label="Nusxalash"
      className={cn(
        "grid h-8 w-8 shrink-0 place-items-center rounded-lg border transition",
        copied
          ? "border-emerald-400/30 bg-emerald-500/10 text-emerald-300"
          : "border-white/10 bg-white/[0.03] text-slate-400 hover:border-white/20 hover:text-slate-100",
      )}
    >
      {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
    </button>
  );
}

/* ------------------------------------------------------------------ ResultCard */
function ResultCard({ r, index }: { r: CollectResult; index: number }) {
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
        "group relative flex h-full animate-fade-in flex-col gap-3 overflow-hidden p-4",
        found && "border-emerald-400/20",
        status === "not_found" && "opacity-80 hover:opacity-100",
      )}
      style={{ animationDelay: `${Math.min(index, 20) * 40}ms` }}
    >
      {found && (
        <div className="pointer-events-none absolute -right-10 -top-10 h-28 w-28 rounded-full bg-emerald-400/10 blur-2xl" />
      )}
      <div className="flex items-start gap-3">
        <div
          className={cn(
            "grid h-10 w-10 shrink-0 place-items-center rounded-full bg-gradient-to-br font-semibold text-white shadow-lg ring-2 ring-white/10",
            found ? gradientFor(r.source) : "from-slate-600 to-slate-700",
          )}
        >
          {letter}
        </div>
        <div className="min-w-0 flex-1">
          <div className="line-clamp-2 break-words font-medium leading-snug text-slate-100" title={r.source}>
            {r.source}
          </div>
          <div className="truncate font-mono text-[11px] uppercase tracking-wider text-slate-500">{r.type}</div>
        </div>
        <StatusBadge status={r.status} />
      </div>

      {r.detail &&
        (longDetail ? (
          <button
            type="button"
            onClick={() => setExpanded((v) => !v)}
            aria-expanded={expanded}
            title={expanded ? "Yig'ish" : "To'liq ko'rsatish"}
            className={cn(
              "break-words rounded text-left text-sm leading-relaxed text-slate-400 transition hover:text-slate-300 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-cyan/60",
              !expanded && "line-clamp-3",
            )}
          >
            {r.detail}
          </button>
        ) : (
          <p className="break-words text-sm leading-relaxed text-slate-400">{r.detail}</p>
        ))}

      <div className="mt-auto flex items-center gap-2 border-t border-white/[0.06] pt-3">
        {r.url ? (
          <a
            href={r.url}
            target="_blank"
            rel="noreferrer"
            className="flex min-w-0 flex-1 items-center gap-1.5 font-mono text-xs text-cyan-300/90 transition hover:text-cyan-200"
          >
            <ExternalLink className="h-3.5 w-3.5 shrink-0" />
            <span className="truncate">{r.url.replace(/^https?:\/\//, "")}</span>
          </a>
        ) : (
          <span className="min-w-0 flex-1 truncate font-mono text-xs text-slate-500">{r.value || "—"}</span>
        )}
        {copyText && <CopyButton text={copyText} />}
      </div>
    </Card>
  );
}

/* ------------------------------------------------------------------ Scanning */
function ScanningState({ query, tone }: { query: string; tone: Tone }) {
  const [elapsed, setElapsed] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setElapsed((s) => s + 1), 1000);
    return () => clearInterval(t);
  }, []);

  return (
    <div className="space-y-4 animate-fade-in">
      <Card glow className="relative overflow-hidden p-6">
        {/* skanerlash nuri */}
        <div className="pointer-events-none absolute inset-0 overflow-hidden">
          <div className="absolute inset-x-0 top-0 h-full animate-scan bg-gradient-to-b from-transparent via-cyan-400/10 to-transparent" />
        </div>
        <div className="relative flex flex-col items-center gap-5 text-center sm:flex-row sm:text-left">
          <div className="relative grid h-16 w-16 shrink-0 place-items-center">
            <span className="absolute inset-0 animate-pulse-ring rounded-full bg-cyan-400/30" />
            <span className="absolute inset-0 rounded-full border border-cyan-400/30" />
            <span className="absolute inset-2 animate-spin-slow rounded-full border border-dashed border-violet-400/40" />
            <IconBox icon={Radar} tone={tone} />
          </div>
          <div className="min-w-0 flex-1">
            <div className="font-mono text-[11px] uppercase tracking-[0.2em] text-brand-cyan/80">Skanerlanmoqda</div>
            <div className="mt-1 text-lg font-medium text-white">Manbalar tekshirilmoqda...</div>
            <div className="mt-1 truncate text-sm text-slate-400">
              Nishon: <span className="font-mono text-slate-200">{query}</span>
            </div>
          </div>
          <div className="font-mono text-2xl tabular-nums text-slate-300">
            {String(Math.floor(elapsed / 60)).padStart(2, "0")}:{String(elapsed % 60).padStart(2, "0")}
          </div>
        </div>
        <div className="relative mt-5 h-1.5 overflow-hidden rounded-full bg-ink-800">
          <div className="absolute inset-0 bg-gradient-to-r from-cyan-400/30 via-violet-500/30 to-fuchsia-500/30" />
          <div className="skeleton relative h-full w-full rounded-full bg-transparent" />
        </div>
      </Card>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {Array.from({ length: 6 }).map((_, i) => (
          <Card key={i} className="animate-fade-in p-4" style={{ animationDelay: `${i * 70}ms` }}>
            <div className="flex items-center gap-3">
              <Skeleton className="h-10 w-10 rounded-full" />
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
  tone = "cyan",
  eyebrow = "Tekshiruv moduli",
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
  eyebrow?: string;
  examples?: string[];
  /** Modul nimalarni tekshirishi (bo'sh holat va yon panel uchun). */
  checks?: string[];
  inputMono?: boolean;
}) {
  const [query, setQuery] = useState("");
  const [running, setRunning] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<SearchResponse | null>(null);
  const [filter, setFilter] = useState<Filter>("all");
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
      setRunning(q);
      try {
        setData(await search(q));
      } catch (err) {
        setError(err instanceof Error ? err.message : "Xatolik yuz berdi");
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
      <PageHeader icon={icon} tone={tone} eyebrow={eyebrow} title={title} subtitle={description} />

      {/* ---------------- Qidiruv paneli */}
      <Card glow className="relative mb-6 animate-fade-in overflow-hidden p-5 sm:p-6" style={{ animationDelay: "60ms" }}>
        <div className="pointer-events-none absolute -right-24 -top-24 h-64 w-64 rounded-full bg-brand-violet/10 blur-3xl" />
        <div className="pointer-events-none absolute -bottom-24 -left-24 h-64 w-64 rounded-full bg-brand-cyan/10 blur-3xl" />
        <form onSubmit={onSubmit} className="relative flex flex-col gap-3 sm:flex-row">
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
            {running ? "Qidirilmoqda" : "Qidirish"}
          </Button>
        </form>
        {examples.length > 0 && (
          <div className="relative mt-4 flex flex-wrap items-center gap-2">
            <span className="flex items-center gap-1 text-xs text-slate-500">
              <Sparkles className="h-3.5 w-3.5" /> Namuna:
            </span>
            {examples.map((ex) => (
              <button
                key={ex}
                type="button"
                onClick={() => {
                  setQuery(ex);
                  inputRef.current?.focus();
                }}
                className="rounded-full border border-white/10 bg-white/[0.03] px-3 py-1 font-mono text-xs text-slate-300 transition hover:border-brand-cyan/40 hover:bg-brand-cyan/10 hover:text-cyan-200"
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
                Qayta urinish
              </Button>
            </div>
          )}

          {running && <ScanningState query={running} tone={tone} />}

          {!running && !data && !error && (
            <Card className="animate-fade-in" style={{ animationDelay: "120ms" }}>
              <EmptyState
                icon={Radar}
                title="Qidiruvni boshlang"
                description={`${description} Faqat ochiq manbalardan foydalaniladi.`}
              />
              {checks.length > 0 && (
                <div className="grid gap-2 border-t border-white/[0.06] p-5 sm:grid-cols-2">
                  {checks.map((c, i) => (
                    <div
                      key={c}
                      className="flex animate-fade-in items-center gap-2.5 rounded-xl border border-white/[0.06] bg-white/[0.02] px-3 py-2.5 text-sm text-slate-300"
                      style={{ animationDelay: `${160 + i * 50}ms` }}
                    >
                      <ShieldCheck className="h-4 w-4 shrink-0 text-emerald-400" />
                      {c}
                    </div>
                  ))}
                </div>
              )}
            </Card>
          )}

          {!running && data && (
            <div className="space-y-6">
              {/* Xulosa */}
              <div className="grid gap-4 sm:grid-cols-3">
                <div className="animate-fade-in">
                  <StatTile label="Tekshirildi" value={checked} icon={Layers} tone="cyan" hint="manba" />
                </div>
                <div className="animate-fade-in" style={{ animationDelay: "60ms" }}>
                  <StatTile label="Topildi" value={found} icon={CheckCircle2} tone="emerald" hint="mos kelish" />
                </div>
                <div className="animate-fade-in" style={{ animationDelay: "120ms" }}>
                  <StatTile label="Noaniq" value={counts.error} icon={CircleHelp} tone="amber" hint="javob yo'q / xato" />
                </div>
              </div>

              <Card className="animate-fade-in p-5" style={{ animationDelay: "160ms" }}>
                <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
                  <div className="min-w-0 text-slate-400">
                    Nishon: <span className="break-all font-mono text-slate-100">{data.query}</span>
                  </div>
                  <div className="font-mono tabular-nums text-slate-300">
                    <span className="text-emerald-300">{found}</span> / {checked} ·{" "}
                    <span className="text-white">{ratio}%</span>
                  </div>
                </div>
                <div
                  className="mt-3 h-2 overflow-hidden rounded-full bg-ink-800"
                  role="progressbar"
                  aria-valuenow={ratio}
                  aria-valuemin={0}
                  aria-valuemax={100}
                >
                  <motion.div
                    className="h-full rounded-full bg-gradient-to-r from-emerald-400 to-cyan-400 shadow-[0_0_12px_rgba(52,211,153,.6)]"
                    initial={{ width: 0 }}
                    animate={{ width: `${ratio}%` }}
                    transition={{ duration: 1.1, ease: EASE, delay: 0.2 }}
                  />
                </div>
              </Card>

              {/* Filtrlar */}
              <div className="flex flex-wrap gap-2">
                {FILTERS.map((f) => {
                  const active = filter === f.id;
                  return (
                    <button
                      key={f.id}
                      type="button"
                      onClick={() => setFilter(f.id)}
                      className={cn(
                        "relative inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-medium transition active:scale-95",
                        active
                          ? "border-transparent text-cyan-200"
                          : "border-white/10 bg-white/[0.03] text-slate-400 hover:border-white/20 hover:text-slate-200",
                      )}
                    >
                      {active && (
                        <motion.span
                          layoutId="search-filter-active"
                          transition={SPRING}
                          className="absolute inset-0 rounded-full bg-brand-cyan/10 shadow-glow ring-1 ring-brand-cyan/40"
                        />
                      )}
                      <f.icon className="relative h-3.5 w-3.5" />
                      <span className="relative">{f.label}</span>
                      <span
                        className={cn(
                          "relative rounded-full px-1.5 font-mono text-[10px] tabular-nums",
                          active ? "bg-cyan-400/20 text-cyan-100" : "bg-white/5 text-slate-500",
                        )}
                      >
                        {counts[f.id]}
                      </span>
                    </button>
                  );
                })}
              </div>

              {visible.length === 0 ? (
                <Card>
                  <EmptyState
                    icon={Search}
                    title="Bu filtrda natija yo'q"
                    description="Boshqa filtrni tanlang yoki yangi qidiruv bajaring."
                  />
                </Card>
              ) : (
                <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
                  <AnimatePresence mode="popLayout" initial={false}>
                    {visible.map((r, i) => (
                      <motion.div
                        key={`${r.source}-${r.value}`}
                        layout
                        initial={{ opacity: 0, scale: 0.9 }}
                        animate={{ opacity: 1, scale: 1 }}
                        exit={{ opacity: 0, scale: 0.9, transition: { duration: 0.15 } }}
                        transition={SPRING}
                        className="h-full"
                      >
                        <ResultCard r={r} index={i} />
                      </motion.div>
                    ))}
                  </AnimatePresence>
                </div>
              )}
            </div>
          )}
        </div>

        {/* ---------------- Yon panel */}
        <aside className="space-y-6">
          <Card className="animate-fade-in p-5" style={{ animationDelay: "100ms" }}>
            <div className="mb-4 flex items-center justify-between">
              <div className="flex items-center gap-2 text-sm font-medium text-slate-200">
                <History className="h-4 w-4 text-brand-cyan" />
                So'nggi qidiruvlar
              </div>
              {history && history.length > 0 && <Badge tone="slate">{history.length}</Badge>}
            </div>

            {history === null && !historyError && (
              <div className="space-y-2">
                {Array.from({ length: 4 }).map((_, i) => (
                  <Skeleton key={i} className="h-11 w-full rounded-xl" />
                ))}
              </div>
            )}

            {historyError && (
              <p className="text-xs text-slate-500">Tarixni yuklab bo'lmadi.</p>
            )}

            {history && history.length === 0 && (
              <div className="flex flex-col items-center gap-2 py-6 text-center">
                <Clock className="h-5 w-5 text-slate-600" />
                <p className="text-xs text-slate-500">Hali qidiruv bajarilmagan.</p>
              </div>
            )}

            {history && history.length > 0 && (
              <ul className="space-y-1.5">
                {history.map((h, i) => (
                  <li key={h.id} className="animate-fade-in" style={{ animationDelay: `${i * 40}ms` }}>
                    <button
                      type="button"
                      disabled={!!running}
                      onClick={() => run(h.query)}
                      className="group flex w-full items-center gap-3 rounded-xl border border-transparent px-3 py-2 text-left transition hover:border-white/10 hover:bg-white/[0.04] disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      <div className="min-w-0 flex-1">
                        <div className="truncate font-mono text-sm text-slate-200">{h.query}</div>
                        <div className="text-[11px] text-slate-500">{timeAgo(h.created_at)}</div>
                      </div>
                      <ArrowRight className="h-4 w-4 shrink-0 text-slate-600 transition group-hover:translate-x-0.5 group-hover:text-brand-cyan" />
                    </button>
                  </li>
                ))}
              </ul>
            )}

            {history && history.length > 0 && (
              <Link
                href="/dashboard/history"
                className="mt-3 flex items-center justify-center gap-1.5 rounded-xl border border-white/[0.06] py-2 text-xs text-slate-400 transition hover:border-brand-cyan/30 hover:text-brand-cyan"
              >
                Butun tarix <ArrowRight className="h-3.5 w-3.5" />
              </Link>
            )}
          </Card>

          {checks.length > 0 && (
            <Card className="animate-fade-in p-5" style={{ animationDelay: "160ms" }}>
              <div className="mb-3 flex items-center gap-2 text-sm font-medium text-slate-200">
                <ShieldCheck className="h-4 w-4 text-emerald-400" />
                Nimalar tekshiriladi
              </div>
              <ul className="space-y-2">
                {checks.map((c) => (
                  <li key={c} className="flex items-start gap-2 text-xs text-slate-400">
                    <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-brand-cyan" />
                    {c}
                  </li>
                ))}
              </ul>
              <p className="mt-4 border-t border-white/[0.06] pt-3 text-[11px] leading-relaxed text-slate-500">
                Faqat ochiq manbalar. Natijalar taxminiy — muhim xulosadan oldin qo'lda tasdiqlang.
              </p>
            </Card>
          )}
        </aside>
      </div>
    </div>
  );
}
