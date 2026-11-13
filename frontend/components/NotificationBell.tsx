"use client";

import { Bell, BellRing, CheckCheck, ExternalLink } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { CategoryBadge, EmptyState, timeAgo } from "@/components/ui";
import { getNotifications, markNotificationsRead, type NotificationsResponse } from "@/lib/api";
import { cn } from "@/lib/cn";

const POLL_MS = 60_000; // har daqiqada tekshiradi

export default function NotificationBell({ onUnreadChange }: { onUnreadChange?: (n: number) => void }) {
  const [data, setData] = useState<NotificationsResponse | null>(null);
  const [open, setOpen] = useState(false);
  const boxRef = useRef<HTMLDivElement>(null);

  const load = useCallback(async () => {
    try {
      const res = await getNotifications(20);
      setData(res);
      onUnreadChange?.(res.unread);
      document.title = res.unread > 0 ? `(${res.unread}) OSINT Platform` : "OSINT Platform";
    } catch {
      /* tarmoq xatosi — keyingi tsiklda qayta urinadi */
    }
  }, [onUnreadChange]);

  useEffect(() => {
    load();
    const t = setInterval(load, POLL_MS);
    return () => clearInterval(t);
  }, [load]);

  useEffect(() => {
    function onClick(e: MouseEvent) {
      if (boxRef.current && !boxRef.current.contains(e.target as Node)) setOpen(false);
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", onClick);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onClick);
      document.removeEventListener("keydown", onKey);
    };
  }, []);

  async function markRead() {
    await markNotificationsRead();
    await load();
  }

  const unread = data?.unread ?? 0;
  const Icon = unread > 0 ? BellRing : Bell;

  return (
    <div className="relative" ref={boxRef}>
      <button
        onClick={() => setOpen((o) => !o)}
        aria-label="Ogohlantirishlar"
        className={cn(
          "relative grid h-10 w-10 place-items-center rounded-xl border transition",
          open
            ? "border-brand-cyan/40 bg-brand-cyan/10 text-brand-cyan"
            : "border-white/10 bg-white/[0.03] text-slate-300 hover:border-white/20 hover:bg-white/[0.06]",
        )}
      >
        <Icon className={cn("h-[18px] w-[18px]", unread > 0 && "text-red-300")} />
        {unread > 0 && (
          <>
            <span className="absolute -right-1 -top-1 h-5 min-w-5 animate-pulse-ring rounded-full bg-red-500/60" />
            <span className="absolute -right-1 -top-1 grid h-5 min-w-5 place-items-center rounded-full bg-red-500 px-1 text-[10px] font-bold text-white ring-2 ring-ink-950">
              {unread > 99 ? "99+" : unread}
            </span>
          </>
        )}
      </button>

      {open && (
        <div className="glass absolute right-0 z-50 mt-3 w-[27rem] max-w-[calc(100vw-2rem)] animate-fade-in overflow-hidden !bg-ink-900/95">
          <div className="flex items-center justify-between border-b border-white/[0.06] px-4 py-3">
            <div>
              <div className="text-sm font-semibold text-white">Ogohlantirishlar</div>
              <div className="text-[11px] text-slate-500">
                {unread > 0 ? `${unread} ta yangi` : "Hammasi o'qilgan"} · {data?.categories.join(", ")}
              </div>
            </div>
            {unread > 0 && (
              <button
                onClick={markRead}
                className="inline-flex items-center gap-1 rounded-lg px-2 py-1 text-xs text-brand-cyan hover:bg-brand-cyan/10"
              >
                <CheckCheck className="h-3.5 w-3.5" /> Hammasini o'qildi
              </button>
            )}
          </div>

          <div className="max-h-[26rem] overflow-y-auto">
            {!data?.items.length ? (
              <EmptyState icon={Bell} title="Hozircha ogohlantirish yo'q" description="Yangi leak yoki ransomware topilsa shu yerda chiqadi." />
            ) : (
              data.items.map((n) => (
                <a
                  key={n.id}
                  href={n.url}
                  target="_blank"
                  rel="noreferrer"
                  className={cn(
                    "group block border-b border-white/[0.04] px-4 py-3 transition last:border-0 hover:bg-white/[0.04]",
                    n.is_new && "bg-gradient-to-r from-red-500/[0.07] to-transparent",
                  )}
                >
                  <div className="flex items-center gap-2">
                    {n.is_new && <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-red-400" />}
                    <CategoryBadge category={n.category} />
                    <span className="truncate text-[11px] text-slate-500">{n.source}</span>
                    <span className="ml-auto shrink-0 text-[11px] text-slate-500">{timeAgo(n.first_seen)}</span>
                  </div>
                  <div className="mt-1.5 flex items-start gap-2">
                    <span className="line-clamp-2 flex-1 text-sm leading-snug text-slate-200 group-hover:text-white">
                      {n.title}
                    </span>
                    <ExternalLink className="mt-0.5 h-3.5 w-3.5 shrink-0 text-slate-600 group-hover:text-slate-400" />
                  </div>
                </a>
              ))
            )}
          </div>

          <Link
            href="/dashboard/events"
            onClick={() => setOpen(false)}
            className="block border-t border-white/[0.06] px-4 py-2.5 text-center text-xs text-slate-400 transition hover:bg-white/[0.04] hover:text-white"
          >
            Barcha hodisalarni ko'rish →
          </Link>
        </div>
      )}
    </div>
  );
}
