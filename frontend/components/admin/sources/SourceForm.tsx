"use client";

import { FlaskConical, MessageCircle, RefreshCw } from "lucide-react";
import { useTranslations } from "next-intl";
import { useId, useMemo, useState } from "react";
import { Button, ErrorBanner, Input, Label, Select } from "@/components/ui";
import {
  createSource, getTgChats, testSourceDraft, updateSource,
  type ConnectorInfo, type Source, type SourceInput, type SourceTest, type TgChat,
} from "@/lib/adminApi";
import { useCategories } from "@/lib/useCategories";
import Overlay from "./Overlay";
import { TestResultView } from "./Results";
import { LANGS, humanInterval } from "./lib";

const NUMERIC_FIELDS = new Set(["limit", "days", "max_pages"]);
const ARRAY_FIELDS = new Set(["countries"]);
const KNOWN_FIELDS = new Set(["url", "query", "countries", "chat", "channel", "item", "title", "link", "date", "date_format", "summary", "limit", "days", "max_pages"]);

const pretty = (o: unknown) => JSON.stringify(o, null, 2);

function rawOf(name: string, v: unknown): string {
  if (v === undefined || v === null) return "";
  if (Array.isArray(v)) return v.join(", ");
  return String(v);
}
function rawMap(fields: string[], cfg: Record<string, unknown>) {
  return Object.fromEntries(fields.map((n) => [n, rawOf(n, cfg[n])]));
}

function FieldError({ id, msg }: { id: string; msg?: string }) {
  return msg ? (
    <p id={id} className="mt-1 text-xs text-danger">
      {msg}
    </p>
  ) : null;
}

function Help({ id, children }: { id: string; children: React.ReactNode }) {
  return (
    <p id={id} className="mt-1 text-xs text-fg-muted">
      {children}
    </p>
  );
}

function Check({
  id, label, help, checked, onChange,
}: { id: string; label: string; help?: string; checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <div>
      <label htmlFor={id} className="flex cursor-pointer items-center gap-2 text-sm font-medium text-fg">
        <input
          id={id}
          type="checkbox"
          checked={checked}
          onChange={(e) => onChange(e.target.checked)}
          aria-describedby={help ? `${id}-h` : undefined}
          className="focus-ring h-4 w-4 rounded border-border accent-primary"
        />
        {label}
      </label>
      {help && <Help id={`${id}-h`}>{help}</Help>}
    </div>
  );
}

function TelegramPicker({ onPick }: { onPick: (v: string) => void }) {
  const t = useTranslations("adminSources");
  const [chats, setChats] = useState<TgChat[] | null>(null);
  const [q, setQ] = useState("");
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const id = useId();

  const load = async (refresh = false) => {
    setLoading(true);
    setErr(null);
    try {
      setChats(await getTgChats(refresh));
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setLoading(false);
    }
  };

  // Akkauntda yuzlab chat bo'lishi mumkin — nomi, @username yoki ID bo'yicha qidirish
  const shown = useMemo(() => {
    const needle = q.trim().replace(/^@/, "").toLowerCase();
    if (!chats || !needle) return chats ?? [];
    return chats.filter((c) =>
      c.title.toLowerCase().includes(needle) || (c.username ?? "").toLowerCase().includes(needle) ||
      String(c.id).includes(needle));
  }, [chats, q]);

  return (
    <div className="rounded-lg border border-border bg-surface-2 p-3">
      {chats === null ? (
        <Button variant="secondary" size="sm" icon={MessageCircle} loading={loading} onClick={() => load()}>
          {loading ? t("tg.loading") : t("tg.pick")}
        </Button>
      ) : chats.length === 0 ? (
        <p className="text-sm text-fg-muted">{t("tg.none")}</p>
      ) : (
        <div className="space-y-2">
          <div className="flex items-end gap-2">
            <div className="min-w-0 flex-1">
              <Label htmlFor={`${id}-q`}>{t("tg.search")}</Label>
              <Input id={`${id}-q`} type="search" value={q} placeholder={t("tg.searchPlaceholder")}
                onChange={(e) => setQ(e.target.value)} />
            </div>
            <Button variant="secondary" size="sm" icon={RefreshCw} loading={loading} onClick={() => load(true)}>
              {t("tg.refresh")}
            </Button>
          </div>
          <div>
            <Label htmlFor={id}>{t("tg.pick")}</Label>
            {shown.length === 0 ? (
              <p className="text-sm text-fg-muted">{t("tg.noMatch")}</p>
            ) : (
              <Select
                key={q}
                id={id}
                defaultValue=""
                aria-describedby={`${id}-n`}
                onChange={(e) => {
                  const c = shown.find((x) => String(x.id) === e.target.value);
                  if (c) onPick(c.username ? c.username : String(c.id));
                }}
              >
                <option value="" disabled>{t("tg.choose")}</option>
                {shown.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.title}
                    {c.username ? ` (@${c.username})` : ""} · {c.kind === "channel" ? t("tg.channel") : t("tg.group")}
                    {c.monitored ? ` · ✓ ${t("tg.monitored")}` : ""}
                  </option>
                ))}
              </Select>
            )}
            <p id={`${id}-n`} className="mt-1 text-xs text-fg-muted">
              {t("tg.count", { shown: shown.length, total: chats.length })}
            </p>
          </div>
        </div>
      )}
      {err && (
        <div className="mt-2">
          <ErrorBanner message={err} />
          <p className="mt-1 text-xs text-fg-muted">{t("tg.manualHint")}</p>
        </div>
      )}
    </div>
  );
}

