# AeroLaminate Pro — System Engineering Specification

**Author, owner and maintainer:** Anwesh Ajitabh Dash · **Spec version:** 1.0

## 1. Architecture

```
AeroLaminate Pro
├── backend/                     Python 3.10+  (NumPy, SciPy, FastAPI, Pydantic v2)
│   ├── aerolaminate/            Pure calculation engine; no web dependencies; independently testable
│   │   ├── materials.py         Material model with per-property provenance; JSON database I/O
│   │   ├── clt.py               Q, Q̄, ABD, response, ply strains/stresses, engineering constants, diagnostics
│   │   ├── criteria.py          Max stress, max strain, Tsai-Hill, Tsai-Wu, Hashin, Puck 2D, LaRC03 2D
│   │   ├── strength.py          Residual-aware reserve factors, FPF, margins, envelopes
│   │   ├── progressive.py       Ply-discount progressive failure (FPF → LPF)
│   │   ├── environment.py       Hygrothermal loads, Chamis hot/wet retention, sweeps, warpage
│   │   ├── interlaminar.py      Transverse-shear recovery, free-edge indicators, O'Brien edge delamination
│   │   ├── buckling.py          Rayleigh–Ritz buckling of SS rectangular plates
│   │   ├── notched.py           Lekhnitskii K_T, Whitney–Nuismer PSC/ASC
│   │   ├── fatigue.py           User S-N + Palmgren–Miner
│   │   ├── uncertainty.py       Monte Carlo, sensitivities, parametric studies
│   │   ├── designrules.py       Manufacturing / stacking guideline checks
│   │   ├── optimize.py          Constrained GA + Pareto archive
│   │   └── data/materials.json  Shipped database (read-only); user edits go to user_data/
│   ├── app/main.py              FastAPI REST layer (validation, error mapping)
│   └── tests/                   pytest verification suite
├── frontend/                    Next.js (App Router) + React + TypeScript + Tailwind CSS + Recharts
└── START_AEROLAMINATE.bat       Windows launcher
```

The engine is stateless: every request carries the full project definition. The frontend owns project state (save/load as JSON).

## 2. Units (consistent N–mm–MPa system)

| Quantity | Unit | Quantity | Unit |
|---|---|---|---|
| Moduli, strengths, stress | MPa | Ply thickness, z, plate dims | mm |
| A matrix | N/mm | B matrix | N |
| D matrix | N·mm | N (force resultant) | N/mm |
| M (moment resultant) | N·mm/mm (= N) | Q (transverse shear resultant) | N/mm |
| Curvature | 1/mm | Strain | mm/mm (UI may show µε) |
| Temperature | °C (converted to °F internally only inside Chamis) | Moisture | % weight gain |
| α | 1/°C | β | 1/(% weight) |
| Density | kg/m³ | Areal mass | kg/m² |
| G_Ic, G_IIc | N/mm (= kJ/m²) | Angle | degrees |

The UI displays moduli in GPa and labels every field with its unit.

## 3. Coordinate and sign conventions

- Laminate axes x, y in-plane, z through-thickness from the geometric mid-plane, **positive upward**.
- The ply list is ordered **bottom (z = −h/2) → top (z = +h/2)**. Ply k occupies [z_{k−1}, z_k].
- Ply angle θ: rotation from +x to the fibre direction 1, positive counter-clockwise viewed from +z.
- Strain: engineering shear strain γxy = 2εxy. Vector order {εx, εy, γxy} and {σx, σy, τxy}.
- Tension positive. Strength magnitudes are positive, and the sign selects XT/XC, YT/YC.
- Curvature κx = −∂²w/∂x², so ε(z) = ε⁰ + zκ.
- Resultants: N = ∫σ dz, M = ∫σ z dz. Positive Mx gives tension at +z when κx > 0.
- Transformations (Jones 1999): σ₁₂ = T σ_xy, T = [[c², s², 2cs], [s², c², −2cs], [−cs, cs, c²−s²]].
  ε₁₂ = T_ε ε_xy with T_ε = [[c², s², cs], [s², c², −cs], [−2cs, 2cs, c²−s²]].
  Q̄ = T⁻¹ Q T_ε. ᾱ = T_ε⁻¹ α (α in engineering-strain form {α1, α2, 0}).

## 4. Governing equations

### 4.1 Laminate response
{N + N^HT; M + M^HT} = [A B; B D]{ε⁰; κ}, where N^HT = Σ Q̄_k(ᾱ_kΔT + β̄_kΔC)(z_k − z_{k−1}) and M^HT = ½Σ Q̄_k(ᾱ_kΔT + β̄_kΔC)(z_k² − z_{k−1}²).
Mechanical stress in ply k at height z: σ = Q̄_k(ε⁰ + zκ − ᾱ_kΔT − β̄_kΔC).
**Solution:** `numpy.linalg.solve` after a conditioning check. The condition number is evaluated on the *scaled* ABD (each row/column scaled by
√diag) so that its magnitude reflects true ill-conditioning rather than unit disparity. A scaled cond > 1e12 or a non-positive-definite ABD
raises `SingularLaminateError` with a diagnostic message.

