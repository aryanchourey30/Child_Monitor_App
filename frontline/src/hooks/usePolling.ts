import { useEffect, useRef, useState } from "react";

interface PollingOptions<T> {
  fetcher: () => Promise<T>;
  intervalMs?: number;
  immediate?: boolean;
}

export function usePolling<T>({
  fetcher,
  intervalMs = 4000,
  immediate = true,
}: PollingOptions<T>) {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState<boolean>(immediate);
  const [error, setError] = useState<string | null>(null);
  const fetcherRef = useRef(fetcher);

  useEffect(() => {
    fetcherRef.current = fetcher;
  }, [fetcher]);

  useEffect(() => {
    let mounted = true;
    let timer: number | null = null;

    const run = async () => {
      try {
        const result = await fetcherRef.current();
        if (!mounted) {
          return;
        }
        setData(result);
        setError(null);
      } catch (err) {
        if (!mounted) {
          return;
        }
        const message = err instanceof Error ? err.message : "Polling failed";
        setError(message);
      } finally {
        if (mounted) {
          setLoading(false);
        }
      }
    };

    if (immediate) {
      void run();
    } else {
      setLoading(false);
    }

    timer = window.setInterval(() => {
      void run();
    }, intervalMs);

    return () => {
      mounted = false;
      if (timer !== null) {
        window.clearInterval(timer);
      }
    };
  }, [intervalMs, immediate]);

  return { data, loading, error };
}
