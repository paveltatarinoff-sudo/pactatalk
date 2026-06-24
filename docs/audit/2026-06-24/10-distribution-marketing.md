# Distribution & marketing surface

Pinned commit: `d46ea5f779abb10afae4148433f7853396eea92f` (per `docs/audit/2026-06-24/00-shared-header.md:4`).

## 1. Scope covered

Examined:
- `gcs-landing-v2/campaigns/` — directory listing and full content of `validation-wave.sample.json`.
- `gcs-landing-v2/docs/validation-wave-operations.md` — full runbook.
- `gcs-landing-v2/scripts/generate-campaign-links.mjs` — UTM link generator referenced by the runbook.
- `gcs-landing-v2/LANDING_CONTEXT.md` and `gcs-landing-v2/README.md` — positioning and operator notes.
- `gcs-landing-v2/app/layout.tsx`, `app/page.tsx` (header), `app/opengraph-image.tsx`, `app/twitter-image.tsx` — metadata, OG/Twitter cards, hero copy, audience signals.
- `docs/audit/_data/landing/index.html` — 70 KB SSR snapshot of `https://pactatalk.app` (the deployed copy that real visitors see).
- `docs/audit/_data/posthog/insights-list.md`, `dashboards-list.md` — to map UTM names to PostHog funnels that read them.
- `git log` + `git status` for the landing tree to see what is tracked vs. untracked, and what landing commits exist.

Not examined (out of scope or no artifact in scope):
- Actual posts / DMs that were sent (text bodies of `post_a v1`, `post_a v2`, `post_b v1`, `dm_intro v1`) — no `.md`/`.txt` copy of message bodies exists in `campaigns/`; only the metadata JSON.
- Real PostHog tile contents and per-campaign counts — that is specialist #5's territory (see `docs/audit/_data/posthog/TODO-for-specialist-5.md`).
- Sender-side tooling on Telegram (channels, account used, contact lists) — no artifact in repo.
- Site UX/layout quality, conversion design → handoff to specialist #9.
- Whether the positioning matches the underlying product hypothesis → handoff to specialist #8.

## 2. Inventory

Distribution-related artifacts on disk at `d46ea5f`:

- `gcs-landing-v2/campaigns/validation-wave.sample.json` (`validation-wave.sample.json:1-33`) — single sample config file holding 4 planned tracking links. Schema: top-level `baseUrl` + `campaigns[]`; each item has `name`, `source`, `campaign`, `messageVariant`, `notes`. Untracked file (`git status` shows `?? gcs-landing-v2/campaigns/`).
- `gcs-landing-v2/scripts/generate-campaign-links.mjs` (`generate-campaign-links.mjs:1-245`) — Node CLI that normalizes `source/campaign/content` tokens to lowercase-hyphenated form and emits final `https://pactatalk.app/?utm_source=…&utm_campaign=…&utm_content=…` URLs. Wired into `package.json` as `npm run campaign:links`. Untracked.
- `gcs-landing-v2/docs/validation-wave-operations.md` (`validation-wave-operations.md:1-77`) — operator runbook: naming convention, generator usage, launch workflow, PostHog reading notes. Untracked.
- `gcs-landing-v2/package.json` (modified, `package.json:10`) — adds `"campaign:links": "node scripts/generate-campaign-links.mjs"`. Not committed.
- `gcs-landing-v2/README.md` (modified, `README.md:43-51`) — adds a "Campaign Links" section pointing to the runbook. Not committed.
- `gcs-landing-v2/LANDING_CONTEXT.md` (`LANDING_CONTEXT.md:8-10,39`) — positioning anchor: "PACTA — AI", domain `pactatalk.app`, CTA target `https://t.me/PactaTalkBot`.
- `gcs-landing-v2/app/layout.tsx` (`layout.tsx:17-39`) — page title, description, OG/Twitter metadata, Russian locale (`locale: "ru_RU"`).
- `gcs-landing-v2/app/opengraph-image.tsx`, `app/twitter-image.tsx` — generated social cards.
- Deployed landing surface evidence (`docs/audit/_data/landing/index.html`):
  - `lang="ru"` (`index.html:1`).
  - Three CTA placements with PostHog props: `ctaLocation:"header_button"`, `ctaLocation:"hero_primary"`, `ctaLocation:"footer_primary"` (visible in the streamed RSC payload).
  - Two tracking components referenced in the SSR HTML: `LandingViewTracker` and `TelegramCtaLink` (in the `__next_f` payload near the bottom of `index.html`).
