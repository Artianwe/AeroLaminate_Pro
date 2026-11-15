"""AeroLaminate Pro REST API.

Author, owner and maintainer: Anwesh Ajitabh Dash.
Run: uvicorn app.main:app --host 127.0.0.1 --port 8000   (from the backend/ directory)
"""
from __future__ import annotations

import math
import os
from pathlib import Path
from typing import Any, Literal

import numpy as np
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator

from aerolaminate import __author__, __version__
from aerolaminate import buckling as BK
from aerolaminate import criteria as C
from aerolaminate import designrules, environment as ENV, fatigue as FT, interlaminar as IL, notched as NT
from aerolaminate import optimize as OPT, progressive as PFA, strength as S, uncertainty as UQ
from aerolaminate.clt import Laminate, LaminateInputError, SingularLaminateError, expand_plies, stiffness_vs_orientation
from aerolaminate.materials import (CAUTION_STATUSES, MaterialDatabase, MaterialValidationError, MissingPropertyError,
                                    validate_material_dict)

USER_FILE = Path(os.environ.get("AEROLAMINATE_USER_DATA", Path(__file__).resolve().parents[1] / "user_data")) / "materials_user.json"
DB = MaterialDatabase(USER_FILE)

app = FastAPI(title="AeroLaminate Pro API", version=__version__,
              description="Composite laminate analysis engine. Author, owner and maintainer: Anwesh Ajitabh Dash.",
              contact={"name": "Anwesh Ajitabh Dash"})
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
                   allow_methods=["*"], allow_headers=["*"])


# ----------------------------------------------------------------------------- error mapping
@app.exception_handler(MissingPropertyError)
async def _missing(_: Request, e: MissingPropertyError):
    return JSONResponse(status_code=400, content={"detail": str(e), "kind": "missing_property"})


@app.exception_handler(SingularLaminateError)
async def _singular(_: Request, e: SingularLaminateError):
    return JSONResponse(status_code=400, content={"detail": str(e), "kind": "singular_laminate"})


@app.exception_handler(C.CriterionUnavailable)
async def _unavail(_: Request, e: C.CriterionUnavailable):
    return JSONResponse(status_code=400, content={"detail": str(e), "kind": "criterion_unavailable"})


@app.exception_handler(LaminateInputError)
@app.exception_handler(MaterialValidationError)
@app.exception_handler(ValueError)
async def _value(_: Request, e: Exception):
    return JSONResponse(status_code=400, content={"detail": str(e), "kind": "invalid_input"})


@app.exception_handler(KeyError)
async def _key(_: Request, e: KeyError):
    return JSONResponse(status_code=404, content={"detail": str(e).strip("'\""), "kind": "not_found"})


# ----------------------------------------------------------------------------- schemas
def _finite(v):
    if v is not None and not math.isfinite(v):
        raise ValueError("must be a finite number")
    return v


class PlyIn(BaseModel):
    angle: float = Field(ge=-180, le=180)
    thickness: float | None = Field(default=None, gt=0, le=50)
    material_id: str | None = None


class LoadsIn(BaseModel):
    Nx: float = 0; Ny: float = 0; Nxy: float = 0
    Mx: float = 0; My: float = 0; Mxy: float = 0
    Qx: float = 0; Qy: float = 0

    @field_validator("*")
    @classmethod
    def _f(cls, v):
        return _finite(v)


class EnvIn(BaseModel):
    T_stress_free: float = Field(default=20.0, ge=-273, le=500)
    T_service: float = Field(default=20.0, ge=-273, le=500)
    moisture: float = Field(default=0.0, ge=0, le=10)
    hotwet_knockdown: bool = False
    T_reference: float = 21.0


class OptionsIn(BaseModel):
    fos: float = Field(default=1.5, gt=0, le=10)
    tsai_wu_F12_star: float = Field(default=-0.5, gt=-1, lt=1)
    puck_p_pt: float = Field(default=0.35, gt=0, lt=1)
    puck_p_pc: float = Field(default=0.30, gt=0, lt=1)
    larc_alpha0_deg: float = Field(default=53.0, ge=45, le=60)
    larc_insitu: bool = True
    hashin_ST: float | None = Field(default=None, gt=0)
    allow_illustrative: bool = False   # explicit demonstration-mode opt-in for records with illustrative values


