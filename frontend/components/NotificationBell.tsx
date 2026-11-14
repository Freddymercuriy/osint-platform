"use client";

import { Bell, CheckCheck, ExternalLink } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { CategoryBadge, EmptyState } from "@/components/ui";
import { getNotifications, markNotificationsRead, type NotificationsResponse } from "@/lib/api";
import { cn } from "@/lib/cn";
import { useFormat } from "@/lib/format";

const POLL_MS = 60_000;

export default function NotificationBell({ onUnreadChange }: { onUnreadChange?: (n: number) => void }) {
  const t = useTranslations("notifications");
  const tc = useTranslations("common");
  const locale = useLocale();
  const f = useFormat();
  const [data, setData] = useState<NotificationsResponse | null>(null);
  const [open, setOpen] = useState(false);
  const boxRef = useRef<HTMLDivElement>(null);
  const btnRef = useRef<HTMLButtonElement>(null);

  const load = useCallback(async () => {
    try {
      const res = await getNotifications(20, locale);
      setData(res);
      onUnreadChange?.(res.unread);
      const app = tc("appName");
      document.title = res.unread > 0 ? `(${res.unread}) ${app}` : app;
    } catch {
      /* tarmoq xatosi — keyingi tsiklda qayta urinadi */
    }
  }, [onUnreadChange, locale, tc]);

  useEffect(() => {
    load();
    const id = setInterval(() => document.visibilityState === "visible" && load(), POLL_MS);
    return () => clearInterval(id);
  }, [load]);

  useEffect(() => {
    if (!open) return;
    function onClick(e: MouseEvent) {
      if (boxRef.current && !boxRef.current.contains(e.target as Node)) setOpen(false);
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") {
        setOpen(false);
        btnRef.current?.focus();
      }
    }
    document.addEventListener("mousedown", onClick);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onClick);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  async function markRead() {
    await markNotificationsRead();
    await load();
  }

  const unread = data?.unread ?? 0;

  return (
    <div className="relative" ref={boxRef}>
      <button
        ref={btnRef}
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-label={t("open")}
        aria-expanded={open}
        aria-haspopup="dialog"
        className={cn(
          "focus-ring relative grid h-9 w-9 place-items-center rounded-lg border border-border bg-surface text-fg-muted transition-colors hover:bg-surface-2 hover:text-fg",
          open && "bg-surface-2 text-fg",
        )}
      >
        <Bell className="h-4 w-4" aria-hidden />
        {unread > 0 && (
          <span className="absolute right-0 top-0 grid h-4 min-w-4 -translate-y-1/3 translate-x-1/3 place-items-center rounded-full bg-danger px-1 text-[10px] font-bold leading-none text-bg">
            {unread > 99 ? "99+" : unread}
          </span>
        )}
      </button>

      {open && (
        <div
          role="dialog"
          aria-label={t("title")}
          className="card absolute right-0 z-50 mt-2 w-[26rem] max-w-[calc(100vw-2rem)] animate-fade-in overflow-hidden shadow-lg"
        >
          <div className="flex items-center justify-between gap-3 border-b border-border px-4 py-3">
            <div>
              <div className="text-sm font-semibold text-fg">{t("title")}</div>
              {unread > 0 && <div className="text-xs text-fg-muted">{t("unread", { count: unread })}</div>}
            </div>
            {unread > 0 && (
              <button type="button" onClick={markRead} className="focus-ring inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs text-primary hover:bg-primary-soft">
                <CheckCheck className="h-3.5 w-3.5" aria-hidden /> {t("markAllRead")}
              </button>
            )}
          </div>

          <div className="max-h-[26rem] overflow-y-auto">
            {!data?.items.length ? (
              <EmptyState icon={Bell} title={t("empty")} description={t("emptyHint")} />
            ) : (
              data.items.map((n) => (
                <a
                  key={n.id}
                  href={n.url}
                  target="_blank"
                  rel="noreferrer"
                  className={cn(
                    "focus-ring group block border-b border-border px-4 py-3 transition-colors last:border-0 hover:bg-surface-2",
                    n.is_new && "bg-primary-soft/60",
                  )}
                >
                  <div className="flex items-center gap-2">
                    {n.is_new && <span className="sr-only">{t("new")}</span>}
                    {n.is_new && <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-danger" aria-hidden />}
                    <CategoryBadge category={n.category} />
                    <span className="truncate text-xs text-fg-subtle">{n.source}</span>
                    <span className="ml-auto shrink-0 text-xs text-fg-subtle">{f.ago(n.first_seen)}</span>
                  </div>
                  <div className="mt-1.5 flex items-start gap-2">
                    <span className="line-clamp-2 flex-1 text-sm leading-snug text-fg">{n.title}</span>
                    <ExternalLink className="mt-0.5 h-3.5 w-3.5 shrink-0 text-fg-subtle" aria-hidden />
                  </div>
                </a>
              ))
            )}
          </div>

          <Link
            href="/dashboard/events"
            onClick={() => setOpen(false)}
            className="focus-ring block border-t border-border px-4 py-2.5 text-center text-sm text-primary transition-colors hover:bg-surface-2"
          >
            {t("allEvents")} →
          </Link>
        </div>
      )}
    </div>
  );
}
