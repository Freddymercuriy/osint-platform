"use client";

import { useRouter } from "next/navigation";
import Link from "next/link";
import { useState } from "react";
import {
  ArrowLeft,
  ArrowRight,
  AtSign,
  Bell,
  Eye,
  EyeOff,
  Lock,
  Mail,
  Radar,
  ShieldCheck,
  type LucideIcon,
} from "lucide-react";
import { Button, Card, ErrorBanner, IconBox, Input, Label, LiveDot, Logo } from "@/components/ui";
import type { Tone } from "@/lib/categories";
import { login } from "@/lib/api";

const VALUE_PROPS: { icon: LucideIcon; tone: Tone; title: string; text: string }[] = [
  {
    icon: Radar,
    tone: "cyan",
    title: "Tahdidlar monitoringi",
    text: "Ransomware, Telegram va yangiliklar — O'zbekiston bo'yicha filtrlangan.",
  },
  {
    icon: AtSign,
    tone: "violet",
    title: "Identifikator tekshiruvi",
    text: "Username, email va telefon raqamini bir necha soniyada tekshiring.",
  },
  {
    icon: Bell,
    tone: "fuchsia",
    title: "Tezkor ogohlantirishlar",
    text: "Yangi hodisa paydo bo'lishi bilan xabardor bo'ling.",
  },
];

