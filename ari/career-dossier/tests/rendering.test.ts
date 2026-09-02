import assert from "node:assert/strict";
import test from "node:test";
import { normalizeCorpus } from "../src/canonical.ts";
import { renderCareerJson } from "../src/render-career-json.ts";
import { renderCareerMarkdown } from "../src/render-career-markdown.ts";
import { renderEvidence } from "../src/render-evidence.ts";
import { renderLandingPage } from "../src/render-landing-page.ts";
import { renderLlmsTxt } from "../src/render-llms-txt.ts";
import { loadAndValidateCorpus } from "../src/validate.ts";

test("all renderers expose retrieval routes and bounded guidance", async () => {
  const corpus = normalizeCorpus(await loadAndValidateCorpus());
  const html = await renderLandingPage(corpus);
  assert.match(html, /\/career\.json/u);
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
  const corpus = normalizeCorpus(await loadAndValidateCorpus());
  assert.match(renderCareerMarkdown(corpus), /candidate-controlled/u);
  assert.match(renderLlmsTxt(corpus), /self-published, not independent verification/u);
});
