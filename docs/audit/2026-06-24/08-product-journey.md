# Product layer / end-to-end journey

Pinned to commit `d46ea5f779abb10afae4148433f7853396eea92f` (per `docs/audit/2026-06-24/00-shared-header.md`).

## 1. Scope covered

Examined:

- Landing copy + structure: `gcs-landing-v2/app/page.tsx`, `gcs-landing-v2/app/layout.tsx`, `gcs-landing-v2/LANDING_CONTEXT.md`, and the SSR snapshot at `docs/audit/_data/landing/index.html` (63 164 chars, single-line HTML).
- Validation-wave hypothesis frame: `gcs-landing-v2/campaigns/validation-wave.sample.json`, `gcs-landing-v2/docs/validation-wave-operations.md`.
- PostHog product-side artefacts: `docs/audit/_data/posthog/insights-list.md` (3 starred funnels), `docs/audit/_data/posthog/dashboards-list.md`, `docs/audit/_data/posthog/TODO-for-specialist-5.md`. Funnels were NOT opened — only their names, IDs, and the campaign config that names the events they expect.
- Bot-side journey states: `gcs45_bot/CLAUDE.md`, `gcs45_bot/bot/handlers/start.py` (onboarding copy and deep-link `join_XXXXXX`), `gcs45_bot/bot/handlers/session.py` (create / join / end / resume / survey wiring), `gcs45_bot/bot/config.py` (`post_session_survey_url`).
- Real journey evidence: `tg/messages.html` (702 message blocks, 06.03→24.03.2026) and `tg/messages2.html` (322 blocks, 24.03→24.06.2026); owner's two-user test conversations with @PactaTalkBot. Counted command invocations and read first 20 + last 40 message texts.
- Fly side: `docs/audit/_data/fly/secrets.txt` (env-var presence), `docs/audit/_data/fly/recent-logs.txt` (last 100 lines, 24.06.2026).

Not examined / coverage gaps:

- Funnel step definitions and current conversion numbers in PostHog → owner of that scope is specialist #5 (per `TODO-for-specialist-5.md`). I report only what the funnels are named and what events the campaign doc says should power them.
- Visual / typography / hierarchy critique of the landing → specialist #9.
- Positioning, channels, audience fit → specialist #10.
- LLM prompt content of facilitator → specialist #1; FSM/handler internals → specialist #2; backend → specialist #3; landing code internals → specialist #4.
- I did not run the bot, did not query Postgres for `session_events`, and did not open PostHog in a browser.

## 2. Inventory

Journey artefacts that exist at SHA `d46ea5f`:

