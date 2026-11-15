"""Hygrothermal effects: residual stresses, sweeps, warpage and hot/wet property retention.

Author: Anwesh Ajitabh Dash.

Hot/wet retention uses the empirical relation of Chamis (1984, NASA TM-83320):
    P/P0 = [(T_gw - T) / (T_g0 - T_0)]^(1/2),   T_gw = (0.005 M^2 - 0.10 M + 1.0) T_g0,
with ALL temperatures in deg F (the T_gw expression is not unit-invariant) and M in % weight gain.
Applied to matrix-dominated properties only. It is an ESTIMATE, not test data.
"""
from __future__ import annotations

import numpy as np

from . import criteria as C
from .clt import Laminate, Ply
from .materials import MissingPropertyError
from .strength import laminate_rf

MATRIX_PROPS = ("E2", "G12", "Yt", "Yc", "S12")


def c_to_f(t):
    return np.asarray(t, float) * 9 / 5 + 32


def chamis_retention(T_C: float, M_pct: float, Tg_dry_C: float, T0_C: float = 21.0) -> float:
    if M_pct < 0 or M_pct > 10:
        raise ValueError("Moisture content must be within 0-10 % weight gain for the Chamis relation")
    Tg0, T, T0 = (float(c_to_f(x)) for x in (Tg_dry_C, T_C, T0_C))
    Tgw = (0.005 * M_pct ** 2 - 0.10 * M_pct + 1.0) * Tg0
    if T >= Tgw:
        raise ValueError(f"Temperature {T_C:.1f} C is at or above the estimated wet Tg ({(Tgw - 32) * 5 / 9:.1f} C)")
    if Tg0 <= T0:
        raise ValueError("Dry Tg must exceed the reference temperature")
    return float(min(1.0, np.sqrt((Tgw - T) / (Tg0 - T0))))


def knockdown_factors(plies: list[Ply], T_C: float, M_pct: float, T0_C: float = 21.0) -> dict:
    """Per-ply retention factors for matrix-dominated properties."""
    f = []
    for p in plies:
        if not p.material.has("Tg_dry"):
            raise MissingPropertyError(p.material.name, "Tg_dry", "hot/wet property retention estimate")
        f.append(chamis_retention(T_C, M_pct, p.material.get("Tg_dry"), T0_C))
    f = np.array(f)
    return {k: f for k in MATRIX_PROPS}


def apply_knockdown(plies: list[Ply], kd: dict) -> list[Ply]:
    """New plies whose stiffness factors include the matrix retention (E2, G12)."""
    out = []
    for p, fE2, fG in zip(plies, kd["E2"], kd["G12"]):
        out.append(Ply(p.material, p.angle, p.thickness, p.f_E1, p.f_E2 * fE2, p.f_G12 * fG, p.f_nu12))
    return out


def residual_stress_profile(lam: Laminate, dT: float, dC: float) -> dict:
    r = lam.solve((0, 0, 0), (0, 0, 0), dT, dC)
    st = lam.ply_state(r, ("bottom", "top"))
    return {"z": st["z"].tolist(), "sigma_12": st["sigma_12"].tolist(), "sigma_xy": st["sigma_xy"].tolist(),
            "eps0": r.eps0.tolist(), "kappa": r.kappa.tolist()}


def warpage(lam: Laminate, dT: float, dC: float, a: float, b: float, n: int = 21) -> dict:
    """Linear-CLT out-of-plane shape of a free a x b plate (centre at origin): w = -(kx x^2 + ky y^2 + kxy x y)/2."""
    r = lam.solve((0, 0, 0), (0, 0, 0), dT, dC)
    kx, ky, kxy = r.kappa
    xs = np.linspace(-a / 2, a / 2, n)
    ys = np.linspace(-b / 2, b / 2, n)
    X, Y = np.meshgrid(xs, ys)
    W = -(kx * X ** 2 + ky * Y ** 2 + kxy * X * Y) / 2
    W = W - W[n // 2, n // 2]
    return {"x": xs.tolist(), "y": ys.tolist(), "w": W.tolist(), "kappa": r.kappa.tolist(),
            "max_abs_w": float(np.abs(W).max()),
            "classification": "linear estimate",
            "warning": ("Thin unsymmetric laminates respond geometrically non-linearly and can be bistable (Hyer 1981); "
                        "linear CLT warpage is an indication only.") if np.linalg.norm(lam.B) > 1e-9 * np.linalg.norm(lam.A) * lam.h else None}


def sweep(plies: list[Ply], St_builder, N, M, mode: str, values, base_dT: float, base_dC: float, criteria: list[str],
          copt, T_stress_free: float | None = None, hotwet: bool = False, T0_C: float = 21.0) -> dict:
    """Sweep temperature (deg C; requires stress-free temperature) or moisture (% wt) and report RF and residual stresses.

    mode 'dT': values are temperature differences (deg C) relative to the stress-free state.
    mode 'T': values are absolute temperatures; dT = T - T_stress_free; with hotwet, matrix properties are retained per Chamis.
    mode 'dC': values are moisture contents (% wt), dT fixed at base_dT.
    """
    out = {"x": [], "rf": {c: [] for c in criteria}, "max_sigma2_residual": [], "max_tau12_residual": [],
           "kappa_residual": [], "retention": [], "warnings": []}
    for v in values:
        v = float(v)
        if mode == "dT":
            dT, dC, T = v, base_dC, None
        elif mode == "T":
            if T_stress_free is None:
                raise ValueError("Temperature sweep needs the stress-free temperature")
            dT, dC, T = v - T_stress_free, base_dC, v
        elif mode == "dC":
            dT, dC, T = base_dT, v, None
        else:
            raise ValueError("mode must be 'dT', 'T' or 'dC'")
        pl, kd = plies, None
        if hotwet:
            Tuse = T if T is not None else T0_C + dT if T_stress_free is None else T_stress_free + dT
            try:
                kd = knockdown_factors(plies, Tuse, max(dC, 0.0), T0_C)
            except ValueError as e:
                out["warnings"].append(f"x={v:g}: {e}")
                out["x"].append(v)
                for c in criteria:
                    out["rf"][c].append(None)
                out["max_sigma2_residual"].append(None); out["max_tau12_residual"].append(None)
                out["kappa_residual"].append(None); out["retention"].append(None)
                continue
            pl = apply_knockdown(plies, kd)
        lam = Laminate(pl)
        St = St_builder(pl, kd)
        r = lam.solve((0, 0, 0), (0, 0, 0), dT, dC)
        s = lam.ply_state(r, ("bottom", "top"))["sigma_12"]
        out["x"].append(v)
        out["max_sigma2_residual"].append(float(s[..., 1].max()))
        out["max_tau12_residual"].append(float(np.abs(s[..., 2]).max()))
        out["kappa_residual"].append(r.kappa.tolist())
        out["retention"].append(float(kd["E2"][0]) if kd else 1.0)
        for c in criteria:
            try:
                rf = laminate_rf(lam, St, N, M, dT, dC, c, copt)
                out["rf"][c].append(rf if np.isfinite(rf) else None)
            except C.CriterionUnavailable:
                out["rf"][c].append(None)
    return out
