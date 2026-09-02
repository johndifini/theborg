import assert from "node:assert/strict";
import test from "node:test";
import type { JsonObject } from "../src/types.ts";
import { loadAndValidateCorpus, validateDocument } from "../src/validate.ts";
import { clone, fixture } from "./helpers.ts";

test("valid synthetic public and private-sidecar records pass", async () => {
  const corpus = await loadAndValidateCorpus();
  assert.deepEqual(
    corpus.claims.filter((claim) => claim.id.startsWith("EX-")).map((claim) => claim.id),
    ["EX-001", "EX-002"]
  );
  await validateDocument("private-provenance", await fixture("examples/synthetic/private-provenance.json"));
  await validateDocument("publication-manifest", await fixture("examples/synthetic/publication-manifest.json"));
});

test("public claim schema rejects every contract violation with a path", async () => {
  const valid = await fixture("content/claims/EX-001.json") as JsonObject;
  const cases: Array<[string, (value: JsonObject) => void, RegExp]> = [
    ["unknown property", (value) => { value.unexpected = true; }, /additional properties/u],
    ["invalid ID", (value) => { value.id = "bad"; }, /\/id/u],
    ["invalid enum", (value) => { value.type = "other"; }, /\/type/u],
    ["invalid date", (value) => { value.asOf = "yesterday"; }, /\/asOf/u],
    ["missing asOf", (value) => { delete value.asOf; }, /asOf/u],
    ["missing approval", (value) => { delete value.approvedAt; }, /approvedAt/u],
    ["not public", (value) => { value.visibility = "private"; }, /\/visibility/u],
    ["no limitations", (value) => { value.limitations = []; }, /\/limitations/u],
    ["documented without evidence", (value) => { value.evidenceIds = []; }, /\/evidenceIds/u]
  ];
  for (const [name, mutate, expected] of cases) {
    const candidate = clone(valid);
    mutate(candidate);
    await assert.rejects(validateDocument("public-claim", candidate, name), expected, name);
  }
});

test("public evidence rejects insecure URLs, local paths, and unknown fields", async () => {
  const valid = await fixture("content/evidence/EVID-EX-001.json") as JsonObject;
  for (const [name, mutate] of [
    ["insecure URL", (value: JsonObject) => { value.url = "http://example.com"; }],
    ["local path", (value: JsonObject) => { value.localPath = "/synthetic/file"; }],
    ["not approved", (value: JsonObject) => { delete value.approvedAt; }]
  ] as const) {
    const candidate = clone(valid);
    mutate(candidate);
    await assert.rejects(validateDocument("public-evidence", candidate, name), Error, name);
  }
});

test("private provenance cannot duplicate public claim prose", async () => {
  const value = await fixture("examples/synthetic/private-provenance.json") as JsonObject;
  value.claim = "A second copy of public prose";
  await assert.rejects(validateDocument("private-provenance", value), /additional properties|must NOT be valid/u);
});
