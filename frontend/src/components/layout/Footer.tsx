import Link from "next/link";
import { Logo } from "@/components/brand/Logo";

const exploreLinks = [
  { href: "/jobs", label: "Browse jobs" },
  { href: "/remote-junior-jobs", label: "Junior-eligible" },
  { href: "/remote-internships", label: "Internships" },
  { href: "/companies", label: "Companies" },
  { href: "/remote-javascript-jobs", label: "JavaScript remote" },
  { href: "/remote-python-jobs", label: "Python remote" },
  { href: "/remote-jobs/pakistan", label: "Pakistan-friendly" },
];

const productLinks = [
  { href: "/matches", label: "Matches" },
  { href: "/saved", label: "Saved jobs" },
  { href: "/alerts", label: "Pulse alerts" },
  { href: "/profile", label: "Profile" },
];

const accountLinks = [
  { href: "/register", label: "Create account" },
  { href: "/login", label: "Sign in" },
];

export function Footer() {
  return (
    <footer className="mt-auto border-t border-line bg-elevated">
      <div className="mx-auto grid max-w-6xl gap-10 px-4 py-12 sm:px-6 md:grid-cols-[1.4fr_1fr_1fr_1fr]">
        <div className="max-w-sm space-y-3">
          <Logo size="sm" />
          <p className="text-sm leading-relaxed text-muted">
            Candidate-first job search: authentic sources, a strict freshness window, and a direct
            path to the employer&apos;s apply page.
          </p>
        </div>
        <div>
          <p className="text-xs font-semibold uppercase tracking-wider text-muted">Explore</p>
          <ul className="mt-3 space-y-2">
            {exploreLinks.map((l) => (
              <li key={l.href}>
                <Link href={l.href} className="text-sm text-ink transition-colors hover:text-accent">
                  {l.label}
                </Link>
              </li>
            ))}
          </ul>
        </div>
        <div>
          <p className="text-xs font-semibold uppercase tracking-wider text-muted">Workspace</p>
          <ul className="mt-3 space-y-2">
            {productLinks.map((l) => (
              <li key={l.href}>
                <Link href={l.href} className="text-sm text-ink transition-colors hover:text-accent">
                  {l.label}
                </Link>
              </li>
            ))}
          </ul>
        </div>
        <div>
          <p className="text-xs font-semibold uppercase tracking-wider text-muted">Account</p>
          <ul className="mt-3 space-y-2">
            {accountLinks.map((l) => (
              <li key={l.href}>
                <Link href={l.href} className="text-sm text-ink transition-colors hover:text-accent">
                  {l.label}
                </Link>
              </li>
            ))}
          </ul>
          <p className="mt-6 text-xs font-semibold uppercase tracking-wider text-muted">Trust</p>
          <ul className="mt-2 space-y-1.5 text-sm text-muted">
            <li>Official apply URLs</li>
            <li>Strict freshness window</li>
            <li>Transparent sources</li>
          </ul>
        </div>
      </div>
      <div className="border-t border-line">
        <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-2 px-4 py-4 text-xs text-muted sm:flex-row sm:px-6">
          <span>© {new Date().getFullYear()} Remote Atlas</span>
          <span>
            Built with care by{" "}
            <a
              href="https://emdanish.dev"
              target="_blank"
              rel="noopener noreferrer"
              className="text-ink underline-offset-2 hover:text-accent hover:underline"
            >
              Danish
            </a>
          </span>
        </div>
      </div>
    </footer>
  );
}
