"use client";

import { Mail } from "lucide-react";
import SearchModule from "@/components/SearchModule";
import { searchEmail } from "@/lib/api";

export default function EmailSearchPage() {
  return (
    <SearchModule
      kind="email"
      icon={Mail}
      tone="violet"
      title="Email tekshiruvi"
      description="Manzil sintaksisi, MX (pochta serveri) yozuvlari va Gravatar profilini tekshiradi."
      placeholder="masalan: user@gmail.com"
      examples={["user@gmail.com", "info@example.com"]}
      checks={[
        "Sintaksis to'g'riligi",
        "MX yozuvlari (pochta serveri)",
        "Gravatar ochiq profili",
      ]}
      inputMono
      search={searchEmail}
    />
  );
}
