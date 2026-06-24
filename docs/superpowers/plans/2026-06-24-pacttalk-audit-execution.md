# PactTalk Audit — Execution Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run the parallel 10-specialist + synthesis audit defined in [docs/superpowers/specs/2026-06-24-pacttalk-audit-prompt-design.md](../specs/2026-06-24-pacttalk-audit-prompt-design.md) and produce a committed `STATE_OF_PACTTALK.md` snapshot.

**Architecture:** Single JavaScript orchestration script consumed by the `Workflow` tool. Phase 1 stamps a shared header. Phase 2 fans out 10 specialist agents in parallel (one per dimension), each writing one markdown file to `docs/audit/<date>/`. Phase 3 runs a synthesizer that reads the 10 files and writes `STATE_OF_PACTTALK.md`. The script is data-driven: specialists are an array of configs, the prompt is a single template rendered per config — no copy-paste between specialists.

**Tech Stack:** `Workflow` tool, Sonnet 4.6 / Opus 4.7 subagents, markdown output, git for snapshotting. Chrome MCP available for specialist #5 (PostHog) if the owner's browser session is still connected at run-time.

**Worktree:** Audit output lives entirely under `docs/audit/` — no source-code mutations. Safe to run on the current branch (`main`) without a worktree.

---

## File structure

**Files this plan will create:**

| Path | Owner | Purpose |
|------|-------|---------|
| `docs/audit/audit-workflow.js` | this plan | The Workflow script (meta + orchestration body + all specialist configs + prompt templates). Single file, ~600 lines. |
| `docs/audit/2026-06-24/00-shared-header.md` | Phase 1 agent | Commit SHA, timestamp, list of pre-captured data paths. |
| `docs/audit/2026-06-24/01-llm-prompts.md` | specialist 1 | LLM/prompt engineering inventory. |
| `docs/audit/2026-06-24/02-dialog-logic.md` | specialist 2 | Multi-agent / dialog logic inventory. |
| `docs/audit/2026-06-24/03-backend.md` | specialist 3 | Bot backend inventory. |
| `docs/audit/2026-06-24/04-frontend-code.md` | specialist 4 | Landing code & deploy inventory. |
| `docs/audit/2026-06-24/05-posthog.md` | specialist 5 | PostHog analytics inventory. |
| `docs/audit/2026-06-24/06-evals.md` | specialist 6 | Evals inventory. |
| `docs/audit/2026-06-24/07-deploy-infra.md` | specialist 7 | Deploy & infra inventory. |
| `docs/audit/2026-06-24/08-product-journey.md` | specialist 8 | Product end-to-end journey inventory. |
| `docs/audit/2026-06-24/09-ux-design.md` | specialist 9 | Landing UX/design audit. |
| `docs/audit/2026-06-24/10-distribution-marketing.md` | specialist 10 | Distribution & marketing surface inventory. |
| `docs/audit/2026-06-24/STATE_OF_PACTTALK.md` | synthesizer | Final synthesis. |

**Files this plan will NOT modify:** any source code in `bot/`, `gcs-landing-v2/app/`, or any config. Audit is read-only against the codebase.

---

## Why the granularity is mixed

The skill recommends 2-5 minute steps. That fits TDD on hand-written code. This plan instead authors **one orchestration script** whose meat is ten data-driven specialist configs plus a prompt template. Splitting "write specialist 1 config" / "write specialist 2 config" into ten near-identical tasks would be ceremony, not signal. So tasks 3-4 each take ~15-25 min but produce one coherent unit (the script). Verification is by dry-running the script with a single specialist, not by unit tests — there is nothing to unit-test in a prompt template.

---

## Task 1: Create the audit output directory and stub workflow script

**Files:**
- Create: `docs/audit/2026-06-24/.gitkeep`
- Create: `docs/audit/audit-workflow.js` (skeleton only)

- [ ] **Step 1: Create the dated audit folder with a .gitkeep**

```bash
mkdir -p "docs/audit/2026-06-24"
touch "docs/audit/2026-06-24/.gitkeep"
```

- [ ] **Step 2: Create the workflow script skeleton**

