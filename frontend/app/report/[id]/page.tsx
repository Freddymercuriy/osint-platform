"use client";

import { ArrowLeft, FileJson, Printer, RotateCcw } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { Button, ErrorBanner, Spinner } from "@/components/ui";
import { getJobReport, getToken, type CollectResult, type JobReport } from "@/lib/api";
import { cn } from "@/lib/cn";
import { useFormat } from "@/lib/format";
import { moduleMeta } from "@/lib/modules";
import { downloadReportJson, reportFileName } from "@/lib/report";

/* Hisobot varag'i ataylab OQ (qog'oz) va HAR QANDAY mavzuda yorug' qoladi: u chop etiladi / PDF bo'ladi,
   shuning uchun faqat varaqda aniq yorug' ranglar ishlatiladi. Asboblar paneli esa tokenlardan foydalanadi. */

const STATUS: Record<CollectResult["status"], { key: string; cls: string }> = {
  found: { key: "status_found", cls: "border-emerald-200 bg-emerald-50 text-emerald-800" },
  not_found: { key: "status_not_found", cls: "border-neutral-200 bg-neutral-100 text-neutral-600" },
  error: { key: "status_unclear", cls: "border-amber-200 bg-amber-50 text-amber-800" },
};

function statusOf(s: string) {
  return STATUS[s as CollectResult["status"]] ?? STATUS.error;
}

function Stat({ label, value, accent }: { label: string; value: number; accent?: string }) {
  return (
    <div className="avoid-break rounded-lg border border-neutral-200 px-3 py-2.5">
      <div className="text-[10px] font-semibold uppercase tracking-wider text-neutral-500">{label}</div>
      <div className={cn("mt-0.5 font-mono text-2xl font-semibold tabular-nums", accent ?? "text-neutral-900")}>{value}</div>
    </div>
  );
}

