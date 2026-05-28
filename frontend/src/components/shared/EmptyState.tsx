export function EmptyState({ message }: { message: string }) {
  return (
    <div className="flex items-center justify-center h-32 text-sm text-ac-text-muted">
      {message}
    </div>
  );
}
