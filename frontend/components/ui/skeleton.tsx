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

export function ReviewEmptyState({ onUpload, reason }: { onUpload: () => void; reason?: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-center">
      <div className="text-base font-medium text-foreground">추출된 데이터가 없습니다</div>
      <p className="mt-2 max-w-md text-sm text-muted-foreground">
        문서를 업로드하고 추출을 먼저 진행해 주세요.
      </p>
      {reason && (
        <p className="mt-2 max-w-md text-xs text-amber-600 dark:text-amber-400">사유: {reason}</p>
      )}
      <div className="mt-6 flex gap-2">
        <button
          onClick={onUpload}
          className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:opacity-90"
        >
          업로드로 이동
        </button>
      </div>
    </div>
  );
}
