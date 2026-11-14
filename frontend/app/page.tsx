"use client";

import {
  Activity,
  ArrowRight,
  AtSign,
  Bell,
  Database,
  Eye,
  Filter,
  Lock,
  Mail,
  Newspaper,
  Phone,
  Radar,
  ScanSearch,
  Scale,
  Send,
  ShieldCheck,
  Skull,
  Users,
  type LucideIcon,
} from "lucide-react";
import Link from "next/link";
import { Badge, ButtonLink, Card, IconBox, LiveDot, Logo } from "@/components/ui";
import type { Tone } from "@/lib/categories";
import { CountUp, Float, Magnetic, Reveal, ScrambleText, Stagger, StaggerItem, TextReveal, Tilt } from "@/components/motion";
import { cn } from "@/lib/cn";

/* ------------------------------------------------------------------ data */
type Feature = {
  icon: LucideIcon;
  tone: Tone;
  eyebrow: string;
  title: string;
  description: string;
  points: { icon: LucideIcon; label: string }[];
  wide?: boolean;
};

const FEATURES: Feature[] = [
  {
    icon: Activity,
    tone: "red",
    eyebrow: "Threat intel",
    title: "Tahdidlar lentasi (Events)",
    description:
      "Markaziy Osiyoga oid kiberhujumlar, sizib chiqishlar va xabarlar bitta lentada — manba, vaqt va kategoriya bilan.",
    points: [
      { icon: Skull, label: "ransomware.live" },
      { icon: Send, label: "Telegram kanal va guruhlar" },
      { icon: Newspaper, label: "Yangilik saytlari (RSS)" },
      { icon: Bell, label: "Ogohlantirishlar" },
    ],
    wide: true,
  },
  {
    icon: AtSign,
    tone: "violet",
    eyebrow: "Username",
    title: "Username qidiruv",
    description: "Bitta taxallusni 13 ta mashhur saytda bir zumda tekshiring.",
    points: [
      { icon: ScanSearch, label: "13 sayt" },
      { icon: Users, label: "Profil havolalari" },
    ],
  },
  {
    icon: Mail,
    tone: "cyan",
    eyebrow: "Email",
    title: "Email tekshiruvi",
    description: "Manzil haqiqiymi va qayerda ishlatilgan — ochiq belgilar orqali.",
    points: [
      { icon: ShieldCheck, label: "Sintaksis" },
      { icon: Database, label: "MX yozuvlari" },
      { icon: Users, label: "Gravatar" },
    ],
  },
  {
    icon: Phone,
    tone: "emerald",
    eyebrow: "Telefon",
    title: "Telefon tekshiruvi",
    description: "Raqam formati bo'yicha davlat, operator va liniya turini aniqlash.",
    points: [
      { icon: Radar, label: "Davlat" },
      { icon: Activity, label: "Operator" },
      { icon: Phone, label: "Tur" },
    ],
  },
];

const STEPS: { icon: LucideIcon; tone: Tone; title: string; text: string }[] = [
  {
    icon: Radar,
    tone: "cyan",
    title: "Yig'ish",
    text: "Ochiq manbalar — ransomware saytlari, Telegram, yangiliklar — muntazam skanerlanadi.",
  },
  {
    icon: Filter,
    tone: "violet",
    title: "Filtrlash (Markaziy Osiyo)",
    text: "Faqat Markaziy Osiyoga tegishli kiberxavfsizlik va leak yozuvlari ajratib olinadi va kategoriyalanadi.",
  },
  {
    icon: Bell,
    tone: "fuchsia",
    title: "Ogohlantirish",
    text: "Yangi tahdid paydo bo'lishi bilan siz darhol xabardor bo'lasiz.",
  },
];

const STATS = [
  { value: "5", label: "manba turi" },
  { value: "13", label: "username sayti" },
  { value: "24/7", label: "monitoring" },
];

/* ------------------------------------------------------------------ hero visual */
const BLIPS = [
  { x: 68, y: 30, c: "bg-red-500", delay: "0s" },
  { x: 30, y: 62, c: "bg-cyan-400", delay: ".6s" },
  { x: 58, y: 72, c: "bg-violet-400", delay: "1.2s" },
  { x: 24, y: 34, c: "bg-amber-400", delay: "1.8s" },
];

/** Server va brauzerda bir xil chiqishi uchun koordinatani yaxlitlaydi (hydration farqi bo'lmasin). */
const r3 = (n: number) => Math.round(n * 1000) / 1000;

