# AeroLaminate Pro

**Composite laminate analysis and optimisation workspace**
Author, owner and maintainer: **Anwesh Ajitabh Dash**

AeroLaminate Pro is a desktop-local engineering application for the analysis of flat, thin, fibre-reinforced polymer laminates.
It has a Python calculation engine (NumPy/SciPy, served by FastAPI) and a Next.js/React workspace in which plots refresh
automatically whenever a validated input changes.

> **Scope and status.** The application is an engineering analysis and screening tool. It is **not** a certification tool,
> and its outputs are not design allowables. Failure indices are deterministic stress measures, not probabilities of failure. Every
> plot carries a label: **CALCULATED** (direct solver output, verified analytically), **SCREENING** (an established approximation with
> stated assumptions), **ESTIMATE** (an empirical relation), **ILLUSTRATIVE DATA** (placeholder material values) or **UNAVAILABLE** (missing inputs).

---

## Quick start (Windows)

1. Install **64-bit Python 3.10+** (python.org, tick *Add python.exe to PATH*) and **Node.js 18.18+ LTS** (nodejs.org, with npm).
   Windows PowerShell 5.1 (built into Windows 10/11) is used for the startup checks.
2. Double-click **`START_AEROLAMINATE.bat`**.
   The first run creates `backend\.venv`, installs the Python and npm dependencies, and builds the UI, which takes a few minutes. Later runs reuse all of it,
   rebuild the UI only when its sources change, reuse either server if it is already running, recreate a broken venv, and refuse
   to start when a port is used by an unrelated program.
3. The browser opens at <http://127.0.0.1:3000>. The engine runs at <http://127.0.0.1:8000> (API docs at `/docs`).
4. **To stop:** close the two console windows titled *AeroLaminate Pro – API* and *AeroLaminate Pro – Web UI* (or press Ctrl+C in each),
   or run `STOP_AEROLAMINATE.bat`. That script stops only processes whose command line identifies them as the AeroLaminate Pro servers.
5. **Check an installation:** `backend\.venv\Scripts\python tools\smoke_test.py` should report `18/18 checks passed`.

> **Windows status:** the launchers are covered by automated lint and PowerShell-snippet tests, but they have **not yet been executed on
> Windows**. Use `WINDOWS_VERIFICATION_CHECKLIST.md` for the first Windows run.

Docker and WSL are not required. Both servers bind to 127.0.0.1 only.

### Manual start (any OS)

```bash
# engine
cd backend
python -m venv .venv
.venv/bin/pip install -r requirements.txt          # Windows: .venv\Scripts\pip
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
# UI (second terminal)
cd frontend
npm ci
npm run build && npm run start                     # or: npm run dev
```

The UI proxies `/api/*` to `http://127.0.0.1:8000`. Set `AEROLAMINATE_API` to use another engine address.

## Capabilities

