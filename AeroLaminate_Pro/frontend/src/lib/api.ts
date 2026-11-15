// AeroLaminate Pro - API client. Author: Anwesh Ajitabh Dash.
import type { Json } from "./types";

export class ApiError extends Error {
  constructor(message: string, public status: number, public kind?: string) { super(message); }
}

function formatDetail(detail: Json): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail.map((d) => `${(d.loc ?? []).filter((x: Json) => x !== "body").join(".")}: ${d.msg}`).join("; ");
  }
  return JSON.stringify(detail);
}

export async function post(path: string, body: unknown, signal?: AbortSignal): Promise<Json> {
  let r: Response;
  try {
    r = await fetch(`/api/${path}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body), signal });
  } catch (e) {
    if ((e as Error).name === "AbortError") throw e;
    throw new ApiError("Analysis engine unreachable - is the FastAPI backend running on port 8000?", 0, "network");
  }
  const text = await r.text();
  let j: Json = null;
  try { j = JSON.parse(text); } catch { /* non-JSON error page */ }
  if (!r.ok) {
    const msg = j?.detail ? formatDetail(j.detail) : `HTTP ${r.status}${r.status >= 500 ? " - engine error (see backend console)" : ""}`;
    throw new ApiError(msg, r.status, j?.kind ?? (r.status === 422 ? "validation" : undefined));
  }
  return j;
}

export async function get(path: string): Promise<Json> {
  const r = await fetch(`/api/${path}`);
  if (!r.ok) throw new ApiError(`HTTP ${r.status}`, r.status);
  return r.json();
}

export async function send(path: string, method: "PUT" | "DELETE", body?: unknown): Promise<Json> {
  const r = await fetch(`/api/${path}`, { method, headers: { "Content-Type": "application/json" }, body: body ? JSON.stringify(body) : undefined });
  const j = await r.json().catch(() => null);
  if (!r.ok) throw new ApiError(j?.detail ? formatDetail(j.detail) : `HTTP ${r.status}`, r.status);
  return j;
}
