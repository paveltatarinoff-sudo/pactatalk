# PostHog analytics

Pinned commit: `d46ea5f779abb10afae4148433f7853396eea92f` (verified via `git rev-parse HEAD`).

## 1. Scope covered

Examined:
- All of `gcs45_bot/bot/`, `gcs45_bot/scripts/`, `gcs45_bot/pyproject.toml`, `gcs45_bot/fly.toml`, `gcs45_bot/CLAUDE.md` — grep for `posthog|PostHog|POSTHOG|capture|telemetry|analytics|i/v0/e` (all cases).
- All committed files under `gcs-landing-v2/` (root, `app/`, `public/`) — grep for `posthog|track|capture|identify|analytics`.
- Untracked-but-on-disk landing pieces: `gcs-landing-v2/.env.example`, `gcs-landing-v2/campaigns/validation-wave.sample.json`, `gcs-landing-v2/docs/validation-wave-operations.md`, `gcs-landing-v2/scripts/generate-campaign-links.mjs`.
- Stale `.next/` build artifacts and source maps under `gcs-landing-v2/.next/` — extracted original TypeScript via sourcesContent for: `lib/analytics/posthog.ts`, `lib/analytics/attribution.ts`, `components/landing-view-tracker.tsx`, `components/telegram-cta-link.tsx`, `app/providers.tsx`, `app/layout.tsx` (older variant), `app/survey-complete/page.tsx`, `app/api/analytics/feedback-submitted/route.ts`.
- Pre-captured inputs: `docs/audit/_data/posthog/insights-list.md`, `dashboards-list.md`, `TODO-for-specialist-5.md`, `docs/audit/_data/fly/secrets.txt`, `docs/audit/_data/landing/index.html`.
- Live PostHog UI (Chrome MCP, logged-in session, project 362123):
  - `data-management/events` page (visible event list).
  - JSON API: `/api/projects/362123/insights/?short_id={k6Qsu86L,P8hcNZK9,X97nyP22}` for funnel step composition.
  - JSON API: `/api/projects/362123/dashboards/1412086/` for dashboard tiles.
  - `/api/projects/362123/query/` (HogQL) for lifetime event counts, `$lib` source split, and `campaign` distribution.

Not examined / out of reach at this commit:
- Deployed bot source on Fly — not in repo. Bot Python at HEAD has zero PostHog code, yet PostHog receives bot-side events (`bot_start`, `session_created`, `invite_sent`, `partner_joined`, `session_started`, `session_completed`, `feedback_shown`, `mid_session_reached`) with `$lib=null` (server send). Where they originate is unknowable from this commit. → Coverage gap.
- Whether the live `pactatalk.app` deployment is the committed minimal `app/page.tsx` or the older instrumented variant whose source is preserved only in `.next/` source maps — inferable but not directly verified.

## 2. Inventory

### Code-side (current commit `d46ea5f`)

- `gcs45_bot/bot/**` — zero PostHog references. Only `structlog` `log.info(...)` events (e.g. `bot/handlers/session.py:365 session_created`, `:700 session_started`, `:504 session_joined`, `:995 session_ended`).
- `gcs-landing-v2/app/layout.tsx`, `gcs-landing-v2/app/page.tsx` — no PostHog, no `<Providers>`, no `LandingViewTracker`, no `TelegramCtaLink`. Static SSR landing.
- `gcs-landing-v2/.env.example:2-3` — `NEXT_PUBLIC_POSTHOG_KEY`, `NEXT_PUBLIC_POSTHOG_HOST` placeholders.
- `gcs-landing-v2/package.json` — no `posthog-js`, no `posthog-node` dependency.
- `gcs-landing-v2/scripts/generate-campaign-links.mjs` — UTM-link generator (`utm_source`/`utm_campaign`/`utm_content`); no event capture itself.
- `gcs-landing-v2/campaigns/validation-wave.sample.json` — 4 campaign definitions (`telegram/post_a/v1`, `telegram/post_a/v2`, `telegram/post_b/v1`, `founder_dm/dm_intro/v1`).
- `gcs-landing-v2/docs/validation-wave-operations.md` — runbook expecting `landing_view` + `click_to_telegram` to arrive with normalized `campaign` and to be read in `Validation / Full Funnel`.

