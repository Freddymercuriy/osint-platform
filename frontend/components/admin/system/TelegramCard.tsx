"use client";

import { Send } from "lucide-react";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";
import { Badge, Button, ErrorBanner, Skeleton } from "@/components/ui";
import { getTgStatus, type TgStatus } from "@/lib/api";
import { Fact, SectionCard } from "./shared";

const CMD = "docker-compose exec backend python scripts/tg_login.py";

export default function TelegramCard() {
  const t = useTranslations("adminSystem");
  const tc = useTranslations("common");
  const [data, setData] = useState<TgStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const load = useCallback(async () => {
    try {
      setData(await getTgStatus());
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : tc("error"));
    }
  }, [tc]);
  useEffect(() => { load(); }, [load]);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(CMD);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch { /* clipboard unavailable: command stays selectable */ }
  };

  const yn = (v: boolean) => (v ? tc("yes") : tc("no"));

  return (
    <SectionCard
      id="sys-telegram"
      icon={Send}
      title={t("telegram.title")}
      hint={t("telegram.hint")}
      actions={<Button variant="secondary" size="sm" onClick={load}>{tc("refresh")}</Button>}
    >
      {error && <div className="mb-3"><ErrorBanner message={error} /></div>}
      {!data && !error && <Skeleton className="h-32 w-full" />}
      {data && (
        <div className="space-y-4">
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone={data.configured ? "green" : "amber"}>{data.configured ? t("telegram.configured") : t("telegram.notConfigured")}</Badge>
            <Badge tone={data.session ? "green" : "amber"}>{data.session ? t("telegram.sessionYes") : t("telegram.sessionNo")}</Badge>
            <Badge tone={data.authorized ? "green" : "red"}>{data.authorized ? t("telegram.authorized") : t("telegram.notAuthorized")}</Badge>
          </div>

          {!data.authorized && data.configured && (
            <div role="alert" className="tone-red space-y-2 rounded-lg border border-tone-border bg-tone-bg p-3 text-sm text-tone-fg">
              <p className="font-medium">{t("telegram.reloginTitle")}</p>
              <p>{t("telegram.reloginHelp")}</p>
              <div className="flex flex-wrap items-center gap-2">
                <code className="min-w-0 flex-1 select-all break-all rounded-md border border-border bg-surface px-2 py-1.5 font-mono text-xs text-fg">{CMD}</code>
                <Button variant="secondary" size="sm" onClick={copy}>{copied ? tc("copied") : tc("copy")}</Button>
              </div>
            </div>
          )}
          {!data.configured && <p className="text-sm text-fg-muted">{t("telegram.notConfiguredHelp")}</p>}

          <dl className="grid grid-cols-2 gap-4 sm:grid-cols-3">
            <Fact label={t("telegram.account")}>{data.account ?? "—"}</Fact>
            <Fact label={t("telegram.regionFilter")}>{yn(data.uz_filter)}</Fact>
            <Fact label={t("telegram.chatsCount")}>{data.chats_filter.length}</Fact>
          </dl>

          <div>
            <div className="mb-1 text-xs text-fg-muted">{t("telegram.chats")}</div>
            {data.chats_filter.length === 0 ? (
              <p className="text-sm text-fg-muted">{t("telegram.noChats")}</p>
            ) : (
              <ul className="flex flex-wrap gap-1.5">
                {data.chats_filter.map((c) => (
                  <li key={c} className="rounded-md border border-border bg-surface-2 px-2 py-0.5 font-mono text-xs text-fg">{c}</li>
                ))}
              </ul>
            )}
          </div>

          {data.message && (
            <p className="text-sm text-fg-muted"><span className="font-medium text-fg">{t("telegram.message")}: </span>{data.message}</p>
          )}
        </div>
      )}
    </SectionCard>
  );
}
