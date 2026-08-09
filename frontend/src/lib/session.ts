/** Client-side session token for cross-origin API calls (Vercel domain → Render API). */

const TOKEN_KEY = "remote_atlas_access_token";

export function getAccessToken(): string | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setAccessToken(token: string | null | undefined): void {
  if (typeof window === "undefined") return;
  try {
    if (token) {
      window.localStorage.setItem(TOKEN_KEY, token);
    } else {
      window.localStorage.removeItem(TOKEN_KEY);
    }
  } catch {
    /* private mode / storage blocked */
  }
}

export function clearAccessToken(): void {
  setAccessToken(null);
}
