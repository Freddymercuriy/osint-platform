"use client";

import { X } from "lucide-react";
import { useEffect, useRef } from "react";
import { cn } from "@/lib/cn";

const FOCUSABLE = 'a[href],button:not([disabled]),input:not([disabled]),select:not([disabled]),textarea:not([disabled]),[tabindex]:not([tabindex="-1"])';

/** O'ng tomondagi panel: Esc yopadi, fokus ichkariga kiradi va yopilganda qaytadi, Tab panel ichida aylanadi. */
export default function Drawer({
  title,
  closeLabel,
  onClose,
  wide,
  children,
}: {
  title: string;
  closeLabel: string;
  onClose: () => void;
  wide?: boolean;
  children: React.ReactNode;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;

  useEffect(() => {
    const prev = document.activeElement as HTMLElement | null;
    const el = ref.current;
    const first = el?.querySelector<HTMLElement>("[data-autofocus]") ?? el?.querySelector<HTMLElement>(FOCUSABLE);
    first?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.stopPropagation();
        onCloseRef.current();
        return;
      }
      if (e.key !== "Tab" || !el) return;
      const items = Array.from(el.querySelectorAll<HTMLElement>(FOCUSABLE));
      if (!items.length) return;
      const a = items[0];
      const z = items[items.length - 1];
      if (e.shiftKey && document.activeElement === a) {
        e.preventDefault();
        z.focus();
      } else if (!e.shiftKey && document.activeElement === z) {
        e.preventDefault();
        a.focus();
      }
    };
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("keydown", onKey);
      prev?.focus?.();
    };
  }, []);

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <div className="absolute inset-0 bg-fg/40" onClick={onClose} aria-hidden />
      <div
        ref={ref}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className={cn("relative flex h-full w-full flex-col border-l border-border bg-surface shadow-lg", wide ? "max-w-3xl" : "max-w-xl")}
      >
        <div className="flex items-center justify-between gap-3 border-b border-border px-4 py-3 sm:px-6">
          <h2 className="min-w-0 truncate text-lg font-semibold text-fg">{title}</h2>
          <button type="button" onClick={onClose} aria-label={closeLabel}
            className="grid h-9 w-9 shrink-0 place-items-center rounded-lg text-fg-muted hover:bg-surface-2 hover:text-fg focus-ring">
            <X className="h-5 w-5" aria-hidden />
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}
