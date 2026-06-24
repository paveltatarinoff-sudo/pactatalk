# Multi-agent / dialog logic

Pinned commit: `d46ea5f779abb10afae4148433f7853396eea92f` (see `00-shared-header.md`).

## 1. Scope covered

Examined:
- `gcs45_bot/bot/fsm/states.py` — aiogram FSM groups.
- `gcs45_bot/bot/handlers/facilitator.py` (~1600 lines) — text/voice intake, BOTH mode buffering, end-session intent flow, resume-alignment text path, setup-topic-split/seed guards, address-feedback regex, loop-mode-shift dispatcher.
- `gcs45_bot/bot/handlers/session.py` — create/join/start/end session, resume confirmation buttons, pass_turn callback, post-session insight, pair_resume save/load.
- `gcs45_bot/bot/services/claude_service.py` (~2070 lines) — `SYSTEM_PROMPT`, per-state guidelines, structured outputs schema, `_resolve_effective_state`, `resolve_handoff_invariants`, repetition / action-loop / OPTIONS-cooldown detection, resume context generator, session insight generator.
- `gcs45_bot/bot/services/loop_guard.py` — out-of-band reply when the same speaker gives low-energy answers to reflective questions.
- `gcs45_bot/bot/services/resume_choice.py` — Redis-backed two-sided voting and free-text alignment for resume continue/new-topic decision.
- `gcs45_bot/bot/services/session_service.py` — SessionService (create, start, end, pass_turn, notify_both).
- `gcs45_bot/bot/models/session.py` — `SessionState` dataclass: `waiting_for`, `pending_a_message`, `pending_b_message`, `consecutive_turns`, `dialogue_state`, `close_choice_*` flags.
- All seven test files under `gcs45_bot/tests/` (handoff, guardrail, loop-mode-shift, end-session-flow, session-resume, privacy-delete, release-hygiene).
- `tg/messages.html` (~1 MB Telegram export) for live behaviour validation. `tg/messages2.html` referenced for second pair.

Not in scope / not examined deeply:
- Actual prompt wording quality of `SYSTEM_PROMPT`/`STATE_GUIDELINES` — handed off (see note in §4). Inventory only here.
- Repository / Redis-Postgres persistence internals — handed off (see §4).
- PostHog dashboards / behavioural metrics — handed off.
- End-to-end UX-as-experienced — handed off.

→ prompt content of `SYSTEM_PROMPT` / `STATE_GUIDELINES`: see specialist #1.
→ Redis history / session-events / pair_resumes persistence: see specialist #3.
→ end-to-end facilitator UX quality from transcript: see specialist #8.

## 2. Inventory

Dialog-flow entities, by layer.

**FSM groups** (`bot/fsm/states.py:1-21`):
- `UserFlow`: `joining`, `feedback_category`, `feedback_message`, `support_category`, `support_message`.
- `AdminFlow`: `replying_to_request`.
- `SessionFlow`: `waiting_partner`, `opening`. Note: only two session states; phase progression is tracked on `SessionState.phase` (`opening | exploration | deepening | agreement | closing`) and not via FSM transitions.

**Dialogue states** (string field `SessionState.dialogue_state`, validated by `RESPONSE_SCHEMA` enum at `claude_service.py:563-566`): `SETUP`, `CLARIFY`, `DEESCALATE`, `DEEPEN`, `OPTIONS`, `AGREE`, `CHECK_IN`.

**Speaker addressing** (`SessionState.waiting_for` ∈ {`A`, `B`, `BOTH`}, model: `session.py:59`). `is_active_speaker` (`session.py:86-92`) returns True for both partners when `waiting_for=="BOTH"`.

**Structured GPT contract** (`claude_service.py:544-571`): JSON schema with `message`, `next_speaker` ∈ {A,B,BOTH}, `risk_flag`, `addressed_to` ∈ {A,B,BOTH}, `next_state` ∈ 7 states. `strict: True`.

