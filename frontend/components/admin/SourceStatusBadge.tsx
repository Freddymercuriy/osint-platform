"use client";

import { useTranslations } from "next-intl";
import { Badge } from "@/components/ui";
import type { Tone } from "@/lib/categories";

export const SOURCE_STATUS_TONE: Record<string, Tone> = {
  ok: "green",
  degraded: "amber",
  down: "red",
  blocked: "purple",
  auth_missing: "yellow",
  disabled: "slate",
  never_run: "slate",
};

/** Manba holati: rang + matn + izoh (title). */
export default function SourceStatusBadge({ status }: { status: string }) {
  const t = useTranslations("admin");
  const known = status in SOURCE_STATUS_TONE;
  return (
    <Badge tone={SOURCE_STATUS_TONE[status] ?? "slate"} title={known ? t(`statusHelp.${status}`) : undefined}>
      {known ? t(`status.${status}`) : status}
    </Badge>
  );
}
