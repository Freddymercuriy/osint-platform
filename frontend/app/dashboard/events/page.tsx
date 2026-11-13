"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { getEvents, getToken, type EventItem } from "@/lib/api";

function timeAgo(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  const diff = (Date.now() - d.getTime()) / 1000;
  if (diff < 60) return "hozirgina";
  if (diff < 3600) return `${Math.floor(diff / 60)} daqiqa oldin`;
  if (diff < 86400) return `${Math.floor(diff / 3600)} soat oldin`;
  return d.toLocaleDateString("uz-UZ");
}

function EventCard({ e }: { e: EventItem }) {
  return (
    <a
      href={e.url}
      target="_blank"
      rel="noreferrer"
      className="block rounded-xl border border-slate-800 bg-slate-900 p-4 transition hover:border-indigo-700"
    >
      <div className="flex items-center justify-between gap-3 text-xs text-slate-500">
        <span className="rounded bg-slate-800 px-2 py-0.5 text-slate-300">{e.source}</span>
        <span>{timeAgo(e.published)}</span>
      </div>
      <h3 className="mt-2 font-medium leading-snug">{e.title}</h3>
      {e.summary && <p className="mt-1 line-clamp-2 text-sm text-slate-400">{e.summary}</p>}
    </a>
  );
}

export default function EventsPage() {
  const router = useRouter();
  const [items, setItems] = useState<EventItem[]>([]);
  const [q, setQ] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (query?: string) => {
    setLoading(true);
    setError(null);
    try {
      const res = await getEvents(query);
      setItems(res.items);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Xatolik");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!getToken()) {
      router.replace("/login");
      return;
    }
    load();
  }, [router, load]);

  return (
    <main className="mx-auto max-w-3xl p-6">
      <a href="/dashboard" className="text-sm text-slate-500 hover:text-slate-300">
        ← Dashboard
      </a>
      <h1 className="mt-2 text-2xl font-bold">Events — O'zbekiston yangiliklari</h1>
      <p className="mt-1 text-sm text-slate-400">
        Ochiq manbalardan (RSS) yig'ilgan so'nggi yangiliklar.
      </p>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          load(q.trim() || undefined);
        }}
        className="mt-5 flex gap-2"
      >
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Kalit so'z bo'yicha filtr (masalan: iqtisod)"
          className="flex-1 rounded-md border border-slate-700 bg-slate-950 px-3 py-2 outline-none focus:border-indigo-500"
        />
        <button className="rounded-md bg-indigo-600 px-5 py-2 font-medium hover:bg-indigo-500">
          Filtr
        </button>
      </form>

      {error && <p className="mt-4 text-red-400">{error}</p>}
      {loading && <p className="mt-6 text-slate-500">Yuklanmoqda...</p>}
      {!loading && items.length === 0 && !error && (
        <p className="mt-6 text-slate-500">Hech narsa topilmadi.</p>
      )}

      <div className="mt-5 grid gap-3">
        {items.map((e, i) => (
          <EventCard key={`${e.url}-${i}`} e={e} />
        ))}
      </div>
    </main>
  );
}
