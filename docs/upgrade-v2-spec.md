# OSINT Platform v2 upgrade

You are the lead engineer on this repository: my OSINT and dark-web monitoring platform for Central Asia. I am the owner and, for now, its only user. Carry out the upgrade below from start to finish in one long run. Decide things the way a senior engineer who has run a threat-intelligence feed in production would: proven tools, small reversible steps, and nothing reported as done until you have run it.

If this text is not already in the repository, save it unchanged as `docs/upgrade-v2-spec.md` in your first commit and re-read it at the start of every phase. Long runs lose early context; the file does not.

## 1. Read first

Read `PROGRESS.md`, `CLAUDE.md`, `docs/architecture.md`, `docs/design-system.md` and `docs/tasks.md`, then the code in `backend/app/services/events/`, `backend/app/api/` and `frontend/`. `PROGRESS.md` also describes this machine's quirks (docker-compose v1, no `--reload`, a root-owned `backend/data/`); use its workarounds.

The problems this upgrade removes:

- All 63 sources are hard-coded in `backend/app/services/events/feeds.py` and polled in one batch every 300 seconds. `aggregator._fetch_cached` swallows every error, so a broken source is invisible.
- The five categories (`news`, `ransomware`, `leak`, `telegram`, `tg_group`) mix what an event is about with where it came from.
- Matched keywords are glued into `summary` as `🔎 a, b · text` and parsed back out by a regex in `frontend/app/dashboard/events/page.tsx`.
- There are no migrations (`create_all` in `backend/app/main.py`), no user roles and no automated tests. Any registered user can call `POST /api/events/refresh` and read my Telegram account name and chat list from `/api/telegram/*`.
- The interface is dark-only with about 700 hard-coded colour classes, every string is hard-coded Uzbek, and the only charts are two hand-written components.

## 2. The result I want

1. Sources live in PostgreSQL, with full CRUD and a health view in an admin area.
2. Every source is fetched on its own randomised schedule.
3. The most important threat-intelligence sources are connected and their data is stored.
4. More than ten topic categories, with CRUD, used as filters everywhere.
5. Every event is stored in English, Russian and Uzbek (Latin script), translated through Google Cloud Translation.
6. A clean interface that is easy to understand, with Light, Dark and System themes and complete uz / ru / en localisation.
7. A dashboard of real, interactive statistics.

## 3. Your permissions

You have my full permission to do everything this task needs inside the project without asking: create, edit and delete files; add or upgrade dependencies; change the database schema through migrations; rebuild and restart the project's containers; run servers, tests and scripts; commit and push to the working branch; and choose names, structure and design details yourself.

The limits, each with its reason:

- Work on a new branch `feat/v2-upgrade`. Never force-push and never merge into `main`. I want to compare v2 with the working version before I switch.
- Before the first migration, dump the database to `~/osint-backups/` (outside the repo). Never drop the Postgres volume. An earlier clean-up already deleted records that cannot be collected again.
- Leave `backend/data/` and the Telegram session alone, and never print or commit secrets. That session file gives full access to my Telegram account.
- Collect only from public pages, feeds and official APIs. When a site answers with a login wall, a CAPTCHA or a Cloudflare challenge, record the source as blocked and cover it through an API or a secondary source instead. Do not add CAPTCHA solvers, browser-fingerprint spoofing, proxy rotation or automated logins. This is the rule the project already follows (`feeds.py`, `PROGRESS.md`): getting around access controls is the point where OSINT work turns into unauthorised access.
- Store event metadata only: who, what, when, which group, a link. Never download or store leaked files, credentials or personal data.
- The check modules (username, email, phone, domain, history) receive the new theme and translations and nothing else. Their logic and scope stay as they are.

## 4. How to work

- Track progress the way this repo already does: phases as a checklist in `docs/tasks.md`, details in `PROGRESS.md` (keep its language and its honest "tekshirildi / tekshirilmadi" lists). Those two files plus the spec are the resume point if a session ends.
- Finish each phase completely before the next one: code, migration, tests, a real run against the local stack, docs, then a commit in the repo's `feat:` / `fix:` / `chore:` style and a push.
- Before a phase's first tool call, say in one line what you are starting. When it is finished, say in one or two lines what changed and what you verified, in the same message as your next tool call.
- Move from phase to phase without waiting for my approval. Do not end a turn with a summary of what comes next or an offer to continue. Stop only when nothing more can move without me. A missing API key is not such a case: build the feature, leave that source disabled with a clear status, and carry on.
- Everything that works today must still work after every phase: login, the four check modules, history, report export, notifications, Telegram collection. `frontend/scripts/qa/smoke.js` is the regression check; extend it as pages are added.
- Use subagents for bounded, parallel work (one connector, the strings of one page). Keep schema and API contracts in the main session.
- Add no Celery, Redis, Kafka or other new services. PostgreSQL and asyncio are enough at this size. Stay on Next.js 14; a framework upgrade is a separate job.
- Before coding against any external API or library, open its current documentation and confirm endpoints, authentication, limits and versions. The facts in this prompt were checked in November 2026 and may have moved.
- Where the repository contradicts this prompt, trust the repository and note the deviation in the final report.

