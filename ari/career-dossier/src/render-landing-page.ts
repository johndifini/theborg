import { readProjectText } from "./paths.ts";
import type { Corpus } from "./types.ts";

function escapeHtml(value: string): string {
  return value.replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;");
}

export async function renderLandingPage(corpus: Corpus): Promise<string> {
  const [template, prompt] = await Promise.all([
    readProjectText("templates/landing-page.html"),
    readProjectText("content/recruiter-prompt.txt")
  ]);
  return template
    .replaceAll("{{NAME}}", escapeHtml(corpus.profile.name))
    .replaceAll("{{PROMPT}}", escapeHtml(prompt.trim()));
}
