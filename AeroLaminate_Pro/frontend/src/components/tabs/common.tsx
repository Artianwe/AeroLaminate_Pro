"use client";
// AeroLaminate Pro - shared tab props and small display helpers. Author: Anwesh Ajitabh Dash.
import type { ReactNode } from "react";
import type { Json, Material, Project } from "@/lib/types";
import type { SolveState } from "@/lib/useSolver";

export interface TabProps {
  project: Project;
  setProject: (f: (p: Project) => Project) => void;
  analysis: Json;
  baseline: { name: string; analysis: Json; project: Project } | null;
  selected: number | null;
  setSelected: (i: number | null) => void;
  materials: Material[];
  illustrative: boolean;
  active: boolean;
}

export function KV({ rows }: { rows: [ReactNode, ReactNode, ReactNode?][] }) {
  return (
    <table className="tbl">
      <tbody>
        {rows.map(([k, v, u], i) => (
          <tr key={i}><td className="font-sans text-graphite-600">{k}</td><td className="num">{v}</td><td className="w-12 text-graphite-400">{u}</td></tr>
        ))}
      </tbody>
    </table>
  );
}

export function Chip({ ok, children, title }: { ok: boolean | null; children: ReactNode; title?: string }) {
  const c = ok === null ? "border-graphite-400 text-graphite-500" : ok ? "border-ok text-ok" : "border-graphite-400 text-graphite-400 line-through";
  return <span title={title} className={`border px-1.5 py-[1px] text-[10.5px] ${c}`}>{children}</span>;
}

export function SolverNote({ s, what }: { s: SolveState; what: string }) {
  if (s.error) return <div className="border border-bad/40 bg-red-50 px-2 py-1 text-[11px] text-bad">⚠ {what}: {s.error}</div>;
  if (s.loading && !s.data) return <div className="px-2 py-1 text-[11px] text-graphite-500">Computing {what}…</div>;
  if (s.stale && s.data) return <div className="px-2 py-1 text-[10.5px] text-warn">Updating {what}…</div>;
  return null;
}

export function Warnings({ items }: { items: string[] }) {
  if (!items?.length) return null;
  return (
    <ul className="space-y-0.5 text-[10.5px] text-graphite-600">
      {items.map((w, i) => <li key={i} className="flex gap-1"><span className="text-warn">▲</span><span>{w}</span></li>)}
    </ul>
  );
}

export const Grid = ({ children, cols = "lg:grid-cols-2" }: { children: ReactNode; cols?: string }) =>
  <div className={`grid grid-cols-1 gap-2 ${cols}`}>{children}</div>;
