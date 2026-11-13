"use client";

import {
  ArrowUpRight,
  CalendarDays,
  ChevronDown,
  Clock,
  Database,
  Hash,
  Layers,
  Radar,
  RefreshCw,
  Search,
  Send,
  Sparkles,
  X,
  type LucideIcon,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Badge,
  Button,
  Card,
  CategoryBadge,
  EmptyState,
  ErrorBanner,
  Input,
  LiveDot,
  PageHeader,
  Skeleton,
  timeAgo,
} from "@/components/ui";
import {
  getCollectorStatus,
  getEvents,
  getTgStatus,
  refreshEvents,
  type CollectorStatus,
  type EventItem,
  type TgStatus,
} from "@/lib/api";
import { CATEGORY_ORDER, categoryMeta, type Tone } from "@/lib/categories";
import { cn } from "@/lib/cn";

const PAGE_SIZE = 40;

/* ------------------------------------------------------------ tone classes */
// Tailwind statik klasslar talab qiladi — shuning uchun to'liq satrlar.
const DOT: Record<Tone, string> = {
  cyan: "text-cyan-300 ring-cyan-400/40 shadow-[0_0_18px_-2px_rgba(34,211,238,.55)]",
  sky: "text-sky-300 ring-sky-400/40 shadow-[0_0_18px_-2px_rgba(56,189,248,.55)]",
  violet: "text-violet-300 ring-violet-400/40 shadow-[0_0_18px_-2px_rgba(139,92,246,.55)]",
  fuchsia: "text-fuchsia-300 ring-fuchsia-400/40 shadow-[0_0_18px_-2px_rgba(217,70,239,.55)]",
  red: "text-red-300 ring-red-400/50 shadow-[0_0_18px_-2px_rgba(239,68,68,.6)]",
  orange: "text-orange-300 ring-orange-400/50 shadow-[0_0_18px_-2px_rgba(249,115,22,.6)]",
  amber: "text-amber-300 ring-amber-400/40 shadow-[0_0_18px_-2px_rgba(245,158,11,.55)]",
  emerald: "text-emerald-300 ring-emerald-400/40 shadow-[0_0_18px_-2px_rgba(16,185,129,.55)]",
  slate: "text-slate-300 ring-slate-400/30",
};

const BAR: Record<Tone, string> = {
  cyan: "bg-cyan-400",
  sky: "bg-sky-400",
  violet: "bg-violet-400",
  fuchsia: "bg-fuchsia-400",
  red: "bg-red-400",
  orange: "bg-orange-400",
  amber: "bg-amber-400",
  emerald: "bg-emerald-400",
  slate: "bg-slate-400",
};

const ICON_TEXT: Record<Tone, string> = {
  cyan: "text-cyan-300",
  sky: "text-sky-300",
  violet: "text-violet-300",
  fuchsia: "text-fuchsia-300",
  red: "text-red-300",
  orange: "text-orange-300",
  amber: "text-amber-300",
  emerald: "text-emerald-300",
  slate: "text-slate-300",
};

/** Kategoriya bo'yicha bo'sh holat matnlari */
const EMPTY_TEXT: Record<string, { title: string; description: string }> = {
  "": {
    title: "Hozircha hodisalar yo'q",
    description: "Fon yig'uvchi manbalarni tekshirmoqda. \"Yangilash\" tugmasi bilan hozir yig'ishni boshlang.",
  },
  ransomware: {
    title: "Ransomware hujumlari qayd etilmagan",
    description: "ransomware.live'da O'zbekiston tashkilotlariga oid yozuv topilmadi.",
  },
  leak: {
    title: "Leak chatlarida O'zbekiston tilga olinmagan",
    description: "Kuzatilayotgan leak chatlari va forumlarida mos xabar topilmadi.",
  },
  telegram: {
    title: "TG kanallarda mos xabar yo'q",
    description: "Kuzatilayotgan Telegram kanallarida O'zbekistonga oid xabar hali uchramadi.",
  },
  tg_group: {
    title: "TG guruhlarda mos xabar yo'q",
    description: "Kuzatilayotgan Telegram guruhlarida O'zbekistonga oid xabar hali uchramadi.",
  },
  news: {
    title: "Yangiliklar hali yig'ilmagan",
    description: "RSS manbalaridan yangiliklar keyingi yig'ishda paydo bo'ladi.",
  },
};

/* ------------------------------------------------------------ helpers */
type FeedItem = EventItem & { first_seen?: string | null };

