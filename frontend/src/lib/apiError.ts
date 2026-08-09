/** Human-readable API / validation errors for UI alerts. */

export function formatApiError(err: unknown, fallback = "Something went wrong."): string {
  if (!err) return fallback;
  if (typeof err === "string") return err || fallback;

  const raw =
    err instanceof Error
      ? err.message
      : typeof err === "object" && err !== null && "message" in err
        ? String((err as { message: unknown }).message)
        : "";

  if (!raw) return fallback;

  // Already friendly
  if (!raw.trimStart().startsWith("[") && !raw.trimStart().startsWith("{")) {
    return raw;
  }

  try {
    const parsed = JSON.parse(raw) as unknown;
    return formatValidationDetail(parsed) || fallback;
  } catch {
    // Sometimes detail is embedded in a larger string
    const start = raw.indexOf("[");
    if (start >= 0) {
      try {
        return formatValidationDetail(JSON.parse(raw.slice(start))) || fallback;
      } catch {
        /* fall through */
      }
    }
  }
  return raw.length > 280 ? `${raw.slice(0, 277)}…` : raw || fallback;
}

function formatValidationDetail(detail: unknown): string | null {
  if (typeof detail === "string") return detail;
  if (!Array.isArray(detail) || detail.length === 0) {
    if (detail && typeof detail === "object" && "msg" in detail) {
      return String((detail as { msg: string }).msg);
    }
    return null;
  }

  const parts: string[] = [];
  for (const item of detail) {
    if (!item || typeof item !== "object") continue;
    const row = item as {
      type?: string;
      loc?: unknown[];
      msg?: string;
      ctx?: { max_length?: number; actual_length?: number; field_type?: string };
    };
    const field = fieldFromLoc(row.loc);
    const msg = row.msg || "Invalid value";
    if (row.type === "too_long" && row.ctx?.max_length != null) {
      const actual = row.ctx.actual_length ?? "?";
      parts.push(
        `${field}: too many items (${actual}). Maximum allowed is ${row.ctx.max_length}.`,
      );
    } else if (row.type === "string_too_long" && row.ctx?.max_length != null) {
      parts.push(`${field}: too long (max ${row.ctx.max_length} characters).`);
    } else if (row.type === "missing") {
      parts.push(`${field}: this field is required.`);
    } else if (row.type === "value_error") {
      parts.push(`${field}: ${msg.replace(/^Value error,\s*/i, "")}`);
    } else {
      parts.push(`${field}: ${msg}`);
    }
  }
  return parts.length ? parts.join(" ") : null;
}

function fieldFromLoc(loc: unknown[] | undefined): string {
  if (!loc?.length) return "Form";
  const parts = loc
    .filter((p) => p !== "body" && p !== "query" && p !== "path")
    .map((p) => String(p).replace(/_/g, " "));
  if (!parts.length) return "Form";
  return parts
    .map((p) => p.charAt(0).toUpperCase() + p.slice(1))
    .join(" › ");
}
