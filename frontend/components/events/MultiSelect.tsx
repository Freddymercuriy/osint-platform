"use client";

import { Check, ChevronDown, Search } from "lucide-react";
import { useTranslations } from "next-intl";
import { useEffect, useId, useMemo, useRef, useState } from "react";
import { useFormat } from "@/lib/format";
import { cn } from "@/lib/cn";

export type Option = { value: string; label: string; count?: number };

/** Ko'p tanlovli ochiladigan ro'yxat (checkbox'lar); ixtiyoriy qidiruv. */
export function MultiSelect({
  label,
  options,
  value,
  onChange,
  searchable,
}: {
  label: string;
  options: Option[];
  value: string[];
  onChange: (next: string[]) => void;
  searchable?: boolean;
}) {
  const t = useTranslations("events.filters");
  const f = useFormat();
  const [open, setOpen] = useState(false);
  const [needle, setNeedle] = useState("");
  const root = useRef<HTMLDivElement>(null);
  const btn = useRef<HTMLButtonElement>(null);
  const id = useId();

  useEffect(() => {
    if (!open) return;
    const onDoc = (ev: MouseEvent) => {
      if (root.current && !root.current.contains(ev.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [open]);

  const shown = useMemo(() => {
    const n = needle.trim().toLowerCase();
    return n ? options.filter((o) => o.label.toLowerCase().includes(n)) : options;
  }, [options, needle]);

  const toggle = (v: string) => onChange(value.includes(v) ? value.filter((x) => x !== v) : [...value, v]);
  const summary =
    value.length === 0
      ? t("any")
      : value.length === 1
        ? (options.find((o) => o.value === value[0])?.label ?? value[0])
        : t("selected", { count: value.length });

  return (
    <div
      ref={root}
      className="relative min-w-0"
      onKeyDown={(ev) => {
        if (ev.key === "Escape" && open) {
          ev.stopPropagation();
          setOpen(false);
          btn.current?.focus();
        }
      }}
    >
      <button
        ref={btn}
        type="button"
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={`${id}-list`}
        onClick={() => setOpen((v) => !v)}
        className={cn(
          "focus-ring flex h-10 w-full items-center gap-2 rounded-lg border bg-surface px-3 text-left text-sm transition-colors hover:border-border-strong",
          value.length ? "border-primary" : "border-border",
        )}
      >
        <span className="shrink-0 text-fg-muted">{label}</span>
        <span className={cn("min-w-0 flex-1 truncate text-right", value.length ? "font-medium text-fg" : "text-fg-subtle")}>
          {summary}
        </span>
        <ChevronDown className={cn("h-4 w-4 shrink-0 text-fg-muted transition-transform", open && "rotate-180")} aria-hidden />
      </button>

      {open && (
        <div className="absolute left-0 z-30 mt-1 w-full min-w-[14rem] max-w-[calc(100vw-2rem)] rounded-lg border border-border bg-surface p-1.5 shadow-lg">
          {searchable && (
            <div className="relative mb-1.5">
              <Search className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-fg-subtle" aria-hidden />
              <input
                autoFocus
                value={needle}
                onChange={(ev) => setNeedle(ev.target.value)}
                placeholder={t("searchOptions")}
                aria-label={`${label}: ${t("searchOptions")}`}
                className="h-9 w-full rounded-md border border-border bg-bg pl-8 pr-2 text-sm text-fg placeholder:text-fg-subtle focus:border-ring focus:outline-none focus:ring-2 focus:ring-ring/30"
              />
            </div>
          )}
          <ul id={`${id}-list`} role="listbox" aria-multiselectable aria-label={label} className="max-h-64 overflow-y-auto">
            {shown.length === 0 && <li className="px-2 py-2 text-xs text-fg-muted">{t("noOptions")}</li>}
            {shown.map((o) => {
              const on = value.includes(o.value);
              return (
                <li key={o.value} role="option" aria-selected={on}>
                  <button
                    type="button"
                    onClick={() => toggle(o.value)}
                    className="focus-ring flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm text-fg hover:bg-surface-2"
                  >
                    <span
                      className={cn(
                        "grid h-4 w-4 shrink-0 place-items-center rounded border",
                        on ? "border-primary bg-primary text-primary-fg" : "border-border-strong bg-surface",
                      )}
                      aria-hidden
                    >
                      {on && <Check className="h-3 w-3" />}
                    </span>
                    <span className="min-w-0 flex-1 truncate">{o.label}</span>
                    {o.count !== undefined && (
                      <span className="font-mono text-xs tabular-nums text-fg-muted">{f.number(o.count)}</span>
                    )}
                  </button>
                </li>
              );
            })}
          </ul>
          {value.length > 0 && (
            <button
              type="button"
              onClick={() => onChange([])}
              className="focus-ring mt-1 w-full rounded-md px-2 py-1.5 text-left text-xs font-medium text-primary hover:bg-primary-soft"
            >
              {t("clearGroup")}
            </button>
          )}
        </div>
      )}
    </div>
  );
}