function MiniRadar() {
  return (
    <div className="relative h-40 w-40">
      <div className="absolute inset-0 rounded-full bg-brand-cyan/10 blur-2xl" />
      <div className="absolute inset-0 overflow-hidden rounded-full border border-cyan-400/25 bg-ink-900/60 shadow-glow">
        <div
          className="absolute inset-0 animate-spin-slow rounded-full"
          style={{
            animationDuration: "5s",
            background:
              "conic-gradient(from 0deg, rgba(34,211,238,0) 0deg, rgba(34,211,238,0) 280deg, rgba(34,211,238,.08) 320deg, rgba(34,211,238,.45) 359deg, rgba(34,211,238,0) 360deg)",
          }}
        />
        <svg viewBox="0 0 100 100" className="absolute inset-0 h-full w-full" fill="none">
          {[46, 32, 18].map((r) => (
            <circle key={r} cx="50" cy="50" r={r} stroke="rgba(34,211,238,.2)" strokeWidth=".6" />
          ))}
          <path d="M50 4V96M4 50H96" stroke="rgba(34,211,238,.14)" strokeWidth=".6" />
        </svg>
        <span className="absolute left-[68%] top-[30%] inline-flex h-2 w-2">
          <span className="absolute inline-flex h-full w-full animate-pulse-ring rounded-full bg-red-500" />
          <span className="relative inline-flex h-2 w-2 rounded-full bg-red-500" />
        </span>
        <span className="absolute left-[30%] top-[64%] inline-flex h-2 w-2">
          <span
            className="absolute inline-flex h-full w-full animate-pulse-ring rounded-full bg-cyan-400"
            style={{ animationDelay: ".9s" }}
          />
          <span className="relative inline-flex h-2 w-2 rounded-full bg-cyan-400" />
        </span>
        <div className="absolute left-1/2 top-1/2 h-2.5 w-2.5 -translate-x-1/2 -translate-y-1/2 rounded-full bg-brand-gradient shadow-glow" />
      </div>
    </div>
  );
}

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await login(email, password);
      router.push("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Xatolik yuz berdi");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="relative grid min-h-screen overflow-hidden lg:grid-cols-2">
      {/* brand panel */}
      <aside className="relative hidden flex-col justify-between overflow-hidden border-r border-white/[0.06] bg-ink-900/40 p-10 lg:flex xl:p-14">
        <div className="pointer-events-none absolute -left-32 -top-32 h-[28rem] w-[28rem] rounded-full bg-brand-cyan/10 blur-[100px]" />
        <div className="pointer-events-none absolute -bottom-40 right-0 h-[30rem] w-[30rem] rounded-full bg-brand-violet/15 blur-[110px]" />

        <Link href="/" className="relative w-fit animate-fade-in">
          <Logo />
        </Link>

        <div className="relative">
          <div className="animate-fade-in" style={{ animationDelay: "80ms" }}>
            <MiniRadar />
          </div>
          <h2
            className="mt-8 max-w-md animate-fade-in text-3xl font-semibold leading-tight tracking-tight text-white xl:text-4xl"
            style={{ animationDelay: "140ms" }}
          >
            Ochiq manbalar razvedkasi — <span className="text-gradient">bir joyda</span>.
          </h2>
          <ul className="mt-8 space-y-4">
            {VALUE_PROPS.map((v, i) => (
              <li
                key={v.title}
                className="flex animate-fade-in items-start gap-3"
                style={{ animationDelay: `${220 + i * 80}ms` }}
              >
                <IconBox icon={v.icon} tone={v.tone} />
                <div>
                  <div className="text-sm font-medium text-white">{v.title}</div>
                  <div className="mt-0.5 max-w-sm text-sm text-slate-400">{v.text}</div>
                </div>
              </li>
            ))}
          </ul>
        </div>

        <div className="relative flex items-center gap-2 font-mono text-[11px] uppercase tracking-[0.18em] text-slate-500">
          <LiveDot tone="emerald" />
          Monitoring faol · O'zbekiston
        </div>
      </aside>

      {/* form side */}
      <section className="relative flex flex-col items-center justify-center px-4 py-10 sm:px-6">
        <div className="pointer-events-none absolute left-1/2 top-1/3 h-80 w-80 -translate-x-1/2 rounded-full bg-brand-violet/10 blur-[100px] lg:hidden" />

        <div className="relative w-full max-w-md">
          <div className="mb-8 flex items-center justify-between lg:hidden">
            <Link href="/">
              <Logo />
            </Link>
          </div>

          <Link
            href="/"
            className="mb-6 hidden w-fit items-center gap-1.5 text-sm text-slate-500 transition hover:text-slate-300 lg:inline-flex"
          >
            <ArrowLeft className="h-4 w-4" /> Bosh sahifa
          </Link>

          <Card glow className="animate-fade-in p-6 sm:p-8">
            <div className="font-mono text-[11px] uppercase tracking-[0.2em] text-brand-cyan/80">Xush kelibsiz</div>
            <h1 className="mt-1.5 text-2xl font-semibold tracking-tight text-white sm:text-3xl">Kirish</h1>
            <p className="mt-1.5 text-sm text-slate-400">Hisobingizga kirib, monitoringni davom ettiring.</p>

            <form onSubmit={onSubmit} className="mt-7 space-y-5">
              {error && <ErrorBanner message={error} />}

              <div>
                <Label htmlFor="email">Email</Label>
                <Input
                  id="email"
                  type="email"
                  required
                  autoComplete="email"
                  placeholder="siz@misol.uz"
                  icon={Mail}
                  inputSize="lg"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                />
              </div>

              <div>
                <Label htmlFor="password">Parol</Label>
                <div className="relative">
                  <Input
                    id="password"
                    type={showPassword ? "text" : "password"}
                    required
                    autoComplete="current-password"
                    placeholder="••••••••"
                    icon={Lock}
                    inputSize="lg"
                    className="!pr-12"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword((s) => !s)}
                    aria-label={showPassword ? "Parolni yashirish" : "Parolni ko'rsatish"}
                    className="absolute right-2 top-1/2 grid h-8 w-8 -translate-y-1/2 place-items-center rounded-lg text-slate-500 transition hover:bg-white/[0.06] hover:text-slate-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-cyan/60"
                  >
                    {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                </div>
              </div>

              <Button type="submit" size="lg" loading={loading} className="w-full">
                {loading ? "Kirilmoqda..." : "Kirish"}
                {!loading && <ArrowRight className="h-4 w-4" />}
              </Button>
            </form>

            <div className="mt-6 border-t border-white/[0.06] pt-5 text-center text-sm text-slate-500">
              Hisob yo'qmi?{" "}
              <Link href="/register" className="font-medium text-cyan-300 transition hover:text-cyan-200">
                Ro'yxatdan o'tish
              </Link>
            </div>
          </Card>

          <p className="mt-6 flex items-center justify-center gap-1.5 text-center text-xs text-slate-600">
            <ShieldCheck className="h-3.5 w-3.5" />
            Faqat qonuniy va axloqiy maqsadlar uchun
          </p>
        </div>
      </section>
    </main>
  );
}
