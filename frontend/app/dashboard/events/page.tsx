"use client";

import { CalendarDays, ChevronDown, Radar, RefreshCw, Search, X } from "lucide-react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import { Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Button, Card, EmptyState, ErrorBanner, PageHeader, Skeleton } from "@/components/ui";
import { EventCard, eventTime, type FilterKey } from "@/components/events/EventCard";
import { EventFilterBar, SCOPES, type Scope } from "@/components/events/EventFilterBar";
import { StatusStrip } from "@/components/events/StatusStrip";
import {
  eventFiltersToParams,
  getCollectorStatus,
  getEvents,
  getMe,
  getTgStatus,
  refreshEvents,
  type CollectorStatus,
  type EventFilters,
  type EventItem,
  type TgStatus,
} from "@/lib/api";
import { getEventFacets, type EventFacets } from "@/lib/adminApi";
import { useCategories } from "@/lib/useCategories";
import { useFormat } from "@/lib/format";

const PAGE_SIZE = 40;
const LIST_KEYS = ["category", "severity", "country", "channel", "source", "source_lang"] as const;
const DATE_RE = /^\d{4}-\d{2}-\d{2}$/;

/** URL query -> filtrlar (API bilan bir xil nomlar, ro'yxatlar vergul bilan). */
function parseFilters(sp: URLSearchParams): { filters: EventFilters; scope: Scope } {
  const filters: EventFilters = {};
  for (const k of LIST_KEYS) {
    const v = (sp.get(k) ?? "").split(",").map((x) => x.trim()).filter(Boolean);
    if (v.length) filters[k] = v;
  }
  const q = (sp.get("q") ?? "").trim();
  if (q) filters.q = q;
  const from = sp.get("date_from");
  const to = sp.get("date_to");
  if (from && DATE_RE.test(from)) filters.date_from = from;
  if (to && DATE_RE.test(to)) filters.date_to = to;
  const sc = sp.get("scope");
  const scope = (SCOPES as string[]).includes(sc ?? "") ? (sc as Scope) : "regional";
  return { filters, scope };
}

function dayKey(iso: string | null): string {
  if (!iso) return "none";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "none";
  return `${d.getFullYear()}-${d.getMonth()}-${d.getDate()}`;
}

function FeedSkeleton() {
  return (
    <ul className="space-y-3" aria-hidden>
      {Array.from({ length: 5 }).map((_, i) => (
        <li key={i}>
          <Card className="space-y-3 p-5">
            <div className="flex items-center gap-2">
              <Skeleton className="h-5 w-20 rounded-full" />
              <Skeleton className="h-5 w-16 rounded-full" />
              <Skeleton className="ml-auto h-4 w-16" />
            </div>
            <Skeleton className="h-5 w-4/5" />
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-2/3" />
          </Card>
        </li>
      ))}
    </ul>
  );
}

