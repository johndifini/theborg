import { mkdir, rm, writeFile } from "node:fs/promises";
import { resolve } from "node:path";
import { normalizeCorpus } from "./canonical.ts";
import { assertDeployableSourcesSafe, assertDistSafe, assertOutputPath, assertPublicValuesSafe } from "./privacy.ts";
import { projectRoot } from "./paths.ts";
import { renderCareerJson } from "./render-career-json.ts";
import { renderCareerMarkdown } from "./render-career-markdown.ts";
import { renderEvidence } from "./render-evidence.ts";
import { renderLandingPage } from "./render-landing-page.ts";
import { renderLlmsTxt } from "./render-llms-txt.ts";
import { loadAndValidateCorpus } from "./validate.ts";

export async function build(outputDirectory = resolve(projectRoot, "dist")): Promise<void> {
  assertOutputPath(outputDirectory);
  await assertDeployableSourcesSafe();
  const corpus = normalizeCorpus(await loadAndValidateCorpus());
  assertPublicValuesSafe(corpus);
  const landing = await renderLandingPage(corpus);
  const files: Record<string, string> = {
    "agent.html": landing,
    "career.json": renderCareerJson(corpus),
    "career.md": renderCareerMarkdown(corpus),
    "evidence.json": renderEvidence(corpus),
    "index.html": landing,
    "llms.txt": renderLlmsTxt(corpus)
  };
  await rm(outputDirectory, { force: true, recursive: true });
  await mkdir(outputDirectory, { recursive: true });
  for (const name of Object.keys(files).sort((left, right) => left.localeCompare(right, "en"))) {
    await writeFile(resolve(outputDirectory, name), files[name] ?? "", "utf8");
  }
  await assertDistSafe(outputDirectory);
}

const requestedOutput = process.argv[2] === "--out" && process.argv[3] ? resolve(process.argv[3]) : undefined;
if (process.argv[1] && resolve(process.argv[1]) === resolve(new URL(import.meta.url).pathname)) {
  await build(requestedOutput);
}
