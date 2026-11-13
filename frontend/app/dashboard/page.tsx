"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { clearToken, getMe, getToken, type Me } from "@/lib/api";

export default function DashboardPage() {
  const router = useRouter();
  const [me, setMe] = useState<Me | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!getToken()) {
      router.replace("/login");
      return;
    }
    getMe()
      .then(setMe)
      .catch((err) => {
        setError(err instanceof Error ? err.message : "Xatolik");
        clearToken();
        router.replace("/login");
      });
  }, [router]);

  function logout() {
    clearToken();
    router.replace("/login");
  }

  return (
    <div className="min-h-screen">
      {/* Header */}
      <header className="flex items-center justify-between border-b border-slate-800 px-6 py-4">
        <h1 className="text-lg font-semibold">🔎 OSINT Dashboard</h1>
        <div className="flex items-center gap-4 text-sm">
          {me && <span className="text-slate-400">{me.email}</span>}
          <button
            onClick={logout}
            className="rounded-md border border-slate-700 px-3 py-1.5 hover:bg-slate-800"
          >
            Chiqish
          </button>
        </div>
      </header>

      <div className="flex">
        {/* Sidebar */}
        <aside className="hidden w-56 shrink-0 border-r border-slate-800 p-4 sm:block">
          <nav className="space-y-1 text-sm">
            <div className="rounded-md bg-slate-800 px-3 py-2 font-medium">Umumiy</div>
            <div className="px-3 py-2 text-slate-500">Username qidiruv (tez orada)</div>
            <div className="px-3 py-2 text-slate-500">Email / telefon (tez orada)</div>
            <div className="px-3 py-2 text-slate-500">Domen / WHOIS (tez orada)</div>
          </nav>
        </aside>

        {/* Content */}
        <main className="flex-1 p-6">
          {error && <p className="text-red-400">{error}</p>}
          {!me && !error && <p className="text-slate-500">Yuklanmoqda...</p>}
          {me && (
            <div className="space-y-6">
              <div>
                <h2 className="text-2xl font-bold">Xush kelibsiz 👋</h2>
                <p className="mt-1 text-slate-400">
                  Bu sizning OSINT boshqaruv panelingiz. Modullar bosqichma-bosqich qo'shiladi.
                </p>
              </div>
              <div className="grid gap-4 sm:grid-cols-3">
                {[
                  { title: "Username qidiruv", desc: "Profilarni ko'p saytda izlash" },
                  { title: "Email / telefon", desc: "Identifikator tekshiruvi" },
                  { title: "Domen / WHOIS", desc: "Domen va IP razvedka" },
                ].map((c) => (
                  <div
                    key={c.title}
                    className="rounded-xl border border-slate-800 bg-slate-900 p-5"
                  >
                    <h3 className="font-semibold">{c.title}</h3>
                    <p className="mt-1 text-sm text-slate-500">{c.desc}</p>
                    <span className="mt-3 inline-block rounded bg-slate-800 px-2 py-0.5 text-xs text-slate-400">
                      Tez orada
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
