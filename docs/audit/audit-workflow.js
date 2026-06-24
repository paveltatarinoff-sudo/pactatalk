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

// --- prompt templates --- (filled in Task 4)
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
const SYNTHESIZER_PROMPT = ''

// --- orchestration --- (filled in Task 5)
phase('Discover')
await agent(SHARED_HEADER_PROMPT, { label: 'header', phase: 'Discover' })
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
