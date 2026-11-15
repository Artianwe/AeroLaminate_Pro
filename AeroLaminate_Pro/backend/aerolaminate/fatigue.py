"""Fatigue screening with a USER-SUPPLIED S-N curve and Palmgren-Miner damage summation.

Author: Anwesh Ajitabh Dash.

No fatigue data are shipped: composite S-N behaviour depends on layup, R-ratio, frequency and environment, and no
traceable data set could be established. S is the peak cyclic load normalised by the static reference failure load.
Models:  'loglinear'  S = 1 - b log10(N)        (common for composite coupons)
         'power'      S = A N^(-1/k)
Miner (1945) linear damage, no sequence effects, no residual-strength modelling. SCREENING only, not a life prediction.
"""
from __future__ import annotations

import numpy as np


def cycles_to_failure(S: float, model: str, p: dict) -> float:
    if S <= 0:
        return np.inf
    if model == "loglinear":
        b = float(p["b"])
        if b <= 0:
            raise ValueError("b must be positive")
        if S >= 1:
            return 1.0
        return float(10 ** ((1 - S) / b))
    if model == "power":
        A, k = float(p["A"]), float(p["k"])
        if A <= 0 or k <= 0:
            raise ValueError("A and k must be positive")
        return float(max((A / S) ** k, 1.0))
    raise ValueError("model must be 'loglinear' or 'power'")


def miner(blocks: list[dict], static_rf: float, model: str, params: dict, endurance_cycles: float = 1e9) -> dict:
    """blocks: [{load_factor (x applied design load), cycles}]; static_rf: static reserve factor of the design load."""
    if not static_rf or not np.isfinite(static_rf) or static_rf <= 0:
        raise ValueError("A finite positive static reserve factor is required to normalise the spectrum")
    rows, D = [], 0.0
    for i, blk in enumerate(blocks):
        lf, n = float(blk["load_factor"]), float(blk["cycles"])
        if lf < 0 or n < 0:
            raise ValueError(f"Block {i + 1}: load factor and cycles must be non-negative")
        S = lf / static_rf
        Nf = min(cycles_to_failure(S, model, params), endurance_cycles) if S > 0 else np.inf
        d = n / Nf if np.isfinite(Nf) and Nf > 0 else 0.0
        D += d
        rows.append({"block": i + 1, "S": S, "cycles": n, "N_allow": Nf if np.isfinite(Nf) else None, "damage": d})
    Ns = np.logspace(0, 9, 91)
    if model == "loglinear":
        curve = 1 - float(params["b"]) * np.log10(Ns)
    else:
        curve = float(params["A"]) * Ns ** (-1 / float(params["k"]))
    curve = np.clip(curve, 0, None)
    return {"blocks": rows, "damage": D, "passes": D < 1.0, "sn_curve": {"N": Ns.tolist(), "S": curve.tolist()},
            "classification": "screening (user S-N, linear Miner)",
            "notes": ["S-N parameters are user data; the R-ratio and environment must match the test data.",
                      "Miner's rule ignores load-sequence effects; D < 1 does not demonstrate fatigue life."]}
