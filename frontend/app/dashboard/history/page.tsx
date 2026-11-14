"use client";

import {
  ChevronDown,
  Clock,
  ExternalLink,
  History,
  Layers,
  RotateCcw,
  Search,
  Trash2,
  X,
} from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import ExportButtons from "@/components/ExportButtons";
import { AnimatePresence, EASE, SPRING, motion } from "@/components/motion";
import {
  Badge,
  Button,
  ButtonLink,
  Card,
  EmptyState,
  ErrorBanner,
  IconBox,
  Input,
  PageHeader,
  Skeleton,
  Spinner,
  StatusBadge,
  formatDateTime,
  timeAgo,
} from "@/components/ui";
import {
  clearHistory,
  deleteJob,
  getHistory,
  getJob,
  type CollectResult,
  type SearchJob,
} from "@/lib/api";
import { cn } from "@/lib/cn";
import { MODULES, moduleLink, moduleMeta } from "@/lib/modules";
import { getOverview } from "@/lib/stats";

const LIMIT = 30;
const ARM_MS = 4000;
const ORDER: Record<string, number> = { found: 0, error: 1, not_found: 2 };

type Counts = { total: number; byKind: Record<string, number> };

/** Ikki bosqichli tasdiq: arm() -> ~4 s ichida ikkinchi bosish; keyin o'zi qaytadi. */
function useArm() {
  const [armed, setArmed] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const disarm = useCallback(() => {
    if (timer.current) clearTimeout(timer.current);
    timer.current = null;
    setArmed(false);
  }, []);

  const arm = useCallback(() => {
    setArmed(true);
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => {
      timer.current = null;
      setArmed(false);
    }, ARM_MS);
  }, []);

  useEffect(
    () => () => {
      if (timer.current) clearTimeout(timer.current);
    },
    [],
  );

  return { armed, arm, disarm };
}

