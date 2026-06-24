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
const renderSpecialistPrompt = (s) => ''
const SYNTHESIZER_PROMPT = ''

// --- orchestration --- (filled in Task 5)
phase('Discover')
await agent(SHARED_HEADER_PROMPT, { label: 'header', phase: 'Discover' })
