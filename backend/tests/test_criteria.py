"""V-F: failure criteria and reserve factors. Author: Anwesh Ajitabh Dash."""
import numpy as np
import pytest

from aerolaminate import criteria as C
from aerolaminate import strength as S
from aerolaminate.clt import Ply
from conftest import lam_of


def ply_set(mat, t=0.125):
    return C.build_strengths([Ply(mat, 0.0, t)])


def fi(name, St, s, opt=None):
    s = np.asarray(s, float).reshape(1, 1, 3)
    modes = C.evaluate(name, s[..., 0], s[..., 1], s[..., 2], St, opt or C.CriterionOptions())
    return float(C.governing(modes)[0][0, 0])


@pytest.mark.parametrize("name", ["max_stress", "max_strain", "tsai_hill", "tsai_wu", "hashin", "puck"])
def test_V_F_1_uniaxial_strength_points(name, t300):
    St = ply_set(t300)
    X, Xc, Y, Yc, S12 = 1500, 1500, 40, 246, 68
    for s in ([X, 0, 0], [-Xc, 0, 0], [0, Y, 0], [0, -Yc, 0], [0, 0, S12], [0, 0, -S12]):
        assert fi(name, St, s) == pytest.approx(1.0, abs=1e-9), (name, s)


def test_V_F_1_larc03_calibration_points(im7):
    St = ply_set(im7)
    opt = C.CriterionOptions(larc_insitu=False)
    Xt, Xc, Yt, Yc, SL = 2323.5, 1200.1, 62.3, 199.8, 92.3
    assert fi("larc03", St, [Xt, 0, 0], opt) == pytest.approx(1.0, abs=1e-9)    # strain-based, derived eps1t = Xt/E1
    assert fi("larc03", St, [0, Yt, 0], opt) == pytest.approx(1.0, abs=1e-9)
    assert fi("larc03", St, [0, 0, SL], opt) == pytest.approx(1.0, abs=1e-9)
    # V-F-4: pure transverse compression fails at Yc on the alpha0 = 53 deg plane (by construction of S_T, eta_T)
    assert fi("larc03", St, [0, -Yc, 0], opt) == pytest.approx(1.0, abs=1e-9)
    # kink-band: phi_C is the exact root, so pure longitudinal compression fails at Xc
    assert fi("larc03", St, [-Xc, 0, 0], opt) == pytest.approx(1.0, abs=1e-9)


def test_larc03_insitu_increases_matrix_strength(im7):
    plies = [Ply(im7, a, 0.131) for a in (0, 90, 90, 0)]
    off = C.build_strengths(plies)
    on = C.build_strengths(plies)
    P_on = C._larc_setup(on, C.CriterionOptions(larc_insitu=True))
    P_off = C._larc_setup(off, C.CriterionOptions(larc_insitu=False))
    assert np.all(P_on["YTis"] >= P_off["YTis"]) and np.all(P_on["SLis"] >= P_off["SLis"])
    # embedded 90 block (2 x 0.131 mm): thin-ply formula sqrt(8 GIc / (pi t Lambda22))
    E1, E2, nu12 = 171420, 9080, 0.32
    lam22 = 2 * (1 / E2 - (nu12 * E2 / E1) ** 2 / E1)
    yt_thin = np.sqrt(8 * 0.2774 / (np.pi * 0.262 * lam22))
    assert P_on["YTis"][1, 0] == pytest.approx(max(yt_thin, 1.12 * np.sqrt(2) * 62.3), rel=1e-12)


def test_larc03_unavailable_without_toughness(t300):
    with pytest.raises(C.CriterionUnavailable) as e:
        fi("larc03", ply_set(t300), [10, 0, 0])
    assert "GIc" in str(e.value)


def test_V_F_2_tsai_wu_biaxial_hand_solution(t300):
    St = ply_set(t300)
    Xt, Xc, Yt, Yc, Ss = 1500, 1500, 40, 246, 68
    F1, F2 = 1 / Xt - 1 / Xc, 1 / Yt - 1 / Yc
    F11, F22, F66 = 1 / (Xt * Xc), 1 / (Yt * Yc), 1 / Ss ** 2
    F12 = -0.5 * np.sqrt(F11 * F22)
    d = np.array([200.0, 10.0, 30.0])
    a = F11 * d[0] ** 2 + F22 * d[1] ** 2 + F66 * d[2] ** 2 + 2 * F12 * d[0] * d[1]
    b = F1 * d[0] + F2 * d[1]
    lam_ref = max(np.roots([a, b, -1]).real)
    rf = S.reserve_factor("tsai_wu", np.zeros((1, 1, 3)), d.reshape(1, 1, 3), St, C.CriterionOptions())
    assert rf[0, 0] == pytest.approx(lam_ref, rel=1e-12)


def test_tsai_hill_hand_value(t300):
    St = ply_set(t300)
    s = [500.0, 20.0, 30.0]
    ref = (500 / 1500) ** 2 - 500 * 20 / 1500 ** 2 + (20 / 40) ** 2 + (30 / 68) ** 2
    assert fi("tsai_hill", St, s) == pytest.approx(ref, rel=1e-12)


