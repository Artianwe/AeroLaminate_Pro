# AeroLaminate Pro — Research and Engineering Gap Analysis

**Author, owner and maintainer:** Anwesh Ajitabh Dash
**Document status:** Engineering research record, written before implementation. Revised after verification (see §9).
**Scope:** Plane-stress analysis of flat, thin, laminated fibre-reinforced polymer plates; screening-level structural checks.

> **Standing caveat.** AeroLaminate Pro is an engineering analysis and teaching/screening tool. Nothing it produces is a certification
> result, a design allowable, or a substitute for the building-block test programme required by FAA AC 20-107B and CMH-17. A failure
> index is a deterministic stress-state measure. It is not a probability of failure, a fatigue life, or a damage-tolerance demonstration.

---

## 0. Research method and source-traceability rules

1. Each method below was checked against its primary publication or a recognised textbook. A citation is listed in §10 only after its
   bibliographic data was confirmed in this session or is a standard identifier (ASTM/ISO/CFR). Each entry carries a
   **verification flag**:
   - **V**: title, authors, venue and year were confirmed online during this research session (and the DOI, if one is quoted).
   - **B**: standard bibliographic reference from the engineering literature. The details were *not* re-confirmed online in this
     session (outbound access to most publisher and NASA PDF hosts was blocked by the session's network policy). Check before quoting.
2. **Material data** carries a status *per property*, not per material (§6). Allowed values are `datasheet`, `literature`,
   `calculated`, `estimated`, `illustrative` and `unavailable`. The software never fills a missing property silently. An analysis that needs
   a missing property reports that it is unavailable.
3. **Mandatory vs. recommended.** Regulations (14 CFR) are mandatory for certificated products. FAA Advisory Circulars and CMH-17
   are *acceptable means / guidance*, not mandatory. ASTM/ISO test methods become mandatory only when a contract, specification or
   certification basis invokes them. Research-level failure theories (Puck, LaRC03, Cuntze …) are *methods*, not requirements.

---

## 1. Baseline specification and identified gaps

The original specification asked for CLT, five classical criteria (max stress, max strain, Tsai-Wu, Tsai-Hill, Hashin), FPF/progressive failure,
hygrothermal loads, margins, and an optimiser. The gap analysis found the following omissions, which would matter in an aerospace laminate workflow:

| # | Gap | Why it matters | Resolution in v1 |
|---|-----|----------------|------------------|
| G1 | No physically based inter-fibre-failure (IFF) criterion with fracture-plane concept | Tsai-Wu/Hill interact fibre and matrix terms non-physically, and they misjudge the strengthening effect of transverse compression on shear | **Implemented:** Puck 2D (modes A/B/C) and LaRC03 (2D) |
| G2 | No ply in-situ strength effect | Embedded thin plies show transverse-tension and shear strengths well above UD coupon values (Dávila & Camanho 2003; Camanho et al. 2006) | **Implemented** within LaRC03 (needs G_Ic, G_IIc), and switchable |
| G3 | Residual thermal stresses are not superposed correctly on margins | Scaling the *total* stress overstates the margin when cure residual stresses are present | **Implemented:** load-factor solve with thermal/moisture state held constant |
| G4 | No transverse-shear (interlaminar τxz, τyz) recovery | CLT gives no interlaminar stress; short-beam/bending loads drive delamination | **Implemented:** equilibrium-based recovery under transverse shear resultants (screening) |
| G5 | No free-edge / delamination onset indicator | Free-edge stresses (Pipes & Pagano 1970) drive delamination of coupons and cut-outs | **Implemented:** Herakovich mismatch indicators + O'Brien edge-delamination strain-energy release rate (screening) |
| G6 | No stability check | Thin compression/shear panels are often sized by buckling, not strength | **Implemented:** Rayleigh–Ritz buckling of simply supported rectangular plates under Nx, Ny, Nxy with D16/D26 retained |
| G7 | No notched (open-hole) strength | OHT/OHC are usually design-driving in aerospace laminates | **Implemented:** Lekhnitskii K_T∞, Konish–Whitney stress distribution, Whitney–Nuismer point/average stress criteria (requires calibrated d₀/a₀) |
| G8 | No environmental knockdown for hot/wet | Matrix-dominated properties drop strongly at ETW | **Implemented:** Chamis empirical matrix-property retention (labelled *estimate*); user may override with test data |
| G9 | No statistical treatment of strength | Allowables are A/B-basis values, not means | **Implemented:** Monte Carlo propagation of user-specified CoVs (*not* CMH-17 basis values) + one-at-a-time sensitivity |
| G10 | No fatigue/spectrum capability | Composite fatigue is usually checked with strain cut-offs and test-derived S-N | **Implemented:** user-supplied S-N + Palmgren–Miner (screening). No fatigue data are shipped, because none could be traced |
| G11 | No design-rule (manufacturability) checks | Industry stacking guidelines: balance, symmetry, 10 % rule, ≤ 4 consecutive plies, ±45 outer plies, angle-change limits | **Implemented** in a design-rule checker and in the optimiser constraints |
| G12 | No laminate-level failure envelope | Designers use N-space FPF envelopes, not only ply stress-space envelopes | **Implemented:** ply stress-space envelopes + laminate Nx–Ny / Nx–Nxy FPF envelopes |
| G13 | No multiobjective trade study | Mass versus reserve factor versus stability is the actual design decision | **Implemented:** GA with constraint handling + non-dominated (Pareto) archive |
| G14 | No numerical conditioning diagnostics | Near-singular [ABD] (e.g. fully failed laminate) produces silent garbage | **Implemented:** condition number, rank check, explicit `SingularLaminateError` |
| G15 | Impact/CAI, bearing/bypass, postbuckling, 3-D free-edge stress, crack growth (VCCT/CZM) | Real design drivers that need test data or FE | **Not implemented.** Roadmap only (§8). The UI states this |

---

## 2. Laminate mechanics (Classical Laminate Theory)

**Purpose.** Relates in-plane force/moment resultants to mid-plane strains and curvatures, and recovers ply stresses.
**Basis.** Kirchhoff–Love kinematics, ply-wise plane stress, perfect bonding (Jones 1999; Reddy 2004; Kaw 2006).

Equations, with material axes 1 (fibre), 2 (transverse) and laminate axes x, y. The ply angle θ is measured from x to 1, positive counter-clockwise viewed from +z:

- Reduced stiffness: Q11 = E1/(1−ν12ν21), Q22 = E2/(1−ν12ν21), Q12 = ν12E2/(1−ν12ν21), Q66 = G12, ν21 = ν12E2/E1.
- Transformed stiffness: Q̄ = T⁻¹ Q R T R⁻¹ (Reuter matrix R handles engineering shear strain). In closed form (Jones 1999, eq. 2.85):
  Q̄11 = Q11c⁴ + 2(Q12+2Q66)s²c² + Q22s⁴, Q̄16 = (Q11−Q12−2Q66)sc³ + (Q12−Q22+2Q66)s³c, etc.
- A_ij = Σ Q̄_ij,k (z_k − z_{k−1}), B_ij = ½ Σ Q̄_ij,k (z_k² − z_{k−1}²), D_ij = ⅓ Σ Q̄_ij,k (z_k³ − z_{k−1}³).
- {N; M} = [A B; B D]{ε⁰; κ} − {N^T + N^H; M^T + M^H}.
- Ply strain: ε(z) = ε⁰ + zκ. Mechanical ply stress: σ = Q̄(ε − α ΔT − β ΔC).
- Effective in-plane engineering constants (Ex, Ey, Gxy, νxy) from a = A⁻¹ · h; flexural constants from d = D⁻¹ (meaningful for B = 0).

**Inputs.** E1, E2, G12, ν12, ply thickness, angle, stacking order.
**Assumptions and limits.** Thin plate (span/thickness ≳ 10–20), small strain, linear elastic, no σz, τxz, τyz, no free-edge zone.
**Validation.** (i) Q and Q̄ against a textbook example (Kaw 2006, Examples 2.6–2.7, T300/5208). (ii) Invariant identities. (iii)
quasi-isotropy of [0/±45/90]s (A11 = A22, A66 = (A11−A12)/2, A16 = A26 = 0). (iv) B = 0 for symmetric layups. (v) the
antisymmetric angle-ply pattern (only B16, B26 ≠ 0). (vi) the round trip {N,M} → {ε,κ} → {N,M}.
**Priority:** P0 (foundation).

**Coupling indicators** (P0): extension–shear |A16|,|A26| normalised by √(A11A66); bending–twisting
δ = D16/(D11³D22)^¼ and γ = D26/(D11D22³)^¼ (Nemeth's non-dimensional parameters, used for buckling relevance); extension–bending
‖B‖ normalised by √(‖A‖‖D‖). Classification: symmetric, balanced, quasi-isotropic (in-plane), specially orthotropic.

## 3. Failure criteria (ply level, plane stress)

All criteria act on the ply stresses in material axes (σ1, σ2, τ12). Strengths are positive magnitudes: XT, XC, YT, YC, S (= S_L).

| Criterion | Equation (FI = 1 at failure) | Homogeneity (for load factor) | Extra inputs | Primary source | Notes |
|---|---|---|---|---|---|
| Max stress | max(σ1/X±, σ2/Y±, abs(τ12)/S) | degree 1 | — | Jones 1999 | Mode-identifying, no interaction |
| Max strain | max(ε1/ε1±, ε2/ε2±, abs(γ12)/γu) | degree 1 | ultimate strains. If unavailable, use the stress-derived ε = X/E (flagged *derived*) | Jones 1999 | Strains are mechanical (thermal free strain removed) |
| Tsai-Hill | (σ1/X)² − σ1σ2/X² + (σ2/Y)² + (τ12/S)², with X, Y selected by sign | degree 2 | — | Azzi & Tsai 1965; Hill 1948 | Sign-dependent selection follows common practice |
| Tsai-Wu | F1σ1 + F2σ2 + F11σ1² + F22σ2² + F66τ12² + 2F12σ1σ2 | non-homogeneous (quadratic solve) | F12* (default −½, Tsai & Hahn 1980) | Tsai & Wu 1971 | Stability requires F11F22 − F12² > 0, which is checked |
| Hashin (1980), 4-mode plane stress | FT: (σ1/XT)² + (τ12/S)²; FC: (σ1/XC)²; MT: (σ2/YT)² + (τ12/S)²; MC: (σ2/2S_T)² + [(YC/2S_T)² − 1]σ2/YC + (τ12/S)² | degree 2 (MC: non-homogeneous) | S_T (transverse shear strength). Default S_T = YC/2 (flagged *assumed*) | Hashin 1980 | FT form with α=1 (Hashin 1980). Some codes use α=0 (Hashin–Rotem) |
| Puck 2D IFF + FF | Mode A, B, C (Puck & Schürmann 1998, 2002) | degree 1 | p⊥∥⁺, p⊥∥⁻ (CFRP recommendations 0.35/0.30, Puck et al. 2002) | Puck & Schürmann 2002; Knops 2008 | Simplified FF (σ1/X±); no fibre-parallel weakening term |
| LaRC03 (2D) | Matrix tension, matrix compression (fracture-plane search), fibre tension (strain), fibre compression (misalignment frame) | numerical | G_Ic, G_IIc, α₀ = 53°, in-situ switch, ply position (outer/embedded) | Dávila & Camanho 2003 (NASA/TM-2003-212663); Dávila, Camanho & Rose 2005 | Reports *unavailable* when toughness data are missing |
| Cuntze FMC | 5 modes with interaction exponent | — | m, μ⊥∥, μ⊥⊥ (curve-fit) | Cuntze & Freund 2004 | **Not implemented.** Interaction exponent and friction parameters are curve-fit and not in the database. Roadmap |
| LaRC04/05 (3D) | 3D, Mohr–Coulomb fracture plane, kinking | — | 3D stresses | Pinho et al. 2005 | **Not implemented.** Needs 3D stresses that CLT cannot give |

**Reserve factor (load multiplier).** RF solves FI(σ_res + RF·σ_mech) = 1, where σ_res is the residual hygrothermal ply stress held
fixed. For homogeneous criteria with σ_res = 0 this reduces to RF = 1/FI^(1/n). With σ_res ≠ 0 the problem is solved numerically
(bracketed Brent root). Tsai-Wu is solved in closed form as a quadratic. Margin of safety: MS = RF/FoS − 1. The FoS is user-defined
(1.5 is the ultimate factor of 14 CFR 25.303 for limit loads; the application does not decide which load level a user enters).

**Validation.** Each criterion must return FI = 1 (RF = 1) for each uniaxial strength state and for pure shear at S. The Tsai-Hill and Tsai-Wu
biaxial points have closed forms. Puck and LaRC03 must reproduce their own calibration points (YT, YC at α₀, S). The RF solver is
cross-checked against brute-force bisection.

**Priority:** P0 (classical 5), P1 (Puck, LaRC03).

## 4. Damage, progressive failure, interlaminar and fracture

### 4.1 Progressive (ply-discount) failure — P0
**Purpose.** Estimate the FPF→LPF sequence and the residual stiffness after the first ply fails.
**Method.** Incremental ply-discount (Tay et al. 2008 review; Garnich & Akula 2009). At each step: (1) with the current degraded stiffness, find the
smallest RF over intact modes of all plies. (2) Scale the mechanical load to RF·λ. (3) Degrade the failed ply/mode. (4) Re-equilibrate at constant
load and iterate until no further plies fail (*convergence criterion:* no new failures, or the iteration cap is reached, which is reported).
(5) Repeat until LPF.
**Degradation laws (documented defaults, user-editable):** fibre failure → E1, E2, G12, ν12 × d_f = 0.01. Matrix (IFF) failure →
E2, G12, ν12 × d_m = 0.20. The small residual factors keep [ABD] non-singular. Discount factors are *modelling choices*, not material data.
**LPF definition:** the load at which (a) [ABD] becomes singular/ill-conditioned (cond > 10¹²), (b) every ply has a fibre-mode
failure, or (c) the laminate secant stiffness in the dominant load direction falls below 5 % of pristine.
**Limitations.** Mesh-free and mode-blind to load redistribution in a structure. The result depends on the discount factors. It is not a
damage-mechanics (CDM) prediction, and no energy regularisation is applied.
**Validation.** Analytical checks: UD 0° laminate in x-tension has FPF = LPF = XT·h. Cross-ply [0/90]s in x-tension: 90° plies fail first at
the CLT-predicted strain, and after matrix discount the laminate stiffness drops to the value computed with degraded 90° plies.

### 4.2 Interlaminar transverse shear — P1 (screening)
Under transverse shear resultants Qx, Qy with linearly varying moments (dM/dx = Q), equilibrium gives
τxz(z) = −∫_{-h/2}^{z} ∂σx/∂x dz, τyz(z) = −∫ ∂τxy/∂x dz (for Qx), where ∂σ/∂x = Q̄(∂ε⁰/∂x + z ∂κ/∂x) and
{∂ε⁰/∂x; ∂κ/∂x} = [ABD]⁻¹{0; ∂M/∂x}. (Whitney 1987; Reddy 2004, "stress recovery from equilibrium").
*Validation:* homogeneous plate τ_max = 1.5Q/h at mid-plane; traction-free top surface (residual ≈ 0).
*Limitation:* not valid near free edges, load introduction, ply drops or cut-outs. The interlaminar strength S13 is taken as S12 (transverse
isotropy assumption, flagged) unless a short-beam/ILSS value is supplied.

### 4.3 Free-edge indicators — P1 (qualitative)
Mismatch of Poisson's ratio νxy and of the coefficient of mutual influence η_xy,x between adjacent plies correlates with free-edge
σz and τxz respectively (Herakovich 1981; Pipes & Pagano 1970). **Indicator only: no interlaminar stress magnitude is claimed.** A
layerwise/3-D FE analysis is required for magnitudes (roadmap).

### 4.4 Edge delamination onset (O'Brien) — P1 (screening)
G = (ε²·t/2)(E_LAM − E*), with E* = Σ E_i t_i / t computed from the sublaminates formed by delaminating the chosen symmetric interfaces
(O'Brien 1982). Onset strain ε_c = √(2G_c / (t(E_LAM − E*))). The total G is compared with G_Ic (conservative, because mode mix is not
resolved and G_c(mixed) ≥ G_Ic for epoxy systems). Benzeggagh–Kenane (1996) mixed-mode G_c = G_Ic + (G_IIc − G_Ic)·B^η is
available when the user supplies a mode ratio B and η. *Assumptions:* straight edge, uniform axial strain, symmetric delamination,
linear elastic sublaminates.

### 4.5 Fracture mechanics data
G_Ic (ASTM D5528, DCB), G_IIc (ASTM D7905, ENF), mixed-mode (ASTM D6671, MMB). Only IM7/8552 has toughness values in the shipped
database (literature, Camanho et al. 2007). VCCT and cohesive-zone growth analysis need FE, so they are roadmap items.

### 4.6 Impact and damage tolerance — Roadmap
BVID, CAI (ASTM D7136/D7137) and damage growth are test-driven, and CLT cannot predict them. They are not implemented, and the UI states this.

## 5. Structural checks

### 5.1 Plate buckling — P1
**Model.** Simply supported (w = 0, M_n = 0) rectangular plate a × b under uniform Nx, Ny, Nxy. Rayleigh–Ritz with
w = Σ_m Σ_n A_mn sin(mπx/a) sin(nπy/b). Stiffness Π_U = ½∫[D11w,xx² + 2D12w,xxw,yy + D22w,yy² + 4D66w,xy² + 4D16w,xxw,xy +
4D26w,yyw,xy]dA. Geometric term ½∫[Nx w,x² + Ny w,y² + 2Nxy w,x w,y]dA. Generalized eigenproblem K a = λ K_G a; the critical
λ is the smallest positive eigenvalue (Whitney 1987; Leissa 1985).
**Exact check:** for D16 = D26 = 0 and Nxy = 0, N_x,cr = (π²/a²)·min_m[D11m² + 2(D12+2D66)(a/b)² + D22(a/b)⁴/m²] (Jones 1999, §5.5).
Isotropic square plate in shear: k_s = 9.34 (Stein & Neff 1947; Timoshenko & Gere 1961).
**Limitations.** B ≠ 0 is handled approximately with the reduced bending stiffness D* = D − B A⁻¹ B (flagged). No postbuckling, no
imperfection knockdown, no transverse-shear flexibility, and only SS boundaries. The sine series converges slowly with D16, D26 and Nxy, so
the user selects the term count and the convergence is reported.

### 5.2 Notched (open-hole) strength — P1 (requires calibration)
K_T∞ = 1 + √(2(√(Ex/Ey) − νxy) + Ex/Gxy) (Lekhnitskii 1968). Konish–Whitney (1975) approximate distribution
σy(x,0)/σ∞ = ½{2 + (R/x)² + 3(R/x)⁴ − (K_T∞−3)[5(R/x)⁶ − 7(R/x)⁸]}. Whitney–Nuismer (1974):
PSC σN/σ0 = 2/(2+ξ²+3ξ⁴−(K_T∞−3)(5ξ⁶−7ξ⁸)), ξ = R/(R+d0); ASC σN/σ0 = 2(1−ξ)/(2−ξ²−ξ⁴+(K_T∞−3)(ξ⁶−ξ⁸)), ξ = R/(R+a0).
Isotropic finite-width correction (2 + (1−2R/W)³)/(3(1−2R/W)) is applied as an *approximation* for orthotropic plates.
**Inputs:** d0 or a0 (characteristic distances must be calibrated from ASTM D5766/D6484 tests; the literature values ≈ 1 mm (PSC) and ≈ 4 mm (ASC) for
carbon/epoxy are labelled *empirical*), unnotched strength σ0 (test value preferred; the CLT FPF estimate is allowed and flagged).
Balanced orthotropic laminates only (A16 = A26 = 0), which is warned otherwise.

### 5.3 Fatigue — P2 (user-data only)
Composite fatigue data depend strongly on layup, R-ratio and environment, and no traceable data were found to ship. The module accepts a
user S-N curve (log-linear S = 1 − b·log10 N, or power law S = A·N^(−1/k)) normalised by a user static strength, plus a block
spectrum, and computes the Palmgren–Miner damage sum (Miner 1945). It is labelled *screening*, it does not predict life, and it ignores sequence effects.

### 5.4 Environmental degradation — P1 (estimate)
Matrix-dominated retention (Chamis 1984): P/P0 = [(T_gw − T)/(T_g0 − T_0)]^½, with T_gw = (0.005M² − 0.10M + 1)·T_g0 (M in % weight,
all temperatures in °F, as in the original. The T_gw expression is not unit-invariant, so the code converts °C → °F before applying it and never
evaluates it in °C). Applied to E2, G12, YT, YC and S only. Retention is clamped to [0, 1], and the module refuses T ≥ T_gw.
It is labelled an **empirical estimate**. Users should replace it with ETW/CTD test data (CMH-17 conditions) when they have them. Hygrothermal strains use
α1, α2, β1, β2. Residual stresses use ΔT = T_operating − T_stress-free (the stress-free temperature is a user input, often taken near the cure temperature).
Warpage of unsymmetric laminates is computed with linear CLT (Hyer 1981 shows that thin unsymmetric laminates are geometrically non-linear and
bistable, so this is labelled a *linear estimate*).

### 5.5 Uncertainty and sensitivity — P1
Monte Carlo over normal (or log-normal) distributions of E1, E2, G12, ν12 and strengths with user-defined CoV gives the distribution of FPF RF,
its percentiles and the empirical exceedance. **Explicitly not CMH-17 A/B-basis allowables.** Those need batch/panel structure, pooling and
specific statistical procedures (CMH-17-1G Ch. 8). One-at-a-time ±Δ finite-difference sensitivities (normalised elasticity
∂ln y/∂ln x) give a tornado diagram for RF, Ex and D11.

## 6. Material database findings

| System | What could be traced | Status in database |
|---|---|---|
| **IM7/8552 (Hexcel)** | Hexcel HexPly 8552 EU datasheet (confirmed in search): 0° tensile modulus 164 GPa, 0° tensile strength 2724 MPa, 90° tensile strength 64 MPa, cured ply thickness 0.131 mm at 35 % RC, Vf 57.7 %. Full lamina set incl. G_Ic, G_IIc used in Camanho, Maimí & Dávila (2007) | Lamina set from the literature (Camanho et al. 2007). Datasheet values are stored as *reference* annotations. The two sources differ (e.g. E1 171 vs 164 GPa), and **they are not mixed.** Thermal expansion: *unverified*. NCAMP NCP-RP-2009-028 Rev B (B-basis) exists, but it could not be retrieved |
| **AS4/3501-6 (Hercules/Hexcel)** | WWFE-I lamina data, Soden, Hinton & Kaddour (1998) | *Literature*, transcribed from the WWFE-I table as widely reproduced; marked "verify against the original paper". Density: *estimated* (rule of mixtures). Ply thickness: *estimated* |
| **CYCOM 5320-1 / T650-35 145 gsm unitape (Solvay/Syensqo)** | NCAMP CAM-RP-2013-002 Rev A (2017), NCP-RP-2013-001 Rev A, NMS 532/5 Rev A exist (confirmed). **Numerical values could not be extracted** | **All mechanical values are *illustrative*.** Ply thickness and Vf are *calculated* from FAW 145 g/m² and 33 % RC. The UI raises a blocking warning, and the user must load NCAMP values before relying on any result |
| **T300/5208** | Tsai & Hahn (1980); reproduced in Kaw (2006) Table 2.1 | *Literature* (textbook). It serves as the reference material for the verification tests |
| **E-glass/epoxy (Scotchply 1002)** | Tsai & Hahn (1980); Kaw (2006) Table 2.1 | *Literature* (textbook) |

**Release-verification pass (2026-10-24).** A second attempt to read the primary documents (Hexcel datasheets, NASA NTRS, NCAMP/NIAR,
ORNL mirror of NCAMP CAM-RP-2009-015) was again denied by the environment's network policy. Web-search extracts were treated as secondary evidence:
- IM7/8552: E1, E2, G12, ν12, Yt, Xc, S12 and G_Ic match an independent table (arXiv:2607.07977, which calls its card a demonstration
  card of unstated origin). Xt (2326 vs 2323.5 MPa) and Yc (200 vs 199.8 MPa) differ slightly and remain *unverified*. The only CTE lead
  (a "typical 8552 composite" value of −0.64 ppm/°C with no direction) is insufficient, so **α1/α2 remain unavailable** and are not invented.
- AS4/3501-6: the WWFE-I paper (doi:10.1016/S0266-3538(98)00078-5) is confirmed, but no accessible source confirms its table values. Other
  AS4/3501-6 data sets differ substantially (E1 138.9–148.9 GPa), which confirms that data sets must not be mixed.
- CYCOM 5320-1/T650: the NCAMP reports exist, but their tables were not extractable. NMS 532/5 acceptance limits (0° tension modulus 126.8–150.1 GPa,
  average strength ≥ 1905.6 MPa) are recorded as a cross-check only. **The record stays illustrative and analyses are blocked by default.**
- T300/5208: elastic constants and one strength set match an uncited secondary table.
The outcome is stored per property (`verification` = primary / secondary / unverified, with a note). No shipped value is primary-verified.

Rules applied: properties from different cure conditions, test environments or sources are not merged into one record. Each property stores its
value, unit, status, source and notes. Mean values are not basis values.

## 7. Practical design rules (manufacturability)

Industry guidelines that are recommendations, not regulations (Niu 1992; Kassapoglou 2013; CMH-17-3G Vol. 3 Ch. 5):
symmetric (avoid warpage), balanced (avoid extension–shear coupling), ≥ 10 % of plies in each of 0/±45/90 ("10 % rule"), ≤ 4
consecutive plies of the same angle (limits matrix-crack/edge-delamination sizes), ±45 surface plies (damage tolerance, buckling),
angle change between adjacent plies ≤ 45–60° (interlaminar stress), discrete angles 0/±45/90 (with optional 30/60). The checker reports
each rule as pass/fail/not-applicable, and the optimiser enforces the selected ones.

## 8. Prioritised roadmap

| Priority | Feature | Status | Reason or prerequisite |
|---|---|---|---|
| P0 | CLT, ABD, conditioning | Implemented, verified | — |
| P0 | Max stress/strain, Tsai-Hill, Tsai-Wu, Hashin | Implemented, verified | — |
| P0 | Residual-aware RF/MS, FPF | Implemented, verified | — |
| P0 | Progressive ply-discount, FPF/LPF | Implemented, verified (analytical cases) | — |
| P0 | Hygrothermal loads, residual stress, warpage | Implemented, verified | — |
| P0 | GA optimiser with constraints + Pareto | Implemented, tested (constraint satisfaction, reproducibility) | Heuristic. No global optimum is claimed |
| P1 | Puck 2D, LaRC03 2D | Implemented, verified at calibration points | Needs p-parameters / G_Ic, G_IIc |
| P1 | Buckling (Ritz, SS) | Implemented, verified vs closed form and k_s = 9.34 | — |
| P1 | Open hole PSC/ASC | Implemented, verified vs Kirsch/Lekhnitskii limits | d0/a0 must be calibrated |
| P1 | Interlaminar shear recovery, free-edge indicators, O'Brien G | Implemented (screening) | — |
| P1 | Monte Carlo, sensitivity, parametric sweeps | Implemented | — |
| P1 | Hot/wet knockdown (Chamis) | Implemented (estimate) | Test data preferred |
| P2 | User S-N + Miner | Implemented (user data) | No shipped fatigue data |
| P2 | Cuntze FMC | Roadmap | Curve-fit parameters needed |
| P2 | 3-D criteria (LaRC04/05, Hashin 3D) | Roadmap | Needs 3-D stresses (layerwise/FE) |
| P2 | Free-edge stress magnitudes (layerwise/FE) | Roadmap | External solver |
| P2 | VCCT / CZM delamination growth | Roadmap | FE (Krueger 2004; Turon et al. 2007) |
| P3 | Impact/CAI, bearing/bypass, ply drops, sandwich, curved panels, postbuckling | Roadmap | Test data + FE |
| P3 | CMH-17 basis-value statistics (B-basis, pooling) | Roadmap | Batch-structured test data |

## 9. Verification plan (summary; detail in SYSTEM_ENGINEERING_SPEC.md §8)

Independent checks, with tolerance justification: closed-form identities (machine-precision, rtol 1e-10), textbook numeric examples quoted to
4 significant figures (rtol 5e-4), Ritz vs exact (rtol 1e-6 for the uncoupled case), k_s = 9.34 (published to 3 s.f.: rtol 1 %), Monte
Carlo (statistical tolerance with a fixed seed). No expected value is tuned to match the code.

## 10. References

Verification flag: **V** = confirmed online in this session; **B** = standard reference, not re-confirmed (verify before quoting).

**Failure theories**
1. Tsai, S.W., Wu, E.M. (1971). A general theory of strength for anisotropic materials. *J. Composite Materials* 5:58–80. doi:10.1177/002199837100500106. **V**
2. Hashin, Z. (1980). Failure criteria for unidirectional fiber composites. *J. Applied Mechanics* 47(2):329–334. doi:10.1115/1.3153664. **V**
3. Azzi, V.D., Tsai, S.W. (1965). Anisotropic strength of composites. *Experimental Mechanics* 5:283–288. **B**
4. Hill, R. (1948). A theory of the yielding and plastic flow of anisotropic metals. *Proc. R. Soc. Lond. A* 193:281–297. **B**
5. Puck, A., Schürmann, H. (1998). Failure analysis of FRP laminates by means of physically based phenomenological models. *Compos. Sci. Technol.* 58:1045–1067; and (2002) 62:1633–1662. **V** (bibliographic)
6. Puck, A., Kopp, J., Knops, M. (2002). Guidelines for the determination of the parameters in Puck's action plane strength criterion. *Compos. Sci. Technol.* 62:371–378. **B**
7. Knops, M. (2008). *Analysis of Failure in Fiber Polymer Laminates: The Theory of Alfred Puck*. Springer. doi:10.1007/978-3-540-75765-8. **V**
8. Dávila, C.G., Camanho, P.P. (2003). *Failure Criteria for FRP Laminates in Plane Stress*. NASA/TM-2003-212663. NTRS 20040001363. **V**
9. Dávila, C.G., Camanho, P.P., Rose, C.A. (2005). Failure criteria for FRP laminates. *J. Composite Materials* 39(4):323–345. doi:10.1177/0021998305046452. **V**
10. Pinho, S.T., Dávila, C.G., Camanho, P.P., Iannucci, L., Robinson, P. (2005). *Failure Models and Criteria for FRP Under In-Plane or Three-Dimensional Stress States Including Shear Non-Linearity* (LaRC04). NASA/TM-2005-213530. NTRS 20050110223. **V**
11. Camanho, P.P., Dávila, C.G., Pinho, S.T., Iannucci, L., Robinson, P. (2006). Prediction of in situ strengths and matrix cracking in composites under transverse tension and in-plane shear. *Composites Part A* 37:165–176. **B**
12. Cuntze, R.G., Freund, A. (2004). The predictive capability of failure mode concept-based strength criteria for multidirectional laminates. *Compos. Sci. Technol.* 64:343–377. **B**
13. Soden, P.D., Hinton, M.J., Kaddour, A.S. (1998). Lamina properties, lay-up configurations and loading conditions for a range of fibre-reinforced composite laminates. *Compos. Sci. Technol.* 58(7):1011–1022. **V** (bibliographic)
14. Hinton, M.J., Kaddour, A.S., Soden, P.D. (eds.) (2004). *Failure Criteria in Fibre Reinforced Polymer Composites: The World-Wide Failure Exercise*. Elsevier. **B**

**Damage, notches, fracture, stability**
15. Camanho, P.P., Maimí, P., Dávila, C.G. (2007). Prediction of size effects in notched laminates using continuum damage mechanics. *Compos. Sci. Technol.* 67:2715–2727. doi:10.1016/j.compscitech.2007.02.005. NTRS 20070035071. **V**
16. Whitney, J.M., Nuismer, R.J. (1974). Stress fracture criteria for laminated composites containing stress concentrations. *J. Composite Materials* 8:253–265. **V** (bibliographic; DOI not confirmed)
17. Konish, H.J., Whitney, J.M. (1975). Approximate stresses in an orthotropic plate containing a circular hole. *J. Composite Materials* 9:157–166. **B**
18. Lekhnitskii, S.G. (1968). *Anisotropic Plates*. Gordon and Breach. **B**
19. Benzeggagh, M.L., Kenane, M. (1996). Measurement of mixed-mode delamination fracture toughness of unidirectional glass/epoxy composites with mixed-mode bending apparatus. *Compos. Sci. Technol.* 56(4):439–449. **V** (bibliographic; DOI not confirmed)
20. O'Brien, T.K. (1982). Characterization of delamination onset and growth in a composite laminate. In *Damage in Composite Materials*, ASTM STP 775, 140–167. **B**
21. Pipes, R.B., Pagano, N.J. (1970). Interlaminar stresses in composite laminates under uniform axial extension. *J. Composite Materials* 4:538–548. **B**
22. Herakovich, C.T. (1981). On the relationship between engineering properties and delamination of composite materials. *J. Composite Materials* 15:336–348. **B**
23. Krueger, R. (2004). Virtual crack closure technique: history, approach, and applications. *Applied Mechanics Reviews* 57(2):109–143. **B**
24. Tay, T.E., Liu, G., Tan, V.B.C., Sun, X.S., Pham, D.C. (2008). Progressive failure analysis of composites. *J. Composite Materials* 42(18):1921–1966. **B**
25. Garnich, M.R., Akula, V.M.K. (2009). Review of degradation models for progressive failure analysis of fiber reinforced polymer composites. *Applied Mechanics Reviews* 62(1):010801. **B**
26. Stein, M., Neff, J. (1947). *Buckling Stresses of Simply Supported Rectangular Flat Plates in Shear*. NACA TN 1222. **B** The classical k_s = 9.34 (square plate) is a 3-significant-figure value. AeroLaminate Pro's Ritz and independent finite-difference solutions both converge to 9.3245 (VERIFICATION_REPORT.md §3).
27. Timoshenko, S.P., Gere, J.M. (1961). *Theory of Elastic Stability*, 2nd ed. McGraw-Hill. **B**
28. Leissa, A.W. (1985). *Buckling of Laminated Composite Plates and Shell Panels*. AFWAL-TR-85-3069. **B**
29. Nemeth, M.P. (1986). Importance of anisotropy on buckling of compression-loaded symmetric composite plates. *AIAA Journal* 24(11):1831–1835. **B**
30. Hyer, M.W. (1981). Some observations on the cured shape of thin unsymmetric laminates. *J. Composite Materials* 15:175–194. **B**
31. Chamis, C.C. (1984). Simplified composite micromechanics equations for hygral, thermal and mechanical properties. *SAMPE Quarterly* 15(3):14–23 (also NASA TM-83320). **B**
32. Miner, M.A. (1945). Cumulative damage in fatigue. *J. Applied Mechanics* 12:A159–A164. **B**

**Textbooks**
33. Jones, R.M. (1999). *Mechanics of Composite Materials*, 2nd ed. Taylor & Francis. **B**
34. Kaw, A.K. (2006). *Mechanics of Composite Materials*, 2nd ed. CRC Press. **B**
35. Tsai, S.W., Hahn, H.T. (1980). *Introduction to Composite Materials*. Technomic. **B**
36. Reddy, J.N. (2004). *Mechanics of Laminated Composite Plates and Shells*, 2nd ed. CRC Press. **B**
37. Whitney, J.M. (1987). *Structural Analysis of Laminated Anisotropic Plates*. Technomic. **B**
38. Herakovich, C.T. (1998). *Mechanics of Fibrous Composites*. Wiley. **B**
39. Kassapoglou, C. (2013). *Design and Analysis of Composite Structures*, 2nd ed. Wiley. **B**
40. Niu, M.C.Y. (1992). *Composite Airframe Structures*. Conmilit Press. **B**
41. Gürdal, Z., Haftka, R.T., Hajela, P. (1999). *Design and Optimization of Laminated Composite Materials*. Wiley. **B**
42. Le Riche, R., Haftka, R.T. (1993). Optimization of laminate stacking sequence for buckling load maximization by genetic algorithm. *AIAA Journal* 31(5):951–956. **B**
43. Deb, K., Pratap, A., Agarwal, S., Meyarivan, T. (2002). A fast and elitist multiobjective genetic algorithm: NSGA-II. *IEEE Trans. Evol. Comput.* 6(2):182–197. **B**

**Regulatory, guidance and handbooks**
44. FAA Advisory Circular AC 20-107B, *Composite Aircraft Structure*, 8 Sep 2009 (guidance, not mandatory). https://www.faa.gov/documentLibrary/media/Advisory_Circular/AC20-107B.pdf **V**
45. CMH-17-3G, *Composite Materials Handbook Vol. 3: Polymer Matrix Composites — Materials Usage, Design and Analysis*, SAE International, 2012 (guidance). **V** (TOC confirmed: wichita.edu/industry_and_defense/NIAR/Documents/Vol3-RevG-TOC.pdf)
46. CMH-17-1G, Vol. 1: *Guidelines for Characterization of Structural Materials* (statistics for basis values). **B**
47. 14 CFR §25.303 (factor of safety 1.5), §25.305 (strength and deformation), §25.613 (material strength properties and design values) — **mandatory** for transport-category certification. **B**

**Test standards (identifiers; content not reproduced)**
48. ASTM D3039/D3039M (tensile), D3410/D3410M and D6641/D6641M (compression), D3518/D3518M (±45° in-plane shear), D5379/D5379M (V-notch shear), D7078/D7078M (V-notched rail shear), D2344/D2344M (short-beam strength), D5528 (mode I DCB), D7905/D7905M (mode II ENF), D6671/D6671M (mixed-mode MMB), D5766/D5766M (open-hole tension), D6484/D6484M (open-hole compression), D7136/D7136M (drop-weight impact), D7137/D7137M (compression after impact), D3479/D3479M (tension–tension fatigue), D6115 (mode I fatigue delamination onset), D5229/D5229M (moisture absorption), E1640 (Tg by DMA), D3171 (constituent content). ISO 527-4/-5, ISO 14126, ISO 14129, ISO 15024, ISO 18352. **B**

**Material data sources**
49. Hexcel, *HexPly 8552 Product Data Sheet* (EU). https://hexcel.com/wp-content/uploads/2025/12/HexPly_8552_eu_DataSheet1.pdf (values quoted in §6 confirmed via search extract). **V**
50. NCAMP, *Hexcel 8552 IM7 Unidirectional Prepreg Statistical Analysis Report*, NCP-RP-2009-028 Rev B, 2019. https://wichita.edu/industry_and_defense/NIAR/Documents/NCP-RP-2009-028-Rev-B-HEXCEL-8552-IM7-Uni-SAR-4-16-2019.pdf **V** (existence; values not extracted)
51. NCAMP, *Cycom 5320-1 T650 Unitape Qualification Material Property Data Report*, CAM-RP-2013-002 Rev A, 27 Jan 2017; *Statistical Analysis Report* NCP-RP-2013-001 Rev A; material specification NMS 532/5 Rev A; process specification NPS 85321. https://www.wichita.edu/industry_and_defense/NIAR/Research/cytec5320-1.php **V** (existence; values not extracted)

---
*Prepared for AeroLaminate Pro by Anwesh Ajitabh Dash.*