### Code-side (only in stale `.next/` artifacts, NOT in HEAD or in git history)

- `gcs-landing-v2/lib/analytics/posthog.ts` — `initPostHog()` wrapper, `posthog.init(apiKey, {api_host, capture_pageview:false, capture_pageleave:false, persistence:"localStorage+cookie"})`.
- `gcs-landing-v2/lib/analytics/attribution.ts` — `ensureAttribution` reads `utm_source/utm_campaign/utm_content/lead_id`, normalizes, persists to `localStorage` (`pt_lead_id`, `pt_attribution`); `buildTelegramDeepLink` injects `?start=trk1_{source}_{campaign}_{variant}_{leadId}`.
- `gcs-landing-v2/components/landing-view-tracker.tsx` — on mount: `client.capture("landing_view", {source, campaign, message_variant, lead_id, landing_path})`, deduped per session via `sessionStorage`.
- `gcs-landing-v2/components/telegram-cta-link.tsx` — on click: `client.capture("click_to_telegram", {source, campaign, message_variant, lead_id, cta_location, destination:"telegram_bot"})`.
- `gcs-landing-v2/app/providers.tsx` — calls `initPostHog()` in `useEffect`.
- `gcs-landing-v2/app/survey-complete/page.tsx` — reads `session_id`, `role`, `source`, `campaign`, `message_variant`, `lead_id`, `initiator_distinct_id` from query string; POSTs to `/api/analytics/feedback-submitted`; dedupes via `sessionStorage`.
- `gcs-landing-v2/app/api/analytics/feedback-submitted/route.ts` — server `POST` forwards to `${POSTHOG_HOST}/i/v0/e/` with `event: "feedback_submitted"`, `distinct_id: initiator_distinct_id`, properties `session_id, source, campaign, message_variant, lead_id, submitted_by_role, survey_actor_role, feedback_type:"post_session_survey"`. Uses `POSTHOG_API_KEY||NEXT_PUBLIC_POSTHOG_KEY` and `POSTHOG_HOST||NEXT_PUBLIC_POSTHOG_HOST`.

### Server / deployment

- Fly bot has `POSTHOG_API_KEY` + `POSTHOG_HOST` set (`docs/audit/_data/fly/secrets.txt` lines visible by name/digest only).

### PostHog UI (project `362123`, US instance, sole member `paveltatarinoff@gmail.com`)

Insights (custom, all starred, all created ~Mar 2026):
- `Validation / Full Funnel` — https://us.posthog.com/project/362123/insights/k6Qsu86L
- `Validation / Session Funnel` — https://us.posthog.com/project/362123/insights/P8hcNZK9
- `Validation / Acquisition Funnel` — https://us.posthog.com/project/362123/insights/X97nyP22

Dashboards:
- `My App Dashboard` — https://us.posthog.com/project/362123/dashboard/1411691 (PostHog default template, pinned).
- `validation` (tag: "Validation Wave") — https://us.posthog.com/project/362123/dashboard/1412086, 3 tiles, each = one of the three Validation funnels above.

Distinct events ever sent (HogQL over `events`, lifetime):

