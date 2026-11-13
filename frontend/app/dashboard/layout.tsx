"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import NotificationBell from "@/components/NotificationBell";
import { clearToken, getMe, getToken, type Me } from "@/lib/api";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [me, setMe] = useState<Me | null>(null);

  useEffect(() => {
    if (!getToken()) {
      router.replace("/login");
      return;
    }
    getMe()
      .then(setMe)
      .catch(() => {
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
      <header className="sticky top-0 z-40 flex items-center justify-between border-b border-slate-800 bg-slate-950/90 px-6 py-3 backdrop-blur">
        <Link href="/dashboard" className="text-lg font-semibold">
          🔎 OSINT Dashboard
        </Link>
        <div className="flex items-center gap-3 text-sm">
          {me && <NotificationBell />}
          {me && <span className="hidden text-slate-400 sm:inline">{me.email}</span>}
          <button
            onClick={logout}
            className="rounded-md border border-slate-700 px-3 py-1.5 hover:bg-slate-800"
          >
            Chiqish
          </button>
        </div>
      </header>
      {children}
    </div>
  );
}
