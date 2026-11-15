"use client";
// AeroLaminate Pro - uncertainty, sensitivity, parametric sweep and fatigue screening. Author: Anwesh Ajitabh Dash.
import { useState } from "react";
import ChartFrame, { Empty } from "@/components/ChartFrame";
import { NumField, Select, critOptions } from "@/components/inputs";
import { BarPlot, XYPlot, type Series } from "@/components/Plots";
import { CRIT_COLOR, CRIT_LABEL, SERIES, fmt } from "@/lib/project";
import type { Criterion } from "@/lib/types";
import { useSolver } from "@/lib/useSolver";
import { Grid, KV, SolverNote, Warnings, type TabProps } from "./common";

export default function DurabilityTab({ project, setProject, analysis: a, active, illustrative }: TabProps) {
  const uq = project.modules.uq, pm = project.modules.parametric, fa = project.modules.fatigue;
  const [metric, setMetric] = useState<"RF" | "Ex" | "Ey" | "Gxy" | "D11">("RF");
  const hotwet = project.payload.environment.hotwet_knockdown;
  const su = useSolver("uncertainty", { project: project.payload, ...uq }, active && !!a && !hotwet, 600);
  const sp = useSolver("parametric", { project: project.payload, ...pm }, active && !!a && pm.vary_plies.length > 0);
  const sf = useSolver("fatigue", { project: project.payload, ...fa }, active && !!a && fa.blocks.length > 0);
  const setM = <K extends "uq" | "parametric" | "fatigue">(mod: K, k: string, v: unknown) =>
    setProject((p) => ({ ...p, modules: { ...p.modules, [mod]: { ...p.modules[mod], [k]: v } } }));
  const mc = su.data?.monte_carlo, sens = su.data?.sensitivity;
  const hist = mc ? mc.histogram.counts.map((c: number, i: number) => ({ bin: fmt((mc.histogram.edges[i] + mc.histogram.edges[i + 1]) / 2, 3), count: c })) : [];
  const tor = sens ? [...sens.rows].filter((r: Record<string, number | null>) => r[metric] !== null)
    .sort((x: Record<string, number>, y: Record<string, number>) => Math.abs(y[metric]) - Math.abs(x[metric]))
    .map((r: Record<string, number | string>) => ({ p: r.parameter, v: r[metric] })) : [];
  const pr = sp.data;
  const prRF: Series[] = pr ? Object.entries(pr.rf).map(([c, v]) => ({ name: CRIT_LABEL[c as Criterion], color: CRIT_COLOR[c as Criterion],
    data: (v as (number | null)[]).map((y, i) => ({ x: pr.theta[i], y: y as number })).filter((d) => d.y !== null) })) : [];
  const prE: Series[] = pr ? [
    { name: "Ex", color: SERIES[0], data: pr.theta.map((t: number, i: number) => ({ x: t, y: pr.Ex[i] / 1000 })) },
    { name: "Ey", color: SERIES[1], data: pr.theta.map((t: number, i: number) => ({ x: t, y: pr.Ey[i] / 1000 })) },
    { name: "Gxy", color: SERIES[2], data: pr.theta.map((t: number, i: number) => ({ x: t, y: pr.Gxy[i] / 1000 })) },
  ] : [];
  const f = sf.data;
  const nply = project.payload.plies.length;
  const toggleVary = (i: number) => setM("parametric", "vary_plies", pm.vary_plies.includes(i) ? pm.vary_plies.filter((x) => x !== i) : [...pm.vary_plies, i].sort((x, y) => x - y));
  const covKeys = ["E1", "E2", "G12", "nu12", "Xt", "Xc", "Yt", "Yc", "S12"];
  return (
    <div className="flex flex-col gap-2">
      <div className="panel flex flex-wrap items-end gap-2 px-2.5 py-1.5">
        <div className="w-32"><Select label="Criterion" value={uq.criterion} onChange={(v) => setM("uq", "criterion", v)} options={critOptions()} /></div>
        <div className="w-20"><NumField label="Samples" value={uq.samples} integer min={10} max={5000} onChange={(v) => setM("uq", "samples", v ?? 400)} /></div>
        <div className="w-16"><NumField label="Seed" value={uq.seed} integer min={0} max={1e9} onChange={(v) => setM("uq", "seed", v ?? 1)} /></div>
        <div className="w-24"><Select label="Distribution" value={uq.distribution} onChange={(v) => setM("uq", "distribution", v)} options={[{ value: "normal", label: "Normal" }, { value: "lognormal", label: "Log-normal" }]} /></div>
        {covKeys.map((k) => <div key={k} className="w-14"><NumField label={`CoV ${k}`} value={uq.cov[k] ?? 0} min={0} max={0.5} onChange={(v) => setM("uq", "cov", { ...uq.cov, [k]: v ?? 0 })} /></div>)}
        <div className="ml-auto"><SolverNote s={su} what="uncertainty" /></div>
      </div>
      {hotwet && <Warnings items={["Uncertainty analysis is disabled while the hot/wet knockdown is active (enter conditioned properties instead)."]} />}
      <Grid cols="xl:grid-cols-[1.3fr_1fr_1fr]">
        <ChartFrame title="Monte Carlo: FPF reserve factor distribution" subtitle={mc ? `${mc.n} samples, ${CRIT_LABEL[mc.criterion as Criterion]}` : ""} classification="screening" illustrative={illustrative}
          csv={() => hist} note="Assumed CoVs, independent normal/log-normal properties, one material lot per sample. NOT CMH-17 A/B-basis allowables; the fraction RF < 1 is not a certified failure probability.">
          {mc ? <BarPlot data={hist} xKey="bin" xLabel="RF" bars={[{ key: "count", name: "Samples", color: SERIES[0] }]} height={230} legend={false} /> : <Empty>{su.error ?? "Computing…"}</Empty>}
        </ChartFrame>
        <ChartFrame title="Statistics" classification="screening" csv={() => mc ? Object.entries(mc.percentiles).map(([k, v]) => ({ statistic: k, rf: v as number })) : []}>
          {mc && <KV rows={[["Mean RF", fmt(mc.mean, 4), ""], ["Std. dev.", fmt(mc.std, 4), ""], ["CoV", fmt(mc.std / mc.mean, 3), ""],
            ["1st percentile", fmt(mc.percentiles.p1, 4), ""], ["10th percentile", fmt(mc.percentiles.p10, 4), ""], ["Median", fmt(mc.percentiles.p50, 4), ""],
            ["Fraction RF < 1", `${fmt(100 * mc.fraction_rf_below_1, 3)} %`, ""], ["95 % CI (Wilson)", `${fmt(100 * mc.fraction_ci95[0], 3)} – ${fmt(100 * mc.fraction_ci95[1], 3)} %`, ""],
            ["Rejected (non-physical)", mc.rejected, ""]]} />}
        </ChartFrame>
        <ChartFrame title="Sensitivity (tornado)" subtitle={`∂ln(${metric})/∂ln(x), ±${(uq.rel_step * 100).toFixed(0)} %`} classification="calculated"
          actions={<select className="inp mr-1 !h-[18px] !w-16 !text-[10px]" value={metric} onChange={(e) => setMetric(e.target.value as typeof metric)}>
            {["RF", "Ex", "Ey", "Gxy", "D11"].map((k) => <option key={k}>{k}</option>)}</select>}
          csv={() => sens ? sens.rows : []}>
          {sens ? <BarPlot data={tor} xKey="p" horizontal bars={[{ key: "v", name: "Normalised sensitivity", color: SERIES[0] }]} height={240} refY={[{ value: 0 }]} legend={false}
            cellColor={(r) => ((r.v as number) < 0 ? SERIES[1] : SERIES[0])} /> : <Empty>—</Empty>}
        </ChartFrame>
      </Grid>
      <div className="panel flex flex-wrap items-end gap-2 px-2.5 py-1.5">
        <span className="lbl">Parametric ±θ sweep — plies varied:</span>
        <div className="flex flex-wrap gap-0.5">{Array.from({ length: nply }, (_, k) => k + 1).map((i) =>
          <button key={i} className={`btn !px-1.5 ${pm.vary_plies.includes(i) ? "btn-primary" : ""}`} onClick={() => toggleVary(i)}>{i}</button>)}</div>
        <div className="w-16"><NumField label="θ from" value={pm.start} min={-90} max={90} onChange={(v) => setM("parametric", "start", v ?? 0)} /></div>
        <div className="w-16"><NumField label="θ to" value={pm.stop} min={-90} max={90} onChange={(v) => setM("parametric", "stop", v ?? 90)} /></div>
        <div className="w-16"><NumField label="Step" value={pm.step} min={0.5} max={45} onChange={(v) => setM("parametric", "step", v ?? 5)} /></div>
        <span className="text-[10.5px] text-graphite-500">Selected plies take angle ±θ (their current sign is kept).</span>
        <div className="ml-auto"><SolverNote s={sp} what="parametric sweep" /></div>
      </div>
      <Grid>
        <ChartFrame title="Reserve factor versus ply angle θ" classification="calculated" illustrative={illustrative}
          csv={() => pr ? pr.theta.map((t: number, i: number) => Object.fromEntries([["theta", t], ...Object.entries(pr.rf).map(([c, v]) => [c, (v as number[])[i]])])) : []}>
          {pr ? <XYPlot series={prRF} xLabel="θ [deg]" yLabel="RF (FPF)" height={240} refY={[{ value: a?.fos ?? 1.5, label: "FoS", color: "#8a5a05" }]} /> : <Empty>Select plies to vary.</Empty>}
        </ChartFrame>
        <ChartFrame title="In-plane stiffness versus ply angle θ" classification="calculated"
          csv={() => pr ? pr.theta.map((t: number, i: number) => ({ theta: t, Ex: pr.Ex[i], Ey: pr.Ey[i], Gxy: pr.Gxy[i], nuxy: pr.nuxy[i], D11: pr.D11[i] })) : []}>
          {pr ? <XYPlot series={prE} xLabel="θ [deg]" yLabel="Modulus [GPa]" height={240} /> : <Empty>Select plies to vary.</Empty>}
        </ChartFrame>
      </Grid>
      <FatiguePanel fa={fa} f={f} sf={sf} setM={setM} />
    </div>
  );
}

