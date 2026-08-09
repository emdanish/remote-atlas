"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";
import { JobCard } from "@/components/jobs/JobCard";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import { WorkspaceNav } from "@/components/workspace/WorkspaceNav";
import {
  generateMatchNotifications,
  getRecommendations,
  listNotifications,
  markNotificationRead,
  markNotificationsRead,
  parseResume,
  type Notification,
} from "@/lib/api";
import { formatApiError } from "@/lib/apiError";
import { useRequireAuth } from "@/lib/auth";
import { formatRelativeDate } from "@/lib/utils";

export default function MatchesPage() {
  const { user, loading, refresh } = useRequireAuth();
  const qc = useQueryClient();
  const [resumeMsg, setResumeMsg] = useState<string | null>(null);
  const [resumeError, setResumeError] = useState<string | null>(null);
  const [notifyError, setNotifyError] = useState<string | null>(null);

  const recs = useQuery({
    queryKey: ["recommendations", user?.id],
    enabled: Boolean(user),
    queryFn: () => getRecommendations(),
  });

  const notes = useQuery({
    queryKey: ["notifications", user?.id],
    enabled: Boolean(user),
    queryFn: () => listNotifications(),
  });

  const resumeMutation = useMutation({
    mutationFn: (file: File) => parseResume(file),
    onSuccess: async (data) => {
      setResumeError(null);
      setResumeMsg(
        `Parsed ${data.skills.length} skills · level ${data.experience_level}. Profile updated.`,
      );
      await refresh();
      void qc.invalidateQueries({ queryKey: ["recommendations"] });
    },
    onError: (err) => {
      setResumeMsg(null);
      setResumeError(formatApiError(err, "Could not parse resume."));
    },
  });

  const genNotes = useMutation({
    mutationFn: () => generateMatchNotifications(),
    onSuccess: () => {
      setNotifyError(null);
      void qc.invalidateQueries({ queryKey: ["notifications"] });
    },
    onError: (err) => setNotifyError(formatApiError(err, "Could not create notifications.")),
  });

  const markAllRead = useMutation({
    mutationFn: markNotificationsRead,
    onSuccess: () => {
      qc.setQueryData<Notification[]>(["notifications", user?.id], (current) =>
        current?.map((notification) => ({ ...notification, is_read: true })),
      );
    },
  });

  const markOneRead = useMutation({
    mutationFn: markNotificationRead,
    onSuccess: ({ id }) => {
      qc.setQueryData<Notification[]>(["notifications", user?.id], (current) =>
        current?.map((notification) =>
          notification.id === id ? { ...notification, is_read: true } : notification,
        ),
      );
    },
  });

  const unreadCount = notes.data?.filter((notification) => !notification.is_read).length || 0;

  if (loading || !user) {
    return <div className="mx-auto max-w-4xl px-4 py-16 text-sm text-muted">Loading…</div>;
  }

  return (
    <div className="mx-auto max-w-4xl px-4 py-10 sm:px-6">
      <h1 className="font-display text-3xl font-semibold text-ink">Matches</h1>
      <p className="mt-2 text-sm text-muted">
        Personalized from your profile. Upload a resume to bootstrap skills.
      </p>
      <WorkspaceNav />

      <div className="mt-8 grid gap-4 rounded-xl border border-line bg-elevated p-5 shadow-soft sm:grid-cols-2">
        <div>
          <p className="text-sm font-medium text-ink">Resume parse</p>
          <p className="mt-1 text-xs text-muted">PDF or text, max 2MB.</p>
          <input
            type="file"
            accept=".pdf,.txt,.md"
            className="mt-3 block w-full text-sm"
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) resumeMutation.mutate(file);
            }}
          />
          {resumeMsg ? (
            <Alert tone="success" className="mt-3" onDismiss={() => setResumeMsg(null)}>
              {resumeMsg}
            </Alert>
          ) : null}
          {resumeError ? (
            <Alert tone="error" className="mt-3" title="Resume parse failed" onDismiss={() => setResumeError(null)}>
              {resumeError}
            </Alert>
          ) : null}
        </div>
        <div className="flex flex-col justify-end gap-2">
          <Button
            variant="secondary"
            onClick={() => genNotes.mutate()}
            disabled={genNotes.isPending}
          >
            {genNotes.isPending ? "Generating…" : "Generate match notifications"}
          </Button>
          {notifyError ? (
            <Alert tone="error" title="Notifications" onDismiss={() => setNotifyError(null)}>
              {notifyError}
            </Alert>
          ) : null}
        </div>
      </div>

      {notes.data && notes.data.length > 0 ? (
        <section className="mt-10">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className="font-semibold text-ink">Notifications</h2>
              <p className="mt-1 text-xs text-muted">
                {unreadCount ? `${unreadCount} unread` : "You’re all caught up"}
              </p>
            </div>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              disabled={!unreadCount || markAllRead.isPending}
              onClick={() => markAllRead.mutate()}
            >
              {markAllRead.isPending ? "Marking…" : "Mark all as read"}
            </Button>
          </div>
          <ul className="mt-3 space-y-2">
            {notes.data.slice(0, 8).map((n) => (
              <li
                key={n.id}
                className={`rounded-lg border px-4 py-3 text-sm ${
                  n.is_read ? "border-line bg-paper" : "border-accent/25 bg-accent-soft/40"
                }`}
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      {!n.is_read ? <span className="h-2 w-2 shrink-0 rounded-full bg-accent" aria-label="Unread" /> : null}
                      {n.link ? (
                        <Link
                          href={n.link}
                          className="font-medium text-ink hover:text-accent"
                          onClick={() => {
                            if (!n.is_read) markOneRead.mutate(n.id);
                          }}
                        >
                          {n.title}
                        </Link>
                      ) : (
                        <p className="font-medium text-ink">{n.title}</p>
                      )}
                    </div>
                    {n.body ? <p className="mt-1 text-muted">{n.body}</p> : null}
                    <p className="mt-1 text-xs text-muted">{formatRelativeDate(n.created_at)}</p>
                  </div>
                  {!n.is_read ? (
                    <button
                      type="button"
                      className="shrink-0 text-xs font-medium text-accent hover:underline disabled:opacity-50"
                      disabled={markOneRead.isPending && markOneRead.variables === n.id}
                      onClick={() => markOneRead.mutate(n.id)}
                    >
                      Mark read
                    </button>
                  ) : null}
                </div>
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      <section className="mt-10">
        <h2 className="font-semibold text-ink">Recommended roles</h2>
        {recs.isLoading ? <p className="mt-4 text-sm text-muted">Loading matches…</p> : null}
        {recs.error ? (
          <Alert tone="error" title="Matches unavailable" className="mt-4">
            {formatApiError(recs.error, "Could not load recommendations.")}
          </Alert>
        ) : null}
        <div className="mt-4 space-y-4">
          {recs.data?.results.map((job, i) => (
            <JobCard key={job.id} job={job} index={i} />
          ))}
        </div>
        {recs.data && recs.data.results.length === 0 ? (
          <EmptyState
            className="mt-4"
            title="No matches yet"
            description={
              recs.data.empty_reason ||
              "Add skills or upload a resume so Atlas can rank roles against your profile."
            }
            actions={[
              { href: "/onboarding", label: "Resume onboarding" },
              { href: "/profile", label: "Edit profile", variant: "secondary" },
              { href: "/jobs", label: "Browse jobs", variant: "ghost" },
            ]}
          />
        ) : null}
      </section>
    </div>
  );
}
