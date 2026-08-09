"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { ExternalLink } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { useToast } from "@/components/ui/Toaster";
import { saveJob, type SavedJob } from "@/lib/api";
import { formatApiError } from "@/lib/apiError";
import { useAuth } from "@/lib/auth";
import { applyDestinationLabel, cn } from "@/lib/utils";

type Props = {
  jobId: number;
  applyUrl: string;
  companyName?: string;
  size?: "sm" | "md" | "lg";
  className?: string;
  showDestination?: boolean;
};

/**
 * Opens the official apply URL and, when signed in, marks the job as applied
 * in the saved pipeline without proxying the employer's form.
 */
export function TrackedApplyButton({
  jobId,
  applyUrl,
  companyName,
  size = "sm",
  className,
  showDestination = false,
}: Props) {
  const { user } = useAuth();
  const toast = useToast();
  const qc = useQueryClient();
  const [tracked, setTracked] = useState(false);
  const destination = applyDestinationLabel(applyUrl);

  const mutation = useMutation({
    mutationFn: () => saveJob(jobId, "applied"),
    onSuccess: (saved) => {
      setTracked(true);
      const key = ["saved", user?.id] as const;
      qc.setQueryData<SavedJob[]>(key, (current) => {
        if (!current?.length) return [saved];
        const rest = current.filter(
          (item) => item.job_id !== saved.job_id && item.id !== saved.id,
        );
        return [saved, ...rest];
      });
      void qc.invalidateQueries({ queryKey: ["saved"] });
      toast.success(
        saved.job_title
          ? `${saved.job_title} marked as applied.`
          : "Role marked as applied in your workspace.",
        "Application tracked",
      );
    },
    onError: (err: Error) => {
      toast.error(formatApiError(err, "Could not track this application."), "Tracking failed");
    },
  });

  const onApply = () => {
    window.open(applyUrl, "_blank", "noopener,noreferrer");
    if (user) {
      mutation.mutate();
    }
  };

  return (
    <div className={cn("flex flex-col gap-1", className)}>
      <Button
        type="button"
        size={size}
        onClick={onApply}
        className="whitespace-nowrap"
        aria-label={
          companyName
            ? `Apply officially at ${companyName}`
            : "Apply on official career page"
        }
      >
        Apply
        <ExternalLink className="h-3.5 w-3.5" aria-hidden />
      </Button>
      {showDestination && destination ? (
        <p className="text-xs text-muted">Opens {destination}</p>
      ) : null}
      {user && tracked ? (
        <p className="text-xs text-accent" role="status">
          Marked as applied
        </p>
      ) : null}
      {user && mutation.isPending ? (
        <p className="text-xs text-muted" role="status">
          Tracking application…
        </p>
      ) : null}
      {!user ? (
        <p className="text-xs text-muted">
          <a href={`/login?next=/jobs/${jobId}`} className="underline hover:text-ink">
            Sign in
          </a>{" "}
          to track applications
        </p>
      ) : null}
    </div>
  );
}
