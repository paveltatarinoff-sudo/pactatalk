# Evals & LLM output quality

Audit pinned to commit `d46ea5f` (per `docs/audit/2026-06-24/00-shared-header.md`).

## 1. Scope covered

Examined:
- `gcs45_bot/evals/` — listed recursively. Result: empty of source, contains one orphan `__pycache__/pactatalk_eval.cpython-314.pyc`.
- The orphan bytecode `gcs45_bot/evals/__pycache__/pactatalk_eval.cpython-314.pyc` (37 762 bytes, mtime 2026-03-24 11:16) — decompiled symbol-level (module names, function names, string constants) via `marshal.load` + `dis` to reconstruct what the missing source did. Function bodies / prompt text not recovered (would require a `.py` decompiler).
- `gcs45_bot/.venv/lib/python3.9/site-packages/__editable___pactatalk_bot_0_1_0_finder.py` — editable-install namespace map listing eval-related namespaces that the editable install was generated against.
- `gcs45_bot/pyproject.toml` — checked for eval entry-points, test markers, optional-deps.
- `gcs45_bot/CLAUDE.md` — checked for any operational reference to evals.
- `git log --all` across the repo for any tracked path matching `eval`, `judge`, `scenario` — none found.
- `gcs45_bot/bot/` source — searched for references to the eval module, the judge constants, or the rule-pattern names embedded in the bytecode (`MECHANICAL_PATTERNS`, `DEPTH_STATES`, `FORBIDDEN_BOTH_STATES`).

Not examined / not reachable:
- The original `evals/pactatalk_eval.py` source — deleted, never tracked in git, no recoverable copy on disk outside the bytecode.
- `gcs45_bot/evals/scenarios/` — directory does not exist on disk (only known to have existed via the editable-install namespace map).
- `gcs45_bot/reports/evaluations/<dated>/` — directory does not exist on disk (only known via the same namespace map).
- Any CI pipeline running evals — no `.github/`, no Fly job config, no Makefile target found in scope referencing eval runs.
- Prompt content under evaluation → out of scope, owned by specialist #1.
- Production runtime LLM logs → out of scope, owned by specialist #7.

## 2. Inventory

What exists on disk under `gcs45_bot/evals/` at commit `d46ea5f`:

- `gcs45_bot/evals/` — directory, mtime `2026-04-03 10:11`. Contains only `__pycache__/`.
- `gcs45_bot/evals/__pycache__/pactatalk_eval.cpython-314.pyc` — single bytecode file, 37 762 bytes, mtime `2026-03-24 11:16`. Not tracked by git (`git ls-files gcs45_bot/evals/` returns empty). Targets CPython 3.14, while the project's pinned interpreter in `gcs45_bot/.venv/` is 3.9 — the bytecode cannot be loaded by the project venv.

What the bytecode header tells us about the missing source (`co_filename: evals/pactatalk_eval.py`):

- Top-level imports recovered from `co_names`: `argparse`, `asyncio`, `json`, `statistics`, `collections.Counter`, `datetime.timezone`, `pathlib.Path`, `typing.Any`, `openai.AsyncOpenAI`, `bot.config.settings`, `bot.models.session.SessionState`, `bot.services.claude_service.ClaudeService`.
- Top-level constants / classes / functions named in `co_names`: `FORBIDDEN_BOTH_STATES`, `DEPTH_STATES`, `MECHANICAL_PATTERNS`, `BRIDGE_PATTERNS`, `SOLUTION_PATTERNS`, `JUDGE_MODEL`, `JUDGE_SCHEMA`, `RUBRIC`, `InMemoryRepo`, `default_scenarios_path`, `_build_session`, `_load_scenarios`, `_starts_with_name`, `_contains_mechanical_pattern`, `_contains_bridge_pattern`, `_contains_solution_pattern`, `evaluate_rule_checks`, `_judge_prompt`, `_judge_scenario`, `run_scenario`, `AXIS_GROUPS`, `_aggregate`, `_format_report`, `_main`.
- Judge model string constant: `'gpt-4o-mini'`.
- JSON-schema name for the structured judge output: `'pactatalk_eval_judge'` with `strict: true`.
- Seven scoring axes embedded as schema properties, each `integer 1..5`: `addressing_routing`, `depth_holding`, `empathy_humanness`, `usefulness`, `neutrality`, `variability_non_template`, `safety_handling`, `realism_as_facilitator`. (Eight axes named; the bytecode lists all eight as schema properties.)
- Rubric strings (Russian, recovered verbatim from `co_consts`), one per axis, e.g. `'1 = сломанная адресация или routing; 3 = в основном корректно; 5 = стабильно согласовано и естественно.'` and `'1 = рано переключается/схлопывает глубину; 3 = иногда удерживает; 5 = уверенно держит конфликт и боль.'`
- Aggregation groups recovered from `co_consts`: `'routing'`, `'depth'`, `'tone'`, `'safety'`.
- Structured-output extras: `hard_failures` (array of string), `soft_failures` (array of string), `notable_strengths`, `summary` — judge returns these alongside the per-axis scores.
- `__main__` block present (run as script via `python -m evals.pactatalk_eval`).

