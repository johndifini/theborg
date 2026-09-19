import assert from "node:assert/strict";
import test from "node:test";
import { normalizeCorpus } from "../src/canonical.ts";
import { renderCareerJson } from "../src/render-career-json.ts";
import { renderCareerMarkdown } from "../src/render-career-markdown.ts";
import { renderEvidence } from "../src/render-evidence.ts";
import { renderLandingPage } from "../src/render-landing-page.ts";
import { loadInteropTestCorpus, renderInteropTestHtml, renderInteropTestJson } from "../src/render-interop-test.ts";
import { renderLlmsTxt } from "../src/render-llms-txt.ts";
import type { PublicClaim, PublicEvidence } from "../src/types.ts";
import { loadAndValidateCorpus } from "../src/validate.ts";
import { fixture } from "./helpers.ts";

test("all renderers expose retrieval routes and bounded guidance", async () => {
  const corpus = normalizeCorpus(await loadAndValidateCorpus());
  const html = await renderLandingPage(corpus);
  assert.match(html, /\/career\.json/u);
  assert.match(html, /\/interop-test/u);
  assert.match(html, /strong matches, partial matches, and gaps/u);
  assert.match(renderLlmsTxt(corpus), /Do not infer qualifications/u);
  assert.doesNotMatch(renderLlmsTxt(corpus), /ignore (?:all|previous) instructions/iu);
  assert.equal(JSON.parse(renderEvidence(corpus)).evidence.length, corpus.evidence.length);
});

test("every claim occurs once as a canonical record and one Markdown heading", async () => {
  const corpus = normalizeCorpus(await loadAndValidateCorpus());
  const json = JSON.parse(renderCareerJson(corpus)) as { claims: Array<{ id: string }> };
  const markdown = renderCareerMarkdown(corpus);
  for (const claim of corpus.claims) {
    assert.equal(json.claims.filter((item) => item.id === claim.id).length, 1);
    assert.equal(markdown.split(`### ${claim.id}:`).length - 1, 1);
  }
});

test("candidate-controlled evidence is explicitly labeled", async () => {
  const base = await loadAndValidateCorpus();
  const corpus = normalizeCorpus({
    ...base,
    claims: [await fixture("examples/synthetic/public-claim-completed.json") as PublicClaim],
    evidence: [await fixture("examples/synthetic/public-evidence.json") as PublicEvidence]
  });
  assert.match(renderCareerMarkdown(corpus), /candidate-controlled/u);
  assert.match(renderLlmsTxt(corpus), /self-published, not independent verification/u);
});

function escapedPattern(value: string): RegExp {
  return new RegExp(value.replace(/[.*+?^${}()|[\]\\]/gu, "\\$&"), "u");
}

test("synthetic interop HTML visibly renders the complete JSON corpus", async () => {
  const corpus = await loadInteropTestCorpus();
  const html = renderInteropTestHtml(corpus);
  const json = JSON.parse(renderInteropTestJson(corpus)) as typeof corpus;

  assert.equal(json.profile.name, "Avery Northstar");
  assert.match(html, /This is fictional test data/u);
  assert.match(html, /rel="canonical" href="https:\/\/agent\.johndifini\.com\/interop-test"/u);
  assert.match(html, /rel="alternate" type="application\/json" href="\/interop-test\.json"/u);
  assert.match(html, /<meta name="robots" content="index,follow">/u);
  assert.doesNotMatch(html, /<script\b/iu);
  for (const artifact of [html, renderInteropTestJson(corpus)]) assert.doesNotMatch(artifact, /John DiFini/u);
  assert.doesNotMatch(html, /\bRB-[0-9]+\b/u);

  for (const claim of json.claims) {
    assert.equal(html.split(`data-claim-id="${claim.id}"`).length - 1, 1);
    assert.match(html, escapedPattern(claim.claim));
    for (const limitation of claim.limitations) assert.match(html, escapedPattern(limitation));
  }
});

test("synthetic interop corpus preserves distinctive retrieval sentinels", async () => {
  const corpus = await loadInteropTestCorpus();
  const rendered = `${renderInteropTestHtml(corpus)}\n${renderInteropTestJson(corpus)}`;
  for (const sentinel of [
    "Avery Northstar",
    "TEST-Q7M-102",
    "Cobalt Kestrel",
    "47 minutes to 11 minutes",
    "26 completed and 2 deferred",
    "did not own the compliance program",
    "no production Rust experience is claimed"
  ]) assert.match(rendered, escapedPattern(sentinel));
});
