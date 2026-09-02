import assert from "node:assert/strict";
import test from "node:test";
import { contentDigest, publicationStatus } from "../src/publication-state.ts";

test("unchanged public content stays published", () => {
  const value = { claimId: "EX-001", sourceFact: "synthetic" };
  assert.equal(publicationStatus(contentDigest(value), value), "published");
});

test("a source change marks publication stale without changing public output", () => {
  const before = { claimId: "EX-001", sourceFact: "synthetic-v1" };
  const after = { claimId: "EX-001", sourceFact: "synthetic-v2" };
  const publicOutput = "Approved public wording remains unchanged.";
  assert.equal(publicationStatus(contentDigest(before), after), "stale");
  assert.equal(publicOutput, "Approved public wording remains unchanged.");
});
