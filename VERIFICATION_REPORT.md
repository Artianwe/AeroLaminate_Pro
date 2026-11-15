# AeroLaminate Pro — Verification Report

**Author, owner and maintainer:** Anwesh Ajitabh Dash · **Engine version:** 1.0.0 · **Release-verification run:** 2026-10-24

"Verified" in this report means agreement with closed-form analytical solutions, published worked examples or an independent
numerical method, within the stated tolerance. **No result has been validated against physical test data, nothing here is
certification evidence, and the Windows launcher has not been executed on Windows** (see §6).

## 1. Release verification — exact commands and outcomes

All commands were run on Linux x86-64, from the repository root unless stated otherwise. PowerShell 7.4.6 for Linux was used for the
launcher snippet tests (release tarball checked against the published SHA-256).

| # | Command | Outcome |
|---|---|---|
| 1 | `cd backend && .venv/bin/python -m pytest -q` (no PowerShell configured) | **130 passed, 4 skipped** (the skipped tests are the PowerShell-backed launcher tests) |
| 2 | `cd backend && AEROLAMINATE_PWSH=<path>/pwsh .venv/bin/python -m pytest -q` | **134 passed, 0 skipped** |
| 3 | Same suite in fresh venvs from `requirements-dev.txt` on **Python 3.10.22** (NumPy 2.2.6, SciPy 1.15.3) and **3.12.15** (NumPy 2.5.4, SciPy 1.18.1) | 130 passed, 4 skipped on each |
| 4 | `cd frontend && npm test` | **5 passed, 0 failed** (layup notation parser) |
| 5 | `cd frontend && npx tsc --noEmit` | no errors |
| 6 | `cd frontend && npm run build` | compiled successfully (routes `/`, `/report`) |
| 7 | Servers started (`uvicorn app.main:app --host 127.0.0.1 --port 8000`; `next start -p 3000 -H 127.0.0.1`), then `backend/.venv/bin/python tools/smoke_test.py` | **18/18 checks passed**, exit 0. Negative control with an unreachable engine: exit 1 |
| 8 | Playwright walkthroughs (all 10 tabs; baseline pinning; optimiser run; report page; illustrative-data block → demonstration mode → turn off; materials verification column) | no page errors; no console errors apart from the expected HTTP 400 of the blocked request |
| 9 | **Clean-checkout test:** scratch copy → `git init`/commit → `git clone` → fresh venv + `npm ci` → items 2, 4–7 | 77 tracked files, no generated files tracked, `.bat` files checked out with CRLF; **134 passed**, 5 passed, tsc OK, build OK, **smoke 18/18** |

### Smoke-test procedure (any OS, about 1 minute)

1. Start the application (Windows: `START_AEROLAMINATE.bat`; elsewhere: see README "Manual start").
2. Run `backend\.venv\Scripts\python tools\smoke_test.py` (Windows) or `backend/.venv/bin/python tools/smoke_test.py`.
3. Pass criterion: `18/18 checks passed`, exit code 0. The script checks the engine health and attribution, the UI page, the report page,
   the `/api` proxy and the material database. It also checks a closed-form CLT value (QI T300/5208, Ex = 69 675.74 MPa), that illustrative
   data are blocked and a missing IM7/8552 CTE is refused, and that all 10 analysis endpoints respond. It uses only the Python standard
   library and bypasses system proxies for 127.0.0.1.
4. In the browser: open each tab once and confirm that no panel shows "This view could not be rendered".

## 2. Changes in this release cycle (completed and tested)

