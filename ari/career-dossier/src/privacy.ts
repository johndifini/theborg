import { readdir, readFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { basename, join, resolve, sep } from "node:path";
import { projectRoot, readProjectText, withinProjectRoot } from "./paths.ts";
import type { JsonValue } from "./types.ts";

export const expectedDistFiles = ["agent.html", "career.json", "career.md", "evidence.json", "index.html", "llms.txt"];

const forbidden: Array<[string, RegExp]> = [
  ["private path", /(?:^|[\\/])\.private(?:[\\/]|$)/iu],
  ["absolute local path", /(?:\/(?:Users|home|opt)\/|[A-Z]:\\Users\\)/iu],
  ["resume or document filename", /[^\s"']+\.(?:docx|pdf)\b/iu],
  ["artifact hash", /\b(?:sha256:)?[a-f0-9]{64}\b/iu],
  ["email address", /\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b/iu],
  ["phone number", /(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]\d{3}[-.\s]\d{4}/u],
  ["credential or token", /\b(?:api[_-]?key|access[_-]?token|client[_-]?secret|password)\b\s*[:=]/iu],
  ["unexpected URL scheme", /\b(?:file|ftp|ssh):\/\//iu]
];

export function privacyFindings(label: string, text: string): string[] {
  return forbidden.flatMap(([kind, pattern]) => pattern.test(text) ? [`${label}: ${kind}`] : []);
}

export function assertPrivateSafe(label: string, text: string): void {
  const findings = privacyFindings(label, text);
  if (findings.length > 0) throw new Error(findings.join("\n"));
}

export function assertPublicValuesSafe(value: JsonValue, path = "public"): void {
  if (typeof value === "string") {
    assertPrivateSafe(path, value);
    if (/^[a-z][a-z0-9+.-]*:\/\//iu.test(value) && !value.startsWith("https://")) {
      throw new Error(`${path}: public URLs must use HTTPS`);
    }
    return;
  }
  if (Array.isArray(value)) {
    value.forEach((child, index) => assertPublicValuesSafe(child, `${path}/${index}`));
    return;
  }
  if (value !== null && typeof value === "object") {
    for (const [key, child] of Object.entries(value)) assertPublicValuesSafe(child, `${path}/${key}`);
  }
}

export async function assertDeployableSourcesSafe(): Promise<void> {
  for (const path of [
    "content/profile.json",
    ...(await sourceFiles("content/claims")),
    ...(await sourceFiles("content/evidence")),
    "templates/landing-page.html"
  ]) {
    assertPrivateSafe(path, await readProjectText(path));
  }
}

async function sourceFiles(directory: string): Promise<string[]> {
  return (await readdir(withinProjectRoot(directory)))
    .filter((name) => name.endsWith(".json"))
    .sort((left, right) => left.localeCompare(right, "en"))
    .map((name) => `${directory}/${name}`);
}

export async function assertDistSafe(outputDirectory: string): Promise<void> {
  const entries = (await readdir(outputDirectory, { withFileTypes: true }))
    .map((entry) => entry.name)
    .sort((left, right) => left.localeCompare(right, "en"));
  if (entries.some((name) => !expectedDistFiles.includes(name)) || entries.length !== expectedDistFiles.length) {
    throw new Error(`dist inventory mismatch: expected ${expectedDistFiles.join(", ")}; received ${entries.join(", ")}`);
  }
  for (const name of entries) {
    assertPrivateSafe(`dist/${basename(name)}`, await readFile(join(outputDirectory, name), "utf8"));
  }
}

export function assertOutputPath(outputDirectory: string): void {
  const projectOutput = outputDirectory === resolve(projectRoot, "dist");
  const temporaryRoot = resolve(tmpdir());
  const temporaryOutput = outputDirectory.startsWith(`${temporaryRoot}${sep}`);
  if (!projectOutput && !temporaryOutput) throw new Error(`Output path is outside approved roots: ${outputDirectory}`);
}
