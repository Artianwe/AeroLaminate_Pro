"""Interlaminar screening: transverse-shear stress recovery, free-edge mismatch indicators, edge delamination.

Author: Anwesh Ajitabh Dash.

CLT does not resolve interlaminar stresses. The methods here are established SCREENING approximations:
* Transverse shear from 3-D equilibrium under transverse shear resultants (Whitney 1987; Reddy 2004), assuming
  cylindrical-bending-type fields (dN/dx = 0, linearly varying moments). Not valid near free edges, loads or ply drops.
* Free-edge indicators: adjacent-ply mismatch of nu_xy and eta_xy,x (Herakovich 1981). Qualitative only.
* Edge delamination onset: O'Brien (1982) G = (eps^2 t / 2)(E_lam - E*), symmetric laminates, total G only.
"""
from __future__ import annotations

import numpy as np

from .clt import Laminate, Ply, T_sigma


def transverse_shear(lam: Laminate, Qx: float, Qy: float, pts_per_ply: int = 11) -> dict:
    lam.check_solvable()
    inv = np.linalg.inv(lam.ABD)
    # derivatives of mid-plane strain/curvature: d/dx under Qx (dMx/dx = Qx), d/dy under Qy (dMy/dy = Qy)
    dx = inv @ np.array([0, 0, 0, Qx, 0, 0.0])
    dy = inv @ np.array([0, 0, 0, 0, Qy, 0.0])
    zs, txz, tyz, ply_idx = [], [], [], []
    acc_xz = acc_yz = 0.0
    for k in range(len(lam.plies)):
        z0, z1 = lam.z[k], lam.z[k + 1]
        Qb = lam.Qbar[k]
        # dsigma/dx = Qb (de0/dx + z dk/dx) = a + b z  (vectors)
        ax, bx = Qb @ dx[:3], Qb @ dx[3:]
        ay, by = Qb @ dy[:3], Qb @ dy[3:]
        for z in np.linspace(z0, z1, pts_per_ply):
            I0, I1 = z - z0, (z ** 2 - z0 ** 2) / 2
            # tau_xz = -int(dsx/dx + dtxy/dy), tau_yz = -int(dtxy/dx + dsy/dy)
            vxz = acc_xz - ((ax[0] * I0 + bx[0] * I1) + (ay[2] * I0 + by[2] * I1))
            vyz = acc_yz - ((ax[2] * I0 + bx[2] * I1) + (ay[1] * I0 + by[1] * I1))
            zs.append(z); txz.append(vxz); tyz.append(vyz); ply_idx.append(k + 1)
        I0, I1 = z1 - z0, (z1 ** 2 - z0 ** 2) / 2
        acc_xz -= (ax[0] * I0 + bx[0] * I1) + (ay[2] * I0 + by[2] * I1)
        acc_yz -= (ax[2] * I0 + bx[2] * I1) + (ay[1] * I0 + by[1] * I1)
    txz, tyz = np.array(txz), np.array(tyz)
    scale = max(abs(Qx), abs(Qy), 1e-30) / lam.h
    residual = float(max(abs(acc_xz), abs(acc_yz)) / scale)
    # interfaces: values at the top of ply k (= bottom of ply k+1)
    interfaces = []
    for k in range(len(lam.plies) - 1):
        zi = lam.z[k + 1]
        j = (k + 1) * pts_per_ply - 1
        interfaces.append({"interface": f"{k + 1}/{k + 2}", "z": float(zi), "tau_xz": float(txz[j]), "tau_yz": float(tyz[j])})
    return {"z": zs, "tau_xz": txz.tolist(), "tau_yz": tyz.tolist(), "ply": ply_idx, "interfaces": interfaces,
            "max_abs": float(np.sqrt(txz ** 2 + tyz ** 2).max()), "top_surface_residual": residual,
            "classification": "screening (equilibrium recovery)"}


