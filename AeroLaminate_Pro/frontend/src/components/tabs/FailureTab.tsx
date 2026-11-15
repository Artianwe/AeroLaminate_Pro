"use client";
// AeroLaminate Pro - failure assessment: envelopes, mode map, reserve-factor comparison. Author: Anwesh Ajitabh Dash.
import ChartFrame, { Empty } from "@/components/ChartFrame";
import { NumField, Select } from "@/components/inputs";
import { BarPlot, XYPlot, type Series } from "@/components/Plots";
import { BASELINE, CRIT_COLOR, CRIT_LABEL, MODE_LABEL, fmt, rfText } from "@/lib/project";
import type { Criterion } from "@/lib/types";
import { useSolver } from "@/lib/useSolver";
import { Grid, SolverNote, Warnings, type TabProps } from "./common";

const PLANE = { s1s2: ["σ1 [MPa]", "σ2 [MPa]", "τ12"], s2t12: ["σ2 [MPa]", "τ12 [MPa]", "σ1"], s1t12: ["σ1 [MPa]", "τ12 [MPa]", "σ2"] } as const;
const LPLANE = { NxNy: ["Nx [N/mm]", "Ny [N/mm]"], NxNxy: ["Nx [N/mm]", "Nxy [N/mm]"], NyNxy: ["Ny [N/mm]", "Nxy [N/mm]"] } as const;
const MODE_COLOR: Record<string, string> = { FT: "#2a78d6", FC: "#6250d6", MT: "#eb6834", MC: "#eda100", S: "#1baf7a", "IFF-A": "#eb6834", "IFF-B": "#1baf7a", "IFF-C": "#eda100", TH: "#8a8780", TW: "#8a8780" };

