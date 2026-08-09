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
 * - Rewrite /remote-{skill}-jobs → /seo/skills/{skill} (Remote OK–style public URLs)
 * - Faceted /jobs?* : noindex,follow
 * - Private routes: noindex,nofollow
 */
export function middleware(request: NextRequest) {
  const { pathname, searchParams } = request.nextUrl;

  const skillMatch = pathname.match(/^\/remote-([a-z0-9-]+)-jobs\/?$/i);
  if (skillMatch) {
    const skill = skillMatch[1].toLowerCase();
    // Avoid catching /remote-jobs-… if ever added; require slug not empty
    if (skill && skill !== "jobs") {
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
    "/remote-:path*",
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