def interlaminar_check(lam: Laminate, ts: dict, fos: float = 1.5) -> dict:
    """Compare interface shear with interlaminar strength (ILSS if available, else S12, flagged)."""
    flags, rows = [], []
    for it in ts["interfaces"]:
        k = int(it["interface"].split("/")[0]) - 1
        mats = [lam.plies[k].material, lam.plies[k + 1].material]
        vals = []
        for m in mats:
            if m.has("ILSS"):
                vals.append(m.get("ILSS"))
            else:
                vals.append(m.get("S12"))
                msg = f"{m.name}: ILSS not available; S12 used as interlaminar shear strength (transverse isotropy assumption)"
                if msg not in flags:
                    flags.append(msg)
        S = min(vals)
        tau = float(np.hypot(it["tau_xz"], it["tau_yz"]))
        rf = S / tau if tau > 0 else None
        rows.append({**it, "tau_resultant": tau, "strength": S, "rf": rf, "ms": (rf / fos - 1) if rf else None})
    return {"interfaces": rows, "flags": flags}


def free_edge_indicators(lam: Laminate) -> dict:
    """Per-ply nu_xy and eta_xy,x (from ply compliance in laminate axes) and adjacent-interface mismatches."""
    nu, eta = [], []
    for Qb in lam.Qbar:
        S = np.linalg.inv(Qb)
        nu.append(-S[0, 1] / S[0, 0])
        eta.append(S[0, 2] / S[0, 0])
    c = lam.engineering_constants()
    rows = []
    for k in range(len(lam.plies) - 1):
        rows.append({"interface": f"{k + 1}/{k + 2}", "z": float(lam.z[k + 1]),
                     "delta_nu_xy": float(nu[k + 1] - nu[k]), "delta_eta_xy_x": float(eta[k + 1] - eta[k]),
                     "angle_change": float(abs(lam.plies[k + 1].angle - lam.plies[k].angle))})
    return {"ply_nu_xy": nu, "ply_eta_xy_x": eta, "laminate_nu_xy": c["nuxy"], "interfaces": rows,
            "classification": "qualitative indicator (no interlaminar stress magnitude)",
            "note": "Large |delta nu_xy| correlates with free-edge sigma_z; large |delta eta| with tau_xz (Herakovich 1981)."}


def _sublaminate_modulus(plies: list[Ply]) -> tuple[float, float]:
    sub = Laminate(plies)
    a = np.linalg.inv(sub.A)
    return 1 / (sub.h * a[0, 0]), sub.h


def edge_delamination(lam: Laminate, interfaces: list[int], strain: float | None = None) -> dict:
    """O'Brien edge-delamination G for delaminations at the given interfaces (1-based index i = between ply i and i+1),
    mirrored about the mid-plane. Laminate must be geometrically symmetric."""
    n = len(lam.plies)
    if not lam.classify()["symmetric_geometry"]:
        raise ValueError("Edge-delamination model (O'Brien 1982) requires a symmetric laminate")
    if not interfaces:
        raise ValueError("Select at least one interface")
    cuts = set()
    for i in interfaces:
        if not 1 <= int(i) <= n - 1:
            raise ValueError(f"Interface {i} out of range 1..{n - 1}")
        cuts.add(int(i)); cuts.add(n - int(i))
    cuts = sorted(cuts)
    bounds = [0] + cuts + [n]
    E_lam = 1 / (lam.h * np.linalg.inv(lam.A)[0, 0])
    Es = 0.0
    subs = []
    for s, e in zip(bounds[:-1], bounds[1:]):
        if e <= s:
            continue
        Ei, ti = _sublaminate_modulus(lam.plies[s:e])
        Es += Ei * ti
        subs.append({"plies": f"{s + 1}-{e}", "E": Ei, "t": ti})
    E_star = Es / lam.h
    dE = E_lam - E_star
    out = {"E_lam": E_lam, "E_star": E_star, "sublaminates": subs, "interfaces": cuts,
           "G_per_strain2": lam.h * dE / 2, "classification": "screening (O'Brien 1982, total G, mode mix not resolved)"}
    mats = {p.material.name: p.material for p in lam.plies}
    gic = [m.get("GIc") for m in mats.values() if m.has("GIc")]
    if len(gic) == len(mats):
        Gc = min(gic)
        out["GIc"] = Gc
        out["onset_strain"] = float(np.sqrt(2 * Gc / (lam.h * dE))) if dE > 0 else None
    else:
        out["GIc"] = None
        out["onset_strain"] = None
        out["note"] = "GIc not available for all materials: onset strain unavailable"
    if strain is not None:
        out["applied_strain"] = strain
        out["G"] = float(strain ** 2 * lam.h * dE / 2)
    return out
