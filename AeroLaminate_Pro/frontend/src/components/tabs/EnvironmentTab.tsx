"use client";
// AeroLaminate Pro - hygrothermal tab: sweeps, residual stress, warpage, hot/wet retention. Author: Anwesh Ajitabh Dash.
import ChartFrame, { Empty } from "@/components/ChartFrame";
import { FieldContour } from "@/components/Graphics";
import { NumField, Select } from "@/components/inputs";
import { BarPlot, XYPlot, type Series } from "@/components/Plots";
import { CRIT_COLOR, CRIT_LABEL, SERIES, fmt } from "@/lib/project";
import type { Criterion } from "@/lib/types";
import { useSolver } from "@/lib/useSolver";
import { Grid, SolverNote, Warnings, type TabProps } from "./common";

export default function EnvironmentTab({ project, setProject, analysis: a, active, illustrative }: TabProps) {
  const m = project.modules.envSweep;
  const s = useSolver("environment", { project: project.payload, ...m }, active && !!a);
  const set = (k: keyof typeof m, v: unknown) => setProject((p) => ({ ...p, modules: { ...p.modules, envSweep: { ...p.modules.envSweep, [k]: v } } }));
  const r = s.data;
  const env = project.payload.environment;
  const ctrl = (
    <div className="panel flex flex-wrap items-end gap-3 px-2.5 py-1.5">
      <div className="w-40"><Select label="Sweep variable" value={m.mode} onChange={(v) => set("mode", v)}
        options={[{ value: "T", label: "Service temperature T" }, { value: "dC", label: "Moisture content" }]} /></div>
      <div className="w-24"><NumField label="From" unit={m.mode === "T" ? "°C" : "%"} value={m.start} onChange={(v) => set("start", v ?? 0)} min={m.mode === "T" ? -273 : 0} max={400} /></div>
      <div className="w-24"><NumField label="To" unit={m.mode === "T" ? "°C" : "%"} value={m.stop} onChange={(v) => set("stop", v ?? 0)} min={m.mode === "T" ? -273 : 0} max={400} /></div>
      <div className="w-20"><NumField label="Points" value={m.points} integer min={2} max={200} onChange={(v) => set("points", v ?? 30)} /></div>
      <div className="w-24"><NumField label="Plate a" unit="mm" value={m.plate_a} min={1} max={1e5} onChange={(v) => set("plate_a", v ?? 300)} /></div>
      <div className="w-24"><NumField label="Plate b" unit="mm" value={m.plate_b} min={1} max={1e5} onChange={(v) => set("plate_b", v ?? 300)} /></div>
      <span className="text-[10.5px] text-graphite-500">Stress-free T = {env.T_stress_free} °C (Inputs panel). Hot/wet knockdown {env.hotwet_knockdown ? "ON (estimate)" : "off"}.</span>
      <div className="ml-auto"><SolverNote s={s} what="hygrothermal analysis" /></div>
    </div>
  );
  if (!r) return <div className="flex flex-col gap-2">{ctrl}<div className="panel"><Empty>{s.error ?? "Computing…"}</Empty></div></div>;
  const sw = r.sweep;
  const xl = m.mode === "T" ? "Service temperature [°C]" : "Moisture content [% wt]";
  const rfS: Series[] = Object.entries(sw.rf).map(([c, v]) => ({ name: CRIT_LABEL[c as Criterion], color: CRIT_COLOR[c as Criterion],
    data: (v as (number | null)[]).map((y, i) => ({ x: sw.x[i], y: y as number })).filter((d) => d.y !== null) }));
  const resS: Series[] = [
    { name: "max σ2 (residual)", color: SERIES[1], data: sw.x.map((x: number, i: number) => ({ x, y: sw.max_sigma2_residual[i] })).filter((d: { y: number | null }) => d.y !== null) },
    { name: "max |τ12| (residual)", color: SERIES[2], data: sw.x.map((x: number, i: number) => ({ x, y: sw.max_tau12_residual[i] })).filter((d: { y: number | null }) => d.y !== null) },
  ];
  const curX = m.mode === "T" ? env.T_service : env.moisture;
  const res = r.residual;
  const resRows = res.sigma_12.map((pl: number[][], k: number) => ({ ply: `${k + 1}`, angle: a.laminate.plies[k].angle, s1: pl[0][0], s2: pl[0][1], t12: pl[0][2] }));
  const w = r.warpage;
  const symmetric = a.classification.symmetric_stiffness;
  const ret = r.retention_curves;
  const retS: Series[] = ret ? Object.entries(ret.curves).map(([M, v], i) => ({ name: `M = ${M} %`, color: SERIES[i],
    data: (v as (number | null)[]).map((y, j) => ({ x: ret.T[j], y: y as number })).filter((d) => d.y !== null) })) : [];
  const noThermal = r.dT === 0 && r.dC === 0;
  return (
    <div className="flex flex-col gap-2">
      {ctrl}
      <Warnings items={[...(sw.warnings ?? []), ...(noThermal ? ["ΔT = 0 and moisture = 0 at the current state: residual-stress plots show zero. Set the stress-free temperature (e.g. 177 °C) to include cure stresses."] : [])]} />
      <Grid>
        <ChartFrame title={`Reserve factor versus ${m.mode === "T" ? "temperature" : "moisture"}`} subtitle="applied mechanical load + residual state" classification={env.hotwet_knockdown ? "estimate" : "calculated"} illustrative={illustrative}
          csv={() => sw.x.map((x: number, i: number) => Object.fromEntries([["x", x], ...Object.entries(sw.rf).map(([c, v]) => [c, (v as number[])[i]])]))}>
          <XYPlot series={rfS} xLabel={xl} yLabel="RF (FPF)" height={260} refY={[{ value: 1, label: "RF = 1", color: "#b3372f" }, { value: a.fos, label: `FoS ${a.fos}`, color: "#8a5a05" }]}
            refX={[{ value: curX, label: "current" }]} />
        </ChartFrame>
        <ChartFrame title="Residual ply stress versus environment" subtitle="no mechanical load" classification={env.hotwet_knockdown ? "estimate" : "calculated"}
          csv={() => sw.x.map((x: number, i: number) => ({ x, max_sigma2_MPa: sw.max_sigma2_residual[i], max_tau12_MPa: sw.max_tau12_residual[i] }))}>
          <XYPlot series={resS} xLabel={xl} yLabel="Stress [MPa]" height={260} refX={[{ value: curX, label: "current" }]} refY={[{ value: 0, dashed: false, color: "#b9b3a3" }]} />
        </ChartFrame>
      </Grid>
      <Grid cols="xl:grid-cols-3">
        <ChartFrame title="Residual stresses by ply" subtitle={`material axes, ΔT = ${fmt(r.dT, 4)} °C, ΔC = ${r.dC} %`} classification="calculated" csv={() => resRows}>
          <BarPlot data={resRows} xKey="ply" bars={[{ key: "s1", name: "σ1", color: SERIES[0] }, { key: "s2", name: "σ2", color: SERIES[1] }, { key: "t12", name: "τ12", color: SERIES[2] }]} height={240} yLabel="MPa" refY={[{ value: 0 }]} />
        </ChartFrame>
        <ChartFrame title="Thermal warpage (free plate)" subtitle={`${m.plate_a} × ${m.plate_b} mm, corner deflection ${fmt(w.max_abs_w, 4)} mm`} classification={symmetric ? "calculated" : "estimate"}
          csv={() => w.w.flatMap((row: number[], j: number) => row.map((v, i) => ({ x_mm: w.x[i], y_mm: w.y[j], w_mm: v })))}
          note={w.warning ?? "Symmetric laminate: zero warpage by symmetry (B = 0)."}>
          {symmetric && w.max_abs_w < 1e-12 ? <Empty>No hygrothermal warpage: B = 0 for this symmetric laminate.</Empty>
            : <FieldContour x={w.x} y={w.y} w={w.w} xLabel="x [mm]" yLabel="y [mm]" unit="mm" />}
        </ChartFrame>
        <ChartFrame title="Hot/wet matrix-property retention" subtitle={ret ? `Chamis (1984), dry Tg ${ret.Tg_dry} °C` : ""} classification="estimate"
          csv={() => ret ? ret.T.map((T: number, i: number) => Object.fromEntries([["T_C", T], ...Object.entries(ret.curves).map(([k, v]) => [`M_${k}`, (v as number[])[i]])])) : []}
          note="Empirical estimate for matrix-dominated properties (E2, G12, Yt, Yc, S12). Replace with ETW/CTD test data where available.">
          {ret ? <XYPlot series={retS} xLabel="Temperature [°C]" yLabel="P / P₀" height={230} yDomain={[0, 1.05]} />
            : <Empty>Unavailable: dry Tg is not in the material record (needed for the Chamis estimate).</Empty>}
        </ChartFrame>
      </Grid>
    </div>
  );
}
