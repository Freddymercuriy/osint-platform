"use client";

import { Globe } from "lucide-react";
import SearchModule from "@/components/SearchModule";
import { searchDomain } from "@/lib/api";

export default function DomainSearchPage() {
  return (
    <SearchModule
      kind="domain"
      icon={Globe}
      tone="sky"
      title="Domen / IP / WHOIS"
      description="Domen yoki IP manzil bo'yicha DNS yozuvlari, WHOIS, subdomenlar va tarmoq (ASN) ma'lumotlarini yig'adi."
      placeholder="masalan: kun.uz yoki 8.8.8.8"
      examples={["kun.uz", "gov.uz", "github.com", "8.8.8.8"]}
      checks={[
        "DNS: A / AAAA, NS, MX",
        "Pochta himoyasi: SPF va DMARC",
        "WHOIS / RDAP: registrator, sanalar, holat",
        "Subdomenlar (Certificate Transparency)",
        "Hosting: ASN, tarmoq, davlat",
        "IP uchun: teskari DNS (PTR) va tarmoq egasi",
      ]}
      inputMono
      search={searchDomain}
    />
  );
}