**Pre-call effective-state resolver** (`ClaudeService._resolve_effective_state`, `claude_service.py:1547-1624`). Re-routes `session.dialogue_state` before the GPT call when:
- `SETUP` with ≥2 consecutive BOTH cycles → falls back to `DEEPEN` / `CLARIFY` (`MAX_CONSECUTIVE_BOTH_TURNS = 2`, line 697).
- two-sided needs conflict detected → forces `CLARIFY` (`_should_force_clarify`, line 1264).
- `OPTIONS`/`AGREE` with <8 user turns → falls back (`MIN_USER_TURNS_FOR_OPTIONS = 8`, line 1541).
- action rejection in `OPTIONS`/`AGREE` → forced `DEEPEN` (line 1586).
- repeated action proposals → forced `DEEPEN` (line 1595).
- cooldown after rejection (<4 user turns since, `MIN_TURNS_AFTER_REJECTION = 4`, line 1504) → fallback state.

**Post-call handoff resolver** (`resolve_handoff_invariants`, `claude_service.py:1626-1707`) — single authority that mutates GPT-emitted `addressed_to` into the final value. Rules in order:
1. invalid value → `BOTH`.
2. single-speaker in `OPTIONS`/`AGREE`/`CHECK_IN` → forced `BOTH`.
3. `BOTH` in `DEEPEN`/`DEESCALATE`/`CLARIFY` → forced to last user speaker.
4. `BOTH` exceeding 2 joint cycles outside joint states → forced to focus speaker.
5. `BOTH` after vulnerable last user turn (non-joint, non-SETUP) → forced to that speaker.
6. 3+ same-speaker turns → forced switch to other.

After this, `next_speaker = addressed_to` (line 1813); the two fields are no longer independent (refactor `f0586d9`).

**Post-call state guards** (`claude_service.py:1816-1872`): block `DEEPEN` after forced `CLARIFY`; block premature `OPTIONS`/`AGREE` (<8 turns); detect action rejection; anti-action-loop; cooldown.

**Server-side prompt scaffolds** in `_developer_prompt_for_state` (`claude_service.py:793-1054`):
- `addressing_rule` (varies per `waiting_for` × `effective_state`); hard override on 3+ consecutive speakers (line 996-1006) or vulnerability hold (line 962-970).
- `last_answer_hint` (vulnerable / safety-adjacent / short / content) at line 938-988.
- `repetition_warning` from `_detect_bot_repetition` (lines 1388-1475): canned interventions, canned phrases, soft-MI cooldown.
- `grounding_hint` when last user reply is broad/abstract (line 949-955).
- `joint_mode_hint` warning a BOTH-cycle is already in use.
- `resume_block` injected only in `SETUP` when `session.resume_context` is set (line 1014-1024).

**BOTH-mode buffering** (`_collect_for_both`, `facilitator.py:1216-1453`): each side writes to `pending_a_message`/`pending_b_message` on `SessionState`. When both present, bot relays both, then calls Claude with combined `[A]:…\n[B]:…` payload. Two SETUP-only short-circuits run before the Claude call:
- `_detect_setup_topic_seed` (`facilitator.py:493-504`): one side names a concrete topic, other is flexible/meta → seed prompt.
- `_looks_like_setup_topic_split` (`facilitator.py:458-481`): both name different concrete topics → split prompt.

**Loop-mode shift** (`bot/services/loop_guard.py:106-136`, dispatched from `_maybe_apply_loop_mode_shift` `facilitator.py:724-769`). Triggers in `DEEPEN`/`CLARIFY`/`DEESCALATE` when the same speaker emits explicit loop feedback OR ≥2 low-energy answers to ≥2 reflective questions. Bypasses Claude entirely; emits a fixed 3-option fallback reply.

**Address-feedback signal** (`_looks_like_address_feedback`, `facilitator.py:426-428`; patterns at 44-53). Detected from user text; flag flows into `_developer_prompt_for_state(...)` as `feedback_hint` (`claude_service.py:910-917`). Authority is prompt-only since commit `bf361de` ("remove feedback handoff override").

