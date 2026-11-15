"""V-HT: hygrothermal loading and environmental estimates. Author: Anwesh Ajitabh Dash."""
import numpy as np
import pytest

from aerolaminate import environment as ENV
from aerolaminate.materials import MissingPropertyError
from conftest import lam_of, make_material


def test_V_HT_1_free_unidirectional_expansion(t300):
    dT = -150.0
    for ang in (0.0, 30.0):
        lam = lam_of(t300, [ang] * 4)
        r = lam.solve((0, 0, 0), (0, 0, 0), dT, 0.5)
        c, s = np.cos(np.radians(ang)), np.sin(np.radians(ang))
        a1, a2 = 0.02e-6 * dT + 0.0 * 0.5, 22.5e-6 * dT + 0.006 * 0.5
        ref = [a1 * c * c + a2 * s * s, a1 * s * s + a2 * c * c, 2 * (a1 - a2) * s * c]
        np.testing.assert_allclose(r.eps0, ref, rtol=1e-10, atol=1e-14)
        np.testing.assert_allclose(r.kappa, 0, atol=1e-14)
        st = lam.ply_state(r)
        np.testing.assert_allclose(st["sigma_xy"], 0, atol=1e-8)


def test_V_HT_2_symmetric_residual_self_equilibrated(t300):
    lam = lam_of(t300, [0, 45, -45, 90, 90, -45, 45, 0])
    r = lam.solve((0, 0, 0), (0, 0, 0), -156.0, 0.0)
    np.testing.assert_allclose(r.kappa, 0, atol=1e-14)
    st = lam.ply_state(r, ("middle",))
    Nres = (st["sigma_xy"][:, 0, :] * np.diff(lam.z)[:, None]).sum(axis=0)
    np.testing.assert_allclose(Nres, 0, atol=1e-8)
    # 90 deg ply transverse residual stress is tensile on cool-down (alpha2 > alpha1)
    assert st["sigma_12"][3, 0, 1] > 0


def test_V_HT_3_unsymmetric_free_warpage_equilibrium(t300):
    lam = lam_of(t300, [0, 90])
    r = lam.solve((0, 0, 0), (0, 0, 0), -100.0, 0.0)
    assert r.kappa[0] == pytest.approx(-r.kappa[1], rel=1e-10)   # [0/90] symmetry
    assert abs(r.kappa[2]) < 1e-14
    # free body: stress resultants vanish (2-point Gauss is exact for linear-in-z stress)
    g = np.array([-1, 1]) / np.sqrt(3)
    N, M = np.zeros(3), np.zeros(3)
    free = lam.free_strains(-100.0, 0.0)
    for k in range(2):
        z0, z1 = lam.z[k], lam.z[k + 1]
        for gp in g:
            z = (z0 + z1) / 2 + gp * (z1 - z0) / 2
            s = lam.Qbar[k] @ (r.eps0 + z * r.kappa - free[k])
            N += s * (z1 - z0) / 2
            M += s * z * (z1 - z0) / 2
    np.testing.assert_allclose(N, 0, atol=1e-9)
    np.testing.assert_allclose(M, 0, atol=1e-10)
    w = ENV.warpage(lam, -100.0, 0.0, 100.0, 100.0)
    assert w["warning"] is not None and w["max_abs_w"] > 0


def test_missing_cte_is_reported_not_assumed(im7):
    lam = lam_of(im7, [0, 90, 90, 0])
    with pytest.raises(MissingPropertyError):
        lam.solve((0, 0, 0), (0, 0, 0), -150.0, 0.0)
    lam.solve((100, 0, 0), (0, 0, 0), 0.0, 0.0)  # mechanical-only analysis still works


def test_chamis_retention_properties():
    assert ENV.chamis_retention(21.0, 0.0, 200.0, 21.0) == pytest.approx(1.0)
    # hand evaluation in deg F
    Tg0, T, T0 = 200 * 1.8 + 32, 120 * 1.8 + 32, 21 * 1.8 + 32
    Tgw = (0.005 * 1.0 - 0.10 * 1.0 + 1.0) * Tg0
    assert ENV.chamis_retention(120.0, 1.0, 200.0, 21.0) == pytest.approx(np.sqrt((Tgw - T) / (Tg0 - T0)), rel=1e-12)
    vals = [ENV.chamis_retention(t, 1.0, 200.0) for t in (21, 60, 100, 140)]
    assert all(a > b for a, b in zip(vals, vals[1:]))
    with pytest.raises(ValueError):
        ENV.chamis_retention(190.0, 1.0, 200.0)   # above wet Tg


def test_knockdown_requires_tg(t300):
    lam = lam_of(t300, [0, 90])
    with pytest.raises(MissingPropertyError):
        ENV.knockdown_factors(lam.plies, 80.0, 1.0)