function Sheet({ data }: { data: JobReport }) {
  const t = useTranslations("report");
  const tg = useTranslations("common");
  const tc = useTranslations("checks");
  const f = useFormat();
  const { job, summary, results, report } = data;
  const meta = moduleMeta(job.kind);
  const modName = tc.has(`modules.${job.kind}.title`) ? tc(`modules.${job.kind}.title`) : meta.title;

  return (
    <article className="report-sheet mx-auto w-full max-w-[210mm] bg-white px-6 py-8 text-neutral-800 shadow-2xl ring-1 ring-black/10 sm:rounded-xl sm:px-10 sm:py-10 print:max-w-none print:rounded-none print:p-0 print:shadow-none">
      {/* sarlavha */}
      <header className="flex flex-wrap items-start justify-between gap-x-6 gap-y-3 border-b-2 border-neutral-900 pb-4">
        <div>
          <div className="font-mono text-xs font-semibold uppercase tracking-[0.25em] text-sky-800">OSINT.uz</div>
          <h1 className="mt-1 text-2xl font-bold tracking-tight text-neutral-900">{t("title")}</h1>
        </div>
        <dl className="text-xs text-neutral-600 sm:text-right">
          <div>
            <dt className="inline">{t("reportNo")}: </dt>
            <dd className="inline font-mono font-semibold text-neutral-900">№ {job.id}</dd>
          </div>
          <div>
            <dt className="inline">{t("generatedAt")}: </dt>
            <dd className="inline">{f.dateTime(report.generated_at)}</dd>
          </div>
        </dl>
      </header>

      {/* nishon */}
      <section className="mt-5">
        <div className="text-[10px] font-semibold uppercase tracking-wider text-neutral-500">{t("target")}</div>
        <div className="mt-1 break-all font-mono text-xl font-semibold text-neutral-900">{job.query}</div>
        <dl className="mt-3 grid gap-x-8 gap-y-1 text-sm sm:grid-cols-2 print:grid-cols-2">
          <div className="flex gap-2">
            <dt className="text-neutral-500">{t("module")}:</dt>
            <dd className="font-medium text-neutral-900">{modName}</dd>
          </div>
          <div className="flex gap-2">
            <dt className="text-neutral-500">{t("checkedAt")}:</dt>
            <dd className="font-medium text-neutral-900">{f.dateTime(job.created_at)}</dd>
          </div>
        </dl>
      </section>

      {/* xulosa */}
      <section className="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-4 print:grid-cols-4" aria-label={t("summary")}>
        <Stat label={t("checked")} value={summary.checked} />
        <Stat label={t("found")} value={summary.found} accent="text-emerald-700" />
        <Stat label={t("notFound")} value={summary.not_found} />
        <Stat label={t("unclear")} value={summary.error} accent={summary.error > 0 ? "text-amber-700" : undefined} />
      </section>

      {/* natijalar */}
      <section className="mt-7">
        <h2 className="text-sm font-bold uppercase tracking-wider text-neutral-900">{t("results")}</h2>
        {results.length === 0 ? (
          <p className="mt-3 text-sm text-neutral-500">{t("noResults")}</p>
        ) : (
          <table className="mt-3 w-full table-fixed border-collapse text-left text-[13px]">
            <thead>
              <tr className="border-y border-neutral-300 bg-neutral-100 text-[10px] uppercase tracking-wider text-neutral-600">
                {/* table-fixed: ustun kengliklari birinchi qatordan olinadi. Tor ekranda "Holat" manba ostida chiqadi */}
                <th className="w-[36%] px-2.5 py-2 font-semibold sm:w-[26%]">{t("source")}</th>
                <th className="hidden w-[16%] px-2.5 py-2 font-semibold sm:table-cell">{t("status")}</th>
                <th className="px-2.5 py-2 font-semibold">{t("result")}</th>
              </tr>
            </thead>
            <tbody>
              {results.map((r, i) => {
                const st = statusOf(r.status);
                const badge = (
                  <span
                    className={cn(
                      "inline-block whitespace-nowrap rounded border px-1.5 py-0.5 text-[11px] font-semibold",
                      st.cls,
                    )}
                  >
                    {tg(st.key)}
                  </span>
                );
                return (
                  <tr key={`${r.source}-${i}`} className="border-b border-neutral-200 align-top">
                    <td className="break-words px-2.5 py-2 font-medium text-neutral-900">
                      {r.source}
                      <div className="mt-1 sm:hidden">{badge}</div>
                    </td>
                    <td className="hidden px-2.5 py-2 sm:table-cell">{badge}</td>
                    <td className="px-2.5 py-2">
                      {r.value && r.value !== job.query && (
                        <div className="break-all font-mono text-[12px] text-neutral-900">{r.value}</div>
                      )}
                      {r.detail && <div className="break-words text-neutral-700">{r.detail}</div>}
                      {r.url && (
                        <a
                          href={r.url}
                          target="_blank"
                          rel="noreferrer"
                          className="break-all font-mono text-[11px] text-sky-900 underline decoration-sky-900/30"
                        >
                          {r.url}
                        </a>
                      )}
                      {!r.detail && !r.url && (!r.value || r.value === job.query) && (
                        <span className="text-neutral-400">—</span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </section>

      <footer className="avoid-break mt-8 border-t border-neutral-200 pt-3 text-[11px] leading-relaxed text-neutral-500">
        {t("notice")} · {report.platform}
      </footer>
    </article>
  );
}

export default function ReportPage() {
  const t = useTranslations("report");
  const tg = useTranslations("common");
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const id = Number(params.id);
  const valid = Number.isInteger(id) && id > 0;

  const [data, setData] = useState<JobReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [jsonBusy, setJsonBusy] = useState(false);

  const load = useCallback(() => {
    setError(null);
    getJobReport(id)
      .then(setData)
      .catch((err) => setError(err instanceof Error ? err.message : t("loadFailed")));
  }, [id]);

  useEffect(() => {
    if (!getToken()) {
      router.replace("/login");
      return;
    }
    if (!valid) {
      setError(t("invalidId"));
      return;
    }
    load();
  }, [router, valid, load, t]);

  // "PDF sifatida saqlash" da fayl nomi sahifa sarlavhasidan olinadi
  useEffect(() => {
    if (!data) return;
    const prev = document.title;
    document.title = reportFileName(data.job);
    return () => {
      document.title = prev;
    };
  }, [data]);

  async function json() {
    setJsonBusy(true);
    setError(null);
    try {
      await downloadReportJson(id);
    } catch (err) {
      setError(err instanceof Error ? err.message : t("loadFailed"));
    } finally {
      setJsonBusy(false);
    }
  }

  return (
    <div className="min-h-screen pb-12 print:pb-0">
      {/* asboblar paneli — chop etishda ko'rinmaydi */}
      <div className="sticky top-0 z-40 border-b border-border bg-bg print:hidden">
        <div className="mx-auto flex max-w-[210mm] flex-wrap items-center gap-2 px-4 py-3 sm:px-0">
          <Link
            href="/dashboard/history"
            className="mr-auto inline-flex h-8 items-center gap-1.5 rounded-lg px-2 text-xs font-medium text-fg-muted transition-colors hover:bg-surface-2 hover:text-fg focus-ring"
          >
            <ArrowLeft className="h-4 w-4" />
            {t("back")}
          </Link>
          <Button variant="secondary" size="sm" icon={FileJson} loading={jsonBusy} disabled={!data} onClick={json}>
            JSON
          </Button>
          <Button size="sm" icon={Printer} disabled={!data} onClick={() => window.print()}>
            {t("print")}
          </Button>
        </div>
      </div>

      <div className="px-0 pt-6 sm:px-4 print:p-0">
        {error && (
          <div className="mx-auto mb-4 max-w-[210mm] space-y-3 px-4 sm:px-0 print:hidden">
            <ErrorBanner message={error} />
            {valid && !data && (
              <Button variant="secondary" size="sm" icon={RotateCcw} onClick={load}>
                {tg("retry")}
              </Button>
            )}
          </div>
        )}
        {data ? (
          <>
            <Sheet data={data} />
            <p className="mx-auto mt-4 max-w-[210mm] px-4 text-center text-xs text-fg-muted sm:px-0 print:hidden">
              {t("pdfHint")}
            </p>
          </>
        ) : (
          !error && (
            <div className="grid place-items-center py-24" aria-busy="true" aria-label={t("loadingAria")}>
              <Spinner />
            </div>
          )
        )}
      </div>
    </div>
  );
}
