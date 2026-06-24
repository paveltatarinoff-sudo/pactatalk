# Frontend code & deploy (landing)

Pinned commit: `d46ea5f779abb10afae4148433f7853396eea92f` (per `docs/audit/2026-06-24/00-shared-header.md:4`). Working tree dirty: `gcs-landing-v2/README.md`, `gcs-landing-v2/package.json` modified, plus untracked `gcs-landing-v2/campaigns/`, `gcs-landing-v2/docs/`, `gcs-landing-v2/scripts/` (git status at session start).

## 1. Scope covered

Examined:
- `gcs-landing-v2/app/` (`layout.tsx`, `page.tsx`, `globals.css`, `opengraph-image.tsx`, `twitter-image.tsx`, `favicon.ico`)
- `gcs-landing-v2/public/landing/` (images: hero photos, avatars, brand logo)
- `gcs-landing-v2/next.config.ts`, `tsconfig.json`, `eslint.config.mjs`, `postcss.config.mjs`, `package.json`, `package-lock.json` (existence only)
- `gcs-landing-v2/.env.example`, `gcs-landing-v2/.vercel/project.json`
- `gcs-landing-v2/README.md`, `gcs-landing-v2/LANDING_CONTEXT.md`, `gcs-landing-v2/docs/validation-wave-operations.md`
- `gcs-landing-v2/scripts/generate-campaign-links.mjs`, `gcs-landing-v2/campaigns/validation-wave.sample.json`
- Pre-captured rendered HTML at `docs/audit/_data/landing/index.html` (70,279 bytes)
- Live response headers from `https://pactatalk.app/` (curl HEAD, captured during this audit)
- `git log --oneline -- gcs-landing-v2/` and `git status gcs-landing-v2/`

Not examined / out of scope for this dimension:
- Visual quality, copy effectiveness, marketing campaigns → see specialists #9, #10, #8
- Vercel dashboard (project settings, env vars actually set, build logs, analytics) — no MCP access; only what's visible via response headers and `.vercel/project.json`
- `node_modules/`, `.next/` build output internals (only top-level manifest filenames listed)
- Lighthouse / Core Web Vitals run — not performed; no captured data

## 2. Inventory

- `app/layout.tsx` — root layout, sets `<html lang="ru">`, loads Manrope + Rubik via `next/font/google` (`layout.tsx:5-13`), exports site `metadata` (title, description, OG, Twitter) with `metadataBase` from `NEXT_PUBLIC_SITE_URL` defaulting to `https://pactatalk.app` (`layout.tsx:16`).
- `app/page.tsx` — single-route landing page, server component, ~511 lines, hard-codes Russian copy and section data (`painPoints`, `steps`, `topics`, `trustPoints`, `heroTrustPoints`, `faqs`).
- `app/globals.css` — Tailwind v4 import + CSS variables for palette and bespoke classes (`.brand-mark`, `.section-frame`, `.telegram-frame`, `.telegram-screen`, etc.).
- `app/opengraph-image.tsx` — Next OG image route, `runtime = "nodejs"`, generates 1200×630 PNG via `next/og` `ImageResponse`.
- `app/twitter-image.tsx` — re-exports the same OG image (`twitter-image.tsx:1`).
- `app/favicon.ico` — 25,931 bytes.
- `public/landing/left-conflict-selected.png` — 2,407,622 bytes (~2.3 MB).
- `public/landing/right-relief-selected.jpg` — 252,063 bytes.
- `public/landing/avatars/{male,female}.jpg` — 3,485 / 6,188 bytes.
- `public/landing/brand/logo-header.png` — 36,901 bytes.
- `next.config.ts` — empty (`{}`) `NextConfig` (`next.config.ts:3-5`).
- `tsconfig.json` — strict TS, `paths: { "@/*": ["./*"] }`, target ES2017.
- `eslint.config.mjs` — `eslint-config-next/core-web-vitals` + `/typescript`.
- `postcss.config.mjs` — `@tailwindcss/postcss` plugin only.
- `package.json` — Next 16.1.6, React 19.2.3, Tailwind 4, scripts `dev/build/start/lint/campaign:links`.
- `.env.example` — declares `NEXT_PUBLIC_SITE_URL`, `NEXT_PUBLIC_POSTHOG_KEY`, `NEXT_PUBLIC_POSTHOG_HOST`.
- `.vercel/project.json` — `projectId=prj_hgG9L0O1sdWvK3f5r7rXWC1OYZL6`, `orgId=team_aCEkzstDtAclLt1BXvnBGnqA`, `projectName=pactatalk-app`.
- `scripts/generate-campaign-links.mjs` — Node CLI building UTM URLs from `campaigns/*.json` (untracked but referenced from modified `package.json`).
- `campaigns/validation-wave.sample.json` — 4 sample UTM definitions targeting `https://pactatalk.app/`.