| event | count | first_seen | last_seen |
|---|---|---|---|
| `landing_view` | 114 | 2026-03-30 | 2026-06-24 |
| `bot_start` | 18 | 2026-03-30 | 2026-06-24 |
| `click_to_telegram` | 10 | 2026-03-30 | 2026-06-24 |
| `session_created` | 8 | 2026-03-30 | 2026-06-24 |
| `invite_sent` | 8 | 2026-03-30 | 2026-06-24 |
| `session_completed` | 7 | 2026-03-30 | 2026-05-15 |
| `feedback_shown` | 7 | 2026-03-30 | 2026-05-15 |
| `$web_vitals` | 5 | 2026-03-30 | 2026-03-30 |
| `session_started` | 4 | 2026-03-30 | 2026-05-15 |
| `partner_joined` | 3 | 2026-03-30 | 2026-05-15 |
| `$create_alias` | 2 | 2026-03-30 | 2026-05-12 |
| `mid_session_reached` | 2 | 2026-05-12 | 2026-05-15 |
| `$autocapture` | 2 | 2026-03-30 | 2026-03-30 |
| `codex_debug_test` | 1 | 2026-03-30 | 2026-03-30 |

Note: `feedback_submitted` event (referenced in stale `route.ts`) is **absent** from PostHog. No production survey submission ever reached PostHog.

## 3. State of each piece

| Item | State | Evidence |
|------|-------|----------|
| Bot Python PostHog instrumentation in repo | broken / missing | `grep -rln posthog gcs45_bot/` → 0 hits at `d46ea5f` |
| Bot Python PostHog instrumentation deployed | partial / unknown source | PostHog received 18 `bot_start` with `$lib=null` and `telegram_user_id` properties (HogQL sample). Fly has `POSTHOG_API_KEY` + `POSTHOG_HOST` set (`_data/fly/secrets.txt`). Source not in repo → coverage gap. |
| Landing PostHog instrumentation in committed code | broken / missing | `gcs-landing-v2/app/page.tsx`, `app/layout.tsx` have no PostHog; `package.json` has no `posthog-js`; no `lib/` or `components/` dirs exist |
| Landing PostHog instrumentation in stale `.next/` build | recoverable artifact only | Sources extracted from `.next/server/chunks/ssr/lib_analytics_posthog_ts_6b80bb3d._.js.map` (source index 92) and `_c42bc653._.js.map` |
| Deployed landing serves PostHog code | partial | `docs/audit/_data/landing/index.html` references `LandingViewTracker` (`6b08238c08.js`); PostHog received 5 `landing_view` + 1 `click_to_telegram` with `$lib=web/1.364.1`. But last 4 `landing_view` (incl. today 11:07 UTC) have `$lib=null`, so the deployed bundle's posthog-js path is currently NOT firing for new pageviews. |
| `/api/analytics/feedback-submitted` route | partial / never fired in prod | Compiled at `.next/server/app/api/analytics/feedback-submitted/route.js`; source in sourcemap only; `feedback_submitted` event count in PostHog = 0 (not in `event_definitions` list nor in HogQL `events`). |
| `Validation / Full Funnel` (`k6Qsu86L`) | works structurally, empty data | API: steps `landing_view → click_to_telegram → bot_start → session_created → invite_sent → partner_joined → session_started → session_completed`. Step 1 gated on `properties.campaign in ['smoke-01']`. UI text last 7 days: "There are no matching events for this query". |
| `Validation / Session Funnel` (`P8hcNZK9`) | works structurally, ~empty | Steps `session_created → invite_sent → partner_joined → session_started → session_completed`. Step 1 gated on `campaign = 'smoke-01'`. |
| `Validation / Acquisition Funnel` (`X97nyP22`) | works structurally, ~empty | Steps `landing_view → click_to_telegram → bot_start`. Step 1 gated on `campaign = 'smoke-01'`. |
| `validation` dashboard (`1412086`) | works, three tiles wired | API: 3 tiles each pointing to the three funnels above. |
| `My App Dashboard` (`1411691`) | unused | "PostHog default template" per `_data/posthog/dashboards-list.md`; not opened by owner per insights inventory note. |
| Campaign `smoke-01` (funnel filter) | exists, single event | HogQL `landing_view` by `campaign`: `unknown=106, test-campaign=6, smoke-01=1, route_check=1`. Funnel will show ≤1 cohort entry. |
| Validation-wave campaign labels (`post_a`, `post_b`, `dm_intro`) | not present in data | None of the four `campaign` values in PostHog (`unknown`, `test-campaign`, `smoke-01`, `route_check`) matches the four config entries in `campaigns/validation-wave.sample.json`. Real validation-wave links were not used, or generator output was not posted. |
| UTM-link generator (`scripts/generate-campaign-links.mjs`) | works structurally, unused for production | Code path verified by reading; absence of generator-produced `campaign` values in PostHog confirms no live use. |
| Feedback flow (`feedback_submitted`) | broken end-to-end | Bot sends `feedback_shown` (7 lifetime) but `feedback_submitted` count = 0. Landing route exists only in stale build. |

