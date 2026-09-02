import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { projectRoot } from "../src/paths.ts";

export async function fixture(path: string): Promise<unknown> {
  return JSON.parse(await readFile(resolve(projectRoot, path), "utf8"));
}

export function clone<T>(value: T): T {
  return structuredClone(value);
}
