/** Session helpers for post-onboarding jobs personalization. */
const SEED_KEY = "remote_atlas_seed_skills";
const ONBOARDING_DONE_KEY = "remote_atlas_onboarding_done";

export function storeSeedSkills(skills: string[]): void {
  try {
    const cleaned = skills.map((s) => s.trim()).filter(Boolean).slice(0, 4);
    if (cleaned.length) localStorage.setItem(SEED_KEY, JSON.stringify(cleaned));
  } catch {
    /* ignore */
  }
}

export function consumeSeedSkills(): string[] {
  try {
    const raw = localStorage.getItem(SEED_KEY);
    if (!raw) return [];
    localStorage.removeItem(SEED_KEY);
    const parsed = JSON.parse(raw) as unknown;
    if (!Array.isArray(parsed)) return [];
    return parsed.map(String).filter(Boolean).slice(0, 4);
  } catch {
    return [];
  }
}

export function peekSeedSkills(): string[] {
  try {
    const raw = localStorage.getItem(SEED_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as unknown;
    if (!Array.isArray(parsed)) return [];
    return parsed.map(String).filter(Boolean).slice(0, 4);
  } catch {
    return [];
  }
}

export function markOnboardingDoneLocal(): void {
  try {
    localStorage.setItem(ONBOARDING_DONE_KEY, "1");
  } catch {
    /* ignore */
  }
}

export function isOnboardingDoneLocal(): boolean {
  try {
    return localStorage.getItem(ONBOARDING_DONE_KEY) === "1";
  } catch {
    return false;
  }
}
