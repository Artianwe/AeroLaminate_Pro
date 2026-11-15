"use client";
// AeroLaminate Pro - plate buckling tab. Author: Anwesh Ajitabh Dash.
import ChartFrame, { Empty } from "@/components/ChartFrame";
import { FieldContour } from "@/components/Graphics";
import { NumField } from "@/components/inputs";
import { XYPlot } from "@/components/Plots";
import { SERIES, fmt } from "@/lib/project";
import { useSolver } from "@/lib/useSolver";
import { Grid, KV, SolverNote, Warnings, type TabProps } from "./common";

export default function StabilityTab({ project, setProject, analysis: a, active, illustrative }: TabProps) {
  const m = project.modules.buckling;
  const L = project.payload.loads;
  const hasInplane = L.Nx !== 0 || L.Ny !== 0 || L.Nxy !== 0;
  const s = useSolver("buckling", { project: project.payload, ...m }, active && !!a && hasInplane);
  const set = (k: keyof typeof m, v: number) => setProject((p) => ({ ...p, modules: { ...p.modules, buckling: { ...p.modules.buckling, [k]: v } } }));
  const r = s.data;
  const ctrl = (
    <div className="panel flex flex-wrap items-end gap-3 px-2.5 py-1.5">
      <div className="w-24"><NumField label="Length a (x)" unit="mm" value={m.a} min={1} max={1e5} onChange={(v) => set("a", v ?? 500)} /></div>
      <div className="w-24"><NumField label="Width b (y)" unit="mm" value={m.b} min={1} max={1e5} onChange={(v) => set("b", v ?? 300)} /></div>
      <div className="w-24"><NumField label="Ritz terms" value={m.terms} integer min={2} max={20} onChange={(v) => set("terms", v ?? 8)} title="Terms per direction (m = n = 1..terms)" /></div>
      <span className="max-w-[560px] text-[10.5px] text-graphite-500">Simply supported on all edges; loads Nx, Ny, Nxy from the Inputs panel (compression negative). Linear eigenvalue: no postbuckling, imperfection knockdown or transverse-shear flexibility.</span>
      <div className="ml-auto"><SolverNote s={s} what="buckling" /></div>
    </div>
  );
  if (!hasInplane) return <div className="flex flex-col gap-2">{ctrl}<div className="panel"><Empty>Enter in-plane loads (Nx, Ny or Nxy) to evaluate buckling.</Empty></div></div>;
  if (!r) return <div className="flex flex-col gap-2">{ctrl}<div className="panel"><Empty>{s.error ?? "Computing…"}</Empty></div></div>;
  const lf = r.load_factor;
  // Any approximation flag (D* for unsymmetric, thick plate, poor Ritz convergence) downgrades the label.
  const cls = r.flags?.length ? "screening" : "calculated";
  const sw = r.aspect_sweep;
  return (
    <div className="flex flex-col gap-2">
      {ctrl}
      <Warnings items={r.flags} />
      <Grid cols="xl:grid-cols-[1fr_auto_1.4fr]">
        <ChartFrame title="Buckling result" classification={cls} illustrative={illustrative}>
          {lf === null ? <Empty>{r.message}</Empty> : <>
            <div className="mb-1 font-mono text-[22px] text-graphite-900">λ<sub>cr</sub> = {fmt(lf, 4)}</div>
            <KV rows={[["Margin vs FoS", fmt(lf / a.fos - 1, 3), ""], ["Critical Nx", fmt(lf * L.Nx, 4), "N/mm"], ["Critical Ny", fmt(lf * L.Ny, 4), "N/mm"],
              ["Critical Nxy", fmt(lf * L.Nxy, 4), "N/mm"], ["Dominant half-waves (m, n)", r.dominant_mode?.join(", "), ""],
              ["Ritz change vs (terms−2)", r.convergence_change !== null ? `${fmt(100 * r.convergence_change, 3)} %` : "—", ""],
              ["δ = D16/(D11³D22)^¼", fmt(r.nondim?.delta, 3), ""], ["γ = D26/(D11D22³)^¼", fmt(r.nondim?.gamma, 3), ""]]} />
            {r.closed_form_check && <p className="mt-1 text-[10.5px] text-ok">Closed-form check (specially orthotropic, Nx only): N<sub>cr</sub> = {fmt(r.closed_form_check.Ncr, 6)} N/mm at m = {r.closed_form_check.m}; Ritz {fmt(r.closed_form_check.ritz_Ncr, 6)}.</p>}
            <p className="mt-1 text-[10.5px] text-graphite-500">λ multiplies the applied in-plane load. λ &lt; 1: buckles below the applied load.</p>
          </>}
        </ChartFrame>
        <ChartFrame title="Buckling mode shape" subtitle="normalised w(x, y)" classification={cls}
          csv={() => r.w ? r.w.flatMap((row: number[], j: number) => row.map((v, i) => ({ x_mm: r.x[i], y_mm: r.y[j], w_norm: v }))) : []}>
          {r.w ? <FieldContour x={r.x} y={r.y} w={r.w} xLabel="x [mm]" yLabel="y [mm]" unit="(normalised)" /> : <Empty>No mode.</Empty>}
        </ChartFrame>
        <ChartFrame title="Load factor versus aspect ratio" subtitle={`b = ${m.b} mm fixed, 6×6 terms`} classification="calculated"
          csv={() => sw ? sw.a_over_b.map((x: number, i: number) => ({ a_over_b: x, load_factor: sw.load_factor[i] })) : []}>
          {sw ? <XYPlot series={[{ name: "λcr", color: SERIES[0], data: sw.a_over_b.map((x: number, i: number) => ({ x, y: sw.load_factor[i] })).filter((d: { y: number | null }) => d.y !== null) }]}
            xLabel="a / b" yLabel="λcr" height={250} refX={[{ value: m.a / m.b, label: "current" }]} refY={[{ value: 1, label: "λ = 1", color: "#b3372f" }]} /> : <Empty>—</Empty>}
        </ChartFrame>
      </Grid>
    </div>
  );
}
