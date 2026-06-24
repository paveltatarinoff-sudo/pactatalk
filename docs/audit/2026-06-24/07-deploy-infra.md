# Deploy & infra

Pinned commit: `d46ea5f779abb10afae4148433f7853396eea92f` (per `docs/audit/2026-06-24/00-shared-header.md`).

## 1. Scope covered

Examined:

- `gcs45_bot/fly.toml`, `gcs45_bot/Dockerfile`, `gcs45_bot/pyproject.toml`
- `gcs45_bot/alembic.ini`, `gcs45_bot/migrations/env.py`, `gcs45_bot/migrations/versions/20260319_0001_baseline_schema.py`
- `gcs45_bot/.env`, `gcs45_bot/.env.example`
- `gcs45_bot/bot/config.py`, `gcs45_bot/bot/main.py` (only for env-var/startup wiring; bot logic itself is out of scope)
- `_deploy_gcs45_bot_alembic/` (git worktree pointer + its `gcs45_bot/CLAUDE.md`, `bot/main.py`, `alembic.ini`, `migrations/`, `scripts/`)
- All pre-captured fly data: `docs/audit/_data/fly/{status,secrets,config,machines,recent-logs,releases}.txt`/`.json`
- `git log` for migration history, recent deploy-relevant changes, and tracing missing files across all branches/tags

Not examined / out of scope:

- Bot code structure, prompt content, handler logic → specialist #3
- Landing Vercel deploy → specialist #4
- Telegram bot UX, PostHog instrumentation correctness → specialists #2 / #5
- Neon Postgres dashboard, Upstash Redis dashboard (no captured data; only inferred from env URLs)
- CI/CD pipeline — none found in repo (`.github/`, `.gitlab-ci`, etc. absent under `gcs45_bot/`)

## 2. Inventory

- **Fly app** `pactatalk-bot` in region `fra` (Frankfurt). One shared-cpu-1x / 512 MB machine `d896e24a069058`, name `twilight-sky-5119` (`docs/audit/_data/fly/status.txt:1-9`, `machines.txt:6`).
- **Build**: Dockerfile-based, `python:3.11-slim`, `pip install -e .` then `COPY . .`, entrypoint `python -m bot.main` (`gcs45_bot/Dockerfile:1-10`).
- **fly.toml**: app/region, `release_command = "python -m alembic upgrade head"`, http_service on internal_port 8080, `force_https=true`, `auto_stop_machines=false`, `min_machines_running=1`, concurrency soft=20/hard=25 (`gcs45_bot/fly.toml:1-22`).
- **Runtime entrypoint** `bot/main.py`: aiohttp webhook server on `0.0.0.0:8080` with handler at `/webhook` and `/health` endpoint when `WEBHOOK_URL` set, else polling fallback (`gcs45_bot/bot/main.py:190-232`).
- **Settings layer**: `pydantic-settings` `Settings` class reading `.env` + env vars; declares `bot_token`, `database_url`, `redis_url`, `webhook_url`, `webhook_secret`, `openai_api_key`, `admin_ids`, `support_inbox_ids`, `payment_provider_token`, `env`, `log_level`, `post_session_survey_url`, `enable_dev_schema_bootstrap`, plus several `openai_*` / `*_timeout_seconds` knobs (`gcs45_bot/bot/config.py:7-72`).
- **Alembic**: `script_location = migrations`, `sqlalchemy.url` left blank, resolved at runtime from `DATABASE_URL` env (`gcs45_bot/alembic.ini:1-4`, `migrations/env.py:33-39`). `env.py` builds async engine with `NullPool`, imports `Base` from `bot.models.user` plus `SessionSnapshot`, `SessionEvent`, `PairResume` for autogenerate metadata (`migrations/env.py:20-23,68-81`).
- **Migrations**: single revision `20260319_0001_baseline_schema` creating 5 tables — `pair_resumes`, `session_events`, `session_snapshots`, `transactions`, `users` (`gcs45_bot/migrations/versions/20260319_0001_baseline_schema.py:14-97`). `down_revision = None` — it is the only migration in the chain.
- **Fly secrets** (12 deployed, names from `docs/audit/_data/fly/secrets.txt:1-13`): `ADMIN_IDS`, `BOT_TOKEN`, `DATABASE_URL`, `ENV`, `OPENAI_API_KEY`, `REDIS_URL`, `WEBHOOK_SECRET`, `WEBHOOK_URL`, `SUPPORT_INBOX_IDS`, `POST_SESSION_SURVEY_URL`, `POSTHOG_API_KEY`, `POSTHOG_HOST`.
- **Local `.env`** (`gcs45_bot/.env:1-29`): contains live-looking `BOT_TOKEN` for bot id `8461119036` (same id observed in deployed-log line `docs/audit/_data/fly/recent-logs.txt:62` `bot id=8461119036`), live `ANTHROPIC_API_KEY` and `OPENAI_API_KEY`, plus localhost `REDIS_URL`/`DATABASE_URL`. File is untracked but **no `.gitignore` exists** in repo root or in `gcs45_bot/` (verified with `ls .gitignore` / `git check-ignore`).
- **Release history** (`docs/audit/_data/fly/releases.txt:1-26`): 83 versions, last successful `v83` on 2026-03-30 11:18 UTC by `paveltatarinoff@gmail.com`. Two failed releases visible (`v77` 2026-03-26, `v59`/`v65` earlier). No `working-*` git tags exist (only `pacta-landing-*` tags).
- **Currently running image**: `pactatalk-bot:deployment-01KMZ7D5FP2Z1TCTMYSTBA86T4`, machine last updated 2026-05-28T01:09:25Z (`status.txt:5`, `machines.txt:6`). Note: `releases.txt` last entry is v83 / Mar 30, but machine updated May 28 — likely an unattended Fly platform restart, not a re-release.
- **Sibling worktree** `_deploy_gcs45_bot_alembic/` — a git worktree pointing to a *different* repo (`/Users/pashkamoroz/Documents/Ai family coach/.git/worktrees/_deploy_gcs45_bot_alembic`, from `.git` pointer). Contains an older snapshot of `gcs45_bot/` from Mar 19 with the same `alembic.ini`, same `env.py`, but a `bot/main.py` that uses `Base.metadata.create_all` unconditionally (`_deploy_gcs45_bot_alembic/gcs45_bot/bot/main.py:103`) and a slightly different `CLAUDE.md` describing server-side handoff override (now removed in main).

