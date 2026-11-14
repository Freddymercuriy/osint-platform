"use client";

import {
  Activity,
  ArrowRight,
  BarChart3,
  Clock,
  Database,
  ExternalLink,
  Globe,
  Radar,
  Search,
  Send,
  ShieldAlert,
  Skull,
  Table2,
} from "lucide-react";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import ColumnChart, { type ColumnDatum } from "@/components/charts/ColumnChart";
import HBarList from "@/components/charts/HBarList";
import { Magnetic, Reveal, ScrambleText, Stagger, StaggerItem, TextReveal } from "@/components/motion";
import {
  ButtonLink,
  Card,
  CategoryBadge,
  EmptyState,
  ErrorBanner,
  IconBox,
  LiveDot,
  Skeleton,
  StatTile,
  timeAgo,
} from "@/components/ui";
import { getCollectorStatus, getMe, type CollectorStatus, type Me } from "@/lib/api";
import { CATEGORY_ORDER, categoryMeta } from "@/lib/categories";
import { cn } from "@/lib/cn";
import { MODULES } from "@/lib/modules";
import { getOverview, type Overview } from "@/lib/stats";

const MONTHS = ["yan", "fev", "mar", "apr", "may", "iyun", "iyul", "avg", "sen", "okt", "noy", "dek"];

function greeting(): string {
  const h = new Date().getHours();
  if (h < 6) return "Xayrli tun";
  if (h < 12) return "Xayrli tong";
  if (h < 18) return "Xayrli kun";
  return "Xayrli kech";
}

/** Bosh sahifadagi kichik radar animatsiyasi */
function RadarVisual() {
  return (
    <div className="relative hidden h-44 w-44 shrink-0 md:block">
      <div className="absolute inset-0 rounded-full border border-cyan-400/20" />
      <div className="absolute inset-6 rounded-full border border-cyan-400/15" />
      <div className="absolute inset-12 rounded-full border border-cyan-400/10" />
      <div className="absolute inset-0 animate-spin-slow rounded-full [background:conic-gradient(from_0deg,rgba(34,211,238,.35),transparent_25%)]" />
      <div className="absolute left-1/2 top-1/2 h-px w-1/2 origin-left bg-gradient-to-r from-cyan-300/60 to-transparent" />
      {[
        ["28%", "30%", "bg-red-400"],
        ["62%", "22%", "bg-orange-400"],
        ["70%", "64%", "bg-sky-400"],
        ["35%", "70%", "bg-violet-400"],
      ].map(([l, t, c], i) => (
        <span key={i} className="absolute" style={{ left: l, top: t }}>
          <span className={cn("absolute h-2 w-2 animate-pulse-ring rounded-full", c)} style={{ animationDelay: `${i * 0.4}s` }} />
          <span className={cn("relative block h-2 w-2 rounded-full", c)} />
        </span>
      ))}
      <div className="absolute left-1/2 top-1/2 h-2.5 w-2.5 -translate-x-1/2 -translate-y-1/2 rounded-full bg-cyan-300 shadow-[0_0_12px_rgba(34,211,238,.9)]" />
    </div>
  );
}