→ Visual design, copy, narrative effectiveness: see specialist #9 / #8.

## 3. State of each piece

| Item | State | Evidence |
|------|-------|----------|
| Live deploy on Vercel (fra1, prerendered, edge-cached) | works | `curl -sI https://pactatalk.app/` → `server: Vercel`, `x-vercel-cache: HIT`, `x-vercel-id: fra1::h2btw-...`, `x-nextjs-prerender: 1`, `x-nextjs-stale-time: 300`, HTTP 200 |
| SSR HTML matches code | works | `docs/audit/_data/landing/index.html:1` has `<html lang="ru">`, title and meta description identical to `app/layout.tsx:17-19`; canonical to `https://pactatalk.app` |
| Next.js 16 / React 19 / Tailwind 4 stack | works (bleeding edge) | `package.json:13-15,18,24` pins `next@16.1.6`, `react@19.2.3`, `@tailwindcss/postcss@^4`, `tailwindcss@^4` |
| Build artifacts present | partial | `.next/build-manifest.json`, `.next/prerender-manifest.json` etc. exist locally; CI build status not observable from this scope |
| `next.config.ts` | works | empty config (`next.config.ts:3-5`); no image-domain whitelist needed since all images are local under `/public/landing/` (`page.tsx:4-7,227,371-394,305,316`) |
| Telegram CTA wiring | works | `TELEGRAM_BOT_URL = "https://t.me/PactaTalkBot"` (`page.tsx:3`), used in header, hero CTA, final CTA (`page.tsx:195,242,494`) |
| OG image + Twitter image | works | `app/opengraph-image.tsx:11-165` returns `ImageResponse` (nodejs runtime); `app/twitter-image.tsx:1` re-exports it; `layout.tsx:26-39` references `/opengraph-image` and `/twitter-image` |
| Fonts (Manrope, Rubik, cyrillic) | works | `layout.tsx:5-13`; HTML shows 4 preloaded `.woff2` files via `_next/static/media/...` |
| Vercel project linked | works | `.vercel/project.json` shows `projectName=pactatalk-app`, IDs present |
| PostHog snippet on landing | broken / missing | `.env.example:2-3` declares `NEXT_PUBLIC_POSTHOG_KEY/HOST`; `docs/validation-wave-operations.md:7-8,63` claims funnel is live; but `grep -rn posthog gcs-landing-v2/app/` returns nothing, `grep posthog docs/audit/_data/landing/index.html` returns 0 hits — no PostHog SDK, no `landing_view` / `click_to_telegram` event code anywhere in the landing repo |
| Hero photo asset weight | partial | `public/landing/left-conflict-selected.png` = 2.3 MB raw PNG; served via Next/Image (`page.tsx:371-377`) so likely transcoded on Vercel, but source asset is heavy in repo |
| `campaigns/` + `scripts/` + `docs/` directories | untracked | `git status` lists all three as untracked; `package.json` script `campaign:links` (modified, unstaged) depends on `scripts/generate-campaign-links.mjs` — works locally, but missing from git → breaks on a fresh clone |
| README & package.json edits | uncommitted | `git diff HEAD -- gcs-landing-v2/README.md gcs-landing-v2/package.json` shows campaign-links docs and script entry added but not committed |
| Robots.txt / sitemap.xml / web manifest | not found in scope | no `app/robots.ts`, `app/sitemap.ts`, `app/manifest.ts`, no `public/robots.txt`, no `public/sitemap.xml` |
| Theme-color / PWA meta | not found in scope | HTML head has only standard `viewport`, `next-size-adjust`, `charSet`; no `theme-color`, no `apple-touch-icon` link |
| FAQ accessibility (native `<details>`) | works | `page.tsx:469-479` uses `<details>`/`<summary>` — keyboard accessible by default |
| Image alt text | partial | hero `<Image alt="PACTA logo">` (`page.tsx:228`), photo blocks have alt (`page.tsx:373,392`); `ChatAvatar` uses `alt=""` + `aria-hidden` (`page.tsx:115-118`) intentional |
| ESLint config | works | `eslint.config.mjs:2-3` extends Next core-web-vitals + TS; `lint` script wired (`package.json:9`); not run during this audit |
| TypeScript strict | works | `tsconfig.json:7` `"strict": true` |

