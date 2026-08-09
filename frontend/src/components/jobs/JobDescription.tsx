import { jobDescriptionHtml } from "@/lib/sanitizeHtml";

type Props = {
  html?: string | null;
  text?: string | null;
  className?: string;
};

/**
 * Server Component: renders sanitized job description HTML with plain-text fallback.
 */
export function JobDescription({ html, text, className }: Props) {
  const safe = jobDescriptionHtml(html, text);
  if (!safe) {
    return (
      <p className={className ?? "text-[15px] leading-relaxed text-ink/90"}>
        No description provided by the source.
      </p>
    );
  }
  return (
    <div
      className={
        className ??
        "prose-job text-[15px] leading-relaxed text-ink/90 [&_h2]:mt-8 [&_h2]:mb-3 [&_h2]:font-display [&_h2]:text-xl [&_h2]:font-semibold [&_h2]:text-ink [&_h3]:mt-6 [&_h3]:mb-2 [&_h3]:text-lg [&_h3]:font-semibold [&_h3]:text-ink [&_h4]:mt-4 [&_h4]:mb-2 [&_h4]:font-semibold [&_p]:my-3 [&_ul]:my-3 [&_ul]:list-disc [&_ul]:pl-5 [&_ol]:my-3 [&_ol]:list-decimal [&_ol]:pl-5 [&_li]:my-1 [&_a]:font-medium [&_a]:text-accent [&_a]:underline-offset-2 hover:[&_a]:underline [&_blockquote]:border-l-2 [&_blockquote]:border-line [&_blockquote]:pl-4 [&_blockquote]:text-muted [&_strong]:font-semibold [&_code]:rounded [&_code]:bg-paper [&_code]:px-1 [&_code]:text-sm"
      }
      dangerouslySetInnerHTML={{ __html: safe }}
    />
  );
}
