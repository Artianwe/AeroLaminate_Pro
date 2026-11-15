"""Constrained stacking-sequence optimisation by genetic algorithm with a non-dominated archive.

Author: Anwesh Ajitabh Dash.

Heuristic search (Le Riche & Haftka 1993; Gurdal, Haftka & Hajela 1999). Constraint handling uses Deb's
feasibility rules in tournament selection (feasible beats infeasible; lower total violation wins among
infeasible; lower objective wins among feasible). Results are NOT guaranteed global optima.

Genome: list of angle 'units' for the half stack (symmetric) or full stack. With balance enforced,
a unit of angle theta not in {0, 90} expands to the pair (+theta, -theta).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from . import criteria as C
from . import designrules
from .buckling import buckling
from .clt import Laminate, Ply, SingularLaminateError
from .strength import laminate_rf


@dataclass
class OptProblem:
    material: object
    ply_thickness: float
    angles: list[float] = field(default_factory=lambda: [0.0, 45.0, 90.0])
    symmetric: bool = True
    balanced: bool = True
    min_plies: int = 8
    max_plies: int = 32
    loads: tuple = ((0, 0, 0), (0, 0, 0))
    dT: float = 0.0
    dC: float = 0.0
    criterion: str = "tsai_wu"
    rf_min: float = 1.5
    min_Ex: float = 0.0
    min_Ey: float = 0.0
    min_Gxy: float = 0.0
    max_mass: float | None = None
    min_fraction: float = 0.0
    max_consecutive: int = 0           # 0 = not enforced
    outer_45: bool = False
    buckling_plate: tuple | None = None  # (a, b) mm; uses Nx, Ny, Nxy of the load case
    buckling_min: float = 1.0
    w_mass: float = 1.0
    w_fi: float = 0.0
    w_coupling: float = 0.0
    w_buckling: float = 0.0
    pop: int = 40
    generations: int = 60
    seed: int = 7
    p_mut: float = 0.3


class Optimizer:
    def __init__(self, P: OptProblem, copt: C.CriterionOptions):
        if not P.angles:
            raise ValueError("At least one allowed angle is required")
        if P.min_plies < 1 or P.max_plies < P.min_plies or P.max_plies > 200:
            raise ValueError("Ply-count bounds must satisfy 1 <= min <= max <= 200")
        if not (2 <= P.pop <= 400 and 1 <= P.generations <= 500):
            raise ValueError("Population 2..400 and generations 1..500")
        self.P, self.copt = P, copt
        self.rng = np.random.default_rng(P.seed)
        self.units = sorted({abs(float(a)) % 180 if abs(float(a)) % 180 <= 90 else 180 - abs(float(a)) % 180 for a in P.angles}) \
            if P.balanced else sorted({float(a) for a in P.angles})
        self.cache: dict[tuple, dict] = {}
        self.mass_ref = None

    # ---------------------------------------------------------------- genome <-> layup
    def unit_plies(self, u: float) -> list[float]:
        if self.P.balanced and u not in (0.0, 90.0):
            return [u, -u]
        return [u]

    def layup(self, g: list[float]) -> list[float]:
        half = [a for u in g for a in self.unit_plies(u)]
        return half + half[::-1] if self.P.symmetric else half

    def random_genome(self) -> list[float]:
        P = self.P
        for _ in range(200):
            k = int(self.rng.integers(1, max(2, P.max_plies)))
            g = [float(self.rng.choice(self.units)) for _ in range(k)]
            if P.min_plies <= len(self.layup(g)) <= P.max_plies:
                return g
        return [float(self.units[0])] * max(1, P.min_plies // (2 if P.symmetric else 1))

    # ---------------------------------------------------------------- evaluation
    def evaluate(self, g: list[float]) -> dict:
        key = tuple(g)
        if key in self.cache:
            return self.cache[key]
        P = self.P
        ang = self.layup(g)
        viol = {}
        res = {"genome": list(g), "layup": ang, "n_plies": len(ang)}
        if len(ang) < P.min_plies:
            viol["min_plies"] = (P.min_plies - len(ang)) / P.min_plies
        if len(ang) > P.max_plies:
            viol["max_plies"] = (len(ang) - P.max_plies) / P.max_plies
        plies = [Ply(P.material, a, P.ply_thickness) for a in ang]
        try:
            lam = Laminate(plies)
            St = C.build_strengths(plies)
            N, M = P.loads
            rf = laminate_rf(lam, St, N, M, P.dT, P.dC, P.criterion, self.copt)
            ec = lam.engineering_constants()
        except (SingularLaminateError, ValueError) as e:
            res.update({"feasible": False, "violation": 1e3, "objective": np.inf, "error": str(e)})
            self.cache[key] = res
            return res
        mass = lam.areal_mass()
        rf_val = rf if np.isfinite(rf) else 1e6
        res.update({"rf": rf_val, "mass": mass, "thickness": lam.h, "Ex": ec["Ex"], "Ey": ec["Ey"], "Gxy": ec["Gxy"]})
        if rf_val < P.rf_min:
            viol["rf_min"] = (P.rf_min - rf_val) / P.rf_min
        for k, lim in (("Ex", P.min_Ex), ("Ey", P.min_Ey), ("Gxy", P.min_Gxy)):
            if lim and ec[k] < lim:
                viol[f"min_{k}"] = (lim - ec[k]) / lim
        if P.max_mass and mass is not None and mass > P.max_mass:
            viol["max_mass"] = (mass - P.max_mass) / P.max_mass
        rules = {r["rule"]: r for r in designrules.check(ang, None, P.min_fraction or 0.0, P.max_consecutive or 10 ** 6)}
        if P.min_fraction:
            r = next(v for k, v in rules.items() if "rule (0" in k)
            if r["status"] == "fail":
                viol["min_fraction"] = 0.5
        if P.max_consecutive:
            r = next(v for k, v in rules.items() if "consecutive" in k)
            if r["status"] == "fail":
                viol["max_consecutive"] = 0.5
        if P.outer_45 and not all(abs(abs(a) - 45) < 1e-9 for a in (ang[0], ang[-1])):
            viol["outer_45"] = 0.5
        cpl = lam.coupling()
        coupling = abs(cpl["bending_twisting_delta"]) + abs(cpl["bending_twisting_gamma"]) + cpl["extension_shear"] + cpl["extension_bending"]
        res["coupling"] = coupling
        lamb = None
        if P.buckling_plate:
            a, b = P.buckling_plate
            Nv = P.loads[0]
            try:
                bk = buckling(lam, a, b, Nv[0], Nv[1], Nv[2], terms=5, grid=3)
                lamb = bk["load_factor"]
            except ValueError:
                lamb = None
            res["buckling"] = lamb if lamb is not None else None
            if lamb is not None and lamb < P.buckling_min:
                viol["buckling"] = (P.buckling_min - lamb) / P.buckling_min
        mref = self.mass_ref or (mass or len(ang))
        obj = P.w_mass * ((mass if mass is not None else len(ang)) / mref) + P.w_fi * (1 / max(rf_val, 1e-9)) \
            + P.w_coupling * coupling + (P.w_buckling * (1 / lamb) if (P.w_buckling and lamb) else 0.0)
        res.update({"violations": viol, "violation": float(sum(viol.values())), "feasible": not viol, "objective": float(obj)})
        self.cache[key] = res
        return res

    # ---------------------------------------------------------------- operators
    def _better(self, a: dict, b: dict) -> bool:
        if a["feasible"] != b["feasible"]:
            return a["feasible"]
        if not a["feasible"]:
            return a["violation"] < b["violation"]
        return a["objective"] < b["objective"]

    def _tournament(self, popres):
        i, j = self.rng.integers(0, len(popres), 2)
        return popres[i] if self._better(popres[i], popres[j]) else popres[j]

    def _crossover(self, g1, g2):
        if len(g1) < 2 or len(g2) < 2:
            return list(g1)
        c1 = int(self.rng.integers(1, len(g1)))
        c2 = int(self.rng.integers(1, len(g2)))
        return list(g1[:c1]) + list(g2[c2:])

    def _mutate(self, g):
        g = list(g)
        r = self.rng.random()
        if r < 0.4 and g:
            g[int(self.rng.integers(0, len(g)))] = float(self.rng.choice(self.units))
        elif r < 0.6 and len(g) > 1:
            i, j = self.rng.integers(0, len(g), 2)
            g[i], g[j] = g[j], g[i]
        elif r < 0.8:
            g.insert(int(self.rng.integers(0, len(g) + 1)), float(self.rng.choice(self.units)))
        elif len(g) > 1:
            g.pop(int(self.rng.integers(0, len(g))))
        return g

    # ---------------------------------------------------------------- run
    def run(self, baseline: list[float] | None = None) -> dict:
        P = self.P
        self.mass_ref = P.max_plies * P.ply_thickness * 1e-3 * (P.material.get("density") if P.material.has("density") else 1000.0)
        pop = [self.random_genome() for _ in range(P.pop)]
        history = []
        for gen in range(P.generations):
            popres = [self.evaluate(g) for g in pop]
            feas = [r for r in popres if r["feasible"]]
            best = min(feas, key=lambda r: r["objective"]) if feas else min(popres, key=lambda r: r["violation"])
            history.append({"generation": gen + 1, "best_objective": best["objective"] if feas else None,
                            "mean_objective": float(np.mean([r["objective"] for r in feas])) if feas else None,
                            "n_feasible": len(feas), "best_violation": best["violation"], "unique_evaluated": len(self.cache)})
            elite = sorted(popres, key=lambda r: (not r["feasible"], r["violation"] if not r["feasible"] else r["objective"]))[:2]
            new = [e["genome"] for e in elite]
            while len(new) < P.pop:
                a, b = self._tournament(popres), self._tournament(popres)
                child = self._crossover(a["genome"], b["genome"]) if self.rng.random() < 0.9 else list(a["genome"])
                if self.rng.random() < P.p_mut or child == a["genome"]:
                    child = self._mutate(child)
                if child:
                    new.append(child)
            pop = new
        allres = [r for r in self.cache.values() if "objective" in r]
        feas = sorted([r for r in allres if r["feasible"]], key=lambda r: r["objective"])
        pareto = _pareto([r for r in feas if r.get("mass") is not None],
                         keys=("mass", "inv_rf") + (("inv_buckling",) if P.buckling_plate else ()))
        viol_count: dict[str, int] = {}
        for r in allres:
            for k in r.get("violations", {}):
                viol_count[k] = viol_count.get(k, 0) + 1
        ranked = []
        for i, r in enumerate(feas[:10]):
            ranked.append({**_public(r), "rank": i + 1, "reasoning": _reason(r, P)})
        base = None
        if baseline:
            plies = [Ply(P.material, a, P.ply_thickness) for a in baseline]
            lam = Laminate(plies)
            St = C.build_strengths(plies)
            rf = laminate_rf(lam, St, P.loads[0], P.loads[1], P.dT, P.dC, P.criterion, self.copt)
            ec = lam.engineering_constants()
            base = {"layup": baseline, "rf": rf if np.isfinite(rf) else None, "mass": lam.areal_mass(), "n_plies": len(baseline),
                    "Ex": ec["Ex"], "Ey": ec["Ey"], "Gxy": ec["Gxy"]}
        return {"history": history, "ranked": ranked, "pareto": [_public(r) for r in pareto],
                "n_evaluated": len(self.cache), "n_feasible": len(feas), "violation_counts": viol_count, "baseline": base,
                "infeasible_examples": [_public(r) for r in sorted([r for r in allres if not r["feasible"]], key=lambda r: r["violation"])[:5]],
                "classification": "heuristic (genetic algorithm); no global-optimality guarantee",
                "objective_definition": "w_mass*mass/mass_ref + w_fi*(1/RF) + w_coupling*coupling + w_buckling*(1/lambda_buckling)"}


def _public(r):
    keys = ("layup", "n_plies", "rf", "mass", "thickness", "Ex", "Ey", "Gxy", "coupling", "buckling", "objective", "feasible", "violations")
    return {k: r.get(k) for k in keys if k in r}


def _reason(r, P) -> str:
    bits = [f"{r['n_plies']} plies, RF {r['rf']:.2f} (>= {P.rf_min:g} required)"]
    if r.get("mass") is not None:
        bits.append(f"areal mass {r['mass']:.3f} kg/m^2")
    if r.get("buckling") is not None:
        bits.append(f"buckling factor {r['buckling']:.2f}")
    margin = r["rf"] / P.rf_min - 1
    bits.append("strength-critical" if margin < 0.1 else f"strength margin {margin:.0%} above the requirement")
    return "; ".join(bits)


def _pareto(rs, keys):
    def vec(r):
        v = []
        for k in keys:
            if k == "inv_rf":
                v.append(1 / max(r["rf"], 1e-9))
            elif k == "inv_buckling":
                v.append(1 / r["buckling"] if r.get("buckling") else np.inf)
            else:
                v.append(r[k])
        return np.array(v)
    vs = [vec(r) for r in rs]
    front = []
    for i, vi in enumerate(vs):
        dominated = any(np.all(vj <= vi) and np.any(vj < vi) for j, vj in enumerate(vs) if j != i)
        if not dominated:
            front.append(rs[i])
    # remove duplicates with identical objective vectors
    seen, out = set(), []
    for r in sorted(front, key=lambda r: r["mass"]):
        k = tuple(np.round(vec(r), 12))
        if k not in seen:
            seen.add(k); out.append(r)
    return out
