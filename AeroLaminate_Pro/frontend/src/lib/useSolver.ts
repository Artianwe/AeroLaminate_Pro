"use client";
// AeroLaminate Pro - debounced, cancellable solver requests keyed on their inputs. Author: Anwesh Ajitabh Dash.
import { useEffect, useRef, useState } from "react";
import { ApiError, post } from "./api";
import type { Json } from "./types";

export interface SolveState { data: Json | null; error: string | null; errorKind?: string; loading: boolean; ms: number | null; stale: boolean; key: string | null }

/** Runs POST /api/<endpoint> whenever `body` changes (deep, via JSON) and `enabled` is true. Keeps last good data. */
export function useSolver(endpoint: string, body: unknown, enabled = true, delay = 350): SolveState & { rerun: () => void } {
  const key = JSON.stringify(body);
  const [st, setSt] = useState<SolveState>({ data: null, error: null, loading: false, ms: null, stale: false, key: null });
  const [nonce, setNonce] = useState(0);
  const ctl = useRef<AbortController | null>(null);
  useEffect(() => {
    if (!enabled || body === null) return;
    if (st.key === key && !st.error && nonce === 0) return;
    setSt((s) => ({ ...s, stale: s.key !== key }));
    const t = setTimeout(async () => {
      ctl.current?.abort();
      const c = new AbortController();
      ctl.current = c;
      setSt((s) => ({ ...s, loading: true }));
      const t0 = performance.now();
      try {
        const data = await post(endpoint, JSON.parse(key), c.signal);
        if (!c.signal.aborted) setSt({ data, error: null, errorKind: undefined, loading: false, ms: performance.now() - t0, stale: false, key });
      } catch (e) {
        if ((e as Error).name === "AbortError") return;
        setSt((s) => ({ ...s, error: (e as Error).message, errorKind: e instanceof ApiError ? e.kind : undefined, loading: false, ms: performance.now() - t0, stale: true, key }));
      }
    }, delay);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [endpoint, key, enabled, nonce]);
  return { ...st, rerun: () => setNonce((n) => n + 1) };
}

/** Explicitly triggered request (optimiser): result remembers the input key it was computed for. */
export function useAction(endpoint: string) {
  const [st, setSt] = useState<SolveState>({ data: null, error: null, loading: false, ms: null, stale: false, key: null });
  const run = async (body: unknown) => {
    const key = JSON.stringify(body);
    setSt((s) => ({ ...s, loading: true, error: null }));
    const t0 = performance.now();
    try {
      const data = await post(endpoint, body);
      setSt({ data, error: null, loading: false, ms: performance.now() - t0, stale: false, key });
    } catch (e) {
      setSt((s) => ({ ...s, error: (e as Error).message, loading: false }));
    }
  };
  return { ...st, run };
}
