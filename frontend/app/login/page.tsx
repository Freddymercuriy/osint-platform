"use client";

import { useRouter } from "next/navigation";
import Link from "next/link";
import { useEffect, useState } from "react";
import { ArrowRight, Eye, EyeOff, Lock, Mail } from "lucide-react";
import { useTranslations } from "next-intl";
import { Button, Card, ErrorBanner, Input, Label } from "@/components/ui";
import { AuthShell } from "@/components/auth/AuthShell";
import { getAuthConfig, login } from "@/lib/api";

export default function LoginPage() {
  const t = useTranslations("auth");
  const c = useTranslations("common");
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expired, setExpired] = useState(false);
  const [loading, setLoading] = useState(false);
  const [registrationOpen, setRegistrationOpen] = useState(false);

  useEffect(() => {
    if (new URLSearchParams(window.location.search).get("expired")) setExpired(true);
    getAuthConfig()
      .then((cfg) => setRegistrationOpen(cfg.registration_open))
      .catch(() => setRegistrationOpen(false));
  }, []);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setExpired(false);
    setLoading(true);
    try {
      await login(email, password);
      router.push("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : c("error"));
    } finally {
      setLoading(false);
    }
  }

  return (
    <AuthShell>
      <Card className="animate-fade-in p-6 sm:p-8">
        <h1 className="text-2xl font-semibold tracking-tight">{t("loginTitle")}</h1>
        <p className="mt-1.5 text-sm text-fg-muted">{t("loginSubtitle")}</p>

        <form onSubmit={onSubmit} className="mt-6 space-y-5">
          {expired && !error && <ErrorBanner message={c("sessionExpired")} />}
          {error && <ErrorBanner message={error} />}

          <div>
            <Label htmlFor="email">{t("email")}</Label>
            <Input
              id="email"
              name="email"
              type="email"
              required
              autoComplete="email"
              placeholder={t("emailPlaceholder")}
              icon={Mail}
              inputSize="lg"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </div>

          <div>
            <Label htmlFor="password">{t("password")}</Label>
            <div className="relative">
              <Input
                id="password"
                name="password"
                type={showPassword ? "text" : "password"}
                required
                autoComplete="current-password"
                icon={Lock}
                inputSize="lg"
                className="!pr-12"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
              <button
                type="button"
                onClick={() => setShowPassword((s) => !s)}
                aria-label={showPassword ? t("hidePassword") : t("showPassword")}
                className="focus-ring absolute right-2 top-1/2 grid h-8 w-8 -translate-y-1/2 place-items-center rounded-lg text-fg-muted transition-colors hover:bg-surface-2 hover:text-fg"
              >
                {showPassword ? <EyeOff className="h-4 w-4" aria-hidden /> : <Eye className="h-4 w-4" aria-hidden />}
              </button>
            </div>
          </div>

          <Button type="submit" size="lg" loading={loading} className="w-full">
            {loading ? t("signingIn") : t("signIn")}
            {!loading && <ArrowRight className="h-4 w-4" aria-hidden />}
          </Button>
        </form>

        {registrationOpen && (
          <div className="mt-6 border-t border-border pt-5 text-center text-sm text-fg-muted">
            {t("noAccount")}{" "}
            <Link href="/register" className="focus-ring rounded font-medium text-primary hover:underline">
              {t("createAccount")}
            </Link>
          </div>
        )}
      </Card>
    </AuthShell>
  );
}