export default function DashboardPage() {
  const [me, setMe] = useState<Me | null>(null);
  const [ov, setOv] = useState<Overview | null>(null);
  const [cs, setCs] = useState<CollectorStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [view, setView] = useState<"chart" | "table">("chart");

  useEffect(() => {
    getMe().then(setMe).catch(() => undefined);
    const load = () => {
      getOverview(14).then(setOv).catch((e) => setError(e instanceof Error ? e.message : "Xatolik"));
      getCollectorStatus().then(setCs).catch(() => undefined);
    };
    load();
    const t = setInterval(load, 60_000);
    return () => clearInterval(t);
  }, []);

  const chartData: ColumnDatum[] = useMemo(
    () =>
      (ov?.daily ?? []).map((d) => {
        const dt = new Date(`${d.day}T00:00:00`);
        return {
          key: d.day,
          label: String(dt.getDate()),
          fullLabel: `${dt.getDate()}-${MONTHS[dt.getMonth()]}, ${dt.getFullYear()}`,
          value: d.total,
          breakdown: CATEGORY_ORDER.filter((c) => d.by_category[c]).map((c) => ({
            label: categoryMeta(c).label,
            value: d.by_category[c],
          })),
        };
      }),
    [ov],
  );

  const tg = ov ? (ov.by_category.telegram ?? 0) + (ov.by_category.tg_group ?? 0) : 0;
  const loading = !ov && !error;
  const name = me?.email.split("@")[0];

  return (
    <div className="space-y-6">
      {/* ---------- Hero ---------- */}
      <Card glow className="relative animate-fade-in overflow-hidden p-6 sm:p-8">
        <div className="pointer-events-none absolute -right-24 -top-24 h-72 w-72 rounded-full bg-brand-violet/20 blur-3xl" />
        <div className="pointer-events-none absolute -bottom-24 left-1/3 h-56 w-56 rounded-full bg-brand-cyan/10 blur-3xl" />
        <div className="relative flex items-center gap-8">
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-x-2 gap-y-1 font-mono text-[11px] uppercase tracking-[0.2em] text-brand-cyan/80">
              <span className="inline-flex items-center gap-2 whitespace-nowrap">
                <LiveDot tone={cs?.running ? (cs.last_error ? "amber" : "emerald") : "red"} />
                <ScrambleText text={cs?.running === false ? "Monitoring to'xtagan" : "Monitoring faol"} />
              </span>
              {cs?.last_run && <span className="whitespace-nowrap text-slate-500">· oxirgi skan {timeAgo(cs.last_run)}</span>}
            </div>
            <h1 className="mt-3 text-3xl font-semibold tracking-tight text-white sm:text-4xl">
              <TextReveal text={`${greeting()},`} delay={0.1} />{" "}
              {name && (
                <span className="inline-block overflow-hidden pb-[0.12em] align-bottom">
                  <span className="text-gradient-animated inline-block animate-fade-in [animation-delay:450ms]">{name}</span>
                </span>
              )}
            </h1>
            <p className="mt-2 max-w-xl text-slate-400">
              O'zbekiston bo'yicha tahdidlar markazi: ransomware hujumlari, leak'lar, Telegram va yangiliklar — har{" "}
              {cs ? Math.round(cs.poll_seconds / 60) : 5} daqiqada avtomatik yig'iladi.
            </p>
            <div className="mt-5 flex flex-wrap gap-2">
              <Magnetic>
                <ButtonLink href="/dashboard/events" icon={Radar}>
                  Events'ni ochish
                </ButtonLink>
              </Magnetic>
              <ButtonLink href="/dashboard/username" variant="secondary" icon={Search}>
                Tekshiruv boshlash
              </ButtonLink>
            </div>
          </div>
          <RadarVisual />
        </div>
      </Card>

      {error && <ErrorBanner message={error} />}

      {/* ---------- KPI ---------- */}
      <Stagger className="grid grid-cols-2 gap-4 lg:grid-cols-5" inView={false}>
        <StaggerItem><StatTile label="Jami hodisalar" value={ov?.total_events ?? 0} icon={Database} tone="cyan" stacked loading={loading} hint="bazada saqlangan" /></StaggerItem>
        <StaggerItem><StatTile label="So'nggi 24 soat" value={ov?.new_24h ?? 0} icon={Activity} tone="violet" stacked loading={loading} hint="yangi topilgan" /></StaggerItem>
        <StaggerItem><StatTile label="Ransomware" value={ov?.by_category.ransomware ?? 0} icon={Skull} tone="red" stacked loading={loading} hint="UZ qurbonlar" /></StaggerItem>
        <StaggerItem><StatTile label="Leak" value={ov?.by_category.leak ?? 0} icon={ShieldAlert} tone="orange" stacked loading={loading} hint="leak chatlarida" /></StaggerItem>
        <StaggerItem className="col-span-2 lg:col-span-1"><StatTile label="Telegram" value={tg} icon={Send} tone="sky" stacked loading={loading} hint="kanal va guruhlar" /></StaggerItem>
      </Stagger>

      {/* ---------- Grafiklar ---------- */}
      <Reveal className="grid gap-6 lg:grid-cols-3" delay={0.1}>
        <Card className="p-5 lg:col-span-2">
          <div className="mb-4 flex items-start justify-between gap-3">
            <div>
              <h2 className="font-semibold text-white">Kunlik hodisalar</h2>
              <p className="text-xs text-slate-500">So'nggi 14 kun · hodisa sanasi bo'yicha · barcha manbalar</p>
            </div>
            <div className="flex rounded-lg border border-white/10 p-0.5">
              {(
                [
                  ["chart", BarChart3, "Grafik"],
                  ["table", Table2, "Jadval"],
                ] as const
              ).map(([v, Icon, label]) => (
                <button
                  key={v}
                  onClick={() => setView(v)}
                  className={cn(
                    "inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs transition",
                    view === v ? "bg-white/10 text-white" : "text-slate-500 hover:text-slate-300",
                  )}
                >
                  <Icon className="h-3.5 w-3.5" /> {label}
                </button>
              ))}
            </div>
          </div>
          {loading ? (
            <Skeleton className="h-56 w-full" />
          ) : view === "chart" ? (
            <ColumnChart data={chartData} />
          ) : (
            <div className="max-h-56 overflow-y-auto">
              <table className="w-full text-sm">
                <thead className="sticky top-0 bg-ink-850 text-left text-xs text-slate-500">
                  <tr>
                    <th className="py-1.5 font-medium">Sana</th>
                    {CATEGORY_ORDER.map((c) => (
                      <th key={c} className="py-1.5 text-right font-medium">{categoryMeta(c).label}</th>
                    ))}
                    <th className="py-1.5 text-right font-medium">Jami</th>
                  </tr>
                </thead>
                <tbody className="font-mono text-slate-300">
                  {[...(ov?.daily ?? [])].reverse().map((d) => (
                    <tr key={d.day} className="border-t border-white/[0.04]">
                      <td className="py-1.5 font-sans text-slate-400">{d.day}</td>
                      {CATEGORY_ORDER.map((c) => (
                        <td key={c} className="py-1.5 text-right">{d.by_category[c] ?? 0}</td>
                      ))}
                      <td className="py-1.5 text-right text-white">{d.total}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>

        <Card className="p-5">
          <h2 className="font-semibold text-white">Kategoriyalar</h2>
          <p className="mb-5 text-xs text-slate-500">Bazadagi barcha hodisalar</p>
          {loading ? (
            <div className="space-y-4">
              {[0, 1, 2, 3, 4].map((i) => (
                <Skeleton key={i} className="h-8 w-full" />
              ))}
            </div>
          ) : (
            <HBarList
              total={ov?.total_events}
              data={CATEGORY_ORDER.map((c) => ({
                key: c,
                label: categoryMeta(c).label,
                value: ov?.by_category[c] ?? 0,
                icon: categoryMeta(c).icon,
                href: "/dashboard/events",
              }))}
            />
          )}
        </Card>
      </Reveal>

      {/* ---------- Muhim hodisalar + manbalar ---------- */}
      <Reveal className="grid gap-6 lg:grid-cols-3">
        <Card className="overflow-hidden lg:col-span-2">
          <div className="flex items-center justify-between border-b border-white/[0.06] px-5 py-4">
            <div className="flex items-center gap-3">
              <IconBox icon={ShieldAlert} tone="red" size="sm" />
              <div>
                <h2 className="font-semibold text-white">Muhim hodisalar</h2>
                <p className="text-xs text-slate-500">So'nggi ransomware va leak'lar</p>
              </div>
            </div>
            <Link href="/dashboard/events" className="inline-flex items-center gap-1 text-xs text-brand-cyan hover:underline">
              Hammasi <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          </div>
          {loading ? (
            <div className="space-y-3 p-5">
              {[0, 1, 2].map((i) => (
                <Skeleton key={i} className="h-14 w-full" />
              ))}
            </div>
          ) : !ov?.critical.length ? (
            <EmptyState icon={ShieldAlert} title="Muhim hodisa yo'q" description="Ransomware yoki leak topilsa shu yerda chiqadi." />
          ) : (
            <ul>
              {ov.critical.map((e, i) => (
                <li key={e.id} className="animate-fade-in" style={{ animationDelay: `${240 + i * 50}ms` }}>
                  <a
                    href={e.url}
                    target="_blank"
                    rel="noreferrer"
                    className="group flex flex-wrap items-start gap-x-4 gap-y-2 border-b border-white/[0.04] px-5 py-3.5 transition last:border-0 hover:bg-white/[0.03] sm:flex-nowrap"
                  >
                    <div className="mt-0.5">
                      <CategoryBadge category={e.category} />
                    </div>
                    {/* mobil: nishon + vaqt birinchi qatorda, sarlavha to'liq kenglikda pastda */}
                    <div className="order-last min-w-0 basis-full sm:order-none sm:flex-1 sm:basis-0">
                      <div className="truncate text-sm font-medium text-slate-200 group-hover:text-white">{e.title}</div>
                      <div className="mt-0.5 line-clamp-1 text-xs text-slate-500">{e.summary || e.source}</div>
                    </div>
                    <div className="ml-auto flex shrink-0 items-center gap-1.5 text-xs text-slate-500 sm:ml-0">
                      <Clock className="h-3.5 w-3.5" />
                      {timeAgo(e.published ?? e.first_seen)}
                      <ExternalLink className="ml-1 h-3.5 w-3.5 opacity-0 transition group-hover:opacity-100" />
                    </div>
                  </a>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card className="p-5">
          <h2 className="font-semibold text-white">Eng faol manbalar</h2>
          <p className="mb-5 text-xs text-slate-500">Hodisalar soni bo'yicha</p>
          {loading ? (
            <div className="space-y-4">
              {[0, 1, 2, 3].map((i) => (
                <Skeleton key={i} className="h-8 w-full" />
              ))}
            </div>
          ) : (
            <HBarList
              total={ov?.total_events}
              data={(ov?.top_sources ?? []).map((s) => ({
                key: s.source,
                label: s.source.replace(/^TG: /, ""),
                value: s.count,
                icon: s.source.startsWith("TG") ? Send : s.source === "ransomware.live" ? Skull : Globe,
              }))}
            />
          )}
        </Card>
      </Reveal>

      {/* ---------- Modullar ---------- */}
      <Reveal>
        <div className="mb-3 flex items-baseline justify-between">
          <h2 className="font-semibold text-white">Tekshiruv modullari</h2>
          <Link href="/dashboard/history" className="group inline-flex items-center gap-1 text-xs text-slate-500 transition hover:text-brand-cyan">
            Sizning qidiruvlaringiz: <span className="font-mono text-slate-300 group-hover:text-brand-cyan">{ov?.searches_total ?? 0}</span>
            <ArrowRight className="h-3.5 w-3.5" />
          </Link>
        </div>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {MODULES.map((m) => (
            <Link key={m.kind} href={m.href}>
              <Card hover className="group h-full p-5">
                <div className="flex items-start justify-between">
                  <IconBox icon={m.icon} tone={m.tone} />
                  <ArrowRight className="h-4 w-4 text-slate-600 transition group-hover:translate-x-0.5 group-hover:text-brand-cyan" />
                </div>
                <div className="mt-4 font-medium text-white">{m.title}</div>
                <div className="mt-1 text-sm text-slate-500">{m.desc}</div>
                <div className="mt-3 font-mono text-[11px] text-slate-600">
                  {ov?.searches_by_kind[m.kind] ?? 0} ta qidiruv
                </div>
              </Card>
            </Link>
          ))}
        </div>
      </Reveal>
    </div>
  );
}
