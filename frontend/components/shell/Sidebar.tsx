"use client";

import { LogOut } from "lucide-react";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import LocaleSwitcher from "@/components/theme/LocaleSwitcher";
import { LiveDot, Logo } from "@/components/ui";
import { getCollectorStatus, type CollectorStatus, type Me } from "@/lib/api";
import { cn } from "@/lib/cn";
import { useFormat } from "@/lib/format";
import { NAV } from "./nav";

export default function Sidebar({
  me,
  unread,
  onLogout,
  onNavigate,
}: {
  me: Me | null;
  unread: number;
  onLogout: () => void;
  onNavigate?: () => void;
}) {
  const t = useTranslations("nav");
  const tc = useTranslations("common");
  const f = useFormat();
  const pathname = usePathname();
  const [cs, setCs] = useState<CollectorStatus | null>(null);
  const isAdmin = me?.role === "admin";

  useEffect(() => {
    const load = () => getCollectorStatus().then(setCs).catch(() => setCs(null));
    load();
    const id = setInterval(load, 60_000);
    return () => clearInterval(id);
  }, []);

  const isActive = (href: string) => pathname === href || (href !== "/dashboard" && pathname.startsWith(`${href}/`));

  return (
    <aside className="flex h-full w-64 flex-col border-r border-border bg-surface">
      <div className="px-5 pb-3 pt-5">
        <Link href="/dashboard" onClick={onNavigate} className="focus-ring inline-block rounded-lg">
          <Logo />
        </Link>
      </div>

      <nav aria-label={tc("menu")} className="flex-1 space-y-5 overflow-y-auto px-3 py-2">
        {NAV.filter((s) => !s.adminOnly || isAdmin).map((section) => (
          <div key={section.key}>
            {section.key !== "overview" && (
              <div className="mb-1.5 px-3 text-xs font-medium text-fg-subtle">{t(section.key)}</div>
            )}
            <ul className="space-y-0.5">
              {section.items.map((item) => {
                const active = isActive(item.href);
                const Icon = item.icon;
                return (
                  <li key={item.href}>
                    <Link
                      href={item.href}
                      onClick={onNavigate}
                      aria-current={active ? "page" : undefined}
                      className={cn(
                        "focus-ring flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors",
                        active ? "bg-primary-soft font-medium text-primary" : "text-fg-muted hover:bg-surface-2 hover:text-fg",
                      )}
                    >
                      <Icon className="h-4 w-4 shrink-0" aria-hidden />
                      <span className="flex-1 truncate">{t(item.key)}</span>
                      {item.badge === "notifications" && unread > 0 && (
                        <span className="rounded-full bg-danger px-1.5 text-[11px] font-semibold text-bg">
                          {unread > 99 ? "99+" : unread}
                        </span>
                      )}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
      </nav>

      {/* Mobil: til tanlash yuqori panelda sig'maydi */}
      <div className="px-3 pb-2 sm:hidden">
        <LocaleSwitcher />
      </div>

      {/* Yig'uvchi holati */}
      <div className="mx-3 mb-3 space-y-1.5 rounded-lg border border-border bg-surface-2 p-3 text-xs">
        <div className="flex items-center gap-2">
          <LiveDot tone={cs?.running ? "green" : "red"} />
          <span className="text-fg">
            {t("collector")}: {cs?.running ? t("collectorRunning") : t("collectorStopped")}
          </span>
        </div>
        {cs && (
          <div className="flex items-center justify-between text-fg-muted">
            <span>{t("eventsInDb", { count: f.number(cs.total_events) })}</span>
            <span>{cs.last_run ? f.ago(cs.last_run) : "—"}</span>
          </div>
        )}
      </div>

      {/* Foydalanuvchi */}
      <div className="flex items-center gap-3 border-t border-border px-4 py-3">
        <div className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-primary-soft text-sm font-semibold uppercase text-primary" aria-hidden>
          {me?.email?.[0] ?? "?"}
        </div>
        <div className="min-w-0 flex-1">
          <div className="truncate text-sm text-fg">{me?.email ?? "…"}</div>
          <div className="text-xs text-fg-subtle">{me ? tc(`role_${me.role}`) : ""}</div>
        </div>
        <button
          type="button"
          onClick={onLogout}
          title={tc("logout")}
          aria-label={tc("logout")}
          className="focus-ring rounded-lg p-2 text-fg-subtle transition-colors hover:bg-surface-2 hover:text-danger"
        >
          <LogOut className="h-4 w-4" />
        </button>
      </div>
    </aside>
  );
}
