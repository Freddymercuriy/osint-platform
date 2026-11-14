"use client";

import { Check } from "lucide-react";
import { useTranslations } from "next-intl";
import { useMemo, useState } from "react";
import { Button, ErrorBanner, Input, Label, Select, toneClass } from "@/components/ui";
import { createCategory, updateCategory, type CategoryAdmin, type CategoryInput } from "@/lib/adminApi";
import { cn } from "@/lib/cn";
import { asTone, SEVERITIES, TONES } from "@/lib/categories";
import { CATEGORY_ICONS } from "@/lib/icons";
import { invalidateCategories } from "@/lib/useCategories";
import Drawer from "./Drawer";

const NAME_LANGS = ["uz", "ru", "en"] as const;
const STEM_LANGS = ["en", "ru", "uz", "kk"] as const;
const SLUG_RE = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;
const TEXTAREA =
  "w-full rounded-lg border border-border bg-surface px-3 py-2 font-mono text-sm text-fg placeholder:text-fg-subtle " +
  "hover:border-border-strong focus:border-ring focus:outline-none focus:ring-2 focus:ring-ring/30";

const lines = (s: string) => s.split("\n").map((x) => x.replace(/\r$/, "")).filter((x) => x.trim() !== "");
const joinLines = (a?: string[]) => (a ?? []).join("\n");

/** Har bir qatorni brauzerda tekshiradi; birinchi xato qator raqami va xabari. */
function badLine(text: string): { line: number; message: string } | null {
  const rows = text.split("\n");
  for (let i = 0; i < rows.length; i++) {
    const r = rows[i].replace(/\r$/, "");
    if (!r.trim()) continue;
    try {
      new RegExp(r);
    } catch (e) {
      return { line: i + 1, message: e instanceof Error ? e.message : String(e) };
    }
  }
  return null;
}

function Help({ id, children }: { id: string; children: React.ReactNode }) {
  return <p id={id} className="mt-1 text-xs text-fg-muted">{children}</p>;
}
function FieldError({ id, children }: { id: string; children: React.ReactNode }) {
  return <p id={id} role="alert" className="mt-1 text-xs font-medium text-danger">{children}</p>;
}

function Toggle({ id, checked, onChange, disabled, label, help }: {
  id: string; checked: boolean; onChange: (v: boolean) => void; disabled?: boolean; label: string; help: string;
}) {
  return (
    <div>
      <label htmlFor={id} className="flex items-center gap-3 text-sm font-medium text-fg">
        <input id={id} type="checkbox" role="switch" checked={checked} disabled={disabled}
          onChange={(e) => onChange(e.target.checked)} aria-describedby={`${id}-h`}
          className="h-4 w-4 rounded border-border accent-primary focus-ring disabled:opacity-50" />
        {label}
      </label>
      <Help id={`${id}-h`}>{help}</Help>
    </div>
  );
}

