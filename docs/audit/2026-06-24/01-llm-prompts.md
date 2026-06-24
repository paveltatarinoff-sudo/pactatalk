# LLM / prompt engineering

Pinned commit: `d46ea5f779abb10afae4148433f7853396eea92f` (per `docs/audit/2026-06-24/00-shared-header.md`).

## 1. Scope covered

Examined:
- `gcs45_bot/bot/services/claude_service.py` (full file, 2073 LOC) — sole LLM service module: prompt text, prompt composition, model selection, decoding params, structured-output schemas, retry/timeout, repetition/MI cooldown detection, state-effect resolution, handoff invariants, resume-context generator, summary/insight generators, Whisper transcription.
- `gcs45_bot/bot/services/shared.py` (4 LOC) — exports a singleton `claude` instance of `ClaudeService`.
- `gcs45_bot/bot/services/loop_guard.py`, `gcs45_bot/bot/services/resume_choice.py`, `gcs45_bot/bot/services/session_service.py` (filenames + grep) — no LLM/prompt calls.
- `gcs45_bot/bot/handlers/facilitator.py` (1598 LOC) — scanned for prompt-text constants and LLM call-sites. Two non-LLM, hand-written user prompts (`_setup_topic_split_prompt`, `_setup_topic_seed_prompt` at lines 484–537). LLM calls only via `_claude.get_facilitator_response`, `_claude.transcribe_voice`, `_claude.clear_history`.
- `gcs45_bot/bot/handlers/session.py` — only call sites: `_claude.generate_session_insight` (line 924), `_claude.generate_resume_context` (line 948).
- `gcs45_bot/bot/config.py` — OpenAI-related env knobs.
- `gcs45_bot/CLAUDE.md` — operational context doc.
- `gcs45_bot/scripts/prompt_harness.py` (read), `gcs45_bot/scripts/prompt_scenarios.json` (existence only).

Not examined / out of scope:
- Where the prompt is *called from* / dialog orchestration → specialist #2.
- Eval/scoring of LLM outputs → specialist #6.
- Production LLM logs and token bills (PostHog/Fly) → specialist #7.

## 2. Inventory

- **Model**: hard-coded constant `MODEL = "gpt-4o"` (`claude_service.py:541`). Used by all four chat call-sites (facilitator turn, resume context, plain summary, structured insight). Despite module name `claude_service` and class `ClaudeService`, the runtime provider is OpenAI only (`AsyncOpenAI` at line 700).
- **Voice model**: `"whisper-1"` (`claude_service.py:1900`), audio transcription via OpenAI.
- **System prompt**: single inline triple-quoted string `SYSTEM_PROMPT` (`claude_service.py:25–334`). ~14.5 KB, ~2 121 words, 310 lines. Russian-language. Contains: 4-step algorithm, 5 facilitation functions, 11 facilitation rules, format rules, banned canned phrases, examples, safety + safety-adjacent triggers, escalation guidance, micro-interventions vocabulary, state-priority ordering, addressing instructions.
- **Per-state developer prompt**: `STATE_GUIDELINES: dict[str, str]` (`claude_service.py:337–519`) — one block per dialogue state (`SETUP`, `CLARIFY`, `DEESCALATE`, `DEEPEN`, `OPTIONS`, `AGREE`, `CHECK_IN`).
- **Resume-mode SETUP override**: `STATE_GUIDELINES_RESUME` (`claude_service.py:521–537`) — replaces SETUP block when `session.resume_context` is present.
- **Dynamic developer prompt builder**: `_developer_prompt_for_state` (`claude_service.py:793–1054`) — assembles per-turn: state header, resume block, last-answer hint, joint-mode hint, anti-generic ("grounding") hint, consecutive-speaker info, anti-repeat warning, MI cooldown notice, address-feedback hint, addressing rule, recent handoff context. Concatenated with `SYSTEM_PROMPT` into a single `system` message (`claude_service.py:1744–1750`).
- **Response schema (Structured Outputs)**: `RESPONSE_SCHEMA` (`claude_service.py:543–571`) — strict JSON schema with `message`, `next_speaker` ∈ {A,B,BOTH}, `risk_flag`, `addressed_to` ∈ {A,B,BOTH}, `next_state` ∈ {SETUP,CLARIFY,DEESCALATE,DEEPEN,OPTIONS,AGREE,CHECK_IN}.
- **Session-insight schema**: `SESSION_INSIGHT_SCHEMA` (`claude_service.py:573–590`) — `topic`, `clarified_text`, `agreement_text`, `summary_text`.
- **Resume-context prompt**: inline f-string in `generate_resume_context` (`claude_service.py:1924–1942`). Free-form text completion, separate `system` message: "Ты помощник, который составляет краткие контексты диалогов для фасилитатора." (line 1952).
- **Summary prompt**: inline string in `generate_summary` (`claude_service.py:1972–1978`). Reuses full `SYSTEM_PROMPT` as system message (line 1987).
- **Session-insight prompt**: inline string in `generate_session_insight` (`claude_service.py:2009–2018`). Also reuses full `SYSTEM_PROMPT` as system message (line 2029).
- **Context strategy**: Redis-backed history per `session_id`, truncated to `MAX_CONTEXT_MESSAGES = 30` (`claude_service.py:539, 1715–1717`). Each message capped to `MAX_MESSAGE_LENGTH = 2000` chars (`claude_service.py:23, 1714`). Full system message + last 30 history items sent on every turn. Resume-context generator uses last 20 history items (`claude_service.py:1953`).
- **Decoding params per call-site**:
  - Facilitator turn: `max_tokens=1024`, `response_format=RESPONSE_SCHEMA`, `timeout=settings.openai_timeout_seconds` (`claude_service.py:1754–1763`).
  - Resume context: `max_tokens=300`, no `response_format` (`claude_service.py:1947–1956`).
  - Summary: `max_tokens=512`, no `response_format` (`claude_service.py:1982–1992`).
  - Session insight: `max_tokens=500`, `response_format=SESSION_INSIGHT_SCHEMA` (`claude_service.py:2023–2034`).
  - **No `temperature`, `top_p`, `presence_penalty`, `frequency_penalty`, or `seed` set anywhere** (grep at `claude_service.py:` returned only `max_tokens` matches). OpenAI defaults apply (gpt-4o default `temperature=1.0`).