function RadarVisual() {
  return (
    <div className="relative mx-auto aspect-square w-full max-w-[460px]">
      {/* glow */}
      <div className="absolute inset-[8%] rounded-full bg-brand-cyan/10 blur-3xl" />
      <div className="absolute inset-[20%] rounded-full bg-brand-violet/15 blur-3xl" />

      {/* radar disc */}
      <div className="absolute inset-0 overflow-hidden rounded-full border border-cyan-400/20 bg-ink-900/60 shadow-glow backdrop-blur-sm">
        {/* grid */}
        <div
          className="absolute inset-0 opacity-60"
          style={{
            backgroundImage:
              "linear-gradient(rgba(34,211,238,.07) 1px, transparent 1px), linear-gradient(90deg, rgba(34,211,238,.07) 1px, transparent 1px)",
            backgroundSize: "28px 28px",
          }}
        />
        {/* sweep beam */}
        <div
          className="absolute inset-0 animate-spin-slow rounded-full"
          style={{
            animationDuration: "6s",
            background:
              "conic-gradient(from 0deg, rgba(34,211,238,0) 0deg, rgba(34,211,238,0) 280deg, rgba(34,211,238,.08) 320deg, rgba(34,211,238,.45) 359deg, rgba(34,211,238,0) 360deg)",
          }}
        />
        {/* rings + crosshair */}
        <svg viewBox="0 0 200 200" className="absolute inset-0 h-full w-full" fill="none">
          {[90, 68, 46, 24].map((r) => (
            <circle key={r} cx="100" cy="100" r={r} stroke="rgba(34,211,238,.18)" strokeWidth=".6" />
          ))}
          <circle cx="100" cy="100" r="90" stroke="url(#ring)" strokeWidth="1.2" />
          <path d="M100 6V194M6 100H194" stroke="rgba(34,211,238,.14)" strokeWidth=".6" />
          <path
            d="M33 33L167 167M167 33L33 167"
            stroke="rgba(139,92,246,.10)"
            strokeWidth=".6"
            strokeDasharray="2 3"
          />
          {Array.from({ length: 36 }).map((_, i) => {
            const a = (i * 10 * Math.PI) / 180;
            const long = i % 3 === 0;
            const r1 = long ? 84 : 87;
            return (
              <line
                key={i}
                x1={r3(100 + Math.cos(a) * r1)}
                y1={r3(100 + Math.sin(a) * r1)}
                x2={r3(100 + Math.cos(a) * 90)}
                y2={r3(100 + Math.sin(a) * 90)}
                stroke="rgba(34,211,238,.35)"
                strokeWidth=".6"
              />
            );
          })}
          <defs>
            <linearGradient id="ring" x1="0" y1="0" x2="200" y2="200">
              <stop offset="0" stopColor="#22d3ee" stopOpacity=".7" />
              <stop offset=".55" stopColor="#8b5cf6" stopOpacity=".5" />
              <stop offset="1" stopColor="#d946ef" stopOpacity=".2" />
            </linearGradient>
          </defs>
        </svg>

        {/* blips */}
        {BLIPS.map((b) => (
          <span
            key={`${b.x}-${b.y}`}
            className="absolute inline-flex h-2.5 w-2.5 -translate-x-1/2 -translate-y-1/2"
            style={{ left: `${b.x}%`, top: `${b.y}%` }}
          >
            <span
              className={cn("absolute inline-flex h-full w-full animate-pulse-ring rounded-full", b.c)}
              style={{ animationDelay: b.delay }}
            />
            <span className={cn("relative inline-flex h-2.5 w-2.5 rounded-full", b.c)} />
          </span>
        ))}

        {/* center */}
        <div className="absolute left-1/2 top-1/2 grid h-12 w-12 -translate-x-1/2 -translate-y-1/2 place-items-center rounded-2xl bg-brand-gradient shadow-glow">
          <Radar className="h-6 w-6 text-white" />
        </div>
      </div>

      {/* outer rotating dashed orbit */}
      <svg
        viewBox="0 0 200 200"
        className="pointer-events-none absolute -inset-[6%] h-[112%] w-[112%] animate-spin-slow"
        style={{ animationDuration: "40s", animationDirection: "reverse" }}
        fill="none"
      >
        <circle cx="100" cy="100" r="98" stroke="rgba(139,92,246,.25)" strokeWidth=".5" strokeDasharray="1 4" />
        <circle cx="100" cy="2" r="1.6" fill="#8b5cf6" />
      </svg>

      {/* floating intel chips */}
      <Float className="absolute -left-2 top-[14%] sm:-left-8" amplitude={10} duration={5.5}>
        <Card className="flex items-center gap-2.5 px-3 py-2">
          <IconBox icon={Skull} tone="red" size="sm" />
          <div className="leading-tight">
            <div className="text-xs font-medium text-white">Ransomware</div>
            <div className="font-mono text-[10px] text-slate-500">.uz · yangi qurbon</div>
          </div>
        </Card>
      </Float>
      <Float className="absolute -right-2 top-[46%] sm:-right-10" amplitude={12} duration={7} delay={1.2}>
        <Card className="flex items-center gap-2.5 px-3 py-2">
          <IconBox icon={Send} tone="sky" size="sm" />
          <div className="leading-tight">
            <div className="text-xs font-medium text-white">TG kanal</div>
            <div className="font-mono text-[10px] text-slate-500">3 ta mos xabar</div>
          </div>
        </Card>
      </Float>
      <Float className="absolute bottom-[6%] left-[8%]" amplitude={7} duration={6} delay={2.4}>
        <Card className="flex items-center gap-2 px-3 py-2">
          <LiveDot tone="emerald" />
          <span className="font-mono text-[11px] text-slate-300">skan: faol</span>
        </Card>
      </Float>
    </div>
  );
}

