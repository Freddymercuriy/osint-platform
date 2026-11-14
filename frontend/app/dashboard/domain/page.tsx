"use client";

import { Globe } from "lucide-react";
import { useTranslations } from "next-intl";
import SearchModule from "@/components/SearchModule";
import { searchDomain } from "@/lib/api";

export default function DomainSearchPage() {
  const t = useTranslations("checks");
  return (
    <SearchModule
      kind="domain"
      icon={Globe}
      tone="sky"
      title={t("modules.domain.title")}
      description={t("modules.domain.pageDesc")}
      placeholder={t("domain.placeholder")}
      examples={["kun.uz", "gov.uz", "github.com", "8.8.8.8"]}
      checks={Array.from({ length: 6 }, (_, i) => t(`domain.checks.${i}`))}
      inputMono
      search={searchDomain}
    />
  );
}
