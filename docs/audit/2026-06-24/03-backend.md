# Backend architecture (bot)

Pinned to commit `d46ea5f779abb10afae4148433f7853396eea92f` (per `docs/audit/2026-06-24/00-shared-header.md`). Working tree is dirty; only git-tracked files were treated as source of truth.

## 1. Scope covered

Examined (git-tracked files at the pinned SHA):

- `gcs45_bot/bot/models/` — all 6 files: `__init__.py`, `user.py`, `session.py`, `session_event.py`, `session_record.py`, `pair_resume.py`.
- `gcs45_bot/bot/repositories/` — `__init__.py`, `session_repo.py`, `user_repo.py`.
- `gcs45_bot/bot/services/` — `__init__.py`, `shared.py`, `loop_guard.py`, `resume_choice.py`, `session_service.py`. (`claude_service.py` deliberately skipped → specialist #1/#2.)
- `gcs45_bot/bot/utils/keyboards.py`.
- `gcs45_bot/migrations/env.py`, `gcs45_bot/migrations/script.py.mako`, `gcs45_bot/migrations/versions/20260319_0001_baseline_schema.py`.
- `gcs45_bot/tests/` — all 7 test files (inventory only, no test execution).
- `gcs45_bot/pyproject.toml`, `gcs45_bot/alembic.ini`.
- Cross-references via `grep` into `gcs45_bot/bot/handlers/`, `gcs45_bot/bot/main.py`, `gcs45_bot/bot/config.py` only to verify imports for repository symbols.

Not examined / out of scope:

- LLM/prompt internals of `bot/services/claude_service.py` → specialist #1.
- Dialog/FSM and handler logic (`bot/fsm/`, `bot/handlers/`) → specialist #2.
- Dockerfile, fly.toml, secrets, runtime → specialist #7.
- `evals/` → specialist #6.
- No test runs, no DB connection, no migration replay — static reading only.

## 2. Inventory

Models (`bot/models/`):

- `user.py` — `Base = DeclarativeBase` (single metadata root), `User` (table `users`), `Transaction` (table `transactions`, payment idempotency via unique `payload`).
- `session.py` — `SessionState` **dataclass** (not ORM). Holds runtime context: identities, names, `dialogue_state`, `mode`, `phase`, `waiting_for`, `consecutive_turns`, `pending_a_message`/`pending_b_message`, `resume_context`, `waiting_since`, `timeout_reminders_sent`, close-flow flags. Methods: `elapsed_minutes`, `response_deadline_exceeded`, `partner_name`, `is_active_speaker`.
- `session_record.py` — `SessionSnapshot` ORM (table `session_snapshots`, PK `session_id`), durable mirror of `SessionState` serialized as JSON in `payload` column plus denormalized columns.
- `session_event.py` — `SessionEvent` ORM (table `session_events`), append-only transcript with `role`, `speaker_label`, `content`, before/after `dialogue_state` and `waiting_for`, `next_speaker`, `addressed_to`, `risk_flag`.
- `pair_resume.py` — `PairResume` ORM (table `pair_resumes`, PK `pair_key` = sorted "lo:hi" of telegram IDs). Free function `make_pair_key(a, b)`.
- `models/__init__.py:1-4` re-exports only `SessionState`, `Base`, `User`, `Transaction` — `SessionSnapshot`, `SessionEvent`, `PairResume` are not exported.

Repositories (`bot/repositories/`):

- `user_repo.py` — `UserRepository` over `AsyncSession`. `get_or_create`, `get`, `get_transactions`, `delete_user_data` (GDPR), `count_users`.
- `session_repo.py` — `SessionRepository`. Holds both `Redis` and optional `async_sessionmaker`. Combines: Redis session/history KV, snapshot upsert + restore-on-miss, event append, pair_resume CRUD, **session_insight CRUD** (via missing `bot.models.session_insight`), **user_request CRUD** (via missing `bot.models.user_request`), GDPR fan-out `delete_all_user_session_data`.
- Keys: `session:{id}`, `user_session:{uid}`, `invite:{code}`, `history:{id}`, set `sessions:active`. TTLs: 7d sessions/history, 24h invites.

Services (non-LLM, non-FSM) (`bot/services/`):

- `shared.py:1-4` — module-level singleton `claude = ClaudeService()`. Process-wide shared state.
- `session_service.py` — orchestration over `SessionRepository`: `create_session` (generates 6-char invite code with collision retry), `join_session`, `start_session`, `pass_turn` (`BUG-PASS-TURN fix` noted at `session_service.py:95`), `end_session`, `notify_both` (best-effort with logged failure), `get_user_session`. Also exports formatting helpers `format_bot_dialog_message`, `format_participant_dialog_label`, `format_participant_dialog_block`, and `generate_invite_code`.
- `loop_guard.py` — pure detection of "stuck-loop" patterns. Keyword tables (`_DIRECT_LOOP_FEEDBACK_MARKERS`, `_LOW_ENERGY_MARKERS`, `_HARD_RISK_MARKERS`, `_REFLECTIVE_QUESTION_MARKERS`). Builds `LoopModeShift` dataclass. Reaches into `ClaudeService` private staticmethods (`_recent_user_turns`, `_contains_any`, `_extract_user_turn`, `_normalize_text`, `_assistant_looks_like_action_proposal`, `_ACTION_REJECTION_MARKERS`).
- `resume_choice.py` — Redis-backed two-party voting for resume continue/new-topic/flexible/alignment_pending. Keys `resume_vote:`, `resume_resolution:`, `resume_alignment_reply:`. TTL 24h.

Utils (`bot/utils/`):

- `keyboards.py` — 18 inline-keyboard factories for menus, onboarding, end-session flow, resume confirm, feedback/support, privacy data actions, admin inbox.

Migrations (`gcs45_bot/migrations/`):

- `env.py` — async Alembic env. Loads `.env`. Reads `DATABASE_URL` or `sqlalchemy.url`, raises if unset. Imports `Base`, `SessionSnapshot`, `SessionEvent`, `PairResume` to populate metadata. `compare_type=True`, `compare_server_default=True`.
- `versions/20260319_0001_baseline_schema.py` — single baseline revision, `down_revision = None`. Creates 5 tables: `pair_resumes`, `session_events`, `session_snapshots`, `transactions`, `users` with indexes.

Tests (`gcs45_bot/tests/`):

- 7 files, 3,256 LOC total. Test functions counted via `grep` (43 functions). Coverage by area:
  - `test_handoff.py` (492 LOC) — handoff/addressing invariants.
  - `test_end_session_flow.py` (609 LOC, 19 tests) — finish buttons, voice/text intents, summary delivery, survey.
  - `test_guardrail.py` (472 LOC, 13 tests) — server-side handoff guardrail, feedback flag, BOTH collection, throttling, setup-topic-split.
  - `test_loop_mode_shift.py` (263 LOC, 7 tests) — `loop_guard` decisions and `process_turn` short-circuit.
  - `test_session_resume.py` (568 LOC) — resume context, pair_resume, alignment vote flow.
  - `test_privacy_delete.py` (318 LOC, 5 tests) — Redis+DB cascade, full wipe orchestration.
  - `test_release_hygiene.py` (34 LOC, 2 tests) — only asserts `user.py`, `session_record.py`, `user_repo.py`, `shared.py` exist and have specs.

Packaging:

- `pyproject.toml:2` name = `pactatalk-bot`, version `0.1.0`, `requires-python = ">=3.9"`.
- Runtime deps: `aiogram>=3.13`, `openai>=1.50`, `redis[asyncio]>=5`, `sqlalchemy[asyncio]>=2`, `asyncpg>=0.30`, `alembic>=1.13`, `pydantic-settings>=2.6`, `pydantic>=2.9`, `structlog>=24.4`, `python-dotenv>=1`.
- Dev deps: `pytest>=8`, `pytest-asyncio>=0.24`, `pytest-mock>=3.14`. `asyncio_mode = "auto"`.
- Build backend: setuptools, `packages.find` from `.`.
- Two egg-info dirs present on disk (untracked): `gcs45_bot/gcs45_bot.egg-info/` and `gcs45_bot/pactatalk_bot.egg-info/` (legacy/rename artefact).

## 3. State of each piece

| Item | State | Evidence |
|------|-------|----------|
| `bot/models/user.py` (`Base`, `User`, `Transaction`) | works | `gcs45_bot/bot/models/user.py:10-36`; table created at `gcs45_bot/migrations/versions/20260319_0001_baseline_schema.py:85-97`. |
| `bot/models/session.py` (`SessionState` dataclass) | works | `gcs45_bot/bot/models/session.py:9-92`; serialized in `gcs45_bot/bot/repositories/session_repo.py:29-45`. |
| `bot/models/session_event.py` | works | `gcs45_bot/bot/models/session_event.py:12-27`; table at `migrations/versions/20260319_0001_baseline_schema.py:35-53`. |
| `bot/models/session_record.py` (`SessionSnapshot`) | works | `gcs45_bot/bot/models/session_record.py:11-23`; table at `migrations/versions/20260319_0001_baseline_schema.py:55-69`. |
| `bot/models/pair_resume.py` | works | `gcs45_bot/bot/models/pair_resume.py:11-27`; table at `migrations/versions/20260319_0001_baseline_schema.py:21-33`. |
| `bot/models/session_insight.py` | **missing on disk** | `git ls-files gcs45_bot/bot/models/` returns 6 files, none named `session_insight.py`. Imported at `gcs45_bot/bot/repositories/session_repo.py:15` and `gcs45_bot/bot/main.py:22`. `git log --all -- gcs45_bot/bot/models/session_insight.py` returns nothing — file was never tracked. |
| `bot/models/user_request.py` | **missing on disk** | Same evidence pattern. Imported at `gcs45_bot/bot/repositories/session_repo.py:19` and `gcs45_bot/bot/main.py:23`. Never tracked in git history. |
| Table `session_insights` | **no migration** | Referenced by `SessionRepository.save_session_insight` / `list_session_insights_for_user` (`session_repo.py:401-505`), but the only Alembic revision (`20260319_0001`) does not create it. |
| Table `user_requests` | **no migration** | Referenced by `SessionRepository.create_user_request` / `list_user_requests_for_user` (`session_repo.py:506-583`), but not created by `20260319_0001`. |
| `bot/repositories/session_repo.py` | partial | Compiles only if missing model files are recreated at runtime (e.g. by `ENABLE_DEV_SCHEMA_BOOTSTRAP` dev flow that calls `Base.metadata.create_all`). Static import will `ImportError` otherwise — `gcs45_bot/bot/repositories/session_repo.py:14-19`. |
| `bot/repositories/user_repo.py` | works | `gcs45_bot/bot/repositories/user_repo.py:12-59`. |
| `bot/services/shared.py` | works (with risk) | Module-level `claude = ClaudeService()` at `gcs45_bot/bot/services/shared.py:4`. Runs at import. |
| `bot/services/session_service.py` | works | `gcs45_bot/bot/services/session_service.py:40-123`. `pass_turn` explicitly references prior `BUG-PASS-TURN` fix at line 95. |
| `bot/services/loop_guard.py` | works (coupled) | `gcs45_bot/bot/services/loop_guard.py:110-173` calls 6+ private `ClaudeService._*` helpers. Tight coupling, but covered by `test_loop_mode_shift.py`. |
| `bot/services/resume_choice.py` | works | `gcs45_bot/bot/services/resume_choice.py:108-236`; covered by `test_session_resume.py`. |
| `bot/utils/keyboards.py` | works | `gcs45_bot/bot/utils/keyboards.py:1-159`. No test coverage in scope. |
| Alembic baseline migration | works | `gcs45_bot/migrations/versions/20260319_0001_baseline_schema.py` is the only revision; `down_revision = None`; covers 5 tables. |
| Alembic env wiring | works | `gcs45_bot/migrations/env.py:20-30` imports all 4 known ORM classes into metadata. |
| `pyproject.toml` packaging | works (minor) | `gcs45_bot/pyproject.toml:2` declares `pactatalk-bot`; project also ships legacy `gcs45_bot.egg-info/` (untracked, on disk only). |
| `tests/test_release_hygiene.py` | partial | `gcs45_bot/tests/test_release_hygiene.py:9-24` whitelist only 4 files / 4 modules — does **not** include `session_insight`, `user_request`, `session_event`, `pair_resume`, or any service module. |
| Test pytest config | works | `gcs45_bot/pyproject.toml:27-28` sets `asyncio_mode = "auto"`. |
| Tests overall (43 funcs) | unknown (not run) | File-level grep of `def test_*` across 7 files. Coverage gap: not executed by this auditor. |

## 4. Non-obvious decisions

- **`SessionState` is a dataclass, not an ORM row.** Durable form is the `SessionSnapshot.payload` JSON blob (`bot/models/session_record.py:21`) plus a small set of denormalized columns. Rationale visible in code: a single Redis JSON ↔ Postgres JSON path keeps `_serialize`/`_deserialize` symmetric (`bot/repositories/session_repo.py:29-45`) and lets the dataclass evolve without migrations.
- **Two storage backends are intentional.** Redis is authoritative for live state (`SESSION_TTL = 7d` at `bot/repositories/session_repo.py:21-23`); Postgres is for resume across TTL expiry and for post-mortem. `SessionRepository.get` (`session_repo.py:73-86`) explicitly rehydrates Redis from the snapshot on cache miss — that path is the documented continuity mechanism.
- **`pair_key` is sorted "lo:hi"** (`bot/models/pair_resume.py:24-27`). This makes pair lookup independent of which side initiated, and is used by GDPR LIKE-pattern fan-out at `session_repo.py:225-237` (`f"{user_id}:%"` and `f"%:{user_id}"`).
- **`session_factory` is optional everywhere.** Every Postgres-touching method early-returns when `self._session_factory is None` (`session_repo.py:153-154, 181-182, 212-213, 293, ...`). Rationale unclear — possibly to allow Redis-only test fixtures (used in `tests/test_privacy_delete.py:65-92` `FakeSessionFactory`).
- **`bot/services/shared.py` instantiates `ClaudeService` at import.** Single process-wide instance (`bot/services/shared.py:4`). Documented purpose in comment: "хранит историю диалогов". Side-effect happens on first import.
- **Alembic is the schema path; `create_all` is gated dev fallback.** `gcs45_bot/bot/main.py:47-61` shows `create_db` (`Base.metadata.create_all`) is only invoked from `maybe_bootstrap_schema` when `settings.enable_dev_schema_bootstrap` is true and `is_production` is false. Consistent with `gcs45_bot/CLAUDE.md` section 8.
- **`loop_guard` reaches into `ClaudeService` private API.** `bot/services/loop_guard.py:110, 117, 120, 144, 168, 171, 179, 181` use `ClaudeService._*` static helpers. Decision deliberate (extracted to a separate module while keeping shared classification primitives), but creates tight coupling.
- **Baseline migration creates 5 tables; repository code expects 7.** Decision rationale unclear — looks like model files were deleted (or never committed) and the migration was not extended. See section 5.
- **`pyproject.toml:5` declares `requires-python = ">=3.9"`** but the code uses 3.10+ syntax (`str | None` PEP 604 unions at e.g. `bot/services/loop_guard.py:106`, `bot/repositories/session_repo.py:438`). Effective floor is Python 3.10. Rationale unclear.

## 5. Risks & landmines

1. **`ImportError` at startup if `bot/main.py` is run from a clean checkout of this SHA.** `bot/main.py:22-23` does `from bot.models.session_insight import SessionInsight` and `from bot.models.user_request import UserRequest`, but neither file exists on disk or in git (`git ls-files gcs45_bot/bot/models/` returns 6 files). Same imports also gate `bot/repositories/session_repo.py:15-19`. Trigger: any fresh deploy or container build at this SHA. What happens: the process crashes before the event loop starts.
2. **Schema drift between repository code and migrations.** `SessionRepository` has CRUD methods for `session_insights` and `user_requests` tables (`session_repo.py:401-583`), but the only Alembic revision (`20260319_0001_baseline_schema.py`) does not create those tables and `migrations/env.py:20-23` does not import their models. Trigger: any code path that calls `save_session_insight`, `create_user_request`, `list_session_insights_for_user`, etc. (called from `bot/handlers/session.py:926`, `bot/handlers/privacy.py:67-69`, `bot/handlers/admin.py:51`). What happens: SQLAlchemy raises `ProgrammingError: relation "session_insights" does not exist` (only if startup imports above are first fixed).
3. **Release hygiene test does not protect against the above.** `tests/test_release_hygiene.py:9-24` checks only 4 files and 4 modules; missing models would not fail it. Trigger: PR review relying on this test. What happens: false confidence.
4. **`bot/services/shared.py` side-effect on import.** A module-level `ClaudeService()` instance (`shared.py:4`) — anything that imports `shared` performs the construction. If that constructor ever touches network/env/secrets it executes during static analysis and during test collection.
5. **No revision history beyond baseline.** A single Alembic revision with `down_revision = None` (`migrations/versions/20260319_0001_baseline_schema.py:15`) means no audit trail of schema evolution — every later table change must be a manual edit of the baseline or a new revision.
6. **`SessionState` ↔ snapshot serialization tolerates unknown fields but silently drops them** (`session_repo.py:44-45` filters by `dataclasses.fields(SessionState)`). Trigger: rolling back a deploy that added a dataclass field. What happens: dropped fields revert to dataclass defaults with no warning.
7. **Active-sessions set is best-effort.** `ACTIVE_SESSIONS_KEY = "sessions:active"` is mutated everywhere but `list_active_sessions` (`session_repo.py:281-290`) self-heals on stale members. Trigger: Redis flush mid-flight or unclean shutdown. What happens: stale set entries linger until first listing.
8. **`pyproject.toml` python floor lies (3.9 vs actual 3.10+ syntax).** Trigger: install on a 3.9 interpreter. What happens: `SyntaxError` on PEP 604 unions at import time.
9. **`gcs45_bot/pactatalk_bot.egg-info/` and `gcs45_bot/gcs45_bot.egg-info/` both exist on disk** — duplicate package metadata under two names. Trigger: anything resolving distribution metadata via importlib.metadata may pick whichever sorts first.
10. **`session_service.pass_turn` documents a fixed bug inline** (`session_service.py:95`): "BUG-PASS-TURN fix: waiting_for controls is_active_speaker". No regression test in scope is visibly named for this — coverage gap (not verified).

## 6. Open questions for the owner

1. Were `bot/models/session_insight.py` and `bot/models/user_request.py` deleted on purpose, or are they un-pushed local files? They are imported by `main.py` and `session_repo.py` but never tracked in git.
2. If those models are intended to ship, where are the migrations for `session_insights` and `user_requests` tables? The pinned SHA contains only the `20260319_0001` baseline.
3. What is the deploy/runtime story for the `ENABLE_DEV_SCHEMA_BOOTSTRAP` flag in production? `main.py:53-60` says it is ignored in production with a warning — is production actually running on Alembic-applied schema only?
4. Is the `requires-python = ">=3.9"` floor in `pyproject.toml:5` intentional, given PEP 604 union syntax is used throughout?
5. Why are both `gcs45_bot.egg-info/` and `pactatalk_bot.egg-info/` shipped on disk? Is the package being renamed?
6. Is `bot/services/shared.py`'s module-level `ClaudeService()` singleton intentional for test imports, or should it be lazy/injected?
7. Is there a deliberate reason `loop_guard` calls `ClaudeService` private staticmethods rather than re-exporting them?
8. What does the current Postgres schema actually look like in prod / staging — is `session_insights` already created there out-of-band?

## 7. Out-of-scope notes

- Recreating the two missing model files and adding a follow-up Alembic revision for `session_insights` + `user_requests` would close items 1–3 in section 5 in one change.
- `tests/test_release_hygiene.py` could be extended to whitelist every module the runtime actually imports from `bot/main.py`.
