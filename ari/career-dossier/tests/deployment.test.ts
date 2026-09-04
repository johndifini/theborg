import assert from "node:assert/strict";
import test from "node:test";
import { expectedDistFiles } from "../src/privacy.ts";
import { readProjectText } from "../src/paths.ts";

type Header = { key: string; value: string };
type HeaderRule = { source: string; headers: Header[] };
type VercelConfig = {
  $schema?: string;
  buildCommand?: string;
  cleanUrls?: boolean;
  framework?: string | null;
  headers?: HeaderRule[];
  ignoreCommand?: string;
  installCommand?: string;
  outputDirectory?: string;
  rewrites?: Array<{ source: string; destination: string }>;
};

async function loadConfig(): Promise<VercelConfig> {
  return JSON.parse(await readProjectText("vercel.json")) as VercelConfig;
}

function headerMap(config: VercelConfig, source: string): Map<string, string> {
  const rule = config.headers?.find((candidate) => candidate.source === source);
  assert.ok(rule, `missing header rule for ${source}`);
  return new Map(rule.headers.map(({ key, value }) => [key.toLowerCase(), value]));
}

test("Vercel uses the deterministic static build and skips unrelated commits", async () => {
  const config = await loadConfig();
  assert.equal(config.$schema, "https://openapi.vercel.sh/vercel.json");
  assert.equal(config.framework, null);
  assert.equal(config.installCommand, "npm ci");
  assert.equal(config.buildCommand, "npm run build");
  assert.equal(config.outputDirectory, "dist");
  assert.equal(config.cleanUrls, true);
  assert.equal(config.ignoreCommand, "git diff --quiet HEAD^ HEAD ./");
  assert.deepEqual(config.rewrites, [{ source: "/agent", destination: "/" }]);
});

test("every public route has an explicit media type and bounded caching", async () => {
  const config = await loadConfig();
  const mediaTypes = new Map([
    ["/", "text/html; charset=utf-8"],
    ["/agent", "text/html; charset=utf-8"],
    ["/career.json", "application/json; charset=utf-8"],
    ["/career.md", "text/markdown; charset=utf-8"],
    ["/evidence.json", "application/json; charset=utf-8"],
    ["/llms.txt", "text/plain; charset=utf-8"]
  ]);

  for (const [route, mediaType] of mediaTypes) {
    const headers = headerMap(config, route);
    assert.equal(headers.get("content-type"), mediaType);
    assert.match(headers.get("cache-control") ?? "", /max-age=(?:0|300)\b/u);
    assert.match(headers.get("vercel-cdn-cache-control") ?? "", /max-age=(?:300|3600)\b/u);
    assert.doesNotMatch(headers.get("cache-control") ?? "", /immutable/iu);
    assert.doesNotMatch(headers.get("vercel-cdn-cache-control") ?? "", /immutable/iu);
  }
});

test("all responses receive the required static-site security headers", async () => {
  const config = await loadConfig();
  const headers = headerMap(config, "/(.*)");
  assert.equal(headers.get("x-content-type-options"), "nosniff");
  assert.equal(headers.get("referrer-policy"), "no-referrer");
  const policy = headers.get("content-security-policy") ?? "";
  assert.match(policy, /default-src 'none'/u);
  assert.match(policy, /frame-ancestors 'none'/u);
  assert.match(policy, /form-action 'none'/u);
});

test("the upload allowlist contains only remote-build inputs", async () => {
  const entries = (await readProjectText(".vercelignore"))
    .split(/\r?\n/u)
    .map((line) => line.trim())
    .filter(Boolean);
  assert.deepEqual(entries, [
    "/*",
    "!content",
    "!package.json",
    "!package-lock.json",
    "!schemas",
    "!src",
    "!templates",
    "!vercel.json"
  ]);
  assert.ok(!entries.some((entry) => /(?:private|docs|examples|tests)/iu.test(entry)));
});

test("the deployment output inventory is the public six-file contract", () => {
  assert.deepEqual(expectedDistFiles, [
    "agent.html",
    "career.json",
    "career.md",
    "evidence.json",
    "index.html",
    "llms.txt"
  ]);
});
