"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Bookmark } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { useToast } from "@/components/ui/Toaster";
import { saveJob, type SavedJob } from "@/lib/api";
import { formatApiError } from "@/lib/apiError";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";

function mergeSavedCache(
  current: SavedJob[] | undefined,
  saved: SavedJob,
): SavedJob[] {
  if (!current?.length) return [saved];
  const rest = current.filter((item) => item.job_id !== saved.job_id && item.id !== saved.id);
  return [saved, ...rest];
}

export function SaveJobButton({
  jobId,
  size = "md",
  compact = false,
  className,
}: {
  jobId: number;
  size?: "sm" | "md" | "lg";
  compact?: boolean;
  className?: string;
}) {
  const { user } = useAuth();
  const toast = useToast();
  const qc = useQueryClient();
  const [done, setDone] = useState(false);

  const mutation = useMutation({
    mutationFn: () => {
      if (!user) throw new Error("Sign in required");
      return saveJob(jobId);
    },
    onSuccess: (saved) => {
      setDone(true);
      const key = ["saved", user?.id] as const;
      // Immediate cache update so /saved shows the job without a hard refresh
      qc.setQueryData<SavedJob[]>(key, (current) => mergeSavedCache(current, saved));
      void qc.invalidateQueries({ queryKey: ["saved"] });
      const title = saved.job_title || "Job";
      toast.success(`${title} is in your saved workspace.`, "Job saved");
    },
    onError: (err) => {
      toast.error(formatApiError(err, "Could not save this job."), "Save failed");
    },
  });

  if (!user) {
    if (compact) {
      return (
        <Button
          href={`/login?next=/jobs/${jobId}`}
          variant="secondary"
          size={size}
          className={className}
          aria-label="Sign in to save"
        >
          <Bookmark className="h-4 w-4" aria-hidden />
        </Button>
      );
    }
    return (
      <Button href={`/login?next=/jobs/${jobId}`} variant="secondary" size={size} className={className}>
        Sign in to save
      </Button>
    );
  }

  return (
    <Button
      variant="secondary"
      size={size}
      onClick={() => mutation.mutate()}
      disabled={mutation.isPending || done}
      className={cn(className)}
      aria-label={done ? "Saved" : "Save job"}
    >
      <Bookmark className={cn("h-4 w-4", done && "fill-current")} aria-hidden />
      {!compact ? (done ? "Saved" : mutation.isPending ? "Saving…" : "Save job") : null}
    </Button>
  );
}