| Area | Change | Evidence |
|---|---|---|
| Launcher | Port check now uses the .NET listener API (locale-independent, IPv4 and IPv6) instead of `netstat … LISTENING` (state name is localised) | `test_portbusy_snippet_behaviour` (real socket) |
| Launcher | Reuses a running Web UI or API individually (previously "port 3000 in use by another program" when only the UI was left running) | code review; Windows check B6/B7 pending |
| Launcher | HTTP probes bypass the system proxy (Windows PowerShell 5.1 otherwise honours it for 127.0.0.1) | `test_probe_snippet_behaviour` |
| Launcher | Added checks for PowerShell, npm and 64-bit Python; a broken venv is recreated; Node range matches Next.js 15 (`^18.18 \|\| ^19.8 \|\| >=20`); `pushd` (UNC-safe) instead of `cd /d`; `ping` instead of `timeout`; timeout message names the failing service | static lint tests |
| Stop helper | Identifies processes by listening port and command-line signature (`uvicorn app.main:app` / Next.js); never kills foreign processes; works when Windows Terminal owns the windows | PowerShell parse test only (uses Windows-only cmdlets): Windows checks D1–D4 pending |
| Launcher tests | `backend/tests/test_launcher.py`: CRLF/ASCII, label resolution, no parenthesised blocks, `call npm`, no `timeout`/`cd /d`, PowerShell snippets free of `%VAR%` and PowerShell-7-only syntax, PowerShell parse check, behaviour of the probe/port/build-staleness snippets (including a path with spaces, parentheses and `&`) | mutation check: an injected block, `%ERRORLEVEL%`, bare `npm`, `timeout`, a dangling `goto` and LF endings are all detected |
| Materials | Per-property `verification` field (`primary` / `secondary` / `unverified`) and notes; a `verification_log` per record; analyses list the unverified properties used | `test_shipped_verification_annotations`, `test_verification_provenance_reported` |
| Materials | Records with illustrative values (CYCOM 5320-1) are **blocked** in every analysis endpoint unless `options.allow_illustrative` (UI: "Enable demonstration mode") is set | `test_illustrative_material_blocked_by_default` |
| Safeguard | Unit-plausibility warnings (e.g. GPa typed into an MPa field, E2 > E1) | `test_unit_slip_warning`; shipped records produce none |
| **Defect fix** | Parametric ±θ sweep ignored the hot/wet knockdown (varied plies lost stiffness retention; strengths not knocked down). With IM7/8552 at 120 °C it reported RF 2.27 against the correct 1.52 at identical angles (**unconservative**) | regression `test_parametric_reproduces_analysis_under_knockdown` (now identical to 1e-9) |
| Safeguard | Optimiser refuses the hot/wet knockdown (it does not apply it), and flags hybrid or variable-thickness inputs (it uses ply 1) | `test_knockdown_unsupported_modules_refuse` |
| Safeguard | Notch and edge-delamination screens flag the load components and residual states they ignore; buckling flags span/thickness < 20 (Kirchhoff theory unconservative); the buckling label drops to SCREENING when any approximation flag is set | `test_notch_and_delamination_flag_ignored_loads`, `test_thick_plate_flag` |
| Safeguard | UI hides results when an analysis is blocked, shows a STALE RESULTS banner whenever the displayed solution no longer matches the inputs, and keeps a permanent banner while the hot/wet estimate is active | Playwright walkthrough |
| Conventions | Added independent checks: tensor-rotation derivation of T_σ and T_ε, fibre-direction sign under +Nxy, moment/curvature sign and the ply-order convention | `test_safeguards.py` |
| Reproducibility | `requirements.txt` comment records the Python versions actually tested; `requirements-lock.txt` gives the exact versions of the 3.13 run (requires Python ≥ 3.12, from package metadata); `package.json` `engines` | items 3, 9 |

## 3. Shear-buckling coefficient: 9.325 (computed) vs 9.34 (published)

**Investigation.**
1. **Equations.** Energy functional, Ritz integrals and boundary conditions were re-derived. With D16 = D26 = 0 and Nxy = 0, the
   implementation reproduces the closed-form Nx,cr to 1e-9 (V-B-1). Biaxial (k = 2) and uniaxial (k = 4) closed forms are reproduced to 1e-9 (V-B-3).
2. **Convergence.** The Ritz value decreases monotonically with the number of terms: 9.32835 (8×8), 9.32511 (12×12), 9.32467 (16×16), 9.32457 (20×20).
   This is consistent with its upper-bound property.
3. **Independent method.** A finite-difference solution of D∇⁴w + 2Nxy w,xy = 0 with simply supported edges (odd-reflection ghost nodes)
   gives 9.44228 (n = 20), 9.35352 (40), 9.33174 (80) and 9.32632 (160). Richardson extrapolation (h²) gives **9.32448–9.32452**.
4. **Reference assumptions.** 9.34 is quoted to three significant figures in the classical literature (Stein & Neff 1947; Timoshenko & Gere 1961).
   It is consistent with the approximation k ≈ 5.35 + 4(b/a)², which gives 9.35 for a square plate. No primary source giving a more precise value was found
   in this session, so none is cited.

**Conclusion.** Two independent methods agree on k_s ≈ 9.3245 to five significant figures. The implementation is therefore not changed.
The remaining −0.16 % difference from 9.34 reflects the precision of the classical value. The original test (9.34 ± 1 %) is kept
**unchanged**, and a new, much tighter regression test (`test_V_B_2b…`) requires Ritz and the independent FD solution to agree within 5e-4 and the Ritz sequence to decrease monotonically.

## 4. Benchmarks (unchanged from the previous release, all re-run)

