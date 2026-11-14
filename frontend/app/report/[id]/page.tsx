"use client";

import { ArrowLeft, FileJson, Printer, RotateCcw } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { Button, ErrorBanner, Spinner, formatDateTime } from "@/components/ui";
import { getJobReport, getToken, type CollectResult, type JobReport } from "@/lib/api";
import { cn } from "@/lib/cn";
import { moduleMeta } from "@/lib/modules";
import { downloadReportJson, reportFileName } from "@/lib/report";

/* Hisobot varag'i ataylab OQ (qog'oz): ekranda hujjat ko'rinishi, chop etishda siyoh tejaladi. */

const STATUS: Record<CollectResult["status"], { label: string; cls: string }> = {
  found: { label: "Topildi", cls: "border-emerald-200 bg-emerald-50 text-emerald-800" },
  not_found: { label: "Yo'q", cls: "border-slate-200 bg-slate-100 text-slate-600" },
  error: { label: "Noaniq", cls: "border-amber-200 bg-amber-50 text-amber-800" },
};

function statusOf(s: string) {
  return STATUS[s as CollectResult["status"]] ?? STATUS.error;
}

function Stat({ label, value, accent }: { label: string; value: number; accent?: string }) {
  return (
    <div className="avoid-break rounded-lg border border-slate-200 px-3 py-2.5">
      <div className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">{label}</div>
      <div className={cn("mt-0.5 font-mono text-2xl font-semibold tabular-nums", accent ?? "text-slate-900")}>{value}</div>
    </div>
  );
}

