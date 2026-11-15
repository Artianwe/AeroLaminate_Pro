"use client";
// AeroLaminate Pro - validated input controls and input panels. Author: Anwesh Ajitabh Dash.
import { useEffect, useState, type ReactNode } from "react";
import { formatLayup, parseLayup } from "@/lib/layup";
import { CRIT_COLOR, CRIT_LABEL } from "@/lib/project";
import { CRITERIA, type Criterion, type Material, type Project } from "@/lib/types";

export function NumField({ value, onChange, min, max, step, unit, label, title, nullable, width, integer }: {
  value: number | null; onChange: (v: number | null) => void; min?: number; max?: number; step?: number; unit?: string;
  label?: ReactNode; title?: string; nullable?: boolean; width?: string; integer?: boolean;
}) {
  const [text, setText] = useState(value === null || value === undefined ? "" : String(value));
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    const cur = text.trim() === "" ? null : Number(text);
    if (cur !== value) setText(value === null || value === undefined ? "" : String(value));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value]);
  const commit = (t: string) => {
    setText(t);
    if (t.trim() === "") {
      if (nullable) { setErr(null); onChange(null); } else setErr("required");
      return;
    }
    const v = Number(t);
    if (!Number.isFinite(v)) return setErr("not a number");
    if (integer && !Number.isInteger(v)) return setErr("integer required");
    if (min !== undefined && v < min) return setErr(`≥ ${min}`);
    if (max !== undefined && v > max) return setErr(`≤ ${max}`);
    setErr(null);
    onChange(v);
  };
  return (
    <label className="flex min-w-0 flex-col gap-[2px]" title={err ?? title} style={width ? { width } : undefined}>
      {label && <span className="lbl truncate">{label}{unit && <span className="ml-1 normal-case text-graphite-400">[{unit}]</span>}</span>}
      <input className={`inp ${err ? "inp-bad" : ""}`} value={text} inputMode="decimal" step={step} onChange={(e) => commit(e.target.value)}
        placeholder={nullable ? "—" : undefined} />
      {err && <span className="text-[9.5px] leading-3 text-bad">{err}</span>}
    </label>
  );
}

export function Toggle({ checked, onChange, label, title }: { checked: boolean; onChange: (v: boolean) => void; label: ReactNode; title?: string }) {
  return (
    <label className="flex cursor-pointer items-center gap-1.5 text-[11px] text-graphite-700" title={title}>
      <input type="checkbox" className="accent-amber-600" checked={checked} onChange={(e) => onChange(e.target.checked)} />
      {label}
    </label>
  );
}