class ProjectIn(BaseModel):
    material_id: str
    materials: list[dict[str, Any]] | None = None   # unsaved inline records (override the database by id)
    plies: list[PlyIn] = Field(min_length=1, max_length=400)
    loads: LoadsIn = LoadsIn()
    environment: EnvIn = EnvIn()
    criteria: list[str] = Field(default_factory=lambda: list(C.CRITERIA))
    options: OptionsIn = OptionsIn()

    @field_validator("criteria")
    @classmethod
    def _crit(cls, v):
        bad = [c for c in v if c not in C.CRITERIA]
        if bad:
            raise ValueError(f"Unknown criteria {bad}; allowed {list(C.CRITERIA)}")
        return v


# ----------------------------------------------------------------------------- context
CORE_PROPS = ("E1", "E2", "G12", "nu12", "Xt", "Xc", "Yt", "Yc", "S12")


class IllustrativeDataBlocked(ValueError):
    """Analysis refused because a material carries illustrative (placeholder) values and demonstration mode is off."""


@app.exception_handler(IllustrativeDataBlocked)
async def _illus(_: Request, e: IllustrativeDataBlocked):
    return JSONResponse(status_code=400, content={"detail": str(e), "kind": "illustrative_blocked"})


class Ctx:
    def __init__(self, p: ProjectIn):
        inline = {}
        for m in p.materials or []:
            mat = validate_material_dict(m)
            mat.meta["origin"] = "inline"
            inline[mat.id] = mat
        lookup = lambda mid: inline[mid] if mid in inline else DB.get(mid)
        self.material = lookup(p.material_id)
        self.plies0 = expand_plies(lookup, [q.model_dump() for q in p.plies], self.material)
        illus = sorted({pl.material.name for pl in self.plies0 if any(pl.material.status(k) == "illustrative" for k in CORE_PROPS)})
        if illus and not p.options.allow_illustrative:
            raise IllustrativeDataBlocked(
                f"Analysis blocked: {', '.join(illus)} uses ILLUSTRATIVE (placeholder) property values that are not verified data. "
                "Enter verified values in the Materials tab, or explicitly enable demonstration mode to view workflow-only results.")
        env = p.environment
        self.dT = env.T_service - env.T_stress_free
        self.dC = env.moisture
        self.copt = C.CriterionOptions(p.options.tsai_wu_F12_star, p.options.puck_p_pt, p.options.puck_p_pc,
                                       p.options.larc_alpha0_deg, p.options.larc_insitu, p.options.hashin_ST)
        self.fos = p.options.fos
        self.kd = None
        self.warnings: list[str] = []
        self.plies = self.plies0
        if env.hotwet_knockdown:
            self.kd = ENV.knockdown_factors(self.plies0, env.T_service, env.moisture, env.T_reference)
            self.plies = ENV.apply_knockdown(self.plies0, self.kd)
            self.warnings.append(f"Hot/wet knockdown (Chamis 1984 empirical estimate) applied: matrix-property retention "
                                 f"{float(self.kd['E2'].min()):.3f} at {env.T_service:g} C, {env.moisture:g} % moisture")
        self.lam = Laminate(self.plies)
        self.St = C.build_strengths(self.plies, self.kd)
        L = p.loads
        self.N = np.array([L.Nx, L.Ny, L.Nxy], float)
        self.M = np.array([L.Mx, L.My, L.Mxy], float)
        self.Q = (L.Qx, L.Qy)
        self.criteria = p.criteria
        self.p = p

    def provenance(self, extra: tuple[str, ...] = ()) -> dict:
        used = ["E1", "E2", "G12", "nu12", "Xt", "Xc", "Yt", "Yc", "S12", "density"] + list(extra)
        if self.dT:
            used += ["alpha1", "alpha2"]
        if self.dC:
            used += ["beta1", "beta2"]
        mats = {pl.material.id: pl.material for pl in self.plies}
        out, ver, warn = {}, {}, []
        for mid, m in mats.items():
            out[mid] = {k: m.status(k) for k in used}
            ver[mid] = {k: (m.verification(k) if m.has(k) else "n/a") for k in used}
            warn += m.caution_list(used)
            warn += m.plausibility_warnings()
            unv = m.unverified_list(used)
            if unv:
                warn.append(f"{m.name}: {len(unv)} of the properties used are NOT verified against a primary source ({', '.join(unv)})")
            if any(m.status(k) == "illustrative" for k in used):
                warn.insert(0, f"{m.name}: ILLUSTRATIVE property values in use (demonstration mode) - results must not be used for engineering decisions")
        flags = list(self.St.flags)
        for m in mats.values():
            flags += [f for f in m.flags if f not in flags]
        return {"status": out, "verification": ver, "warnings": self.warnings + warn, "flags": flags}


