import { Skeleton } from "@/components/ui/Skeleton";

export function JobCardSkeleton() {
  return (
    <div className="rounded-xl border border-line bg-elevated p-5">
      <div className="flex gap-2">
        <Skeleton className="h-5 w-16" />
        <Skeleton className="h-5 w-14" />
        <Skeleton className="h-5 w-12" />
      </div>
      <Skeleton className="mt-3 h-7 w-3/4" />
      <Skeleton className="mt-2 h-4 w-1/3" />
      <Skeleton className="mt-3 h-4 w-full" />
      <Skeleton className="mt-1 h-4 w-5/6" />
    </div>
  );
}
