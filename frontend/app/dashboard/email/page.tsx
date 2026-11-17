"use client";

import { Mail } from "lucide-react";
import { useTranslations } from "next-intl";
import SearchModule from "@/components/SearchModule";
import { searchEmail } from "@/lib/api";

export default function EmailSearchPage() {
  const t = useTranslations("checks");
  return (
    <SearchModule
      kind="email"
      icon={Mail}
      tone="violet"
      title={t("modules.email.title")}
      description={t("modules.email.pageDesc")}
      placeholder={t("email.placeholder")}
      examples={["user@gmail.com", "info@example.com"]}
      checks={Array.from({ length: 3 }, (_, i) => t(`email.checks.${i}`))}
      inputMono
      search={searchEmail}
    />
  );
}