function Sheet({ data }: { data: JobReport }) {
  const { job, summary, results, report } = data;
  const meta = moduleMeta(job.kind);

  return (
    <article className="report-sheet mx-auto w-full max-w-[210mm] bg-white px-6 py-8 text-slate-800 shadow-2xl sm:rounded-xl sm:px-10 sm:py-10 print:max-w-none print:rounded-none print:p-0 print:shadow-none">
      {/* sarlavha */}
      <header className="flex flex-wrap items-start justify-between gap-x-6 gap-y-3 border-b-2 border-slate-900 pb-4">
        <div>
          <div className="font-mono text-xs font-semibold uppercase tracking-[0.25em] text-cyan-700">OSINT.uz</div>
          <h1 className="mt-1 text-2xl font-bold tracking-tight text-slate-900">Tekshiruv hisoboti</h1>
        </div>
        <dl className="text-xs text-slate-600 sm:text-right">
          <div>
            <dt className="inline">Hisobot: </dt>
            <dd className="inline font-mono font-semibold text-slate-900">№ {job.id}</dd>
          </div>
          <div>
            <dt className="inline">Tuzilgan: </dt>
            <dd className="inline">{formatDateTime(report.generated_at)}</dd>
          </div>
        </dl>
      </header>

      {/* nishon */}
      <section className="mt-5">
        <div className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">Nishon</div>
        <div className="mt-1 break-all font-mono text-xl font-semibold text-slate-900">{job.query}</div>
        <dl className="mt-3 grid gap-x-8 gap-y-1 text-sm sm:grid-cols-2 print:grid-cols-2">
          <div className="flex gap-2">
            <dt className="text-slate-500">Modul:</dt>
            <dd className="font-medium text-slate-900">{meta.title}</dd>
          </div>
          <div className="flex gap-2">
            <dt className="text-slate-500">Tekshirilgan vaqt:</dt>
            <dd className="font-medium text-slate-900">{formatDateTime(job.created_at)}</dd>
          </div>
        </dl>
      </section>

      {/* xulosa */}
      <section className="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-4 print:grid-cols-4" aria-label="Xulosa">
        <Stat label="Tekshirildi" value={summary.checked} />
        <Stat label="Topildi" value={summary.found} accent="text-emerald-700" />
        <Stat label="Topilmadi" value={summary.not_found} />
        <Stat label="Noaniq" value={summary.error} accent={summary.error > 0 ? "text-amber-700" : undefined} />
      </section>

      {/* natijalar */}
      <section className="mt-7">
        <h2 className="text-sm font-bold uppercase tracking-wider text-slate-900">Natijalar</h2>
        {results.length === 0 ? (
          <p className="mt-3 text-sm text-slate-500">Bu qidiruvda natija saqlanmagan.</p>
        ) : (
          <table className="mt-3 w-full table-fixed border-collapse text-left text-[13px]">
            <thead>
              <tr className="border-y border-slate-300 bg-slate-100 text-[10px] uppercase tracking-wider text-slate-600">
                {/* table-fixed: ustun kengliklari birinchi qatordan olinadi. Tor ekranda "Holat" manba ostida chiqadi */}
                <th className="w-[36%] px-2.5 py-2 font-semibold sm:w-[26%]">Manba</th>
                <th className="hidden w-[16%] px-2.5 py-2 font-semibold sm:table-cell">Holat</th>
                <th className="px-2.5 py-2 font-semibold">Natija</th>
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
                    {st.label}
                  </span>
                );
                return (
                  <tr key={`${r.source}-${i}`} className="border-b border-slate-200 align-top">
                    <td className="break-words px-2.5 py-2 font-medium text-slate-900">
                      {r.source}
                      <div className="mt-1 sm:hidden">{badge}</div>
                    </td>
                    <td className="hidden px-2.5 py-2 sm:table-cell">{badge}</td>
                    <td className="px-2.5 py-2">
                      {r.value && r.value !== job.query && (
                        <div className="break-all font-mono text-[12px] text-slate-900">{r.value}</div>
                      )}
                      {r.detail && <div className="break-words text-slate-700">{r.detail}</div>}
                      {r.url && (
                        <a
                          href={r.url}
                          target="_blank"
                          rel="noreferrer"
                          className="break-all font-mono text-[11px] text-cyan-800 underline decoration-cyan-800/30"
                        >
                          {r.url}
                        </a>
                      )}
                      {!r.detail && !r.url && (!r.value || r.value === job.query) && (
                        <span className="text-slate-400">—</span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </section>

      <footer className="avoid-break mt-8 border-t border-slate-200 pt-3 text-[11px] leading-relaxed text-slate-500">
        {report.notice} · {report.platform}
      </footer>
    </article>
  );
}

export default function ReportPage() {
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
      .catch((err) => setError(err instanceof Error ? err.message : "Hisobotni yuklab bo'lmadi"));
  }, [id]);

  useEffect(() => {
    if (!getToken()) {
      router.replace("/login");
      return;
    }
    if (!valid) {
      setError("Hisobot raqami noto'g'ri");
      return;
    }
    load();
  }, [router, valid, load]);

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
      setError(err instanceof Error ? err.message : "Hisobotni yuklab bo'lmadi");
    } finally {
      setJsonBusy(false);
    }
  }

  return (
    <div className="min-h-screen pb-12 print:pb-0">
      {/* asboblar paneli — chop etishda ko'rinmaydi */}
      <div className="sticky top-0 z-40 border-b border-white/[0.06] bg-ink-950/80 backdrop-blur-xl print:hidden">
        <div className="mx-auto flex max-w-[210mm] flex-wrap items-center gap-2 px-4 py-3 sm:px-0">
          <Link
            href="/dashboard/history"
            className="mr-auto inline-flex h-8 items-center gap-1.5 rounded-lg px-2 text-xs font-medium text-slate-400 transition hover:bg-white/[0.06] hover:text-slate-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-cyan/60"
          >
            <ArrowLeft className="h-4 w-4" />
            Qidiruv tarixi
          </Link>
          <Button variant="secondary" size="sm" icon={FileJson} loading={jsonBusy} disabled={!data} onClick={json}>
            JSON
          </Button>
          <Button size="sm" icon={Printer} disabled={!data} onClick={() => window.print()}>
            Chop etish / PDF
          </Button>
        </div>
      </div>

      <div className="px-0 pt-6 sm:px-4 print:p-0">
        {error && (
          <div className="mx-auto mb-4 max-w-[210mm] space-y-3 px-4 sm:px-0 print:hidden">
            <ErrorBanner message={error} />
            {valid && !data && (
              <Button variant="secondary" size="sm" icon={RotateCcw} onClick={load}>
                Qayta urinish
              </Button>
            )}
          </div>
        )}
        {data ? (
          <>
            <Sheet data={data} />
            <p className="mx-auto mt-4 max-w-[210mm] px-4 text-center text-xs text-slate-500 sm:px-0 print:hidden">
              PDF olish uchun «Chop etish / PDF» ni bosib, printer o'rniga «PDF sifatida saqlash» ni tanlang.
            </p>
          </>
        ) : (
          !error && (
            <div className="grid place-items-center py-24" aria-busy="true" aria-label="Hisobot yuklanmoqda">
              <Spinner />
            </div>
          )
        )}
      </div>
    </div>
  );
}
