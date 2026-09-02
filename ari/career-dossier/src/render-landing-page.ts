import { readProjectText } from "./paths.ts";
import type { Corpus } from "./types.ts";

const prompt = "Using the career dossier at https://agent.johndifini.com/career.json and the attached job description, identify strong matches, partial matches, and gaps. Cite the dossier claim and evidence IDs for every conclusion. Do not infer missing qualifications; state uncertainty explicitly.";

function escapeHtml(value: string): string {
  return value.replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;");
}

export async function renderLandingPage(corpus: Corpus): Promise<string> {
  const template = await readProjectText("templates/landing-page.html");
  return template
    .replaceAll("{{NAME}}", escapeHtml(corpus.profile.name))
    .replaceAll("{{PROMPT}}", escapeHtml(prompt));
}