def _fin(x):
    if isinstance(x, (float, np.floating)):
        return float(x) if np.isfinite(x) else None
    if isinstance(x, np.ndarray):
        return _fin(x.tolist())
    if isinstance(x, (list, tuple)):
        return [_fin(v) for v in x]
    if isinstance(x, dict):
        return {k: _fin(v) for k, v in x.items()}
    if isinstance(x, np.integer):
        return int(x)
    if isinstance(x, np.bool_):
        return bool(x)
    return x


# ----------------------------------------------------------------------------- endpoints
@app.get("/api/health")
def health():
    return {"status": "ok", "app": "AeroLaminate Pro", "version": __version__, "author": __author__,
            "criteria": {k: C.CRITERION_LABEL[k] for k in C.CRITERIA}}


@app.get("/api/materials")
def materials():
    return {"materials": [m.to_dict() for m in DB.all()], "references": DB.references,
            "user_file_error": getattr(DB, "user_error", None)}


@app.put("/api/materials/{mid}")
def save_material(mid: str, body: dict[str, Any]):
    body = {**body, "id": mid}
    if mid in DB.shipped and not body.get("allow_shadow_shipped"):
        raise ValueError("Shipped records are read-only; save the edited record under a new id")
    return DB.save_user(body).to_dict()


@app.delete("/api/materials/{mid}")
def delete_material(mid: str):
    DB.delete_user(mid)
    return {"deleted": mid}


@app.post("/api/analyze")
def analyze(p: ProjectIn):
    c = Ctx(p)
    lam = c.lam
    lam.check_solvable()
    r = lam.solve(c.N, c.M, c.dT, c.dC)
    NT, MT = lam.hygrothermal_resultants(c.dT, c.dC)
    st = lam.ply_state(r, ("bottom", "middle", "top"))
    fail = S.evaluate_criteria(lam, c.St, c.N, c.M, c.dT, c.dC, c.criteria, c.copt, c.fos)
    prov = c.provenance()
    for k, reasons in fail["unavailable"].items():
        prov["warnings"].append(f"{C.CRITERION_LABEL[k]} unavailable: " + "; ".join(reasons))
    fpf = None
    avail = {k: v["critical"] for k, v in fail["results"].items()}
    if avail:
        finite = {k: v for k, v in avail.items() if v["rf"] is not None}
        if finite:
            kmin = min(finite, key=lambda k: finite[k]["rf"])
            fpf = {"criterion": kmin, **finite[kmin]}
    # Display hygiene: zero round-off-level B terms and interface coordinates (the solver itself keeps full precision).
    scaleB = 1e-10 * np.sqrt(np.linalg.norm(lam.A) * np.linalg.norm(lam.D))
    Bd = np.where(np.abs(lam.B) < scaleB, 0.0, lam.B)
    zd = np.where(np.abs(lam.z) < 1e-12 * lam.h, 0.0, lam.z)
    out = {
        "laminate": {"n_plies": len(lam.plies), "h": lam.h, "z": zd,
                     "plies": [{"index": i + 1, "angle": pl.angle, "thickness": pl.thickness, "material_id": pl.material.id,
                                "material": pl.material.name} for i, pl in enumerate(lam.plies)],
                     "areal_mass": lam.areal_mass()},
        "matrices": {"A": lam.A, "B": Bd, "D": lam.D, "ABD": np.block([[lam.A, Bd], [Bd, lam.D]]), "abd": np.linalg.inv(lam.ABD),
                     "Q": lam.Q, "Qbar": lam.Qbar},
        "diagnostics": lam.diagnostics, "classification": lam.classify(), "coupling": lam.coupling(),
        "engineering_constants": lam.engineering_constants(),
        "response": {**_chop_response(r.eps0, r.kappa, lam.h), "N_HT": NT, "M_HT": MT, "dT": c.dT, "dC": c.dC},
        "ply_state": {k: v for k, v in st.items()},
        "failure": fail, "fpf": fpf, "fos": c.fos,
        "design_rules": designrules.check([pl.angle for pl in lam.plies], [pl.thickness for pl in lam.plies]),
        "orientation": stiffness_vs_orientation(lam, 3.0),
        "provenance": prov,
    }
    return _fin(out)


