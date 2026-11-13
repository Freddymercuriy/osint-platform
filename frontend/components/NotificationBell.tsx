"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  getNotifications,
  markNotificationsRead,
  type NotificationsResponse,
} from "@/lib/api";

const POLL_MS = 60_000; // har daqiqada tekshiradi

const CAT_STYLE: Record<string, string> = {
  ransomware: "bg-red-950 text-red-300",
  leak: "bg-orange-950 text-orange-300",
};

function ago(iso: string): string {
  const diff = (Date.now() - new Date(iso).getTime()) / 1000;
  if (diff < 60) return "hozirgina";
  if (diff < 3600) return `${Math.floor(diff / 60)} daq oldin`;
  if (diff < 86400) return `${Math.floor(diff / 3600)} soat oldin`;
  return new Date(iso).toLocaleDateString("uz-UZ");
}

export default function NotificationBell() {
  const [data, setData] = useState<NotificationsResponse | null>(null);
  const [open, setOpen] = useState(false);
  const boxRef = useRef<HTMLDivElement>(null);
  const prevUnread = useRef(0);

  const load = useCallback(async () => {
    try {
      const res = await getNotifications(20);
      // Yangi ogohlantirish kelsa — sahifa sarlavhasida ham ko'rsatamiz
      if (res.unread > prevUnread.current && typeof document !== "undefined") {
        document.title = `(${res.unread}) OSINT Platform`;
      }
      prevUnread.current = res.unread;
      setData(res);
    } catch {
      /* tarmoq xatosi — keyingi tsiklda qayta urinadi */
    }
  }, []);

  useEffect(() => {
    load();
    const t = setInterval(load, POLL_MS);
    return () => clearInterval(t);
  }, [load]);

  // Tashqariga bosilsa yopiladi
  useEffect(() => {
    function onClick(e: MouseEvent) {
      if (boxRef.current && !boxRef.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, []);

  async function markRead() {
    await markNotificationsRead();
    document.title = "OSINT Platform";
    await load();
  }

  const unread = data?.unread ?? 0;

  return (
    <div className="relative" ref={boxRef}>
      <button
        onClick={() => setOpen((o) => !o)}
        className="relative rounded-md border border-slate-700 px-3 py-1.5 hover:bg-slate-800"
        aria-label="Ogohlantirishlar"
      >
        🔔
        {unread > 0 && (
          <span className="absolute -right-2 -top-2 min-w-5 rounded-full bg-red-600 px-1.5 text-center text-xs font-semibold text-white">
            {unread > 99 ? "99+" : unread}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 z-50 mt-2 w-[26rem] max-w-[90vw] overflow-hidden rounded-xl border border-slate-700 bg-slate-900 shadow-2xl">
          <div className="flex items-center justify-between border-b border-slate-800 px-4 py-2.5">
            <div className="text-sm font-semibold">
              Ogohlantirishlar{" "}
              <span className="font-normal text-slate-500">
                ({data?.categories.join(", ")})
              </span>
            </div>
            {unread > 0 && (
              <button onClick={markRead} className="text-xs text-indigo-400 hover:underline">
                Hammasini o'qildi
              </button>
            )}
          </div>

          <div className="max-h-[28rem] overflow-y-auto">
            {!data?.items.length && (
              <p className="px-4 py-6 text-center text-sm text-slate-500">Hozircha yo'q</p>
            )}
            {data?.items.map((n) => (
              <a
                key={n.id}
                href={n.url}
                target="_blank"
                rel="noreferrer"
                className={`block border-b border-slate-800 px-4 py-3 last:border-0 hover:bg-slate-800/60 ${
                  n.is_new ? "bg-indigo-950/30" : ""
                }`}
              >
                <div className="flex items-center gap-2 text-xs">
                  {n.is_new && <span className="h-2 w-2 rounded-full bg-red-500" />}
                  <span className={`rounded px-1.5 py-0.5 ${CAT_STYLE[n.category] ?? "bg-slate-800"}`}>
                    {n.category}
                  </span>
                  <span className="truncate text-slate-500">{n.source}</span>
                  <span className="ml-auto shrink-0 text-slate-500">{ago(n.first_seen)}</span>
                </div>
                <div className="mt-1 text-sm leading-snug">{n.title}</div>
              </a>
            ))}
          </div>

          <a
            href="/dashboard/events"
            className="block border-t border-slate-800 px-4 py-2 text-center text-xs text-slate-400 hover:bg-slate-800"
          >
            Barcha hodisalar →
          </a>
        </div>
      )}
    </div>
  );
}
