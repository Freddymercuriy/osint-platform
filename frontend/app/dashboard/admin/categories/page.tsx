"use client";

import { ArrowDown, ArrowUp, Bell, BellOff, Lock, Pencil, Plus, RefreshCw, Tags, Trash2 } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { useCallback, useEffect, useRef, useState } from "react";
import CategoryDrawer from "@/components/admin/categories/CategoryDrawer";
import ReclassifyDrawer from "@/components/admin/categories/ReclassifyDrawer";
import { Badge, Button, Card, EmptyState, ErrorBanner, SeverityBadge, Skeleton, toneClass, useFormat } from "@/components/ui";
import { deleteCategory, listAdminCategories, reorderCategories, type CategoryAdmin } from "@/lib/adminApi";
import { cn } from "@/lib/cn";
import { asTone } from "@/lib/categories";
import { categoryIcon } from "@/lib/icons";
import { invalidateCategories } from "@/lib/useCategories";

export default function AdminCategoriesPage() {
  const t = useTranslations("adminCategories");
  const tn = useTranslations("adminCategories.tones");
  const locale = useLocale() as "uz" | "ru" | "en";
  const f = useFormat();

  const [rows, setRows] = useState<CategoryAdmin[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [editor, setEditor] = useState<{ cat: CategoryAdmin | null } | null>(null);
  const [reclassOpen, setReclassOpen] = useState(false);
  const [confirmId, setConfirmId] = useState<number | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [rowError, setRowError] = useState<string | null>(null);
  const focusRef = useRef<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const r = await listAdminCategories();
      setRows([...r].sort((a, b) => a.sort_order - b.sort_order || a.id - b.id));
    } catch (e) {
      setError(e instanceof Error ? e.message : t("loadError"));
      setRows((p) => p ?? []);
    }
  }, [t]);

  useEffect(() => {
    void load();
  }, [load]);

  // Tartib o'zgargach fokusni xuddi shu tugmaga qaytaramiz
  useEffect(() => {
    if (focusRef.current) {
      document.getElementById(focusRef.current)?.focus();
      focusRef.current = null;
    }
  }, [rows]);

  const move = async (index: number, dir: -1 | 1) => {
    if (!rows) return;
    const j = index + dir;
    if (j < 0 || j >= rows.length) return;
    const next = [...rows];
    [next[index], next[j]] = [next[j], next[index]];
    focusRef.current = `cat-${dir < 0 ? "up" : "down"}-${rows[index].id}`;
    setRows(next);
    setRowError(null);
    try {
      await reorderCategories(next.map((c) => c.id));
      invalidateCategories();
    } catch (e) {
      setRows(rows);
      setRowError(e instanceof Error ? e.message : t("list.reorderFailed"));
    }
  };

  const remove = async (c: CategoryAdmin) => {
    setDeleting(true);
    setRowError(null);
    try {
      const r = await deleteCategory(c.id);
      invalidateCategories();
      setConfirmId(null);
      setNotice(t("delete.done", { count: r.moved_to_other }));
      await load();
    } catch (e) {
      setRowError(e instanceof Error ? e.message : t("delete.failed"));
    } finally {
      setDeleting(false);
    }
  };

  const nextOrder = (rows?.reduce((m, c) => Math.max(m, c.sort_order), 0) ?? 0) + 10;
  const nameOf = (c: CategoryAdmin) => c[`name_${locale}`] || c.name_en;

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <p className="max-w-2xl text-sm text-fg-muted">{t("intro")}</p>
        <div className="flex flex-wrap gap-2">
          <Button variant="secondary" icon={RefreshCw} onClick={() => setReclassOpen(true)}>{t("reclassify")}</Button>
          <Button icon={Plus} onClick={() => setEditor({ cat: null })}>{t("add")}</Button>
        </div>
      </div>

      {error && <ErrorBanner message={error} action={<Button size="sm" variant="secondary" onClick={load}>{/* retry */}{t("loadRetry")}</Button>} />}
      {rowError && <ErrorBanner message={rowError} />}
      {notice && (
        <div role="status" className={cn("flex items-start justify-between gap-2 rounded-lg border px-4 py-3 text-sm", toneClass("green"))}>
          <span>{notice}</span>
          <button type="button" className="font-medium underline focus-ring rounded" onClick={() => setNotice(null)}>{t("form.close")}</button>
        </div>
      )}

      {rows === null ? (
        <div className="space-y-3" role="status" aria-label={t("loadingLabel")}>
          {[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-24 w-full" />)}
        </div>
      ) : rows.length === 0 && !error ? (
        <Card>
          <EmptyState icon={Tags} title={t("empty.title")} description={t("empty.description")}
            action={<Button icon={Plus} onClick={() => setEditor({ cat: null })}>{t("add")}</Button>} />
        </Card>
      ) : (
        <ul aria-label={t("list.label")} className="space-y-3">
          {rows.map((c, i) => {
            const Icon = categoryIcon(c.icon);
            const tone = asTone(c.color);
            const name = nameOf(c);
            const confirming = confirmId === c.id;
            return (
              <li key={c.id}>
                <Card className={cn("p-3 sm:p-4", !c.enabled && "opacity-90")}>
                  <div className="flex items-start gap-3">
                    <div className="flex shrink-0 flex-col gap-1">
                      <button type="button" id={`cat-up-${c.id}`} onClick={() => move(i, -1)} disabled={i === 0}
                        aria-label={t("list.moveUp", { name })}
                        className="grid h-8 w-8 place-items-center rounded-lg border border-border text-fg-muted hover:bg-surface-2 hover:text-fg focus-ring disabled:cursor-not-allowed disabled:opacity-40">
                        <ArrowUp className="h-4 w-4" aria-hidden />
                      </button>
                      <button type="button" id={`cat-down-${c.id}`} onClick={() => move(i, 1)} disabled={i === rows.length - 1}
                        aria-label={t("list.moveDown", { name })}
                        className="grid h-8 w-8 place-items-center rounded-lg border border-border text-fg-muted hover:bg-surface-2 hover:text-fg focus-ring disabled:cursor-not-allowed disabled:opacity-40">
                        <ArrowDown className="h-4 w-4" aria-hidden />
                      </button>
                    </div>
                    <span className={cn("grid h-10 w-10 shrink-0 place-items-center rounded-lg border", toneClass(tone))}>
                      <Icon className="h-5 w-5" aria-hidden />
                    </span>
                    <div className="min-w-0 flex-1">
                      <div className="break-words font-medium text-fg">{name}</div>
                      <div className="break-all font-mono text-xs text-fg-muted">{c.slug}</div>
                    </div>
                    <div className="flex shrink-0 gap-1">
                      <Button size="sm" variant="secondary" icon={Pencil} onClick={() => setEditor({ cat: c })}
                        aria-label={t("list.edit", { name })}>
                        <span className="hidden sm:inline">{t("list.editShort")}</span>
                      </Button>
                      {!c.is_system && (
                        <Button size="sm" variant="danger" icon={Trash2} onClick={() => setConfirmId(c.id)}
                          aria-label={`${t("delete.button")}: ${name}`}>
                          <span className="hidden sm:inline">{t("delete.button")}</span>
                        </Button>
                      )}
                    </div>
                  </div>

                  <dl className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-2 text-sm">
                    <div className="flex items-center gap-1.5">
                      <dt className="sr-only">{t("list.severity")}</dt>
                      <dd><SeverityBadge severity={c.severity} /></dd>
                    </div>
                    <div className="flex items-center gap-1.5">
                      <dt className="sr-only">{t("list.color")}</dt>
                      <dd><Badge tone={tone}>{tn(tone)}</Badge></dd>
                    </div>
                    <div className="flex items-center gap-1.5 text-fg-muted">
                      <dt className="sr-only">{t("list.notify")}</dt>
                      <dd className="inline-flex items-center gap-1">
                        {c.notify ? <Bell className="h-4 w-4 text-primary" aria-hidden /> : <BellOff className="h-4 w-4" aria-hidden />}
                        {c.notify ? t("list.notifyOn") : t("list.notifyOff")}
                      </dd>
                    </div>
                    <div className="text-fg-muted">
                      <dt className="sr-only">{t("list.retention")}</dt>
                      <dd>{c.retention_days == null ? t("list.forever") : t("list.days", { count: c.retention_days })}</dd>
                    </div>
                    <div>
                      <dt className="sr-only">{t("list.enabled")}</dt>
                      <dd><Badge tone={c.enabled ? "green" : "slate"}>{c.enabled ? t("list.enabledOn") : t("list.enabledOff")}</Badge></dd>
                    </div>
                    {c.is_system && (
                      <div>
                        <dt className="sr-only">{t("list.system")}</dt>
                        <dd><Badge icon={Lock} title={t("list.systemHelp")}>{t("list.system")}</Badge></dd>
                      </div>
                    )}
                    <div className="text-fg-muted sm:ml-auto">
                      <dt className="sr-only">{t("list.events")}</dt>
                      <dd className="tabular-nums">{t("list.eventsCount", { count: c.event_count, n: f.number(c.event_count) })}</dd>
                    </div>
                  </dl>

                  {confirming && (
                    <div role="alertdialog" aria-label={t("delete.confirmTitle", { name })} className={cn("mt-3 rounded-lg border p-3 text-sm", toneClass("red"))}>
                      <div className="font-medium">{t("delete.confirmTitle", { name })}</div>
                      <p className="mt-1">{t("delete.confirmBody")}</p>
                      <div className="mt-3 flex flex-wrap gap-2">
                        <Button size="sm" variant="secondary" onClick={() => setConfirmId(null)} data-autofocus>{t("delete.cancel")}</Button>
                        <Button size="sm" variant="primary" className="bg-danger text-bg hover:bg-danger/90" loading={deleting} onClick={() => remove(c)}>
                          {t("delete.confirm")}
                        </Button>
                      </div>
                    </div>
                  )}
                </Card>
              </li>
            );
          })}
        </ul>
      )}

      {editor && (
        <CategoryDrawer
          category={editor.cat}
          nextOrder={nextOrder}
          onClose={() => setEditor(null)}
          onSaved={() => {
            setEditor(null);
            void load();
          }}
        />
      )}
      {reclassOpen && rows && (
        <ReclassifyDrawer categories={rows} onClose={() => setReclassOpen(false)} onApplied={() => void load()} />
      )}
    </div>
  );
}
