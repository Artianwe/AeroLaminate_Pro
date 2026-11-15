// AeroLaminate Pro - shared types. Author: Anwesh Ajitabh Dash.

export type Status = "datasheet" | "literature" | "calculated" | "estimated" | "illustrative" | "unavailable";
export type Verification = "primary" | "secondary" | "unverified";
export interface Prop { value: number | null; unit: string; status: Status; source?: string; note?: string; verification?: Verification; verification_note?: string }
export interface Material {
  id: string; name: string; origin?: string; manufacturer?: string; form?: string; cure?: string; condition?: string;
  direction_convention?: string; applicability?: string; properties: Record<string, Prop>;
}

export interface PlyIn { angle: number; thickness?: number | null; material_id?: string | null }
export interface Loads { Nx: number; Ny: number; Nxy: number; Mx: number; My: number; Mxy: number; Qx: number; Qy: number }
export interface Env { T_stress_free: number; T_service: number; moisture: number; hotwet_knockdown: boolean; T_reference: number }
export interface Options {
  fos: number; tsai_wu_F12_star: number; puck_p_pt: number; puck_p_pc: number; larc_alpha0_deg: number; larc_insitu: boolean;
  hashin_ST: number | null;
  allow_illustrative?: boolean;
}
export const CRITERIA = ["max_stress", "max_strain", "tsai_hill", "tsai_wu", "hashin", "puck", "larc03"] as const;
export type Criterion = (typeof CRITERIA)[number];

export interface ProjectPayload {
  material_id: string; materials?: Material[]; plies: PlyIn[]; loads: Loads; environment: Env; criteria: Criterion[]; options: Options;
}

export interface ModuleSettings {
  buckling: { a: number; b: number; terms: number };
  notch: { diameter: number; width: number | null; d0: number; a0: number; sigma0: number | null; criterion: Criterion };
  envSweep: { mode: "T" | "dC"; start: number; stop: number; points: number; plate_a: number; plate_b: number };
  pfa: { criterion: Criterion; d_fibre: number; d_matrix: number };
  interlaminar: { delam_interfaces: number[] };
  fatigue: { criterion: Criterion; model: "loglinear" | "power"; params: Record<string, number>; blocks: { load_factor: number; cycles: number }[]; static_rf: number | null; R_ratio: number };
  uq: { criterion: Criterion; samples: number; seed: number; distribution: "normal" | "lognormal"; cov: Record<string, number>; rel_step: number };
  parametric: { vary_plies: number[]; start: number; stop: number; step: number };
  envelope: { plane: "s1s2" | "s2t12" | "s1t12"; fixed: number; laminate_plane: "NxNy" | "NxNxy" | "NyNxy" };
  opt: Record<string, number | boolean | string | number[]>;
}

export interface Project {
  schema: "aerolaminate-project/1";
  name: string;
  author: string;
  notes: string;
  payload: ProjectPayload;
  modules: ModuleSettings;
  savedAt?: string;
}

// The analysis response is large and mostly numeric; it is typed loosely and accessed defensively.
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export type Json = any;
