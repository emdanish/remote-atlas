export function cn(...parts: Array<string | false | null | undefined>) {
  return parts.filter(Boolean).join(" ");
}

export function formatRelativeDate(iso?: string | null): string {
  if (!iso) return "Recently";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "Recently";
  const diffMs = Date.now() - date.getTime();
  const days = Math.floor(diffMs / (1000 * 60 * 60 * 24));
  if (days <= 0) return "Today";
  if (days === 1) return "Yesterday";
  if (days < 14) return `${days}d ago`;
  return date.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

export function titleCase(value: string): string {
  if (!value) return value;
  return value.charAt(0).toUpperCase() + value.slice(1).replace(/_/g, " ");
}

export function seniorityBadgeLabel(job: {
  career_stage?: string | null;
  junior_eligible?: boolean;
}): string | null {
  const stage = (job.career_stage || "unknown").toLowerCase();
  if (stage && stage !== "unknown") return titleCase(stage);
  if (job.junior_eligible) return "Seniority not stated";
  return null;
}

export function truncate(text: string, max = 160): string {
  const t = text.trim();
  if (t.length <= max) return t;
  return `${t.slice(0, max - 1).trimEnd()}…`;
}

export function officialApplyUrl(job: {
  source: string;
  external_id?: string;
  title: string;
  apply_url?: string | null;
}): string | null {
  const url = job.apply_url;
  if (!url) return null;
  const lower = url.toLowerCase();
  // Never send users to internal API hosts
  if (
    lower.includes("api.smartrecruiters.com/") ||
    lower.includes("boards-api.greenhouse.io/") ||
    lower.includes("api.lever.co/") ||
    lower.includes("api.ashbyhq.com/")
  ) {
    if (job.source === "smartrecruiters" && job.external_id?.includes(":")) {
      const separator = job.external_id.indexOf(":");
      const company = job.external_id.slice(0, separator);
      const postingId = job.external_id.slice(separator + 1);
      const titleSlug = job.title
        .normalize("NFKD")
        .replace(/[\u0300-\u036f]/g, "")
        .replace(/[^a-zA-Z0-9]+/g, "-")
        .replace(/^-|-$/g, "")
        .toLowerCase();
      return `https://jobs.smartrecruiters.com/${company}/${postingId}${titleSlug ? `-${titleSlug}` : ""}?oga=true`;
    }
    return null;
  }
  return url;
}

/** Human-readable domain for “Opens X careers” trust line. */
export function applyDestinationLabel(url?: string | null): string | null {
  if (!url) return null;
  try {
    const host = new URL(url).hostname.replace(/^www\./, "");
    if (!host) return null;
    // Map well-known ATS hosts to clearer labels
    if (host.includes("greenhouse.io")) return "Greenhouse careers";
    if (host.includes("lever.co")) return "Lever careers";
    if (host.includes("ashbyhq.com")) return "Ashby careers";
    if (host.includes("smartrecruiters.com")) return "SmartRecruiters careers";
    if (host.includes("workable.com")) return "Workable careers";
    if (host.includes("bamboohr.com")) return "BambooHR careers";
    if (host.includes("myworkdayjobs.com")) return "Workday careers";
    if (host.includes("weworkremotely.com")) return "We Work Remotely";
    return host;
  } catch {
    return null;
  }
}

export function sourceKindLabel(kind?: string | null, fallbackSource?: string): string {
  if (kind === "ats") return "Official ATS board";
  if (kind === "curated_board") return "Curated job board";
  if (kind === "aggregator") return "Job aggregator";
  return fallbackSource || "Source";
}

/**
 * Deduplicate display labels case-insensitively while keeping first casing.
 * Use for React lists so keys stay unique.
 */
export function uniqueLabels(
  ...lists: Array<string[] | null | undefined>
): string[] {
  const map = new Map<string, string>();
  for (const list of lists) {
    if (!list) continue;
    for (const raw of list) {
      if (raw == null) continue;
      const trimmed = String(raw).trim();
      if (!trimmed) continue;
      const key = trimmed.toLowerCase();
      if (!map.has(key)) map.set(key, trimmed);
    }
  }
  return Array.from(map.values());
}
