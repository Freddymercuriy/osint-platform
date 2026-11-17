"use client";

import { useLocale, useTranslations } from "next-intl";
import { useMemo } from "react";

/* Brauzerlarning ko'pida "uz-UZ" lokali to'liq emas ("2026 M09 22") — o'zbekcha oy nomlari qo'lda; ru/en — Intl. */
const UZ_MONTHS = ["yanvar", "fevral", "mart", "aprel", "may", "iyun", "iyul", "avgust", "sentabr", "oktabr", "noyabr", "dekabr"];
const UZ_MONTHS_SHORT = ["yan", "fev", "mar", "apr", "may", "iyn", "iyl", "avg", "sen", "okt", "noy", "dek"];
// O'zbek kirill (latin.jaybi.uz qoidalari: yanvar → январь ...)
const UZC_MONTHS = ["январь", "февраль", "март", "апрель", "май", "июнь", "июль", "август", "сентябрь", "октябрь", "ноябрь", "декабрь"];
const UZC_MONTHS_SHORT = ["янв", "фев", "мар", "апр", "май", "июн", "июл", "авг", "сен", "окт", "ноя", "дек"];
const pad2 = (n: number) => String(n).padStart(2, "0");
const TZ = "Asia/Tashkent";

type DateLike = Date | string | number | null | undefined;

function toDate(v: DateLike): Date | null {
  if (v === null || v === undefined || v === "") return null;
  const d = v instanceof Date ? v : new Date(v);
  return Number.isNaN(d.getTime()) ? null : d;
}

/** Toshkent vaqtidagi kalendar qismlari (brauzer zonasidan qat'i nazar). */
function parts(d: Date) {
  const p = Object.fromEntries(
    new Intl.DateTimeFormat("en-GB", {
      timeZone: TZ, year: "numeric", month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit", hourCycle: "h23",
    }).formatToParts(d).map((x) => [x.type, x.value]),
  );
  return { y: Number(p.year), m: Number(p.month) - 1, d: Number(p.day), h: Number(p.hour), min: Number(p.minute) };
}

export function formatDate(locale: string, v: DateLike, opts: { short?: boolean; year?: boolean } = {}): string {
  const d = toDate(v);
  if (!d) return "";
  if (locale === "uz" || locale === "uz-Cyrl") {
    const p = parts(d);
    const cyr = locale === "uz-Cyrl";
    const month = (opts.short ? (cyr ? UZC_MONTHS_SHORT : UZ_MONTHS_SHORT) : cyr ? UZC_MONTHS : UZ_MONTHS)[p.m];
    return `${p.d} ${month}${opts.year === false ? "" : ` ${p.y}`}`;
  }
  return new Intl.DateTimeFormat(locale === "ru" ? "ru-RU" : "en-GB", {
    timeZone: TZ, day: "numeric", month: opts.short ? "short" : "long", ...(opts.year === false ? {} : { year: "numeric" }),
  }).format(d);
}

export function formatTime(v: DateLike): string {
  const d = toDate(v);
  if (!d) return "";
  const p = parts(d);
  return `${pad2(p.h)}:${pad2(p.min)}`;
}

export function formatNumber(locale: string, n: number | null | undefined, opts: Intl.NumberFormatOptions = {}): string {
  if (n === null || n === undefined || Number.isNaN(n)) return "—";
  if (locale === "uz" || locale === "uz-Cyrl") {
    // 12 345,6 — o'zbek an'anasi (bo'shliq bilan guruhlash)
    return new Intl.NumberFormat("ru-RU", opts).format(n);
  }
  return new Intl.NumberFormat(locale === "ru" ? "ru-RU" : "en-US", opts).format(n);
}

/** Sahifalarda: const f = useFormat(); f.date(x), f.dateTime(x), f.ago(x), f.number(n). */
export function useFormat() {
  const locale = useLocale();
  const t = useTranslations("time");
  return useMemo(
    () => ({
      locale,
      date: (v: DateLike, opts?: { short?: boolean; year?: boolean }) => formatDate(locale, v, opts),
      time: (v: DateLike) => formatTime(v),
      dateTime: (v: DateLike) => {
        const date = formatDate(locale, v);
        return date ? `${date}, ${formatTime(v)}` : "";
      },
      number: (n: number | null | undefined, opts?: Intl.NumberFormatOptions) => formatNumber(locale, n, opts),
      percent: (n: number | null | undefined, digits = 0) =>
        formatNumber(locale, n, { style: "percent", maximumFractionDigits: digits }),
      /** "5 daqiqa oldin"; bir haftadan eski bo'lsa — sana */
      ago: (v: DateLike) => {
        const d = toDate(v);
        if (!d) return "";
        const diff = (Date.now() - d.getTime()) / 1000;
        if (diff < 0) {
          const ahead = -diff;
          if (ahead < 3600) return t("inMinutes", { count: Math.max(1, Math.round(ahead / 60)) });
          if (ahead < 86400) return t("inHours", { count: Math.round(ahead / 3600) });
          return formatDate(locale, d, { short: true });
        }
        if (diff < 60) return t("justNow");
        if (diff < 3600) return t("minutesAgo", { count: Math.floor(diff / 60) });
        if (diff < 86400) return t("hoursAgo", { count: Math.floor(diff / 3600) });
        if (diff < 86400 * 7) return t("daysAgo", { count: Math.floor(diff / 86400) });
        return formatDate(locale, d, { short: true });
      },
    }),
    [locale, t],
  );
}
