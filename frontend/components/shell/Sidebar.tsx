"use client";

import { LogOut } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useId, useState } from "react";
import { motion, SPRING } from "@/components/motion";
import { LiveDot, Logo, timeAgo } from "@/components/ui";
import { getCollectorStatus, getTgStatus, type CollectorStatus, type Me, type TgStatus } from "@/lib/api";
import { cn } from "@/lib/cn";
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
  const pathname = usePathname();
  const uid = useId(); // desktop va mobil nusxalar bir-biriga aralashmasligi uchun
  const [cs, setCs] = useState<CollectorStatus | null>(null);
  const [tg, setTg] = useState<TgStatus | null>(null);

  useEffect(() => {
    const load = () => {
      getCollectorStatus().then(setCs).catch(() => setCs(null));
      getTgStatus().then(setTg).catch(() => setTg(null));
    };
    load();
    const t = setInterval(load, 60_000);
    return () => clearInterval(t);
  }, []);

  return (
    <aside className="flex h-full w-64 flex-col border-r border-white/[0.06] bg-ink-900/80 backdrop-blur-xl">
      <div className="px-5 pb-4 pt-5">
        <Link href="/dashboard" onClick={onNavigate}>
          <Logo />
        </Link>
      </div>

      <nav className="flex-1 space-y-6 overflow-y-auto px-3 py-2">
        {NAV.map((section) => (
          <div key={section.title}>
            <div className="mb-2 px-3 font-mono text-[10px] uppercase tracking-[0.2em] text-slate-600">
              {section.title}
            </div>
            <ul className="space-y-0.5">
              {section.items.map((item) => {
                const active = pathname === item.href;
                const Icon = item.icon;
                if (item.soon)
                  return (
                    <li key={item.label}>
                      <div className="flex cursor-not-allowed items-center gap-3 rounded-xl px-3 py-2 text-sm text-slate-600">
                        <Icon className="h-4 w-4 shrink-0" />
                        <span className="min-w-0 flex-1 truncate whitespace-nowrap">{item.label}</span>
                        <span className="kbd shrink-0 !px-1 !text-[9px]">tez orada</span>
                      </div>
                    </li>
                  );
                return (
                  <li key={item.href}>
                    <Link
                      href={item.href}
                      onClick={onNavigate}
                      className={cn(
                        "group relative flex items-center gap-3 rounded-xl px-3 py-2 text-sm transition",
                        active ? "text-white" : "text-slate-400 hover:bg-white/[0.04] hover:text-slate-100",
                      )}
                    >
                      {active && (
                        <motion.span
                          layoutId={`sidebar-active-${uid}`}
                          transition={SPRING}
                          className="absolute inset-0 rounded-xl bg-gradient-to-r from-brand-cyan/15 to-brand-violet/10 ring-1 ring-inset ring-white/[0.06]"
                        >
                          <span className="absolute left-0 top-1/2 h-5 w-[3px] -translate-y-1/2 rounded-r bg-brand-gradient shadow-[0_0_10px_rgba(34,211,238,.9)]" />
                        </motion.span>
                      )}
                      <Icon
                        className={cn(
                          "relative h-4 w-4 transition-transform duration-300 group-hover:scale-110",
                          active ? "text-brand-cyan" : "text-slate-500 group-hover:text-slate-300",
                        )}
                      />
                      <span className="relative flex-1 truncate">{item.label}</span>
                      {item.badge === "notifications" && unread > 0 && (
                        <span className="relative rounded-full bg-red-500/90 px-1.5 text-[10px] font-semibold text-white">
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

      {/* Tizim holati */}
      <div className="mx-3 mb-3 space-y-2 rounded-xl border border-white/[0.06] bg-ink-850/60 p-3 text-xs">
        <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-slate-600">Tizim holati</div>
        <div className="flex items-center gap-2">
          <LiveDot tone={cs?.running ? (cs.last_error ? "amber" : "emerald") : "red"} />
          <span className="text-slate-300">Monitoring</span>
          <span className="ml-auto text-slate-500">{cs?.last_run ? timeAgo(cs.last_run) : "—"}</span>
        </div>
        <div className="flex items-center gap-2">
          <LiveDot tone={tg?.authorized ? "emerald" : "amber"} />
          <span className="text-slate-300">Telegram</span>
          <span className="ml-auto text-slate-500">{tg?.authorized ? "ulangan" : "ulanmagan"}</span>
        </div>
        {cs && (
          <div className="flex items-center justify-between border-t border-white/[0.05] pt-2 text-slate-500">
            <span>Bazada</span>
            <span className="font-mono text-slate-300">{cs.total_events} hodisa</span>
          </div>
        )}
      </div>

      {/* Foydalanuvchi */}
      <div className="flex items-center gap-3 border-t border-white/[0.06] px-4 py-3">
        <div className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-brand-gradient text-sm font-semibold uppercase text-white">
          {me?.email?.[0] ?? "?"}
        </div>
        <div className="min-w-0 flex-1">
          <div className="truncate text-sm text-slate-200">{me?.email ?? "..."}</div>
          <div className="text-[11px] text-slate-500">Analitik</div>
        </div>
        <button
          onClick={onLogout}
          title="Chiqish"
          className="rounded-lg p-2 text-slate-500 transition hover:bg-white/[0.06] hover:text-red-300"
        >
          <LogOut className="h-4 w-4" />
        </button>
      </div>
    </aside>
  );
}
