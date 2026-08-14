"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Bookmark, Bell, Sparkles, UserRound, ListChecks } from "lucide-react";
import { cn } from "@/lib/utils";

const items = [
  { href: "/matches", label: "Matches", icon: Sparkles },
  { href: "/hunt", label: "Hunt", icon: ListChecks },
  { href: "/alerts", label: "Pulse", icon: Bell },
  { href: "/saved", label: "Saved jobs", icon: Bookmark },
  { href: "/profile", label: "Profile", icon: UserRound },
];

export function WorkspaceNav() {
  const pathname = usePathname();

  return (
    <nav
      aria-label="Career workspace"
      className="mt-6 flex gap-1 overflow-x-auto rounded-xl border border-line bg-elevated p-1 shadow-soft"
    >
      {items.map(({ href, label, icon: Icon }) => {
        const active = pathname === href || pathname.startsWith(`${href}/`);
        return (
          <Link
            key={href}
            href={href}
            aria-current={active ? "page" : undefined}
            className={cn(
              "inline-flex min-w-fit flex-1 items-center justify-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
              active
                ? "bg-ink text-white shadow-soft"
                : "text-muted hover:bg-paper hover:text-ink",
            )}
          >
            <Icon className="h-4 w-4" aria-hidden />
            {label}
          </Link>
        );
      })}
    </nav>
  );
}