What is referenced but absent from disk (sourced from `__editable___pactatalk_bot_0_1_0_finder.py:NAMESPACES`):

- `evals.scenarios` — dataset directory.
- `reports.evaluations.2026-03-19-core15`
- `reports.evaluations.2026-03-19-v2`
- `reports.evaluations.2026-03-20-depth-prompt-only-full30`
- `reports.evaluations.2026-03-20-depth-guard-rerun-live`
- `reports.evaluations.2026-03-20-depth-guard-rerun-judge`
- `reports.evaluations.2026-03-20-depth-guard-weak4`
- `reports.evaluations.2026-03-20-depth-pregen-rerun-live`
- `reports.evaluations.2026-03-20-depth-v2-baseline-full30`

All nine of those paths are registered as Python namespaces in the editable-install metadata, meaning they existed on disk at the moment `pip install -e .` was last run, but none of them exist now.

What is **not** in scope and was not found:
- No `pytest`-style eval tests (`pyproject.toml:24-26` declares only `pytest`, `pytest-asyncio`, `pytest-mock` and `asyncio_mode = "auto"`, no eval marker).
- No CI workflow file (`.github/workflows/`) in the repo root.
- No Makefile / `tox.ini` / `noxfile.py` in scope.
- No reference to `evals`, `pactatalk_eval`, `judge` in `gcs45_bot/CLAUDE.md`.
- No reference to the eval module in `gcs45_bot/bot/` source.

## 3. State of each piece

| Item | State | Evidence |
|------|-------|----------|
| `gcs45_bot/evals/` package source | broken (deleted) | `ls -la gcs45_bot/evals/` shows only `__pycache__/`; `git ls-files gcs45_bot/evals/` returns empty; `git log --all -- gcs45_bot/evals/` returns empty |
| `gcs45_bot/evals/__pycache__/pactatalk_eval.cpython-314.pyc` orphan | unloadable | File is CPython 3.14 bytecode (`cpython-314` tag); venv interpreter is 3.9 per `.venv/lib/python3.9/...`; cannot be imported by this project even if source were present |
| `gcs45_bot/evals/scenarios/` dataset | broken (deleted) | Directory absent on disk; only referenced by `__editable___pactatalk_bot_0_1_0_finder.py:NAMESPACES['evals.scenarios']` |
| `gcs45_bot/reports/evaluations/` outputs (8 dated runs) | broken (deleted) | Directory absent on disk; eight dated subdirs listed in `__editable___pactatalk_bot_0_1_0_finder.py:NAMESPACES` (`2026-03-19-core15`, `2026-03-19-v2`, six `2026-03-20-depth-*` runs) |
| Judge runner (`_judge_scenario`, `_judge_prompt`, `JUDGE_MODEL='gpt-4o-mini'`, `JUDGE_SCHEMA`) | broken (deleted) | Symbols present in `pactatalk_eval.cpython-314.pyc` `co_names`; source absent |
| Rule-check layer (`MECHANICAL_PATTERNS`, `BRIDGE_PATTERNS`, `SOLUTION_PATTERNS`, `_contains_*_pattern`, `evaluate_rule_checks`) | broken (deleted) | Symbols present in `pactatalk_eval.cpython-314.pyc` `co_names`; no live equivalents found in `gcs45_bot/bot/` via grep |
| Aggregation / reporting (`_aggregate`, `_format_report`, `AXIS_GROUPS`) | broken (deleted) | Symbols present in bytecode; no output reports on disk |
| Scoring axes (8 axes, 1..5 integer scale, Russian rubrics) | known but inert | Recovered from `co_consts` of the bytecode (full rubric strings present); no runner to execute against them |
| CI / scheduled eval execution | not found | No workflow files in repo; no Fly cron in `docs/audit/_data/fly/`; no Makefile / `pyproject.toml` script entry referencing evals |
| Eval coverage of current production handoff/BOTH/anti-template rules (per `gcs45_bot/CLAUDE.md:32-104`) | coverage gap (no runner) | Same — runner deleted; cannot measure |
| Imports the eval depended on (`bot.config.settings`, `bot.models.session.SessionState`, `bot.services.claude_service.ClaudeService`) | still present | `ls gcs45_bot/bot/services/` shows `claude_service.py`; `ls gcs45_bot/bot/models/` shows `session.py` — so a restored source file would resolve its imports |

