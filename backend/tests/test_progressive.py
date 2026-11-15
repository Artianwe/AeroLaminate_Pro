"""V-PF: progressive failure. Author: Anwesh Ajitabh Dash."""
import numpy as np
import pytest

from aerolaminate import criteria as C
from aerolaminate import progressive as PFA
from conftest import lam_of


def run(lam, crit="max_stress", N=(1, 0, 0), **kw):
    St = C.build_strengths(lam.plies)
    return PFA.run(lam.plies, St, N, (0, 0, 0), 0, 0, PFA.PFAOptions(criterion=crit, **kw), C.CriterionOptions())


def test_V_PF_1_unidirectional_fpf_equals_lpf(t300):
    lam = lam_of(t300, [0] * 4)
    r = run(lam)
    assert r["fpf_load_factor"] == pytest.approx(1500 * lam.h, rel=1e-6)
    assert r["lpf_load_factor"] == pytest.approx(r["fpf_load_factor"], rel=1e-12)
    assert r["lpf_reason"] == "all plies fibre-failed"


def test_V_PF_2_cross_ply_sequence_and_residual_stiffness(t300):
    t, dm, df = 0.125, 0.2, 0.01
    E1, E2, G12, nu = 181000, 10300, 7170, 0.28

    def Q(E1_, E2_, nu_):
        den = 1 - nu_ * nu_ * E2_ / E1_
        return E1_ / den, E2_ / den, nu_ * E2_ / den

    def strains(Q0, Q90):  # [0/90]s, equal thickness, Nx = 1
        A11 = 2 * t * (Q0[0] + Q90[1]); A22 = 2 * t * (Q0[1] + Q90[0]); A12 = 2 * t * (Q0[2] + Q90[2])
        det = A11 * A22 - A12 ** 2
        return A22 / det, -A12 / det
    Q0 = Q(E1, E2, nu)
    ex, ey = strains(Q0, Q0)
    fpf_ref = 40 / (Q0[1] * ex + Q0[2] * ey)                    # 90-deg plies, sigma2 = Yt
    Q90d = Q(E1, E2 * dm, nu * dm)                              # matrix-discounted 90 plies
    ex2, ey2 = strains(Q0, Q90d)
    lpf_ref = 1500 / (Q0[0] * ex2 + Q0[2] * ey2)                # 0-deg plies, sigma1 = Xt
    lam = lam_of(t300, [0, 90, 90, 0], t)
    r = run(lam, d_matrix=dm, d_fibre=df)
    assert r["fpf_load_factor"] == pytest.approx(fpf_ref, rel=1e-6)
    first = r["steps"][0]
    assert {f["ply"] for f in first["failed"]} == {2, 3} and all(f["mode"] == "MT" for f in first["failed"])
    # residual Ex after matrix discount: Ex = 1/(h a11)
    Ex_ref = 1 / (4 * t * ex2)
    assert first["Ex"] == pytest.approx(Ex_ref, rel=1e-10)
    assert r["lpf_load_factor"] == pytest.approx(lpf_ref, rel=1e-6)
    assert r["lpf_load_factor"] > r["fpf_load_factor"]


def test_progressive_rejects_non_mode_criterion(t300):
    with pytest.raises(ValueError):
        run(lam_of(t300, [0, 90, 90, 0]), crit="tsai_wu")


@pytest.mark.parametrize("crit", ["hashin", "puck", "max_strain"])
def test_progressive_monotone_and_terminates(crit, t300):
    lam = lam_of(t300, [45, -45, 0, 90, 90, 0, -45, 45])
    r = run(lam, crit, N=(1, 0.5, 0.2))
    loads = [s["load_factor"] for s in r["steps"]]
    assert loads == sorted(loads)
    ratios = [s["stiffness_ratio"] for s in r["steps"]]
    assert all(a >= b - 1e-12 for a, b in zip(ratios, ratios[1:]))
    assert r["fpf_load_factor"] is not None and len(r["steps"]) <= 200
