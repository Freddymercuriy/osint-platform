"use client";

import {
  ArrowUpRight,
  Bug,
  Cpu,
  Hash,
  Landmark,
  Languages,
  Link2,
  Newspaper,
  Pencil,
  RadioTower,
  ShieldAlert,
  Sparkles,
  TrendingUp,
  User,
  type LucideIcon,
} from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import { Badge, Button, CategoryBadge, Select, SeverityBadge } from "@/components/ui";
import { setEventCategory } from "@/lib/adminApi";
import { useCategories, type CategoryView } from "@/lib/useCategories";
import { CHANNEL_META, type Tone } from "@/lib/categories";
import { useFormat } from "@/lib/format";
import type { EventItem } from "@/lib/api";
import { API_URL } from "@/lib/config";
import { PriorityBadge } from "@/components/events/PriorityBadge";

export function eventTime(e: EventItem): string | null {
  return e.published || e.first_seen || null;
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
          <mark key={i} className="rounded bg-primary-soft px-0.5 text-primary">
            {p}
          </mark>
        ) : (
          <span key={i}>{p}</span>
        ),
      )}
    </>
  );
}

const RUBRIC_ICON: Record<string, LucideIcon> = {
  cyber: ShieldAlert,
  vulnerability: Bug,
  ai: Sparkles,
  tech: Cpu,
  telecom: RadioTower,
  economy: TrendingUp,
  politics: Landmark,
};

/** "CyberScoop (NewsNow)" -> "CyberScoop" */
function outletName(source: string): string {
  return source.replace(/\s*\([^)]*\)\s*$/, "").trim() || source;
}

/** Faqat haqiqatan ahamiyatli jiddiylik / ustuvorlik rasm ustida ko'rsatiladi. */
const LOUD = new Set(["critical", "high", "medium"]);

/** 16:9 rasm bloki: rasm yo'q yoki yuklanmasa — token asosidagi o'rinbosar. */
function CardImage({
  e,
  title,
  rubricLabel,
  Icon,
  children,
}: {
  e: EventItem;
  title: string;
  rubricLabel: string | null;
  Icon: LucideIcon;
  children?: React.ReactNode;
}) {
  const tcard = useTranslations("events.card");
  const thumb = e.image?.thumb;
  const src = thumb ? `${API_URL}${thumb}` : null;
  const [failed, setFailed] = useState(false);
  useEffect(() => setFailed(false), [src]);
  const showImg = !!src && !failed;
  const kind = e.image?.kind;
  // maqolaning o'z rasmi — manba; platforma chizgani — "Illyustratsiya" (haqiqiy foto deb o'ylanmasin)
  const credit = !kind ? null : kind === "source" ? (e.source ? tcard("photoCredit", { source: outletName(e.source) }) : null) : tcard("illustration");

  return (
    <div className="relative">
      <div className="relative aspect-video w-full overflow-hidden rounded-t-xl border-b border-border bg-surface-2">
        {showImg ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={src}
            alt={title}
            loading="lazy"
            decoding="async"
            onError={() => setFailed(true)}
            className="h-full w-full object-cover"
          />
        ) : (
          <div
            className="flex h-full w-full items-center justify-center bg-gradient-to-br from-primary-soft via-surface-2 to-surface"
            role="img"
            aria-label={title}
          >
            <Icon className="h-12 w-12 text-fg-subtle" strokeWidth={1.25} aria-hidden />
          </div>
        )}
        {showImg && (
          <div className="pointer-events-none absolute inset-x-0 bottom-0 h-1/3 rounded-b-none bg-gradient-to-t from-black/60 to-transparent" aria-hidden />
        )}
      </div>
      {showImg && credit && (
        <span className="absolute bottom-2 left-2 max-w-[70%] truncate rounded bg-black/60 px-1.5 py-0.5 text-[11px] font-medium text-white">
          {credit}
        </span>
      )}
      {rubricLabel && (
        <span className="absolute left-2 top-2 inline-flex max-w-[65%] items-center gap-1 rounded-full bg-black/65 px-2.5 py-1 text-xs font-semibold text-white">
          <Icon className="h-3 w-3 shrink-0" aria-hidden />
          <span className="truncate">{rubricLabel}</span>
        </span>
      )}
      {children && <div className="absolute right-2 top-2 flex max-w-[55%] flex-wrap items-center justify-end gap-1.5">{children}</div>}
    </div>
  );
}

