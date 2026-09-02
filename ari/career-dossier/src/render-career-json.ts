import { stableJson } from "./canonical.ts";
import type { Corpus, JsonObject } from "./types.ts";

export function renderCareerJson(corpus: Corpus): string {
  return stableJson({
    schemaVersion: 1,
    asOf: corpus.claims.map((claim) => claim.asOf).sort().at(-1) ?? "1970-01-01",
    profile: corpus.profile,
    claims: corpus.claims,
    evidence: corpus.evidence
  } as JsonObject);
}
