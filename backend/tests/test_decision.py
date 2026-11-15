"""V-O, V-U and supporting modules: optimisation, uncertainty, fatigue, design rules, materials. Author: Anwesh Ajitabh Dash."""
import json

import numpy as np
import pytest

from aerolaminate import criteria as C
from aerolaminate import designrules, fatigue as FT, optimize as OPT, uncertainty as UQ
from aerolaminate.materials import MaterialDatabase, MaterialValidationError, validate_material_dict
from aerolaminate.strength import laminate_rf
from conftest import lam_of


def problem(t300, **kw):
    base = dict(material=t300, ply_thickness=0.125, angles=[0, 45, 90], symmetric=True, balanced=True, min_plies=8,
                max_plies=24, loads=((400.0, 150.0, 60.0), (0, 0, 0)), criterion="tsai_wu", rf_min=1.5,
                min_fraction=0.1, max_consecutive=4, pop=24, generations=25, seed=3)
    base.update(kw)
    return OPT.OptProblem(**base)


def test_V_O_1_constraints_satisfied(t300):
    P = problem(t300)
    res = OPT.Optimizer(P, C.CriterionOptions()).run()
    assert res["ranked"], "optimizer found no feasible design for a known-feasible problem"
    for r in res["ranked"]:
        ang = r["layup"]
        assert ang == ang[::-1]                                  # symmetric
        for a in set(ang):
            if a not in (0, 90):
                assert ang.count(a) == ang.count(-a)             # balanced
        assert 8 <= len(ang) <= 24
        rules = {x["rule"]: x["status"] for x in designrules.check(ang, None, 0.1, 4)}
        assert rules["<= 4 consecutive plies of equal angle"] == "pass"
        assert rules["10% rule (0, +-45, 90 each >= 10%)"] == "pass"
        # independent re-evaluation of the strength constraint
        lam = lam_of(t300, ang)
        rf = laminate_rf(lam, C.build_strengths(lam.plies), (400, 150, 60), (0, 0, 0), 0, 0, "tsai_wu", C.CriterionOptions())
        assert rf >= 1.5 - 1e-9
        assert rf == pytest.approx(r["rf"], rel=1e-9)


def test_V_O_2_reproducible(t300):
    a = OPT.Optimizer(problem(t300), C.CriterionOptions()).run()
    b = OPT.Optimizer(problem(t300), C.CriterionOptions()).run()
    assert [r["layup"] for r in a["ranked"]] == [r["layup"] for r in b["ranked"]]
    assert a["history"] == b["history"]


def test_V_O_3_pareto_non_dominated(t300):
    res = OPT.Optimizer(problem(t300, generations=15), C.CriterionOptions()).run()
    pts = [(p["mass"], 1 / p["rf"]) for p in res["pareto"]]
    assert pts
    for i, p in enumerate(pts):
        for j, q in enumerate(pts):
            if i != j:
                assert not (q[0] <= p[0] and q[1] <= p[1] and (q[0] < p[0] or q[1] < p[1]))


def test_optimizer_reports_infeasible(t300):
    res = OPT.Optimizer(problem(t300, max_plies=8, rf_min=50.0, generations=5), C.CriterionOptions()).run()
    assert res["n_feasible"] == 0 and res["ranked"] == [] and "rf_min" in res["violation_counts"]


def test_optimizer_buckling_constraint(t300):
    P = problem(t300, loads=((-60.0, 0, 0), (0, 0, 0)), buckling_plate=(300.0, 200.0), buckling_min=1.0,
                generations=15, min_fraction=0.0, max_consecutive=0)
    res = OPT.Optimizer(P, C.CriterionOptions()).run()
    for r in res["ranked"]:
        assert r["buckling"] >= 1.0


def test_V_U_1_zero_cov_reproduces_deterministic(t300):
    lam = lam_of(t300, [0, 45, -45, 90, 90, -45, 45, 0])
    det = laminate_rf(lam, C.build_strengths(lam.plies), (200, 0, 0), (0, 0, 0), 0, 0, "tsai_wu", C.CriterionOptions())
    mc = UQ.monte_carlo(lam.plies, (200, 0, 0), (0, 0, 0), 0, 0, "tsai_wu", C.CriterionOptions(), {"Xt": 0.0}, n=20)
    assert mc["mean"] == pytest.approx(det, rel=1e-12) and mc["std"] == pytest.approx(0, abs=1e-12)


def test_monte_carlo_strength_scaling(t300):
    """Max-stress FPF RF is linear in Yt when the 90 ply governs: CoV(RF) ~ CoV(Yt)."""
    lam = lam_of(t300, [0, 90, 90, 0])
    mc = UQ.monte_carlo(lam.plies, (100, 0, 0), (0, 0, 0), 0, 0, "max_stress", C.CriterionOptions(), {"Yt": 0.1}, n=3000, seed=11)
    assert mc["std"] / mc["mean"] == pytest.approx(0.1, rel=0.08)