- **Retry/error handling**: `_with_retry` (`claude_service.py:718–764`). Retries on `RateLimitError`, `APIConnectionError`, `APITimeoutError`, `APIStatusError` (5xx/429). Linear backoff: `base * attempt + uniform(0,0.5)`. Configurable: `openai_timeout_seconds=30`, `openai_max_retries=3`, `openai_retry_base_delay_seconds=1.5` (`config.py:31–33`).
- **Hand-written (non-LLM) Telegram prompts in handler**: `_setup_topic_split_prompt`, `_setup_topic_seed_prompt` (`handlers/facilitator.py:484–537`). Static HTML strings sent to users — not LLM-generated.
- **Prompt-harness**: `scripts/prompt_harness.py` exists, loads scenarios from `prompt_scenarios.json`, drives `ClaudeService.get_facilitator_response` through an in-memory repo. Referenced by `CLAUDE.md:166` as the canonical prompt-regression tool.
- **Repetition / MI-cooldown apparatus** (prompt-side guard, compiled inside `_developer_prompt_for_state`):
  - `_CANNED_INTERVENTION_MARKERS`, `_CANNED_PHRASING_MARKERS` (`claude_service.py:1339–1351`).
  - `_GROUNDING_REQUIRED_MARKERS`, `_SPECIFIC_MOMENT_MARKERS` (`claude_service.py:1352–1363`).
  - `_SOFT_MI_MARKERS_SHORT` (cooldown 4 turns), `_SOFT_MI_MARKERS_LONG` (cooldown 6 turns) (`claude_service.py:1366–1386`).
  - `_VULNERABILITY_MARKERS`, `_SAFETY_ADJACENT_MARKERS` (`claude_service.py:1318–1338`).
  - `_ACTION_REJECTION_MARKERS`, `_ACTION_PROPOSAL_MARKERS` (`claude_service.py:1477–1487`).
- **Name handling**: cyrillic↔latin transliteration tables (`claude_service.py:592–693`) for `_starts_with_partner_name` address-conflict observation (logged only, no rewrite — `claude_service.py:1796–1809`).

→ how this prompt is *called from* orchestration / dialog flow: see specialist #2.

## 3. State of each piece

