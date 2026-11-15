"""Monte Carlo propagation of material variability, one-at-a-time sensitivities and parametric sweeps.

Author: Anwesh Ajitabh Dash.

The Monte Carlo results are NOT CMH-17 A/B-basis allowables: those need batch/panel-structured test data, pooling
and specific statistical procedures (CMH-17-1G ch. 8). Each material is sampled once per realisation (properties are fully
correlated across plies of the same material, which represents one material lot). Properties are sampled independently of
each other.
"""
from __future__ import annotations

import numpy as np

from . import criteria as C
from .clt import Laminate, Ply
from .strength import laminate_rf

SAMPLED = ("E1", "E2", "G12", "nu12", "Xt", "Xc", "Yt", "Yc", "S12")


def _replace(plies: list[Ply], overrides: dict[str, dict[str, float]], thickness_scale: float = 1.0) -> list[Ply]:
    cache = {}
    out = []
    for p in plies:
        mid = p.material.id
        if mid not in cache:
            cache[mid] = p.material.with_overrides(overrides.get(mid, {}), status=p.material.status("E1"), note="sampled") \
                if overrides.get(mid) else p.material
        out.append(Ply(cache[mid], p.angle, p.thickness * thickness_scale))
    return out


def monte_carlo(plies, N, M, dT, dC, criterion, copt, cov: dict[str, float], n: int = 500, seed: int = 1,
                dist: str = "normal") -> dict:
    if not (10 <= n <= 5000):
        raise ValueError("Number of samples must be within 10..5000")
    rng = np.random.default_rng(seed)
    mats = {p.material.id: p.material for p in plies}
    for k, v in cov.items():
        if k not in SAMPLED:
            raise ValueError(f"Cannot sample '{k}'; allowed: {SAMPLED}")
        if not (0 <= v <= 0.5):
            raise ValueError(f"CoV for {k} must be within 0..0.5")
    rfs, rejected = [], 0
    for _ in range(n):
        ov = {}
        for mid, m in mats.items():
            d = {}
            for k, c in cov.items():
                if c == 0:
                    continue
                mu = m.get(k)
                if dist == "lognormal":
                    s = np.sqrt(np.log(1 + c ** 2))
                    d[k] = mu * np.exp(rng.normal(-s ** 2 / 2, s))
                else:
                    d[k] = rng.normal(mu, c * abs(mu))
            ov[mid] = d
        ok = all(v > 0 for d in ov.values() for k, v in d.items() if k != "nu12")
        try:
            pl = _replace(plies, ov)
            if not ok:
                raise ValueError
            lam = Laminate(pl)
            St = C.build_strengths(pl)
            rfs.append(laminate_rf(lam, St, N, M, dT, dC, criterion, copt))
        except (ValueError, np.linalg.LinAlgError):
            rejected += 1  # non-physical sample (negative modulus, inadmissible Poisson ratio)
    r = np.array([x for x in rfs if np.isfinite(x)])
    if r.size == 0:
        raise ValueError("No finite reserve factors in the sample (load may not cause failure)")
    pf = float(np.mean(r < 1.0))
    # Wilson 95 % interval for the exceedance fraction
    z, m_ = 1.96, r.size
    centre = (pf + z * z / (2 * m_)) / (1 + z * z / m_)
    half = z * np.sqrt(pf * (1 - pf) / m_ + z * z / (4 * m_ * m_)) / (1 + z * z / m_)
    hist, edges = np.histogram(r, bins=30)
    pct = {f"p{q}": float(np.percentile(r, q)) for q in (1, 5, 10, 50, 90, 95, 99)}
    return {"n": int(m_), "rejected": rejected, "mean": float(r.mean()), "std": float(r.std(ddof=1)) if m_ > 1 else 0.0,
            "percentiles": pct, "fraction_rf_below_1": pf, "fraction_ci95": [max(0.0, centre - half), min(1.0, centre + half)],
            "histogram": {"edges": edges.tolist(), "counts": hist.tolist()}, "criterion": criterion, "seed": seed,
            "classification": "statistical screening (assumed CoVs, independent properties)",
            "notes": ["Not CMH-17 A/B-basis values.", "Sample fraction with RF < 1 is not a certified probability of failure."]}


def sensitivity(plies, N, M, dT, dC, criterion, copt, rel_step: float = 0.05) -> dict:
    """Normalised central-difference sensitivities d ln y / d ln x for material properties and ply thickness."""
    def metrics(pl):
        lam = Laminate(pl)
        St = C.build_strengths(pl)
        c = lam.engineering_constants()
        rf = laminate_rf(lam, St, N, M, dT, dC, criterion, copt)
        return {"RF": rf, "Ex": c["Ex"], "Ey": c["Ey"], "Gxy": c["Gxy"], "D11": float(lam.D[0, 0])}
    base = metrics(plies)
    mats = {p.material.id: p.material for p in plies}
    rows = []
    params = list(SAMPLED) + ["thickness"]
    for prm in params:
        vals = {}
        for sgn in (+1, -1):
            if prm == "thickness":
                pl = _replace(plies, {}, 1 + sgn * rel_step)
            else:
                pl = _replace(plies, {mid: {prm: m.get(prm) * (1 + sgn * rel_step)} for mid, m in mats.items()})
            vals[sgn] = metrics(pl)
        row = {"parameter": prm}
        for key in base:
            yp, ym, y0 = vals[1][key], vals[-1][key], base[key]
            if all(np.isfinite([yp, ym, y0])) and y0 != 0:
                row[key] = float((yp - ym) / (2 * rel_step * y0))
            else:
                row[key] = None
        rows.append(row)
    return {"base": {k: (v if np.isfinite(v) else None) for k, v in base.items()}, "rows": rows, "rel_step": rel_step,
            "criterion": criterion}


def angle_family_sweep(plies, var_idx: list[int], N, M, dT, dC, criteria_list, copt, start=0.0, stop=90.0, step=5.0,
                       knock: dict | None = None) -> dict:
    """Replace the angle of selected plies by +-theta (keeping each ply's sign) and sweep theta.

    Ply stiffness-retention factors (e.g. hot/wet knockdown) are preserved and ``knock`` is applied to strengths, so a
    sweep point at the current angles reproduces the main analysis exactly."""
    if not var_idx:
        raise ValueError("Select at least one ply to vary")
    thetas = np.arange(start, stop + 1e-9, step)
    if thetas.size > 181:
        raise ValueError("Too many sweep points (max 181)")
    out = {"theta": thetas.tolist(), "Ex": [], "Ey": [], "Gxy": [], "nuxy": [], "D11": [], "rf": {c: [] for c in criteria_list}}
    for th in thetas:
        pl = []
        for i, p in enumerate(plies):
            if i in var_idx:
                sgn = -1.0 if p.angle < 0 else 1.0
                pl.append(Ply(p.material, sgn * th, p.thickness, p.f_E1, p.f_E2, p.f_G12, p.f_nu12))
            else:
                pl.append(p)
        lam = Laminate(pl)
        c = lam.engineering_constants()
        for k in ("Ex", "Ey", "Gxy", "nuxy"):
            out[k].append(c[k])
        out["D11"].append(float(lam.D[0, 0]))
        St = C.build_strengths(pl, knock)
        for cr in criteria_list:
            try:
                rf = laminate_rf(lam, St, N, M, dT, dC, cr, copt)
                out["rf"][cr].append(rf if np.isfinite(rf) else None)
            except C.CriterionUnavailable:
                out["rf"][cr].append(None)
    return out