**End-session intent** (`facilitator.py:54-149`, `561-688`). Pattern-based detection of "хочу завершить / на сегодня всё / закончим" → posts a single end-session button (`_present_direct_end_session_button`). Two-stage flow elsewhere: confirmation pending → end-choice with both-vote continuation (`session.py:1136-1197`).

**Resume continuity** (`bot/services/resume_choice.py`): Redis keys `resume_vote:{sid}:{uid}`, `resume_resolution:{sid}`, `resume_alignment_reply:{sid}:{uid}` (TTL 24h). States: vote `waiting | matched | mismatch | duplicate | resolved`. Mismatch → `ALIGNMENT_PENDING` → free-text alignment with `decide_resume_resolution` that classifies continue / new / flexible. `_handle_resume_alignment_text` (`facilitator.py:867-918`) runs the text path; voice messages also reroute through it (line 1167-1175).

**Lock/throttle hygiene** (`facilitator.py:43-44, 241-249, 1036-1041, 1119-1124`): per-session asyncio lock prevents concurrent Claude calls; per-user Redis throttle key `throttle:{uid}` TTL 5s.

**Session lifecycle** (`SessionService`, `session_service.py:40-123`):
- `create_session` mints invite code, persists.
- `join_session` rejects duplicate join.
- `start_session` sets `phase="opening"`, `mode="structured"`, `dialogue_state="SETUP"`, `waiting_for="BOTH"`.
- `pass_turn` swaps `waiting_for` A↔B and resets counters (callback at `session.py:839-869`, not invoked by facilitator turn flow — only manual button).
- `end_session` sets `phase="closing"`. Real teardown done by `cb_end_session` at `session.py:891-995` (insight generation, pair-resume save, ephemeral history clear).

**Tests covering this dimension** (`gcs45_bot/tests/`):
- `test_handoff.py`: 492 lines, ~30 tests on `_consecutive_same_speaker`, `_last_user_speaker`, vulnerability/safety-adjacent/grounding detection, `resolve_handoff_invariants` (5 cases), forced-switch developer prompt, OPTIONS/AGREE mandatory BOTH.
- `test_guardrail.py`: feedback-flag pass-through, append_event failure isolation, throttle, SETUP topic-split/seed.
- `test_loop_mode_shift.py`: explicit loop feedback, low-energy repetition, risk override, short-circuit, productive-flow negative.
- `test_session_resume.py`: resume vote, alignment, classify text, prompt injection.
- `test_end_session_flow.py`: end-intent direct button, confirmation flow, two-side continue vote.

## 3. State of each piece

