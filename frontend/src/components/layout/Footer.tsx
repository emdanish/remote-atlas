import Link from "next/link";
import { Logo } from "@/components/brand/Logo";

const productLinks = [
  { href: "/jobs", label: "Browse jobs" },
  { href: "/remote-javascript-jobs", label: "JavaScript remote" },
  { href: "/remote-python-jobs", label: "Python remote" },
  { href: "/companies", label: "Companies" },
  { href: "/remote-jobs/pakistan", label: "Pakistan-friendly remote" },
  { href: "/register", label: "Create account" },
  { href: "/login", label: "Sign in" },
];

export function Footer() {
  return (
    <footer className="mt-auto border-t border-line bg-elevated">
      <div className="mx-auto flex max-w-6xl flex-col gap-8 px-4 py-12 sm:px-6 md:flex-row md:items-start md:justify-between">
        <div className="max-w-sm space-y-3">
          <Logo size="sm" />
          <p className="text-sm leading-relaxed text-muted">
            A candidate-first job search engine: authentic sources, a strict freshness
            window, and a path straight to the employer&apos;s apply page — plus optional
            resume tailoring.
          </p>
        </div>
        <div>
          <p className="text-xs font-semibold uppercase tracking-wider text-muted">Product</p>
          <ul className="mt-3 space-y-2">
            {productLinks.map((l) => (
              <li key={l.href}>
                <Link href={l.href} className="text-sm text-ink hover:text-accent">
                  {l.label}
                </Link>
              </li>
            ))}
          </ul>
        </div>
        <div>
          <p className="text-xs font-semibold uppercase tracking-wider text-muted">Trust</p>
          <ul className="mt-3 space-y-2 text-sm text-muted">
            <li>Official apply URLs only</li>
            <li>Strictly recent job listings</li>
            <li>Transparent sources</li>
          </ul>
        </div>
      </div>
      <div className="border-t border-line">
        <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-2 px-4 py-4 text-xs text-muted sm:flex-row sm:px-6">
          <span>© {new Date().getFullYear()} Remote Atlas</span>
          <span>
            Built with ❤️ by{" "}
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