## 4. Non-obvious decisions

- **Single-file landing.** All ~511 lines live in `app/page.tsx` (`page.tsx:219-511`) — no `components/` directory, no shared layout primitives. Section data (`painPoints`, `steps`, `topics`, `heroTrustPoints`, `faqs`) is hard-coded at module scope (`page.tsx:9-87`). Rationale visible in `LANDING_CONTEXT.md:7-9` ("Актуальный публичный лендинг", single-page marketing site) — deliberate "one page, no abstractions" choice.
- **Inline SVGs for every icon** (`TelegramIcon`, `PainIcon`, `StepIcon`, `page.tsx:89-189`). No icon library dependency; keeps `dependencies` at 3 packages (`package.json:12-16`). Rationale unclear whether for bundle size or just minimalism.
- **Server-component-only.** No `"use client"` directive anywhere in `app/`. No `onClick`, `useEffect`, or `window.*` calls. The whole page renders as static HTML — confirmed by `x-nextjs-prerender: 1` in live headers and by the absence of analytics handlers. Implication: CTA tracking can only happen via referrer/UTM landing-page parsing on the bot side, not via in-page events.
- **PostHog declared but never installed.** `.env.example:2-3` lists `NEXT_PUBLIC_POSTHOG_KEY/HOST`. `docs/validation-wave-operations.md:7-8` states the "analytics funnel is already live end-to-end" and references `landing_view` / `click_to_telegram` events. No PostHog provider, no `posthog-js` dependency in `package.json`, no events fired from landing code. Either (a) PostHog autocapture is configured at the project level via a different surface, (b) events are recorded only on the bot side, or (c) the doc is aspirational. Rationale unclear.
- **OG image runtime = nodejs**, not edge. `opengraph-image.tsx:3` explicitly `export const runtime = "nodejs"`. Default in Next 16 for `ImageResponse` is edge; the override suggests an earlier edge-runtime issue. Rationale unclear from code/commits.
- **Untracked support code in package.json.** `package.json:10` adds `campaign:links` script pointing to `scripts/generate-campaign-links.mjs`, and `README.md:42-51` documents `docs/validation-wave-operations.md` — but all three directories (`scripts/`, `campaigns/`, `docs/`) are untracked in git. Looks like an in-progress local addition the owner forgot to commit.
- **`metadataBase` env-driven** (`layout.tsx:16`). Defaults to `https://pactatalk.app` when `NEXT_PUBLIC_SITE_URL` is unset, allowing preview deploys to set their own URL. Sensible.
- **No `next.config.ts` customization.** Empty config (`next.config.ts:3-5`) means default behavior for images, headers, redirects, i18n. The site is Russian-only (`<html lang="ru">`) — no i18n needed.

## 5. Risks & landmines

