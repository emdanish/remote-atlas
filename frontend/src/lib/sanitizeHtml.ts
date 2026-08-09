import sanitizeHtml from "sanitize-html";

/** Allowlist for third-party job description HTML (XSS-safe presentation only). */
const SANITIZE_OPTIONS: sanitizeHtml.IOptions = {
  allowedTags: [
    "p",
    "br",
    "hr",
    "h2",
    "h3",
    "h4",
    "strong",
    "b",
    "em",
    "i",
    "u",
    "ul",
    "ol",
    "li",
    "blockquote",
    "a",
    "span",
    "div",
    "section",
    "pre",
    "code",
  ],
  allowedAttributes: {
    a: ["href", "name", "target", "rel", "title"],
    span: ["class"],
    div: ["class"],
    code: ["class"],
    pre: ["class"],
  },
  allowedSchemes: ["http", "https", "mailto"],
  allowProtocolRelative: false,
  transformTags: {
    a: sanitizeHtml.simpleTransform("a", {
      rel: "noopener noreferrer nofollow",
      target: "_blank",
    }),
  },
  exclusiveFilter(frame) {
    if (frame.tag === "span" && !frame.text.trim() && !frame.mediaChildren?.length) {
      return true;
    }
    return false;
  },
};

const ENCODED_TAG_RE =
  /&lt;\s*\/?\s*(?:p|div|br|ul|ol|li|h[1-6]|span|strong|em|b|i|a|section)(?:\s|&gt;|\/)/i;

const REAL_TAG_RE = /<\s*\/?\s*[a-zA-Z][a-zA-Z0-9]*\b/;

/** Detect entity-encoded outer HTML (&lt;p&gt;...) that browsers show as raw tags. */
export function looksLikeEncodedHtml(value: string): boolean {
  if (!value) return false;
  if (REAL_TAG_RE.test(value) && value.includes("<")) {
    // Real tags present — not outer-encoded
    if (!ENCODED_TAG_RE.test(value)) return false;
  }
  return ENCODED_TAG_RE.test(value);
}

/**
 * Decode only outer entity-encoded markup (Greenhouse-style content).
 * Stops after a few rounds to avoid over-unescaping legitimate entities.
 */
export function decodeEntityEncodedHtml(value: string, maxRounds = 3): string {
  let out = value;
  for (let i = 0; i < maxRounds; i++) {
    if (!looksLikeEncodedHtml(out)) break;
    const textarea =
      typeof document !== "undefined" ? document.createElement("textarea") : null;
    let next: string;
    if (textarea) {
      textarea.innerHTML = out;
      next = textarea.value;
    } else {
      // SSR / Node: minimal entity decode for common markup entities
      next = out
        .replace(/&lt;/g, "<")
        .replace(/&gt;/g, ">")
        .replace(/&quot;/g, '"')
        .replace(/&#39;/g, "'")
        .replace(/&amp;/g, "&");
    }
    if (next === out) break;
    out = next;
  }
  return out;
}

/** Convert simple Markdown links that sometimes appear inside source bodies. */
function markdownLinksToHtml(value: string): string {
  return value.replace(
    /\[([^\]]+)\]\((https?:\/\/[^\s)]+|mailto:[^\s)]+)\)/gi,
    (_m, label: string, href: string) =>
      `<a href="${href}">${String(label).replace(/</g, "&lt;")}</a>`,
  );
}

/** Sanitize source HTML for safe React rendering. */
export function sanitizeJobHtml(html: string | null | undefined): string {
  if (!html || !html.trim()) return "";
  let input = html.trim();
  if (looksLikeEncodedHtml(input)) {
    input = decodeEntityEncodedHtml(input);
  }
  if (input.includes("[") && input.includes("](")) {
    input = markdownLinksToHtml(input);
  }
  return sanitizeHtml(input, SANITIZE_OPTIONS).trim();
}

/** Convert plain text job descriptions into simple HTML paragraphs/line breaks. */
export function plainTextToHtml(text: string | null | undefined): string {
  if (!text || !text.trim()) return "";
  // If text secretly holds markup, route through HTML path
  if (looksLikeEncodedHtml(text) || REAL_TAG_RE.test(text)) {
    const viaHtml = sanitizeJobHtml(text);
    if (viaHtml) return viaHtml;
  }
  const escaped = text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
  const parts = escaped
    .split(/\n{2,}/)
    .map((p) => `<p>${p.replace(/\n/g, "<br/>")}</p>`)
    .join("");
  return parts || `<p>${escaped}</p>`;
}

export function jobDescriptionHtml(
  html: string | null | undefined,
  text: string | null | undefined,
): string {
  const fromHtml = sanitizeJobHtml(html);
  if (fromHtml) return fromHtml;
  return plainTextToHtml(text);
}
