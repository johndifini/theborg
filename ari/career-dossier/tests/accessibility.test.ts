import assert from "node:assert/strict";
import test from "node:test";
import { normalizeCorpus } from "../src/canonical.ts";
import { renderLandingPage } from "../src/render-landing-page.ts";
import { loadAndValidateCorpus } from "../src/validate.ts";

function rgb(hex: string): [number, number, number] {
  const value = hex.replace("#", "");
  assert.equal(value.length, 6);
  return [0, 2, 4].map((offset) => Number.parseInt(value.slice(offset, offset + 2), 16)) as [number, number, number];
}

function luminance(hex: string): number {
  const channels = rgb(hex).map((channel) => {
    const normalized = channel / 255;
    return normalized <= 0.04045 ? normalized / 12.92 : ((normalized + 0.055) / 1.055) ** 2.4;
  });
  const [red = 0, green = 0, blue = 0] = channels;
  return 0.2126 * red + 0.7152 * green + 0.0722 * blue;
}

function contrast(foreground: string, background: string): number {
  const values = [luminance(foreground), luminance(background)].sort((left, right) => right - left);
  return ((values[0] ?? 0) + 0.05) / ((values[1] ?? 0) + 0.05);
}

test("landing page exposes semantic navigation and metadata", async () => {
  const html = await renderLandingPage(normalizeCorpus(await loadAndValidateCorpus()));
  assert.match(html, /<html lang="en">/u);
  assert.match(html, /<a class="skip-link" href="#main-content">Skip to main content<\/a>/u);
  assert.match(html, /<main class="shell" id="main-content" tabindex="-1">/u);
  assert.equal(html.match(/<h1\b/gu)?.length, 1);
  assert.match(html, /<button type="button" id="copy" aria-describedby="copy-status">/u);
  assert.match(html, /id="copy-status" aria-live="polite"/u);
  assert.match(html, /<nav class="shell resource-nav" aria-label="Machine-readable dossier files">/u);
  assert.match(html, /<link rel="canonical" href="https:\/\/agent\.johndifini\.com\/">/u);
  assert.equal(html.match(/<link rel="alternate"/gu)?.length, 4);
  assert.equal(html.match(/<li><div><strong>/gu)?.length, 2);
  assert.doesNotMatch(html, /Copy the dossier URL/u);
});

test("prompt remains visible without JavaScript and copy failure has a fallback", async () => {
  const html = await renderLandingPage(normalizeCorpus(await loadAndValidateCorpus()));
  const scriptAt = html.indexOf("<script>");
  const promptAt = html.indexOf('<pre id="prompt"');
  assert.ok(promptAt > 0 && promptAt < scriptAt);
  assert.match(html, /navigator\.clipboard\.writeText/u);
  assert.match(html, /The prompt is selected for manual copying/u);
  assert.match(html, /https:\/\/agent\.johndifini\.com\/career\.json/u);
  assert.doesNotMatch(html, /https:\/\/johndifini\.com\/agent/u);
});

test("focus, reduced-motion, responsive, and contrast safeguards are present", async () => {
  const html = await renderLandingPage(normalizeCorpus(await loadAndValidateCorpus()));
  assert.match(html, /:focus-visible/u);
  assert.match(html, /@media \(prefers-reduced-motion: reduce\)/u);
  assert.match(html, /@media \(max-width: 34rem\)/u);
  assert.match(html, /letter-spacing: \.015em;/u);
  assert.match(html, /word-spacing: \.14em;/u);
  assert.match(html, /--accent-bright: #1ec503ff;/u);
  assert.ok(contrast("#191919", "#f4f2ec") >= 7, "light primary text contrast");
  assert.ok(contrast("#62615c", "#f4f2ec") >= 4.5, "light secondary text contrast");
  assert.ok(contrast("#006b20", "#f4f2ec") >= 4.5, "light accent-text contrast");
  assert.ok(contrast("#191919", "#1ec503") >= 4.5, "light button contrast");
  assert.ok(contrast("#f3f1ea", "#11120f") >= 7, "dark primary text contrast");
  assert.ok(contrast("#b7b5ad", "#11120f") >= 4.5, "dark secondary text contrast");
  assert.ok(contrast("#1ec503", "#11120f") >= 4.5, "dark accent-text contrast");
  assert.ok(contrast("#11120f", "#1ec503") >= 4.5, "dark button contrast");
});