/* ------------------------------------------------------------------ page */
export default function Home() {
  return (
    <div className="relative min-h-screen overflow-x-hidden">
      {/* background glows */}
      <div className="pointer-events-none absolute -top-40 left-1/2 h-[36rem] w-[60rem] -translate-x-1/2 rounded-full bg-brand-violet/10 blur-[120px]" />

      {/* nav */}
      <header className="sticky top-0 z-30 border-b border-white/[0.06] bg-ink-950/70 backdrop-blur-xl">
        <nav className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4 sm:px-6">
          <Link href="/" aria-label="Bosh sahifa">
            <Logo />
          </Link>
          <div className="flex items-center gap-2">
            <ButtonLink href="/login" variant="ghost" size="sm" className="sm:h-10 sm:px-4 sm:text-sm">
              Kirish
            </ButtonLink>
            <ButtonLink href="/register" size="sm" icon={ArrowRight} className="sm:h-10 sm:px-4 sm:text-sm">
              Boshlash
            </ButtonLink>
          </div>
        </nav>
      </header>

      <main className="relative">
        {/* hero */}
        <section className="mx-auto grid max-w-6xl items-center gap-14 px-4 pb-20 pt-14 sm:px-6 lg:grid-cols-[1.1fr_1fr] lg:pt-24">
          <div>
            <div className="animate-fade-in">
              <Badge tone="cyan" className="gap-2 px-3 py-1 font-mono text-[11px] uppercase tracking-[0.18em]">
                <LiveDot tone="cyan" />
                <ScrambleText text="OSINT · Markaziy Osiyo" delay={0.2} />
              </Badge>
            </div>
            <h1 className="mt-6 text-4xl font-semibold leading-[1.08] tracking-tight text-white sm:text-5xl lg:text-6xl">
              <TextReveal text="Tahdidlarni birinchi bo'lib ko'ring." gradientWords={[1, 2]} delay={0.15} />
            </h1>
            <p
              className="mt-5 max-w-xl animate-fade-in text-base leading-relaxed text-slate-400 sm:text-lg"
              style={{ animationDelay: "160ms" }}
            >
              Markaziy Osiyo uchun ochiq manbalar razvedkasi va tahdidlar monitoringi — ransomware hujumlari,
              Telegram, yangiliklar va identifikator tekshiruvi bitta platformada.
            </p>
            <div
              className="mt-8 flex animate-fade-in flex-col gap-3 sm:flex-row"
              style={{ animationDelay: "240ms" }}
            >
              <Magnetic>
                <ButtonLink href="/register" size="lg" icon={ArrowRight} className="w-full flex-row-reverse">
                  Boshlash
                </ButtonLink>
              </Magnetic>
              <ButtonLink href="/login" size="lg" variant="secondary">
                Kirish
              </ButtonLink>
            </div>

            <dl
              className="mt-10 grid max-w-md animate-fade-in grid-cols-3 gap-4 border-t border-white/[0.06] pt-6"
              style={{ animationDelay: "320ms" }}
            >
              {STATS.map((s) => (
                <div key={s.label}>
                  <dt className="sr-only">{s.label}</dt>
                  <dd className="font-mono text-2xl font-semibold tabular-nums text-white">
                    {/^\d+$/.test(s.value) ? <CountUp value={Number(s.value)} duration={1.6} /> : s.value}
                  </dd>
                  <dd className="mt-0.5 text-xs text-slate-500">{s.label}</dd>
                </div>
              ))}
            </dl>
          </div>

          <div className="animate-fade-in px-6 sm:px-10 lg:px-0" style={{ animationDelay: "200ms" }}>
            <RadarVisual />
          </div>
        </section>

        {/* features */}
        <section className="mx-auto max-w-6xl px-4 py-16 sm:px-6">
          <Reveal className="mb-10 max-w-2xl">
            <div className="font-mono text-[11px] uppercase tracking-[0.2em] text-brand-cyan/80">Modullar</div>
            <h2 className="mt-2 text-3xl font-semibold tracking-tight text-white sm:text-4xl">
              Razvedka uchun kerakli <span className="text-gradient">hamma narsa</span>
            </h2>
            <p className="mt-3 text-slate-400">
              Monitoringdan tortib bitta identifikatorni chuqur tekshirishgacha — to'rtta asosiy modul.
            </p>
          </Reveal>

          <Stagger className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3" stagger={0.09}>
            {FEATURES.map((f) => (
              <StaggerItem key={f.title} className={cn(f.wide && "sm:col-span-2 lg:col-span-2 lg:row-span-1")}>
              <Tilt className="h-full" max={f.wide ? 3 : 6}>
              <Card hover glow={f.wide} className="group relative h-full overflow-hidden p-6">
                {f.wide && (
                  <div className="pointer-events-none absolute -right-20 -top-20 h-64 w-64 rounded-full bg-red-500/10 blur-3xl" />
                )}
                <div className="relative flex items-start justify-between gap-4">
                  <IconBox icon={f.icon} tone={f.tone} size="lg" />
                  <span className="kbd uppercase tracking-wider">{f.eyebrow}</span>
                </div>
                <h3 className="relative mt-5 text-lg font-semibold text-white">{f.title}</h3>
                <p className="relative mt-1.5 text-sm leading-relaxed text-slate-400">{f.description}</p>
                <div className="relative mt-5 flex flex-wrap gap-2">
                  {f.points.map((p) => (
                    <Badge key={p.label} tone={f.tone} icon={p.icon} className="px-2.5 py-1 text-xs">
                      {p.label}
                    </Badge>
                  ))}
                </div>
              </Card>
              </Tilt>
              </StaggerItem>
            ))}

            <StaggerItem className="sm:col-span-2 lg:col-span-1">
            <Card className="relative flex h-full flex-col justify-between overflow-hidden bg-brand-gradient-soft p-6">
              <div>
                <IconBox icon={Eye} tone="fuchsia" size="lg" />
                <h3 className="mt-5 text-lg font-semibold text-white">Bitta oynada nazorat</h3>
                <p className="mt-1.5 text-sm leading-relaxed text-slate-300">
                  Statistika, filtrlar va qidiruv tarixi — hammasi boshqaruv panelida.
                </p>
              </div>
              <Link
                href="/register"
                className="mt-6 inline-flex items-center gap-1.5 text-sm font-medium text-cyan-300 transition hover:gap-2.5 hover:text-cyan-200"
              >
                Hisob ochish <ArrowRight className="h-4 w-4" />
              </Link>
            </Card>
            </StaggerItem>
          </Stagger>
        </section>

        {/* how it works */}
        <section className="mx-auto max-w-6xl px-4 py-16 sm:px-6">
          <Reveal className="mb-10 text-center">
            <div className="font-mono text-[11px] uppercase tracking-[0.2em] text-brand-cyan/80">Qanday ishlaydi</div>
            <h2 className="mt-2 text-3xl font-semibold tracking-tight text-white sm:text-4xl">
              Uch qadam — <span className="text-gradient">manbadan signalgacha</span>
            </h2>
          </Reveal>

          <Stagger className="relative grid gap-4 md:grid-cols-3" stagger={0.16}>
            {/* connector line */}
            <div className="pointer-events-none absolute left-[16%] right-[16%] top-[52px] hidden h-px bg-gradient-to-r from-cyan-400/40 via-violet-400/40 to-fuchsia-400/40 md:block" />
            {STEPS.map((s, i) => (
              <StaggerItem key={s.title}>
              <Card hover className="relative h-full p-6 text-center">
                <div className="relative mx-auto w-fit">
                  <div className="absolute inset-0 rounded-2xl bg-brand-cyan/10 blur-xl" />
                  <IconBox icon={s.icon} tone={s.tone} size="lg" className="relative h-14 w-14" />
                </div>
                <div className="mt-4 font-mono text-[11px] tracking-[0.2em] text-slate-500">
                  0{i + 1}
                </div>
                <h3 className="mt-1 text-lg font-semibold text-white">{s.title}</h3>
                <p className="mx-auto mt-2 max-w-xs text-sm leading-relaxed text-slate-400">{s.text}</p>
              </Card>
              </StaggerItem>
            ))}
          </Stagger>
        </section>

        {/* ethics */}
        <section className="mx-auto max-w-6xl px-4 py-16 sm:px-6">
          <Reveal>
          <Card glow className="relative overflow-hidden p-6 sm:p-10">
            <div className="pointer-events-none absolute -left-24 -top-24 h-72 w-72 rounded-full bg-emerald-500/10 blur-3xl" />
            <div className="relative grid gap-8 lg:grid-cols-[1fr_1.2fr] lg:items-center">
              <div>
                <IconBox icon={Scale} tone="emerald" size="lg" />
                <h2 className="mt-5 text-2xl font-semibold tracking-tight text-white sm:text-3xl">
                  Axloqiy va qonuniy yondashuv
                </h2>
                <p className="mt-3 text-slate-400">
                  Platforma himoya maqsadida ishlaydi: tahdidni oldindan ko'rish va javob berish uchun.
                </p>
              </div>
              <ul className="grid gap-3">
                {[
                  { icon: Eye, t: "Faqat ochiq manbalar", d: "Hech qanday yopiq tizimga kirish yoki buzish yo'q." },
                  {
                    icon: Lock,
                    t: "Leak'larning o'zi saqlanmaydi",
                    d: "Sizib chiqqan ma'lumotlar yuklab olinmaydi va tarqatilmaydi.",
                  },
                  { icon: Database, t: "Faqat metadata", d: "Manba, sana, tashkilot nomi va havola — boshqa hech narsa." },
                ].map((x) => (
                  <li
                    key={x.t}
                    className="flex items-start gap-3 rounded-xl border border-white/[0.06] bg-ink-900/50 p-4"
                  >
                    <IconBox icon={x.icon} tone="emerald" size="sm" />
                    <div>
                      <div className="text-sm font-medium text-white">{x.t}</div>
                      <div className="mt-0.5 text-sm text-slate-400">{x.d}</div>
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          </Card>
          </Reveal>
        </section>

        {/* final CTA */}
        <section className="mx-auto max-w-6xl px-4 pb-20 pt-4 text-center sm:px-6">
          <Reveal>
          <h2 className="text-3xl font-semibold tracking-tight text-white sm:text-4xl">
            Monitoringni <span className="text-gradient-animated">bugun</span> boshlang
          </h2>
          <p className="mx-auto mt-3 max-w-lg text-slate-400">Ro'yxatdan o'tish bir daqiqa oladi.</p>
          <div className="mt-8 flex flex-col justify-center gap-3 sm:flex-row">
            <ButtonLink href="/register" size="lg" icon={ArrowRight} className="flex-row-reverse">
              Boshlash
            </ButtonLink>
            <ButtonLink href="/login" size="lg" variant="secondary">
              Kirish
            </ButtonLink>
          </div>
          </Reveal>
        </section>
      </main>

      {/* footer */}
      <footer className="border-t border-white/[0.06]">
        <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-4 px-4 py-8 sm:flex-row sm:px-6">
          <Logo />
          <p className="text-center text-xs text-slate-500">
            Faqat qonuniy va axloqiy maqsadlar uchun · Faqat ochiq ma'lumotlar
          </p>
          <span className="font-mono text-[11px] text-slate-600">© {new Date().getFullYear()} OSINT.uz</span>
        </div>
      </footer>
    </div>
  );
}
