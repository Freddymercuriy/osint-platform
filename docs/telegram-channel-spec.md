# Leadership Telegram channel: critical cyber events for Uzbekistan and Central Asia

You are the lead engineer on this repository, my OSINT and dark-web monitoring platform for Central Asia. The v2 upgrade is finished on the branch `feat/v2-upgrade`. Build the feature below on top of it, from start to finish, in one long run.

Decide things the way a senior engineer who has run alerting for executives would. A false alarm in front of leadership costs trust that is hard to win back. A flood of messages gets the channel muted. A missed critical event defeats the purpose. Every rule below serves one of those three.

If this text is not already in the repository, save it unchanged as `docs/telegram-channel-spec.md` in your first commit and re-read it at the start of every phase.

## 1. What already exists

Read `PROGRESS.md` (start with "▶️ DAVOM ETISH UCHUN" and the notes written after v2), `CLAUDE.md`, `docs/tasks.md`, `docs/architecture.md` and `docs/upgrade-v2-spec.md`, then the code named here. This feature builds on:

- Events with `severity`, `category_id`, `countries` (UZ, KZ, KG, TJ, TM), `sector`, `actor`, `scope`, `channel`, `also_reported_by`, `is_baseline` and `extra` (structured fields such as `victim`, `group`, `cve_id`, `pwn_count`): `backend/app/models/event.py`, filled in `services/events/pipeline.py::store_items`.
- 15 categories, each with a default severity (`models/category.py`, admin CRUD, `services/events/categories.py::reclassify`).
- Translations in en, ru and uz from the self-hosted NLLB service (`services/i18n/translator.py`, `worker.py`, table `event_translations`). Uzbek Cyrillic is derived from Uzbek Latin by the vendored jaybi engine (`services/i18n/text.py::uz_to_cyrillic`). `api/events.py::localize` chooses the display text. `services/i18n/templates.py::render_title` builds titles for structured items without translation. `core/i18n.py::t` is the backend catalogue, with `DISPLAY_LANGS = uz, uz-Cyrl, ru, en`.
- The collector loop with its advisory lock and housekeeping (`services/events/scheduler.py`), and admin alerts shown in the 🔔 bell (`models/alert.py`).
- Statistics SQL in `api/stats_v2.py`, bucketed in `APP_TIMEZONE` (Asia/Tashkent).
- The old `NOTIFY_TELEGRAM` path (`pipeline.notify_new`), which sends alerts to Saved Messages through the Telethon collection account. Leave it as it is. This feature replaces it and does not build on it.
- The platform is reachable only on the LAN (`0.0.0.0:3000` and `:8000`, no public address). Telegram cannot reach a webhook here, and leadership cannot open dashboard links from their phones.

## 2. The result I want

1. A private Telegram channel for leadership receives the most critical cyber-security events: Uzbekistan first, then Kazakhstan, Kyrgyzstan, Tajikistan and Turkmenistan.
2. Someone who is not a security specialist can read any post on a phone in about 20 seconds and know what happened, who is affected, how sure we are and what to do.
3. Instant alerts for critical items, a short morning brief on weekdays, and a weekly report with one chart.
4. Nothing reaches leadership by accident. Every event gets an explainable priority. Each channel starts in dry-run, then review, then automatic. Daily caps, quiet hours and a pause switch are built in.
5. An admin area for all of it: channel CRUD, queue and history, watchlist CRUD, scoring settings with a simulation, previews and health.
6. Each channel has its own language: Uzbek Latin, Uzbek Cyrillic, Russian or English.

"Leadership" here means the readers: managers who decide and delegate, read on their phones, and have no time for jargon.

## 3. Your permissions

You have my full permission to do everything this task needs inside the project without asking: create, edit and delete files; add dependencies; change the schema through migrations; rebuild and restart the project's containers; run servers, tests and scripts; commit and push to the working branch; and choose names, structure and design details yourself.

The limits, each with its reason:

