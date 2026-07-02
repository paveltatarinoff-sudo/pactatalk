# PactTalk audit — prompt design

**Date:** 2026-06-24
**Owner:** Pavel Tatarinov
**Status:** Design approved (pending owner review of this file)
**Next step:** writing-plans skill produces the executable plan

---

## 1. Why this exists

PactTalk (Telegram couples-therapy bot + Next.js landing at `pactatalk.app` + PostHog analytics) was actively built and then paused for several months. The owner wants to **reanimate** the project — first by knowing exactly what is there, in what state, and what was decided. The output is one self-contained snapshot that the owner can later turn into:

- a portfolio case (hybrid AI-engineer + product-mindset positioning)
- a remediation roadmap (separate work, not in scope here)
- a marketing/distribution strategy (separate work, not in scope here)

**Scope of this artifact: inventory only.** No fixes proposed, no roadmap, no recommendations beyond `## 7. Out-of-scope notes` one-liners per specialist. Evaluation only.

## 2. Approach: parallel fan-out by dimension + synthesis

Ten specialist agents run in parallel, each owning one dimension under one lens. Each writes a markdown document with an identical six-section schema. A synthesis agent then assembles the ten reports into `STATE_OF_PACTTALK.md`. The synthesizer does not invent facts — only collates, deduplicates, and flags contradictions.

Why parallel: project is clearly partitioned along orthogonal axes (Python bot / Next.js landing / PostHog / prompts / infra); each can be examined independently; the synthesis is mechanical when the schema is uniform.

## 3. The ten specialists

Boundaries are defined by **lens**, not by artifact. Two specialists may read the same file under different lenses — that is expected and not a duplication.

| # | Dimension | Owns (lens) | Hands off to |
|---|-----------|-------------|--------------|
| 1 | LLM/prompt engineering | prompt texts, prompt loading/composition, temperature, token budgets, context strategy, system messages | call sites → #2; output quality → #6 |
| 2 | Multi-agent / dialog logic | facilitator FSM, handoff, `addressed_to`/`next_speaker`, guards, orchestration code in `bot/fsm/`, `bot/handlers/`, handoff services | prompt text → #1; persistence → #3 |
| 3 | Backend architecture (bot) | overall `bot/` structure, repositories, services (non-LLM, non-FSM), models, migrations-as-code, tests, packaging | prompts → #1; dialog logic → #2; fly.toml/Docker/secrets → #7; evals → #6 |
| 4 | Frontend code & deploy (landing) | Next.js `app/`, components, build configs (next/tsconfig/eslint/postcss), `package.json`, Vercel deployment target | visual quality & copy → #9; marketing content in `campaigns/` → #10 |
| 5 | PostHog analytics | events sent and from where (event calls in bot + landing), funnels/dashboards/cohorts currently configured, what is alive in the data | what we *should* measure → #8; product interpretation of metrics → #8 |
| 6 | Evals & LLM output quality | `evals/` directory, datasets, runners, golden examples, how systematic, what is covered | prompts themselves → #1; prod LLM logs → #7 |
| 7 | Deploy & infra | `fly.toml`, `Dockerfile`, `alembic.ini` + migration execution, `_deploy_gcs45_bot_alembic/`, secrets management, what would prevent a restart today | code structure → #3; landing deploy → #4 |
| 8 | Product layer / end-to-end journey | the holistic landing → bot → session → outcome journey, hypotheses being tested, value delivered, product interpretation of PostHog metrics | site aesthetics → #9; positioning/channels → #10; code internals → #3/#4 |
| 9 | UX/design audit (landing) | IA, visual hierarchy, copy effectiveness, trust signals, conversion narrative, mobile/desktop responsiveness, friction points — as a visitor sees it | end-to-end including bot → #8; code → #4; positioning across channels → #10 |
| 10 | Distribution & marketing surface | `campaigns/` (validation-wave), validation-wave operations doc, positioning in copy, audience definitions, channels mentioned/used | site UX quality → #9; product hypotheses framing → #8 |

### Mechanisms against gaps and duplication

