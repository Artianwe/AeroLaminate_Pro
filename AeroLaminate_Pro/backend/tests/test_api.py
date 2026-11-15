"""V-API: REST layer validation and error handling. Author: Anwesh Ajitabh Dash."""
import os
import warnings

import pytest

warnings.filterwarnings("ignore", category=DeprecationWarning)


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    os.environ["AEROLAMINATE_USER_DATA"] = str(tmp_path_factory.mktemp("user"))
    from fastapi.testclient import TestClient
    from app.main import app
    return TestClient(app)


P = {"material_id": "AS4_3501-6", "plies": [{"angle": a} for a in [45, -45, 0, 90, 90, 0, -45, 45]],
     "loads": {"Nx": 200, "Nxy": 30, "Qx": 10}, "environment": {"T_stress_free": 177, "T_service": 21}}


def test_health(client):
    j = client.get("/api/health").json()
    assert j["author"] == "Anwesh Ajitabh Dash" and j["status"] == "ok"


def test_analyze_shape_and_provenance(client):
    r = client.post("/api/analyze", json=P)
    assert r.status_code == 200
    j = r.json()
    assert len(j["matrices"]["ABD"]) == 6 and j["classification"]["symmetric_stiffness"]
    assert "larc03" in j["failure"]["unavailable"]
    assert any("density" in w for w in j["provenance"]["warnings"])
    assert j["fpf"]["rf"] > 0


@pytest.mark.parametrize("ep,body", [
    ("analyze", {**P, "plies": [{"angle": 200}]}),
    ("analyze", {**P, "plies": [{"angle": 0, "thickness": -1}]}),
    ("analyze", {**P, "plies": []}),
    ("analyze", {**P, "criteria": ["bogus"]}),
    ("analyze", {**P, "loads": {"Nx": "abc"}}),
    ("buckling", {"project": P, "terms": 50}),
])
def test_validation_422(client, ep, body):
    assert client.post(f"/api/{ep}", json=body).status_code == 422


def test_unknown_material_404(client):
    assert client.post("/api/analyze", json={**P, "material_id": "NOPE"}).status_code == 404


def test_missing_property_400(client):
    r = client.post("/api/analyze", json={**P, "material_id": "IM7_8552"})
    assert r.status_code == 400 and r.json()["kind"] == "missing_property" and "alpha1" in r.json()["detail"]


def test_illustrative_material_blocked_by_default(client):
    body = {**P, "material_id": "CYCOM5320-1_T650", "environment": {}}
    for ep, wrap in (("analyze", False), ("progressive", True), ("buckling", True), ("optimize", True)):
        r = client.post(f"/api/{ep}", json={"project": body} if wrap else body)
        assert r.status_code == 400 and r.json()["kind"] == "illustrative_blocked", ep
    # explicit demonstration-mode opt-in runs, with the warning first
    r = client.post("/api/analyze", json={**body, "options": {"allow_illustrative": True}})
    assert r.status_code == 200
    assert "ILLUSTRATIVE" in r.json()["provenance"]["warnings"][0]


def test_verification_provenance_reported(client):
    j = client.post("/api/analyze", json=P).json()
    ver = j["provenance"]["verification"]["AS4_3501-6"]
    assert ver["E1"] == "unverified"
    assert any("NOT verified against a primary source" in w for w in j["provenance"]["warnings"])


def test_unit_slip_warning(client):
    mats = client.get("/api/materials").json()["materials"]
    m = next(x for x in mats if x["id"] == "T300_5208")
    m["properties"]["E1"] = {"value": 181.0, "status": "estimated"}   # GPa typed into an MPa field
    m["properties"]["E2"] = {"value": 10.3, "status": "estimated"}
    m["properties"]["G12"] = {"value": 7.17, "status": "estimated"}
    r = client.post("/api/analyze", json={**P, "material_id": "T300_5208", "materials": [m], "environment": {}})
    assert r.status_code == 200
    assert any("check units" in w for w in r.json()["provenance"]["warnings"])


def test_inline_material_override(client):
    mats = client.get("/api/materials").json()["materials"]
    im7 = next(m for m in mats if m["id"] == "IM7_8552")
    im7["properties"]["alpha1"] = {"value": -0.5e-6, "status": "estimated"}
    im7["properties"]["alpha2"] = {"value": 30e-6, "status": "estimated"}
    r = client.post("/api/analyze", json={**P, "material_id": "IM7_8552", "materials": [im7]})
    assert r.status_code == 200
    assert any("alpha1" in w for w in r.json()["provenance"]["warnings"])


def test_user_material_crud(client):
    rec = {"name": "Test", "properties": {"E1": 140000, "E2": 9000, "G12": 5000, "nu12": 0.3}}
    assert client.put("/api/materials/IM7_8552", json=rec).status_code == 400   # shipped is read-only
    assert client.put("/api/materials/TEST_1", json=rec).status_code == 200
    assert any(m["id"] == "TEST_1" for m in client.get("/api/materials").json()["materials"])
    assert client.delete("/api/materials/TEST_1").status_code == 200
    assert client.delete("/api/materials/TEST_1").status_code == 404


@pytest.mark.parametrize("ep,extra", [
    ("envelope", {"ply": 4}), ("progressive", {}), ("environment", {"points": 6}),
    ("interlaminar", {"delam_interfaces": [3]}), ("notched", {}), ("uncertainty", {"samples": 20}),
    ("parametric", {"vary_plies": [1, 2, 7, 8], "step": 30}),
    ("fatigue", {"blocks": [{"load_factor": 1, "cycles": 1000}]}),
    ("optimize", {"generations": 3, "pop": 8, "rf_min": 0.1}),
])
def test_endpoints_ok(client, ep, extra):
    r = client.post(f"/api/{ep}", json={"project": P, **extra})
    assert r.status_code == 200, r.text


def test_buckling_endpoint(client):
    r = client.post("/api/buckling", json={"project": {**P, "loads": {"Nx": -10}, "environment": {}}, "a": 400, "b": 300})
    j = r.json()
    assert r.status_code == 200 and j["load_factor"] > 0 and len(j["w"]) == 31


def test_progressive_rejects_tsai_wu(client):
    assert client.post("/api/progressive", json={"project": P, "criterion": "tsai_wu"}).status_code == 422