- Work on a new branch `feat/telegram-channel` created from `feat/v2-upgrade`, which is GitHub's default branch. Never force-push and never merge. I merge after I have seen the channel working.
- Dump the database to `~/osint-backups/` before the first migration, and never drop the Postgres volume. Collected events cannot be fetched again.
- Use a dedicated bot through the Bot API. Never post with the Telethon account in `backend/data/`. It is the collection account: posting from it reveals which account watches the underground chats, and a ban would stop collection.
- The bot token lives only in `backend/.env` as `TG_BOT_TOKEN`. It must never appear in logs, the database, API responses, error texts or commits. Anyone holding it can post into the leadership channel, which turns it into a phishing tool aimed at leadership.
- Send real messages only to a channel marked as a test channel until I switch a channel out of dry-run myself. Every new channel starts in dry-run.
- Never post personal data (names of private individuals, e-mail addresses, phone numbers, passwords, document numbers), samples of leaked data, or links to .onion sites or to downloads of leaked files.
- No language model writes alert text. Every sentence in a post comes either from a template filled with stored fields, or from the event's own text and its stored translation. That way each statement can be traced to a source.
- Add no new services (Redis, Celery) and no bot framework. asyncio and PostgreSQL are enough, and the bot needs only about ten Bot API methods, which the project's existing `httpx` can call directly. The only new dependency allowed is `matplotlib`, for the weekly chart.

## 4. How to work

- Track the phases as a checklist in a new section of `docs/tasks.md` and the details in `PROGRESS.md`, in that file's language, with its honest "tekshirildi / tekshirilmadi" lists. Those two files plus the spec are the resume point if a session ends.
- Finish each phase completely before the next one. That means code, a migration with a working downgrade, tests, a real run against the local stack and docs, followed by a commit in the repo's `feat:` / `fix:` / `docs:` / `chore:` style and a push.
- Before a phase's first tool call, say in one line what you are starting. When it is finished, say in one or two lines what changed and what you verified, in the same message as your next tool call.
- Move from phase to phase without waiting for my approval. Do not end a turn with a summary of what comes next or an offer to continue. Stop only when nothing more can move without me. A missing bot token or channel is not such a case. Build and test against a fake Telegram (`httpx.MockTransport`, no new test dependency), keep dry-run working without a token, show the status "token missing" in admin, and carry on.
- Everything that works today must still work after every phase. Run `docker-compose exec backend pytest`, and in `frontend/` run `npm run typecheck`, `npm run test:i18n` and `node scripts/qa/smoke.js`. Extend the smoke script as pages are added.
- Use subagents for bounded, parallel work (the strings for one language, one admin page). Keep the schema and API contracts in the main session.
- Before coding against the Bot API, read the current reference at core.telegram.org/bots/api; it was at version 10.3 (24 August 2026) when this was written. The facts in section 5 were checked in November 2026 and may have moved.
- Where the repository contradicts this prompt, trust the repository and note the deviation in the final report.

## 5. Telegram facts to design around

Checked in November 2026; confirm each in the docs.

- `sendMessage` accepts 1–4096 characters of text after entity parsing. Photo captions accept 0–1024.
- Telegram asks bots to stay under about one message per second in a single chat and 20 messages a minute in one group. Treat a channel the same way. Over the limit the API answers 429 with `parameters.retry_after`.
- Formatting: use `parse_mode=HTML`. Supported tags are `b`, `i`, `u`, `s`, `a href`, `code`, `pre`, `blockquote`, `blockquote expandable` and `tg-spoiler`. Every other `<`, `>` and `&` must be escaped. The only named entities recognised are `&lt;`, `&gt;`, `&amp;` and `&quot;`.
- Useful send options: `link_preview_options={"is_disabled": true}`, `disable_notification`, `protect_content`, `reply_parameters`, and `reply_markup` with inline URL or callback buttons, which also work on channel posts.
- A bot can delete its channel posts only during their first 48 hours.
- `getUpdates` does not work while a webhook is set, and only one poller per bot can run at a time (409 Conflict). This platform has no public address, so use long polling.
- Bot API 10.1 and later add Rich Messages (`sendRichMessage`) with tables and headings. Do not use them. The docs describe no fallback for older Telegram apps and say nothing about channels, and leaders' Telegram apps may not be up to date.

## 6. The work

### Phase 0 — Foundations

- Create the branch and take the backup.
- Add settings to `core/config.py` and `backend/.env.example`, with Uzbek comments like the existing ones:
  - `TG_BOT_TOKEN`
  - `PUBLISHER_ENABLED` (default true; false switches the whole publisher off)
  - `PUBLISHER_TRANSLATION_WAIT_MINUTES` (default 10)
  - `PUBLIC_APP_URL` (empty by default; when set, posts get an "open in the platform" button)