function eventTime(e: FeedItem): string | null {
  return e.published || e.first_seen || null;
}

/** "🔎 uzbek, .uz · matn" → { keywords: ["uzbek", ".uz"], snippet: "matn" } */
function parseSummary(summary: string): { keywords: string[]; snippet: string } {
  const s = (summary || "").trim();
  const m = s.match(/^🔎️?\s*([^\n·]{1,160}?)\s*·\s*([\s\S]*)$/);
  if (m) {
    const keywords = m[1]
      .split(",")
      .map((k) => k.trim())
      .filter(Boolean);
    return { keywords, snippet: m[2].trim() };
  }
  // Marker bo'lsa-yu, ajratuvchi bo'lmasa — emoji'ni olib tashlaymiz
  return { keywords: [], snippet: s.replace(/^🔎️?\s*/, "") };
}

function dayKey(iso: string | null): string {
  if (!iso) return "none";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "none";
  return `${d.getFullYear()}-${d.getMonth()}-${d.getDate()}`;
}

function dayLabel(iso: string | null): string {
  if (!iso) return "Sanasiz";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "Sanasiz";
  const today = new Date();
  const yest = new Date();
  yest.setDate(today.getDate() - 1);
  if (dayKey(d.toISOString()) === dayKey(today.toISOString())) return "Bugun";
  if (dayKey(d.toISOString()) === dayKey(yest.toISOString())) return "Kecha";
  return d.toLocaleDateString("uz-UZ", {
    day: "numeric",
    month: "long",
    year: d.getFullYear() === today.getFullYear() ? undefined : "numeric",
  });
}

function clockTime(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleTimeString("uz-UZ", { hour: "2-digit", minute: "2-digit" });
}

