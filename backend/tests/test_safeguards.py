"""Engineering safeguards: conventions, unsupported-analysis guards, consistency under knockdown.
Author: Anwesh Ajitabh Dash."""
import warnings

import numpy as np
import pytest

from aerolaminate import buckling as BK
from aerolaminate.clt import T_eps, T_sigma
from conftest import lam_of, make_material

warnings.filterwarnings("ignore", category=DeprecationWarning)


def _rot(theta):
    t = np.radians(theta)
    return np.array([[np.cos(t), np.sin(t)], [-np.sin(t), np.cos(t)]])   # x-y -> 1-2 (fibre at +theta CCW)


@pytest.mark.parametrize("theta", [0, 30, -45, 60, 90, 137])
def test_transformations_match_tensor_rotation(theta):
    """Independent derivation: rotate the 2x2 stress/strain tensors with R s R^T."""
    R = _rot(theta)
    sx, sy, txy = 120.0, -35.0, 42.0
    s12 = R @ np.array([[sx, txy], [txy, sy]]) @ R.T
    np.testing.assert_allclose(T_sigma(theta) @ [sx, sy, txy], [s12[0, 0], s12[1, 1], s12[0, 1]], atol=1e-10)
    ex, ey, gxy = 1e-3, -4e-4, 6e-4
    e12 = R @ np.array([[ex, gxy / 2], [gxy / 2, ey]]) @ R.T
    np.testing.assert_allclose(T_eps(theta) @ [ex, ey, gxy], [e12[0, 0], e12[1, 1], 2 * e12[0, 1]], atol=1e-15)


def test_fibre_direction_sign_convention(t300):
    """A +45 ply under pure positive shear Nxy carries fibre-direction TENSION (theta CCW from +x)."""
    lam = lam_of(t300, [45, 45, 45, 45])
    st = lam.ply_state(lam.solve((0, 0, 10.0), (0, 0, 0)))
    tau = 10.0 / lam.h                                   # homogeneous single-material laminate: tau_xy = Nxy / h
    np.testing.assert_allclose(st["sigma_12"][0, 0], [tau, -tau, 0.0], atol=1e-9)   # sigma1 = +tau, sigma2 = -tau
    lam = lam_of(t300, [-45] * 4)
    assert lam.ply_state(lam.solve((0, 0, 10.0), (0, 0, 0)))["sigma_12"][0, 0, 0] < 0


def test_moment_sign_convention(t300):
    """Positive Mx gives positive kappa_x and tension on the top (+z) surface, ply list bottom -> top."""
    lam = lam_of(t300, [0] * 4)
    r = lam.solve((0, 0, 0), (5.0, 0, 0))
    st = lam.ply_state(r)
    assert r.kappa[0] > 0
    assert st["sigma_xy"][-1, 2, 0] > 0 and st["sigma_xy"][0, 0, 0] < 0   # top in tension, bottom in compression
    np.testing.assert_allclose(st["z"][-1, 2], lam.h / 2) and np.testing.assert_allclose(st["z"][0, 0], -lam.h / 2)


def test_thick_plate_flag():
    lam = lam_of(make_material(), [0] * 4, 2.5)       # h = 10 mm, b = 150 mm -> span/h = 15
    assert any("span/thickness" in f for f in BK.buckling(lam, 150, 150, -1, 0, 0, terms=4)["flags"])
    lam = lam_of(make_material(), [0] * 4, 0.25)
    assert not any("span/thickness" in f for f in BK.buckling(lam, 150, 150, -1, 0, 0, terms=4)["flags"])


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    import os
    os.environ["AEROLAMINATE_USER_DATA"] = str(tmp_path_factory.mktemp("user"))
    from fastapi.testclient import TestClient
    from app.main import app
    return TestClient(app)


HOT = {"material_id": "IM7_8552", "plies": [{"angle": a} for a in [45, -45, 0, 90, 90, 0, -45, 45]],
       "loads": {"Nx": 300, "Ny": 60}, "criteria": ["tsai_wu", "hashin"],
       "environment": {"T_stress_free": 120, "T_service": 120, "moisture": 0.0, "hotwet_knockdown": True}}


def test_parametric_reproduces_analysis_under_knockdown(client):
    """Regression: the sweep at the current angles must equal the main analysis (hot/wet knockdown included)."""
    a = client.post("/api/analyze", json=HOT).json()
    p = client.post("/api/parametric", json={"project": HOT, "vary_plies": [1, 2, 7, 8], "start": 45, "stop": 45, "step": 1}).json()
    for c in ("tsai_wu", "hashin"):
        assert p["rf"][c][0] == pytest.approx(a["failure"]["results"][c]["critical"]["rf"], rel=1e-9)
    assert p["Ex"][0] == pytest.approx(a["engineering_constants"]["Ex"], rel=1e-12)


def test_knockdown_unsupported_modules_refuse(client):
    for ep, extra in (("optimize", {"generations": 2, "pop": 4}), ("uncertainty", {"samples": 10})):
        r = client.post(f"/api/{ep}", json={"project": HOT, **extra})
        assert r.status_code == 400 and "knockdown" in r.json()["detail"], ep


def test_notch_and_delamination_flag_ignored_loads(client):
    P = {"material_id": "IM7_8552", "plies": [{"angle": a} for a in [45, -45, 0, 90, 90, 0, -45, 45]],
         "loads": {"Nx": 200, "Ny": 50, "Mx": 1}}
    n = client.post("/api/notched", json={"project": P}).json()
    assert any("Only Nx" in f for f in n["flags"])
    il = client.post("/api/interlaminar", json={"project": P, "delam_interfaces": [3]}).json()
    assert any("uniaxial" in f for f in il["edge_delamination"]["flags"])


def test_missing_swelling_coefficient_refused(client):
    r = client.post("/api/analyze", json={**HOT, "environment": {**HOT["environment"], "moisture": 1.0}})
    assert r.status_code == 400 and "beta1" in r.json()["detail"]
