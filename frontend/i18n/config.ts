// uz-Cyrl — o'zbek kirill: messages/uz-Cyrl.json uz.json dan generatsiya qilinadi
// (python3 backend/scripts/gen_uz_cyrl_messages.py — latin.jaybi.uz dvigateli)
export const LOCALES = ["uz", "uz-Cyrl", "ru", "en"] as const;
export type Locale = (typeof LOCALES)[number];
export const DEFAULT_LOCALE: Locale = "uz";
export const LOCALE_COOKIE = "NEXT_LOCALE";

export function isLocale(v: string | null | undefined): v is Locale {
  return !!v && (LOCALES as readonly string[]).includes(v);
}

/** O'zbekcha (lotin yoki kirill)mi — oy nomlari, raqam formati va h.k. uchun. */
export function isUzbek(locale: string): boolean {
  return locale === "uz" || locale === "uz-Cyrl";
}

/** Accept-Language → eng mos til (uz/uz-Cyrl/ru/en), bo'lmasa null. */
export function matchAcceptLanguage(header: string | null | undefined): Locale | null {
  if (!header) return null;
  const prefs = header
    .split(",")
    .map((part) => {
      const [tag, q] = part.trim().split(";q=");
      const low = tag.toLowerCase();
      const lang = low === "uz-cyrl" || low.startsWith("uz-cyrl-") ? "uz-Cyrl" : low.split("-")[0];
      return { lang, q: q ? Number(q) : 1 };
    })
    .sort((a, b) => b.q - a.q);
  for (const p of prefs) if (isLocale(p.lang)) return p.lang;
  return null;
}
