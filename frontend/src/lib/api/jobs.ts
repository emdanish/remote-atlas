import { apiFetch } from "./client";
import type { Job, JobSearchParams, JobSearchResponse, MatchResponse } from "./types";

export async function searchJobs(
  params: JobSearchParams = {},
  init?: { signal?: AbortSignal },
): Promise<JobSearchResponse> {
  const qs = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v === undefined || v === "" || v === false) return;
    qs.set(k, String(v));
  });
  if (params.hybrid === undefined) qs.set("hybrid", "true");
  return apiFetch<JobSearchResponse>(`/jobs/search?${qs.toString()}`, {
    cache: "no-store",
    signal: init?.signal,
  });
}

export async function getJob(id: number, init?: { signal?: AbortSignal }): Promise<Job> {
  return apiFetch<Job>(`/jobs/${id}`, { cache: "no-store", signal: init?.signal });
}

export async function getRecommendations(
  pageSize = 20,
): Promise<MatchResponse> {
  return apiFetch<MatchResponse>(`/recommendations?page_size=${pageSize}`, {
    cache: "no-store",
  });
}
