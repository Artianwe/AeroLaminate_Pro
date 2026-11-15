"""Ply-level plane-stress failure criteria.

Author: Anwesh Ajitabh Dash.

All functions are vectorised. Stresses s1, s2, t12 are arrays of shape (n, K) (n plies, K evaluation points);
strength attributes of :class:`StrengthSet` have shape (n, 1). Each criterion returns a dict mode -> FI array,
where FI = 1 is the criterion's failure surface. FI definitions differ between criteria (linear ratio, quadratic
form, ...), so the load multiplier (reserve factor) is the quantity to compare across criteria (see strength.py).

Sources: Jones (1999); Azzi & Tsai (1965); Tsai & Wu (1971); Hashin (1980); Puck & Schuermann (2002);
Davila & Camanho (2003) NASA/TM-2003-212663.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .clt import Ply

FIBRE_MODES = {"FT", "FC"}
CRITERIA = ("max_stress", "max_strain", "tsai_hill", "tsai_wu", "hashin", "puck", "larc03")
CRITERION_LABEL = {"max_stress": "Maximum stress", "max_strain": "Maximum strain", "tsai_hill": "Tsai-Hill",
                   "tsai_wu": "Tsai-Wu", "hashin": "Hashin (1980)", "puck": "Puck 2D", "larc03": "LaRC03 (2D)"}
MODE_BASED = {"max_stress", "max_strain", "hashin", "puck", "larc03"}
# Homogeneity degree of the governing FI in stress (None: solve numerically/quadratically)
DEGREE = {"max_stress": 1, "max_strain": 1, "tsai_hill": 2, "tsai_wu": None, "hashin": None, "puck": 1, "larc03": None}


class CriterionUnavailable(Exception):
    def __init__(self, criterion: str, reasons: list[str]):
        self.criterion, self.reasons = criterion, reasons
        super().__init__(f"{CRITERION_LABEL.get(criterion, criterion)} unavailable: " + "; ".join(reasons))


@dataclass
class CriterionOptions:
    tsai_wu_F12_star: float = -0.5           # Tsai & Hahn (1980) default
    puck_p_pt: float = 0.35                  # p(+)_perp-par, CFRP recommendation (Puck et al. 2002)
    puck_p_pc: float = 0.30                  # p(-)_perp-par
    larc_alpha0_deg: float = 53.0            # fracture angle in pure transverse compression
    larc_insitu: bool = True                 # use in-situ strengths
    hashin_ST: float | None = None           # transverse shear strength override, MPa


@dataclass
class StrengthSet:
    """Per-ply strengths, shape (n, 1) arrays, plus flags describing derived/assumed values."""
    Xt: np.ndarray; Xc: np.ndarray; Yt: np.ndarray; Yc: np.ndarray; S: np.ndarray
    E1: np.ndarray; E2: np.ndarray; G12: np.ndarray; nu12: np.ndarray
    flags: list[str] = field(default_factory=list)
    extra: dict = field(default_factory=dict)  # lazily built criterion-specific arrays
    plies: list = field(default_factory=list)
    knock: dict | None = None


def _col(vals) -> np.ndarray:
    return np.asarray(vals, float).reshape(-1, 1)


def build_strengths(plies: list[Ply], knock: dict | None = None) -> StrengthSet:
    """Strength set from ply materials. ``knock`` optionally maps property -> per-ply retention factor array."""
    def get(prop):
        vals = np.array([p.material.get(prop, "strength analysis") for p in plies], float)
        if knock and prop in knock:
            vals = vals * np.asarray(knock[prop], float)
        return _col(vals)
    St = StrengthSet(get("Xt"), get("Xc"), get("Yt"), get("Yc"), get("S12"),
                     get("E1"), get("E2"), get("G12"), get("nu12"))
    St.plies = plies
    St.knock = knock
    return St


# ----------------------------------------------------------------------------- helpers
def _pos(x):
    return np.maximum(x, 0.0)


def _strains(s1, s2, t12, St):
    e1 = s1 / St.E1 - St.nu12 * s2 / St.E1
    e2 = -St.nu12 * s1 / St.E1 + s2 / St.E2
    g12 = t12 / St.G12
    return e1, e2, g12


def _strain_limits(St: StrengthSet):
    if "eps" in St.extra:
        return St.extra["eps"]
    lim = {k: [] for k in ("e1t", "e1c", "e2t", "e2c", "g12")}
    pairs = {"e1t": ("eps1t", "Xt", "E1"), "e1c": ("eps1c", "Xc", "E1"), "e2t": ("eps2t", "Yt", "E2"),
             "e2c": ("eps2c", "Yc", "E2"), "g12": ("gamma12u", "S12", "G12")}
    for p in St.plies:
        for k, (prop, num, den) in pairs.items():
            lim[k].append(p.material.get_or_derived(prop, num, den))
            for f in p.material.flags:
                if f not in St.flags:
                    St.flags.append(f)
    out = {k: _col(v) for k, v in lim.items()}
    St.extra["eps"] = out
    return out


# ----------------------------------------------------------------------------- criteria
def max_stress(s1, s2, t12, St, opt):
    return {"FT": _pos(s1) / St.Xt, "FC": _pos(-s1) / St.Xc, "MT": _pos(s2) / St.Yt,
            "MC": _pos(-s2) / St.Yc, "S": np.abs(t12) / St.S}


def max_strain(s1, s2, t12, St, opt):
    e1, e2, g = _strains(s1, s2, t12, St)
    L = _strain_limits(St)
    return {"FT": _pos(e1) / L["e1t"], "FC": _pos(-e1) / L["e1c"], "MT": _pos(e2) / L["e2t"],
            "MC": _pos(-e2) / L["e2c"], "S": np.abs(g) / L["g12"]}


def tsai_hill(s1, s2, t12, St, opt):
    X = np.where(s1 >= 0, St.Xt, St.Xc)
    Y = np.where(s2 >= 0, St.Yt, St.Yc)
    return {"TH": (s1 / X) ** 2 - s1 * s2 / X ** 2 + (s2 / Y) ** 2 + (t12 / St.S) ** 2}


def tsai_wu_coeffs(St, opt):
    F1 = 1 / St.Xt - 1 / St.Xc
    F2 = 1 / St.Yt - 1 / St.Yc
    F11 = 1 / (St.Xt * St.Xc)
    F22 = 1 / (St.Yt * St.Yc)
    F66 = 1 / St.S ** 2
    if not (-1 < opt.tsai_wu_F12_star < 1):
        raise CriterionUnavailable("tsai_wu", ["F12* must lie in (-1, 1) for a closed (ellipsoidal) surface"])
    F12 = opt.tsai_wu_F12_star * np.sqrt(F11 * F22)
    return F1, F2, F11, F22, F66, F12


def tsai_wu(s1, s2, t12, St, opt):
    F1, F2, F11, F22, F66, F12 = tsai_wu_coeffs(St, opt)
    return {"TW": F1 * s1 + F2 * s2 + F11 * s1 ** 2 + F22 * s2 ** 2 + F66 * t12 ** 2 + 2 * F12 * s1 * s2}


def _hashin_ST(St, opt):
    if opt.hashin_ST:
        return np.full_like(St.Yc, float(opt.hashin_ST))
    if "ST" in St.extra:
        return St.extra["ST"]
    vals = []
    for p in St.plies:
        if p.material.has("S23"):
            vals.append(p.material.get("S23"))
        else:
            vals.append(None)
    if any(v is None for v in vals):
        msg = "Hashin matrix compression: transverse shear strength S_T not available; assumed S_T = Yc/2 (Hashin 1980 suggestion)"
        if msg not in St.flags:
            St.flags.append(msg)
    ST = np.array([v if v is not None else 0.0 for v in vals], float).reshape(-1, 1)
    ST = np.where(ST > 0, ST, St.Yc / 2)
    St.extra["ST"] = ST
    return ST


def hashin(s1, s2, t12, St, opt):
    ST = _hashin_ST(St, opt)
    t = t12 / St.S
    ft = np.where(s1 >= 0, (s1 / St.Xt) ** 2 + t ** 2, 0.0)
    fc = np.where(s1 < 0, (s1 / St.Xc) ** 2, 0.0)
    mt = np.where(s2 >= 0, (s2 / St.Yt) ** 2 + t ** 2, 0.0)
    mc = np.where(s2 < 0, (s2 / (2 * ST)) ** 2 + ((St.Yc / (2 * ST)) ** 2 - 1) * s2 / St.Yc + t ** 2, 0.0)
    return {"FT": ft, "FC": fc, "MT": mt, "MC": mc}


def puck_parameters(St, opt):
    ppt, ppc = opt.puck_p_pt, opt.puck_p_pc
    if not (0 < ppt < 1 and 0 < ppc < 1):
        raise CriterionUnavailable("puck", ["inclination parameters must lie in (0, 1)"])
    RA = St.S / (2 * ppc) * (np.sqrt(1 + 2 * ppc * St.Yc / St.S) - 1)
    pcc = ppc * RA / St.S
    t21c = St.S * np.sqrt(1 + 2 * pcc)
    return ppt, ppc, RA, pcc, t21c


def puck(s1, s2, t12, St, opt):
    ppt, ppc, RA, pcc, t21c = puck_parameters(St, opt)
    t = np.abs(t12)
    fA = np.sqrt((t / St.S) ** 2 + (1 - ppt * St.Yt / St.S) ** 2 * (s2 / St.Yt) ** 2) + ppt * s2 / St.S
    fB = (np.sqrt(t ** 2 + (ppc * s2) ** 2) + ppc * s2) / St.S
    with np.errstate(divide="ignore", invalid="ignore"):
        fC = ((t / (2 * (1 + pcc) * St.S)) ** 2 + (s2 / St.Yc) ** 2) * St.Yc / (-s2)
        ratio = np.abs(s2) / np.where(t > 0, t, np.nan)
    is_A = s2 >= 0
    is_B = (~is_A) & (t > 0) & (ratio <= RA / t21c)
    is_C = (~is_A) & (~is_B)
    zero = np.zeros_like(s1)
    return {"FT": np.where(s1 >= 0, s1 / St.Xt, 0.0), "FC": np.where(s1 < 0, -s1 / St.Xc, 0.0),
            "IFF-A": np.where(is_A, fA, zero), "IFF-B": np.where(is_B, fB, zero),
            "IFF-C": np.where(is_C, np.nan_to_num(fC, nan=0.0, posinf=0.0), zero)}


# ----------------------------------------------------------------------------- LaRC03
def _larc_setup(St: StrengthSet, opt: CriterionOptions) -> dict:
    key = ("larc", opt.larc_alpha0_deg, opt.larc_insitu)
    if key in St.extra:
        return St.extra[key]
    missing = []
    plies = St.plies
    for p in plies:
        for prop in ("GIc", "GIIc"):
            if not p.material.has(prop):
                missing.append(f"{p.material.name}: {prop}")
    if missing:
        raise CriterionUnavailable("larc03", sorted(set(missing)) + ["(fracture toughness needed for g = GIc/GIIc and in-situ strengths)"])
    GIc = _col([p.material.get("GIc") for p in plies])
    GIIc = _col([p.material.get("GIIc") for p in plies])
    if St.knock:  # toughness is not knocked down (no traceable model); flag it
        St.flags.append("LaRC03: fracture toughness not adjusted for environment (no traceable model)")
    a0 = np.radians(opt.larc_alpha0_deg)
    g = GIc / GIIc
    etaL_base = -St.S * np.cos(2 * a0) / (St.Yc * np.cos(a0) ** 2)
    etaT = -1 / np.tan(2 * a0)
    ST = St.Yc * np.cos(a0) * (np.sin(a0) + np.cos(a0) / np.tan(2 * a0))
    nu21 = St.nu12 * St.E2 / St.E1
    Lam = 2 * (1 / St.E2 - nu21 ** 2 / St.E1)
    YTis, SLis = St.Yt.copy(), St.S.copy()
    if opt.larc_insitu:
        # Effective ply-block thickness: consecutive plies with equal angle and material act as one ply.
        n = len(plies)
        tb = np.zeros(n)
        i = 0
        while i < n:
            j = i
            while j + 1 < n and plies[j + 1].angle == plies[i].angle and plies[j + 1].material.id == plies[i].material.id:
                j += 1
            tb[i:j + 1] = sum(plies[k].thickness for k in range(i, j + 1))
            i = j + 1
        tb = tb.reshape(-1, 1)
        outer = np.zeros((n, 1), bool)
        outer[0] = outer[-1] = True
        bi = 0
        while bi + 1 < n and plies[bi + 1].angle == plies[0].angle and plies[bi + 1].material.id == plies[0].material.id:
            bi += 1
        outer[: bi + 1] = True
        ti = n - 1
        while ti - 1 >= 0 and plies[ti - 1].angle == plies[-1].angle and plies[ti - 1].material.id == plies[-1].material.id:
            ti -= 1
        outer[ti:] = True
        Yt_thin_emb = np.sqrt(8 * GIc / (np.pi * tb * Lam))
        SL_thin_emb = np.sqrt(8 * St.G12 * GIIc / (np.pi * tb))
        Yt_outer = 1.79 * np.sqrt(GIc / (np.pi * tb * Lam))
        SL_outer = np.sqrt(4 * St.G12 * GIIc / (np.pi * tb))
        Yt_thick, SL_thick = 1.12 * np.sqrt(2) * St.Yt, np.sqrt(2) * St.S
        YTis = np.where(outer, np.maximum(St.Yt, Yt_outer), np.maximum(Yt_thick, Yt_thin_emb))
        SLis = np.where(outer, np.maximum(St.S, SL_outer), np.maximum(SL_thick, SL_thin_emb))
    etaL = etaL_base
    q = SLis / St.Xc + etaL
    disc = 1 - 4 * q * SLis / St.Xc
    if np.any(disc < 0):
        raise CriterionUnavailable("larc03", ["kink-band misalignment angle phi_C has no real solution for these strengths"])
    phiC = np.arctan((1 - np.sqrt(disc)) / (2 * q))
    eps1t = _col([p.material.get_or_derived("eps1t", "Xt", "E1") for p in plies])
    if St.knock and "Xt" in St.knock:
        eps1t = eps1t * _col(St.knock["Xt"])
    for p in plies:
        for f in p.material.flags:
            if f not in St.flags:
                St.flags.append(f)
    alphas = np.radians(np.arange(0.0, 90.0, 0.5))
    out = {"g": g, "etaL": etaL, "etaT": etaT, "ST": ST, "YTis": YTis, "SLis": SLis, "phiC": phiC,
           "eps1t": eps1t, "alphas": alphas}
    St.extra[key] = out
    return out


def _larc_mc(s2, t, P):
    """max over fracture angle of the LaRC03 matrix-compression index (s2 < 0 assumed where used)."""
    a = P["alphas"]
    ca, sa = np.cos(a), np.sin(a)
    s2e, te = s2[..., None], np.abs(t)[..., None]
    tT = _pos(-s2e * ca * (sa - P["etaT"] * ca))
    tL = _pos(ca * (te + P["etaL"][..., None] * s2e * ca))
    val = (tT / P["ST"][..., None]) ** 2 + (tL / P["SLis"][..., None]) ** 2
    return val.max(axis=-1)


def larc03(s1, s2, t12, St, opt):
    P = _larc_setup(St, opt)
    g, YT, SL = P["g"], P["YTis"], P["SLis"]
    t = np.abs(t12)
    e1 = s1 / St.E1 - St.nu12 * s2 / St.E1
    ft = np.where(s1 >= 0, e1 / P["eps1t"], 0.0)
    mt = np.where(s2 >= 0, (1 - g) * s2 / YT + g * (s2 / YT) ** 2 + (t / SL) ** 2, 0.0)
    # misalignment frame (used by fibre compression, and by matrix compression when s1 < -Yc)
    phi = (t + (St.G12 - St.Xc) * P["phiC"]) / (St.G12 + s1 - s2)
    sp, cp = np.sin(phi), np.cos(phi)
    s2m = sp ** 2 * s1 + cp ** 2 * s2 - 2 * sp * cp * t
    t12m = -sp * cp * s1 + sp * cp * s2 + (cp ** 2 - sp ** 2) * t
    fc_kink = np.where(s2m < 0, _pos(np.abs(t12m) + P["etaL"] * s2m) / SL,
                       (1 - g) * s2m / YT + g * (s2m / YT) ** 2 + (t12m / SL) ** 2)
    fc = np.where(s1 < 0, fc_kink, 0.0)
    neg = s2 < 0
    mc_plain = _larc_mc(np.where(neg, s2, 0.0), np.where(neg, t, 0.0), P)
    mc_mis = _larc_mc(np.where(neg, s2m, 0.0), np.where(neg, t12m, 0.0), P)
    mc = np.where(neg, np.where(s1 >= -St.Yc, mc_plain, mc_mis), 0.0)
    return {"FT": ft, "FC": fc, "MT": mt, "MC": mc}


FUNCS = {"max_stress": max_stress, "max_strain": max_strain, "tsai_hill": tsai_hill, "tsai_wu": tsai_wu,
         "hashin": hashin, "puck": puck, "larc03": larc03}


def evaluate(name: str, s1, s2, t12, St: StrengthSet, opt: CriterionOptions) -> dict[str, np.ndarray]:
    if name not in FUNCS:
        raise ValueError(f"Unknown criterion '{name}'")
    return FUNCS[name](s1, s2, t12, St, opt)


def governing(modes: dict[str, np.ndarray]) -> tuple[np.ndarray, np.ndarray]:
    names = list(modes)
    stack = np.stack([modes[k] for k in names])
    idx = np.argmax(stack, axis=0)
    return stack.max(axis=0), np.array(names, dtype=object)[idx]


def is_fibre_mode(mode: str) -> bool:
    return mode in FIBRE_MODES