## 5. The work

### Phase 0 — Foundations

- Create the branch and take the database backup.
- Alembic: a baseline revision that matches today's schema, `alembic stamp` for the existing database, migrations applied on container start, and `create_all` removed from application start-up.
- Roles: `users.role` (`admin` or `analyst`) and `users.locale`. Admins are the addresses in `ADMIN_EMAILS`, otherwise the oldest user. Add a `require_admin` dependency and put it on every `/api/admin/*` route, on `POST /api/events/refresh` and on `/api/telegram/*`. Add `REGISTRATION_OPEN` (off by default outside development).
- Refuse to start outside development while `SECRET_KEY` is still the default. Move off `python-jose` 3.3.0 (CVE-2024-33663): upgrade it or switch to PyJWT.
- pytest with pytest-asyncio, an httpx `AsyncClient` and a separate test database. Tests that need the network run against recorded fixtures.

### Phase 1 — Data model

Column names are suggestions; keep them consistent.

- `sources`: name, `kind`, connector settings (JSONB: URL, query, country codes, chat id), language, fixed category (optional), `scope`, `region_filter`, `cyber_filter`, `translate`, enabled, `interval_seconds`, `jitter_pct`, `backfill_days`, the name of the environment variable that holds its key (never the key), ETag and Last-Modified, `next_run_at`, and health fields: status, last check, last success, last error, last HTTP status, latency, consecutive failures, items and new items in the last run, date of the newest item.
- `source_runs`: one row per fetch attempt (start, duration, HTTP status, ok, items, new items, error). Keep 30 days.
- `categories`: see Phase 4.
- `events` gains `source_id`, `category_id`, `category_locked`, `channel`, `scope`, `severity`, `countries` (array), `sector`, `actor`, `matched_keywords` (array), `extra` (JSONB for structured fields such as a CVE id or a record count), `also_reported_by` (JSONB) and `is_baseline`.
- `event_translations`: see Phase 5.

Migrate the existing rows in the same revision chain: move the `🔎 … ·` prefix out of `summary` into `matched_keywords`, set `channel`, link `source_id` by name, fill `countries` from the text. Keep `GET /api/events` backward compatible until the frontend is rebuilt in Phase 7: `category` stays a slug string and new fields are added beside it.

### Phase 2 — Collector engine: each source on its own randomised schedule

Replace the single 300-second loop with a scheduler that treats every source separately.

- Each source has `interval_seconds` and `jitter_pct` (default 20). After a run, `next_run_at = now + interval × random(1 − jitter, 1 + jitter)`. On start-up, spread the first runs randomly across one interval so sources never fire together.
- One loop wakes every 15–30 seconds and runs whatever is due: at most 8 fetches at once, one request at a time per host, and a random 1–4 second pause between requests to the same host.
- Send `If-None-Match` and `If-Modified-Since` when the source supplied an ETag or Last-Modified. A 304 is a healthy run with no new items.
- On failure, back off exponentially with jitter (capped at 6 hours) and obey `Retry-After` on 429 and 503. Treat Telethon's `FloodWaitError` the same way. Recover automatically on the next success.
- Keep schedule and cache state in the database rather than in process memory, so a restart neither refetches everything nor forgets a rate limit. ransomware.live and Google News are strict about this.
- Keep the collector inside the API process, because the Telethon session file cannot be shared by two processes. Guard the loop with a PostgreSQL advisory lock so a second worker never starts a second scheduler.
- Write one `source_runs` row per attempt and update the source's health fields. Status values: `ok`; `degraded` (succeeds but slow, flapping, or its newest item is much older than usual); `down` (three or more failures in a row); `blocked` (403, 429 or a challenge page); `auth_missing` (needs a key or a login that is not configured); `disabled`; `never_run`.
- A source's first successful run is a baseline. Store the items that fall inside its backfill window (`backfill_days`, default 14, and never earlier than `EVENTS_SINCE`), but they must not raise notifications or count as unread. The "table is empty" check in `collector.py` today does not cover a source that is added later.
- Validate at ingestion: item links must be `http` or `https`, since a feed-supplied `javascript:` link would become clickable in the UI.
- Admin API for sources: list, create, update, delete, enable and disable, test (a dry run that stores nothing), run now, and run history.

