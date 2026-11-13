"use client";

import SearchModule from "@/components/SearchModule";
import { searchEmail } from "@/lib/api";

export default function EmailSearchPage() {
  return (
    <SearchModule
      title="Email tekshiruvi"
      description="Sintaksis, MX (pochta serveri) va Gravatar profilini tekshiradi."
      placeholder="masalan: user@example.com"
      search={searchEmail}
    />
  );
}
