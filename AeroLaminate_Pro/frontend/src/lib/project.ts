// AeroLaminate Pro - project defaults, (de)serialisation. Author: Anwesh Ajitabh Dash.
import { CRITERIA, type Criterion, type Project } from "./types";

export const AUTHOR = "Anwesh Ajitabh Dash";
export const APP = "AeroLaminate Pro";

export function defaultProject(): Project {
  return {
    schema: "aerolaminate-project/1",
    name: "Quasi-isotropic skin panel",
    author: "",
    notes: "",
    payload: {
      material_id: "AS4_3501-6",
      plies: [45, -45, 0, 90, 90, 0, -45, 45].map((angle) => ({ angle })),
      loads: { Nx: 250, Ny: 40, Nxy: 30, Mx: 0, My: 0, Mxy: 0, Qx: 0, Qy: 0 },
      environment: { T_stress_free: 20, T_service: 20, moisture: 0, hotwet_knockdown: false, T_reference: 21 },
      criteria: [...CRITERIA],
      options: { fos: 1.5, tsai_wu_F12_star: -0.5, puck_p_pt: 0.35, puck_p_pc: 0.3, larc_alpha0_deg: 53, larc_insitu: true, hashin_ST: null },
    },
    modules: {
      buckling: { a: 500, b: 300, terms: 8 },
      notch: { diameter: 6.35, width: 38.1, d0: 1.0, a0: 4.0, sigma0: null, criterion: "tsai_wu" },
      envSweep: { mode: "T", start: -55, stop: 120, points: 36, plate_a: 300, plate_b: 300 },
      pfa: { criterion: "hashin", d_fibre: 0.01, d_matrix: 0.2 },
      interlaminar: { delam_interfaces: [] },
      fatigue: { criterion: "tsai_wu", model: "loglinear", params: { b: 0.1, A: 1, k: 12 }, blocks: [], static_rf: null, R_ratio: 0.1 },
      uq: { criterion: "tsai_wu", samples: 400, seed: 1, distribution: "normal", rel_step: 0.05,
            cov: { E1: 0.05, E2: 0.05, G12: 0.05, nu12: 0.0, Xt: 0.08, Xc: 0.08, Yt: 0.08, Yc: 0.08, S12: 0.08 } },
      parametric: { vary_plies: [1, 2, 7, 8], start: 0, stop: 90, step: 5 },
      envelope: { plane: "s1s2", fixed: 0, laminate_plane: "NxNy" },
      opt: { angles: [0, 45, 90], symmetric: true, balanced: true, min_plies: 8, max_plies: 32, criterion: "tsai_wu", rf_min: 1.5,
             min_Ex: 0, min_Ey: 0, min_Gxy: 0, max_mass: 0, min_fraction: 0.1, max_consecutive: 4, outer_45: true,
             buckling: false, plate_a: 500, plate_b: 300, buckling_min: 1.0, w_mass: 1, w_fi: 0, w_coupling: 0, w_buckling: 0,
             pop: 40, generations: 60, seed: 7 },
    },
  };
}

export function validateProject(j: unknown): { project?: Project; error?: string } {
  const p = j as Project;
  if (!p || typeof p !== "object") return { error: "Not a JSON object" };
  if (p.schema !== "aerolaminate-project/1") return { error: "Unrecognised file: expected an AeroLaminate Pro project (schema aerolaminate-project/1)" };
  const d = defaultProject();
  if (!p.payload?.plies?.length || typeof p.payload.material_id !== "string") return { error: "Project has no laminate definition" };
  for (const [i, ply] of p.payload.plies.entries()) {
    if (typeof ply.angle !== "number" || !Number.isFinite(ply.angle)) return { error: `Ply ${i + 1}: invalid angle` };
  }
  const crit = (p.payload.criteria ?? d.payload.criteria).filter((c): c is Criterion => (CRITERIA as readonly string[]).includes(c));
  return {
    project: {
      ...d, ...p,
      payload: { ...d.payload, ...p.payload, criteria: crit, loads: { ...d.payload.loads, ...p.payload.loads },
                 environment: { ...d.payload.environment, ...p.payload.environment }, options: { ...d.payload.options, ...p.payload.options } },
      modules: { ...d.modules, ...(p.modules ?? {}) },
    },
  };
}

export const CRIT_LABEL: Record<Criterion, string> = {
  max_stress: "Max stress", max_strain: "Max strain", tsai_hill: "Tsai-Hill", tsai_wu: "Tsai-Wu", hashin: "Hashin", puck: "Puck", larc03: "LaRC03",
};

// Categorical colours: validated reference palette (dataviz skill, light mode), fixed per criterion so colour follows the entity.
export const CRIT_COLOR: Record<Criterion, string> = {
  max_stress: "#2a78d6", max_strain: "#eb6834", tsai_hill: "#1baf7a", tsai_wu: "#eda100", hashin: "#e87ba4", puck: "#008300", larc03: "#6250d6",
};
export const SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"];
export const BASELINE = "#8a8780";

export const MODE_LABEL: Record<string, string> = {
  FT: "Fibre tension", FC: "Fibre compression", MT: "Matrix tension", MC: "Matrix compression", S: "In-plane shear",
  TH: "Tsai-Hill (interactive)", TW: "Tsai-Wu (interactive)", "IFF-A": "IFF mode A", "IFF-B": "IFF mode B", "IFF-C": "IFF mode C",
};

export function fmt(v: number | null | undefined, digits = 4): string {
  if (v === null || v === undefined || !Number.isFinite(v)) return "—";
  const a = Math.abs(v);
  if (a !== 0 && (a < 1e-3 || a >= 1e6)) return v.toExponential(Math.max(1, digits - 1));
  return Number(v.toPrecision(digits)).toLocaleString("en-US", { maximumFractionDigits: 8 });
}

export function rfText(v: number | null | undefined): string {
  if (v === null || v === undefined || v < 0) return "no failure";
  return fmt(v, 4);
}
