"use client";

import { Phone } from "lucide-react";
import { useTranslations } from "next-intl";
import SearchModule from "@/components/SearchModule";
import { searchPhone } from "@/lib/api";

export default function PhoneSearchPage() {
  const t = useTranslations("checks");
  return (
    <SearchModule
      kind="phone"
      icon={Phone}
      tone="emerald"
      title={t("modules.phone.title")}
      description={t("modules.phone.pageDesc")}
      placeholder={t("phone.placeholder")}
      examples={["+998901234567", "+14155552671"]}
      checks={Array.from({ length: 4 }, (_, i) => t(`phone.checks.${i}`))}
      inputMono
      search={searchPhone}
    />
  );
}