1. **"Linked but not owned" block** — each specialist's system prompt lists 2-3 sibling specialists whose lenses touch the same artifacts, with explicit instruction "if you see X under sibling's lens → emit a one-line handoff note inline (`→ <topic>: see specialist #N`), do not write that section yourself."
2. **"Coverage gap" flag** — section `## 1. Scope covered` of every specialist must explicitly state where the specialist hit a wall (no access, no logs, couldn't reproduce). The synthesizer reports these gaps in the final document.
3. **Single commit SHA** — all 10 specialists pin to one repo commit, recorded in `00-shared-header.md`. No race-condition on "which version did agent X read."

## 4. Uniform output schema

Every specialist returns one markdown document with these sections in this order:

```
# <Dimension name>

## 1. Scope covered
What the specialist actually examined: paths, files, directories, services,
dashboards, events. Anything not examined: "out of scope" or "couldn't access".
Without this, the synthesizer cannot tell whether the dimension is covered.

## 2. Inventory
Map of what exists. Bullet list of entities with a short role each.
Factual, not evaluative.

## 3. State of each piece
Table: Item | State (works / broken / partial / unknown) | Evidence (file:line,
commit SHA, log excerpt, screenshot). No evidence → row does not count;
write "unknown" instead of guessing.

## 4. Non-obvious decisions
Decisions visible from code/commits/docs that are not obvious to an outsider:
why this way and not another. If "why" is not recoverable: "decision made
(evidence: X), rationale unclear". Gold for case-building and self-assessment.

## 5. Risks & landmines
What would bite if you tried to run / deploy / show this today. For each:
what it is, what happens, what trigger. Diagnosis only — no fixes.

## 6. Open questions for the owner
Questions the specialist could not answer from artifacts — only the owner can.
Direct, not rhetorical.

## 7. Out-of-scope notes (optional, one-liners)
If a fix idea is screaming, here, one line, no elaboration.
```

### Hard rules for every specialist

- **No recommendations on how to fix.** This is inventory, not remediation.
- **Every factual claim needs evidence** (`file:line`, commit SHA, PostHog event name, dashboard URL). Without evidence → mark `[unverified]` or drop.
- **No invention.** If not found → `not found in scope`, never "probably exists somewhere."
- **Soft word limit ~1500 per specialist** so the synthesizer can absorb all 10 without drowning. If pressed for space, compress "Inventory" first.

## 5. Synthesis report

The synthesizer receives 10 markdown documents matching the schema above and produces `STATE_OF_PACTTALK.md`:

```
# State of PactTalk — <YYYY-MM-DD>, commit <sha>

## TL;DR (≤10 lines)
What the owner needs to know right now. No water.

## What's solid
Things shippable / demonstrable today without embarrassment.
Pointers to specific modules/files.

## What's broken or fragile
What will bite on first attempt to run or show. Each item: trigger + evidence.

## What was tried and abandoned
Traces of experiments and dropped branches — so we don't repeat them and
so we remember the context of past decisions.

## Cross-cutting risks
Risks that touch ≥2 dimensions (e.g. bot migration breaks a PostHog event
that powers a funnel dashboard).

## Non-obvious decisions worth preserving
Strong decisions not obvious from code — material for the future case.

## Coverage gaps
Where specialists hit walls. So we know what we do not know.

## Open questions for the owner
Grouped questions from all 10 specialists; only the owner can answer.

## Contradictions between specialists
If #5 says "event X is sent" and #3 finds no such call in code — recorded
here, no "winner" picked.

## Per-dimension scorecard
Table: dimension | maturity (raw finding, not score) | key evidence | top
risk | top open question. One row per dimension.
```

The synthesizer is forbidden from introducing facts that are not in any of the 10 specialist reports.

## 6. Artifact layout on disk

```
docs/audit/<YYYY-MM-DD>/
├── 00-shared-header.md            ← commit SHA, date, tools used
├── 01-llm-prompts.md
├── 02-dialog-logic.md
├── 03-backend.md
├── 04-frontend-code.md
├── 05-posthog.md
├── 06-evals.md
├── 07-deploy-infra.md
├── 08-product-journey.md
├── 09-ux-design.md
├── 10-distribution-marketing.md
└── STATE_OF_PACTTALK.md            ← synthesis
```

The folder is committed to git → owner has a dated snapshot, future audits can diff.

## 7. Pre-captured data (already on disk)

Done by orchestrator before audit runs so specialists do not have to re-fetch:

- `docs/audit/_data/fly/` — `status.txt`, `secrets.txt` (names only, no values), `config.json`, `machines.txt`, `recent-logs.txt`, `releases.txt`. For specialist #7.
- `docs/audit/_data/posthog/insights-list.md` — 3 custom Validation funnels + 6 PostHog defaults. For specialist #5.
- `docs/audit/_data/posthog/dashboards-list.md` — 2 dashboards (1 user, 1 default). For specialist #5.
- `docs/audit/_data/posthog/TODO-for-specialist-5.md` — instructions for the deeper PostHog dive (events list, funnel step composition, code↔PostHog reconciliation) that specialist #5 must do itself via Chrome MCP.
- `docs/audit/_data/landing/index.html` — 70 KB Vercel-rendered SSR HTML of `pactatalk.app`. For specialists #4 / #9 / #10.
- `/Users/pashkamoroz/Documents/PAVEL AI/projects/ai-family-coach/tg/messages.html` and `messages2.html` — Telegram Desktop export of owner's bot test conversations (~1.3 MB). For specialists #2 / #8.

## 8. Execution plan (will be detailed by writing-plans)

The audit will be orchestrated by the `Workflow` tool:

- Phase 1 ("Discover") — single fast agent stamps `00-shared-header.md` with the current commit SHA, ensures all pre-captured data is in place.
- Phase 2 ("Specialists") — `parallel()` over 10 specialist agents, each producing one file under the audit folder. Each gets:
  - the shared header
  - paths to the pre-captured data relevant to their lens
  - their "linked but not owned" list of sibling lenses
  - the output schema reminder
  - the hard rules
- Phase 3 ("Synthesize") — single synthesizer reads the 10 files, writes `STATE_OF_PACTTALK.md`, commits the folder.

Concurrency: 10 specialists hit the harness cap (~10-16 concurrent agents) but fit. Specialist runtime expected: 5-15 min per specialist depending on dimension; synthesizer ~3-5 min.

**External-access prerequisite for specialist #5:** PostHog deep dive requires a live Chrome MCP connection to the owner's logged-in browser session. If absent at execution time, specialist #5 falls back to "Coverage gap: no live PostHog access" and works only from pre-captured `_data/posthog/` files + code-side event-call inventory. This is acceptable degradation, not a failure.

## 9. Out of scope (explicitly deferred)

- Remediation, fixes, redesigns.
- Marketing strategy / user acquisition planning.
- Self-assessment of the builder.
- Production redeploy of bot or landing.
- Migration between PostHog instances (US vs EU).

## 10. Open questions for the design itself

- None at time of writing. If owner sees a gap during review, file goes back to brainstorming, otherwise we proceed to writing-plans.
