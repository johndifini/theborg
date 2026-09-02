export type JsonObject = { [key: string]: JsonValue };
export type JsonValue = null | boolean | number | string | JsonValue[] | JsonObject;

export interface PublicProfile extends JsonObject {
  schemaVersion: 1;
  name: string;
  headline: string;
  summary: string;
  location?: string;
  website: string;
  visibility: "public";
  approvedAt: string;
}

export interface PublicClaim extends JsonObject {
  schemaVersion: 1;
  id: string;
  type: "experience" | "project" | "leadership" | "writing" | "speaking" | "award" | "education";
  title: string;
  claim: string;
  status: "completed" | "historical" | "in-development" | "scheduled";
  asOf: string;
  period?: { start: string; end: string | null };
  organizations?: string[];
  skills: string[];
  evidenceIds: string[];
  limitations: string[];
  evidenceLevel: "publicly-documented" | "resume-sourced" | "candidate-confirmed";
  visibility: "public";
  approvedAt: string;
}

export interface PublicEvidence extends JsonObject {
  schemaVersion: 1;
  id: string;
  type: "article" | "credential" | "project-page" | "publication" | "recording" | "website";
  title: string;
  url: string;
  publisher: string;
  ownerType: "independent" | "candidate-controlled";
  publishedAt?: string;
  accessedAt: string;
  supports: string;
  visibility: "public";
  approvedAt: string;
}

export interface Corpus extends JsonObject {
  profile: PublicProfile;
  claims: PublicClaim[];
  evidence: PublicEvidence[];
}