| Item | State | Evidence |
|---|---|---|
| Dialogue 7-state enum | works (validated by Structured Outputs) | `claude_service.py:563-566` |
| `addressed_to` as single handoff authority | works (post `f0586d9`, `90cc912`) | `claude_service.py:1811-1813`, commit `f0586d9` |
| `resolve_handoff_invariants` consolidates 6 post-guards | works | `claude_service.py:1626-1707`, commit `407e904` |
| BOTH forced in OPTIONS/AGREE/CHECK_IN | works (CHECK_IN added `2010383`) | `claude_service.py:1645-1652`, tests `test_handoff.py:199-206` |
| BOTH blocked in DEEPEN/DEESCALATE/CLARIFY | works | `claude_service.py:1654-1664`, test `test_handoff.py:208-215` |
| 3+ consecutive turns force switch | works | `claude_service.py:1695-1706`, test `test_handoff.py:226-233` |
| Vulnerability hold | works | `claude_service.py:1680-1693`, test `test_handoff.py:217-224` |
| Sticky-BOTH exit after 2 cycles | works in SETUP and outside joint states | `claude_service.py:1666-1678`, `_resolve_effective_state:1548-1559`, test `test_handoff.py:472-481` |
| OPTIONS premature-block (<8 user turns) | works pre- and post-call | `claude_service.py:1572-1583, 1830-1840` |
| Action-rejection → DEEPEN | works | `claude_service.py:1585-1593, 1842-1849` |
| OPTIONS cooldown 4 turns after rejection | works | `claude_service.py:1604-1617, 1861-1872` |
| Loop-mode-shift bypass | works, narrowly scoped to 3 states with 3 triggers | `bot/services/loop_guard.py:106-136`, tests `test_loop_mode_shift.py:94-150` |
| Address-feedback handoff override | removed (now log+prompt-only) | commit `bf361de`, `facilitator.py:1415-1422` (log line `facilitator_reply_routing_observed_conflict`); test `test_guardrail.py:test_feedback_signal_does_not_override_service_handoff` |
| BOTH buffering / pending_a/b | works | `facilitator.py:1216-1287`, `session.py:62-64` |
| SETUP topic-split guard | works for short distinct topics ≤120 chars | `facilitator.py:458-481, 1329-1361`, test `test_guardrail.py:test_setup_topic_split_*` |
| SETUP topic-seed prompt | works when one specific + one flexible/meta | `facilitator.py:493-537, 1288-1327` |
| `_apply_next_speaker` updates `waiting_for` & resets `consecutive_turns` | works | `facilitator.py:259-281` |
| `SessionService.pass_turn` | partial — only manual callback, never invoked from facilitator turn loop | `session_service.py:91-100`, callback `session.py:839-869` |
| End-session intent detection | works, voice path included | `facilitator.py:561-581, 1160-1165` |
| End-session two-sided continue vote | works | `session.py:1136-1197`, tests `test_end_session_flow.py:test_*_continue_callback_*` |
| Resume continuation Redis voting | works including duplicate/race protection | `resume_choice.py:134-165`, tests in `test_session_resume.py` |
| Resume alignment free-text path | works for text and voice | `facilitator.py:867-918, 1167-1175` |
| Per-session asyncio lock + per-user 5s throttle | works | `facilitator.py:43-44, 241-249` |
| Silent-error swallowing on append_event | works (logs `append_event_failed`) | `facilitator.py:252-256`, test `test_guardrail.py:test_collect_for_both_keeps_pending_when_append_event_fails` |
| Generic handler-level catch returns retry prompt | works (commit `a3d5d42`) | `facilitator.py:1073-1078, 1206-1211` |
| `phase` field has no transitions beyond `opening` → `closing` | partial — declared values `exploration/deepening/agreement` exist but no code transitions into them | `session.py:36`; ripgrep `bot/services/session_service.py:103` only sets `closing` |
| `consecutive_turns` counter on SessionState | unused as authority — `_consecutive_same_speaker` recomputes from history | `claude_service.py:1057-1076`, model field `session.py:61` |
| `SessionFlow.opening` FSM state | unused for routing once session is live; facilitator dispatches by message type only | `facilitator.py:945` decorator is `@router.message(F.text)` with no state filter |
| `loop_mode_shift_triggered` log line | present | `facilitator.py:751-755` |
| `post_guard_*` log lines (5 variants) | present | `claude_service.py:1647, 1659, 1672, 1689, 1699` |
| `setup_topic_split_guard_triggered` log | present | `facilitator.py:1336-1341` |

## 4. Non-obvious decisions

**Handoff authority moved from text-detection to `addressed_to`.**
Facilitator originally rewrote handoff based on whether the reply text started with a name. After `bf361de`, `f0586d9`, `407e904`, `90cc912` the only authoritative path is `addressed_to` → `resolve_handoff_invariants` → `next_speaker = addressed_to`. Text-based detection (`_detect_explicit_reply_addressee`) survives only as a log signal `facilitator_reply_routing_observed_conflict` at `facilitator.py:1415-1422`. CLAUDE.md §2 documents this. Rationale: single point of truth, easier to test.

**Same six post-guards re-checked twice.**
Premature-OPTIONS / action-rejection / cooldown logic lives both pre-call (`_resolve_effective_state`) and post-call (`get_facilitator_response` lines 1819-1872). This is intentional: pre-call shapes prompt, post-call defends against GPT picking `next_state` anyway. Rationale visible from log labels (`blocked_premature_options` vs `post_guard_blocked_premature_options`).

