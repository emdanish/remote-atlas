import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Tech jobs — remote, hybrid & onsite",
  description:
    "Browse fresh software and tech roles from official company career systems. Filter by workplace, stack, seniority, and recency. Apply on the employer’s page.",
  alternates: { canonical: "/jobs" },
  openGraph: {
    title: "Tech jobs on Remote Atlas",
    description:
      "Fresh listings from authentic ATS sources. Search remote and hybrid roles without paywalled “unlocks”.",
    url: "/jobs",
  },
  twitter: {
    card: "summary_large_image",
    title: "Tech jobs on Remote Atlas",
    description: "Fresh, source-transparent tech jobs. Search freely; apply on official career pages.",
  },
  robots: { index: true, follow: true },
};

export default function JobsLayout({ children }: { children: React.ReactNode }) {
  return children;
}
