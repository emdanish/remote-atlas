import { apiFetch } from "./client";
import type { Profile, TokenResponse, User } from "./types";

export async function register(
  email: string,
  password: string,
  full_name?: string,
): Promise<TokenResponse> {
  return apiFetch<TokenResponse>("/auth/register", {
    method: "POST",
    body: JSON.stringify({ email, password, full_name }),
  });
}

export async function login(email: string, password: string): Promise<TokenResponse> {
  return apiFetch<TokenResponse>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

export async function getMe(): Promise<User> {
  return apiFetch<User>("/auth/me");
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
  return apiFetch<void>("/auth/logout", { method: "POST" });
}