**`MAX_CONSECUTIVE_BOTH_TURNS = 2` is hard.**
After 2 joint cycles in non-joint states, server forces single-speaker focus chosen by `_preferred_focus_speaker_after_joint`, which scores vulnerability > safety-adjacent > grounding > word count (`claude_service.py:1232-1261`). Test `test_handoff.py:181-186` covers preference. Rationale: avoid the BOTH cycle that the SETUP prompt produced naturally.

**`MIN_USER_TURNS_FOR_OPTIONS = 8` is hard.**
GPT cannot enter OPTIONS/AGREE before 8 user turns. Joint subturns count as 2 (`_count_user_turns` line 1302-1315). Rationale: anti-premature-solutions baseline from CLAUDE.md §4.

**Loop-mode-shift bypasses Claude entirely.**
When triggered (`facilitator.py:746-768`), the canned reply is appended to history as assistant turn, and `_process_turn` returns it as if Claude responded. Only available in `DEEPEN`/`CLARIFY`/`DEESCALATE`. Rationale unclear from commits — appears to be a manual circuit-breaker for the "buksuet" case observed in the transcript.

**Resume alignment uses Redis, not SessionState.**
Vote state (`resume_vote:*`, TTL 24h) and free-text replies (`resume_alignment_reply:*`) live entirely in Redis. SessionState only carries `resume_context`. Rationale: idempotent two-side coordination without writing back to the session snapshot on every callback.

**`SessionService.pass_turn` is dead-ish.**
The only caller is `cb_pass_turn` (`session.py:839-869`). The facilitator turn loop never invokes it; `_apply_next_speaker` writes `waiting_for` directly without going through the service. No test exercises the callback. Rationale unclear.

**`SessionState.phase` is informational only.**
`phase="closing"` is the only meaningful runtime transition (set by `end_session`). The declared values `exploration/deepening/agreement` are not produced by any code path. The active state machine is `dialogue_state`, not `phase`.

**`SessionState.consecutive_turns` is dead.**
Field is set/reset in `_apply_next_speaker` (`facilitator.py:264-282`) but never read — `_consecutive_same_speaker` recomputes from message history (`claude_service.py:1057-1076`). Rationale: history is the source of truth after the handoff refactor; the counter is a stale leftover.

→ Why these prompt rules exist (e.g. why "ОБЯЗАТЕЛЬНО BOTH в OPTIONS"): see specialist #1.

## 5. Risks & landmines

**Address-feedback patterns are surface-level Russian substrings.**
`ADDRESS_FEEDBACK_PATTERNS` (`facilitator.py:44-53`) and end-session detector (lines 54-149) are static substring lists with `_normalize_text` (lower + ё→е + collapse-spaces). A user phrasing the same intent slightly differently is silently ignored. Trigger: any localisation or paraphrase. Symptom: bot ignores explicit user complaint about wrong addressing.

**Loop-mode-shift writes history without going through `_add_message`.**
`facilitator.py:744-747` calls `repo.save_history` directly with the appended entry. `_add_message` in `ClaudeService` (line 1712-1717) is the only place that truncates content to `MAX_MESSAGE_LENGTH` and history to `MAX_CONTEXT_MESSAGES`. The loop-mode path uses `append_history_entry` (`loop_guard.py:99-103`) which trims length but content length is not capped. If a very long mode-shift reply is constructed (today it is fixed-format, but a future edit could break this), nothing prevents it.

**`waiting_for` mutation outside the lock.**
`_apply_next_speaker` is called from inside the per-session lock. But session is also mutated from `cb_end_session`, `cb_continue_session`, `cb_resume_choice` (`session.py`) without acquiring the facilitator lock — those handlers run in parallel with an in-flight facilitator turn. Trigger: user clicks "Завершить сессию" while bot is producing a reply. Symptom: state can race — `phase="closing"` set, then `_apply_next_speaker` overwrites `waiting_since/waiting_for`. No test covers this.

