import type { Corpus } from "./types.ts";

export function renderCareerMarkdown(corpus: Corpus): string {
  const lines = [
    `# ${corpus.profile.name} — public career dossier`,
    "",
    `> ${corpus.profile.headline}`,
    "",
    corpus.profile.summary,
    "",
    `As of: ${corpus.claims.map((claim) => claim.asOf).sort().at(-1) ?? "unknown"}`,
    "",
    "## Claims",
    ""
  ];
  for (const claim of corpus.claims) {
    lines.push(
      `### ${claim.id}: ${claim.title}`,
      "",
      claim.claim,
      "",
      `- Type/status: ${claim.type} / ${claim.status}`,
      `- As of: ${claim.asOf}`,
      `- Evidence level: ${claim.evidenceLevel}`,
      `- Skills: ${claim.skills.join(", ")}`,
      `- Evidence IDs: ${claim.evidenceIds.length > 0 ? claim.evidenceIds.join(", ") : "none"}`,
      `- Limitations: ${claim.limitations.join("; ")}`,
      ""
    );
  }
  lines.push("## Evidence", "");
  for (const record of corpus.evidence) {
    lines.push(
      `### ${record.id}: ${record.title}`,
      "",
      `- URL: ${record.url}`,
      `- Publisher/owner: ${record.publisher} / ${record.ownerType}`,
      `- Supports: ${record.supports}`,
      `- Accessed: ${record.accessedAt}`,
      ""
    );
  }
  return `${lines.join("\n").trimEnd()}\n`;
}