def _chop_response(eps0, kappa, h):
    """Zero round-off-level components for display: strain-equivalent magnitudes below 1e-12 of the largest one."""
    mag = np.concatenate([np.abs(eps0), np.abs(kappa) * h / 2])
    tol = 1e-12 * max(mag.max(), 1e-300)
    return {"eps0": np.where(np.abs(eps0) < tol, 0.0, eps0), "kappa": np.where(np.abs(kappa) * h / 2 < tol, 0.0, kappa)}


class EnvelopeIn(BaseModel):
    project: ProjectIn
    ply: int = Field(default=1, ge=1)
    plane: Literal["s1s2", "s2t12", "s1t12"] = "s1s2"
    fixed: float = 0.0
    laminate_plane: Literal["NxNy", "NxNxy", "NyNxy"] = "NxNy"


@app.post("/api/envelope")
def envelope(b: EnvelopeIn):
    c = Ctx(b.project)
    k = b.ply - 1
    if k >= len(c.plies):
        raise ValueError(f"Ply {b.ply} does not exist")
    St1 = C.build_strengths([c.plies[k]], {kk: v[k:k + 1] for kk, v in c.kd.items()} if c.kd else None)
    ply_env, lam_env, unavailable = {}, {}, {}
    for name in c.criteria:
        try:
            ply_env[name] = S.ply_envelope(St1, name, c.copt, b.plane, b.fixed)
            lam_env[name] = S.laminate_envelope(c.lam, c.St, name, c.copt, c.dT, c.dC, b.laminate_plane)
        except C.CriterionUnavailable as e:
            unavailable[name] = e.reasons
    r = c.lam.solve(c.N, c.M, c.dT, c.dC)
    s12 = c.lam.ply_state(r, ("bottom", "top"))["sigma_12"][k]
    ax = {"s1s2": (0, 1), "s2t12": (1, 2), "s1t12": (0, 2)}[b.plane]
    lax = {"NxNy": (0, 1), "NxNxy": (0, 2), "NyNxy": (1, 2)}[b.laminate_plane]
    return _fin({"ply": b.ply, "plane": b.plane, "fixed": b.fixed, "ply_envelopes": ply_env,
                 "applied_ply": [[float(s[ax[0]]), float(s[ax[1]])] for s in s12],
                 "laminate_plane": b.laminate_plane, "laminate_envelopes": lam_env,
                 "applied_laminate": [float(c.N[lax[0]]), float(c.N[lax[1]])],
                 "unavailable": unavailable,
                 "note": "Ply envelopes exclude residual stresses (material strength surface). Laminate envelopes include the hygrothermal residual state."})


class PFAIn(BaseModel):
    project: ProjectIn
    criterion: Literal["max_stress", "max_strain", "hashin", "puck", "larc03"] = "hashin"
    d_fibre: float = Field(default=0.01, gt=0, le=1)
    d_matrix: float = Field(default=0.2, gt=0, le=1)


@app.post("/api/progressive")
def progressive(b: PFAIn):
    c = Ctx(b.project)
    res = PFA.run(c.plies, c.St, c.N, c.M, c.dT, c.dC, PFA.PFAOptions(b.criterion, b.d_fibre, b.d_matrix), c.copt)
    # Governing failure index of the pristine laminate versus load factor (residual stresses included)
    top = res["lpf_load_factor"] or res["fpf_load_factor"] or 1.0
    lams = np.linspace(0, 1.15 * top, 47)
    s_res, s_m = S.ply_stress_split(c.lam, c.N, c.M, c.dT, c.dC)
    fi_curves = {}
    for name in c.criteria:
        try:
            vals = []
            for L in lams:
                s = s_res + L * s_m
                fi, _ = C.governing(C.evaluate(name, s[..., 0], s[..., 1], s[..., 2], c.St, c.copt))
                vals.append(float(fi.max()))
            fi_curves[name] = vals
        except C.CriterionUnavailable:
            pass
    res["fi_vs_load"] = {"load_factor": lams.tolist(), "fi": fi_curves,
                         "note": "Pristine laminate (no degradation). FI definitions differ between criteria; FI = 1 is failure for all."}
    res["provenance"] = c.provenance()
    return _fin(res)


