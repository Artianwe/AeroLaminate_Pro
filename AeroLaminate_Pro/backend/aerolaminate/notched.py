"""Open-hole (notched) laminate strength: Lekhnitskii K_T, Konish-Whitney distribution, Whitney-Nuismer criteria.

Author: Anwesh Ajitabh Dash.

Infinite orthotropic plate with a circular hole of radius R under uniaxial far-field stress along laminate x.
K_T = 1 + sqrt(2 (sqrt(Ex/Ey) - nu_xy) + Ex/Gxy)                                (Lekhnitskii 1968)
sigma_x(0,y)/sigma = 1/2 {2 + r^2 + 3 r^4 - (K_T - 3)(5 r^6 - 7 r^8)},  r = R/y      (Konish & Whitney 1975)
PSC: sigma_N/sigma_0 = 2 / (2 + xi^2 + 3 xi^4 - (K_T-3)(5 xi^6 - 7 xi^8)),  xi = R/(R+d0)
ASC: sigma_N/sigma_0 = 2(1-xi) / (2 - xi^2 - xi^4 + (K_T-3)(xi^6 - xi^8)),  xi = R/(R+a0)   (Whitney & Nuismer 1974)
d0 and a0 are EMPIRICAL and must be calibrated with ASTM D5766 / D6484 tests for the laminate family.
"""
from __future__ import annotations

import numpy as np

from .clt import Laminate


def kt_orthotropic(Ex, Ey, Gxy, nuxy) -> float:
    return float(1 + np.sqrt(2 * (np.sqrt(Ex / Ey) - nuxy) + Ex / Gxy))


def stress_distribution(KT: float, R: float, y: np.ndarray) -> np.ndarray:
    r = R / np.asarray(y, float)
    return 0.5 * (2 + r ** 2 + 3 * r ** 4 - (KT - 3) * (5 * r ** 6 - 7 * r ** 8))


def psc_ratio(KT: float, R: float, d0: float) -> float:
    xi = R / (R + d0)
    return float(2 / (2 + xi ** 2 + 3 * xi ** 4 - (KT - 3) * (5 * xi ** 6 - 7 * xi ** 8)))


def asc_ratio(KT: float, R: float, a0: float) -> float:
    xi = R / (R + a0)
    return float(2 * (1 - xi) / (2 - xi ** 2 - xi ** 4 + (KT - 3) * (xi ** 6 - xi ** 8)))


def finite_width_factor(R: float, W: float) -> float:
    """Isotropic finite-width correction K_T(W)/K_T(inf) (approximation when used for orthotropic plates)."""
    lam = 2 * R / W
    return float((2 + (1 - lam) ** 3) / (3 * (1 - lam)))


def open_hole(lam: Laminate, R: float, d0: float, a0: float, sigma0: float, sigma0_source: str,
              W: float | None = None, applied_Nx: float | None = None) -> dict:
    if R <= 0 or d0 <= 0 or a0 <= 0:
        raise ValueError("Hole radius and characteristic distances must be positive")
    if sigma0 <= 0:
        raise ValueError("Unnotched strength must be positive (magnitude)")
    flags = []
    cls = lam.classify()
    if not cls["balanced"]:
        flags.append("Laminate is not balanced (A16/A26 != 0): Lekhnitskii orthotropic K_T is not exact")
    if not cls["symmetric_stiffness"]:
        flags.append("Laminate is unsymmetric: bending coupling ignored in the notch model")
    c = lam.engineering_constants()
    KT = kt_orthotropic(c["Ex"], c["Ey"], c["Gxy"], c["nuxy"])
    fwc = 1.0
    if W is not None:
        if W <= 2 * R:
            raise ValueError("Plate width must exceed the hole diameter")
        fwc = finite_width_factor(R, W)
        flags.append("Isotropic finite-width correction applied to an orthotropic plate (approximation)")
    psc = psc_ratio(KT, R, d0) / fwc
    asc = asc_ratio(KT, R, a0) / fwc
    ys = R * np.linspace(1.0, 6.0, 121)
    dist = stress_distribution(KT, R, ys) * fwc
    out = {"KT_inf": KT, "fwc": fwc, "KT_net": KT * fwc, "psc_ratio": psc, "asc_ratio": asc,
           "sigma_N_psc": psc * sigma0, "sigma_N_asc": asc * sigma0, "sigma0": sigma0, "sigma0_source": sigma0_source,
           "N_psc": psc * sigma0 * lam.h, "N_asc": asc * sigma0 * lam.h,
           "distribution": {"y": ys.tolist(), "ratio": dist.tolist()}, "d0": d0, "a0": a0, "flags": flags,
           "classification": "semi-empirical (requires calibrated d0/a0)", "engineering_constants": c}
    if applied_Nx:
        out["rf_psc"] = abs(out["N_psc"] / applied_Nx)
        out["rf_asc"] = abs(out["N_asc"] / applied_Nx)
    # size-effect curve: notched/unnotched ratio vs hole diameter
    diam = np.linspace(1.0, 40.0, 60)
    out["size_effect"] = {"diameter": diam.tolist(),
                          "psc": [psc_ratio(KT, d / 2, d0) for d in diam],
                          "asc": [asc_ratio(KT, d / 2, a0) for d in diam]}
    return out