export type FilterKey = "category" | "severity" | "country" | "channel" | "source";

/** Bosiladigan "chip": bosilganda filtr qo'shiladi. */
function FilterChip({ label, onClick, children }: { label: string; onClick?: () => void; children: React.ReactNode }) {
  const t = useTranslations("events.card");
  if (!onClick) return <>{children}</>;
  return (
    <button
      type="button"
      onClick={onClick}
      title={t("addFilter", { label })}
      aria-label={t("addFilter", { label })}
      className="focus-ring rounded-full transition-opacity hover:opacity-80"
    >
      {children}
    </button>
  );
}

export function EventCard({
  e,
  query,
  onFilter,
  isAdmin,
  categories,
  onUpdated,
}: {
  e: EventItem;
  query: string;
  onFilter?: (key: FilterKey, value: string) => void;
  isAdmin?: boolean;
  categories?: CategoryView[];
  onUpdated?: (next: EventItem) => void;
}) {
  const tcard = useTranslations("events.card");
  const [editing, setEditing] = useState(false);
  const [newCat, setNewCat] = useState(e.category);
  const [saving, setSaving] = useState(false);
  const [catErr, setCatErr] = useState<string | null>(null);
  const [savedMsg, setSavedMsg] = useState(false);

  async function saveCategory() {
    if (e.id == null || !newCat || newCat === e.category) {
      setEditing(false);
      return;
    }
    setSaving(true);
    setCatErr(null);
    try {
      const res = await setEventCategory(e.id, newCat);
      onUpdated?.({ ...e, category: res.category ?? newCat, category_id: res.category_id ?? e.category_id });
      setEditing(false);
      setSavedMsg(true);
    } catch (err) {
      setCatErr(err instanceof Error ? err.message : "");
    } finally {
      setSaving(false);
    }
  }

  const t = useTranslations("events");
  const tc = useTranslations("common");
  const tch = useTranslations("channel");
  const tco = useTranslations("country");
  const locale = useLocale();
  const f = useFormat();
  const tsev = useTranslations("severity");
  const { bySlug } = useCategories();
  const [showOrig, setShowOrig] = useState(false);

  const origTitle = e.original_title ?? "";
  const hasOriginal = !!e.translated || (!!origTitle && origTitle !== e.title);
  const title = (showOrig && hasOriginal ? origTitle || e.title : e.title) || t("untitled");
  const summary = showOrig && hasOriginal ? e.original_summary || e.summary : e.summary;
  const pending =
    (e.translation_status === "pending" || e.translation_status === "skipped") &&
    !!e.source_lang &&
    e.display_lang === e.source_lang &&
    e.source_lang !== locale;

  const when = eventTime(e);
  const keywords = (e.matched_keywords ?? []).slice(0, 6);
  const chMeta = e.channel ? CHANNEL_META[e.channel] : undefined;
  const ChIcon = chMeta?.icon;
  const also = e.also_reported_by ?? [];
  const countries = e.countries ?? [];
  const trub = useTranslations("events.rubric");
  const rubricLabel = e.rubric && trub.has(e.rubric) ? trub(e.rubric) : null;
  const RubricIcon = (e.rubric && RUBRIC_ICON[e.rubric]) || Newspaper;

  return (
    <li className="h-full">
      <article className="card flex h-full flex-col overflow-visible transition-colors hover:border-border-strong">
        <CardImage e={e} title={title} rubricLabel={rubricLabel} Icon={RubricIcon}>
          {e.severity && LOUD.has(e.severity) && (
            <FilterChip label={tsev(e.severity)} onClick={onFilter && (() => onFilter("severity", e.severity!))}>
              <SeverityBadge severity={e.severity} />
            </FilterChip>
          )}
          {e.priority_band && LOUD.has(e.priority_band) && <PriorityBadge e={e} align="right" />}
        </CardImage>

        <div className="flex flex-1 flex-col p-4 sm:p-5">
          <div className="flex flex-wrap items-center gap-x-2 gap-y-1.5 text-xs">
            <FilterChip label={bySlug(e.category).name} onClick={onFilter && (() => onFilter("category", e.category))}>
              <CategoryBadge category={e.category} />
            </FilterChip>
            {e.severity && !LOUD.has(e.severity) && (
              <FilterChip label={tsev(e.severity)} onClick={onFilter && (() => onFilter("severity", e.severity!))}>
                <SeverityBadge severity={e.severity} />
              </FilterChip>
            )}
            {!(e.priority_band && LOUD.has(e.priority_band)) && <PriorityBadge e={e} />}
            {e.channel && chMeta && ChIcon && (
              <FilterChip label={tch.has(e.channel) ? tch(e.channel) : e.channel} onClick={onFilter && (() => onFilter("channel", e.channel!))}>
                <Badge tone={chMeta.tone as Tone} icon={ChIcon}>
                  {tch.has(e.channel) ? tch(e.channel) : e.channel}
                </Badge>
              </FilterChip>
            )}
            {countries.map((c) => (
              <FilterChip key={c} label={tco.has(c) ? tco(c) : c} onClick={onFilter && (() => onFilter("country", c))}>
                <Badge tone="slate">{tco.has(c) ? tco(c) : c}</Badge>
              </FilterChip>
            ))}
          </div>

          <h3 className="mt-3 line-clamp-3 text-base font-bold leading-snug text-fg sm:text-lg">
            {e.url ? (
              <a href={e.url} target="_blank" rel="noreferrer" className="hover:text-primary focus-ring rounded-sm">
                <Highlight text={title} query={query} />
              </a>
            ) : (
              <Highlight text={title} query={query} />
            )}
          </h3>

          {summary && (
            <p className="mt-1.5 line-clamp-3 text-sm leading-relaxed text-fg-muted">
              <Highlight text={summary} query={query} />
            </p>
          )}

          <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-2 text-xs text-fg-muted">
            {e.source &&
              (onFilter && e.source_id != null ? (
                <button
                  type="button"
                  onClick={() => onFilter("source", String(e.source_id))}
                  title={tcard("addFilter", { label: e.source })}
                  aria-label={tcard("addFilter", { label: e.source })}
                  className="focus-ring max-w-[16rem] truncate rounded-md border border-border px-1.5 py-0.5 font-mono hover:border-border-strong hover:text-fg"
                >
                  {e.source}
                </button>
              ) : (
                <span className="max-w-[16rem] truncate font-mono" title={e.source}>
                  {e.source}
                </span>
              ))}
            {when && (
              <span className="flex items-center gap-1.5" title={f.dateTime(when)}>
                <span className="font-mono tabular-nums">{f.time(when)}</span>
                <span>{f.ago(when)}</span>
              </span>
            )}
            {e.actor && (
              <span className="inline-flex items-center gap-1" title={t("actorHint")}>
                <User className="h-3.5 w-3.5" aria-hidden />
                <span className="font-mono text-fg">{e.actor}</span>
              </span>
            )}
            {keywords.map((k) => (
              <span
                key={k}
                className="inline-flex items-center gap-0.5 rounded-md border border-border bg-surface-2 px-1.5 py-0.5 font-mono text-[11px]"
              >
                <Hash className="h-3 w-3" aria-hidden />
                {k}
              </span>
            ))}
          </div>

          {pending && (
            <p className="mt-2 flex items-center gap-1.5 text-xs text-fg-muted">
              <Languages className="h-3.5 w-3.5 shrink-0" aria-hidden />
              {tc("notTranslated")}
            </p>
          )}

          {also.length > 0 && (
            <details className="group mt-2 text-xs text-fg-muted">
              <summary className="focus-ring inline-flex cursor-pointer list-none items-center gap-1.5 rounded-sm hover:text-fg">
                <Link2 className="h-3.5 w-3.5" aria-hidden />
                {t("alsoReported", { count: also.length })}
              </summary>
              <ul className="mt-1.5 space-y-1 border-l border-border pl-3">
                {also.map((a, i) => (
                  <li key={`${a.source}-${i}`} className="flex flex-wrap gap-x-2">
                    {a.url ? (
                      <a href={a.url} target="_blank" rel="noreferrer" className="font-mono text-primary hover:underline">
                        {a.source}
                      </a>
                    ) : (
                      <span className="font-mono">{a.source}</span>
                    )}
                    {a.at && <span>{f.ago(a.at)}</span>}
                  </li>
                ))}
              </ul>
            </details>
          )}

          <div className="flex-1" />
          {(hasOriginal || e.url || (isAdmin && e.id != null)) && (
            <div className="mt-3 flex flex-wrap items-center gap-2 border-t border-border pt-2.5">
              {isAdmin && e.id != null && !editing && (
                <button
                  type="button"
                  onClick={() => {
                    setNewCat(e.category);
                    setSavedMsg(false);
                    setEditing(true);
                  }}
                  className="focus-ring inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-xs font-medium text-fg-muted hover:bg-surface-2 hover:text-fg"
                >
                  <Pencil className="h-3.5 w-3.5" aria-hidden />
                  {tcard("changeCategory")}
                </button>
              )}
              {hasOriginal && (
                <button
                  type="button"
                  onClick={() => setShowOrig((v) => !v)}
                  className="focus-ring inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-xs font-medium text-fg-muted hover:bg-surface-2 hover:text-fg"
                >
                  <Languages className="h-3.5 w-3.5" aria-hidden />
                  {showOrig ? tc("showTranslation") : tc("showOriginal")}
                </button>
              )}
              {e.url && (
                <a
                  href={e.url}
                  target="_blank"
                  rel="noreferrer"
                  className="focus-ring ml-auto inline-flex items-center gap-1 rounded-md border border-border px-2.5 py-1 text-xs font-semibold text-primary hover:border-border-strong hover:bg-primary-soft"
                >
                  {t("openSource")}
                  <ArrowUpRight className="h-3.5 w-3.5" aria-hidden />
                </a>
              )}
            </div>
          )}
          {isAdmin && editing && (
            <div
              className="mt-2 space-y-2 rounded-lg border border-border bg-surface-2 p-3"
              onKeyDown={(ev) => ev.key === "Escape" && setEditing(false)}
            >
              <div className="flex flex-wrap items-center gap-2">
                <Select
                  autoFocus
                  value={newCat}
                  onChange={(ev) => setNewCat(ev.target.value)}
                  aria-label={tcard("chooseCategory")}
                  className="!h-9 min-w-0 flex-1 sm:max-w-xs"
                >
                  {(categories ?? []).map((c) => (
                    <option key={c.slug} value={c.slug}>
                      {c.name}
                    </option>
                  ))}
                </Select>
                <Button size="sm" loading={saving} onClick={saveCategory} disabled={newCat === e.category}>
                  {tcard("save")}
                </Button>
                <Button size="sm" variant="ghost" onClick={() => setEditing(false)}>
                  {tc("cancel")}
                </Button>
              </div>
              <p className="text-xs text-fg-muted">{tcard("lockedHint")}</p>
              {catErr && (
                <p role="alert" className="text-xs text-danger">
                  {catErr}
                </p>
              )}
            </div>
          )}
          {savedMsg && !editing && (
            <p role="status" className="mt-2 text-xs text-success">
              {tcard("saved")}
            </p>
          )}
        </div>
      </article>
    </li>
  );
}

