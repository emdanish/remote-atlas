/**
 * Lightweight pure-function checks for SEO job helpers.
 * Run with: npx --yes tsx src/lib/seo.test.ts (optional)
 * Primary verification is production build + manual JSON-LD inspection.
 */

import {
  buildJobPostingJsonLd,
  descriptionToHtml,
  isJobIndexable,
  mapEmploymentType,
  safeJsonLd,
} from "./seo";
import type { Job } from "./api/types";

function assert(cond: unknown, msg: string) {
  if (!cond) throw new Error(msg);
}

const baseJob: Job = {
  id: 9,
  source: "greenhouse",
  title: "Senior Python Engineer",
  company_name: "Acme",
  workplace_type: "remote",
  career_stage: "senior",
  skills: ["python", "fastapi"],
  tech_tags: ["postgresql"],
  first_seen_at: new Date().toISOString(),
  posted_at: new Date().toISOString(),
  is_active: true,
  description_text: "Build APIs.\n\nShip features.",
  employment_type: "full-time",
};

assert(mapEmploymentType("full-time") === "FULL_TIME", "employment map");
assert(isJobIndexable(baseJob, 30), "fresh job indexable");
assert(
  !isJobIndexable({ ...baseJob, is_active: false }, 30),
  "inactive not indexable",
);
assert(safeJsonLd({ a: "</script>" }).includes("\\u003c"), "json-ld escape");
assert(descriptionToHtml("a\n\nb", "x").includes("<p>"), "html desc");
const ld = buildJobPostingJsonLd(baseJob);
assert(ld?.["@type"] === "JobPosting", "job posting type");
assert(ld?.jobLocationType === "TELECOMMUTE", "remote type");
assert(ld?.directApply === false, "external apply");

console.log("seo helpers ok");