function EventsView() {
  const t = useTranslations("events");
  const tc = useTranslations("common");
  const locale = useLocale();
  const f = useFormat();
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const { list: categories } = useCategories();

  const spKey = searchParams.toString();
  const { filters, scope } = useMemo(() => parseFilters(new URLSearchParams(spKey)), [spKey]);
  const effective = useMemo<EventFilters>(() => ({ ...filters, scope }), [filters, scope]);
  const queryKey = useMemo(() => eventFiltersToParams(effective).toString(), [effective]);

  const [items, setItems] = useState<EventItem[]>([]);
  const [total, setTotal] = useState(0);
  const [qInput, setQInput] = useState(filters.q ?? "");
  const [facets, setFacets] = useState<EventFacets | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [cs, setCs] = useState<CollectorStatus | null>(null);
  const [tg, setTg] = useState<TgStatus | null>(null);
  const [isAdmin, setIsAdmin] = useState(false);
  const [statusLoading, setStatusLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [lastNew, setLastNew] = useState<number | null>(null);
  const reqId = useRef(0);
  const lastQ = useRef(filters.q ?? "");
  const spRef = useRef(spKey);
  spRef.current = spKey;

  /** Filtrlarni URL ga yozish (skrollsiz). */
  const setFilters = useCallback(
    (patch: Partial<EventFilters>) => {
      const p = new URLSearchParams(spRef.current);
      for (const [k, v] of Object.entries(patch)) {
        if (v === undefined || v === "" || (Array.isArray(v) && v.length === 0) || (k === "scope" && v === "regional")) {
          p.delete(k);
        } else p.set(k, Array.isArray(v) ? v.join(",") : String(v));
      }
      const qs = p.toString();
      spRef.current = qs;
      router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
    },
    [router, pathname],
  );

  const resetAll = useCallback(() => {
    lastQ.current = "";
    setQInput("");
    spRef.current = "";
    router.replace(pathname, { scroll: false });
  }, [router, pathname]);

  const addFilter = useCallback(
    (key: FilterKey, value: string) => {
      const cur = filters[key] ?? [];
      if (!cur.includes(value)) setFilters({ [key]: [...cur, value] });
    },
    [filters, setFilters],
  );

  const loadStatus = useCallback(async () => {
    // Telegram akkaunt ma'lumotlari va yangilash faqat admin uchun (backend 403 qaytaradi)
    const admin = await getMe().then((m) => m.role === "admin", () => false);
    setIsAdmin(admin);
    const [c, g] = await Promise.allSettled([
      getCollectorStatus(),
      admin ? getTgStatus() : Promise.reject(new Error("not admin")),
    ]);
    setCs(c.status === "fulfilled" ? c.value : null);
    setTg(g.status === "fulfilled" ? g.value : null);
    setStatusLoading(false);
  }, []);

  const load = useCallback(async () => {
    const id = ++reqId.current;
    setLoading(true);
    setError(null);
    try {
      const res = await getEvents({ filters: effective, lang: locale, limit: PAGE_SIZE });
      if (id !== reqId.current) return;
      setItems(res.items);
      setTotal(res.count);
    } catch (err) {
      if (id !== reqId.current) return;
      setError(err instanceof Error ? err.message : tc("error"));
      setItems([]);
      setTotal(0);
    } finally {
      if (id === reqId.current) setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [queryKey, locale, tc]);

  async function loadMore() {
    const id = reqId.current;
    setLoadingMore(true);
    try {
      const res = await getEvents({ filters: effective, lang: locale, limit: PAGE_SIZE, offset: items.length });
      if (id !== reqId.current) return;
      setItems((prev) => [...prev, ...res.items]);
      setTotal(res.count);
    } catch (err) {
      setError(err instanceof Error ? err.message : tc("error"));
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
      await Promise.all([load(), loadStatus(), getEventFacets().then(setFacets, () => {})]);
    } catch (err) {
      setError(err instanceof Error ? err.message : tc("error"));
    } finally {
      setRefreshing(false);
    }
  }

  useEffect(() => {
    loadStatus();
    const id = setInterval(loadStatus, 60_000);
    return () => clearInterval(id);
  }, [loadStatus]);

  useEffect(() => {
    getEventFacets().then(setFacets, () => setFacets(null));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  // Qidiruv — 400ms debounce, keyin URL ga
  useEffect(() => {
    const v = qInput.trim();
    if (v === (filters.q ?? "")) return;
    const id = setTimeout(() => {
      lastQ.current = v;
      setFilters({ q: v || undefined });
    }, 400);
    return () => clearTimeout(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [qInput]);

  // URL tashqaridan o'zgarsa (orqaga, havola) — qidiruv maydonini moslash
  useEffect(() => {
    const urlQ = filters.q ?? "";
    if (urlQ !== lastQ.current) {
      lastQ.current = urlQ;
      setQInput(urlQ);
    }
  }, [filters.q]);

  useEffect(() => {
    if (lastNew === null) return;
    const id = setTimeout(() => setLastNew(null), 8000);
    return () => clearTimeout(id);
  }, [lastNew]);

  const dayLabel = useCallback(
    (iso: string | null) => {
      if (!iso || dayKey(iso) === "none") return t("noDate");
      const d = new Date(iso);
      const today = new Date();
      const yest = new Date();
      yest.setDate(today.getDate() - 1);
      if (dayKey(iso) === dayKey(today.toISOString())) return t("today");
      if (dayKey(iso) === dayKey(yest.toISOString())) return t("yesterday");
      return f.date(d, { year: d.getFullYear() !== today.getFullYear() });
    },
    [f, t],
  );

  const groups = useMemo(() => {
    const out: { key: string; label: string; items: { e: EventItem; idx: number }[] }[] = [];
    items.forEach((e, idx) => {
      const when = eventTime(e);
      const key = dayKey(when);
      const last = out[out.length - 1];
      if (last && last.key === key) last.items.push({ e, idx });
      else out.push({ key, label: dayLabel(when), items: [{ e, idx }] });
    });
    return out;
  }, [items, dayLabel]);

  const updateItem = useCallback((next: EventItem) => {
    setItems((prev) => prev.map((x) => (x.id !== undefined && x.id === next.id ? next : x)));
  }, []);

  const hasMore = items.length < total;
  const filtered = Object.keys(filters).length > 0 || scope !== "regional";

  return (
    <div className="animate-fade-in">
      <PageHeader
        icon={Radar}
        tone="cyan"
        title={t("title")}
        description={t("description")}
        actions={
          isAdmin ? (
            <Button icon={RefreshCw} loading={refreshing} onClick={onRefresh}>
              {refreshing ? t("refreshing") : tc("refresh")}
            </Button>
          ) : undefined
        }
      />

      <div className="space-y-5">
        <StatusStrip cs={cs} tg={tg} loading={statusLoading} lastNew={lastNew} />

        <EventFilterBar
          filters={filters}
          scope={scope}
          qInput={qInput}
          onQInput={setQInput}
          onChange={setFilters}
          onReset={resetAll}
          facets={facets}
        />

        <div className="text-sm text-fg-muted" aria-live="polite">
          {loading ? <Skeleton className="h-4 w-36" /> : <span className="font-medium text-fg">{t("eventsCount", { count: total })}</span>}
        </div>

        {error && (
          <ErrorBanner
            message={error}
            action={
              <Button variant="secondary" size="sm" onClick={() => load()}>
                {tc("retry")}
              </Button>
            }
          />
        )}

        {loading ? (
          <FeedSkeleton />
        ) : items.length === 0 ? (
          !error && (
            <Card>
              {filtered ? (
                <EmptyState
                  icon={Search}
                  title={t("emptyFilteredTitle")}
                  description={t("emptyFilteredDesc")}
                  action={
                    <Button variant="secondary" size="sm" icon={X} onClick={resetAll}>
                      {t("resetFilters")}
                    </Button>
                  }
                />
              ) : (
                <EmptyState
                  icon={Radar}
                  title={t("emptyTitle")}
                  description={t("emptyNoneDesc")}
                  action={
                    isAdmin ? (
                      <Button variant="secondary" size="sm" icon={RefreshCw} loading={refreshing} onClick={onRefresh}>
                        {t("collectNow")}
                      </Button>
                    ) : undefined
                  }
                />
              )}
            </Card>
          )
        ) : (
          <div className="space-y-6">
            {groups.map((g) => (
              <section key={g.key + g.items[0].idx}>
                <div className="mb-3 inline-flex items-center gap-2 rounded-full border border-border bg-surface px-3 py-1">
                  <CalendarDays className="h-3.5 w-3.5 text-fg-muted" aria-hidden />
                  <h2 className="text-xs font-semibold text-fg">{g.label}</h2>
                  <span className="font-mono text-[11px] tabular-nums text-fg-muted">{g.items.length}</span>
                </div>
                <ul className="space-y-3">
                  {g.items.map(({ e, idx }) => (
                    <EventCard
                      key={`${e.id ?? e.url}-${idx}`}
                      e={e}
                      query={filters.q ?? ""}
                      onFilter={addFilter}
                      isAdmin={isAdmin}
                      categories={categories}
                      onUpdated={updateItem}
                    />
                  ))}
                </ul>
              </section>
            ))}

            <div className="flex flex-col items-center gap-2 pt-2">
              {hasMore ? (
                <Button variant="secondary" icon={ChevronDown} loading={loadingMore} onClick={loadMore}>
                  {tc("loadMore")}
                </Button>
              ) : (
                <div className="text-xs text-fg-muted">{t("feedEnd")}</div>
              )}
              <div className="font-mono text-[11px] tabular-nums text-fg-muted">
                {f.number(items.length)} / {f.number(total)}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default function EventsPage() {
  return (
    <Suspense fallback={<FeedSkeleton />}>
      <EventsView />
    </Suspense>
  );
}