**`pass_turn` callback can fire mid-Claude-call.**
`cb_pass_turn` (`session.py:839-869`) does not check the asyncio lock or `dialogue_state`. It can flip `waiting_for` A↔B between the lock acquire and the GPT response, and `_apply_next_speaker` then overwrites it again. Result is unpredictable from the user's point of view.

**Voice path skips end-session-confirmation pending check.**
`handle_voice_message` (`facilitator.py:1083-1211`) detects `_looks_like_end_session_intent(text)` (line 1160) but does NOT call `_resolve_end_session_confirmation`. If `close_confirmation_pending=True` and user replies "да" via voice, the bot will not interpret it as confirmation — it falls through to normal turn handling. Trigger: voice-only user during confirmation. The text handler does check this (`facilitator.py:968-977`).

**`SETUP_TOPIC_SPLIT_GENERIC_TOKENS` filter is brittle.**
Long lists at `facilitator.py:151-200` with one duplicate `"просто"` and one duplicate `"тема"`. False negatives (topic word looks generic) silently skip the guard. False positives (two short messages with non-overlapping first-3-character prefixes) trigger the split prompt. No test covers boundary cases.

**`partner_name` ambiguity if `user_a_id == user_b_id == 0`.**
`SessionState.partner_name` (`session.py:79-84`) returns `"A"` for `user_id=0` matching `user_a_id=0` (waiting-for-partner state). Combined with `if session.user_b_id == 0: return early` in the facilitator (line 959-961), this is currently safe — but any future code path that handles a session with B not yet joined will produce wrong sender labels.

**`_release_lock` only fires on risk_flag end-session or ephemeral-delete.**
The dict `_locks` (`facilitator.py:43`) grows over the process lifetime; `_release_lock(session_id)` is called only in 3 spots. Long-running deployment retains lock entries for every ever-seen session_id. Slow leak; not user-visible but real.

**Resume context only injected when `effective_state == "SETUP"`.**
`_developer_prompt_for_state` injects `resume_block` only if `effective_state == "SETUP"` (line 1015). If `_resolve_effective_state` fallback-moves a resume session out of SETUP (e.g. two BOTH cycles already happened), the resume context disappears from the prompt mid-conversation. No test covers this transition.

**Telegram export evidence of handoff signature working.**
`grep "теперь твой ход"` in `tg/messages.html` → 149 hits; `"теперь ваш ход"` → 92 hits. Handoff signature shows up consistently in production transcripts, confirming `_speaker_signature` (`facilitator.py:540-547`) is reached. This is the only inventory-level evidence of live behaviour; UX quality is out of scope here.

## 6. Open questions for the owner

1. Is `SessionService.pass_turn` (and its `session:pass_turn` callback) deliberately retained, or is it dead UI? No test or keyboard entry-point I could find.
2. Is `SessionState.phase` (`opening/exploration/deepening/agreement/closing`) a vestige of an earlier design, or is something planned to set the intermediate values?
3. Is `SessionState.consecutive_turns` (always set, never read after the handoff refactor) intentionally kept for future use, or should it be removed?
4. Was the choice not to check `close_confirmation_pending` in `handle_voice_message` intentional (e.g. you don't expect "да" via voice), or is it an oversight?
5. The loop-mode-shift fallback is wired only for `DEEPEN`/`CLARIFY`/`DEESCALATE`. Is `OPTIONS`/`AGREE` deliberately excluded (action rejection has its own path) or just not yet ported?
6. Why does `_apply_next_speaker` reset `consecutive_turns` and `timeout_reminders_sent`, given there is no timeout-reminder code path anywhere in scope? (`SessionState.timeout_reminders_sent` declared at `session.py:68` but only assignments and resets; no producer of reminders).

## 7. Out-of-scope notes

- Loop-mode-shift path bypasses `_add_message` content-length cap. Currently safe; one-line fix to route through it.
- Voice handler should call `_resolve_end_session_confirmation` symmetrically with text handler.
- `_locks` dict should be cleared on more termination paths (any `phase="closing"` transition).
