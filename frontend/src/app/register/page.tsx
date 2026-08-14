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
  const [experienceLevel, setExperienceLevel] = useState("junior");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await register(email, password, fullName || undefined, experienceLevel);
      await refresh();
      router.push("/onboarding");
    } catch (err) {
      setError(formatApiError(err, "Registration failed"));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="relative mx-auto flex min-h-[70vh] max-w-md flex-col justify-center px-4 py-16">
      <div
        className="pointer-events-none absolute inset-x-0 top-8 -z-10 mx-auto h-40 max-w-sm rounded-full bg-accent/8 blur-3xl"
        aria-hidden
      />
      <Logo href="/" size="sm" className="mb-8 justify-center" />
      <h1 className="text-center font-display text-3xl font-semibold tracking-tight text-ink">
        Create account
      </h1>
      <p className="mt-2 text-center text-sm text-muted">
        Save jobs, track applications, and personalize recommendations.
      </p>
      <form
        onSubmit={onSubmit}
        className="mt-8 space-y-4 rounded-xl border border-line bg-elevated p-6 shadow-soft sm:p-7"
      >
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
        <fieldset className="text-sm">
          <legend className="mb-1.5 font-medium">Where are you in your hunt?</legend>
          <div className="grid gap-2">
            {[
              { value: "internship", label: "Internship" },
              { value: "new_grad", label: "New graduate" },
              { value: "junior", label: "Junior / first IC role" },
            ].map((opt) => (
              <label key={opt.value} className="flex items-center gap-2">
                <input
                  type="radio"
                  name="experience_level"
                  value={opt.value}
                  checked={experienceLevel === opt.value}
                  onChange={() => setExperienceLevel(opt.value)}
                  className="accent-accent"
                />
                {opt.label}
              </label>
            ))}
          </div>
        </fieldset>
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
