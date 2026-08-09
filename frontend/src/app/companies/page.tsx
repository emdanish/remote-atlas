import type { Metadata } from "next";
import Link from "next/link";
import { getSeoCompanies } from "@/lib/api";

export const revalidate = 3600;

export const metadata: Metadata = {
  title: "Companies hiring remotely",
  description:
    "Browse companies with fresh roles in the Remote Atlas index. Open a company page to see current postings and apply on official career pages.",
  alternates: { canonical: "/companies" },
};

export default async function CompaniesHubPage() {
  const items = await getSeoCompanies(60).catch(() => []);
  return (
    <div className="mx-auto max-w-6xl px-4 py-12 sm:px-6">
      <h1 className="font-display text-3xl font-semibold text-ink">Companies with fresh roles</h1>
      <p className="mt-3 max-w-2xl text-muted">
        Companies that currently have enough active jobs in the freshness window to earn a
        dedicated landing page. Thin or empty company pages are not indexed.
      </p>
      <ul className="mt-10 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
        {items.map((c) => (
          <li key={c.slug}>
            <Link
              href={c.href}
              className="flex items-center justify-between rounded-lg border border-line bg-elevated px-4 py-3 text-sm hover:border-accent"
            >
              <span className="font-medium text-ink">{c.label}</span>
              <span className="text-muted">{c.count}</span>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
