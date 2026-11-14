"use client";

import { Languages } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import { useTransition } from "react";
import { LOCALES, type Locale } from "@/i18n/config";
import { getToken, setLocaleCookie, updateMyLocale } from "@/lib/api";
import { cn } from "@/lib/cn";

/** Til tanlash: cookie + (kirgan bo'lsa) users.locale; sahifa server tomonda qayta chiziladi. */
export default function LocaleSwitcher({ className }: { className?: string }) {
  const t = useTranslations("locale");
  const locale = useLocale() as Locale;
  const router = useRouter();
  const [pending, start] = useTransition();

  const change = (next: Locale) => {
    setLocaleCookie(next);
    if (getToken()) updateMyLocale(next).catch(() => undefined);
    start(() => router.refresh());
  };

  return (
    <label className={cn("relative inline-flex items-center", className)}>
      <span className="sr-only">{t("label")}</span>
      <Languages className="pointer-events-none absolute left-2 h-4 w-4 text-fg-subtle" aria-hidden />
      <select
        value={locale}
        disabled={pending}
        onChange={(e) => change(e.target.value as Locale)}
        className="focus-ring h-8 appearance-none rounded-lg border border-border bg-surface pl-7 pr-2 text-sm text-fg hover:bg-surface-2"
      >
        {LOCALES.map((l) => (
          <option key={l} value={l}>
            {t(l)}
          </option>
        ))}
      </select>
    </label>
  );
}
