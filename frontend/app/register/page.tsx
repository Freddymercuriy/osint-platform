"use client";

import { useRouter } from "next/navigation";
import Link from "next/link";
import { useEffect, useState } from "react";
import { Eye, EyeOff, Lock, Mail, UserPlus, LockKeyhole } from "lucide-react";
import { useTranslations } from "next-intl";
import { Button, ButtonLink, Card, EmptyState, ErrorBanner, Input, Label, Skeleton } from "@/components/ui";
import { AuthShell } from "@/components/auth/AuthShell";
import { getAuthConfig, login, register } from "@/lib/api";

export default function RegisterPage() {
  const t = useTranslations("auth");
  const c = useTranslations("common");
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState<boolean | null>(null);
  const [configError, setConfigError] = useState<string | null>(null);

  useEffect(() => {
    getAuthConfig()
      .then((cfg) => setOpen(cfg.registration_open))
      .catch((err) => {
        setConfigError(err instanceof Error ? err.message : c("error"));
        setOpen(false);
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (password.length < 8) {
      setError(t("passwordTooShort"));
      return;
    }
    setLoading(true);
    try {
      await register(email, password);
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
        {open === null ? (
          <div className="space-y-4" aria-busy="true">
            <Skeleton className="h-8 w-2/3" />
            <Skeleton className="h-11 w-full" />
            <Skeleton className="h-11 w-full" />
            <Skeleton className="h-11 w-full" />
          </div>
        ) : open === false ? (
          <div className="space-y-4">
            {configError && <ErrorBanner message={configError} />}
            <EmptyState
              icon={LockKeyhole}
              title={t("closedTitle")}
              description={t("closedText")}
              action={<ButtonLink href="/login">{t("signIn")}</ButtonLink>}
            />
          </div>
        ) : (
          <>
            <h1 className="text-2xl font-semibold tracking-tight">{t("registerTitle")}</h1>
            <p className="mt-1.5 text-sm text-fg-muted">{t("registerSubtitle")}</p>

            <form onSubmit={onSubmit} className="mt-6 space-y-5">
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
                    minLength={8}
                    autoComplete="new-password"
                    aria-describedby="password-hint"
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
                <p id="password-hint" className="mt-1.5 text-xs text-fg-muted">
                  {t("passwordHint")}
                </p>
              </div>

              <Button type="submit" size="lg" loading={loading} icon={UserPlus} className="w-full">
                {loading ? t("creating") : t("createAccount")}
              </Button>
            </form>

            <div className="mt-6 border-t border-border pt-5 text-center text-sm text-fg-muted">
              {t("haveAccount")}{" "}
              <Link href="/login" className="focus-ring rounded font-medium text-primary hover:underline">
                {t("signIn")}
              </Link>
            </div>
          </>
        )}
      </Card>
    </AuthShell>
  );
}
