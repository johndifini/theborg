import type { Corpus, JsonValue, PublicClaim, PublicEvidence } from "./types.ts";

function sortedStrings(values: string[] | undefined): string[] | undefined {
  return values?.slice().sort((left, right) => left.localeCompare(right, "en"));
}

export function normalizeCorpus(corpus: Corpus): Corpus {
  return {
    profile: corpus.profile,
    claims: corpus.claims
      .map((claim): PublicClaim => ({
        ...claim,
        ...(claim.organizations ? { organizations: sortedStrings(claim.organizations) ?? [] } : {}),
        skills: sortedStrings(claim.skills) ?? [],
        evidenceIds: sortedStrings(claim.evidenceIds) ?? [],
        limitations: sortedStrings(claim.limitations) ?? []
      }))
      .sort((left, right) => left.id.localeCompare(right.id, "en")),
    evidence: corpus.evidence
      .slice()
      .sort((left: PublicEvidence, right: PublicEvidence) => left.id.localeCompare(right.id, "en"))
  };
}

function ordered(value: JsonValue): JsonValue {
  if (Array.isArray(value)) return value.map(ordered);
  if (value !== null && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value)
        .sort(([left], [right]) => left.localeCompare(right, "en"))
        .map(([key, child]) => [key, ordered(child)])
    );
  }
  return value;
}

export function stableJson(value: JsonValue): string {
  return `${JSON.stringify(ordered(value), null, 2)}\n`;
}