| Item | State | Evidence |
|------|-------|----------|
| Model = `gpt-4o` (constant) | works, hard-coded | `claude_service.py:541`; no env override |
| Whisper transcription = `whisper-1` | works, hard-coded | `claude_service.py:1900` |
| `SYSTEM_PROMPT` (~14.5 KB inline) | works, monolithic | `claude_service.py:25–334`, 310 lines |
| `STATE_GUIDELINES` per-state | works | `claude_service.py:337–519` |
| `STATE_GUIDELINES_RESUME` | works | `claude_service.py:521–537`; applied only when `session.resume_context` AND `effective_state=="SETUP"` (line 1028) |
| Dynamic dev-prompt assembler | works | `claude_service.py:793–1054`; covered by `prompt_harness.py` per `CLAUDE.md:166` |
| `RESPONSE_SCHEMA` (strict) | works | `claude_service.py:543–571`, used at 1757 |
| `SESSION_INSIGHT_SCHEMA` (strict) | works; falls back to `generate_summary` on any exception | `claude_service.py:573–590, 2020–2055` |
| `temperature` / decoding params | partial — **none set** anywhere | grep result above; OpenAI default applies |
| `max_tokens` budgets | works | 1024/300/512/500 across call-sites |
| Context window strategy (`MAX_CONTEXT_MESSAGES=30`, per-msg 2000 chars) | works | `claude_service.py:23, 539, 1714–1717` |
| Retry/timeout (`_with_retry`) | works | `claude_service.py:718–764`; configurable via `config.py:31–33` |
| Per-turn repetition warning | works | `_detect_bot_repetition` `claude_service.py:1388–1475`; injected `claude_service.py:919–928` |
| Soft-MI cooldown | works | `claude_service.py:929–936, 1444–1459` |
| Vulnerability / safety-adjacent hold | works | `_pre_generation_hold_reason` `claude_service.py:1149–1171`; addressing override `claude_service.py:956–970` |
| Anti-generic ("grounding") hint | works | `_last_user_message_needs_grounding` `claude_service.py:1128–1147`; injected at `949–955` |
| Resume-context generator | works; silent empty-string fallback on exception | `claude_service.py:1912–1964` |
| Session insight generator | works; silent fallback to `generate_summary` on exception | `claude_service.py:2020–2055` |
| Plain summary generator | works | `claude_service.py:1966–1996` |
| `generate_summary` + `generate_session_insight` reuse full SYSTEM_PROMPT for non-facilitation tasks | unknown effect; intentional? | `claude_service.py:1987, 2029` — same 2 121-word facilitator instructions sent as system for summarization tasks where they are not strictly relevant |
| `generate_resume_context` uses a different, short system message | works | `claude_service.py:1952` |
| Address-conflict detector (cyrillic/latin name match) | logs only, no override | `claude_service.py:1796–1809` matches removed override per commit `bf361de` ("remove feedback handoff override, keep as prompt signal") |
| `prompt_harness.py` exists | works (file readable, imports `ClaudeService`) | `scripts/prompt_harness.py:1–80` |
| Live runtime output of these prompts in production | unknown — out of scope | specialist #7 |

## 4. Non-obvious decisions