- PostHog read-side (`docs/audit/_data/posthog/insights-list.md:13-19`) — three custom funnels named `Validation / Full Funnel`, `Validation / Session Funnel`, `Validation / Acquisition Funnel`. Dashboard `validation` (id 1412086) carries the `Validation Wave` tag (`dashboards-list.md`).

Channels and audiences named anywhere in scope:
- Channels named in the sample config (`validation-wave.sample.json:5-31`): `telegram` (posts A and B) and `founder_dm` (DM intro).
- Audience signal in the runbook (`validation-wave-operations.md:16,18`): "telegram", "founder-dm", "partner-community" given as `utm_source` examples; no demographic, persona, or geo definition anywhere.
- Audience signal in landing copy (`page.tsx:33-47`, `app/layout.tsx:17-19`): Russian-speaking couples discussing a fixed list of topics (Дети, Деньги, Дистанция, Доверие, Будущее, Накопленные обиды, Ревность, Измена, Секс и близость, Родители, Быт, Поддержка, Границы).
- CTA target everywhere: `https://t.me/PactaTalkBot` (`page.tsx:3`, `index.html` hero/header/footer, `LANDING_CONTEXT.md:39`).

→ Positioning vs. underlying product hypothesis fit: see specialist #8.
→ Whether the landing reads well / converts well: see specialist #9.

## 3. State of each piece