## 4. Non-obvious decisions

- **All landing events have `lib/analytics/posthog.ts` configured with `capture_pageview:false, capture_pageleave:false`.** Source (sourcemap, `lib/analytics/posthog.ts`): `posthog.init(apiKey, {api_host, capture_pageview:false, capture_pageleave:false, persistence:"localStorage+cookie"})`. Rationale: send a custom `landing_view` (with attribution) instead of the default `$pageview`. Confirmed by absence of `$pageview` from event list.
- **Custom attribution model: `lead_id` generated client-side, persisted to `localStorage` (`pt_lead_id`, `pt_attribution`), forwarded to Telegram via `?start=trk1_{source}_{campaign}_{variant}_{leadId}` deep link.** Source: `lib/analytics/attribution.ts`. Rationale: stitch landing visitor → Telegram user via the `start` payload so bot-side `bot_start` can record matching `lead_id/source/campaign`. Evidence: `bot_start` properties include `source`, `campaign`, `message_variant`, `lead_id` (HogQL sample, line "campaign":"unknown" / "lead_id":"" — empty for direct entries).
- **Three funnels all gate the first step on `properties.campaign IN ['smoke-01']`.** API response for all three insights. Rationale unclear from code — looks like a smoke-test left in production. Result: funnels only ever see 1 cohort entry, which is why the Full Funnel UI says "There are no matching events for this query" on last-7-days.
- **Feedback submission goes through a Next.js server route (`/api/analytics/feedback-submitted`) that proxies to PostHog `/i/v0/e/` server-side**, instead of using posthog-js on the survey-complete page. Source: `app/api/analytics/feedback-submitted/route.ts` (recovered from sourcemap). Rationale unclear — likely to avoid leaking distinct_id correlation through the client, or to deduplicate via server. Either way, the route is not in committed code at HEAD.
- **Bot events arrive at PostHog with no `$lib`, no `$lib_version`.** HogQL aggregation: 18/18 `bot_start`, 8/8 `session_created`, 7/7 `session_completed`, etc. all have `$lib=null`. → bot is using the raw HTTP capture endpoint (`POST /i/v0/e/`) directly, not the `posthog` Python SDK. Rationale unclear; source not in repo.
- **The committed `gcs-landing-v2/app/page.tsx` is fundamentally a different (simpler, analytics-free) landing than the one whose `.next/` artifacts are on disk and whose code is currently deployed at `pactatalk.app`.** The instrumented landing files (`lib/analytics/*`, `components/*-tracker.tsx`, `app/providers.tsx`, `app/survey-complete/page.tsx`, `app/api/analytics/feedback-submitted/route.ts`) appear in **no git commit** (`git log --all -- gcs-landing-v2/lib/analytics/posthog.ts` → empty). Rationale unclear — work was done locally, deployed (likely to Vercel; `.vercel/` directory present), and never committed.

## 5. Risks & landmines