- **Module/class named `claude_service` / `ClaudeService` but uses OpenAI exclusively.** `AsyncOpenAI` instantiated at `claude_service.py:700`; no Anthropic SDK imported anywhere in scope. Rationale unclear from code; likely historical naming retained across provider switch. `CLAUDE.md` itself refers to the service as `claude_service.py` without mentioning Claude.
- **Model `gpt-4o` is hard-coded** rather than env-configurable. Other OpenAI knobs (key, timeout, retries) are env-driven (`config.py:17, 31–33`); model choice is not. Rationale unclear.
- **No explicit `temperature`** anywhere despite (a) deterministic-style structured output, (b) explicit instructions like "не повторяй фразы" that benefit from lower temperature. Default `temperature=1.0` on gpt-4o is being relied on. Rationale unclear / absent.
- **`next_speaker` removed as authority** — collapsed into `addressed_to` per commit `f0586d9` ("make next_speaker derived from addressed_to"). The schema still requires both fields (`claude_service.py:553–556, 567`), and the model is told "Всегда ставь next_speaker = addressed_to" (`claude_service.py:292`). The server then ignores model's `next_speaker` and sets it to the resolved `addressed_to` (`claude_service.py:1813`). Schema kept for backwards compatibility per commit `90cc912`.
- **`address_feedback` no longer overrides handoff** — commit `bf361de` ("remove feedback handoff override, keep as prompt signal"). When a user complains about misaddressed turn, the server now only adds an `⚠ ADDRESS FEEDBACK` block to the developer prompt (`claude_service.py:910–917`) and lets the model choose. No server-side rewrite.
- **`_starts_with_partner_name` mismatch is observed-and-logged only** (`claude_service.py:1796–1809`, log key `gpt_message_address_conflict_observed`). Same commit `bf361de`: removed the rewrite, kept only telemetry.
- **`generate_summary` and `generate_session_insight` reuse full facilitator `SYSTEM_PROMPT`** (`claude_service.py:1987, 2029`) instead of a task-specific summarization system message. Inflates input tokens on every end-of-session call. Rationale unclear; `generate_resume_context` does use a short bespoke system message (`claude_service.py:1952`), so the pattern is inconsistent.
- **`MAX_CONTEXT_MESSAGES = 30`** without any token-based counting (`claude_service.py:539`). Implicit token budget assumes ≤30 × 2000-char messages plus the ~14.5 KB system + ~3–6 KB dynamic dev-prompt. Rationale unclear from comments.
- **Heuristic linguistic markers are duplicated in three places**: `_VULNERABILITY_MARKERS` (`claude_service.py:1318–1327`) and the inlined copy inside `_last_user_message_is_vulnerable` (`claude_service.py:1096–1106`); same pattern for `_SAFETY_ADJACENT_MARKERS` (`1115–1125` vs `1328–1338`). Rationale unclear.
- **Prompt enforces "максимум один эмодзи"** (`claude_service.py:103`) but no server-side check exists for emoji count.
- **Russian-only prompt and markers.** All instructions, banned phrases, and detection markers are in Russian. No language detection or English fallback. This is intentional given target audience (`CLAUDE.md:173`) but it means the bot cannot be exercised in any other language without rewriting the entire prompt stack.
- **`SETUP_BOTH_LIMIT` fallback** falls into `CLARIFY` only if `_should_force_clarify` matches markers like "пространство/свобода" vs "близость" (`claude_service.py:1287–1299, 1544–1545`); otherwise into `DEEPEN`. Marker list is narrow and rationale (why these exact lexemes) is unclear.
- **`MIN_USER_TURNS_FOR_OPTIONS = 8`** (`claude_service.py:1541`) — a hard floor blocking OPTIONS/AGREE. Rationale not commented; aligns with the prompt's rule "в диалоге не накопилось хотя бы 8 пользовательских ходов" (`claude_service.py:140`).
- **`MIN_TURNS_AFTER_REJECTION = 4`** (`claude_service.py:1504`) — cooldown before re-attempting OPTIONS after action rejection. Rationale not commented.

## 5. Risks & landmines

