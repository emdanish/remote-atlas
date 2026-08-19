export const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
export const SITE_URL = (process.env.NEXT_PUBLIC_SITE_URL || "http://localhost:3000").replace(
  /\/+$/,
  "",
);

export class ApiError extends Error {
  status: number;
  /** Parsed field-level messages when available */
  fields?: string[];

  constructor(status: number, message: string, fields?: string[]) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.fields = fields;
  }
}

function humanizeDetail(body: unknown): { message: string; fields?: string[] } {
  if (!body || typeof body !== "object") {
    return { message: "Request failed" };
  }
  const detail = (body as { detail?: unknown }).detail;
  if (typeof detail === "string") return { message: detail };
  if (Array.isArray(detail)) {
    const fields: string[] = [];
    for (const item of detail) {
      if (!item || typeof item !== "object") continue;
      const row = item as {
        type?: string;
        loc?: unknown[];
        msg?: string;
        ctx?: { max_length?: number; actual_length?: number };
      };
      const loc = (row.loc || [])
        .filter((p) => p !== "body" && p !== "query" && p !== "path")
        .map(String);
      const field = loc.map((p) => p.replace(/_/g, " ")).join(" › ") || "Field";
      const prettyField = field
        .split(" › ")
        .map((p) => p.charAt(0).toUpperCase() + p.slice(1))
        .join(" › ");
      if (row.type === "too_long" && row.ctx?.max_length != null) {
        const actual = row.ctx.actual_length ?? "?";
        fields.push(
          `${prettyField}: too many items (${actual}). Max ${row.ctx.max_length}.`,
        );
      } else if (row.msg) {
        fields.push(`${prettyField}: ${row.msg}`);
      }
    }
    if (fields.length) {
      return {
        message: fields.join(" "),
        fields,
      };
    }
  }
  if (detail != null) {
    try {
      return { message: JSON.stringify(detail) };
    } catch {
      /* ignore */
    }
  }
  return { message: "Request failed" };
}

export function jsonHeaders(): HeadersInit {
  return { "Content-Type": "application/json" };
}

export async function handle<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let message = res.statusText || "Request failed";
    let fields: string[] | undefined;
    try {
      const body = await res.json();
      const parsed = humanizeDetail(body);
      message = parsed.message || message;
      fields = parsed.fields;
    } catch {
      /* ignore */
    }
    if (res.status === 401) {
      message = message || "Please sign in again.";
    } else if (res.status === 429) {
      message = "Too many requests. Wait a moment and try again.";
    } else if (res.status >= 500 && !fields?.length) {
      message = message || "Server error. Please try again shortly.";
    }
    throw new ApiError(res.status, message, fields);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export async function apiFetch<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const { headers, ...rest } = init || {};
  const merged: HeadersInit = {
    ...jsonHeaders(),
    ...(headers || {}),
  };
  // Cookies are browser-only. credentials:include on the server (generateMetadata)
  // is a common source of Next.js streaming-metadata failures.
  const credentials = typeof window === "undefined" ? "omit" : "include";
  // Allow FormData callers to omit Content-Type
  if (rest.body instanceof FormData) {
    const h = new Headers(merged);
    h.delete("Content-Type");
    const res = await fetch(`${API_URL}${path}`, { credentials, ...rest, headers: h });
    return handle<T>(res);
  }
  const res = await fetch(`${API_URL}${path}`, {
    credentials,
    ...rest,
    headers: merged,
  });
  return handle<T>(res);
}