## 3. State of each piece

| Item | State | Evidence |
|------|-------|----------|
| Fly app `pactatalk-bot`, machine `d896e24a069058` | works (running) | `docs/audit/_data/fly/status.txt:9` STATE=`started`; `recent-logs.txt:63-100` shows live webhook traffic and heartbeats through 2026-06-24T11:06Z |
| Webhook `POST /webhook` returning 200 | works | `docs/audit/_data/fly/recent-logs.txt:63` `POST /webhook HTTP/1.1" 200` |
| `/health` endpoint | works (added in main but never observed in captured logs) | code at `gcs45_bot/bot/main.py:195-205`; no `/health` request in `recent-logs.txt` (only `/webhook`) |
| Alembic migration chain | partial — schema covers 5 tables, code imports 2 extra models with no migration | baseline at `migrations/versions/20260319_0001_baseline_schema.py:21-97` only creates `pair_resumes,session_events,session_snapshots,transactions,users`; `bot/main.py:22-23` imports `SessionInsight` and `UserRequest` |
| `bot/main.py` import graph | **broken at HEAD** — would crash on restart | `bot/main.py:15` imports `bot.handlers.menu` but `bot/handlers/menu.py` is absent (`ls bot/handlers/` returns only `admin,facilitator,privacy,session,start,__init__`); `bot/main.py:22-23` imports `bot.models.session_insight` and `bot.models.user_request` which do not exist on disk and do not exist in any branch/tag (`git log --all -- <paths>` returns empty) |
| `.pyc` artifacts for missing modules | present locally only | `bot/handlers/__pycache__/menu.cpython-314.pyc` (Mar 25 18:12), `bot/models/__pycache__/{session_insight,user_request}.cpython-314.pyc` — proves `.py` files existed on dev machine when v83 was built but were never committed |
| Running image vs git HEAD | divergent | image tag `01KMZ7D5FP2Z1TCTMYSTBA86T4` from Mar 30; HEAD has 7+ commits since (`a3d5d42`, `90cc912`, `611d952`, `f0586d9`, `407e904`, `bf361de`, audit commits) — none deployed |
| Fly secret `OPENAI_API_KEY` | deployed | `secrets.txt:6`; required by `bot/main.py:181-182` (hard `RuntimeError` if missing) |
| Fly secret `BOT_TOKEN` | deployed | `secrets.txt:3`; bot id `8461119036` confirmed in `recent-logs.txt:62` |
| Fly secret `DATABASE_URL` | deployed | `secrets.txt:4`; consumed by `migrations/env.py:34` and `bot/config.py:21` |
| Fly secret `REDIS_URL` | deployed | `secrets.txt:7`; consumed by `bot/config.py:20` |
| Fly secrets `WEBHOOK_URL`, `WEBHOOK_SECRET` | deployed | `secrets.txt:8-9`; passed to `bot.set_webhook(..., secret_token=...)` at `bot/main.py:210` |
| Fly secrets `ADMIN_IDS`, `SUPPORT_INBOX_IDS`, `POST_SESSION_SURVEY_URL`, `ENV` | deployed | `secrets.txt:2,5,10,11`; all referenced in `bot/config.py` |
| Fly secrets `POSTHOG_API_KEY`, `POSTHOG_HOST` | **deployed but unused** | `secrets.txt:12-13`; `grep -rE "POSTHOG\|posthog" gcs45_bot/bot/` returns no matches; `Settings` in `bot/config.py:7-72` does not declare them |
| `PAYMENT_PROVIDER_TOKEN` | declared in code, absent from fly secrets | `bot/config.py:12` `payment_provider_token: str = ""`; not in `secrets.txt` — would default to empty (likely intentional; payments not in baseline) |
| `release_command: python -m alembic upgrade head` | works on baseline schema | `fly.toml:8`; would run successfully against `20260319_0001` baseline; **never tested against post-Mar-26 model additions** because no later migration exists |
| `enable_dev_schema_bootstrap` fallback | gated off in prod | `bot/main.py:52-60` early-returns when `is_production`; safe |
| `.env` file safety | **uncontrolled** | `gcs45_bot/.env` exists with live keys; no `.gitignore` in repo root, no `gcs45_bot/.gitignore`; `git status` shows it as `??` (untracked) — one `git add .` away from being committed |
| `working-YYYY-MM-DD` rollback tags (per global rule) | missing | `git tag` lists only `pacta-landing-baseline-v1`, `pacta-landing-final-v1` — no `working-*` tags |
| `_deploy_gcs45_bot_alembic/` worktree | stale, orphaned reference to another repo | `.git` pointer at line 1 points to `/Users/pashkamoroz/Documents/Ai family coach/.git/worktrees/...` — that path is outside this project root; files last touched Mar 19 |

