import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Matches",
  robots: { index: false, follow: false },
};

export default function MatchesLayout({ children }: { children: React.ReactNode }) {
  return children;
}