export function Select<T extends string>({ value, onChange, options, label }: {
  value: T; onChange: (v: T) => void; options: { value: T; label: string }[]; label?: ReactNode;
}) {
  return (
    <label className="flex min-w-0 flex-col gap-[2px]">
      {label && <span className="lbl">{label}</span>}
      <select className="inp" value={value} onChange={(e) => onChange(e.target.value as T)}>
        {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
      </select>
    </label>
  );
}

export function Section({ title, children, right, open = true }: { title: string; children: ReactNode; right?: ReactNode; open?: boolean }) {
  const [o, setO] = useState(open);
  return (
    <section className="panel">
      <div className="sec-title cursor-pointer select-none" onClick={() => setO(!o)}>
        <span>{o ? "▾" : "▸"} {title}</span>
        <span onClick={(e) => e.stopPropagation()}>{right}</span>
      </div>
      {o && <div className="p-2">{children}</div>}
    </section>
  );
}

export const critOptions = (list: readonly Criterion[] = CRITERIA) => list.map((c) => ({ value: c, label: CRIT_LABEL[c] }));

type SetP = (f: (p: Project) => Project) => void;

// ----------------------------------------------------------------------------- ply table
export function PlyTable({ project, setProject, materials, selected, onSelect, plyState }: {
  project: Project; setProject: SetP; materials: Material[]; selected: number | null; onSelect: (i: number | null) => void; plyState?: string[];
}) {
  const plies = project.payload.plies;
  const mat = materials.find((m) => m.id === project.payload.material_id);
  const tDefault = mat?.properties?.t_ply?.value ?? null;
  const [layup, setLayup] = useState(formatLayup(plies.map((p) => p.angle)));
  const [lerr, setLerr] = useState<string | null>(null);
  useEffect(() => { setLayup(formatLayup(plies.map((p) => p.angle))); }, [plies]);
  const setPlies = (f: (p: typeof plies) => typeof plies) => setProject((p) => ({ ...p, payload: { ...p.payload, plies: f(p.payload.plies) } }));
  const applyLayup = () => {
    const r = parseLayup(layup);
    if (r.error) return setLerr(r.error);
    setLerr(null);
    setPlies((old) => r.angles.map((a, i) => ({ angle: a, thickness: old[i]?.thickness ?? null, material_id: old[i]?.material_id ?? null })));
  };
  const move = (i: number, d: number) => setPlies((ps) => {
    const j = i + d; if (j < 0 || j >= ps.length) return ps;
    const c = [...ps]; [c[i], c[j]] = [c[j], c[i]]; return c;
  });
  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-end gap-1">
        <label className="flex flex-1 flex-col gap-[2px]">
          <span className="lbl">Stacking sequence (bottom → top)</span>
          <input className={`inp ${lerr ? "inp-bad" : ""}`} value={layup} onChange={(e) => setLayup(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && applyLayup()} title="e.g. [0/±45/90]s, [45/-45/0_2]2s, [0/90~]s" />
        </label>
        <button className="btn" onClick={applyLayup}>Apply</button>
      </div>
      {lerr && <div className="text-[10px] text-bad">{lerr}</div>}
      <div className="max-h-[260px] overflow-auto border border-rule">
        <table className="tbl">
          <thead><tr><th>#</th><th>θ [°]</th><th>t [mm]</th><th>Material</th><th></th></tr></thead>
          <tbody>
            {[...plies.keys()].reverse().map((i) => {
              const p = plies[i];
              const st = plyState?.[i];
              return (
                <tr key={i} onClick={() => onSelect(i)} className={selected === i ? "bg-amber-400/15" : ""}>
                  <td className="w-6 text-graphite-500">{i + 1}{st && st !== "-" ? <span className={st === "F" ? "text-bad" : "text-warn"}> {st}</span> : null}</td>
                  <td className="w-16"><NumField value={p.angle} min={-180} max={180} onChange={(v) => v !== null && setPlies((ps) => ps.map((q, k) => k === i ? { ...q, angle: v } : q))} /></td>
                  <td className="w-[70px]"><NumField value={p.thickness ?? null} nullable min={0.001} max={50}
                    title={`Blank = database ply thickness (${tDefault ?? "n/a"} mm)`}
                    onChange={(v) => setPlies((ps) => ps.map((q, k) => k === i ? { ...q, thickness: v } : q))} /></td>
                  <td><select className="inp" value={p.material_id ?? ""} onChange={(e) => setPlies((ps) => ps.map((q, k) => k === i ? { ...q, material_id: e.target.value || null } : q))}>
                    <option value="">(laminate)</option>
                    {materials.map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}
                  </select></td>
                  <td className="whitespace-nowrap">
                    <button className="px-0.5 text-graphite-500 hover:text-graphite-900" title="Move up" onClick={(e) => { e.stopPropagation(); move(i, 1); }}>↑</button>
                    <button className="px-0.5 text-graphite-500 hover:text-graphite-900" title="Move down" onClick={(e) => { e.stopPropagation(); move(i, -1); }}>↓</button>
                    <button className="px-0.5 text-graphite-500 hover:text-graphite-900" title="Duplicate" onClick={(e) => { e.stopPropagation(); setPlies((ps) => [...ps.slice(0, i + 1), { ...ps[i] }, ...ps.slice(i + 1)]); }}>⧉</button>
                    <button className="px-0.5 text-graphite-500 hover:text-bad" title="Delete" disabled={plies.length <= 1}
                      onClick={(e) => { e.stopPropagation(); onSelect(null); setPlies((ps) => ps.length > 1 ? ps.filter((_, k) => k !== i) : ps); }}>✕</button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <div className="flex gap-1">
        <button className="btn" onClick={() => setPlies((ps) => [...ps, { angle: 0 }])}>+ ply (top)</button>
        <button className="btn" onClick={() => setPlies((ps) => [...ps, ...[...ps].reverse()])} title="Append mirrored copy">Mirror</button>
        <button className="btn" onClick={() => setPlies((ps) => ps.map((q) => ({ ...q, thickness: null })))} title="Use database ply thickness for all plies">Reset t</button>
      </div>
      <p className="text-[10px] leading-snug text-graphite-500">Table lists top ply first. θ counter-clockwise from +x to fibres, viewed from +z. Blank thickness uses the database value.</p>
    </div>
  );
}

// ----------------------------------------------------------------------------- loads / env / options
export function LoadsPanel({ project, setProject }: { project: Project; setProject: SetP }) {
  const L = project.payload.loads;
  const set = (k: keyof typeof L) => (v: number | null) => setProject((p) => ({ ...p, payload: { ...p.payload, loads: { ...p.payload.loads, [k]: v ?? 0 } } }));
  const f = (k: keyof typeof L, unit: string, label: string) => <NumField key={k} label={label} unit={unit} value={L[k]} onChange={set(k)} min={-1e7} max={1e7} />;
  return (
    <div className="flex flex-col gap-1.5">
      <div className="grid grid-cols-3 gap-1.5">{f("Nx", "N/mm", "Nx")}{f("Ny", "N/mm", "Ny")}{f("Nxy", "N/mm", "Nxy")}</div>
      <div className="grid grid-cols-3 gap-1.5">{f("Mx", "N", "Mx")}{f("My", "N", "My")}{f("Mxy", "N", "Mxy")}</div>
      <div className="grid grid-cols-3 gap-1.5">{f("Qx", "N/mm", "Qx")}{f("Qy", "N/mm", "Qy")}</div>
      <p className="text-[10px] leading-snug text-graphite-500">Resultants per unit width. Moment unit N·mm/mm = N. Q (transverse shear) drives the interlaminar recovery only. Tension positive.</p>
    </div>
  );
}

export function EnvPanel({ project, setProject }: { project: Project; setProject: SetP }) {
  const E = project.payload.environment;
  const set = <K extends keyof typeof E>(k: K) => (v: (typeof E)[K]) => setProject((p) => ({ ...p, payload: { ...p.payload, environment: { ...p.payload.environment, [k]: v } } }));
  return (
    <div className="flex flex-col gap-1.5">
      <div className="grid grid-cols-3 gap-1.5">
        <NumField label="T stress-free" unit="°C" value={E.T_stress_free} min={-273} max={500} onChange={(v) => set("T_stress_free")(v ?? 20)} title="Temperature at which the laminate is stress-free (often near cure temperature)" />
        <NumField label="T service" unit="°C" value={E.T_service} min={-273} max={500} onChange={(v) => set("T_service")(v ?? 20)} />
        <NumField label="Moisture" unit="% wt" value={E.moisture} min={0} max={10} onChange={(v) => set("moisture")(v ?? 0)} />
      </div>
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <span className="font-mono text-[11px] text-graphite-600">ΔT = {(E.T_service - E.T_stress_free).toFixed(1)} °C</span>
        <Toggle checked={E.hotwet_knockdown} onChange={set("hotwet_knockdown")} label="Hot/wet matrix knockdown (Chamis estimate)" title="Empirical estimate; requires dry Tg in the material record" />
      </div>
      <div className="flex gap-1">
        <button className="btn" onClick={() => setProject((p) => ({ ...p, payload: { ...p.payload, environment: { ...p.payload.environment, T_stress_free: 177, T_service: 21 } } }))}>Cure residual (177→21 °C)</button>
        <button className="btn" onClick={() => setProject((p) => ({ ...p, payload: { ...p.payload, environment: { ...p.payload.environment, T_stress_free: 20, T_service: 20, moisture: 0 } } }))}>No residual</button>
      </div>
    </div>
  );
}

export function OptionsPanel({ project, setProject }: { project: Project; setProject: SetP }) {
  const O = project.payload.options;
  const crit = project.payload.criteria;
  const set = <K extends keyof typeof O>(k: K) => (v: (typeof O)[K]) => setProject((p) => ({ ...p, payload: { ...p.payload, options: { ...p.payload.options, [k]: v } } }));
  const toggle = (c: Criterion) => setProject((p) => {
    const has = p.payload.criteria.includes(c);
    const next = has ? p.payload.criteria.filter((x) => x !== c) : CRITERIA.filter((x) => x === c || p.payload.criteria.includes(x));
    return next.length ? { ...p, payload: { ...p.payload, criteria: next } } : p;
  });
  return (
    <div className="flex flex-col gap-2">
      <div className="grid grid-cols-2 gap-x-2 gap-y-1">
        {CRITERIA.map((c) => (
          <Toggle key={c} checked={crit.includes(c)} onChange={() => toggle(c)}
            label={<span className="flex items-center gap-1"><span className="inline-block h-2 w-2" style={{ background: CRIT_COLOR[c] }} />{CRIT_LABEL[c]}</span>} />
        ))}
      </div>
      <div className="grid grid-cols-3 gap-1.5">
        <NumField label="Factor of safety" value={O.fos} min={0.01} max={10} onChange={(v) => set("fos")(v ?? 1.5)} title="MS = RF/FoS − 1. 1.5 is the 14 CFR 25.303 ultimate factor applied to limit loads" />
        <NumField label="Tsai-Wu F12*" value={O.tsai_wu_F12_star} min={-0.999} max={0.999} onChange={(v) => set("tsai_wu_F12_star")(v ?? -0.5)} />
        <NumField label="Hashin S_T" unit="MPa" value={O.hashin_ST} nullable min={0.1} onChange={(v) => set("hashin_ST")(v)} title="Transverse shear strength; blank = database S23 or Yc/2 (flagged)" />
        <NumField label="Puck p⊥∥(+)" value={O.puck_p_pt} min={0.01} max={0.99} onChange={(v) => set("puck_p_pt")(v ?? 0.35)} />
        <NumField label="Puck p⊥∥(−)" value={O.puck_p_pc} min={0.01} max={0.99} onChange={(v) => set("puck_p_pc")(v ?? 0.3)} />
        <NumField label="LaRC α₀" unit="°" value={O.larc_alpha0_deg} min={45} max={60} onChange={(v) => set("larc_alpha0_deg")(v ?? 53)} />
      </div>
      <Toggle checked={O.larc_insitu} onChange={set("larc_insitu")} label="LaRC03 in-situ strengths (needs G_Ic, G_IIc)" />
    </div>
  );
}
