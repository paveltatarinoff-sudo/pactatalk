#!/usr/bin/env node

import fs from "node:fs";
import path from "node:path";
import process from "node:process";

const DEFAULT_BASE_URL = "https://pactatalk.app/";

function printUsage() {
  console.log(`Usage:
  npm run campaign:links -- --config campaigns/validation-wave.sample.json
  npm run campaign:links -- --source telegram --campaign post_a --content v1

Supported flags:
  --config <path>       Read batch definitions from a JSON file
  --base-url <url>      Override the landing URL (default: ${DEFAULT_BASE_URL})
  --source <value>      Acquisition source, becomes utm_source
  --campaign <value>    Campaign identifier, becomes utm_campaign
  --content <value>     Message variant, becomes utm_content
  --medium <value>      Optional utm_medium
  --term <value>        Optional utm_term
  --help                Show this message`);
}

function parseArgs(argv) {
  const args = {};

  for (let index = 0; index < argv.length; index += 1) {
    const entry = argv[index];

    if (!entry.startsWith("--")) {
      throw new Error(`Unexpected argument "${entry}". Use --help for usage.`);
    }

    const key = entry.slice(2);

    if (key === "help") {
      args.help = true;
      continue;
    }

    const value = argv[index + 1];

    if (!value || value.startsWith("--")) {
      throw new Error(`Flag "--${key}" requires a value.`);
    }

    args[key] = value;
    index += 1;
  }

  return args;
}

function normalizeToken(value) {
  const normalized = String(value ?? "")
    .trim()
    .toLowerCase()
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/&/g, " and ")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .replace(/-{2,}/g, "-");

  if (!normalized) {
    throw new Error(`Could not normalize "${value}" into a tracking token.`);
  }

  return normalized;
}

function loadConfig(configPath) {
  const absolutePath = path.resolve(process.cwd(), configPath);
  const raw = fs.readFileSync(absolutePath, "utf8");
  const parsed = JSON.parse(raw);

  if (Array.isArray(parsed)) {
    return {
      baseUrl: DEFAULT_BASE_URL,
      campaigns: parsed,
    };
  }

  if (!parsed || typeof parsed !== "object" || !Array.isArray(parsed.campaigns)) {
    throw new Error(
      `Config "${configPath}" must be an array or an object with a "campaigns" array.`,
    );
  }

  return {
    baseUrl: parsed.baseUrl ?? DEFAULT_BASE_URL,
    campaigns: parsed.campaigns,
  };
}

function readField(definition, ...keys) {
  for (const key of keys) {
    const value = definition[key];

    if (typeof value === "string" && value.trim()) {
      return value;
    }
  }

  return undefined;
}

function buildTrackedLink(definition, fallbackBaseUrl = DEFAULT_BASE_URL) {
  const baseUrl = readField(definition, "baseUrl") ?? fallbackBaseUrl;
  const sourceInput = readField(definition, "source", "utm_source");
  const campaignInput = readField(definition, "campaign", "utm_campaign");
  const contentInput = readField(
    definition,
    "content",
    "messageVariant",
    "message_variant",
    "utm_content",
  );
  const mediumInput = readField(definition, "medium", "utm_medium");
  const termInput = readField(definition, "term", "utm_term");

  if (!sourceInput) {
    throw new Error(`Missing source in definition ${JSON.stringify(definition)}.`);
  }

  if (!campaignInput) {
    throw new Error(`Missing campaign in definition ${JSON.stringify(definition)}.`);
  }

  const url = new URL(baseUrl);
  const source = normalizeToken(sourceInput);
  const campaign = normalizeToken(campaignInput);
  const content = contentInput ? normalizeToken(contentInput) : undefined;
  const medium = mediumInput ? normalizeToken(mediumInput) : undefined;
  const term = termInput ? normalizeToken(termInput) : undefined;

  url.searchParams.set("utm_source", source);
  url.searchParams.set("utm_campaign", campaign);

  if (content) {
    url.searchParams.set("utm_content", content);
  }

  if (medium) {
    url.searchParams.set("utm_medium", medium);
  }

  if (term) {
    url.searchParams.set("utm_term", term);
  }

  return {
    label: readField(definition, "name", "label") ?? `${source} / ${campaign}${content ? ` / ${content}` : ""}`,
    notes: readField(definition, "notes"),
    source,
    campaign,
    content,
    medium,
    term,
    url: url.toString(),
  };
}

function renderEntry(entry, index) {
  const lines = [
    `${index + 1}. ${entry.label}`,
    `   url: ${entry.url}`,
    `   source: ${entry.source}`,
    `   campaign: ${entry.campaign}`,
  ];

  if (entry.content) {
    lines.push(`   message_variant (utm_content): ${entry.content}`);
  }

  if (entry.medium) {
    lines.push(`   medium: ${entry.medium}`);
  }

  if (entry.term) {
    lines.push(`   term: ${entry.term}`);
  }

  if (entry.notes) {
    lines.push(`   notes: ${entry.notes}`);
  }

  return lines.join("\n");
}

function runBatch(args) {
  const { baseUrl, campaigns } = loadConfig(args.config);
  const resolvedBaseUrl = args["base-url"] ?? baseUrl;
  const rendered = campaigns.map((definition, index) =>
    renderEntry(buildTrackedLink(definition, resolvedBaseUrl), index),
  );

  console.log(`Validation wave links (${campaigns.length})\n`);
  console.log(rendered.join("\n\n"));
}

function runSingle(args) {
  const entry = buildTrackedLink(
    {
      baseUrl: args["base-url"],
      source: args.source,
      campaign: args.campaign,
      content: args.content,
      medium: args.medium,
      term: args.term,
    },
    DEFAULT_BASE_URL,
  );

  console.log(renderEntry(entry, 0));
}

function main() {
  const args = parseArgs(process.argv.slice(2));

  if (args.help) {
    printUsage();
    return;
  }

  if (args.config) {
    runBatch(args);
    return;
  }

  if (!args.source || !args.campaign) {
    printUsage();
    throw new Error("Single-link mode requires at least --source and --campaign.");
  }

  runSingle(args);
}

try {
  main();
} catch (error) {
  console.error(`Error: ${error.message}`);
  process.exit(1);
}
