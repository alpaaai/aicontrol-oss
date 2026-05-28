import { useEffect, useRef, useState, useCallback } from "react";

export function usePoll<T>(
  fetcher: () => Promise<T>,
  intervalMs: number,
  options: { immediate?: boolean } = {}
) {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | undefined>(undefined);

  const run = useCallback(async () => {
    try {
      const result = await fetcher();
      setData(result);
      setError(null);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Request failed");
    } finally {
      setLoading(false);
    }
  }, [fetcher]);

  useEffect(() => {
    if (options.immediate !== false) run();
    timerRef.current = setInterval(run, intervalMs);
    return () => clearInterval(timerRef.current);
  }, [run, intervalMs, options.immediate]);

  return { data, loading, error, refetch: run };
}
