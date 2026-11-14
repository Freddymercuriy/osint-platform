"use client";

import { useEffect, useState } from "react";
import { Activity, AtSign, ArrowRight, Globe, Mail, Phone, ShieldCheck, Users, type LucideIcon } from "lucide-react";
import Link from "next/link";
import { useTranslations } from "next-intl";
import { ButtonLink, Card, IconBox, Logo } from "@/components/ui";
import ThemeToggle from "@/components/theme/ThemeToggle";
import LocaleSwitcher from "@/components/theme/LocaleSwitcher";
import type { Tone } from "@/lib/categories";
import { getAuthConfig } from "@/lib/api";

const FEATURES: { key: string; icon: LucideIcon; tone: Tone }[] = [
  { key: "events", icon: Activity, tone: "red" },
  { key: "username", icon: AtSign, tone: "violet" },
  { key: "email", icon: Mail, tone: "cyan" },
  { key: "phone", icon: Phone, tone: "emerald" },
];

const AUDIENCE = ["analysts", "security", "journalists"] as const;

export default function LandingPage() {
  const t = useTranslations("landing");
  const c = useTranslations("common");
  const [registrationOpen, setRegistrationOpen] = useState(false);

  useEffect(() => {
    getAuthConfig()
      .then((cfg) => setRegistrationOpen(cfg.registration_open))
      .catch(() => setRegistrationOpen(false));
  }, []);

  return (
    <div className="min-h-screen bg-bg text-fg">
      <header className="border-b border-border">
        <div className="mx-auto flex max-w-5xl items-center justify-between gap-3 px-4 py-3 sm:px-6">
          <Link href="/" className="focus-ring rounded-lg" aria-label={c("appName")}>
            <Logo />
          </Link>
          <div className="flex items-center gap-2">
            <LocaleSwitcher />
            <ThemeToggle />
            <ButtonLink href="/login" size="sm" className="ml-1 hidden sm:inline-flex">
              {t("signIn")}
            </ButtonLink>
          </div>
        </div>
      </header>

      <main id="main">
        <section className="mx-auto max-w-5xl px-4 py-12 sm:px-6 sm:py-20">
          <h1 className="max-w-2xl text-3xl font-semibold tracking-tight sm:text-4xl">{t("heroTitle")}</h1>
          <p className="mt-4 max-w-2xl text-base text-fg-muted sm:text-lg">{t("heroText")}</p>
          <div className="mt-7 flex flex-wrap gap-3">
            <ButtonLink href="/login" size="lg" icon={ArrowRight}>
              {t("signIn")}
            </ButtonLink>
            {registrationOpen && (
              <ButtonLink href="/register" size="lg" variant="secondary">
                {t("createAccount")}
              </ButtonLink>
            )}
          </div>
          <p className="mt-4 flex items-center gap-1.5 text-sm text-fg-muted">
            <ShieldCheck className="h-4 w-4" aria-hidden /> {c("publicSourcesOnly")}
          </p>
        </section>

        <section className="border-t border-border bg-surface" aria-labelledby="features-title">
          <div className="mx-auto max-w-5xl px-4 py-12 sm:px-6">
            <h2 id="features-title" className="text-xl font-semibold tracking-tight">
              {t("featuresTitle")}
            </h2>
            <div className="mt-6 grid gap-4 sm:grid-cols-2">
              {FEATURES.map((f) => (
                <Card key={f.key} className="p-5">
                  <IconBox icon={f.icon} tone={f.tone} />
                  <h3 className="mt-3 text-base font-semibold">{t(`features.${f.key}.title`)}</h3>
                  <p className="mt-1.5 text-sm text-fg-muted">{t(`features.${f.key}.text`)}</p>
                </Card>
              ))}
            </div>
          </div>
        </section>

        <section className="mx-auto max-w-5xl px-4 py-12 sm:px-6" aria-labelledby="audience-title">
          <h2 id="audience-title" className="flex items-center gap-2 text-xl font-semibold tracking-tight">
            <Users className="h-5 w-5 text-primary" aria-hidden /> {t("audienceTitle")}
          </h2>
          <ul className="mt-5 grid gap-4 sm:grid-cols-3">
            {AUDIENCE.map((a) => (
              <li key={a} className="rounded-xl border border-border bg-surface p-4">
                <div className="text-sm font-semibold">{t(`audience.${a}.title`)}</div>
                <p className="mt-1 text-sm text-fg-muted">{t(`audience.${a}.text`)}</p>
              </li>
            ))}
          </ul>
        </section>
      </main>

      <footer className="border-t border-border">
        <div className="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-2 px-4 py-5 text-sm text-fg-muted sm:px-6">
          <span className="flex items-center gap-1.5">
            <Globe className="h-4 w-4" aria-hidden /> {t("footer")}
          </span>
          <Link href="/login" className="focus-ring rounded font-medium text-primary hover:underline">
            {t("signIn")}
          </Link>
        </div>
      </footer>
    </div>
  );
}
