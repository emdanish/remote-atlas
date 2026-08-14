import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Hunt plan",
  robots: { index: false, follow: false },
};

export default function HuntLayout({ children }: { children: React.ReactNode }) {
  return children;
}
