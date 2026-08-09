"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useMemo, useState } from "react";
import { Bell, Play, Plus, Trash2 } from "lucide-react";
import { JobCard } from "@/components/jobs/JobCard";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { Input } from "@/components/ui/Input";
import { WorkspaceNav } from "@/components/workspace/WorkspaceNav";
import {
  createSavedSearch,
  deleteSavedSearch,
  listSavedSearches,
  runSavedSearch,
  updateSavedSearch,
} from "@/lib/api";
import { formatApiError } from "@/lib/apiError";
import { useRequireAuth } from "@/lib/auth";
import { formatRelativeDate } from "@/lib/utils";

function AlertsInner() {
  const { user, loading } = useRequireAuth();
  const qc = useQueryClient();
  const sp = useSearchParams();
  const [name, setName] = useState("Remote + my stack");
  const [q, setQ] = useState("");
  const [skills, setSkills] = useState("");
  const [pakistan, setPakistan] = useState(true);
  const [runPreview, setRunPreview] = useState<Awaited<ReturnType<typeof runSavedSearch>> | null>(
    null,
  );
  const [formError, setFormError] = useState<string | null>(null);
  const [runError, setRunError] = useState<string | null>(null);
  const [deleteId, setDeleteId] = useState<number | null>(null);

  useEffect(() => {
    const q0 = sp.get("q");
    const skills0 = sp.get("skills");
    if (q0) setQ(q0);
    if (skills0) setSkills(skills0);
  }, [sp]);

  const profileSkills = useMemo(() => {
    const p = user?.profile;
    if (!p) return "";
    return [...(p.technologies || []), ...(p.skills || [])].slice(0, 5).join(", ");
  }, [user]);

  const searches = useQuery({
    queryKey: ["saved-searches", user?.id],
    enabled: Boolean(user),
    queryFn: listSavedSearches,
    staleTime: 15_000,
  });

  const createMut = useMutation({
    mutationFn: createSavedSearch,
    onSuccess: () => {
      setFormError(null);
      void qc.invalidateQueries({ queryKey: ["saved-searches"] });
    },
    onError: (e) => setFormError(formatApiError(e, "Could not save pulse.")),
  });

  const deleteMut = useMutation({
    mutationFn: deleteSavedSearch,
    onSuccess: () => {
      setDeleteId(null);
      void qc.invalidateQueries({ queryKey: ["saved-searches"] });
    },
  });

  const runMut = useMutation({
    mutationFn: runSavedSearch,
    onSuccess: (data) => {
      setRunError(null);
      setRunPreview(data);
      void qc.invalidateQueries({ queryKey: ["saved-searches"] });
      void qc.invalidateQueries({ queryKey: ["notifications"] });
    },
    onError: (e) => setRunError(formatApiError(e, "Pulse run failed.")),
  });

  const toggleMut = useMutation({
    mutationFn: ({ id, is_active }: { id: number; is_active: boolean }) =>
      updateSavedSearch(id, { is_active }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["saved-searches"] }),
  });

  if (loading || !user) {
    return <div className="mx-auto max-w-4xl px-4 py-16 text-sm text-muted">Loading…</div>;
  }

  return (
    <div className="mx-auto max-w-4xl px-4 py-10 sm:px-6">
      <div className="flex items-start gap-3">
        <Bell className="mt-1 h-6 w-6 text-accent" aria-hidden />
        <div>
          <h1 className="font-display text-3xl font-semibold text-ink">Atlas Pulse</h1>
          <p className="mt-2 max-w-2xl text-sm text-muted">
            Saved catalogue watches. After each ingest cycle (or when you press Run), we drop
            in-app notifications for new matching roles — no email required on this tier.
          </p>
        </div>
      </div>
      <WorkspaceNav />

      <form
        className="mt-8 space-y-4 rounded-xl border border-line bg-elevated p-5 shadow-soft"
        onSubmit={(e) => {
          e.preventDefault();
          const skillCsv = skills.trim() || profileSkills;
          createMut.mutate({
            name: name.trim() || "Untitled pulse",
            query_params: {
              q: q.trim() || undefined,
              skills: skillCsv || undefined,
              workplace: "remote",
              posted_within: 7,
              pakistan_friendly: pakistan,
            },
            is_active: true,
          });
        }}
      >
        <h2 className="text-sm font-semibold text-ink">Create a pulse</h2>
        <div className="grid gap-3 sm:grid-cols-2">
          <label className="block text-sm">
            <span className="mb-1.5 block font-medium text-ink">Name</span>
            <Input value={name} onChange={(e) => setName(e.target.value)} required maxLength={160} placeholder="e.g. Remote Python · PK friendly" />
          </label>
          <label className="block text-sm">
            <span className="mb-1.5 block font-medium text-ink">Keywords (optional)</span>
            <Input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="e.g. staff engineer, platform, or backend"
            />
          </label>
          <label className="block text-sm sm:col-span-2">
            <span className="mb-1.5 block font-medium text-ink">Technologies</span>
            <Input
              value={skills}
              onChange={(e) => setSkills(e.target.value)}
              placeholder={
                profileSkills
                  ? `e.g. ${profileSkills} — or leave blank to use these`
                  : "e.g. react, typescript, node.js (comma-separated)"
              }
            />
            <span className="mt-1 block text-xs text-muted">
              Leave empty to use top skills from your profile.
            </span>
          </label>
        </div>
        <label className="flex items-center gap-2 text-sm text-ink">
          <input
            type="checkbox"
            checked={pakistan}
            onChange={(e) => setPakistan(e.target.checked)}
            className="h-4 w-4 accent-accent"
          />
          Prefer Pakistan-friendly remote
        </label>
        {formError ? (
          <Alert tone="error" title="Couldn’t save pulse" onDismiss={() => setFormError(null)}>
            {formError}
          </Alert>
        ) : null}
        <Button type="submit" disabled={createMut.isPending}>
          <Plus className="h-4 w-4" aria-hidden />
          {createMut.isPending ? "Saving…" : "Save pulse"}
        </Button>
      </form>

      <section className="mt-10">
        <h2 className="font-semibold text-ink">Your pulses</h2>
        {searches.isLoading ? <p className="mt-3 text-sm text-muted">Loading…</p> : null}
        {searches.isError ? (
          <Alert tone="error" title="Couldn’t load pulses" className="mt-3">
            {formatApiError(searches.error)}
          </Alert>
        ) : null}
        {runError ? (
          <Alert tone="error" title="Run failed" className="mt-3" onDismiss={() => setRunError(null)}>
            {runError}
          </Alert>
        ) : null}
        {searches.data?.length === 0 ? (
          <p className="mt-3 text-sm text-muted">No pulses yet — create one above.</p>
        ) : null}
        <ul className="mt-4 space-y-3">
          {searches.data?.map((s) => (
            <li
              key={s.id}
              className="flex flex-col gap-3 rounded-xl border border-line bg-elevated p-4 sm:flex-row sm:items-center sm:justify-between"
            >
              <div className="min-w-0">
                <p className="font-medium text-ink">
                  {s.name}{" "}
                  <span className="text-xs font-normal text-muted">
                    {s.is_active ? "· active" : "· paused"}
                  </span>
                </p>
                <p className="mt-0.5 truncate text-xs text-muted">
                  {JSON.stringify(s.query_params)}
                </p>
                <p className="mt-1 text-xs text-muted">
                  Last check{" "}
                  {s.last_checked_at ? formatRelativeDate(s.last_checked_at) : "never"}
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                <Button
                  size="sm"
                  variant="secondary"
                  disabled={runMut.isPending}
                  onClick={() => runMut.mutate(s.id)}
                >
                  <Play className="h-3.5 w-3.5" aria-hidden />
                  Run
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => toggleMut.mutate({ id: s.id, is_active: !s.is_active })}
                >
                  {s.is_active ? "Pause" : "Resume"}
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => setDeleteId(s.id)}
                >
                  <Trash2 className="h-3.5 w-3.5" aria-hidden />
                </Button>
              </div>
            </li>
          ))}
        </ul>
      </section>

      <ConfirmDialog
        open={deleteId != null}
        title="Delete this pulse?"
        description="You can create a new pulse anytime. Existing notifications stay in Matches."
        confirmLabel="Delete"
        destructive
        busy={deleteMut.isPending}
        onCancel={() => setDeleteId(null)}
        onConfirm={() => {
          if (deleteId != null) deleteMut.mutate(deleteId);
        }}
      />

      {runPreview ? (
        <section className="mt-10">
          <h2 className="font-semibold text-ink">
            Last run · {runPreview.matched} matched · {runPreview.notified} new notifies
          </h2>
          <div className="mt-4 space-y-3">
            {runPreview.results.map((job, i) => (
              <JobCard key={job.id} job={job} index={i} />
            ))}
            {runPreview.results.length === 0 ? (
              <p className="text-sm text-muted">No roles matched this pulse right now.</p>
            ) : null}
          </div>
        </section>
      ) : null}
    </div>
  );
}

export default function AlertsPage() {
  return (
    <Suspense fallback={<div className="mx-auto max-w-4xl px-4 py-16 text-sm text-muted">Loading…</div>}>
      <AlertsInner />
    </Suspense>
  );
}