| Area | What it does | Classification |
|---|---|---|
| Classical Laminate Theory | [Q], [Q̄], [A], [B], [D], [ABD] and its inverse; mid-plane strains and curvatures; ply strains/stresses in x-y and 1-2 axes at the bottom, middle and top of each ply; arbitrary angles, thicknesses and per-ply materials (hybrids) | Calculated |
| Laminate properties | Membrane and flexural engineering constants, areal mass, symmetry/balance/quasi-isotropy classification, coupling indicators (extension–shear, extension–bending, Nemeth δ/γ), scaled condition number with explicit singular-laminate detection | Calculated |
| Failure criteria | Maximum stress, maximum strain, Tsai-Hill, Tsai-Wu, Hashin 1980 (4 modes), Puck 2D (IFF modes A/B/C), LaRC03 2D with in-situ strengths. A criterion whose required parameters are missing reports *unavailable* | Calculated |
| Margins | Reserve factor (load multiplier) with residual hygrothermal stress held constant, margin of safety MS = RF/FoS − 1, critical ply/position/mode | Calculated |
| Envelopes | Ply envelopes in σ1–σ2, σ2–τ12, σ1–τ12; laminate first-ply-failure envelopes in Nx–Ny, Nx–Nxy, Ny–Nxy with applied-load markers | Calculated |
| Progressive failure | Ply-discount FPF → LPF with mode-dependent degradation, equilibrium iterations, residual stiffness, damage map, FI-versus-load | Screening |
| Hygrothermal | ΔT/ΔC loads, cure residual stresses, temperature/moisture sweeps, linear warpage of unsymmetric laminates, Chamis hot/wet retention | Calculated / Estimate |
| Stability | Rayleigh–Ritz buckling of simply supported plates under Nx, Ny, Nxy with D16/D26, mode shape, convergence check, λ versus aspect ratio | Calculated |
| Notched strength | Lekhnitskii K_T∞, Konish–Whitney stress distribution, Whitney–Nuismer point/average stress criteria, hole-size effect | Screening (needs calibrated d0/a0) |
| Interlaminar | Equilibrium-based transverse-shear stress recovery, interface checks, free-edge mismatch indicators, O'Brien edge-delamination G | Screening |
| Uncertainty | Monte Carlo over property CoVs (RF distribution, percentiles, Wilson interval), normalised sensitivities (tornado), ±θ parametric sweeps | Screening |
| Fatigue | User S-N curve + Palmgren–Miner block spectrum. No fatigue data are shipped | Screening |
| Optimisation | Constrained GA (symmetry, balance, ply count, 10 % rule, ≤ n consecutive, ±45 surfaces, RF, stiffness, mass, buckling) with weighted objectives, Pareto archive, ranked candidates with reasoning, comparison with the current design | Heuristic |
| Workflow | Editable ply table and layup notation (`[0/±45/90]s`, `[45/-45/0_2]2s`, `[0/90~]s`), material editor with per-property provenance, baseline pinning and overlay, project save/open (JSON), browser autosave, PNG/SVG/CSV export of every plot, ply-results CSV, printable report | — |

## Material database

| Record | Data status |
|---|---|
| IM7/8552 | Literature lamina set (Camanho, Maimí & Dávila 2007) incl. G_Ic, G_IIc. Ply thickness from the Hexcel datasheet. **No traceable CTE**, so thermal analysis reports *unavailable* until the user enters values |
| AS4/3501-6 | WWFE-I lamina data (Soden, Hinton & Kaddour 1998), transcribed, pending verification against the original. Density and ply thickness estimated |
| CYCOM 5320-1 / T650-35 | **Illustrative placeholders only — analyses are blocked** unless *demonstration mode* is enabled explicitly. NCAMP data exist but could not be extracted. Ply thickness and Vf calculated from FAW and resin content |
| T300/5208, E-glass/epoxy | Textbook values (Tsai & Hahn 1980; Kaw 2006) used in verification |

Every property stores value, unit, status (`datasheet`, `literature`, `calculated`, `estimated`, `illustrative`, `unavailable`), source and notes,
plus a **verification level**: `primary` (checked against the primary document), `secondary` (matched in an independent secondary source)
or `unverified`. **No shipped value is currently primary-verified**, because the primary PDFs could not be retrieved (see `VERIFICATION_REPORT.md` §5). Each analysis
lists the unverified properties it used, and warns about implausible values that suggest a unit slip (e.g. GPa typed into an MPa field).
The engine never substitutes a missing property silently. The only fallback is the explicitly flagged linear-elastic derivation of ultimate
strains (ε = X/E). Shipped records are read-only. Edits apply to the project, or are saved as user records in `backend/user_data/`.

## Conventions

Units N–mm–MPa (moduli shown in GPa); z is measured upward from the mid-plane, and ply 1 is at the bottom (z = −h/2). θ is measured counter-clockwise from +x to the fibre
axis, viewed from +z. Engineering shear strain is used, and tension is positive. Full details are in `SYSTEM_ENGINEERING_SPEC.md` §2–3.

## Project structure

