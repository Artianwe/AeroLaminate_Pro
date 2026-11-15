"""Linear buckling of simply supported rectangular laminated plates (Rayleigh-Ritz).

Author: Anwesh Ajitabh Dash.

w = sum A_mn sin(m pi x / a) sin(n pi y / b), all four edges simply supported (w = 0, M_n = 0).
Bending energy keeps D16 and D26. The geometric stiffness keeps Nx, Ny and Nxy (tension positive).
Critical load factor lambda: (K + lambda K_G) a = 0 (Whitney 1987; Leissa 1985).
Limitations: no postbuckling, no imperfections, no transverse-shear flexibility, SS edges only.
B != 0 is handled approximately with D* = D - B A^-1 B (flagged).
"""
from __future__ import annotations

import numpy as np
from scipy.linalg import eigh

from .clt import Laminate


def _Isc(m: np.ndarray, p: np.ndarray, L: float) -> np.ndarray:
    """int_0^L sin(m pi x/L) cos(p pi x/L) dx."""
    M, P = np.meshgrid(m, p, indexing="ij")
    with np.errstate(divide="ignore", invalid="ignore"):
        v = L / np.pi * M * (1 - (-1.0) ** (M + P)) / (M ** 2 - P ** 2)
    return np.where(M == P, 0.0, v)


def specially_orthotropic_Nx(D: np.ndarray, a: float, b: float, mmax: int = 30) -> tuple[float, int]:
    """Exact critical Nx (compression positive) for D16 = D26 = 0 (Jones 1999 section 5.5); returns (Ncr, m)."""
    best = (np.inf, 0)
    for m in range(1, mmax + 1):
        am, bn = m / a, 1 / b
        N = np.pi ** 2 * (D[0, 0] * am ** 4 + 2 * (D[0, 1] + 2 * D[2, 2]) * am ** 2 * bn ** 2 + D[1, 1] * bn ** 4) / am ** 2
        if N < best[0]:
            best = (N, m)
    return best


def ritz(D: np.ndarray, a: float, b: float, Nx: float, Ny: float, Nxy: float, M: int = 8, Nn: int = 8):
    m = np.arange(1, M + 1); n = np.arange(1, Nn + 1)
    am = m * np.pi / a; bn = n * np.pi / b
    idx = [(i, j) for i in range(M) for j in range(Nn)]
    size = len(idx)
    I = np.array([i for i, _ in idx]); J = np.array([j for _, j in idx])
    Sa = _Isc(m, m, a)  # Sa[i, p] = int sin(m_i) cos(m_p)
    Sb = _Isc(n, n, b)
    ii, pp = np.meshgrid(I, I, indexing="ij")
    jj, qq = np.meshgrid(J, J, indexing="ij")
    same = (ii == pp) & (jj == qq)
    ab4 = a * b / 4
    D11, D12, D22, D66, D16, D26 = D[0, 0], D[0, 1], D[1, 1], D[2, 2], D[0, 2], D[1, 2]
    # diagonal (orthotropic) part
    Kd = (D11 * am[ii] ** 4 + 2 * D12 * am[ii] ** 2 * bn[jj] ** 2 + D22 * bn[jj] ** 4 + 4 * D66 * am[ii] ** 2 * bn[jj] ** 2) * ab4
    K = np.where(same, Kd, 0.0)
    # anisotropic cross terms: integrand 4 D16 w,xx w,xy + 4 D26 w,yy w,xy -> coefficient of A_mn A_pq
    cross = -(4 * D16 * am[ii] ** 2 + 4 * D26 * bn[jj] ** 2) * am[pp] * bn[qq] * Sa[ii, pp] * Sb[jj, qq]
    K = K + (cross + cross.T) / 2
    # geometric stiffness (tension positive): Nx w,x^2 + Ny w,y^2 + 2 Nxy w,x w,y
    Gd = (Nx * am[ii] ** 2 + Ny * bn[jj] ** 2) * ab4
    G = np.where(same, Gd, 0.0)
    # w,x w,y = sum A_mn A_pq am bq cos(m)sin(n) sin(p)cos(q) -> int = am bq Sa[p, m] Sb[n, q]
    gx = 2 * Nxy * am[ii] * bn[qq] * Sa[pp, ii] * Sb[jj, qq]
    G = G + (gx + gx.T) / 2
    # Pi = 1/2 a^T K a + lambda/2 a^T G a ; buckling when K + lambda G singular -> (-G) a = mu K a, lambda = 1/mu
    mu, vecs = eigh(-G, K)
    pos = mu > 1e-14 * max(1.0, np.abs(mu).max())
    if not np.any(pos):
        return None, None, idx
    k = int(np.argmax(np.where(pos, mu, -np.inf)))
    return 1.0 / mu[k], vecs[:, k], idx


