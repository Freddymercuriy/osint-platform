"use client";

import { Cog, Database, ShieldAlert, Tags } from "lucide-react";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { ButtonLink, EmptyState, PageHeader, Skeleton } from "@/components/ui";
import { getMe, type Me } from "@/lib/api";
import { cn } from "@/lib/cn";

const TABS = [
  { href: "/dashboard/admin/sources", key: "sources", icon: Database },
  { href: "/dashboard/admin/categories", key: "categories", icon: Tags },
  { href: "/dashboard/admin/system", key: "system", icon: Cog },
] as const;

/** Admin bo'limi: faqat `role === "admin"` (backend ham har so'rovda tekshiradi). */
export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const t = useTranslations("admin");
  const pathname = usePathname();
  const [me, setMe] = useState<Me | null>(null);
  useEffect(() => {
    getMe().then(setMe).catch(() => setMe(null));
  }, []);

  if (!me) return <Skeleton className="h-40 w-full" />;
  if (me.role !== "admin") {
    return (
      <div className="card">
        <EmptyState
          icon={ShieldAlert}
          title={t("onlyAdmins")}
          description={t("onlyAdminsHint")}
          action={<ButtonLink href="/dashboard" variant="secondary">{t("backToOverview")}</ButtonLink>}
        />
      </div>
    );
  }

  return (
    <div>
      <PageHeader title={t("title")} description={t("description")} />
      <nav aria-label={t("title")} className="mb-6 flex gap-1 overflow-x-auto border-b border-border">
        {TABS.map(({ href, key, icon: Icon }) => {
          const active = pathname === href || pathname.startsWith(`${href}/`);
          return (
            <Link
              key={href}
              href={href}
              aria-current={active ? "page" : undefined}
              className={cn(
                "focus-ring -mb-px inline-flex items-center gap-2 whitespace-nowrap border-b-2 px-3 py-2 text-sm transition-colors",
                active ? "border-primary font-medium text-primary" : "border-transparent text-fg-muted hover:text-fg",
              )}
            >
              <Icon className="h-4 w-4" aria-hidden />
              {t(`tabs.${key}`)}
            </Link>
          );
        })}
      </nav>
      {children}
    </div>
  );
}