export default function FailureTab({ project, setProject, analysis: a, baseline, selected, active, illustrative }: TabProps) {
  const env = project.modules.envelope;
  const ply = (selected ?? 0) + 1;
  const req = { project: project.payload, ply: Math.min(ply, project.payload.plies.length), ...env };
  const s = useSolver("envelope", req, active && !!a);
  const bReq = baseline ? { project: baseline.project.payload, ply: 1, ...env } : null;
  const sb = useSolver("envelope", bReq, active && !!baseline);
  const setEnv = (k: keyof typeof env, v: unknown) => setProject((p) => ({ ...p, modules: { ...p.modules, envelope: { ...p.modules.envelope, [k]: v } } }));
  if (!a) return null;
  const e = s.data;
  const crits = Object.keys(a.failure.results) as Criterion[];
  const plySeries: Series[] = e ? Object.entries(e.ply_envelopes).map(([c, v]) => {
    const env = v as { x: number[]; y: number[]; valid: boolean[] };
    return { name: CRIT_LABEL[c as Criterion], color: CRIT_COLOR[c as Criterion], data: env.x.map((x, i) => ({ x, y: env.y[i] })).filter((_, i) => env.valid[i]) };
  }) : [];
  const lamSeries: Series[] = e ? Object.entries(e.laminate_envelopes).map(([c, v]) => {
    const env = v as { x: (number | null)[]; y: (number | null)[]; critical_ply: (number | null)[] };
    return { name: CRIT_LABEL[c as Criterion], color: CRIT_COLOR[c as Criterion],
      data: env.x.map((x, i) => ({ x: x as number, y: env.y[i] as number, ply: env.critical_ply[i] })).filter((d) => d.x !== null) };
  }) : [];
  if (sb.data && e) {
    const tw = sb.data.laminate_envelopes[crits.includes("tsai_wu") ? "tsai_wu" : crits[0]];
    if (tw) lamSeries.push({ name: `Baseline (${baseline!.name})`, color: BASELINE, dashed: true,
      data: tw.x.map((x: number | null, i: number) => ({ x: x as number, y: tw.y[i] as number })).filter((d: { x: number | null }) => d.x !== null) });
  }
  const rfBars = crits.map((c) => ({ c: CRIT_LABEL[c], rf: a.failure.results[c].critical.rf ?? 0, key: c }));
  const fos = a.fos;
  return (
    <div className="flex flex-col gap-2">
      <div className="panel flex flex-wrap items-end gap-3 px-2.5 py-1.5">
        <div className="w-36"><Select label="Ply stress plane" value={env.plane} onChange={(v) => setEnv("plane", v)}
          options={[{ value: "s1s2", label: "σ1 – σ2" }, { value: "s2t12", label: "σ2 – τ12" }, { value: "s1t12", label: "σ1 – τ12" }]} /></div>
        <div className="w-28"><NumField label={`Fixed ${PLANE[env.plane][2]}`} unit="MPa" value={env.fixed} onChange={(v) => setEnv("fixed", v ?? 0)} min={-5000} max={5000} /></div>
        <div className="w-36"><Select label="Laminate plane" value={env.laminate_plane} onChange={(v) => setEnv("laminate_plane", v)}
          options={[{ value: "NxNy", label: "Nx – Ny" }, { value: "NxNxy", label: "Nx – Nxy" }, { value: "NyNxy", label: "Ny – Nxy" }]} /></div>
        <span className="text-[11px] text-graphite-500">Ply envelope for ply {ply} ({a.laminate.plies[ply - 1]?.angle}°) — select a ply in the stack or table.</span>
        <div className="ml-auto"><SolverNote s={s} what="envelopes" /></div>
      </div>
      <Grid>
        <ChartFrame title={`Ply failure envelope — ply ${ply}`} subtitle={`${PLANE[env.plane][2]} = ${env.fixed} MPa; material strength surface`} classification="calculated" illustrative={illustrative}
          csv={() => plySeries.flatMap((sr) => sr.data.map((d) => ({ criterion: sr.name, x: d.x, y: d.y })))}
          note="Applied stress (bottom/top of ply) shown as dots, including residual stress. Open curves: the criterion has no failure in that direction.">
          {e ? <XYPlot series={plySeries} xLabel={PLANE[env.plane][0]} yLabel={PLANE[env.plane][1]} height={320}
            refX={[{ value: 0, dashed: false, color: "#b9b3a3" }]} refY={[{ value: 0, dashed: false, color: "#b9b3a3" }]}
            points={(e.applied_ply as number[][]).map((p, i) => ({ x: p[0], y: p[1], label: i ? "top" : "bot", color: "#1a1a19" }))} /> : <Empty>{s.error ?? "Computing…"}</Empty>}
        </ChartFrame>
        <ChartFrame title="Laminate first-ply-failure envelope" subtitle={`${LPLANE[env.laminate_plane].join(" vs ")}; moments = 0, residual included`} classification="calculated" illustrative={illustrative}
          csv={() => lamSeries.flatMap((sr) => sr.data.map((d) => ({ criterion: sr.name, x: d.x, y: d.y, critical_ply: (d as { ply?: number }).ply })))}
          note="Black dot: applied in-plane load. Inside the envelope = no ply failure predicted by that criterion.">
          {e ? <XYPlot series={lamSeries} xLabel={LPLANE[env.laminate_plane][0]} yLabel={LPLANE[env.laminate_plane][1]} height={320}
            refX={[{ value: 0, dashed: false, color: "#b9b3a3" }]} refY={[{ value: 0, dashed: false, color: "#b9b3a3" }]}
            points={[{ x: e.applied_laminate[0], y: e.applied_laminate[1], label: "applied" }]}
            tooltipExtra={(p) => p.ply ? <div>critical ply {String(p.ply)}</div> : null} /> : <Empty>{s.error ?? "Computing…"}</Empty>}
        </ChartFrame>
      </Grid>
      <Grid cols="xl:grid-cols-[1fr_2fr]">
        <ChartFrame title="Reserve factor by criterion" subtitle="minimum over plies" classification="calculated" illustrative={illustrative}
          csv={() => rfBars.map((r) => ({ criterion: r.c, rf: r.rf, ms: a.failure.results[r.key].critical.ms }))}>
          <BarPlot data={rfBars} xKey="c" bars={[{ key: "rf", name: "RF", color: "#2a78d6" }]} height={230} yDomain={[0, "auto"]} legend={false}
            cellColor={(row) => CRIT_COLOR[(row as { key: Criterion }).key]}
            refY={[{ value: 1, label: "RF = 1", color: "#b3372f" }, { value: fos, label: `FoS ${fos}`, color: "#8a5a05" }]} />
          <Warnings items={Object.entries(a.failure.unavailable).map(([k, r]) => `${CRIT_LABEL[k as Criterion]} unavailable: ${(r as string[]).join("; ")}`)} />
        </ChartFrame>
        <ChartFrame title="Failure-mode map" subtitle="mode at failure load, governing position per ply" classification="calculated"
          csv={() => a.laminate.plies.map((p: { index: number; angle: number }, k: number) => Object.fromEntries([["ply", p.index], ["angle", p.angle],
            ...crits.flatMap((c) => [[`${c}_rf`, a.failure.results[c].rf_ply[k]], [`${c}_mode`, modeOf(a, c, k)]])]))}>
          <div className="overflow-auto">
            <table className="tbl">
              <thead><tr><th>Ply</th><th>θ</th>{crits.map((c) => <th key={c} style={{ borderBottom: `2px solid ${CRIT_COLOR[c]}` }}>{CRIT_LABEL[c]}</th>)}</tr></thead>
              <tbody>
                {[...a.laminate.plies].reverse().map((p: { index: number; angle: number }) => {
                  const k = p.index - 1;
                  return <tr key={k} className={selected === k ? "bg-amber-400/15" : ""}><td>{p.index}</td><td>{p.angle}°</td>
                    {crits.map((c) => {
                      const m = modeOf(a, c, k); const rf = a.failure.results[c].rf_ply[k];
                      const crit = a.failure.results[c].critical.ply === p.index;
                      return <td key={c} title={MODE_LABEL[m] ?? m} className={crit ? "font-semibold" : ""}>
                        <span className="mr-1 inline-block h-2 w-2" style={{ background: MODE_COLOR[m] ?? "#8a8780" }} />{m} <span className="text-graphite-500">{rfText(rf)}</span>{crit ? " ◀" : ""}</td>;
                    })}</tr>;
                })}
              </tbody>
            </table>
          </div>
          <p className="mt-1 text-[10.5px] text-graphite-500">FT/FC fibre tension/compression · MT/MC matrix tension/compression · S shear · IFF-A/B/C Puck inter-fibre modes · ◀ critical ply. FoS = {fos}; critical MS shown in the summary bar.</p>
        </ChartFrame>
      </Grid>
    </div>
  );
}

function modeOf(a: { failure: { results: Record<string, { rf: number[][]; mode_at_failure: string[][] }> } }, c: string, k: number) {
  const R = a.failure.results[c];
  const rfs = R.rf[k].map((v) => (v < 0 ? Infinity : v));
  const p = rfs.indexOf(Math.min(...rfs));
  return Number.isFinite(rfs[p]) ? R.mode_at_failure[k][p] : "—";
}

