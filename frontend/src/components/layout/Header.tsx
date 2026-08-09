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
];

const authLinks = [
  { href: "/jobs", label: "Jobs" },
  { href: "/matches", label: "Matches" },
  { href: "/alerts", label: "Pulse" },
  { href: "/saved", label: "Saved" },
  { href: "/profile", label: "Profile" },
];

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
    <header className="sticky top-0 z-40 border-b border-line/80 bg-elevated/90 backdrop-blur-md">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4 sm:px-6">
        <Logo size="sm" />
        <nav className="hidden items-center gap-1 md:flex" aria-label="Primary">
          {links.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className={cn(
                "rounded-md px-3 py-2 text-sm font-medium text-muted transition-colors hover:text-ink",
                pathname === link.href || pathname.startsWith(`${link.href}/`)
                  ? "bg-paper text-ink"
                  : "",
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
              <summary className="flex cursor-pointer list-none items-center gap-2 rounded-full border border-line bg-elevated p-1 pr-2 shadow-soft transition hover:border-accent/30 hover:shadow-lift [&::-webkit-details-marker]:hidden">
                <span className="grid h-9 w-9 place-items-center rounded-full bg-gradient-to-br from-accent to-ink text-xs font-bold text-white">
                  {initials}
                </span>
                <span className="hidden max-w-32 truncate text-sm font-semibold text-ink lg:block">
                  {displayName}
                </span>
                <ChevronDown className="h-4 w-4 text-muted transition group-open:rotate-180" aria-hidden />
              </summary>
              <div className="absolute right-0 top-[calc(100%+0.65rem)] w-72 overflow-hidden rounded-xl border border-line bg-elevated shadow-lift">
                <div className="border-b border-line bg-paper/70 p-4">
                  <div className="flex items-center gap-3">
                    <span className="grid h-11 w-11 shrink-0 place-items-center rounded-full bg-gradient-to-br from-accent to-ink text-sm font-bold text-white">
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
                <div className="p-2">
                  <Link
                    href="/profile"
                    className="flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium text-ink hover:bg-paper"
                  >
                    <UserRound className="h-4 w-4 text-muted" aria-hidden />
                    View profile
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
          className="inline-flex h-10 w-10 items-center justify-center rounded-md border border-line md:hidden"
          aria-label={open ? "Close menu" : "Open menu"}
          aria-expanded={open}
          onClick={() => setOpen((v) => !v)}
        >
          {open ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
        </button>
      </div>
      {open ? (
        <div className="border-t border-line bg-elevated px-4 py-4 md:hidden">
          <nav className="flex flex-col gap-1" aria-label="Mobile">
            {links.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                className="rounded-md px-3 py-2.5 text-sm font-medium text-ink hover:bg-paper"
                onClick={() => setOpen(false)}
              >
                {link.label}
              </Link>
            ))}
            {!user ? (
              <>
                <Link href="/login" className="rounded-md px-3 py-2.5 text-sm" onClick={() => setOpen(false)}>
                  Sign in
                </Link>
                <Link href="/register" className="rounded-md px-3 py-2.5 text-sm font-medium text-accent" onClick={() => setOpen(false)}>
                  Create account
                </Link>
              </>
            ) : (
              <>
                <div className="my-2 flex items-center gap-3 rounded-xl bg-paper p-3">
                  <span className="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-gradient-to-br from-accent to-ink text-xs font-bold text-white">
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