Write `docs/audit/audit-workflow.js`:

```javascript
export const meta = {
  name: 'pacttalk-audit',
  description: 'Parallel 10-specialist + synthesis audit of PactTalk per docs/superpowers/specs/2026-06-24-pacttalk-audit-prompt-design.md',
  whenToUse: 'Run once to produce a dated State of PactTalk snapshot. Re-run later to diff.',
  phases: [
    { title: 'Discover', detail: 'stamp shared header with commit SHA and pre-captured data paths' },
    { title: 'Specialists', detail: 'parallel fan-out of 10 dimension specialists' },
    { title: 'Synthesize', detail: 'collate the 10 specialist reports into STATE_OF_PACTTALK.md' },
  ],
}

// --- specialist configs --- (filled in Task 3)
const SPECIALISTS = []

// --- prompt templates --- (filled in Task 4)
const SHARED_HEADER_PROMPT = ''
const renderSpecialistPrompt = (s) => ''
const SYNTHESIZER_PROMPT = ''

// --- orchestration --- (filled in Task 5)
phase('Discover')
log('TODO')
```

- [ ] **Step 3: Sanity-check the skeleton parses by invoking Workflow as a dry-test**

Run via Workflow tool with `{scriptPath: "docs/audit/audit-workflow.js"}`. Expected: the run starts, logs "TODO", and exits cleanly. (The phase() call with no agents is valid.)

- [ ] **Step 4: Commit**

```bash
git add docs/audit/2026-06-24/.gitkeep docs/audit/audit-workflow.js
git commit -m "audit: scaffold workflow script and dated output folder"
```

---

## Task 2: Implement the Discover phase (shared header)

**Files:**
- Modify: `docs/audit/audit-workflow.js` (replace the Discover phase body)

- [ ] **Step 1: Write the SHARED_HEADER_PROMPT constant**

Replace `const SHARED_HEADER_PROMPT = ''` with:

```javascript
const AUDIT_DATE = '2026-06-24'
const AUDIT_DIR  = `docs/audit/${AUDIT_DATE}`

const SHARED_HEADER_PROMPT = `
You are stamping the shared header for the PactTalk audit dated ${AUDIT_DATE}.

