"use client";

/**
 * OSINT Platform dizayn tizimi — umumiy komponentlar.
 * Qo'llanma: docs/design-system.md
 */

import { CheckCircle2, CircleHelp, Loader2, XCircle, type LucideIcon } from "lucide-react";
import Link from "next/link";
import { forwardRef } from "react";
import { cn } from "@/lib/cn";
import { categoryMeta, type Tone } from "@/lib/categories";

/* ------------------------------------------------------------------ tones */
const TONE: Record<Tone, string> = {
  cyan: "border-cyan-400/25 bg-cyan-400/10 text-cyan-300",
  sky: "border-sky-400/25 bg-sky-400/10 text-sky-300",
  violet: "border-violet-400/25 bg-violet-400/10 text-violet-300",
  fuchsia: "border-fuchsia-400/25 bg-fuchsia-400/10 text-fuchsia-300",
  red: "border-red-400/30 bg-red-500/10 text-red-300",
  orange: "border-orange-400/30 bg-orange-500/10 text-orange-300",
  amber: "border-amber-400/30 bg-amber-500/10 text-amber-300",
  emerald: "border-emerald-400/30 bg-emerald-500/10 text-emerald-300",
  slate: "border-slate-400/20 bg-slate-400/10 text-slate-300",
};

export const TONE_TEXT: Record<Tone, string> = {
  cyan: "text-cyan-300",
  sky: "text-sky-300",
  violet: "text-violet-300",
  fuchsia: "text-fuchsia-300",
  red: "text-red-300",
  orange: "text-orange-300",
  amber: "text-amber-300",
  emerald: "text-emerald-300",
  slate: "text-slate-300",
};

const TONE_ICON_BG: Record<Tone, string> = {
  cyan: "from-cyan-400/25 to-cyan-400/5 text-cyan-300 ring-cyan-400/20",
  sky: "from-sky-400/25 to-sky-400/5 text-sky-300 ring-sky-400/20",
  violet: "from-violet-400/25 to-violet-400/5 text-violet-300 ring-violet-400/20",
  fuchsia: "from-fuchsia-400/25 to-fuchsia-400/5 text-fuchsia-300 ring-fuchsia-400/20",
  red: "from-red-500/25 to-red-500/5 text-red-300 ring-red-400/20",
  orange: "from-orange-500/25 to-orange-500/5 text-orange-300 ring-orange-400/20",
  amber: "from-amber-500/25 to-amber-500/5 text-amber-300 ring-amber-400/20",
  emerald: "from-emerald-500/25 to-emerald-500/5 text-emerald-300 ring-emerald-400/20",
  slate: "from-slate-400/20 to-slate-400/5 text-slate-300 ring-slate-400/15",
};

/* ------------------------------------------------------------------ Card */
export function Card({
  className,
  hover,
  glow,
  children,
  ...rest
}: React.HTMLAttributes<HTMLDivElement> & { hover?: boolean; glow?: boolean }) {
  return (
    <div
      className={cn("glass", hover && "glass-hover", glow && "gradient-border", className)}
      {...rest}
    >
      {children}
    </div>
  );
}

/* ------------------------------------------------------------------ Button */
type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";
type ButtonSize = "sm" | "md" | "lg";

const BTN_VARIANT: Record<ButtonVariant, string> = {
  primary:
    "bg-brand-gradient text-white shadow-glow hover:brightness-110 active:brightness-95 disabled:shadow-none",
  secondary:
    "border border-white/10 bg-white/[0.04] text-slate-200 hover:border-white/20 hover:bg-white/[0.08]",
  ghost: "text-slate-400 hover:bg-white/[0.06] hover:text-slate-100",
  danger: "border border-red-400/30 bg-red-500/10 text-red-300 hover:bg-red-500/20",
};
const BTN_SIZE: Record<ButtonSize, string> = {
  sm: "h-8 gap-1.5 rounded-lg px-3 text-xs",
  md: "h-10 gap-2 rounded-xl px-4 text-sm",
  lg: "h-12 gap-2 rounded-xl px-6 text-base",
};

type ButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant;
  size?: ButtonSize;
  loading?: boolean;
  icon?: LucideIcon;
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = "primary", size = "md", loading, icon: Icon, className, children, disabled, ...rest },
  ref,
) {
  return (
    <button
      ref={ref}
      disabled={disabled || loading}
      className={cn(
        "inline-flex select-none items-center justify-center font-medium transition duration-200",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-cyan/60",
        "disabled:cursor-not-allowed disabled:opacity-50",
        BTN_VARIANT[variant],
        BTN_SIZE[size],
        className,
      )}
      {...rest}
    >
      {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : Icon ? <Icon className="h-4 w-4" /> : null}
      {children}
    </button>
  );
});

