"use client";

import { useLocale } from "next-intl";
import { useEffect, useMemo, useState } from "react";
import { getCategories, type Category } from "@/lib/api";
import { asTone, type Tone } from "@/lib/categories";
import { categoryIcon } from "@/lib/icons";
import type { LucideIcon } from "lucide-react";

export type CategoryView = Category & { name: string; description: string; tone: Tone; Icon: LucideIcon };

let cache: Promise<Category[]> | null = null;

/** Kategoriyalar bazadan (bir sahifada bir marta so'raladi); nomi interfeys tilida. */
export function useCategories(): { list: CategoryView[]; bySlug: (slug: string) => CategoryView; loading: boolean } {
  const locale = useLocale() as "uz" | "ru" | "en";
  const [rows, setRows] = useState<Category[] | null>(null);
  useEffect(() => {
    cache ??= getCategories().catch((e) => {
      cache = null;
      throw e;
    });
    let alive = true;
    cache.then((r) => alive && setRows(r)).catch(() => alive && setRows([]));
    return () => {
      alive = false;
    };
  }, []);
  return useMemo(() => {
    const list: CategoryView[] = (rows ?? []).map((c) => ({
      ...c,
      name: c[`name_${locale}`] || c.name_en,
      description: c[`description_${locale}`] || c.description_en,
      tone: asTone(c.color),
      Icon: categoryIcon(c.icon),
    }));
    const map = new Map(list.map((c) => [c.slug, c]));
    const bySlug = (slug: string): CategoryView =>
      map.get(slug) ?? {
        id: 0, slug, name_en: slug, name_ru: slug, name_uz: slug, description_en: "", description_ru: "",
        description_uz: "", severity: "info", color: "slate", icon: "Tag", notify: false, retention_days: null,
        sort_order: 9999, enabled: true, is_system: false, event_count: 0,
        name: slug, description: "", tone: "slate", Icon: categoryIcon(null),
      };
    return { list, bySlug, loading: rows === null };
  }, [rows, locale]);
}

export function invalidateCategories() {
  cache = null;
}
