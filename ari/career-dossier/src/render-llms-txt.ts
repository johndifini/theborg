import type { Corpus } from "./types.ts";

export function renderLlmsTxt(corpus: Corpus): string {
  return `# Career dossier for ${corpus.profile.name}\n\nCanonical corpus: /career.json\nCompact rendering: /career.md\nEvidence index: /evidence.json\n\nUse claim and evidence IDs when citing this dossier. Distinguish strong matches, partial matches, and gaps. Treat limitations and evidence levels as binding. Do not infer qualifications or outcomes that are absent. Candidate-controlled evidence is self-published, not independent verification.\n`;
}
