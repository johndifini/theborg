import assert from "node:assert/strict";
import test from "node:test";
import type { PublicClaim, PublicEvidence } from "../src/types.ts";
import { loadAndValidateCorpus, validateReferences } from "../src/validate.ts";

test("all synthetic references resolve", async () => {
  const corpus = await loadAndValidateCorpus();
  assert.doesNotThrow(() => validateReferences(corpus.claims, corpus.evidence));
});

test("missing evidence ID has an actionable claim path", async () => {
  const corpus = await loadAndValidateCorpus();
  const claim = structuredClone(corpus.claims[0]) as PublicClaim;
  claim.evidenceIds = ["EVID-MISSING"];
  assert.throws(() => validateReferences([claim], corpus.evidence), /claims\/EX-001\/evidenceIds: missing evidence ID EVID-MISSING/u);
});

test("duplicate claim and evidence IDs fail", async () => {
  const corpus = await loadAndValidateCorpus();
  assert.throws(() => validateReferences([corpus.claims[0]!, corpus.claims[0]!], corpus.evidence), /duplicate claim ID/u);
  assert.throws(() => validateReferences(corpus.claims, [corpus.evidence[0]!, corpus.evidence[0]!] as PublicEvidence[]), /duplicate evidence ID/u);
});
