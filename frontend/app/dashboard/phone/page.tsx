"use client";

import { Phone } from "lucide-react";
import SearchModule from "@/components/SearchModule";
import { searchPhone } from "@/lib/api";

export default function PhoneSearchPage() {
  return (
    <SearchModule
      kind="phone"
      icon={Phone}
      tone="emerald"
      title="Telefon tekshiruvi"
      description="Raqamning davlati, operatori, turi va vaqt mintaqasini aniqlaydi (offline)."
      placeholder="masalan: +998901234567"
      examples={["+998901234567", "+14155552671"]}
      checks={["Davlat va hudud", "Mobil operator", "Raqam turi (mobil / statsionar)", "Vaqt mintaqasi"]}
      inputMono
      search={searchPhone}
    />
  );
}
