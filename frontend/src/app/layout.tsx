import type { Metadata } from "next";
import { Fraunces, Plus_Jakarta_Sans } from "next/font/google";
import "./globals.css";
import { AppProviders } from "@/components/providers/AppProviders";
import { Header } from "@/components/layout/Header";
import { Footer } from "@/components/layout/Footer";
import { OnboardingBanner } from "@/components/onboarding/OnboardingBanner";
import { SITE_URL } from "@/lib/api";
import { absoluteUrl, safeJsonLd } from "@/lib/seo";

const jakarta = Plus_Jakarta_Sans({
  subsets: ["latin"],
  variable: "--font-jakarta",
  display: "swap",
});

const fraunces = Fraunces({
  subsets: ["latin"],
  variable: "--font-fraunces",
  display: "swap",
});

const defaultTitle = "Remote Atlas | Candidate-first job discovery";
const defaultDescription =
  "Search fresh tech roles from authentic company career systems. Filters that match how candidates decide. Optional resume tailoring. Apply on the employer's official page.";

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: {
    default: defaultTitle,
    template: "%s · Remote Atlas",
  },
  description: defaultDescription,
  applicationName: "Remote Atlas",
  authors: [{ name: "Remote Atlas" }],
  creator: "Remote Atlas",
  category: "jobs",
  keywords: [
    "remote jobs",
    "tech jobs",
    "software engineer jobs",
    "developer jobs",
    "job search",
    "ATS jobs",
    "Remote Atlas",
  ],
  alternates: {
    canonical: "/",
  },
  openGraph: {
    type: "website",
    locale: "en_US",
    siteName: "Remote Atlas",
    title: defaultTitle,
    description:
      "Fresh roles from trusted sources. Semantic + keyword search. Resume tailoring without inventing experience.",
    url: SITE_URL,
  },
  twitter: {
    card: "summary_large_image",
    title: "Remote Atlas",
    description: "A job search engine built for candidates — not recruiters.",
  },
  robots: {
    index: true,
    follow: true,
    googleBot: {
      index: true,
      follow: true,
      "max-image-preview": "large",
      "max-snippet": -1,
      "max-video-preview": -1,
    },
  },
  icons: {
    icon: [{ url: "/favicon.svg", type: "image/svg+xml" }],
    apple: [{ url: "/icon.svg" }],
  },
  other: {
    "theme-color": "#0B1F1A",
  },
};

const orgJsonLd = {
  "@context": "https://schema.org",
  "@type": "Organization",
  name: "Remote Atlas",
  url: SITE_URL,
  logo: absoluteUrl("/brand/logo.svg"),
  description:
    "Developer-focused job discovery engine with verified official apply links and a strict freshness window.",
};

const siteJsonLd = {
  "@context": "https://schema.org",
  "@type": "WebSite",
  name: "Remote Atlas",
  url: SITE_URL,
  potentialAction: {
    "@type": "SearchAction",
    target: {
      "@type": "EntryPoint",
      urlTemplate: `${SITE_URL}/jobs?q={search_term_string}`,
    },
    "query-input": "required name=search_term_string",
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html
      lang="en"
      className={`${jakarta.variable} ${fraunces.variable}`}
      data-scroll-behavior="smooth"
    >
      <body className="flex min-h-screen flex-col font-sans antialiased">
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: safeJsonLd(orgJsonLd) }}
        />
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: safeJsonLd(siteJsonLd) }}
        />
        <AppProviders>
          <a
            href="#main-content"
            className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-md focus:bg-accent focus:px-3 focus:py-2 focus:text-white"
          >
            Skip to main content
          </a>
          <Header />
          <OnboardingBanner />
          <main id="main-content" className="flex-1" tabIndex={-1}>
            {children}
          </main>
          <Footer />
        </AppProviders>
      </body>
    </html>
  );
}
