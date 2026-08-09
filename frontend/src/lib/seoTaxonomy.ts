/**
 * Frontend copies of SEO skill/tag maps (must stay aligned with backend taxonomy).
 */
export const SEO_SKILL_TAGS: Record<string, string[]> = {
  javascript: ["javascript", "js"],
  typescript: ["typescript", "ts"],
  python: ["python"],
  react: ["react", "react.js", "reactjs"],
  "next-js": ["next.js", "nextjs"],
  "node-js": ["node.js", "nodejs"],
  java: ["java"],
  go: ["go", "golang"],
  rust: ["rust"],
  php: ["php"],
  ruby: ["ruby"],
  kotlin: ["kotlin"],
  swift: ["swift"],
  sql: ["sql"],
  postgresql: ["postgresql", "postgres"],
  mongodb: ["mongodb"],
  mysql: ["mysql"],
  redis: ["redis"],
  graphql: ["graphql"],
  docker: ["docker"],
  kubernetes: ["kubernetes", "k8s"],
  aws: ["aws"],
  azure: ["azure"],
  gcp: ["gcp"],
  fastapi: ["fastapi"],
  django: ["django"],
  flask: ["flask"],
  vue: ["vue", "vue.js"],
  angular: ["angular"],
  svelte: ["svelte"],
  express: ["express", "express.js"],
  terraform: ["terraform"],
  linux: ["linux"],
  "tailwind-css": ["tailwind", "tailwind css"],
  pytorch: ["pytorch"],
  tensorflow: ["tensorflow"],
  langchain: ["langchain"],
};

export function skillTagsForSlug(slug: string): string {
  return (SEO_SKILL_TAGS[slug] || [slug.replace(/-/g, " ")]).join(",");
}

export function skillSeoHref(tag: string): string | null {
  const t = tag.toLowerCase().trim();
  for (const [slug, tags] of Object.entries(SEO_SKILL_TAGS)) {
    if (tags.includes(t) || slug === t.replace(/\./g, "-")) {
      return `/remote-${slug}-jobs`;
    }
  }
  return null;
}

export function companySeoHref(companyName: string): string {
  const slug = companyName
    .toLowerCase()
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/-+/g, "-")
    .replace(/^-|-$/g, "")
    .slice(0, 80);
  return `/companies/${slug || "company"}`;
}