| ID | Quantity | Reference | Expected | Computed | Tolerance |
|---|---|---|---|---|---|
| V-CLT-1 | Q11, Q12, Q22, Q66 of T300/5208 [GPa] | Kaw (2006) Ex. 2.6 | 181.8, 2.897, 10.35, 7.17 | 181.811, 2.8969, 10.3462, 7.170 | rtol 5e-4 |
| V-CLT-2 | Q̄ at 60° [GPa] | Kaw (2006) Ex. 2.7 | 23.65, 32.46, 20.05, 109.4, 54.19, 36.74 | 23.647, 32.463, 20.054, 109.379, 54.193, 36.736 | rtol 5e-4 |
| V-CLT-3…9 | Invariants, quasi-isotropy (Ex = 69 675.7 MPa), B = 0, UD constants, round trip, singular detection, isotropic invariance | Analytical | — | — | ≤ 1e-9 |
| V-HT-1…3 | Free expansion, self-equilibrated residual stress, [0/90] free warpage equilibrium | Analytical | — | — | ≤ 1e-8 |
| V-F-1…3 | FI = 1 at strengths (all 7 criteria; LaRC03 calibration points), Tsai-Wu quadratic, residual-aware RF vs brute force | Definitions / hand solutions | — | — | ≤ 1e-6 |
| V-PF-1/2 | UD FPF = LPF = XT·h; [0/90]s FPF 187.139, LPF 379.246 N/mm, post-discount Ex | Hand CLT | — | — | ≤ 1e-6 |
| V-B-1…3 | Closed forms (Nx,cr 2.35972 N/mm for [0/90]2s 500×300), k_s vs 9.34, k = 2 and k = 4 | Jones; Stein & Neff; closed form | — | — | 1e-9 / 1 % / 1e-9 |
| V-B-2b | k_s: Ritz vs independent FD (Richardson) | Independent numerical method | 9.3245 | 9.32457 (Ritz) / 9.32448 (FD) | 5e-4 |
| V-N-1…3 | Isotropic K_T = 3, Kirsch distribution, PSC/ASC limits, orthotropic K_T | Analytical | — | — | ≤ 1e-3 |
| V-IL-1/2 | Parabolic τxz = 1.5Q/h, traction-free surfaces, O'Brien E* = E_lam for identical plies | Beam theory / analytical | — | — | ≤ 1e-9 |
| V-O-1…3 | Optimiser constraints (independently re-evaluated), determinism, Pareto non-dominance | Definitions | — | — | exact |
| V-U-1 | Zero-CoV Monte Carlo = deterministic; sensitivity identities | Limits | — | — | ≤ 1e-9 |

## 5. Material-data verification status

The primary documents could not be opened: the environment's network policy returned HTTP 403 for `hexcel.com`, `ntrs.nasa.gov`,
`wichita.edu` (NCAMP), `energy.ornl.gov`, `compositeenvisions.com` and `reports.aerade.cranfield.ac.uk`. Only web-search extracts
were available, and these are treated as secondary evidence. No value was changed on the basis of the search. The outcome is recorded per property in
`backend/aerolaminate/data/materials.json` (`verification`, `verification_note`):

| Record | Primary-verified | Secondary match | Unverified | Notes |
|---|---|---|---|---|
| IM7/8552 | 0 | E1, E2, G12, ν12, Yt, Xc, S12, G_Ic (arXiv:2607.07977 Table 1); t_ply, Vf (Hexcel datasheet extracts) | Xt (secondary lists 2326 vs 2323.5 MPa), Yc (200 vs 199.8 MPa), G_IIc, density, Tg | **α1, α2 not entered.** The only lead (a "typical 8552 composite" CTE of −0.64 ppm/°C, direction unstated) is insufficient. Thermal analysis stays refused |
| AS4/3501-6 | 0 | — | all | WWFE-I citation/DOI confirmed, but no accessible source confirms the values. Other AS4/3501-6 sets differ (E1 138.9–148.9 GPa) |
| CYCOM 5320-1/T650 | 0 | — | all (illustrative) | **Blocked by default.** NMS 532/5 acceptance limits (E1 126.8–150.1 GPa, strength ≥ 1905.6 MPa) are recorded as a cross-check only |
| T300/5208 | 0 | E1, E2, G12 and the stress-based strengths (an uncited table) | ν12, α, β, density, t_ply, Vf | That table also lists a second strength set (1448/1448/44.8/248/62.1 MPa) |
| E-glass/epoxy | 0 | — | all | Textbook values |

To complete this item: allow those hosts in the environment's network settings (or obtain the PDFs), then compare each value and set
`verification: "primary"` with the page/table reference.

## 6. Not verified / remaining limitations

**Windows (requires execution on Windows; checklist: `WINDOWS_VERIFICATION_CHECKLIST.md`, all items pending):**
- The cmd.exe control flow of `START_AEROLAMINATE.bat`/`STOP_AEROLAMINATE.bat` has never been executed.
- Windows PowerShell 5.1 behaviour. The snippets were parsed and run with PowerShell 7.4 on Linux, and checked statically for 7-only syntax.
- `Get-NetTCPConnection` / `Get-CimInstance` in the STOP helper. These are Windows-only and were parse-checked only.
- Console windows under conhost vs Windows Terminal, browser opening, firewall/antivirus behaviour, UNC paths, non-English locales,
  corporate proxies, and Windows wheel availability for the tested Python versions.

**Engineering:**
- No experimental validation of any failure, progressive-failure, notched, delamination, fatigue or hot/wet prediction.
- Material values are not primary-verified (§5). CYCOM 5320-1 results are demonstration-only.
- The shear-buckling reference value is classical (3 s.f.). §3 documents the independent check.
- Screening modules (progressive failure, notched strength, interlaminar, edge delamination, fatigue, Chamis hot/wet) remain screening
  methods with their stated assumptions. 3-D stresses, delamination growth, impact/CAI and postbuckling are out of scope (roadmap).
