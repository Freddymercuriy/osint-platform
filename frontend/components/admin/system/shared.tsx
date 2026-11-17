"use client";

import { useEffect, useRef } from "react";
import { useTranslations } from "next-intl";
import { Card, IconBox } from "@/components/ui";
import type { LucideIcon } from "lucide-react";

export function SectionCard({
  icon,
  title,
  hint,
  actions,
  children,
  id,
}: {
  icon: LucideIcon;
  title: string;
  hint: string;
  actions?: React.ReactNode;
  children: React.ReactNode;
  id: string;
}) {
  return (
    <Card className="p-4 sm:p-5" aria-labelledby={id}>
      <div className="mb-4 flex flex-wrap items-start gap-3">
        <IconBox icon={icon} />
        <div className="min-w-0 flex-1">
          <h2 id={id} className="font-semibold text-fg">{title}</h2>
          <p className="text-sm text-fg-muted">{hint}</p>
        </div>
        {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
      </div>
      {children}
    </Card>
  );
}

export function Fact({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="min-w-0">
      <dt className="text-xs text-fg-muted">{label}</dt>
      <dd className="mt-0.5 break-words text-sm font-medium text-fg">{children}</dd>
    </div>
  );
}

/** Kichik tasdiqlash oynasi: fokus ichiga kiradi, Esc yopadi, yopilganda fokus qaytadi. */
export function ConfirmDialog({
  title,
  body,
  confirmLabel,
  danger,
  busy,
  error,
  onConfirm,
  onCancel,
}: {
  title: string;
  body: string;
  confirmLabel: string;
  danger?: boolean;
  busy?: boolean;
  error?: string | null;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  const t = useTranslations("common");
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const prev = document.activeElement as HTMLElement | null;
    ref.current?.querySelector<HTMLElement>("button")?.focus();
    return () => prev?.focus?.();
  }, []);
  const onKey = (e: React.KeyboardEvent) => {
    if (e.key === "Escape") onCancel();
    if (e.key === "Tab" && ref.current) {
      const els = ref.current.querySelectorAll<HTMLElement>("button:not([disabled])");
      if (!els.length) return;
      const first = els[0];
      const last = els[els.length - 1];
      if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
    }
  };
  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-bg/80 p-4" onKeyDown={onKey}>
      <div
        ref={ref}
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="confirm-title"
        aria-describedby="confirm-body"
        className="card w-full max-w-md p-5 shadow-lg"
      >
        <h3 id="confirm-title" className="font-semibold text-fg">{title}</h3>
        <p id="confirm-body" className="mt-2 text-sm text-fg-muted">{body}</p>
        {error && (
          <p role="alert" className="tone-red mt-3 rounded-lg border border-tone-border bg-tone-bg px-3 py-2 text-sm text-tone-fg">
            {error}
          </p>
        )}
        <div className="mt-5 flex flex-wrap justify-end gap-2">
          <button
            type="button"
            onClick={onCancel}
            className="focus-ring inline-flex h-10 items-center rounded-lg border border-border bg-surface px-4 text-sm font-medium text-fg hover:bg-surface-2"
          >
            {t("cancel")}
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={busy}
            className={
              "focus-ring inline-flex h-10 items-center rounded-lg px-4 text-sm font-medium disabled:opacity-50 " +
              (danger
                ? "tone-red border border-tone-border bg-tone-bg text-tone-fg"
                : "bg-primary text-primary-fg hover:bg-primary/90")
            }
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
