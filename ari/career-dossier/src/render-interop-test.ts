import { stableJson } from "./canonical.ts";
import { readProjectJson } from "./paths.ts";
import type { JsonObject } from "./types.ts";

export interface InteropTestClaim extends JsonObject {
  id: string;
  title: string;
  claim: string;
  asOf: string;
  evidenceLevel: "synthetic-test";
  evidenceIds: string[];
  limitations: string[];
}

export interface InteropTestCorpus extends JsonObject {
  schemaVersion: 1;
  corpusType: "synthetic-retrieval-test";
  disclaimer: string;
  profile: { name: string; headline: string; summary: string; website: string };
  claims: InteropTestClaim[];
}

function object(value: unknown, path: string): Record<string, unknown> {
  if (value === null || typeof value !== "object" || Array.isArray(value)) throw new Error(`${path}: expected object`);
  return value as Record<string, unknown>;
}

function exactKeys(value: Record<string, unknown>, expected: string[], path: string): void {
  const actual = Object.keys(value).sort((left, right) => left.localeCompare(right, "en"));
  const sortedExpected = expected.slice().sort((left, right) => left.localeCompare(right, "en"));
  if (JSON.stringify(actual) !== JSON.stringify(sortedExpected)) throw new Error(`${path}: unexpected properties`);
}

function text(value: unknown, path: string): string {
  if (typeof value !== "string" || value.length === 0) throw new Error(`${path}: expected non-empty string`);
  return value;
}

function strings(value: unknown, path: string): string[] {
  if (!Array.isArray(value) || value.some((item) => typeof item !== "string" || item.length === 0)) {
    throw new Error(`${path}: expected string array`);
  }
  return value as string[];
}

function validateInteropTestCorpus(value: unknown): InteropTestCorpus {
  const corpus = object(value, "interop-test");
  exactKeys(corpus, ["schemaVersion", "corpusType", "disclaimer", "profile", "claims"], "interop-test");
  if (corpus.schemaVersion !== 1) throw new Error("interop-test/schemaVersion: expected 1");
  if (corpus.corpusType !== "synthetic-retrieval-test") throw new Error("interop-test/corpusType: unexpected value");
  text(corpus.disclaimer, "interop-test/disclaimer");

  const profile = object(corpus.profile, "interop-test/profile");
  exactKeys(profile, ["name", "headline", "summary", "website"], "interop-test/profile");
  text(profile.name, "interop-test/profile/name");
  text(profile.headline, "interop-test/profile/headline");
  text(profile.summary, "interop-test/profile/summary");
  if (!text(profile.website, "interop-test/profile/website").startsWith("https://")) {
    throw new Error("interop-test/profile/website: expected HTTPS URL");
  }

  if (!Array.isArray(corpus.claims) || corpus.claims.length !== 6) throw new Error("interop-test/claims: expected exactly six claims");
  const ids = new Set<string>();
  for (const [index, rawClaim] of corpus.claims.entries()) {
    const path = `interop-test/claims/${index}`;
    const claim = object(rawClaim, path);
    exactKeys(claim, ["id", "title", "claim", "asOf", "evidenceLevel", "evidenceIds", "limitations"], path);
    const id = text(claim.id, `${path}/id`);
    if (!/^TEST-Q7M-[0-9]{3}$/u.test(id)) throw new Error(`${path}/id: unexpected format`);
    if (ids.has(id)) throw new Error(`${path}/id: duplicate ${id}`);
    ids.add(id);
    text(claim.title, `${path}/title`);
    text(claim.claim, `${path}/claim`);
    if (!/^\d{4}-\d{2}-\d{2}$/u.test(text(claim.asOf, `${path}/asOf`))) throw new Error(`${path}/asOf: expected date`);
    if (claim.evidenceLevel !== "synthetic-test") throw new Error(`${path}/evidenceLevel: unexpected value`);
    if (strings(claim.evidenceIds, `${path}/evidenceIds`).length !== 0) throw new Error(`${path}/evidenceIds: expected empty array`);
    if (strings(claim.limitations, `${path}/limitations`).length === 0) throw new Error(`${path}/limitations: expected at least one limitation`);
  }
  return value as InteropTestCorpus;
}

export async function loadInteropTestCorpus(): Promise<InteropTestCorpus> {
  return validateInteropTestCorpus(await readProjectJson("examples/synthetic/interop-test-corpus.json"));
}

function escapeHtml(value: string): string {
  return value.replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;");
}

export function renderInteropTestJson(corpus: InteropTestCorpus): string {
  return stableJson(corpus);
}