Your one task: write the file \`${AUDIT_DIR}/00-shared-header.md\` with EXACTLY the following structure, filling in the real values:

# PactTalk audit — shared header

- Audit date: ${AUDIT_DATE}
- Commit SHA: <run \`git rev-parse HEAD\` in the repo root and paste the SHA>
- Working tree clean: <yes/no — run \`git status --porcelain | wc -l\`; "yes" if 0, else "no, N dirty paths">
- Branch: <git rev-parse --abbrev-ref HEAD>

## Pre-captured data available to specialists

- docs/audit/_data/fly/ — Fly status, secrets (names only), config, machines, recent logs, releases
- docs/audit/_data/posthog/insights-list.md — 3 custom Validation funnels + PostHog defaults
- docs/audit/_data/posthog/dashboards-list.md — dashboards list
- docs/audit/_data/posthog/TODO-for-specialist-5.md — deeper PostHog work instructions
- docs/audit/_data/landing/index.html — 70 KB SSR HTML of pactatalk.app
- tg/messages.html, tg/messages2.html — Telegram export of owner's bot test conversations

Do NOT write anything else. Do NOT add commentary outside the file. Your final text reply is irrelevant — your output is the file.
`
```

- [ ] **Step 2: Replace the Discover phase body with a real agent call**

Replace:
```javascript
phase('Discover')
log('TODO')
```
with:
```javascript
phase('Discover')
await agent(SHARED_HEADER_PROMPT, { label: 'header', phase: 'Discover' })
```

- [ ] **Step 3: Run the workflow up to end of Discover and inspect the header file**

Invoke Workflow with the updated script. Expected: `docs/audit/2026-06-24/00-shared-header.md` exists, contains a real SHA, and lists the six pre-captured data paths above.

- [ ] **Step 4: Commit**

```bash
git add docs/audit/audit-workflow.js docs/audit/2026-06-24/00-shared-header.md
git commit -m "audit: implement Discover phase (shared header)"
```

---

## Task 3: Define the 10 specialist configs

**Files:**
- Modify: `docs/audit/audit-workflow.js` (fill the `SPECIALISTS` array)

- [ ] **Step 1: Replace `const SPECIALISTS = []` with the full array**

This is the heart of the data-driven design. Every specialist has the same shape; the prompt template (Task 4) consumes these fields and renders one system prompt per specialist.

```javascript
const SPECIALISTS = [
  {
    n: 1,
    file: '01-llm-prompts.md',
    name: 'LLM / prompt engineering',
    lens: 'Prompt texts, prompt loading/composition, model selection, temperature, token budgets, context strategy, system messages.',
    scopeRoots: ['gcs45_bot/bot/services/', 'gcs45_bot/bot/handlers/', 'gcs45_bot/bot/', 'gcs45_bot/CLAUDE.md'],
    scopeHints: ['Grep for system_prompt, SYSTEM_PROMPT, facilitator prompt files, openai.ChatCompletion / client.chat.completions calls, temperature=', 'Identify where prompts live: separate .md/.txt files vs inline strings vs templates.'],
    preCapturedData: [],
    handsOffTo: [
      'Where the prompt is *called from* / dialog orchestration → specialist #2',
      'How LLM outputs are *evaluated* or scored → specialist #6',
      'Production LLM logs / token bills → specialist #7',
    ],
  },
  {
    n: 2,
    file: '02-dialog-logic.md',
    name: 'Multi-agent / dialog logic',
    lens: 'Facilitator FSM, handoff, addressed_to/next_speaker, guards, dialog orchestration, loop detection, session lifecycle.',
    scopeRoots: ['gcs45_bot/bot/fsm/', 'gcs45_bot/bot/handlers/', 'gcs45_bot/bot/services/', 'gcs45_bot/tests/'],
    scopeHints: ['Recent commits (git log --oneline -30) heavily refactored handoff: addressed_to derives next_speaker (commit f0586d9), resolve_handoff_invariants consolidates post-guards (commit 407e904).', 'Read tg/messages.html for examples of real facilitator behaviour to validate the code-level inventory.'],
    preCapturedData: ['tg/messages.html', 'tg/messages2.html'],
    handsOffTo: [
      'Prompt text itself → specialist #1',
      'Repository / persistence layer → specialist #3',
      'How well the facilitator behaves end-to-end as product UX → specialist #8',
    ],
  },
  {
    n: 3,
    file: '03-backend.md',
    name: 'Backend architecture (bot)',
    lens: 'Overall bot/ structure, repositories, services (non-LLM, non-FSM), models, migrations as code, tests, packaging.',
    scopeRoots: ['gcs45_bot/bot/repositories/', 'gcs45_bot/bot/models/', 'gcs45_bot/bot/utils/', 'gcs45_bot/migrations/', 'gcs45_bot/tests/', 'gcs45_bot/pyproject.toml', 'gcs45_bot/alembic.ini'],
    scopeHints: ['Check tests/ for coverage — what is tested, what is not. Note pytest config.', 'Look for SQLAlchemy models, Alembic migration files (latest revision).'],
    preCapturedData: [],
    handsOffTo: [
      'Prompts → specialist #1',
      'Dialog logic → specialist #2',
      'Fly / Docker / secrets / runtime → specialist #7',
      'evals/ → specialist #6',
    ],
  },
  {
    n: 4,
    file: '04-frontend-code.md',
    name: 'Frontend code & deploy (landing)',
    lens: 'Next.js app/, components, build configs, package.json, Vercel deployment target.',
    scopeRoots: ['gcs-landing-v2/app/', 'gcs-landing-v2/public/', 'gcs-landing-v2/next.config.ts', 'gcs-landing-v2/tsconfig.json', 'gcs-landing-v2/package.json', 'gcs-landing-v2/eslint.config.mjs', 'gcs-landing-v2/postcss.config.mjs'],
    scopeHints: ['Check Vercel deploy via the rendered HTML at docs/audit/_data/landing/index.html (x-vercel-cache: HIT, x-vercel-id includes fra1 region).', 'Note Next.js version and any unusual dependencies.'],
    preCapturedData: ['docs/audit/_data/landing/index.html'],
    handsOffTo: [
      'Visual quality, copy effectiveness → specialist #9',
      'Marketing content / campaigns/ → specialist #10',
      'Product narrative across landing+bot → specialist #8',
    ],
  },
  {
    n: 5,
    file: '05-posthog.md',
    name: 'PostHog analytics',
    lens: 'Events sent and from where, funnels / dashboards / cohorts configured, what is alive in the data.',
    scopeRoots: ['gcs45_bot/bot/', 'gcs-landing-v2/app/'],
    scopeHints: ['Grep posthog.capture(, posthog.identify(, posthog.alias(, $pageview, posthog.track( in bot Python and landing TypeScript.', 'Pre-captured PostHog UI snapshot in docs/audit/_data/posthog/ lists 3 Validation funnels and 2 dashboards. TODO-for-specialist-5.md tells you what deeper UI dive is required.', 'If Chrome MCP is connected, drive https://us.posthog.com/project/362123/* to capture event definitions and funnel step composition. Otherwise emit "Coverage gap: no live PostHog access" and work from pre-captured + code-side inventory only.'],
    preCapturedData: ['docs/audit/_data/posthog/insights-list.md', 'docs/audit/_data/posthog/dashboards-list.md', 'docs/audit/_data/posthog/TODO-for-specialist-5.md'],
    handsOffTo: [
      'What we *should* be measuring → specialist #8',
      'Product interpretation of the metrics → specialist #8',
    ],
  },
  {
    n: 6,
    file: '06-evals.md',
    name: 'Evals & LLM output quality',
    lens: 'evals/ directory, datasets, runners, golden examples, how systematic, what is covered.',
    scopeRoots: ['gcs45_bot/evals/'],
    scopeHints: ['Inventory all files in evals/. Classify: datasets vs runners vs prompts vs scoring code.', 'Run wc -l on each file to size the effort.', 'Check if evals have ever been run (look for outputs/, results/, or CI traces).'],
    preCapturedData: [],
    handsOffTo: [
      'The prompts being evaluated → specialist #1',
      'Production runtime LLM logs → specialist #7',
    ],
  },
  {
    n: 7,
    file: '07-deploy-infra.md',
    name: 'Deploy & infra',
    lens: 'fly.toml, Dockerfile, alembic.ini + migration execution, _deploy_gcs45_bot_alembic/, secrets management, what would prevent a restart today.',
    scopeRoots: ['gcs45_bot/fly.toml', 'gcs45_bot/Dockerfile', 'gcs45_bot/alembic.ini', '_deploy_gcs45_bot_alembic/', 'gcs45_bot/migrations/', 'docs/audit/_data/fly/'],
    scopeHints: ['All Fly state is pre-captured in docs/audit/_data/fly/ — read those files first.', 'Cross-check: are secrets in fly secrets list (docs/audit/_data/fly/secrets.txt) all referenced from code? Are any code-required env vars missing from the deployed list?', 'Note last deploy date from releases.txt — if old, flag as fragility risk (bit-rot of dependencies).'],
    preCapturedData: ['docs/audit/_data/fly/status.txt', 'docs/audit/_data/fly/secrets.txt', 'docs/audit/_data/fly/config.json', 'docs/audit/_data/fly/machines.txt', 'docs/audit/_data/fly/recent-logs.txt', 'docs/audit/_data/fly/releases.txt'],
    handsOffTo: [
      'Bot code structure → specialist #3',
      'Landing Vercel deploy → specialist #4',
    ],
  },
  {
    n: 8,
    file: '08-product-journey.md',
    name: 'Product layer / end-to-end journey',
    lens: 'Holistic landing → bot → session → outcome journey, hypotheses being tested, value delivered, product interpretation of PostHog metrics.',
    scopeRoots: ['docs/audit/_data/landing/index.html', 'gcs-landing-v2/LANDING_CONTEXT.md', 'gcs45_bot/CLAUDE.md', 'tg/messages.html', 'docs/audit/_data/posthog/'],
    scopeHints: ['Map the journey as states: landing visitor → click → Telegram open → /start → onboarding → first session → return.', 'For each state, find where it is encoded (landing copy, bot handler, FSM state) and what evidence we have it works (PostHog event, log line, real conversation in tg/).', 'Interpret PostHog Validation funnel intent from its name and the campaigns/validation-wave artifact.'],
    preCapturedData: ['docs/audit/_data/landing/index.html', 'tg/messages.html', 'tg/messages2.html', 'docs/audit/_data/posthog/insights-list.md', 'gcs-landing-v2/campaigns/validation-wave.sample.json', 'gcs-landing-v2/docs/validation-wave-operations.md'],
    handsOffTo: [
      'Site visual quality → specialist #9',
      'Positioning / channels → specialist #10',
      'Code internals → specialists #3 / #4',
    ],
  },
  {
    n: 9,
    file: '09-ux-design.md',
    name: 'UX / design audit (landing)',
    lens: 'IA, visual hierarchy, copy effectiveness, trust signals, conversion narrative, mobile/desktop responsiveness, friction points — as a visitor sees it.',
    scopeRoots: ['docs/audit/_data/landing/index.html', 'gcs-landing-v2/app/', 'gcs-landing-v2/public/'],
    scopeHints: ['If Chrome MCP is connected, drive https://pactatalk.app/ for live screenshots at desktop (1440x900) and mobile (390x844). Save them under docs/audit/2026-06-24/_screens/ (you may create that folder).', 'Critique copy: does the hero promise something concrete? Does the page answer "what is it / for whom / why now"? Are CTAs clear?', 'List friction points: jargon, missing trust signals, unclear next step, accessibility issues.'],
    preCapturedData: ['docs/audit/_data/landing/index.html'],
    handsOffTo: [
      'End-to-end journey including the bot → specialist #8',
      'Code-level Next.js inventory → specialist #4',
      'Positioning across channels → specialist #10',
    ],
  },
  {
    n: 10,
    file: '10-distribution-marketing.md',
    name: 'Distribution & marketing surface',
    lens: 'campaigns/, validation-wave artifacts, positioning in copy, audience definitions, channels mentioned/used.',
    scopeRoots: ['gcs-landing-v2/campaigns/', 'gcs-landing-v2/docs/validation-wave-operations.md', 'gcs-landing-v2/LANDING_CONTEXT.md', 'docs/audit/_data/landing/index.html'],
    scopeHints: ['Inventory exactly what is in campaigns/ — files, schemas, what each represents.', 'From validation-wave-operations.md: who was the target audience, which channels were tried, what success was defined as.', 'From the landing HTML and LANDING_CONTEXT.md: what is the positioning, what is the implicit audience.'],
    preCapturedData: ['docs/audit/_data/landing/index.html'],
    handsOffTo: [
      'Site UX quality → specialist #9',
      'Product hypothesis framing → specialist #8',
    ],
  },
]
```

- [ ] **Step 2: Sanity-check the array parses**

Re-invoke the workflow with `scriptPath`. Expected: the run completes Discover phase as before (no specialists called yet). No JS parse error.

- [ ] **Step 3: Commit**

```bash
git add docs/audit/audit-workflow.js
git commit -m "audit: define 10 specialist configs"
```

---

## Task 4: Write the specialist prompt template

**Files:**
- Modify: `docs/audit/audit-workflow.js` (replace `renderSpecialistPrompt`)

- [ ] **Step 1: Replace the stub with the real template**

```javascript
const renderSpecialistPrompt = (s) => `
You are specialist #${s.n} on the PactTalk audit dated ${AUDIT_DATE}.
Your dimension: **${s.name}**.

# Your single deliverable

Write the file \`${AUDIT_DIR}/${s.file}\` with EXACTLY the six-section schema below.
Your final text reply is irrelevant — your output is that file. Nothing else.

# Your lens

${s.lens}

# Where to look (scope roots)

${s.scopeRoots.map(p => `- ${p}`).join('\n')}

# Tips for your scope

${s.scopeHints.map(h => `- ${h}`).join('\n')}

# Pre-captured data you can read directly (already on disk, no extraction needed)

${s.preCapturedData.length ? s.preCapturedData.map(p => `- ${p}`).join('\n') : '- (none — work from the scope roots above)'}

# Linked-but-not-owned (do NOT write these sections; emit a one-line handoff note inline)

${s.handsOffTo.map(h => `- ${h}`).join('\n')}

Handoff format inside your file: a single line wherever the topic appears, e.g.
\`→ prompt content of facilitator_system: see specialist #1\`.

# Hard rules

- **Inventory only.** No recommendations on how to fix. If a fix idea is screaming, one line under \`## 7. Out-of-scope notes\`, no elaboration.
- **Every factual claim needs evidence.** Use \`file:line\` (e.g. \`bot/services/llm.py:42\`), commit SHA (\`git log\` to verify), PostHog event/dashboard URL, log excerpt. Without evidence → mark \`[unverified]\` or drop.
- **No invention.** If something is not in your scope or you cannot reach it → write "not found in scope" or "out of scope" or "coverage gap: <reason>". Do not guess.
- **Soft limit ~1500 words.** Compress \`## 2. Inventory\` first if pressed.
- **Pin to the commit SHA from \`${AUDIT_DIR}/00-shared-header.md\`.** Read it first.

# Required file structure (exact heading names, in this order)

\`\`\`
# ${s.name}

## 1. Scope covered

[What you actually examined: paths, files, services, dashboards, events.
Anything you didn't or couldn't examine: state it. Without this, the
synthesizer cannot tell whether the dimension is covered.]

## 2. Inventory

[Map of what exists. Bullet list of entities with a short role each.
Factual, not evaluative.]

## 3. State of each piece

| Item | State | Evidence |
|------|-------|----------|
| <name> | works / broken / partial / unknown | file:line, commit, log, URL |

## 4. Non-obvious decisions

[Decisions visible from code/commits/docs that aren't obvious to an outsider.
For each: what was decided, why (with evidence), or "rationale unclear".]

## 5. Risks & landmines

[What would bite if you tried to run / deploy / show this today.
For each: what it is, what happens, what trigger. Diagnosis only.]

## 6. Open questions for the owner

[Direct questions only the owner can answer from memory.]

## 7. Out-of-scope notes (optional)

[One-liners only if a fix idea was unavoidable. Skip otherwise.]
\`\`\`

Start by reading \`${AUDIT_DIR}/00-shared-header.md\` for the pinned commit SHA, then begin.
`
```

- [ ] **Step 2: Smoke-test the template by logging its render for specialist #6 (smallest scope = evals)**

Add a temporary log line *before* the agent calls in Task 5:
```javascript
log(renderSpecialistPrompt(SPECIALISTS.find(s => s.n === 6)))
```
Run the workflow. Expected: the rendered prompt appears in the Workflow log, references `evals/`, lists `## 1. Scope covered` through `## 7.`, includes the handoff-format example. Remove the temporary log line before committing.

