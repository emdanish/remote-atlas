"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { FormEvent, Suspense, useState } from "react";
import { Logo } from "@/components/brand/Logo";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { login } from "@/lib/api";
import { formatApiError } from "@/lib/apiError";
import { useAuth } from "@/lib/auth";

function LoginForm() {
  const { refresh } = useAuth();
  const router = useRouter();
  const search = useSearchParams();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await login(email, password);
      await refresh();
      const nextRaw = search.get("next") || "";
      let dest = nextRaw || "/jobs";
      try {
        const { getMe } = await import("@/lib/api");
        const user = await getMe();
        if (
          (!nextRaw || nextRaw === "/jobs") &&
          user.onboarding &&
          !user.onboarding.onboarding_complete
        ) {
          dest = "/onboarding";
        }
      } catch {
        /* keep dest */
      }
      router.push(dest);
    } catch (err) {
      setError(formatApiError(err, "Login failed"));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="relative mx-auto flex min-h-[70vh] max-w-md flex-col justify-center px-4 py-16">
      <div className="pointer-events-none absolute inset-x-0 top-8 -z-10 mx-auto h-40 max-w-sm rounded-full bg-accent/8 blur-3xl" aria-hidden />
      <Logo href="/" size="sm" className="mb-8 justify-center" />
      <h1 className="text-center font-display text-3xl font-semibold tracking-tight text-ink">
        Welcome back
      </h1>
      <p className="mt-2 text-center text-sm text-muted">
        Sign in to save roles, track applications, and get matches.
      </p>
      <form
        onSubmit={onSubmit}
        className="mt-8 space-y-4 rounded-xl border border-line bg-elevated p-6 shadow-soft sm:p-7"
      >
        <label className="block text-sm">
          <span className="mb-1.5 block font-medium">Email</span>
          <Input
            type="email"
            required
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="e.g. you@example.com"
          />
        </label>
        <label className="block text-sm">
          <span className="mb-1.5 block font-medium">Password</span>
          <Input
            type="password"
            required
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="Your account password"
          />
        </label>
        {error ? (
          <Alert tone="error" title="Sign-in failed" onDismiss={() => setError(null)}>
            {error}
          </Alert>
        ) : null}
        <Button type="submit" className="w-full" disabled={loading}>
          {loading ? "Signing in…" : "Sign in"}
        </Button>
      </form>
      <p className="mt-6 text-center text-sm text-muted">
        No account?{" "}
        <Link href="/register" className="font-medium text-accent hover:underline">
          Create one
        </Link>
      </p>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense>
      <LoginForm />
    </Suspense>
  );
}
