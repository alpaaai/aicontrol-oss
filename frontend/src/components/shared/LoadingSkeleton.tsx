export function SkeletonRow() {
  return (
    <div className="flex gap-3 py-3 border-b border-ac-border last:border-0 animate-pulse">
      <div className="h-4 bg-gray-100 rounded flex-1" />
      <div className="h-4 bg-gray-100 rounded w-24" />
      <div className="h-4 bg-gray-100 rounded w-16" />
    </div>
  );
}

export function SkeletonCard() {
  return (
    <div className="rounded-[10px] border border-ac-border bg-ac-card p-5 animate-pulse">
      <div className="h-3 bg-gray-100 rounded w-24 mb-3" />
      <div className="h-7 bg-gray-200 rounded w-16" />
    </div>
  );
}
