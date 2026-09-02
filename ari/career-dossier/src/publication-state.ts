import { createHash } from "node:crypto";
import { stableJson } from "./canonical.ts";
import type { JsonValue } from "./types.ts";

export function contentDigest(value: JsonValue): string {
  return `sha256:${createHash("sha256").update(stableJson(value)).digest("hex")}`;
}

export function publicationStatus(recordedDigest: string, currentValue: JsonValue): "published" | "stale" {
  return recordedDigest === contentDigest(currentValue) ? "published" : "stale";
}