export default function SourceForm({
  source, connectors, onClose, onSaved,
}: {
  source: Source | null;
  connectors: ConnectorInfo[];
  onClose: () => void;
  onSaved: (s: Source, created: boolean) => void;
}) {
  const t = useTranslations("adminSources");
  const tc = useTranslations("common");
  const uid = useId();
  const { list: cats } = useCategories();
  const editing = !!source;

  const [name, setName] = useState(source?.name ?? "");
  const [kind, setKind] = useState(source?.kind ?? "");
  const [config, setConfig] = useState<Record<string, unknown>>(source?.config ?? {});
  const [jsonText, setJsonText] = useState(pretty(source?.config ?? {}));
  const [jsonErr, setJsonErr] = useState<string | null>(null);
  const conn0 = connectors.find((c) => c.kind === source?.kind);
  const [raw, setRaw] = useState<Record<string, string>>(
    rawMap([...(conn0?.config_fields ?? []), ...Object.keys(source?.config ?? {})], source?.config ?? {}),
  );
  const [lang, setLang] = useState(source?.lang ?? "en");
  const [category, setCategory] = useState(source?.category ?? "");
  const [scope, setScope] = useState<"regional" | "global">(source?.scope ?? "regional");
  const [region, setRegion] = useState(source?.region_filter ?? false);
  const [cyber, setCyber] = useState(source?.cyber_filter ?? true);
  const [translate, setTranslate] = useState(source?.translate ?? true);
  const [enabled, setEnabled] = useState(source?.enabled ?? true);
  const [interval, setIntervalS] = useState(String(source?.interval_seconds ?? 600));
  const [jitter, setJitter] = useState(String(source?.jitter_pct ?? 20));
  const [backfill, setBackfill] = useState(String(source?.backfill_days ?? 14));
  const [keyEnv, setKeyEnv] = useState(source?.api_key_env ?? "");
  const [notes, setNotes] = useState(source?.notes ?? "");

  const [errors, setErrors] = useState<Record<string, string>>({});
  const [serverErr, setServerErr] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testRes, setTestRes] = useState<SourceTest | null>(null);

  const conn = connectors.find((c) => c.kind === kind);
  const fields = useMemo(() => conn?.config_fields ?? [], [conn]);

  const syncConfig = (next: Record<string, unknown>) => {
    setConfig(next);
    setJsonText(pretty(next));
    setJsonErr(null);
  };

  const setField = (n: string, value: string) => {
    setRaw((r) => ({ ...r, [n]: value }));
    const next = { ...config };
    const v = value.trim();
    if (v === "") delete next[n];
    else if (ARRAY_FIELDS.has(n)) next[n] = v.split(",").map((x) => x.trim()).filter(Boolean);
    else if (NUMERIC_FIELDS.has(n) && Number.isFinite(Number(v))) next[n] = Number(v);
    else next[n] = value;
    syncConfig(next);
  };

  const onJson = (text: string) => {
    setJsonText(text);
    try {
      const p = JSON.parse(text);
      if (p === null || typeof p !== "object" || Array.isArray(p)) {
        setJsonErr(t("form.jsonNotObject"));
        return;
      }
      setJsonErr(null);
      setConfig(p as Record<string, unknown>);
      setRaw(rawMap(fields, p as Record<string, unknown>));
    } catch (e) {
      setJsonErr(t("form.jsonInvalid", { error: (e as Error).message }));
    }
  };

  const onKind = (k: string) => {
    setKind(k);
    const c = connectors.find((x) => x.kind === k);
    syncConfig({});
    setRaw({});
    setKeyEnv(c?.key ? (c.default_key_env ?? "") : "");
    setTestRes(null);
  };

  const buildInput = (): SourceInput | null => {
    const e: Record<string, string> = {};
    if (!name.trim()) e.name = t("form.nameRequired");
    if (!kind) e.kind = t("form.kindRequired");
    const iv = Number(interval);
    if (!Number.isFinite(iv) || interval.trim() === "") e.interval = t("form.numberInvalid");
    else if (iv < 60) e.interval = t("form.intervalMin");
    const jt = Number(jitter);
    if (!Number.isFinite(jt) || jitter.trim() === "") e.jitter = t("form.numberInvalid");
    const bf = Number(backfill);
    if (!Number.isFinite(bf) || backfill.trim() === "") e.backfill = t("form.numberInvalid");
    if (jsonErr) e.json = jsonErr;
    setErrors(e);
    if (Object.keys(e).length) return null;
    return {
      name: name.trim(),
      kind,
      config,
      lang,
      category: category || null,
      scope,
      region_filter: region,
      cyber_filter: cyber,
      translate,
      enabled,
      interval_seconds: Math.round(iv),
      jitter_pct: jt,
      backfill_days: Math.round(bf),
      api_key_env: keyEnv.trim() || null,
      notes,
    };
  };

  const runTest = async () => {
    setServerErr(null);
    const input = buildInput();
    if (!input) return;
    setTesting(true);
    setTestRes(null);
    try {
      setTestRes(await testSourceDraft(input));
    } catch (e) {
      setServerErr((e as Error).message);
    } finally {
      setTesting(false);
    }
  };

  const submit = async (ev: React.FormEvent) => {
    ev.preventDefault();
    setServerErr(null);
    const input = buildInput();
    if (!input) return;
    setSaving(true);
    try {
      if (source) {
        const { kind: _k, ...rest } = input;
        void _k;
        onSaved(await updateSource(source.id, rest), false);
      } else {
        onSaved(await createSource(input), true);
      }
    } catch (e) {
      setServerErr((e as Error).message);
    } finally {
      setSaving(false);
    }
  };

  const err = (k: string) => (errors[k] ? `${uid}-${k}-e` : undefined);
  const ivNum = Number(interval);
  const intervalHuman = Number.isFinite(ivNum) && ivNum >= 60 ? humanInterval(ivNum, t) : "—";
  const formId = `${uid}-form`;

  return (
    <Overlay
      side
      title={editing ? t("form.titleEdit") : t("form.titleCreate")}
      onClose={onClose}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>{tc("cancel")}</Button>
          <Button variant="secondary" icon={FlaskConical} loading={testing} onClick={runTest} title={t("form.testHint")}>
            {t("form.test")}
          </Button>
          <Button type="submit" form={formId} loading={saving}>
            {editing ? t("form.save") : t("form.create")}
          </Button>
        </>
      }
    >
      <form id={formId} onSubmit={submit} noValidate className="space-y-4">
        {serverErr && <ErrorBanner message={serverErr} />}

        <div>
          <Label htmlFor={`${uid}-name`}>{t("form.name")}</Label>
          <Input
            id={`${uid}-name`}
            data-autofocus
            value={name}
            onChange={(e) => setName(e.target.value)}
            aria-invalid={!!errors.name}
            aria-describedby={err("name")}
            maxLength={200}
          />
          <FieldError id={`${uid}-name-e`} msg={errors.name} />
        </div>

        <div>
          <Label htmlFor={`${uid}-kind`}>{t("form.kind")}</Label>
          <Select
            id={`${uid}-kind`}
            value={kind}
            disabled={editing}
            onChange={(e) => onKind(e.target.value)}
            aria-invalid={!!errors.kind}
            aria-describedby={err("kind") ?? (editing ? `${uid}-kind-h` : undefined)}
          >
            {!kind && <option value="">{t("form.kindPick")}</option>}
            {connectors.map((c) => (
              <option key={c.kind} value={c.kind}>{c.title}</option>
            ))}
            {kind && !conn && <option value={kind}>{kind}</option>}
          </Select>
          {editing && <Help id={`${uid}-kind-h`}>{t("form.kindFixed")}</Help>}
          <FieldError id={`${uid}-kind-e`} msg={errors.kind} />
        </div>

        {kind && (
          <fieldset className="space-y-3 rounded-lg border border-border p-3">
            <legend className="px-1 text-sm font-medium text-fg">{t("form.config")}</legend>
            {kind === "telegram_user" && (
              <TelegramPicker onPick={(v) => setField("chat", v)} />
            )}
            {fields.map((n) => {
              const label = KNOWN_FIELDS.has(n) ? t(`fields.${n}`) : n;
              const id = `${uid}-f-${n}`;
              return (
                <div key={n}>
                  <Label htmlFor={id}>{label}</Label>
                  <Input
                    id={id}
                    mono
                    value={raw[n] ?? ""}
                    onChange={(e) => setField(n, e.target.value)}
                    inputMode={NUMERIC_FIELDS.has(n) ? "numeric" : undefined}
                    aria-describedby={n === "countries" ? `${id}-h` : undefined}
                  />
                  {n === "countries" && <Help id={`${id}-h`}>{t("fields.countriesHelp")}</Help>}
                </div>
              );
            })}
            <div>
              <Label htmlFor={`${uid}-json`}>{t("form.advanced")}</Label>
              <textarea
                id={`${uid}-json`}
                value={jsonText}
                onChange={(e) => onJson(e.target.value)}
                rows={6}
                spellCheck={false}
                aria-invalid={!!jsonErr}
                aria-describedby={`${uid}-json-h ${uid}-json-e`}
                className="w-full rounded-lg border border-border bg-surface px-3 py-2 font-mono text-xs text-fg hover:border-border-strong focus:border-ring focus:outline-none focus:ring-2 focus:ring-ring/30"
              />
              <Help id={`${uid}-json-h`}>{t("form.advancedHelp")}</Help>
              <FieldError id={`${uid}-json-e`} msg={jsonErr ?? undefined} />
            </div>
          </fieldset>
        )}

        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <Label htmlFor={`${uid}-lang`}>{t("form.language")}</Label>
            <Select id={`${uid}-lang`} value={lang} onChange={(e) => setLang(e.target.value)}>
              {LANGS.map((l) => <option key={l} value={l}>{t(`langs.${l}`)}</option>)}
              {!(LANGS as readonly string[]).includes(lang) && <option value={lang}>{lang}</option>}
            </Select>
          </div>
          <div>
            <Label htmlFor={`${uid}-scope`}>{t("form.scope")}</Label>
            <ScopeSelect id={`${uid}-scope`} value={scope} onChange={setScope} />
          </div>
        </div>

        <div>
          <Label htmlFor={`${uid}-cat`}>{t("form.category")}</Label>
          <Select id={`${uid}-cat`} value={category} onChange={(e) => setCategory(e.target.value)} aria-describedby={`${uid}-cat-h`}>
            <option value="">{t("form.categoryNone")}</option>
            {cats.map((c) => <option key={c.slug} value={c.slug}>{c.name}</option>)}
            {category && !cats.some((c) => c.slug === category) && <option value={category}>{category}</option>}
          </Select>
          <Help id={`${uid}-cat-h`}>{t("form.categoryHelp")}</Help>
        </div>

        <div className="space-y-3 rounded-lg border border-border p-3">
          <Check id={`${uid}-region`} label={t("form.regionFilter")} help={t("form.regionFilterHelp")} checked={region} onChange={setRegion} />
          <Check id={`${uid}-cyber`} label={t("form.cyberFilter")} help={t("form.cyberFilterHelp")} checked={cyber} onChange={setCyber} />
          <Check id={`${uid}-tr`} label={t("form.translate")} help={t("form.translateHelp")} checked={translate} onChange={setTranslate} />
          <Check id={`${uid}-en`} label={t("form.enabled")} help={t("form.enabledHelp")} checked={enabled} onChange={setEnabled} />
        </div>

        <div className="grid gap-4 sm:grid-cols-3">
          <div className="sm:col-span-3">
            <Label htmlFor={`${uid}-iv`}>{t("form.interval")}</Label>
            <Input
              id={`${uid}-iv`}
              type="number"
              min={60}
              step={1}
              value={interval}
              onChange={(e) => setIntervalS(e.target.value)}
              aria-invalid={!!errors.interval}
              aria-describedby={`${uid}-iv-h ${uid}-interval-e`}
            />
            <Help id={`${uid}-iv-h`}>{t("form.intervalHelp", { human: intervalHuman })}</Help>
            <FieldError id={`${uid}-interval-e`} msg={errors.interval} />
          </div>
          <div>
            <Label htmlFor={`${uid}-jt`}>{t("form.jitter")}</Label>
            <Input id={`${uid}-jt`} type="number" min={0} max={100} value={jitter} onChange={(e) => setJitter(e.target.value)}
              aria-invalid={!!errors.jitter} aria-describedby={`${uid}-jt-h ${uid}-jitter-e`} />
            <Help id={`${uid}-jt-h`}>{t("form.jitterHelp")}</Help>
            <FieldError id={`${uid}-jitter-e`} msg={errors.jitter} />
          </div>
          <div className="sm:col-span-2">
            <Label htmlFor={`${uid}-bf`}>{t("form.backfill")}</Label>
            <Input id={`${uid}-bf`} type="number" min={0} value={backfill} onChange={(e) => setBackfill(e.target.value)}
              aria-invalid={!!errors.backfill} aria-describedby={`${uid}-bf-h ${uid}-backfill-e`} />
            <Help id={`${uid}-bf-h`}>{t("form.backfillHelp")}</Help>
            <FieldError id={`${uid}-backfill-e`} msg={errors.backfill} />
          </div>
        </div>

        <div>
          <Label htmlFor={`${uid}-key`}>{t("form.apiKeyEnv")}</Label>
          <Input id={`${uid}-key`} mono value={keyEnv} onChange={(e) => setKeyEnv(e.target.value)} placeholder="OTX_API_KEY"
            autoComplete="off" aria-describedby={`${uid}-key-h`} />
          <Help id={`${uid}-key-h`}>
            {t("form.apiKeyHint")}
            {conn?.key === "required" ? ` ${t("form.keyRequired")}` : conn?.key === "optional" ? ` ${t("form.keyOptional")}` : ""}
          </Help>
        </div>

        <div>
          <Label htmlFor={`${uid}-notes`}>{t("form.notes")}</Label>
          <textarea
            id={`${uid}-notes`}
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            rows={3}
            className="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-fg hover:border-border-strong focus:border-ring focus:outline-none focus:ring-2 focus:ring-ring/30"
          />
        </div>

        {(testing || testRes) && (
          <div className="rounded-lg border border-border p-3">
            <div className="mb-2 text-sm font-semibold text-fg">{t("test.title")}</div>
            {testing ? <p className="text-sm text-fg-muted">{t("test.running")}</p> : testRes && <TestResultView r={testRes} />}
          </div>
        )}
      </form>
    </Overlay>
  );
}

function ScopeSelect({ id, value, onChange }: { id: string; value: "regional" | "global"; onChange: (v: "regional" | "global") => void }) {
  const ts = useTranslations("scope");
  return (
    <Select id={id} value={value} onChange={(e) => onChange(e.target.value as "regional" | "global")}>
      <option value="regional">{ts("regional")}</option>
      <option value="global">{ts("global")}</option>
    </Select>
  );
}