/* ------------------------------------------------------------------ natijalar */
function ResultsList({ results }: { results: CollectResult[] }) {
  const sorted = useMemo(
    () => [...results].sort((a, b) => (ORDER[a.status] ?? 3) - (ORDER[b.status] ?? 3)),
    [results],
  );

  if (sorted.length === 0) {
    return <p className="px-1 py-3 text-sm text-slate-500">Bu qidiruvda natija saqlanmagan.</p>;
  }

  return (
    <ul className="divide-y divide-white/[0.05]">
      {sorted.map((r, i) => (
        <li
          key={`${r.source}-${r.value}-${i}`}
          className="flex flex-col gap-1.5 py-2.5 sm:flex-row sm:items-center sm:gap-3"
        >
          <div className="flex items-center justify-between gap-2 sm:w-44 sm:shrink-0 sm:justify-start">
            <span className="min-w-0 truncate text-sm font-medium text-slate-200">{r.source}</span>
            <StatusBadge status={r.status} />
          </div>
          <div className="min-w-0 flex-1 text-xs">
            {r.detail && <p className="break-words text-slate-400">{r.detail}</p>}
            {r.url ? (
              <a
                href={r.url}
                target="_blank"
                rel="noreferrer"
                className="mt-0.5 inline-flex max-w-full items-center gap-1.5 rounded font-mono text-cyan-300/90 transition hover:text-cyan-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-cyan/60"
              >
                <ExternalLink className="h-3.5 w-3.5 shrink-0" />
                <span className="truncate">{r.url.replace(/^https?:\/\//, "")}</span>
              </a>
            ) : (
              r.value && <div className="mt-0.5 break-all font-mono text-slate-500">{r.value}</div>
            )}
          </div>
        </li>
      ))}
    </ul>
  );
}

/* ------------------------------------------------------------------ qator */
function JobRow({
  job,
  cache,
  onDeleted,
}: {
  job: SearchJob;
  cache: React.MutableRefObject<Map<number, CollectResult[]>>;
  onDeleted: (id: number) => void;
}) {
  const meta = moduleMeta(job.kind);
  const found = job.found ?? 0;
  const checked = job.checked ?? 0;

  const [open, setOpen] = useState(false);
  const [results, setResults] = useState<CollectResult[] | null>(() => cache.current.get(job.id) ?? null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);
  const del = useArm();

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const res = await getJob(job.id);
      cache.current.set(job.id, res.results);
      setResults(res.results);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Natijalarni yuklab bo'lmadi");
    } finally {
      setLoading(false);
    }
  }

  function toggle() {
    const next = !open;
    setOpen(next);
    if (next && !results && !loading) void load();
  }

  async function remove() {
    if (!del.armed) {
      del.arm();
      return;
    }
    del.disarm();
    setDeleting(true);
    setError(null);
    try {
      await deleteJob(job.id);
      cache.current.delete(job.id);
      onDeleted(job.id);
    } catch (err) {
      setDeleting(false);
      setError(err instanceof Error ? err.message : "O'chirib bo'lmadi");
    }
  }

  const focusRing = "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-cyan/60";

  return (
    <motion.li
      layout="position"
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, height: 0, marginBottom: 0, transition: { duration: 0.25, ease: EASE } }}
      transition={SPRING}
      className="mb-3 list-none"
    >
      <Card className="overflow-hidden">
        <div className="flex flex-col gap-3 p-3.5 sm:flex-row sm:items-center sm:p-4">
          {/* so'rov */}
          <div className="flex min-w-0 flex-1 items-center gap-3">
            <IconBox icon={meta.icon} tone={meta.tone} />
            <div className="min-w-0 flex-1">
              <div className="line-clamp-2 break-all font-mono text-sm text-slate-100" title={job.query}>
                {job.query}
              </div>
            </div>
          </div>

          {/* meta + amallar */}
          <div className="flex flex-wrap items-center gap-x-3 gap-y-2 sm:flex-nowrap sm:justify-end">
            <Badge tone={meta.tone}>{meta.label}</Badge>
            <span
              className="inline-flex items-center gap-1 text-xs text-slate-500"
              title={formatDateTime(job.created_at)}
            >
              <Clock className="h-3 w-3" />
              {timeAgo(job.created_at)}
            </span>
            <span
              className={cn(
                "font-mono text-xs tabular-nums",
                found > 0 ? "text-emerald-300" : "text-slate-500",
              )}
              title="Topildi / tekshirildi"
            >
              {found} / {checked}
            </span>

            <div className="ml-auto flex items-center gap-1.5 sm:ml-0">
              <Link
                href={moduleLink(job.kind, job.query)}
                aria-label={`Qayta qidirish: ${job.query}`}
                title="Qayta qidirish"
                className={cn(
                  "inline-flex h-8 items-center gap-1.5 rounded-lg border border-white/10 bg-white/[0.04] px-2.5 text-xs font-medium text-slate-200 transition hover:border-white/20 hover:bg-white/[0.08]",
                  focusRing,
                )}
              >
                <RotateCcw className="h-3.5 w-3.5" />
                <span className="hidden sm:inline">Qayta</span>
              </Link>

              <ExportButtons jobId={job.id} onError={setError} />

              <button
                type="button"
                onClick={remove}
                disabled={deleting}
                aria-label={del.armed ? "O'chirishni tasdiqlash" : `O'chirish: ${job.query}`}
                title={del.armed ? "Tasdiqlash" : "O'chirish"}
                className={cn(
                  "inline-flex h-8 items-center gap-1.5 rounded-lg border px-2.5 text-xs font-medium transition disabled:opacity-50",
                  focusRing,
                  del.armed
                    ? "border-red-400/40 bg-red-500/20 text-red-200"
                    : "border-white/10 bg-white/[0.03] text-slate-400 hover:border-red-400/30 hover:text-red-300",
                )}
              >
                {deleting ? <Spinner className="h-3.5 w-3.5 text-red-300" /> : <Trash2 className="h-3.5 w-3.5" />}
                {del.armed && <span>Aniq?</span>}
              </button>
              {del.armed && (
                <button
                  type="button"
                  onClick={del.disarm}
                  aria-label="Bekor qilish"
                  title="Bekor qilish"
                  className={cn(
                    "grid h-8 w-8 place-items-center rounded-lg border border-white/10 bg-white/[0.03] text-slate-400 transition hover:text-slate-100",
                    focusRing,
                  )}
                >
                  <X className="h-3.5 w-3.5" />
                </button>
              )}

              <button
                type="button"
                onClick={toggle}
                aria-expanded={open}
                aria-label={open ? "Natijalarni yopish" : "Natijalarni ochish"}
                title={open ? "Yopish" : "Natijalarni ko'rish"}
                className={cn(
                  "grid h-8 w-8 place-items-center rounded-lg border border-white/10 bg-white/[0.03] text-slate-400 transition hover:border-white/20 hover:text-slate-100",
                  focusRing,
                )}
              >
                <ChevronDown className={cn("h-4 w-4 transition-transform duration-200", open && "rotate-180")} />
              </button>
            </div>
          </div>
        </div>

        {error && (
          <div className="px-3.5 pb-3.5 sm:px-4 sm:pb-4">
            <ErrorBanner message={error} />
          </div>
        )}

        <AnimatePresence initial={false}>
          {open && (
            <motion.div
              key="details"
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: "auto", opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={{ duration: 0.3, ease: EASE }}
              className="overflow-hidden"
            >
              <div className="border-t border-white/[0.06] px-3.5 py-2 sm:px-4">
                {loading && (
                  <div className="space-y-2 py-2" aria-busy="true">
                    {Array.from({ length: 3 }).map((_, i) => (
                      <Skeleton key={i} className="h-8 w-full" />
                    ))}
                  </div>
                )}
                {!loading && results && <ResultsList results={results} />}
                {!loading && !results && error && (
                  <div className="py-2">
                    <Button variant="secondary" size="sm" icon={RotateCcw} onClick={() => void load()}>
                      Qayta urinish
                    </Button>
                  </div>
                )}
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </Card>
    </motion.li>
  );
}