- [ ] **Step 3: Commit**

```bash
git add docs/audit/audit-workflow.js
git commit -m "audit: add specialist prompt template"
```

---

## Task 5: Implement the Specialists phase (parallel fan-out)

**Files:**
- Modify: `docs/audit/audit-workflow.js` (add the Specialists phase body)

- [ ] **Step 1: Append the Specialists phase after the Discover phase**

After the `await agent(SHARED_HEADER_PROMPT, ...)` call in the orchestration block, append:

```javascript
phase('Specialists')
const specialistResults = await parallel(
  SPECIALISTS.map(s => () =>
    agent(renderSpecialistPrompt(s), {
      label: `#${s.n} ${s.name}`,
      phase: 'Specialists',
    })
  )
)
log(`Specialists complete: ${specialistResults.filter(Boolean).length}/${SPECIALISTS.length} returned non-null`)
```

- [ ] **Step 2: First, dry-run a single specialist (the cheapest: #6 evals)**

Temporarily replace the `SPECIALISTS.map(...)` with `[SPECIALISTS.find(s => s.n === 6)].map(...)`. Run the workflow.

Expected: `docs/audit/2026-06-24/06-evals.md` exists, has the six headings `## 1. Scope covered` through `## 6. Open questions for the owner` (and optional `## 7.`), pins to the commit SHA from `00-shared-header.md`, contains evidence-backed entries (file paths under `gcs45_bot/evals/`).