## 4. Non-obvious decisions

- **Evals were never under version control.** `git log --all -- gcs45_bot/evals/` returns no commits, and `git log --all --diff-filter=D` matched on `eval|judge|scenario` returns nothing. The entire eval harness, dataset and eight dated result folders existed only on the owner's laptop. Rationale unclear — possible options: `.gitignore` filtered them out (no project-root `.gitignore` exists in scope; `gcs45_bot/.gitignore` does not exist), or files were never `git add`-ed. From an outsider's view this looks intentional (kept out of repo) rather than an accident.
- **Judge model pinned to `gpt-4o-mini`.** String literal recovered from `pactatalk_eval.cpython-314.pyc` `co_consts`. Cheap judge for a runtime that itself uses Anthropic Claude (the eval imports `bot.services.claude_service.ClaudeService` and calls `openai.AsyncOpenAI` only for the judge). Rationale unclear — likely cost-driven.
- **Eight scoring axes, integer 1..5, plus four free-text fields** (`hard_failures`, `soft_failures`, `notable_strengths`, `summary`). The structured-output schema name `pactatalk_eval_judge` is marked `strict: true`. Rubric language is Russian, which matches the bot's user-facing language but means the judge prompt and outputs are non-English. Rationale: likely matches user-facing transcripts.
- **Aggregation collapsed eight axes into four groups** (`routing`, `depth`, `tone`, `safety`) per the `AXIS_GROUPS` symbol + four group-name string constants. Rationale unclear — likely for a four-quadrant dashboard view.
- **Rule layer separate from judge layer.** Three pattern sets (`MECHANICAL_PATTERNS`, `BRIDGE_PATTERNS`, `SOLUTION_PATTERNS`) plus state-list constants (`FORBIDDEN_BOTH_STATES`, `DEPTH_STATES`) ran deterministic checks (`evaluate_rule_checks`) before the LLM judge saw the transcript. Decision: belt-and-braces — catch shape violations cheaply, then let the judge score everything else. Rationale visible from the symbol pairing but not from documentation (no docs exist in scope).
- **Burst of work in March, then nothing.** Eight dated result folders span 2026-03-19 → 2026-03-20 ("core15", "v2", six "depth-*" runs in one day). Bytecode mtime 2026-03-24. Folder mtime on `evals/` itself is 2026-04-03. After early April there is no further activity touching eval-related paths in `git log` (most recent commits are about handoff refactoring, not evals — see `git log --oneline -5`). Rationale unclear — the eval harness was apparently used intensively for one week then abandoned.
- **`InMemoryRepo` class in the eval** suggests the eval bypassed the real `session_repo.py` (Postgres-backed) and ran scenarios fully in-process. Decision: keep the eval hermetic — no DB, no Telegram. Rationale follows from cost/speed of an LLM-judge harness.

## 5. Risks & landmines

