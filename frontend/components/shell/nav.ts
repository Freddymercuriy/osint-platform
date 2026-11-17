import { AtSign, Globe, History, LayoutDashboard, Mail, Phone, Radar, Shield, type LucideIcon } from "lucide-react";

export type NavItem = {
  href: string;
  /** `nav.<key>` tarjima kaliti */
  key: string;
  icon: LucideIcon;
  badge?: "notifications";
  adminOnly?: boolean;
};
export type NavSection = { key: string; items: NavItem[]; adminOnly?: boolean };

/** Navigatsiya: Umumiy ko'rinish · Hodisalar · Tekshiruvlar · Admin (faqat adminlar). */
export const NAV: NavSection[] = [
  {
    key: "overview",
    items: [
      { href: "/dashboard", key: "overview", icon: LayoutDashboard },
      { href: "/dashboard/events", key: "events", icon: Radar, badge: "notifications" },
    ],
  },
  {
    key: "checks",
    items: [
      { href: "/dashboard/username", key: "username", icon: AtSign },
      { href: "/dashboard/email", key: "email", icon: Mail },
      { href: "/dashboard/phone", key: "phone", icon: Phone },
      { href: "/dashboard/domain", key: "domain", icon: Globe },
      { href: "/dashboard/history", key: "history", icon: History },
    ],
  },
  {
    key: "admin",
    adminOnly: true,
    items: [{ href: "/dashboard/admin", key: "admin", icon: Shield, adminOnly: true }],
  },
];

/** Joriy sahifaning nav kaliti (yuqori panel sarlavhasi uchun). */
export function navKeyFor(pathname: string): string {
  let best: NavItem | null = null;
  for (const s of NAV)
    for (const i of s.items)
      if (pathname === i.href || (i.href !== "/dashboard" && pathname.startsWith(`${i.href}/`)))
        if (!best || i.href.length > best.href.length) best = i;
  return best?.key ?? "overview";
}
