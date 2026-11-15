"""Reserve factors, margins, first-ply failure and failure envelopes.

Author: Anwesh Ajitabh Dash.

The reserve factor RF is the smallest positive mechanical-load multiplier lambda such that
FI(sigma_HT + lambda * sigma_M) = 1, with the hygrothermal residual stress sigma_HT held constant
(SYSTEM_ENGINEERING_SPEC.md section 4.2). RF = 0 means the residual state alone violates the criterion. RF = inf means no
failure along the load ray within lambda <= 1e6.
"""
from __future__ import annotations

import numpy as np

from . import criteria as C
from .clt import Laminate

LAMBDA_MAX = 1.0e6
_GRID = np.concatenate([[0.0], np.logspace(-6, 6, 289)])


def _gov(name, s, St, opt):
    modes = C.evaluate(name, s[..., 0], s[..., 1], s[..., 2], St, opt)
    return C.governing(modes)


def reserve_factor(name: str, sig_r: np.ndarray, sig_m: np.ndarray, St, opt, exclude_modes=None) -> np.ndarray:
    """RF for stresses of shape (n, K, 3) in material axes. Returns (n, K).

    ``exclude_modes``: optional (n,) list of sets of mode names to ignore (already-failed modes in progressive analysis).
    """
    n, K, _ = sig_m.shape
    has_res = bool(np.any(np.abs(sig_r) > 0))
    if exclude_modes is None and not has_res and C.DEGREE.get(name):
        fi, _ = _gov(name, sig_m, St, opt)
        with np.errstate(divide="ignore"):
            rf = np.where(fi > 0, fi ** (-1.0 / C.DEGREE[name]), np.inf)
        return np.minimum(rf, np.inf)
    if name == "tsai_wu" and exclude_modes is None:
        return _tsai_wu_rf(sig_r, sig_m, St, opt)
    return _numeric_rf(name, sig_r, sig_m, St, opt, exclude_modes)


def _masked_gov(name, s, St, opt, exclude_modes):
    modes = C.evaluate(name, s[..., 0], s[..., 1], s[..., 2], St, opt)
    if exclude_modes is not None:
        for k, ex in enumerate(exclude_modes):
            for m in ex:
                if m in modes:
                    modes[m] = modes[m].copy()
                    modes[m][k, ...] = -np.inf
    return C.governing(modes)


def _numeric_rf(name, sig_r, sig_m, St, opt, exclude_modes):
    n, K, _ = sig_m.shape
    L = _GRID.size
    s = sig_r[:, :, None, :] + _GRID[None, None, :, None] * sig_m[:, :, None, :]
    fi, _ = _masked_gov(name, s.reshape(n, K * L, 3), St, opt, exclude_modes)
    fi = fi.reshape(n, K, L)
    fail = fi >= 1.0
    any_fail = fail.any(axis=2)
    first = np.argmax(fail, axis=2)
    rf = np.full((n, K), np.inf)
    already = fail[:, :, 0]
    rf[already] = 0.0
    todo = any_fail & ~already
    if np.any(todo):
        lo = np.where(todo, _GRID[np.maximum(first - 1, 0)], 0.0)
        hi = np.where(todo, _GRID[first], 1.0)
        for _ in range(60):
            mid = 0.5 * (lo + hi)
            sm = sig_r + mid[..., None] * sig_m
            fm, _ = _masked_gov(name, sm, St, opt, exclude_modes)
            up = fm >= 1.0
            hi = np.where(up, mid, hi)
            lo = np.where(up, lo, mid)
        rf[todo] = hi[todo]
    return rf


def _tsai_wu_rf(sig_r, sig_m, St, opt):
    F1, F2, F11, F22, F66, F12 = C.tsai_wu_coeffs(St, opt)
    r1, r2, r6 = sig_r[..., 0], sig_r[..., 1], sig_r[..., 2]
    m1, m2, m6 = sig_m[..., 0], sig_m[..., 1], sig_m[..., 2]
    a = F11 * m1 ** 2 + F22 * m2 ** 2 + F66 * m6 ** 2 + 2 * F12 * m1 * m2
    b = F1 * m1 + F2 * m2 + 2 * (F11 * r1 * m1 + F22 * r2 * m2 + F66 * r6 * m6 + F12 * (r1 * m2 + r2 * m1))
    c = F1 * r1 + F2 * r2 + F11 * r1 ** 2 + F22 * r2 ** 2 + F66 * r6 ** 2 + 2 * F12 * r1 * r2 - 1.0
    rf = np.full(a.shape, np.inf)
    already = c >= 0
    rf[already] = 0.0
    ok = (~already) & (a > 0)
    disc = b ** 2 - 4 * a * c
    with np.errstate(invalid="ignore", divide="ignore"):
        root = (-b + np.sqrt(np.maximum(disc, 0))) / (2 * a)
    rf[ok] = root[ok]
    lin = (~already) & (a <= 0) & (b > 0)  # degenerate: linear in lambda
    rf[lin] = (-c / b)[lin]
    return np.where(rf > LAMBDA_MAX, np.inf, rf)


# ----------------------------------------------------------------------------- laminate-level evaluation
def ply_stress_split(lam: Laminate, N, M, dT, dC, positions=("bottom", "top")):
    """Residual (hygrothermal) and mechanical ply stresses in material axes, each shape (n, P, 3)."""
    r_res = lam.solve((0, 0, 0), (0, 0, 0), dT, dC)
    r_mech = lam.solve(N, M, 0.0, 0.0)
    s_res = lam.ply_state(r_res, positions)["sigma_12"]
    s_mech = lam.ply_state(r_mech, positions)["sigma_12"]
    return s_res, s_mech