## 4. Non-obvious decisions

- **Release-command-only migrations, no separate job.** `fly.toml:8` runs `python -m alembic upgrade head` as Fly release command, so migrations run inside a one-off release machine before the app machine starts. Rationale (visible in `gcs45_bot/CLAUDE.md` section 8): Alembic is now the baseline schema path, `create_all` demoted to dev-only via `ENABLE_DEV_SCHEMA_BOOTSTRAP`. Trade-off: a failed migration blocks deploy entirely (which is desired) but also means schema must be reproducible from baseline + future revisions — currently only baseline exists.
- **Empty `sqlalchemy.url` in alembic.ini.** `alembic.ini:4` `sqlalchemy.url =` is intentionally blank; `env.py:33-39` resolves it from `DATABASE_URL` env var at runtime. Lets the same alembic config work locally with `.env` and in fly release machine with fly secret.
- **Manual SSL-mode handling for Neon.** `bot/main.py:150-154` strips `?ssl=require` from the URL and passes `ssl="require"` via `connect_args` because asyncpg doesn't parse `ssl=` in the URL. Rationale visible in inline comment: "Neon PostgreSQL требует SSL". This is duplicated only in `main.py`, not in `migrations/env.py` — see Risks.
- **`auto_stop_machines=false` + `min_machines_running=1`.** `fly.toml:13-14` keeps the machine warm. Inline comment "бот должен работать постоянно". Cost trade-off accepted to avoid Telegram webhook cold-start latency.
- **Region `fra` choice.** `fly.toml:2` comment "близко к Neon eu-central и Upstash EU" — co-locates with assumed managed DB/Redis providers. Cannot verify managed providers from inventory (no DB host captured).
- **`force_https=true` + webhook_secret.** Belt-and-braces: Fly terminates TLS for `force_https` (`fly.toml:12`), aiogram `SimpleRequestHandler(... secret_token=settings.webhook_secret)` (`bot/main.py:206`) additionally verifies Telegram's `X-Telegram-Bot-Api-Secret-Token` header.
- **`shared-cpu-1x / 512MB`.** `fly.toml:20-22`. Smallest paid tier; matches a 4-active-session steady state seen in heartbeats (`recent-logs.txt:66-100` `active_session_count: 4`). No memory metric in captured data.
- **Single migration file 8 days old.** `git log -- gcs45_bot/migrations/versions/` shows only `30079af Add Alembic scaffold and baseline schema revision` (Mar 19). All subsequent model additions (e.g. import of `SessionInsight`, `UserRequest`) carry no companion migration — rationale unclear.