### 4.2 Superposition for reserve factors
Total ply stress σ = σ_HT + λ σ_M, with σ_HT the response to (ΔT, ΔC) with zero external load and σ_M the response to the external load.
RF = smallest positive λ with FI(σ_HT + λσ_M) = 1. If FI(σ_HT) ≥ 1, the ply has already failed under residual stress alone: RF = 0 and a warning is raised.
If no positive root exists below λ_max = 1e6 (e.g. pure compression on a criterion that cannot fail in that direction), RF = ∞ and is reported as "no failure".

### 4.3 Failure criteria
As tabulated in RESEARCH_AND_GAP_ANALYSIS.md §3. Implementation details:

- **Tsai-Wu:** F1 = 1/XT − 1/XC, F11 = 1/(XT·XC), F2, F22 likewise, F66 = 1/S², F12 = F12*·√(F11F22), with F12* user-set (default −0.5).
- **Hashin MC:** S_T default YC/2 (flagged).
- **Puck 2D:** R⊥⊥A = S/(2p⊥∥⁻)[√(1 + 2p⊥∥⁻YC/S) − 1], p⊥⊥⁻ = p⊥∥⁻R⊥⊥A/S, τ21c = S√(1 + 2p⊥⊥⁻).
  Mode A (σ2 ≥ 0): f = √[(τ/S)² + (1 − p⊥∥⁺YT/S)²(σ2/YT)²] + p⊥∥⁺σ2/S.
  Mode B (σ2 < 0, |σ2/τ| ≤ R⊥⊥A/τ21c): f = [√(τ² + (p⊥∥⁻σ2)²) + p⊥∥⁻σ2]/S.
  Mode C (otherwise): f = [(τ/(2(1 + p⊥⊥⁻)S))² + (σ2/YC)²]·YC/(−σ2). FF: σ1/XT or −σ1/XC.
- **LaRC03 (Dávila & Camanho 2003):** α₀ = 53°. η^L = −S_L cos2α₀/(YC cos²α₀), η^T = −1/tan2α₀,
  S_T = YC cosα₀(sinα₀ + cosα₀/tan2α₀), g = G_Ic/G_IIc, Λ22 = 2(1/E2 − ν21²/E1).
  In-situ: embedded thin ply YT_is = √(8G_Ic/(π t Λ22)), S_L,is = √(8G12G_IIc/(π t)) (linear shear). Outer ply: YT_is = 1.79√(G_Ic/(π t Λ22)),
  S_L,is = √(4G12G_IIc/(π t)). Thick ply: 1.12√2·YT and √2·S_L. Embedded plies use max(thin, thick), as recommended in the TM.
  Matrix tension (σ2 ≥ 0): (1−g)σ2/YT_is + g(σ2/YT_is)² + (τ/S_L,is)².
  Matrix compression (σ2 < 0, σ1 ≥ −YC): max over α∈[0°, 90°) of (τ_eff^T/S_T)² + (τ_eff^L/S_L,is)².
  Fibre tension (σ1 ≥ 0): ε1/ε1T. Fibre compression: misalignment-frame stresses with
  φ_C = atan[(1 − √(1 − 4(S_L,is/XC + η^L)S_L,is/XC)) / (2(S_L,is/XC + η^L))], φ = (|τ| + (G12 − XC)φ_C)/(G12 + σ1 − σ2).
- When a required parameter is missing, the criterion returns `status = "unavailable"` with the missing-parameter list. It never substitutes.

### 4.4 Progressive failure
As in RESEARCH §4.1. Output per step: load factor, failed ply/mode list, A11..A66 (residual), dominant strain, convergence iterations.

### 4.5 Buckling
Ritz terms m = 1..M, n = 1..N (default 8 × 8). K and K_G are assembled from the closed-form sine/cosine orthogonality integrals. The cross terms
(D16, D26, Nxy) use the integral ∫₀^a sin(mπx/a)cos(pπx/a)dx = a·m·(1 − (−1)^{m+p}) / (π(m² − p²)) for m ≠ p, 0 otherwise.
The eigenproblem K a = λK_G a is solved by `scipy.linalg.eigh` on the symmetric pair after making K_G definite. Because K is symmetric positive
definite, we solve K_G a = μ K a and take λ = 1/μ for the largest positive μ. For shear, which has ± symmetric eigenvalues, the smallest positive λ is reported.

