"""Progressive (ply-discount) failure analysis, FPF -> LPF.

Author: Anwesh Ajitabh Dash.

Method (RESEARCH_AND_GAP_ANALYSIS.md section 4.1): incremental ply discount under proportional mechanical loading,
with the hygrothermal state held constant. Mode-dependent degradation:
  fibre failure  -> E1, E2, G12, nu12 multiplied by d_f
  matrix failure -> E2, G12, nu12 multiplied by d_m
The discount factors are modelling choices (Tay et al. 2008; Garnich & Akula 2009), not material data.
This is a screening method: it is mesh-free, it has no energy regularisation, and it is sensitive to d_f and d_m.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from . import criteria as C
from .clt import Laminate, Ply, SingularLaminateError
from .strength import reserve_factor


@dataclass
class PFAOptions:
    criterion: str = "hashin"
    d_fibre: float = 0.01
    d_matrix: float = 0.20
    max_steps: int = 200
    max_inner: int = 100
    lpf_stiffness_ratio: float = 0.05
    tol: float = 1e-9


def _build(plies: list[Ply], fib: np.ndarray, mat: np.ndarray, o: PFAOptions) -> Laminate:
    new = []
    for p, f, m in zip(plies, fib, mat):
        q = Ply(p.material, p.angle, p.thickness)
        if f:
            q.f_E1 = q.f_E2 = q.f_G12 = q.f_nu12 = o.d_fibre
        elif m:
            q.f_E2 = q.f_G12 = q.f_nu12 = o.d_matrix
        new.append(q)
    return Laminate(new)


def _state_rf(lam, St, N, M, dT, dC, fib, mat, o, copt):
    """RF of every ply's intact modes for the current degraded laminate (min over bottom/top)."""
    r_res = lam.solve((0, 0, 0), (0, 0, 0), dT, dC)
    r_m = lam.solve(N, M)
    s_res = lam.ply_state(r_res, ("bottom", "top"))["sigma_12"]
    s_m = lam.ply_state(r_m, ("bottom", "top"))["sigma_12"]
    modes_all = None
    exclude = []
    for f, m in zip(fib, mat):
        ex = set()
        if f:
            ex = {"FT", "FC", "MT", "MC", "S", "IFF-A", "IFF-B", "IFF-C"}
        elif m:
            ex = {"MT", "MC", "S", "IFF-A", "IFF-B", "IFF-C"}
        exclude.append(ex)
    rf = reserve_factor(o.criterion, s_res, s_m, St, copt, exclude_modes=exclude)
    # all-excluded plies give -inf FI -> rf inf, as intended
    return rf.min(axis=1), s_res, s_m, exclude, modes_all


def _failed_modes_at(lam_load, St, s_res, s_m, exclude, o, copt):
    s = s_res + lam_load * s_m
    modes = C.evaluate(o.criterion, s[..., 0], s[..., 1], s[..., 2], St, copt)
    hits = []
    for k, ex in enumerate(exclude):
        for name, v in modes.items():
            if name in ex:
                continue
            if np.max(v[k]) >= 1.0 - 1e-7:
                hits.append((k, name))
    return hits