class EnvSweepIn(BaseModel):
    project: ProjectIn
    mode: Literal["T", "dC"] = "T"
    start: float = -55.0
    stop: float = 120.0
    points: int = Field(default=36, ge=2, le=200)
    plate_a: float = Field(default=300.0, gt=0)
    plate_b: float = Field(default=300.0, gt=0)


@app.post("/api/environment")
def environment(b: EnvSweepIn):
    c = Ctx(b.project)
    env = b.project.environment
    vals = np.linspace(b.start, b.stop, b.points)
    builder = lambda pl, kd: C.build_strengths(pl, kd)
    sw = ENV.sweep(c.plies0, builder, c.N, c.M, b.mode, vals, c.dT, c.dC, c.criteria, c.copt,
                   T_stress_free=env.T_stress_free, hotwet=env.hotwet_knockdown, T0_C=env.T_reference)
    out = {"sweep": sw, "mode": b.mode, "residual": ENV.residual_stress_profile(c.lam, c.dT, c.dC),
           "warpage": ENV.warpage(c.lam, c.dT, c.dC, b.plate_a, b.plate_b), "dT": c.dT, "dC": c.dC,
           "provenance": c.provenance()}
    if any(pl.material.has("Tg_dry") for pl in c.plies0):
        Ts = np.linspace(-55, 180, 48)
        tg = c.plies0[0].material.get("Tg_dry") if c.plies0[0].material.has("Tg_dry") else None
        if tg:
            ret = {}
            for M_ in (0.0, 0.5, 1.0, 1.5):
                row = []
                for T in Ts:
                    try:
                        row.append(ENV.chamis_retention(float(T), M_, tg, env.T_reference))
                    except ValueError:
                        row.append(None)
                ret[f"{M_:g}"] = row
            out["retention_curves"] = {"T": Ts.tolist(), "curves": ret, "Tg_dry": tg,
                                       "classification": "empirical estimate (Chamis 1984)"}
    return _fin(out)


class InterlamIn(BaseModel):
    project: ProjectIn
    delam_interfaces: list[int] = Field(default_factory=list)


@app.post("/api/interlaminar")
def interlaminar(b: InterlamIn):
    c = Ctx(b.project)
    out: dict[str, Any] = {"free_edge": IL.free_edge_indicators(c.lam)}
    Qx, Qy = c.Q
    if Qx or Qy:
        ts = IL.transverse_shear(c.lam, Qx, Qy)
        out["transverse_shear"] = ts
        out["check"] = IL.interlaminar_check(c.lam, ts, c.fos)
    else:
        out["transverse_shear"] = None
        out["message"] = "Enter transverse shear resultants Qx/Qy to recover interlaminar shear stresses"
    if b.delam_interfaces:
        r = c.lam.solve(c.N, c.M)
        try:
            ed = IL.edge_delamination(c.lam, b.delam_interfaces, float(r.eps0[0]))
            ed["flags"] = []
            if c.N[1] or c.N[2] or np.any(c.M):
                ed["flags"].append("O'Brien's G assumes uniform uniaxial strain; only the mechanical eps_x of this load case is used")
            if c.dT or c.dC:
                ed["flags"].append("Residual hygrothermal strain energy is not included")
            out["edge_delamination"] = ed
        except ValueError as e:
            out["edge_delamination"] = {"error": str(e)}
    out["provenance"] = c.provenance()
    return _fin(out)


class BucklingIn(BaseModel):
    project: ProjectIn
    a: float = Field(default=500.0, gt=0, le=1e5)
    b: float = Field(default=300.0, gt=0, le=1e5)
    terms: int = Field(default=8, ge=2, le=20)


