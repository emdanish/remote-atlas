import { ApiError, apiFetch } from "./client";
import type { Profile, TokenResponse, User } from "./types";

export async function register(
  email: string,
  password: string,
  full_name?: string,
  experience_level?: string,
): Promise<TokenResponse> {
  return apiFetch<TokenResponse>("/auth/register", {
    method: "POST",
    body: JSON.stringify({ email, password, full_name, experience_level }),
  });
}

export async function login(email: string, password: string): Promise<TokenResponse> {
  return apiFetch<TokenResponse>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

export async function getMe(): Promise<User | null> {
  try {
    return await apiFetch<User>("/auth/me");
  } catch (err) {
    if (err instanceof ApiError && err.status === 401) return null;
    throw err;
  }
}

export async function updateProfile(
  profile: Partial<Profile>,
): Promise<Profile> {
  return apiFetch<Profile>("/auth/me/profile", {
    method: "PUT",
    body: JSON.stringify(profile),
  });
}

export async function logout(): Promise<void> {
  await apiFetch<void>("/auth/logout", { method: "POST" });
}