def test_hashin_modes_hand_values(t300):
    St = ply_set(t300)
    s1, s2, t = 900.0, -100.0, 40.0
    s = np.array([[s1]]), np.array([[s2]]), np.array([[t]])
    m = C.hashin(*s, St, C.CriterionOptions())
    assert m["FT"][0, 0] == pytest.approx((s1 / 1500) ** 2 + (t / 68) ** 2, rel=1e-12)
    ST = 246 / 2
    assert m["MC"][0, 0] == pytest.approx((s2 / (2 * ST)) ** 2 + ((246 / (2 * ST)) ** 2 - 1) * s2 / 246 + (t / 68) ** 2, rel=1e-12)
    assert m["MT"][0, 0] == 0 and m["FC"][0, 0] == 0


def test_puck_mode_regions(t300):
    St = ply_set(t300)
    opt = C.CriterionOptions()
    ppt, ppc, RA, pcc, t21c = C.puck_parameters(St, opt)
    # mode B/C boundary point (sigma2 = -RA, tau = tau21c) evaluates to 1 in both expressions
    s2, t = -float(RA[0, 0]), float(t21c[0, 0])
    m = C.puck(np.array([[0.0]]), np.array([[s2]]), np.array([[t]]), St, opt)
    assert m["IFF-B"][0, 0] == pytest.approx(1.0, rel=1e-9)
    fC = ((t / (2 * (1 + pcc[0, 0]) * 68)) ** 2 + (s2 / 246) ** 2) * 246 / (-s2)
    assert fC == pytest.approx(1.0, rel=1e-9)
    # moderate transverse compression raises shear capacity above S (physical feature of Puck IFF mode B)
    rf_shear = S.reserve_factor("puck", np.array([[[0, -60.0, 0]]]), np.array([[[0, 0, 1.0]]]), St, opt)
    assert rf_shear[0, 0] > 68


@pytest.mark.parametrize("name", list(C.CRITERIA))
def test_V_F_3_residual_rf_matches_bruteforce(name, im7):
    St = ply_set(im7)
    opt = C.CriterionOptions()
    sr = np.array([[[50.0, 25.0, -10.0]]])
    sm = np.array([[[800.0, 8.0, 20.0]]])
    rf = float(S.reserve_factor(name, sr, sm, St, opt)[0, 0])
    lo, hi = 0.0, 1e3
    f = lambda lam: fi(name, St, (sr + lam * sm)[0, 0], opt)
    # independent: march to first crossing then bisect
    grid = np.linspace(0, 10, 20001)
    vals = np.array([f(x) for x in grid])
    i = int(np.argmax(vals >= 1))
    lo, hi = grid[i - 1], grid[i]
    for _ in range(80):
        mid = (lo + hi) / 2
        lo, hi = (lo, mid) if f(mid) >= 1 else (mid, hi)
    assert rf == pytest.approx(hi, rel=1e-6)
    assert f(rf) == pytest.approx(1.0, abs=1e-6)


def test_rf_zero_when_residual_already_fails(t300):
    St = ply_set(t300)
    rf = S.reserve_factor("max_stress", np.array([[[0, 50.0, 0]]]), np.array([[[1.0, 0, 0]]]), St, C.CriterionOptions())
    assert rf[0, 0] == 0.0


def test_rf_infinite_when_no_failure_along_ray(t300):
    St = ply_set(t300)
    rf = S.reserve_factor("max_stress", np.zeros((1, 1, 3)), np.zeros((1, 1, 3)), St, C.CriterionOptions())
    assert np.isinf(rf[0, 0])


def test_tsai_wu_F12_range_rejected(t300):
    with pytest.raises(C.CriterionUnavailable):
        fi("tsai_wu", ply_set(t300), [1, 0, 0], C.CriterionOptions(tsai_wu_F12_star=1.2))


def test_laminate_fpf_cross_ply_hand(t300):
    """[0/90]s under Nx: 90-deg plies reach Yt (max stress). Hand CLT with closed-form A of a cross-ply."""
    t = 0.125
    E1, E2, G12, nu = 181000, 10300, 7170, 0.28
    den = 1 - nu * nu * E2 / E1
    Q11, Q22, Q12 = E1 / den, E2 / den, nu * E2 / den
    A11 = A22 = 2 * t * (Q11 + Q22)
    A12 = 4 * t * Q12
    ex = A22 / (A11 * A22 - A12 ** 2)
    ey = -A12 / (A11 * A22 - A12 ** 2)
    s2_90 = Q22 * ex + Q12 * ey
    lam = lam_of(t300, [0, 90, 90, 0], t)
    St = C.build_strengths(lam.plies)
    rf = S.laminate_rf(lam, St, (1, 0, 0), (0, 0, 0), 0, 0, "max_stress", C.CriterionOptions())
    assert rf == pytest.approx(40 / s2_90, rel=1e-10)


def test_envelope_contains_uniaxial_points(t300):
    St = ply_set(t300)
    env = S.ply_envelope(St, "max_stress", C.CriterionOptions(), "s1s2", 0.0, n=5)  # angles 0, 90, 180, 270, 360
    np.testing.assert_allclose(env["x"][0], 1500, rtol=1e-9)
    np.testing.assert_allclose(env["y"][1], 40, rtol=1e-9)
    np.testing.assert_allclose(env["x"][2], -1500, rtol=1e-9)
    np.testing.assert_allclose(env["y"][3], -246, rtol=1e-9)
