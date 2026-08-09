import { apiFetch, API_URL } from "./client";

export type UserResume = {
  id: number;
  filename: string;
  content_type: string;
  byte_size: number;
  is_primary: boolean;
  created_at: string;
  has_text: boolean;
};

export type Tailoring = {
  id: number;
  job_id: number;
  resume_id: number;
  status: string;
  stage?: string | null;
  error_message?: string | null;
  model_used?: string | null;
  created_at: string;
  completed_at?: string | null;
  original_excerpt?: string | null;
  tailored?: {
    summary?: string;
    contact?: {
      name?: string;
      headline?: string;
      email?: string;
      phone?: string;
      location?: string;
      links?: string[];
      [key: string]: unknown;
    };
    skill_groups?: Array<{ category: string; items: string[] }>;
    experience?: Array<{
      title?: string;
      org?: string;
      location?: string;
      dates?: string;
      bullets?: string[];
    }>;
    projects?: Array<{
      name?: string;
      technologies?: string[];
      bullets?: string[];
    }>;
    education?: Array<{
      school?: string;
      degree?: string;
      dates?: string;
      details?: string[];
    }>;
    other_sections?: Array<{ heading: string; items: string[] }>;
    sections?: Array<{
      heading: string;
      blocks: Array<Record<string, unknown>>;
    }>;
    changes?: unknown[];
    match_panel?: MatchPanel;
  } | null;
  changes?: TailorChange[] | null;
  match_panel?: MatchPanel | null;
  validation?: {
    ok?: boolean;
    issue_count?: number;
    high_severity?: number;
    issues?: Array<Record<string, unknown>>;
    fallback?: boolean;
    message?: string;
    fidelity_note?: string;
    page_count?: number;
    summary_heading_count?: number;
    has_tailored_for?: boolean;
    pdf_text_extractable?: boolean;
    quality_fixed?: string[];
  } | null;
  job_analysis?: Record<string, unknown> | null;
  has_pdf: boolean;
  fidelity_note?: string | null;
};

export type MatchPanel = {
  strong_matches?: string[];
  emphasized?: string[];
  missing?: string[];
  potential_gaps?: string[];
  note?: string;
};

export type TailorChange = {
  id: string;
  type: string;
  section: string;
  before: string;
  after: string;
  reason: string;
};

export async function listResumes(): Promise<UserResume[]> {
  return apiFetch<UserResume[]>("/resumes");
}

export async function uploadResume(file: File): Promise<UserResume> {
  const form = new FormData();
  form.append("file", file);
  return apiFetch<UserResume>("/resumes", { method: "POST", body: form });
}

export async function deleteResume(id: number): Promise<void> {
  await apiFetch(`/resumes/${id}`, { method: "DELETE" });
}

export async function startTailoring(
  jobId: number,
  resumeId?: number | null,
): Promise<Tailoring> {
  return apiFetch<Tailoring>(`/jobs/${jobId}/tailor-resume`, {
    method: "POST",
    body: JSON.stringify({ resume_id: resumeId ?? null }),
  });
}

export async function getTailoring(id: number): Promise<Tailoring> {
  return apiFetch<Tailoring>(`/tailorings/${id}`, { cache: "no-store" });
}

export async function listJobTailorings(jobId: number): Promise<Tailoring[]> {
  return apiFetch<Tailoring[]>(`/jobs/${jobId}/tailorings`, { cache: "no-store" });
}

export async function regenerateTailoring(id: number): Promise<Tailoring> {
  return apiFetch<Tailoring>(`/tailorings/${id}/regenerate`, { method: "POST" });
}

export async function deleteTailoring(id: number): Promise<void> {
  await apiFetch(`/tailorings/${id}`, { method: "DELETE" });
}

export function tailoredPdfUrl(id: number): string {
  return `${API_URL}/tailorings/${id}/pdf`;
}

/** Download with cookies (do not open blank window). */
export async function downloadTailoredPdf(id: number, filename?: string): Promise<void> {
  const res = await fetch(tailoredPdfUrl(id), { credentials: "include" });
  if (!res.ok) {
    throw new Error("Could not download PDF");
  }
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename || `tailored-resume-${id}.pdf`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