- **Landing (`pactatalk.app`, SSR by Next.js 16.1.6)** — single Russian page. Hero with H1 "Когда в паре пора обсудить важное…" (`docs/audit/_data/landing/index.html:title/h1`); three trust bullets; mock Telegram screenshot with avatars; pain block (3 "когда" cards); how-it-works (3 steps: open bot → speak in turns → get clarity); 13-item topics grid (Дети, Деньги, Дистанция, …); "Важно понимать" trust block; 5-question FAQ; final CTA. CTA buttons (3 instances at `gcs-landing-v2/app/page.tsx:195,242,494`) all hardcode `TELEGRAM_BOT_URL = "https://t.me/PactaTalkBot"` (`app/page.tsx:3`) — no UTM passthrough, no per-click event.
- **Hypothesis frame** — the validation wave (`gcs-landing-v2/campaigns/validation-wave.sample.json`) defines 4 placements: Telegram post A v1, A v2, B v1, Founder DM v1. Naming convention rules and link generator described in `gcs-landing-v2/docs/validation-wave-operations.md:11-46`.
- **PostHog dashboards/insights** — 3 funnels, all starred, all created ≈March 2026: `Validation / Full Funnel` (k6Qsu86L), `Validation / Session Funnel` (P8hcNZK9), `Validation / Acquisition Funnel` (X97nyP22) (`docs/audit/_data/posthog/insights-list.md:14-16`). One dashboard `validation` tagged "Validation Wave" (`docs/audit/_data/posthog/dashboards-list.md:9`).
- **Bot deep-link entry** — `cmd_start` in `gcs45_bot/bot/handlers/start.py:104-149` accepts `/start join_XXXXXX`; if no payload and user is new, branches to `INITIATOR_ONBOARDING_INTRO`; otherwise to main menu.
- **Onboarding copy (initiator)** — three sequential screens with inline-keyboard callbacks `onboarding:init:intro` → `:step2` → `:step3` (`bot/handlers/start.py:159-186`). Mentions EFT/Gottman/IBCT/CBT inside step three (`bot/handlers/start.py:48`).
- **Onboarding copy (partner)** — `PARTNER_ONBOARDING_INTRO` rendered when deep-link payload `join_XXXXXX` is present (`bot/handlers/start.py:136-139`); details screen on callback (`:200-208`).
- **Session creation** — `/new_session` or `session:new` callback → `SessionService.create_session(user_id)` → invite link `https://t.me/{bot}?start=join_{invite_code}` sent as a forwardable message (`bot/handlers/session.py:329-393`).
- **Join flow** — `/join`, `session:join`, `cb_join_confirm` (`bot/handlers/session.py:400-561`); on success emits log `session_joined` (`:504`).
- **Resume flow** — `cb_resume_choice` on three callbacks `resume_continue / resume_new_topic / resume_not_accurate` (`bot/handlers/session.py:703`); resume copy visible in `tg/messages2.html` block 257-258 and 266-267.
- **End / summary / survey** — `/end_session` or `session:end` callback (`bot/handlers/session.py:873-995`). Always sends "📋 Краткий итог разговора". If `settings.post_session_survey_url` is non-empty it adds an inline button leading to per-role URL built by `_build_post_session_survey_url` (`:277`). The env var `POST_SESSION_SURVEY_URL` is `Deployed` (`docs/audit/_data/fly/secrets.txt:11`).
- **Other journey commands** — `/status`, `/support`, `/progress`, `/privacy`, `/end_session`, `/new_session`, `/join`, all observed in `tg/messages2.html`.

## 3. State of each piece

