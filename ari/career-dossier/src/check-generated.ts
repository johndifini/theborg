import { mkdtemp, readdir, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { build } from "./build.ts";
import { expectedDistFiles } from "./privacy.ts";
import { projectRoot } from "./paths.ts";

export async function checkGenerated(): Promise<void> {
  const temporary = await mkdtemp(join(tmpdir(), "career-dossier-"));
  try {
    await build(temporary);
    const committed = (await readdir(resolve(projectRoot, "dist"))).sort();
    if (JSON.stringify(committed) !== JSON.stringify(expectedDistFiles)) {
      throw new Error(`dist inventory differs: ${committed.join(", ")}`);
    }
    for (const name of expectedDistFiles) {
      const [expected, actual] = await Promise.all([
        readFile(resolve(projectRoot, "dist", name)),
        readFile(resolve(temporary, name))
      ]);
      if (!expected.equals(actual)) throw new Error(`generated file differs: dist/${name}`);
    }
  } finally {
    await rm(temporary, { force: true, recursive: true });
  }
}

await checkGenerated();
