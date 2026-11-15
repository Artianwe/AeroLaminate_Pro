"use client";
// AeroLaminate Pro - engineering workspace. Author, owner and maintainer: Anwesh Ajitabh Dash.
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { get } from "@/lib/api";
import { download, exportCSV, slug } from "@/lib/exporters";
import { formatLayup } from "@/lib/layup";
import { APP, AUTHOR, CRIT_LABEL, MODE_LABEL, defaultProject, fmt, validateProject } from "@/lib/project";
import type { Criterion, Json, Material, Project } from "@/lib/types";
import { useSolver } from "@/lib/useSolver";
import { EnvPanel, LoadsPanel, OptionsPanel, PlyTable, Section } from "./inputs";
import { Warnings } from "./tabs/common";
import DurabilityTab from "./tabs/DurabilityTab";
import EnvironmentTab from "./tabs/EnvironmentTab";
import FailureTab from "./tabs/FailureTab";
import LaminateTab from "./tabs/LaminateTab";
import MaterialsTab from "./tabs/MaterialsTab";
import NotchTab from "./tabs/NotchTab";
import OptimizerTab from "./tabs/OptimizerTab";
import PlyTab from "./tabs/PlyTab";
import ProgressiveTab from "./tabs/ProgressiveTab";
import StabilityTab from "./tabs/StabilityTab";

const TABS = [
  ["laminate", "Laminate"], ["ply", "Ply response"], ["failure", "Failure"], ["progressive", "Progressive"], ["environment", "Hygrothermal"],
  ["stability", "Stability"], ["notch", "Notch & interlaminar"], ["durability", "Uncertainty & fatigue"], ["optimizer", "Optimizer"], ["materials", "Materials"],
] as const;
type Tab = (typeof TABS)[number][0];
const STORE = "aerolaminate.project.v1";

