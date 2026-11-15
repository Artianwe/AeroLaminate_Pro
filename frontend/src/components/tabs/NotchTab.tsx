"use client";
// AeroLaminate Pro - open-hole strength and interlaminar screening tab. Author: Anwesh Ajitabh Dash.
import ChartFrame, { Empty } from "@/components/ChartFrame";
import { NumField, Select, critOptions } from "@/components/inputs";
import { BarPlot, XYPlot, type Series } from "@/components/Plots";
import { SERIES, fmt } from "@/lib/project";
import { useSolver } from "@/lib/useSolver";
import { Grid, KV, SolverNote, Warnings, type TabProps } from "./common";

export default function NotchTab({ project, setProject, analysis: a, active, illustrative }: TabProps) {
  const n = project.modules.notch;
  const il = project.modules.interlaminar;
  const L = project.payload.loads;
  const sn = useSolver("notched", { project: project.payload, ...n }, active && !!a);
  const si = useSolver("interlaminar", { project: project.payload, ...il }, active && !!a);
  const setN = (k: keyof typeof n, v: unknown) => setProject((p) => ({ ...p, modules: { ...p.modules, notch: { ...p.modules.notch, [k]: v } } }));
  const r = sn.data, t = si.data;
  const nply = project.payload.plies.length;
  const toggleIf = (i: number) => setProject((p) => {
    const cur = p.modules.interlaminar.delam_interfaces;
    const next = cur.includes(i) ? cur.filter((x) => x !== i) : [...cur, i].sort((x, y) => x - y);
    return { ...p, modules: { ...p.modules, interlaminar: { delam_interfaces: next } } };
  });
  const R = n.diameter / 2;
  const dist: Series[] = r ? [{ name: "σx(0,y)/σ∞ (Konish–Whitney)", color: SERIES[0], data: r.distribution.y.map((y: number, i: number) => ({ x: y / R, y: r.distribution.ratio[i] })) }] : [];
  const size: Series[] = r ? [
    { name: "PSC", color: SERIES[0], data: r.size_effect.diameter.map((d: number, i: number) => ({ x: d, y: r.size_effect.psc[i] })) },
    { name: "ASC", color: SERIES[1], data: r.size_effect.diameter.map((d: number, i: number) => ({ x: d, y: r.size_effect.asc[i] })) },
  ] : [];
  const ts = t?.transverse_shear;
  const tsS: Series[] = ts ? [
    { name: "τxz", color: SERIES[0], data: ts.z.map((z: number, i: number) => ({ x: ts.tau_xz[i], y: z })) },
    { name: "τyz", color: SERIES[1], data: ts.z.map((z: number, i: number) => ({ x: ts.tau_yz[i], y: z })) },
  ] : [];
  const fe = t?.free_edge;
  const feRows = fe ? fe.interfaces.map((r: { interface: string; delta_nu_xy: number; delta_eta_xy_x: number }) => ({ i: r.interface, dnu: r.delta_nu_xy, deta: r.delta_eta_xy_x })) : [];
  const ed = t?.edge_delamination;
  return (
    <div className="flex flex-col gap-2">
      <div className="panel flex flex-wrap items-end gap-3 px-2.5 py-1.5">
        <div className="w-24"><NumField label="Hole Ø" unit="mm" value={n.diameter} min={0.1} max={1000} onChange={(v) => setN("diameter", v ?? 6.35)} /></div>
        <div className="w-24"><NumField label="Width W" unit="mm" value={n.width} nullable min={0.2} max={1e5} onChange={(v) => setN("width", v)} title="Blank = infinite plate" /></div>
        <div className="w-20"><NumField label="d₀ (PSC)" unit="mm" value={n.d0} min={0.01} max={100} onChange={(v) => setN("d0", v ?? 1)} /></div>
        <div className="w-20"><NumField label="a₀ (ASC)" unit="mm" value={n.a0} min={0.01} max={100} onChange={(v) => setN("a0", v ?? 4)} /></div>
        <div className="w-28"><NumField label="Unnotched σ₀" unit="MPa" value={n.sigma0} nullable min={0.1} onChange={(v) => setN("sigma0", v)} title="Blank = CLT first-ply-failure estimate (conservative)" /></div>
        <div className="w-32"><Select label="σ₀ criterion" value={n.criterion} onChange={(v) => setN("criterion", v)} options={critOptions()} /></div>
        <div className="ml-auto flex flex-col items-end"><SolverNote s={sn} what="open-hole" /><SolverNote s={si} what="interlaminar" /></div>
      </div>
      <Grid cols="xl:grid-cols-3">
        <ChartFrame title="Open-hole strength" subtitle={r ? `${r.loading}, load along x` : ""} classification="screening" illustrative={illustrative}
          csv={() => r ? [{ KT_inf: r.KT_inf, fwc: r.fwc, psc_ratio: r.psc_ratio, asc_ratio: r.asc_ratio, sigma0: r.sigma0, sigma_N_psc: r.sigma_N_psc, sigma_N_asc: r.sigma_N_asc }] : []}>
          {r ? <>
            <KV rows={[["K_T∞ (Lekhnitskii)", fmt(r.KT_inf, 4), ""], ["Finite-width factor", fmt(r.fwc, 4), ""], ["σ₀ (unnotched)", fmt(r.sigma0, 4), "MPa"],
              ["σ_N PSC", fmt(r.sigma_N_psc, 4), "MPa"], ["σ_N ASC", fmt(r.sigma_N_asc, 4), "MPa"], ["N_x notched PSC", fmt(r.N_psc, 4), "N/mm"],
              ["RF (PSC / ASC) vs Nx", r.rf_psc ? `${fmt(r.rf_psc, 3)} / ${fmt(r.rf_asc, 3)}` : "Nx = 0", ""]]} />
            <p className="mt-1 text-[10.5px] text-graphite-500">σ₀ source: {r.sigma0_source}.</p>
            <Warnings items={r.flags} />
          </> : <Empty>{sn.error ?? "Computing…"}</Empty>}
        </ChartFrame>
        <ChartFrame title="Stress concentration near hole" subtitle="along y-axis through the hole centre" classification="screening"
          csv={() => dist[0]?.data.map((d) => ({ y_over_R: d.x, ratio: d.y })) ?? []}>
          {r ? <XYPlot series={dist} xLabel="y / R" yLabel="σx / σ∞" height={240} refX={[{ value: 1 + n.d0 / R, label: "R+d₀" }, { value: 1 + n.a0 / R, label: "R+a₀", color: "#8a5a05" }]}
            refY={[{ value: 1, dashed: false, color: "#b9b3a3" }]} /> : <Empty>—</Empty>}
        </ChartFrame>
        <ChartFrame title="Hole-size effect" subtitle="notched / unnotched strength, infinite plate" classification="screening"
          csv={() => size.length ? size[0].data.map((d, i) => ({ diameter_mm: d.x, psc: d.y, asc: size[1].data[i].y })) : []}>
          {r ? <XYPlot series={size} xLabel="Hole diameter [mm]" yLabel="σN / σ0" height={240} yDomain={[0, 1]} refX={[{ value: n.diameter, label: "current" }]} /> : <Empty>—</Empty>}
        </ChartFrame>
      </Grid>
      <Grid cols="xl:grid-cols-3">
        <ChartFrame title="Transverse shear stress through thickness" subtitle={ts ? `Qx = ${L.Qx}, Qy = ${L.Qy} N/mm` : ""} classification="screening"
          csv={() => ts ? ts.z.map((z: number, i: number) => ({ z_mm: z, tau_xz_MPa: ts.tau_xz[i], tau_yz_MPa: ts.tau_yz[i], ply: ts.ply[i] })) : []}
          note="Equilibrium recovery for linearly varying moments; not valid near free edges, load points or ply drops.">
          {ts ? <XYPlot series={tsS} xLabel="τ [MPa]" yLabel="z [mm]" height={250} refY={a.laminate.z.map((v: number) => ({ value: v, color: "#d9d3c2", dashed: false }))} />
            : <Empty>{t?.message ?? si.error ?? "Computing…"}</Empty>}
        </ChartFrame>
        <ChartFrame title="Free-edge mismatch indicators" subtitle="adjacent-ply Δνxy and Δηxy,x" classification="screening" csv={() => feRows}
          note="Qualitative (Herakovich 1981): large |Δν| correlates with free-edge σz, large |Δη| with τxz. No stress magnitude is implied.">
          {fe ? <BarPlot data={feRows} xKey="i" xLabel="Interface" bars={[{ key: "dnu", name: "Δνxy", color: SERIES[0] }, { key: "deta", name: "Δηxy,x", color: SERIES[1] }]} height={230} refY={[{ value: 0 }]} /> : <Empty>—</Empty>}
        </ChartFrame>
        <ChartFrame title="Interlaminar checks" classification="screening"
          csv={() => t?.check ? t.check.interfaces : []}>
          {t?.check ? <div className="max-h-[150px] overflow-auto"><table className="tbl"><thead><tr><th>Interface</th><th className="num">τ [MPa]</th><th className="num">S [MPa]</th><th className="num">RF</th></tr></thead>
            <tbody>{t.check.interfaces.map((r: { interface: string; tau_resultant: number; strength: number; rf: number | null }) =>
              <tr key={r.interface}><td>{r.interface}</td><td className="num">{fmt(r.tau_resultant, 4)}</td><td className="num">{fmt(r.strength, 4)}</td><td className="num">{r.rf ? fmt(r.rf, 4) : "—"}</td></tr>)}</tbody></table>
            <Warnings items={t.check.flags} /></div> : <p className="text-[11px] text-graphite-500">Enter Qx/Qy to check interface shear.</p>}
          <div className="mt-2 border-t border-rule pt-1.5">
            <div className="lbl mb-1">Edge delamination (O&apos;Brien) — select interfaces (mirrored)</div>
            <div className="flex flex-wrap gap-1">{Array.from({ length: Math.max(0, Math.floor(nply / 2)) }, (_, k) => k + 1).map((i) =>
              <button key={i} className={`btn ${il.delam_interfaces.includes(i) ? "btn-primary" : ""}`} onClick={() => toggleIf(i)}>{i}/{i + 1}</button>)}</div>
            {ed && (ed.error ? <p className="mt-1 text-[11px] text-bad">{ed.error}</p> : <KV rows={[
              ["E_lam / E*", `${fmt(ed.E_lam / 1000, 4)} / ${fmt(ed.E_star / 1000, 4)}`, "GPa"],
              ["G at applied εx⁰", ed.G !== undefined ? fmt(ed.G, 4) : "—", "N/mm"],
              ["Onset strain (vs G_Ic)", ed.onset_strain ? `${fmt(ed.onset_strain * 1e6, 4)}` : (ed.note ?? "—"), "µε"]]} />)}
            {ed?.flags?.length ? <Warnings items={ed.flags} /> : null}
          </div>
        </ChartFrame>
      </Grid>
    </div>
  );
}