def evaluate_criteria(lam: Laminate, St, N, M, dT, dC, names, opt, fos: float = 1.5,
                      positions=("bottom", "middle", "top")) -> dict:
    """FI at the applied state, RF and margin for every ply, position and criterion."""
    s_res, s_mech = ply_stress_split(lam, N, M, dT, dC, positions)
    total = s_res + s_mech
    out, unavailable = {}, {}
    for name in names:
        try:
            modes = C.evaluate(name, total[..., 0], total[..., 1], total[..., 2], St, opt)
            fi, mode = C.governing(modes)
            rf = reserve_factor(name, s_res, s_mech, St, opt)
            s_fail = s_res + np.where(np.isfinite(rf), rf, 0.0)[..., None] * s_mech
            _, mode_fail = C.governing(C.evaluate(name, s_fail[..., 0], s_fail[..., 1], s_fail[..., 2], St, opt))
        except C.CriterionUnavailable as e:
            unavailable[name] = e.reasons
            continue
        rf_ply = rf.min(axis=1)
        k = int(np.argmin(rf_ply))
        p = int(np.argmin(rf[k]))
        rf_min = float(rf_ply[k])
        out[name] = {
            "label": C.CRITERION_LABEL[name],
            "fi": fi.tolist(), "mode": mode.tolist(), "rf": _clean(rf), "mode_at_failure": mode_fail.tolist(),
            "modes": {m: v.tolist() for m, v in modes.items()},
            "rf_ply": _clean(rf_ply), "fi_ply": fi.max(axis=1).tolist(),
            "critical": {"ply": k + 1, "position": positions[p], "rf": _num(rf_min),
                         "mode": str(mode_fail[k, p]), "ms": _num(rf_min / fos - 1) if np.isfinite(rf_min) else None},
        }
    return {"positions": list(positions), "results": out, "unavailable": unavailable}


def _num(x):
    x = float(x)
    return x if np.isfinite(x) else None


def _clean(a):
    a = np.asarray(a, float)
    return np.where(np.isfinite(a), a, -1.0).round(10).tolist()  # -1 encodes "no failure" (infinite RF) in JSON


def laminate_rf(lam: Laminate, St, N, M, dT, dC, name, opt) -> float:
    s_res, s_mech = ply_stress_split(lam, N, M, dT, dC)
    return float(reserve_factor(name, s_res, s_mech, St, opt).min())


# ----------------------------------------------------------------------------- envelopes
def ply_envelope(St1, name, opt, plane: str = "s1s2", fixed: float = 0.0, n: int = 181) -> dict:
    """Failure locus of a single ply in stress space, found by radial scan with closed/numerical RF.

    plane 's1s2': sigma1-sigma2 with tau12 = fixed; 's2t12': sigma2-tau12 with sigma1 = fixed; 's1t12'.
    """
    th = np.linspace(0, 2 * np.pi, n)
    d = np.zeros((1, n, 3))
    base = np.zeros((1, n, 3))
    ax = {"s1s2": (0, 1, 2), "s2t12": (1, 2, 0), "s1t12": (0, 2, 1)}[plane]
    d[0, :, ax[0]] = np.cos(th)
    d[0, :, ax[1]] = np.sin(th)
    base[0, :, ax[2]] = fixed
    rf = reserve_factor(name, base, d, St1, opt)[0]
    rf = np.where(np.isfinite(rf), rf, np.nan)
    x = rf * np.cos(th)
    y = rf * np.sin(th)
    return {"x": np.nan_to_num(x, nan=0).tolist(), "y": np.nan_to_num(y, nan=0).tolist(),
            "valid": np.isfinite(x).tolist(), "open": bool(np.any(~np.isfinite(rf)))}


def laminate_envelope(lam: Laminate, St, name, opt, dT, dC, plane: str = "NxNy", n: int = 121) -> dict:
    """First-ply-failure envelope in force-resultant space (N/mm), residual stresses included."""
    idx = {"NxNy": (0, 1), "NxNxy": (0, 2), "NyNxy": (1, 2)}[plane]
    r_res = lam.solve((0, 0, 0), (0, 0, 0), dT, dC)
    s_res = lam.ply_state(r_res, ("bottom", "top"))["sigma_12"]
    unit = []
    for j in range(3):
        Nv = np.zeros(3); Nv[j] = 1.0
        unit.append(lam.ply_state(lam.solve(Nv, (0, 0, 0)), ("bottom", "top"))["sigma_12"])
    th = np.linspace(0, 2 * np.pi, n)
    c, s = np.cos(th), np.sin(th)
    P = s_res.shape[1]
    # stack all directions along the evaluation axis: (n_ply, n_dir * P, 3)
    sm = c[None, :, None, None] * unit[idx[0]][:, None] + s[None, :, None, None] * unit[idx[1]][:, None]
    sr = np.broadcast_to(s_res[:, None], sm.shape)
    nply = sm.shape[0]
    rf = reserve_factor(name, sr.reshape(nply, n * P, 3), sm.reshape(nply, n * P, 3), St, opt).reshape(nply, n, P)
    rf_dir = rf.min(axis=2)                     # (n_ply, n_dir)
    r = rf_dir.min(axis=0)
    crit_ply = np.argmin(rf_dir, axis=0) + 1
    fin = np.isfinite(r)
    xs = [float(v) if f else None for v, f in zip(r * c, fin)]
    ys = [float(v) if f else None for v, f in zip(r * s, fin)]
    crit = [int(k) if f else None for k, f in zip(crit_ply, fin)]
    return {"x": xs, "y": ys, "critical_ply": crit, "plane": plane}
