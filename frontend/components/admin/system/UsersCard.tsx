"use client";

import { Users } from "lucide-react";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";
import { Badge, Button, EmptyState, ErrorBanner, Skeleton, useFormat } from "@/components/ui";
import { getMe } from "@/lib/api";
import { listUsers, updateUser, type AdminUserRow } from "@/lib/adminApi";
import { ConfirmDialog, SectionCard } from "./shared";

type Pending = { user: AdminUserRow; patch: { role?: "admin" | "analyst"; is_active?: boolean } };

export default function UsersCard() {
  const t = useTranslations("adminSystem");
  const tc = useTranslations("common");
  const f = useFormat();
  const [users, setUsers] = useState<AdminUserRow[] | null>(null);
  const [meId, setMeId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState<Pending | null>(null);
  const [busy, setBusy] = useState(false);
  const [dialogError, setDialogError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setUsers(await listUsers());
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : tc("error"));
    }
  }, [tc]);
  useEffect(() => {
    load();
    getMe().then((m) => setMeId(m.id)).catch(() => setMeId(null));
  }, [load]);

  const ask = (user: AdminUserRow, patch: Pending["patch"]) => { setDialogError(null); setPending({ user, patch }); };

  const confirm = async () => {
    if (!pending) return;
    setBusy(true);
    setDialogError(null);
    try {
      await updateUser(pending.user.id, pending.patch);
      setPending(null);
      await load();
    } catch (e) {
      setDialogError(e instanceof Error ? e.message : tc("error"));
    } finally { setBusy(false); }
  };

  let dlg: { title: string; body: string; label: string; danger: boolean } | null = null;
  if (pending) {
    const { user, patch } = pending;
    if (patch.role) {
      dlg = {
        title: t("users.confirmRoleTitle", { email: user.email }),
        body: t(patch.role === "admin" ? "users.confirmToAdmin" : "users.confirmToAnalyst", { email: user.email }),
        label: t("users.confirmRoleAction", { role: t(`users.role.${patch.role}`) }),
        danger: patch.role === "analyst",
      };
    } else {
      const on = !!patch.is_active;
      dlg = {
        title: t(on ? "users.confirmActivateTitle" : "users.confirmDeactivateTitle", { email: user.email }),
        body: t(on ? "users.confirmActivate" : "users.confirmDeactivate", { email: user.email }),
        label: t(on ? "users.activate" : "users.deactivate"),
        danger: !on,
      };
    }
  }

  return (
    <SectionCard id="sys-users" icon={Users} title={t("users.title")} hint={t("users.hint")}>
      {error && <div className="mb-3"><ErrorBanner message={error} action={<Button variant="secondary" size="sm" onClick={load}>{tc("retry")}</Button>} /></div>}
      {!users && !error && <Skeleton className="h-40 w-full" />}
      {users && users.length === 0 && (
        <EmptyState icon={Users} title={t("users.emptyTitle")} description={t("users.emptyHint")} />
      )}
      {users && users.length > 0 && (
        <div className="overflow-x-auto rounded-lg border border-border">
          <table className="w-full min-w-[44rem] text-sm">
            <caption className="sr-only">{t("users.title")}</caption>
            <thead className="bg-surface-2 text-left text-xs text-fg-muted">
              <tr>
                <th scope="col" className="px-3 py-2 font-medium">{t("users.email")}</th>
                <th scope="col" className="px-3 py-2 font-medium">{t("users.roleCol")}</th>
                <th scope="col" className="px-3 py-2 font-medium">{t("users.active")}</th>
                <th scope="col" className="px-3 py-2 font-medium">{t("users.language")}</th>
                <th scope="col" className="px-3 py-2 font-medium">{t("users.created")}</th>
                <th scope="col" className="px-3 py-2 text-right font-medium">{t("users.searches")}</th>
                <th scope="col" className="px-3 py-2 font-medium">{t("users.actions")}</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => {
                const isMe = u.id === meId;
                const otherRole = u.role === "admin" ? "analyst" : "admin";
                return (
                  <tr key={u.id} className="border-t border-border align-middle">
                    <td className="px-3 py-2">
                      <span className="break-all font-medium text-fg">{u.email}</span>
                      {isMe && <Badge tone="blue" className="ml-2">{t("users.you")}</Badge>}
                    </td>
                    <td className="px-3 py-2"><Badge tone={u.role === "admin" ? "purple" : "slate"}>{t(`users.role.${u.role}`)}</Badge></td>
                    <td className="px-3 py-2"><Badge tone={u.is_active ? "green" : "slate"}>{u.is_active ? t("users.activeYes") : t("users.activeNo")}</Badge></td>
                    <td className="px-3 py-2 uppercase text-fg-muted">{u.locale ?? "—"}</td>
                    <td className="whitespace-nowrap px-3 py-2 text-fg-muted">{f.date(u.created_at)}</td>
                    <td className="px-3 py-2 text-right tabular-nums">{f.number(u.searches)}</td>
                    <td className="px-3 py-2">
                      <div className="flex flex-wrap gap-1.5">
                        <Button variant="secondary" size="sm" onClick={() => ask(u, { role: otherRole })}>
                          {t("users.makeRole", { role: t(`users.role.${otherRole}`) })}
                        </Button>
                        <Button variant="secondary" size="sm" onClick={() => ask(u, { is_active: !u.is_active })}>
                          {u.is_active ? t("users.deactivate") : t("users.activate")}
                        </Button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
      {pending && dlg && (
        <ConfirmDialog
          title={dlg.title}
          body={dlg.body}
          confirmLabel={dlg.label}
          danger={dlg.danger}
          busy={busy}
          error={dialogError}
          onConfirm={confirm}
          onCancel={() => setPending(null)}
        />
      )}
    </SectionCard>
  );
}
