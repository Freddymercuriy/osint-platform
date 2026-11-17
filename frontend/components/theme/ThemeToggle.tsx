"use client";

import { Monitor, Moon, Sun, type LucideIcon } from "lucide-react";
import { useTranslations } from "next-intl";
import { useTheme } from "next-themes";
import { useEffect, useState } from "react";
import { cn } from "@/lib/cn";

const OPTIONS: { value: "light" | "dark" | "system"; icon: LucideIcon }[] = [
  { value: "light", icon: Sun },
  { value: "dark", icon: Moon },
  { value: "system", icon: Monitor },
];

/** Uch holatli almashtirgich: Yorug' / Qorong'i / Tizim. */
export default function ThemeToggle({ className }: { className?: string }) {
  const t = useTranslations("theme");
  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  const current = mounted ? theme ?? "system" : "system";

  return (
    <div role="radiogroup" aria-label={t("label")} className={cn("inline-flex rounded-lg border border-border bg-surface p-0.5", className)}>
      {OPTIONS.map(({ value, icon: Icon }) => {
        const active = current === value;
        return (
          <button
            key={value}
            type="button"
            role="radio"
            aria-checked={active}
            title={t(value)}
            aria-label={t(value)}
            onClick={() => setTheme(value)}
            className={cn(
              "focus-ring grid h-7 w-7 place-items-center rounded-md text-fg-muted transition-colors hover:text-fg",
              active && "bg-surface-2 text-fg shadow-sm",
            )}
          >
            <Icon className="h-4 w-4" />
          </button>
        );
      })}
    </div>
  );
}
