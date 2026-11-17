"use client";

import { useTranslations } from "next-intl";
import CollectorCard from "@/components/admin/system/CollectorCard";
import TelegramCard from "@/components/admin/system/TelegramCard";
import TranslationCard from "@/components/admin/system/TranslationCard";
import UsersCard from "@/components/admin/system/UsersCard";

export default function SystemPage() {
  const t = useTranslations("adminSystem");
  return (
    <div className="space-y-6">
      <p className="text-sm text-fg-muted">{t("intro")}</p>
      <CollectorCard />
      <TranslationCard />
      <TelegramCard />
      <UsersCard />
    </div>
  );
}