If the file is malformed: edit `renderSpecialistPrompt` to tighten constraints, rerun. Iterate until #6 produces a clean file.

- [ ] **Step 3: Restore the full SPECIALISTS array and run all 10 in parallel**

Revert the dry-run filter. Run the workflow.

Expected: all 10 files appear under `docs/audit/2026-06-24/0X-*.md`. The `log(...)` line reports `10/10`. Walltime: ~10-20 min depending on dimension complexity.

- [ ] **Step 4: Spot-check 3 specialist outputs for schema compliance**

Open the produced files for specialists #1 (LLM/prompts), #5 (PostHog), and #9 (UX). For each, verify:
- All six required headings are present in order.
- `## 3. State of each piece` is a table with `Item | State | Evidence` columns.
- Hard rules are followed: no recommendations outside `## 7.`, every claim has evidence or `[unverified]`, no invented facts.
- Word count is in the rough vicinity of 1500 (use `wc -w docs/audit/2026-06-24/0X-*.md`).

If any file is non-compliant, identify what rule was broken, tighten the prompt template, re-run *that* specialist only by filtering as in Step 2.

- [ ] **Step 5: Commit the 10 specialist files together with the workflow change**

```bash
git add docs/audit/audit-workflow.js docs/audit/2026-06-24/*.md
git commit -m "audit: run 10-specialist fan-out, produce dimension reports"
```

