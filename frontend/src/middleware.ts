import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";

const PRIVATE_PREFIXES = [
  "/profile",
  "/saved",
  "/matches",
  "/alerts",
  "/onboarding",
  "/login",
  "/register",
];

/**
 * Crawler hints that complement robots.txt + page metadata:
 * - Faceted job search URLs: noindex (canonical consolidates to /jobs)
 * - Private/auth routes: noindex, nofollow
 */
export function middleware(request: NextRequest) {
  const { pathname, searchParams } = request.nextUrl;
  const response = NextResponse.next();

  if (pathname === "/jobs" && searchParams.toString().length > 0) {
    response.headers.set("X-Robots-Tag", "noindex, follow");
    return response;
  }

  if (PRIVATE_PREFIXES.some((p) => pathname === p || pathname.startsWith(`${p}/`))) {
    response.headers.set("X-Robots-Tag", "noindex, nofollow");
  }

  return response;
}

export const config = {
  matcher: [
    "/jobs",
    "/profile/:path*",
    "/saved/:path*",
    "/matches/:path*",
    "/alerts/:path*",
    "/onboarding/:path*",
    "/login",
    "/register",
  ],
};
