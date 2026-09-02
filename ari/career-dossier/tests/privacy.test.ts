import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import { resolve } from "node:path";
import { assertDeployableSourcesSafe, assertOutputPath, assertPrivateSafe, assertPublicValuesSafe } from "../src/privacy.ts";
import { projectRoot, readProjectText } from "../src/paths.ts";

test("deployable sources contain no private patterns", async () => {
  await assert.doesNotReject(assertDeployableSourcesSafe());
});

test("every adversarial privacy fixture is rejected", async () => {
  const cases = JSON.parse(await readFile(resolve(projectRoot, "tests/fixtures/adversarial/privacy-cases.json"), "utf8")) as Array<{ name: string; value: string }>;
  for (const item of cases) {
    assert.throws(() => assertPrivateSafe(item.name, item.value), Error, item.name);
  }
});

test("public values reject unexpected URL schemes", () => {
  assert.throws(() => assertPublicValuesSafe({ url: "http://example.com" }), /must use HTTPS/u);
});

test("project reader rejects a private-sidecar escape before filesystem access", async () => {
  await assert.rejects(readProjectText("../.private/synthetic.json"), /escapes project root/u);
});

test("output guard permits only dist or an OS temporary child", () => {
  assert.doesNotThrow(() => assertOutputPath(resolve(projectRoot, "dist")));
  assert.throws(() => assertOutputPath(projectRoot), /outside approved roots/u);
  assert.throws(() => assertOutputPath(resolve(projectRoot, "src")), /outside approved roots/u);
});

test("project gitignore keeps private directories and machine-local command link untracked", async () => {
  const ignore = await readProjectText(".gitignore");
  assert.match(ignore, /\*\*\/\.private\//u);
  assert.match(ignore, /\.claude\/commands/u);
});