export function renderInteropTestHtml(corpus: InteropTestCorpus): string {
  const claims = corpus.claims.map((claim) => `
      <section class="claim" id="${escapeHtml(claim.id)}" data-claim-id="${escapeHtml(claim.id)}">
        <p class="claim__id">${escapeHtml(claim.id)}</p>
        <h2>${escapeHtml(claim.title)}</h2>
        <p class="claim__text">${escapeHtml(claim.claim)}</p>
        <dl>
          <dt>As of</dt><dd>${escapeHtml(claim.asOf)}</dd>
          <dt>Evidence level</dt><dd>${escapeHtml(claim.evidenceLevel)}</dd>
          <dt>Evidence IDs</dt><dd>${claim.evidenceIds.length === 0 ? "none" : claim.evidenceIds.map(escapeHtml).join(", ")}</dd>
          <dt>Limitations</dt><dd>${claim.limitations.map(escapeHtml).join("; ")}</dd>
        </dl>
      </section>`).join("");

  return `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="description" content="A fictional same-origin dossier for testing AI-assistant retrieval across HTML and JSON.">
  <meta name="robots" content="index,follow">
  <meta name="theme-color" content="#f4f2ec">
  <link rel="canonical" href="https://agent.johndifini.com/interop-test">
  <link rel="alternate" type="application/json" href="/interop-test.json" title="Synthetic retrieval-test JSON">
  <link rel="icon" type="image/png" href="/favicon.png">
  <title>Synthetic retrieval test — ${escapeHtml(corpus.profile.name)}</title>
  <style>
    :root { color-scheme: light; --canvas:#f4f2ec; --surface:#fff; --ink:#191919; --muted:#62615c; --line:#d4d0c5; --accent:#006b20; --accent-bright:#26ff00; --focus:#d43e00; font-family:Inter,ui-sans-serif,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; line-height:1.5; }
    * { box-sizing:border-box; } html { background:var(--canvas); }
    body { min-width:20rem; margin:0; color:var(--ink); background:linear-gradient(135deg,rgb(38 255 0 / 6%) 0,transparent 34rem),var(--canvas); }
    a { color:inherit; text-underline-offset:.2em; } a:hover { color:var(--accent); }
    :focus-visible { outline:.2rem solid var(--focus); outline-offset:.2rem; }
    .shell { width:min(74rem,calc(100% - 2rem)); margin-inline:auto; } header { padding:2.5rem 0 1.5rem; }
    .eyebrow,.claim__id { margin:0 0 .6rem; color:var(--accent); font-size:.78rem; font-weight:780; letter-spacing:.12em; text-transform:uppercase; }
    h1 { max-width:18ch; margin:0; font-size:clamp(2.4rem,6vw,4rem); line-height:1; }
    .lede { max-width:48rem; color:var(--muted); font-size:1.1rem; }
    .notice { margin:1.5rem 0 0; padding:1rem 1.2rem; border-left:.4rem solid var(--accent-bright); background:var(--surface); font-weight:650; }
    main { display:grid; gap:1rem; padding:1rem 0 3rem; }
    .claim { padding:clamp(1.25rem,3vw,2rem); border:1px solid var(--line); border-radius:1rem; background:var(--surface); }
    .claim h2 { margin:0; font-size:1.35rem; } .claim__text { max-width:70ch; font-size:1.05rem; }
    dl { display:grid; grid-template-columns:minmax(8rem,12rem) 1fr; gap:.45rem 1rem; margin:1.25rem 0 0; }
    dt { color:var(--muted); font-weight:700; } dd { margin:0; }
    footer { padding:1.25rem 0 2.5rem; border-top:1px solid var(--line); } nav { display:flex; flex-wrap:wrap; gap:1rem; font-size:.9rem; font-weight:680; }
    @media (max-width:34rem) { .shell { width:min(100% - 1.25rem,74rem); } dl { grid-template-columns:1fr; } dd + dt { margin-top:.6rem; } }
    @media (prefers-color-scheme:dark) { :root { color-scheme:dark; --canvas:#11120f; --surface:#1b1c19; --ink:#f3f1ea; --muted:#b7b5ad; --line:#3f403a; --accent:#26ff00; --focus:#ff9c73; } body { background:linear-gradient(135deg,rgb(30 197 3 / 9%) 0,transparent 34rem),var(--canvas); } }
  </style>
</head>
<body data-corpus-type="${escapeHtml(corpus.corpusType)}">
  <header class="shell">
    <p class="eyebrow">Synthetic AI retrieval experiment</p>
    <h1>${escapeHtml(corpus.profile.name)}</h1>
    <p class="lede">${escapeHtml(corpus.profile.headline)}. ${escapeHtml(corpus.profile.summary)}</p>
    <p class="notice">${escapeHtml(corpus.disclaimer)}</p>
  </header>
  <main class="shell" id="main-content">${claims}
  </main>
  <footer><nav class="shell" aria-label="Synthetic retrieval-test resources">
    <a href="/">Career dossier home</a><a href="/interop-test.json">Equivalent synthetic JSON</a>
  </nav></footer>
</body>
</html>
`;
}
