export function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`animate-pulse rounded-md bg-muted ${className}`} />;
}

export function ReviewSkeleton() {
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3 md:gap-4">
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="rounded-lg border p-5 space-y-2">
            <Skeleton className="h-3 w-16" />
            <Skeleton className="h-8 w-24" />
          </div>
        ))}
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {Array.from({ length: 2 }).map((_, i) => (
          <div key={i} className="rounded-lg border p-5 space-y-3">
            <Skeleton className="h-5 w-32" />
            <div className="space-y-2">
              {Array.from({ length: 4 }).map((_, j) => (
                <Skeleton key={j} className="h-4 w-full" />
              ))}
            </div>
          </div>
        ))}
      </div>
      <div className="rounded-lg border p-5 space-y-3">
        <Skeleton className="h-5 w-40" />
        <Skeleton className="h-32 w-full" />
      </div>
    </div>
  );
}