@app.post("/api/buckling")
def buckling_ep(b: BucklingIn):
    c = Ctx(b.project)
    Nx, Ny, Nxy = float(c.N[0]), float(c.N[1]), float(c.N[2])
    res = BK.buckling(c.lam, b.a, b.b, Nx, Ny, Nxy, b.terms)
    if res.get("load_factor") is not None:
        # load factor versus aspect ratio a/b at fixed b (6 x 6 terms; trend plot)
        ratios = np.linspace(0.4, 4.0, 37)
        sw = []
        for r_ in ratios:
            lf, _, _ = BK.ritz(_buckling_D(c.lam), r_ * b.b, b.b, Nx, Ny, Nxy, 6, 6)
            sw.append(lf)
        res["aspect_sweep"] = {"a_over_b": ratios.tolist(), "load_factor": sw, "b": b.b}
    if np.any(c.M) or c.dT or c.dC:
        res["flags"].append("Only Nx, Ny, Nxy enter the buckling eigenproblem; moments and hygrothermal prestress are ignored")
    res["fos"] = c.fos
    return _fin(res)


def _buckling_D(lam):
    if np.linalg.norm(lam.B) > 1e-9 * np.sqrt(np.linalg.norm(lam.A) * np.linalg.norm(lam.D)):
        return lam.D - lam.B @ np.linalg.solve(lam.A, lam.B)
    return lam.D


class NotchIn(BaseModel):
    project: ProjectIn
    diameter: float = Field(default=6.35, gt=0)
    width: float | None = Field(default=None, gt=0)
    d0: float = Field(default=1.0, gt=0)
    a0: float = Field(default=4.0, gt=0)
    sigma0: float | None = Field(default=None, gt=0)
    criterion: str = "tsai_wu"


@app.post("/api/notched")
def notched(b: NotchIn):
    c = Ctx(b.project)
    Nx = float(c.N[0])
    sign = -1.0 if Nx < 0 else 1.0
    if b.sigma0:
        s0, src = b.sigma0, "user-entered unnotched strength"
    else:
        rf = S.laminate_rf(c.lam, c.St, (sign, 0, 0), (0, 0, 0), c.dT, c.dC, b.criterion, c.copt)
        if not np.isfinite(rf):
            raise ValueError("Cannot derive unnotched strength from CLT (no failure); enter sigma0")
        s0, src = rf / c.lam.h, f"CLT first-ply-failure estimate ({C.CRITERION_LABEL[b.criterion]}) - conservative, prefer test data"
    res = NT.open_hole(c.lam, b.diameter / 2, b.d0, b.a0, s0, src, b.width, Nx if Nx else None)
    res["loading"] = "compression" if sign < 0 else "tension"
    if c.N[1] or c.N[2] or np.any(c.M):
        res["flags"].append("Only Nx enters the open-hole model (uniaxial far field); Ny, Nxy and moments in the load case are ignored")
    if c.dT or c.dC:
        res["flags"].append("Hygrothermal residual stresses are not included in the notched-strength ratio (only in the CLT-derived sigma0)")
    res["flags"].append("d0/a0 defaults (1 mm, 4 mm) are typical literature values for carbon/epoxy (Whitney & Nuismer 1974) - calibrate with OHT/OHC tests")
    return _fin(res)


class FatigueIn(BaseModel):
    project: ProjectIn
    criterion: str = "tsai_wu"
    model: Literal["loglinear", "power"] = "loglinear"
    params: dict[str, float] = Field(default_factory=lambda: {"b": 0.1})
    blocks: list[dict[str, float]] = Field(default_factory=list)
    static_rf: float | None = Field(default=None, gt=0)
    R_ratio: float = 0.1


@app.post("/api/fatigue")
def fatigue_ep(b: FatigueIn):
    c = Ctx(b.project)
    rf = b.static_rf or S.laminate_rf(c.lam, c.St, c.N, c.M, c.dT, c.dC, b.criterion, c.copt)
    res = FT.miner(b.blocks, rf, b.model, b.params)
    res.update({"static_rf": rf, "static_basis": "user value" if b.static_rf else f"CLT FPF ({C.CRITERION_LABEL[b.criterion]})",
                "R_ratio": b.R_ratio})
    return _fin(res)


