"use client";

import { Menu, X } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { usePathname, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import NotificationBell from "@/components/NotificationBell";
import { navKeyFor } from "@/components/shell/nav";
import Sidebar from "@/components/shell/Sidebar";
import LocaleSwitcher from "@/components/theme/LocaleSwitcher";
import ThemeToggle from "@/components/theme/ThemeToggle";
import { Logo, Spinner } from "@/components/ui";
import { clearToken, getMe, getToken, setLocaleCookie, type Me } from "@/lib/api";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const locale = useLocale();
  const t = useTranslations("nav");
  const tc = useTranslations("common");
  const [me, setMe] = useState<Me | null>(null);
  const [unread, setUnread] = useState(0);
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(() => {
    if (!getToken()) {
      router.replace("/login");
      return;
    }
    getMe()
      .then((m) => {
        setMe(m);
        // Akkauntda saqlangan til boshqa bo'lsa — shunga o'tamiz (boshqa qurilmadan tanlangan)
        if (m.locale && m.locale !== locale) {
          setLocaleCookie(m.locale);
          router.refresh();
        }
      })
      .catch(() => {
        clearToken();
        router.replace("/login");
      });
    // locale ataylab qo'shilmagan: faqat birinchi yuklanishda sinxronlanadi
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [router]);

  useEffect(() => setMobileOpen(false), [pathname]);

  useEffect(() => {
    if (!mobileOpen) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setMobileOpen(false);
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [mobileOpen]);

  const logout = useCallback(() => {
    clearToken();
    router.replace("/login");
  }, [router]);

  if (!me) {
    return (
      <div className="grid min-h-screen place-items-center">
        <div className="flex flex-col items-center gap-4">
          <Logo />
          <Spinner label={tc("loading")} />
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen">
      <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-[60] focus:rounded-lg focus:bg-surface focus:px-3 focus:py-2 focus:text-fg focus:ring-2 focus:ring-ring">
        {tc("skipToContent")}
      </a>

      <div className="sticky top-0 hidden h-screen lg:block">
        <Sidebar me={me} unread={unread} onLogout={logout} />
      </div>

      {mobileOpen && (
        <div className="fixed inset-0 z-50 lg:hidden" role="dialog" aria-modal="true" aria-label={tc("menu")}>
          <div className="absolute inset-0 bg-black/40" onClick={() => setMobileOpen(false)} />
          <div className="relative h-full w-64 animate-fade-in shadow-xl">
            <Sidebar me={me} unread={unread} onLogout={logout} onNavigate={() => setMobileOpen(false)} />
            <button
              type="button"
              onClick={() => setMobileOpen(false)}
              aria-label={tc("close")}
              className="focus-ring absolute -right-11 top-3 grid h-9 w-9 place-items-center rounded-lg bg-surface text-fg"
            >
              <X className="h-5 w-5" />
            </button>
          </div>
        </div>
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-40 flex h-14 items-center gap-2 border-b border-border bg-bg/90 px-3 backdrop-blur sm:gap-3 sm:px-6">
          <button
            type="button"
            onClick={() => setMobileOpen(true)}
            className="focus-ring grid h-9 w-9 place-items-center rounded-lg border border-border bg-surface text-fg-muted lg:hidden"
            aria-label={tc("menu")}
          >
            <Menu className="h-5 w-5" />
          </button>
          <div className="min-w-0 flex-1 truncate text-sm font-medium text-fg">{t(navKeyFor(pathname))}</div>
          <span className="hidden text-xs text-fg-subtle md:inline">{tc("publicSourcesOnly")}</span>
          <LocaleSwitcher className="hidden sm:inline-flex" />
          <ThemeToggle />
          <NotificationBell onUnreadChange={setUnread} />
        </header>

        <main id="main" className="mx-auto w-full max-w-7xl flex-1 px-4 py-6 sm:px-6 lg:px-8">
          {children}
        </main>
      </div>
    </div>
  );
}
