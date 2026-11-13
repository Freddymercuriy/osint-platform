"use client";

import Link from "next/link";
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

  return (
    <div>
      {/* Yuqori panel (🔔, Chiqish) — app/dashboard/layout.tsx da */}
      <div className="flex">
        {/* Sidebar */}
        <aside className="hidden w-56 shrink-0 border-r border-slate-800 p-4 sm:block">
          <nav className="space-y-1 text-sm">
            <Link href="/dashboard" className="block rounded-md bg-slate-800 px-3 py-2 font-medium">
              Umumiy
            </Link>
            <Link
              href="/dashboard/username"
              className="block rounded-md px-3 py-2 hover:bg-slate-800"
            >
              Username qidiruv
            </Link>
            <Link
              href="/dashboard/email"
              className="block rounded-md px-3 py-2 hover:bg-slate-800"
            >
              Email tekshiruvi
            </Link>
            <Link
              href="/dashboard/phone"
              className="block rounded-md px-3 py-2 hover:bg-slate-800"
            >
              Telefon tekshiruvi
            </Link>
            <Link
              href="/dashboard/events"
              className="block rounded-md px-3 py-2 hover:bg-slate-800"
            >
              Events (O'zbekiston)
            </Link>
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
                  {
                    title: "Username qidiruv",
                    desc: "Profilarni ko'p saytda izlash",
                    href: "/dashboard/username",
                    ready: true,
                  },
                  {
                    title: "Email tekshiruvi",
                    desc: "Sintaksis, MX, Gravatar",
                    href: "/dashboard/email",
                    ready: true,
                  },
                  {
                    title: "Telefon tekshiruvi",
                    desc: "Davlat, operator, tur",
                    href: "/dashboard/phone",
                    ready: true,
                  },
                  {
                    title: "Events",
                    desc: "O'zbekiston yangiliklari (RSS)",
                    href: "/dashboard/events",
                    ready: true,
                  },
                  { title: "Domen / WHOIS", desc: "Domen va IP razvedka", ready: false },
                ].map((c) => {
                  const card = (
                    <div className="h-full rounded-xl border border-slate-800 bg-slate-900 p-5 transition hover:border-slate-700">
                      <h3 className="font-semibold">{c.title}</h3>
                      <p className="mt-1 text-sm text-slate-500">{c.desc}</p>
                      <span
                        className={`mt-3 inline-block rounded px-2 py-0.5 text-xs ${
                          c.ready
                            ? "bg-emerald-950 text-emerald-300"
                            : "bg-slate-800 text-slate-400"
                        }`}
                      >
                        {c.ready ? "Ishga tayyor" : "Tez orada"}
                      </span>
                    </div>
                  );
                  return c.ready && c.href ? (
                    <Link key={c.title} href={c.href}>
                      {card}
                    </Link>
                  ) : (
                    <div key={c.title}>{card}</div>
                  );
                })}
              </div>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