- **Validation-wave docs out of sync with code (telemetry gap).** `docs/validation-wave-operations.md:7,63` promises `landing_view` and `click_to_telegram` PostHog events. Code does not emit them and PostHog SDK is not loaded. Anyone reading the dashboard for landing funnel data may see zero events from the actual landing surface; campaign comparisons by `utm_source` / `utm_campaign` rely on whatever the bot captures after the redirect, not on landing impressions. Trigger: opening "Validation / Full Funnel" in PostHog after a campaign launch.
- **Untracked critical files.** `scripts/generate-campaign-links.mjs`, `campaigns/validation-wave.sample.json`, `docs/validation-wave-operations.md` are untracked. `package.json` references the script. On any fresh clone or Vercel CI build, `npm run campaign:links` fails. Trigger: another collaborator (or you on a new machine) clones the repo and runs the documented command.
- **Uncommitted `package.json` change.** The `campaign:links` script entry exists locally and ships only because nothing rebuilds from `git`. If Vercel rebuilds from the pinned SHA `d46ea5f`, that commit pre-dates the change (`git log -- gcs-landing-v2/` shows only `d45f8ba` and `8d92cec`, neither touching scripts) — the live deploy and HEAD diverge. Trigger: any redeploy from main.
- **Stale Vercel edge cache.** Live `age: 1844578` (≈21 days) with `x-vercel-cache: HIT`. Pre-rendered page is fine since it's stable, but any future code change requires explicit cache purge / new deploy SHA to propagate. Trigger: shipping copy fix and waiting for it to appear without a redeploy.
- **Heavy hero image in repo.** `left-conflict-selected.png` is 2.3 MB raw (`ls -la gcs-landing-v2/public/landing/`). Served through `next/image` so end-user payload is fine, but the repo carries the raw asset on every clone and every Vercel build pulls it. Trigger: repo size growth as more landings/iterations land.
- **No `robots.txt` / `sitemap.xml`.** Not found anywhere in `app/` or `public/`. Vercel defaults will serve a permissive robots, but there's no explicit policy or sitemap. Trigger: SEO indexing, link-preview crawlers, AI crawlers.
- **No CSP / security headers in `next.config.ts`.** Config is empty. Defaults are whatever Vercel applies. Trigger: security review or third-party script injection later.
- **Bleeding-edge stack.** Next 16.1.6 + React 19.2.3 + Tailwind 4. Major versions are very recent — minor ecosystem breakage and plugin incompatibilities are plausible if a dependency is added. Trigger: `npm install <anything>`.
- **`scripts/`, `docs/`, `campaigns/` paths in `LANDING_CONTEXT.md` point to old absolute path `/Users/pashkamoroz/Documents/Ai family coach/...`** (`LANDING_CONTEXT.md:12,30,46`), but the current project lives under `/Users/pashkamoroz/Documents/PAVEL AI/projects/ai-family-coach/`. Trigger: any agent or human following these links.
- **`.vercel/project.json` checked in.** Contains real `projectId`/`orgId` (`gcs-landing-v2/.vercel/project.json:1`). Standard for Vercel-linked repos but leaks Vercel project handles to anyone with repo read access. Diagnosis only, not necessarily an issue.

## 6. Open questions for the owner

- Is PostHog actually firing for landing visits? If yes, from where (autocapture project-wide, reverse proxy, GTM)? If not, are `landing_view`/`click_to_telegram` numbers in `Validation / Full Funnel` real or zero?
- Why are `scripts/`, `campaigns/`, `docs/`, and the matching `package.json`/`README.md` edits not committed? Should they be?
- Is the empty `next.config.ts` intentional, or are headers/redirects/image config expected to be added before launch?
- Is `runtime = "nodejs"` on the OG image route a workaround for a known edge-runtime issue, or just a default that drifted?
- Is the absence of `robots.ts` / `sitemap.ts` intentional (block indexing until validation complete) or an oversight?
- Did the cache `age` of ~21 days from the live edge fetch surprise you, i.e., were there any landing copy/code changes you expected to be live by 2026-06-24?

## 7. Out-of-scope notes

- Commit the untracked `scripts/`, `campaigns/`, `docs/` and the modified `package.json`/`README.md` before next deploy, or revert them, so live deploy and HEAD agree.
- If PostHog is supposed to track landing, add the snippet (provider in `app/layout.tsx` or a small client component) and emit `landing_view` on mount + `click_to_telegram` on CTA click.
