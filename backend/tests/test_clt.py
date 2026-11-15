"""V-CLT: Classical Laminate Theory verification. Author: Anwesh Ajitabh Dash."""
import numpy as np
import pytest

from aerolaminate.clt import (Laminate, Ply, SingularLaminateError, LaminateInputError, T_eps, T_sigma, invariants, qbar,
                              reduced_stiffness)
from conftest import lam_of, make_material


def test_V_CLT_1_kaw_reduced_stiffness():
    # Kaw (2006) Example 2.6, T300/5208: Q11 = 181.8, Q12 = 2.897, Q22 = 10.35, Q66 = 7.17 GPa (4 s.f.)
    Q = reduced_stiffness(181000, 10300, 7170, 0.28) / 1000
    np.testing.assert_allclose([Q[0, 0], Q[0, 1], Q[1, 1], Q[2, 2]], [181.8, 2.897, 10.35, 7.17], rtol=5e-4)


def test_V_CLT_2_kaw_transformed_stiffness_60deg():
    # Kaw (2006) Example 2.7: Qbar at 60 deg [GPa]
    Qb = qbar(reduced_stiffness(181000, 10300, 7170, 0.28), 60.0) / 1000
    ref = {(0, 0): 23.65, (0, 1): 32.46, (0, 2): 20.05, (1, 1): 109.4, (1, 2): 54.19, (2, 2): 36.74}
    for (i, j), v in ref.items():
        assert Qb[i, j] == pytest.approx(v, rel=5e-4)
        assert Qb[j, i] == pytest.approx(Qb[i, j], rel=1e-12)


def test_V_CLT_3_qbar_closed_form_and_invariants():
    Q = reduced_stiffness(171420, 9080, 5290, 0.32)
    U1, U2, U3, U4, U5 = invariants(Q)
    for th in np.linspace(-90, 90, 37):
        t = np.radians(th)
        Qb = qbar(Q, th)
        # Tsai-Pagano invariant form (independent closed form)
        ref11 = U1 + U2 * np.cos(2 * t) + U3 * np.cos(4 * t)
        ref22 = U1 - U2 * np.cos(2 * t) + U3 * np.cos(4 * t)
        ref12 = U4 - U3 * np.cos(4 * t)
        ref66 = U5 - U3 * np.cos(4 * t)
        ref16 = U2 / 2 * np.sin(2 * t) + U3 * np.sin(4 * t)
        np.testing.assert_allclose([Qb[0, 0], Qb[1, 1], Qb[0, 1], Qb[2, 2], Qb[0, 2]],
                                   [ref11, ref22, ref12, ref66, ref16], rtol=1e-10, atol=1e-8 * Q[0, 0])
        # Rotational invariants
        assert Qb[0, 0] + Qb[1, 1] + 2 * Qb[0, 1] == pytest.approx(Q[0, 0] + Q[1, 1] + 2 * Q[0, 1], rel=1e-12)
        np.testing.assert_allclose(qbar(Q, th + 180), Qb, atol=1e-8 * Q[0, 0])


def test_transformation_round_trip():
    for th in (0, 17, 45, -60, 90):
        Ts, Te = T_sigma(th), T_eps(th)
        np.testing.assert_allclose(T_sigma(-th) @ Ts, np.eye(3), atol=1e-12)
        np.testing.assert_allclose(T_eps(-th) @ Te, np.eye(3), atol=1e-12)
        # work conjugacy: sigma . eps invariant
        s, e = np.array([3.0, -1.0, 2.0]), np.array([1e-3, 2e-4, -5e-4])
        assert (Ts @ s) @ (Te @ e) == pytest.approx(s @ e, rel=1e-12)


def test_V_CLT_9_isotropic_invariance():
    iso = make_material()
    Q = reduced_stiffness(70000, 70000, 70000 / 2.6, 0.3)
    for th in (0, 13, 45, 77):
        np.testing.assert_allclose(qbar(Q, th), Q, atol=1e-8 * Q[0, 0])
    lam = lam_of(iso, [0, 30, 60], 1.0)
    c = lam.engineering_constants()
    assert c["Ex"] == pytest.approx(70000, rel=1e-12)
    assert c["nuxy"] == pytest.approx(0.3, rel=1e-12)


def test_V_CLT_4_quasi_isotropic(t300):
    lam = lam_of(t300, [0, 45, -45, 90, 90, -45, 45, 0])
    A = lam.A
    assert A[0, 0] == pytest.approx(A[1, 1], rel=1e-12)
    assert A[2, 2] == pytest.approx((A[0, 0] - A[0, 1]) / 2, rel=1e-12)
    assert abs(A[0, 2]) < 1e-10 * A[0, 0] and abs(A[1, 2]) < 1e-10 * A[0, 0]
    cl = lam.classify()
    assert cl["quasi_isotropic_inplane"] and cl["symmetric_stiffness"] and cl["balanced"]
    # In-plane modulus independent of direction
    from aerolaminate.clt import stiffness_vs_orientation
    s = stiffness_vs_orientation(lam, 15)
    np.testing.assert_allclose(s["Ex"], s["Ex"][0], rtol=1e-10)
    # QI modulus from invariants: Ex = (U1^2 - U4^2)/U1
    U1, _, _, U4, _ = invariants(reduced_stiffness(181000, 10300, 7170, 0.28))
    assert lam.engineering_constants()["Ex"] == pytest.approx((U1 ** 2 - U4 ** 2) / U1, rel=1e-10)


