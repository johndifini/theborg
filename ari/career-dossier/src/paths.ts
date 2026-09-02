import { readdir, readFile } from "node:fs/promises";
import { dirname, isAbsolute, relative, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";

export const projectRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");

export function withinProjectRoot(path: string): string {
  if (isAbsolute(path)) {
    throw new Error(`Absolute project path rejected: ${path}`);
  }
  const resolved = resolve(projectRoot, path);
  const child = relative(projectRoot, resolved);
  if (child === "" || (!child.startsWith(`..${sep}`) && child !== ".." && !isAbsolute(child))) {
    return resolved;
  }
  throw new Error(`Path escapes project root: ${path}`);
}

export async function readProjectText(path: string): Promise<string> {
  return readFile(withinProjectRoot(path), "utf8");
}

export async function readProjectJson(path: string): Promise<unknown> {
  try {
    return JSON.parse(await readProjectText(path));
  } catch (error) {
    throw new Error(`${path}: ${error instanceof Error ? error.message : String(error)}`);
  }
}

export async function projectJsonFiles(directory: string): Promise<string[]> {
  const absolute = withinProjectRoot(directory);
  return (await readdir(absolute, { withFileTypes: true }))
    .filter((entry) => entry.isFile() && entry.name.endsWith(".json"))
    .map((entry) => `${directory}/${entry.name}`)
    .sort((left, right) => left.localeCompare(right, "en"));
}