### 4.6 Optimisation
Genome: half-stack sequence (symmetric option) of angle "units" chosen from the allowed set. A non-zero/non-90 angle θ maps to a ±θ pair when
balance is enforced. Fitness = weighted, normalised objective + penalty·Σ(normalised constraint violations). Tournament selection, one-point
crossover, mutation (angle change, swap, add/remove unit), elitism. Every evaluated feasible design enters a non-dominated archive (mass,
−min RF, optional −buckling λ). The seed is user-settable for reproducibility. Results state "heuristic: no global optimality guarantee".

## 5. REST API (all POST bodies are JSON; validation errors → HTTP 422 with field paths; engineering errors → 400 with message)

| Endpoint | Purpose |
|---|---|
| GET /api/health | Engine version, author |
| GET /api/materials | Shipped + user materials |
| PUT /api/materials/{id} | Save user material (validated) |
| DELETE /api/materials/{id} | Delete a user material (shipped records are read-only) |
| POST /api/analyze | CLT + ply response + all criteria + RF/MS + design rules + diagnostics |
| POST /api/envelope | Ply stress-space and laminate N-space FPF envelopes |
| POST /api/progressive | Progressive failure |
| POST /api/environment | ΔT / ΔC sweeps, residual stress, warpage, hot/wet retention |
| POST /api/interlaminar | Transverse-shear recovery, free-edge indicators, edge delamination |
| POST /api/buckling | Ritz buckling + mode shape |
| POST /api/notched | Open-hole PSC/ASC |
| POST /api/fatigue | S-N / Miner |
| POST /api/uncertainty | Monte Carlo + sensitivities |
| POST /api/parametric | Angle / thickness / temperature sweeps |
| POST /api/optimize | GA optimiser |

Common project payload: `{ material_id | material, plies: [{angle, thickness?, material_id?}], loads: {Nx,Ny,Nxy,Mx,My,Mxy}, environment: {dT, dC}, options }`.

## 6. Dependencies

Backend: numpy ≥ 1.26, scipy ≥ 1.11, fastapi ≥ 0.110, uvicorn ≥ 0.27, pydantic ≥ 2.5, pytest, httpx (tests).
Frontend: next 15.x, react 19.x, typescript 5.x, tailwindcss 3.4.x, recharts 2.15.x. No other runtime services. Docker/WSL are not required.

## 7. Data provenance model

```json
"E1": {"value": 171420, "unit": "MPa", "status": "literature", "source": "ref-id", "note": "..."}
```
Statuses: `datasheet | literature | calculated | estimated | illustrative | unavailable`. Each analysis response includes a `provenance`
block listing the status of every property it used. Any use of `illustrative`, `estimated` or `unavailable` data raises a warning in the response.

Independently of the status, each available property carries `verification: primary | secondary | unverified` (with `verification_note`),
and each record carries a `verification_log`. The `provenance` block reports the verification level of every property used and lists the
unverified ones.

**Blocking rule.** If any ply's material has an `illustrative` value among E1, E2, G12, ν12, Xt, Xc, Yt, Yc or S12, every analysis
endpoint returns HTTP 400 (`kind: "illustrative_blocked"`) unless `options.allow_illustrative = true` (UI: *demonstration mode*).

**Plausibility warnings** (not errors) flag values outside physical ranges for continuous-fibre polymer laminae in N–mm–MPa units
(e.g. E1 outside 2 000–1 000 000 MPa, t_ply outside 0.01–2 mm) and E2 > E1. Their typical cause is a unit slip or swapped material axes.

**Module consistency rules.** Every module must apply the same hot/wet knockdown to stiffness *and* strength, or refuse. The parametric
sweep applies it. The optimiser and the uncertainty module refuse it. Modules that use only part of the load case (notch: Nx only; edge
delamination: mechanical εx only; buckling: Nx, Ny, Nxy only) report what they ignore.

## 8. Verification criteria

