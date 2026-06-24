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