```
START_AEROLAMINATE.bat / STOP_AEROLAMINATE.bat   Windows launcher and stop helper
RESEARCH_AND_GAP_ANALYSIS.md                     literature review, gap analysis, roadmap, references
SYSTEM_ENGINEERING_SPEC.md                       architecture, equations, conventions, verification criteria
VERIFICATION_REPORT.md                           exact test results, benchmarks, known limitations
backend/aerolaminate/                            calculation engine (independently importable and testable)
backend/app/main.py                              FastAPI REST layer
backend/tests/                                   pytest verification suite (134 tests, incl. launcher checks)
backend/requirements*.txt                        runtime ranges, dev/test extras, exact lockfile of the verified run
tools/smoke_test.py                              end-to-end check of a running installation (stdlib only)
WINDOWS_VERIFICATION_CHECKLIST.md                manual checks still to be executed on Windows
frontend/src/                                    Next.js workspace (components, tabs, report page)
```

## Verification

```bash
cd backend && python -m pytest          # 134 tests (4 launcher tests need PowerShell: on Windows it is found automatically,
                                        #  elsewhere set AEROLAMINATE_PWSH=/path/to/pwsh, otherwise they are skipped)
cd frontend && npm test && npx tsc --noEmit && npm run build
python tools/smoke_test.py              # against a running installation
```
The tests check closed-form solutions, published worked examples and independent numerical methods (Kaw 2006, Jones 1999,
Stein & Neff 1947, Whitney & Nuismer 1974, Dávila & Camanho 2003, and others), plus the engineering safeguards and the launcher rules.
The backend suite was also run on Python 3.10 and 3.12. `VERIFICATION_REPORT.md` lists the exact commands and outcomes, and **what was not verified**:
there is no test-data validation, no primary-verified material values, and no execution of the Windows launcher on Windows.

## Limitations (summary)

CLT does not resolve σz, τxz or τyz, free-edge stresses, impact damage or postbuckling. The interlaminar, notched, progressive and fatigue
modules are screening methods, each with its stated assumptions. 3-D criteria (LaRC04/05), Cuntze FMC, VCCT/cohesive-zone delamination growth,
CAI, bearing/bypass, ply drops, sandwich and curved panels are **roadmap items** (see `RESEARCH_AND_GAP_ANALYSIS.md` §8). They need an external
solver or test data and are not implemented.

## Troubleshooting

| Symptom | Fix |
|---|---|
| "Python 3.10 or newer was not found" | Install Python from python.org with *Add to PATH*; reopen the launcher |
| "Port 8000/3000 is used by another program" | Close that program, or run `STOP_AEROLAMINATE.bat` if an earlier session is still open |
| pip/npm failures behind a corporate proxy | Configure `HTTPS_PROXY` (pip) and `npm config set proxy …`, then relaunch |
| Clean reinstall | Delete `backend\.venv` and/or `frontend\node_modules` and `frontend\.next`, then relaunch |
| "Cannot reach the analysis engine …" | The page retries every 3 s and recovers by itself once the engine answers. If it persists, read the *AeroLaminate Pro – API* window. `WinError 10013` means Windows reserved port 8000 (Hyper-V/WSL/Docker): check `netsh interface ipv4 show excludedportrange protocol=tcp`, then restart Windows or run `net stop winnat` / `net start winnat` as administrator. Also open <http://127.0.0.1:8000/api/health> directly |
| "… engine is running … but the web UI's /api proxy cannot reach it" | Run `STOP_AEROLAMINATE.bat`, then start again |
| "has no value for 'alpha1'" | The selected material has no traceable CTE. Enter one in the Materials tab (with its source) or set ΔT = 0 |
| "Analysis blocked … ILLUSTRATIVE" | The record contains placeholder values. Enter verified data, or click *Enable demonstration mode* to view workflow-only results |
| STALE RESULTS banner | The current inputs could not be solved; the views show the last valid solution until the error is fixed |

## Attribution and copyright

AeroLaminate Pro — Copyright © 2026 **Anwesh Ajitabh Dash**. Author, owner and maintainer. All rights reserved unless the owner
adds a licence file. Cited methods and data belong to their respective authors and organisations (see `RESEARCH_AND_GAP_ANALYSIS.md` §10).
No aerospace certification is claimed.
