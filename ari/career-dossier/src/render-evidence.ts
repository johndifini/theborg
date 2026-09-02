import { stableJson } from "./canonical.ts";
import type { Corpus, JsonObject } from "./types.ts";

export function renderEvidence(corpus: Corpus): string {
  const supportedClaims = Object.fromEntries(corpus.evidence.map((record) => [
    record.id,
    corpus.claims.filter((claim) => claim.evidenceIds.includes(record.id)).map((claim) => claim.id)
  ]));
  return stableJson({ schemaVersion: 1, evidence: corpus.evidence, supportedClaims } as JsonObject);
}