def run(plies: list[Ply], St, N, M, dT: float, dC: float, o: PFAOptions, copt: C.CriterionOptions) -> dict:
    if o.criterion not in C.MODE_BASED:
        raise ValueError(f"Progressive failure needs a mode-identifying criterion {sorted(C.MODE_BASED)}; "
                         f"'{o.criterion}' does not distinguish fibre from matrix failure")
    if not (0 < o.d_fibre <= 1 and 0 < o.d_matrix <= 1):
        raise ValueError("Degradation factors must lie in (0, 1]")
    N = np.asarray(N, float); M = np.asarray(M, float)
    if not np.any(N) and not np.any(M):
        raise ValueError("Progressive failure needs a non-zero mechanical load direction")
    n = len(plies)
    fib = np.zeros(n, bool); mat = np.zeros(n, bool)
    lam0 = _build(plies, fib, mat, o)
    k0 = lam0.secant_stiffness(N, M)
    Fvec = np.concatenate([N, M])
    dom = int(np.argmax(np.abs(Fvec)))
    labels = ["eps_x", "eps_y", "gamma_xy", "kappa_x", "kappa_y", "kappa_xy"]
    steps, curve = [], [{"load": 0.0, "response": 0.0, "event": "start"}]
    load = 0.0
    fpf = lpf = None
    lpf_reason = "maximum number of steps reached"
    lam = lam0
    for step in range(o.max_steps):
        try:
            rf_ply, s_res, s_m, exclude, _ = _state_rf(lam, St, N, M, dT, dC, fib, mat, o, copt)
        except SingularLaminateError:
            lpf, lpf_reason = load, "[ABD] singular"
            break
        lam_next = float(np.min(rf_ply))
        if not np.isfinite(lam_next):
            lpf_reason = "no further failure possible along this load path (remaining modes cannot fail)"
            lpf = None
            break
        load = max(load, lam_next)
        r_before = lam.solve(N * load, M * load, dT, dC)
        x_before = np.concatenate([r_before.eps0, r_before.kappa])[dom]
        curve.append({"load": load, "response": float(x_before), "event": "pre-failure"})
        if fpf is None:
            fpf = load
        failed_now = []
        converged = False
        for it in range(o.max_inner):
            hits = _failed_modes_at(load, St, s_res, s_m, exclude, o, copt)
            if not hits and it == 0:
                # The critical ply sits exactly at RF (bisection tolerance); fail its governing intact mode.
                hits = [(int(np.argmin(rf_ply)), "?")]
            if not hits:
                converged = True
                break
            for k, mode in hits:
                if mode == "?":  # numerical edge: ply at RF but below FI tolerance -> treat its governing intact mode
                    s = s_res + load * s_m
                    modes = C.evaluate(o.criterion, s[..., 0], s[..., 1], s[..., 2], St, copt)
                    cand = {nm: np.max(v[k]) for nm, v in modes.items() if nm not in exclude[k]}
                    mode = max(cand, key=cand.get)
                if C.is_fibre_mode(mode):
                    fib[k] = True; mat[k] = True
                else:
                    mat[k] = True
                failed_now.append({"ply": k + 1, "angle": plies[k].angle, "mode": mode, "iteration": it + 1})
            try:
                lam = _build(plies, fib, mat, o)
                rf_ply, s_res, s_m, exclude, _ = _state_rf(lam, St, N, M, dT, dC, fib, mat, o, copt)
            except SingularLaminateError:
                break
        try:
            ks = lam.secant_stiffness(N, M)
            r_after = lam.solve(N * load, M * load, dT, dC)
            x_after = float(np.concatenate([r_after.eps0, r_after.kappa])[dom])
            ec = lam.engineering_constants()
            singular = False
        except SingularLaminateError:
            ks, x_after, ec, singular = 0.0, None, None, True
        steps.append({"step": step + 1, "load_factor": load, "failed": failed_now, "converged": converged,
                      "n_fibre_failed": int(fib.sum()), "n_matrix_failed": int(mat.sum()),
                      "stiffness_ratio": ks / k0 if k0 > 0 else 0.0,
                      "Ex": ec["Ex"] if ec else None, "Ey": ec["Ey"] if ec else None, "Gxy": ec["Gxy"] if ec else None,
                      "ply_state": ["F" if f else ("M" if m else "-") for f, m in zip(fib, mat)]})
        if x_after is not None:
            curve.append({"load": load, "response": x_after, "event": "post-degradation"})
        if singular:
            lpf, lpf_reason = load, "[ABD] singular after degradation"
            break
        if fib.all():
            lpf, lpf_reason = load, "all plies fibre-failed"
            break
        if ks / k0 < o.lpf_stiffness_ratio:
            lpf, lpf_reason = load, f"secant stiffness below {o.lpf_stiffness_ratio:.0%} of pristine"
            break
        if not converged:
            lpf, lpf_reason = load, "equilibrium iterations did not converge (unstable damage growth)"
            break
    return {"criterion": o.criterion, "fpf_load_factor": fpf, "lpf_load_factor": lpf, "lpf_reason": lpf_reason,
            "response_label": labels[dom], "curve": curve, "steps": steps,
            "degradation": {"d_fibre": o.d_fibre, "d_matrix": o.d_matrix},
            "classification": "screening (ply-discount)",
            "notes": ["Load factors multiply the applied mechanical load; hygrothermal state held constant.",
                      "Results depend on the chosen discount factors and do not model load redistribution in a structure."]}