function escapeRe(s: string) {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

/** Qidiruv so'zini matnda yoritish */
function Highlight({ text, query }: { text: string; query: string }) {
  const q = query.trim();
  if (!q) return <>{text}</>;
  const parts = text.split(new RegExp(`(${escapeRe(q)})`, "gi"));
  return (
    <>
      {parts.map((p, i) =>
        p.toLowerCase() === q.toLowerCase() ? (
          <mark key={i} className="rounded bg-brand-cyan/20 px-0.5 text-cyan-100">
            {p}
          </mark>
        ) : (
          <span key={i}>{p}</span>
        ),
      )}
    </>
  );
}

function fmt(n: number | undefined) {
  return (n ?? 0).toLocaleString("en-US").replace(/,/g, " ");
}

/* ------------------------------------------------------------ status strip */
function StatusStrip({
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
  return (
    <div className="space-y-3">
      <Card className="relative overflow-hidden px-5 py-3.5">
        {/* nozik skaner chizig'i */}
        <div className="pointer-events-none absolute inset-y-0 left-0 w-full bg-gradient-to-r from-transparent via-brand-cyan/[0.04] to-transparent" />
        <div className="relative flex flex-col gap-3 text-sm md:flex-row md:items-center md:justify-between">
          <div className="flex flex-wrap items-center gap-x-5 gap-y-2">
            <div className="flex items-center gap-2.5">
              <LiveDot tone={!cs ? "red" : cs.last_error ? "amber" : cs.running ? "emerald" : "amber"} />
              <span className="font-medium text-slate-200">
                {!cs ? "Yig'uvchi holati noma'lum" : cs.running ? "Jonli kuzatuv" : "Yig'uvchi to'xtagan"}
              </span>
            </div>
            {cs && (
              <>
                <span className="flex items-center gap-1.5 text-slate-400">
                  <Clock className="h-3.5 w-3.5 text-slate-500" />
                  har <span className="font-mono tabular-nums text-slate-200">{minutes}</span> daq · oxirgi:{" "}
                  <span className="text-slate-200">{cs.last_run ? timeAgo(cs.last_run) : "hali yo'q"}</span>
                </span>
                <span className="flex items-center gap-1.5 text-slate-400">
                  <Database className="h-3.5 w-3.5 text-slate-500" />
                  bazada <span className="font-mono tabular-nums text-slate-200">{fmt(cs.total_events)}</span> ta
                </span>
                {cs.last_new > 0 && (
                  <span className="flex items-center gap-1.5 text-emerald-300">
                    <Sparkles className="h-3.5 w-3.5" />
                    <span className="font-mono tabular-nums">+{cs.last_new}</span> oxirgi yig'ishda
                  </span>
                )}
              </>
            )}
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {lastNew !== null && (
              <Badge tone={lastNew > 0 ? "emerald" : "slate"} icon={Sparkles} className="animate-fade-in">
                {lastNew > 0 ? `${lastNew} ta yangi hodisa` : "Yangi hodisa yo'q"}
              </Badge>
            )}
            {tg && (
              <span
                title={tg.authorized ? undefined : tg.message}
                className={cn(
                  "inline-flex max-w-full items-center gap-1.5 truncate rounded-full border px-2.5 py-1 text-xs",
                  tg.authorized
                    ? "border-sky-400/25 bg-sky-400/10 text-sky-300"
                    : "border-amber-400/30 bg-amber-500/10 text-amber-300",
                )}
              >
                <Send className="h-3 w-3 shrink-0" />
                <span className="truncate">
                  {tg.authorized ? (
                    <>
                      Telegram: <span className="font-mono">{tg.account}</span>
                      <span className="text-sky-300/60">
                        {" "}
                        · {tg.chats_filter.length ? `${tg.chats_filter.length} chat` : "barcha chatlar"}
                        {tg.uz_filter ? " · UZ filtr" : ""}
                      </span>
                    </>
                  ) : (
                    <>Telegram ulanmagan</>
                  )}
                </span>
              </span>
            )}
          </div>
        </div>
      </Card>
      {cs?.last_error && <ErrorBanner message={`Yig'uvchi xatosi: ${cs.last_error}`} />}
    </div>
  );
}

/* ------------------------------------------------------------ category cards */
function CategoryCard({
  label,
  icon: Icon,
  tone,
  count,
  share,
  active,
  onClick,
  index,
}: {
  label: string;
  icon: LucideIcon;
  tone: Tone | "brand";
  count: number | null;
  share: number;
  active: boolean;
  onClick: () => void;
  index: number;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      style={{ animationDelay: `${index * 50}ms` }}
      className={cn(
        "glass group relative animate-fade-in overflow-hidden p-4 text-left transition duration-300",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-cyan/60",
        active
          ? "gradient-border bg-ink-800/80 shadow-glow"
          : "hover:-translate-y-0.5 hover:border-white/15 hover:bg-ink-800/60",
      )}
    >
      {active && <div className="pointer-events-none absolute inset-0 bg-brand-gradient-soft opacity-60" />}
      <div className="relative flex items-center justify-between gap-2">
        <Icon
          className={cn(
            "h-4 w-4 transition",
            tone === "brand" ? "text-brand-cyan" : ICON_TEXT[tone],
            !active && "opacity-80 group-hover:opacity-100",
          )}
        />
        {active && <span className="h-1.5 w-1.5 rounded-full bg-brand-cyan shadow-[0_0_8px_rgba(34,211,238,.9)]" />}
      </div>
      <div className="relative mt-3 font-mono text-2xl font-semibold tabular-nums text-white">
        {count === null ? <Skeleton className="h-7 w-12" /> : fmt(count)}
      </div>
      <div className={cn("relative mt-0.5 truncate text-xs font-medium", active ? "text-slate-200" : "text-slate-400")}>
        {label}
      </div>
      <div className="relative mt-3 h-1 overflow-hidden rounded-full bg-white/[0.06]">
        <div
          className={cn("h-full rounded-full transition-all duration-700", tone === "brand" ? "bg-brand-gradient" : BAR[tone])}
          style={{ width: `${Math.max(share > 0 ? 4 : 0, Math.round(share * 100))}%` }}
        />
      </div>
    </button>
  );
}

/* ------------------------------------------------------------ event card */
function EventCard({ e, query, delay }: { e: FeedItem; query: string; delay: number }) {
  const meta = categoryMeta(e.category);
  const Icon = meta.icon;
  const t = eventTime(e);
  const { keywords, snippet } = parseSummary(e.summary);
  const critical = e.category === "ransomware" || e.category === "leak";

  return (
    <li className="relative animate-fade-in pl-12 sm:pl-14" style={{ animationDelay: `${delay}ms` }}>
      {/* timeline tuguni */}
      <div
        className={cn(
          "absolute left-0 top-4 z-[1] grid h-8 w-8 place-items-center rounded-full bg-ink-900 ring-1 sm:left-1",
          DOT[meta.tone],
        )}
      >
        <Icon className="h-4 w-4" />
      </div>

      <article
        className={cn(
          "glass glass-hover group relative overflow-hidden p-4 sm:p-5",
          critical && (e.category === "ransomware" ? "bg-red-500/[0.03]" : "bg-orange-500/[0.03]"),
        )}
      >
        {critical && (
          <span
            className={cn(
              "absolute inset-y-3 left-0 w-[3px] rounded-r-full",
              e.category === "ransomware"
                ? "bg-red-400/80 shadow-[0_0_12px_rgba(239,68,68,.7)]"
                : "bg-orange-400/80 shadow-[0_0_12px_rgba(249,115,22,.7)]",
            )}
          />
        )}

        <div className="flex flex-wrap items-center gap-x-2.5 gap-y-1.5 text-xs">
          <CategoryBadge category={e.category} />
          {e.source && (
            <span className="max-w-[16rem] truncate font-mono text-[11px] text-slate-400" title={e.source}>
              {e.source}
            </span>
          )}
          {t && (
            <span
              className="ml-auto flex items-center gap-1.5 text-slate-500"
              title={new Date(t).toLocaleString("uz-UZ")}
            >
              <span className="font-mono tabular-nums text-slate-600">{clockTime(t)}</span>
              <span>{timeAgo(t)}</span>
            </span>
          )}
        </div>

        <h3 className="mt-2.5 line-clamp-2 font-semibold leading-snug text-white">
          {e.url ? (
            <a
              href={e.url}
              target="_blank"
              rel="noreferrer"
              className="transition hover:text-cyan-200 focus-visible:outline-none focus-visible:underline"
            >
              <Highlight text={e.title || "Sarlavhasiz"} query={query} />
            </a>
          ) : (
            <Highlight text={e.title || "Sarlavhasiz"} query={query} />
          )}
        </h3>

        {snippet && (
          <p className="mt-1.5 line-clamp-3 text-sm leading-relaxed text-slate-400">
            <Highlight text={snippet} query={query} />
          </p>
        )}

        {(keywords.length > 0 || e.url) && (
          <div className="mt-3 flex flex-wrap items-center gap-1.5">
            {keywords.map((k) => (
              <span
                key={k}
                className="inline-flex items-center gap-1 rounded-md border border-cyan-400/20 bg-cyan-400/[0.07] px-1.5 py-0.5 font-mono text-[11px] text-cyan-300"
              >
                <Hash className="h-3 w-3 opacity-60" />
                {k}
              </span>
            ))}
            {e.url && (
              <a
                href={e.url}
                target="_blank"
                rel="noreferrer"
                className="ml-auto inline-flex items-center gap-1 rounded-lg px-2 py-1 text-xs font-medium text-slate-400 transition hover:bg-white/[0.06] hover:text-cyan-200"
              >
                Manbani ochish
                <ArrowUpRight className="h-3.5 w-3.5 transition group-hover:-translate-y-0.5 group-hover:translate-x-0.5" />
              </a>
            )}
          </div>
        )}
      </article>
    </li>
  );
}

function FeedSkeleton() {
  return (
    <ol className="relative space-y-4">
      <div className="absolute bottom-0 left-4 top-0 w-px bg-white/[0.06] sm:left-5" />
      {Array.from({ length: 5 }).map((_, i) => (
        <li key={i} className="relative pl-12 sm:pl-14">
          <Skeleton className="absolute left-0 top-4 h-8 w-8 rounded-full sm:left-1" />
          <Card className="space-y-3 p-5">
            <div className="flex items-center gap-2">
              <Skeleton className="h-5 w-20 rounded-full" />
              <Skeleton className="h-4 w-28" />
              <Skeleton className="ml-auto h-4 w-16" />
            </div>
            <Skeleton className="h-5 w-4/5" />
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-2/3" />
          </Card>
        </li>
      ))}
    </ol>
  );
}

/* ------------------------------------------------------------ page */
export default function EventsPage() {
  const [items, setItems] = useState<FeedItem[]>([]);
  const [total, setTotal] = useState(0);
  const [qInput, setQInput] = useState("");
  const [q, setQ] = useState("");
  const [cat, setCat] = useState("");
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [cs, setCs] = useState<CollectorStatus | null>(null);
  const [tg, setTg] = useState<TgStatus | null>(null);
  const [statusLoading, setStatusLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [lastNew, setLastNew] = useState<number | null>(null);
  const reqId = useRef(0);

  const loadStatus = useCallback(async () => {
    const [c, t] = await Promise.allSettled([getCollectorStatus(), getTgStatus()]);
    setCs(c.status === "fulfilled" ? c.value : null);
    setTg(t.status === "fulfilled" ? t.value : null);
    setStatusLoading(false);
  }, []);

  const load = useCallback(async (query: string, category: string) => {
    const id = ++reqId.current;
    setLoading(true);
    setError(null);
    try {
      const res = await getEvents(query || undefined, category || undefined, PAGE_SIZE);
      if (id !== reqId.current) return;
      setItems(res.items);
      setTotal(res.count);
    } catch (err) {
      if (id !== reqId.current) return;
      setError(err instanceof Error ? err.message : "Xatolik yuz berdi");
      setItems([]);
      setTotal(0);
    } finally {
      if (id === reqId.current) setLoading(false);
    }
  }, []);

  async function loadMore() {
    const id = reqId.current;
    setLoadingMore(true);
    try {
      const res = await getEvents(q || undefined, cat || undefined, PAGE_SIZE, items.length);
      if (id !== reqId.current) return;
      setItems((prev) => [...prev, ...res.items]);
      setTotal(res.count);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Xatolik yuz berdi");
    } finally {
      setLoadingMore(false);
    }
  }

  async function onRefresh() {
    setRefreshing(true);
    setLastNew(null);
    try {
      const r = await refreshEvents();
      setLastNew(r.new);
      await Promise.all([load(q, cat), loadStatus()]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Xatolik yuz berdi");
    } finally {
      setRefreshing(false);
    }
  }

  // Holat: dastlab va har daqiqada
  useEffect(() => {
    loadStatus();
    const t = setInterval(loadStatus, 60_000);
    return () => clearInterval(t);
  }, [loadStatus]);

  // Qidiruv — 400ms debounce
  useEffect(() => {
    const t = setTimeout(() => setQ(qInput.trim()), 400);
    return () => clearTimeout(t);
  }, [qInput]);

  useEffect(() => {
    load(q, cat);
  }, [q, cat, load]);

  // "Yangi hodisalar" yorlig'ini biroz vaqtdan keyin yashirish
  useEffect(() => {
    if (lastNew === null) return;
    const t = setTimeout(() => setLastNew(null), 8000);
    return () => clearTimeout(t);
  }, [lastNew]);

  // Kunlar bo'yicha guruhlash (API tartibi saqlanadi)
  const groups = useMemo(() => {
    const out: { key: string; label: string; items: { e: FeedItem; idx: number }[] }[] = [];
    items.forEach((e, idx) => {
      const t = eventTime(e);
      const key = dayKey(t);
      const last = out[out.length - 1];
      if (last && last.key === key) last.items.push({ e, idx });
      else out.push({ key, label: dayLabel(t), items: [{ e, idx }] });
    });
    return out;
  }, [items]);

  const totalAll = cs?.total_events ?? null;
  const catCards = [
    { key: "", label: "Hammasi", icon: Layers as LucideIcon, tone: "brand" as const, count: totalAll },
    ...CATEGORY_ORDER.map((k) => {
      const m = categoryMeta(k);
      return { key: k, label: m.label, icon: m.icon, tone: m.tone, count: cs ? cs.by_category[k] ?? 0 : null };
    }),
  ];

  const activeMeta = cat ? categoryMeta(cat) : null;
  const empty = EMPTY_TEXT[cat] ?? EMPTY_TEXT[""];
  const hasMore = items.length < total;

  return (
    <div>
      <PageHeader
        icon={Radar}
        tone="cyan"
        eyebrow="THREAT INTELLIGENCE · O'ZBEKISTON"
        title="Events"
        subtitle="Ransomware hujumlari, leak chatlari, Telegram kanal va guruhlari hamda yangiliklar — O'zbekistonga oid barcha signallar bitta lentada."
        actions={
          <Button icon={RefreshCw} loading={refreshing} onClick={onRefresh}>
            {refreshing ? "Yig'ilmoqda..." : "Yangilash"}
          </Button>
        }
      />

      <div className="space-y-6">
        <StatusStrip cs={cs} tg={tg} loading={statusLoading} lastNew={lastNew} />

        {/* Kategoriyalar */}
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
          {catCards.map((c, i) => (
            <CategoryCard
              key={c.key || "all"}
              index={i}
              label={c.label}
              icon={c.icon}
              tone={c.tone}
              count={c.count}
              share={c.key === "" ? (totalAll ? 1 : 0) : totalAll ? (c.count ?? 0) / totalAll : 0}
              active={cat === c.key}
              onClick={() => setCat(c.key)}
            />
          ))}
        </div>

        {/* Qidiruv */}
        <form
          onSubmit={(ev) => {
            ev.preventDefault();
            const v = qInput.trim();
            if (v === q) load(v, cat);
            else setQ(v);
          }}
          className="flex flex-col gap-3 sm:flex-row sm:items-center"
        >
          <div className="relative flex-1">
            <Input
              icon={Search}
              inputSize="lg"
              value={qInput}
              onChange={(ev) => setQInput(ev.target.value)}
              placeholder="Kalit so'z bo'yicha qidirish: bank, .uz, Toshkent, uzcard..."
              className="!pr-10"
              aria-label="Hodisalarni qidirish"
            />
            {qInput && (
              <button
                type="button"
                onClick={() => {
                  setQInput("");
                  setQ("");
                }}
                className="absolute right-3 top-1/2 grid h-6 w-6 -translate-y-1/2 place-items-center rounded-md text-slate-500 transition hover:bg-white/[0.06] hover:text-slate-200"
                aria-label="Tozalash"
              >
                <X className="h-4 w-4" />
              </button>
            )}
          </div>
          <div className="flex shrink-0 items-center gap-2 text-xs text-slate-500">
            {loading ? (
              <Skeleton className="h-4 w-36" />
            ) : (
              <span>
                <span className="font-mono tabular-nums text-slate-300">{fmt(total)}</span> ta natija
                {activeMeta && (
                  <>
                    {" "}
                    · <span className={ICON_TEXT[activeMeta.tone]}>{activeMeta.label}</span>
                  </>
                )}
                {q && (
                  <>
                    {" "}
                    · <span className="font-mono text-cyan-300">&quot;{q}&quot;</span>
                  </>
                )}
              </span>
            )}
          </div>
        </form>

        {error && <ErrorBanner message={error} />}

        {/* Lenta */}
        {loading ? (
          <FeedSkeleton />
        ) : items.length === 0 ? (
          !error && (
            <Card>
              {q ? (
                <EmptyState
                  icon={Search}
                  title={`"${q}" bo'yicha hech narsa topilmadi`}
                  description="Boshqa kalit so'z bilan urinib ko'ring yoki kategoriya filtrini o'zgartiring."
                  action={
                    <Button
                      variant="secondary"
                      size="sm"
                      icon={X}
                      onClick={() => {
                        setQInput("");
                        setQ("");
                      }}
                    >
                      Qidiruvni tozalash
                    </Button>
                  }
                />
              ) : (
                <EmptyState
                  icon={activeMeta?.icon ?? Radar}
                  title={empty.title}
                  description={empty.description}
                  action={
                    <Button variant="secondary" size="sm" icon={RefreshCw} loading={refreshing} onClick={onRefresh}>
                      Hozir yig'ish
                    </Button>
                  }
                />
              )}
            </Card>
          )
        ) : (
          <div className="space-y-6">
            {groups.map((g) => (
              <section key={g.key + g.items[0].idx}>
                <div className="sticky top-16 z-10 -mx-1 mb-3 px-1 py-2">
                  <div className="inline-flex items-center gap-2 rounded-full border border-white/[0.08] bg-ink-900/85 px-3 py-1 shadow-card backdrop-blur-xl">
                    <CalendarDays className="h-3.5 w-3.5 text-brand-cyan" />
                    <span className="text-xs font-semibold text-slate-200">{g.label}</span>
                    <span className="font-mono text-[11px] tabular-nums text-slate-500">{g.items.length}</span>
                  </div>
                </div>
                <ol className="relative space-y-3">
                  <div className="pointer-events-none absolute bottom-0 left-4 top-0 w-px bg-gradient-to-b from-brand-cyan/30 via-white/[0.08] to-white/[0.03] sm:left-5" />
                  {g.items.map(({ e, idx }) => (
                    <EventCard
                      key={`${e.url}-${idx}`}
                      e={e}
                      query={q}
                      delay={Math.min(idx % PAGE_SIZE, 12) * 40}
                    />
                  ))}
                </ol>
              </section>
            ))}

            <div className="flex flex-col items-center gap-2 pt-2">
              {hasMore ? (
                <Button variant="secondary" icon={ChevronDown} loading={loadingMore} onClick={loadMore}>
                  Ko&apos;proq yuklash
                </Button>
              ) : (
                <div className="flex items-center gap-2 text-xs text-slate-600">
                  <span className="h-px w-10 bg-white/[0.08]" />
                  Lenta oxiri
                  <span className="h-px w-10 bg-white/[0.08]" />
                </div>
              )}
              <div className="font-mono text-[11px] tabular-nums text-slate-600">
                {fmt(items.length)} / {fmt(total)}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
