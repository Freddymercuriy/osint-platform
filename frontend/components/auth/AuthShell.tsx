"use client";

import Link from "next/link";
import { ArrowLeft, ShieldCheck } from "lucide-react";
import { useTranslations } from "next-intl";
import { Logo } from "@/components/ui";
import ThemeToggle from "@/components/theme/ThemeToggle";
import LocaleSwitcher from "@/components/theme/LocaleSwitcher";

export function AuthShell({ children }: { children: React.ReactNode }) {
  const t = useTranslations("auth");
  const c = useTranslations("common");
  return (
    <div className="flex min-h-screen flex-col bg-bg text-fg">
      <header className="flex items-center justify-between gap-3 px-4 py-4 sm:px-6">
        <Link href="/" className="focus-ring rounded-lg" aria-label={c("appName")}>
          <Logo />
        </Link>
        <div className="flex items-center gap-2">
          <LocaleSwitcher />
          <ThemeToggle />
        </div>
      </header>
      <main className="flex flex-1 items-center justify-center px-4 py-8 sm:px-6">
        <div className="w-full max-w-md">
          <Link
            href="/"
            className="focus-ring mb-4 inline-flex items-center gap-1.5 rounded text-sm text-fg-muted transition-colors hover:text-fg"
          >
            <ArrowLeft className="h-4 w-4" aria-hidden /> {t("backHome")}
          </Link>
          {children}
          <p className="mt-6 flex items-center justify-center gap-1.5 text-center text-xs text-fg-muted">
            <ShieldCheck className="h-3.5 w-3.5" aria-hidden />
            {c("publicSourcesOnly")}
          </p>
        </div>
      </main>
    </div>
  );
}