| Item | State | Evidence |
|------|-------|----------|
| Landing page renders Russian copy + 3 CTAs to `t.me/PactaTalkBot` | works | `docs/audit/_data/landing/index.html` head/body extract; `gcs-landing-v2/app/page.tsx:3,195,242,494` |
| Landing carries UTM into Telegram | broken-by-design | CTA hrefs are the bare constant `TELEGRAM_BOT_URL` at `app/page.tsx:195,242,494`; no query-string forwarding. The validation-wave doc itself says only `landing_view` and `click_to_telegram` are checked client-side (`gcs-landing-v2/docs/validation-wave-operations.md:62`), not that UTM survives the t.me jump. |
| Landing fires `landing_view` / `click_to_telegram` events to PostHog | broken | Source tree under `gcs-landing-v2/` has no `posthog-js` dependency (`gcs-landing-v2/package.json:12-26` lists only `next`, `react`, `react-dom`), no `posthog` reference in any `app/*.tsx`, no `<Script>` injection in `app/layout.tsx`. SSR snapshot `docs/audit/_data/landing/index.html` contains zero occurrences of `posthog`, `capture`, `landing_view`, or `click_to_telegram`. A stale `.next/server/chunks/ssr/lib_analytics_posthog_ts_*.js` exists from a 2026-03-29 build, but no `lib/analytics/posthog.ts` source is tracked in git. |
| 3 Validation funnels exist in PostHog | partial | `docs/audit/_data/posthog/insights-list.md:14-16` lists IDs. Step definitions and current numbers not captured (deferred to specialist #5 per `TODO-for-specialist-5.md:8-12`). Because landing fires no events (row above), the `landing_view`-anchored funnels must currently read zeroes from the website — unverified, owner to confirm in PostHog. |
| Campaign-link generator (`npm run campaign:links`) | works | Script entry `gcs-landing-v2/package.json:10` + `scripts/generate-campaign-links.mjs` referenced by `gcs-landing-v2/docs/validation-wave-operations.md:36-46`. Not executed in this audit. |
| Bot deep-link `/start join_XXXXXX` lands on partner intro | works | `gcs45_bot/bot/handlers/start.py:133-140`; mirrored in real session shown by `tg/messages2.html` block 256 ("Перешли следующее сообщение партнёру"). |
| `/start` command on production reaches DB | partial / intermittent | Stack trace at `docs/audit/_data/fly/recent-logs.txt` lines covering 2026-06-24 09:48:43 originates at `bot/handlers/start.py:136` → `bot/repositories/user_repo.py:36` → SQLAlchemy. The subsequent log line at 09:48:54 shows the update was eventually handled (3 355 ms). Read-only: not investigated further (→ specialist #3). |
| Onboarding initiator 3-screen flow | works (untested in live) | Inline-keyboard callbacks defined `bot/handlers/start.py:159-186`. Not observed in `tg/messages2.html` (owner uses `/new_session`, skipping the intro flow). |
| Session create + invite | works | `tg/messages2.html` blocks 255-256, 271-272 show invite text appearing after `/start` and `/new_session`. Log line `session_created` at `docs/audit/_data/fly/recent-logs.txt` 2026-06-24 09:48:58. |
| Resume context across sessions | works | Real resume in production at `tg/messages2.html` blocks 257-258 and 266-267: "С возвращением! Я помню ваш прошлый разговор. Тема: Взаимные ожидания и знаки внимания …". Matches design in `gcs45_bot/CLAUDE.md` "6. Session continuity". |
| Post-session summary | partial | In 6 of the last `/end_session` observations in `tg/messages2.html` (blocks 253, 262, 269, 274, plus earlier), the summary body is the canned "Данных для итога разговора недостаточно. Итог уже сохранён в разделе «Мои итоги»." Bot does not appear to be generating a substantive summary in these sessions. |
| Post-session survey URL | works (configured) | `POST_SESSION_SURVEY_URL` is `Deployed` in Fly (`docs/audit/_data/fly/secrets.txt:11`); `bot/handlers/session.py:976-993` conditionally renders the button. Actual target URL and response capture were not opened. |
| `/progress` returns history of past sessions | works | `tg/messages2.html` block 264 shows three dated summaries returned. Each carries the same "недостаточно" body — degraded content, same underlying defect as the summary cell above. |
| `/support` ticketing | works | `tg/messages2.html` blocks 241-247: support category chosen, free-text accepted, bot responds "Спасибо, я передал это команде." |

## 4. Non-obvious decisions

- **Landing is shipped, analytics is not.** The owner authored the validation wave operations doc (`gcs-landing-v2/docs/validation-wave-operations.md`) and committed the funnel naming convention, but the source tree at SHA `d46ea5f` has no PostHog SDK and no event firing on the page. The stale `.next` artefact suggests a previous prototype was deleted and never re-added. Rationale unclear.
- **Three sequential funnels (Acquisition / Session / Full)** is a deliberate split per the inventory in `docs/audit/_data/posthog/insights-list.md:14-16`. The split is consistent with the journey decomposition landing → bot start → session completion, but the events that would power Session and Full live in the bot — and the bot also has no PostHog wiring (`grep -rni posthog gcs45_bot/` empty). Rationale: likely "build the dashboards first, instrument later"; not stated in code.
- **CTA goes to a single non-parameterised `t.me/PactaTalkBot` URL** in all three placements on the landing (`gcs-landing-v2/app/page.tsx:195,242,494`). The validation-wave doc treats UTM as a *landing-side* phenomenon (`docs/validation-wave-operations.md:11-30`) — UTMs are not propagated into the Telegram deep-link, so per-campaign attribution stops at the click on the landing. This is a deliberate scope cut, not a bug; the operations doc never claims otherwise.
- **Initiator onboarding is 3 screens, partner onboarding is 2** (`bot/handlers/start.py:23-80`). Initiator gets the framework citations (EFT/Gottman/IBCT/CBT); partner does not. Rationale unclear; consistent with "the inviting partner needs to feel they understand what they're inviting their partner into".
- **Resume default-on**. The bot proactively offers resume on `/start` and `/new_session` when a previous session exists (`tg/messages2.html` blocks 257, 266). The CLAUDE.md baseline (`gcs45_bot/CLAUDE.md:104-117`) explicitly states "resume-start не должен звучать как новый onboarding" — that decision is enforced at the prompt layer (→ specialist #1) and visible in the resume copy.
- **Telegram (Russian-language Telegram bot) is the only product surface.** Landing exists only to direct traffic into Telegram; there is no web app, no waitlist (waitlist explicitly removed per `LANDING_CONTEXT.md:63`), no email capture. Rationale stated: "Без регистрации на новой платформе" (`app/page.tsx:19`).
- **One owner, sole PostHog member, all funnels visited within the hour of the audit capture** (`docs/audit/_data/posthog/insights-list.md:10`). Reading: validation is in active-monitoring phase, not a passive setup.

→ prompt content of facilitator_system: see specialist #1.
→ landing visual/typography quality: see specialist #9.
→ positioning/channel fit: see specialist #10.
→ bot FSM and handler internals: see specialist #2; backend internals: see specialist #3.

## 5. Risks & landmines

- **Validation funnels likely show zero acquisition** because the landing fires no events. If the owner reads `Validation / Full Funnel` today and sees a step-1 drop-off, the conclusion "the message doesn't land" would be premature — the underlying signal is missing, not negative. Trigger: any decision off the current funnel numbers.
- **`/start` handler latency from the SQLAlchemy stack** captured at `docs/audit/_data/fly/recent-logs.txt` 2026-06-24 09:48:43-54: the `await repo.get(user.id)` call took ≈11 s before the update was marked handled. If a new partner clicks the invite during a Postgres hiccup, they may abandon before the welcome arrives. Trigger: cold start, DB slow query, or pool exhaustion. Diagnosis-only; root cause is for specialist #3.
- **"Данных для итога разговора недостаточно"** appears in every visible production end-of-session in `tg/messages2.html` (blocks 253, 262, 269, 274). The post-session moment is the only product surface that can show a user "this was worth it". A degraded summary at that moment removes the strongest retention signal the product can offer. Diagnosis-only; cause likely in summary-generation logic (→ specialist #1 / #2).
- **No per-link attribution beyond the click on the landing**. Even once landing-side events are wired, the moment a user lands inside Telegram, the campaign is lost (deep-link payload is fixed to `join_<code>`, owner does not encode campaign). Trigger: cross-channel comparison ("which Telegram post brought higher session-completion?") is currently unanswerable in PostHog regardless of how the funnels are configured.
- **Onboarding bypass via `/new_session`**: the only path that shows the 3-screen initiator onboarding is when the user is brand new and does NOT type `/new_session` first. In `tg/messages2.html` the owner repeatedly uses `/new_session` directly, never seeing the intro — a real new user who reads the landing CTA "Перейти в Telegram" lands on `/start` and DOES see it. The two paths produce different first impressions. Trigger: real users following the landing CTA vs. returning users.
- **Stale `.next` build artefact contains a `posthog.ts` chunk** that no longer exists in source (`gcs-landing-v2/.next/server/chunks/ssr/lib_analytics_posthog_ts_6b80bb3d._.js`, mtime 2026-03-29). If a future redeploy uses a different fresh build the discrepancy disappears, but right now the artefact suggests the page was once instrumented and that capability was lost. Trigger: someone trusts the build cache as evidence that analytics exists.
- **Working tree is dirty** at audit time (per shared header). Findings about "what is deployed" are based on `secrets.txt` + the SSR snapshot, not necessarily on what runs locally.

## 6. Open questions for the owner

1. Are the 3 Validation funnels currently showing any data? If yes — where do the `landing_view` / `click_to_telegram` events originate, since the source tree has none?
2. Was the previous `gcs-landing-v2/lib/analytics/posthog.ts` removed deliberately (privacy, refactor) or accidentally?
3. When you tested in `tg/messages2.html` and the summary said "Данных для итога разговора недостаточно", was that a fresh test session each time, or a resumed session with no genuine new content?
4. How is a real user expected to discover `/progress`, `/support`, `/privacy`? They are not surfaced in the onboarding screens that I read.
5. Is the post-session survey URL (`POST_SESSION_SURVEY_URL` secret) a Typeform / Google Form? Are survey responses currently being read back into PostHog or only stored externally?
6. Is the validation hypothesis "people will click the CTA" (acquisition) or "couples will complete a session" (engagement)? The funnel naming suggests both, but priority is unclear.

## 7. Out-of-scope notes

- Single fix idea worth flagging only: instrument `landing_view` and `click_to_telegram` in `app/page.tsx` before reading any funnel number. Without this the validation wave cannot answer its own question.
