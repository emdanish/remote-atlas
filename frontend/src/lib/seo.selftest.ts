/**
 * Lightweight pure-function checks for SEO job helpers.
 * Run with: npm run test:seo
 */

import {
  buildJobPostingJsonLd,
  descriptionToHtml,
  isJobIndexable,
  jobEmploymentType,
  mapEmploymentType,
  parseApplicantCountryIsos,
  parsePostalAddress,
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
assert(mapEmploymentType("Full-Time") === "FULL_TIME", "employment full-time hyphen");
assert(mapEmploymentType("contract") === "CONTRACTOR", "employment contract");
assert(mapEmploymentType("mystery-band") === undefined, "unknown employment not invented");
assert(jobEmploymentType({ employment_type: null, career_stage: "senior" }) === "OTHER", "empty → OTHER");
assert(isJobIndexable(baseJob, 30), "fresh job indexable");
assert(
  !isJobIndexable({ ...baseJob, is_active: false }, 30),
  "inactive not indexable",
);
assert(safeJsonLd({ a: "</script>" }).includes("\\u003c"), "json-ld escape");
assert(descriptionToHtml("a\n\nb", "x").includes("<p>"), "html desc");

const texas = parsePostalAddress("Conroe, Texas");
assert(texas?.addressCountry === "US", "texas country");
assert(texas?.addressRegion === "TX", "texas region");
assert(texas?.addressLocality === "Conroe", "texas city");

const co = parsePostalAddress("Littleton, CO");
assert(co?.addressCountry === "US", "co country");
assert(co?.addressRegion === "CO", "co region");

assert(parsePostalAddress("Remote") == null, "vague remote has no street address");
assert(parsePostalAddress("London, United Kingdom")?.addressCountry === "GB", "uk country");
assert(parseApplicantCountryIsos("Remote, United Kingdom").includes("GB"), "uk from remote string");

const ld = buildJobPostingJsonLd(baseJob);
assert(ld?.["@type"] === "JobPosting", "job posting type");
assert(ld?.jobLocationType === "TELECOMMUTE", "remote type");
assert(ld?.directApply === false, "external apply");
assert(ld?.datePosted, "datePosted present");
assert(ld?.validThrough, "validThrough present");
assert(ld?.employmentType === "FULL_TIME", "employmentType present");
assert(!("jobLocation" in (ld || {})), "remote omits stub Place");
assert(!("baseSalary" in (ld || {})), "never invent salary");
const worldReq = ld?.applicantLocationRequirements as { "@type"?: string; name?: string };
assert(worldReq?.["@type"] === "Country", "remote requires Country");
assert(worldReq?.name === "Worldwide", "vague remote is Worldwide, not a fake US address");

const ukRemote = buildJobPostingJsonLd({
  ...baseJob,
  location_raw: "London, United Kingdom",
});
const ukReq = ukRemote?.applicantLocationRequirements as { name?: string };
assert(ukRemote?.jobLocationType === "TELECOMMUTE", "uk remote still TELECOMMUTE");
assert(ukReq?.name === "United Kingdom", "uk remote applicant country");
assert(!("jobLocation" in (ukRemote || {})), "remote still omits Place when country is known");

const datedFromLastSeen = buildJobPostingJsonLd({
  ...baseJob,
  posted_at: null,
  first_seen_at: undefined as unknown as string,
  last_seen_at: new Date().toISOString(),
});
assert(datedFromLastSeen?.datePosted, "datePosted falls back to last_seen_at");
assert(datedFromLastSeen?.validThrough, "validThrough follows datePosted fallback");

const otherEmp = buildJobPostingJsonLd({
  ...baseJob,
  employment_type: "band-unspecified",
});
assert(otherEmp?.employmentType === "OTHER", "unmapped employmentType is OTHER");

const onsite: Job = {
  ...baseJob,
  id: 47924,
  workplace_type: "unknown",
  location_raw: "Conroe, Texas",
  employment_type: "Full-Time",
  title: "Electrical & Mechanical Maintenance Engineer",
  company_name: "Full Circle",
};
const onsiteLd = buildJobPostingJsonLd(onsite);
const place = onsiteLd?.jobLocation as { address?: Record<string, string> };
assert(place?.address?.addressCountry === "US", "onsite addressCountry");
assert(place?.address?.addressRegion === "TX", "onsite addressRegion");
assert(place?.address?.addressLocality === "Conroe", "onsite locality");
assert(!place?.address?.streetAddress, "do not invent street");
assert(!place?.address?.postalCode, "do not invent postal code");
assert(onsiteLd?.employmentType === "FULL_TIME", "Full-Time maps");
assert(!(onsiteLd as { jobLocationType?: string })?.jobLocationType, "unknown workplace with city is not TELECOMMUTE");

const onsiteNoCountry = buildJobPostingJsonLd({
  ...baseJob,
  workplace_type: "onsite",
  location_raw: "HQ Campus",
});
assert(!("jobLocation" in (onsiteNoCountry || {})), "onsite without country has no stub Place");
assert(!("jobLocationType" in (onsiteNoCountry || {})), "onsite without country is not faked as remote");

const unknownEmpty = buildJobPostingJsonLd({
  ...baseJob,
  workplace_type: "unknown",
  location_raw: "",
});
assert(unknownEmpty?.jobLocationType === "TELECOMMUTE", "unknown empty defaults to remote-first TELECOMMUTE");
assert(
  (unknownEmpty?.applicantLocationRequirements as { name?: string })?.name === "Worldwide",
  "unknown empty still has applicant country",
);

console.log("seo helpers ok");
