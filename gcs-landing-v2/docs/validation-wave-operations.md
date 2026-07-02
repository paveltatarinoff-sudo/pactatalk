# Validation Wave Operations

Operational notes for the current validation wave. This is intentionally narrow: generate clean tracking links, launch real posts, and read conversion honestly in PostHog.

## What this is for

- The analytics funnel is already live end-to-end.
- The operational risk now is inconsistent naming or manually assembled links.
- This workflow keeps `source`, `campaign`, and `message_variant` consistent before launch.

## Naming convention

Recommended field ownership:

- `utm_source`: where the click happened
  - Examples: `telegram`, `founder-dm`, `partner-community`
- `utm_campaign`: the placement or hypothesis you want to compare in the funnel
  - Examples: `post-a`, `dm-intro`, `channel-reviewers`
- `utm_content`: the message variant
  - Examples: `v1`, `v2`, `long`, `soft-hook`

Rules:

- Use lowercase Latin characters, digits, and hyphens only.
- Avoid spaces, underscores, Cyrillic, and punctuation in final values.
- Change `utm_content` when copy changes but the same placement/hypothesis stays the same.
- Change `utm_campaign` when the placement or comparison bucket changes.
- Keep `utm_source` stable for the distribution surface.

Even if someone enters `post_a` or `founder dm`, the generator normalizes it to hyphenated tokens so PostHog filters stay predictable.

## Link generator

Generate a batch from a config:

```bash
cd "/Users/pashkamoroz/Documents/Ai family coach/gcs-landing-v2"
npm run campaign:links -- --config campaigns/validation-wave.sample.json
```

Generate a single link on the fly:

```bash
cd "/Users/pashkamoroz/Documents/Ai family coach/gcs-landing-v2"
npm run campaign:links -- --source telegram --campaign post_a --content v1
```

Example output:

```text
1. telegram / post-a / v1
   url: https://pactatalk.app/?utm_source=telegram&utm_campaign=post-a&utm_content=v1
   source: telegram
   campaign: post-a
   message_variant (utm_content): v1
```

## Suggested launch workflow

1. Add or edit planned links in `campaigns/validation-wave.sample.json` or copy it into a wave-specific file.
2. Generate links with the script and paste them into posts, announcements, or DMs.
3. After the first live click, verify that `landing_view` and `click_to_telegram` arrive with the expected normalized `campaign`.
4. Read campaign performance in PostHog via `Validation / Full Funnel`.

## PostHog reading notes

- To compare campaigns, use breakdown by `campaign`.
- To inspect one campaign, filter the first step `landing_view` by the normalized `campaign` value.
- Example: if the input was `post_a`, filter using `campaign = post-a`.

## Recommended next extension

If the team starts actively comparing distribution surfaces or copy variants in PostHog, the next safe step is to add saved views with:

- breakdown by `source`
- breakdown by `message_variant` or the property currently backed by `utm_content`
