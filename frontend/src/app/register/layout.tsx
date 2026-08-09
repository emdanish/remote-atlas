import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Create account",
  description: "Create a free Remote Atlas account for job matches, saves, alerts, and resume tailoring.",
  robots: { index: false, follow: false },
  alternates: { canonical: "/register" },
};

export default function RegisterLayout({ children }: { children: React.ReactNode }) {
  return children;
}
