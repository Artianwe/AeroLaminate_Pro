"use client";
// AeroLaminate Pro - printable engineering report. Author, owner and maintainer: Anwesh Ajitabh Dash.
import { useEffect, useState } from "react";
import { formatLayup } from "@/lib/layup";
import { APP, AUTHOR, CRIT_LABEL, MODE_LABEL, fmt, rfText } from "@/lib/project";
import type { Criterion, Json, Project } from "@/lib/types";

export default function Report() {
  const [d, setD] = useState<{ project: Project; analysis: Json; generated: string } | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    try {
      const s = localStorage.getItem("aerolaminate.report");
      if (!s) return setErr("No report data. Open the report from the workspace (Report button).");
      setD(JSON.parse(s));
    } catch { setErr("Report data could not be read."); }
  }, []);
  if (err) return <div className="p-8 text-graphite-700">{err}</div>;
  if (!d) return null;
  const { project: p, analysis: a } = d;
  if (!a) return <div className="p-8">The analysis had not completed when the report was requested.</div>;
  const ec = a.engineering_constants;
  const crits = Object.keys(a.failure.results) as Criterion[];
  const L = p.payload.loads, E = p.payload.environment;
  const M = (m: number[][], unit: string, label: string) => (
    <div><div className="mb-0.5 text-[10.5px] font-semibold">{label} [{unit}]</div>
      <table className="tbl"><tbody>{m.map((r, i) => <tr key={i}>{r.map((v, j) => <td key={j} className="num">{Math.abs(v) < 1e-12 * Math.abs(m[0][0]) ? "0" : fmt(v, 5)}</td>)}</tr>)}</tbody></table></div>);
  return (
    <div className="mx-auto max-w-[960px] bg-white p-8 text-[11.5px] leading-relaxed text-graphite-900 print:p-0">
      <div className="no-print mb-4 flex gap-2"><button className="btn btn-primary" onClick={() => window.print()}>Print / save as PDF</button>
        <span className="text-graphite-500">Use the browser print dialog; choose "Save as PDF" for a file.</span></div>
      <header className="mb-4 border-b-2 border-graphite-900 pb-2">
        <div className="flex items-baseline justify-between">
          <h1 className="font-mono text-[20px] font-semibold">{APP} — Laminate Analysis Report</h1>
          <span className="font-mono text-[10.5px]">{new Date(d.generated).toLocaleString()}</span>
        </div>
        <div className="mt-1 grid grid-cols-2 gap-x-6 text-[11px]">
          <div><b>Project:</b> {p.name}</div><div><b>Analyst:</b> {p.author || "—"}</div>
          <div><b>Software:</b> {APP} 1.0 — author, owner and maintainer {AUTHOR}</div><div><b>Layup:</b> <span className="font-mono">{formatLayup(p.payload.plies.map((x) => x.angle))}</span></div>
        </div>
      </header>

      <section className="mb-4 border border-amber-600 bg-amber-400/10 p-2 text-[10.5px]">
        <b>Status of results.</b> Screening-level analysis based on Classical Laminate Theory and the documented methods listed in RESEARCH_AND_GAP_ANALYSIS.md.
        Failure indices are deterministic stress measures, not probabilities. This report is not a certification document and does not replace the
        test-based building-block substantiation of FAA AC 20-107B / CMH-17. Material values are mean/typical data with the provenance listed below, not design allowables.
      </section>

      <h2 className="mb-1 mt-3 border-b border-rule text-[13px] font-semibold">1. Inputs</h2>
      <table className="tbl mb-2"><tbody>
        <tr><td>Material</td><td>{a.laminate.plies[0].material} ({p.payload.material_id}){p.payload.materials?.length ? " — with project-level edits" : ""}</td></tr>
        <tr><td>Plies / thickness</td><td>{a.laminate.n_plies} plies, h = {fmt(a.laminate.h, 5)} mm, areal mass {a.laminate.areal_mass ? `${fmt(a.laminate.areal_mass, 4)} kg/m²` : "n/a"}</td></tr>
        <tr><td>Loads</td><td className="font-mono">Nx {L.Nx}, Ny {L.Ny}, Nxy {L.Nxy} N/mm; Mx {L.Mx}, My {L.My}, Mxy {L.Mxy} N; Qx {L.Qx}, Qy {L.Qy} N/mm</td></tr>
        <tr><td>Environment</td><td>T stress-free {E.T_stress_free} °C, T service {E.T_service} °C (ΔT = {E.T_service - E.T_stress_free} °C), moisture {E.moisture} %, hot/wet knockdown {E.hotwet_knockdown ? "ON (Chamis estimate)" : "off"}</td></tr>
        <tr><td>Factor of safety</td><td>{a.fos} (MS = RF/FoS − 1)</td></tr>
      </tbody></table>
      <table className="tbl mb-2"><thead><tr><th>Ply</th><th>θ [°]</th><th>t [mm]</th><th>z bottom</th><th>z top</th><th>Material</th></tr></thead>
        <tbody>{a.laminate.plies.map((q: { index: number; angle: number; thickness: number; material: string }, i: number) =>
          <tr key={i}><td>{q.index}</td><td>{q.angle}</td><td>{fmt(q.thickness, 4)}</td><td>{fmt(a.laminate.z[i], 4)}</td><td>{fmt(a.laminate.z[i + 1], 4)}</td><td>{q.material}</td></tr>)}</tbody></table>

      <h2 className="mb-1 mt-3 border-b border-rule text-[13px] font-semibold">2. Laminate stiffness</h2>
      <div className="grid grid-cols-3 gap-3">{M(a.matrices.A, "N/mm", "A")}{M(a.matrices.B, "N", "B")}{M(a.matrices.D, "N·mm", "D")}</div>
      <p className="mt-1">Ex {fmt(ec.Ex / 1000, 4)} GPa · Ey {fmt(ec.Ey / 1000, 4)} GPa · Gxy {fmt(ec.Gxy / 1000, 4)} GPa · νxy {fmt(ec.nuxy, 4)} · Efx {fmt(ec.Efx / 1000, 4)} GPa ·
        symmetric {String(a.classification.symmetric_stiffness)} · balanced {String(a.classification.balanced)} · scaled cond(ABD) {fmt(a.diagnostics.scaled_condition, 3)}</p>

      <h2 className="mb-1 mt-3 border-b border-rule text-[13px] font-semibold">3. Response</h2>
      <p className="font-mono">ε⁰ = [{a.response.eps0.map((v: number) => fmt(v * 1e6, 5)).join(", ")}] µε; κ = [{a.response.kappa.map((v: number) => fmt(v * 1e3, 5)).join(", ")}] 1/m</p>

      <h2 className="mb-1 mt-3 border-b border-rule text-[13px] font-semibold">4. Failure assessment (first-ply failure)</h2>
      <table className="tbl mb-1"><thead><tr><th>Criterion</th><th className="num">Min RF</th><th className="num">MS</th><th>Critical ply / position</th><th>Mode</th></tr></thead>
        <tbody>{crits.map((c) => { const k = a.failure.results[c].critical; return <tr key={c}><td>{CRIT_LABEL[c]}</td><td className="num">{rfText(k.rf)}</td><td className="num">{fmt(k.ms, 3)}</td>
          <td>{k.ply} / {k.position}</td><td>{MODE_LABEL[k.mode] ?? k.mode}</td></tr>; })}</tbody></table>
      {Object.keys(a.failure.unavailable).length > 0 && <p className="text-[10.5px]">Unavailable: {Object.entries(a.failure.unavailable).map(([k, v]) => `${CRIT_LABEL[k as Criterion]} (${(v as string[]).join("; ")})`).join(" · ")}</p>}
      <table className="tbl mt-2"><thead><tr><th>Ply</th>{crits.map((c) => <th key={c} className="num">{CRIT_LABEL[c]} RF</th>)}</tr></thead>
        <tbody>{a.laminate.plies.map((q: { index: number }, k: number) => <tr key={k}><td>{q.index}</td>{crits.map((c) => <td key={c} className="num">{rfText(a.failure.results[c].rf_ply[k])}</td>)}</tr>)}</tbody></table>

      <h2 className="mb-1 mt-3 border-b border-rule text-[13px] font-semibold">5. Design-rule checks (guidelines, not regulations)</h2>
      <table className="tbl"><tbody>{a.design_rules.map((r: { rule: string; status: string; detail: string }) => <tr key={r.rule}><td>{r.rule}</td><td className={r.status === "pass" ? "text-ok" : r.status === "fail" ? "text-bad" : ""}>{r.status}</td><td>{r.detail}</td></tr>)}</tbody></table>

      <h2 className="mb-1 mt-3 border-b border-rule text-[13px] font-semibold">6. Data provenance, assumptions and flags</h2>
      <ul className="list-disc pl-5 text-[10.5px]">{[...a.provenance.warnings, ...a.provenance.flags].map((w: string, i: number) => <li key={i}>{w}</li>)}</ul>
      <p className="mt-1 text-[10.5px]">Property status by material: {Object.entries(a.provenance.status).map(([m, st]) => `${m}: ${Object.entries(st as Record<string, string>).map(([k, v]) => `${k}=${v}`).join(", ")}`).join(" | ")}</p>
      <p className="mt-2 text-[10.5px]">Assumptions: plane stress, Kirchhoff kinematics, linear elastic plies, perfect bonding; no interlaminar, free-edge or 3-D effects; residual hygrothermal stresses held constant while mechanical load is scaled.</p>
      {p.notes && <><h2 className="mb-1 mt-3 border-b border-rule text-[13px] font-semibold">7. Notes</h2><p className="whitespace-pre-wrap">{p.notes}</p></>}
      <footer className="mt-6 border-t border-rule pt-1 text-[10px] text-graphite-500">Generated by {APP} — software authored, owned and maintained by {AUTHOR}. Results are the responsibility of the analyst.</footer>
    </div>
  );
}
