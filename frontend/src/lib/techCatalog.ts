/** Popular tech catalog for filter chips (always available). */
export const TECH_CATALOG: Array<{ label: string; value: string }> = [
  { label: "React", value: "react" },
  { label: "Next.js", value: "next.js" },
  { label: "TypeScript", value: "typescript" },
  { label: "JavaScript", value: "javascript" },
  { label: "Python", value: "python" },
  { label: "Node.js", value: "node.js" },
  { label: "Flutter", value: "flutter" },
  { label: "Java", value: "java" },
  { label: "Go", value: "go" },
  { label: "Rust", value: "rust" },
  { label: "C#/.NET", value: "c#" },
  { label: "PHP", value: "php" },
  { label: "Ruby", value: "ruby" },
  { label: "Kotlin", value: "kotlin" },
  { label: "Swift", value: "swift" },
  { label: "AWS", value: "cloud" },
  { label: "DevOps", value: "devops" },
  { label: "AI / ML", value: "ai/ml" },
  { label: "PostgreSQL", value: "postgresql" },
  { label: "MongoDB", value: "mongodb" },
  { label: "Redis", value: "redis" },
  { label: "GraphQL", value: "graphql" },
  { label: "Vue", value: "vue" },
  { label: "Angular", value: "angular" },
  { label: "Android", value: "android" },
  { label: "iOS", value: "ios" },
  { label: "SQL", value: "sql" },
  { label: "Terraform", value: "terraform" },
];

const CATALOG_VALUES = new Set(TECH_CATALOG.map((t) => t.value));

/** Normalize free-form profile skill text into a chip value. */
export function normalizeTechValue(raw: string): string {
  const s = raw.trim().toLowerCase();
  if (!s) return "";
  const aliases: Record<string, string> = {
    ts: "typescript",
    js: "javascript",
    node: "node.js",
    nodejs: "node.js",
    nextjs: "next.js",
    next: "next.js",
    "react.js": "react",
    reactjs: "react",
    golang: "go",
    postgres: "postgresql",
    k8s: "devops",
    docker: "devops",
    kubernetes: "cloud",
    gcp: "cloud",
    azure: "cloud",
    ml: "ai/ml",
    "machine learning": "ai/ml",
    "deep learning": "ai/ml",
    pytorch: "ai/ml",
    tensorflow: "ai/ml",
    llm: "ai/ml",
  };
  if (aliases[s]) return aliases[s];
  const inCatalog = TECH_CATALOG.find(
    (t) => t.value === s || t.label.toLowerCase() === s,
  );
  return inCatalog?.value || s;
}

export function formatTechLabel(value: string): string {
  const hit = TECH_CATALOG.find((t) => t.value === value.toLowerCase());
  if (hit) return hit.label;
  if (!value) return value;
  return value
    .split(/[\s._/-]+/)
    .map((w) => (w.length <= 2 ? w.toUpperCase() : w.charAt(0).toUpperCase() + w.slice(1)))
    .join(" ");
}

/**
 * Build recommended chips from profile skills/technologies (resume-derived).
 * Returns items not already identical, max `limit`.
 */
export function recommendedTechsFromProfile(
  skills: string[] = [],
  technologies: string[] = [],
  limit = 16,
): Array<{ label: string; value: string }> {
  const seen = new Set<string>();
  const out: Array<{ label: string; value: string }> = [];
  for (const raw of [...technologies, ...skills]) {
    const value = normalizeTechValue(raw);
    if (!value || seen.has(value)) continue;
    seen.add(value);
    out.push({ label: formatTechLabel(value), value });
    if (out.length >= limit) break;
  }
  return out;
}

/** Catalog chips excluding ones already listed in recommended. */
export function catalogTechsExcluding(
  recommended: Array<{ value: string }>,
): Array<{ label: string; value: string }> {
  const skip = new Set(recommended.map((r) => r.value));
  return TECH_CATALOG.filter((t) => !skip.has(t.value));
}

export function isCatalogTech(value: string): boolean {
  return CATALOG_VALUES.has(value.toLowerCase());
}