/** Havola ko'rinishidagi tugma */
export function ButtonLink({
  href,
  variant = "primary",
  size = "md",
  icon: Icon,
  className,
  children,
}: {
  href: string;
  variant?: ButtonVariant;
  size?: ButtonSize;
  icon?: LucideIcon;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <Link
      href={href}
      className={cn(
        "inline-flex items-center justify-center font-medium transition duration-200",
        BTN_VARIANT[variant],
        BTN_SIZE[size],
        className,
      )}
    >
      {Icon && <Icon className="h-4 w-4" />}
      {children}
    </Link>
  );
}

/* ------------------------------------------------------------------ Input */
type InputProps = React.InputHTMLAttributes<HTMLInputElement> & {
  icon?: LucideIcon;
  mono?: boolean;
  inputSize?: "md" | "lg";
};

export const Input = forwardRef<HTMLInputElement, InputProps>(function Input(
  { icon: Icon, mono, inputSize = "md", className, ...rest },
  ref,
) {
  return (
    <div className="relative w-full">
      {Icon && (
        <Icon className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" />
      )}
      <input
        ref={ref}
        className={cn(
          "w-full rounded-xl border border-white/10 bg-ink-900/80 text-slate-100 placeholder:text-slate-600",
          "outline-none transition focus:border-brand-cyan/50 focus:ring-4 focus:ring-brand-cyan/10",
          inputSize === "lg" ? "h-12 text-base" : "h-10 text-sm",
          Icon ? "pl-10 pr-3.5" : "px-3.5",
          mono && "font-mono",
          className,
        )}
        {...rest}
      />
    </div>
  );
});

export function Label({ children, htmlFor }: { children: React.ReactNode; htmlFor?: string }) {
  return (
    <label htmlFor={htmlFor} className="mb-1.5 block text-xs font-medium uppercase tracking-wider text-slate-400">
      {children}
    </label>
  );
}

/* ------------------------------------------------------------------ Badge */
export function Badge({
  tone = "slate",
  icon: Icon,
  className,
  children,
}: {
  tone?: Tone;
  icon?: LucideIcon;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-medium",
        TONE[tone],
        className,
      )}
    >
      {Icon && <Icon className="h-3 w-3" />}
      {children}
    </span>
  );
}

/** Events kategoriyasi uchun yorliq (rang + ikon + nom). */
export function CategoryBadge({ category }: { category: string }) {
  const m = categoryMeta(category);
  return (
    <Badge tone={m.tone} icon={m.icon}>
      {m.label}
    </Badge>
  );
}

/** Qidiruv natijasi holati: found / not_found / error. */
export function StatusBadge({ status }: { status: string }) {
  if (status === "found")
    return (
      <Badge tone="emerald" icon={CheckCircle2}>
        Topildi
      </Badge>
    );
  if (status === "not_found")
    return (
      <Badge tone="slate" icon={XCircle}>
        Yo'q
      </Badge>
    );
  return (
    <Badge tone="amber" icon={CircleHelp}>
      Noaniq
    </Badge>
  );
}

/* ------------------------------------------------------------------ IconBox */
export function IconBox({
  icon: Icon,
  tone = "cyan",
  size = "md",
  className,
}: {
  icon: LucideIcon;
  tone?: Tone;
  size?: "sm" | "md" | "lg";
  className?: string;
}) {
  const s = size === "lg" ? "h-12 w-12 rounded-2xl" : size === "sm" ? "h-8 w-8 rounded-lg" : "h-10 w-10 rounded-xl";
  const i = size === "lg" ? "h-6 w-6" : size === "sm" ? "h-4 w-4" : "h-5 w-5";
  return (
    <div className={cn("grid shrink-0 place-items-center bg-gradient-to-br ring-1", TONE_ICON_BG[tone], s, className)}>
      <Icon className={i} />
    </div>
  );
}

