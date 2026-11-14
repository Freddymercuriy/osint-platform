"use client";

import { CalendarDays, ChevronDown, Radar, RefreshCw, Search, X } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Button, Card, EmptyState, ErrorBanner, Input, PageHeader, Select, Skeleton } from "@/components/ui";
import { EventCard, eventTime } from "@/components/events/EventCard";
import { StatusStrip } from "@/components/events/StatusStrip";
import {
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
import { useCategories } from "@/lib/useCategories";
import { useFormat } from "@/lib/format";
import { cn } from "@/lib/cn";

const PAGE_SIZE = 40;
type Scope = NonNullable<EventFilters["scope"]>;
const SCOPES: Scope[] = ["regional", "global", "all"];

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

export default function EventsPage() {
  const t = useTranslations("events");
  const tc = useTranslations("common");
  const ts = useTranslations("scope");
  const locale = useLocale();
  const f = useFormat();
  const { list: categories } = useCategories();

  const [items, setItems] = useState<EventItem[]>([]);
  const [total, setTotal] = useState(0);
  const [qInput, setQInput] = useState("");
  const [q, setQ] = useState("");
  const [cat, setCat] = useState("");
  const [scope, setScope] = useState<Scope>("regional");
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

  const filters = useCallback(
    (query: string, category: string, sc: Scope): EventFilters => ({
      q: query || undefined,
      category: category ? [category] : undefined,
      scope: sc,
    }),
    [],
  );

  const load = useCallback(
    async (query: string, category: string, sc: Scope) => {
      const id = ++reqId.current;
      setLoading(true);
      setError(null);
      try {
        const res = await getEvents({ filters: filters(query, category, sc), lang: locale, limit: PAGE_SIZE });
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
    },
    [filters, locale, tc],
  );

  async function loadMore() {
    const id = reqId.current;
    setLoadingMore(true);
    try {
      const res = await getEvents({
        filters: filters(q, cat, scope),
        lang: locale,
        limit: PAGE_SIZE,
        offset: items.length,
      });
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
      await Promise.all([load(q, cat, scope), loadStatus()]);
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

  // Qidiruv — 400ms debounce
  useEffect(() => {
    const id = setTimeout(() => setQ(qInput.trim()), 400);
    return () => clearTimeout(id);
  }, [qInput]);

  useEffect(() => {
    load(q, cat, scope);
  }, [q, cat, scope, load]);

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

  const hasMore = items.length < total;
  const clearSearch = () => {
    setQInput("");
    setQ("");
  };

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

        <div className="flex flex-col gap-3 lg:flex-row lg:items-center">
          <form
            role="search"
            onSubmit={(ev) => {
              ev.preventDefault();
              const v = qInput.trim();
              if (v === q) load(v, cat, scope);
              else setQ(v);
            }}
            className="relative min-w-0 flex-1"
          >
            <Input
              icon={Search}
              value={qInput}
              onChange={(ev) => setQInput(ev.target.value)}
              placeholder={t("searchPlaceholder")}
              className="!pr-10"
              aria-label={t("searchAria")}
            />
            {qInput && (
              <button
                type="button"
                onClick={clearSearch}
                className="focus-ring absolute right-2.5 top-1/2 grid h-6 w-6 -translate-y-1/2 place-items-center rounded-md text-fg-muted hover:bg-surface-2 hover:text-fg"
                aria-label={t("clear")}
              >
                <X className="h-4 w-4" aria-hidden />
              </button>
            )}
          </form>
          <Select
            value={cat}
            onChange={(ev) => setCat(ev.target.value)}
            aria-label={t("categoryAria")}
            className="lg:w-56"
          >
            <option value="">{t("allCategories")}</option>
            {categories.map((c) => (
              <option key={c.slug} value={c.slug}>
                {c.name}
              </option>
            ))}
          </Select>
          <div
            role="group"
            aria-label={ts("label")}
            className="inline-flex shrink-0 overflow-hidden rounded-lg border border-border bg-surface"
          >
            {SCOPES.map((s) => (
              <button
                key={s}
                type="button"
                aria-pressed={scope === s}
                onClick={() => setScope(s)}
                className={cn(
                  "focus-ring h-10 flex-1 px-3 text-sm font-medium transition-colors",
                  scope === s ? "bg-primary text-primary-fg" : "text-fg-muted hover:bg-surface-2 hover:text-fg",
                )}
              >
                {ts(s)}
              </button>
            ))}
          </div>
        </div>

        <div className="text-xs text-fg-muted">
          {loading ? (
            <Skeleton className="h-4 w-36" />
          ) : (
            <span>
              {t("results", { count: total })}
              {q && <span className="font-mono"> · &quot;{q}&quot;</span>}
            </span>
          )}
        </div>

        {error && <ErrorBanner message={error} action={
          <Button variant="secondary" size="sm" onClick={() => load(q, cat, scope)}>{tc("retry")}</Button>
        } />}

        {loading ? (
          <FeedSkeleton />
        ) : items.length === 0 ? (
          !error && (
            <Card>
              {q ? (
                <EmptyState
                  icon={Search}
                  title={t("emptySearchTitle", { q })}
                  description={t("emptySearchDesc")}
                  action={
                    <Button variant="secondary" size="sm" icon={X} onClick={clearSearch}>
                      {t("clearSearch")}
                    </Button>
                  }
                />
              ) : (
                <EmptyState
                  icon={Radar}
                  title={t("emptyTitle")}
                  description={
                    <>
                      {t("emptyWhat")} {cat || scope !== "regional" ? t("emptyWhyFilters") : t("emptyWhySince")}
                    </>
                  }
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
                    <EventCard key={`${e.id ?? e.url}-${idx}`} e={e} query={q} />
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
