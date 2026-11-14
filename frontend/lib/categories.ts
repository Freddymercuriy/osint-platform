import {
  Newspaper,
  Send,
  ShieldAlert,
  Skull,
  Users,
  type LucideIcon,
} from "lucide-react";

export type Tone =
  | "cyan"
  | "sky"
  | "violet"
  | "fuchsia"
  | "red"
  | "orange"
  | "amber"
  | "emerald"
  | "slate";

export type CategoryMeta = { label: string; tone: Tone; icon: LucideIcon; description: string };

/** Events kategoriyalari — butun UI'da bir xil nom, rang va ikon. */
export const CATEGORIES: Record<string, CategoryMeta> = {
  ransomware: {
    label: "Ransomware",
    tone: "red",
    icon: Skull,
    description: "Markaziy Osiyo tashkilotlariga qarshi ransomware hujumlari",
  },
  leak: {
    label: "Leak",
    tone: "orange",
    icon: ShieldAlert,
    description: "Leak forumlari va kanallaridagi Markaziy Osiyo ma'lumotlari",
  },
  telegram: {
    label: "TG kanal",
    tone: "sky",
    icon: Send,
    description: "Telegram kanallaridagi Markaziy Osiyoga oid xabarlar",
  },
  tg_group: {
    label: "TG guruh",
    tone: "violet",
    icon: Users,
    description: "Telegram guruhlaridagi Markaziy Osiyoga oid xabarlar",
  },
  news: {
    label: "Yangilik",
    tone: "slate",
    icon: Newspaper,
    description: "Kiberxavfsizlik va data leak yangiliklari (RSS)",
  },
};

export const CATEGORY_ORDER = ["ransomware", "leak", "telegram", "tg_group", "news"] as const;

export function categoryMeta(key: string): CategoryMeta {
  return CATEGORIES[key] ?? { label: key, tone: "slate", icon: Newspaper, description: "" };
}