class UQIn(BaseModel):
    project: ProjectIn
    criterion: str = "tsai_wu"
    cov: dict[str, float] = Field(default_factory=lambda: {"E1": 0.05, "E2": 0.05, "G12": 0.05, "Xt": 0.08, "Xc": 0.08,
                                                            "Yt": 0.08, "Yc": 0.08, "S12": 0.08})
    samples: int = Field(default=400, ge=10, le=5000)
    seed: int = 1
    distribution: Literal["normal", "lognormal"] = "normal"
    rel_step: float = Field(default=0.05, gt=0, le=0.5)


@app.post("/api/uncertainty")
def uncertainty(b: UQIn):
    c = Ctx(b.project)
    if c.kd:
        raise ValueError("Uncertainty analysis with hot/wet knockdown is not supported; disable the knockdown or enter conditioned properties")
    mc = UQ.monte_carlo(c.plies, c.N, c.M, c.dT, c.dC, b.criterion, c.copt, b.cov, b.samples, b.seed, b.distribution)
    sens = UQ.sensitivity(c.plies, c.N, c.M, c.dT, c.dC, b.criterion, c.copt, b.rel_step)
    return _fin({"monte_carlo": mc, "sensitivity": sens, "provenance": c.provenance()})


class ParamIn(BaseModel):
    project: ProjectIn
    vary_plies: list[int] = Field(default_factory=list)  # 1-based
    start: float = 0.0
    stop: float = 90.0
    step: float = Field(default=5.0, gt=0)


@app.post("/api/parametric")
def parametric(b: ParamIn):
    c = Ctx(b.project)
    idx = [i - 1 for i in b.vary_plies if 1 <= i <= len(c.plies)]
    return _fin(UQ.angle_family_sweep(c.plies, idx, c.N, c.M, c.dT, c.dC, c.criteria, c.copt, b.start, b.stop, b.step, c.kd))


class OptIn(BaseModel):
    project: ProjectIn
    angles: list[float] = Field(default_factory=lambda: [0, 45, 90])
    symmetric: bool = True
    balanced: bool = True
    min_plies: int = Field(default=8, ge=1, le=200)
    max_plies: int = Field(default=32, ge=1, le=200)
    criterion: str = "tsai_wu"
    rf_min: float = Field(default=1.5, gt=0)
    min_Ex: float = 0; min_Ey: float = 0; min_Gxy: float = 0
    max_mass: float | None = None
    min_fraction: float = Field(default=0.1, ge=0, le=0.33)
    max_consecutive: int = Field(default=4, ge=0, le=50)
    outer_45: bool = False
    buckling: bool = False
    plate_a: float = 500.0
    plate_b: float = 300.0
    buckling_min: float = 1.0
    w_mass: float = 1.0; w_fi: float = 0.0; w_coupling: float = 0.0; w_buckling: float = 0.0
    pop: int = Field(default=40, ge=4, le=400)
    generations: int = Field(default=60, ge=1, le=500)
    seed: int = 7


@app.post("/api/optimize")
def optimize(b: OptIn):
    c = Ctx(b.project)
    if b.criterion not in C.CRITERIA:
        raise ValueError("Unknown criterion")
    if c.kd:
        raise ValueError("The optimiser does not apply the hot/wet knockdown; disable it or enter conditioned properties as a material record")
    t = c.plies0[0].thickness
    opt_flags = []
    if len({pl.material.id for pl in c.plies0}) > 1:
        opt_flags.append(f"Hybrid laminate: every candidate uses the material of ply 1 ({c.material.name})")
    if len({round(pl.thickness, 9) for pl in c.plies0}) > 1:
        opt_flags.append(f"Non-uniform ply thickness: every candidate uses the ply-1 thickness ({t:g} mm)")
    P = OPT.OptProblem(c.material, t, b.angles, b.symmetric, b.balanced, b.min_plies, b.max_plies, (c.N, c.M), c.dT, c.dC,
                       b.criterion, b.rf_min, b.min_Ex, b.min_Ey, b.min_Gxy, b.max_mass, b.min_fraction, b.max_consecutive,
                       b.outer_45, (b.plate_a, b.plate_b) if b.buckling else None, b.buckling_min,
                       b.w_mass, b.w_fi, b.w_coupling, b.w_buckling, b.pop, b.generations, b.seed)
    res = OPT.Optimizer(P, c.copt).run([pl.angle for pl in c.plies0])
    res["flags"] = opt_flags
    res["provenance"] = c.provenance()
    return _fin(res)
