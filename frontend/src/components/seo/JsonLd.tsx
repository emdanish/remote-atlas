import { safeJsonLd } from "@/lib/seo";

/**
 * JSON-LD as a normal script tag (Next.js documented approach).
 * Do not use next/script here — it is a client component and collides with
 * streamed generateMetadata (AsyncMetadataOutlet) on dynamic routes.
 */
export function JsonLd({ id, data }: { id: string; data: unknown }) {
  return (
    <script
      id={id}
      type="application/ld+json"
      dangerouslySetInnerHTML={{ __html: safeJsonLd(data) }}
    />
  );
}