The randomised timing exists to spread load and stay under each source's limits, which is what prevents 429s and temporary bans. It does not get past real bot protection, and that is not its purpose (section 3).

### Phase 3 — Sources

Seed the `sources` table from the current `FEEDS` list with identical flags, mapping `ttl` and `min_interval` to `interval_seconds`. From then on the database is the only runtime source of truth; the keyword and regex constants stay in code. Create one source row per monitored Telegram chat from `TG_CHATS` and `TG_LEAK_CHATS` (if `TG_CHATS` is empty, keep a single "all joined chats" source). Give each source kind one connector class registered by `kind`, so a new kind means one new file.

Add the sources below, in this order of value. Where a key is required and missing from `backend/.env`, still build the connector and test it against recorded fixtures, seed the source disabled with status `auth_missing`, and add the variable to `backend/.env.example`.

| Source | What it adds | Access (confirm in the docs) |
|---|---|---|
| ransomware.live PRO API | ransomware victims by country | Free personal key. Replaces the legacy v2 endpoint the code calls today (one request a minute, personal use only, delayed data). Keep v2 as the fallback. |
| RansomLook | a second leak-site tracker to cross-check the first | Public API. |
| Have I Been Pwned `/api/v3/breaches` | breach catalogue with dates, record counts and data classes | No key, but a descriptive `User-Agent` is mandatory. Replaces the HIBP RSS feed. |
| CISA KEV | vulnerabilities exploited in the wild | JSON from the `cisagov/kev-data` GitHub mirror (cisa.gov returned 403 from this network). |
| abuse.ch URLhaus and ThreatFox | malware URLs and indicators | Free Auth-Key. Keep only hosts under `.uz .kz .kg .tj .tm`. |
| OpenPhish community feed | live phishing URLs | Plain-text feed. Keep regional domains and URLs that contain the brand names in `TG_EXTRA_KEYWORDS`. |
| LevelBlue (AlienVault) OTX | community threat pulses | Free key, `pulses/subscribed`. Keep pulses that name the region. |
| National CERTs of the five countries | official advisories | Add each one that publishes RSS or a stable news page. UZCERT is already in. |
| NVD API 2.0 | new critical CVEs | 5 requests per 30 seconds without a key, 50 with one. Seed it disabled; it is noisy. |
| Cloudflare Radar | outages and attack trends per country | Free API token. Optional. |

Rules for every connector:

- KEV, NVD and similar feeds have no country. Give sources and events a `scope` (`regional` or `global`). The default view stays regional, and global items appear only when the filter asks for them.
- Fill the structured fields whenever the source provides them: `countries`, `actor` (the ransomware group), `sector`, CVE id, record count. Otherwise derive `countries` and `sector` from the keyword maps that already exist in `feeds.py` and `dedup.py`.
- When ransomware.live and RansomLook report the same victim, keep one event and list both sources in `also_reported_by`. Do the same in the existing news de-duplication, so "reported by N sources" becomes a number the dashboard can use.
- Do not crawl .onion sites, forums behind logins, or the contents of pastes and dumps. The aggregators above already publish the metadata this platform needs.

### Phase 4 — Categories with CRUD and classification

`categories` holds a `slug`, names and descriptions in en / ru / uz, `severity` (info, low, medium, high, critical), a colour token, a Lucide icon name, `notify`, `retention_days` (empty means keep forever), sort order, enabled, `is_system`, and classification rules (keyword stems and regexes per language).

Seed fifteen: `ransomware`, `leak` (data breaches and leaks), `darkweb-sale` (access and databases offered for sale), `credentials` (stolen credentials and infostealers), `phishing`, `fraud` (online and financial fraud, account theft), `malware`, `vulnerability`, `ddos-outage`, `defacement` (defacement and hacktivism), `espionage` (APT and spyware), `law-enforcement` (arrests and takedowns), `advisory` (regulation and official warnings), `research` (threat reports), and `other` (the fallback, which cannot be deleted).