/* ------------------------------------------------------------------ sahifa */
export default function HistoryPage() {
  const [kind, setKind] = useState<string>("all");
  const [qInput, setQInput] = useState("");
  const [q, setQ] = useState("");
  const [jobs, setJobs] = useState<SearchJob[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hasMore, setHasMore] = useState(false);
  const [counts, setCounts] = useState<Counts | null>(null);
  const [clearing, setClearing] = useState(false);
  const [clearError, setClearError] = useState<string | null>(null);

  const gen = useRef(0);
  const cache = useRef<Map<number, CollectResult[]>>(new Map());
  const clearArm = useArm();

  // qidiruv matni debounce (~300 ms)
  useEffect(() => {
    const t = setTimeout(() => setQ(qInput.trim()), 300);
    return () => clearTimeout(t);
  }, [qInput]);

  const loadCounts = useCallback(() => {
    getOverview()
      .then((o) => setCounts({ total: o.searches_total ?? 0, byKind: o.searches_by_kind ?? {} }))
      .catch(() => {
        /* sanoqlar ixtiyoriy */
      });
  }, []);

  useEffect(() => {
    loadCounts();
  }, [loadCounts]);

  const fetchPage = useCallback(
    async (offset: number, append: boolean) => {
      // eskirgan javob yangisini bosib ketmasligi uchun avlod raqami
      const my = append ? gen.current : ++gen.current;
      if (append) setLoadingMore(true);
      else {
        setLoading(true);
        setLoadingMore(false);
      }
      setError(null);
      try {
        const rows = await getHistory({
          kind: kind === "all" ? undefined : kind,
          q: q || undefined,
          limit: LIMIT,
          offset,
        });
        if (my !== gen.current) return;
        setJobs((prev) => {
          if (!append) return rows;
          const seen = new Set(prev.map((j) => j.id));
          return [...prev, ...rows.filter((j) => !seen.has(j.id))];
        });
        setHasMore(rows.length === LIMIT);
      } catch (err) {
        if (my !== gen.current) return;
        setError(err instanceof Error ? err.message : "Tarixni yuklab bo'lmadi");
      } finally {
        if (my === gen.current) {
          setLoading(false);
          setLoadingMore(false);
        }
      }
    },
    [kind, q],
  );

  useEffect(() => {
    void fetchPage(0, false);
  }, [fetchPage]);

  // filtr o'zgarsa tasdiq holati bekor bo'ladi
  useEffect(() => {
    clearArm.disarm();
    setClearError(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [kind]);

  function onDeleted(id: number) {
    setJobs((prev) => prev.filter((j) => j.id !== id));
    loadCounts();
  }

  async function onClear() {
    if (!clearArm.armed) {
      clearArm.arm();
      return;
    }
    clearArm.disarm();
    setClearing(true);
    setClearError(null);
    try {
      await clearHistory(kind === "all" ? undefined : kind);
      cache.current.clear();
      loadCounts();
      await fetchPage(0, false);
    } catch (err) {
      setClearError(err instanceof Error ? err.message : "Tarixni tozalab bo'lmadi");
    } finally {
      setClearing(false);
    }
  }

  const kindLabel = kind === "all" ? null : moduleMeta(kind).label;
  const filtered = kind !== "all" || q !== "";

  const chips = [
    { id: "all", label: "Hammasi", icon: Layers, count: counts?.total },
    ...MODULES.map((m) => ({ id: m.kind, label: m.label, icon: m.icon, count: counts?.byKind[m.kind] ?? 0 })),
  ];

  return (
    <div>
      <PageHeader
        icon={History}
        tone="violet"
        eyebrow="Tekshiruv"
        title="Qidiruv tarixi"
        subtitle="Bajarilgan barcha tekshiruvlar: natijalarni qayta ko'ring, hisobot (JSON / PDF) oling, qayta qidiring yoki o'chiring."
        actions={
          <div className="flex flex-wrap items-center gap-2">
            {clearArm.armed && (
              <Button variant="ghost" size="sm" onClick={clearArm.disarm} aria-label="Bekor qilish">
                Bekor qilish
              </Button>
            )}
            <Button
              variant="danger"
              size="sm"
              icon={Trash2}
              loading={clearing}
              disabled={loading || jobs.length === 0}
              onClick={onClear}
              aria-label={
                clearArm.armed
                  ? "Tarixni tozalashni tasdiqlash"
                  : kindLabel
                    ? `${kindLabel} tarixini tozalash`
                    : "Tarixni tozalash"
              }
            >
              {clearArm.armed ? "Aniq o'chirilsinmi?" : kindLabel ? `${kindLabel} tarixini tozalash` : "Tarixni tozalash"}
            </Button>
          </div>
        }
      />

      {clearArm.armed && (
        <p className="-mt-3 mb-4 animate-fade-in text-xs text-red-300/90" role="status">
          {kindLabel ? (
            <>
              Faqat <span className="font-semibold">{kindLabel}</span> moduli tarixi o'chiriladi. Tasdiqlash uchun
              yana bosing.
            </>
          ) : (
            <>Barcha modullar tarixi o'chiriladi. Tasdiqlash uchun yana bosing.</>
          )}
        </p>
      )}

      {clearError && (
        <div className="mb-4">
          <ErrorBanner message={clearError} />
        </div>
      )}

      {/* filtr chiplari */}
      <div className="mb-4 flex flex-wrap gap-2" role="group" aria-label="Modul bo'yicha filtr">
        {chips.map((c) => {
          const active = kind === c.id;
          return (
            <button
              key={c.id}
              type="button"
              onClick={() => setKind(c.id)}
              aria-pressed={active}
              className={cn(
                "relative inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-medium transition active:scale-95",
                "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-cyan/60",
                active
                  ? "border-transparent text-cyan-200"
                  : "border-white/10 bg-white/[0.03] text-slate-400 hover:border-white/20 hover:text-slate-200",
              )}
            >
              {active && (
                <motion.span
                  layoutId="history-filter-active"
                  transition={SPRING}
                  className="absolute inset-0 rounded-full bg-brand-cyan/10 shadow-glow ring-1 ring-brand-cyan/40"
                />
              )}
              <c.icon className="relative h-3.5 w-3.5" />
              <span className="relative">{c.label}</span>
              {c.count !== undefined && (
                <span
                  className={cn(
                    "relative rounded-full px-1.5 font-mono text-[10px] tabular-nums",
                    active ? "bg-cyan-400/20 text-cyan-100" : "bg-white/5 text-slate-500",
                  )}
                >
                  {c.count}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* qidiruv */}
      <div className="mb-5">
        <Input
          icon={Search}
          value={qInput}
          onChange={(e) => setQInput(e.target.value)}
          placeholder="So'rov bo'yicha qidirish..."
          aria-label="Tarixda so'rov bo'yicha qidirish"
          spellCheck={false}
          autoComplete="off"
          mono
        />
      </div>

      {/* ro'yxat */}
      {loading ? (
        <div className="space-y-3" aria-busy="true" aria-label="Yuklanmoqda">
          {Array.from({ length: 5 }).map((_, i) => (
            <Card key={i} className="p-4">
              <div className="flex items-center gap-3">
                <Skeleton className="h-10 w-10 shrink-0 rounded-xl" />
                <div className="flex-1 space-y-2">
                  <Skeleton className="h-3.5 w-1/2" />
                  <Skeleton className="h-2.5 w-1/3" />
                </div>
              </div>
            </Card>
          ))}
        </div>
      ) : error && jobs.length === 0 ? (
        <div className="space-y-3">
          <ErrorBanner message={error} />
          <Button variant="secondary" size="sm" icon={RotateCcw} onClick={() => void fetchPage(0, false)}>
            Qayta urinish
          </Button>
        </div>
      ) : jobs.length === 0 ? (
        <Card>
          {filtered ? (
            <EmptyState
              icon={Search}
              title="Hech narsa topilmadi"
              description="Bu filtr yoki qidiruv matniga mos yozuv yo'q. Filtrni o'zgartirib yoki matnni tozalab ko'ring."
              action={
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => {
                    setKind("all");
                    setQInput("");
                  }}
                >
                  Filtrlarni tozalash
                </Button>
              }
            />
          ) : (
            <EmptyState
              icon={History}
              title="Tarix hali bo'sh"
              description="Birinchi tekshiruvni bajaring, u shu yerda paydo bo'ladi."
              action={
                <div className="flex flex-wrap justify-center gap-2">
                  {MODULES.map((m) => (
                    <ButtonLink key={m.kind} href={m.href} variant="secondary" size="sm" icon={m.icon}>
                      {m.label}
                    </ButtonLink>
                  ))}
                </div>
              }
            />
          )}
        </Card>
      ) : (
        <>
          {error && (
            <div className="mb-3">
              <ErrorBanner message={error} />
            </div>
          )}
          <ul className="m-0 p-0">
            <AnimatePresence initial={false}>
              {jobs.map((job) => (
                <JobRow key={job.id} job={job} cache={cache} onDeleted={onDeleted} />
              ))}
            </AnimatePresence>
          </ul>

          {hasMore && (
            <div className="mt-2 flex justify-center">
              <Button
                variant="secondary"
                loading={loadingMore}
                onClick={() => void fetchPage(jobs.length, true)}
                aria-label="Yana yuklash"
              >
                Yana yuklash
              </Button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
