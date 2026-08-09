import { API_URL, handle } from "./client";
import type { IngestHealth } from "./types";

export async function getIngestStats(): Promise<IngestHealth> {
  const res = await fetch(`${API_URL}/health/ingest`, {
    next: { revalidate: 120 },
  });
  return handle<IngestHealth>(res);
}