| Item | State | Evidence |
|------|-------|----------|
| `campaigns/validation-wave.sample.json` | works (parseable; matches script's schema) | `validation-wave.sample.json:1-33`; matches `readField` keys in `generate-campaign-links.mjs:97-122` |
| `scripts/generate-campaign-links.mjs` | works (self-contained Node script, normalization + URL build covered) | `generate-campaign-links.mjs:55-163`; `package.json:10` wires `npm run campaign:links` |
| `docs/validation-wave-operations.md` runbook | partial — accurate to script, but references unverified PostHog events `landing_view`, `click_to_telegram` | `validation-wave-operations.md:62,68`; events not grep-able in tracked `gcs-landing-v2/app/` source (`grep -rn "landing_view\|click_to_telegram" gcs-landing-v2/app/` → no results); event capture lives in `LandingViewTracker`/`TelegramCtaLink` referenced only in deployed SSR HTML (`docs/audit/_data/landing/index.html`), not in committed source tree |
| `package.json` script entry `campaign:links` | works locally; uncommitted | `git diff gcs-landing-v2/package.json` shows the line as unstaged modification |
| `README.md` "Campaign Links" section | works as docs; uncommitted | `git diff gcs-landing-v2/README.md` shows the appended block as unstaged |
| Campaign config file under `campaigns/` | uncommitted (entire folder untracked) | `git status` reports `?? gcs-landing-v2/campaigns/`, `?? gcs-landing-v2/docs/`, `?? gcs-landing-v2/scripts/` |
| OG card / Twitter card (`og:image`, `twitter:image`) | works (1200x630 PNG referenced; `og:image:alt`, `og:image:width`, `og:image:height` present) | `docs/audit/_data/landing/index.html:1` `<meta property="og:image" content="https://pactatalk.app/landing/og-card.png"/>`; `app/layout.tsx:26-33` |
| Canonical URL + `metadataBase` | works | `docs/audit/_data/landing/index.html:1` `<link rel="canonical" href="https://pactatalk.app"/>`; `app/layout.tsx:16` `metadataBase` falls back to `https://pactatalk.app` |
| Hero CTA, header CTA, footer CTA → t.me/PactaTalkBot | works on deployed landing; tracked with `ctaLocation` PostHog property | `docs/audit/_data/landing/index.html` (grep `ctaLocation` → 3 hits: `header_button`, `hero_primary`, `footer_primary`); local source (`app/page.tsx:3`) only declares the URL constant — does not emit the `TelegramCtaLink` component |
| `LandingViewTracker` / `TelegramCtaLink` components | unknown locally — not in committed source | `grep -rn "TelegramCtaLink\|LandingViewTracker" gcs-landing-v2` returns no source matches; components appear only in the deployed SSR payload at `docs/audit/_data/landing/index.html`. Coverage gap: components live somewhere outside the audited tree or in an uncommitted change |
| PostHog "Validation Wave" dashboard + 3 Validation funnels | exists, contents unread here | `docs/audit/_data/posthog/insights-list.md:13-19`, `dashboards-list.md` — counts/breakdowns deferred to specialist #5 |
| Locale targeting (Russian) | works | `app/layout.tsx:25` `locale: "ru_RU"`; `<html lang="ru">` in `docs/audit/_data/landing/index.html:1`; all hero/body copy in Russian (`app/page.tsx:9-87`) |

## 4. Non-obvious decisions

- **Self-service link generator instead of a PostHog/Plausible-managed campaign UI.** The owner chose a local Node script (`generate-campaign-links.mjs`) that normalizes tokens before they hit the URL. Rationale stated in `validation-wave-operations.md:7-9,30`: "The operational risk now is inconsistent naming or manually assembled links… normalizes it to hyphenated tokens so PostHog filters stay predictable." Reasonable for a one-person validation phase.
- **Two-axis split between `utm_campaign` (placement/hypothesis) and `utm_content` (message variant).** Documented in `validation-wave-operations.md:14-27`. This is the convention specialist #5's funnels assume when they "compare campaigns" with breakdown by `campaign` (`validation-wave-operations.md:67-69`). Non-obvious because most teams overload `utm_campaign` for both axes.
- **`utm_medium` and `utm_term` declared optional in the generator but never used in the sample config.** `generate-campaign-links.mjs:120-121,145-151` accepts them; `validation-wave.sample.json` does not set them; the runbook (`validation-wave-operations.md:13-21`) recommends only `source/campaign/content`. Decision: keep the dimensional space minimal during the validation wave.
- **`baseUrl` defaults to `https://pactatalk.app/` (trailing slash) in both script and sample config** (`generate-campaign-links.mjs:7`, `validation-wave.sample.json:2`). All emitted links carry that exact origin; no preview/staging surface is tracked.
- **All distribution tooling is untracked.** `campaigns/`, `docs/`, `scripts/` are in `git status` as untracked, and the supporting `package.json`/`README.md` edits are unstaged. Rationale unclear — either work-in-progress about to be committed, or owner is keeping the validation runbook local. Either way, the validation wave operationally depends on files that are not in the repo's history.
- **Only one named DM channel, no email, no paid, no SEO.** The sample config enumerates `telegram` posts and one `founder_dm`; no other distribution surface (email blast, paid social, search, partner referral) appears anywhere in scope. Decision: scoped, founder-only outreach.
- **Locale-locked to Russian.** `<html lang="ru">`, `locale: "ru_RU"`, all copy in Russian, all topic tags in Russian (`app/page.tsx:33-47`). No `hreflang` alternates, no language switcher. Decision: validate in one language first.
- **Three CTA emission points with explicit location tags (`header_button`, `hero_primary`, `footer_primary`)** are deployed via `TelegramCtaLink` (`docs/audit/_data/landing/index.html`). Decision: differentiate which CTA fires per click without breaking the funnel's first step. Rationale clear from the prop names.
- **`LandingViewTracker` is loaded via React `Suspense` with `fallback: null` in the SSR payload.** Decision: don't block render on analytics — analytics is best-effort.
- **Implicit audience definition.** Audience is never written out as a persona. It is inferred from copy: Russian-speaking couples in long-running relationships, comfortable in Telegram, with a "topic that keeps coming back" (`app/page.tsx:9-13,33-47`, `app/layout.tsx:17-23`). The disclaimer "Не терапия и не замена психолога" (`app/page.tsx:50`) and the FAQ entry "Когда PACTA не подходит" (`app/page.tsx:82-86`) implicitly exclude couples in crisis / abuse situations.

## 5. Risks & landmines

- **Validation runbook + generator are untracked.** Triggered by anyone running `git stash`, `git clean -fd`, fresh clone, or new contributor: the entire validation toolchain disappears. Anything PostHog says about the wave becomes unreproducible because the link-generation logic and the campaign config no longer exist in repo history. Evidence: `git status` → `?? gcs-landing-v2/campaigns/`, `?? gcs-landing-v2/docs/`, `?? gcs-landing-v2/scripts/`; `git ls-files gcs-landing-v2/` confirms nothing in those paths is tracked.
- **Runbook claims `landing_view` and `click_to_telegram` arrive after first click** (`validation-wave-operations.md:62`), but the components that emit those events (`LandingViewTracker`, `TelegramCtaLink`) are absent from the committed source tree. They are only visible in the deployed SSR HTML (`docs/audit/_data/landing/index.html`). Trigger: a rebuild from `main` at `d46ea5f` would not contain these trackers — meaning the deployed site and the repo are out of sync, or the trackers live outside `gcs-landing-v2/app/` in a path not audited here. Either way, the validation wave's analytics surface is not fully reproducible from this commit.
- **Only one sample config file, named `*.sample.json`.** `validation-wave-operations.md:60` instructs operators to "edit planned links in `campaigns/validation-wave.sample.json` or copy it into a wave-specific file." Trigger: if real wave links are pasted directly into the `.sample.json` file (the path of least resistance), the sample loses its example role and operators cannot tell which file is canonical. There is no wave-specific file on disk yet, so the wave either has not launched or its real config is not in this tree.
- **`messageVariant` is mapped to `utm_content` and the runbook says "Change `utm_content` when copy changes"** (`validation-wave-operations.md:26`), but the sample config (`validation-wave.sample.json:5-31`) only stores 1-line `notes` per variant — not the actual message body. Trigger: a wave is paused for a week, the operator returns and cannot reconstruct what `v1` vs `v2` actually said. Copy archeology becomes impossible from the repo alone.
- **Token normalization is destructive.** `normalizeToken` (`generate-campaign-links.mjs:55-71`) lowercases, ASCII-folds Cyrillic, collapses runs of non-alphanumerics to `-`, and refuses to emit if the result is empty. Trigger: an operator passes `--campaign "тест-кампания"`; the result becomes the empty token and the script throws. Or: two different inputs (`post a` and `post-a` and `post_a`) all collapse to `post-a`, silently merging analytics buckets. Documented as a feature in `validation-wave-operations.md:30`, but the failure mode for Cyrillic-only inputs is not documented.
- **No `utm_medium` is ever set in the sample config.** Some downstream tools (and PostHog's default property mapping) expect a `medium` to classify channels. Trigger: any future tool that breaks down by channel medium will see "(not set)" for the entire wave.
- **All CTAs share one bot link without per-CTA UTM.** `https://t.me/PactaTalkBot` (`app/page.tsx:3`, plus the deployed `TelegramCtaLink`) is the only target; differentiation between header/hero/footer clicks lives in the PostHog event property `ctaLocation`, not in the URL itself. Trigger: the bot has no way to attribute a new user to a specific landing position — only "they came via the landing." If `ctaLocation` is not also forwarded to the bot via Telegram's `?start=` parameter, the funnel breaks at the bot boundary. (No `?start=` parameter is set in any CTA in `docs/audit/_data/landing/index.html`.)
- **Single language, single channel pair (Telegram post + founder DM).** Trigger: if the Russian-speaking, Telegram-using, founder-network audience does not convert, the team has zero data on whether the product idea fails or just the channel fails.
- **`pactatalk.app` is the only public surface, hard-coded.** `LANDING_CONTEXT.md:40` says "`metadataBase` должен оставаться `https://pactatalk.app`, не `localhost`." Trigger: any preview deploy / staging URL inherits production canonical and OG image URLs, polluting social previews and SEO signals.
- **No commit pinning the validation wave's launch.** The runbook describes steps 1-4 (`validation-wave-operations.md:58-64`) but there is no log/changelog file recording "wave launched on YYYY-MM-DD with these links." Trigger: when reading PostHog data later, there is no anchor in the repo to correlate event timestamps with the launch moment.

## 6. Open questions for the owner

- Has the validation wave actually been launched, and if so, with which links exactly (the sample file, or a copy)?
- Why are `campaigns/`, `docs/validation-wave-operations.md`, and `scripts/generate-campaign-links.mjs` untracked — intentional, or just not committed yet?
- Where do `LandingViewTracker` and `TelegramCtaLink` live? They are in the deployed SSR HTML but not in the audited source tree at `d46ea5f`.
- What was the success bar for the wave (clicks, bot starts, paired sessions, completed sessions, payment)? The runbook stops at "read campaign performance in PostHog via Validation / Full Funnel" (`validation-wave-operations.md:63`) without naming a threshold.
- Is the audience definition really "Russian-speaking couples on Telegram"? Anything narrower (e.g., parents 30-45, urban, founder's network) — and is that intentional?
- Are the actual message bodies of `post_a v1`, `post_a v2`, `post_b v1`, `dm_intro v1` stored anywhere? Nothing in scope contains them.
- Should `?start=<utm_content>` be forwarded to the bot so attribution survives the Telegram boundary?

## 7. Out-of-scope notes (optional)

- Track `campaigns/`, `docs/validation-wave-operations.md`, `scripts/generate-campaign-links.mjs` in git.
- Store message bodies alongside the variant id (e.g. `campaigns/messages/post_a__v1.md`).
- Pass `?start=<utm_content>` through `TelegramCtaLink` so the bot can complete the funnel.
