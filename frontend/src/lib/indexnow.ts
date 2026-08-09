/**
 * Optional IndexNow (Bing family) notifier — free protocol.
 * Call only from trusted server contexts when INDEXNOW_ENABLED=true.
 */

import { SITE_URL } from "@/lib/api/client";

export const INDEXNOW_KEY = "remoteatlasindexnow2026key32chars";

export function indexNowKeyLocation(): string {
  return `${SITE_URL.replace(/\/+$/, "")}/${INDEXNOW_KEY}.txt`;
}

export async function submitIndexNow(urls: string[]): Promise<{ ok: boolean; status: number }> {
  if (process.env.INDEXNOW_ENABLED !== "true") {
    return { ok: false, status: 0 };
  }
  if (process.env.VERCEL_ENV && process.env.VERCEL_ENV !== "production") {
    return { ok: false, status: 0 };
  }
  const unique = [...new Set(urls.filter(Boolean))].slice(0, 10_000);
  if (!unique.length) return { ok: false, status: 0 };

  let host: string;
  try {
    host = new URL(SITE_URL).host;
  } catch {
    return { ok: false, status: 0 };
  }

  const res = await fetch("https://api.indexnow.org/indexnow", {
    method: "POST",
    headers: { "Content-Type": "application/json; charset=utf-8" },
    body: JSON.stringify({
      host,
      key: INDEXNOW_KEY,
      keyLocation: indexNowKeyLocation(),
      urlList: unique,
    }),
  });
  return { ok: res.ok || res.status === 202, status: res.status };
}