- **All three Validation funnels are filtered down to `campaign = "smoke-01"` (only 1 lifetime event matches).** Trigger: opening the validation dashboard to read campaign performance. Effect: dashboards show "no matching events"; the analytics ground-truth for the wave is invisible even though raw events (`landing_view: 113 non-smoke-01`) are flowing.
- **Validation-wave campaigns named in `campaigns/validation-wave.sample.json` (`post_a`, `post_b`, `dm_intro`) are not present in any captured PostHog event.** Effect: no live data exists for the four planned campaigns. Triggered when reading the funnels by campaign.
- **`feedback_submitted` event count = 0.** Trigger: opening any insight that depends on post-session feedback. Effect: feedback funnel collapses at the last hop; survey-complete page either never gets traffic, or its `/api/analytics/feedback-submitted` proxy is silently failing or absent from current deploy.
- **Critical analytics source (landing `lib/analytics/*` + `components/*-tracker.tsx` + survey-complete + feedback API) is not in git.** Trigger: re-deploy / fresh checkout / hand-off. Effect: the instrumentation that PostHog depends on cannot be reproduced from `main`; only `.next/` sourcemaps preserve it.
- **Recent (last 24 h) `landing_view` events have `$lib=null`, while older ones from March had `$lib=web/1.364.1`.** Effect: the posthog-js path may have stopped firing; events seen today must be coming from a server-side or rewritten path, otherwise the recent landing_view count would be 0. Confidence: medium; needs cross-check with deploy log [unverified].
- **Bot side: PostHog `POSTHOG_API_KEY`+`POSTHOG_HOST` are deployed (Fly secrets, names visible in `_data/fly/secrets.txt`), but no Python code at HEAD calls them.** Trigger: rotate keys, re-deploy from current `main`. Effect: bot stops sending `bot_start`, `session_created`, etc.; all three funnels go to zero.
- **Funnels have no explicit `dateRange` set** (API: `dateRange` field absent). Default is "last 7 days". Trigger: any owner expectation of lifetime conversion. Effect: a Mar-30 → May-15 cohort is invisible in the default view.
- **Sole PostHog member is `paveltatarinoff@gmail.com`.** Trigger: account loss. Effect: total analytics access loss; no other admin.
- **Single PostHog ongoing-incident banner observed at capture time** (`_data/posthog/insights-list.md`). Unrelated to project but timing-suspicious for fresh measurements [unverified].

## 6. Open questions for the owner

- Where does the deployed bot's PostHog code actually live? Is it on a different branch, an unpushed worktree, or hand-edited on Fly? (Nothing in `d46ea5f` sends events, yet 18 `bot_start` reached PostHog.)
- Same for the deployed landing: which revision is on Vercel? The committed `app/page.tsx` is static; the served HTML at `pactatalk.app` references `LandingViewTracker`. Was the instrumented variant ever in git?
- Why are the three Validation funnels gated on `campaign = "smoke-01"`? Was this a permanent filter, a leftover from a smoke test, or an unfinished change?
- `feedback_submitted` was designed end-to-end (landing route + bot `feedback_shown` exists) but never produced a single event in lifetime — is the survey URL out in the wild, or is the wave still pre-launch?
- The four validation-wave campaign names from `campaigns/validation-wave.sample.json` (`post_a`, `post_b`, `dm_intro`) never appear in PostHog data. Were any of those links posted publicly?
- Are recent `landing_view` events with `$lib=null` expected (server-side proxy), or symptomatic of posthog-js failing to load in the current deploy?
- → prompt content of facilitator_system: see specialist #1.
- → what we *should* be measuring: see specialist #8.
- → product interpretation of the metrics: see specialist #8.

## 7. Out-of-scope notes

- Commit `lib/analytics/*`, `components/*-tracker.tsx`, `app/providers.tsx`, `app/survey-complete/page.tsx`, `app/api/analytics/feedback-submitted/route.ts` before next deploy.
- Remove or parametrize the `campaign = "smoke-01"` filter on all three Validation funnels.
- Set explicit `dateRange` on the Validation funnels (current default = last 7 days masks all real data).