/* ------------------------------------------------------------------ PageHeader */
export function PageHeader({
  icon,
  tone = "cyan",
  eyebrow,
  title,
  subtitle,
  actions,
}: {
  icon?: LucideIcon;
  tone?: Tone;
  eyebrow?: string;
  title: React.ReactNode;
  subtitle?: React.ReactNode;
  actions?: React.ReactNode;
}) {
  return (
    <div className="mb-6 flex animate-fade-in flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
      <div className="flex items-start gap-4">
        {icon && <IconBox icon={icon} tone={tone} size="lg" />}
        <div>
          {eyebrow && (
            <div className="mb-1 font-mono text-[11px] uppercase tracking-[0.2em] text-brand-cyan/80">
              {eyebrow}
            </div>
          )}
          <h1 className="text-2xl font-semibold tracking-tight text-white sm:text-3xl">{title}</h1>
          {subtitle && <p className="mt-1.5 max-w-2xl text-sm text-slate-400">{subtitle}</p>}
        </div>
      </div>
      {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
    </div>
  );
}

/* ------------------------------------------------------------------ StatTile */
export function StatTile({
  label,
  value,
  icon,
  tone = "cyan",
  hint,
  loading,
}: {
  label: string;
  value: React.ReactNode;
  icon: LucideIcon;
  tone?: Tone;
  hint?: React.ReactNode;
  loading?: boolean;
}) {
  return (
    <Card hover className="relative overflow-hidden p-5">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="text-xs font-medium uppercase tracking-wider text-slate-500">{label}</div>
          {loading ? (
            <div className="skeleton mt-2 h-8 w-20" />
          ) : (
            <div className="mt-1.5 font-mono text-3xl font-semibold tabular-nums text-white">{value}</div>
          )}
          {hint && <div className="mt-1 text-xs text-slate-500">{hint}</div>}
        </div>
        <IconBox icon={icon} tone={tone} />
      </div>
    </Card>
  );
}

/* ------------------------------------------------------------------ states */
export function EmptyState({
  icon: Icon,
  title,
  description,
  action,
}: {
  icon: LucideIcon;
  title: string;
  description?: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center px-6 py-14 text-center">
      <div className="relative mb-4">
        <div className="absolute inset-0 rounded-full bg-brand-cyan/10 blur-xl" />
        <div className="relative grid h-14 w-14 place-items-center rounded-2xl border border-white/10 bg-ink-800 text-slate-400">
          <Icon className="h-6 w-6" />
        </div>
      </div>
      <div className="font-medium text-slate-200">{title}</div>
      {description && <p className="mt-1 max-w-sm text-sm text-slate-500">{description}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

export function ErrorBanner({ message }: { message: string }) {
  return (
    <div className="flex items-start gap-2 rounded-xl border border-red-400/25 bg-red-500/10 px-4 py-3 text-sm text-red-300">
      <XCircle className="mt-0.5 h-4 w-4 shrink-0" />
      <span>{message}</span>
    </div>
  );
}

export function Spinner({ className }: { className?: string }) {
  return <Loader2 className={cn("h-5 w-5 animate-spin text-brand-cyan", className)} />;
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("skeleton", className)} />;
}

/** Yonib-o'chib turadigan "jonli" nuqta */
export function LiveDot({ tone = "emerald" }: { tone?: "emerald" | "amber" | "red" | "cyan" }) {
  const c = {
    emerald: "bg-emerald-400",
    amber: "bg-amber-400",
    red: "bg-red-500",
    cyan: "bg-cyan-400",
  }[tone];
  return (
    <span className="relative inline-flex h-2.5 w-2.5">
      <span className={cn("absolute inline-flex h-full w-full animate-pulse-ring rounded-full", c)} />
      <span className={cn("relative inline-flex h-2.5 w-2.5 rounded-full", c)} />
    </span>
  );
}

/* ------------------------------------------------------------------ Logo */
export function Logo({ compact }: { compact?: boolean }) {
  return (
    <div className="flex items-center gap-2.5">
      <div className="relative grid h-9 w-9 place-items-center rounded-xl bg-brand-gradient shadow-glow">
        <svg viewBox="0 0 24 24" className="h-5 w-5 text-white" fill="none" stroke="currentColor" strokeWidth="2">
          <circle cx="12" cy="12" r="9" opacity=".45" />
          <circle cx="12" cy="12" r="5" opacity=".75" />
          <path d="M12 12 L19 6" strokeLinecap="round" />
          <circle cx="12" cy="12" r="1.6" fill="currentColor" stroke="none" />
        </svg>
      </div>
      {!compact && (
        <div className="leading-tight">
          <div className="text-[15px] font-semibold tracking-tight text-white">
            OSINT<span className="text-gradient">.uz</span>
          </div>
          <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-slate-500">
            threat intel
          </div>
        </div>
      )}
    </div>
  );
}

/** Nisbiy vaqt: "5 daq oldin" */
export function timeAgo(iso: string | null | undefined): string {
  if (!iso) return "";
  const d = new Date(iso);
  const diff = (Date.now() - d.getTime()) / 1000;
  if (diff < 60) return "hozirgina";
  if (diff < 3600) return `${Math.floor(diff / 60)} daq oldin`;
  if (diff < 86400) return `${Math.floor(diff / 3600)} soat oldin`;
  if (diff < 86400 * 7) return `${Math.floor(diff / 86400)} kun oldin`;
  return d.toLocaleDateString("uz-UZ", { day: "2-digit", month: "short", year: "numeric" });
}