---

## Task 6: Write the synthesizer prompt

**Files:**
- Modify: `docs/audit/audit-workflow.js` (replace `SYNTHESIZER_PROMPT`)

- [ ] **Step 1: Replace the stub with the real prompt**

```javascript
const SYNTHESIZER_PROMPT = `
You are the synthesizer for the PactTalk audit dated ${AUDIT_DATE}.

# Your single deliverable

Write the file \`${AUDIT_DIR}/STATE_OF_PACTTALK.md\` with the structure below.
Your final text reply is irrelevant — your output is that file.

# Hard rules

- **You may NOT introduce any fact that is not in one of the 10 specialist files** under \`${AUDIT_DIR}/\`. You collate, deduplicate, and flag contradictions. You do not analyze the codebase yourself.
- Every claim cites at least one source: \`[#N]\` (the specialist file number). Multiple sources welcome: \`[#3, #7]\`.
- If two specialists disagree on a fact, do NOT pick a side. Record the disagreement in the "Contradictions" section.
- If a specialist's "Scope covered" section reports a coverage gap, surface it in the "Coverage gaps" section.

# Inputs

Read every file under \`${AUDIT_DIR}/\` matching \`0[1-9]-*.md\` and \`10-*.md\` (the 10 specialist reports) plus \`00-shared-header.md\` (for date/SHA).

# Required file structure (exact heading names)

\`\`\`
# State of PactTalk — ${AUDIT_DATE}, commit <SHA from 00-shared-header.md>

## TL;DR

[≤10 lines. What the owner needs to know right now.]

## What's solid

[Things shippable / demonstrable today. Pointers to specific modules/files. Cite specialists.]

## What's broken or fragile

[What will bite on first attempt to run or show. Each item: trigger + evidence + specialist citation.]

## What was tried and abandoned

[Traces of experiments and dropped branches. Cite specialists.]

## Cross-cutting risks

[Risks that touch ≥2 dimensions. Cite all relevant specialists.]

## Non-obvious decisions worth preserving

[Strong decisions not obvious from code — case-material. Cite specialists.]

## Coverage gaps

[Where specialists hit walls. Cite which specialist reported the gap.]

## Open questions for the owner

[Grouped questions from all 10 specialists' "## 6." sections. Cite each.]

## Contradictions between specialists

[Where specialists disagreed on a fact. No "winner" picked.]

## Per-dimension scorecard

| # | Dimension | Maturity finding (raw) | Key evidence | Top risk | Top open question |
|---|-----------|------------------------|--------------|----------|-------------------|
| 1 | LLM/prompts | ... | ... | ... | ... |
... (one row per dimension #1–#10)
\`\`\`
`
```

- [ ] **Step 2: Commit**

```bash
git add docs/audit/audit-workflow.js
git commit -m "audit: add synthesizer prompt"
```

---

## Task 7: Implement the Synthesize phase + commit the audit folder

**Files:**
- Modify: `docs/audit/audit-workflow.js` (add Synthesize phase body and a final log)

- [ ] **Step 1: Append the Synthesize phase**

After the Specialists `log(...)` line, append:

```javascript
phase('Synthesize')
await agent(SYNTHESIZER_PROMPT, { label: 'synth', phase: 'Synthesize' })
log(`Audit complete. Output: ${AUDIT_DIR}/STATE_OF_PACTTALK.md`)
```

- [ ] **Step 2: Run the full workflow**

Invoke Workflow with the script. Expected: Discover (1 agent) → Specialists (10 parallel agents) → Synthesize (1 agent). Final log reports the output path. `docs/audit/2026-06-24/STATE_OF_PACTTALK.md` exists.

- [ ] **Step 3: Spot-check the synthesis output**

Open `STATE_OF_PACTTALK.md`. Verify:
- All required sections present in order.
- TL;DR is ≤10 lines.
- Every claim has at least one `[#N]` citation.
- The "Per-dimension scorecard" has exactly 10 rows.
- "Contradictions between specialists" section exists (may be empty).
- "Coverage gaps" includes specialist #5's PostHog gap if Chrome MCP wasn't reached.

If non-compliant, tighten the synthesizer prompt and re-run only Phase 3 by temporarily commenting out the Discover and Specialists phases in the script (their outputs already exist on disk, the synth reads them from there).

- [ ] **Step 4: Commit the synthesis + final workflow**

```bash
git add docs/audit/audit-workflow.js docs/audit/2026-06-24/STATE_OF_PACTTALK.md
git commit -m "audit: run synthesis, produce STATE_OF_PACTTALK"
```

---

## Task 8: Tag the working state and present to owner

**Files:** none (git tag + user-facing summary)

- [ ] **Step 1: Tag the audit snapshot**

```bash
git tag audit-2026-06-24 && git push origin audit-2026-06-24
```

This enables instant return to this exact state with `git checkout audit-2026-06-24`.

- [ ] **Step 2: Hand the report to the owner**

Print to chat:
- Path to `STATE_OF_PACTTALK.md` as a clickable link.
- One-line summary lifted from its TL;DR.
- Note: deeper dives (e.g. specialist #5 PostHog) may have flagged coverage gaps — owner reviews them in `## Coverage gaps` section and decides whether to re-run individual specialists with extra access.

- [ ] **Step 3: Mark plan complete**

No more steps. The follow-up brainstorms (marketing strategy, builder self-assessment) are out of scope per spec section 9.

---

## Self-review checklist (done before save)

- **Spec coverage:** every section of the spec maps to at least one task. Sections 3 (10 specialists) → Task 3. Section 4 (schema) → Task 4 (rendered in template). Section 5 (synthesis) → Task 6. Section 6 (layout) → Task 1 + outputs of Tasks 2/5/7. Section 7 (pre-captured data) → referenced in Tasks 2 and 3. Section 8 (execution) → Tasks 2/5/7. Section 9 (out of scope) → respected by absence of tasks. ✓
- **Placeholders:** none. Every step shows the actual code/command/expected output.
- **Type consistency:** `SPECIALISTS`, `renderSpecialistPrompt`, `SHARED_HEADER_PROMPT`, `SYNTHESIZER_PROMPT`, `AUDIT_DATE`, `AUDIT_DIR` named consistently across tasks.
- **No invented references:** all paths (file paths, scope roots, pre-captured data) verified to exist or to be the planned output of a prior step.
