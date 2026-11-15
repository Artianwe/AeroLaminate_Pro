"""Stacking-sequence design-rule checks (industry guidelines, not regulations).

Author: Anwesh Ajitabh Dash. Sources: Niu (1992); Kassapoglou (2013); CMH-17-3G Vol. 3 ch. 5.
"""
from __future__ import annotations

from collections import Counter


def _norm(a: float) -> float:
    a = ((a + 90) % 180) - 90
    return 90.0 if abs(a + 90) < 1e-9 else a


def check(angles: list[float], thicknesses: list[float] | None = None, min_fraction: float = 0.10,
          max_consecutive: int = 4, max_angle_jump: float = 60.0) -> list[dict]:
    a = [_norm(x) for x in angles]
    n = len(a)
    t = thicknesses or [1.0] * n
    rules = []
    sym = all(abs(a[i] - a[n - 1 - i]) < 1e-9 and abs(t[i] - t[n - 1 - i]) < 1e-12 for i in range(n))
    rules.append({"rule": "Symmetric about mid-plane", "status": "pass" if sym else "fail",
                  "detail": "B = 0, no thermal warpage" if sym else "Extension-bending coupling and cure warpage expected"})
    cnt = Counter()
    for x, ti in zip(a, t):
        if abs(x) > 1e-9 and abs(abs(x) - 90) > 1e-9:
            cnt[round(x, 6)] += ti
    unb = [f"{k:g}" for k in cnt if abs(cnt[k] - cnt.get(-k, 0)) > 1e-12]
    rules.append({"rule": "Balanced (+theta / -theta pairs)", "status": "pass" if not unb else "fail",
                  "detail": "A16 = A26 = 0" if not unb else f"Unpaired angles: {', '.join(sorted(set(unb)))}"})
    tot = sum(t)
    fams = {"0": lambda x: abs(x) < 1e-9, "+-45": lambda x: abs(abs(x) - 45) < 1e-9, "90": lambda x: abs(abs(x) - 90) < 1e-9}
    fr = {k: sum(ti for x, ti in zip(a, t) if f(x)) / tot for k, f in fams.items()}
    low = [f"{k}: {v:.0%}" for k, v in fr.items() if v < min_fraction - 1e-12]
    only_std = all(any(f(x) for f in fams.values()) for x in a)
    rules.append({"rule": f"{min_fraction:.0%} rule (0, +-45, 90 each >= {min_fraction:.0%})",
                  "status": ("pass" if not low else "fail") if only_std else "n/a",
                  "detail": ", ".join(f"{k} {v:.0%}" for k, v in fr.items()) if only_std else "Non-standard angles present"})
    run, worst = 1, 1
    for i in range(1, n):
        run = run + 1 if abs(a[i] - a[i - 1]) < 1e-9 else 1
        worst = max(worst, run)
    rules.append({"rule": f"<= {max_consecutive} consecutive plies of equal angle", "status": "pass" if worst <= max_consecutive else "fail",
                  "detail": f"Longest block: {worst} plies"})
    outer = [a[0], a[-1]]
    ok45 = all(abs(abs(x) - 45) < 1e-9 for x in outer)
    rules.append({"rule": "+-45 surface plies (damage tolerance)", "status": "pass" if ok45 else "fail",
                  "detail": f"Outer plies: {outer[0]:g} / {outer[1]:g}"})
    jumps = [abs(_norm(a[i] - a[i - 1])) for i in range(1, n)]
    big = max(jumps) if jumps else 0
    rules.append({"rule": f"Adjacent angle change <= {max_angle_jump:g} deg", "status": "pass" if big <= max_angle_jump + 1e-9 else "fail",
                  "detail": f"Largest change: {big:g} deg"})
    return rules
