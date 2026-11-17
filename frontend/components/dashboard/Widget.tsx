"use client";

import { BarChart3, Download, EyeOff, Info, Table2 } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { EmptyState, ErrorBanner, Skeleton } from "@/components/ui";
import { cn } from "@/lib/cn";
import { downloadCsv } from "@/lib/statsApi";

export type TableData = { header: string[]; rows: (string | number | null | undefined)[][] };

/**
 * Vidjet qobig'i: sarlavha + izoh, Grafik/Jadval almashtirgich, CSV eksport, yashirish.
 * Har vidjetda jadval ko'rinishi bor (rang yolg'iz ma'no tashimasligi uchun ham).
 */
export function Widget({
  id,
  title,
  help,
  loading,
  error,
  empty,
  emptyHint,
  table,
  onHide,
  className,
  noChart,
  actions,
  children,
}: {
  id: string;
  title: string;
  help?: string;
  loading: boolean;
  error?: string | null;
  empty: boolean;
  emptyHint?: string;
  table?: TableData;
  onHide?: () => void;
  className?: string;
  /** Faqat ro'yxat/jadval (grafik yo'q) — almashtirgich ko'rsatilmaydi */
  noChart?: boolean;
  actions?: React.ReactNode;
  children: React.ReactNode;
}) {
  const t = useTranslations("dashboard.widget");
  const [asTable, setAsTable] = useState(false);
  const headingId = `w-${id}`;

  return (
    <section aria-labelledby={headingId} className={cn("card flex min-w-0 flex-col p-4 sm:p-5", className)}>
      <div className="mb-3 flex items-start gap-2">
        <div className="min-w-0 flex-1">
          <h2 id={headingId} className="flex items-center gap-1.5 text-sm font-semibold text-fg">
            {title}
            {help && (
              <span title={help} className="text-fg-subtle" aria-label={help}>
                <Info className="h-3.5 w-3.5" aria-hidden />
              </span>
            )}
          </h2>
        </div>
        <div className="flex shrink-0 items-center gap-0.5">
          {actions}
          {!noChart && table && (
            <button
              type="button"
              onClick={() => setAsTable((v) => !v)}
              aria-pressed={asTable}
              title={asTable ? t("showChart") : t("showTable")}
              aria-label={asTable ? t("showChart") : t("showTable")}
              className="focus-ring grid h-7 w-7 place-items-center rounded-md text-fg-subtle hover:bg-surface-2 hover:text-fg"
            >
              {asTable ? <BarChart3 className="h-4 w-4" /> : <Table2 className="h-4 w-4" />}
            </button>
          )}
          {table && table.rows.length > 0 && (
            <button
              type="button"
              onClick={() => downloadCsv(`osint-${id}.csv`, table.header, table.rows)}
              title={t("csv")}
              aria-label={t("csv")}
              className="focus-ring grid h-7 w-7 place-items-center rounded-md text-fg-subtle hover:bg-surface-2 hover:text-fg"
            >
              <Download className="h-4 w-4" />
            </button>
          )}
          {onHide && (
            <button
              type="button"
              onClick={onHide}
              title={t("hide")}
              aria-label={t("hide")}
              className="focus-ring grid h-7 w-7 place-items-center rounded-md text-fg-subtle hover:bg-surface-2 hover:text-fg"
            >
              <EyeOff className="h-4 w-4" />
            </button>
          )}
        </div>
      </div>
      <div className="min-w-0 flex-1">
        {error ? (
          <ErrorBanner message={error} />
        ) : loading ? (
          <Skeleton className="h-48 w-full" />
        ) : empty ? (
          <EmptyState icon={BarChart3} title={t("empty")} description={emptyHint ?? t("emptyHint")} />
        ) : asTable && table ? (
          <DataTable table={table} />
        ) : (
          children
        )}
      </div>
    </section>
  );
}

export function DataTable({ table }: { table: TableData }) {
  return (
    <div className="max-h-80 overflow-auto rounded-lg border border-border">
      <table className="w-full text-sm">
        <thead className="sticky top-0 bg-surface-2 text-left text-xs text-fg-muted">
          <tr>
            {table.header.map((h, i) => (
              <th key={i} scope="col" className={cn("px-3 py-2 font-medium", i > 0 && "text-right")}>
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {table.rows.map((r, i) => (
            <tr key={i} className="border-t border-border">
              {r.map((c, j) => (
                <td key={j} className={cn("px-3 py-1.5 text-fg", j > 0 && "text-right tabular-nums")}>
                  {c ?? "—"}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