- **Zero eval coverage in repo as of `d46ea5f`.** No runner, no dataset, no scoring code, no historical results checked in. Trigger: any prompt or handoff change today. What happens: no automated way to detect regressions on the eight axes the team previously cared about (addressing, depth-holding, empathy, usefulness, neutrality, anti-template, safety, realism). All recent prompt-affecting commits (`a3d5d42`, `90cc912`, `f0586d9`, `407e904`, `bf361de` — `git log --oneline -5`) shipped without an eval gate.
- **Orphan `.pyc` is misleading.** A new contributor sees `gcs45_bot/evals/__pycache__/pactatalk_eval.cpython-314.pyc` and assumes there is an eval suite. There is not. Trigger: someone reads `ls evals/` and stops there. What happens: false confidence that evals exist.
- **Bytecode is also Python-version-incompatible.** Tagged `cpython-314`, but the venv is 3.9. Trigger: someone tries `python -m evals.pactatalk_eval`. What happens: `ImportError: bad magic number` (or namespace-missing error). Cannot even resurrect by re-decompiling without a Python 3.14 interpreter.
- **Eight `reports/evaluations/*` namespaces still registered in the editable install** via `__editable___pactatalk_bot_0_1_0_finder.py:NAMESPACES`. Trigger: any code that does `import reports.evaluations.X`. What happens: `ImportError` at runtime because the directories are gone — the finder will still claim it owns those names. Low-probability trigger (nothing in `bot/` imports them) but a latent footgun.
- **Lost institutional knowledge.** The dated folder names — `depth-prompt-only-full30`, `depth-guard-rerun-live`, `depth-guard-rerun-judge`, `depth-guard-weak4`, `depth-pregen-rerun-live`, `depth-v2-baseline-full30` — describe a structured A/B comparison (prompt-only vs guard vs pregen, full30 vs weak4, live vs judge-rerun) that decided the current depth/anti-premature-solutions baseline documented in `gcs45_bot/CLAUDE.md:75-90`. None of those eval inputs or outputs survived. Trigger: someone challenges that baseline or wants to revisit a decision. What happens: no way to re-run the comparison without rebuilding the harness and dataset from scratch.
- **Judge cost and provider mix.** If the harness is resurrected unchanged, it will call OpenAI (`gpt-4o-mini`) for scoring while the bot itself calls Anthropic. Trigger: enabling the eval in CI. What happens: a second LLM vendor and a second API key on the critical path, not currently provisioned in `docs/audit/_data/fly/secrets-names.txt`. → secrets / cost surface owned by specialists #3 / #7.

## 6. Open questions for the owner

1. Was deleting `evals/`, `evals/scenarios/` and the eight `reports/evaluations/*` directories intentional, or accidental cleanup (e.g. `rm -rf` of "untracked stuff")? The `.pyc` survived only because `__pycache__` was probably not in the rm pattern.
2. Is there a backup of `evals/pactatalk_eval.py` and `evals/scenarios/*` anywhere (other branch, other machine, Time Machine, gist)? If yes, the harness is one paste away from working.
3. Were the eval results (the eight dated folders) ever exported anywhere durable — a doc, a Notion page, a screenshot in the team chat — or did they live only in JSON inside the deleted folders?
4. Why was the harness paused after 2026-03-24? Was the question it answered ("is depth-guard ready to ship?") considered closed, or did the harness itself prove unreliable?
5. Did the eval ever run in CI / on a schedule, or was it always a manual local invocation (`python -m evals.pactatalk_eval ...`)?
6. Should the eight-axis rubric, the four aggregation groups (`routing` / `depth` / `tone` / `safety`), and the `gpt-4o-mini` judge choice still be considered the team's official quality model, or are they superseded?
7. Are the rule-pattern lists (`MECHANICAL_PATTERNS`, `BRIDGE_PATTERNS`, `SOLUTION_PATTERNS`) the same patterns now enforced server-side in `bot/services/claude_service.py` (anti-template / anti-premature-solutions guards per `gcs45_bot/CLAUDE.md:75-104`), or do they encode a different/older taxonomy?

→ prompt content of facilitator_system: see specialist #1.
→ production runtime LLM call logs and quality signals: see specialist #7.

## 7. Out-of-scope notes

- Delete the orphan `gcs45_bot/evals/__pycache__/pactatalk_eval.cpython-314.pyc` or restore the source — current state misleads readers.
