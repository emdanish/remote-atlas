export type MatchBreakdown = {
  total: number;
  skill: number;
  role: number;
  seniority: number;
  remote: number;
  pakistan: number;
  freshness: number;
  matched_skills: string[];
  missing_skills: string[];
  reasons: string[];
};

export type Job = {
  id: number;
  source: string;
  external_id?: string;
  title: string;
  company_name: string;
  company_url?: string | null;
  apply_url?: string | null;
  career_page_url?: string | null;
  location_raw?: string | null;
  workplace_type: string;
  employment_type?: string | null;
  career_stage: string;
  skills: string[];
  tech_tags: string[];
  posted_at?: string | null;
  first_seen_at: string;
  last_seen_at?: string;
  is_active?: boolean;
  description_text?: string | null;
  score?: number | null;
  source_kind?: string | null;
  source_kind_label?: string | null;
  match_reasons?: string[];
  match_breakdown?: MatchBreakdown | null;
};

export type JobSearchResponse = {
  total: number;
  page: number;
  page_size: number;
  freshness_days: number;
  results: Job[];
};

export type MatchResponse = {
  total: number;
  freshness_days: number;
  results: Job[];
  empty_reason?: string | null;
  profile_complete?: boolean;
};

export type OnboardingStatus = {
  has_profile: boolean;
  has_skills: boolean;
  has_resume: boolean;
  has_desired_roles: boolean;
  onboarding_complete: boolean;
  seed_skills: string[];
  completion_percent: number;
  resume_uploaded_at?: string | null;
};

export type Profile = {
  headline?: string | null;
  bio?: string | null;
  experience_level: string;
  skills: string[];
  technologies: string[];
  desired_roles: string[];
  location_preference?: string | null;
  remote_preference: string;
  cities: string[];
  pakistan_friendly: boolean;
};

export type User = {
  id: number;
  email: string;
  full_name?: string | null;
  profile?: Profile | null;
  onboarding?: OnboardingStatus | null;
};

export type TokenResponse = {
  access_token: string;
  token_type: string;
};

export type ApplicationStatus = "saved" | "applied" | "interview" | "offer" | "rejected";

export type SavedJob = {
  id: number;
  job_id: number;
  notes?: string | null;
  status: ApplicationStatus;
  created_at?: string;
  job_title?: string | null;
  company_name?: string | null;
  apply_url?: string | null;
};

export type Notification = {
  id: number;
  title: string;
  body?: string | null;
  link?: string | null;
  is_read: boolean;
  created_at: string;
};

export type FitBrief = {
  job_id: number;
  score: number;
  breakdown: MatchBreakdown;
  verdict: "apply" | "maybe" | "skip" | string;
  narrative: string;
  tips: string[];
  provider: string;
  apply_url?: string | null;
  career_page_url?: string | null;
};

export type SavedSearch = {
  id: number;
  name: string;
  query_params: Record<string, unknown>;
  is_active: boolean;
  last_checked_at?: string | null;
  last_notified_at?: string | null;
  created_at: string;
};

export type SavedSearchRun = {
  search: SavedSearch;
  matched: number;
  notified: number;
  results: Job[];
};

export type IngestHealth = {
  freshness_days: number;
  inventory: {
    total_jobs: number;
    active_jobs: number;
    fresh_jobs: number;
    embedded_jobs: number;
    active_sources: number;
    indexed_companies: number;
  };
  companies: {
    enabled_companies: number;
    pk_companies: number;
    ats_integrations: number;
  };
  sources: Array<{
    source: string;
    last_run: string | null;
    last_fetched: number | null;
    had_errors_24h: boolean | null;
  }>;
};

export type JobSearchParams = {
  q?: string;
  workplace?: string;
  city?: string;
  pakistan_friendly?: boolean;
  skills?: string;
  career_stage?: string;
  source?: string;
  country?: string;
  company?: string;
  employment_type?: string;
  posted_within?: number;
  hybrid?: boolean;
  sort?: string;
  page?: number;
  page_size?: number;
};

export type ResumeParseResponse = {
  skills: string[];
  technologies: string[];
  experience_level: string;
  summary: string;
  raw_chars: number;
  seed_skills?: string[];
  onboarding?: OnboardingStatus | null;
};
