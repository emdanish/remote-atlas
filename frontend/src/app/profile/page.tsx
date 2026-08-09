"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { WorkspaceNav } from "@/components/workspace/WorkspaceNav";
import { updateProfile, type Profile } from "@/lib/api";
import { formatApiError } from "@/lib/apiError";
import { useRequireAuth } from "@/lib/auth";

const MAX_SKILL_ITEMS = 120;
const MAX_ROLE_ITEMS = 30;
const MAX_CITY_ITEMS = 30;

function splitList(raw: string): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const part of raw.split(",")) {
    const v = part.trim();
    if (!v) continue;
    const key = v.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(v);
  }
  return out;
}

export default function ProfilePage() {
  const { user, loading, refresh } = useRequireAuth();
  const [form, setForm] = useState<Partial<Profile>>({});
  const [skills, setSkills] = useState("");
  const [tech, setTech] = useState("");
  const [desiredRoles, setDesiredRoles] = useState("");
  const [cities, setCities] = useState("");
  const [success, setSuccess] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!user?.profile) return;
    setForm(user.profile);
    setSkills((user.profile.skills || []).join(", "));
    setTech((user.profile.technologies || []).join(", "));
    setDesiredRoles((user.profile.desired_roles || []).join(", "));
    setCities((user.profile.cities || []).join(", "));
  }, [user]);

  const skillCount = useMemo(() => splitList(skills).length, [skills]);
  const techCount = useMemo(() => splitList(tech).length, [tech]);
  const roleCount = useMemo(() => splitList(desiredRoles).length, [desiredRoles]);
  const cityCount = useMemo(() => splitList(cities).length, [cities]);

  if (loading || !user) {
    return (
      <div className="mx-auto max-w-2xl px-4 py-16 text-sm text-muted">Loading profile…</div>
    );
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setSaving(true);
    setSuccess(null);
    setError(null);

    const skillItems = splitList(skills);
    const techItems = splitList(tech);
    const roleItems = splitList(desiredRoles);
    const cityItems = splitList(cities);

    if (skillItems.length > MAX_SKILL_ITEMS || techItems.length > MAX_SKILL_ITEMS) {
      setError(
        `Skills and technologies allow at most ${MAX_SKILL_ITEMS} items each. You have ${skillItems.length} skills and ${techItems.length} technologies — merge duplicates or keep the ones you use most.`,
      );
      setSaving(false);
      return;
    }
    if (roleItems.length > MAX_ROLE_ITEMS) {
      setError(`Desired roles: at most ${MAX_ROLE_ITEMS} items (you have ${roleItems.length}).`);
      setSaving(false);
      return;
    }
    if (cityItems.length > MAX_CITY_ITEMS) {
      setError(`Cities: at most ${MAX_CITY_ITEMS} items (you have ${cityItems.length}).`);
      setSaving(false);
      return;
    }

    try {
      await updateProfile({
        ...form,
        skills: skillItems,
        technologies: techItems,
        desired_roles: roleItems,
        cities: cityItems,
      });
      await refresh();
      setSuccess("Profile saved. Matches will use your updated preferences.");
    } catch (err) {
      setError(formatApiError(err, "Could not save profile."));
    } finally {
      setSaving(false);
    }
  }

  const completionChecks = [
    Boolean(form.headline?.trim()),
    skillCount > 0,
    techCount > 0,
    roleCount > 0,
    Boolean(form.location_preference?.trim()),
    form.remote_preference === "remote" || cityCount > 0,
  ];
  const completion = Math.round(
    (completionChecks.filter(Boolean).length / completionChecks.length) * 100,
  );

  return (
    <div className="mx-auto max-w-2xl px-4 py-10 sm:px-6">
      <h1 className="font-display text-3xl font-semibold text-ink">Profile</h1>
      <p className="mt-2 text-sm text-muted">
        Preferences power matches and Fit Briefs. Signed in as {user.email}.
      </p>
      <WorkspaceNav />
      <div
        className="mt-6 rounded-xl border border-line bg-elevated p-4 shadow-soft"
        aria-label={`Profile ${completion}% complete`}
      >
        <div className="flex items-center justify-between gap-4 text-sm">
          <span className="font-medium text-ink">Profile completeness</span>
          <span className="font-semibold text-accent">{completion}%</span>
        </div>
        <div className="mt-2 h-2 overflow-hidden rounded-full bg-line">
          <div
            className="h-full rounded-full bg-accent transition-[width]"
            style={{ width: `${completion}%` }}
          />
        </div>
        <p className="mt-2 text-xs leading-5 text-muted">
          Complete profiles produce more focused recommendations. Jobs search stays unfiltered by
          default so you explore freely.
        </p>
      </div>
      <form
        onSubmit={onSubmit}
        className="mt-8 space-y-4 rounded-xl border border-line bg-elevated p-6 shadow-soft"
      >
        <label className="block text-sm">
          <span className="mb-1.5 block font-medium">Headline</span>
          <Input
            value={form.headline || ""}
            onChange={(e) => setForm({ ...form, headline: e.target.value })}
            placeholder="e.g. Junior backend engineer · Python & FastAPI"
            maxLength={512}
          />
        </label>
        <label className="block text-sm">
          <span className="mb-1.5 block font-medium">Bio</span>
          <textarea
            className="min-h-28 w-full rounded-md border border-line bg-elevated px-3 py-2 shadow-soft outline-none focus-visible:border-accent focus-visible:ring-2 focus-visible:ring-accent/20"
            value={form.bio || ""}
            onChange={(e) => setForm({ ...form, bio: e.target.value })}
            maxLength={5000}
            placeholder="e.g. Full-stack developer with 2 years building remote SaaS products. Strong in Python, React, and distributed systems."
          />
        </label>
        <div className="grid gap-4 sm:grid-cols-2">
          <label className="block text-sm">
            <span className="mb-1.5 block font-medium">Experience</span>
            <select
              className="h-11 w-full rounded-md border border-line bg-elevated px-3 outline-none focus-visible:border-accent"
              value={form.experience_level || "junior"}
              onChange={(e) => setForm({ ...form, experience_level: e.target.value })}
            >
              <option value="internship">Internship</option>
              <option value="junior">Junior</option>
              <option value="mid">Mid</option>
              <option value="senior">Senior</option>
            </select>
          </label>
          <label className="block text-sm">
            <span className="mb-1.5 block font-medium">Remote preference</span>
            <select
              className="h-11 w-full rounded-md border border-line bg-elevated px-3 outline-none focus-visible:border-accent"
              value={form.remote_preference || "remote"}
              onChange={(e) => setForm({ ...form, remote_preference: e.target.value })}
            >
              <option value="remote">Remote</option>
              <option value="hybrid">Hybrid</option>
              <option value="onsite">On-site</option>
              <option value="any">Any</option>
            </select>
          </label>
        </div>
        <label className="block text-sm">
          <span className="mb-1.5 block font-medium">
            Desired roles{" "}
            <span className="font-normal text-muted">
              ({roleCount}/{MAX_ROLE_ITEMS})
            </span>
          </span>
          <Input
            value={desiredRoles}
            onChange={(e) => setDesiredRoles(e.target.value)}
            placeholder="e.g. Backend Engineer, Python Developer, Full-stack"
          />
          <span className="mt-1.5 block text-xs leading-5 text-muted">
            Comma-separated job titles. Your first role is the main match target.
          </span>
        </label>
        <label className="block text-sm">
          <span className="mb-1.5 block font-medium">Location preference</span>
          <Input
            value={form.location_preference || ""}
            onChange={(e) => setForm({ ...form, location_preference: e.target.value })}
            placeholder="e.g. Pakistan · Worldwide remote · UTC+5 friendly"
            maxLength={255}
          />
        </label>
        <label className="block text-sm">
          <span className="mb-1.5 block font-medium">
            Preferred cities{" "}
            <span className="font-normal text-muted">
              ({cityCount}/{MAX_CITY_ITEMS})
            </span>
          </span>
          <Input
            value={cities}
            onChange={(e) => setCities(e.target.value)}
            placeholder="e.g. Lahore, Islamabad, Karachi (comma-separated)"
          />
        </label>
        <label className="block text-sm">
          <span className="mb-1.5 flex flex-wrap items-center justify-between gap-2 font-medium">
            <span>
              Skills{" "}
              <span className="font-normal text-muted">
                ({skillCount}/{MAX_SKILL_ITEMS})
              </span>
            </span>
          </span>
          <textarea
            className="min-h-24 w-full rounded-md border border-line bg-elevated px-3 py-2 text-sm shadow-soft outline-none focus-visible:border-accent focus-visible:ring-2 focus-visible:ring-accent/20"
            value={skills}
            onChange={(e) => setSkills(e.target.value)}
            placeholder="e.g. python, fastapi, system design, api design, communication (comma-separated)"
          />
          <span className="mt-1.5 block text-xs leading-5 text-muted">
            Comma-separated. Duplicates are removed on save.
          </span>
        </label>
        <label className="block text-sm">
          <span className="mb-1.5 block font-medium">
            Technologies{" "}
            <span className="font-normal text-muted">
              ({techCount}/{MAX_SKILL_ITEMS})
            </span>
          </span>
          <textarea
            className="min-h-24 w-full rounded-md border border-line bg-elevated px-3 py-2 text-sm shadow-soft outline-none focus-visible:border-accent focus-visible:ring-2 focus-visible:ring-accent/20"
            value={tech}
            onChange={(e) => setTech(e.target.value)}
            placeholder="e.g. typescript, react, postgresql, docker, next.js (comma-separated stack)"
          />
        </label>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={form.pakistan_friendly ?? true}
            onChange={(e) => setForm({ ...form, pakistan_friendly: e.target.checked })}
            className="accent-accent"
          />
          Prefer Pakistan-friendly remote roles
        </label>

        {error ? (
          <Alert tone="error" title="Couldn’t save" onDismiss={() => setError(null)}>
            {error}
          </Alert>
        ) : null}
        {success ? (
          <Alert tone="success" title="Saved" onDismiss={() => setSuccess(null)}>
            {success}
          </Alert>
        ) : null}

        <Button type="submit" disabled={saving}>
          {saving ? "Saving…" : "Save profile"}
        </Button>
      </form>
    </div>
  );
}