## 5. Risks & landmines

1. **Import failure on restart (P0).** `bot/main.py:15,22-23` (HEAD `d46ea5f`) imports `bot.handlers.menu`, `bot.models.session_insight`, `bot.models.user_request`. None of these files exist in the working tree, in any branch, or in any tag (`git log --all -- <paths>` empty). Only `.pyc` artifacts remain (`bot/handlers/__pycache__/menu.cpython-314.pyc`, `bot/models/__pycache__/{session_insight,user_request}.cpython-314.pyc`, timestamps Mar 24-26). Trigger: any `fly deploy` from this tree, any `git clone && fly deploy` from CI, any container rebuild. Effect: `ImportError` at startup, release machine exits non-zero, deploy fails. Currently masked only because the running image was built locally before the files vanished and Fly is not restarting it.
2. **Schema drift between Alembic and runtime models.** `migrations/env.py:20-23` imports only 4 model modules for autogenerate target; `bot/main.py:22-23` imports 2 additional model modules (`session_insight`, `user_request`) that are not in any migration. `down_revision = None` means baseline is the only revision. Trigger: a fresh DB (e.g. recreating Neon branch) would not have these tables; any code path that touches `SessionInsight` or `UserRequest` would error with "relation does not exist". Cannot determine if such code paths are reachable — out of scope.
3. **Plaintext live secrets in untracked `.env` with no `.gitignore`.** `gcs45_bot/.env:2,6,9` contains `BOT_TOKEN` (bot id matches production), `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`. Neither `.gitignore` nor `gcs45_bot/.gitignore` exists. Trigger: a `git add .` or `git add gcs45_bot/` while the file is untracked. Effect: secrets in git history → potentially public if repo is pushed. Severity inflated by the file containing what appears to be a real Anthropic + OpenAI key, not the placeholder values in `.env.example`.
4. **Alembic env.py does not handle Neon SSL the way main.py does.** `migrations/env.py:33-81` passes `DATABASE_URL` straight into `async_engine_from_config` with no `connect_args={"ssl": "require"}` and no stripping of `?ssl=require`. `main.py:150-154` has explicit handling. Trigger: if the deployed `DATABASE_URL` secret contains `?ssl=require` or points to `*.neon.tech`, the release command may fail to connect even though the runtime app would. Cannot verify without secret value; could be why some past releases failed (`v59`, `v65`, `v77`). [unverified]
5. **No `working-*` rollback tags.** Per the global rule in `~/.claude/CLAUDE.md`, successful states should be tagged `working-YYYY-MM-DD`. `git tag` shows only landing-related tags. Trigger: if a bad deploy ships, fastest rollback is `fly releases rollback` (Fly-side), not git — but the git tree has no known-good marker, so rebuilding the current working image from source is non-trivial.
6. **Deploy age + dependency bit-rot.** Last successful release `v83` on 2026-03-30 (`releases.txt:2`); audit date 2026-06-24 → ~86 days unredeployed. Dockerfile pins `python:3.11-slim` (no patch digest), `pyproject.toml` uses `>=` for all deps (no lock file: no `requirements.txt`, `poetry.lock`, `uv.lock`). Trigger: next rebuild may pull different transitive deps; combined with risk #1, any forced restart that triggers a rebuild is a coin flip.
7. **`POSTHOG_*` secrets deployed but never read by code.** `secrets.txt:12-13` lists `POSTHOG_API_KEY`, `POSTHOG_HOST`; `grep -rE "POSTHOG\|posthog" gcs45_bot/bot/` returns no hits, and `Settings` does not declare them. Trigger: no immediate failure, but indicates either dead config or that PostHog ingestion isn't actually wired on the bot side (relevant cross-check for specialist #5).
8. **No CI / no automated migration check.** No `.github/workflows/`, no `.gitlab-ci.yml`, no Fly remote-builder check that the working tree even imports cleanly. Trigger: risks #1 and #2 are only catchable by running the bot or running `alembic upgrade head` locally; nothing enforces this before `fly deploy`.
9. **Single machine, no replica.** `machines.txt:6` shows one machine; `fly.toml:14` `min_machines_running=1`. Trigger: machine eviction / region issue → bot down with no failover. Acceptable for current scale but a single point of failure.
10. **Stale sibling worktree `_deploy_gcs45_bot_alembic/`.** Its `.git` pointer references a project root (`/Users/pashkamoroz/Documents/Ai family coach/.git`) that is not this repo. Trigger: confusion — someone editing under `_deploy_gcs45_bot_alembic/` thinking it ships to fly. It does not; nothing in `fly.toml`/`Dockerfile` references this path.
11. **Webhook secret defaults to empty.** `bot/config.py:25` `webhook_secret: str = ""`. If the fly secret were ever unset, aiogram would accept any caller. Currently deployed (`secrets.txt:8`), so not active risk; included as configuration fragility.
12. **Long stack-trace in recent logs.** `recent-logs.txt:1-62` shows an unfinished SQLAlchemy stack from `bot/handlers/start.py:136 cmd_start` → `bot/repositories/user_repo.py:36`. Log capture is truncated at the top, so root exception type/message is not visible. Bot continues serving (`Update id=675671060 is handled. Duration 3355 ms`), suggesting handled error, but worth surfacing — likely belongs to specialist #3.