- Where an event came from becomes `events.channel` (`news`, `telegram_channel`, `telegram_group`, `api`). Old `ransomware` and `leak` rows keep their category. Old `news`, `telegram` and `tg_group` rows are classified by the rules and receive the matching channel.
- Classifier: the source's fixed category if it has one, otherwise the best-scoring rule match, otherwise `other`. Build the starting rules from `TOPIC_STEMS`, `TOPIC_PATTERNS` and `dedup._TOPICS`. Rules are data, so I can tune them from the admin page. Severity defaults to the category's, and a connector may raise it.
- Move `NOTIFY_CATEGORIES` and `EVENTS_RETENTION_KEEP` into the `notify` and `retention_days` columns, using the environment values once as the seed.
- Admin API: create, read, update, delete, reorder. Deleting a category moves its events to `other`; system categories can be disabled but not deleted. "Re-classify" runs the rules over stored events and shows a dry-run count first. A manual category change on an event sets `category_locked`, which re-classification respects.
- Event filters in the API and the UI: categories, severity, countries, channel, source, scope, language, date range and text search. All combine, and all are reflected in the URL so a view can be bookmarked.

### Phase 5 — English, Russian and Uzbek (Latin) for every event

- `event_translations (event_id, lang, title, summary, provider, status, error, translated_at)`, one row per language in `en`, `ru`, `uz`. The row for the source language is a copy (`provider = source`).
- Use the official Google Cloud Translation API behind a small `Translator` interface. The key goes in `GOOGLE_TRANSLATE_API_KEY`; the Basic edition accepts an API key, and target code `uz` gives Uzbek. Do not use `googletrans`-style libraries that scrape the public web endpoint, because they break without warning and get the server's address blocked. With no key configured, translations stay `pending` and the UI shows the original with a "not translated yet" mark.
- Translate asynchronously after insert, in batches, highest severity first, with retries. Cache by a hash of source language, target language and text, so repeated text is never paid for twice.
- Cost guard: the first 500,000 characters a month are free, then about $20 per million. Clip titles to 300 characters and summaries to 600, count the characters sent, stop at `TRANSLATE_MONTHLY_CHAR_LIMIT` (default 450,000), and show that state in admin.
- Do not machine-translate structured items. Build ransomware-victim, CVE and indicator titles from localised templates on the backend and send only free text to Google.
- Detect the real language of each item, since Telegram posts often differ from their channel's default. Convert Uzbek written in Cyrillic to Latin with a deterministic transliteration table at no API cost, and use the same table if Google ever returns Cyrillic for target `uz`. Normalise the apostrophe variants (`ʻ`, `ʼ`, `'`, `` ` ``) to the one the UI already uses, so search matches.
- Give each source a `translate` switch, so the text of a private Telegram group is not sent to a third party unless I allow it.
- API: `GET /api/events?lang=uz` returns the title and summary in that language with a fallback chain (requested, then `en`, then the original), together with the original text, the source language and a `translated` flag. Text search covers the original and every translation.
- Back-fill the existing events. Add an admin panel showing pending and failed counts, characters used this month, and "retry failed".

### Phase 6 — A clean interface: Light / Dark / System, uz / ru / en

The goal: someone who is not a security specialist understands every screen within a few seconds.

Before delegating any UI work, rewrite `docs/design-system.md` and `.claude/agents/ui-designer.md`. They still prescribe a dark-only, Uzbek-only design and would steer subagents back to it. Bring the other files in `.claude/agents/` in line with whatever this upgrade changes for them.

Theme

- Define semantic tokens as CSS variables (background, surface, border, text, muted text, primary, success, warning, danger, severity and category tones, chart palette) with light and dark values. Map them in `frontend/tailwind.config.ts` and replace the hard-coded `ink-*`, `slate-*` and `white/…` classes, starting in `frontend/components/ui` and working outwards. Change token values per theme instead of scattering `dark:` variants.
- Use `next-themes`: System by default, a three-way switch in the header and on the login page, no flash on load. Charts read their colours from the tokens and redraw when the theme changes. The print report stays light.
- Remove the decoration that competes with content: aurora blobs, grid background, radar, scramble and reveal text, magnetic and tilt effects, spotlight, sheen, animated gradients. Keep short fades and hover transitions. One accent colour. WCAG AA contrast in both themes, visible focus rings, full keyboard use.
- The same plain structure on every page: a title, one sentence saying what the page is for, the main action, then the content. Short helper text or tooltips for jargon. Empty states say what will appear here and why it is empty now. Navigation: Overview, Events, Checks, Admin (admins only).

Languages

