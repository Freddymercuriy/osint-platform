"use client";

import { Check, FileJson, Printer } from "lucide-react";
import { useTranslations } from "next-intl";
import { useEffect, useRef, useState } from "react";
import { Spinner } from "@/components/ui";
import { cn } from "@/lib/cn";
import { downloadReportJson, reportPrintHref } from "@/lib/report";

const BTN =
  "focus-ring inline-flex h-8 items-center gap-1.5 rounded-lg border border-border bg-surface px-2.5 text-xs font-medium text-fg transition-colors hover:bg-surface-2 disabled:opacity-50";

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
  const t = useTranslations("checks.export");
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
      onError?.(err instanceof Error ? err.message : t("downloadError"));
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
        aria-label={t("jsonAria")}
        title={t("jsonTitle")}
        className={BTN}
      >
        {busy ? (
          <Spinner className="h-3.5 w-3.5" />
        ) : done ? (
          <Check className="h-3.5 w-3.5 text-success" />
        ) : (
          <FileJson className="h-3.5 w-3.5" />
        )}
        <span className={text}>JSON</span>
      </button>
      <a
        href={reportPrintHref(jobId)}
        target="_blank"
        rel="noopener"
        aria-label={t("pdfAria")}
        title={t("pdfTitle")}
        className={BTN}
      >
        <Printer className="h-3.5 w-3.5" />
        <span className={text}>PDF</span>
      </a>
    </div>
  );
}
