"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { getEvents, getTgStatus, getToken, type EventItem, type TgStatus } from "@/lib/api";

const TABS: { key: string; label: string }[] = [
  { key: "", label: "Hammasi" },
  { key: "ransomware", label: "🔴 Ransomware" },
  { key: "leak", label: "🟠 Leak" },
  { key: "telegram", label: "✈️ TG kanallar" },
  { key: "tg_group", label: "👥 TG guruhlar" },
  { key: "news", label: "📰 Yangiliklar" },
];

const CATEGORY_STYLE: Record<string, string> = {
  ransomware: "bg-red-950 text-red-300 border-red-800",
  leak: "bg-orange-950 text-orange-300 border-orange-800",
  telegram: "bg-sky-950 text-sky-300 border-sky-800",
  tg_group: "bg-violet-950 text-violet-300 border-violet-800",
  news: "bg-slate-800 text-slate-300 border-slate-700",
};

function TgStatusBar({ s }: { s: TgStatus | null }) {
  if (!s) return null;
  return (
    <div
      className={`mt-4 rounded-lg border px-4 py-2 text-sm ${
        s.authorized
          ? "border-emerald-900 bg-emerald-950/40 text-emerald-300"
          : "border-amber-900 bg-amber-950/40 text-amber-300"
      }`}
    >
      <span className="font-medium">Telegram akkaunt:</span>{" "}
      {s.authorized ? s.account : s.message}
      {s.authorized && (
        <span className="text-slate-400">
          {" "}
          · chatlar: {s.chats_filter.length ? s.chats_filter.join(", ") : "barchasi"} · UZ filtr:{" "}
          {s.uz_filter ? "yoqilgan" : "o'chiq"}
        </span>
      )}
    </div>
  );
}

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
        <div className="flex items-center gap-2">
          <span
            className={`rounded border px-2 py-0.5 ${
              CATEGORY_STYLE[e.category] ?? CATEGORY_STYLE.news
            }`}
          >
            {e.category}
          </span>
          <span className="text-slate-400">{e.source}</span>
        </div>
        <span>{timeAgo(e.published)}</span>
      </div>
      <h3 className="mt-2 font-medium leading-snug">{e.title}</h3>
      {e.summary && <p className="mt-1 line-clamp-3 text-sm text-slate-400">{e.summary}</p>}
    </a>
  );
}

export default function EventsPage() {
  const router = useRouter();
  const [items, setItems] = useState<EventItem[]>([]);
  const [q, setQ] = useState("");
  const [tab, setTab] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tg, setTg] = useState<TgStatus | null>(null);

  useEffect(() => {
    if (getToken()) getTgStatus().then(setTg).catch(() => setTg(null));
  }, []);

  const load = useCallback(async (query: string, category: string) => {
    setLoading(true);
    setError(null);
    try {
      const res = await getEvents(query || undefined, category || undefined);
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
    load(q.trim(), tab);
    // q faqat "Filtr" bosilganda ishlatiladi
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [router, load, tab]);

  return (
    <main className="mx-auto max-w-3xl p-6">
      <a href="/dashboard" className="text-sm text-slate-500 hover:text-slate-300">
        ← Dashboard
      </a>
      <h1 className="mt-2 text-2xl font-bold">Events — O'zbekiston</h1>
      <p className="mt-1 text-sm text-slate-400">
        Ransomware hodisalari, Telegram kanal/guruhlar va yangiliklar — O'zbekiston bo'yicha.
      </p>
      <TgStatusBar s={tg} />

      <div className="mt-5 flex flex-wrap gap-2">
        {TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`rounded-full border px-3 py-1 text-sm ${
              tab === t.key
                ? "border-indigo-500 bg-indigo-950 text-indigo-200"
                : "border-slate-700 text-slate-400 hover:bg-slate-800"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          load(q.trim(), tab);
        }}
        className="mt-4 flex gap-2"
      >
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Kalit so'z (masalan: bank, .uz, Toshkent)"
          className="flex-1 rounded-md border border-slate-700 bg-slate-950 px-3 py-2 outline-none focus:border-indigo-500"
        />
        <button className="rounded-md bg-indigo-600 px-5 py-2 font-medium hover:bg-indigo-500">
          Filtr
        </button>
      </form>

      {error && <p className="mt-4 text-red-400">{error}</p>}
      {loading && <p className="mt-6 text-slate-500">Yuklanmoqda...</p>}
      {!loading && items.length === 0 && !error && (
        <p className="mt-6 text-slate-500">Bu bo'limda hozircha hech narsa yo'q.</p>
      )}

      <div className="mt-5 grid gap-3">
        {items.map((e, i) => (
          <EventCard key={`${e.url}-${i}`} e={e} />
        ))}
      </div>
    </main>
  );
}
