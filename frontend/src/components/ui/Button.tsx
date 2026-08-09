import Link from "next/link";
import { cn } from "@/lib/utils";
import type { ButtonHTMLAttributes, ReactNode } from "react";

type Variant = "primary" | "secondary" | "ghost" | "danger";
type Size = "sm" | "md" | "lg";

const variants: Record<Variant, string> = {
  primary:
    "bg-accent text-white hover:bg-accent-strong shadow-soft border border-transparent",
  secondary:
    "bg-elevated text-ink border border-line hover:border-ink/20 shadow-soft",
  ghost: "bg-transparent text-ink hover:bg-ink/5 border border-transparent",
  danger: "bg-danger text-white hover:opacity-90 border border-transparent",
};

const sizes: Record<Size, string> = {
  sm: "h-9 px-3 text-sm rounded-md",
  md: "h-11 px-4 text-sm rounded-md",
  lg: "h-12 px-6 text-base rounded-lg",
};

type Props = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: Variant;
  size?: Size;
  href?: string;
  children: ReactNode;
  external?: boolean;
};

export function Button({
  variant = "primary",
  size = "md",
  className,
  href,
  children,
  external,
  ...rest
}: Props) {
  const classes = cn(
    "inline-flex items-center justify-center gap-2 font-medium transition-colors disabled:opacity-50 disabled:pointer-events-none",
    variants[variant],
    sizes[size],
    className,
  );

  if (href) {
    if (external) {
      return (
        <a href={href} className={classes} target="_blank" rel="noopener noreferrer">
          {children}
        </a>
      );
    }
    return (
      <Link href={href} className={classes}>
        {children}
      </Link>
    );
  }

  return (
    <button className={classes} {...rest}>
      {children}
    </button>
  );
}