| ID | Test | Reference / independent solution | Tolerance |
|---|---|---|---|
| V-CLT-1 | Q of T300/5208 | Kaw (2006) Ex. 2.6: Q11 = 181.8, Q12 = 2.897, Q22 = 10.35, Q66 = 7.17 GPa | rtol 5e-4 (4 s.f.) |
| V-CLT-2 | Q̄(60°) | Kaw (2006) Ex. 2.7: 23.65, 32.46, 20.05, 109.4, 54.19, 36.74 GPa | rtol 5e-4 |
| V-CLT-3 | Q̄ invariants and periodicity | Tsai–Pagano invariants U1–U5 | 1e-9 relative |
| V-CLT-4 | Quasi-isotropy of [0/±45/90]s | Analytical identity | 1e-10 |
| V-CLT-5 | B = 0 for symmetric; antisymmetric pattern | Analytical | 1e-9·‖A‖h |
| V-CLT-6 | UD engineering constants Ex = E1, νxy = ν12 | Analytical | 1e-10 |
| V-CLT-7 | Round-trip loads ↔ deformations | Identity | 1e-10 |
| V-CLT-8 | Singular laminate detection | Zero-stiffness ply set | raises |
| V-CLT-9 | Stress transformation of an isotropic material is invariant | Analytical | 1e-10 |
| V-HT-1 | Free UD laminate: ε = αΔT, σ = 0 | Analytical | 1e-10 |
| V-HT-2 | Symmetric laminate: ΣN from residual stresses = 0, κ = 0 | Equilibrium | 1e-8 |
| V-HT-3 | [0/90] free warpage | Symmetry (κx = −κy, κxy = 0) and free-body equilibrium N = M = 0 by independent Gauss re-integration of ply stresses | 1e-9 |
| V-F-1 | All criteria FI = 1 at uniaxial strengths and pure shear | Definition | 1e-9 |
| V-F-2 | Tsai-Wu biaxial quadratic root | Hand-solved quadratic | 1e-9 |
| V-F-3 | Residual-aware RF equals bisection | Independent brute-force | 1e-6 |
| V-F-4 | LaRC03 matrix compression at σ2 = −YC (no in-situ) gives FI = 1 at α ≈ α₀ | Construction of S_T, η^T | 1e-6 |
| V-PF-1 | UD 0° tension FPF = LPF = XT | Analytical | 1e-6 |
| V-PF-2 | [0/90]s: FPF strain = YT/E2-based CLT strain; post-discount stiffness | Analytical rule of mixtures | 1e-6 |
| V-B-1 | Specially orthotropic SS plate Nx_cr | Closed form (Jones §5.5) | 1e-6 |
| V-B-2 | Isotropic square SS plate shear k_s | 9.34 (Stein & Neff 1947) | 1 % with 12 × 12 terms |
| V-B-2b | Isotropic square plate k_s: Ritz (monotone decreasing with terms) vs independent finite-difference solution with Richardson extrapolation | Independent numerical method (≈ 9.3245) | 5e-4 |
| V-SAFE | Tensor-rotation check of T_σ/T_ε; +Nxy gives fibre tension in +45°; +Mx gives top-surface tension; parametric = analysis under knockdown; unsupported combinations refused or flagged; illustrative data blocked | Independent derivation / consistency | 1e-9 / exact |
| V-LAUNCH | Launcher lint (CRLF, labels, no blocks, `call npm`, PowerShell 5.1-compatible snippets) + PowerShell parse/behaviour tests | Rules in START_AEROLAMINATE.bat header | exact |
| V-B-3 | Biaxial isotropic square plate | k = 2 (closed form: Ncr = 2π²D/b² for Nx = Ny) | 1e-6 |
| V-N-1 | Isotropic K_T∞ = 3 | Kirsch | 1e-10 |
| V-N-2 | PSC with K_T = 3 reproduces Kirsch distribution | Analytical | 1e-10 |
| V-N-3 | σN/σ0 → 1/K_T as d0 → 0 and → 1 as d0 → ∞ | Limits | 1e-3 |
| V-IL-1 | Homogeneous plate τxz,max = 1.5Q/h, τ(top) = 0 | Beam theory | 1e-8 |
| V-IL-2 | O'Brien G = 0 when all plies identical | Analytical | 1e-12 |
| V-O-1 | Optimiser candidates satisfy symmetry, balance, ply limits | Constraint check | exact |
| V-O-2 | Optimiser reproducible for fixed seed | Determinism | exact |
| V-O-3 | Pareto archive is mutually non-dominated | Definition | exact |
| V-U-1 | MC with CoV → 0 reproduces deterministic RF | Limit | 1e-9 |
| V-API | Endpoint validation, 422 on invalid inputs, 400 on singular laminates | — | — |

No expected value is adjusted to make the code pass. If a published value disagrees with an independent analytical recomputation, the
discrepancy is documented in VERIFICATION_REPORT.md.

## 9. Classification of outputs shown to users

| Label | Meaning |
|---|---|
| **Verified (analytical)** | Implementation agrees with closed-form solutions within tolerance |
| **Screening** | Established engineering approximation with stated assumptions. Not a high-fidelity prediction |
| **Estimate** | Empirical relation or illustrative data. Trends only |
| **Unavailable** | Missing inputs or an unsupported configuration. Nothing is computed |
| **External solver required** | Outside plate theory (3-D free edge, CZM/VCCT, impact) |

No output is labelled "certified" or "validated against test".
