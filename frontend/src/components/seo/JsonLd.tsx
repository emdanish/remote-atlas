import Script from "next/script";
import { safeJsonLd } from "@/lib/seo";

/** JSON-LD via next/script so it does not collide with streamed generateMetadata. */
export function JsonLd({ id, data }: { id: string; data: unknown }) {
  return (
    <Script
      id={id}
      type="application/ld+json"
      dangerouslySetInnerHTML={{ __html: safeJsonLd(data) }}
    />
  );
}
