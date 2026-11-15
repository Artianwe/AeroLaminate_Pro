"""AeroLaminate Pro - smoke test against a RUNNING installation (standard library only).
Author, owner and maintainer: Anwesh Ajitabh Dash.

Usage (after START_AEROLAMINATE.bat, or after starting both servers manually):
    backend\\.venv\\Scripts\\python tools\\smoke_test.py            (Windows)
    backend/.venv/bin/python tools/smoke_test.py                   (Linux/macOS)
Options: --ui http://127.0.0.1:3000  --api http://127.0.0.1:8000
Exit code 0 = all checks passed. Checks go through the UI's /api proxy (the path the browser uses) and directly to the engine.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request

OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))   # never route 127.0.0.1 via a proxy


def call(url: str, body: dict | None = None, timeout: float = 60):
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"} if data else {})
    try:
        with OPENER.open(req, timeout=timeout) as r:
            raw = r.read()
            return r.status, raw
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ui", default="http://127.0.0.1:3000")
    ap.add_argument("--api", default="http://127.0.0.1:8000")
    a = ap.parse_args()
    results: list[tuple[str, bool, str]] = []

    def check(name, ok, detail=""):
        results.append((name, bool(ok), detail))

    QI = {"material_id": "T300_5208", "plies": [{"angle": x} for x in (0, 45, -45, 90, 90, -45, 45, 0)],
          "loads": {"Nx": 100}, "criteria": ["max_stress", "tsai_wu"]}
    try:
        s, raw = call(a.api + "/api/health")
        h = json.loads(raw)
        check("engine /api/health", s == 200 and h.get("author") == "Anwesh Ajitabh Dash", f"version {h.get('version')}")
        s, raw = call(a.ui + "/")
        check("UI root page", s == 200 and b"AeroLaminate Pro" in raw)
        s, raw = call(a.ui + "/report")
        check("UI report page", s == 200)
        s, raw = call(a.ui + "/api/health")
        check("UI -> engine proxy", s == 200)
        s, raw = call(a.ui + "/api/materials")
        mats = {m["id"] for m in json.loads(raw)["materials"]} if s == 200 else set()
        check("material database", {"IM7_8552", "AS4_3501-6", "CYCOM5320-1_T650"} <= mats, f"{len(mats)} records")
        s, raw = call(a.ui + "/api/analyze", QI)
        j = json.loads(raw)
        ex = j.get("engineering_constants", {}).get("Ex", 0) if s == 200 else 0
        # Independent closed form for a quasi-isotropic laminate: Ex = (U1^2 - U4^2)/U1 = 69 675.74 MPa (T300/5208)
        check("CLT reference value (QI Ex)", s == 200 and abs(ex - 69675.74) < 0.05, f"Ex = {ex:.2f} MPa")
        s, raw = call(a.ui + "/api/analyze", {**QI, "material_id": "CYCOM5320-1_T650"})
        check("illustrative data blocked", s == 400 and json.loads(raw).get("kind") == "illustrative_blocked")
        s, raw = call(a.ui + "/api/analyze", {**QI, "material_id": "IM7_8552", "environment": {"T_stress_free": 177, "T_service": 21}})
        check("missing IM7/8552 CTE refused", s == 400 and json.loads(raw).get("kind") == "missing_property")
        for ep, extra in (("envelope", {"ply": 4}), ("progressive", {"criterion": "max_stress"}), ("environment", {"points": 5}),
                          ("interlaminar", {}), ("buckling", {}), ("notched", {}), ("uncertainty", {"samples": 20}),
                          ("parametric", {"vary_plies": [2, 3], "step": 30}), ("fatigue", {"blocks": [{"load_factor": 0.5, "cycles": 1000}]}),
                          ("optimize", {"generations": 3, "pop": 6, "rf_min": 0.5})):
            proj = {**QI, "loads": {"Nx": -20}} if ep == "buckling" else QI
            s, raw = call(a.ui + f"/api/{ep}", {"project": proj, **extra})
            check(f"endpoint /api/{ep}", s == 200, "" if s == 200 else raw[:160].decode(errors="replace"))
    except (urllib.error.URLError, OSError, ValueError) as e:
        check("connection", False, str(e))

    w = max(len(n) for n, _, _ in results)
    for n, ok, d in results:
        print(f"[{'PASS' if ok else 'FAIL'}] {n.ljust(w)}  {d}")
    failed = sum(not ok for _, ok, _ in results)
    print(f"\n{len(results) - failed}/{len(results)} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