## 6. Open questions for the owner

1. Were `bot/models/session_insight.py`, `bot/models/user_request.py`, and `bot/handlers/menu.py` ever committed? They're imported by `bot/main.py` at HEAD but exist nowhere in git. The deployed v83 image must have been built locally with them present. Where are the source files now?
2. Is the running deployment expected to be safe to restart today? Given the import errors above, a manual `fly machine restart` could fail to come back up.
3. Why is there a single Alembic migration covering Mar 19 schema, with no follow-up migration for `SessionInsight` / `UserRequest`? Was a migration drafted and lost, or is the intent that these models never reach Postgres?
4. Are the `POSTHOG_API_KEY` / `POSTHOG_HOST` fly secrets reserved for future use, or were they at some point read by code that is now gone?
5. Was the `gcs45_bot/.env` file deliberately left untracked without a `.gitignore`? If the keys in it are real production credentials, were they meant to be stored elsewhere (1Password, fly secrets only)?
6. What lives at `/Users/pashkamoroz/Documents/Ai family coach/` — is `_deploy_gcs45_bot_alembic/` still in use as a deploy staging worktree, or is it abandoned?
7. Releases `v59`, `v65`, `v77` are marked `failed` in `releases.txt`. Do you recall why, and was the cause in `release_command` (alembic) or in build?
8. How do you deploy today — manual `fly deploy` from your laptop in `gcs45_bot/`, or through some script not in this repo?

→ Bot code structure (start.py / facilitator.py / claude_service.py details): see specialist #3.
→ Landing Vercel deploy: see specialist #4.
→ PostHog event ingestion correctness: see specialist #5.

## 7. Out-of-scope notes (optional)

- Add `.gitignore` with at minimum `.env`, `__pycache__/`, `.venv/`, `*.egg-info/` at repo root.
- Either commit the missing `session_insight.py` / `user_request.py` / `menu.py` files, or remove the imports from `bot/main.py`.
- Add `working-YYYY-MM-DD` tag at the SHA that built image `01KMZ7D5FP2Z1TCTMYSTBA86T4` (currently unknown — needs owner).
