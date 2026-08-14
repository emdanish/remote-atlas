import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";

const PRIVATE_PREFIXES = [
  "/profile",
  "/saved",
  "/matches",
  "/hunt",
  "/alerts",
  "/onboarding",
  "/login",
  "/register",
];

/**
 * - Rewrite /remote-{skill}-jobs → /seo/skills/{skill} (defense in depth with next.config)
 * - Faceted /jobs?* : noindex,follow
 * - Private routes: noindex,nofollow
 *
 * IMPORTANT: matcher must use a path-to-regexp pattern that actually compiles.
 * `/remote-:path*` is INVALID and previously caused all skill public URLs to 404.
 */
export function middleware(request: NextRequest) {
  const { pathname, searchParams } = request.nextUrl;

  const skillMatch = pathname.match(/^\/remote-([a-z0-9]+(?:-[a-z0-9]+)*)-jobs\/?$/i);
  if (skillMatch) {
    const skill = skillMatch[1].toLowerCase();
    // Explicit catalogue landings live as app routes, not skill taxonomy.
    if (skill && skill !== "jobs" && skill !== "junior") {
      const url = request.nextUrl.clone();
      url.pathname = `/seo/skills/${skill}`;
      return NextResponse.rewrite(url);
    }
  }

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
    // Compiles to /^\/remote-([^\/#\?]+?)-jobs[\/#\?]?$/i
    "/remote-:skill-jobs",
    "/jobs",
    "/profile/:path*",
    "/saved/:path*",
    "/matches/:path*",
    "/hunt/:path*",
    "/alerts/:path*",
    "/onboarding/:path*",
    "/login",
    "/register",
  ],
};