def test_V_CLT_5_symmetry_and_antisymmetric_pattern(t300):
    sym = lam_of(t300, [30, -30, 0, 0, -30, 30])
    assert np.abs(sym.B).max() < 1e-9 * np.abs(sym.A).max() * sym.h
    anti = lam_of(t300, [30, -30, 30, -30])
    B = anti.B
    assert abs(B[0, 0]) < 1e-9 and abs(B[1, 1]) < 1e-9 and abs(B[0, 1]) < 1e-9 and abs(B[2, 2]) < 1e-9
    assert abs(B[0, 2]) > 1 and abs(B[1, 2]) > 1
    assert abs(anti.A[0, 2]) < 1e-9 * anti.A[0, 0]   # balanced
    assert abs(anti.D[0, 2]) < 1e-9 * anti.D[0, 0]   # antisymmetric: D16 = D26 = 0
    # z-integration identities: A = sum Qbar t, B for single ply = 0
    one = lam_of(t300, [37], 1.0)
    np.testing.assert_allclose(one.B, 0, atol=1e-9)
    np.testing.assert_allclose(one.D, one.Qbar[0] / 12, rtol=1e-12)


def test_V_CLT_6_unidirectional_constants(t300):
    lam = lam_of(t300, [0] * 6)
    c = lam.engineering_constants()
    assert c["Ex"] == pytest.approx(181000, rel=1e-12)
    assert c["Ey"] == pytest.approx(10300, rel=1e-12)
    assert c["Gxy"] == pytest.approx(7170, rel=1e-12)
    assert c["nuxy"] == pytest.approx(0.28, rel=1e-12)
    assert c["Efx"] == pytest.approx(181000, rel=1e-10)
    # off-axis modulus, Jones (1999) eq. 2.98
    th = np.radians(30)
    c4, s4, cs2 = np.cos(th) ** 4, np.sin(th) ** 4, (np.sin(th) * np.cos(th)) ** 2
    Ex_ref = 1 / (c4 / 181000 + (1 / 7170 - 2 * 0.28 / 181000) * cs2 + s4 / 10300)
    assert lam_of(t300, [30] * 4).engineering_constants()["Ex"] == pytest.approx(Ex_ref, rel=1e-10)


def test_V_CLT_7_round_trip(t300):
    lam = lam_of(t300, [0, 45, 90, -45, 30])  # unsymmetric, unbalanced
    N, M = np.array([120.0, -40, 15]), np.array([3.0, -1.5, 0.7])
    r = lam.solve(N, M)
    back = lam.ABD @ np.concatenate([r.eps0, r.kappa])
    np.testing.assert_allclose(back, np.concatenate([N, M]), rtol=1e-10, atol=1e-10)
    # Stress resultants recomputed from ply stresses (2-point Gauss, exact for linear sigma) equal applied loads
    g = np.array([-1, 1]) / np.sqrt(3)
    Nr, Mr = np.zeros(3), np.zeros(3)
    for k in range(len(lam.plies)):
        z0, z1 = lam.z[k], lam.z[k + 1]
        for gp in g:
            z = (z0 + z1) / 2 + gp * (z1 - z0) / 2
            s = lam.Qbar[k] @ (r.eps0 + z * r.kappa)
            Nr += s * (z1 - z0) / 2
            Mr += s * z * (z1 - z0) / 2
    np.testing.assert_allclose(Nr, N, rtol=1e-10, atol=1e-9)
    np.testing.assert_allclose(Mr, M, rtol=1e-10, atol=1e-9)


def test_V_CLT_8_singular_detection():
    E1, E2 = 100000.0, 1000.0
    bad = make_material("NEAR", E1=E1, E2=E2, G12=500.0, nu12=np.sqrt(E1 / E2) * (1 - 1e-15))
    with pytest.raises((SingularLaminateError, LaminateInputError)):
        lam_of(bad, [0, 0]).solve((1, 0, 0))


def test_ply_stress_transform_consistency(t300):
    lam = lam_of(t300, [0, 45, -45, 90, 90, -45, 45, 0])
    r = lam.solve((100, 20, 5), (0, 0, 0))
    st = lam.ply_state(r)
    for k, p in enumerate(lam.plies):
        s_xy = st["sigma_xy"][k, 0]
        e12 = st["mech_eps_12"][k, 0]
        # material-axis stress from material-axis strain via Q must equal transformed stress
        np.testing.assert_allclose(p.Q() @ e12, st["sigma_12"][k, 0], rtol=1e-10, atol=1e-8)
        np.testing.assert_allclose(T_sigma(p.angle) @ s_xy, st["sigma_12"][k, 0], rtol=1e-10, atol=1e-8)


def test_input_validation(t300):
    from aerolaminate.clt import expand_plies
    with pytest.raises(LaminateInputError):
        expand_plies(lambda m: t300, [], t300)
    with pytest.raises(LaminateInputError):
        expand_plies(lambda m: t300, [{"angle": 200}], t300)
    with pytest.raises(LaminateInputError):
        expand_plies(lambda m: t300, [{"angle": 0, "thickness": -1}], t300)
    pl = expand_plies(lambda m: t300, [{"angle": 0}], t300)
    assert pl[0].thickness == 0.125


def test_areal_mass(t300):
    lam = lam_of(t300, [0] * 8)
    assert lam.areal_mass() == pytest.approx(1600 * 1.0e-3, rel=1e-12)   # 1 mm at 1600 kg/m3
