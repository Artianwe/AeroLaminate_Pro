"use client";
// AeroLaminate Pro - laminate mechanics tab: stack, ABD, constants, coupling, orientation. Author: Anwesh Ajitabh Dash.
import { useState } from "react";
import ChartFrame from "@/components/ChartFrame";
import { MatrixHeatmap, PlyStack } from "@/components/Graphics";
import { BarPlot, XYPlot, type Series } from "@/components/Plots";
import { BASELINE, SERIES, fmt } from "@/lib/project";
import { Chip, Grid, KV, type TabProps } from "./common";

const LBL = ["Nx", "Ny", "Nxy", "Mx", "My", "Mxy"];
const unitOf = (i: number, j: number) => (i < 3 && j < 3 ? "N/mm" : i >= 3 && j >= 3 ? "N·mm" : "N");

export default function LaminateTab({ analysis: a, baseline, selected, setSelected, illustrative }: TabProps) {
  const [mat, setMat] = useState<"A" | "B" | "D" | "abd">("A");
  if (!a) return null;
  const ec = a.engineering_constants, cl = a.classification, cp = a.coupling, dg = a.diagnostics, lam = a.laminate;
  const or = a.orientation;
  const mkOr = (src: typeof or, k: string, name: string, color: string, dashed = false): Series =>
    ({ name, color, dashed, data: src.psi.map((p: number, i: number) => ({ x: p, y: src[k][i] / 1000 })) });
  const orSeries: Series[] = [mkOr(or, "Ex", "Ex (membrane)", SERIES[0]), mkOr(or, "Efx", "Efx (flexural)", SERIES[1]), mkOr(or, "Gxy", "Gxy", SERIES[2])];
  if (baseline) orSeries.push(mkOr(baseline.analysis.orientation, "Ex", `Ex baseline (${baseline.name})`, BASELINE, true));
  const r = a.response;
  const defo = [
    { k: "εx⁰", v: r.eps0[0] * 1e6 }, { k: "εy⁰", v: r.eps0[1] * 1e6 }, { k: "γxy⁰", v: r.eps0[2] * 1e6 },
  ];
  const curv = [{ k: "κx", v: r.kappa[0] * 1e3 }, { k: "κy", v: r.kappa[1] * 1e3 }, { k: "κxy", v: r.kappa[2] * 1e3 }];
  const M = mat === "abd" ? a.matrices.abd : a.matrices[mat];
  const mUnit = mat === "A" ? "N/mm" : mat === "B" ? "N" : mat === "D" ? "N·mm" : "compliance (mixed units)";
  const coup = [
    { k: "Ext–shear", v: cp.extension_shear, t: "max(|A16|,|A26|)/√(A11A66)" },
    { k: "Ext–bend", v: cp.extension_bending, t: "‖B‖/√(‖A‖‖D‖)" },
    { k: "B–T δ", v: Math.abs(cp.bending_twisting_delta), t: "|D16|/(D11³D22)^¼ (Nemeth)" },
    { k: "B–T γ", v: Math.abs(cp.bending_twisting_gamma), t: "|D26|/(D11D22³)^¼" },
  ];
  return (
    <div className="flex flex-col gap-2">
      <Grid cols="xl:grid-cols-[auto_1fr_1fr]">
        <ChartFrame title="Ply stack cross-section" subtitle={`${lam.n_plies} plies · h = ${fmt(lam.h, 4)} mm`} classification="calculated"
          csv={() => lam.plies.map((p: { index: number; angle: number; thickness: number; material: string }, i: number) => ({ ply: p.index, angle_deg: p.angle, thickness_mm: p.thickness, z_bottom_mm: lam.z[i], z_top_mm: lam.z[i + 1], material: p.material }))}
          note="Click a ply to select it in every view. Hatching shows the fibre direction in plan; dashed line = mid-plane.">
          <PlyStack plies={lam.plies} z={lam.z} selected={selected} onSelect={setSelected}
            rf={a.fpf ? a.failure.results[a.fpf.criterion]?.rf_ply : undefined} />
        </ChartFrame>
        <ChartFrame title="Laminate properties" classification="calculated" illustrative={illustrative}
          csv={() => Object.entries(ec).map(([k, v]) => ({ quantity: k, value: v as number }))}>
          <div className="mb-1.5 flex flex-wrap gap-1">
            <Chip ok={cl.symmetric_stiffness}>Symmetric (B=0)</Chip><Chip ok={cl.balanced}>Balanced (A16=A26=0)</Chip>
            <Chip ok={cl.quasi_isotropic_inplane}>Quasi-isotropic</Chip><Chip ok={cl.specially_orthotropic}>Specially orthotropic</Chip>
          </div>
          <div className="grid grid-cols-2 gap-2">
            <KV rows={[["Ex", fmt(ec.Ex / 1000, 4), "GPa"], ["Ey", fmt(ec.Ey / 1000, 4), "GPa"], ["Gxy", fmt(ec.Gxy / 1000, 4), "GPa"],
              ["νxy", fmt(ec.nuxy, 4), "–"], ["ηxy,x", fmt(Math.abs(ec.eta_xy_x) < 1e-12 ? 0 : ec.eta_xy_x, 3), "–"], ["Areal mass", lam.areal_mass ? fmt(lam.areal_mass, 4) : "n/a", "kg/m²"]]} />
            <KV rows={[["Efx", fmt(ec.Efx / 1000, 4), "GPa"], ["Efy", fmt(ec.Efy / 1000, 4), "GPa"], ["Gfxy", fmt(ec.Gfxy / 1000, 4), "GPa"],
              ["Thickness", fmt(lam.h, 4), "mm"], ["cond(ABD)ₛ", fmt(dg.scaled_condition, 3), "–"], ["Pos. definite", dg.positive_definite ? "yes" : "NO", ""]]} />
          </div>
          {!cl.symmetric_stiffness && <p className="mt-1 text-[10.5px] text-warn">Membrane constants assume bending restrained (from A⁻¹); free-to-bend Ex = {fmt(ec.Ex_free / 1000, 4)} GPa.</p>}
        </ChartFrame>
        <ChartFrame title="Coupling indicators" subtitle="0 = uncoupled" classification="calculated" csv={() => coup.map((c) => ({ indicator: c.k, value: c.v, definition: c.t }))}>
          <BarPlot data={coup} xKey="k" bars={[{ key: "v", name: "Indicator", color: SERIES[0] }]} height={190} yDomain={[0, "auto"]} legend={false} />
        </ChartFrame>
      </Grid>
      <Grid cols="xl:grid-cols-[auto_1fr]">
        <ChartFrame title="[ABD] stiffness heatmap" classification="calculated"
          csv={() => a.matrices.ABD.map((row: number[], i: number) => Object.fromEntries([["row", LBL[i]], ...row.map((v, j) => [LBL[j], v])]))}>
          <MatrixHeatmap M={a.matrices.ABD} labels={["εx", "εy", "γxy", "κx", "κy", "κxy"]} units={unitOf} />
        </ChartFrame>
        <ChartFrame title="Matrix inspection" subtitle={mUnit} classification="calculated"
          actions={<div className="mr-2 flex gap-0.5">{(["A", "B", "D", "abd"] as const).map((k) =>
            <button key={k} className={`btn ${mat === k ? "btn-primary" : ""}`} onClick={() => setMat(k)}>{k === "abd" ? "[ABD]⁻¹" : `[${k}]`}</button>)}</div>}
          csv={() => M.map((row: number[], i: number) => Object.fromEntries([["row", i + 1], ...row.map((v, j) => [`c${j + 1}`, v])]))}>
          <table className="tbl"><tbody>
            {M.map((row: number[], i: number) => <tr key={i}>{row.map((v, j) => <td key={j} className="num">{Math.abs(v) < 1e-12 * Math.abs(M[0][0]) ? "0" : fmt(v, 6)}</td>)}</tr>)}
          </tbody></table>
          <p className="mt-1 text-[10.5px] text-graphite-500">Ordering {mat === "abd" || M.length === 6 ? "{εx εy γxy κx κy κxy}" : "{x y xy}"}. z measured upward from the mid-plane; ply 1 at z = −h/2.</p>
        </ChartFrame>
      </Grid>
      <Grid cols="xl:grid-cols-[2fr_1fr_1fr]">
        <ChartFrame title="Stiffness versus orientation" subtitle="laminate axes rotated by ψ" classification="calculated"
          csv={() => or.psi.map((p: number, i: number) => ({ psi_deg: p, Ex_MPa: or.Ex[i], Efx_MPa: or.Efx[i], Gxy_MPa: or.Gxy[i], nuxy: or.nuxy[i] }))}>
          <XYPlot series={orSeries} xLabel="ψ [deg]" yLabel="Modulus [GPa]" height={230} xDomain={[0, 180]} />
        </ChartFrame>
        <ChartFrame title="Mid-plane strains" subtitle="total incl. hygrothermal" classification="calculated" csv={() => defo.map((d) => ({ component: d.k, microstrain: d.v }))}>
          <BarPlot data={defo} xKey="k" bars={[{ key: "v", name: "µε", color: SERIES[0] }]} yLabel="µε" height={200} refY={[{ value: 0 }]} legend={false} />
        </ChartFrame>
        <ChartFrame title="Curvatures" classification="calculated" csv={() => curv.map((d) => ({ component: d.k, per_m: d.v }))}>
          <BarPlot data={curv} xKey="k" bars={[{ key: "v", name: "1/m", color: SERIES[1] }]} yLabel="κ [1/m]" height={200} refY={[{ value: 0 }]} legend={false} />
        </ChartFrame>
      </Grid>
    </div>
  );
}
