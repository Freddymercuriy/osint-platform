"use client";

import { ArrowUpRight, Hash, Languages, Link2, Pencil, User } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { useState } from "react";
import { Badge, Button, CategoryBadge, Select, SeverityBadge } from "@/components/ui";
import { setEventCategory } from "@/lib/adminApi";
import { useCategories, type CategoryView } from "@/lib/useCategories";
import { CHANNEL_META, type Tone } from "@/lib/categories";
import { useFormat } from "@/lib/format";
import type { EventItem } from "@/lib/api";
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

  return (
    <li>
      <article className="card p-4 transition-colors hover:border-border-strong sm:p-5">
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1.5 text-xs">
          <FilterChip label={bySlug(e.category).name} onClick={onFilter && (() => onFilter("category", e.category))}>
            <CategoryBadge category={e.category} />
          </FilterChip>
          {e.severity && (
            <FilterChip label={tsev(e.severity)} onClick={onFilter && (() => onFilter("severity", e.severity!))}>
              <SeverityBadge severity={e.severity} />
            </FilterChip>
          )}
          <PriorityBadge e={e} />
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
          {when && (
            <span className="ml-auto flex items-center gap-1.5 text-fg-muted" title={f.dateTime(when)}>
              <span className="font-mono tabular-nums">{f.time(when)}</span>
              <span>{f.ago(when)}</span>
            </span>
          )}
        </div>

        <h3 className="mt-2.5 line-clamp-3 font-semibold leading-snug text-fg">
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
                className="focus-ring ml-auto inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium text-primary hover:bg-primary-soft"
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
      </article>
    </li>
  );
}