function FatiguePanel({ fa, f, sf, setM }: { fa: TabProps["project"]["modules"]["fatigue"]; f: ReturnType<typeof useSolver>["data"]; sf: ReturnType<typeof useSolver>; setM: (mod: "fatigue", k: string, v: unknown) => void }) {
  const blocks = fa.blocks;
  const sn: Series[] = f ? [{ name: "User S-N curve", color: SERIES[0], data: f.sn_curve.N.map((n: number, i: number) => ({ x: Math.log10(n), y: f.sn_curve.S[i] })) }] : [];
  const pts = f ? f.blocks.filter((b: { N_allow: number | null }) => b.N_allow).map((b: { S: number; cycles: number; block: number }) => ({ x: Math.log10(Math.max(b.cycles, 1)), y: b.S, label: `B${b.block}`, color: "#d69214" })) : [];
  return (
    <ChartFrame title="Fatigue screening (user S-N + Miner)" classification="screening"
      subtitle="no fatigue data are shipped — enter test-derived S-N parameters"
      csv={() => f ? f.blocks : []} note="S = peak load / static failure load (FPF RF basis or user value). R-ratio and environment must match the S-N data. Miner's rule ignores sequence effects; D < 1 does not demonstrate fatigue life.">
      <div className="grid grid-cols-1 gap-3 xl:grid-cols-[1fr_1.2fr]">
        <div className="flex flex-col gap-1.5">
          <div className="grid grid-cols-4 gap-1.5">
            <Select label="S-N model" value={fa.model} onChange={(v) => setM("fatigue", "model", v)} options={[{ value: "loglinear", label: "S = 1 − b log N" }, { value: "power", label: "S = A N^(−1/k)" }]} />
            {fa.model === "loglinear" ? <NumField label="b" value={fa.params.b ?? 0.1} min={1e-4} max={1} onChange={(v) => setM("fatigue", "params", { ...fa.params, b: v ?? 0.1 })} />
              : <><NumField label="A" value={fa.params.A ?? 1} min={1e-4} max={10} onChange={(v) => setM("fatigue", "params", { ...fa.params, A: v ?? 1 })} />
                <NumField label="k" value={fa.params.k ?? 12} min={0.1} max={200} onChange={(v) => setM("fatigue", "params", { ...fa.params, k: v ?? 12 })} /></>}
            <NumField label="R-ratio" value={fa.R_ratio} min={-10} max={10} onChange={(v) => setM("fatigue", "R_ratio", v ?? 0.1)} title="Recorded for traceability: must match the S-N test data" />
          </div>
          <table className="tbl"><thead><tr><th>Block</th><th>Load factor (× applied)</th><th>Cycles</th><th></th></tr></thead><tbody>
            {blocks.map((b, i) => <tr key={i}><td>{i + 1}</td>
              <td><NumField value={b.load_factor} min={0} max={100} onChange={(v) => setM("fatigue", "blocks", blocks.map((x, k) => k === i ? { ...x, load_factor: v ?? 0 } : x))} /></td>
              <td><NumField value={b.cycles} min={0} max={1e12} onChange={(v) => setM("fatigue", "blocks", blocks.map((x, k) => k === i ? { ...x, cycles: v ?? 0 } : x))} /></td>
              <td><button className="text-graphite-500 hover:text-bad" onClick={() => setM("fatigue", "blocks", blocks.filter((_, k) => k !== i))}>✕</button></td></tr>)}
          </tbody></table>
          <div className="flex gap-1"><button className="btn" onClick={() => setM("fatigue", "blocks", [...blocks, { load_factor: 0.5, cycles: 1e5 }])}>+ block</button>
            <SolverNote s={sf} what="fatigue" /></div>
          {f && <KV rows={[["Static RF basis", `${fmt(f.static_rf, 4)} (${f.static_basis})`, ""], ["Miner damage D", fmt(f.damage, 4), ""], ["D < 1", f.passes ? "yes (screening)" : "NO", ""]]} />}
        </div>
        {f ? <XYPlot series={sn} xLabel="log₁₀ N [cycles]" yLabel="S = σmax/σult" height={220} points={pts} yDomain={[0, 1.05]} />
          : <Empty>Add a load block to evaluate the spectrum against the S-N curve.</Empty>}
      </div>
    </ChartFrame>
  );
}
