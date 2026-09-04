import assert from "node:assert/strict";
import test from "node:test";
import type { PublicClaim, PublicEvidence } from "../src/types.ts";
import { validateReferences } from "../src/validate.ts";
import { fixture } from "./helpers.ts";

async function syntheticRecords(): Promise<{ claims: PublicClaim[]; evidence: PublicEvidence[] }> {
  return {
    claims: [
      await fixture("examples/synthetic/public-claim-completed.json") as PublicClaim,
      await fixture("examples/synthetic/public-claim-in-development.json") as PublicClaim
    ],
    evidence: [await fixture("examples/synthetic/public-evidence.json") as PublicEvidence]
  };
}

test("all synthetic references resolve", async () => {
  const synthetic = await syntheticRecords();
  assert.doesNotThrow(() => validateReferences(synthetic.claims, synthetic.evidence));
});

test("missing evidence ID has an actionable claim path", async () => {
  const synthetic = await syntheticRecords();
  const claim = structuredClone(synthetic.claims[0]) as PublicClaim;
  claim.evidenceIds = ["EVID-MISSING"];
  assert.throws(() => validateReferences([claim], synthetic.evidence), /claims\/EX-001\/evidenceIds: missing evidence ID EVID-MISSING/u);
});

test("duplicate claim and evidence IDs fail", async () => {
  const synthetic = await syntheticRecords();
  assert.throws(() => validateReferences([synthetic.claims[0]!, synthetic.claims[0]!], synthetic.evidence), /duplicate claim ID/u);
  assert.throws(() => validateReferences(synthetic.claims, [synthetic.evidence[0]!, synthetic.evidence[0]!] as PublicEvidence[]), /duplicate evidence ID/u);
});
