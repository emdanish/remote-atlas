"use client";

import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { Save, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { Alert } from "@/components/ui/Alert";
import { EmptyState } from "@/components/ui/EmptyState";
import { WorkspaceNav } from "@/components/workspace/WorkspaceNav";
import { TrackedApplyButton } from "@/components/jobs/TrackedApplyButton";
import {
  deleteSaved,
  listSaved,
  updateApplication,
  type ApplicationStatus,
  type SavedJob,
} from "@/lib/api";
import { formatApiError } from "@/lib/apiError";
import { useRequireAuth } from "@/lib/auth";
import { formatRelativeDate, titleCase } from "@/lib/utils";

const statuses: ApplicationStatus[] = [
  "saved",
  "applied",
  "interview",
  "offer",
  "rejected",
  "ghosted",
];

const statusTone: Record<ApplicationStatus, "neutral" | "accent" | "success" | "warn"> = {
  saved: "neutral",
  applied: "accent",
  interview: "warn",
  offer: "success",
  rejected: "neutral",
  ghosted: "warn",
};

export default function SavedPage() {
  const { loading, user } = useRequireAuth();
  const queryClient = useQueryClient();
  const [noteDrafts, setNoteDrafts] = useState<Record<number, string>>({});
  const [statusFilter, setStatusFilter] = useState<"all" | ApplicationStatus>("all");
  const [confirmRemove, setConfirmRemove] = useState<number | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const savedQuery = useQuery({
    queryKey: ["saved", user?.id],
    enabled: Boolean(user),
    queryFn: listSaved,
    // Keep list in sync after SaveJobButton / Apply updates elsewhere in the app
    staleTime: 0,
    refetchOnMount: "always",
  });

  useEffect(() => {
    if (!savedQuery.data) return;
    setNoteDrafts((current) => {
      const next = { ...current };
      for (const item of savedQuery.data) {
        if (!(item.id in next)) next[item.id] = item.notes || "";
      }
      return next;
    });
  }, [savedQuery.data]);

  const updateMutation = useMutation({
    mutationFn: ({
      id,
      status,
      notes,
    }: {
      id: number;
      status: ApplicationStatus;
      notes?: string;
    }) => updateApplication(id, status, notes),
    onSuccess: (updated) => {
      queryClient.setQueryData<SavedJob[]>(["saved", user?.id], (current) =>
        current?.map((item) =>
          item.id === updated.id
            ? { ...item, status: updated.status, notes: updated.notes }
            : item,
        ),
      );
      setMessage("Saved job updated.");
      setError(null);
    },
    onError: (err) => {
      setMessage(null);
      setError(formatApiError(err, "Could not update saved job."));
    },
  });

  const removeMutation = useMutation({
    mutationFn: deleteSaved,
    onSuccess: (_, removedId) => {
      queryClient.setQueryData<SavedJob[]>(["saved", user?.id], (current) =>
        current?.filter((item) => item.id !== removedId),
      );
      setConfirmRemove(null);
      setMessage("Job removed from your workspace.");
      setError(null);
    },
    onError: (err) => {
      setMessage(null);
      setError(formatApiError(err, "Could not remove job."));
    },
  });

  const counts = useMemo(() => {
    const result: Record<ApplicationStatus, number> = {
      saved: 0,
      applied: 0,
      interview: 0,
      offer: 0,
      rejected: 0,
      ghosted: 0,
    };
    for (const item of savedQuery.data || []) result[item.status] += 1;
    return result;
  }, [savedQuery.data]);

  const visibleItems = useMemo(
    () =>
      statusFilter === "all"
        ? savedQuery.data || []
        : (savedQuery.data || []).filter((item) => item.status === statusFilter),
    [savedQuery.data, statusFilter],
  );

  if (loading || !user) {
    return <div className="mx-auto max-w-5xl px-4 py-16 text-sm text-muted">Loading…</div>;
  }

  return (
    <div className="mx-auto max-w-5xl px-4 py-10 sm:px-6">
      <h1 className="font-display text-3xl font-semibold text-ink">Saved jobs</h1>
      <p className="mt-2 text-sm text-muted">
        Keep notes, track progress, and continue to the employer&apos;s official application page.
      </p>
      <WorkspaceNav />

      <section className="mt-8 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6" aria-label="Application summary">
        {statuses.map((status) => (
          <button
            type="button"
            key={status}
            onClick={() => setStatusFilter(statusFilter === status ? "all" : status)}
            aria-pressed={statusFilter === status}
            className={`rounded-xl border p-3 text-left transition ${
              statusFilter === status
                ? "border-accent bg-accent-soft"
                : "border-line bg-elevated hover:border-ink/20"
            }`}
          >
            <span className="block text-2xl font-semibold text-ink">{counts[status]}</span>
            <span className="text-xs text-muted">{titleCase(status)}</span>
          </button>
        ))}
      </section>

      <div className="mt-6 flex items-center justify-between gap-4">
        <p className="text-sm text-muted" role="status" aria-live="polite">
          {savedQuery.isLoading
            ? "Loading saved jobs…"
            : `${visibleItems.length} ${visibleItems.length === 1 ? "role" : "roles"}${
                statusFilter === "all" ? " in your workspace" : ` marked ${statusFilter}`
              }`}
        </p>
        {statusFilter !== "all" ? (
          <Button type="button" variant="ghost" size="sm" onClick={() => setStatusFilter("all")}>
            Show all
          </Button>
        ) : null}
      </div>

      {savedQuery.error ? (
        <Alert tone="error" title="Couldn’t load saved jobs" className="mt-4">
          {formatApiError(savedQuery.error)}
        </Alert>
      ) : null}
      {error ? (
        <Alert tone="error" className="mt-3" title="Action failed" onDismiss={() => setError(null)}>
          {error}
        </Alert>
      ) : null}
      {message ? (
        <Alert tone="success" className="mt-3" onDismiss={() => setMessage(null)}>
          {message}
        </Alert>
      ) : null}

      {!savedQuery.isLoading && savedQuery.data?.length === 0 ? (
        <EmptyState
          className="mt-8"
          title="Your saved jobs will appear here"
          description="Save a role from search or a job page, then track Saved → Applied → Interview → Offer."
          actions={[{ href: "/jobs", label: "Browse jobs" }]}
        />
      ) : null}

      {!savedQuery.isLoading && savedQuery.data?.length && visibleItems.length === 0 ? (
        <EmptyState
          className="mt-8"
          title="No jobs with this status"
          description="Switch the filter above or move a saved role into this stage."
          actions={[{ label: "Show all", onClick: () => setStatusFilter("all"), variant: "secondary" }]}
        />
      ) : null}

      <ul className="mt-6 space-y-4">
        {visibleItems.map((item) => {
          const draft = noteDrafts[item.id] ?? "";
          const updatingThis = updateMutation.isPending && updateMutation.variables?.id === item.id;
          const removingThis = removeMutation.isPending && removeMutation.variables === item.id;
          return (
            <li key={item.id} className="rounded-xl border border-line bg-elevated p-5 shadow-soft">
              <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge tone={statusTone[item.status]}>{titleCase(item.status)}</Badge>
                    {item.created_at ? (
                      <span className="text-xs text-muted">Saved {formatRelativeDate(item.created_at)}</span>
                    ) : null}
                  </div>
                  <h2 className="mt-2 font-display text-xl font-semibold text-ink">
                    {item.job_id ? (
                      <Link href={`/jobs/${item.job_id}`} className="hover:text-accent">
                        {item.job_title || `Job #${item.job_id}`}
                      </Link>
                    ) : (
                      item.job_title || "Listing removed from index"
                    )}
                  </h2>
                  <p className="mt-1 text-sm text-muted">{item.company_name}</p>
                  {item.listing_gone ? (
                    <p className="mt-1 text-xs text-muted">
                      Original listing left the freshness window. Tracker kept from your snapshot.
                    </p>
                  ) : null}
                  {item.applied_at ? (
                    <p className="mt-1 text-xs text-muted">
                      Applied {formatRelativeDate(item.applied_at)}
                      {item.follow_up_on ? ` · follow up ${formatRelativeDate(item.follow_up_on)}` : ""}
                    </p>
                  ) : null}
                </div>
                <div className="flex flex-wrap gap-2">
                  {item.apply_url && item.job_id ? (
                    <TrackedApplyButton
                      jobId={item.job_id}
                      applyUrl={item.apply_url}
                      companyName={item.company_name || undefined}
                      size="sm"
                    />
                  ) : item.apply_url ? (
                    <Button href={item.apply_url} external size="sm">
                      Open apply URL
                    </Button>
                  ) : null}
                  <select
                    className="h-9 rounded-md border border-line bg-elevated px-2 text-sm"
                    value={item.status}
                    disabled={updatingThis || removingThis}
                    onChange={(event) => {
                      setMessage(null);
                      updateMutation.mutate({
                        id: item.id,
                        status: event.target.value as ApplicationStatus,
                      });
                    }}
                    aria-label={`Application status for ${item.job_title || `job ${item.job_id}`}`}
                  >
                    {statuses.map((status) => (
                      <option key={status} value={status}>{titleCase(status)}</option>
                    ))}
                  </select>
                </div>
              </div>

              <div className="mt-5 border-t border-line pt-4">
                <label className="text-sm font-medium text-ink" htmlFor={`notes-${item.id}`}>
                  Private notes
                </label>
                <textarea
                  id={`notes-${item.id}`}
                  value={draft}
                  maxLength={5000}
                  onChange={(event) =>
                    setNoteDrafts((current) => ({ ...current, [item.id]: event.target.value }))
                  }
                  placeholder="e.g. Interview on Tue 3pm · recruiting via Greenhouse · ask about salary band"
                  className="mt-2 min-h-24 w-full rounded-lg border border-line bg-paper px-3 py-2 text-sm text-ink shadow-inner outline-none focus:border-accent"
                />
                <div className="mt-2 flex flex-wrap items-center justify-between gap-3">
                  <span className="text-xs text-muted">{draft.length.toLocaleString()} / 5,000</span>
                  <div className="flex gap-2">
                    {confirmRemove === item.id ? (
                      <Button type="button" variant="ghost" size="sm" onClick={() => setConfirmRemove(null)}>
                        Cancel
                      </Button>
                    ) : null}
                    <Button
                      type="button"
                      variant={confirmRemove === item.id ? "danger" : "ghost"}
                      size="sm"
                      disabled={removingThis || updatingThis}
                      onClick={() => {
                        if (confirmRemove === item.id) removeMutation.mutate(item.id);
                        else setConfirmRemove(item.id);
                      }}
                    >
                      <Trash2 className="h-4 w-4" aria-hidden />
                      {removingThis
                        ? "Removing…"
                        : confirmRemove === item.id
                          ? "Confirm remove"
                          : "Remove"}
                    </Button>
                    <Button
                      type="button"
                      variant="secondary"
                      size="sm"
                      disabled={updatingThis || draft === (item.notes || "")}
                      onClick={() => {
                        setMessage(null);
                        updateMutation.mutate({ id: item.id, status: item.status, notes: draft });
                      }}
                    >
                      <Save className="h-4 w-4" aria-hidden />
                      {updatingThis ? "Saving…" : "Save notes"}
                    </Button>
                  </div>
                </div>
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
