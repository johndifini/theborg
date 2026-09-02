import { createRequire } from "node:module";
import { Ajv2020, type AnySchema, type ErrorObject, type ValidateFunction } from "ajv/dist/2020.js";
import { projectJsonFiles, readProjectJson } from "./paths.ts";
import type { Corpus, PublicClaim, PublicEvidence, PublicProfile } from "./types.ts";

type SchemaName = "public-profile" | "public-claim" | "public-evidence" | "private-provenance" | "publication-manifest";

const require = createRequire(import.meta.url);
const addFormats = require("ajv-formats") as typeof import("ajv-formats").default;

const schemaPaths: Record<SchemaName, string> = {
  "public-profile": "schemas/public-profile.schema.json",
  "public-claim": "schemas/public-claim.schema.json",
  "public-evidence": "schemas/public-evidence.schema.json",
  "private-provenance": "schemas/private-provenance.schema.json",
  "publication-manifest": "schemas/publication-manifest.schema.json"
};

let validators: Promise<Record<SchemaName, ValidateFunction>> | undefined;

function errorText(path: string, errors: ErrorObject[] | null | undefined): string {
  return (errors ?? [])
    .map((error) => `${path}${error.instancePath || "/"}: ${error.message ?? error.keyword}`)
    .join("\n");
}

async function getValidators(): Promise<Record<SchemaName, ValidateFunction>> {
  validators ??= (async () => {
    const ajv = new Ajv2020({ allErrors: true, strict: true });
    addFormats(ajv);
    const entries = await Promise.all(
      Object.entries(schemaPaths).map(async ([name, path]) => [name, ajv.compile(await readProjectJson(path) as AnySchema)] as const)
    );
    return Object.fromEntries(entries) as Record<SchemaName, ValidateFunction>;
  })();
  return validators;
}

export async function validateDocument(name: SchemaName, value: unknown, path: string = name): Promise<void> {
  const validator = (await getValidators())[name];
  if (!validator(value)) throw new Error(errorText(path, validator.errors));
}

export function validateReferences(claims: PublicClaim[], evidence: PublicEvidence[]): void {
  const claimIds = new Set<string>();
  for (const claim of claims) {
    if (claimIds.has(claim.id)) throw new Error(`claims/${claim.id}: duplicate claim ID`);
    claimIds.add(claim.id);
  }

  const evidenceIds = new Set<string>();
  for (const record of evidence) {
    if (evidenceIds.has(record.id)) throw new Error(`evidence/${record.id}: duplicate evidence ID`);
    evidenceIds.add(record.id);
  }

  for (const claim of claims) {
    for (const evidenceId of claim.evidenceIds) {
      if (!evidenceIds.has(evidenceId)) {
        throw new Error(`claims/${claim.id}/evidenceIds: missing evidence ID ${evidenceId}`);
      }
    }
  }
}

export async function loadAndValidateCorpus(): Promise<Corpus> {
  const profilePath = "content/profile.json";
  const claimPaths = await projectJsonFiles("content/claims");
  const evidencePaths = await projectJsonFiles("content/evidence");
  const profile = await readProjectJson(profilePath) as PublicProfile;
  const claims = await Promise.all(claimPaths.map(async (path) => {
    const value = await readProjectJson(path) as PublicClaim;
    await validateDocument("public-claim", value, path);
    return value;
  }));
  const evidence = await Promise.all(evidencePaths.map(async (path) => {
    const value = await readProjectJson(path) as PublicEvidence;
    await validateDocument("public-evidence", value, path);
    return value;
  }));
  await validateDocument("public-profile", profile, profilePath);
  validateReferences(claims, evidence);
  return { profile, claims, evidence };
}
