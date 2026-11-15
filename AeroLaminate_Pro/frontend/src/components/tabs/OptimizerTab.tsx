"use client";
// AeroLaminate Pro - constrained stacking-sequence optimiser tab. Author: Anwesh Ajitabh Dash.
import ChartFrame, { Empty } from "@/components/ChartFrame";
import { NumField, Select, Toggle, critOptions } from "@/components/inputs";
import { BarPlot, XYPlot, type Series } from "@/components/Plots";
import { formatLayup } from "@/lib/layup";
import { BASELINE, SERIES, fmt } from "@/lib/project";
import { useAction } from "@/lib/useSolver";
import { Grid, Warnings, type TabProps } from "./common";

interface Cand { layup: number[]; n_plies: number; rf: number; mass: number | null; Ex: number; Ey: number; Gxy: number; buckling?: number | null; objective: number; rank?: number; reasoning?: string }

export default function OptimizerTab({ project, setProject, analysis: a, illustrative }: TabProps) {
  const o = project.modules.opt as Record<string, number | boolean | string | number[]>;
  const act = useAction("optimize");
  const set = (k: string, v: number | boolean | string | number[]) => setProject((p) => ({ ...p, modules: { ...p.modules, opt: { ...p.modules.opt, [k]: v } } }));
  const body = { project: project.payload, ...o, max_mass: (o.max_mass as number) > 0 ? o.max_mass : null };
  const stale = act.data && act.key !== JSON.stringify(body);
  const r = act.data;
  const num = (k: string, label: string, p: { min?: number; max?: number; unit?: string; integer?: boolean; title?: string } = {}) =>
    <div className="w-[88px]"><NumField label={label} value={o[k] as number} onChange={(v) => set(k, v ?? 0)} {...p} /></div>;
  const conv: Series[] = r ? [
    { name: "Best feasible objective", color: SERIES[0], points: true, data: r.history.filter((h: { best_objective: number | null }) => h.best_objective !== null).map((h: { generation: number; best_objective: number }) => ({ x: h.generation, y: h.best_objective })) },
    { name: "Population mean (feasible)", color: SERIES[1], data: r.history.filter((h: { mean_objective: number | null }) => h.mean_objective !== null).map((h: { generation: number; mean_objective: number }) => ({ x: h.generation, y: h.mean_objective })) },
  ] : [];
  const feasN: Series[] = r ? [{ name: "Feasible in population", color: SERIES[2], data: r.history.map((h: { generation: number; n_feasible: number }) => ({ x: h.generation, y: h.n_feasible })) }] : [];
  const par: Series[] = r ? [
    { name: "Pareto front (feasible, non-dominated)", color: SERIES[0], points: true, data: r.pareto.map((c: Cand) => ({ x: c.mass ?? c.n_plies, y: c.rf, layup: formatLayup(c.layup) })) },
    { name: "Top-ranked", color: SERIES[3], line: false, data: r.ranked.map((c: Cand) => ({ x: c.mass ?? c.n_plies, y: c.rf, layup: formatLayup(c.layup) })) },
  ] : [];
  const basePt = r?.baseline ? [{ x: r.baseline.mass ?? r.baseline.n_plies, y: r.baseline.rf ?? 0, label: "current", color: BASELINE }] : [];
  const viol = r ? Object.entries(r.violation_counts).map(([k, v]) => ({ c: k.replace(/_/g, " "), n: v as number })) : [];
  const best: Cand | undefined = r?.ranked?.[0];
  const cmp = best && r.baseline ? ["rf", "mass", "Ex", "Ey", "Gxy", "n_plies"].map((k) => ({
    q: k, current: 1, best: (r.baseline[k] ? (best as unknown as Record<string, number>)[k] / r.baseline[k] : null) })) : [];
  const apply = (c: Cand) => setProject((p) => ({ ...p, payload: { ...p.payload, plies: c.layup.map((angle) => ({ angle })) } }));
  return (
    <div className="flex flex-col gap-2">
      <div className="panel flex flex-col gap-1.5 px-2.5 py-2">
        <div className="flex flex-wrap items-end gap-2">
          <div className="w-36"><label className="flex flex-col gap-[2px]"><span className="lbl">Allowed angles [°]</span>
            <input className="inp" defaultValue={(o.angles as number[]).join(", ")} onBlur={(e) => {
              const v = e.target.value.split(/[,\s]+/).filter(Boolean).map(Number);
              if (v.length && v.every((x) => Number.isFinite(x) && Math.abs(x) <= 90)) set("angles", v);
            }} /></label></div>
          {num("min_plies", "Min plies", { integer: true, min: 1, max: 200 })}{num("max_plies", "Max plies", { integer: true, min: 1, max: 200 })}
          <div className="w-28"><Select label="Strength criterion" value={o.criterion as "tsai_wu"} onChange={(v) => set("criterion", v)} options={critOptions()} /></div>
          {num("rf_min", "Min RF", { min: 0.01, max: 100, title: "Required first-ply-failure reserve factor (e.g. the factor of safety)" })}
          {num("min_Ex", "Min Ex", { unit: "MPa", min: 0 })}{num("min_Ey", "Min Ey", { unit: "MPa", min: 0 })}{num("min_Gxy", "Min Gxy", { unit: "MPa", min: 0 })}
          {num("max_mass", "Max mass", { unit: "kg/m²", min: 0, title: "0 = no limit" })}
          {num("min_fraction", "Min fraction", { min: 0, max: 0.33, title: "10 % rule: each of 0/±45/90 ≥ fraction" })}
          {num("max_consecutive", "Max consec.", { integer: true, min: 0, max: 50, title: "0 = not enforced" })}
        </div>
        <div className="flex flex-wrap items-end gap-2">
          <Toggle checked={!!o.symmetric} onChange={(v) => set("symmetric", v)} label="Symmetric" />
          <Toggle checked={!!o.balanced} onChange={(v) => set("balanced", v)} label="Balanced (±θ pairs)" />
          <Toggle checked={!!o.outer_45} onChange={(v) => set("outer_45", v)} label="±45 outer plies" />
          <Toggle checked={!!o.buckling} onChange={(v) => set("buckling", v)} label="Buckling constraint (SS plate)" />
          {o.buckling && <>{num("plate_a", "Plate a", { unit: "mm", min: 1 })}{num("plate_b", "Plate b", { unit: "mm", min: 1 })}{num("buckling_min", "Min λcr", { min: 0.01 })}</>}
          <span className="lbl ml-2">Objective weights</span>
          {num("w_mass", "Mass", { min: 0, max: 100 })}{num("w_fi", "1/RF", { min: 0, max: 100 })}{num("w_coupling", "Coupling", { min: 0, max: 100 })}{o.buckling && num("w_buckling", "1/λcr", { min: 0, max: 100 })}
          {num("pop", "Population", { integer: true, min: 4, max: 400 })}{num("generations", "Generations", { integer: true, min: 1, max: 500 })}{num("seed", "Seed", { integer: true, min: 0 })}
          <button className="btn btn-primary ml-auto h-[26px] px-4" disabled={act.loading} onClick={() => act.run(body)}>{act.loading ? "Running…" : "Run optimiser"}</button>
        </div>
        <p className="text-[10.5px] text-graphite-500">Genetic algorithm with Deb feasibility rules; ply thickness and material from ply 1; loads and environment from the Inputs panel. Heuristic search: no global-optimality guarantee. Runs on request (expensive).</p>
        {act.error && <div className="text-[11px] text-bad">⚠ {act.error}</div>}
        {r?.flags?.length ? <Warnings items={r.flags} /> : null}
        {stale && <div className="text-[11px] text-warn">▲ Inputs changed since this run: results are stale. Re-run to update.</div>}
      </div>
      {!r ? <div className="panel"><Empty>Configure constraints and objectives, then run the optimiser.</Empty></div> : <>
        <Grid cols="xl:grid-cols-3">
          <ChartFrame title="Convergence" subtitle={`${r.n_evaluated} unique designs evaluated, ${r.n_feasible} feasible`} classification="calculated"
            csv={() => r.history}>
            <XYPlot series={conv} xLabel="Generation" yLabel="Objective (lower is better)" height={220} />
          </ChartFrame>
          <ChartFrame title="Pareto front: mass vs reserve factor" classification="calculated" illustrative={illustrative}
            csv={() => r.pareto.map((c: Cand) => ({ layup: formatLayup(c.layup), mass: c.mass, rf: c.rf, n_plies: c.n_plies }))}>
            <XYPlot series={par} xLabel={r.pareto[0]?.mass !== null ? "Areal mass [kg/m²]" : "Plies"} yLabel="RF (FPF)" height={220} points={basePt}
              refY={[{ value: o.rf_min as number, label: "min RF", color: "#8a5a05" }]} tooltipExtra={(p) => <div>{String(p.layup ?? "")}</div>} />
          </ChartFrame>
          <ChartFrame title="Constraint violations (all evaluated)" subtitle="count of designs violating each constraint" classification="calculated" csv={() => viol}>
            {viol.length ? <BarPlot data={viol} xKey="c" horizontal bars={[{ key: "n", name: "Designs", color: SERIES[1] }]} height={220} legend={false} /> : <Empty>No violations recorded.</Empty>}
          </ChartFrame>
        </Grid>
        <Grid cols="xl:grid-cols-[2fr_1fr]">
          <ChartFrame title="Ranked candidate layups" subtitle={r.classification} classification="calculated"
            csv={() => r.ranked.map((c: Cand) => ({ rank: c.rank, layup: formatLayup(c.layup), plies: c.n_plies, rf: c.rf, mass: c.mass, Ex: c.Ex, Ey: c.Ey, Gxy: c.Gxy, buckling: c.buckling, objective: c.objective, reasoning: c.reasoning }))}>
            {r.ranked.length ? <div className="max-h-[300px] overflow-auto"><table className="tbl"><thead><tr><th>#</th><th>Layup</th><th className="num">n</th><th className="num">RF</th><th className="num">Mass</th>
              <th className="num">Ex [GPa]</th><th className="num">Gxy [GPa]</th>{o.buckling && <th className="num">λcr</th>}<th>Reasoning</th><th></th></tr></thead>
              <tbody>{r.ranked.map((c: Cand) => <tr key={c.rank}><td>{c.rank}</td><td>{formatLayup(c.layup)}</td><td className="num">{c.n_plies}</td><td className="num">{fmt(c.rf, 4)}</td>
                <td className="num">{fmt(c.mass, 4)}</td><td className="num">{fmt(c.Ex / 1000, 4)}</td><td className="num">{fmt(c.Gxy / 1000, 4)}</td>{o.buckling && <td className="num">{fmt(c.buckling, 3)}</td>}
                <td className="font-sans text-[10.5px]">{c.reasoning}</td><td><button className="btn" onClick={() => apply(c)}>Apply</button></td></tr>)}</tbody></table></div>
              : <div><Empty>No feasible design found. Relax constraints (ply count, minimum RF) or allow more angles.</Empty>
                <Warnings items={r.infeasible_examples.map((c: Cand & { violations: Record<string, number> }) => `${formatLayup(c.layup)}: violates ${Object.keys(c.violations).join(", ")}`)} /></div>}
          </ChartFrame>
          <ChartFrame title="Best vs current design" subtitle="ratio to current layup" classification="calculated" csv={() => cmp as never}>
            {cmp.length ? <BarPlot data={cmp} xKey="q" bars={[{ key: "current", name: "Current", color: BASELINE }, { key: "best", name: "Rank 1", color: SERIES[0] }]} height={220} refY={[{ value: 1 }]} />
              : <Empty>—</Empty>}
            <XYPlot series={feasN} xLabel="Generation" yLabel="Feasible count" height={120} legend={false} />
          </ChartFrame>
        </Grid>
        <p className="text-[10.5px] text-graphite-500">Objective = {r.objective_definition}. Trade-off: moving along the Pareto front buys reserve factor with mass; the ranked list applies your weights.</p>
      </>}
      {!a && null}
    </div>
  );
}
