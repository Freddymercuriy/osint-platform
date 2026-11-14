"use client";

import { Check, FileJson, Printer } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Spinner } from "@/components/ui";
import { cn } from "@/lib/cn";
import { downloadReportJson, reportPrintHref } from "@/lib/report";

const BTN =
  "inline-flex h-8 items-center gap-1.5 rounded-lg border border-white/10 bg-white/[0.04] px-2.5 text-xs font-medium text-slate-200 transition hover:border-white/20 hover:bg-white/[0.08] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-cyan/60 disabled:opacity-50";

/**
 * Qidiruv hisobotini eksport qilish: JSON fayl va chop etish sahifasi (brauzerda "PDF sifatida saqlash").
 * `labels="always"` — matn doim ko'rinadi; `"sm"` — tor ekranda faqat ikonka.
 */
export default function ExportButtons({
  jobId,
  labels = "sm",
  onError,
  className,
}: {
  jobId: number;
  labels?: "always" | "sm";
  onError?: (message: string | null) => void;
  className?: string;
}) {
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(
    () => () => {
      if (timer.current) clearTimeout(timer.current);
    },
    [],
  );

  async function json() {
    setBusy(true);
    onError?.(null);
    try {
      await downloadReportJson(jobId);
      setDone(true);
      if (timer.current) clearTimeout(timer.current);
      timer.current = setTimeout(() => setDone(false), 1800);
    } catch (err) {
      onError?.(err instanceof Error ? err.message : "Hisobotni yuklab bo'lmadi");
    } finally {
      setBusy(false);
    }
  }

  const text = labels === "always" ? "" : "hidden sm:inline";

  return (
    <div className={cn("flex items-center gap-1.5", className)}>
      <button
        type="button"
        onClick={json}
        disabled={busy}
        aria-label="Hisobotni JSON fayl sifatida yuklash"
        title="JSON hisobotni yuklash"
        className={BTN}
      >
        {busy ? (
          <Spinner className="h-3.5 w-3.5" />
        ) : done ? (
          <Check className="h-3.5 w-3.5 text-emerald-300" />
        ) : (
          <FileJson className="h-3.5 w-3.5" />
        )}
        <span className={text}>JSON</span>
      </button>
      <a
        href={reportPrintHref(jobId)}
        target="_blank"
        rel="noopener"
        aria-label="Hisobotni chop etish yoki PDF sifatida saqlash (yangi oynada)"
        title="Chop etish / PDF"
        className={BTN}
      >
        <Printer className="h-3.5 w-3.5" />
        <span className={text}>PDF</span>
      </a>
    </div>
  );
}
