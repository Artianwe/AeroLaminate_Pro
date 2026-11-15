"use client";
// AeroLaminate Pro - material database editor with per-property provenance. Author: Anwesh Ajitabh Dash.
import { useEffect, useState } from "react";
import ChartFrame from "@/components/ChartFrame";
import { NumField } from "@/components/inputs";
import { get, send } from "@/lib/api";
import type { Material, Prop, Status, Verification } from "@/lib/types";
import type { TabProps } from "./common";

const ORDER = ["E1", "E2", "G12", "nu12", "Xt", "Xc", "Yt", "Yc", "S12", "S23", "ILSS", "eps1t", "eps1c", "eps2t", "eps2c", "gamma12u",
  "GIc", "GIIc", "t_ply", "density", "alpha1", "alpha2", "beta1", "beta2", "Tg_dry", "Vf"];
const DESC: Record<string, string> = {
  E1: "Longitudinal modulus", E2: "Transverse modulus", G12: "In-plane shear modulus", nu12: "Major Poisson ratio", Xt: "Longitudinal tensile strength",
  Xc: "Longitudinal compressive strength", Yt: "Transverse tensile strength", Yc: "Transverse compressive strength", S12: "In-plane shear strength",
  S23: "Transverse shear strength", ILSS: "Interlaminar shear strength", eps1t: "Ult. strain 1 tension", eps1c: "Ult. strain 1 compression",
  eps2t: "Ult. strain 2 tension", eps2c: "Ult. strain 2 compression", gamma12u: "Ult. shear strain", GIc: "Mode I toughness", GIIc: "Mode II toughness",
  t_ply: "Cured ply thickness", density: "Density", alpha1: "CTE, fibre dir.", alpha2: "CTE, transverse", beta1: "CME, fibre dir.", beta2: "CME, transverse",
  Tg_dry: "Dry glass transition", Vf: "Fibre volume fraction",
};
const STATUSES: Status[] = ["datasheet", "literature", "calculated", "estimated", "illustrative", "unavailable"];
const SCOLOR: Record<Status, string> = { datasheet: "text-ok", literature: "text-ok", calculated: "text-graphite-700", estimated: "text-warn", illustrative: "text-bad", unavailable: "text-graphite-400" };