def buckling(lam: Laminate, a: float, b: float, Nx: float, Ny: float, Nxy: float, terms: int = 8, grid: int = 31) -> dict:
    if a <= 0 or b <= 0:
        raise ValueError("Plate dimensions must be positive")
    if not (2 <= terms <= 20):
        raise ValueError("Ritz terms per direction must be within 2..20")
    if Nx == 0 and Ny == 0 and Nxy == 0:
        raise ValueError("Buckling needs a non-zero in-plane load")
    flags = []
    if min(a, b) / lam.h < 20:
        flags.append(f"Plate span/thickness = {min(a, b) / lam.h:.1f} < 20: classical (Kirchhoff) plate theory neglects transverse "
                     "shear deformation and over-predicts the buckling load; use a shear-deformable model")
    D = lam.D.copy()
    Bn = np.linalg.norm(lam.B)
    if Bn > 1e-9 * np.sqrt(np.linalg.norm(lam.A) * np.linalg.norm(lam.D)):
        D = lam.D - lam.B @ np.linalg.solve(lam.A, lam.B)
        flags.append("Unsymmetric laminate: reduced bending stiffness D* = D - B A^-1 B used (approximation)")
    lamb, vec, idx = ritz(D, a, b, Nx, Ny, Nxy, terms, terms)
    lamb_c, _, _ = ritz(D, a, b, Nx, Ny, Nxy, max(terms - 2, 1), max(terms - 2, 1))
    out = {"a": a, "b": b, "load": [Nx, Ny, Nxy], "terms": terms, "flags": flags,
           "classification": "linear eigenvalue, SS edges (no postbuckling or imperfection knockdown)"}
    if lamb is None:
        out.update({"load_factor": None, "message": "No positive critical load factor: under proportional scaling of this load state the tensile components stabilise every mode"})
        return out
    out["load_factor"] = float(lamb)
    out["convergence_change"] = float(abs(lamb - lamb_c) / lamb) if lamb_c else None
    if out["convergence_change"] and out["convergence_change"] > 0.01:
        flags.append(f"Ritz solution changed {out['convergence_change']:.1%} between {terms - 2} and {terms} terms; increase terms")
    xs = np.linspace(0, a, grid); ys = np.linspace(0, b, grid)
    X, Y = np.meshgrid(xs, ys)
    W = np.zeros_like(X)
    for c, (i, j) in zip(vec, idx):
        W += c * np.sin((i + 1) * np.pi * X / a) * np.sin((j + 1) * np.pi * Y / b)
    W /= np.abs(W).max()
    dom = int(np.argmax(np.abs(vec)))
    out.update({"x": xs.tolist(), "y": ys.tolist(), "w": W.tolist(), "dominant_mode": [idx[dom][0] + 1, idx[dom][1] + 1],
                "nondim": {"delta": float(D[0, 2] / (D[0, 0] ** 3 * D[1, 1]) ** 0.25),
                           "gamma": float(D[1, 2] / (D[0, 0] * D[1, 1] ** 3) ** 0.25)}})
    if abs(D[0, 2]) < 1e-12 * D[0, 0] and abs(D[1, 2]) < 1e-12 * D[0, 0] and Nxy == 0 and Ny == 0 and Nx < 0:
        Ncr, m = specially_orthotropic_Nx(D, a, b)
        out["closed_form_check"] = {"Ncr": Ncr, "m": m, "ritz_Ncr": float(lamb * -Nx)}
    return out