- `next-intl` without locale-prefixed routes. This is a logged-in app, so the locale lives in a cookie and in `users.locale`; the first visit follows the browser and falls back to `uz`. Messages go in `frontend/messages/uz.json`, `ru.json` and `en.json`. Move every hard-coded string, including those in `frontend/lib/categories.ts`, `frontend/lib/modules.ts`, `frontend/components/shell/nav.ts`, the empty states, the report page, and the landing, login and register pages.
- Use ICU plurals (Russian needs them). Add a test that fails when the three files do not contain identical keys.
- Dates and numbers: `PROGRESS.md` records that `uz-UZ` formatting is broken in browsers. Keep the hand-written Uzbek month names and use `Intl` for ru and en only.
- Backend: return a stable error code with each message, and localise backend-generated text (errors, collector result labels, alert text) from a small catalogue chosen by `Accept-Language`. Search results that are already stored stay as they are.
- Event text follows the interface language, with a "show original" toggle. Category names come from the database.

### Phase 7 — Admin area and the Events page

Under `/dashboard/admin`, visible to admins only, built with the new tokens and translations:

- Sources: a table with name, kind, category, language, interval, status badge, last success, latency, items in the last 24 hours, 7-day uptime and next run. Filter by status, kind and enabled. Create, edit, enable or disable, delete (events keep the source name). "Test now" does a dry run and shows the HTTP status, latency, items parsed, how many pass the filters, and three sample titles. "Run now" fetches for real. Run history shows the error text. Export and import the source list as JSON, for moving to another machine. A summary strip counts sources by status, and a source that stays down for hours raises a notification for admins. For a Telegram source, the form offers a picker filled from the account's chat list.
- Admins type URLs that the server then fetches, so resolve the host first and refuse private, loopback and link-local addresses.
- Categories: the CRUD from Phase 4 with a rule editor, icon and colour pickers, and event counts.
- System: collector status, translation usage, the Telegram connection, and a short user list (change role, deactivate).

Rebuild the Events page on the new model: the filter bar from Phase 4, category and severity badges, country and source chips, translated text with the original one click away, and keywords taken from `matched_keywords`.

### Phase 8 — Dashboard with real, interactive statistics

Every number comes from SQL over stored rows. No sample or placeholder data anywhere. A widget with nothing to show gets an honest empty state.

Backend: flexible, filterable endpoints instead of one fixed overview. A time series (`bucket` = hour, day, week or month; `group_by` = category, country, source, channel or severity); top-N breakdowns by any of those and by actor and sector; a weekday-by-hour heatmap; KPIs with the change against the previous period; and source-health totals. Bucket in `Asia/Tashkent` through an `APP_TIMEZONE` setting, not in UTC as `backend/app/api/stats.py` does now. Add the indexes these queries need.

Frontend:

- One filter bar drives every widget: date range (24 hours, 7, 30 and 90 days, custom), categories, countries, channel, source, severity and scope. The state lives in the URL.
- Cross-filtering: clicking a bar, a slice or a legend entry adds that filter, and one click resets everything. Clicking through opens the Events page with the same filters.
- Widgets: KPI row; events over time, stacked by category, with zoom; category breakdown; countries; top sources; severity trend; heatmap; top ransomware groups; targeted sectors; latest critical events; source health.
- Every widget has tooltips, a table view and CSV export. I can show, hide and reorder widgets, and the layout is remembered.
- Use Apache ECharts through one thin wrapper component, tree-shaken and lazy-loaded. Never put more than eight colours in one chart: show the top categories and group the rest as "Other". Check the palette for contrast and colour-blind safety in both themes.
- Refresh every 60 seconds, paused while the tab is hidden.

### Phase 9 — Hardening and hand-over

- Rate-limit login, the check endpoints and manual refresh. Escape `%` and `_` in the events search the way `backend/app/api/search.py` already does for history. Remove the documented QA account and its password from the docs and the database, because the repository is public. Let the tests create their own users, and update `.claude/agents/qa-tester.md`, which logs in with that account.
- Tests: the classifier; the scheduler (jitter bounds, back-off, baseline run); health states; the translation pipeline with a fake provider; permissions on every admin route; the statistics queries; and migrations up and down on a scratch database. Frontend: `tsc --noEmit`, a production build, and the smoke script extended to light and dark in uz, ru and en on the main pages, at desktop width and at 360 px.
- Update `README.md`, `PROGRESS.md`, `docs/architecture.md`, `docs/tasks.md` and `backend/.env.example`.

## 6. Final report

When everything above is done, give me one report: what was built in each phase; what you verified and how; what you could not verify; every key I still have to obtain and which variable it goes in; how to apply the migrations on another machine and how to roll back; and every place where you deviated from this prompt, with the reason. Base each claim on something you ran, not on what the code should do.
