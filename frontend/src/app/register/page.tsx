"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";
import { Logo } from "@/components/brand/Logo";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { register } from "@/lib/api";
import { formatApiError } from "@/lib/apiError";
import { useAuth } from "@/lib/auth";

export default function RegisterPage() {
  const { refresh } = useAuth();
  const router = useRouter();
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await register(email, password, fullName || undefined);
      await refresh();
      router.push("/onboarding");
    } catch (err) {
      setError(formatApiError(err, "Registration failed"));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mx-auto flex min-h-[70vh] max-w-md flex-col justify-center px-4 py-16">
      <Logo href="/" size="sm" className="mb-8 justify-center" />
      <h1 className="text-center font-display text-3xl font-semibold text-ink">Create account</h1>
      <p className="mt-2 text-center text-sm text-muted">
        Save jobs, track applications, and personalize recommendations.
      </p>
      <form onSubmit={onSubmit} className="mt-8 space-y-4 rounded-xl border border-line bg-elevated p-6 shadow-soft">
        <label className="block text-sm">
          <span className="mb-1.5 block font-medium">Full name</span>
          <Input
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
            autoComplete="name"
            placeholder="e.g. Ahmed Khan"
          />
        </label>
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
            minLength={8}
            autoComplete="new-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="At least 8 characters"
          />
        </label>
        {error ? (
          <Alert tone="error" title="Couldn’t create account" onDismiss={() => setError(null)}>
            {error}
          </Alert>
        ) : null}
        <Button type="submit" className="w-full" disabled={loading}>
          {loading ? "Creating…" : "Create account"}
        </Button>
      </form>
      <p className="mt-6 text-center text-sm text-muted">
        Already have an account?{" "}
        <Link href="/login" className="font-medium text-accent hover:underline">
          Sign in
        </Link>
      </p>
    </div>
  );
}
