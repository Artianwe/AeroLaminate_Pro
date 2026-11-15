"use client";
// AeroLaminate Pro - progressive failure tab. Author: Anwesh Ajitabh Dash.
import ChartFrame, { Empty } from "@/components/ChartFrame";
import { NumField, Select } from "@/components/inputs";
import { BarPlot, XYPlot, type Series } from "@/components/Plots";
import { CRIT_COLOR, CRIT_LABEL, SERIES, fmt } from "@/lib/project";
import type { Criterion } from "@/lib/types";
import { useSolver } from "@/lib/useSolver";
import { Grid, KV, SolverNote, Warnings, type TabProps } from "./common";

const MODE_CRIT: Criterion[] = ["hashin", "puck", "larc03", "max_stress", "max_strain"];

export default function ProgressiveTab({ project, setProject, analysis: a, active, illustrative }: TabProps) {
  const m = project.modules.pfa;
  const L = project.payload.loads;
  const hasLoad = [L.Nx, L.Ny, L.Nxy, L.Mx, L.My, L.Mxy].some((v) => v !== 0);
  const s = useSolver("progressive", { project: project.payload, ...m }, active && !!a && hasLoad);
  const set = (k: keyof typeof m, v: unknown) => setProject((p) => ({ ...p, modules: { ...p.modules, pfa: { ...p.modules.pfa, [k]: v } } }));
  const r = s.data;
  const ctrl = (
    <div className="panel flex flex-wrap items-end gap-3 px-2.5 py-1.5">
      <div className="w-36"><Select label="Criterion (mode-based)" value={m.criterion} onChange={(v) => set("criterion", v)}
        options={MODE_CRIT.map((c) => ({ value: c, label: CRIT_LABEL[c] }))} /></div>
      <div className="w-28"><NumField label="Fibre discount d_f" value={m.d_fibre} min={1e-6} max={1} onChange={(v) => set("d_fibre", v ?? 0.01)} title="Retention of E1, E2, G12, ν12 after fibre failure" /></div>
      <div className="w-28"><NumField label="Matrix discount d_m" value={m.d_matrix} min={1e-6} max={1} onChange={(v) => set("d_matrix", v ?? 0.2)} title="Retention of E2, G12, ν12 after matrix failure" /></div>
      <span className="max-w-[520px] text-[10.5px] text-graphite-500">Ply-discount under proportional loading of the applied mechanical load (hygrothermal state held). Discount factors are modelling choices; results are sensitive to them.</span>
      <div className="ml-auto"><SolverNote s={s} what="progressive failure" /></div>
    </div>
  );
  if (!hasLoad) return <div className="flex flex-col gap-2">{ctrl}<div className="panel"><Empty>Progressive failure needs a non-zero mechanical load (N or M).</Empty></div></div>;
  if (!r) return <div className="flex flex-col gap-2">{ctrl}<div className="panel"><Empty>{s.error ?? "Computing…"}</Empty></div></div>;
  // A post-collapse point (laminate compliance ~1/d_f) is orders of magnitude off-scale: omit it from the plot, keep it in the CSV.
  const sc = r.response_label.startsWith("kappa") ? 1e3 : 1e6;
  const pre = Math.max(...r.curve.filter((p: { event: string }) => p.event !== "post-degradation").map((p: { response: number }) => Math.abs(p.response)), 1e-30);
  const plotted = r.curve.filter((p: { response: number }) => Math.abs(p.response) <= 5 * pre);
  const omitted = r.curve.length - plotted.length;
  const curve: Series[] = [{ name: "Load path", color: SERIES[0], points: true, data: plotted.map((p: { load: number; response: number; event: string }) => ({ x: p.response * sc, y: p.load, event: p.event })) }];
  const refs = [{ value: r.fpf_load_factor, label: `FPF ${fmt(r.fpf_load_factor, 3)}`, color: "#8a5a05" }];
  if (r.lpf_load_factor) refs.push({ value: r.lpf_load_factor, label: `LPF ${fmt(r.lpf_load_factor, 3)}`, color: "#b3372f" });
  const steps = r.steps as { step: number; load_factor: number; failed: { ply: number; mode: string; angle: number }[]; n_fibre_failed: number; n_matrix_failed: number; stiffness_ratio: number; Ex: number | null; Ey: number | null; Gxy: number | null; ply_state: string[]; converged: boolean }[];
  const ex0 = a?.engineering_constants;
  const stiff: Series[] = ex0 ? [
    { name: "Ex/Ex₀", color: SERIES[0], points: true, data: [{ x: 0, y: 1 }, ...steps.filter((t) => t.Ex).map((t) => ({ x: t.load_factor, y: (t.Ex as number) / ex0.Ex }))] },
    { name: "Ey/Ey₀", color: SERIES[1], points: true, data: [{ x: 0, y: 1 }, ...steps.filter((t) => t.Ey).map((t) => ({ x: t.load_factor, y: (t.Ey as number) / ex0.Ey }))] },
    { name: "Gxy/Gxy₀", color: SERIES[2], points: true, data: [{ x: 0, y: 1 }, ...steps.filter((t) => t.Gxy).map((t) => ({ x: t.load_factor, y: (t.Gxy as number) / ex0.Gxy }))] },
    { name: "Secant (load dir.)", color: SERIES[6], points: true, data: [{ x: 0, y: 1 }, ...steps.map((t) => ({ x: t.load_factor, y: t.stiffness_ratio }))] },
  ] : [];
  const counts = steps.map((t) => ({ step: `${t.step} (${fmt(t.load_factor, 3)})`, fibre: t.failed.filter((f) => ["FT", "FC"].includes(f.mode)).length, matrix: t.failed.filter((f) => !["FT", "FC"].includes(f.mode)).length }));
  const fi = r.fi_vs_load;
  const fiSeries: Series[] = Object.entries(fi.fi).map(([c, v]) => ({ name: CRIT_LABEL[c as Criterion], color: CRIT_COLOR[c as Criterion], data: (v as number[]).map((y, i) => ({ x: fi.load_factor[i], y })) }));
  const nply = steps[0]?.ply_state.length ?? 0;
  return (
    <div className="flex flex-col gap-2">
      {ctrl}
      <Grid cols="xl:grid-cols-[2fr_1fr]">
        <ChartFrame title="Load factor versus response" subtitle={`dominant component ${r.response_label}`} classification="screening" illustrative={illustrative}
          csv={() => r.curve.map((p: { load: number; response: number; event: string }) => ({ load_factor: p.load, [r.response_label]: p.response, event: p.event }))}
          note={`Horizontal jumps at constant load are stiffness loss after ply discount.${omitted ? ` ${omitted} post-collapse point(s) off-scale, omitted from the plot (included in CSV).` : ""}`}>
          <XYPlot series={curve} xLabel={`${r.response_label} [${r.response_label.startsWith("kappa") ? "1/m" : "µε"}]`} yLabel="Load factor λ" height={280} refY={refs}
            tooltipExtra={(p) => <div>{String(p.event)}</div>} />
        </ChartFrame>
        <ChartFrame title="Summary" classification="screening">
          <KV rows={[["FPF load factor", fmt(r.fpf_load_factor, 5), "×"], ["LPF load factor", r.lpf_load_factor ? fmt(r.lpf_load_factor, 5) : "not reached", "×"],
            ["LPF / FPF", r.lpf_load_factor ? fmt(r.lpf_load_factor / r.fpf_load_factor, 4) : "—", ""], ["Steps", steps.length, ""],
            ["Termination", r.lpf_reason, ""], ["d_f / d_m", `${r.degradation.d_fibre} / ${r.degradation.d_matrix}`, ""]]} />
          <div className="mt-1"><Warnings items={[...r.notes, ...(steps.some((t) => !t.converged) ? ["An equilibrium iteration did not converge"] : [])]} /></div>
        </ChartFrame>
      </Grid>
      <Grid cols="xl:grid-cols-3">
        <ChartFrame title="Failure index versus load factor" subtitle="pristine laminate" classification="calculated"
          csv={() => fi.load_factor.map((l: number, i: number) => Object.fromEntries([["load_factor", l], ...Object.entries(fi.fi).map(([c, v]) => [c, (v as number[])[i]])]))}>
          <XYPlot series={fiSeries} xLabel="Load factor λ" yLabel="max FI" height={240} refY={[{ value: 1, label: "FI = 1", color: "#b3372f" }]} refX={refs.slice(0, 1)} />
        </ChartFrame>
        <ChartFrame title="Residual laminate stiffness" subtitle="after each degradation step" classification="screening"
          csv={() => steps.map((t) => ({ load_factor: t.load_factor, Ex: t.Ex, Ey: t.Ey, Gxy: t.Gxy, secant_ratio: t.stiffness_ratio }))}>
          <XYPlot series={stiff} xLabel="Load factor λ" yLabel="Stiffness ratio" height={240} yDomain={[0, 1.05]} />
        </ChartFrame>
        <ChartFrame title="Plies failed per step" classification="screening" csv={() => counts}>
          <BarPlot data={counts} xKey="step" stacked bars={[{ key: "fibre", name: "Fibre", color: "#b3372f" }, { key: "matrix", name: "Matrix", color: "#d69214" }]} height={240} yLabel="Ply failures" />
        </ChartFrame>
      </Grid>
      <ChartFrame title="Damage progression map" subtitle="ply state after each step (M matrix, F fibre)" classification="screening"
        csv={() => steps.map((t) => Object.fromEntries([["step", t.step], ["load_factor", t.load_factor], ...t.ply_state.map((v, i) => [`ply_${i + 1}`, v])]))}>
        <div className="overflow-auto">
          <table className="tbl w-auto">
            <thead><tr><th>Step</th><th className="num">λ</th>{Array.from({ length: nply }, (_, i) => <th key={i} className="text-center">{i + 1}</th>)}<th>New failures</th></tr></thead>
            <tbody>{steps.map((t) => <tr key={t.step}><td>{t.step}</td><td className="num">{fmt(t.load_factor, 4)}</td>
              {t.ply_state.map((v, i) => <td key={i} className="text-center" style={{ background: v === "F" ? "#b3372f55" : v === "M" ? "#d6921455" : undefined }}>{v}</td>)}
              <td className="font-sans text-[10.5px]">{t.failed.map((f) => `${f.ply}(${f.angle}°) ${f.mode}`).join(", ")}</td></tr>)}</tbody>
          </table>
        </div>
      </ChartFrame>
    </div>
  );
}
