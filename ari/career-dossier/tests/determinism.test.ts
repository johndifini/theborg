import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { mkdtemp, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import test from "node:test";
import { build } from "../src/build.ts";
import { normalizeCorpus, stableJson } from "../src/canonical.ts";
import { expectedDistFiles } from "../src/privacy.ts";
import { loadAndValidateCorpus } from "../src/validate.ts";

async function treeDigest(directory: string): Promise<string> {
  const hash = createHash("sha256");
  for (const name of expectedDistFiles) {
    hash.update(name);
    hash.update(await readFile(resolve(directory, name)));
  }
  return hash.digest("hex");
}

test("two clean builds produce byte-identical trees", async () => {
  const first = await mkdtemp(join(tmpdir(), "career-first-"));
  const second = await mkdtemp(join(tmpdir(), "career-second-"));
  try {
    await build(first);
    await build(second);
    assert.equal(await treeDigest(first), await treeDigest(second));
  } finally {
    await Promise.all([rm(first, { force: true, recursive: true }), rm(second, { force: true, recursive: true })]);
  }
});

test("record input order cannot change canonical output", async () => {
  const corpus = await loadAndValidateCorpus();
  const forward = stableJson(normalizeCorpus(corpus));
  const reversed = stableJson(normalizeCorpus({ profile: corpus.profile, claims: corpus.claims.slice().reverse(), evidence: corpus.evidence.slice().reverse() }));
  assert.equal(forward, reversed);
});