def test_sensitivity_signs(t300):
    lam = lam_of(t300, [0, 90, 90, 0])
    s = UQ.sensitivity(lam.plies, (100, 0, 0), (0, 0, 0), 0, 0, "max_stress", C.CriterionOptions())
    rows = {r["parameter"]: r for r in s["rows"]}
    assert rows["Yt"]["RF"] == pytest.approx(1.0, rel=1e-9)   # RF proportional to Yt (90 ply governs)
    assert rows["E1"]["Ex"] > 0.8 and rows["thickness"]["RF"] == pytest.approx(1.0, rel=1e-2)
    assert rows["thickness"]["D11"] == pytest.approx(3.0, rel=1e-2)


def test_fatigue_miner():
    res = FT.miner([{"load_factor": 0.5, "cycles": 1000}, {"load_factor": 0.25, "cycles": 1e5}], 1.0, "loglinear", {"b": 0.1})
    N1 = 10 ** (0.5 / 0.1); N2 = 10 ** (0.75 / 0.1)
    assert res["damage"] == pytest.approx(1000 / N1 + 1e5 / N2, rel=1e-12)
    assert FT.cycles_to_failure(0.5, "power", {"A": 1.0, "k": 10}) == pytest.approx(2 ** 10, rel=1e-12)
    with pytest.raises(ValueError):
        FT.miner([], float("inf"), "loglinear", {"b": 0.1})


def test_design_rules():
    r = {x["rule"]: x["status"] for x in designrules.check([45, -45, 0, 90, 90, 0, -45, 45])}
    assert r["Symmetric about mid-plane"] == "pass" and r["Balanced (+theta / -theta pairs)"] == "pass"
    assert r["+-45 surface plies (damage tolerance)"] == "pass"
    r = {x["rule"]: x["status"] for x in designrules.check([0, 0, 0, 0, 0, 30])}
    assert r["Balanced (+theta / -theta pairs)"] == "fail" and r["<= 4 consecutive plies of equal angle"] == "fail"
    assert r["10% rule (0, +-45, 90 each >= 10%)"] == "n/a"


def test_material_validation():
    good = {"id": "X1", "properties": {k: {"value": v, "status": "literature"} for k, v in
                                       dict(E1=100000, E2=8000, G12=4000, nu12=0.3).items()}}
    m = validate_material_dict(good)
    assert not m.has("Xt") and m.status("Xt") == "unavailable"
    for bad in ({**good, "id": "bad id!"},
                {**good, "properties": {**good["properties"], "E2": {"value": -1, "status": "literature"}}},
                {**good, "properties": {**good["properties"], "nu12": {"value": 5, "status": "literature"}}},
                {**good, "properties": {**good["properties"], "E1": {"value": 1, "status": "made-up"}}},
                {"id": "X2", "properties": {"E1": {"value": 1e5, "status": "literature"}}}):
        with pytest.raises(MaterialValidationError):
            validate_material_dict(bad)


def test_shipped_database_provenance(db):
    ids = {m.id for m in db.all()}
    assert {"IM7_8552", "AS4_3501-6", "CYCOM5320-1_T650"} <= ids
    cy = db.get("CYCOM5320-1_T650")
    assert cy.status("E1") == "illustrative" and cy.status("Xt") == "illustrative"
    for m in db.all():
        for k, p in m.properties.items():
            if p["status"] != "unavailable":
                assert p.get("unit"), (m.id, k)


def test_user_database_round_trip(tmp_path):
    db = MaterialDatabase(tmp_path / "u.json")
    rec = {"id": "MY_MAT", "name": "Mine", "properties": {"E1": 150000, "E2": 9000, "G12": 5000, "nu12": 0.3}}
    db.save_user(rec)
    db2 = MaterialDatabase(tmp_path / "u.json")
    assert db2.get("MY_MAT").get("E1") == 150000 and db2.get("MY_MAT").status("E1") == "estimated"
    db2.delete_user("MY_MAT")
    assert json.loads((tmp_path / "u.json").read_text())["materials"] == []
    with pytest.raises(KeyError):
        db2.delete_user("IM7_8552")


def test_verification_field_validation():
    rec = {"id": "V1", "properties": {"E1": {"value": 1.4e5, "status": "literature", "verification": "primary"},
                                      "E2": 9000, "G12": 5000, "nu12": 0.3}}
    m = validate_material_dict(rec)
    assert m.verification("E1") == "primary" and m.verification("E2") == "unverified"
    with pytest.raises(MaterialValidationError):
        validate_material_dict({**rec, "properties": {**rec["properties"], "E1": {"value": 1.4e5, "verification": "trust-me"}}})


def test_shipped_verification_annotations(db):
    im7 = db.get("IM7_8552")
    assert not im7.has("alpha1") and not im7.has("alpha2")          # never invented
    assert "NOT ENTERED" in im7.properties["alpha1"]["verification_note"]
    cy = db.get("CYCOM5320-1_T650")
    assert all(cy.verification(k) == "unverified" and cy.status(k) == "illustrative" for k in ("E1", "Xt", "Yt", "S12"))
    for m in db.all():
        assert m.plausibility_warnings() == [], m.id                 # shipped data in correct units
        for k, p in m.properties.items():
            if p["status"] != "unavailable":
                assert p["verification"] in ("primary", "secondary", "unverified")