- **No `temperature` set on gpt-4o → default 1.0**. With a model instructed not to repeat phrases, high sampling temperature directly fights the anti-repeat heuristics that try to detect those repeats post-hoc. Likely contributor to: false-positive anti-repeat warnings filling the dev-prompt, intermittent off-spec outputs, and addressing-rule violations that have to be caught server-side. Trigger: every facilitator turn (`claude_service.py:1754–1763`).
- **Single giant `system` content per call** (~14.5 KB SYSTEM_PROMPT + 1–4 KB dynamic dev-prompt + up to 30 × ≤2000-char history). On gpt-4o, this is well within context, but cost grows linearly per turn. No prompt caching (`prompt_caching=True` or `cache_control`) is requested. Trigger: every facilitator turn.
- **Hard-coded `MODEL = "gpt-4o"`**. If OpenAI deprecates `gpt-4o` or pricing/quality changes, production behaviour cannot be migrated without a code change + deploy. Trigger: provider lifecycle event.
- **Hard-coded `"whisper-1"`** (deprecated by `gpt-4o-transcribe`/`gpt-4o-mini-transcribe` for some accounts) [unverified — provider lifecycle]. Trigger: voice transcription path (`claude_service.py:1900`).
- **No JSON-mode fallback**. Facilitator and insight calls use Structured Outputs (`response_format=RESPONSE_SCHEMA`). If gpt-4o returns a refusal or malformed JSON (which Structured Outputs is meant to prevent but does not always), `json.loads(raw)` raises `JSONDecodeError` and `OpenAIServiceError` is surfaced to user as "AI вернул некорректный ответ" (`claude_service.py:1771–1775`). Trigger: any model JSON refusal.
- **`generate_resume_context` and `generate_session_insight` silently swallow exceptions** (`claude_service.py:1962–1964`, `2047–2055`). Resume returns empty string → next session loses continuity without surfacing the failure. Insight falls back to plain summary → user gets a less-structured recap with no signal that the structured path failed.
- **Two copies of vulnerability/safety-adjacent marker lists** can drift (`claude_service.py:1096–1106` vs `1318–1327`; `1115–1125` vs `1328–1338`). A future edit to one set will silently leave the other inconsistent.
- **Heuristic-only safety detection**. `_last_user_message_is_vulnerable` and `_last_user_message_is_safety_adjacent` rely on Russian-language substring matching of ~30 lexemes each. Misspellings, latin transliteration in user input, or paraphrases bypass them entirely; the prompt's safety triggers then depend solely on model judgement.
- **Repetition detection looks only at last 4 (short MI) / 6 (long MI) assistant messages** (`claude_service.py:1403, 1405`). Cross-session repetition is invisible. Trigger: long sessions or back-to-back sessions on the same topic.
- **System-prompt size makes diff review hard.** 310-line single string; any change risks unintended interaction between sections (e.g. between "11 ПРАВИЛ" and "МИКРОВМЕШАТЕЛЬСТВА"). No section tests or modular composition. Trigger: any prompt iteration.
- **`SYSTEM_PROMPT` reused verbatim for summarization tasks** (`claude_service.py:1987, 2029`). The facilitator instructions (e.g. "Каждый твой ответ должен звучать свежо", banned phrase list, addressing rules) are mostly irrelevant for a summarization role and may bias the summary text. Trigger: every end-of-session.
- **`_with_retry` linear backoff** (`base*attempt + uniform(0,0.5)`). Three retries with `base=1.5` → ≤~6 s of waiting in worst case. Combined with `timeout=30s` per attempt, a stuck OpenAI call can keep a Telegram update handler busy for ~100 s before erroring out. Trigger: provider incident.
- **`max_tokens=1024` for facilitator** vs prompt's "3–5 предложений" limit (`claude_service.py:89`). Headroom is large; if model produces a long off-spec reply, it may approach the cap and be truncated mid-sentence. Trigger: rare model verbosity.
- **`MAX_MESSAGE_LENGTH = 2000`** truncates user input at message-store time (`claude_service.py:23, 1714`). Long voice transcriptions get silently chopped before being fed to the LLM. Trigger: voice messages > ~2000 chars (~5 min speech).

## 6. Open questions for the owner

1. Why is `MODEL` hard-coded to `gpt-4o` (not env-driven), and is there an intended migration path to a newer/cheaper model?
2. Was the absence of `temperature` (and `top_p`/`seed`) intentional, or simply never set? Has anyone A/B'd lower temperature against the current default?
3. Why does `generate_summary`/`generate_session_insight` reuse the full facilitator `SYSTEM_PROMPT` while `generate_resume_context` uses a short bespoke system message? Is the difference intentional?
4. The class name `ClaudeService` and module `claude_service.py` no longer reflect the provider. Is this kept for backward compat or pending rename?
5. The duplicated vulnerability/safety-adjacent marker lists (in `_last_user_message_is_*` methods vs the class-level constants) — is one of them dead code?
6. Are the numeric thresholds `MIN_USER_TURNS_FOR_OPTIONS=8`, `MIN_TURNS_AFTER_REJECTION=4`, `MAX_CONSECUTIVE_BOTH_TURNS=2`, `MAX_CONTEXT_MESSAGES=30`, `MAX_MESSAGE_LENGTH=2000` derived from session-data analysis or initial guesses?
7. Is `prompt_harness.py` actually run before prompt-edit deploys, and where do its outputs go (CI, manual review, ignored)? → also relevant to specialist #6.
8. What is the production token cost per facilitator turn today? → specialist #7.

## 7. Out-of-scope notes

- Move `MODEL` into `config.py` as env-driven.
- Extract `SYSTEM_PROMPT` into a versioned `.md` file under `bot/prompts/` for diffability.
