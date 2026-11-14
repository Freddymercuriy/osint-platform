import { AtSign, Globe, Mail, Phone, Search, type LucideIcon } from "lucide-react";
import type { Tone } from "@/lib/categories";

export type ModuleMeta = {
  kind: string;
  /** tarjima kaliti: useTranslations("checks")("modules.<key>.label|title|desc") */
  key: string;
  href: string;
  /** @deprecated uz fallback — useTranslations("checks")("modules.<key>.label") ishlating */
  label: string;
  /** @deprecated modules.<key>.title */
  title: string;
  /** @deprecated modules.<key>.desc */
  desc: string;
  icon: LucideIcon;
  tone: Tone;
};

/** Tekshiruv modullari — butun UI'da bir xil nom, rang va ikon (sidebar, dashboard, tarix). */
export const MODULES: ModuleMeta[] = [
  { kind: "username", key: "username", href: "/dashboard/username", label: "Username", title: "Telegram username", desc: "ID, username tarixi, umumiy guruhlar", icon: AtSign, tone: "cyan" },
  { kind: "email", key: "email", href: "/dashboard/email", label: "Email", title: "Email tekshiruvi", desc: "Sintaksis, MX server, Gravatar", icon: Mail, tone: "violet" },
  { kind: "phone", key: "phone", href: "/dashboard/phone", label: "Telefon", title: "Telefon tekshiruvi", desc: "Davlat, operator, raqam turi", icon: Phone, tone: "emerald" },
  { kind: "domain", key: "domain", href: "/dashboard/domain", label: "Domen / IP", title: "Domen / IP / WHOIS", desc: "DNS, WHOIS, subdomenlar, ASN", icon: Globe, tone: "sky" },
];

export const MODULE_KINDS = MODULES.map((m) => m.kind);

export function moduleMeta(kind: string): ModuleMeta {
  return (
    MODULES.find((m) => m.kind === kind) ?? {
      kind,
      key: "unknown",
      href: "/dashboard",
      label: kind,
      title: kind,
      desc: "",
      icon: Search,
      tone: "slate",
    }
  );
}

/** Modul sahifasiga so'rovni oldindan to'ldirib o'tish havolasi. */
export function moduleLink(kind: string, query: string): string {
  return `${moduleMeta(kind).href}?q=${encodeURIComponent(query)}`;
}
