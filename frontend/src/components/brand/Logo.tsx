import Link from "next/link";
import { cn } from "@/lib/utils";

type Props = {
  className?: string;
  markClassName?: string;
  showWordmark?: boolean;
  href?: string | null;
  size?: "sm" | "md" | "lg";
};

const sizes = {
  sm: { mark: "h-7 w-7", text: "text-lg" },
  md: { mark: "h-8 w-8", text: "text-xl" },
  lg: { mark: "h-10 w-10", text: "text-2xl" },
};

export function LogoMark({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 40 40"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={cn("shrink-0", className)}
      aria-hidden
    >
      <circle cx="20" cy="20" r="15.5" stroke="currentColor" strokeWidth="1.5" opacity="0.18" />
      <path
        d="M20 5.5 C11.5 5.5 6.5 12 6.5 20 C6.5 28 11.5 34.5 20 34.5"
        stroke="var(--color-accent)"
        strokeWidth="2.25"
        strokeLinecap="round"
      />
      <path
        d="M12 26.5 L20 14.5 L28.5 22.5"
        stroke="currentColor"
        strokeWidth="2.25"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <circle cx="20" cy="14.5" r="2.1" fill="var(--color-accent)" />
      <path d="M20 8.2 V11.4" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" />
    </svg>
  );
}

export function Logo({
  className,
  markClassName,
  showWordmark = true,
  href = "/",
  size = "md",
}: Props) {
  const s = sizes[size];
  const inner = (
    <span className={cn("inline-flex items-center gap-2.5 text-ink", className)}>
      <LogoMark className={cn(s.mark, markClassName)} />
      {showWordmark ? (
        <span className={cn("font-display font-semibold tracking-tight", s.text)}>
          Remote Atlas
        </span>
      ) : (
        <span className="sr-only">Remote Atlas</span>
      )}
    </span>
  );

  if (href === null) return inner;
  return (
    <Link href={href} className="inline-flex items-center" aria-label="Remote Atlas home">
      {inner}
    </Link>
  );
}
