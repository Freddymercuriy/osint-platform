"use client";

import SearchModule from "@/components/SearchModule";
import { searchPhone } from "@/lib/api";

export default function PhoneSearchPage() {
  return (
    <SearchModule
      title="Telefon tekshiruvi"
      description="Davlat, operator, raqam turi va vaqt mintaqasini aniqlaydi (offline)."
      placeholder="masalan: +998901234567"
      search={searchPhone}
    />
  );
}