- Write `services/publisher/bot.py`, a small async Bot API client on `httpx`. It needs `getMe`, `getWebhookInfo`, `getUpdates`, `getChat`, `getChatMember`, `sendMessage`, `sendPhoto`, `editMessageText`, `editMessageReplyMarkup`, `deleteMessage` and `answerCallbackQuery`.
- Read `ok`, `error_code`, `description` and `parameters` from the JSON body instead of calling `raise_for_status()`. httpx puts the request URL, and with it the token, into its own error text.
- Map errors to types the rest of the code can act on:
  - rate limited, with `retry_after`
  - unauthorised (bad token)
  - forbidden (bot removed or missing rights)
  - bad request, with the description (parse error, message too long, chat not found)
  - conflict (webhook set, or a second poller)
  - network
- Remove the token from every exception message before it is logged or stored. Test this: drive each error type through the client and assert that the token is absent from captured logs, stored errors and API responses.

### Phase 1 — Priority: deciding what is critical

Every event gets a score from 0 to 100, a band and the list of reasons behind it. One pure function computes all three, so the planner, the Events page and the simulation always agree.

**Schema.** One migration adds:
- `events.priority` (smallint, indexed), `events.priority_band`, `events.priority_reasons` (JSONB list of `{code, points}`)
- `sources.reliability`: `official`, `tracker`, `media`, `community` or `underground`
- a `watchlist` table
- a `publisher_settings` row holding the weights and thresholds

**Source reliability.** Seed it as follows, and make it editable in the source form:
- official: national CERTs, CISA KEV, NVD
- tracker: ransomware.live, RansomLook, HIBP, abuse.ch, OpenPhish, OTX, Cloudflare Radar
- media: RSS, Google News, NewsNow
- community: Telegram channels
- underground: the chats in `TG_LEAK_CHATS`, and chats whose fixed category is `leak` or `darkweb-sale`

**Starting weights.** Store them as data, editable from admin:

| Signal | Points |
|---|---|
| Category severity: critical / high / medium / low / info | 50 / 35 / 20 / 10 / 0 |
| Uzbekistan is among `countries` | +30 |
| Another Central Asian country, and not Uzbekistan | +15 |
| Sector: government, finance, telecom, energy or healthcare | +10 |
| Watchlist match: organisation, domain or brand | +40 |
| Watchlist match: product (an exploited flaw in software we use) | +25 |
| Watchlist match: person (impersonation, deepfake, or a leak claim naming them) | +30 |
| Official source | +10 |
| Each further distinct source in `also_reported_by`, up to two (a Google News copy of a site already counted does not count again) | +5 each |
| Record count ≥ 100 000 / ≥ 1 000 000 | +5 / +10 |
| Published more than 48 hours before it was collected | −20 |
| Only one source, which is underground | −10 |

**Bands.** Critical is 80 and above, high 60–79, medium 40–59, low below 40. A global-scope event without a watchlist match stays low however severe it is, because this channel is about the region.

**Sectors.** The sector dictionaries (`dedup._SECTORS` for the word stems, `geo.SECTOR_NAMES` for the names) have no energy or transport. Add both; they are critical infrastructure.

**Recomputing.** Recompute an event's priority whenever it changes: another source merges in through `pipeline._add_report`, its translations arrive, an admin changes its category, or re-classification runs. When the watchlist or the weights change, recompute the last 14 days.

**Watchlist CRUD (admin).**
- Fields: kind (organisation, domain, brand, product, person), name, aliases in Latin and Cyrillic, country, enabled, notes.
- Match whole words in the title, summary, translations, `matched_keywords`, `extra.victim` and `extra.domain`. Normalise apostrophes and Cyrillic/Latin the way the existing filters do.
- Seed organisations and brands from `TG_EXTRA_KEYWORDS`, leaving out place names such as `toshkent`.
- Persons are only the organisation's own senior officials and executives. A post states that a source mentions them and links the source, nothing more.

**Events page and API.** Show a priority badge with the reasons in a tooltip, and add a band filter. This is useful even without Telegram.

