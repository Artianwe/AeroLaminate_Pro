"""Classical Laminate Theory.

Author: Anwesh Ajitabh Dash.

Conventions (SYSTEM_ENGINEERING_SPEC.md section 3): z positive upward from the mid-plane, ply list ordered bottom -> top,
theta measured counter-clockwise from +x to the fibre axis, engineering shear strain, units N-mm-MPa.
References: Jones (1999) ch. 2 and 4; Reddy (2004) ch. 3; Kaw (2006) ch. 2 and 4.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .materials import Material, MissingPropertyError

COND_LIMIT = 1.0e12  # scaled condition number above which [ABD] is treated as singular


class SingularLaminateError(ValueError):
    """[ABD] is singular, not positive definite, or too ill-conditioned for a meaningful solution."""


class LaminateInputError(ValueError):
    pass


# ----------------------------------------------------------------------------- lamina level
def reduced_stiffness(E1: float, E2: float, G12: float, nu12: float) -> np.ndarray:
    """Plane-stress reduced stiffness [Q] in material axes (Jones 1999 eq. 2.61)."""
    nu21 = nu12 * E2 / E1
    den = 1.0 - nu12 * nu21
    if den <= 0:
        raise LaminateInputError("1 - nu12*nu21 must be positive")
    return np.array([[E1 / den, nu12 * E2 / den, 0.0],
                     [nu12 * E2 / den, E2 / den, 0.0],
                     [0.0, 0.0, G12]])


def compliance(E1: float, E2: float, G12: float, nu12: float) -> np.ndarray:
    return np.array([[1 / E1, -nu12 / E1, 0.0], [-nu12 / E1, 1 / E2, 0.0], [0.0, 0.0, 1 / G12]])


def T_sigma(theta_deg: float) -> np.ndarray:
    """Stress transformation x-y -> 1-2: sigma_12 = T sigma_xy."""
    t = np.radians(theta_deg)
    c, s = np.cos(t), np.sin(t)
    return np.array([[c * c, s * s, 2 * c * s], [s * s, c * c, -2 * c * s], [-c * s, c * s, c * c - s * s]])


def T_eps(theta_deg: float) -> np.ndarray:
    """Engineering-strain transformation x-y -> 1-2: eps_12 = T_eps eps_xy (gamma = 2 eps)."""
    t = np.radians(theta_deg)
    c, s = np.cos(t), np.sin(t)
    return np.array([[c * c, s * s, c * s], [s * s, c * c, -c * s], [-2 * c * s, 2 * c * s, c * c - s * s]])


def qbar(Q: np.ndarray, theta_deg: float) -> np.ndarray:
    """Transformed reduced stiffness Q_bar = T_sigma^-1 Q T_eps."""
    return np.linalg.solve(T_sigma(theta_deg), Q @ T_eps(theta_deg))


def invariants(Q: np.ndarray) -> tuple[float, float, float, float, float]:
    """Tsai-Pagano stiffness invariants U1..U5."""
    Q11, Q12, Q22, Q66 = Q[0, 0], Q[0, 1], Q[1, 1], Q[2, 2]
    U1 = (3 * Q11 + 3 * Q22 + 2 * Q12 + 4 * Q66) / 8
    U2 = (Q11 - Q22) / 2
    U3 = (Q11 + Q22 - 2 * Q12 - 4 * Q66) / 8
    U4 = (Q11 + Q22 + 6 * Q12 - 4 * Q66) / 8
    U5 = (Q11 + Q22 - 2 * Q12 + 4 * Q66) / 8
    return U1, U2, U3, U4, U5


# ----------------------------------------------------------------------------- ply definition
@dataclass
class Ply:
    material: Material
    angle: float
    thickness: float
    # Stiffness retention factors (1 = intact). Used by progressive failure and environmental knockdown.
    f_E1: float = 1.0
    f_E2: float = 1.0
    f_G12: float = 1.0
    f_nu12: float = 1.0

    def elastic(self) -> tuple[float, float, float, float]:
        m = self.material
        return (m.get("E1") * self.f_E1, m.get("E2") * self.f_E2, m.get("G12") * self.f_G12, m.get("nu12") * self.f_nu12)

    def Q(self) -> np.ndarray:
        return reduced_stiffness(*self.elastic())

    def S(self) -> np.ndarray:
        return compliance(*self.elastic())


def expand_plies(material_lookup, plies_in: list[dict], default_material: Material) -> list[Ply]:
    """Build Ply objects from dicts {angle, thickness?, material_id?}; validates inputs."""
    if not plies_in:
        raise LaminateInputError("Laminate must contain at least one ply")
    if len(plies_in) > 400:
        raise LaminateInputError("At most 400 plies are supported")
    out = []
    for i, p in enumerate(plies_in):
        mat = material_lookup(p["material_id"]) if p.get("material_id") else default_material
        ang = float(p["angle"])
        if not np.isfinite(ang) or abs(ang) > 180:
            raise LaminateInputError(f"Ply {i + 1}: angle must be within [-180, 180] deg")
        t = p.get("thickness")
        if t is None:
            t = mat.get("t_ply", "ply thickness (enter a thickness explicitly)")
        t = float(t)
        if not np.isfinite(t) or t <= 0 or t > 50:
            raise LaminateInputError(f"Ply {i + 1}: thickness must be in (0, 50] mm")
        out.append(Ply(mat, ang, t))
    return out


# ----------------------------------------------------------------------------- laminate
@dataclass
class Response:
    eps0: np.ndarray
    kappa: np.ndarray
    N: np.ndarray
    M: np.ndarray
    dT: float
    dC: float


@dataclass
class Laminate:
    plies: list[Ply]
    z: np.ndarray = field(init=False)
    h: float = field(init=False)

    def __post_init__(self):
        if not self.plies:
            raise LaminateInputError("Laminate must contain at least one ply")
        t = np.array([p.thickness for p in self.plies], dtype=float)
        if np.any(t <= 0):
            raise LaminateInputError("Ply thicknesses must be positive")
        self.h = float(t.sum())
        self.z = np.concatenate([[0.0], np.cumsum(t)]) - self.h / 2
        self.Q = np.array([p.Q() for p in self.plies])
        self.Qbar = np.array([qbar(Qk, p.angle) for Qk, p in zip(self.Q, self.plies)])
        dz1 = np.diff(self.z)
        dz2 = np.diff(self.z ** 2) / 2
        dz3 = np.diff(self.z ** 3) / 3
        self.A = np.einsum("k,kij->ij", dz1, self.Qbar)
        self.B = np.einsum("k,kij->ij", dz2, self.Qbar)
        self.D = np.einsum("k,kij->ij", dz3, self.Qbar)
        self.ABD = np.block([[self.A, self.B], [self.B, self.D]])
        self._diag = self._diagnose()

    # ---------------------------------------------------------------- diagnostics
    def _diagnose(self) -> dict:
        d = np.diag(self.ABD)
        if np.any(~np.isfinite(self.ABD)) or np.any(d <= 0):
            return {"positive_definite": False, "scaled_condition": float("inf")}
        s = 1 / np.sqrt(d)
        scaled = self.ABD * np.outer(s, s)
        try:
            np.linalg.cholesky(scaled)
            pd = True
        except np.linalg.LinAlgError:
            pd = False
        cond = float(np.linalg.cond(scaled)) if pd else float("inf")
        return {"positive_definite": pd, "scaled_condition": cond, "raw_condition": float(np.linalg.cond(self.ABD))}

    def check_solvable(self) -> None:
        if not self._diag["positive_definite"]:
            raise SingularLaminateError("[ABD] is not positive definite (laminate has lost load-carrying stiffness)")
        if self._diag["scaled_condition"] > COND_LIMIT:
            raise SingularLaminateError(
                f"[ABD] is ill-conditioned (scaled condition number {self._diag['scaled_condition']:.3g} > {COND_LIMIT:.0e})")

    @property
    def diagnostics(self) -> dict:
        return dict(self._diag)

    # ---------------------------------------------------------------- hygrothermal
    def _expansion(self, key1: str, key2: str, needed: bool) -> np.ndarray:
        out = np.zeros((len(self.plies), 3))
        if not needed:
            return out
        for k, p in enumerate(self.plies):
            m = p.material
            for name in (key1, key2):
                if not m.has(name):
                    raise MissingPropertyError(m.name, name, "hygrothermal analysis")
            a12 = np.array([m.get(key1), m.get(key2), 0.0])
            out[k] = np.linalg.solve(T_eps(p.angle), a12)  # alpha_xy = T_eps^-1 alpha_12
        return out

    def free_strains(self, dT: float, dC: float) -> np.ndarray:
        """Unconstrained hygrothermal ply strains in laminate axes, shape (n, 3)."""
        a = self._expansion("alpha1", "alpha2", dT != 0)
        b = self._expansion("beta1", "beta2", dC != 0)
        return a * dT + b * dC

    def hygrothermal_resultants(self, dT: float, dC: float) -> tuple[np.ndarray, np.ndarray]:
        e = self.free_strains(dT, dC)
        sig = np.einsum("kij,kj->ki", self.Qbar, e)
        N = np.einsum("k,ki->i", np.diff(self.z), sig)
        M = np.einsum("k,ki->i", np.diff(self.z ** 2) / 2, sig)
        return N, M

    # ---------------------------------------------------------------- solution
    def solve(self, N=(0, 0, 0), M=(0, 0, 0), dT: float = 0.0, dC: float = 0.0) -> Response:
        self.check_solvable()
        N = np.asarray(N, float)
        M = np.asarray(M, float)
        NT, MT = self.hygrothermal_resultants(dT, dC)
        rhs = np.concatenate([N + NT, M + MT])
        x = np.linalg.solve(self.ABD, rhs)
        return Response(x[:3], x[3:], N, M, dT, dC)

    def ply_state(self, r: Response, positions=("bottom", "middle", "top")) -> dict:
        """Strains/stresses at requested through-thickness positions of every ply.

        Returns arrays of shape (n_ply, n_pos, 3): total strain (x-y), mechanical strain (x-y and 1-2),
        stress (x-y and 1-2). 'Mechanical' strain = total - free hygrothermal strain (the stress-producing part).
        """
        frac = {"bottom": 0.0, "middle": 0.5, "top": 1.0}
        f = np.array([frac[p] for p in positions])
        zk = self.z[:-1, None] + np.diff(self.z)[:, None] * f[None, :]
        eps = r.eps0[None, None, :] + zk[..., None] * r.kappa[None, None, :]
        free = self.free_strains(r.dT, r.dC)
        mech = eps - free[:, None, :]
        sig = np.einsum("kij,kpj->kpi", self.Qbar, mech)
        Ts = np.array([T_sigma(p.angle) for p in self.plies])
        Te = np.array([T_eps(p.angle) for p in self.plies])
        sig12 = np.einsum("kij,kpj->kpi", Ts, sig)
        mech12 = np.einsum("kij,kpj->kpi", Te, mech)
        return {"z": zk, "positions": list(positions), "eps_xy": eps, "mech_eps_xy": mech, "sigma_xy": sig,
                "sigma_12": sig12, "mech_eps_12": mech12}

    # ---------------------------------------------------------------- properties
    def engineering_constants(self) -> dict:
        """Effective in-plane (membrane) and flexural engineering constants.

        Membrane constants come from a = A^-1 (B decoupled). They describe the laminate behaviour under in-plane
        loads only when B = 0 or the laminate is restrained against bending.
        """
        h = self.h
        a = np.linalg.inv(self.A)
        out = {"Ex": 1 / (h * a[0, 0]), "Ey": 1 / (h * a[1, 1]), "Gxy": 1 / (h * a[2, 2]),
               "nuxy": -a[0, 1] / a[0, 0], "nuyx": -a[0, 1] / a[1, 1],
               "eta_xy_x": a[0, 2] / a[0, 0], "eta_xy_y": a[1, 2] / a[1, 1]}
        d = np.linalg.inv(self.D)
        out.update({"Efx": 12 / (h ** 3 * d[0, 0]), "Efy": 12 / (h ** 3 * d[1, 1]), "Gfxy": 12 / (h ** 3 * d[2, 2]),
                    "nufxy": -d[0, 1] / d[0, 0]})
        # Membrane constants including extension-bending coupling (laminate free to bend), from the full inverse.
        abd_inv = np.linalg.inv(self.ABD)
        out.update({"Ex_free": 1 / (h * abd_inv[0, 0]), "Ey_free": 1 / (h * abd_inv[1, 1]), "Gxy_free": 1 / (h * abd_inv[2, 2])})
        return {k: float(v) for k, v in out.items()}

    def areal_mass(self) -> float | None:
        """kg/m^2, or None if any ply lacks density."""
        tot = 0.0
        for p in self.plies:
            if not p.material.has("density"):
                return None
            tot += p.material.get("density") * p.thickness * 1e-3
        return tot

    def coupling(self) -> dict:
        A, B, D = self.A, self.B, self.D
        nA, nB, nD = np.linalg.norm(A), np.linalg.norm(B), np.linalg.norm(D)
        ext_shear = max(abs(A[0, 2]), abs(A[1, 2])) / np.sqrt(A[0, 0] * A[2, 2])
        bend_twist_delta = D[0, 2] / (D[0, 0] ** 3 * D[1, 1]) ** 0.25
        bend_twist_gamma = D[1, 2] / (D[0, 0] * D[1, 1] ** 3) ** 0.25
        ext_bend = nB / np.sqrt(nA * nD)
        return {"extension_shear": float(ext_shear), "bending_twisting_delta": float(bend_twist_delta),
                "bending_twisting_gamma": float(bend_twist_gamma), "extension_bending": float(ext_bend)}

    def classify(self, tol: float = 1e-9) -> dict:
        A, B, D = self.A, self.B, self.D
        sA = max(A[0, 0], A[1, 1])
        sB = np.sqrt(np.linalg.norm(A) * np.linalg.norm(D))
        geom_sym = all(
            abs(p.angle - q.angle) < 1e-9 and abs(p.thickness - q.thickness) < 1e-12 and p.material.id == q.material.id
            for p, q in zip(self.plies, reversed(self.plies)))
        sym = bool(np.linalg.norm(B) <= tol * sB)
        balanced = bool(abs(A[0, 2]) <= tol * sA and abs(A[1, 2]) <= tol * sA)
        qi = bool(balanced and abs(A[0, 0] - A[1, 1]) <= 1e-6 * sA and abs(A[2, 2] - (A[0, 0] - A[0, 1]) / 2) <= 1e-6 * sA)
        spec_orth = bool(sym and balanced and abs(D[0, 2]) <= tol * D[0, 0] and abs(D[1, 2]) <= tol * D[0, 0])
        return {"symmetric_stiffness": sym, "symmetric_geometry": geom_sym, "balanced": balanced,
                "quasi_isotropic_inplane": qi, "specially_orthotropic": spec_orth}

    def secant_stiffness(self, N, M) -> float:
        """Generalised secant stiffness F.F / F.u for the mechanical load vector (used for LPF tracking)."""
        r = self.solve(N, M)
        F = np.concatenate([np.asarray(N, float), np.asarray(M, float)])
        u = np.concatenate([r.eps0, r.kappa])
        fu = float(F @ u)
        return float(F @ F) / fu if fu > 0 else float("inf")

    def rotated(self, psi: float) -> "Laminate":
        """Laminate whose x-axis is rotated by psi (equivalent to ply angles theta - psi)."""
        return Laminate([Ply(p.material, p.angle - psi, p.thickness, p.f_E1, p.f_E2, p.f_G12, p.f_nu12) for p in self.plies])


def stiffness_vs_orientation(lam: Laminate, step: float = 2.0) -> dict:
    """Ex(psi), Gxy(psi), Efx(psi) for laminate axes rotated by psi in [0, 180]."""
    psis = np.arange(0.0, 180.0 + 1e-9, step)
    Ex, Gxy, Efx, nuxy = [], [], [], []
    for psi in psis:
        c = lam.rotated(psi).engineering_constants()
        Ex.append(c["Ex"]); Gxy.append(c["Gxy"]); Efx.append(c["Efx"]); nuxy.append(c["nuxy"])
    # Single-ply Qbar11 vs angle for the first ply's material
    Q = lam.plies[0].Q()
    q11 = [float(qbar(Q, a)[0, 0]) for a in psis]
    return {"psi": psis.tolist(), "Ex": Ex, "Gxy": Gxy, "Efx": Efx, "nuxy": nuxy, "ply_Qbar11": q11}
