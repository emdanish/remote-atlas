import { NextRequest, NextResponse } from "next/server";
import { submitIndexNow } from "@/lib/indexnow";
import { SITE_URL } from "@/lib/api/client";

/**
 * Optional IndexNow submit endpoint.
 * Requires Authorization: Bearer $INDEXNOW_SUBMIT_TOKEN and INDEXNOW_ENABLED=true.
 * Body: { "urls": ["https://www.remoteatlas.dev/jobs/1", ...] }
 * or empty body to ping homepage + /jobs only.
 */
export async function POST(request: NextRequest) {
  const token = process.env.INDEXNOW_SUBMIT_TOKEN;
  if (!token) {
    return NextResponse.json({ error: "IndexNow submit not configured" }, { status: 503 });
  }
  const auth = request.headers.get("authorization") || "";
  if (auth !== `Bearer ${token}`) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  let urls: string[] = [`${SITE_URL}/`, `${SITE_URL}/jobs`];
  try {
    const body = (await request.json()) as { urls?: string[] };
    if (Array.isArray(body?.urls) && body.urls.length) {
      urls = body.urls.filter((u) => typeof u === "string" && u.startsWith("https://"));
    }
  } catch {
    /* use defaults */
  }

  const result = await submitIndexNow(urls);
  return NextResponse.json(result, { status: result.ok ? 200 : 502 });
}
