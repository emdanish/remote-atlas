import type { Metadata } from "next";
import { Fraunces, Plus_Jakarta_Sans } from "next/font/google";
import "./globals.css";
import { AppProviders } from "@/components/providers/AppProviders";
import { Header } from "@/components/layout/Header";
import { Footer } from "@/components/layout/Footer";
import { OnboardingBanner } from "@/components/onboarding/OnboardingBanner";
import { SITE_URL } from "@/lib/api";
import { absoluteUrl } from "@/lib/seo";
import { JsonLd } from "@/components/seo/JsonLd";

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
    "junior remote jobs",
    "remote internships",
    "job search",
    "ATS jobs",
    "Remote Atlas",
  ],
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
    icon: [
      { url: "/icon-48.png", sizes: "48x48", type: "image/png" },
      { url: "/icon-192.png", sizes: "192x192", type: "image/png" },
      { url: "/favicon.ico", sizes: "48x48", type: "image/x-icon" },
      { url: "/favicon.svg", type: "image/svg+xml" },
    ],
    apple: [{ url: "/apple-touch-icon.png", sizes: "180x180", type: "image/png" }],
    shortcut: "/favicon.ico",
  },
  other: {
    "theme-color": "#0B1F1A",
  },
};

const orgJsonLd = {
  "@context": "https://schema.org",
  "@type": "Organization",
  "@id": `${SITE_URL}/#organization`,
  name: "Remote Atlas",
  url: SITE_URL,
  logo: {
    "@type": "ImageObject",
    url: absoluteUrl("/icon-512.png"),
    width: 512,
    height: 512,
  },
  image: absoluteUrl("/icon-512.png"),
  description:
    "Developer-focused job discovery engine with verified official apply links and a strict freshness window.",
};

const siteJsonLd = {
  "@context": "https://schema.org",
  "@type": "WebSite",
  "@id": `${SITE_URL}/#website`,
  name: "Remote Atlas",
  url: SITE_URL,
  publisher: { "@id": `${SITE_URL}/#organization` },
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
        <JsonLd id="ld-organization" data={orgJsonLd} />
        <JsonLd id="ld-website" data={siteJsonLd} />
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
