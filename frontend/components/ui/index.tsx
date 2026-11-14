"use client";

/**
 * Umumiy komponentlar — faqat semantik tokenlar (Light/Dark/System). Qo'llanma: docs/design-system.md
 */

import { CheckCircle2, CircleHelp, Loader2, XCircle, type LucideIcon } from "lucide-react";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { forwardRef } from "react";
import { cn } from "@/lib/cn";
import { SEVERITY_TONE, type Tone } from "@/lib/categories";
import { useCategories } from "@/lib/useCategories";

export { useFormat } from "@/lib/format";

/* ------------------------------------------------------------------ tone yordamchilari */
/** Nishon/yorliq: `tone-<rang>` + fon/matn/chegara tokenlari. */
export function toneClass(tone: Tone) {
  return `tone-${tone} border-tone-border bg-tone-bg text-tone-fg`;
}

/** Faqat matn rangi (tone). */
export function toneText(tone: Tone) {
  return `tone-${tone} text-tone-fg`;
}

/* ------------------------------------------------------------------ Card */
export function Card({
  className,
  hover,
  glow: _glow,
  children,
  ...rest
}: React.HTMLAttributes<HTMLDivElement> & { hover?: boolean; glow?: boolean }) {
  return (
    <div className={cn("card", hover && "transition-colors hover:border-border-strong", className)} {...rest}>
      {children}
    </div>
  );
}

/* ------------------------------------------------------------------ Button */
type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";
type ButtonSize = "sm" | "md" | "lg";

const BTN_VARIANT: Record<ButtonVariant, string> = {
  primary: "bg-primary text-primary-fg shadow-sm hover:bg-primary/90",
  secondary: "border border-border bg-surface text-fg hover:bg-surface-2",
  ghost: "text-fg-muted hover:bg-surface-2 hover:text-fg",
  danger: "tone-red border border-tone-border bg-tone-bg text-tone-fg hover:brightness-95",
};
const BTN_SIZE: Record<ButtonSize, string> = {
  sm: "h-8 gap-1.5 rounded-lg px-3 text-xs",
  md: "h-10 gap-2 rounded-lg px-4 text-sm",
  lg: "h-11 gap-2 rounded-lg px-5 text-base",
};
const BTN_BASE =
  "inline-flex select-none items-center justify-center font-medium transition-colors focus-ring disabled:cursor-not-allowed disabled:opacity-50";

type ButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant;
  size?: ButtonSize;
  loading?: boolean;
  icon?: LucideIcon;
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = "primary", size = "md", loading, icon: Icon, className, children, disabled, type = "button", ...rest },
  ref,
) {
  return (
    <button
      ref={ref}
      type={type}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      className={cn(BTN_BASE, BTN_VARIANT[variant], BTN_SIZE[size], className)}
      {...rest}
    >
      {loading ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> : Icon ? <Icon className="h-4 w-4" aria-hidden /> : null}
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
    <Link href={href} className={cn(BTN_BASE, BTN_VARIANT[variant], BTN_SIZE[size], className)}>
      {Icon && <Icon className="h-4 w-4" aria-hidden />}
      {children}
    </Link>
  );
}

/* ------------------------------------------------------------------ Input / Select */
const FIELD =
  "w-full rounded-lg border border-border bg-surface text-fg placeholder:text-fg-subtle transition-colors " +
  "hover:border-border-strong focus:border-ring focus:outline-none focus:ring-2 focus:ring-ring/30";

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
        <Icon className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-fg-subtle" aria-hidden />
      )}
      <input
        ref={ref}
        className={cn(FIELD, inputSize === "lg" ? "h-11 text-base" : "h-10 text-sm", Icon ? "pl-9 pr-3" : "px-3",
          mono && "font-mono", className)}
        {...rest}
      />
    </div>
  );
}
);

export const Select = forwardRef<HTMLSelectElement, React.SelectHTMLAttributes<HTMLSelectElement>>(function Select(
  { className, children, ...rest },
  ref,
) {
  return (
    <select ref={ref} className={cn(FIELD, "h-10 px-3 text-sm", className)} {...rest}>
      {children}
    </select>
  );
});

export function Label({ children, htmlFor }: { children: React.ReactNode; htmlFor?: string }) {
  return (
    <label htmlFor={htmlFor} className="mb-1.5 block text-sm font-medium text-fg">
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
  title,
}: {
  tone?: Tone;
  icon?: LucideIcon;
  className?: string;
  children: React.ReactNode;
  title?: string;
}) {
  return (
    <span
      title={title}
      className={cn("inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium", toneClass(tone), className)}
    >
      {Icon && <Icon className="h-3 w-3" aria-hidden />}
      {children}
    </span>
  );
}

/** Kategoriya yorlig'i — nom (interfeys tilida), rang va ikon bazadan. */
export function CategoryBadge({ category }: { category: string }) {
  const { bySlug } = useCategories();
  const c = bySlug(category);
  return (
    <Badge tone={c.tone} icon={c.Icon} title={c.description || undefined}>
      {c.name}
    </Badge>
  );
}

/** Jiddiylik: critical / high / medium / low / info. */
export function SeverityBadge({ severity }: { severity: string }) {
  const t = useTranslations("severity");
  const known = ["critical", "high", "medium", "low", "info"].includes(severity);
  return <Badge tone={SEVERITY_TONE[severity] ?? "slate"}>{known ? t(severity) : severity}</Badge>;
}

/** Qidiruv natijasi holati: found / not_found / error. */
export function StatusBadge({ status }: { status: string }) {
  const t = useTranslations("common");
  if (status === "found") return <Badge tone="green" icon={CheckCircle2}>{t("status_found")}</Badge>;
  if (status === "not_found") return <Badge tone="slate" icon={XCircle}>{t("status_not_found")}</Badge>;
  return <Badge tone="amber" icon={CircleHelp}>{t("status_unclear")}</Badge>;
}

