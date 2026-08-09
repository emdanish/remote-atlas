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
    a: ["href", "name", "target", "rel"],
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
  // Drop empty noisy wrappers from ATS HTML
  exclusiveFilter(frame) {
    if (frame.tag === "span" && !frame.text.trim() && !frame.mediaChildren?.length) {
      return true;
    }
    return false;
  },
};

/** Sanitize source HTML for safe React rendering. */
export function sanitizeJobHtml(html: string | null | undefined): string {
  if (!html || !html.trim()) return "";
  return sanitizeHtml(html, SANITIZE_OPTIONS).trim();
}

/** Convert plain text job descriptions into simple HTML paragraphs/line breaks. */
export function plainTextToHtml(text: string | null | undefined): string {
  if (!text || !text.trim()) return "";
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
