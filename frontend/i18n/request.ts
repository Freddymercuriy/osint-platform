import { cookies, headers } from "next/headers";
import { getRequestConfig } from "next-intl/server";
import { DEFAULT_LOCALE, LOCALE_COOKIE, isLocale, matchAcceptLanguage } from "./config";

// Til URL'da emas: cookie (foydalanuvchi tanlagan / users.locale) → brauzer tili → uz
export default getRequestConfig(async () => {
  const fromCookie = (await cookies()).get(LOCALE_COOKIE)?.value;
  const locale = isLocale(fromCookie)
    ? fromCookie
    : matchAcceptLanguage((await headers()).get("accept-language")) ?? DEFAULT_LOCALE;
  return {
    locale,
    messages: (await import(`../messages/${locale}.json`)).default,
    timeZone: "Asia/Tashkent",
  };
});
