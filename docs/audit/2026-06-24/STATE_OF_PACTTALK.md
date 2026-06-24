# State of PactTalk — 2026-06-24, commit d46ea5f779abb10afae4148433f7853396eea92f

## TL;DR

- The Telegram bot is alive in Fly (`pactatalk-bot`, region `fra`, machine `d896e24a069058`, last successful release `v83` on 2026-03-30), serving real two-user sessions today via webhook [#7].
- HEAD imports three files that do not exist in git or on disk (`bot/handlers/menu.py`, `bot/models/session_insight.py`, `bot/models/user_request.py`) — any restart or rebuild from this SHA will crash on `ImportError` before the event loop starts [#3, #7].
- The deployed landing at `pactatalk.app` references `LandingViewTracker` / `TelegramCtaLink` and PostHog instrumentation, but none of that code is in the committed source tree at HEAD; only stale `.next/` sourcemap artefacts preserve it [#4, #5, #10].
- All three PostHog "Validation" funnels are filtered to `campaign = "smoke-01"` (lifetime: 1 matching event) and `feedback_submitted` has 0 lifetime events — so the validation-wave dashboards read empty even where raw events exist [#5, #8].
- The dialog facilitator (handoff / state machine / BOTH-mode / resume) is the most-tested and most-stable surface: ~30 handoff tests, all post-guards consolidated into one resolver, live transcripts confirm handoff signature firing (149+ "теперь твой ход" hits in `tg/messages.html`) [#2].
- The LLM service is OpenAI-only `gpt-4o` (hard-coded), module is misleadingly named `claude_service.py`, runs with default `temperature=1.0` and no caching [#1].
- The eval harness that produced the team's depth/anti-template baseline is gone — `evals/pactatalk_eval.py`, `evals/scenarios/`, and 8 dated `reports/evaluations/*` runs were never tracked in git and have been deleted from disk (only an orphan `.pyc` survives) [#6].
- `gcs45_bot/.env` holds live-looking `BOT_TOKEN`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY` and the repo has no `.gitignore` — one `git add .` away from leaking [#7].
- Most production end-of-session summaries in the owner's own test transcripts show "Данных для итога разговора недостаточно" — the strongest retention moment is degraded [#8].
- One owner, sole PostHog admin, one Fly machine, no CI, no rollback tags — every operational surface is a single point of failure [#5, #7].

## What's solid

- **Dialog state machine and handoff invariants.** `addressed_to` is the single authoritative handoff field; `resolve_handoff_invariants` consolidates 6 post-guards into one resolver (commit `407e904`); ~30 tests cover handoff/addressing in `tests/test_handoff.py`; live Telegram transcripts confirm the handoff signature reaches users (`grep "теперь твой ход" tg/messages.html` → 149 hits) [#2].
- **Structured Outputs schema.** Facilitator turn uses strict JSON schema `RESPONSE_SCHEMA` with `message`, `next_speaker`, `risk_flag`, `addressed_to`, `next_state`; session-insight uses `SESSION_INSIGHT_SCHEMA` [#1].
- **Per-state developer prompt assembly** is mature: `_developer_prompt_for_state` injects state header, resume block, last-answer hint, joint-mode hint, anti-generic ("grounding") hint, consecutive-speaker info, anti-repeat warning, MI cooldown notice, address-feedback hint, addressing rule [#1].
- **Pre- and post-call guards re-checked at both layers** (premature OPTIONS <8 user turns, action rejection → DEEPEN, cooldown after rejection). Belt-and-braces design with distinct log labels [#2].
- **Resume continuity in production.** Bot proactively offers resume on `/start` and `/new_session` when a prior session exists; `tg/messages2.html` blocks 257-258 and 266-267 show working resume copy: "С возвращением! Я помню ваш прошлый разговор. Тема: …" [#8].
- **Loop-mode-shift circuit breaker.** When the same speaker emits low-energy answers to reflective questions in `DEEPEN/CLARIFY/DEESCALATE`, a canned fallback bypasses Claude entirely (`bot/services/loop_guard.py:106-136`); covered by `test_loop_mode_shift.py` [#2].
- **Resume voting in Redis.** Two-party `resume_vote:{sid}:{uid}` with `waiting | matched | mismatch | duplicate | resolved` states; alignment free-text path classifies continue/new/flexible; idempotent and race-protected (`test_session_resume.py`) [#2].
- **Fly deploy is up.** App running, webhook returning 200, heartbeats showing 4 active sessions, retry/timeout wired (`OPENAI_TIMEOUT_SECONDS=30`, 3 retries with linear backoff) [#1, #7].
- **Alembic baseline migration works** for the 5 tables it covers (`pair_resumes`, `session_events`, `session_snapshots`, `transactions`, `users`); `release_command = "python -m alembic upgrade head"` wired in `fly.toml` [#3, #7].
- **Landing is up at `pactatalk.app`** — Vercel-served Next.js 16 + React 19 + Tailwind 4, SSR HTML matches code at `gcs-landing-v2/app/page.tsx`, fonts preloaded, OG/Twitter cards declared, `<html lang="ru">`, valid heading hierarchy (1×H1, 5×H2, 5×H3) [#4, #9].
- **Validation-wave runbook + UTM link generator** are well-thought-out (`scripts/generate-campaign-links.mjs` normalizes tokens, `docs/validation-wave-operations.md` documents two-axis convention `utm_campaign`=placement, `utm_content`=variant) [#10].
- **Privacy-delete cascade** is implemented and tested (`tests/test_privacy_delete.py`, 5 tests) covering Redis + DB fan-out [#3].
- **Webhook security.** `force_https=true` on Fly + aiogram `SimpleRequestHandler(... secret_token=settings.webhook_secret)` verifying Telegram's `X-Telegram-Bot-Api-Secret-Token` header [#7].
- **Session lifecycle in Telegram.** `/new_session`, `/join`, `/end_session`, `/progress`, `/support`, `/privacy` all observed working in `tg/messages2.html`; support ticketing returns "Спасибо, я передал это команде." [#8].

## What's broken or fragile

- **Import failure on restart (P0).** `bot/main.py:15,22-23` imports `bot.handlers.menu`, `bot.models.session_insight`, `bot.models.user_request`. None exist in working tree, in any branch, or in any tag (`git log --all -- <paths>` empty); only `.pyc` artefacts remain. Trigger: any `fly deploy`, container rebuild, or forced restart. Effect: process crashes before event loop starts; release machine exits non-zero [#3, #7].
- **Schema drift, Alembic vs. runtime.** `SessionRepository` has CRUD for `session_insights` and `user_requests` tables (`session_repo.py:401-583`), but the only Alembic revision (`20260319_0001`) does not create them. Trigger: fresh DB or any code path that calls `save_session_insight`/`create_user_request`. Effect: `relation "session_insights" does not exist` [#3, #7].
- **PostHog instrumentation not in git.** Committed landing has no `posthog-js` dependency, no provider, no `landing_view`/`click_to_telegram` emitters; bot Python at HEAD has zero PostHog references either. Yet PostHog received 18 `bot_start`, 114 `landing_view`, etc., with `$lib=null` (server send). Critical analytics source lives only in stale `.next/` sourcemaps and on Fly secrets. Trigger: redeploy from `main`. Effect: all funnels go to zero [#5, #8, #10].
- **All three Validation funnels filtered to `campaign = "smoke-01"` (1 lifetime matching event).** UI text on last 7 days: "There are no matching events for this query." Real campaign data (`landing_view: 113 non-smoke-01`, `bot_start: 18`) is invisible in the validation dashboard [#5, #8].
- **Validation-wave campaigns never used.** Names from `campaigns/validation-wave.sample.json` (`post_a`, `post_b`, `dm_intro`) are absent from any PostHog event. Either the wave never launched, or the generator output was not posted [#5, #10].
- **`feedback_submitted` event count = 0 lifetime.** Bot sends `feedback_shown` (7 lifetime) but no survey response ever reached PostHog. End-to-end feedback loop is non-functional [#5].
- **Post-session summary degraded.** In every visible production end-of-session in `tg/messages2.html` (blocks 253, 262, 269, 274), the summary body is "Данных для итога разговора недостаточно. Итог уже сохранён в разделе «Мои итоги»." The strongest retention moment shows no value [#8].
- **`/start` handler latency.** Captured 2026-06-24 09:48:43-54: `await repo.get(user.id)` took ~11s before the update was handled. A new partner clicking the invite during a Postgres hiccup may abandon [#7, #8].
- **Live secrets in untracked `.env` with no `.gitignore`.** `gcs45_bot/.env` contains real-looking `BOT_TOKEN`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`; no `.gitignore` at repo root or in `gcs45_bot/`. Trigger: one `git add .` [#7].
- **OG card drift on landing.** Production HTML hard-codes `https://pactatalk.app/landing/og-card.png` (returns 200); source `layout.tsx:28` points to dynamic `/opengraph-image` route (returns 404). Next redeploy from HEAD breaks Telegram/Twitter previews [#9].
- **Validation tooling untracked.** `gcs-landing-v2/campaigns/`, `gcs-landing-v2/scripts/`, `gcs-landing-v2/docs/` all untracked; `package.json`/`README.md` edits unstaged. `npm run campaign:links` references a script not in git [#4, #10].
- **Voice end-session confirmation path missing.** `handle_voice_message` detects end-session intent but does NOT call `_resolve_end_session_confirmation`. If a user replies "да" via voice during a confirmation pending state, the bot will not interpret it as confirmation [#2].
- **Eval harness deleted.** `evals/`, `evals/scenarios/`, and 8 dated `reports/evaluations/*` (Mar 19-20: `core15`, `v2`, six `depth-*` runs) were never tracked in git and are gone from disk. Only `evals/__pycache__/pactatalk_eval.cpython-314.pyc` survives — and it targets Python 3.14 while the venv is 3.9, so it cannot even be loaded [#6].
- **No `working-*` rollback tags** despite the global rule, no CI, no automated migration check. Single Fly machine. Single PostHog admin (`paveltatarinoff@gmail.com`) [#5, #7].
- **`pyproject.toml` lies about Python floor.** Declares `requires-python = ">=3.9"` but code uses PEP 604 `str | None` unions throughout. Install on 3.9 → `SyntaxError` at import [#3].
- **No `temperature` set on gpt-4o → default 1.0.** With explicit "do not repeat phrases" instructions and post-hoc anti-repeat heuristics, high sampling temperature directly fights what the guards try to detect [#1].

## What was tried and abandoned

- **Eval suite (Mar 2026).** `evals/pactatalk_eval.py` with judge model `gpt-4o-mini`, 8 scoring axes (`addressing_routing`, `depth_holding`, `empathy_humanness`, `usefulness`, `neutrality`, `variability_non_template`, `safety_handling`, `realism_as_facilitator`), 4 aggregation groups (`routing`/`depth`/`tone`/`safety`), in-memory repo for hermetic runs. Eight dated comparison runs across one week (`core15`, `v2`, six `depth-*` variants). Never tracked in git; all source and outputs deleted; bytecode orphan misleadingly remains [#6].
- **Server-side handoff override.** Earlier design rewrote handoff based on text-detection of partner name. Removed by commit `bf361de` ("remove feedback handoff override, keep as prompt signal"); now logs only as `facilitator_reply_routing_observed_conflict` [#1, #2].
- **`next_speaker` as independent authority.** Collapsed into `addressed_to` per commit `f0586d9`; schema retains the field for backwards compat per commit `90cc912`; server now sets `next_speaker = addressed_to` after resolution [#1, #2].
- **Instrumented landing with PostHog provider.** `gcs-landing-v2/lib/analytics/posthog.ts`, `attribution.ts`, `LandingViewTracker`, `TelegramCtaLink`, `app/providers.tsx`, `app/survey-complete/page.tsx`, `app/api/analytics/feedback-submitted/route.ts` were built (recoverable only from `.next/` sourcemaps) and apparently deployed, but never committed to git. The committed landing reverted to static SSR with no analytics [#4, #5, #8, #10].
- **`SessionState.consecutive_turns` and `SessionState.timeout_reminders_sent`** are set/reset but never read; `_consecutive_same_speaker` recomputes from history. Stale leftovers from earlier design [#2].
- **`SessionState.phase` intermediate values.** Declared `opening | exploration | deepening | agreement | closing`, but only `opening` and `closing` are ever set. Dialogue state machine moved to `dialogue_state` field [#2].
- **`SessionService.pass_turn` and its callback.** Dead-ish: only invoked from a manual button (`cb_pass_turn`), never from the facilitator turn loop. No test, unclear if intentionally retained [#2].
- **Sibling worktree `_deploy_gcs45_bot_alembic/`.** Stale, points to a different repo root (`/Users/pashkamoroz/Documents/Ai family coach/.git/...`). Last touched Mar 19, nothing in `fly.toml`/`Dockerfile` references it [#7].
- **Egg-info under two names.** Both `gcs45_bot.egg-info/` and `pactatalk_bot.egg-info/` exist on disk — package rename in flight, never cleaned up [#3].

## Cross-cutting risks

- **Repo↔deployment drift.** HEAD does not match what is actually running. Bot's running image was built locally on Mar 30 before `menu.py`/`session_insight.py`/`user_request.py` vanished; landing's deployed bundle contains PostHog code that is not in the committed tree. Both surfaces will break on next clean rebuild [#3, #4, #5, #7, #8, #10].
- **Analytics integrity is bundled with deploy drift.** PostHog secrets are deployed on Fly (`POSTHOG_API_KEY`, `POSTHOG_HOST`) but no code at HEAD reads them; the bot must be sending events from a build that contains code not in this SHA. Any rotation, rebuild, or fresh checkout severs the analytics pipeline that the validation wave depends on [#5, #7, #8, #10].
- **Critical-path code lives only on owner's laptop.** Missing model files (`session_insight.py`, `user_request.py`), missing handler (`menu.py`), eval harness (`evals/`), instrumented landing — all are or were on disk and never made it into git. A single laptop loss removes them all [#3, #5, #6, #7, #8, #10].
- **No quality gate before prompt/handoff changes.** Eval harness is deleted; no CI; recent prompt-affecting commits (`a3d5d42`, `90cc912`, `f0586d9`, `407e904`, `bf361de`) shipped with no automated regression check on the eight axes the team previously cared about. Combined with `temperature=1.0` and degraded summaries, this is hard to debug [#1, #6, #8].
- **Single point of failure across people and infra.** One owner, one Fly machine, sole PostHog admin (`paveltatarinoff@gmail.com`), sole Vercel project owner, no rollback tags, no CI, no `.gitignore` to protect leaking secrets [#5, #7, #9].
- **Bleeding-edge stack on landing.** Next 16.1.6 + React 19.2.3 + Tailwind 4 — any added dependency may pull incompatible peer ranges; combined with uncommitted `package.json` edits, the Vercel build behaviour can drift silently between owner laptop and CI [#4].
- **Russian-only stack.** All prompts, markers (vulnerability, safety-adjacent, action rejection, end-session intent, address-feedback), runbook, landing copy, and the topic chip list are Russian. No language detection, no fallback. Mismatch between user's actual phrasing and the heuristic substring lists silently bypasses safety/intent detection [#1, #2, #9, #10].
- **Attribution stops at the Telegram boundary.** All three landing CTAs go to bare `https://t.me/PactaTalkBot` with no `?start=<utm_content>` payload. The bot has no way to attribute a session to a specific landing position or campaign. PostHog funnels cannot be joined across the boundary [#8, #10].
- **Schema-evolution path is unclear.** Only one Alembic revision (`down_revision=None`); two model files imported but never migrated; `enable_dev_schema_bootstrap` only gated to non-production. Any non-baseline DB change requires hand-writing a migration with no precedent in repo [#3, #7].

## Non-obvious decisions worth preserving

- **`addressed_to` as single handoff authority** (commits `f0586d9`, `90cc912`, `407e904`, `bf361de`). All addressing decisions flow through `resolve_handoff_invariants` post-call; `next_speaker` is derived; text-based detection survives only as telemetry. Documented in `CLAUDE.md §2`. Rationale: single point of truth, easier to test [#1, #2].
- **Pre-call effective-state resolver + post-call state guards re-run the same six checks** (`_resolve_effective_state` + `get_facilitator_response` post-guards). Pre-call shapes the prompt, post-call defends against GPT picking `next_state` anyway. Distinct log labels (`blocked_premature_options` vs `post_guard_blocked_premature_options`) [#2].
- **`MAX_CONSECUTIVE_BOTH_TURNS = 2` is hard.** After 2 joint cycles in non-joint states, server forces single-speaker focus chosen by `_preferred_focus_speaker_after_joint` scoring vulnerability > safety-adjacent > grounding > word count [#2].
- **`MIN_USER_TURNS_FOR_OPTIONS = 8`** — GPT cannot enter OPTIONS/AGREE before 8 user turns. Anti-premature-solutions baseline from `CLAUDE.md §4` [#2].
- **Resume Redis voting with TTL 24h.** Two-sided coordination without writing back to session snapshot on every callback. Idempotent and race-protected [#2].
- **Hermetic eval harness via `InMemoryRepo`.** Bypassed the real Postgres-backed `session_repo.py` to keep eval runs fast and isolated from DB state (recovered from bytecode; source gone) [#6].
- **Two-storage backend split.** Redis authoritative for live state (7d TTL); Postgres for resume across TTL expiry. `SessionRepository.get` rehydrates Redis from snapshot on cache miss — documented continuity mechanism [#3].
- **`pair_key = sorted "lo:hi"`** for `PairResume`. Independent of which side initiated; supports GDPR LIKE-pattern fan-out [#3].
- **Telegram chat mock-up as hero visual** instead of a couple photo. Removes ambiguity that this is a Telegram bot [#9].
- **H1 leads with user pain, not product name.** "Когда в паре пора обсудить важное, но самим удержать разговор уже не получается" — parallel structure in OG image confirms deliberate problem-first positioning [#9].
- **Self-service UTM generator with destructive token normalization.** Lowercase + ASCII-fold + collapse-runs ensures PostHog filters stay predictable, accepting that two near-identical inputs merge into one analytics bucket [#10].
- **Two-axis UTM split** (`utm_campaign` = placement/hypothesis, `utm_content` = message variant). Non-obvious because most teams overload `utm_campaign` for both [#10].
- **Custom attribution via `?start=trk1_{source}_{campaign}_{variant}_{leadId}`** (in the lost instrumented landing) to stitch landing visitor → Telegram user [#5].
- **Bot uses raw HTTP capture endpoint to PostHog**, not the Python SDK (events arrive with `$lib=null`) — likely intentional to avoid the Python SDK's batching/buffering complexity [#5].

## Coverage gaps

- **Where the deployed bot's PostHog code actually lives.** Bot Python at HEAD has zero PostHog code; PostHog received 18 `bot_start` with `$lib=null` and `telegram_user_id` properties; Fly has `POSTHOG_API_KEY`+`POSTHOG_HOST` set. Source not in repo — unknowable from this commit [#5].
- **Whether the live `pactatalk.app` deployment is the committed minimal `app/page.tsx` or the older instrumented variant** whose source is preserved only in `.next/` sourcemaps — inferable but not directly verified [#5].
- **Step definitions and current conversion numbers in PostHog** — specialist #8 only inventoried funnel names/IDs and the campaign config that names the events they expect; did not open the funnels in the UI [#8].
- **Funnel raw numbers and per-campaign breakdowns** — specialist #5 captured event totals via HogQL but did not click into the validation dashboard tiles to read current funnel cohort sizes per step [#5, #8].
- **Test execution.** Specialist #3 inventoried 43 test functions across 7 files but did not run them (`unknown (not run)`). Specialist #6 confirmed no CI exists to run them automatically [#3, #6].
- **Visual / mobile QA on landing.** No live Chrome MCP screenshots; mobile-specific layout/contrast not measured; keyboard focus states not exercised [#9].
- **Production LLM logs / token costs.** Out of scope for #1; not captured by #7 either (release log only, not LLM telemetry) [#1, #7].
- **Owner test conversation contents in `tg/messages2.html`** — specialist #8 read first 20 + last 40 messages, not the full ~322 blocks; depth-holding and reply quality not audited end-to-end [#8].
- **Backups of deleted assets.** No specialist could determine if `evals/pactatalk_eval.py`, `evals/scenarios/`, `bot/handlers/menu.py`, `bot/models/session_insight.py`, `bot/models/user_request.py`, instrumented landing files, or the lost `reports/evaluations/*` runs exist on another branch, another machine, or Time Machine [#3, #5, #6, #7, #8].
- **Neon Postgres dashboard, Upstash Redis dashboard, Vercel build logs** — not inspected; only inferred from env URLs and HTTP headers [#4, #7].
- **Per-CTA / per-position click attribution at the Telegram boundary.** Specialist #10 observed `?start=` is not used for `utm_content`; specialists #5/#8 noted attribution is lost there; nobody validated whether the bot extracts any campaign info from `start` payloads [#5, #8, #10].

## Open questions for the owner

**On LLM / prompts (specialist #1, §6):**
1. Why is `MODEL` hard-coded to `gpt-4o` (not env-driven), and what is the intended migration path? [#1]
2. Was the absence of `temperature` (and `top_p`/`seed`) intentional, or simply never set? Any A/B vs. lower temperature? [#1]
3. Why does `generate_summary`/`generate_session_insight` reuse the full facilitator `SYSTEM_PROMPT` while `generate_resume_context` uses a short bespoke message? Intentional asymmetry? [#1]
4. The class `ClaudeService` / module `claude_service.py` no longer reflect the provider. Backward compat or pending rename? [#1]
5. The duplicated vulnerability/safety-adjacent marker lists (`_last_user_message_is_*` vs class-level constants) — is one dead code? [#1]
6. Are thresholds `MIN_USER_TURNS_FOR_OPTIONS=8`, `MIN_TURNS_AFTER_REJECTION=4`, `MAX_CONSECUTIVE_BOTH_TURNS=2`, `MAX_CONTEXT_MESSAGES=30`, `MAX_MESSAGE_LENGTH=2000` derived from data or initial guesses? [#1]
7. Is `prompt_harness.py` actually run before prompt-edit deploys? Where do outputs go? [#1]
8. Production token cost per facilitator turn today? [#1]

**On dialog logic (specialist #2, §6):**
9. Is `SessionService.pass_turn` (and its callback) deliberately retained, or dead UI? [#2]
10. Is `SessionState.phase` a vestige or is something planned to set intermediate values? [#2]
11. Is `SessionState.consecutive_turns` intentionally kept for future use, or remove? [#2]
12. Was excluding `close_confirmation_pending` from voice handler intentional? [#2]
13. Is loop-mode-shift's exclusion of `OPTIONS`/`AGREE` deliberate, or unported? [#2]
14. Why does `_apply_next_speaker` reset counters tied to never-implemented timeout reminders? [#2]

**On backend (specialist #3, §6):**
15. Were `bot/models/session_insight.py` and `bot/models/user_request.py` deleted on purpose, or unpushed local files? [#3]
16. Where are the migrations for `session_insights` and `user_requests` tables? [#3]
17. What is the deploy/runtime story for `ENABLE_DEV_SCHEMA_BOOTSTRAP` in production? [#3]
18. Is `requires-python = ">=3.9"` floor intentional given PEP 604 syntax is used? [#3]
19. Why both `gcs45_bot.egg-info/` and `pactatalk_bot.egg-info/`? Package rename? [#3]
20. Is `bot/services/shared.py`'s module-level `ClaudeService()` singleton intentional? [#3]
21. Is `loop_guard` calling `ClaudeService` private staticmethods deliberate? [#3]
22. What does the current Postgres schema actually look like in prod / staging? [#3]

**On landing frontend (specialist #4, §6):**
23. Is PostHog actually firing for landing visits? From where (autocapture, reverse proxy, GTM)? [#4]
24. Why are `scripts/`, `campaigns/`, `docs/`, `package.json`/`README.md` edits not committed? [#4]
25. Is the empty `next.config.ts` intentional? [#4]
26. Is `runtime = "nodejs"` on OG image a workaround for a known edge-runtime issue? [#4]
27. Is absence of `robots.ts` / `sitemap.ts` intentional (block indexing until validation complete)? [#4]
28. Did the cache `age` of ~21 days from live edge fetch surprise you? Were any landing changes expected to be live by 2026-06-24? [#4]

**On PostHog (specialist #5, §6):**
29. Where does the deployed bot's PostHog code actually live? Different branch, unpushed worktree, hand-edited on Fly? [#5]
30. Same for deployed landing: which revision is on Vercel? Was the instrumented variant ever in git? [#5]
31. Why are the three Validation funnels gated on `campaign = "smoke-01"`? Leftover from smoke test? [#5]
32. `feedback_submitted` was designed end-to-end but never produced an event. Is the survey URL out in the wild? [#5]
33. The four validation-wave campaign names never appear in PostHog data — were any of those links posted publicly? [#5]
34. Are recent `landing_view` events with `$lib=null` expected (server-side proxy), or symptomatic of posthog-js failing? [#5]

**On evals (specialist #6, §6):**
35. Was deleting `evals/`, `evals/scenarios/`, and the eight `reports/evaluations/*` directories intentional or accidental? [#6]
36. Is there a backup of `evals/pactatalk_eval.py` and `evals/scenarios/*` anywhere (branch, machine, Time Machine, gist)? [#6]
37. Were the eval results ever exported anywhere durable (doc, Notion, screenshot), or only inside the deleted folders? [#6]
38. Why was the harness paused after 2026-03-24? Question considered closed, or harness proved unreliable? [#6]
39. Did the eval ever run in CI/schedule, or always manual local invocation? [#6]
40. Should the eight-axis rubric, four aggregation groups, and `gpt-4o-mini` judge choice still be official quality model? [#6]
41. Are the rule-pattern lists the same patterns now enforced server-side, or older taxonomy? [#6]

**On deploy/infra (specialist #7, §6):**
42. Were `bot/models/session_insight.py`, `bot/models/user_request.py`, `bot/handlers/menu.py` ever committed? Where are the source files now? [#7]
43. Is the running deployment expected to be safe to restart today? [#7]
44. Why is there a single Alembic migration with no follow-up for `SessionInsight`/`UserRequest`? [#7]
45. Are the `POSTHOG_*` Fly secrets reserved for future use, or read by code that is now gone? [#7]
46. Was `gcs45_bot/.env` deliberately left untracked without a `.gitignore`? Were the keys meant to be stored elsewhere? [#7]
47. What lives at `/Users/pashkamoroz/Documents/Ai family coach/` — is `_deploy_gcs45_bot_alembic/` still in use? [#7]
48. Releases `v59`, `v65`, `v77` are marked `failed` — do you recall why? [#7]
49. How do you deploy today — manual `fly deploy` from laptop, or a script not in this repo? [#7]

**On product journey (specialist #8, §6):**
50. Are the 3 Validation funnels currently showing any data? If yes, where do `landing_view`/`click_to_telegram` originate? [#8]
51. Was the previous `gcs-landing-v2/lib/analytics/posthog.ts` removed deliberately (privacy, refactor) or accidentally? [#8]
52. When tests in `tg/messages2.html` showed "Данных для итога недостаточно", was it fresh test session or resumed with no new content? [#8]
53. How is a real user expected to discover `/progress`, `/support`, `/privacy`? [#8]
54. Is the post-session survey URL a Typeform / Google Form? Are responses read back into PostHog? [#8]
55. Is the validation hypothesis "people will click the CTA" (acquisition) or "couples will complete a session" (engagement)? [#8]

**On UX/design (specialist #9, §6):**
56. Is `/landing/og-card.png` the source of truth, or should `app/opengraph-image.tsx` win? [#9]
57. Is absence of Privacy/Terms/Contact link deliberate stealth-launch stance, or oversight? [#9]
58. Why is the brand wordmark rendered twice in the header (logo image + adjacent `PACTA — AI`)? [#9]
59. Was the choice to lead H1 with pain rather than product name validated against any audience? [#9]
60. Are there testimonials / sample transcripts / clinician advisors intentionally withheld for now? [#9]
61. Was a sticky / repeating mobile CTA considered and rejected, or just not built yet? [#9]

**On distribution/marketing (specialist #10, §6):**
62. Has the validation wave actually been launched, and with which links exactly (sample file, or a copy)? [#10]
63. Why are `campaigns/`, `docs/validation-wave-operations.md`, `scripts/generate-campaign-links.mjs` untracked? [#10]
64. Where do `LandingViewTracker` and `TelegramCtaLink` live? [#10]
65. What was the success bar for the wave (clicks, bot starts, paired sessions, completed sessions, payment)? [#10]
66. Is the audience really "Russian-speaking couples on Telegram", or anything narrower? [#10]
67. Are the actual message bodies of `post_a v1`, `post_a v2`, `post_b v1`, `dm_intro v1` stored anywhere? [#10]
68. Should `?start=<utm_content>` be forwarded to the bot so attribution survives the Telegram boundary? [#10]

## Contradictions between specialists

- **Did the instrumented landing ever live in git?** Specialist #5 reports it appears in **no git commit** (`git log --all -- gcs-landing-v2/lib/analytics/posthog.ts` → empty) [#5]. Specialist #8 reports the previous `gcs-landing-v2/lib/analytics/posthog.ts` was "removed" (`Was the previous … removed deliberately`), implying it once existed [#8]. Specialist #10 reports the components are "absent from the committed source tree at `d46ea5f`" and asks "Where do `LandingViewTracker` and `TelegramCtaLink` live?" — leaving open whether they ever did live in git [#10]. Specialists do not converge on whether the code was ever committed at any earlier SHA.
- **Is the bot actually sending PostHog events today, or did it stop?** Specialist #5 reports 18 `bot_start` events with `$lib=null` ingested over the lifetime, last_seen `2026-06-24` for `bot_start` (= today) [#5]. Specialist #7 reports `POSTHOG_API_KEY`/`POSTHOG_HOST` are deployed but no code at HEAD reads them, framing them as "**deployed but unused**" [#7]. Both can be true if the running image was built before HEAD, but the specialists describe the state in different terms ("functioning ingestion" vs. "dead config").
- **What is the actual LLM provider in production?** Specialist #1 reports the runtime provider is "OpenAI only" (`AsyncOpenAI` at `claude_service.py:700`, `gpt-4o` constant, `whisper-1`) and `Anthropic SDK is not imported anywhere in scope` [#1]. Specialist #7 reports `gcs45_bot/.env` contains a live-looking `ANTHROPIC_API_KEY` alongside the `OPENAI_API_KEY` [#7]. Specialist #6 reports the missing eval imported `bot.services.claude_service.ClaudeService` and called `openai.AsyncOpenAI` only for the judge — implying the bot itself uses Anthropic ("a runtime that itself uses Anthropic Claude") [#6]. The three accounts of which provider the bot calls do not agree.

## Per-dimension scorecard

| # | Dimension | Maturity finding (raw) | Key evidence | Top risk | Top open question |
|---|-----------|------------------------|--------------|----------|-------------------|
| 1 | LLM/prompts | Single mature 14.5 KB Russian `SYSTEM_PROMPT` + per-state guidelines + dynamic dev-prompt assembler + repetition/MI/safety heuristics; model hard-coded `gpt-4o`, no `temperature` set, module misleadingly named `claude_service` while using OpenAI exclusively [#1] | `claude_service.py:25-334` SYSTEM_PROMPT, `:541` MODEL, `:700` AsyncOpenAI, `:543-571` strict RESPONSE_SCHEMA [#1] | Hard-coded `gpt-4o` + default `temperature=1.0` + no JSON-mode fallback if Structured Outputs returns refusal → user sees "AI вернул некорректный ответ" [#1] | Why is `MODEL` hard-coded and what is the migration path? [#1] |
| 2 | Dialog logic | Most mature surface: 7-state dialogue enum, post-`addressed_to` handoff authority, single consolidated post-guard resolver, ~30 handoff tests, BOTH-mode buffering, loop-mode-shift bypass, resume voting [#2] | `claude_service.py:1626-1707` resolve_handoff_invariants, `tests/test_handoff.py` 492 LOC, transcript: 149 "теперь твой ход" hits in `tg/messages.html` [#2] | `pass_turn` callback and `cb_end_session` can race in-flight Claude calls without acquiring facilitator lock; voice path skips end-session-confirmation check [#2] | Is `SessionService.pass_turn` deliberately retained or dead UI? [#2] |
| 3 | Backend | Layered models/repos/services with Redis-primary + Postgres-snapshot; well-isolated tests (43 functions, not run); but baseline-only Alembic and two model imports point at files that don't exist in git [#3] | `gcs45_bot/bot/main.py:22-23` imports `SessionInsight`/`UserRequest`; `git ls-files gcs45_bot/bot/models/` returns 6 files, neither present; baseline migration covers 5 tables [#3] | `ImportError` at startup on any clean rebuild of this SHA + `relation "session_insights" does not exist` on any code path touching the missing models [#3] | Were `session_insight.py`/`user_request.py` deleted on purpose, or unpushed local files? [#3] |
| 4 | Frontend code (landing) | Next 16.1.6 / React 19 / Tailwind 4 single-page server component, deployed on Vercel (fra1, prerendered, edge-cached); empty `next.config.ts`; PostHog declared in `.env.example` but not installed; untracked `scripts/`, `campaigns/`, `docs/` referenced by modified `package.json` [#4] | `package.json:13-15` Next 16.1.6, live `x-vercel-cache: HIT` `age: 1844578` (~21 days); `grep posthog gcs-landing-v2/app/` → empty [#4] | `npm run campaign:links` fails on fresh clone because the script is untracked; live deploy and HEAD diverge [#4] | Is PostHog actually firing for landing visits, and from where? [#4] |
| 5 | PostHog analytics | Three Validation funnels + one dashboard exist and are well-structured; bot and landing are both sending events to PostHog (18 `bot_start`, 114 `landing_view`); but instrumentation source is not in git on either side and all funnels filtered to `campaign = "smoke-01"` (1 matching event) [#5] | API: all three insights have `properties.campaign in ['smoke-01']`; HogQL: `campaign` distribution `unknown=106, test-campaign=6, smoke-01=1, route_check=1` [#5] | `feedback_submitted` count = 0 lifetime; critical analytics code only in stale `.next/` sourcemaps; one rebuild from `main` and the entire pipeline is dead [#5] | Where does the deployed bot's PostHog code actually live? [#5] |
| 6 | Evals | None at HEAD: source, dataset, and 8 dated result folders all gone; only an orphan Python-3.14 `.pyc` survives in a Python-3.9 venv; no CI [#6] | `git ls-files gcs45_bot/evals/` returns empty; `__editable___pactatalk_bot_0_1_0_finder.py:NAMESPACES` lists 9 deleted paths; bytecode is `cpython-314` [#6] | All recent prompt-affecting commits (`a3d5d42`, `90cc912`, `f0586d9`, `407e904`, `bf361de`) shipped with no automated regression check on the eight axes the team previously measured [#6] | Is there a backup of `evals/pactatalk_eval.py` and `evals/scenarios/*` anywhere? [#6] |
| 7 | Deploy & infra | One Fly machine running in `fra`, last successful release v83 on 2026-03-30 (~86 days ago), Alembic baseline-only schema, no `.gitignore`, live keys in untracked `.env`, no `working-*` tags, no CI [#7] | `releases.txt:2` v83=2026-03-30; `secrets.txt:1-13` 12 secrets deployed; `gcs45_bot/.env:2,6,9` has live-looking tokens; `git tag` returns only `pacta-landing-*` [#7] | Restart or rebuild will fail because `bot/main.py` imports 3 files absent from git [#7] | Were the three missing files ever committed, and where are the source files now? [#7] |
| 8 | Product journey | End-to-end path works in production: landing → CTA → bot deep link → onboarding → session → resume; but conversion measurement is broken (no landing events, all funnels filtered to smoke-01) and post-session summary is degraded in every observed test [#8] | `tg/messages2.html` blocks 253, 262, 269, 274 all show "Данных для итога разговора недостаточно"; landing has 3 unparameterised CTAs to `t.me/PactaTalkBot`; resume works (blocks 257-258, 266-267) [#8] | Validation funnels likely read zero because landing fires no events — owner cannot tell if low conversion is signal or instrumentation gap [#8] | Are the 3 Validation funnels currently showing any data, and if yes, from where? [#8] |
| 9 | UX/design (landing) | Clean Russian single-page landing with strong narrative arc (pain → fix preview → mechanics → topics + reassurance → FAQ → CTA), valid HTML, good heading hierarchy; missing trust/proof, no privacy link, brand wordmark duplicated, OG drift, 2.4 MB hero PNG [#9] | `page.tsx:222-508` 7 sections; OG drift: `curl -I /opengraph-image` → 404, `/landing/og-card.png` → 200; no `priv|terms|cookie` in cached HTML [#9] | Next redeploy from HEAD breaks Telegram/Twitter social-preview cards because dynamic OG route 404s and the static PNG is not in `public/` [#9] | Is `/landing/og-card.png` or `app/opengraph-image.tsx` intended to win? [#9] |
| 10 | Distribution / marketing | Validation-wave runbook + UTM generator + sample config are well-designed (two-axis split, destructive normalization for predictable filters); but entire toolchain is untracked, only one channel pair (Telegram + founder DM), only one language, no `?start=` propagation [#10] | `git status` → `?? gcs-landing-v2/campaigns/ docs/ scripts/`; `validation-wave.sample.json` has 4 placements; CTAs use bare `t.me/PactaTalkBot` [#10] | Validation toolchain disappears on first `git stash`/`git clean`; deployed trackers are not in committed source [#10] | Has the validation wave actually launched, and with which links exactly? [#10] |