export default function MaterialsTab({ project, setProject, materials, }: TabProps & { reload?: () => void }) {
  const inline = project.payload.materials ?? [];
  const [id, setId] = useState(project.payload.material_id);
  const base = inline.find((m) => m.id === id) ?? materials.find((m) => m.id === id);
  const [draft, setDraft] = useState<Material | null>(base ? structuredClone(base) : null);
  const [msg, setMsg] = useState<string | null>(null);
  const [newId, setNewId] = useState("");
  const [refs, setRefs] = useState<Record<string, string>>({});
  useEffect(() => { get("materials").then((j) => setRefs(j.references ?? {})).catch(() => setRefs({})); }, []);
  useEffect(() => { const b = inline.find((m) => m.id === id) ?? materials.find((m) => m.id === id); setDraft(b ? structuredClone(b) : null); setMsg(null); // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id, materials]);
  if (!draft) return <div className="panel p-3">No material selected.</div>;
  const setP = (k: string, patch: Partial<Prop>) => setDraft((d) => d && ({ ...d, properties: { ...d.properties, [k]: { ...(d.properties[k] ?? { unit: "", status: "estimated", value: null }), ...patch } } }));
  const isInline = inline.some((m) => m.id === draft.id);
  const useInProject = () => {
    setProject((p) => ({ ...p, payload: { ...p.payload, materials: [...(p.payload.materials ?? []).filter((m) => m.id !== draft.id), draft] } }));
    setMsg("Edits applied to this project (stored in the project file; database unchanged). All analyses refresh automatically.");
  };
  const revert = () => {
    setProject((p) => ({ ...p, payload: { ...p.payload, materials: (p.payload.materials ?? []).filter((m) => m.id !== draft.id) } }));
    const b = materials.find((m) => m.id === id); setDraft(b ? structuredClone(b) : null); setMsg("Project edits removed; database record restored.");
  };
  const saveLib = async () => {
    const target = newId.trim() || draft.id;
    try {
      await send(`materials/${encodeURIComponent(target)}`, "PUT", { ...draft, id: target, name: target === draft.id ? draft.name : `${draft.name} (edited)` });
      setMsg(`Saved to user library as '${target}'. Reload the page or reselect to see it in all lists.`);
      window.dispatchEvent(new Event("aerolaminate:materials"));
    } catch (e) { setMsg(`Save failed: ${(e as Error).message}`); }
  };
  const del = async () => {
    if (!confirm(`Delete user material '${draft.id}'?`)) return;
    try { await send(`materials/${encodeURIComponent(draft.id)}`, "DELETE"); setMsg("Deleted."); window.dispatchEvent(new Event("aerolaminate:materials")); }
    catch (e) { setMsg(`Delete failed: ${(e as Error).message}`); }
  };
  const origin = materials.find((m) => m.id === draft.id)?.origin;
  return (
    <div className="flex flex-col gap-2">
      <div className="panel flex flex-wrap items-end gap-2 px-2.5 py-1.5">
        <label className="flex w-72 flex-col gap-[2px]"><span className="lbl">Material record</span>
          <select className="inp" value={id} onChange={(e) => setId(e.target.value)}>{materials.map((m) => <option key={m.id} value={m.id}>{m.name} — {m.origin}</option>)}</select></label>
        <button className="btn btn-primary" onClick={useInProject}>Apply edits to project</button>
        {isInline && <button className="btn" onClick={revert}>Revert to database</button>}
        <label className="flex w-48 flex-col gap-[2px]"><span className="lbl">Save as user id</span>
          <input className="inp" value={newId} placeholder={origin === "shipped" ? "new id required" : draft.id} onChange={(e) => setNewId(e.target.value)} /></label>
        <button className="btn" onClick={saveLib} disabled={origin === "shipped" && !newId.trim()}>Save to user library</button>
        {origin === "user" && <button className="btn" onClick={del}>Delete user record</button>}
        {msg && <span className="text-[11px] text-graphite-600">{msg}</span>}
      </div>
      <div className="grid grid-cols-1 gap-2 xl:grid-cols-[2fr_1fr]">
        <ChartFrame title={`${draft.name}`} subtitle={`${draft.manufacturer ?? ""} · ${draft.form ?? ""}`} classification="reference"
          illustrative={Object.values(draft.properties).some((p) => p.status === "illustrative")}
          csv={() => ORDER.map((k) => ({ property: k, description: DESC[k], value: draft.properties[k]?.value ?? null, unit: draft.properties[k]?.unit, status: draft.properties[k]?.status, source: draft.properties[k]?.source, note: draft.properties[k]?.note }))}>
          <table className="tbl">
            <thead><tr><th>Property</th><th>Description</th><th className="num">Value</th><th>Unit</th><th>Status</th><th>Verified</th><th>Source / note</th></tr></thead>
            <tbody>{ORDER.map((k) => {
              const p = draft.properties[k] ?? { value: null, unit: "", status: "unavailable" as Status };
              return <tr key={k}><td className="font-semibold">{k}</td><td className="font-sans text-graphite-600">{DESC[k]}</td>
                <td className="w-28"><NumField value={p.value} nullable onChange={(v) => v === null
                  ? setP(k, { value: null, status: "unavailable" })
                  : setP(k, { value: v, status: p.status === "unavailable" ? "estimated" : p.status })} /></td>
                <td className="text-graphite-500">{p.unit}</td>
                <td className="w-28"><select className={`inp ${SCOLOR[p.status]}`} value={p.status} onChange={(e) => setP(k, { status: e.target.value as Status })}>{STATUSES.map((s) => <option key={s}>{s}</option>)}</select></td>
                <td className="w-28"><select className={`inp ${p.verification === "primary" ? "text-ok" : p.verification === "secondary" ? "text-graphite-700" : "text-warn"}`}
                  value={p.status === "unavailable" ? "unverified" : (p.verification ?? "unverified")} disabled={p.status === "unavailable"}
                  title={p.verification_note ?? "primary = checked against the primary document; secondary = matched in a secondary source; unverified = not confirmed"}
                  onChange={(e) => setP(k, { verification: e.target.value as Verification })}>
                  {(["primary", "secondary", "unverified"] as const).map((v) => <option key={v}>{v}</option>)}</select></td>
                <td className="max-w-[340px] font-sans text-[10.5px] text-graphite-600" title={[p.note, p.verification_note].filter(Boolean).join(" | ")}>{p.source ? `[${p.source}] ` : ""}{p.note}{p.verification_note ? <span className="ml-1 cursor-help text-warn" title={`Verification: ${p.verification_note}`}>[verification note]</span> : null}</td></tr>;
            })}</tbody>
          </table>
        </ChartFrame>
        <ChartFrame title="Record metadata and provenance" classification="reference">
          <dl className="space-y-1 text-[11px]">
            {(["condition", "cure", "direction_convention", "applicability"] as const).map((k) => draft[k] ? <div key={k}><dt className="lbl">{k.replace("_", " ")}</dt><dd className="text-graphite-800">{draft[k]}</dd></div> : null)}
          </dl>
          {(() => {
            const used = Array.from(new Set(Object.values(draft.properties).map((p) => p.source).filter((x): x is string => !!x)));
            return used.length ? <div className="mt-2 border-t border-rule pt-1.5"><div className="lbl mb-0.5">References</div>
              <ul className="space-y-1 text-[10.5px] text-graphite-700">{used.map((k) => <li key={k}><b>[{k}]</b> {refs[k] ?? "user-supplied source"}</li>)}</ul></div> : null;
          })()}
          <div className="mt-2 border-t border-rule pt-1.5 text-[10.5px] leading-snug text-graphite-600">
            <p><b>Status legend.</b> <span className="text-ok">datasheet / literature</span>: traceable source; <b>calculated</b>: derived from other recorded data;
              <span className="text-warn"> estimated</span>: engineering estimate; <span className="text-bad">illustrative</span>: placeholder for demonstration only; <span className="text-graphite-400">unavailable</span>: not used — analyses needing it report "unavailable".</p>
            <p className="mt-1">Values are mean/typical, not A/B-basis design allowables. Do not combine properties from different cure conditions, environments or sources in one record.</p>
          </div>
        </ChartFrame>
      </div>
    </div>
  );
}