### Phase 2 — Data model for publishing

**`channel_destinations`** — one row per Telegram chat the platform posts to:
- Name, `chat_id`, cached chat title and type, and optional `topic_id` (for a group with topics).
- `lang` (`uz`, `uz-Cyrl`, `ru` or `en`), `mode` (`dry_run`, `review` or `auto`), `is_test`.
- What it covers: countries (default all five), `include_global`, category filter. Thresholds `instant_min_band` (default critical) and `brief_min_band` (default medium).
- Schedules: daily brief on/off, time and weekdays (default 08:30, Monday to Friday); weekly report on/off, day and time (default Monday 08:45).
- Quiet hours (default 22:00–07:00) and what happens in them; `max_instant_per_day` (default 6).
- Options: `protect_content`, `show_original`, `explain_terms`.
- State: enabled, `enabled_at`, a paused flag with its reason, and health fields (last success, last error, consecutive failures, when the bot's rights were last checked).

**`channel_posts`** — the outbox, and the audit trail of what leadership was told:
- Destination, and kind: `alert`, `group`, `daily`, `weekly`, `update`, `correction` or `test`.
- Event ids, and a `dedup_key` that is unique per destination (`alert:<event_id>`, `daily:2026-11-18`, …).
- Status: `waiting_translation`, `draft`, `awaiting_approval`, `queued`, `sending`, `sent`, `failed`, `skipped`, `rejected`, `expired` or `unknown`.
- Content: the rendered text frozen at render time, an optional edited text, buttons, a silent flag, and the post it replies to.
- Delivery: Telegram `message_id`, scheduled time, attempts, next attempt, last error (with the token removed) and skip reason.
- Who approved it and when (a web user or a Telegram reviewer); created and sent times.
- The event's band and source count at send time.
- Keep rows for at least a year.

**`bot_chats`** — chats the bot has been added to, or that wrote to it, filled from `my_chat_member` and `/start` updates, with the bot's current status and rights. This lets admins pick a channel without copying ids by hand.

**`reviewers`** — the Telegram user ids allowed to approve, linked to a platform user where possible.

**`publisher_state`** — the `getUpdates` offset and the global pause.

### Phase 3 — How a post looks

**Rules for every post**, because the readers are leaders on phones:
- Lead with the bottom line, in plain words. A term such as ransomware or phishing gets a short explanation the first time it appears (in an expandable quote when `explain_terms` is on).
- Always say how sure we are, based on the source's reliability. The labels are:
  - official source
  - confirmed by several sources
  - claimed by the attacker group, not confirmed
  - claim in an underground channel, not confirmed
  - media report

  Ransomware trackers only show that a group claims a victim, so their posts never say the victim "was hacked".
- No raw URLs in the text (links go on the title or in buttons) and no link previews. Emoji only as markers: the severity dot, the country flag, and one icon on a brief's heading.
- An instant alert stays under about 900 characters so it fits on one phone screen.
- Times are in Tashkent time. Numbers and dates follow the channel's language: use `templates._num` and the month names the frontend and `core/i18n.py` already use.
- In a public channel (one with a username), unconfirmed claims name the sector and country instead of the organisation, because repeating an extortion claim in public helps the extortion.

**Instant alert**, in Uzbek Latin; the other languages follow the same structure:

```
🔴 KRITIK · 🇺🇿 O'zbekiston · Moliya
<b>Akira guruhi "Example Bank" tashkilotiga hujum qilganini da'vo qilmoqda</b>

17-noyabr, 14:05 (Toshkent). Guruh bankni o'z saytidagi qurbonlar ro'yxatiga qo'shdi.

<b>Ishonchlilik:</b> guruh da'vosi, tasdiqlanmagan · 2 manba: ransomware.live, RansomLook
<b>Nima uchun muhim:</b> O'zbekistondagi moliya tashkiloti.
<b>Tavsiya:</b> bank bilan bog'lanib holatni aniqlash; mijozlarni soxta xabar va qo'ng'iroqlardan ogohlantirish.

#UZ #ransomware #finance
[ Manbani ochish ]
```

- **Header:** severity label, flag and country, sector. Labels: KRITIK / YUQORI / O'RTA in Uzbek, КРИТИЧНО / ВЫСОКИЙ / СРЕДНИЙ in Russian, CRITICAL / HIGH / MEDIUM in English.
- **Title:** for structured items (ransomware victim, breach, exploited vulnerability, phishing host, outage), use plain-language templates in all three catalogue languages, built on the fields `render_title` already reads. Otherwise use the translated title.
- **Body:** the first one or two sentences of the cleaned, translated summary. The cleaner removes URLs, @mentions, hashtags, "subscribe" lines, runs of emoji and leftover HTML, and cuts at a sentence boundary. Telegram sources need this most.
- **"Why it matters":** built only from the priority reasons, leaving out any the confidence line already states.
- **"What to do":** a recommended action per category. Add `explain_*` and `action_*` (uz, ru, en) to `categories`, seed sensible text for all 15, and make them editable in the category form. Uzbek Cyrillic is derived the same way as everywhere else.
- **Repeats:** if an event about the same organisation was posted in the last 90 days, say so with its date. Leak claims are often re-posts of old data.
- **Original text:** translated items can carry the original in a collapsed `<blockquote expandable>` (`show_original`), because NLLB output sometimes drops a detail.
- **Hashtags:** country code, category slug and sector, in ASCII only (`#UZ #ransomware #finance`), so they stay clickable and searchable whatever the channel's language.
- **Buttons:** "Manbani ochish" with the source URL. Add "Platformada ochish" only when `PUBLIC_APP_URL` is set.

**Grouped alert.** When three or more qualifying events from the same attacker group, or of the same category in the same country, arrive within ten minutes, send one post that lists them. A ransomware group often lists many victims at once.

**Daily brief** (weekdays, default 08:30), for example:

```
📋 <b>Kunlik brifing · 18-noyabr, chorshanba</b>
O'zbekiston va Markaziy Osiyo · 17-noyabr 08:30 dan beri

<b>Asosiy xulosa:</b> O'zbekistonga oid 1 ta kritik hodisa; mintaqada jami 6 ta muhim hodisa.
🔴 1 · 🟠 2 · 🟡 3   (oldingi davr: 0 · 1 · 4)

🇺🇿 <b>O'zbekiston</b>
1. 🔴 <a href="…">Akira guruhi "Example Bank" tashkilotiga hujum qilganini da'vo qilmoqda</a>
2. 🟡 <a href="…">…</a>

🌏 <b>Markaziy Osiyo</b>
3. 🇰🇿 🟠 <a href="…">…</a>

<b>Tavsiyalar:</b> …
```

- The brief covers everything since the previous daily brief, so Monday's covers the weekend.
- At most about 10 items: Uzbekistan first, then the other countries in a fixed order, then watchlist matches from elsewhere. Each item is one line.
- Put recommended actions for the top items at the end.
- When nothing qualified, send a short all-clear that says how many sources were checked and how many are working. Silence should never look like a broken system.
- When many sources are down, say so. Reduced coverage is part of the message.

**Weekly report** (default Monday 08:45):
- First one PNG chart, sent with `sendPhoto` and a short caption: events per day for the last seven days, stacked by country, medium band and above.
- Then a text message:
  - the bottom line
  - comparison with the previous week by country and by category
  - the three most important events
  - the most active attacker groups and most targeted sectors in the region
  - recommended actions
- Draw the chart with matplotlib's Agg backend and its bundled DejaVu Sans font, using the light-theme chart colours from the frontend tokens.
- Use a solid white background, because a transparent image looks broken in Telegram's dark theme, and put no emoji in the image.
- Check that Uzbek Latin, Uzbek Cyrillic and Russian labels render without "Glyph missing" warnings.

**Language.**
- Build each post from text fields in the channel's language, then assemble the HTML.
- For Uzbek Cyrillic, run `uz_to_cyrillic` on the text fields before assembly, never on the finished HTML, so tags, links, hashtags and CVE ids stay intact.
- Wait up to `PUBLISHER_TRANSLATION_WAIT_MINUTES` for the translation into the channel's language (`event_translations.status = done`). After that, send the original text with a short note. Titles built from templates need no translation.

**Escaping and limits.** Escape all text taken from events. Enforce the 4096-character and 1024-character limits on the rendered result by dropping whole items or sentences, never by cutting inside a tag or an entity.

### Phase 4 — Planner, sender and approval

Run one publisher task inside the API process, containing the planner, the sender and the updates poller, under its own advisory lock key (not `scheduler.LOCK_KEY`). Dry-run needs no token.

**Planner** (every 30 seconds):
- Candidates are events that:
  - are not baseline
  - were first collected after the destination's `enabled_at` (enabling a channel never floods it with the backlog), and within the last 24 hours
  - are in a band at or above the destination's threshold
  - match its countries and categories (watchlist matches pass the country filter)
- Insert each post with its `dedup_key`. The unique key makes restarts and double ticks harmless.
- Quiet hours: by default only critical events in Uzbekistan go out with sound, other critical events go out silently, and high events wait for the morning brief.
- Daily cap: past `max_instant_per_day`, alerts move to the next brief, which says how many were moved.
- Update instead of re-posting:
  - Another source joins an event posted within the last 48 hours: edit the post's confidence line.
  - The band rises to critical: reply to the original post with a short update.
  - An admin marks the event wrong or moves it to `other`: reply with a correction, which goes through approval in review mode.
  - Never silently delete a post leadership may already have read.
- Approval: in `review` mode every post waits for approval. In `auto` mode, a post whose only source is underground still waits.
- Stale posts:
  - An alert not sent within 6 hours of collection becomes `expired`; the next brief covers it.
  - A brief missed because the computer was off is still sent if the platform comes back within 3 hours of its time; otherwise it is `skipped`, with the reason.
- Dry-run: a `dry_run` channel renders and stores every post exactly as it would be sent, and never calls Telegram.

**Sender** (every 5 seconds):
- Send `queued` posts in priority order, at most one per 1.1 seconds and 18 per minute per chat.
- Errors:
  - 429: wait `retry_after`.
  - 400 parse error: send once more as plain text, and record it as a bug to fix.
  - 403 or chat not found: stop sending to that destination, mark it down and raise an `AdminAlert`.
  - 401: stop sending everywhere and raise an `AdminAlert`.
  - Network error: back off exponentially with jitter.
  - Add the alert kinds `channel_down`, `bot_token_invalid`, `post_unknown` and `webhook_conflict`, and show them in the bell the way `source_down` is shown.
- Set the status to `sending` before the call, and to `sent` with the `message_id` after it. On start-up, any post still in `sending` becomes `unknown` and raises an admin alert asking to check the channel, then resend or mark it sent. A duplicate in front of leadership is worse than a gap the admin page shows.
- Check the `entities` in Telegram's response. They show how Telegram parsed the formatting, which catches a template whose bold text or links silently broke.

**Updates poller** (long-polling `getUpdates` with `allowed_updates` set to `my_chat_member`, `callback_query` and `message`, with the offset kept in the database):
- On start, call `getWebhookInfo`. If a webhook is set, do not delete it, because another system may own this bot. Pause instead, with an admin alert asking for a dedicated bot.
- `my_chat_member` updates fill `bot_chats`. When the bot is removed from a destination or loses its rights there, mark the destination down at once.
- `/start` in a private chat replies with the person's Telegram id and explains how to become a reviewer.
- **Review chat.** When a post needs approval and a review chat is set, the bot sends the draft there with ✅ Send, 🔕 Send silently and ❌ Reject buttons:
  - Accept a press only from a registered reviewer, and answer anyone else with "not allowed".
  - Keep `callback_data` under 64 bytes (for example `ap:<post_id>`), and make repeated presses harmless.
  - After the decision, edit the draft to show who decided and when, and remove the buttons.
  - Text edits happen in the web admin (LAN only).
- Drafts expire after 6 hours for alerts, or at the next brief.

### Phase 5 — Admin area

Add a "Kanal" tab (Telegram channel publishing) next to Sources, Categories and System in `frontend/app/dashboard/admin/layout.tsx`. Write strings in `uz.json`, `ru.json` and `en.json`, regenerate `uz-Cyrl.json` with `backend/scripts/gen_uz_cyrl_messages.py`, and use the theme tokens. Name new backend catalogue keys with a `pub_` prefix, since `tg_` already belongs to the Telethon features.

- **Overview:** bot status (from `getMe`, or token missing, or webhook conflict), the pause switch with its reason, each destination's mode and health, today's counts by status, and the approval queue.
- **Destinations:**
  - CRUD, with the chat picked from `bot_chats`.
  - The bot's actual rights from `getChatMember`, naming any that are missing. It needs post messages, edit messages and delete messages, and nothing more.
  - A "Send test message" button.
  - Mode changes ask for confirmation. Switching to `auto` first shows how many posts the last 7 days would have produced.
- **Queue and history:**
  - Filters by destination, status, kind and date; open the rendered post.
  - Actions: approve, reject, edit before approval, resend, mark sent.
  - A "View in Telegram" link (`https://t.me/c/<id without -100>/<message_id>` for private channels).
- **Watchlist:** CRUD, plus a "test this entry" button that shows which events from the last 30 days it would match.
- **Scoring:** weights and band thresholds, plus a simulation. It replays the last 14 or 30 days through the current or edited settings and shows, per day and per destination, how many posts would go out as instant alerts, how many would go into briefs and how many would be skipped, with the list, before anything is saved.
- **Preview:** pick an event and a language and see the post as Telegram would show it. Render it with a small parser that allows only the tags listed in section 5 and outputs React elements. Never use `dangerouslySetInnerHTML`, because post text comes from external feeds.
- **Events page (admins):** a "Send to channel" action on any event. It creates a post for a chosen destination and respects that destination's mode.

### Phase 6 — Calibration and go-live

- Replay the last 14 days in dry-run with the starting weights. Report per day how many instant alerts and brief items the leadership channel would get. A normal day should give a few instant alerts at most. If it gives many more, propose new thresholds and show the numbers both ways; do not tune silently.
- Once I register a test channel (`is_test`), send every post type in all four languages: alert, grouped alert, update, correction, daily brief, all-clear, and weekly report with its chart. Check the API responses (`entities`, lengths, buttons), then leave the posts there for me to look at on a phone and on desktop, in light and dark themes.
- Write `docs/telegram-channel.md` in Uzbek, covering:
  - creating the bot in @BotFather
  - creating the private channel
  - adding the bot as an administrator with only "Post messages", "Edit messages" and "Delete messages"
  - picking the channel in admin, and adding reviewers
  - the dry-run → review → auto path, and pausing
  - what each post status means
  - rotating the token if it leaks
  - reviewing the channel's member list when people leave the organisation

### Phase 7 — Hardening and hand-over

- Backend tests:
  - scoring rules and bands; watchlist matching (Latin, Cyrillic, apostrophes); recomputation
  - the renderer: escaping text such as `AT&T <b>`, length limits in all four languages, Cyrillic conversion leaving tags, URLs, hashtags and CVE ids untouched, and the summary cleaner
  - the planner: baseline and backlog excluded, grouping, quiet hours, the daily cap, translation wait and fallback, approval rules, expiry, catch-up, updates and corrections, and idempotency across a restart
  - the sender: pacing, 429, the plain-text fallback for parse errors, 403 and 401, `sending` becoming `unknown`
  - the poller: webhook conflict, `my_chat_member`, the reviewer check, repeated presses
  - briefs: Tashkent windows, Monday's weekend window, the all-clear, reduced coverage
  - chart glyphs, admin permissions on every new route, migrations up and down on a scratch database, and token redaction
- Frontend: typecheck, `test:i18n`, a production build, and the smoke script extended to the new pages at desktop width and at 360 px.
- Update `README.md`, `PROGRESS.md`, `docs/architecture.md`, `docs/tasks.md` and `backend/.env.example`. Mark `NOTIFY_TELEGRAM` as legacy in the docs.
- Write down the rollback. Before checking out `feat/v2-upgrade` again, run `docker-compose exec backend python scripts/migrate.py downgrade 0016_telegram_global`. `scripts/start.sh` upgrades to whatever head it finds, and the v2 code does not know the new revisions.

## 7. Final report

When everything above is done, give me one report:
- what was built in each phase
- what you verified and how, and what you could not verify
- the calibration numbers: expected instant alerts and brief items per day
- the exact steps I still have to take (bot, channel, test channel, reviewers) and the setting each one fills
- how to roll back
- every place where you deviated from this prompt, with the reason

Base each claim on something you ran, not on what the code should do.
