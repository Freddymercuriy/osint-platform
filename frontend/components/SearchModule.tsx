"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { getToken, type CollectResult, type SearchResponse } from "@/lib/api";

const STATUS_STYLES: Record<string, string> = {
  found: "bg-emerald-950 text-emerald-300 border-emerald-800",
  not_found: "bg-slate-800 text-slate-500 border-slate-700",
  error: "bg-amber-950 text-amber-300 border-amber-800",
};

const STATUS_LABEL: Record<string, string> = {
  found: "Topildi",
  not_found: "Yo'q",
  error: "Noaniq",
};

function ResultRow({ r }: { r: CollectResult }) {
  return (
    <div className="flex items-center justify-between gap-3 border-b border-slate-800 py-3 last:border-0">
      <div className="min-w-0">
        <div className="font-medium">{r.source}</div>
        {r.detail && <div className="text-sm text-slate-400">{r.detail}</div>}
        {r.url && (
          <a
            href={r.url}
            target="_blank"
            rel="noreferrer"
            className="block truncate text-sm text-indigo-400 hover:underline"
          >
            {r.url}
          </a>
        )}
      </div>
      <span
        className={`shrink-0 rounded-full border px-3 py-1 text-xs ${
          STATUS_STYLES[r.status] ?? STATUS_STYLES.error
        }`}
      >
        {STATUS_LABEL[r.status] ?? r.status}
      </span>
    </div>
  );
}

const ORDER: Record<string, number> = { found: 0, error: 1, not_found: 2 };

export default function SearchModule({
  title,
  description,
  placeholder,
  search,
}: {
  title: string;
  description: string;
  placeholder: string;
  search: (query: string) => Promise<SearchResponse>;
}) {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<SearchResponse | null>(null);

  useEffect(() => {
    if (!getToken()) router.replace("/login");
  }, [router]);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setData(null);
    setLoading(true);
    try {
      setData(await search(query.trim()));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Xatolik");
    } finally {
      setLoading(false);
    }
  }

  const sorted = data
    ? [...data.results].sort((a, b) => (ORDER[a.status] ?? 3) - (ORDER[b.status] ?? 3))
    : [];

  return (
    <main className="mx-auto max-w-2xl p-6">
      <a href="/dashboard" className="text-sm text-slate-500 hover:text-slate-300">
        ← Dashboard
      </a>
      <h1 className="mt-2 text-2xl font-bold">{title}</h1>
      <p className="mt-1 text-sm text-slate-400">{description}</p>

      <form onSubmit={onSubmit} className="mt-6 flex gap-2">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={placeholder}
          required
          className="flex-1 rounded-md border border-slate-700 bg-slate-950 px-3 py-2 outline-none focus:border-indigo-500"
        />
        <button
          type="submit"
          disabled={loading}
          className="rounded-md bg-indigo-600 px-5 py-2 font-medium hover:bg-indigo-500 disabled:opacity-50"
        >
          {loading ? "Qidirilmoqda..." : "Qidirish"}
        </button>
      </form>

      {error && <p className="mt-4 text-red-400">{error}</p>}
      {loading && <p className="mt-6 text-slate-500">Tekshirilmoqda, biroz kuting...</p>}

      {data && (
        <div className="mt-6">
          <p className="text-sm text-slate-400">
            <span className="font-semibold text-slate-200">{data.query}</span> — {data.checked}{" "}
            manbadan <span className="text-emerald-400">{data.found} tasida topildi</span>
          </p>
          <div className="mt-2 rounded-xl border border-slate-800 bg-slate-900 px-4">
            {sorted.map((r, i) => (
              <ResultRow key={`${r.source}-${i}`} r={r} />
            ))}
          </div>
        </div>
      )}
    </main>
  );
}
