"""V-B, V-N, V-IL: buckling, open-hole and interlaminar screening. Author: Anwesh Ajitabh Dash."""
import numpy as np
import pytest

from aerolaminate import buckling as BK
from aerolaminate import interlaminar as IL
from aerolaminate import notched as NT
from conftest import lam_of, make_material

ISO = make_material("ISO", E1=70000.0, nu12=0.3)


def iso_plate(h=2.0):
    lam = lam_of(ISO, [0, 0, 0, 0], h / 4)
    D = 70000 * h ** 3 / (12 * (1 - 0.09))
    return lam, D


def test_V_B_1_specially_orthotropic_closed_form(t300):
    lam = lam_of(t300, [0, 90, 0, 90, 90, 0, 90, 0])
    for a, b in ((500, 300), (300, 300), (900, 200)):
        r = BK.buckling(lam, a, b, -1.0, 0, 0, terms=10)
        assert r["closed_form_check"]["ritz_Ncr"] == pytest.approx(r["closed_form_check"]["Ncr"], rel=1e-9)


def test_V_B_2_isotropic_square_shear():
    lam, D = iso_plate()
    b = 300.0
    r = BK.buckling(lam, b, b, 0, 0, 1.0, terms=12)
    k = r["load_factor"] * b ** 2 / (np.pi ** 2 * D)
    assert k == pytest.approx(9.34, rel=0.01)   # Stein & Neff (1947); Timoshenko & Gere (1961)
    # shear buckling is sign-independent for an isotropic plate
    r2 = BK.buckling(lam, b, b, 0, 0, -1.0, terms=12)
    assert r2["load_factor"] == pytest.approx(r["load_factor"], rel=1e-9)


def test_V_B_3_isotropic_biaxial_and_uniaxial():
    lam, D = iso_plate()
    b = 250.0
    r = BK.buckling(lam, b, b, -1.0, -1.0, 0, terms=6)
    assert r["load_factor"] == pytest.approx(2 * np.pi ** 2 * D / b ** 2, rel=1e-9)
    r = BK.buckling(lam, b, b, -1.0, 0, 0, terms=6)
    assert r["load_factor"] == pytest.approx(4 * np.pi ** 2 * D / b ** 2, rel=1e-9)   # k = 4


def test_buckling_tension_no_buckling():
    lam, _ = iso_plate()
    r = BK.buckling(lam, 200, 200, 10.0, 5.0, 0, terms=4)
    assert r["load_factor"] is None


def test_buckling_anisotropy_lowers_load(t300):
    # +-45 laminate with D16, D26: Ritz value must not exceed the value obtained by dropping D16/D26 (upper bound property
    # holds for the full model; dropping coupling is unconservative per Nemeth 1986)
    lam = lam_of(t300, [45, -45, 45, -45, -45, 45, -45, 45])
    full = BK.buckling(lam, 400, 400, -1.0, 0, 0, terms=12)["load_factor"]
    D = lam.D.copy(); D[0, 2] = D[2, 0] = D[1, 2] = D[2, 1] = 0
    ortho, _, _ = BK.ritz(D, 400, 400, -1.0, 0, 0, 12, 12)
    assert full < ortho


def test_V_N_1_isotropic_kt():
    assert NT.kt_orthotropic(70000, 70000, 70000 / 2.6, 0.3) == pytest.approx(3.0, rel=1e-12)


def test_V_N_2_psc_kirsch():
    R = 3.0
    for d0 in (0.5, 1.0, 2.0):
        xi = R / (R + d0)
        kirsch = 1 + xi ** 2 / 2 + 3 * xi ** 4 / 2           # sigma_y(x)/sigma for an isotropic infinite plate
        assert NT.psc_ratio(3.0, R, d0) == pytest.approx(1 / kirsch, rel=1e-12)
        assert NT.stress_distribution(3.0, R, np.array([R + d0]))[0] == pytest.approx(kirsch, rel=1e-12)
    assert NT.stress_distribution(5.1, R, np.array([R]))[0] == pytest.approx(5.1, rel=1e-12)


def test_V_N_3_limits():
    for KT in (3.0, 4.5, 6.0):
        assert NT.psc_ratio(KT, 3.0, 1e-6) == pytest.approx(1 / KT, rel=1e-3)
        assert NT.asc_ratio(KT, 3.0, 1e-6) == pytest.approx(1 / KT, rel=1e-3)
        assert NT.psc_ratio(KT, 3.0, 1e6) == pytest.approx(1.0, rel=1e-3)
        assert NT.asc_ratio(KT, 3.0, 1e6) == pytest.approx(1.0, rel=1e-3)


