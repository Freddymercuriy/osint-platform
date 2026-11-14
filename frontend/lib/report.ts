import { getJobReport, type JobReport } from "@/lib/api";

/** Fayl nomi uchun xavfsiz bo'lak: "kun.uz" → "kun.uz", "+998 90…" → "998-90…" */
function slug(text: string): string {
  return (
    text
      .toLowerCase()
      .replace(/[^a-z0-9.@_-]+/g, "-")
      .replace(/^-+|-+$/g, "")
      .slice(0, 40) || "sorov"
  );
}

/** Hisobot fayli nomi (kengaytmasiz): "osint-hisobot-domain-kun.uz-17" */
export function reportFileName(job: JobReport["job"]): string {
  return `osint-hisobot-${slug(job.kind)}-${slug(job.query)}-${job.id}`;
}

/** Chop etish (PDF) sahifasi manzili. */
export function reportPrintHref(jobId: number): string {
  return `/report/${jobId}`;
}

/** Hisobotni backend'dan olib, JSON fayl sifatida yuklab beradi. */
export async function downloadReportJson(jobId: number): Promise<void> {
  const report = await getJobReport(jobId);
  const blob = new Blob([JSON.stringify(report, null, 2) + "\n"], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${reportFileName(report.job)}.json`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  // brauzer yuklashni boshlab olishi uchun biroz kutamiz
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
