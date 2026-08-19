import { readFileSync } from "node:fs";
import { join } from "node:path";

/**
 * Load the OG mark only inside `/api/og`. Never import this from pages:
 * Next used to import app/opengraph-image.tsx while resolving metadata on
 * every dynamic route, which crashed streamed metadata (error $Z).
 */
export function readOgLogoPng(): Buffer {
  return readFileSync(join(process.cwd(), "public/icon-192.png"));
}
