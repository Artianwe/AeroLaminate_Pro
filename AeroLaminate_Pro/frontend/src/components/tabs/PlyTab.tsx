"use client";
// AeroLaminate Pro - ply response tab: through-thickness stress/strain, material-axis stresses, FI and RF per ply.
// Author: Anwesh Ajitabh Dash.
import { useState } from "react";
import ChartFrame from "@/components/ChartFrame";
import { BarPlot, XYPlot, type Series } from "@/components/Plots";
import { BASELINE, CRIT_COLOR, CRIT_LABEL, MODE_LABEL, SERIES, fmt, rfText } from "@/lib/project";
import type { Criterion } from "@/lib/types";
import { Grid, type TabProps } from "./common";

type Arr3 = number[][][];

function throughThickness(z: number[][], v: Arr3, comp: number, scale: number) {
  const pts: { x: number; y: number; ply: number }[] = [];
  for (let k = 0; k < z.length; k++) {
    pts.push({ x: v[k][0][comp] * scale, y: z[k][0], ply: k + 1 });
    pts.push({ x: v[k][2][comp] * scale, y: z[k][2], ply: k + 1 });
  }
  return pts;
}

export default function PlyTab({ analysis: a, baseline, selected, setSelected, illustrative }: TabProps) {
  const [axes, setAxes] = useState<"xy" | "12">("xy");
  const [pos, setPos] = useState(0); // 0 bottom, 1 middle, 2 top
  if (!a) return null;
  const st = a.ply_state;
  const z = st.z as number[][];
  const sig = (axes === "xy" ? st.sigma_xy : st.sigma_12) as Arr3;
  const eps = (axes === "xy" ? st.mech_eps_xy : st.mech_eps_12) as Arr3;
  const tot = st.eps_xy as Arr3;
  const names = axes === "xy" ? ["σx", "σy", "τxy"] : ["σ1", "σ2", "τ12"];
  const enames = axes === "xy" ? ["εx", "εy", "γxy"] : ["ε1", "ε2", "γ12"];
  const sSeries: Series[] = names.map((n, c) => ({ name: n, color: SERIES[c], data: throughThickness(z, sig, c, 1) }));
  if (baseline && baseline.analysis.ply_state) {
    const bs = (axes === "xy" ? baseline.analysis.ply_state.sigma_xy : baseline.analysis.ply_state.sigma_12) as Arr3;
    sSeries.push({ name: `${names[0]} baseline`, color: BASELINE, dashed: true, data: throughThickness(baseline.analysis.ply_state.z, bs, 0, 1) });
  }
  const eSeries: Series[] = enames.map((n, c) => ({ name: `${n} (mech.)`, color: SERIES[c], data: throughThickness(z, eps, c, 1e6) }));
  if (axes === "xy" && (a.response.dT || a.response.dC)) eSeries.push({ name: "εx (total)", color: SERIES[0], dashed: true, data: throughThickness(z, tot, 0, 1e6) });
  const interfaces = a.laminate.z.map((v: number) => ({ value: v, color: "#d9d3c2", dashed: false }));
  const plyRows = a.laminate.plies.map((p: { index: number; angle: number }, k: number) => ({
    ply: `${p.index}`, angle: p.angle, s1: st.sigma_12[k][pos][0], s2: st.sigma_12[k][pos][1], t12: st.sigma_12[k][pos][2],
  }));
  const crits = Object.keys(a.failure.results) as Criterion[];
  const fiRows = a.laminate.plies.map((p: { index: number; angle: number }, k: number) => {
    const row: Record<string, unknown> = { ply: `${p.index}` };
    for (const c of crits) row[c] = a.failure.results[c].fi_ply[k];
    return row;
  });
  const rfRows = a.laminate.plies.map((p: { index: number }, k: number) => {
    const row: Record<string, unknown> = { ply: `${p.index}` };
    for (const c of crits) { const v = a.failure.results[c].rf_ply[k]; row[c] = v < 0 ? null : v; }
    return row;
  });
  const sel = selected ?? 0;
  const selPly = a.laminate.plies[sel];
  const posName = ["bottom", "middle", "top"][pos];
  const selCls = selected !== null ? (row: Record<string, unknown>) => (row.ply === `${sel + 1}` || String(row.ply).startsWith(`${sel + 1} `) ? undefined : "#cfc9b8") : undefined;
  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center gap-2 text-[11px]">
        <span className="lbl">Axes</span>
        <button className={`btn ${axes === "xy" ? "btn-primary" : ""}`} onClick={() => setAxes("xy")}>Laminate x-y</button>
        <button className={`btn ${axes === "12" ? "btn-primary" : ""}`} onClick={() => setAxes("12")}>Material 1-2</button>
        <span className="lbl ml-3">Ply position</span>
        {["bottom", "middle", "top"].map((p, i) => <button key={p} className={`btn ${pos === i ? "btn-primary" : ""}`} onClick={() => setPos(i)}>{p}</button>)}
        <span className="ml-3 text-graphite-500">Selected ply: {selected === null ? "none (click a bar or the stack)" : `${sel + 1} (${selPly?.angle}°)`}</span>
        {selected !== null && <button className="btn" onClick={() => setSelected(null)}>Clear</button>}
      </div>
      <Grid>
        <ChartFrame title="Stress through thickness" subtitle={axes === "xy" ? "laminate axes, MPa" : "material axes, MPa"} classification="calculated" illustrative={illustrative}
          csv={() => sSeries.flatMap((s) => s.data.map((d) => ({ series: s.name, z_mm: d.y, stress_MPa: d.x })))}>
          <XYPlot series={sSeries} xLabel="Stress [MPa]" yLabel="z [mm]" height={300} refY={interfaces} refX={[{ value: 0, dashed: false, color: "#8a8780" }]}
            tooltipExtra={(p) => <div>ply {String(p.ply)}</div>} />
        </ChartFrame>
        <ChartFrame title="Mechanical strain through thickness" subtitle="stress-producing strain, µε" classification="calculated"
          csv={() => eSeries.flatMap((s) => s.data.map((d) => ({ series: s.name, z_mm: d.y, microstrain: d.x })))}>
          <XYPlot series={eSeries} xLabel="Strain [µε]" yLabel="z [mm]" height={300} refY={interfaces} refX={[{ value: 0, dashed: false, color: "#8a8780" }]}
            tooltipExtra={(p) => <div>ply {String(p.ply)}</div>} />
        </ChartFrame>
      </Grid>
      <Grid cols="xl:grid-cols-3">
        <ChartFrame title="σ1 per ply" subtitle={`material axes, ${posName}`} classification="calculated" csv={() => plyRows}>
          <BarPlot data={plyRows} xKey="ply" bars={[{ key: "s1", name: "σ1 [MPa]", color: SERIES[0] }]} height={200} refY={[{ value: 0 }]} cellColor={selCls} legend={false} />
        </ChartFrame>
        <ChartFrame title="σ2 and τ12 per ply" subtitle={`material axes, ${posName}`} classification="calculated" csv={() => plyRows}>
          <BarPlot data={plyRows} xKey="ply" bars={[{ key: "s2", name: "σ2 [MPa]", color: SERIES[1] }, { key: "t12", name: "τ12 [MPa]", color: SERIES[2] }]} height={200} refY={[{ value: 0 }]} />
        </ChartFrame>
        <ChartFrame title="Selected ply" subtitle={selPly ? `ply ${sel + 1}, θ = ${selPly.angle}°` : ""} classification="calculated">
          {selPly && <table className="tbl"><thead><tr><th>Criterion</th><th className="num">FI</th><th className="num">RF</th><th>Mode at failure</th></tr></thead><tbody>
            {crits.map((c) => {
              const R = a.failure.results[c];
              const rf = R.rf_ply[sel];
              const p = R.rf[sel].indexOf(Math.min(...R.rf[sel].map((v: number) => (v < 0 ? Infinity : v))));
              return <tr key={c}><td className="font-sans"><span style={{ color: CRIT_COLOR[c] }}>■</span> {CRIT_LABEL[c]}</td><td className="num">{fmt(R.fi_ply[sel], 4)}</td>
                <td className="num">{rfText(rf)}</td><td className="font-sans text-[10.5px]">{p >= 0 ? MODE_LABEL[R.mode_at_failure[sel][p]] ?? R.mode_at_failure[sel][p] : "—"}</td></tr>;
            })}
          </tbody></table>}
        </ChartFrame>
      </Grid>
      <Grid>
        <ChartFrame title="Failure index versus ply" subtitle="max over ply thickness, at applied load" classification="calculated" illustrative={illustrative} csv={() => fiRows as never}
          note="FI definitions differ (linear ratio vs quadratic form): compare criteria by reserve factor, not FI magnitude.">
          <BarPlot data={fiRows} xKey="ply" xLabel="Ply" bars={crits.map((c) => ({ key: c, name: CRIT_LABEL[c], color: CRIT_COLOR[c] }))} height={240} refY={[{ value: 1, label: "FI = 1", color: "#b3372f" }]} />
        </ChartFrame>
        <ChartFrame title="Reserve factor versus ply" subtitle="load multiplier to failure (residual held)" classification="calculated" illustrative={illustrative} csv={() => rfRows as never}>
          <BarPlot data={rfRows} xKey="ply" xLabel="Ply" bars={crits.map((c) => ({ key: c, name: CRIT_LABEL[c], color: CRIT_COLOR[c] }))} height={240}
            yDomain={[0, "auto"]} refY={[{ value: 1, label: "RF = 1", color: "#b3372f" }, { value: a.fos, label: `FoS ${a.fos}`, color: "#8a5a05" }]} />
        </ChartFrame>
      </Grid>
    </div>
  );
}