/* ------------------------------------------------------------------ IconBox */
export function IconBox({
  icon: Icon,
  tone = "blue",
  size = "md",
  className,
}: {
  icon: LucideIcon;
  tone?: Tone;
  size?: "sm" | "md" | "lg";
  className?: string;
}) {
  const s = size === "lg" ? "h-11 w-11 rounded-xl" : size === "sm" ? "h-8 w-8 rounded-lg" : "h-10 w-10 rounded-lg";
  const i = size === "lg" ? "h-5 w-5" : size === "sm" ? "h-4 w-4" : "h-5 w-5";
  return (
    <div className={cn("grid shrink-0 place-items-center border", toneClass(tone), s, className)} aria-hidden>
      <Icon className={i} />
    </div>
  );
}

/* ------------------------------------------------------------------ PageHeader */
/** Har sahifa: sarlavha → bitta gap tavsif → asosiy amal. */
export function PageHeader({
  icon,
  tone = "blue",
  title,
  description,
  subtitle,
  actions,
}: {
  icon?: LucideIcon;
  tone?: Tone;
  /** @deprecated v1 — ko'rsatilmaydi */
  eyebrow?: string;
  title: React.ReactNode;
  description?: React.ReactNode;
  /** @deprecated `description` ishlating */
  subtitle?: React.ReactNode;
  actions?: React.ReactNode;
}) {
  const desc = description ?? subtitle;
  return (
    <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
      <div className="flex min-w-0 items-start gap-3">
        {icon && <IconBox icon={icon} tone={tone} />}
        <div className="min-w-0">
          <h1 className="text-xl font-semibold tracking-tight text-fg sm:text-2xl">{title}</h1>
          {desc && <p className="mt-1 max-w-2xl text-sm text-fg-muted">{desc}</p>}
        </div>
      </div>
      {actions && <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}

/* ------------------------------------------------------------------ StatTile */
export function StatTile({
  label,
  value,
  icon,
  tone = "blue",
  hint,
  loading,
  stacked,
}: {
  label: string;
  value: React.ReactNode;
  icon: LucideIcon;
  tone?: Tone;
  hint?: React.ReactNode;
  loading?: boolean;
  stacked?: boolean;
}) {
  return (
    <Card className={cn("h-full min-w-0", stacked ? "p-4" : "p-5")}>
      <div className={cn("flex items-start justify-between gap-3", stacked && "flex-col-reverse sm:flex-row")}>
        <div className="min-w-0">
          <div className="break-words text-sm text-fg-muted">{label}</div>
          {loading ? (
            <div className="skeleton mt-2 h-8 w-20" />
          ) : (
            <div className="mt-1 text-2xl font-semibold tabular-nums text-fg">{value}</div>
          )}
          {hint && <div className="mt-1 text-xs text-fg-subtle">{hint}</div>}
        </div>
        <IconBox icon={icon} tone={tone} size="sm" />
      </div>
    </Card>
  );
}

/* ------------------------------------------------------------------ holatlar */
/** Bo'sh holat: nima paydo bo'lishini va hozir nega bo'shligini aytadi. */
export function EmptyState({
  icon: Icon,
  title,
  description,
  action,
}: {
  icon: LucideIcon;
  title: string;
  description?: React.ReactNode;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center px-6 py-12 text-center">
      <div className="mb-3 grid h-12 w-12 place-items-center rounded-xl border border-border bg-surface-2 text-fg-subtle">
        <Icon className="h-6 w-6" aria-hidden />
      </div>
      <div className="font-medium text-fg">{title}</div>
      {description && <p className="mt-1 max-w-md text-sm text-fg-muted">{description}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

export function ErrorBanner({ message, action }: { message: string; action?: React.ReactNode }) {
  return (
    <div role="alert" className={cn("flex items-start gap-2 rounded-lg border px-4 py-3 text-sm", toneClass("red"))}>
      <XCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
      <span className="min-w-0 flex-1">{message}</span>
      {action}
    </div>
  );
}

export function Spinner({ className, label }: { className?: string; label?: string }) {
  return (
    <Loader2 role="status" aria-label={label ?? "loading"} className={cn("h-5 w-5 animate-spin text-primary", className)} />
  );
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("skeleton", className)} aria-hidden />;
}

/** Holat nuqtasi (harakatsiz). */
export function LiveDot({ tone = "green" }: { tone?: "green" | "emerald" | "amber" | "red" | "cyan" | "slate" }) {
  const c = { green: "bg-success", emerald: "bg-success", amber: "bg-warning", red: "bg-danger", cyan: "bg-info", slate: "bg-fg-subtle" }[tone];
  return <span className={cn("inline-block h-2 w-2 rounded-full", c)} aria-hidden />;
}

/* ------------------------------------------------------------------ Logo */
export function Logo({ compact }: { compact?: boolean }) {
  const t = useTranslations("common");
  return (
    <div className="flex items-center gap-2.5">
      <div className="grid h-8 w-8 place-items-center rounded-lg bg-primary text-primary-fg" aria-hidden>
        <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="2">
          <circle cx="12" cy="12" r="9" opacity=".5" />
          <circle cx="12" cy="12" r="5" opacity=".8" />
          <circle cx="12" cy="12" r="1.6" fill="currentColor" stroke="none" />
        </svg>
      </div>
      {!compact && (
        <div className="leading-tight">
          <div className="text-[15px] font-semibold tracking-tight text-fg">OSINT</div>
          <div className="hidden text-xs text-fg-subtle sm:block">{t("tagline")}</div>
        </div>
      )}
    </div>
  );
}