export default function CategoryDrawer({
  category,
  nextOrder,
  onClose,
  onSaved,
}: {
  category: CategoryAdmin | null;
  nextOrder: number;
  onClose: () => void;
  onSaved: () => void;
}) {
  const t = useTranslations("adminCategories");
  const ts = useTranslations("severity");
  const editing = category !== null;
  const locked = category?.slug === "other";

  const [slug, setSlug] = useState(category?.slug ?? "");
  const [names, setNames] = useState({ uz: category?.name_uz ?? "", ru: category?.name_ru ?? "", en: category?.name_en ?? "" });
  const [descs, setDescs] = useState({ uz: category?.description_uz ?? "", ru: category?.description_ru ?? "", en: category?.description_en ?? "" });
  const [severity, setSeverity] = useState<CategoryInput["severity"]>(category?.severity ?? "info");
  const [color, setColor] = useState(asTone(category?.color));
  const [icon, setIcon] = useState(category?.icon && CATEGORY_ICONS[category.icon] ? category.icon : "Tag");
  const [notify, setNotify] = useState(category?.notify ?? false);
  const [retention, setRetention] = useState(category?.retention_days != null ? String(category.retention_days) : "");
  const [enabled, setEnabled] = useState(category?.enabled ?? true);
  const [stems, setStems] = useState<Record<string, string>>(
    Object.fromEntries(STEM_LANGS.map((l) => [l, joinLines(category?.rules?.stems?.[l])])),
  );
  const [patterns, setPatterns] = useState(joinLines(category?.rules?.patterns));
  const [exclude, setExclude] = useState(joinLines(category?.rules?.exclude));
  const [weight, setWeight] = useState(category?.rules?.weight != null ? String(category.rules.weight) : "");
  const [minScore, setMinScore] = useState(category?.rules?.min_score != null ? String(category.rules.min_score) : "");

  const [submitted, setSubmitted] = useState(false);
  const [confirmDisable, setConfirmDisable] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const errs = useMemo(() => {
    const e: Record<string, string> = {};
    if (!editing && (slug.length < 2 || slug.length > 48 || !SLUG_RE.test(slug))) e.slug = t("form.slugInvalid");
    if (NAME_LANGS.some((l) => !names[l].trim())) e.names = t("form.nameRequired");
    if (retention.trim() !== "" && !/^[1-9]\d{0,5}$/.test(retention.trim())) e.retention = t("form.retentionInvalid");
    const pb = badLine(patterns);
    if (pb) e.patterns = t("rules.invalidLine", pb);
    const xb = badLine(exclude);
    if (xb) e.exclude = t("rules.invalidLine", xb);
    const num = (v: string, min: number, max: number) =>
      v.trim() === "" || (Number.isFinite(Number(v)) && Number(v) >= min && Number(v) <= max);
    if (!num(weight, 0, 10)) e.weight = t("rules.number", { min: 0, max: 10 });
    if (!num(minScore, 0, 100)) e.minScore = t("rules.number", { min: 0, max: 100 });
    return e;
  }, [editing, slug, names, retention, patterns, exclude, weight, minScore, t]);

  const disabling = editing && category.enabled && !enabled;

  const submit = async (ev: React.FormEvent) => {
    ev.preventDefault();
    setSubmitted(true);
    setError(null);
    if (Object.keys(errs).length) return;
    if (disabling && !confirmDisable) {
      setConfirmDisable(true);
      return;
    }
    const rules: NonNullable<CategoryInput["rules"]> = {
      stems: Object.fromEntries(STEM_LANGS.map((l) => [l, lines(stems[l])])),
      patterns: lines(patterns),
      exclude: lines(exclude),
    };
    if (weight.trim() !== "") rules.weight = Number(weight);
    if (minScore.trim() !== "") rules.min_score = Number(minScore);
    const body = {
      name_uz: names.uz.trim(), name_ru: names.ru.trim(), name_en: names.en.trim(),
      description_uz: descs.uz.trim(), description_ru: descs.ru.trim(), description_en: descs.en.trim(),
      severity, color, icon, notify, enabled,
      retention_days: retention.trim() === "" ? null : Number(retention),
      rules,
    };
    setSaving(true);
    try {
      if (editing) await updateCategory(category.id, body);
      else await createCategory({ ...body, slug, sort_order: nextOrder });
      invalidateCategories();
      onSaved();
    } catch (e) {
      setError(e instanceof Error ? e.message : t("form.saveFailed"));
    } finally {
      setSaving(false);
    }
  };

  const show = (k: string) => (submitted ? errs[k] : undefined);

  return (
    <Drawer title={editing ? t("form.editTitle") : t("form.addTitle")} closeLabel={t("form.close")} onClose={onClose}>
      <form onSubmit={submit} noValidate className="flex min-h-0 flex-1 flex-col">
        <div className="min-h-0 flex-1 space-y-6 overflow-y-auto px-4 py-5 sm:px-6">
          {error && <ErrorBanner message={error} />}

          {!editing && (
            <div>
              <Label htmlFor="cat-slug">{t("form.slug")}</Label>
              <Input id="cat-slug" data-autofocus mono value={slug} maxLength={48} autoComplete="off"
                onChange={(e) => setSlug(e.target.value.toLowerCase())}
                aria-invalid={!!show("slug")} aria-describedby="cat-slug-h cat-slug-e" />
              <Help id="cat-slug-h">{t("form.slugHelp")}</Help>
              {show("slug") && <FieldError id="cat-slug-e">{show("slug")}</FieldError>}
            </div>
          )}

          <fieldset className="space-y-4">
            <legend className="mb-2 text-sm font-semibold text-fg">{t("form.names")}</legend>
            {NAME_LANGS.map((l, i) => (
              <div key={l} className="space-y-2 rounded-lg border border-border p-3">
                <div className="text-xs font-semibold uppercase tracking-wide text-fg-muted">{t(`form.langs.${l}`)}</div>
                <div>
                  <Label htmlFor={`cat-name-${l}`}>{t("form.name")}</Label>
                  <Input id={`cat-name-${l}`} data-autofocus={editing && i === 0 ? true : undefined} value={names[l]}
                    maxLength={120} onChange={(e) => setNames({ ...names, [l]: e.target.value })}
                    aria-invalid={!!show("names") && !names[l].trim()} />
                </div>
                <div>
                  <Label htmlFor={`cat-desc-${l}`}>{t("form.description")}</Label>
                  <textarea id={`cat-desc-${l}`} rows={2} value={descs[l]} className={cn(TEXTAREA, "font-sans")}
                    onChange={(e) => setDescs({ ...descs, [l]: e.target.value })} />
                </div>
              </div>
            ))}
            {show("names") && <FieldError id="cat-names-e">{show("names")}</FieldError>}
          </fieldset>

          <div>
            <Label htmlFor="cat-sev">{t("form.severity")}</Label>
            <Select id="cat-sev" value={severity} onChange={(e) => setSeverity(e.target.value as CategoryInput["severity"])}
              aria-describedby="cat-sev-h">
              {SEVERITIES.map((s) => <option key={s} value={s}>{ts(s)}</option>)}
            </Select>
            <Help id="cat-sev-h">{t("form.severityHelp")}</Help>
          </div>

          <fieldset>
            <legend className="mb-2 text-sm font-medium text-fg">{t("form.color")}</legend>
            <div className="grid grid-cols-2 gap-2 min-[420px]:grid-cols-3">
              {TONES.map((c) => {
                const on = color === c;
                return (
                  <label key={c} className={cn("flex min-h-10 cursor-pointer items-center gap-2 rounded-lg border px-2 text-xs font-medium",
                    "focus-within:ring-2 focus-within:ring-ring", on ? "border-primary bg-surface-2 text-fg" : "border-border text-fg-muted hover:bg-surface-2")}>
                    <input type="radio" name="cat-color" value={c} checked={on} onChange={() => setColor(c)} className="sr-only" />
                    <span aria-hidden className={cn("grid h-5 w-5 shrink-0 place-items-center rounded-full border", toneClass(c))}>
                      {on && <Check className="h-3 w-3" />}
                    </span>
                    <span className="min-w-0 truncate">{t(`tones.${c}`)}</span>
                    {on && <span className="sr-only">{t("form.colorSelected")}</span>}
                  </label>
                );
              })}
            </div>
          </fieldset>

          <fieldset>
            <legend className="mb-2 text-sm font-medium text-fg">{t("form.icon")}</legend>
            <div className="grid grid-cols-4 gap-2 min-[420px]:grid-cols-6">
              {Object.entries(CATEGORY_ICONS).map(([name, Icon]) => {
                const on = icon === name;
                return (
                  <label key={name} title={name}
                    className={cn("relative flex h-14 cursor-pointer flex-col items-center justify-center gap-0.5 rounded-lg border",
                      "focus-within:ring-2 focus-within:ring-ring", on ? "border-primary bg-primary-soft text-primary" : "border-border text-fg-muted hover:bg-surface-2")}>
                    <input type="radio" name="cat-icon" value={name} checked={on} onChange={() => setIcon(name)} className="sr-only" />
                    <Icon className="h-5 w-5" aria-hidden />
                    <span className="max-w-full truncate px-0.5 text-[10px] leading-none">{name}</span>
                    {on && <Check className="absolute right-1 top-1 h-3 w-3" aria-hidden />}
                  </label>
                );
              })}
            </div>
          </fieldset>

          <Toggle id="cat-notify" checked={notify} onChange={setNotify} label={t("form.notify")} help={t("form.notifyHelp")} />

          <div>
            <Label htmlFor="cat-ret">{t("form.retention")}</Label>
            <Input id="cat-ret" inputMode="numeric" value={retention} onChange={(e) => setRetention(e.target.value)}
              aria-invalid={!!show("retention")} aria-describedby="cat-ret-h cat-ret-e" />
            <Help id="cat-ret-h">{t("form.retentionHelp")}</Help>
            {show("retention") && <FieldError id="cat-ret-e">{show("retention")}</FieldError>}
          </div>

          <div>
            <Toggle id="cat-enabled" checked={enabled} disabled={locked}
              onChange={(v) => { setEnabled(v); setConfirmDisable(false); }}
              label={t("form.enabled")} help={locked ? t("form.enabledLockedHelp") : t("form.enabledHelp")} />
            {confirmDisable && disabling && (
              <p role="alert" className={cn("mt-2 rounded-lg border px-3 py-2 text-xs", toneClass("amber"))}>{t("form.disableWarn")}</p>
            )}
          </div>

          <section className="space-y-4 border-t border-border pt-5">
            <div>
              <h3 className="text-sm font-semibold text-fg">{t("rules.title")}</h3>
              <p className="mt-1 text-xs text-fg-muted">{t("rules.intro")}</p>
            </div>
            {STEM_LANGS.map((l) => (
              <div key={l}>
                <Label htmlFor={`cat-stems-${l}`}>{t("rules.stems", { lang: t(`form.langs.${l}`) })}</Label>
                <textarea id={`cat-stems-${l}`} rows={4} value={stems[l]} className={TEXTAREA} spellCheck={false}
                  onChange={(e) => setStems({ ...stems, [l]: e.target.value })} aria-describedby={`cat-stems-${l}-h`} />
                <Help id={`cat-stems-${l}-h`}>{t("rules.stemsHelp")}</Help>
              </div>
            ))}
            <div>
              <Label htmlFor="cat-patterns">{t("rules.patterns")}</Label>
              <textarea id="cat-patterns" rows={3} value={patterns} className={TEXTAREA} spellCheck={false}
                onChange={(e) => setPatterns(e.target.value)} aria-invalid={!!show("patterns")} aria-describedby="cat-patterns-h cat-patterns-e" />
              <Help id="cat-patterns-h">{t("rules.patternsHelp")}</Help>
              {show("patterns") && <FieldError id="cat-patterns-e">{show("patterns")}</FieldError>}
            </div>
            <div>
              <Label htmlFor="cat-exclude">{t("rules.exclude")}</Label>
              <textarea id="cat-exclude" rows={3} value={exclude} className={TEXTAREA} spellCheck={false}
                onChange={(e) => setExclude(e.target.value)} aria-invalid={!!show("exclude")} aria-describedby="cat-exclude-h cat-exclude-e" />
              <Help id="cat-exclude-h">{t("rules.excludeHelp")}</Help>
              {show("exclude") && <FieldError id="cat-exclude-e">{show("exclude")}</FieldError>}
            </div>
            <div className="grid grid-cols-1 gap-4 min-[420px]:grid-cols-2">
              <div>
                <Label htmlFor="cat-weight">{t("rules.weight")}</Label>
                <Input id="cat-weight" type="number" step="0.1" min={0} max={10} placeholder="1" value={weight}
                  onChange={(e) => setWeight(e.target.value)} aria-invalid={!!show("weight")} aria-describedby="cat-weight-h cat-weight-e" />
                <Help id="cat-weight-h">{t("rules.weightHelp")}</Help>
                {show("weight") && <FieldError id="cat-weight-e">{show("weight")}</FieldError>}
              </div>
              <div>
                <Label htmlFor="cat-min">{t("rules.minScore")}</Label>
                <Input id="cat-min" type="number" step="0.5" min={0} max={100} placeholder="1" value={minScore}
                  onChange={(e) => setMinScore(e.target.value)} aria-invalid={!!show("minScore")} aria-describedby="cat-min-h cat-min-e" />
                <Help id="cat-min-h">{t("rules.minScoreHelp")}</Help>
                {show("minScore") && <FieldError id="cat-min-e">{show("minScore")}</FieldError>}
              </div>
            </div>
          </section>
        </div>
        <div className="flex justify-end gap-2 border-t border-border px-4 py-3 sm:px-6">
          <Button variant="secondary" onClick={onClose}>{t("delete.cancel")}</Button>
          <Button type="submit" loading={saving}>
            {confirmDisable && disabling ? t("form.confirmSave") : editing ? t("form.save") : t("form.create")}
          </Button>
        </div>
      </form>
    </Drawer>
  );
}
