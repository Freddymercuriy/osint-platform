import {
  AtSign,
  Globe,
  LayoutDashboard,
  Mail,
  Phone,
  Radar,
  type LucideIcon,
} from "lucide-react";

export type NavItem = {
  href: string;
  label: string;
  icon: LucideIcon;
  soon?: boolean;
  badge?: "notifications";
};
export type NavSection = { title: string; items: NavItem[] };

export const NAV: NavSection[] = [
  {
    title: "Umumiy",
    items: [{ href: "/dashboard", label: "Boshqaruv paneli", icon: LayoutDashboard }],
  },
  {
    title: "Razvedka",
    items: [{ href: "/dashboard/events", label: "Events · O'zbekiston", icon: Radar, badge: "notifications" }],
  },
  {
    title: "Tekshiruv",
    items: [
      { href: "/dashboard/username", label: "Username qidiruv", icon: AtSign },
      { href: "/dashboard/email", label: "Email tekshiruvi", icon: Mail },
      { href: "/dashboard/phone", label: "Telefon tekshiruvi", icon: Phone },
      { href: "#", label: "Domen / WHOIS", icon: Globe, soon: true },
    ],
  },
];

/** Joriy sahifa nomi (yuqori panel uchun) */
export function titleFor(pathname: string): string {
  for (const s of NAV) for (const i of s.items) if (i.href === pathname) return i.label;
  return "Boshqaruv paneli";
}