export default function Workspace() {
  const [project, setProjectRaw] = useState<Project>(() => defaultProject());
  const [materials, setMaterials] = useState<Material[]>([]);
  const [matErr, setMatErr] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("laminate");
  const [selected, setSelected] = useState<number | null>(null);
  const [baseline, setBaseline] = useState<{ name: string; analysis: Json; project: Project } | null>(null);
  const [dirty, setDirty] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const loaded = useRef(false);

  const setProject = useCallback((f: (p: Project) => Project) => { setProjectRaw(f); setDirty(true); }, []);

  const loadMaterials = useCallback(async (): Promise<boolean> => {
    try {
      const j = await get("materials");
      setMaterials(j.materials); setMatErr(j.user_file_error ?? null);
      return true;
    } catch {
      // Tell apart "engine not running" from "engine running but the UI's /api proxy cannot reach it".
      let direct = false;
      try { direct = (await fetch("http://127.0.0.1:8000/api/health", { cache: "no-store" })).ok; } catch { /* engine unreachable */ }
      setMatErr(direct
        ? "The analysis engine is running on 127.0.0.1:8000, but the web UI's /api proxy cannot reach it. Close both AeroLaminate Pro windows (or run STOP_AEROLAMINATE.bat) and start again. Retrying every 3 s…"
        : "Cannot reach the analysis engine (FastAPI on 127.0.0.1:8000). Check the 'AeroLaminate Pro - API' window for an error message. Retrying every 3 s…");
      return false;
    }
  }, []);
  // Retry until the engine answers, so a page opened before the engine finished starting recovers by itself.
  useEffect(() => {
    if (materials.length) return;
    const t = setInterval(() => { void loadMaterials(); }, 3000);
    return () => clearInterval(t);
  }, [materials.length, loadMaterials]);
  useEffect(() => {
    void loadMaterials();
    const h = () => { void loadMaterials(); };
    window.addEventListener("aerolaminate:materials", h);
    try {
      const s = localStorage.getItem(STORE);
      if (s) { const r = validateProject(JSON.parse(s)); if (r.project) setProjectRaw(r.project); }
    } catch { /* storage unavailable: start from defaults */ }
    loaded.current = true;
    return () => window.removeEventListener("aerolaminate:materials", h);
  }, [loadMaterials]);
  useEffect(() => {
    if (!loaded.current) return;
    try { localStorage.setItem(STORE, JSON.stringify(project)); } catch { /* ignore */ }
  }, [project]);

  const s = useSolver("analyze", project.payload, materials.length > 0, 250);
  // A blocked analysis must not leave the previous material's results on screen.
  const blocked = s.errorKind === "illustrative_blocked";
  const a = blocked ? null : s.data;
  const staleShown = !!(s.error && a);
  const demo = !!project.payload.options.allow_illustrative;
  const hotwet = project.payload.environment.hotwet_knockdown;
  const setDemo = (v: boolean) => setProject((p) => ({ ...p, payload: { ...p.payload, options: { ...p.payload.options, allow_illustrative: v } } }));
  const mat = materials.find((m) => m.id === project.payload.material_id);
  const illustrative = !!a?.provenance?.warnings?.some((w: string) => w.includes("ILLUSTRATIVE"));
  const plyCount = project.payload.plies.length;
  useEffect(() => { if (selected !== null && selected >= plyCount) setSelected(null); }, [plyCount, selected]);

  const save = () => {
    const p = { ...project, savedAt: new Date().toISOString() };
    download(`${slug(project.name)}.aerolam.json`, JSON.stringify(p, null, 1), "application/json");
    setDirty(false);
  };
  const open = (f: File) => f.text().then((t) => {
    try {
      const r = validateProject(JSON.parse(t));
      if (r.error) return alert(`Cannot open project: ${r.error}`);
      setProjectRaw(r.project!); setSelected(null); setDirty(false);
    } catch { alert("Cannot open project: file is not valid JSON"); }
  });
  const exportResults = () => {
    if (!a) return;
    const rows: Record<string, number | string | null>[] = [];
    a.laminate.plies.forEach((p: { index: number; angle: number; thickness: number; material: string }, k: number) => {
      ["bottom", "middle", "top"].forEach((pos, j) => {
        const row: Record<string, number | string | null> = { ply: p.index, angle_deg: p.angle, thickness_mm: p.thickness, material: p.material, position: pos, z_mm: a.ply_state.z[k][j] };
        ["x", "y", "xy"].forEach((c, i) => { row[`sigma_${c}_MPa`] = a.ply_state.sigma_xy[k][j][i]; row[`eps_${c}`] = a.ply_state.eps_xy[k][j][i]; });
        ["1", "2", "12"].forEach((c, i) => { row[`sigma_${c}_MPa`] = a.ply_state.sigma_12[k][j][i]; });
        for (const [c, R] of Object.entries(a.failure.results) as [string, Json][]) {
          const pi = a.failure.positions.indexOf(pos);
          if (pi >= 0) { row[`${c}_FI`] = R.fi[k][pi]; row[`${c}_RF`] = R.rf[k][pi] < 0 ? null : R.rf[k][pi]; row[`${c}_mode`] = R.mode_at_failure[k][pi]; }
        }
        rows.push(row);
      });
    });
    exportCSV(`${project.name} ply results`, rows, `${APP} ply results; author ${AUTHOR}; RF blank = no failure along load path`);
  };
  const report = () => {
    try { localStorage.setItem("aerolaminate.report", JSON.stringify({ project, analysis: a, generated: new Date().toISOString() })); } catch { /* ignore */ }
    window.open("/report", "_blank");
  };

  const status = s.error ? { t: "ERROR", c: "bg-bad text-ivory-50" } : s.loading ? { t: "SOLVING", c: "bg-amber-500 text-graphite-900" }
    : a ? { t: "SOLVED", c: "bg-ok text-ivory-50" } : { t: "IDLE", c: "bg-graphite-600 text-ivory-50" };
  const fpf = a?.fpf;
  const tabProps = { project, setProject, analysis: a, baseline, selected, setSelected, materials, illustrative };
  const layupStr = useMemo(() => formatLayup(project.payload.plies.map((p) => p.angle)), [project.payload.plies]);

  return (
    <div className="flex min-h-screen flex-col">
      {/* ------------------------------------------------------------ top bar */}
      <header className="no-print flex h-10 items-center gap-3 bg-graphite-900 px-3 text-ivory-100">
        <div className="flex items-baseline gap-2">
          <span className="font-mono text-[15px] font-semibold tracking-tight">Aero<span className="text-amber-400">Laminate</span> Pro</span>
          <span className="text-[10px] text-graphite-400">by {AUTHOR}</span>
        </div>
        <input className="ml-3 h-6 w-64 border border-graphite-700 bg-graphite-800 px-1.5 text-[12px] text-ivory-50 outline-none focus:border-amber-500"
          value={project.name} onChange={(e) => setProject((p) => ({ ...p, name: e.target.value }))} title="Project name" />
        {dirty && <span className="text-[10px] text-amber-400" title="Unsaved changes (autosaved in this browser)">●</span>}
        <span className={`px-2 py-[2px] font-mono text-[10.5px] tracking-widest ${status.c}`} title={s.error ?? undefined}>{status.t}</span>
        {s.ms !== null && <span className="font-mono text-[10.5px] text-graphite-400">{s.ms.toFixed(0)} ms</span>}
        <div className="ml-auto flex items-center gap-1 text-[11px]">
          {[["New", () => { if (!dirty || confirm("Discard current project?")) { setProjectRaw(defaultProject()); setSelected(null); setDirty(false); } }],
            ["Open…", () => fileRef.current?.click()], ["Save", save], ["Export CSV", exportResults], ["Report", report]].map(([l, f]) =>
            <button key={l as string} onClick={f as () => void} className="h-6 border border-graphite-700 px-2 text-ivory-100 hover:border-amber-500 hover:text-amber-400">{l as string}</button>)}
          <input ref={fileRef} type="file" accept=".json,application/json" className="hidden" onChange={(e) => { const f = e.target.files?.[0]; if (f) open(f); e.target.value = ""; }} />
        </div>
      </header>

      {/* ------------------------------------------------------------ status strip */}
      <div className="no-print flex flex-wrap items-center gap-x-4 gap-y-0.5 border-b border-rule bg-ivory-100 px-3 py-1 font-mono text-[11px]">
        <span className="text-graphite-600">{layupStr}</span>
        {a && <>
          <span>h = {fmt(a.laminate.h, 4)} mm</span>
          <span>{a.laminate.areal_mass ? `${fmt(a.laminate.areal_mass, 4)} kg/m²` : "mass n/a"}</span>
          <span>Ex = {fmt(a.engineering_constants.Ex / 1000, 4)} GPa</span>
          {fpf ? <span className={fpf.rf < a.fos ? "font-semibold text-bad" : "text-ok"}>
            FPF RF = {fmt(fpf.rf, 4)} ({CRIT_LABEL[fpf.criterion as Criterion]}, ply {fpf.ply} {fpf.position}, {MODE_LABEL[fpf.mode] ?? fpf.mode}) · MS = {fmt(fpf.ms, 3)} @ FoS {a.fos}</span>
            : <span className="text-graphite-500">No failure along the load path</span>}
        </>}
        <span className="ml-auto flex items-center gap-1 font-sans">
          {baseline ? <><span className="text-graphite-600">Baseline: <b>{baseline.name}</b></span><button className="btn" onClick={() => setBaseline(null)}>Clear</button></>
            : <button className="btn" disabled={!a} title="Freeze the current design; plots overlay it for comparison" onClick={() => a && setBaseline({ name: layupStr, analysis: a, project: structuredClone(project) })}>Pin baseline</button>}
        </span>
      </div>
      {(s.error || matErr) && <div className="no-print border-b border-bad/30 bg-red-50 px-3 py-1 text-[11.5px] text-bad">⚠ {matErr ?? s.error}
        {blocked && <button className="btn ml-2" onClick={() => setDemo(true)} title="Run with placeholder values; every result is marked ILLUSTRATIVE">Enable demonstration mode</button>}</div>}
      {staleShown && <div className="no-print border-b border-amber-600 bg-amber-400/25 px-3 py-1 text-[11.5px] font-semibold text-graphite-900">
        STALE RESULTS — the current inputs could not be solved; every view below shows the last valid solution, not the current inputs.</div>}
      {hotwet && a && <div className="no-print border-b border-amber-600/50 bg-amber-400/10 px-3 py-1 text-[11.5px] text-graphite-800">
        Hot/wet knockdown active: matrix-dominated properties are reduced by the Chamis (1984) empirical relation — an ESTIMATE, not conditioned test data.</div>}
      {demo && <div className="no-print border-b border-bad/30 bg-red-50 px-3 py-1 text-[11.5px] text-bad">Demonstration mode is ON (illustrative material data allowed).
        <button className="btn ml-2" onClick={() => setDemo(false)}>Turn off</button></div>}
      {illustrative && <div className="no-print border-b border-bad/30 bg-red-50 px-3 py-1 text-[11.5px] font-semibold text-bad">
        ILLUSTRATIVE material data in use ({mat?.name}). Results demonstrate the workflow only and must not be used for engineering decisions. Load qualified data in the Materials tab.</div>}

      <div className="flex min-h-0 flex-1">
        {/* ---------------------------------------------------------- inputs */}
        <aside className="no-print flex w-[372px] shrink-0 flex-col gap-1.5 overflow-y-auto border-r border-rule bg-ivory-100 p-1.5" style={{ maxHeight: "calc(100vh - 66px)" }}>
          <Section title="Material">
            <select className="inp" value={project.payload.material_id} onChange={(e) => setProject((p) => ({ ...p, payload: { ...p.payload, material_id: e.target.value } }))}>
              {materials.map((m) => <option key={m.id} value={m.id}>{m.name}{m.origin === "user" ? " (user)" : ""}</option>)}
            </select>
            {mat && <p className="mt-1 text-[10.5px] leading-snug text-graphite-600">{mat.condition}. {mat.applicability}</p>}
            {project.payload.materials?.some((m) => m.id === project.payload.material_id) && <p className="mt-1 text-[10.5px] text-warn">Project-level edits to this record are active.</p>}
          </Section>
          <Section title="Ply stack" right={<span className="font-mono text-[10.5px] text-graphite-500">{plyCount} plies</span>}>
            <PlyTable project={project} setProject={setProject} materials={materials} selected={selected} onSelect={setSelected} />
          </Section>
          <Section title="Loads"><LoadsPanel project={project} setProject={setProject} /></Section>
          <Section title="Environment"><EnvPanel project={project} setProject={setProject} /></Section>
          <Section title="Criteria & margins"><OptionsPanel project={project} setProject={setProject} /></Section>
          {a && (a.provenance.warnings.length > 0 || a.provenance.flags.length > 0) && <Section title="Data provenance & flags" open={false}>
            <Warnings items={[...a.provenance.warnings, ...a.provenance.flags]} />
          </Section>}
          <Section title="Conventions" open={false}>
            <ul className="list-disc space-y-0.5 pl-4 text-[10.5px] text-graphite-600">
              <li>Units N, mm, MPa; moduli shown in GPa. Strain in µε where noted.</li>
              <li>z upward from mid-plane; ply 1 at bottom (z = −h/2).</li>
              <li>θ counter-clockwise from +x to fibre (1) axis, viewed from +z.</li>
              <li>Engineering shear strain γ = 2ε. Tension positive.</li>
              <li>RF = mechanical-load multiplier to failure with residual hygrothermal stress held fixed. MS = RF/FoS − 1.</li>
              <li>CLT: no σz/τxz/τyz, no free-edge zone. Interlaminar outputs are screening estimates.</li>
            </ul>
          </Section>
          <p className="px-1 pb-2 pt-1 text-[10px] leading-snug text-graphite-500">{APP} — author, owner and maintainer {AUTHOR}. Engineering analysis and screening tool; not a certification tool.</p>
        </aside>

        {/* ---------------------------------------------------------- workspace */}
        <main className="min-w-0 flex-1 overflow-y-auto" style={{ maxHeight: "calc(100vh - 66px)" }}>
          <nav className="no-print sticky top-0 z-20 flex gap-0 border-b border-rule bg-ivory-50 px-2">
            {TABS.map(([k, l]) => (
              <button key={k} onClick={() => setTab(k)}
                className={`border-b-2 px-2.5 py-1.5 text-[11.5px] ${tab === k ? "border-amber-500 font-semibold text-graphite-900" : "border-transparent text-graphite-500 hover:text-graphite-900"}`}>{l}</button>
            ))}
          </nav>
          <div className="p-2">
            {!a && !s.error && <div className="panel p-6 text-center text-graphite-500">{materials.length ? "Solving…" : "Connecting to the analysis engine…"}</div>}
            {!a && s.error && <div className="panel p-6 text-center text-bad">{s.error}
              {blocked && <div className="mt-2 text-[11px] text-graphite-600">Results are withheld because the material record contains placeholder values. Load verified data in the Materials tab.</div>}</div>}
            {a && <>
              {tab === "laminate" && <LaminateTab {...tabProps} active />}
              {tab === "ply" && <PlyTab {...tabProps} active />}
              {tab === "failure" && <FailureTab {...tabProps} active />}
              {tab === "progressive" && <ProgressiveTab {...tabProps} active />}
              {tab === "environment" && <EnvironmentTab {...tabProps} active />}
              {tab === "stability" && <StabilityTab {...tabProps} active />}
              {tab === "notch" && <NotchTab {...tabProps} active />}
              {tab === "durability" && <DurabilityTab {...tabProps} active />}
              {tab === "optimizer" && <OptimizerTab {...tabProps} active />}
            </>}
            {tab === "materials" && materials.length > 0 && <MaterialsTab {...tabProps} active />}
          </div>
        </main>
      </div>
    </div>
  );
}
