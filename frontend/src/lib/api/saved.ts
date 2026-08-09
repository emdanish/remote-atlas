import { apiFetch } from "./client";
import type {
  ApplicationStatus,
  FitBrief,
  Notification,
  OnboardingStatus,
  ResumeParseResponse,
  SavedJob,
  SavedSearch,
  SavedSearchRun,
} from "./types";

export async function listSaved(): Promise<SavedJob[]> {
  return apiFetch<SavedJob[]>("/saved-jobs");
}

export async function saveJob(
  job_id: number,
  status: ApplicationStatus = "saved",
): Promise<SavedJob> {
  return apiFetch<SavedJob>("/saved-jobs", {
    method: "POST",
    body: JSON.stringify({ job_id, status }),
  });
}

export async function deleteSaved(savedId: number): Promise<void> {
  return apiFetch<void>(`/saved-jobs/${savedId}`, { method: "DELETE" });
}

export async function updateApplication(
  savedId: number,
  status: ApplicationStatus,
  notes?: string | null,
): Promise<{ id: number; status: ApplicationStatus; notes: string | null }> {
  return apiFetch(`/applications/${savedId}`, {
    method: "PATCH",
    body: JSON.stringify({ status, notes }),
  });
}

export async function listNotifications(): Promise<Notification[]> {
  return apiFetch<Notification[]>("/notifications");
}

export async function generateMatchNotifications(): Promise<Notification[]> {
  return apiFetch<Notification[]>("/notifications/generate-matches", {
    method: "POST",
  });
}

export async function markNotificationsRead(): Promise<{ updated: number }> {
  return apiFetch<{ updated: number }>("/notifications/mark-read", {
    method: "POST",
  });
}

export async function markNotificationRead(
  notificationId: number,
): Promise<{ id: number; is_read: boolean }> {
  return apiFetch<{ id: number; is_read: boolean }>(
    `/notifications/${notificationId}/read`,
    { method: "PATCH" },
  );
}

export async function parseResume(file: File): Promise<ResumeParseResponse> {
  const form = new FormData();
  form.append("file", file);
  return apiFetch<ResumeParseResponse>("/resume/parse", {
    method: "POST",
    body: form,
  });
}

export async function getFitBrief(jobId: number): Promise<FitBrief> {
  return apiFetch<FitBrief>(`/jobs/${jobId}/fit-brief`, { cache: "no-store" });
}

export async function completeOnboarding(body: {
  skipped?: boolean;
  seed_skills?: string[];
}): Promise<OnboardingStatus> {
  return apiFetch<OnboardingStatus>("/onboarding/complete", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function getOnboardingStatus(): Promise<OnboardingStatus> {
  return apiFetch<OnboardingStatus>("/onboarding/status", { cache: "no-store" });
}

export async function listSavedSearches(): Promise<SavedSearch[]> {
  return apiFetch<SavedSearch[]>("/saved-searches");
}

export async function createSavedSearch(body: {
  name: string;
  query_params: Record<string, unknown>;
  is_active?: boolean;
}): Promise<SavedSearch> {
  return apiFetch<SavedSearch>("/saved-searches", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function updateSavedSearch(
  id: number,
  body: Partial<{ name: string; query_params: Record<string, unknown>; is_active: boolean }>,
): Promise<SavedSearch> {
  return apiFetch<SavedSearch>(`/saved-searches/${id}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

export async function deleteSavedSearch(id: number): Promise<void> {
  return apiFetch<void>(`/saved-searches/${id}`, { method: "DELETE" });
}

export async function runSavedSearch(id: number): Promise<SavedSearchRun> {
  return apiFetch<SavedSearchRun>(`/saved-searches/${id}/run`, { method: "POST" });
}
