import { Newspaper, Send, Server, Users, type LucideIcon } from "lucide-react";

/** Tone ranglari — `app/tones.css` (`.tone-<rang>`), kategoriya rangi bazadan (`categories.color`). */
export const TONES = [
  "red", "orange", "amber", "yellow", "lime", "green", "emerald", "teal", "cyan", "sky", "blue", "indigo",
  "violet", "purple", "fuchsia", "pink", "rose", "slate",
] as const;
export type Tone = (typeof TONES)[number];

export function asTone(v: string | null | undefined): Tone {
  return (TONES as readonly string[]).includes(v ?? "") ? (v as Tone) : "slate";
}

export const SEVERITY_TONE: Record<string, Tone> = {
  critical: "red",
  high: "orange",
  medium: "amber",
  low: "sky",
  info: "slate",
};

export const SEVERITIES = ["critical", "high", "medium", "low", "info"] as const;

/** Hodisa kanali (qayerdan kelgani). Nomi — `channel.<key>` tarjimasi. */
export const CHANNEL_META: Record<string, { tone: Tone; icon: LucideIcon }> = {
  news: { tone: "slate", icon: Newspaper },
  telegram_channel: { tone: "sky", icon: Send },
  telegram_group: { tone: "violet", icon: Users },
  api: { tone: "teal", icon: Server },
};

export const COUNTRIES = ["UZ", "KZ", "KG", "TJ", "TM"] as const;
