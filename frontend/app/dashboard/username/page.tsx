"use client";

import { AtSign } from "lucide-react";
import { useTranslations } from "next-intl";
import SearchModule from "@/components/SearchModule";
import { searchUsername } from "@/lib/api";

export default function UsernameSearchPage() {
  const t = useTranslations("checks");
  return (
    <SearchModule
      kind="username"
      icon={AtSign}
      tone="cyan"
      title={t("modules.username.title")}
      description={t("modules.username.pageDesc")}
      placeholder={t("username.placeholder")}
      examples={["botfather", "telegram", "93372553"]}
      checks={Array.from({ length: 4 }, (_, i) => t(`username.checks.${i}`))}
      inputMono
      search={searchUsername}
    />
  );
}