def test_open_hole_unidirectional_kt(t300):
    lam = lam_of(t300, [0] * 8)
    r = NT.open_hole(lam, 3.0, 1.0, 4.0, 1000.0, "test")
    ref = 1 + np.sqrt(2 * (np.sqrt(181000 / 10300) - 0.28) + 181000 / 7170)
    assert r["KT_inf"] == pytest.approx(ref, rel=1e-10)
    assert NT.finite_width_factor(1.0, 1e9) == pytest.approx(1.0, rel=1e-6)


def test_V_IL_1_homogeneous_parabolic_shear():
    lam, _ = iso_plate(h=4.0)
    Q = 50.0
    r = IL.transverse_shear(lam, Q, 0.0, pts_per_ply=21)
    assert r["max_abs"] == pytest.approx(1.5 * Q / lam.h, rel=1e-10)
    assert r["top_surface_residual"] < 1e-10
    z = np.array(r["z"]); tau = np.array(r["tau_xz"])
    np.testing.assert_allclose(tau, 1.5 * Q / lam.h * (1 - 4 * z ** 2 / lam.h ** 2), atol=1e-10)


def test_transverse_shear_laminate_traction_free(t300):
    lam = lam_of(t300, [0, 45, -45, 90, 90, -45, 45, 0])
    r = IL.transverse_shear(lam, 20.0, 10.0)
    assert r["top_surface_residual"] < 1e-9
    assert abs(r["tau_xz"][0]) < 1e-12 and abs(r["tau_yz"][0]) < 1e-12


def test_V_IL_2_obrien_zero_for_identical_plies(t300):
    lam = lam_of(t300, [0] * 8)
    r = IL.edge_delamination(lam, [2])
    assert abs(r["E_lam"] - r["E_star"]) < 1e-9 * r["E_lam"]


def test_obrien_positive_for_mismatched_layup(t300):
    lam = lam_of(t300, [30, -30, 30, -30, 90, 90, -30, 30, -30, 30])
    r = IL.edge_delamination(lam, [4])  # -30/90 interface (classic O'Brien case family)
    assert r["E_star"] < r["E_lam"]
    assert r["onset_strain"] is None   # no GIc for T300/5208 in the database


def test_obrien_requires_symmetric(t300):
    with pytest.raises(ValueError):
        IL.edge_delamination(lam_of(t300, [0, 90, 45]), [1])


def test_free_edge_indicator_values(t300):
    lam = lam_of(t300, [0, 90, 90, 0])
    r = IL.free_edge_indicators(lam)
    assert r["ply_nu_xy"][0] == pytest.approx(0.28, rel=1e-12)
    assert r["ply_nu_xy"][1] == pytest.approx(0.28 * 10300 / 181000, rel=1e-12)
    assert all(abs(e) < 1e-12 for e in r["ply_eta_xy_x"])


def _fd_shear_k(n: int) -> float:
    """Independent finite-difference solution (test-only) of D lap^2 w + 2 Nxy w_xy = 0 on a unit SS square plate.
    Interior nodes only; w = 0 and w_nn = 0 on the edges are satisfied by odd reflection, so the squared 5-point
    Laplacian is the SS biharmonic. Returns k_s = Nxy_cr b^2 / (pi^2 D) with D = 1."""
    import scipy.sparse as sp
    import scipy.sparse.linalg as sla
    h = 1.0 / n
    m = n - 1
    I = sp.identity(m, format="csr")
    D2 = sp.diags([1.0, -2.0, 1.0], [-1, 0, 1], shape=(m, m)) / h ** 2
    D1 = sp.diags([-1.0, 1.0], [-1, 1], shape=(m, m)) / (2 * h)
    L = sp.kron(I, D2) + sp.kron(D2, I)
    K = (L @ L).tocsc()
    G = (2 * sp.kron(D1, D1)).tocsc()
    solve = sla.factorized(K)
    op = sla.LinearOperator(K.shape, matvec=lambda x: solve(-(G @ x)))
    mu = sla.eigs(op, k=4, which="LR", return_eigenvectors=False).real
    return 1.0 / mu.max() / np.pi ** 2


def test_V_B_2b_shear_coefficient_independent_fd_and_upper_bound():
    """The classical 9.34 is a 3-significant-figure value from approximate solutions. Two independent methods
    (Ritz sine series, upper bound; finite differences with Richardson h^2 extrapolation) converge to 9.3245."""
    lam, D = iso_plate()
    b = 300.0
    ks = [BK.buckling(lam, b, b, 0, 0, 1.0, terms=t)["load_factor"] * b ** 2 / (np.pi ** 2 * D) for t in (8, 12, 16, 20)]
    assert all(x > y for x, y in zip(ks, ks[1:])), "Ritz must decrease monotonically (upper-bound property)"
    fd = (4 * _fd_shear_k(80) - _fd_shear_k(40)) / 3
    assert ks[-1] == pytest.approx(fd, rel=5e-4)
    assert fd == pytest.approx(9.3245, abs=2e-3)
