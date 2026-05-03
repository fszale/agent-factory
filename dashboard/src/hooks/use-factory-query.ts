import { useCallback, useEffect, useRef, useState } from "react";
import { useCredentials } from "@/components/admin/credentials-context";
import type { FactoryClient } from "@/lib/agent-factory/client";

export interface UseFactoryQueryResult<T> {
  data: T | null;
  error: unknown;
  isLoading: boolean;
  refetch: () => Promise<void>;
}

export function useFactoryQuery<T>(
  fetcher: (client: FactoryClient, signal: AbortSignal) => Promise<T>,
  deps: ReadonlyArray<unknown> = [],
  options: { pollMs?: number } = {},
): UseFactoryQueryResult<T> {
  const { client } = useCredentials();
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [isLoading, setLoading] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;

  const run = useCallback(async () => {
    if (!client) return;
    abortRef.current?.abort();
    const ctl = new AbortController();
    abortRef.current = ctl;
    setLoading(true);
    setError(null);
    try {
      const result = await fetcherRef.current(client, ctl.signal);
      if (!ctl.signal.aborted) {
        setData(result);
      }
    } catch (err) {
      if ((err as { name?: string })?.name === "AbortError") return;
      if (!ctl.signal.aborted) {
        setError(err);
      }
    } finally {
      if (!ctl.signal.aborted) setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [client, ...deps]);

  useEffect(() => {
    void run();
    return () => abortRef.current?.abort();
  }, [run]);

  useEffect(() => {
    if (!options.pollMs || !client) return;
    const id = window.setInterval(() => {
      void run();
    }, options.pollMs);
    return () => window.clearInterval(id);
  }, [run, options.pollMs, client]);

  return { data, error, isLoading, refetch: run };
}
