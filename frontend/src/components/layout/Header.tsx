"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ChevronDown, LogOut, Menu, UserRound, X } from "lucide-react";
import { useState } from "react";
import { Logo } from "@/components/brand/Logo";
import { Button } from "@/components/ui/Button";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";

const publicLinks = [
  { href: "/jobs", label: "Jobs" },
  { href: "/companies", label: "Companies" },
];

const authLinks = [
  { href: "/jobs", label: "Jobs" },
  { href: "/matches", label: "Matches" },
  { href: "/saved", label: "Saved" },
  { href: "/alerts", label: "Pulse" },
  { href: "/companies", label: "Companies" },
];

function isActive(pathname: string, href: string) {
  if (href === "/jobs") return pathname === "/jobs" || pathname.startsWith("/jobs/");
  return pathname === href || pathname.startsWith(`${href}/`);
}

export function Header() {
  const { user, logout, loading } = useAuth();
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const links = user ? authLinks : publicLinks;
  const displayName = user?.full_name?.trim() || "Remote Atlas member";
  const initials = user
    ? (user.full_name || user.email)
        .split(/[\s@._-]+/)
        .filter(Boolean)
        .slice(0, 2)
        .map((part) => part[0]?.toUpperCase())
        .join("")
    : "";

  return (
    <header className="sticky top-0 z-40 border-b border-line/70 bg-elevated/85 backdrop-blur-md supports-[backdrop-filter]:bg-elevated/75">
      <div className="mx-auto flex h-14 max-w-6xl items-center justify-between gap-4 px-4 sm:h-16 sm:px-6">
        <Logo size="sm" />
        <nav className="hidden items-center gap-0.5 md:flex" aria-label="Primary">
          {links.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className={cn(
                "rounded-md px-3 py-2 text-sm font-medium transition-colors",
                isActive(pathname, link.href)
                  ? "bg-paper text-ink"
                  : "text-muted hover:bg-paper/70 hover:text-ink",
              )}
            >
              {link.label}
            </Link>
          ))}
        </nav>
        <div className="hidden items-center gap-2 md:flex">
          {!loading && !user ? (
            <>
              <Button href="/login" variant="ghost" size="sm">
                Sign in
              </Button>
              <Button href="/register" size="sm">
                Create account
              </Button>
            </>
          ) : null}
          {!loading && user ? (
            <details className="group relative">
              <summary className="flex cursor-pointer list-none items-center gap-2 rounded-full border border-line bg-elevated p-1 pr-2.5 shadow-soft transition hover:border-accent/30 [&::-webkit-details-marker]:hidden">
                <span className="grid h-8 w-8 place-items-center rounded-full bg-accent text-xs font-bold text-white">
                  {initials}
                </span>
                <span className="hidden max-w-28 truncate text-sm font-semibold text-ink lg:block">
                  {displayName}
                </span>
                <ChevronDown
                  className="h-3.5 w-3.5 text-muted transition group-open:rotate-180"
                  aria-hidden
                />
              </summary>
              <div className="absolute right-0 top-[calc(100%+0.5rem)] w-64 overflow-hidden rounded-xl border border-line bg-elevated shadow-lift">
                <div className="border-b border-line bg-paper/80 p-3.5">
                  <div className="flex items-center gap-2.5">
                    <span className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-accent text-xs font-bold text-white">
                      {initials}
                    </span>
                    <div className="min-w-0">
                      <p className="truncate text-sm font-semibold text-ink">{displayName}</p>
                      <p className="truncate text-xs text-muted" title={user.email}>
                        {user.email}
                      </p>
                    </div>
                  </div>
                </div>
                <div className="p-1.5">
                  <Link
                    href="/profile"
                    className="flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium text-ink hover:bg-paper"
                  >
                    <UserRound className="h-4 w-4 text-muted" aria-hidden />
                    Profile
                  </Link>
                  <button
                    type="button"
                    className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm font-medium text-muted hover:bg-paper hover:text-ink"
                    onClick={logout}
                  >
                    <LogOut className="h-4 w-4" aria-hidden />
                    Sign out
                  </button>
                </div>
              </div>
            </details>
          ) : null}
        </div>
        <button
          type="button"
          className="inline-flex h-10 w-10 items-center justify-center rounded-md border border-line text-ink transition hover:bg-paper md:hidden"
          aria-label={open ? "Close menu" : "Open menu"}
          aria-expanded={open}
          onClick={() => setOpen((v) => !v)}
        >
          {open ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
        </button>
      </div>
      {open ? (
        <div className="border-t border-line bg-elevated px-4 py-3 md:hidden">
          <nav className="flex flex-col gap-0.5" aria-label="Mobile">
            {links.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                className={cn(
                  "rounded-md px-3 py-2.5 text-sm font-medium",
                  isActive(pathname, link.href) ? "bg-paper text-ink" : "text-ink hover:bg-paper",
                )}
                onClick={() => setOpen(false)}
              >
                {link.label}
              </Link>
            ))}
            {!user ? (
              <>
                <Link
                  href="/login"
                  className="rounded-md px-3 py-2.5 text-sm text-muted"
                  onClick={() => setOpen(false)}
                >
                  Sign in
                </Link>
                <Link
                  href="/register"
                  className="rounded-md px-3 py-2.5 text-sm font-semibold text-accent"
                  onClick={() => setOpen(false)}
                >
                  Create account
                </Link>
              </>
            ) : (
              <>
                <Link
                  href="/profile"
                  className="rounded-md px-3 py-2.5 text-sm font-medium text-ink"
                  onClick={() => setOpen(false)}
                >
                  Profile
                </Link>
                <div className="my-2 flex items-center gap-3 rounded-xl border border-line bg-paper p-3">
                  <span className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-accent text-xs font-bold text-white">
                    {initials}
                  </span>
                  <div className="min-w-0">
                    <p className="truncate text-sm font-semibold text-ink">{displayName}</p>
                    <p className="truncate text-xs text-muted">{user.email}</p>
                  </div>
                </div>
                <button
                  type="button"
                  className="rounded-md px-3 py-2.5 text-left text-sm text-muted"
                  onClick={() => {
                    logout();
                    setOpen(false);
                  }}
                >
                  Sign out
                </button>
              </>
            )}
          </nav>
        </div>
      ) : null}
    </header>
  );
}
