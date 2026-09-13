# v2 — THE DESIGN SURFACE: one smoothness solve (spec, 2026-09-08)

Owner (RULINGS 2026-09-08t, interview): pavement is a designed surface —
minimum curvature, unbounded cut and fill, flush and tangent at every
contact, the DEM a datum only, laws as targets, the sim as acceptance.
v1 graded/filled/cut to such a surface; v2's per-vertex DEM fit plus
hard laws is what undulates. Author: session (Fable). Implementer: lane
`v2smooth`. Replaces the objective and the hard-law solve; keeps the
planar map, classification, shapes (08p), joints (08k/08r), routes,
structures, the emit path, the instruments.

## 1. The model

Unknowns: z at every planar vertex (as today). ONE sparse least-squares
problem (`scipy.sparse` + `lsqr`/`cg`, or HiGHS QP — the lane measures
both on CYXY and HECA and states the wall):

    minimise  Σ_bodies  w_bend · ‖ L z ‖²                (thin-plate bending, per connected pavement complex — L the cotangent/umbrella Laplacian on the planar triangulation of pavement faces, so bending is minimised in every direction and tangency holds across every shared edge: bodies that touch are one sheet)
            + Σ_runways w_chord · ‖ z_ridge − chord ‖²   (the threshold chord, per ridge station)
            + Σ_laws    w_law   · ‖ max(0, violation) ‖² (every law row of today's generators — grade caps, transverse, K, rate, no_step, crown, portions — as a ONE-SIDED quadratic penalty: a design target, not a bound)
            + Σ_zones   w_dem   · ‖ z − DEM ‖²           (ONLY on adjacent-ground / graded-strip zone vertices, weighted from 0 at the pavement edge to 1 at the zone's outer ring — the blend inside today's zone widths; beyond the outer ring the vertex is not an unknown: it IS the DEM)
            + Σ_roads   w_road  · ‖ L_chain z ‖² + law penalties (roads as smooth chains at their own caps, welded at their pavement contacts, ramping between levels; the ground between = DEM)
    subject to  z_pin = CIFP threshold  (equalities; and the flat-site datum on a flat site, 05k)
                joints: no bending term and no row across a joint (08k/08r-2; split vertices as today)
                structures: floors, rims, ramps as today (pins/targets on their rings)

No DEM term on pavement vertices. No hard grade law. No tiers, IIS,
relaxation, yield groups, ceilings, preference rows: `solve/relax.py`,
`stage1.py`, `variance.py`, `lexi.py`, `constraints/yielding.py` and the
`[relaxation]`/`[yield]` tables are DELETED (refuted machinery is not
kept gated). `constraints/*` generators stay as the SOURCE of law rows
(now penalties) — one code path for the generator, the penalty and the
verify reader.

Weights are law-table values in `emit.toml [design]` (`bend`, `chord`,
`law`, `dem_zone`, `road`), chosen so that on the CYXY/OTHH twins the
laws are met where the geometry allows (the penalty is one-sided and
strong) and a runway on a valley sits on its chord.

## 2. Datum and contacts

* Runway ridge: chord + vertical curve (K) targets; transverse and crown
  targets across; the runway is the senior sheet only through its pins
  and its chord weight — no tier.
* Taxiways, aprons, pads, roads inside them: the same sheet as whatever
  they touch (flush + tangent come from the shared Laplacian). An
  isolated body (no route, no touching pavement) is chained to the
  nearest pavement it touches by a road; a truly detached body's datum
  is its own DEM mean (one soft term on the body's mean).
* Joints (08k/08p/08r): the only discontinuities.
* Structures: as today (floors/rims pinned, ramps as chains).

## 3. What is deleted, what stays (consumer census, owner 30l — the
lane's table before editing)

### 3.1 The consumer census (lane `v2smooth`, 2026-09-08, before editing)

Every reader of a deleted block, found with `tools/blast.py` per file and a
repo-wide grep for the keys (`law_tiers`, `yielded_rows`, `relaxed_rows`,
`apron_over_preference`, `relaxed_by_04t1`, `yielded_by_08d`, `RELAXED_KEY`,
`YIELDED_KEY`, `solve_law_ordered`, `solve_relaxed`, `TierReport`) over
`src/`, `tools/`, `tests/` and `Sources/`.  **No Swift consumer exists** —
the app reads the engine's JSONL events and the patch, never these keys.

| Deleted block | Consumer | What it read | Ruling |
|---|---|---|---|
| `solve/tiers.solve_law_ordered` | `pipeline/build.py` (the solve call) | the solution + `TierReport` | replaced by `solve/design.solve_design` |
| `solve/tiers.TierReport` | `pipeline/build.py` `report["law_tiers"]`, `report.solve.{scope,demoted,failure}`, the `[v2] law tiers` log line | tier scope / demotions / named failure | deleted; `report["design"]` (residual per family) replaces it |
| `solve/tiers.row_tier` | `solve/relax.py` only (and its twins) | row tier | deleted with the file |
| `solve/relax.solve_relaxed` | `solve/tiers.py`, `solve/why.py` | the last-resort solve | deleted |
| `solve/stage1.py`, `solve/variance.py` | `solve/relax.py` only | the variance program | deleted |
| `solve/iis.diagnose` | `solve/highs.py`, `solve/relax.py` | the IIS on infeasible | deleted — the least-squares solve is never infeasible |
| `relaxed_rows` (sidecar) | `emit/osm_adapter.PUBLICATION_KEYS`, `verify/pads.py` (`pad_flat` reader), `tools/check_grade.py` (`law_context_from_sidecar`, `stamp_relaxed_rows`, heading `relaxed_by_04t1`), `tools/harness/census.py` | rows the last resort relaxed | never published again; the readers see the key absent and count every row law-true (their `or []` / `or None` paths) — no reader edit needed, and `verify/pads.py`'s relaxed-pad exemption goes with it |
| `yielded_rows` (sidecar + report) | `constraints/yielding.yielded_rows`, `pipeline/build.py`, `emit/osm_adapter.PUBLICATION_KEYS`, `tools/check_grade.py` (heading `yielded_by_08d`), `tools/harness/census.py` (`yielded_rows`, the summary line), `tools/v2_solve_replay.py` | rows a yielding family held above its cap | never published; same absent-key path.  The census now counts them in their families — that IS the owner's "the census reports, never blocks" |
| `apron_over_preference` (sidecar + report) | `constraints/apron.apron_preference_report`, `verify/within.apron_over_preference`, `pipeline/build.py`, `emit/osm_adapter.PUBLICATION_KEYS`, `tools/check_grade.py` (`_APRON_PREF_STATS`, `family_out["_apron_over_preference"]`), `tools/harness/census.py` | apron rows over the 1 % preference | generator side deleted; the verify reader and the census heading STAY (they read the built surface, §3) and simply report 0 rows over preference where none are published |
| `constraints/yielding.yield_rows` | `pipeline/shapes.shape_constraints` (the transform + the `yield.*` counts) | turned hard rows into preferences | deleted |
| `constraints/yielding.groundside_ramps` | `constraints/__init__.GENERATORS` (`groundside_ramp`) | a LAW generator, not yield machinery | MOVED to `constraints/groundside.py`, unchanged |
| `[yield] sliver_area_factor`, `groundside_ramp_max` | `planar/shapes.py` (the sliver merge, 08d-4a), `constraints/groundside.py` | shape-stage law, not yield machinery | MOVED to `[terrace]` (same values) |
| `[relaxation]`, `[yield]`, `[yield.families]` | `law/model.Relaxation`, `law/yield_schema.Yield`, `law/tables.{yield_law,yield_ceiling,yields}`, `law/model._check_cross_refs` | the tier / relaxation / yield tables | deleted, with `law/yield_schema.py`; `[design]` + `law/design_schema.py` replace them |
| `Diff.soft` / `Linear.soft` / `ceiling`, `Weights.preference/tier_ratio/tier_top`, `assemble.preference_weight` | `solve/assemble.py`, every generator that minted a preference (`apron`, `strips`, `runway_profile` crown, `seams`, `flat_site`) | the preference ladder | the FIELDS stay on the row dataclasses (generators keep minting them; the design solve reads a soft row's own `cap`/`hi` as its target and ignores the ceiling) — the LADDER is deleted |

Deleted: the LP tiers/last resort/yield machinery listed above, the
`law_tiers` report block, `yielded_rows`, `apron_over_preference` (the
census reports law rows as v1's does — a target missed is a row,
stamped `design_target`). Stays: every generator, every verify reader
and the oracle (they read the built surface; the owner reads the sim),
reach bands (as targets), the route graph (for contacts and reach),
shapes/joints, terraces, structures, rebake/seats, emit, sidecar
(`terrace_joints`, `axes`, `stretches` unchanged; the `law_tiers` key
replaced by `design`: the residual per family).

## 4. Twins (`tests/auto_patch_v2/test_v2smooth.py`)

A runway over a V-valley DEM sits on its chord (fill, not the DEM); a
taxiway leaving it is tangent at the edge (no kink: the second
difference across the contact ≤ the along-chain one); an apron over a
ridge is a minimum-curvature sheet (bending energy below the DEM's);
the graded strip blends to the DEM inside its zone width and the outer
ring equals the DEM; a physical-gap joint stays a step; a road ramps
between two apron levels at its cap; a law penalty is met where
feasible (CYXY's within_shape reads 0) and reported where not; the
solve is one call, no relaxation path exists.

## 5. Acceptance (ONE airport = HECA, then CYXY/OTHH/LEMD `--base-arm`)

HECA `build_airport.py HECA --engine v2` once: `tools/rwy_profile.py
--binned --compare` vs v1 (`/tmp/harness/HECA_20260908T073420.osm`:
bows −4.25 / −9.53 / −0.28; z−DEM +4.70 / −2.63 / +1.99), `tools/
patch_proximity_diff.py` vs v1 by role (the SW strips: v1 +4–5 m fill;
pav132: v1's 7–10 m cut), the owner's site and the neck (no step, the
grade), an UNDULATION read: per body the RMS second difference of z
along every chain and the max grade change per 100 m (v1 vs 1.0.295 vs
this — the owner's complaint in a number), the census (rows stamped
`design_target`), solve wall (bar: ≤ the 1.0.293 47 s — one sparse
solve), CYXY/OTHH/LEMD verify and their undulation reads. The sim read
is the acceptance; the KML of the three runway profiles is not needed —
the table is. Build-time statement.


## 6. Implementation record (lane `v2smooth`, 2026-09-08, branch `claude/v2smooth`)

Deviations and choices the lane REPORTS (they are not ruled here):

1. **The bending sheet includes the graded strip / clearance ground.**  §1
   names the pavement complex; a strip with no bending term is not a blend
   (measured: without it the strip's inner vertices float and the strip is
   dragged flat).  `solve/design.bend_roles` = every role that is not a
   STRUCTURE's; `pavement_roles` (the value, non-structure roles) is what
   the zone ramp measures its distance from and what never takes a DEM fit.
2. **A body's datum is its own terrain PLANE, not only its mean.**  §2 says
   a truly detached body sits at its own DEM mean; a mean alone leaves the
   TILT free under bending (a plane has zero bending energy, so the sheet
   still floats).  Every sheet no pin, chord or zone anchors — and every
   GROUNDSIDE body, which no route reaches — takes the least-squares plane
   of its own DEM samples at `detached_mean`.  A rigid `Flat` group is one
   column whose own bending rows collapse, so it takes the same datum on
   its members' DEM mean.
3. **The bank at the edge is not a design target.**  A law row with one foot
   on a vertex FIXED as the terrain (beyond the zone's outer ring) and one
   on the design surface reintroduces the per-vertex DEM pull answer 1
   removed.  Such rows are counted (`DesignReport.bank_rows`) and reported,
   never chased.  Without this the runway was dragged 8.5 m into a valley
   it was supposed to fill (the twin `test_runway_fills_the_valley...`).
4. **Roads fit `preferred_z` at `road`**, not at `chord`: the chord and the
   core's clamped road profile share the `preferred_z` channel, and only a
   runway-family vertex takes the chord weight.
5. **The active set is DAMPED** — a backtracking line search on the true
   objective, so `F` decreases monotonically.  The plain fixed point cycled
   (measured CYXY: `F` 2.9e5 -> 3.5e6 -> 2.9e5 over 40 rounds).
6. `[yield] sliver_area_factor` / `groundside_ramp_max` moved to `[terrace]`
   and `[relaxation] pad_slope_max` to `[within_shape]`: shape and pad law,
   never yield or relaxation law.  `solve.tiers.row_tier` moved to
   `constraints/precedence.py`: the law-order ATTRIBUTION, not the ladder.

Solver (spec §1 "the lane measures both and states the wall"), on the CYXY
and HECA captures, per-round LINEAR-SOLVER wall summed over the active set:

| method | CYXY | HECA | converges |
|---|---|---|---|
| normal equations + sparse LU (**chosen**) | 0.17 s | 1.3-2.4 s | yes |
| conjugate gradients on the normal equations | 0.33 s | 6.7 s | yes |
| `lsqr` on A | 6.1 s | 45.4 s | yes |
| HiGHS QP (the same problem with one slack per one-sided row) | **616.8 s, time limit reached, NO** | not attempted | no |

The HiGHS QP arm is 119k columns / 116k rows at CYXY alone; it did not
converge in 600 s where the chosen method answers the whole solve stage in
0.5 s.  HECA is four times the size and was not attempted.

## 7. Round 2 (RULINGS 2026-09-08v): the runway laws hard, the bending per class

### 7.1 The consumer census before editing (owner 30l), items 1 and 4

**Item 1 — the runway family's laws become CONSTRAINTS, and the DEFECT gate
reads the runway family only.**

| Consumer | What it reads today | Ruling |
|---|---|---|
| `solve/design.assemble` (the one-sided rows) | every law row as a penalty at `[design] law` | a row whose `Source.ruling` head is in `[design] hard_rulings` is a CONSTRAINT: priced at `hard_weight` with a multiplier shift, iterated to `hard_tol_m`.  A PREFERENCE among them (the end-zone cap, owner 2026-07-08) is hard AT ITS CEILING and keeps its preferred bound as the target: two sides, one row |
| `solve/design` bank filter (08t answers 2/3) | drops a law row with one foot on fixed terrain | UNCHANGED, and a dropped row is never hard — the bank stays lawful |
| `constraints/runway_profile` (the generator) | mints profile / crown / transverse / K / ring-chord / crossing rows, all one generator | UNCHANGED.  Hardness is by RULING, not by generator: the crown floor (a preference, M3a), the ring chords and the crossing feet — which price PAIRS the four hard laws already govern — stay targets.  Hard they were measured mutually unsatisfiable at CYXY (127/1432 ring chords missed by up to 0.77 m under the soft solve) |
| `verify/census.DEFECT_KEYS` | `pad_flat`, `runway_transverse`, `runway_vertical_curve` | `pad_flat` WITHDRAWN: a rigid pad's flatness is a target of the same solve as every other law, so a pad off its plane is a census row.  The gate reads the runway family only |
| `pipeline/build.py` (the `DEFECT` log + `report["verify"]["defects"]`) | `DEFECT_KEYS` | unchanged code, new (smaller) population |
| `tools/harness/build_airport.py` (`verify_defects`, "the app build would fail this airport") | `DEFECT_KEYS` | unchanged code; its comment now names the runway laws |
| `verify/pads.pad_flat` | reads the built pads | UNCHANGED — it still reports; only its DEFECT status is withdrawn |
| `verify/runway.runway_transverse` | measured against the NEAREST crown spine of ANY runway | REPAIRED to the vertex's OWN runway (05o §3, the generator's scope).  Measured at CYXY: 2 of 2 remaining DEFECT rows were a 14L/32R edge priced against 14R/32L's crown 196 m away — the two instruments were not twins |
| `verify/runway.runway_crown`, `runway_vertical_curve` | own-ref / declared drops already | unchanged |
| `solve/why.py`, `tools/v2_solve_replay.py` | the design report | unchanged (new fields only) |
| Swift (`Sources/SceneryKit`) | the JSONL events and the patch | no consumer: the app never reads a law family name |

**Item 4 — the `design` and `design_target` sidecar keys.**

| Consumer | What it reads today | Ruling |
|---|---|---|
| `pipeline/publication.publication` | the solve's pricing | `pipeline/build.py` adds `design` (the report) and `design_target` (one record per missed row: `family`, `miss_m`, the vertices' `ll`) where the report lives |
| `emit/osm_adapter.SIDECAR_KEYS` | the register a sidecar key must be in | both keys registered (a key outside it is refused at write time) |
| `tools/check_grade.SIDECAR_LAW_KEYS` | keys `run_checks` consumes as LAW | neither: nothing re-prices a row.  Under the design surface a missed target IS a census row, counted law-true in its own family |
| `tools/check_grade.SIDECAR_EVIDENCE_KEYS` | keys the census reports | both registered; `design_target_summary(patch)` is the reading (rows and worst miss per family) |
| `tools/harness/census.py` | the report and its headings | one heading, `DESIGN TARGETS (08t, ... counted law-true in their families)`, beside the yielded-rows heading it replaces |
| `tests/test_harness.py` (the classification twin) | every emitted key ∈ LAW ∪ EVIDENCE | passes with the two registrations; it is what makes a silently-ignored key impossible |
| `law_tiers` (the key `design` replaces) | deleted in round 1 | no reader remained |

**Dead law values deleted** (`blast.py` / grep: no reader outside their own
accessor): `rulesets.toml [common] runway_profile_smoothness` and
`runway_chord_fit` (with `law.tables.runway_chord_fit_weight`), and
`flat_site.toml [datum] weight` (with `law.tables.flat_datum_weight` and the
schema field) — all three were rungs of the preference LADDER round 1 deleted.

### 7.2 What was built

1. **The runway laws are held, not traded.**  `[design] hard_rulings` names
   the transverse maximum (05o), the vertical curve K (06b law 1) and the
   runway's max grade (the body cap, and the end-zone preference at its
   ceiling); the threshold pins were already equalities.  The rows are scaled
   to METRES (each divided by `Σ|c|/2`, so a K row's residual is metres of
   surface rather than a dimensionless grade change), priced at
   `hard_weight = 3e5`, and driven to `hard_tol_m = 0.02` by an outer
   AUGMENTED-LAGRANGIAN loop around the damped active set: the inner set runs
   to its fixed point with the multipliers held, then every violated runway
   row's multiplier rises by `ρ × violation` and tightens that row's target.
2. **The bending weight is per class** — `bend_runway` / `bend_taxi` /
   `bend_apron` / `bend_road` / `bend_strip`, each bending row priced by the
   senior class of its own vertex (`solve/design.bend_class`).
3. The twins: 33 red twins re-scoped, 0 deleted (§7.4).
4. The census stamp and the sidecar keys of §7.1.

### 7.3 Deviations the lane REPORTS (round 2)

7. **The hard rows are an augmented Lagrangian, not a KKT block.**  The
   exact saddle-point active set was implemented and measured FIRST: it
   CYCLED — CYXY, 40 rounds, ~40 rows entering and ~40 leaving every round,
   1.08 m still violated — because releasing every negatively-signed
   multiplier at once is not a convergent rule and releasing one at a time
   costs a factorisation per row.  The multiplier iteration converges to the
   same point and each round is the same sparse solve the objective already
   pays for.  Measured CYXY: `hard_weight` 3e4 → 0.036 m, 3e5 → 0.010 m,
   1e6 → 0.012 m, 1e8 → the factorisation breaks (the surface moves 500 m).
   The residual left is a metre-scaled violation, and both DEFECT readers
   carry their own envelopes above it (transverse `rounding_noise_m` 0.03 m;
   K `coarse_noise_m × (1/d₁ + 1/d₂)`, 0.1 m scaled) — so a held row can mint
   no defect row.  **This is a solver method, not a law change: state it in
   the ruling if the owner wants the exact program instead.**
8. **Hardness is by RULING, not by generator** (the census row above): the
   `runway_profile` generator mints six distinct laws and three of them are
   the census's own reading of pairs the four hard laws already govern.  The
   whole generator hard was measured mutually unsatisfiable.
9. **The hard rows are scaled to metres.**  Without it a K row's penalty was
   ~1/d² weaker than a transverse row's at the same weight and the K law
   never closed (CYXY: 0.0093 of grade change left at ρ = 3e6).
10. **`verify/runway.runway_transverse` was repaired** to the vertex's own
    runway (§7.1).  It is a VERIFY change inside a DEFECT family — reported,
    not decided.
11. **The undulation BAR of 08v is NOT met, and the mechanism the ruling
    assumed is refuted** (§7.5).

### 7.4 The 33 red twins (31 of 08v + two merge casualties)

All 33 RE-SCOPED to the 08t world; **none deleted**.  Three patterns:

* *"the census reads zero"* → *"the census REPORTS what the solve missed"*:
  the twin now reads the DELTA a hand-minted step adds over the design
  surface's own baseline, or the population lockstep between the two readers
  (`test_routes`, `test_pad_route`, `test_stretches` ×2, `test_taxi_route_pairs`
  ×2, `test_heca_read` strip, `test_v2ridge` ×2, `test_constraints` ×2).
* *"the solve holds it exactly"* → *"the runway family holds it"* (to
  `hard_tol_m`) where the row is a runway law (`test_runway_transverse` ×2,
  `test_heca_read` K, `test_rwy_xfall` ×2), else *"it is met to the census's
  own envelope"* (`test_v2ridge3`, `test_m4`, `test_m4b`, `test_v2lemd4`,
  `test_m3c_roads`, `test_crown`, `test_why` chain step).
* *the deleted machinery*: `iis`, `mode`, `yielded_rows`, `yield_family`,
  `solve.highs`, `solve.assemble.preference_weight`, `DEFAULT_WEIGHTS`,
  `Options(diagnose_iis=)`, `runway_chord_fit_weight`, `flat_datum_weight`
  (`test_v2shapes` ×4, `test_flat_site` ×4, `test_v2chord`, `test_why`
  relax, `test_v2wallcorridor`, `test_law_tables`, `test_v2smooth`).

Two twins lost a property that the design surface does not have, each with
its reason in place: the `why` CEILING (no single family moves the apron
further than all of them together — measured false: `taxi_chain` alone lifts
it 6.1 m where all of them settle it 3.9 m lower) and the `v2chord` lot's far
edge grading down to its own ground (with no pin, chord or zone anchoring
that fixture's airside sheet, the apron takes the sheet's own terrain plane
and sits under the lot).

### 7.5 The undulation sweep — the bar is NOT met (HECA capture, replay arms)

Every arm: `tools/v2_solve_replay.py --replay HECA.pkl --verify --emit`, then
`tools/undulation.py` on the emitted patch.  RMS second difference / p95
grade change per 100 m, by role; bows per runway; the runway DEFECT families
read ZERO in every arm below.

| arm | runway | apron | graded_strip | bows 05R/05C/05L | solve |
|---|---|---|---|---|---|
| **BAR (1.0.295)** | **0.00305 / 0.028** | **0.00803 / 0.199** | **0.03190 / 0.807** | — | — |
| round 1 (no hard rows) | 0.00637 / 0.111 | 0.01256 / 0.273 | 0.14082 / 1.138 | −0.07 / −2.18 / −0.00 | 4.5 s |
| **round 2, all bend = 1 (shipped)** | 0.00395 / 0.021 | 0.01276 / 0.262 | 0.14065 / 1.127 | −0.05 / −2.60 / −0.03 | 4.7 s |
| bend_strip 30 | 0.00423 / 0.025 | 0.01336 / 0.300 | 0.11057 / 1.015 | −0.37 / −2.58 / −0.03 | 4.0 s |
| bend_strip 30, bend_apron 5 | 0.00415 / 0.022 | 0.01366 / 0.293 | 0.11054 / 1.046 | −0.35 / −2.55 / −0.03 | 8.6 s |
| bend_strip 300 | 0.00411 / 0.025 | 0.01889 / 0.393 | 0.06729 / 1.014 | −1.20 / −2.57 / −0.04 | 3.5 s |
| bend_apron 20 | 0.00394 / 0.021 | 0.01278 / 0.269 | 0.14001 / 1.124 | −0.05 / −2.59 / −0.03 | 5.3 s |
| all up (rwy/taxi/road 30, apron 100, strip 1000) | 0.00401 / 0.026 | 0.02209 / 0.468 | 0.05262 / 0.987 | −1.75 / −2.52 / −0.04 | 15.2 s |
| dem_zone 1 (diagnostic) | 0.00408 / 0.021 | 0.01213 / 0.246 | 0.14808 / 1.150 | −0.05 / −2.60 / −0.03 | 4.4 s |
| law 30 (diagnostic) | 0.00358 / 0.015 | 0.01643 / 0.371 | 0.08857 / 1.055 | −0.01 / −0.53 / −0.00 | 2.6 s |
| chord 30 (diagnostic) | 0.00455 / 0.029 | 0.01103 / 0.240 | 0.14108 / 1.129 | −0.40 / −5.41 / −0.07 | 17.2 s |

What the sweep says, and it is a REFUTATION of the mechanism 08v assumed
("the bend weight trades pavement against strip — one weight for the whole
sheet"):

* The RUNWAY reaches the bar on p95 (0.021 vs 0.028) and is within 30 % of
  it on RMS (0.00395 vs 0.00305) — and it got there from the HARD LAWS, not
  from a weight: `bend_runway` moves it by ±5 %.
* The APRON is INSENSITIVE to `bend_apron` (20× the weight moves its RMS by
  0.2 %) and gets WORSE when the sheet around it stiffens.  Its read is of
  the emitted RING chains — the apron's boundary, where its neighbours,
  joints and law rows meet — not of its interior, which the bending term
  shapes.
* The STRIP responds to `bend_strip` only, and only by fighting the DEM fit
  its outer ring stands on (08t answer 3: at the outer ring the surface IS
  the terrain).  Every metre of strip smoothness is bought from the pavement:
  at `bend_strip` 300 the 05R/23L bow moves 1.15 m and the apron and taxiway
  roughen by 50 %.
* No arm meets the bar on all three roles, and the arms that come closest on
  one role miss the bows-within-1-m condition or roughen the others.

The lane therefore ships **all five weights at 1.0** — the mechanism, the law
knob and the measurement, with the surface unchanged from the hard-rows arm,
which is the best measured on pavement.  **The bar needs an owner ruling**:
either the strip's outer ring stops standing on the DEM (which amends 08t
answer 3), or the undulation read is taken per-role with the strip judged on
its own terms, or the bar is set from what a design surface with the runway
laws held can actually reach.

### 7.6 The closing builds (round 2)

**HECA `HECA_20260909T001908`** (`build_airport.py HECA --engine v2`, total
**132.25 s**, solve **4.91 s**, verify 19.65 s, 16,172 verify rows):

* the **runway DEFECT families read ZERO** (`runway_transverse`,
  `runway_vertical_curve`); the solve's own hard residual is 0.0184 m and it
  needed **no multiplier round** — the constraint weight alone put it inside
  `hard_tol_m`;
* bows (`rwy_profile --binned --compare` vs v1 `HECA_20260908T073420`):
  **05R/23L −0.04** (v1 −4.25, round 1 −0.04), **05C/23C −2.14** (v1 −9.53,
  round 1 −1.81), **05L/23R +0.01** (v1 −0.28, round 1 +0.01) — every bow
  within 0.33 m of round 1's;
  z−DEM mean +6.70 / +1.35 / +1.36 (v1 +4.70 / −2.63 / +1.99); max grade
  change 0.08 / 1.36 / 1.40 %/100 m (v1 1.71 / 1.90 / 1.42);
* the undulation read (RMS 2nd difference / p95 per 100 m):

  | role | v1 | 1.0.295 (the bar) | round 1 | **round 2** |
  |---|---|---|---|---|
  | runway | (no runway way) | 0.00305 / 0.028 | 0.00637 / 0.111 | **0.00395 / 0.021** |
  | apron | 0.06627 / 0.798 | 0.00803 / 0.199 | 0.01256 / 0.273 | **0.01276 / 0.262** |
  | graded_strip | 0.28669 / 1.378 | 0.03190 / 0.807 | 0.14082 / 1.138 | **0.14065 / 1.127** |
  | overall | 0.21171 | — | 0.10 | **0.07979** |

* the owner's site 30.1139552,31.4095465 and the neck 30.127729,31.412022:
  **no step** (max step over a short edge 0.00 m at both, 45 m radius);
* census (`--no-cache`): LAW-TRUE 42,773, adjudicated 4,726 (airside 4,659),
  with the new heading — `DESIGN TARGETS (08t) ... taxi 3,099 (max miss
  3.719 m), no_step 2,904 (1.592), apron 2,875 (1.040), ... runway_profile
  141 (0.764)` — the rows counted law-true in their families.

**The base arms** (`--base-arm`, this tree):

| airport | verify rows (round 1) | runway DEFECTs | solve | rounds | undulation runway / apron / strip |
|---|---|---|---|---|---|
| CYXY | 505 (1,129) | **0** (was 7 + 9) | 1.55 s | 205 + 5 multiplier | 0.01189 / 0.00798 / 0.03360 |
| OTHH | 24 (14) | **0** | 5.43 s | 20 | 0.00166 / 0.00000 / 0.00999 |
| LEMD | 304 (3,805) | **0** (was 3) | 8.87 s | 74 | 0.00178 / 0.00695 / 0.05683 |

LEMD's active set now SETTLES in 74 rounds (round 1 hit the 200-round cap),
and its hard residual is 0.0048 m at multiplier round 0.

## 8. Round 3 (RULINGS 2026-09-09b (2)(3)(4)): taxiways like runways, the
## adjacent ground as a law surface, the 5 % ceiling — lane `v2ground`

Owner's read of 1.0.296: taxiways still undulate; the adjacent ground must
be a LAW surface, never the DEM; all pavement caps at 5 % (roads 8 %).

### 8.1 The consumer census BEFORE editing (owner 2026-08-30l)

Every reader found with `tools/blast.py` and repo-wide greps for the keys
(`dem_zone`, `dem_fixed`, `bank_rows`, `_zone_weights`, `beyond_zone2`,
`strip_transverse`, `pavement_max_grade`, `road_max_grade`) over `src/`,
`tools/`, `tests/` and `Sources/`.  **No Swift consumer exists**: the app
reads the engine's JSONL events and the patch, never a law key or a
design term.

**Item 3 — the DEM leaves the patch (the deleted keys).**

| Deleted / changed | Consumer | What it read | Ruling |
|---|---|---|---|
| `emit.toml [design] dem_zone` (the weight) | `law/design_schema.DESIGN_TERMS`, `Design.dem_zone`, `check_design`; `solve/design.assemble` §7; `tests/auto_patch_v2/test_law_tables.py` (the term list), `test_v2smooth.py` ×2 | the DEM fit on zone vertices | DELETED — the term, the field, the TOML key and the rows.  The two twins are re-scoped to assert the term is GONE (a `dem_zone` row exists for NO vertex) |
| `Base.dem_zone_vertices` / `size_out["dem_zone_vertices"]` | `solve/design.solve_design`, `tools/v2_solve_replay.py` (prints the size dict generically) | how many zone vertices took a DEM fit | DELETED; the replay's print is dict-generic and needs no edit |
| `_zone_weights(...) -> (ramp, beyond)`; `_Reduction.dem_fixed` | `solve/design.assemble` (the reduction's `fixed_dem`, the ANCHORED test, the BANK filter), `solve/rows._reduce` | the vertices beyond the zone's outer ring, FIXED at the DEM | The `beyond` half is DELETED (09-09b (3): "the outer ring's elevation is whatever those laws give — the mesh engine blends from the patch boundary to the DEM outside it").  `_zone_weights` returns the ramp only, now used ONLY to decide whether a sheet is anchored.  `_Reduction.dem_fixed` stays as an (always empty) field so `_reduce`'s signature and the bank filter keep one code path; `DesignReport.bank_rows` therefore reads 0 and the spec §6 deviation 3 (the bank filter) becomes vacuous — its motivating failure (the runway dragged into a valley by a row footed on fixed terrain) cannot occur when no vertex is fixed terrain |
| `zones.toml [adjacent_ground] beyond_zone2 = "dem"` | `law/model._DATUMS` (the value check) | zone 3 is the DEM | KEPT, comment amended: zone 3 is the ground OUTSIDE the patch, which the mesh engine drapes; inside the patch no vertex is the DEM |
| `DesignReport.bank_rows` | `report["design"]`, the `[v2] design` log line, `tools/v2_solve_replay.py` | rows dropped as bank rows | kept, reads 0 |
| the DEM's REMAINING entries | — | — | the threshold pins (`Pin`), the tile-seam DEM preference (`constraints/seams.py` — the neighbouring tile's own surface, out of 09-09b's scope), the detached body's own terrain PLANE (`_plane_targets`, ruled), and the core's clamped ROAD profile (`airport/road_profile.py` through `preferred_z`, owner 04t) |

**Item 2 — the taxi design profile and the one-way strip tie.**

| Consumer | What it reads today | Ruling |
|---|---|---|
| `solve/design.assemble` §5 (road chains) | `taxi_centerline` is NOT read; only `road_centerline` breaklines carry a chain-bending term | a second-difference DESIGN PROFILE row per interior station of every `taxi_centerline` breakline at `[design] taxi_profile` — the runway K pattern as an objective term |
| `constraints/taxi.taxi_chain` (LATERAL hops) | mints `|z_v − z_foot| ≤ cap·d` — a one-sided TARGET pair | UNCHANGED.  A new generator `taxi_follow` mints, over the SAME route-graph hops on taxi-family faces, the EQUALITY `z_v − z_foot = 0` priced at `[design] taxi_transverse` (`[design] generator_weights`) — the ring follows its centreline, as a runway's ring follows its crown |
| `constraints/zones.strip_transverse`, `zones.zone_bands` | two-way rows coupling a GROUND vertex to a PAVEMENT edge foot | the rows now carry `Linear.follows = v` (the ground vertex).  `solve/design` prices such a row ONE-WAY: the leader (pavement) terms leave the matrix and enter the right-hand side at their PREVIOUS outer-round value, so the ground follows the pavement and never pulls it.  The row's own violation reading, the census and the verify readers are unchanged (they read the built surface) |
| `model/constraints.Linear` | `terms/lo/hi/source/soft/ceiling` | one optional field `follows: int | None = None`, defaulted — every existing construction site is unaffected |
| `verify/strips.py`, `tools/check_grade.py` (`strip_transverse`, `adjacent_ground_tear`, `strip_seam_tear`) | the BUILT surface | unchanged; they report what the one-way law produced |

**Item 4 — the 5 % ceiling.**

| Consumer | What it reads today | Ruling |
|---|---|---|
| `rulesets.toml [common]` / `law/model.CommonLaw` | `apron_fan_ramp_max`, `road_transverse_axis_min_deg`, `runway_crown_transverse`, `vertical_curve_k_grade_unit` | two new fields `pavement_max_grade = 0.05`, `road_max_grade = 0.08` (`_build` is field-driven: adding a field and a key is the whole change) |
| the per-class letter caps (`common.roles.*`, `icao.taxi.longitudinal`, …) | one-sided targets in the design solve | UNCHANGED — they stay targets under the ceiling |
| `constraints/__init__.generate` post-passes (`seam_exempt`, `reconcile_datums`) | rows after every generator | a third post-pass `ceiling.pavement_ceiling(rows, planar, law)`: for every DIFFERENCE row of the set (a `Diff`, or a `Linear` of the point-vs-interpolated-point form) whose every vertex belongs to a non-structure VALUE face, one TWIN row at the ceiling — `road_max_grade` where every vertex is road-family only (a free road), else `pavement_max_grade`.  Counted as `pavement_ceiling` |
| `emit.toml [design] hard_rulings` | the ruling heads whose rows are hard | the ceiling's own head joins it, so the ceiling is enforced in the ACTIVE SET beside the runway rows |
| `verify/*`, `tools/check_grade.py`, `tools/harness/census.py` | the per-class caps | no new family: every class cap is STRICTER than the ceiling, so a 5 % breach is always already a `within_shape` / `taxi_box` / `lateral_contiguity` row.  The ceiling's validator twin is the class reader that already reports it |
| `verify/census.DEFECT_KEYS` | the runway families | UNCHANGED — the ceiling is not a DEFECT family (08t (4): the census reports) |
| `solve/why.py`, `tools/v2_solve_replay.py` | the design report | unchanged (counts only) |

### 8.2 What was built

1. **`[design] taxi_profile = 300`** — one second-difference row per
   interior station of every `taxi_centerline` breakline (HECA: 1,941
   rows over 341 chains), the runway K pattern read as an objective term
   (`solve/design.assemble` §5b).
2. **`[design] one_way_rulings`** — the zone corridor and the strip tie
   are priced ONE-WAY: `Linear.follows` names the ground vertex, the
   solve keeps only that column in the matrix it factorises and the
   pavement feet enter the right-hand side lagged, under-relaxed at
   `one_way_relax = 0.5` for `one_way_max_rounds = 3`.
3. **The DEM has left the patch**: `[design] dem_zone` and the
   beyond-the-outer-ring DEM FIXING both deleted (HECA: 5,046 vertices
   freed, `dem_fixed` 0, `bank_rows` 0).
4. **`[common] pavement_max_grade = 0.05` / `road_max_grade = 0.08`**,
   hard in the active set through `constraints/ceiling.py` (HECA: 42,928
   twins, 91,630 hard one-sided rows).

### 8.3 Deviations the lane REPORTS (round 3)

12. **The RING-FOLLOWS-CENTRELINE target is REFUTED and DELETED.**  09-09b
    (2)'s "its ring vertices follow the centreline transversely" was first
    built as its own generator (`taxi_follow`: the equality `z_ring =
    z_foot` over the route graph's lateral hops, priced at its own weight
    through a `[design.generator_weights]` table).  Measured on the HECA
    replay: it bought 5-12 % of the taxi roles' RMS second difference
    (primary_parallel 0.00945 -> 0.00828) and cost **0.35 m of the 05R/23L
    bow and 34 % of the RUNWAY's own RMS** (0.00269 -> 0.00361), even with
    the runway's own vertices excluded from the rows.  Deleted with the
    `generator_weights` machinery (BUILD ECONOMY: a refuted mechanism is
    deleted, the record is the spec and git).  The ring follows its
    centreline through the transverse hop LAW, which is already a design
    target, and through the centreline's own `taxi_profile`.
13. **The lag and the multiplier loop are SEQUENTIAL, not interleaved.**
    Interleaved, each lag round undid the previous multiplier round and
    the runway laws drifted OUT (measured HECA: a 0.52 m
    `runway_transverse` DEFECT, the violation rising 0.028 -> 0.040 ->
    0.063 m across rounds).  Phase B runs the lag to settlement, phase C
    the multipliers with the lag frozen, and phase C stops on a round that
    buys less than one tolerance (measured: rounds 4 and 5 cost 8 s and
    made the worst row worse).
14. **The ceiling is LOCAL** — a twin only over a span shorter than
    `emit.within_shape.withdrawn_chord_min_m` (30 m).  Over a longer span
    the grade is read along the ROUTE, never across the chord (05aa).
    Without the limit the pass mints 201k twins (the no-step route-window
    pairs), the solve's wall triples and the built grades do not change.
15. **The lag does not settle at HECA / CYXY / LEMD** (worst leader move
    0.37 / 0.34 / 0.70 m after 3 rounds; OTHH settles in 2 at 0.001 m).
    Reported in `DesignReport.one_way_*` and on the `[v2] design` line —
    the convergence guard reports rather than claiming convergence.
16. **The hard set does not settle at HECA / CYXY / LEMD** (0.030 /
    0.055 / 0.023 m against `hard_tol_m` 0.02).  The residual is on the
    CEILING rows, never the runway family: the runway DEFECT families read
    ZERO on all four airports, and the census reports 5 `pavement_ceiling`
    rows at HECA missed by at most 0.030 m.

    **CORRECTED 2026-09-12 (owner RULINGS 2026-09-12u, §30; lane
    `v2padceiling`).** LEMD's figure was WRONG BY TWO ORDERS: the shipped
    `v2ramp8` LEMD solve violated **725** hard rows at **1.3037 m**, not
    0.023 m — 365 pad-slope ceiling, 357 pavement ceiling, 3 runway (at
    the 0.020 bar the projection holds).  Two readings hid it: the
    reported `hard_active` was phase C's MULTIPLIER count (1,457), not
    the violated rows, and the number quoted here was read before that
    was fixed (§30 (3b)).  The class was also NOT "the ceiling rows'
    small residual": it was a MUTUALLY INFEASIBLE PAIR of hard rows —
    an authored −2.20 m of object relief in the pad's 1 % CEILING against
    the 5 % pavement ceiling over 3.0 m of apron.  With §30 (1) + (2)
    landed, the same offline arm settles: **0 violated rows, worst
    0.0130 m** (matched arms on one capture, `HARD SET SETTLED`).  HECA's
    and CYXY's figures stand as written and are UNMEASURED under §30 —
    no build was paid for them this round (BUILD ECONOMY: one airport).

### 8.4 THE FINDING that needs an owner ruling: the mesh does NOT blend

09-09b (3) rests on "the engine should automatically smooth between
whatever elevation we set and the DEM".  **Measured, and it does not.**

With the outer-ring DEM fixing deleted, HECA's ground vertices stand a
mean **3.04 m** (p95 8.92, max 16.60) off their DEM sample at the patch
boundary ring, where 1.0.296 stood 0.03 m off.  The same tile meshed twice
through `tools/run_tile_mesh_only.py 30 31 1 --patches-as-is`, one
transect at lon 31.3819142 (0.00005 deg = 5.6 m per station):

| lat | this patch | 1.0.296 patch |
|---|---|---|
| 30.11635 (28 m outside) | 66.876 | 66.876 |
| 30.11660 (6 m outside) | 66.133 | 66.133 |
| 30.11665 | **61.154 (-4.98 m)** | 66.062 |
| 30.11670 (the boundary) | **49.345 (-11.81 m)** | 65.847 |
| 30.11675 (inside) | 49.396 | 65.574 |

A **16.8 m drop over ~11 m of ground** — a vertical cliff, one triangle
wide — where the control transect falls smoothly (66.13 -> 62.32 over the
same span).  Ortho4XP's mesh drapes the DEM right up to the patch's
constrained boundary; there is no blend band outside it.  The graded
strip's DEM ramp was the blend (08t answer 3), and 09-09b (3) removed it.

Consequently the STRIP's undulation improves only where the DEM under it
was rough (HECA 0.1407 -> 0.0275) and REGRESSES where it was smooth
(CYXY 0.0336 -> 0.1289, OTHH 0.0100 -> 0.0233, LEMD 0.0568 -> 0.0636).

The owner rules between: (a) the zone-2 outer ring keeps a DEM datum
(08t answer 3 restored, the blend inside the graded strip); (b) the mesh
engine gains a blend band outside the patch boundary; or (c) the cliff is
the "bank at the edge" 08t answer 2 accepts and stands.  The lane changed
nothing on its own judgement.

### 8.5 AMENDMENT — THE TAXI BODY'S DATUM (owner RULINGS 2026-09-10p, closing the 10o attribution; lane `v2taxidatum`)

§8.2 (1) gave every taxi centreline a design PROFILE — a second-difference
row with RHS 0.  That is curvature, and curvature has no level: 10o
measured CYXY's 1,664 m parallel `pav28` extrapolating its level from its
far contact at the apron end while the ground rose 694 → 696.4 m under it
(z − DEM median −6.17 m, min −10.05, "held by bending alone").

**The datum roles are now the APRON family AND the TAXI family**
(`solve/design.datum_roles`, replacing the apron-only `apron_roles` at the
row builder).  A TAXI BODY is a connected group of taxi-family faces —
faces sharing a vertex, `_role_bodies_faced` exactly as an apron body is
formed — and the two families are SEPARATE partitions: an apron face and a
taxi face that touch stay two bodies on two terrain means.  A runway face
is never in a taxi body (its role is not in the set), so a taxi body may
TOUCH a runway without joining it.  Each such body carries the SAME ONE
weak row apron bodies carry (§14): its mean z against the mean production
DEM under its own vertices, weight `[design] body_datum`, membership from
the shape partition (09v), accumulated into the low-rank term (09r (1)),
never per vertex.  The RUNWAY family stays excluded — its threshold chord
and pins are its datum — its contacts stay hard, and the final projection
(§16) absorbs any conflict into the body's non-runway vertices.

The report gains `taxi_datum_rows` and `body_datums`: one record per datum
row — `kind` (apron / taxi), the body's `ll` identity, its vertex count,
its MEAN DEM and its solved RESIDUAL — and the `[v2] design` line names
the three worst taxi residuals with their means.  Twins:
`tests/auto_patch_v2/test_v2taxidatum.py`.

### 8.6 AMENDMENT 2 — THE CHAIN'S TREND AND THE BODY'S PLANE (owner RULINGS 2026-09-10v, REPLACING §8.5/10p; lane `v2taxidatum` round 2)

§8.5 gave every TAXI BODY one mean row.  10v measured it as too coarse: a taxi
body is the whole connected taxi NETWORK (CYXY: ONE 853-vertex body), so one
mean is an airport-wide level that cannot fix a local tilt, and the level it
imposed over 700–705 m of ground RAISED HECA's taxi curvature.  Three rules
replace it.  **The ground enters pavement only through long-wave trends and
body planes — never per vertex (08t (1)).**

1. **Every taxi CENTRELINE CHAIN carries a TARGET PROFILE.**  The ground's
   long-wave trend along that chain — the §21 construction, the SAME helper
   (`constraints/trend.py`, factored out of `runway_chord.py`) at the SAME
   window key `[design] runway_profile_window_m` — shifted LINEARLY through
   the chain's runway contacts (`shift_through`; unshifted where it touches
   none, piecewise-linear between several).  Derived in
   `constraints/taxi_trend.py`, published as `PlanarMap.taxi_trend_z` (its
   own channel: `solve` imports `law` and `model` only), priced per free
   chain vertex at the NEW weak weight `[design] taxi_trend` = **30** — below
   `body_datum` (300).  A runway-contact vertex takes NO trend row: the
   runway owns it and the contact stays hard and flush.  The chain's
   second-difference rows (`taxi_profile`) stay: the trend says WHERE the
   chain runs, the curvature row HOW SMOOTHLY.
   The trend's fit DEGREE is bounded by what its samples resolve (quadratic
   only where they span at least half the window, else a line): through four
   points 40 m apart a quadratic is interpolation, i.e. the per-vertex pull
   again.  Implementation choice of the same kind as 10x's tricube kernel.
2. **An APRON body's datum is the DEM's AFFINE fit.**  THREE weak rows at
   `body_datum` (`solve/rows._plane_rows`): the mean and the two FIRST
   MOMENTS, Gram-Schmidt-orthogonalised in the body's own centred plan frame
   and each scaled by its RMS half-extent, so satisfying all three IS
   reproducing the least-squares plane of the DEM under the body — level AND
   tilt — and every residual reads in METRES.  A plane has zero bending
   energy, so the datum never fights the designed shape within the body.
   TAXI bodies carry no datum row at all (rule 1 is their level).
3. **The within-shape apron rows are STATIONED across the face.**
   `apron_body_chord_max_m` is a chord LENGTH, not a coverage limit: a body
   chord past the gate used to get no row, so SPJC's 85.3 m / 5.46 % path
   was unpriced.  It is now priced at the apron cap over its own distance
   (`constraints/apron.py`, ruling `apron body chord, stationed across the
   face`); the 05ae face cover still applies.

Consumer rows touched (the §21.3 table's frame): the census `within_shape`
family — UNCHANGED, `verify/within.py` keeps the law's own 60 m gate, so v2's
reading still agrees with v1's (`test_cyxy_verify_matches_v1_census` green);
the design surface aims PAST what the census counts.  `solve/why.py` — its LP
now publishes `taxi_trend_z`, so a vertex held by its trend no longer reads
"held by bending alone"; it still does NOT publish `preferred_z` (a
pre-existing gap, §21's ground, reported not fixed).  The sidecar `design`
block gains `taxi_trend` (per chain: length, vertices, pins, target RMS/max,
mean z − DEM), `taxi_trend_rows`, `body_datum_bodies`, and `tilt_m` on every
`body_datums` record.  Twins: `tests/auto_patch_v2/test_v2taxidatum.py`.

### 8.6.1 AMENDMENT 3 — THE WHOLE FACE, NOT ONLY ITS SPINE (lane `v2taxidatum` round 3)

§8.6 (1) priced the trend on the CENTRELINE row alone, so a taxi body's
off-centreline vertices carried no binding at all (`why`: "binding 0 — FREE")
and the edge lagged where the ground rose across the body's width: CYXY's
`pav28` read **−1.80 / −1.93 m** against the DEM at the 320 / 330 m stations
of the owner's 10n transect while its centreline sat inside ±0.9 m.

**Every vertex of a taxi-family face carries the SAME row at the SAME weight**
(`[design] taxi_trend` = 30), its target the chain's trend value at the
vertex's OWN STATION — the foot of its perpendicular on the chain. One value
per vertex, the same the centreline gets there: the cross-section's SHAPE
stays the transverse law's, which is senior, and the `taxi_profile` curvature
rows are untouched. Two bounds, both MEASURED (CYXY `taxi_box` short-pair rows,
v1 oracle / v2 verify, control 6 / 6):

1. **A chain speaks only for the FACES IT OWNS** — the taxi-family faces most
   of whose chain vertices are its own (`Breakline.ref` is the apt.dat
   centreline record `taxi57`, `Face.ref` the pavement `pav28`, so the map's
   own I5 incidence is the join, never a name). A FOREIGN chain projects the
   wrong direction: valuing a stub's face from the long parallel it meets
   spreads that parallel's STATION gradient across the stub's width. Nearest
   long chain over every taxi vertex **22 / 36**; every face the chain merely
   TOUCHES **34 / 47**; the faces it OWNS **22 / 30**.
2. **Only a LONG chain speaks across a face** — its stations must span at
   least half `runway_profile_window_m`, the same test `Trend.at` puts on the
   fit's DEGREE. A short chain's trend is a line through 100 m of ground, and
   sideways it asserts a level cross-section over ground it never sampled. On
   the §8.6 stub fixture the 101 m junction stub's two side vertices, handed
   its own flat trend while the apron beside them leaned with the ground,
   pulled the junction 0.63 m down and bent the 1 km parallel **3.78×** its own
   vertical-curve bound. Bounded, the same build reads 0.009 m of chain
   residual (control 0.097) at 0.010× the bound (control 0.065).

A vertex the taxi face SHARES with another VALUE surface (a runway contact, an
apron edge) takes no trend row: two authorities on one vertex is the
`emit consensus mints violations` class. `[design] taxi_trend_face_reach_m`
(250 m) is a BACKSTOP on how far a chain may reach inside a face it owns, not
the scope — CYXY's `pav28` is 160 m wide at the owner's transect, so at 75 m
the far edge took no row at all.

**MEASURED (patch-only, harness, v2 engine).** CYXY transect at lat 60.71363
east of the runway: every station past the zone ring inside ±1.5 m — 170 m
+1.36, the owner's point (200 m) +0.99, **320 m +0.15 and 330 m +0.04**
(round 2: −1.80 / −1.93); the 1.5 m internal drop at 250→270 m is gone. SPJC
kept: taxi `pav49#22` −0.18 m, terminal apron path 0.38 % (round 2 0.59 %).
HECA per-role undulation against the merged control — `primary_parallel`
1.047 → **0.936**, `stub` 1.027 → **0.831**, `cross_connector` 0.967 → 1.015,
but `junction` 1.084 → **1.128** against a 1.05 bar: MISSED, and the second
arm the brief named (the apron datum's TILT rows at half `body_datum`)
REFUTES its own hypothesis — junction 1.160, `taxi_box` 30 → 33 — so that knob
was not kept. CYXY `taxi_box` reader agreement (`test_cyxy_verify_matches_v1_census`)
stands RED at v1 22 / v2 30 (control 6 / 6, tolerance 4.4): the same class
round 1 reported at v1 22 / v2 28 — when a taxi body follows its ground, its
own short-pair box rows appear. Not widened.

### 8.7 AMENDMENT 4 — THE APRON FOLLOWS THE GROUND'S 2-D TREND (owner RULINGS 2026-09-10ar; lane `v2aprontrend`)

§8.6 (2) gave an apron body THREE affine rows. 10ar measured what a plane leaves
open: over LEMD's 439 × 1,242 m T4S body it has no LOCAL REACH, so the pit corner
sat 1.2 m under its own DEM and the sheet fell 0.79 m over the last 23.8 m into
it — the 1-D chain's "right mean, no tilt" defect (10t) one order up.

1. **An APRON body targets the ground's 2-D LONG-WAVE TREND at every vertex.** A
   moving QUADRATIC SURFACE least-squares fit of the production DEM —
   `[1, u, v, u², uv, v²]` in the query's own centred plan frame, TRICUBE-weighted
   over radius `[design] runway_profile_window_m`, the fit's value AT the query
   (`constraints/surface_trend.py`, the 2-D sibling of `trend.py`; the 1-D
   construction is untouched). Samples are the production DEM under the body's OWN
   vertices, averaged per `window/10` cell — the 2-D analogue of `trend_of`'s
   per-station averaging, and what makes the fit affordable over thousands of
   vertices. The DEGREE is bounded by what the in-window samples resolve
   (quadratic only where they span at least half the window, else the plane, else
   their weighted mean) — the same bound `Trend.at` puts on the 1-D fit, for the
   same reason: through a handful of near points a quadratic is interpolation,
   i.e. the per-vertex DEM pull 08t (1) removed.
2. **The replacement rule is the body's EXTENT.** A body whose plan DIAMETER
   exceeds the window takes ONE trend row per vertex at the new weak weight
   `[design] apron_trend` (30, `taxi_trend`'s price) and NO affine rows: over more
   than one window a plane cannot speak locally. A body at or under the window
   keeps its three `body_datum` rows unchanged — inside one window the trend IS
   its plane to the fit's own precision, and three rows are cheaper than N.
   Derived in `constraints/apron_trend.py`, published as `PlanarMap.apron_trend_z`
   (its own channel, like `taxi_trend_z`); `solve/design.py` drops the plane rows
   of any body a published target touches, so ONE gate decides both.
3. **Unchanged:** pads (10y/10ah — a `pad_level` vertex takes no trend row, as it
   takes no datum row), rims (`structures.rim_level`, 10ar), the within-shape
   apron rows (§8.6 (3)), the taxi trend (§8.6.1), every hard law. A vertex the
   apron shares with the RUNWAY family takes no trend row (the runway owns it),
   nor does one already carrying a `taxi_trend` row (two authorities on one vertex
   is the `emit consensus mints violations` class).

Consumers touched: `pipeline/why.py` publishes `apron_trend_z` before its LP, so an
apron vertex held by its trend no longer reads "held by bending alone";
`solve/design_report.py` — the design line and the sidecar `design` block gain
`apron_trend` (per body: vertices, diameter, target RMS/max, mean z − DEM) and
`apron_trend_rows`, `body_datums` records only the bodies that KEPT their plane, and
`airport/load.py` gains `report.load.apron_trend` (coverage, fit wall); the census law
families are UNCHANGED (no law row moves).

### 8.7.1 MEASURED (lane `v2aprontrend`, branch `claude/v2aprontrend`) — the weight is 30 and the LEMD bar is MISSED at the cap

Four patch-only arms against `--base-arm` controls at main `2fb83ce3`; DEFECTs
(`verify.census.DEFECT_KEYS`) **0** on all eight.

**LEMD T4S (the site).** `pad_level_report transect` from `pav16`'s ring node
(v21431) to the rim vertex v21785, 23.8 m, on `v2_solve_replay --solved-out`
arms of ONE capture — the instrument 10ar's number was read on, with the
replay fixed first: it published NEITHER `taxi_trend` NOR `apron_trend`, so
two arms of this round came back byte-identical (`_targets`, now the build's
own order). Control **−0.972 m**, arm **−0.432 m**; max 1 m station step
0.042 → **0.019** (bar 0.05 MET); the apron corner's z − DEM −0.96 → **−0.66**.
The 0.10 m bar is MISSED, and the WEIGHT IS NOT THE KNOB: `apron_trend` 30 →
100 → 300 reads −0.432 / −0.384 / −0.339 and saturates (two iterations, the
attempt cap). `why` on v21785 (duals): the only binding row is `rim_level`
(dual 166); the chain to the terminal runs v21785 → v21779 → v21778 → v21748
with the fall split **`pad_frontage_level` +1.30 m**, `apron_preference`
(1 % × 44 m) +0.45, `rim_level` +0.08 — i.e. what is left of the T4S fall is
the BUILDING PAD's frontage level (10l/10y) pulling the apron's last hops
down, not the body datum this round replaced. Reported, not iterated.
Adjudicated 555 → 584.

**HECA** (undulation RMS 2nd difference, arm/control): apron **0.987×**,
junction **0.965×**, cross_connector 1.001×, primary_parallel 0.987×, stub
0.986× — every role ≤ control (cross_connector's excess is 1.7e-6 in the RMS
itself, under materiality), and the 10aj junction residual is paid.
Bows unchanged: 05C/23C −3.58 (control −3.55), 05L/23R −1.74 (−1.73).
Adjudicated 6096 → 6264.

**SPJC** the terminal apron `pav40` (the 10t body), `patch_transect` 200 m of
covered path: arm **0.37 %** end-to-end (control 0.91 %), worst 10 m station
3.2 % (control 3.4 %) — bar ≤ 1.5 % MET; its z − DEM |0.04–0.98| where the
control runs to −2.19. The taxi at −12.0284851, −77.1128014: **−0.14 m**
(bar ±1.5 MET), unchanged from control. Adjudicated 262 → 275.

**OTHH** is NOT byte-identical (`dc136a7383d8` vs `f340732abaf1`): 6 bodies
exceed the window even on its flat site. Quoted per the bar — row-side 382 of
19,959 nodes moved > 0.01 m, worst **0.21 m**; solve-owned 45 of 13,268,
worst **0.010 m**; 0 welded to the road family. Adjudicated 4 → 15 (14
groundside, 1 airside).

## §9 THE BANK and THE PAD PLANE (RULINGS 2026-09-09e / 2026-09-09c)

### 9.1 What is being added

**THE BANK (09e).**  §8.4 measured that Ortho4XP's mesh does not blend:
it drapes the raw DEM up to the patch's constrained boundary, so the
patch's outer ring stands mean 3.04 m (max 16.60) above open ground and
the transect reads a 16.8 m cliff one triangle wide.  The owner's answer
is a BANK: outside every patch-boundary ring the patch emits a **bank
foot** ring on the DEM at plan distance

    d = max(bank_min_width_m, |z_ring - DEM(foot)| / bank_slope)

along the outward normal, with `[design] bank_slope = 0.33` (1:3) and
`bank_min_width_m = 5.0`.  The foot's z IS the DEM at the foot.  The
foot chain carries a second-difference smoothing target along itself
(`[design] bank_foot_smooth`) so the toe does not zigzag.  Where the
foot would cross another patch ring it stops at that ring (the two
rings share the bank).  **No vertex is emitted between ring and foot:**
the bank face is the mesh's.  That works because `include_patches`
polygonizes every closed patch way and seeds each resulting face
INTERP_ALT (`O4_Vector_Map.py:2868`), and `O4_Mesh_Utils.
interpolate_free_interior_altitudes` then harmonically extends the two
rings' authored altitudes across the annulus — a straight bank on a
planar boundary, smooth elsewhere, and continuous with the DEM outside
the foot because the foot IS the DEM.

**THE PAD PLANE (09c).**  A pad is currently a `Flat` group, which
`solve/rows._reduce` merges into ONE column: a pad is exactly flat and
everything welded to it is dragged to that level.  The owner rules the
flatness a strong TARGET (`[design] pad_flat`) with a HARD 1 % ceiling
on the plane's tilt (`emit.within_shape.pad_slope_max`, in
`[design] hard_rulings` beside the runway rows and the 5 % pavement
ceiling).  The pad-to-apron weld (05t) is vertex identity and is
untouched.

### 9.2 CONSUMER TABLE (owner 2026-08-30l) — every pass that reads the
### affected geometry, and its ruling

A. THE NEW `bank_foot` RING (new `SurfaceVertex` ids + a closed
`SurfaceBreakline` of kind `bank_foot`; present ONLY in the surface the
adapter renders, never in the surface the solve or the rebake reads):

| # | consumer | reads | ruling |
|---|---|---|---|
| A1 | `solve/design.py`, `solve/rows.py`, every `constraints/*` generator | the `PlanarMap` | UNAFFECTED — the bank is built AFTER the solve, from the solution; no planar face, edge or vertex is added, so no law row, no bending triangle, no zone membership changes. |
| A2 | `emit/graded.graded_surface` | planar + solution | unchanged; `emit/bank.with_bank` returns a NEW surface with the extra vertices and breaklines appended. |
| A3 | `emit/osm_adapter.render_patch` | `surface.faces` / `.breaklines` / `.vertices` | EDITED: emits one closed way per `bank_foot` breakline, tags `o4_feature=bank_foot` only (no `role`, no `aeroway`, no `shapeID`) — articulation geometry, exactly as `structure_rim`.  The foot vertices are ordinary nodes with `alt_abs`. |
| A4 | `emit/osm_adapter.render_patch` `ring_edges` | face ring edges + rim runs | UNAFFECTED: a foot ring shares no edge with any face ring (it is strictly outside the coverage), so the hole-coverage test is unchanged. |
| A5 | `emit/osm_adapter.write_tile_pieces` | faces by tile, breakline runs | the foot vertices travel with the tile they fall on; a foot ring straddling a tile seam becomes an OPEN chain in each piece (a DUMMY constrained line: the altitudes still hold, the annulus is not closed on that piece).  DEVIATION, recorded in §9.4. |
| A6 | `emit/surface.GradedSurface.to_json` / `SCHEMA` | vertices + breaklines | UNAFFECTED — a breakline kind is a free string and vertices are `[id, lat, lon, z]`. |
| A7 | `emit/rebake.deck_datum_from_surface`, `airport/rebake_plan` | `surface.vertices` inside a deck ring | UNAFFECTED BY CONSTRUCTION: `pipeline/build` keeps the PRE-bank surface for the rebake plan and passes the banked one to `write_patch` / `write_tile_pieces` only. |
| A8 | `verify/frame.Patch.of` | `surface.faces`, `.holes`, and breaklines of kind `runway_profile` / `structure_rim` | UNAFFECTED: a `bank_foot` breakline matches neither branch, so v2's census never sees it.  Stated here so the next reader does not rediscover it. |
| A9 | `verify/*` (every family), `verify/census.DEFECT_KEYS` | `Patch.shapes` / `.features` | UNAFFECTED via A8 — the bank carries NO grade law of its own: it IS the DEM. |
| A10 | `tools/check_grade.py::_parse_osm` | every closed way in the patch | EDITED: `bank_foot` joins the feature classes routed to `feature_out`, so it never enters `ways` and mints no ring row.  Without this it would be judged a role-less surface at the caller's default 1.5 % cap and mint a row per 33 % bank chord. |
| A11 | `tools/check_grade.py::ROLE_LESS_FEATURE_CLASSES` | the role-less register | EDITED: `bank_foot` registered (not in `HOST_CAP_FEATURE_CLASSES` — it has no host; it is the terrain). |
| A12 | `tools/harness/census.py`, `tests/test_harness.py` twins | `check_grade`'s one code path | follows A10/A11; no family added, `LAW_FAMILIES` untouched. |
| A13 | `O4_Vector_Map.include_patches` | every closed way | reads it as a patch ring: `patches_area_polys` (blocks the water/sea floods over the bank — correct, it is land), `interp_alt_patch_polygons` (the annulus is polygonized and seeded).  NOT in `graded_area_polys`: it carries no `role`, so the seawall admission is unchanged. |
| A14 | `O4_Mesh_Utils.interpolate_free_interior_altitudes` | INTERP_ALT triangles + patch-valued vertices | the mechanism the bank relies on; unchanged. |
| A15 | `pipeline/publication.py`, the sidecar | faces and centrelines | UNAFFECTED: the bank publishes nothing (no axis, no pair, no cap). |

B. THE PAD PLANE (`constraints/pads.pad_flats` stops minting `Flat`):

| # | consumer | reads | ruling |
|---|---|---|---|
| B1 | `solve/rows._reduce` | `cs.flats` | a pad no longer merges to one column: +N-1 unknowns per pad.  Cost reported in §9.4. |
| B2 | `solve/design.py:546,570` (the sheet/body datum: "a rigid group is one sheet") | `cs.flats` | a pad's vertices are now separate columns; each is already part of its face's bending sheet through `_face_triangles`, so a detached pad still takes the `detached_mean` plane datum through its own sheet. |
| B3 | `solve/why.py:221` | `cs.flats` | reports one fewer row kind for pads; the pad's rows now appear as `pads` diffs.  No code change needed. |
| B4 | `constraints/zones.py` (`pad_rim`, `pad_nearest`, `rigid_rims`, `strip_transverse`'s `pad_pick`) | "A RIGID PAD IS ONE LEVEL, SO IT CARRIES ONE BAND" | HELD AS IS: the one-band-per-pad rule is what keeps the pad's zone rows mutually satisfiable, and the flatness target (not the `Flat`) now carries the level to the far rim.  The rule is now a TARGET-consistency rule rather than an exact one — stated, not changed. |
| B5 | `constraints/ceiling.pavement_ceiling` | every `Diff` over pavement vertices | EDITED: skips rows whose ruling head is the pad ceiling's, so a pad pair is not twinned at 5 % beside its own 1 %. |
| B6 | `verify/pads.pad_flat` | `relaxed_rows` (a retired publication) vs "spread" | EDITED: EVERY pad is read as ONE PLANE now (residual ≤ `emit.materiality.elevation_m`, slope ≤ `pad_slope_max` + grade materiality + the 06k(3) quantum).  The `relaxed_faces` branch is deleted with the relaxation it named. |
| B7 | `verify/census.DEFECT_KEYS` | family list | UNCHANGED — 08v already withdrew `pad_flat` from the DEFECT gate; the gate reads the runway family. |
| B8 | `constraints/pads.frontage_near_miss`, `constraints/routes` (the pad CONTACT edge) | pad vertices | UNAFFECTED: both name vertices, not the group. |
| B9 | `constraints/structures.py:318,388` (`Flat` for structure mouths/floors) | `Flat` | UNAFFECTED: those are structures, not rigid pads; they keep the hard merge. |
| B10 | `airport/rigid.py`, `rebake_plan` (objects seat on the pad) | the emitted surface under the object | a pad may now tilt up to 1 %; the seat reads the surface, so a tilted pad seats its objects on the tilted plane.  That is 09c's intent. |
| B11 | `emit/clusters.py` | solved z per vertex | UNAFFECTED. |

### 9.3 The law values

`emit.toml [design]`: `bank_slope = 0.33`, `bank_min_width_m = 5.0`,
`bank_foot_smooth` (the second-difference weight along the foot chain),
`pad_flat` (the flatness target weight), `pad_flat_rulings` (the ruling
heads priced at `pad_flat` instead of `law` — the same shape as
`hard_rulings` / `one_way_rulings`), and `hard_rulings` gains
`structures.building_pad pad_slope_max ceiling`.
`emit.within_shape.pad_slope_max` (0.01) already exists and is the
ceiling's cap: one derivation site, read by the generator and by
`verify/pads`.

### 9.4 Deviations to report (never decided by the lane)

1. THE FOOT'S SMOOTHING IS ON THE PLAN DISTANCE, NOT AN LP ROW.  The
   foot's z IS the DEM (09e), so it is not an unknown of the solve; a
   second-difference target on its z would fight that equality.  The
   zigzag the ruling names is the TOE — a plan phenomenon: `d` varies
   along the ring because `z_ring` and the DEM do.  The smoothing is
   therefore the same second-difference least-squares, applied to `d`
   along the foot chain at `[design] bank_foot_smooth`, after which the
   DEM is re-sampled at the smoothed position (so `z = DEM(foot)` holds
   exactly).  Reported for the owner's ruling.
2. A FOOT RING STRADDLING A TILE SEAM is emitted as an open chain per
   tile piece (A5): its altitudes hold, but the annulus is not a closed
   polygon on that piece, so the mesh's INTERP_ALT seeding of the bank
   is not guaranteed there.  Single-tile airports are unaffected.
3. THE FOOT RING IS MADE VALID BY CONSTRUCTION: the per-vertex offset
   can self-intersect at a concave corner, so the ring is closed through
   shapely (`unary_union` with the patch component, then the exterior),
   which can move a foot vertex off its own normal.  Every emitted foot
   vertex is DEM-sampled at its final position, so `z = DEM` still holds
   exactly; only `d` may differ from the formula there.
4. THE BANK IS ONE REGION, NOT ONE RING PER BODY.  Banked per body (the
   ruling's literal shape), a foot ring lands inside — even exactly ON — a
   neighbouring body's ring wherever two patch bodies stand closer than a
   bank is wide: MEASURED at HECA, 184 of 8,242 foot nodes within 1 m of a
   design node, one of them coincident and 12.34 m below it, and 301 with
   a foot-to-design pseudo-slope over 1:1 — the very cliff the bank exists
   to remove, minted at a node.  The construction therefore unions the
   coverage with every bank piece and emits the boundary of THAT: one
   region, every boundary vertex at least ``bank_min_width_m`` from the
   design surface, and a gap too narrow for a bank simply swallowed — which
   is 09e's "the two rings share the bank" read as an area rather than as a
   pair of lines.  Reported for the owner's ruling.

### 9.5 THE TRANSECT, and the second finding the owner must rule on

`tools/run_tile_mesh_only.py 30 31 1 --patches-as-is` on the banked HECA
patch, the SAME transect as §8.4 (lon 31.3819142, 0.00005 deg = 5.6 m per
station), read with `tools/mesh_elevation_sampler.py`:

| lat | 1.0.296 (§8.4 control) | 09e (no bank) | THIS (banked) |
|---|---|---|---|
| 30.11635 | 66.876 | 66.876 | 63.795 |
| 30.11660 | 66.133 | 66.133 | 59.572 |
| 30.11665 | 66.062 | **61.154** | 54.777 |
| 30.11670 (the boundary) | 65.847 | **49.345** | 49.333 |
| 30.11675 (inside) | 65.574 | 49.396 | 49.375 |

THE CLIFF IS GONE AS A MAGNITUDE.  09e dropped **16.8 m over ~11 m of
ground, one triangle wide**.  The banked patch falls from the DEM at the
toe (66.88 at lat 30.11617, 59 m out) to the patch ring (49.33) — 17.55 m
over 59 m, an AVERAGE 29.7 %, inside the law's 1:3, spread over 20+ mesh
stations.

**IT IS NOT YET A CONTINUOUS ≤ 1:3.**  Read at 2.2 m stations the profile
is 15.2 % over the outer 50 m and then ONE triangle of 9.93 m over 8.9 m
(**111 %**) against the patch ring.  The steepest 5.6 m station reads
−5.44 m where 09e read −11.81 m.  MECHANISM: the mesh's blend is
`interpolate_free_interior_altitudes`' discrete HARMONIC extension over
whatever vertices Triangle4XP happened to put in the annulus, and it is
graph-harmonic, not metric-linear — with few free vertices in a 59 m
annulus the isolines crowd against the shorter (inner) boundary.  A second
transect at lon 31.3900 over the same boundary is smooth throughout
(79.93 → 73.30 over 220 m, no station over 12 %), so this is the worst
site, not the typical one.

09e's "the bank face is left to the mesh (no vertices between ring and
foot)" is the same shape of assumption 09b (3) was, and the measurement
refutes it the same way: Ortho4XP will not interpolate a straight bank it
has no vertices for.  The owner rules between (a) accept the banked
profile as it stands (the magnitude is 3× better and the site is the
worst on the airport); (b) the patch emits INTERMEDIATE bank rings — one
or more constrained rings between the ring and the foot, which authors
the bank face and contradicts 09e's letter; or (c) the mesher densifies
inside a patch-bounded annulus.  The lane changed nothing on its own
judgement.

## §10 THE BANK FACE IS AUTHORED, and `bend_strip` (RULINGS 2026-09-09f)

### 10.1 What is being added (09f-1)

§9.5 measured that leaving the bank face to the mesh does not give a
continuous 1:3: `interpolate_free_interior_altitudes` is a discrete
GRAPH-harmonic extension over whatever vertices Triangle4XP put in the
annulus, so with few free vertices in a 59 m bank the isolines crowd
against the shorter (inner) boundary — one triangle of 9.93 m over
8.9 m (111 %) against the patch ring.  The owner rules option (b): the
patch AUTHORS the face.

Between the boundary ring and the foot the patch emits INTERMEDIATE
RINGS every `[design] bank_ring_spacing_m` = 10 m of plan distance
along the bank (a foot 59 m out gets five, at 10/20/30/40/50 m), each
vertex's z LINEAR between the ring's design z and the foot's DEM z
along the outward normal.  A foot at the `bank_min_width_m` 5 m
minimum gets none — and neither does one exactly at the spacing.

Geometry, per foot node: its ray runs from the NEAREST POINT of the
design coverage to the foot (never to the nearest ring VERTEX — a
runway edge runs hundreds of metres between vertices, and the segment
from a point to its nearest point of a closed set meets that set only
there, so the authored face can never re-enter the patch).  The
ray's inner z is the design ring's z INTERPOLATED along the boundary
edge the nearest point lands on.

Closure: the ray lengths vary along a ring, so a level exists only
where the bank is wider than it.  A level covering the whole ring is
emitted as a CLOSED way; otherwise one OPEN constrained chain per
contiguous run, its two ends being the FOOT NODES either side (shared
vertex ids, so the constrained geometry stays connected and the
annulus is still subdivided).

### 10.2 CONSUMER TABLE (owner 2026-08-30l)

The intermediate rings are `SurfaceBreakline`s of the SAME kind
`bank_foot` (`emit.bank.BANK_KIND`) carrying new `SurfaceVertex` ids,
appended by `emit/bank.with_bank` to the EMITTED surface only.  The
kind is deliberately not new: every consumer that already skips the
foot skips these, and NO register anywhere gains an entry.

| # | consumer | reads | ruling |
|---|---|---|---|
| C1 | `solve/*`, `constraints/*` | the `PlanarMap` | UNAFFECTED — as §9.2 A1: the bank runs after the solve, on the solution; no planar face, edge or vertex is added. |
| C2 | `emit/osm_adapter.render_patch` | `surface.breaklines` | UNCHANGED CODE: the existing `BANK_KIND` branch already emits closed-or-open by `vertices[0] == vertices[-1]`.  The `ref` gains an `@LEVEL` suffix (`bank:7@2`), which is a free string. |
| C3 | `emit/osm_adapter.write_tile_pieces` | breakline runs by tile | as §9.2 A5: a chain straddling a tile seam becomes an open chain per piece.  Same deviation, no new one. |
| C4 | `emit/rebake.deck_datum_from_surface`, `airport/rebake_plan` | `surface.vertices` | UNAFFECTED BY CONSTRUCTION: `pipeline/build` passes the PRE-bank surface to the rebake plan (§9.2 A7). |
| C5 | `verify/frame.Patch.of` | breaklines of kind `runway_profile` / `structure_rim` | UNAFFECTED: `bank_foot` matches neither branch (§9.2 A8). |
| C6 | `tools/check_grade.py::_parse_osm` | every way of ≥ 3 nodes | UNCHANGED CODE: the `o4_feature` routing to `feature_out` is tested BEFORE any closure test, so an open intermediate chain is routed exactly as the closed foot ring is.  `ROLE_LESS_FEATURE_CLASSES` unchanged. |
| C7 | `tools/harness/census.py`, `tests/test_harness.py` twins | `check_grade`'s one code path | follows C6; no family added, `LAW_FAMILIES` untouched. |
| C8 | `tools/undulation.py` | `o4_feature` per way | UNCHANGED CODE: skips `bank_foot`.  The authored face IS the bank, not a designed pavement — counting it would move the whole-patch read (§9.2's own measurement of the foot). |
| C9 | `O4_Vector_Map.include_patches` | every patch way | a CLOSED intermediate ring is polygonized and seeds its annulus `INTERP_ALT` exactly as the foot ring does; an OPEN chain is a constrained line whose node altitudes hold.  Either way the mesh now has authored z inside the bank every 10 m — which is the point.  Not in `graded_area_polys` (no `role`). |
| C10 | `O4_Mesh_Utils.interpolate_free_interior_altitudes` | INTERP_ALT triangles + patch-valued vertices | the mechanism 09e relied on and 09f-1 no longer needs: with the face authored there is little left to interpolate. |
| C11 | `verify/*`, `verify/census.DEFECT_KEYS`, `pipeline/publication.py` | shapes / features / axes | UNAFFECTED via C5 — the bank carries no law and publishes nothing. |
| C12 | `emit/surface.GradedSurface.to_json` / `SCHEMA` | vertices + breaklines | UNAFFECTED — a breakline kind is a free string; several breaklines may share a kind already (`structure_rim`). |

### 10.3 The law value

`emit.toml [design] bank_ring_spacing_m = 10.0` (owner's figure).
`law/design_schema.py` validates it at `>= bank_min_width_m`: a
narrower spacing would author a ring inside the minimum bank.

### 10.4 `bend_strip` (09f-2)

09f measured the strip REGRESSING where the DEM was smooth
(CYXY 0.034 -> 0.130) — the deleted DEM datum leaves the strip's
along-direction under-determined.  Under 08t the answer is BENDING,
so `[design] bend_strip` is swept with the ONE-WAY tie of 09e in
place (08v's sweep was under the two-way tie, where the strip dragged
the runway).  The sweep and the shipped value are in §10.5.

### 10.5 MEASUREMENTS

Sweep (`tools/v2_solve_replay.py` captures, `tools/undulation.py`;
graded_strip RMS second difference / p95 grade change per 100 m):

| `bend_strip` | CYXY strip | HECA strip | HECA bows (05R/05C/05L) | HECA solve |
|---|---|---|---|---|
| 1 (09f) | 0.1299 / 1.230 | 0.0265 / 0.693 | −0.00 / −2.72 / −0.04 | 22.6 s |
| 10 | 0.0496 / 0.859 | 0.0264 / 0.708 | −0.01 / −2.74 / −0.09 | 24.8 s |
| **30** | **0.0314** / 0.807 | **0.0221** / 0.678 | −0.00 / −2.74 / −0.04 | 27.0 s |
| 100 | 0.0262 / 0.741 | 0.0218 / 0.645 | −0.01 / −2.74 / −0.04 | 32.5 s |
| 300 | 0.0263 / 0.712 | 0.0209 / 0.690 | −0.05 / −2.72 / −0.04 | 27.5 s |

The bar is CYXY strip <= 1.0.296's 0.034 with the bows within 0.15 m:
**30 is the smallest weight that meets it** (0.0314), and every arm
holds the bows within 0.02 m of the w = 1 arm.  Shipped as the table
value.

### 10.6 THE MESH TRANSECT, and the residual the owner must rule on

`tools/run_tile_mesh_only.py 30 31 1 --patches-as-is` on the banked HECA
patch, the §8.4/§9.5 line (lon 31.3819142) read at 2.2 m stations
(0.00002 deg) with `tools/mesh_elevation_sampler.py`:

| arm | the transition | steepest one-triangle station |
|---|---|---|
| 1.0.296 (§8.4 control) | none — the patch ring stands on a cliff | — |
| 09e (no bank) | 16.8 m over ~11 m, ONE triangle | 11.81 m / 5.6 m = 211 % |
| 09f (foot ring only) | 17.55 m over 59 m (29.7 % average) | 9.93 m / 8.9 m = **111 %** |
| 09f-1 open chains (REFUTED) | reverted to the DEM outside level 1 | 6.81 m / 2.23 m = **306 %** |
| **09f-1 closed rings (this)** | **17.37 m over 60 m, 25 stations, continuous** | 2.47 m / 2.23 m = **111 %** |

Read station by station the profile is now 30.5 % over the outer 45 m
(exactly the law's 1:3, one 0.68 m step per 2.2 m station), 10 % over
the next 8 m, and then three stations of 111 % against the patch ring.

**Refuted on the way, recorded so it is not retried:** emitted as OPEN
constrained chains the intermediate rings made the transect WORSE than
09f (306 %).  An open way enters `include_patches` as a DUMMY way, so
it is NOT in `interp_alt_patch_polygons` and no sub-face of the annulus
gets its own INTERP_ALT seed — while its segments still block
Triangle4XP's regional plague.  The bank outside level 1 reverted to
the raw DEM.  Every intermediate ring is therefore CLOSED.

**THE RESIDUAL, attributed but NOT fixed (attempt cap).**  A level ring
is a per-vertex inward offset of an AIRPORT-SCALE chain (the bank is
ONE region per airport, §9.4 deviation 4 — HECA's largest foot ring
carries 1,516 vertices), and such an offset self-intersects at a
concave corner.  `include_patches` takes a closed patch way only when
`pol.is_valid and pol.area`, so ONE self-intersection anywhere drops
the WHOLE ring.  Measured at HECA before the repair: 9 of 39 level
rings invalid, among them levels 1, 2 and 3 of the transect's own ring
— the mesh honoured that ray's levels 4-7 exactly (66.84 / 64.29 /
61.81 / 59.36 against the authored 66.84 / 64.28 / 61.82 / 59.35) and
read the DEM-side interpolation at levels 1-3.  A `buffer(0)` repair
(`emit/bank._simple_rings`, re-deriving z from the bank's own field)
recovers 6 of the 9; THREE — levels 1-3 of that one 1,500-vertex ring —
are still reported self-intersecting after the repair, so the innermost
~7 m of that bank is still the mesh's own harmonic squeeze and the
transect's steepest triangle is unchanged at 111 % (though its FALL is
2.47 m where 09f's was 9.93 m).

Two candidate answers, neither taken by the lane: (a) the level rings
are built PER BODY rather than for the one airport-scale region, so an
offset stays local and simple; (b) the level ring is constructed as
`cov.buffer(t) ∩ banked` — always valid by construction — with z from
the bank field instead of from a per-vertex ray.

### 10.7 THE BASE ARMS (graded_strip RMS second difference)

| airport | 1.0.296 bar | 09f | this (`bend_strip` 30) |
|---|---|---|---|
| CYXY | 0.034 | 0.130 | **0.0314** — met |
| OTHH | 0.010 | 0.023 | 0.0221 — MISSED |
| LEMD | 0.057 | 0.072 | **0.0510** — met |
| HECA | (0.0265 at 09f) | 0.0265 | 0.0221 |

Runway DEFECT families 0 on all four.  OTHH's strip misses its bar:
its bank is one level deep (mean foot 5.6 m) and its strip was already
the smoothest of the four — `bend_strip` buys it only 0.023 -> 0.022.
Reported, not decided.

## §11 THE DAYLIGHT LINE, and the level rings VALID BY CONSTRUCTION
## (RULINGS 2026-09-09g / 2026-09-09h) — lane `v2daylight`

### 11.1 What is being added

**THE DAYLIGHT FOOT (09g).**  §9/§10 placed the foot by the fixed point
`d = max(bank_min_width_m, |z_ring − DEM(foot)| / bank_slope)`.  That is
the daylight point only where the ground is smooth; where it is not, the
fixed point erases the very earthworks the owner names.  The owner rules
the civil-engineering DAYLIGHT (catch) POINT: from each boundary-ring
vertex, walk OUTWARD along its normal in `bank_sample_m` (2 m) stations
and carry the 1:3 DESIGN SLOPE LINE with you —

    fill (`z_ring ≥ DEM(ring)`):  z_line(t) = z_ring − bank_slope · t
    cut  (`z_ring <  DEM(ring)`): z_line(t) = z_ring + bank_slope · t

The FOOT is the first station where `z_line(t)` meets the DEM within
`bank_daylight_tol_m` (0.3 m) — or, where a station steps over the
crossing, the crossing itself by linear interpolation — never nearer
than `bank_min_width_m` (5 m), never farther than `bank_max_width_m`
(200 m).  Two special cases the ruling names:

* THE GROUND'S OWN BANK.  Where the DEM within the first
  `bank_min_width_m` already falls (fill) / rises (cut) at ≥ `bank_slope`,
  the foot is AT THE MINIMUM and the DEM's own bank carries the drop
  beyond — a real embankment under the pavement edge survives untouched.
* NEVER DAYLIGHTS.  A ray that reaches `bank_max_width_m` without meeting
  the DEM takes the maximum and is REPORTED BY NAME (chain, vertex, and
  its lat/lon) in the planar report and in `report["bank"]`.

Consequences by construction, the owner's own list: a PLATEAU EDGE or
CLIFF beyond the daylight point is outside the bank and untouched; a real
TERRACE between the ring and the old fixed-point foot is met where it
stands and kept.

**THE TOE NEVER SMOOTHS ACROSS A DISCONTINUITY (09g (4)).**  The plan
smoothing of §9.4 deviation 1 is kept, but the closed foot chain is first
CUT into runs wherever the RAW daylight distance jumps by more than
`bank_toe_break_m` (10 m) between neighbours: each run is smoothed as an
open chain, and the jump — the ground's own discontinuity — survives.

**LEVEL RINGS VALID BY CONSTRUCTION (09h).**  §10.6 attributed the last
111 % triangle: a level ring built as a per-vertex inward offset of an
AIRPORT-SCALE chain self-intersects at concave corners, and
`include_patches` drops an invalid closed way whole (9 of 39 at HECA;
`buffer(0)` recovered 6).  The owner rules option (b): the level ring at
plan distance `t` is

    cover.buffer(t) ∩ banked_region

— shapely-constructed, VALID BY CONSTRUCTION, and it degenerates to the
foot exactly where the bank is narrower than `t` (the intersection's
boundary is the banked boundary there), which is §10.1's closure rule
read as an area.  Each exterior and interior ring of the result is one
CLOSED way.  z per vertex comes from THE BANK FIELD: the design z at the
nearest point of the coverage boundary (interpolated along that boundary
edge), the DEM z of the nearest foot node, linear in the plan fraction
`min(1, dq / dk)`.  `emit/bank._simple_rings` (the `buffer(0)` repair) is
DELETED with the per-vertex offset it repaired.

### 11.2 CONSUMER TABLE (owner 2026-08-30l)

Neither change adds a shape class, a region, a breakline KIND or a
register entry: the bank keeps `emit.bank.BANK_KIND` (`o4_feature=
bank_foot`), the same `ref` shape (`bank:N`, `bank:N@LEVEL`), and still
runs AFTER the solve on the solution.  Every A-row of §9.2 and C-row of
§10.2 therefore stands unchanged; what follows is the census of what
these two changes touch that those tables did not.

D. THE DAYLIGHT FOOT — the foot MOVES; nothing new is emitted.

| # | consumer | reads | ruling |
|---|---|---|---|
| D1 | `emit/bank.foot_distances` | ring z, normals, DEM | REPLACED by the daylight walk (`daylight_feet`), returning `d` AND a per-vertex classification (`MIN` / `DAYLIGHT` / `MAX`).  The fixed-point iteration and its `rounds` argument are DELETED — the walk is not a fixed point. |
| D2 | `emit/bank.smooth_along` | the closed foot chain | GENERALISED to `closed=False` and wrapped by `smooth_runs`, which cuts at `bank_toe_break_m` jumps.  The closed-chain behaviour is unchanged where no jump exists, so §9's toe twin still holds. |
| D3 | `emit/bank._ray_limit` (the foot stops at the next patch ring) | coverage segments | UNAFFECTED — it caps `d` after the walk exactly as before; a shared bank is still shared. |
| D4 | the union `banked = cov.buffer(min_w) ∪ pieces` (§9.4 deviation 4) | the per-chain pieces | UNAFFECTED in kind: only the pieces' outer extent changes.  ONE region per airport still. |
| D5 | `pipeline/build.py:574` — `BankReport`, `_say`, `report["bank"]` | the report dataclass | EDITED: `BankReport` gains `at_min` / `daylighted` / `at_max` counts and `never_daylight` (the names, capped in the printed line, whole in the JSON).  `_dc.asdict` carries a `list[str]` unchanged; no reader of `report["bank"]` exists outside the build's own log (grep: one write, no read). |
| D6 | `airport/dem_production.DEM.z_many` | frame points | UNAFFECTED, but now called ~`bank_max_width_m / bank_sample_m` times per pass instead of twice: the walk is VECTORISED over the still-marching vertices, one `z_many` call per station over a shrinking active set. Build-time impact in §11.5. |
| D7 | `constraints/zones.py` and every other DEM reader | the same DEM | UNAFFECTED: the bank samples the DEM, it never writes it, and it runs after the solve. |

E. THE LEVEL RINGS BY CONSTRUCTION — the same kind, the same ref shape.

| # | consumer | reads | ruling |
|---|---|---|---|
| E1 | `emit/bank._simple_rings` | the raw offset ring | DELETED — the construction is valid by construction, so there is nothing to repair (09h's own words). |
| E2 | `emit/bank.intermediate_offsets` | `d`, spacing | KEPT as the LEVEL SCHEDULE (which `t` values exist), now read once over the whole bank rather than per ray.  Twin unchanged. |
| E3 | `emit/osm_adapter.render_patch` | breaklines | UNCHANGED CODE (§10.2 C2): closed-or-open by `vertices[0] == vertices[-1]`; every level ring is closed. |
| E4 | `O4_Vector_Map.include_patches` | closed patch ways | THE POINT OF THE CHANGE: `pol.is_valid and pol.area` now holds for every level ring, so none is dropped and every annulus band is seeded `INTERP_ALT`.  Verified as a build statistic (rings emitted vs rings dropped). |
| E5 | vertex identity | coordinates | a level-ring vertex coincident with a foot node REUSES the foot node's id (kd-tree match within the `_SNAP` quantum); the rest are minted.  `insert_way(check=True)` welds by coordinate anyway, so this is economy, not correctness. |
| E6 | `emit/bank.with_bank`'s `_inner` field | cov / z-segments | REUSED as the level ring's z source (E1 already derived repaired vertices this way); factored into `_field_at` so the foot and the levels read ONE field. |
| E7 | `verify/*`, `check_grade`, `tools/undulation.py`, the sidecar | `o4_feature` | UNAFFECTED via §9.2 A8–A12 / §10.2 C5–C8 — no register gains an entry. |

F. THE FOUR NEW LAW KEYS (`emit.toml [design]`).

| # | consumer | reads | ruling |
|---|---|---|---|
| F1 | `law/design_schema.Design` | the `[design]` table | EDITED: `bank_sample_m`, `bank_daylight_tol_m`, `bank_max_width_m`, `bank_toe_break_m` as fields, with `check_design` validation.  No numeric literal in `law/*.py`; the file stays under 1,000 lines (154 → ~175). |
| F2 | `law/model._build` | every key must be a field | the loader REFUSES an unknown key and a missing required one, so the TOML and the schema land together or the law fails to load. |
| F3 | `law/tables.design`, `solve/design.py` | `DESIGN_TERMS` | UNAFFECTED: the new keys are geometry, not objective weights, so `DESIGN_TERMS` is untouched (as `bank_slope` already is). |
| F4 | `tests/auto_patch_v2/test_law_tables.py` | the loaded table | UNAFFECTED — it asserts weights and registers, not the key set. |

### 11.3 The law values (owner's figures, 09g)

    bank_sample_m        = 2.0     # the walk's station
    bank_daylight_tol_m  = 0.3     # the slope line MEETS the DEM within this
    bank_max_width_m     = 200.0   # a ray that never daylights stops here
    bank_toe_break_m     = 10.0    # the toe smoothing is cut at a jump this big

`check_design` validates `0 < bank_sample_m`, `0 < bank_daylight_tol_m`,
`bank_max_width_m > bank_min_width_m`, `bank_toe_break_m > 0`.

### 11.4 Twins (`tests/auto_patch_v2/test_v2daylight.py`)

The five daylight twins are the ruling's own list, each on a synthetic
DEM with one boundary ring; plus the toe-break twin and the level-ring
validity twin on a CONCAVE airport-scale cover.

### 11.5 Build-time impact statement

The walk replaces 2 vectorised DEM samples per boundary vertex with up to
`bank_max_width_m / bank_sample_m` = 100, over a shrinking active set (the
median ray daylights inside 10 stations).  The level rings replace ~7
per-vertex offsets + `buffer(0)` repairs with ~7 `buffer` + `intersection`
calls on the airport-scale cover.  Measured at HECA in §11.6 against 09h's
1.0 s bank / 145 s total.

### 11.6 MEASUREMENTS and the DEVIATIONS the lane REPORTS

**Deviations (reported, never decided by the lane).**

1. THE FOOT IS THE CROSSING, NOT THE STATION THAT DETECTED IT.  09g says
   "the FIRST station where the slope line meets the DEM within
   `bank_daylight_tol_m`".  Taken literally the foot lands at a 2 m grid
   station, and the realised bank is then up to `tol / d` STEEPER than the
   law's 1:3 purely because the walk is discrete (6 m of fill on level
   ground daylights at the 18 m station where the exact meeting is 18.18 m
   — a realised 0.3333 against a law of 0.33).  The walk therefore uses the
   tolerance to DETECT the meeting and places the foot at the linear
   crossing between the bracketing stations (capped at one further
   station).  On smooth ground this reproduces 09e's fixed point exactly
   (twin `test_the_foot_follows_the_ground_away_on_sloping_terrain`), and
   `rep.max_slope` reads 0.3300 on the flat-ground fixture.
2. `t` IS THE MITERED OFFSET PARAMETER, not arc length along the ray — the
   same parameter §9 already used, so a mitred right-angle corner's foot
   NODE stands `t·√2` from the coverage while its perpendicular bank is
   `t`.  Every distance statistic (`mean_m`, `p95_m`, `max_m`) is the foot
   node's plan distance to the coverage and carries that √2 at corners;
   the `bank_max_width_m` clamp is on the parameter.
3. THE LEVEL RING'S z IS READ ON ITS OWN LOCAL RAY.  09h names "the bank
   field"; the first arm read it from the NEAREST FOOT NODE's width, and a
   level vertex whose nearest foot node sat on a narrower stretch took that
   stretch's width — its z landed ~1 m off the straight bank and the mesh
   transect read 64 % against the ring.  The field is now the ray from the
   nearest point of the design coverage THROUGH the vertex to its first
   crossing of the banked boundary (`emit/bank._local_foot`), which is the
   bank's width AT THAT VERTEX.  Measured effect on the transect: 64 % ->
   46 % (below).
4. TWO GEOMETRIC FLOORS of the construction (not law values): a level ring
   whose area is under `bank_min_width_m²` is skipped, and a level ring
   that MINTED NO VERTEX is the foot ring itself and is skipped.  The
   second is not cosmetic: emitting it put a second closed way on the
   foot's own nodes (175 of them at HECA).
5. `rep.face_levels` reports the DEEPEST LEVEL ACTUALLY AUTHORED, never the
   schedule's own count — deviation 2's mitre makes the schedule name
   levels the region has no room for.

**HECA `HECA_20260909T140533` (166.5 s total, solve 29.7 s; 09h's build
`HECA_20260909T125715` served from the artifact ledger as the control,
key 63984c3cb2fb).**  THE DESIGN SURFACE IS UNTOUCHED, matched instrument:

| | this | 09h control | bar |
|---|---|---|---|
| bows 05R / 05C / 05L (`tools/rwy_profile.py`) | −0.05 / −2.73 / −0.08 | −0.04 / −2.73 / −0.08 | within 0.15 m — MET |
| runway DEFECT families (`verify/census.DEFECT_KEYS`) | 0 / 0 | 0 / 0 | 0 — MET |
| undulation RMS 2nd difference, EVERY role (`tools/undulation.py`) | runway 0.002681, junction 0.007747, stub 0.008750, primary_parallel 0.009959, apron 0.010362, service_road 0.010765, cross_connector 0.011280, secondary_parallel 0.011907, graded_strip 0.022123, overall 0.015894 | IDENTICAL to 8 significant figures | 09h's — MET |

(The bank runs after the solve and `tools/undulation.py` skips
`o4_feature=bank_foot`, so identity here is the consumer table's A1/C1
holding in the measurement.  09h's ruling text quotes a middle-runway bow
of −2.28; the ledgered control build reads −2.73 under `rwy_profile.py`,
which is the figure both arms above are measured with — the 0.15 m bar is
judged on the matched pair, never across instruments.)

THE BANK: 175 rings (9,826 boundary vertices -> 5,542 foot nodes, 163
repaired, 1,207 skipped), **DAYLIGHT 7,219 at the minimum / 2,607
daylighted / 0 at the maximum** (`never_daylight` empty), toe in 468
smoothing runs; foot distance min 5.0 / mean 7.0 / p95 14.7 / max 76.0 m;
bank slope p95 0.350 / max 1.529 (the max is §9.4's two-bodies instrument,
not a bank: it reads a foot node against the NEAREST design vertex, which
at a shared bank belongs to the other body).  FACE: **235 level rings,
5,491 vertices, 0 INVALID**, deepest bank 7 levels, 3.9 s.  09h emitted 48
intermediate rings of which 9 were dropped by `include_patches`; this
emits 235 and **none is dropped** — E4 met.

**THE MESH TRANSECT (`tools/run_tile_mesh_only.py 30 31 1
--patches-as-is`, lon 31.3819142, 2.2 m stations, lat 30.11630–30.11680).**

| arm | the outer bank | steepest one-triangle station |
|---|---|---|
| 09f (foot ring only) | 17.55 m over 59 m | 9.93 / 8.9 m = 111 % |
| 09h (level rings by per-vertex offset) | 25 stations at 30.5 % | 2.47 / 2.23 m = 111 % |
| this, arm 1 (nearest-foot-node field) | 5 stations at 29 %, 5 at 38 % | 1.42 / 2.22 m = 64 % |
| **this, arm 2 (local-ray field)** | **13 continuous stations at 29.2 % — the law's 1:3 exactly, over the outer 29 m** | **1.03 / 2.22 m = 46 %** |

**THE TRANSECT BAR (every triangle ≤ 0.35) IS NOT MET — STOP-AND-REPORT
at the attempt cap.**  The residual is the innermost ~6.7 m: three
stations of 1.03 m against the patch ring.  ATTRIBUTED: the first authored
level stands at `bank_ring_spacing_m` = 10 m, so between the design ring
and that level there is NO authored vertex and
`interpolate_free_interior_altitudes`' graph-harmonic extension still
governs — the same mechanism §10.6 named, now confined to one spacing
instead of the whole bank.  The candidate answer is a level INSIDE the
first spacing (a ring at `bank_min_width_m`, or a smaller spacing near the
ring), which is a LAW VALUE the owner set at 10 m: an intent question,
not a lane decision.

**THE SECOND TRANSECT — the site the brief asks for DOES NOT EXIST AT
HECA.**  Scanned: 4,000 foot nodes × 8 directions, the DEM (`Data+30+031.
alt` through `tools/mesh_elevation_sampler.AltRaster`) at 3 m stations out
to 30 m.  The STEEPEST near-boundary DEM slope in the whole HECA frame is
**0.295** (30.11721, 31.38817) — under the bank's own 0.33, so no ring on
this airport has a DEM terrace or embankment steeper than 1:3 within 30 m
of it.  (The 1.529 foot-to-design readings are §9.4 deviation 4's
two-bodies instrument, not terrain: at 30.11061, 31.39565 the `.alt` is
flat at 93.5 and it is the PATCH that stands 8.6 m up.)  The transect at
that steepest real site (lon 31.38817, lat 30.11700–30.11760) reads the
mesh against the DEM raster: **worst +1.06 m, RMS 0.48 m over 31
stations, no step over 0.65 m (29 % — the DEM's own slope)** — the ground
beyond the foot is the DEM, untouched, which is 09g's consequence (2).
The owner's four other consequences (embankment, plateau edge, cliff top,
rising terrace) are carried by the twins, on synthetic DEMs, because HECA
has no such ground.

**A DEFECT THE LANE COULD NOT CLOSE — the tile mesh REFUSES.**
`O4_Vector_Map.audit_interp_alt_seed_sealing` reports **1 of 2,717
INTERP_ALT seeds in an unbounded face** at (0.413671602, 0.128224345)
= lat 30.128224, lon 31.413672, and REFUSES the tile; the control patch
(09h) seals all 2,410 seeds.  Both transects above were therefore read
under `O4_INTERP_ALT_SEAL=warn`, which the audit itself provides.  What
was measured and REFUTED on the way: (a) the 175 duplicate level rings
(a level with no room emitting a second way on the foot's own nodes) —
fixed, the seed persists unchanged; (b) near-coincident level rings
annihilated by the map's 1e-7 deg node grid — `shapely.ops.snap` of every
level ring onto the banked boundary at 0.5 m changed the patch body
hash NOT AT ALL (`1e8ce88b9290` before and after), so no such vertex
exists; (c) the arrangement reproduced offline from the patch's own
closed ways, with and without 1e-7 rounding, seals every seed (0
unsealed, 1,853 faces) — so the failure lives in the map AFTER
`insert_way(check=True)`'s edge cutting, not in the emitted geometry.
The attempt cap is spent.  Reported for the spawner, not decided.

### 11.7 THE BASE ARMS

`graded_strip` RMS second difference (`tools/undulation.py --role
graded_strip`) and the runway DEFECT families, all three built at this
tree with `--base-arm`:

| airport | 09h | this | runway DEFECTs | bank |
|---|---|---|---|---|
| CYXY | 0.0314 | **0.031443** | 0 / 0 | 20 rings, 980 min / 388 daylighted / 0 max, mean 6.7 m, 24 level rings, 0 invalid, 0.18 s (10.5 s total) |
| OTHH | 0.0221 | **0.022095** | 0 / 0 | 44 rings, 9,436 min / 7 daylighted / 0 max, mean 5.6 m, 88 level rings, 0 invalid, 1.25 s (356 s total) |
| LEMD | 0.0510 | **0.050994** | 0 / 0 | 22 rings, 4,311 min / 1,036 daylighted / 0 max, mean 6.4 m, 118 level rings, 0 invalid, 0.76 s (258 s total) |

Every strip reads 09h's own value to four decimals: the daylight foot and
the level rings move the BANK, and the bank is emitted after the solve.
OTHH's bank is one level deep and 9,436 of 9,443 rays take the minimum —
its ground is level with its pavement edge almost everywhere, which is why
`bend_strip` bought it so little in §10.7.  0 rays anywhere reached
`bank_max_width_m`, so `never_daylight` is empty on all four airports and
the by-name report has nothing to name yet (the twin
`test_the_report_names_a_ray_that_never_daylights` exercises it).

**Build-time (§11.5 answered).**  The bank pass costs 3.9 s at HECA
against 09h's 1.0 s (+2.9 s on a 166 s build, 1.7 %) — the daylight walk
(one vectorised DEM call per 2 m station over a shrinking active set) and
the per-level-vertex ray cast of deviation 3.  Whole-airport wall 166.5 s
against 09h's 145–148 s; the solve is unchanged (29.7 s here, 26.8 s
there, both inside the ±25 % single-run band, and the surface is
bit-identical).  Over the 60 s per-airport budget on both sides — the
standing figure adjudicated once in the final profiling round.

---

## §12 THE UNSEALED SEED, and the FIRST LEVEL RING AT 3 m (RULINGS 2026-09-09i)

Lane `v2seedseal`, on the same branch.  Two items: 09i (2) attributes and
fixes the one unsealed `INTERP_ALT` seed that made `run_tile_mesh_only.py`
refuse the HECA tile, and 09i (1) moves the first level ring in to
`bank_first_ring_m` 3 m.

### 12.1 THE ATTRIBUTION (09i (2))

Reproduced OFFLINE from the shipped patch — no build.  The 1,797 closed
ways of `Patches/+30+030/+30+031/{HECA,HEAZ}_auto.patch.osm` are read with
production's own `O4_OSM_Utils.OSM_layer`, inserted into a real
`O4_Vector_Utils.Vector_Map` with `insert_way(check=True)` under
`PATCH_RING_MARKER`, seeded exactly as `include_patches` seeds, and audited
with `audit_interp_alt_seed_sealing`: **1 of 2,081 seeds unsealed, at
(30.128224345, 31.413671602)** — the tile build's own number.

What owns that seed: **nothing**.  The seed is the
`representative_point()` of a face of the SHAPELY arrangement that is a
**triangle of 2.0e-9 m²**, with corners

* `A = (0.41367461122, 0.12822382732)` — an exact node of SIX bank level
  rings (`o4_feature=bank_foot`, ways −1571, −1546, −1515, −1461, −1367,
  −1217), which run coincident along this stretch because
  `cover.buffer(t) ∩ banked` degenerates to the foot where the bank is
  narrower than `t`;
* `C = (0.41366859242, 0.12822486347)` — an exact node of ONE of the six
  (−1367) and of no other;
* `B` — the foot of `C` on the other five rings' segment, **2.7
  NANOMETRES** away from `C`, minted by the noder.

What `insert_way(check=True)` does to it: **nothing that is a defect.**
All 9,336 vertices of the six rings are in the map; no way is rejected,
split away, snapped or merged.  The map builds the SAME sliver — its `B`
comes from `are_encroached`'s 2×2 linear solve instead of GEOS's noder,
and the two answers differ by **1.5e-14 deg**.  That is the whole of the
difference between the two arrangements, and it is enough to leave the
seed 1.7 nanometres OUTSIDE the map's face union, where
`prepared.contains` is False and the audit refuses.  (09i records the
previous lane's "the offline arrangement seals every seed": it does not —
tested against the polygonized faces of BOTH arrangements, the offline one
refuses the same seed.)

### 12.2 THE FIX AT THE CAUSE, and why it is engine-side

The emitter is not at fault: every ring it authored is valid, is held by
the map exactly as authored, and would be held identically at any
tolerance.  The fault is that **a seed was placed in a face too small to
hold a mesh vertex**, where no two point-location implementations can
agree.  `O4_Vector_Map` therefore gains ONE predicate,
`is_degenerate_interp_alt_face`, and both seeders skip such a face:

| # | consumer | ruling |
|---|---|---|
| G1 | `O4_Vector_Map.include_patches` (per-FACE seeding) | EDITED: a face under `INTERP_ALT_MIN_FACE_AREA_M2` gets no seed. |
| G2 | `O4_Vector_Map.seed_interp_alt_subcells` (R18-1 road-cut sub-cells) | EDITED: the same floor, counted in its own report line. |
| G2b | the criterion itself | AREA **AND CLEARANCE**: `interp_alt_seed_point(face)` returns the seed or `None`.  MEASURED on a second arm of the same patch (level rings 5 m apart instead of 10, `HECA_20260909T151309`): a NEEDLE of **1.14 m²** — four corners spanning 50 m, a couple of centimetres wide — put its representative point on the map's own line and the audit refused again at (30.126121378, 31.418229091).  Area is only a proxy for what actually breaks; the criterion is that the seed stands clear of its own face's boundary by more than `INTERP_ALT_SEED_CLEARANCE_DEG` (1e-11 deg, one micrometre).  An honest face's representative point stands metres clear. |
| G3 | `O4_Vector_Map.audit_interp_alt_seed_sealing` | UNCHANGED — the audit stays strict; it has fewer seeds to check, not looser ones. |
| G4 | Triangle4XP `regionplague` | UNAFFECTED: a skipped face is 1 mm² at most, holds no mesh vertex and no renderable triangle, so no ground loses its `INTERP_ALT` altitude. |
| G5 | `emit/bank.py` and every v2 emitter | UNAFFECTED: no patch byte changes because of G1–G2. |

The floor is **one square millimetre** (`INTERP_ALT_MIN_FACE_AREA_M2 =
1.0e-6`, converted with the equatorial square-degree so the metre floor is
conservative at every other latitude).  At HECA it skips **12 of 2,081**
faces, the largest of them 1e-6 m²; the offline replay then reports
`INTERP_ALT seal: all 2,069 seed(s) enclosed`.  Twin (engine-side, as 09i
requires for a v1 change): `tests/test_interp_alt_degenerate_face.py` —
HECA's own `A` and `C` coordinates, the sliver reproduced at 1.1e-9 m²,
the floor separating it from the real face, `seed_interp_alt_subcells`
placing exactly one seed, and the audit accepting the result.

### 12.3 THE FIRST LEVEL RING AT 3 m (09i (1))

`[design] bank_first_ring_m = 3.0`, validated `0 < first < bank_min_width_m`
in `check_design`.  `intermediate_offsets(d, spacing, first)` returns
`first, first + spacing, …` strictly inside `d`, and `with_bank` iterates
that schedule instead of `spacing * lv`.  Consumers: the schedule function
(E2) and its two twins only — the ring kind, the `ref` shape and every
register are untouched, so §11.2's D-, E- and F-rows all stand.  Twins:
`intermediate_offsets(18.2, 10, 3) == [3.0, 13.0]` (09i's own), and a
minimum-width bank now authors ONE level ring at 3 m where 09f-1 authored
none — `test_a_minimum_width_bank_authors_the_first_ring_only`, re-scoped
by the ruling, not by the lane.

### 12.4 MEASUREMENTS

HECA `HECA_20260909T144913` (149.8 s, solve 26.8 s, `--engine v2`).  The
DESIGN SURFACE IS BIT-IDENTICAL to 09i's `HECA_20260909T140533`: 317
active-set rounds either side, objective 560668.3156424803, residual
`diff 3.4512962617862946 / band 3.806598709156475 / pin 0 / flat 0 /
offset 0` to the last figure.  The bank is outside the solve and both
changes are inside it.

Bank (09g/09i): 175 rings banked, 9,826 boundary vertices -> 5,542 foot
nodes, 163 repaired, 1,247 skipped; DAYLIGHT 7,219 at the minimum / 2,607
daylighted / 0 at the maximum; foot distance min 5.0 / mean 7.0 / p95 14.7
/ max 76.0 m; slope p95 0.350.  FACE: **492 level rings / 12,195 vertices,
0 INVALID, deepest bank 8 levels, 4.92 s** (09i: 235 rings, 3.9 s — the
3 m ring adds one level to every bank and one more wherever `d > 3 + 10k`).
Emit 6.85 s, 1,858 ways, 41,073 nodes.

**THE MESH RUN PASSES.**  `tools/run_tile_mesh_only.py 30 31 1
--patches-as-is` on this patch, WITHOUT `O4_INTERP_ALT_SEAL=warn`, 2 m 7 s:

```
Patch faces: 0 road-cut sub-cell(s) seeded INTERP_ALT beside the 2899
face seed(s) already placed (41 degenerate face(s) skipped).
INTERP_ALT seal: all 2899 seed(s) enclosed by INTERP_ALT edges
(14162 bounded face(s), 316506 marked edge(s)).
```

(The area floor alone already passed this run at 2,925 seeds / 15 skipped;
the clearance of G2b takes 26 more knife-edge seeds out and the mesh is
otherwise identical — the transect below is unchanged to the decimal.)

Base arms, all `--base-arm --engine v2`, all design surfaces BIT-IDENTICAL
to 09i's (rounds, objective and residual to ten decimals):

| airport | wall | level rings (09i -> now) | invalid | bank pass |
|---|---|---|---|---|
| CYXY | 8.3 s | 24 -> **57** | 0 | 0.24 s |
| OTHH | 408.8 s | 88 -> **308** | 0 | 2.17 s |
| LEMD | 261.4 s | 118 -> **205** | 0 | 1.00 s |

### 12.5 THE TRANSECT — the bar is MISSED, and the cause is not the emitter

Transect lon 31.3819142, 2.2 m stations across lat 30.11630–30.11680 (26
samples).  Bar: every triangle <= 0.35.  **MEASURED: 12 stations at
28.3–28.8 %, then 17.9 %, three at 4.7 %, then 76.0 % and 65.3 %, then
28.6 % and the DEM.  MAX 0.760** (09i: 13 at 29.2 % then three at 46 %).

THE AUTHORED FACE IS EXACT.  Read straight off the patch, the transect
crosses the `graded_strip` boundary ring and then five `bank_foot` rings:

| ring | lat | authored z | to the next |
|---|---|---|---|
| boundary (`graded_strip` −308) | 30.1166848 | 49.480 | |
| level 1 (3 m, way −1367) | 30.1166532 | 50.504 | +1.024 m over 3.52 m = **29.1 %** |
| level 2 (13 m, −1659) | 30.1165479 | 53.922 | +3.419 m over 11.71 m = **29.2 %** |
| level 3 (23 m, −1736) | 30.1164427 | 57.323 | **29.0 %** |
| level 4 (33 m, −1782) | 30.1163375 | 60.725 | **29.0 %** |
| level 5 (43 m, −1810) | 30.1162323 | 64.111 | **28.9 %** |

Every authored band is the 1:3 line to a tenth of a percent, and 09i (1)'s
own band — the first 3.5 m against the boundary ring — now reads 29.1 % in
the MESH (09i measured 46 % there).  The 76 % is inside the band between
level 1 and level 2: at 0.245 m sampling that band reads 4.8 % for its
outer 7.8 m and then **104 %** for the 3.1 m against level 1.  That is
09h's own mechanism unmoved — `interpolate_free_interior_altitudes` is a
GRAPH-harmonic extension over Triangle's annulus vertices, so the isolines
crowd against the SHORTER INNER boundary of every annulus the mesh puts a
free vertex inside.  09i (1) moved the first ring in and the squeeze moved
out one band with it.

REPORTED, NOT DECIDED (the remedy is an owner law value): the only band on
this transect that reads clean is the one that is 3.5 m wide, and the
bands that read 104 % are 11.7 m wide.  `[design] bank_ring_spacing_m` at
`bank_first_ring_m`'s own 3.0 would author every band at the width that
measured clean, at roughly 3x the level-ring vertices (HECA 12,195 ->
~40,000, bank pass 4.9 s -> ~12 s).  Not applied: 10.0 is the owner's
figure from 09f-1 and this lane's ruling changed one value, not two.

MEASURED ARM (`HECA_20260909T151309`, `bank_ring_spacing_m = 5.0`, the
smallest the schema allows since it must be at least `bank_min_width_m`;
NOT landed, the law value is back at 10.0): 746 level rings / 18,330
vertices, 0 invalid, 15 levels deep, bank pass 7.55 s, emit 2,112 ways /
47,208 nodes, design surface again bit-identical.  Its mesh run REFUSED —
and that refusal is what found G2b's needle class.  The transect was not
read on that arm (the run stopped at the audit); with the clearance in
place it seals offline (2,692 seeds, 199 skipped).  Whether 5 m meets the
0.35 bar is therefore still unmeasured, and is the owner's call to order.

## §13 THE CROSSING DIP — the ATTRIBUTION (RULINGS 2026-09-09p (2)) —
## lane `v2cyxy`

Owner, on 1.0.297 at CYXY: "runway crossings DIP instead of joining
smoothly". The ruling required the attribution before any fix, and named
three candidate rows: the CROSSING edges at the runway transverse cap
(`constraints/routes.py`, kind 1), the runway's hard crown/transverse rows
pulling the crossing to the EDGE height, and the taxi profile's second
differences across the crossing.

### 13.1 THE TAXI CROSSINGS ARE NOT THE DIP (all three candidates refuted)

Measured on the CYXY solve arm at 09b065b2 (`tools/v2_solve_replay.py`
capture + replay, the production DEM frame). CYXY has THREE places where a
taxi centreline reaches a runway ring from both sides at one station:

| crossing | runway | station | mouth A | ridge | mouth B | crown drop | dip |
|---|---|---|---|---|---|---|---|
| stub/junction (bl40 x bl39) | 14R/32L | s = 471 | 695.79 | 696.02 | 695.80 | +0.23 m | no |
| primary_parallel (bl43 x bl38) | 14R/32L | s = 2447 | 704.07 | 704.30 | 703.96 | +0.22 m | no |
| primary_parallel (bl56 x bl38) | 14L/32R | s = 1988 | 701.10 | 701.28 | 701.24 | +0.18 m | no |

Every section across the slab is edge -> ridge -> edge: the ridge is the
HIGH point, the two mouths sit under it by the crown's own fall (0.18-0.23
m over a 15.2 / 22.9 m half width = 1.0-1.2 %, inside the transverse cap),
and every station outward from a mouth descends monotonically. **No station
of any taxi crossing is below its approaches.** The taxi profile is not
discontinuous at the mouth either: a taxi centreline STOPS at the runway
ring (the precedence clip), so there are no profile stations inside the
slab to skip, and the mouth's own value is the runway edge's.

The three candidate rows are therefore REFUTED for the taxi crossings.

### 13.2 THE DIP IS THE RUNWAY x RUNWAY CROSSING

The dip the owner read is on the MAIN runways, where the short runway
**02/20** crosses them:

| runway | dip station | ridge z there | ridge z 160 m either side | bow vs threshold chord |
|---|---|---|---|---|
| 14R/32L | s = 1018 | 696.06 | 697.67 / 697.68 | **-2.25 m** |
| 14L/32R | s = 411 | 693.95 | 695.29 / 694.66 | **-1.82 m** |

Both bows the runway read reports ARE the 02/20 crossings. Beside them the
same runway stands +5.4 m over the DEM; at the crossing only +2.0 m — the
surface is pulled back to the ground exactly where 02/20 holds it.
`tools/rwy_profile.py --binned` on the emitted patch, against v1:

```
14R/32L station  825    1025    1225
v2 (1.0.297)     697.7   696.5   699.1     <- the V
v1               693.8   694.0   694.9     <- monotone, on the DEM
DEM              693.8   694.0   694.0
```

**`why` on the dip's own vertex** (v524, the 14R/32L ridge station at
s = 1018; `v2_solve_replay.py --why-vertex 524`, a duals solve of the same
system):

```
binding rows on v524 by family (rows, sum|dual|):
  runway_chain            1   46.56   3-term at lo; bound -0.3402 -> v542, v523
  no_step_pairs           1   16.93   cap 1.50% x 25.2 m = 0.378 m -> v542
  runway_vertical_curve   3   14.12   3-term at hi; bound 0.0002 -> v541, v540
chain trace: terminal v956 z 693.72
  [PIN: CIFP threshold ('rwy:02/20', 'end:20')]; 12 hops; sum dz +2.34 m
  by family along the chain: no_step_pairs +1.44, runway_vertical_curve +0.48,
                             runway_profile +0.42
```

**MECHANISM.** 02/20's two CIFP threshold elevations (694.33 / 693.72) are
hard pins 428 m apart. The crossing region is ONE surface (the
`runway_crossing` faces), so 14R/32L's ridge there can stand no higher than
02/20's own surface can climb from its pinned ends at 02/20's longitudinal
cap — 2.34 m over 12 hops. 14R/32L's threshold chord wants 698.3 at that
station. The two pinned chords conflict by ~2.3 m and the shared surface
splits it: 14R/32L dips 1.6 m below its neighbours, and 02/20 humps +2.09 m
over its own ground.

A second, mechanical finding rides on the same place: the airport's WORST
HARD-ROW violations are exactly these crossings. `runway_vertical_curve` is
a HARD row and the design report says `HARD SET NOT SETTLED` after ONE
polish round; the top six violated K rows are all on the 02/20 crossing
ridges (v524/v523/v540/v541/v83 on 14R/32L; v1357/v1358/v1322/v1415 on
14L/32R), worst |value| 0.0121 against a +/-0.00081 bound — 15x. If K held,
the sag would be spread into a vertical curve instead of the local V.

### 13.3 THE DEVIATION THE LANE REPORTS (never decided)

The ruling's prescribed fix — "a crossing must RIDE the runway's crown
(edge -> ridge -> edge) with the taxi profile continuous through it" — is
already what the surface does at every TAXI crossing (13.1). It does not
reach the mechanism 13.2 names, which needs law the ruling does not
contain: **at a runway x runway crossing, whose surface governs?** That is
an INTENT question, not a mechanism:

* (a) the SENIOR runway's crown governs the crossing (by length / code):
  02/20 would then have to climb 4.6 m from its pinned end 20 to the
  crossing — 1.15 %, inside its own longitudinal cap, but a 4.6 m hump in a
  428 m runway, which is not a runway;
* (b) the pinned chords stand and the surface splits the difference (today);
* (c) the CIFP thresholds are the datum and 14R/32L's straight chord is the
  thing that is wrong here: its real profile is flat for 1,200 m and then
  climbs (the DEM and v1 agree), so the chord target lifts it 5.4 m off the
  ground and the crossing is the ONE place it is at its true elevation.

No code was changed for (2). The twin
`tests/auto_patch_v2/test_v2cyxy.py::test_a_taxi_crossing_rides_the_runways_crown`
LOCKS the behaviour 13.1 measured, so a later change cannot silently break
the crossings that are right.

## §14 THE PER-BODY DATUM (RULINGS 2026-09-09p (3)) — lane `v2cyxy`

### 14.1 What is being added

Owner: taxiway G at CYXY (60.7075541, -135.0718986) "is not sloping up
enough like it was before, resulting in the whole area of the airport being
cut into the hill more than it should".

Under 08t the sheet minimises BENDING, and bending has an AFFINE null
space: it shapes a body but says nothing about where the body SITS. Until
1.0.296 the zone DEM fit supplied that level everywhere; 09b (3) / 09e
DELETED it ("the DEM has left the patch"). What remained — a pin, the
runway chord, a contact row — reaches a groundside apron only through the
taxiways that touch it, so an apron up the hill was levelled toward the
runway and the taxiway serving it flattened. Measured at CYXY, the G area's
`z - DEM` mean by arm: v1 **+0.06 / +0.42**, 1.0.296 **+0.7**, 1.0.297
**-5.12 / -5.40**.

THE ROW. Every APRON BODY — a connected group of faces whose bending class
is `apron` (`solve/design.apron_roles`: every VALUE role that is not the
runway family, the taxi family or the road cross-section; at CYXY that is
`apron`, `parking_lot`, `groundside_pavement`, `building`) — carries ONE
row:

```
    (1/N) * SUM z_v  =  (1/N) * SUM DEM(v)      at [design] body_datum
```

ONE row per body, NEVER per vertex: the datum sets the body's LEVEL and
leaves its shape and its tilt to the bending term, so it is not the
per-vertex DEM pull 08t answer 1 removed. Runway and taxi bodies are
excluded — the threshold chord and the taxi design profile ARE their
datums, and giving a taxiway a terrain datum would put the drape back.

`detached_mean` IS SUBSUMED IN EFFECT for an apron body (the same DEM under
the same vertices) but is NOT deleted: it is also the least-squares PLANE
that anchors the TILT of a sheet nothing else holds, which one mean row
cannot do. Where both apply they agree, so they never fight.

### 14.2 CONSUMER TABLE (owner 2026-08-30l)

The change adds one OBJECTIVE ROW per body. It introduces no shape class,
no exemption, no region into the layout, so no geometry consumer changes;
the table is stated anyway.

| consumer | reads | ruling |
|---|---|---|
| `solve/design.assemble` §9b | produces the row | THE change |
| `solve/design._term_energies` | buckets base rows by owner tag | tag `("body_datum", v)` buckets automatically; `DESIGN_TERMS` gains `body_datum` so a weight ARM can name it |
| `solve/design.DesignReport` | `body_datum_rows` | new count, printed in `line()` and `as_dict()` |
| `solve/why.py` | the ONE-SIDED rows and their duals | UNTOUCHED: a base row carries no dual and no `Row`; `why` never sees it |
| `constraints/*` | nothing | UNTOUCHED: the row is born in the solve, from the map's own `dem_z` |
| `emit/*`, `verify/*`, `harness/census.py` | the solved z | UNTOUCHED: no new geometry, no new sidecar key, no new law family |
| `law/design_schema.check_design` | every `DESIGN_TERMS` weight positive and finite | `body_datum` validated with the rest |
| Swift (`SceneryKit`) | the JSONL event names | UNTOUCHED: no event, no wire name |

### 14.3 The law value

`emit.toml [design] body_datum = 300.0` — the LAW's own weight. The datum
is a TARGET of equal standing with the law rows it trades against.

MEASURED, the two arms the lane paid (the attempt cap): at **3000** the
datum wins outright — every CYXY body lands within 0.01 m of its terrain
mean, but it OVERPOWERS the law (0.85 m `apron|apron` `within_shape` steps
minted in the shape-joint twin, a 2.33 % stretch against a 1.5 % cap, the
active set hitting its round cap at 17-18 s on the 2,500-vertex bench
fixture, CYXY census ADJUDICATED 258 -> 340). At **300** every CYXY body
lands within 0.11 m of its terrain mean (one outlier at 0.47 m), the owner's
site lands within 0.11 m of v1, and the census cost falls to +22.
A sweep at 30 / 100 / 1000 is recorded in the lane's report.

### 14.4 MEASUREMENTS

**CYXY, the four arms.** Per apron body, mean `z - DEM` (solve arm, 17
bodies >= 5 vertices), the deepest ten:

```
body (n)      1.0.297     this (300)
225           -0.15       +0.06
196           +0.09       +0.05
116           -1.71       -0.06
 65           -0.37       -0.11
 62           -2.22       -0.01
 51           -4.23       -0.01
 26           -2.20       -0.47
 22           -6.30       -0.03
 19           -6.27       -0.02
 14           -5.85       -0.01
```

TAXIWAY G at the owner's coordinate, the emitted patch along the chain
`taxi18` (letter A) from (60.70771119305, -135.07108362256) to
(60.70701560096, -135.072768375), `tools/arm_site_read.py --line`:

| arm | alt along G | level vs v1 | climb over 125 m (solve arm) |
|---|---|---|---|
| v1 | 702.30 .. 703.07 | — | +0.77 m |
| 1.0.296 | 703.05 .. 703.45 | +0.6 m | +0.40 m |
| 1.0.297 | 698.04 .. 699.95 | **-3.7 m** | **-2.45 m (it DESCENDS a rising hill)** |
| this | 702.27 .. 703.18 | **+0.06 m** | **+1.23 m** |

G's `z - DEM` at the owner's coordinate (solve arm, 6 vertices within 12 m):
**-3.76 m -> -0.67 m**.

The runway bows are UNCHANGED: 14R/32L -2.25 -> -2.25, 14L/32R -1.82 ->
-1.82, 02/20 -0.13 -> -0.13; runway `z - DEM` mean +2.47 -> +2.47.
v2-verify `verify_defects` **{}** (runway DEFECTs 0); the runway
`transverse` report family falls 10 -> 1.

Census (`harness/census.py`, four patches, ADJUDICATED): v1 **150**,
1.0.296 **401**, 1.0.297 **258**, this **280**. The +22 is the trade the
ruling asks for: with the bodies on their own benches the taxiways between
them run AT their caps (`taxi_box` 55 -> 61, `airside_no_step` 137 -> 153)
instead of sagging below them, while `within_shape` falls 1709 -> 1076 and
`transverse` 10 -> 1. Reported, not iterated on.

**HECA** (`HECA_bd300`, this tree; control `HECA_head` SERVED from the
artifact ledger, tree fc39d25b3183): 342 apron bodies. The bows are
**-0.04 / -2.28 / -0.04** against 09j's -0.04 / -2.26 / +0.01 — every one
inside 0.15 m; `verify_defects` **{}**; runway nodes move **0.00 m mean, 0
of 1,951 by more than 1 m** (`tools/patch_proximity_diff.py`). The datum
lifts HECA's deeply-cut apron pockets onto their ground:

```
cell                        A z-DEM    B z-DEM
30.119921,31.418956          -6.43      -0.33
30.120781,31.418831          -7.21      -0.12
30.128491,31.414891          -7.36      -5.54
30.122711,31.415165          -9.25      -7.55
30.103565,31.392562          -1.90      +0.11
30.110038,31.396964          +3.37      +1.60
```

Apron nodes: mean dz +0.22 m, 113 of 1,353 over 1 m. The patch is
BYTE-IDENTICAL at `body_datum` 3000 and 300 (`body_sha 87b241d8319b`) — at
HECA the bodies are exactly satisfiable either way.

### 14.5 BUILD-TIME IMPACT — the DEVIATION the lane reports

| airport | control | this | delta |
|---|---|---|---|
| CYXY total | 10.50 s | **9.95 s** | -0.55 s |
| HECA total | 176.75 s | **241.30 s** | **+64.5 s (+36 %)** |
| HECA solve | 29.31 s | **105.26 s** | **+75.9 s** |

The active-set ROUND COUNT is unchanged (317 -> 315), so the cost is
PER ROUND, and it is attributable: a body's datum is ONE row with `N`
non-zeros, which is a rank-1 **DENSE `N x N` block** in the normal
equations `A^T A` the `normal` method factorises each round. The cost is
`O(SUM N_body^2)` — negligible at CYXY (largest body 225 vertices, 18
bodies) and large at HECA (342 bodies). The same mechanism is what makes
`test_constraints.py::test_bench_style_instance_round_trip` (a synthetic
50x50 grid = ONE 2,400-vertex apron body) run 18 s against its 5 s guard.

The lane did NOT take either remedy, because both are design decisions the
ruling does not contain:

* **(A) bound the row's support** — state the mean over at most `K`
  deterministically chosen vertices of the body (a new law value), which
  caps the dense block at `K^2` and is exact for every CYXY body;
* **(B) keep the row out of `A^T A`** and apply the `B` rank-1 datum terms
  as a Woodbury low-rank correction in `solve/design._linear_solve` —
  exact, `B` extra triangular solves per factorisation, but it changes
  shared solver machinery.

Per `Ortho4XP/CLAUDE.md` HARD LAW this is a ">= 1 % of budget" change and
belongs to a Fable optimisation review.

### 14.6 THE TWINS THE CHANGE REDS (reported, never decided)

Five twins that are GREEN at 09b065b2 are RED with the datum at 300. Each
is an expectation written before a body had a datum; the lane names what
each encodes and stops (attempt cap spent on the weight):

| twin | what it asserts | why it reds |
|---|---|---|
| `test_constraints::test_bench_style_instance_round_trip` | `sol.wall_s < 5.0` on a 50x50 grid | 18.7 s — the dense block above (a PERF guard, not a surface law) |
| `test_constraints::test_cyxy_verify_matches_v1_census` | `res.wall["total"] < 10.0` on the real CYXY | 11.3 s through the pipeline API (the harness build is 9.95 s; the guard has ~0 headroom either way) |
| `test_stretches::test_the_solved_fixture_reads_zero_rows_in_both_readers` | "3 % is used, not just allowed" — a G-side stretch takes its 3 % | the body's datum holds the apron on its terrain, so the stretch uses 0.81 m where the twin wants > 0.86 m |
| `test_stretches::test_a_minted_step_on_a_g_side_mesh_edge_reads_at_g_cap_in_both_readers` | at most one junction row unpriced | two rows at 2.33 % / 1.77 % against a 1.5 % cap |
| `test_v2shapes::test_a_road_along_a_boundary_takes_its_shapes_level_and_the_step_stands_at_its_far_edge` | "the road at one level (A's)" (spread < 0.5 m) | 0.65 m: apron A and apron B are two bodies at two terrain means, so the road along their boundary now tilts — which may be exactly what 09p (3) intends, or may be the free-road ruling being crossed |

### 14.7 Twins (`tests/auto_patch_v2/test_v2cyxy.py`)

* `test_a_taxi_crossing_rides_the_runways_crown` — §13.1's lock: the
  section across the slab is edge -> ridge -> edge, the ridge is the high
  point, and no station of the crossing sits below BOTH its neighbours.
* `test_the_apron_roles_are_the_bodies_the_datum_sits` — the register:
  never the runway family, never the taxi family, never a road.
* `test_each_apron_sits_on_its_own_terrain_mean` — two aprons on benches 3
  m apart, joined ONLY by a taxiway: each body's mean z is its own terrain
  mean within 0.5 m, and the difference between them is the benches' own.
* `test_the_taxiway_climbs_between_the_two_aprons` — the taxiway climbs at
  least 80 % of the ground's rise, in the ground's direction.
* `test_the_body_datum_is_one_row_per_body_never_per_vertex` — the
  report's `body_datum_rows` equals the number of bodies.
* Falsification arm: at `body_datum = 1e-6` the two level twins FAIL.

## §15 ROUND 2 (RULINGS 2026-09-09r) — THE WOODBURY DATUM, THE RUNWAY x
## RUNWAY CROSSING, AND THE SETTLING POLISH — lane `v2cyxy`

### 15.1 What is added

1. **(09r (1)) THE PER-BODY DATUM LEAVES THE FACTORISED MATRIX.**
   `assemble` accumulates the body rows in their own `_Rows` (`Base.body`)
   instead of the always-on matrix; `solve/linear._linear_solve` takes them
   as the low-rank term `U` and applies the WOODBURY identity
   `(M + UᵀU)⁻¹ = M⁻¹ − M⁻¹Uᵀ(I + U M⁻¹ Uᵀ)⁻¹ U M⁻¹`.  Three modes
   (`LOW_RANK_MODES`): `bordered` (default) solves the augmented
   quasi-definite system `[[M, Uᵀ], [U, −I]]`, whose Schur complement onto
   the border IS the identity's `k x k` dense system — ONE sparse solve, no
   `k` back-solves; `woodbury` applies the identity explicitly (the twin's
   reference); `dense` stacks the rows as ordinary rows (round 1).
2. **(09r (2)) THE PRIMARY RUNWAY GOVERNS A RUNWAY x RUNWAY CROSSING.**
   `constraints/runway_chord.crossing_primary` (longer runway; tie: higher
   code letter; tie: lower id) and `runway_crossing_release` read the
   `runway_crossing` faces' `A+B` refs and return, per SECONDARY, the
   station spans within `[design] crossing_release_m` (200 m) of the
   crossing along its OWN axis.  Inside them the secondary contributes no
   chord target, so a shared-slab vertex takes the PRIMARY's chord and a
   secondary vertex takes none.  Its pins, profile rows and hard laws are
   untouched.
3. **(09r (3)) THE POLISH RUNS ITS ROUNDS.**  The stall break is deleted;
   the loop runs to `[design] polish_rounds_max` and reports the failure BY
   NAME (`hard_worst`) when the set is not held.  `line()` now says HARD SET
   SETTLED as well as NOT SETTLED.
4. `solve/linear.py` is split out of `solve/design.py` (the 1,000-line file
   law): the linear solve, the objective and the term energies.

### 15.2 CONSUMER TABLE (owner 2026-08-30l)

| consumer | reads | ruling |
|---|---|---|
| `solve/design.assemble` §9b | produces the body rows | now into `Base.body`, never `Base.rows` (twin) |
| `solve/design.solve_design` `_stack` / `_inner` | the base matrix | UNCHANGED shape; `Ub, cb` ride beside it |
| `solve/linear._objective` | the line search's descent test | the body term is ADDED to it — held out of the factorisation, never out of the objective |
| `solve/linear._term_energies` | base rows by owner tag | the `body_datum` bucket is computed separately and merged, so the report keeps the term |
| `DesignReport.rows` | the row count | includes the low-rank rows |
| `solve/why.py` | the ONE-SIDED rows and their duals | UNTOUCHED (a base row carries no dual) |
| `constraints/runway_chord.runway_chord_targets` | `preferred_z` | drops the secondary's targets inside the release; every other target is unchanged |
| `constraints/runway_profile` | pins, profile, crown, K, transverse | UNTOUCHED: the release is a TARGET release, never a law release |
| `emit/*`, `verify/*`, `harness/census.py` | the solved z | UNTOUCHED: no new geometry, no new sidecar key, no new law family |
| `law/design_schema.check_design` | the `[design]` table | `crossing_release_m` positive, `polish_rounds_max >= 1`; `hard_max_rounds` renamed |

### 15.3 MEASUREMENTS

**(1) THE WOODBURY WALL — HECA, same rounds, same surface.**  With the
polish capped at round 1's effective 2 rounds the arm is BYTE-IDENTICAL to
round 1 (`body_sha 87b241d8319b`, 315 active-set rounds, worst hard row
0.1488 m — the same numbers §14.4 records), so the delta is the linear
algebra alone:

| arm | solve | total | rounds | s / round |
|---|---|---|---|---|
| 09j control (no datum) | 29.31 s | 176.75 s | 317 | 0.092 |
| round 1 (dense block) | 105.26 s | 241.30 s | 315 | 0.334 |
| **round 2 (Woodbury)** | **43.42 s** | **196.87 s** | 315 | **0.138** |

The dense `O(Σ N²)` block is GONE — 62 of the 76 s the datum cost (81 %)
is recovered, per round 0.334 -> 0.138 s.  The **bar (within 10 % of 29.3
s) is MISSED**: 43.4 s is +48 %.  The residue is not the datum's rows in
`AᵀA` (they are not there) but the border's own fill: 342 extra rows and
columns whose Schur complement is a dense 342 x 342 block inside one
factorisation per round.

**(2) THE CROSSING, CYXY** (`CYXY_final`, 11.1 s, `body_sha f602f09b4e39`):

| reading | 1.0.297 / round 1 | round 2 |
|---|---|---|
| 14R/32L deepest local V | 1.61 m | **1.07 m** |
| 14L/32R deepest local V | 1.34 m | **1.31 m** |
| 14R/32L bow vs its chord | −2.25 m | **−1.64 m** |
| 14L/32R bow | −1.82 m | −1.81 m |
| 02/20 bow | −0.13 m | −0.07 m |
| verify DEFECT families | {} | **{}** |
| census ADJUDICATED | 280 | **275** |
| taxiway G along its line | 701.85..703.18 | 701.45..703.05 |

**The bar (the primary's ridge monotone, the dip gone) is MISSED, and the
residual is ATTRIBUTED.**  02/20's ridge now climbs from its north CIFP pin
at EXACTLY its 1.5 % longitudinal cap for 130 m, peaks at 696.55 at the
14R/32L crossing (02/20 station 166 m; 694.334 + 0.015 x 166 = 696.82) and
descends at exactly −1.5 % into its south pin at 693.72 — which is 02/20
station 381 m, and the 14L/32R crossing sits at 02/20 stations 388-415 m,
i.e. ON that threshold.  The crossing elevation is therefore the MAXIMUM
02/20's own pins and cap permit; the mains' chords want 1.1 m and 1.3 m
more.  The release does everything the ruling asks and the remainder is the
two things the ruling KEEPS: the secondary's CIFP thresholds and its
longitudinal law.  §13.3's option (a) assumed a 400 m run to the crossing;
at CYXY the runs are 166 m and 15 m.

**(3) THE HARD SET DOES NOT SETTLE ON A REAL AIRPORT.**  The loop is
implemented as ruled.  Measured, the augmented-Lagrangian multiplier
sequence does not converge at CYXY or HECA at any weight tried — it
OSCILLATES while the one-sided active set re-forms under it:

```
CYXY, hard_weight 3e5, 12 rounds:  .037 .027 .039 .101 .076 .057 .054 .026 .057 .034 .097 .098
```

| arm | CYXY | HECA |
|---|---|---|
| 3e5, 2 rounds (shipped) | 0.0267 m, solve 3.5 s, DEFECTs {} | 0.1488 m, solve 43.4 s, DEFECTs {} |
| 3e5, 12 rounds | 0.0261 m, solve 8.8 s, DEFECTs {} | 0.1270 m, solve 133.0 s, 05C/23C bow −2.28 -> **−2.76 m** |
| 1e6, 12 rounds | 0.0219 m, solve 13.9 s | not run |
| 1e7, 12 rounds | 0.0170 m SETTLED, 0 rounds, solve 5.8 s | 0.0276 m NOT settled, solve 280.4 s |

Two findings ride on that table.  (a) `polish_rounds_max` is set to **2**
from it: beyond two rounds the polish buys no law and costs surface — at
HECA 0.02 m of hard violation for +90 s of solve and half a metre of bow,
and the "best iterate" the loop keeps is best by HARD VIOLATION, which is
not best by surface.  (b) Raising `hard_weight` is not a free settle: 1e7
settles CYXY outright but MOVES THE WIDER SURFACE — five further twins red
(the m3c lawful road leaves its core profile, 37 route-budget rows at the
taxi-route pairs, the v2ridge falsification arm 6.0 -> 4.3 m) — and does
not settle HECA at all.  **09r (3) is not achievable with this polish**;
the certificate it asks for needs the hard rows solved as a KKT block (the
module docstring's own claim) rather than by penalty and multiplier.

### 15.4 THE TWINS

New in `tests/auto_patch_v2/test_v2cyxy.py`: the Woodbury/dense/bordered
parity on a three-body fixture (same z within 1 mm), the mechanism twin
(no `body_datum` row reaches `Base.rows`), the primary register, the row-level
release, the primary's ridge monotone through the crossing, the secondary
climbing into it inside its own grade and K with its thresholds pinned, the
settled certificate on a reachable crossing, and the NAMED FAILURE on one
that is not.  Re-scoped per 09r (4): the two wall-time guards (bench 18.7 ->
8.4 s, guard 5 -> 12 s; CYXY pipeline 16.1 s, guard 10 -> 22 s), the two
`test_stretches` expectations and the junction/oracle envelopes (to the
datum's own trade), and the road twin's level (0.65 m of tilt across a 4 m
step between two bodies).

**ONE TWIN LEFT RED, deliberately.**
`test_v2shapes::test_a_road_along_a_boundary_takes_its_shapes_level_...`
now mints `service_road|service_road` `within_shape` census rows of 0.24 -
0.29 m: with apronA and apronB on two terrain means, the road along their
boundary tilts and prices its own cross-section.  09r (4) named this as
"what 09p (3) intends, or the free-road ruling being crossed".  It is a LAW
question (RULINGS 2026-07-27: a road edge-sharing an apron IS the apron),
so the lane re-scoped the twin's LEVEL assertion and left its CENSUS
assertion standing for the owner.
## §13 THE LEVEL RINGS ARE DELETED AND THE ENGINE BLENDS THE BANK
## (RULINGS 2026-09-09p (1) / 2026-09-09t) — lane `v2bankblend`

NOTE ON NUMBERING: the brief names this section §16; the spec ended at
§12, so it lands as §13.  Reported, not decided.

### 13.1 What changes

Two changes, one on each side of the step boundary.

1. EMIT.  `emit/bank.py` emits ONE closed `bank_foot` ring per boundary of
   the banked region and NOTHING between it and the patch ring.  The level
   rings of 09f-1 / 09h / 09i (1) / 09j are deleted with the law keys that
   sized them (`bank_ring_spacing_m`, `bank_first_ring_m`) and their
   schema validations.  The daylight foot (09g), the foot chain's plan
   smoothing (09e/09f, `smooth_along` / `smooth_runs`), the ray limit, the
   `_push_off` collar and the one-region union all STAY: nothing about
   where the foot stands changes.

   WHY: 09t measured that a level ring re-emits the FOOT's own edges
   wherever the bank is narrower than the level's offset `t` — the
   `cov.buffer(t) ∩ banked` ring degenerates onto the foot there, its
   vertices snap to the foot's node ids and the closed way lays a SECOND
   constrained segment on each of them.  Triangle's segment recovery then
   spins forever at HECA (1 h 40 min in `formskeleton → insertsegment →
   scoutsegment → finddirection`, killed) and errors at HEAZ
   (`segmentintersection(): Topological inconsistency` at node −4798,
   shared by `bank:6` and `bank@2..@5`).  The `minted == 0` guard catches
   only the ring that degenerates EVERYWHERE, never the partial case, and
   the spacing sets only how many partial cases there are.  The +30+031
   tile is unbuildable at 1.0.297.

2. ENGINE.  Inside a BANK ANNULUS — the ground between the design
   coverage and its `bank_foot` ring — a free interior vertex takes its
   altitude LINEAR IN PLAN DISTANCE between the two rings

       z(v) = z_in(p) + (z_out(q) − z_in(p)) · d_in / (d_in + d_out)

   with `p` the nearest point of the design coverage boundary, `q` the
   nearest point of the foot ring, `d_in = |v − p|`, `d_out = |v − q|`.
   That replaces the GRAPH-harmonic extension
   (`interpolate_free_interior_altitudes`) for those vertices ONLY; every
   other face — every design face, every road ribbon, every trench floor —
   is untouched, because the annulus vertices simply join the Dirichlet
   set before the one harmonic solve runs, exactly as the ring-segment
   split values of the 2026-09-06 amendment already do.

   WHY the engine and not the emitter: 09h/09j/09t measured the harmonic
   extension squeezing any band wider than its innermost against the inner
   ring (111 % → 46 % → 104 % → 0.43 at 5 m spacing), and the only remedy
   an emitter has is to author more rings — which is the defect above.
   The bank is a RULED SURFACE by construction; a metric interpolation
   reproduces it exactly with whatever vertices Triangle4XP happened to
   put in the annulus.

### 13.2 CONSUMER TABLE (owner 2026-08-30l), BEFORE editing

G. THE LEVEL RINGS DELETED.  No shape class, region, breakline kind or
register entry is added; the `bank_foot` kind, the `o4_feature=bank_foot`
tag and the `bank:N` ref shape are unchanged, so every A-row of §9.2 and
every C-row of §10.2 stands.  What the deletion touches:

| # | consumer | reads | ruling |
|---|---|---|---|
| G1 | `emit/bank.intermediate_offsets` (§11.2 E2) | `d`, spacing, first | DELETED with its twin `test_the_offsets_start_at_the_first_ring_then_run_every_spacing`; the level SCHEDULE no longer exists. |
| G2 | `emit/bank.with_bank`'s level loop, `_local_foot`, `_WELD_M`, `_MIN_LEVEL_AREA_WIDTHS` | the banked region, the bank field | DELETED — they exist only to place level vertices.  `_inner` STAYS: the foot's own distance statistic reads it. |
| G3 | `emit/bank.BankReport` `face_rings` / `face_vertices` / `face_levels` / `face_rings_invalid` | the report | DELETED with the `line()` clause that printed them.  `pipeline/build.py:577` `_dc.asdict(brep)` carries whatever fields exist; grep shows one write and no reader of `report["bank"]` outside the build log. |
| G4 | `law/emit.toml [design]` `bank_ring_spacing_m`, `bank_first_ring_m` | the law table | DELETED with their `check_design` validations.  `law/model._build` REFUSES an unknown key, so the TOML and the schema must land in the same commit — they do. |
| G5 | `law/design_schema.DESIGN_TERMS`, `solve/design.py` | objective weights | UNAFFECTED: neither key was a weight (as `bank_slope` is not). |
| G6 | `tests/auto_patch_v2/test_v2bank.py` (3 twins), `test_v2daylight.py` (2 assertions + the level-validity twin) | `intermediate_offsets`, `face_*`, the spacing | RE-SCOPED: a 6 m ring emits its FOOT and NO level ring; the concave-cover validity twin is deleted with the construction it defended. |
| G7 | `tools/patch_seed_seal.py` (the offline replay) | the emitted patch's closed ways | UNAFFECTED IN KIND and STRICTLY EASIER: the duplicate-segment class it was built for cannot arise from one ring per boundary.  Run on the twin patch and on the HECA patch as acceptance. |
| G8 | `O4_Vector_Map.include_patches` | closed patch ways | one closed way per boundary instead of one plus N levels: `patches_area_polys`, `interp_alt_patch_polygons` and the per-face INTERP_ALT seeding are all unchanged in KIND; the annulus is again ONE face per boundary and takes ONE seed. |
| G9 | `O4_Vector_Map.interp_alt_seed_point`, `audit_interp_alt_seed_sealing` | the arrangement's faces | UNAFFECTED — the degenerate-face clearance of 09j stays; there are simply far fewer near-coincident rings for it to skip. |
| G10 | `tools/check_grade.py`, `tools/undulation.py`, `verify/*`, the sidecar | `o4_feature` | UNAFFECTED via §9.2 A8–A12: the register is the same one. |
| G11 | `emit/osm_adapter.render_patch` / `write_tile_pieces` | breaklines | UNCHANGED CODE: closed-or-open by `vertices[0] == vertices[-1]`; only the ref shape `bank:N@L` stops occurring. |

H. THE ENGINE BLEND (`O4_Mesh_Utils`).  ONE new function,
`bank_annulus_blend_values`, and ONE call site inside
`post_process_nodes_altitudes`, placed between the ring-segment split
values and the harmonic solve.

| # | consumer | reads | ruling |
|---|---|---|---|
| H1 | `O4_Mesh_Utils.interpolate_free_interior_altitudes` | free vertices + Dirichlet data | UNCHANGED CODE.  Annulus vertices arrive as Dirichlet data, so the harmonic system is solved over the remaining free vertices exactly as before.  Every other face is bit-identical. |
| H2 | `O4_Mesh_Utils.patch_valued_vertex_indices` | `PATCH_RING_MARKER` edges | UNAFFECTED — the discriminator is unchanged; the blend ADDS to the set it returns, it does not redefine it. |
| H3 | `O4_Mesh_Utils.patch_segment_split_values` (2026-09-06 amendment) | inserted vertices on ring segments | RUNS FIRST and is unaffected: a vertex ON a ring is patch-valued before the blend looks for annulus vertices, so a foot-ring split vertex keeps the ring's own value. |
| H4 | `O4_Mesh_Utils.patch_coverage_polygon` / `triangles_inside_coverage` (R18-1c) | the `.poly`'s patch rings | UNAFFECTED: the annulus is inside the coverage (the foot ring is a patch ring), so its triangles are admitted exactly as today.  The blend is a strict subset of the vertices R18-1c already admits. |
| H5 | `O4_Mesh_Utils.audit_interp_alt_extent` (the leak detector) | the vertices the SOLVE moved | UNAFFECTED and still meaningful: annulus vertices are no longer in `changed_indices` (they are Dirichlet), and they lie inside the coverage anyway, so the detector's population shrinks and its verdict cannot change. |
| H6 | `O4_Mesh_Utils.post_process_nodes_altitudes`'s final `interp_alt_tris` copy (`z = column 5`) | column 5 | UNAFFECTED CODE — the blend writes column 5 only, like every other law in this function. |
| H7 | `O4_Mesh_Utils.py:805` (the sea-levelling precedence lane `v2water` is editing, RULINGS 2026-09-09o (3)) | the triangle attribute | NOT TOUCHED.  The blend is a separate function called from a separate line; the two lanes' diffs do not overlap. |
| H8 | the INTERP_ALT SEED AUDIT (`O4_Vector_Map.audit_interp_alt_seed_sealing`) | step 1's arrangement | UNAFFECTED: the blend runs in step 2, after Triangle4XP, and writes no vector geometry. |
| H9 | `O4_Vector_Map.include_patches`' file selection (manual before auto, `resolved_auto_patch_mode`) | the patch dir | REUSED, not re-derived: the blend's geometry reader imports `resolved_auto_patch_mode` lazily (no import cycle — `O4_Vector_Map` does not import `O4_Mesh_Utils`) and applies the same manual-first / mode filter, so the two steps read the same patch files. |
| H10 | the patch `.osm` files | closed ways + `o4_feature` | READ IN STEP 2.  Not a new artifact across the step boundary — it is the SAME source `include_patches` reads, and `_auto_patch_post_mesh_rebake` already reads the patch dir from this module.  The `.poly` carries no `o4_feature`, and a marker bit for the foot ring would change what Triangle4XP is handed, which is precisely the class 09t killed the tile with. |
| H11 | the mesh's other laws (water/sea smoothing, apt.dat RUNWAY/TAXIWAY/APRON regions, `_interp_alt_only_tris` scoping) | triangle attributes | UNAFFECTED: the blend is scoped to free vertices of `attr == INTERP_ALT` triangles inside the patch coverage AND inside a bank annulus. |
| H12 | tiles with NO v2 patch (a v1 patch, a manual patch, no patch at all) | the patch dir | NO-OP by construction: no `o4_feature=bank_foot` way ⇒ no annulus ⇒ empty dict ⇒ the harmonic extension runs exactly as today.  A read failure is a WARNING and the same no-op, never a failed tile. |

### 13.3 How the annulus is identified (the geometry)

From the patch `.osm` files of the tile, in tile-relative coordinates:

* `design_cov` = the union of every CLOSED way that is NOT
  `o4_feature=bank_foot` — which is `emit/bank.coverage_polygon`'s own
  `cov`, the union of the planar faces.
* the `bank_foot` closed ways are the RINGS of the banked region.  A ring
  whose polygon meets `design_cov` is an EXTERIOR ring; one that does not
  is a HOLE of the banked region (design coverage is a subset of the
  banked region, so a hole can contain none of it).
  `banked = ∪exteriors − ∪holes`.
* `annulus = banked − design_cov`.

The Z DATA comes from the `.poly`, never from the `.osm`: every
`PATCH_RING_MARKER` edge carries its two endpoints' altitudes in column 5
of the vertex array (the same source `patch_segment_split_values` reads).
Each such edge is classified by its midpoint — within
`PATCH_SEGMENT_SPLIT_TOLERANCE * 100` of the foot linework it is an OUTER
segment, otherwise if it is on `design_cov.boundary` it is an INNER
segment, and an edge strictly inside the design coverage (a face-to-face
rim) is neither.  `d_in` / `z_in` come from the nearest INNER segment,
`d_out` / `z_out` from the nearest OUTER segment: the nearest segment of a
set IS the set's nearest point, so one `STRtree.nearest` per side gives
both the distance and the segment to interpolate z along.

DEGENERATE CASES, all resolved to "leave it to the harmonic extension":
no inner or no outer segment in range, `d_in + d_out == 0`, a non-finite
z.  Nothing is written for a vertex the reader cannot place.

### 13.4 Twins

* `tests/auto_patch_v2/test_v2bank.py` re-scoped: a 6 m ring emits its
  foot ring and NO level ring (`"@" not in ref` for every `bank_foot`
  breakline), the foot's z is still the DEM, the daylight twins unchanged.
* `tests/test_mesh_bank_annulus_blend.py` (the ENGINE's conventions, like
  `tests/test_r18_free_interior_altitudes.py`): a synthetic annulus
  between a square patch ring at z 10 and a foot ring at z 0, meshed by
  the function's own inputs — every interior vertex within 0.05 m of the
  linear value, and no triangle steeper than the ring-to-foot slope.

### 13.5 Build-time impact statement

EMIT: the level-ring construction is deleted — 09t measured the bank pass
at 12.8 s at HECA (13 % of the 60 s per-airport budget) with the rings.
Deleting them removes every `buffer` / `intersection` / `snap` / per-vertex
`_local_foot` ray and leaves the daylight walk and the foot chain, which
09h measured at 1.0 s.  A REDUCTION of roughly 12 s, reported in §13.6.

ENGINE: one shapely read of the patch `.osm` (the same files step 1
parses), one union, and two `STRtree.nearest` queries per annulus free
vertex.  Against the tile budget (300 s) it is a fraction of a second;
the material change is that Step 2 stops spinning in segment recovery.

### 13.6 MEASUREMENTS (lane `v2bankblend`, branch `claude/v2bankblend`)

THE HECA AIRPORT BUILD (`build_airport.py HECA --engine v2`, tag
`v2bankblend`, 165.5 s, solve 29.03 s, `body_sha f2fc42082abc`):

* THE DESIGN SURFACE IS BIT-IDENTICAL: `objective 560668.3156424803`
  (09j/09t's 560668.3156), residual `pin 0.0000 diff 3.4513 flat 0.0000
  band 3.8066 offset 0.0000` — the bank runs after the solve and the
  deletion touched nothing the solve reads.
* THE BANK, feet only: 175 rings banked (9,826 boundary vertices → 5,542
  foot nodes, 163 repaired, 0 skipped), DAYLIGHT 7,219 at the minimum /
  2,607 daylighted / 0 at the maximum (09i/09j's classification to the
  vertex), toe in 468 smoothing runs; foot distance min 5.0 / mean 7.0 /
  p95 14.7 / max 76.0 m; bank slope p95 0.350 / max 1.529.
* BANK PASS WALL **0.93 s**, against 09t's **12.8 s** with the level
  rings — a 11.9 s reduction, 20 % of the 60 s per-airport budget.  Emit
  3.02 s, 1,366 ways / 28,878 nodes (09t's 5 m arm: 2,112 / 47,208).
* `tools/patch_seed_seal.py` PASSES on the HECA patch (1,363 closed rings,
  1,454 seeds, 0 faces refused a seed, all enclosed) and on the twin patch
  (2 rings, 2 seeds, 0 refused).

THE TILE MESH (`run_tile_mesh_only.py 30 31 1 --patches-as-is`, the HECA
+ HEAZ patches of this branch on disk):

* rc 0.  **Step 1 56.7 s, Step 2 1 m 0 s** — against 09t's 1 h 40 min
  spin at 3 m spacing and rc 1 at 5 m, and inside the bar (1.0.296's
  2–3 min).
* THE SEED AUDIT PASSES: "0 road-cut sub-cell(s) seeded INTERP_ALT beside
  the 2,314 face seed(s) already placed (0 degenerate face(s) skipped)";
  "INTERP_ALT seal: all 2,314 seed(s) enclosed by INTERP_ALT edges
  (13,522 bounded face(s), 304,515 marked edge(s))".
* THE BLEND FIRED: "Bank annulus: 40 free vertex(es) took the 1:3 bank's
  own altitude"; 3,578 mesher-inserted vertices took a ring's own value;
  99 free interior vertices of 99 took the harmonic extension.

THE WHOLE TILE (`build_airport.py HECA --engine v2 --tile 30 31
--refresh-data dem`, tag `v2bbtile`): **rc 0, 450.3 s** — step 1 vector
217.7 s, step 2 mesh 55.8 s, step 3 masks 1.3 s, step 4 tile 175.0 s.
"shared repo UNCHANGED by this build (full-surface before/after
snapshot)" and "refresh scope 'dem' was authorised but wrote NOTHING".
HEAZ MESHES — 09t's `segmentintersection(): Topological inconsistency` at
HEAZ node −4798 is GONE, and HEAZ's own rings are in the 2,314 sealed
seeds.  Objects: 392 object files written, 7,945,305 vertices, 7 reverted,
6 findings; 43 units (1 deck-founded), 42 baked, 0 held; 5,221 of 5,261
clusters seated, 32 under the 1 m threshold, 8 refused, 596 pad requests;
HEAZ no unit to seat (47 resources skipped at plan time).

### 13.7 THE TRANSECT: ONE BAR MET, ONE MISSED — and what it attributes

TRANSECT 2 (lon 31.4350, lat 30.10730–30.10830, 2.2 m stations) — **PASS**:
a continuous cut bank 130.82 → 138.51 m over 27 m at 0.245 for twelve
stations, one station at **0.255**, then the DEM.  Max 0.255, bar 0.35.

TRANSECT 1 (lon 31.3819142, lat 30.11630–30.11680, 2.2 m stations) —
**MISS**: 62.63 m down to 53.94 at a constant 0.247 for fifteen stations,
then three stations at **0.527 / 0.618 / 0.618**, then the DEM at 49.5.
Max 0.62, bar 0.35.  (The history at this site: 09h 1.11, 09i 0.46, 09j
0.76, 09t 0.43 at 5 m spacing WITH THE TILE UNBUILDABLE.)

ATTRIBUTED, and the attribution is the finding of this round:

1. THE ENGINE'S FIELD IS EXACT.  Of the 11,153 mesh vertices inside the
   annulus, EVERY one carries the blend field to within **4.7 mm**
   (mean 0.5 mm, p95 4.7 mm) — measured against an independent
   recomputation of `z_in + (z_out − z_in)·d_in/(d_in+d_out)` from the
   tile's own `.poly` and patch `.osm`.  Nothing about the interpolation
   is wrong.
2. THE ANNULUS HAS ALMOST NO FREE VERTICES TO INTERPOLATE.  Only **40**
   of those 11,153 are FREE — the rest are ring nodes and mesher-inserted
   ring-segment splits.  Triangle4XP puts essentially nothing inside the
   bank: on transect 1 there is no vertex at all across 32 m of it.  So
   the bank's shape is the RING→FOOT TRIANGULATION, and the blend, while
   exactly right, is not what carries it at HECA.
3. THE RESIDUAL IS THE TRIANGULATION.  Over the whole tile's annulus,
   18,168 triangles: |grad| p50 0.105, p90 0.367, p95 0.550, max 34.6;
   12.4 % over 0.35, but only **3.43 % by area** — the tail is thin
   skewed triangles that join a ring vertex to a foot vertex at a
   DIFFERENT bank width (the daylight foot varies 5.0–76.0 m).  A ruled
   surface between two rings sampled at different densities is not a
   plane, and a triangulation with no interior vertices cannot render it.

REPORTED, NOT DECIDED (the remedy is a spawner/owner call, and it is a
spec-time mechanism, not a lane fix):

* The level rings were also, incidentally, what put VERTICES in the
  annulus.  09p (1) ruled the squeeze out of the engine, which is done and
  measured; it did not rule how the annulus gets vertices.
* Two candidate remedies, neither attempted here.  (a) ENGINE: give the
  annulus a Triangle REGION MAX-AREA constraint so Triangle4XP refines it
  — `O4_Vector_Utils.write_poly_file` writes region records as
  `idx x y marker` with no area column, so this changes what Triangle4XP
  is handed, which is the exact class 09t hung the tile with; it needs its
  own measurement round.  (b) EMIT: author the intermediate stations as
  ISOLATED INPUT NODES rather than closed ways — vertices with no
  constrained segment cannot duplicate the foot's edges, which was 09t's
  whole failure mode; the patch `.osm` / `include_patches` path has no
  way to carry a node without a way, so it needs a new mechanism.
* `v2_rebake_replay.py bodies`: **143** components stranded after the
  rigid-body completion (188 members affected), against 09t's 461 on the
  5 m plan.  Above 09d's bar of 2, unrelated to the bank (the strandings
  sit at 30.11212,31.41203 inside the terminal block, not in any annulus),
  and carried forward as the standing seat residual.

---

## §13.8 THE ANNULUS AS A TRIANGLE REGION — implemented, and REFUTED in
## the vendored binary (RULINGS 2026-09-09x; lane `v2bankblend` round 2)

09x ruled remedy (a) of §13.7: write the bank annulus as a Triangle
REGION carrying `max_area = (w / [design] bank_triangle_divisions) ** 2`,
run Triangle4XP with `-a`, "and the blend then has vertices to carry it".

### §13.8.1 THE LAW AND ITS ONE DERIVATION SITE

`[design] bank_triangle_divisions = 3.0` (`design_schema.Design`,
validated `>= 1.0`).  `O4_Mesh_Utils.bank_annulus_region_areas(tile,
seeds)` is the single derivation: it reuses `bank_annulus_polygon` and
`_bank_rings_from_patches` — the SAME rings, read from the SAME patch
`.osm` files, that `bank_annulus_blend_values` rules the blend from — so
the two steps can never disagree about where the annulus is.

WIDTH AT THE SEED (the choice §13.7 left open): `w = d_in + d_out` at the
region's own seed point — the very sum the blend law divides by, at the
same point, so the region is refined in exactly the metric the blend is
ruled in.

A PER-COMPONENT MEDIAN WAS TRIED FIRST AND IS WRONG.  Measured at HECA:
the annulus is **212 connected components and ONE of them holds 60 % of
its area** (2.74 km²) — every ring's bank, merged wherever two feet meet,
with the ground BETWEEN the airport's bodies inside it.  A component
median read a 319 m "bank" against a measured foot distance of
5.0–74.4 m.  The per-seed width is also self-limiting: a seed out in that
merged interior is far from both rings, gets a large area, and is left
effectively unconstrained — which is right, because that ground is not a
bank.

UNITS — AND A FRAME TRAP.  `_bank_rings_from_patches` **already** returns
the isotropic frame `(x·scalx, y)` (it scales as it reads the `.osm`
nodes), which is what `bank_annulus_blend_values` relies on; scaling it
again reads every bank `1/scalx` too narrow.  The first cut did exactly
that and passed a 10 % twin (51.7 m for a 60 m bank at lat 30) — the twin
now asserts the width to **2 %** and is the frame's pin.  Only the SEEDS,
which arrive in raw tile-relative degrees, are scaled; the resulting area
is divided by `scalx` to land in the `.poly`'s own (lon × lat degree)
units.

MEASURED at HECA +30+031 (2,910 region records): **214 sized**, all
marker 8, `max_area` 2.8 – 262,648 m² (median **4.1 m²**, i.e. ~2 m
triangles); implied bank width median **6.1 m** against the emitter's own
foot distance mean of 6.9 m.  Derivation cost **0.56 s** in the tile's
step 1 (0.19 % of the 300 s tile budget; the 60 s airport budget is not
touched — this runs only in the tile's vector step).

### §13.8.2 CONSUMER ROWS — every reader of a region record

| Consumer | Reads | Ruling |
|---|---|---|
| `O4_Vector_Utils.Vector_Map.write_poly_file` | `self.seeds`, new `self.seed_areas` | writes a FIFTH field only for a seed that carries an area; every other record byte-identical |
| `O4_Vector_Map.size_bank_annulus_regions` | the seeds about to be written | new; marries `bank_annulus_region_areas`' answer to the seed list, never raises |
| `Triangle4XP` `readpoly` (`:15009`) | region section | a 5-field record is read as `x y attribute area`; a 4-field one sets `area = attribute` (`:15035`), NOT `-1` — the ruling's "regions without an area are unconstrained" is Shewchuk's rule, not this fork's. HARMLESS: markers are 1–128 in SQUARE DEGREES beside a 1 deg² tile |
| `Triangle4XP` `regionplague` (`:13478`) | `regionlist[4i+3]` | spreads the area with the attribute; unchanged behaviour, and the plague's segment-blocked flood is untouched |
| `Triangle4XP` `testtriangle` (`:7193`) | — | **DOES NOT READ `areabound` AT ALL.** See §13.8.3 |
| `Triangle4XP` `regionplague`, marker 0/1 regions, after a binary fix | area = attribute | `DUMMY` 0 → `areabound 0` → the `> 0.0` guard leaves it unconstrained; `WATER` 1 → 1 deg² on a 1 deg² tile, never binding. No landmine either way |
| `O4_Mesh_Utils.generate_mesh` | `Tri_option` | `a` rides with `A` exactly (`regional_areas = "a" if do_refine == "A" else ""`): with `-r` Triangle4XP demands an `.area` file and exits 1 (`:11743`) |
| `O4_Mask_Utils` / `O4_Imagery_Utils` `write_poly_file` | their own vector maps | never populate `seed_areas`, so their `.poly` files are byte-identical |
| `bank_annulus_blend_values` | free vertices in the annulus | unchanged; it simply gets more of them |

### §13.8.3 REFUTED: `-a` IS INERT IN THIS FORK

The ruling calls the region area "a standard Triangle facility".  It is —
in Shewchuk's `Utils/src/triangle.c`, whose `testtriangle` compares the
triangle's area against `areabound(*testtri)` at **line 7336**.
`Utils/src/Triangle4XP.c` HAS NO SUCH LINE: the fork rewrote
`testtriangle` around the DEM-curvature criterion and dropped the area
test with it.  `grep areabound Triangle4XP.c` returns the macro, the
propagation copies (`:8567`, `:8749`, `:9028`), a debug `printf` and the
two setters — the value is stored, spread, and read by no quality test.

A SECOND, independent blocker sits on top: `testtriangle` opens with
`if (attribute >= 8) return;` ("Refinement in INTERP_ALT tris is
useless").  The bank annulus is INTERP_ALT (marker 8).

MEASURED, interventionally, on a synthetic 30 m annulus (184 input
vertices, region `max_area` 9.4e-9 deg² ≈ 100 m², annulus triangles
≈ 150 m²), the shipped `Utils/mac/Triangle4XP`:

| arm | vertices in → out | triangles |
|---|---|---|
| no area column, no `-a` | 184 → 184 | 262 |
| area column + `-a`, marker 8 | 184 → **184** | 262 |
| area column + `-a`, marker 0 | 184 → **184** | 262 |

Triangle prints `Spreading regional attributes and area constraints`, so
the flag IS parsed and the area IS read; nothing consumes it.  (The same
null result on a plain unit square at markers 0 and 8, areas 1e-7/1e-8.)

### §13.8.4 THE COUNTERFACTUAL — nine lines of C would meet the bar

`Triangle4XP.c` with the stock area test restored AHEAD of the INTERP_ALT
exemption (the area is already computed a few lines below; the patch
hoists it and adds the `b->vararea` test), rebuilt with `cc -O2`:

| arm (same fixture) | vertices in → out | free vertices in the 30 m band |
|---|---|---|
| shipped binary, `-a` | 184 → 184 | 0 |
| patched binary, **no** area column | 184 → 184 | 0 |
| patched binary, `-a` + area | 184 → **314** | **130** |

and with the ruled blend on those vertices the annulus's edge slopes come
back **p50 0.207, p90 0.331, max 0.333** against a ring-to-foot slope of
0.333 — **0 % over slope + 0.02**, i.e. §13.7's bar met exactly.  With no
region carrying an area the patched binary is identical to the shipped
one, so the change is inert on every tile that has no bank.

REPORTED, NOT DECIDED.  A vendored-binary change ships mac/win/lin
(`Utils/CMakeLists.txt`, `Utils/toolchains/`) and is well outside a lane's
authority.  The Python side above is landed and correct: it writes the
regions, sizes them, passes the flag, and costs nothing until the binary
can act on it.  `test_triangle_puts_vertices_inside_a_region_that_asks_
for_them` is `xfail(strict=True)` — the day Triangle4XP is rebuilt it
fails as unexpectedly-passing and this section is deleted.

### §13.8.5 LANDED: the vendored Triangle4XP is patched (RULINGS 2026-09-09aa/ab; lane `v2bankblend` round 3, merged `ea85d373`)

09aa ruled §13.8.4's counterfactual in.  `Utils/src/Triangle4XP.c` carries
the stock maximum-area test in `testtriangle`, inserted BEFORE the
`if (attribute >= 8) return;` INTERP_ALT exemption; the priority argument
is the shortest squared edge (round 2's 314-vs-306 band vertices differ
only in that argument — the slopes are identical).  `Utils/mac/Triangle4XP`
is rebuilt from it, `cc -O2 -arch arm64 -arch x86_64` (Apple clang 21), a
universal binary as the shipped one is, committed WITH the source and its
sha1 pinned by a twin
(`test_the_shipped_mac_triangle4xp_is_the_patched_binary`,
`TRIANGLE4XP_MAC_SHA1 = 7ca193114522035fb0449432431b14db02fe37e1`) so a
later rebuild that forgets the patch, or a merge that restores the
vendored binary, fails loudly instead of silently putting the bank back
on the ring-to-foot triangulation.  The region-area twin
(`test_triangle_puts_vertices_inside_a_region_that_asks_for_them`) is no
longer `xfail`: it is a HARD twin on macOS, asking for at least
`BANK_REGION_MIN_FREE_VERTICES = 40` free vertices in the 30 m band and
measuring **306 output vertices from 184 in — 122 free vertices inside
the band**.  The win/lin binaries still carry the old test, so both twins
skip off macOS with that reason; the release CI owns the rebuild
(`docs/DEFERRED_VERIFICATION.md`).

MEASURED, HECA `+30+031`, mesh-only replay (`run_tile_mesh_only.py 30 31 1
--patches-as-is`): Step 1 **54 s** / Step 2 **63 s**, all 2,314 INTERP_ALT
seeds sealed, 214 sized regions (median `max_area` 4.1 m²); annulus
vertices carrying the blend **40 → 45,533**; annulus triangle slopes p50
**0.093**, p90 **0.329**, over the 0.35 bar **6.6 % by count / 3.1 % by
area** (round 2: 12.4 % / 3.4 %).  Transect 3 (lon 31.4150, lat
30.12955–30.13005, a 29 m east bank) max **0.124** PASS.  Transect 1
(lon 31.3819142) max **0.533** at three stations — MISSED, and attributed
in §13.9 below.  The whole tile aborted at Step 1 on the 09y runway
DEFECTs (lane `v2settle`'s, not the bank's); CYXY's patch on disk predates
the bank, so there is no transect there.

---

## §13.9 THE FIELD RUNS ALONG THE RING'S NORMAL (RULINGS 2026-09-09ab; lane `v2bankblend` round 4)

### §13.9.1 The law, and what it replaces

09t's field divided by `d_in + d_out`: the distance to the nearest ring
plus the distance to the nearest FOOT — **two different ring stations**
wherever the annulus pinches.  09ab rules the field along ONE ray:

    z(v) = z_ring(p) + (z_foot(p) − z_ring(p)) · min(1, d(v, ring) / D(p))

with `p` the nearest point of the design coverage boundary, `D(p)` that
ring station's daylight foot distance and `z_foot(p)` that station's foot
altitude.  Both ends of the ratio belong to one ray, so the slope along
every normal is exactly that ray's ring-to-foot slope — the daylight walk
already bounded it at 1:3 — and never steeper where the band pinches.

### §13.9.2 THE DATA PATH: how the mesh side recovers `D(p)` and `z_foot(p)`

BY RAY-CASTING, in `O4_Mesh_Utils._bank_foot_along_normal`, against the
foot linework `bank_annulus_blend_values` already reads.  `D(p)` is the
first foot crossing's distance along the ray and `z_foot(p)` is the foot
ring's own carried altitude (`.poly` column 5) interpolated along the
crossed edge at the crossing.  The ray is the NEAREST INNER SEGMENT'S OWN
OUTWARD NORMAL (sign taken from the side the vertex stands on), not the
direction `v − p`: `D` and `z_foot` are properties of `p` alone, so every
vertex a station carries — a corner fan included — shares one denominator
and the field stays continuous across the fan.  Measured on HECA transect
1: with `(v − p)` a grazing direction in a corner fan ran far before
meeting a foot and the mid-bank read **0.153** where the ring-to-foot
slope is 0.290; with the station's own normal the same stretch reads
**0.269–0.288**, the ruled value.

WHY NOT THE PUBLISHED-TAG OPTION.  Publishing a per-vertex `d` /
`z_foot` on the `bank_foot` way needs no new sidecar either, but it needs
a patch-FORMAT change on both sides — and the emitted foot ring is the
boundary of a UNION (`emit/bank.py`:
`unary_union([cov.buffer(min_w), *pieces])`), so its vertices do not
index-correspond to design-ring stations at all: the emitter would have
to publish the very nearest-point map the ray already inverts.  The ray
is mesh-local and needs neither.

FALLBACK.  A ray that meets no foot within `BANK_RAY_MAX_M` (400 m, twice
`bank_max_width_m`) keeps 09t's nearest-boundary value, so no vertex
reverts to the harmonic squeeze.  `BANK_BLEND_STATS` reports the split and
the tile log prints it.

### §13.9.3 Twins

`tests/test_mesh_bank_annulus_blend.py`.  The square-annulus twin is
UNCHANGED and green (the fixture is uniform in ring z, where both fields
agree).  New: `TestThePinchedAnnulusRunsAlongTheRingsNormal`, a PINCHED
annulus — two design bodies at **z 10 and z 30** standing **4 m** apart,
their banks merged so the gap between them is annulus with NO foot in it
and a **57 m** foot outside, the foot's z the daylight 1:3 below its own
body and its ring densified to 5 m so a constrained edge never spans a
daylight jump.  6,853 free vertices.  Asserted against an INDEPENDENT
reimplementation of the ray (nearest ring segment → its outward normal →
analytic ray/segment crossing), with tied corner-fan candidates all
returned because which station carries a fan vertex is genuinely
ambiguous:

* every vertex takes the ruled value — residual **0.0000 m**;
* no vertex is steeper than its own ray's ring-to-foot slope — worst
  ratio **1.0000**;
* the 4 m pinch itself is sampled (>100 vertices) and shallow;
* THE TRIPWIRE: 09t's own formula on the same geometry reaches
  **13.0×** that bound, so the twin measures the ruled change and not
  the fixture.

Suite (`tests/auto_patch_v2 tests/test_harness.py
tests/test_patch_seed_seal.py tests/test_interp_alt_degenerate_face.py
tests/test_mesh_bank_annulus_blend.py tests/test_mesh_water_precedence.py`)
**792 passed, 1 skipped** (788 on main + the 4 new).

### §13.9.4 MEASURED at HECA — the bar is NOT met, and why

`run_tile_mesh_only.py 30 31 1 --patches-as-is`, rc 0, shared repo
UNCHANGED.  Step 1 **53.4 s**, Step 2 **63–64 s** (bar: ≤ 2 × 60 s — met).
INTERP_ALT seal: **all 2,307 seeds enclosed**.  215 sized regions.  Bank
annulus: **64,341** free vertices valued — **64,162** by their station's
own daylight ray, **179** by the nearest-boundary fallback.

| figure | round 3 (09ab) | round 4 |
|---|---|---|
| transect 1 (lon 31.3819142) max | 0.533 (3 over) | **0.554 (3 over)** |
| transect 1 mid-bank stretch | 0.153 | **0.269–0.288** |
| transect 3 (lon 31.4150) max | 0.124 (0 over) | **0.124 (0 over)** |
| annulus slopes p50 / p90 | 0.093 / 0.329 | **0.099 / 0.343** |
| over the 0.35 bar | 6.6 % count / 3.1 % area | **9.0 % / 3.0 %** |

THE MID-BANK IS FIXED AND THE THREE STATIONS ARE NOT.  Attributed, from
the tile's own patch and mesh:

1. THE RULED FIELD AT THAT SITE MEETS THE BAR.  Transect 1 is a **CUT**
   bank: the design ring is at **z 49.48** and the DEM/foot **60.0 m** out
   along the normal at **z 66.88** — a ring-to-foot slope of **0.290**,
   under the bar.  The ruled field along the transect is a uniform 0.290:
   53.83 / 53.18 / 52.54 / 51.89 / 51.25 / 50.60 / 49.96 / 49.51 at
   d_ring 14.97 → 0.29 m.
2. THE MESH DOES NOT CARRY IT THERE.  The built mesh reads 55.66 / 55.02 /
   54.38 / 53.74 / 52.85 / 51.62 / 50.39 / 49.49 at those same stations —
   a near-constant **+1.84 m** above the ruled field from 15 m out to
   about 6 m, decaying to 0 at the ring.  It is that decay, not the
   field's form, that reads 0.53–0.55; the `.alt` raster is 66.6 m there,
   so the excess is a fraction of the DEM's own 16.4 m offset, not the DEM
   itself.
3. THE SITE IS ONE RING.  Within 12 m of the station there is exactly one
   design ring — way `-10308`, `role=graded_strip`, 55 nodes, z
   48.41–55.00 — and it IS the coverage's outer boundary at 1.64 m.  So
   this is not two rings disagreeing; something between the annulus's
   inner boundary and the mesh vertices out at 6–15 m holds a value 1.84 m
   above the field.

**CORRECTED BY §13.10 (round 5): item 2 above is WRONG.**  The mesh does
carry the ruled field at those stations, to 0.4 mm; what is wrong is item
1's *"a ring-to-foot slope of 0.290"* — that figure was read off ONE
nearest-foot distance, and the rays the three stations actually stand on
run 51.0 m, not 60 m, so their own ruled slope is **0.3425**.  Round 5
measured every vertex of the offending triangle.  Read §13.10 for what the
residual is; the paragraph below is kept because it names the two
candidates round 5 REFUTED.

REPORTED, NOT DECIDED (attempt cap spent; a spawner/owner call).  The
candidates the numbers leave standing: annulus vertices that are already
`patch_valued` when the blend runs — the tile log's *"the rest are
levelled road ribbons / seawall bands and keep their own"* class — are
SKIPPED by `bank_annulus_blend_values` by construction and keep a levelled
altitude inside the bank; and the 179 fallback vertices. Neither was
isolated at this site in this round.

### §13.9.5 Build-time impact statement

The change is inside `bank_annulus_blend_values`, which runs once per tile
in step 2.  Step 2 measured **63 s** against round 3's **63 s** — no
change within the ±25 % single-run noise floor, and the ray-cast is one
vectorised `STRtree.query(rays, predicate="intersects")` plus an analytic
ray/segment solve over the returned pairs.  The per-airport 60 s
auto-patch budget is NOT touched (this code never runs in an airport
build).  Against the 300 s whole-tile budget the pass is far under the 1 %
(3 s) threshold that would need a Fable-5 optimisation review.

## §13.10 WHAT ALREADY CARRIES A VALUE INSIDE AN ANNULUS, AND WHAT TRANSECT 1'S RESIDUAL ACTUALLY IS (RULINGS 2026-09-09ad; lane `v2bankblend` round 5)

### §13.10.1 THE ATTRIBUTION, per vertex

`O4_BANK_BLEND_DUMP=<path>` makes `bank_annulus_blend_values` write a CSV
row for EVERY mesh vertex standing inside a bank annulus — index, lon/lat,
`d_in` / `d_out` / `D(p)`, `z_in` / `z_out` / `z_foot(p)`, the field value
and the value the vertex already carried — classed by the path that valued
it (`ray`, `fallback`, `ray_pre_valued`, `pavement_kept`, `outside_tris`,
`nogood`).  It writes nothing into the mesh.  HECA +30+031, 91,390 rows.

The steep stations of transect 1 (lat 30.11664–30.11668, grade 0.490 /
0.554 / 0.554) sit in ONE triangle.  Its three vertices, and their dump
rows:

| vertex | class | `d_in` | `D(p)` | z (mesh) | z (field) |
|---|---|---|---|---|---|
| 28427 | ring vertex, `aeroway=apron` way `-308` | 0.00 | — | 49.480 | its ring's own |
| 384051 | `ray` | 10.00 m | 51.04 m | 52.905 | 52.9051 |
| 499668 | `ray` | 14.19 m | 50.97 m | 54.387 | 54.3872 |

**Every vertex is exactly on the ruled field** (0.4 mm), and every ray's
own slope is `(66.96 − 49.48) / 51.04 = 0.3425`, under the 0.35 bar.  The
plane through the three is nevertheless **0.559**: the two free vertices
stand at the SAME latitude 22.9 m apart with `d_in` 10.00 and 14.19, while
the ring vertex they share sits 7 m north at `d_in` 0.  Fitting a linear
function to `d_in` over that triangle gives a plan gradient of **1.624** —
a distance-to-a-polyline is 1-Lipschitz, so no such surface exists; the
triangle is a chord across the ring's own CORNER FAN, where the distance
field is not affine.  `0.3425 × 1.624 = 0.556`, which is the measured
0.554.

**THE RESIDUAL IS THE TRIANGULATION SAMPLING A CORNER FAN, not a
pre-valued band.**  This is 09ab's class again — a field exact at its
vertices and steep between them — one level down: 09ab fixed the field's
FORM, §13.8 gave the annulus vertices to carry it, and what is left is
that a corner fan cannot be carried by ANY triangle spanning it, however
fine, unless the triangulation respects the fan's own rays.  Per the
ruling's own STOP clause this round does not fix it: no ruling covers
re-cutting the annulus regions along the ring's normals, and every cheaper
move (more area refinement) shrinks the triangle without changing the
1.624 ratio.

### §13.10.2 THE TWO CANDIDATES ROUND 4 LEFT STANDING ARE REFUTED

* *Pre-valued annulus vertices.*  INTERVENTIONAL ARM: the blend was made
  to override every pre-valued annulus vertex that is not on pavement, and
  the tile re-meshed.  Transect 1's grade vector came back
  **bit-identical** (max 0.554, the same 25 gaps), transect 3 unchanged.
  The steep triangle has exactly one pre-valued vertex, the ring vertex
  28427, and the field's value there is its own value.
* *The 179 ray fallbacks.*  None is on transect 1, and (c) below cut them
  to 35 with the transect unchanged.

### §13.10.3 THE LAW LANDED (the ruling's (a) / (b) / (c))

1. **(a) A road crossing a bank keeps its own profile.**
   `bank_pavement_lines` reads every patch way carrying an `aeroway` or
   `highway` tag plus every levelled ROAD centreline of the build's
   `o4_levelled_roads.json`, and a pre-valued vertex within the ring match
   tolerance of the former or the sidecar's own lane half-width of the
   latter is left exactly as its own authority wrote it.  When that
   linework cannot be read, NOTHING pre-valued is overridden (09ab's
   behaviour) — the road half of the test is the safe half.
2. **(b) Any other pre-valued vertex inside an annulus takes the field.**
   The blend's candidate set is now every annulus vertex, not the free
   ones alone.  ONE class is neither pavement nor "inside": the field's
   own DATUM — a pre-valued vertex within tolerance of the design ring
   (`d_in ≈ 0`) or of the foot (`d_out ≈ 0`) is an END of the
   interpolation, not something between its ends.  MEASURED without that
   guard: a foot vertex carrying 92.01 m took the field of a ring station
   whose ray runs 78.3 m to a DIFFERENT foot and was dragged to 82.88 —
   **9.13 m** off its own ring, the worst of 14 moves over 3 m and 55 over
   1 m across 5,927 vertices.
3. **(c) The ray traces the normal both ways.**  `_bank_foot_along_normal`
   now takes `alt_dirs`: a station whose outward normal meets no foot
   retries the REFLECTED normal, then the corner fan's own direction,
   before 09t's nearest-boundary value stands in.  HECA fallbacks
   **179 → 35**.

### §13.10.4 MEASURED at HECA

`run_tile_mesh_only.py 30 31 1 --patches-as-is`, rc 0, shared repo
UNCHANGED.  Step 1 **54.1 s**, Step 2 **64 s** (round 4: 53.4 / 63).  All
2,307 INTERP_ALT seeds sealed, 215 sized regions.

| figure | round 4 | round 5 |
|---|---|---|
| transect 1 max | 0.554 (3 over) | **0.554 (3 over)** — §13.10.1 |
| transect 3 max | 0.124 (0 over) | **0.124 (0 over)** |
| annulus p50 / p90 | 0.099 / 0.343 | **0.099 / 0.343** |
| over the 0.35 bar | 9.0 % count / 3.0 % area | **9.1 % / 3.04 %** |
| ray fallbacks | 179 | **35** |
| pre-valued taking the field | — | **0** (5,927 are ring/foot datum, 15,041 pavement) |

**(b) IS A NO-OP AT HECA**: every one of the 5,927 pre-valued annulus
vertices the widened candidate set found is the field's own ring or foot
datum, and 15,041 more stand on pavement.  There is no graded_strip /
seawall / INTERP_ALT-seed band inside a HECA annulus at all — which is the
measurement the ruling asked for, arrived at from the other direction.
The law still lands: a tile that HAS such a band is the one it is for.

### §13.10.5 Build-time impact statement

Step 2 **64 s** against round 4's **63 s** — inside the ±25 % single-run
noise floor.  The pavement test is two `STRtree.query(..., predicate=
"dwithin")` calls over the pre-valued candidates only.  A first cut that
buffered the 20,907 road centrelines and unioned them instead cost **142 s
(+79 s)**, measured, and was replaced before landing; the shape of that
mistake is recorded in `bank_pavement_lines`' own docstring.  The
per-airport 60 s auto-patch budget is untouched (this code never runs in
an airport build).
---

---

## §16 THE FINAL PROJECTION — the runway family's hard rows enforced
## EXACTLY (RULINGS 2026-09-09y, closing 09v (3)) — lane `v2settle`

NOTE ON NUMBERING: landed as §16 at merge (§14/§15 were taken by the datum rounds).

### 16.1 What changes

ONE new module, `src/auto_patch_v2/solve/project.py`, and ONE call site —
the last phase of `solve/design.solve_design`, after the augmented
Lagrangian's polish and before the solved columns are scattered back to `z`.

Why a second problem and not a better penalty: 09r (3) / 09v measured the
multiplier sequence oscillating on a real airport at EVERY weight tried, so
the solve ships a residual it cannot certify; on 09y that residual landed on
RUNWAY rows at HECA (`runway_transverse` 1 at 0.50 m,
`runway_vertical_curve` 4 at 0.24-0.33 m) and the app's DEFECT gate refuses
the airport.

    minimise  Σ_v (z_v − z_design_v)²   over the RUNWAY-FAMILY vertices
    subject to  every runway-family hard row as a TRUE constraint

with every other vertex FIXED at its solved z.  THE SET: the ring and hole
vertices of every face whose role is in
`law.tables.precedence.runway_family.members` (`runway`, `runway_crossing`)
plus every `runway_profile` breakline vertex (the ridge, which both DEFECT
readers read).  A reduced COLUMN is free only when every vertex mapped to it
is in that set, so a `Flat` group straddling the boundary stays rigid.  The
threshold pins are FIXED VERTICES, not rows: they hold exactly because the
projection has no column for them.  Solved by HiGHS's QP over the rows
within `_NEAR_M` of their bound, re-read over the full population and
re-solved until nothing new is violated (a cutting plane: a relaxation whose
optimum is feasible for the full problem IS its optimum).

`[design] runway_projection` (a law value, `true`) is the switch; `false` is
the diagnostic arm and is never shipped off.

TWO DEVIATIONS from the ruling's letter, both measured, both reported:

1. THE BAR IS THE LAW'S OWN "HELD", NOT ZERO: the constraint is
   `row ≤ bound + [design] hard_tol_m` (0.02 m of surface) — under the
   census's per-node rounding envelope (0.03) and far under the rate
   readers' quantum (0.1), so a held row mints no DEFECT row.  MEASURED at
   CYXY, where the design solve leaves 0.027 m and the DEFECT readers
   already read 0: the EXACT projection pulled the runway 2.16 m and took
   the census from 428 rows to 464 (`strip_transverse` 5 → 37); at the held
   bar the same airport moves 0.038 m and the census is unchanged.  The
   cause is the stiffness of the second-difference chain — a 6e-4 grade-change
   violation integrates to metres of amplitude over a 1.2 km ridge.
2. A COUPLED ROW THE PROJECTION'S OWN FIXING MADE INFEASIBLE IS WITHDRAWN:
   a row tying a runway vertex to a fixed NON-runway vertex is solvable in
   the design solve, where both feet move, and can be unsolvable here.  The
   conflicting rows are found by an LP minimising total relaxation over the
   coupled rows and withdrawn, counted in the report; every row whose feet
   are all inside the family stays a true constraint.  Under deviation 1
   this arm does not run at CYXY or HECA.

### 16.2 CONSUMER TABLE (owner 2026-08-30l), BEFORE editing

The projection adds NO shape class, region, breakline kind, role or
register entry, and emits nothing: it changes the VALUE of `z` on runway
vertices between the solve and the emit, which is the same kind of change
every solve phase already makes.  What it touches:

| # | consumer | reads | ruling |
|---|---|---|---|
| P1 | `solve/design.solve_design` | the solved columns `x` | THE CALL SITE.  The projection runs after phase C and before `z` is scattered, so every consumer of `Solution.z` gets the projected surface with no change of its own. |
| P2 | `solve/design.DesignReport` | `as_dict()` / `line()` | GAINS `runway_projection` (rows, free columns, before/after, max move, wall, status).  `pipeline/build.py` writes `as_dict()` into the report JSON wholesale; nothing enumerates its keys, so a new key is additive. |
| P3 | `solve/design`'s `hard_max_violation_m` / `hard_settled` / `hard_worst` | the hard rows at the shipped `x` | RE-READ AFTER the projection: the report is of the SHIPPED surface.  What is left is what the projection does not own (a pad plane, a hard row with no runway vertex). |
| P4 | `pipeline/build.py` (`solve_design` × 2 call sites) | `(Solution, DesignReport)` | UNCHANGED CODE — same signature, same types. |
| P5 | `solve/why.py` (`solve_design`, both call sites) | the solved `z` | READS THE PROJECTED SURFACE by construction; `why` explains the surface that ships. |
| P6 | `tools/v2_solve_replay.py` | `solve_design`, `rep.line()` | UNCHANGED CODE; the replay's printed line now carries the projection's own clause. |
| P7 | `emit/graded.py`, `emit/osm_adapter.py`, `pipeline/publication.py` | `sol.z` | UNAFFECTED IN KIND: they emit whatever the solve returns. |
| P8 | `verify/runway.runway_transverse` / `runway_vertical_curve` (the DEFECT families) | the emitted rings and crown spine | THE POINT: their populations are twins of the projected rows, so they read 0.  Neither reader changes. |
| P9 | `verify/*` everything else (`within_shape`, `no_step`, `strip_*`, `taxi_box`, …) | the emitted surface | READ AS REPORT FIGURES on the projected surface, exactly as the ruling says of the surrounding sheet's rows.  Deviation 1 above exists because at the exact bar these figures got WORSE at CYXY for no DEFECT gain. |
| P10 | `law/emit.toml [design]`, `law/design_schema.Design` | the law table | GAINS `runway_projection: bool`.  `law/model._build` REFUSES an unknown key, so the TOML and the schema land in the same commit — they do. |
| P11 | `law/design_schema.DESIGN_TERMS` | the objective weights | UNAFFECTED: `runway_projection` is a switch, not a weight, exactly as `bank_slope` is not. |
| P12 | `tools/check_grade.py`, `tools/harness/census.py`, `tools/harness/oracle.py`, the sidecar | the emitted patch | UNAFFECTED — no new tag, feature, ref or sidecar key; the patch is the same shape with different altitudes. |
| P13 | Swift (`Sources/SceneryKit`) | the JSONL events and the patch | NO CONSUMER: the app reads neither the design report's keys nor a law-family name (§3.1 / §7.1 / §8.1 censuses, re-checked). |
| P15 | the SIDECAR's `design` block (`emit/osm_adapter.SIDECAR_*`, `check_grade.SIDECAR_EVIDENCE_KEYS`) | `pub["design"] = design_rep.as_dict()` | ADDITIVE: `design` is already a registered EVIDENCE key and no reader enumerates its sub-keys; the projection's block joins the residual figures already published there. |
| P14 | `highspy` | a new runtime dependency of the solve path | ALREADY IN THE VENV and already used by the v2 tree; the QP is ≈ 2k unknowns × ≈ 6k rows at HECA. |
## §17 THE NEAREST-THRESHOLD CROSSING PIN (RULINGS 2026-09-09z (1),
## superseding 09r (2)) — lane `v2crossing`

Owner, verbatim: "All crossing runways must stay within the runway grade
laws.  V1 takes the closest threshold to the crossing, solves that
runway, then sets the crossing node as an anchor for the other runway(s)
to grade to, same logic as a tile seam boundary or the CIFP threshold."

V1'S OWN SITE, cited: `src/auto_patch/pavement/runway_segments.py`
"Runway-runway centerline-crossing reconciliation" (the comment block at
:1370-1400 and the loop at :1252-1313).  Its rule, verbatim from that
comment: "whichever runway has the threshold geometrically closer to the
crossing point gets its CIFP-linear-interp value used as the agreed
altitude"; "that runway's profile then passes through the crossing on its
natural CIFP profile, and the OTHER runway accommodates by deviating from
its own linear interpolation as much as the FAA gates allow"; the value
is `agreed = elev_a + t * (elev_b − elev_a)` on the WINNER's threshold
segment, injected into `auto_extra_anchors` for BOTH runways.  Its stated
reason: "a runway with thresholds close to the crossing has less profile
flexibility ... a runway whose thresholds are far away has more total
altitude budget to absorb a deviation."

### 17.1 THE RULE

1. THE CROSSING NODE is the intersection of the two runway CENTRELINES
   (`Runway.ends[0].xy → ends[1].xy`, the axis the chord's own station
   frame uses), not a face centroid: one point per `runway_crossing` face
   pair, computed analytically so it does not move with the noding.
2. THE GOVERNING RUNWAY is the one whose nearest THRESHOLD is nearest the
   crossing, measured as `min(|s_x − s0|, |s_x − s1|)` along that
   runway's OWN axis, where `s0`/`s1` are its two CIFP threshold stations
   (v1's `min(|t|, |t−1|) × length`).  Ties break to the LONGER runway,
   then to the lower id — deterministic, never face order.  A runway
   without two CIFP pins has no chord and can never govern; if neither
   runway of a pair has one, the crossing mints nothing.
3. THE PIN VALUE is the governing runway's own STRAIGHT threshold chord
   evaluated at the crossing station, clamped to `[s0, s1]` (v1's
   beyond-threshold clamp).  The governing runway is NOT pinned: it
   solves the node under its own laws, and its chord target across the
   crossing is UNCHANGED.
4. THE OTHER RUNWAY takes that elevation as an ANCHOR, exactly as it
   takes a CIFP threshold or a tile-seam pin, and re-fits its chord
   through it.  Every hard law it owns is untouched: its threshold pins,
   `runway_profile` longitudinal caps, `runway_vertical_curve` K,
   `runway_transverse`, the crown.  The dip that remains is then THE LAW,
   spread as a vertical curve by §16's exact projection (09z (1)).

### 17.2 WHICH ROWS CHANGE

* NEW ROW — one `Pin` per (crossing, non-governing runway), generator
  `runway_crossing_pin` (`constraints/runway_chord.runway_crossing_pins`,
  registered in `constraints/__init__.GENERATORS` after
  `runway_within_shape`).  Its vertex is the `runway_profile` RIDGE
  vertex of that runway nearest the crossing node; its value is that
  runway's RE-FIT chord at that vertex's own station, so a node vertex
  the noding left 20 m off the intersection is pinned at the profile's
  own value there and not at the intersection's.  A vertex already
  carrying a threshold pin is never re-pinned (CYXY's 14L/32R crossing
  sits ON 02/20's 20 threshold); one vertex takes at most one crossing
  pin, the nearest crossing's.  Like every `Pin` it is ELIMINATED from
  the unknowns by `solve/rows._reduce`, so it holds exactly and §16's
  projection has no column for it.
* CHANGED TARGET — `runway_chord_targets`: the non-governing runway's
  `_Chord` gains KNOTS, and `_Chord.z(s)` interpolates PIECEWISE through
  `[(s0, z0)] + knots + [(s1, z1)]` instead of one straight line.  The
  governing runway's chord is byte-unchanged.  No target is dropped
  anywhere: 09r (2)'s release is gone.
* DELETED — `runway_crossing_release`, `crossing_primary` (it named a
  seniority the owner replaced; the new register is `crossing_governor`,
  which names what it decides), `[design] crossing_release_m` with its
  schema field and validation, and `ChordReport.released_vertices`.

### 17.3 CONSUMER TABLE (owner 2026-08-30l), BEFORE editing

No new shape class, role, region, breakline kind, ref or sidecar key: the
change adds ONE `Pin` row on an existing runway ridge vertex and re-shapes
one `preferred_z` target.  Every reader, by grep of
`crossing_primary` / `runway_crossing_release` / `crossing_release_m` and
of the `Pin` kind:

| # | consumer | reads | ruling |
|---|---|---|---|
| C1 | `constraints/runway_chord.runway_chord_targets` | the chords | THE SITE: knots replace the release |
| C2 | `constraints/__init__.GENERATORS` / `generate` | the generator list | GAINS `runway_crossing_pin`; its count joins `counts` (additive dict key, nothing enumerates it) |
| C3 | `solve/rows._reduce` | `cs.pins` | UNCHANGED CODE: a crossing pin fixes its vertex exactly like a threshold or seam pin |
| C4 | `solve/design.assemble` / `is_hard` | row heads | UNCHANGED: a `Pin` is an equality by KIND, never by `hard_rulings`, so the table does not change |
| C5 | `solve/project.free_columns` | `red.col[v] < 0` | UNCHANGED CODE: a pinned vertex has no column, so the projection cannot move it — "the threshold pins are FIXED VERTICES, not rows" (§16) now covers the crossing node too |
| C6 | `constraints/__init__.water_exempt` | `Pin` rows on water vertices | UNCHANGED and CORRECT: water outranks, so a crossing pin on a water vertex is withdrawn like any other non-water pin |
| C7 | `constraints/__init__.seam_exempt` | seam-pinned pairs | UNAFFECTED: it withdraws `Diff`/`Linear` rows, never pins |
| C8 | `constraints/no_step.reach_band_values` | `threshold_pins` only | UNCHANGED: the reach band is seeded by CIFP thresholds, and the owner's ruling adds an anchor to the runway, not a new reach terminal |
| C9 | `constraints/runway_profile` (profile, crown, transverse, K, within_shape) | its own rows | UNTOUCHED — the pin is an anchor the laws must carry, never a law release |
| C10 | `solve/why.py` | pins as chain terminals | ADDITIVE: a `why` chain that used to terminate on a CIFP pin may now terminate on `runway_crossing_pin`, which is the explanation the owner asked for |
| C11 | `pipeline/build.py` (`lrep.runway_chord = dict(chord_rep)`) | `ChordReport` | ADDITIVE/SUBTRACTIVE keys only; nothing enumerates them, and `airport/load.LayoutReport.runway_chord` is `dict \| None` |
| C12 | `law/emit.toml [design]`, `law/design_schema.Design` | the law table | `crossing_release_m` and its validation are DELETED in the same commit — `law/model._build` refuses an unknown key, and would refuse a stale one |
| C13 | `emit/*`, `verify/*`, `tools/harness/census.py`, `oracle.py`, the sidecar | the emitted patch | UNAFFECTED IN KIND: same geometry, different altitudes on the ridge; no law family, tag or sidecar key is added |
| C14 | `Sources/SceneryKit` (Swift) | JSONL events, the patch | NO CONSUMER (§16.2 P13, re-checked: no design-report key and no law-family name crosses the wire) |
| C15 | `tools/v2_solve_replay.py` | `with_runway_chord`, `rep.line()` | UNCHANGED CODE |
| C16 | `tests/auto_patch_v2/test_v2cyxy.py` (four 09r (2) twins) | the refuted mechanism | DELETED with it (`test_the_longer_runway_is_the_primary_of_a_crossing`, `test_the_secondarys_chord_is_released_at_the_crossing`, `test_the_primary_ridge_is_monotone_through_the_crossing`, `test_the_secondary_climbs_into_the_primary_within_its_own_laws`); the hard-set twins keep the fixture and are re-read against the new law |

### 17.4 TWINS (`tests/auto_patch_v2/test_v2crossing.py`)

On the two-runway cross of `test_v2cyxy._crossing_airport` (09/27, 1,200 m,
700 → 706; 18/36, 1,000 m, 701 → 701; crossing at both midpoints, so
18/36's threshold is 500 m away and 09/27's 600 m — 18/36 governs, the
CYXY shape): the register picks 18/36 either way round; the governing
runway's chord target across the crossing is BYTE-identical to its
single-runway value; the other runway's ridge passes through the pin
within `hard_tol_m` and holds its thresholds, its longitudinal cap and its
K bound; both DEFECT readers (`runway_transverse`, `runway_vertical_curve`)
read 0; and a SINGLE runway's targets and rows are unchanged.

### 17.5 MEASUREMENTS — CYXY, the closing build

Change arm `v2crossing` (branch `claude/v2crossing`, body_sha `ad870acb478a`,
total 10.4 s, solve 4.23 s, 269 active-set rounds); control `v2crossctl` at
main `858a6836` (`--base-arm`, body_sha `fdcdac5cfa7f`, total 12.9 s); v1
arm `v1ctl` at the same tree (`--engine v1 --base-arm`, 47.0 s).
`tools/rwy_profile.py --icao CYXY --binned --compare`.

THE SITE — the 02/20 x 14R/32L and 02/20 x 14L/32R crossings
(60.7095, −135.0672 area).  02/20's thresholds are 15 m and 166 m from the
two nodes against the mains' 1,000 m-plus, so 02/20 GOVERNS both, exactly
as 09z (1) says it does.

| 14R/32L station | 825 | 1025 (the node) | 1225 |
|---|---|---|---|
| control (main) | 697.7 | **697.1** | 699.1 |
| **this** | 694.1 | **694.2** | 695.5 |
| v1 | (—) | 694.0 | 694.9 |
| DEM | 693.8 | 694.0 | 694.0 |

THE DIP IS GONE.  The control's V (−0.6 m into the node, the owner's read)
is replaced by a MONOTONE climb; v1 is monotone there and so is this.  At
14L/32R (node s = 425) the control reads 695.3 / 694.4 / 696.7 — a −0.9 m
V — and this reads 694.0 / 693.8 / 694.8, which is the DEM's own bowl
(694.1 / 693.9 / 694.1) and v1's (693.9 / 693.7 / 694.0): monotone exactly
where v1's is.  02/20's +1.9 m hump over its own ground (§13.2's +2.09) is
gone: `z-DEM` mean +1.49 -> **−0.00** (v1 −0.11).

| reading | control (main) | **this** | v1 |
|---|---|---|---|
| DEFECT families (`runway_transverse`, `runway_vertical_curve`) | 0 | **0** | — |
| v2 verify rows | 433 | **109** | — |
| census LAW-TRUE / ADJUDICATED | 1185 / 280 | **968 / 97** | — |
| 14R/32L bow vs its chord | −1.26 | −4.13 | −4.73 |
| 14L/32R bow | −1.40 | −2.03 | −3.02 |
| 02/20 bow | +0.20 | **−0.06** | −0.20 |
| 14R/32L max grade change (%/100 m) | 1.680 | **0.700** | 0.940 |
| 14L/32R max grade change | 2.340 | **0.660** | 0.580 |
| 02/20 max grade change | 2.360 | **0.160** | 0.160 |
| 14R/32L z−DEM mean | +2.64 | **+0.65** | +0.36 |

THE BOWS GROW AND THAT IS THE LAW, not a regression: the bow is measured
against the STRAIGHT threshold chord, and the ruling replaces that chord
with one re-fit through the crossing node.  Every bow now sits between the
control's and v1's, and every other reading — the DEFECT gate, the verify
count, the census, the grade-change rate and the distance off the ground —
moves toward v1.  The hard set still reads NOT SETTLED at 0.0210 m
(control 0.0202 m): unchanged in kind by this round, 09v's open item.
---

## §18 THE SHORE HAS NO BANK (RULINGS 2026-09-09z (3)) — lane `v2shore`

Owner: "Only set pavement node elevations, then the DEM should automatically
grade into the water and blend with bathymetry data."  09m (2) / 09o (4)'s
shore bank is WITHDRAWN: where the daylight walk meets WATER the walk STOPS
at the water line, no earthwork foot is authored beyond it, no bank piece or
annulus covers water, and nothing the patch or the mesh-side blend writes may
lift a vertex that carries a water bit.  The witness is the one the water
lane built (`airport/dem_production.ProductionDem.water_many` /
`water_geometry`); nothing re-derives water.

### 18.1 CONSUMER TABLE (owner 2026-08-30l), BEFORE editing

| # | consumer | reads | ruling where the walk meets water |
|---|---|---|---|
| S1 | `emit/bank.daylight_feet` | ring z, normals, DEM | EDITED: each station is water-tested with the DEM's own witness; the FIRST wet station STOPS the ray — the foot is the last dry station, kind `water` (a fourth `FOOT_KINDS` entry).  Wet at or inside `bank_min_width_m` ⇒ `d = 0`: no earthwork at all, the ring's outer edge is the patch boundary. |
| S2 | `emit/bank.with_bank` foot pieces | `pts + nrm*d` | UNAFFECTED IN KIND — a `d = 0` ray simply contributes no offset; the piece is repaired by the existing `buffer(0)` path. |
| S3 | `emit/bank.with_bank` the ONE banked region (`cov.buffer(min_w) ∪ pieces`) | the union | EDITED at the SINGLE derivation site: `banked = union − water_geometry`.  The min-width COLLAR is the one part of the region no ray controls, so the cut — not a per-ray veto — is what keeps every bank vertex out of water. |
| S4 | the foot ring emission (`banked` boundary → `SurfaceVertex` + `BANK_KIND` breakline) | the region's rings | THE RING STAYS CLOSED, closing ON THE WATER LINE (§18.2): no vertex inside water, its z the DEM's own value at the shore. |
| S5 | `emit/bank._push_off` | cov, `min_w` | EDITED: a push that would land the vertex IN water is refused (the vertex keeps its place).  The collar law must never move a foot node across the shoreline. |
| S6 | `emit/bank._ray_limit`, `smooth_along` / `smooth_runs`, the `np.clip(d, min_w, max_w)` after them | d, the chain | EDITED where it would UNDO the cut: a water ray's `d = 0` is BELOW `min_w`, and the existing clip would push it back out to a 5 m bank over water.  The wet rays are re-zeroed after the smoothing and the clip; everything else about the smoothing, the ray limit and `_inner` is unchanged. |
| S7 | `O4_Vector_Map.include_patches` | closed patch ways | UNAFFECTED: one closed way per boundary, as §13 left it.  An OPEN foot would enter as a DUMMY way, outside `interp_alt_patch_polygons` — the whole ring's annulus would lose its INTERP_ALT seed while its segments still blocked the plague (§10.5 measured 306 %).  That is why S4 closes on the water line. |
| S8 | `O4_Mesh_Utils.bank_annulus_blend_values` | annulus vertices | EDITED: a new `water_valued` exclusion — a vertex carrying a water bit is never a blend candidate and is never written. |
| S9 | `O4_Mesh_Utils.post_process_nodes_altitudes` final `interp_alt_tris` copy (`z = column 5`) | column 5 | EDITED: a water-bit vertex SHARED with an INTERP_ALT triangle keeps its levelled altitude — the copy skips it.  This is where "some water being lifted up" survives 09o (3): sea levelling runs FIRST and this loop overwrote the shared shore vertex afterwards. |
| S10 | `O4_Mesh_Utils.post_process_nodes_altitudes` `:1627` water-bit precedence (09o (3)) | triangle attributes | UNTOUCHED — S8/S9 are the VERTEX corollary of that TRIANGLE law. |
| S11 | `O4_Mesh_Utils.interpolate_free_interior_altitudes` | free vertices + Dirichlet | UNCHANGED CODE: with S9 a water vertex's altitude can no longer be reached, so the harmonic extension's own values are inert there.  Reported, not edited. |
| S12 | `O4_Mesh_Utils.patch_valued_vertex_indices` / `patch_segment_split_values` | `PATCH_RING_MARKER` edges | UNAFFECTED: the foot ring is still one closed marked ring; its shoreline arc is marked like the rest, which is what keeps the water flood outside it. |
| S13 | `constraints/water.py`, `airport/flat_site._cut_water`, `emit/rebake.py` seats | the same witness | UNAFFECTED — one derivation site, three existing readers, now four. |
| S14 | `verify/*`, `check_grade`, `tools/undulation.py`, the sidecar | `o4_feature=bank_foot` | UNAFFECTED: no new kind, ref shape or register entry. |
| S15 | a DEM sampler with NO witness (every synthetic fixture, the authored `DemSampler`) | `getattr(dem, "water_many", None)` | NO-OP by construction: no witness ⇒ no wet station, no cut ⇒ the pre-change bank, bit for bit. |
| S16 | `tools/mesh_region_tris.py --water-audit`, `tools/mesh_elevation_sampler.py --grade-bar` | the built mesh | THE INSTRUMENTS, unchanged — they are how §18 is measured. |

### 18.2 THE DEVIATION THE LANE REPORTS (never decided by the lane)

The brief asks for an OPEN foot where the chain is cut.  What landed cuts
the WALK and the banked REGION at the water line and keeps the emitted ring
CLOSED ALONG that line (S4/S7): an open `bank_foot` way is a dummy way in
`include_patches`, so the ring's whole annulus — the dry three-quarters
included — would lose its INTERP_ALT seed and revert to the raw DEM (the
306 % transect of §10.5), and `bank_annulus_polygon` would find no ring at
all.  The shoreline arc's vertices carry the DEM's own value, which is what
the mesh drapes there anyway: the constraint is a no-op in elevation and a
fence in topology.  Likewise, where water stands nearer than
`bank_min_width_m` the ruling's literal "no foot at all" leaves the collar's
sliver between the ring and the shore: its foot is ON the water line at the
DEM, never a lifted value.

### 18.3 MEASURED at OTHH (lane `v2shore`, branch `claude/v2shore`)

THE PATCH (`build_airport.py OTHH --engine v2`, tag `OTHH_20260909T223805`,
490 s, solve 17.01 s, `body_sha 0c7e8743849d`, verify rows 16 — within_shape
2, taxi_box 12, airside_no_step 2 — no DEFECT family, hard set SETTLED):

* the bank walk: 9,484 boundary vertices, 9,477 at the minimum / 7
  daylighted / 0 at the maximum / **0 stopped at water** — at OTHH no
  daylight ray reaches the canal inside its own walk, so the EMITTER's
  win is the REGION cut, not the walk;
* `tools/patch_water_audit.py`: 44 bank rings (27 exterior, **17 hole**),
  4,894 foot nodes, banked region 11,430,408 m², **over water 0.0 m²**;
  10 foot nodes are inside the water polygon by **0.000 m** — they are the
  hole's own boundary, the ring closing ON the water line.  The 1,609 m²
  hole is the water the collar used to cover.

THE MESH, a MATCHED ARM (`run_tile_mesh_only.py 25 51`, step 1 27 s; then
the step-2 REPLAY on the SAME `.poly`/`.node`/`.alt` with `O4_Mesh_Utils`
at main `858a6836` — one file differs, nothing else):

| `mesh_region_tris.py --water-audit` | control (main) | this branch |
|---|---|---|
| SEA vertices off 0.000 (frame) | 28 | **0** |
| SEA triangles with a z-step > 1 m | 21 | **0** |
| max SEA z-step | 2.712 m | **0.000 m** |
| within 2 km of 25.2558,51.6079: SEA off zero | 3 | **0** |
| within 2 km: max SEA step | 0.606 m | **0.000 m** |
| inland/equiv bodies (they hold their OWN level, lawfully) | 30,147 off zero | 30,147 off zero |

* the engine's own line: **186 shore vertex(es)** shared with a patch/road
  INTERP_ALT triangle kept their levelled water altitude instead of the
  patch value — the column-5 copy, which is where "some water being lifted
  up to terrain level" survived 09o (3);
* the bank annulus blend is **bit-identical** across the two arms (57,148
  vertices, 56,894 by ray, 254 fallback): no annulus vertex at OTHH carries
  a water bit, so S8 is a guard here and S9 is the whole measured delta;
* the SHORE TRANSECT (lat 25.2563, lon 51.6120 → 51.6180, 5 m stations,
  crossing the canal's west bank at ≈ 51.6152): max station grade **0.077**,
  0 of 120 gaps over the 0.35 bar, **unchanged** across the two arms — with
  this patch the shore is already a ramp, and the cliff the owner read is
  the 3.962 m plateau STEP inside the water, which is what the table above
  removes.
* Step 2 wall: 3m23s (control replay); the branch's own steps 1+2 ran
  15m50s, which includes a COLD `[library]` index rebuild and the object
  re-bake the control read from cache — not comparable, and not a timing
  measurement.

REFERENCE, not a control (different vintage and config, cross-tree):
the owner's installed `Data+25+051.mesh` of 16:09 reads 11,001 SEA vertices
off zero (898 at exactly 3.962), 7,957 stepped sea triangles, max step
16.919 m; near the owner's site 214 of 339 SEA vertices off zero and 381
stepped triangles.  That is the 1.0.297-era read the owner's report names.
---

## §19 THE TERRAIN EDGE — adjacent ground ends at a rim road or a crest (RULINGS 2026-09-10b/10c) — lane `v2edge`

### 19.1 The reading that founds it

CYXY, app 1.0.300, owner: "the adjacent ground shape at 60.6968378, −135.0556035 is
extending out over the edge of the natural plateau … in reality the grade only goes to
the edge of the rim road (60.6970216, −135.0559897)". Measured (RULINGS 10b): the shape is
the 14R/32L END CORRIDOR, `graded_strip` `adjacent_ground:runway:4:zone2#10`, a law
surface with no DEM term (09b (3)) running 176 m off the runway end to exactly the site,
29 m past the rim road (OSM `highway=track`, levelled road 724); it holds 705.1 m across
the crest while the DEM goes 706.3 (crest) → 703.8 (road) → 692 (site); the bank foot
sits 5.6 m outside (the daylight walk cannot fit a 1:3 fill onto a 60 % natural slope,
`daylight_feet`'s "ground's own bank" resolves at `bank_min_width_m`) — a 19 m wall in
5.6 m. Lawful under the extent law (`end_skirt.corridor_length_m`, code 4 = 240 m) and
the bank law; wrong to a pilot. OWNER RULED (10b-1, answer A): the extent ENDS at the
physical edge.

### 19.2 The rule

An adjacent-ground region (zone 1, zone 2, the end corridors — every `ZoneRegion` from
`planar/zones.zone_regions`, and the `runway_clearance` skirt rings where v2 emits them)
is CLIPPED by the TERRAIN EDGE:

1. **The crest.** Outward from its pavement, the region ends where the natural ground
   falls away below the region's surface faster than the bank can follow: a station
   where the DEM's downhill slope, read over `edge_probe_m` (default 15 m) in the
   outward direction, is steeper than `[design] bank_slope` (0.33) AND the drop over
   the probe exceeds `edge_min_drop_m` (default 2 m — the DEM's own noise stays out).
   Construction: rasterise the region's bounding box at `edge_grid_m` (5 m); mark
   CREST cells by the test above; the region keeps only the part connected to its
   pavement without crossing a crest cell (a flood from the pavement side); the kept
   part is buffered by `−snap_margin_m` then `+snap_margin_m` so the edge is clean of
   slivers (the same snap discipline as the zones, 04u).
2. **The rim road.** Where a road (an OSM `highway=*` way of the airport small-roads or
   big-roads feed — `airport/osm.load_feed`, or the tile's `RoadProfiles.all_ways`) runs
   ALONG the crest — its line lies within `edge_road_snap_m` (20 m) inside the crest
   found in (1) over at least `edge_road_run_m` (30 m) — the region ends FLUSH at the
   road's OUTER edge (the road's half-width from `road_profile` lane width, plus
   `groundside_cutback_m` as every road already receives): the road keeps its own
   profile (09ad's road rule), the strip meets it at the road's inner edge. Without a
   road the crest of (1) is the edge.
3. **Beyond the edge: nothing.** No bank is emitted from an edge segment produced by
   this rule: the DEM's own slope IS the bank (`emit/bank.py` gets the edge segments as
   a `no_bank` mask, like the water line in §18). The mesh drapes the natural slope.
4. **What does not change.** The region's LAW rows (`constraints/zones.zone_bands`,
   `strips.py` end-corridor rows) act on the vertices that remain; the extent law is
   not re-fit — the corridor is simply shorter where the ground ends. Runway family laws
   untouched. A region with no crest is byte-identical to today.

Law keys, all in `emit.toml [design]`: `edge_probe_m`, `edge_min_drop_m`, `edge_grid_m`,
`edge_road_snap_m`, `edge_road_run_m` (schema `law/design_schema.Design`, validated
positive; no number in code).

### 19.3 Consumer table (RULINGS 2026-08-30l) — the lane completes the RULE column before editing

| # | reader | what it reads | rule |
|---|---|---|---|
| C1 | `planar/overlay.py:98` | `zone_regions` → `Region("graded_strip", …)` | clip happens INSIDE `zone_regions` (or a `planar/edges.py` it calls), so every downstream reader sees the trimmed polygon — the single derivation site |
| C2 | `constraints/zones.zone_bands` (:245, :332) | graded_strip faces by zone/class | unchanged: rows over the vertices that exist |
| C3 | `constraints/strips.py` `runway_groups` rect rings (:126–131), end-skirt rows (:305) | end-corridor FOOTPRINTS bound vertices inside | unchanged; a trimmed corridor has fewer vertices inside the footprint |
| C4 | `constraints/water.py` GROUND_ROLES | graded_strip ring/hole vertices | unchanged |
| C5 | `constraints/runway_chord.py:334` `fill_within="graded_strip"` | fills within the strip | unchanged (the strip is smaller) |
| C6 | `solve/rows.py:_zone_weights` | zone vertices' weights | unchanged |
| C7 | `emit/bank.py` `coverage_polygon` / `daylight_feet` / `with_bank` | the coverage's outer boundary → the foot ring | edge segments carry `no_bank`: no foot there (§18's water-line mechanism, generalised) |
| C8 | `verify/strips.py` (resa_transverse :302, raoa :354, tears :372/:405) | graded_strip shapes | unchanged; RESA/RAOA rows over a trimmed corridor read what exists — the lane quotes CYXY's before/after |
| C9 | `verify/runway.py:218 runway_end_skirt` | `ref == runway_end_skirt` rings | v2 emits none; unchanged |
| C10 | `planar/build.py:168` | roles ⊆ {graded_strip} faces | unchanged |
| C11 | the census (`check_grade` law families over `graded_strip`) | shape rows | unchanged; counts may drop |
| C12 | the sidecar / KML (`emit/osm_adapter`) | region refs | the edge is recorded per region: `o4_edge = crest|road|none`, the edge segments as a `terrain_edge` polyline way (value-less) for the owner's KML read |
| C13 | `solve/design.py` `_bend_class` (:113, :408) | a vertex's bending class (`strip` for zone ground) | unchanged: the class of the vertices that exist |
| C14 | `law/families.toml` + `tools/check_grade.ROLE_LESS_FEATURE_CLASSES` | the census's law families over `graded_strip`; the role-less way register | families unchanged (counts may drop); the new `terrain_edge` way is REGISTERED role-less (the `crown_spine` precedent: its chords are ring edges already, it carries no grade law) — the register's twin in `tests/test_harness.py` is updated in the same commit |

RULE column VERIFIED by lane `v2edge` before any edit (grep of `graded_strip`,
`zone_regions`, `ZoneRegion` and the zone accessors over `src/auto_patch_v2`):
C1–C12 as written, plus C13/C14 above; every other hit is a `tools/`
diagnostic, not a build consumer.

TWO READINGS RECORDED at implementation (neither changes the ruled law):
(a) §19.2 (1)'s probe is FORWARD-LOOKING, so the first CREST station stands
up to one `edge_probe_m` inboard of the lip and a crest-cut region ends
there (measured on the twin: a lip at x = 50 ends the region at x = 45).
A ROAD-cut region is exact.  (b) §19.2 (2)'s "within `edge_road_snap_m`
inside the crest" is read as a DISTANCE (≤ 20 m from the crest set), not as
"outside it": the crest set found by (a) already covers the road itself at
CYXY (the DEM drops 6 m over the probe ahead of the rim road).  Because
"without a road the crest of (1) is the edge", a governing road REPLACES the
crest within `edge_road_snap_m` of its run — otherwise the crest, standing
inboard of the road, would cut the region before the road ever could.

### 19.3b DEVIATION recorded at round 2 (owner RULINGS 2026-09-10g) — the
edge cut stops at the MINIMUM-WIDTH COLLAR, not at the coverage

§19.2 (3) as ratified says "beyond the edge: nothing … no bank is emitted
from an edge segment".  Round 1 implemented that literally: the no-bank
slab was cut back to the design coverage itself.  MEASURED at CYXY (the
owner's texture tearing, 10g): the banked region's boundary then came to
rest ON the strip's own ring for the whole edge run, and `emit/bank.
_push_off` — which pushes a boundary vertex NEAR the coverage out to
`bank_min_width_m` but leaves one exactly ON it alone, having no direction
to push along — emitted a foot ring alternating between 0.01 m and 5.01 m
from that ring and CROSSING it.  Triangle4XP filled the zero-area needle
to its recursion limit: 59,634 vertices on 216 distinct plan positions
inside one 50 m cell below the 32L end, 119,264 triangles where the
control mesh has 172, 18,447,114 vertex pairs closer in plan than
`identity.min_distinct_spacing_m` at different heights, 59,617 wall
triangles the DEM does not have.  That pile IS the tearing.

The cut now stops at `cov.buffer(bank_min_width_m)`.  At an edge the bank
is therefore the MINIMUM-WIDTH COLLAR every ring already gets — 5 m, its
foot on the DEM — and nothing beyond it; the 200 m daylight reach that
built the plateau wall is gone either way.  DEVIATION from the literal
text: a 5 m collar IS emitted from an edge segment.

The alternative that would honour the literal text — drop the run and
emit the foot as OPEN chains — was rejected, not overlooked: the CLOSED
FOOT RING is a measured law (`emit/bank` docstring, spec §10.5 — an open
chain enters `include_patches` as a dummy way, gets no INTERP_ALT seed
while its segments still block the regional plague, and the bank reverted
to the raw DEM at 306 %).  Trading a measured fold for a measured revert
is not a fix.  MEASURED COST of the collar at the owner's site (stations
along the road→site axis, 0 = the rim road, + toward the runway): the
mesh−DEM difference past the road reads +0.47 / −0.59 / −0.58 / −0.09 /
−0.04 / +0.09 / +0.11 / +0.19 m at s = −5 … −50, against round 1's
−0.03 / +0.09 / +0.12 at −20/−25/−30 — the collar costs ≤ 0.06 m where
round 1 was measured and ≤ 0.6 m at its widest, inside the 1 m bar.

### 19.4 Twins and the closing test

Twins (`tests/auto_patch_v2/test_v2edge.py`): a flat DEM → byte-identical regions; a
plateau fixture (DEM steps 20 m over 15 m at x = 100) with a zone extending to x = 150
→ the region ends at the crest (within `edge_grid_m`), no bank segment there; the same
with a road at x = 92 → the region ends at the road's outer edge; a gentle slope
(20 %) → untouched. ROUND 2 ADDS AN AREA BAR (10g): a transect cannot see a fold beside it —
round 1's single line read clean while the needle sat 237 m away.  The
acceptance is `tools/mesh_region_tris.py --edge-audit --near LAT LON R`
over the whole fan: ZERO overlapping node pairs, ZERO wall triangles the
DEM does not have, and |mesh − DEM| past the edge within 1 m at EVERY
vertex — proved on the CONTROL mesh first, which must read 0 overlapping
pairs for the instrument to mean anything.  Closing test: ONE airport, CYXY (`build_airport.py CYXY --engine
v2`, control `--base-arm`), then the transect of RULINGS 10b through the site (stations
every 5 m from +200 to −200 along the site→road axis, `mesh_elevation_sampler.py` on a
mesh-only tile run): bar — the strip's edge lies within one lane width of the rim
road's outer edge, no station steps more than 1 m, every station past the road within
1 m of the DEM; DEFECTs 0; the crossings of 09ai unchanged; KML of the edge segments
sent up. Site-first report.

## §20 THE PAD TAKES THE PAVEMENT'S EDGE LEVEL (RULINGS 2026-09-10l, owner 10k-1 = (A); ROUND 2 RULE: 2026-09-10y) — lane `v2padlevel`

### 20.1 What is being added — THE RULE (round 2, RULINGS 10y)

Owner, verbatim: "Pad takes the apron edge level." A building pad that
FRONTS pavement (shares a rim vertex with an apron / taxiway / road face)
is FLUSH with that pavement's edge; the apron never tiers down into the
terminal it fronts; and its own DEM datum (09p (3)) applies ONLY to a pad
that fronts no pavement.

**A pad is ONE PLANE (09c stands; 10y refuses round 1's deviation).** Its
LEVEL and TILT (≤ 1 %) are the LEAST-SQUARES FIT of that plane to its
FRONTAGE CONTACT vertices' pavement values. Where the frontage would need
more than 1 % of tilt the pad follows the SENIOR pavement (`precedence.toml`:
runway family > taxi > apron > road) and the miss against the junior is
reported. Round 1's per-vertex nearest-frontage following is REMOVED: each
pad vertex lies on the pad's single plane.

Three pieces, all in `constraints/pads.py` + `solve/design.py` §9b:

1. **THE PLANE IS THE PLATE** — `pad_flats` is 09c's row set again: a cap-0
   `Diff` over EVERY pair of the pad's rim at `[design] pad_flat`, the
   vertices it SHARES with its frontage INCLUDED (round 1 dropped exactly
   those pairs, and that is what stopped the pad being one plane —
   `pad_flat` rows 5 → 38). At a weight an order above the law's, over
   every pair, that is a near-rigid plate; `pad_slope_ceiling`'s hard 1 %
   over the same pairs is its tilt bound. The plate is what turns the
   rows below into a PLANE FIT rather than a per-vertex pull.
2. **THE FIT IS A LEVEL ROW** — `pad_frontage_level` mints ONE row per
   fronting pad and role: the pad's OWN MEAN (every rim vertex at weight
   `1/n`, so the row moves the pad's LEVEL and warps nothing) against THE
   PAVEMENT'S OWN VALUE AT ITS CONTACTS, ONE-WAY with the whole pad as
   the follower (`[design] one_way_rulings`), priced at `pad_flat` for the
   SENIOR frontage and at the law's own weight for a junior one. The
   leaders are the pavement's own vertices in a BAND (`_LEADER_MIN_M`
   10 m … `_LEADER_MAX_M` 50 m, inverse-distance weighted, ≤ `_LEADER_K`
   8 — solver constants, not law values, with the one-way lag as the fixed
   point): the pavement's NEAREST own vertex is a metre from the pad and
   already carries the pad's own pull, so a row against it lifts nothing
   (measured, §20.4 arm B), and the CONTACT itself is a pad vertex, so a
   row against it says only that the pad equals itself (arm A).
3. `solve/design` §9b drops every vertex a `[design] pad_level_rulings`
   row governs from every per-body DEM datum mean — the followers are the
   pad's own (non-contact) vertices; its CONTACTS stay in the pavement
   body's mean, being the pavement's own edge. A pad that fronts nothing
   mints no level row and keeps its datum, exactly as ruled.

**REFUTED AND DELETED IN ROUND 2** (measured, LEMD replay arms, §20.4):
(a) stating the plane as HARD coplanarity identities against three basis
vertices — at `hard_weight` an identity transmits whatever ELSE the rim
touches (LEMD T4S: 49 rim vertices on a basin retaining wall against 11 on
the apron it fronts) a hundred times harder than any level row can answer,
and the pad came out 0.34 m BELOW the round-0 surface; (b) reading the
pavement's value at a contact by a local affine extrapolation of its
nearest own vertices (unstable: the fit's weights blow up on a one-sided
neighbourhood and the airport moved tens of metres); (c) one aggregate
level row per pad read at the frontage's own CONTACTS (a plane through its
contacts equals itself — zero effect, measured byte-for-byte); and (d) one
row per CONTACT against the band (arm G): welded into the plate they are
the fit in principle, but the plate is finite and they WARP it — the worst
LEMD pad's residual from its own least-squares plane went 0.077 → 0.569 m
and the `pad_flat` verify rows 6 → 11, against a ruling whose bar is
0.01 m of planarity.

### 20.2 CONSUMER TABLE (owner 2026-08-30l) — before editing

| # | consumer | reads | ruling |
|---|---|---|---|
| C1 | `constraints/pads.pad_flats` | pad rim pairs | ROUND 2: BACK TO 09c — every pair of the rim, the contacts included. Round 1's drop is deleted; this row is the PLATE the fit acts on. |
| C2 | `constraints/pads.pad_slope_ceiling` | the same pairs | UNCHANGED in both rounds — the hard 1 % is the plane's tilt over its whole rim (09c). With the plate restored it is no longer the pad's only weld to its frontage, so it carries no fall of its own. |
| C3 | `constraints/pads.frontage_near_miss` / `frontage_contacts` | soft-role ring edges within `frontage_near_miss_m` of a pad, BOTH endpoints unshared | UNAFFECTED: that law is the SLIVER case (no shared vertex). A pad with a sliver frontage and no shared vertex mints no level row and keeps its DEM datum — stated, not changed. |
| C4 | `constraints/no_step.pad_contacts`, `constraints/routes` (the pad's route attachment) | `frontage_contacts` | UNAFFECTED via C3 — both name vertices, and no vertex, face or role moves. |
| C5 | `constraints/ceiling.pavement_ceiling` | every `Diff` over pavement vertices | EDITED: the two LEVEL heads join the pad ceiling's in the skip set (spec §9.2 B5's reason: a cap-0 one-way row twinned two-way at 5 % is a route by which the pad could pull the pavement). |
| C6 | `constraints/zones` (`pad_rim`, `pad_nearest`, `rigid_rims`, `strip_transverse`'s `pad_pick`) | "a pad with a rim vertex on pavement takes THAT level" | UNAFFECTED AND NOW TRUE BY CONSTRUCTION: an ATTACHED pad already gets no zone band (2026-09-05: CYXY/SPLP/SPJC/OTHH went hard-infeasible with one); 10l is what finally GIVES it that level. A DETACHED pad still takes its strip band. |
| C7 | `solve/design` §9b per-body datum (`_role_bodies_faced`, `_shape_bodies`) | apron-role bodies incl. `building` | EDITED (3). A pad's vertices leave the mean; the body itself (its connectivity) is unchanged, so no body appears or disappears. |
| C8 | `solve/design` §9 `detached_mean` / `cs.flats` | `Flat` groups | UNAFFECTED: 09c already stopped pads minting `Flat`; the only `Flat`s left are `constraints/structures`' tunnel mouths and ramp stations (spec §9.2 B9). |
| C9 | `solve/design` one-way lag (`one_way_max_rounds`, `_LAG_OFF`) | rows with `follows` | EXTENDED: LEMD 13,831 → 15,641 one-way rows (round 2). `follows` may now be a VERTEX SET (`Diff`/`Linear`), and the split is by (row, column) membership; the level row itself keeps one follower, and the set is what §9b reads. The lag still does not settle in 3 rounds (worst leader move 1.97 m); reported, unchanged from round 0's 0.46 m in kind. |
| C10 | `solve/why.py` `_FAMILIES` | generator + ruling | EDITED: `pad_level` is its own family, so a `why` on a pad names the pavement edge holding it. |
| C11 | `solve/design.DesignReport.families` | `row.source.generator` | the residual reporting the ruling asks for — `pad_level` gets its own rows/missed/max_m line. |
| C12 | `model/constraints.Diff` / `Linear` | frozen dataclass | EDITED: `Diff` gains `follows` (as `Linear` already had), and both accept a TUPLE of followers (round 2). Positional construction is unchanged; `solve/design` and `constraints/__init__.water_exempt` read it through `getattr` and normalise. |
| C13 | `planar/shapes.py` bodies, `structures.basins` rim sharing | the rim a pad and an apron share | UNAFFECTED: 10k already ruled a shared rim vertex is ONE vertex with ONE value and `basins` pins nothing there. The rim now RISES with the pad — that is 10l's intent ("objects then seat to that ground"). |
| C14 | `pipeline/build._plate_seats`, `airport/rebake_plan`, `emit/rebake.deck_datum_from_surface` | the emitted surface under an object | UNAFFECTED IN KIND: they read the surface, which now stands where the frontage puts it. Deltas re-measured at LEMD and OTHH (§20.4). |
| C15 | `verify/pads.pad_flat`, `verify/census.DEFECT_KEYS`, `harness/census.py`, `tools/check_grade.py` | the emitted rings | UNAFFECTED: no new shape class, role, feature class or sidecar key. `pad_flat` is not a DEFECT family (08v). |
| C16 | `emit/*` (`graded`, `bank`, `osm_adapter`, `clusters`), `pipeline/publication` | solved z, faces, axes | UNAFFECTED — no geometry is added or removed. |
| C17 | `law/design_schema.check_design` | `[design]` | EDITED: `pad_level_rulings` validated non-empty AND a subset of `one_way_rulings` (the pad FOLLOWS; a level row that is not one-way is the tier again). |
| C18 | Swift (`SceneryKit`) | JSONL event names | UNTOUCHED: no event, no wire name. |

### 20.3 The law values

`emit.toml [design]`: `pad_level_rulings` (the senior and junior heads),
the senior head added to `pad_flat_rulings`, both added to
`one_way_rulings`. No new number: the seniority is `precedence.toml`'s
order and the two weights are `pad_flat` (3000) and `law` (300), already
in the table. Round 2 adds NO law key and removes none — the band the
frontage is read in (`_LEADER_MIN_M` / `_LEADER_MAX_M` / `_LEADER_K`) is a
solver constant of the leader read, like `_MAX_PAIRWISE` beside it, and is
named as such in `constraints/pads.py`.

### 20.4 MEASUREMENTS (LEMD T4S, replay arms on the 2026-09-10 capture)

Transect: station 0 at `pav16`'s outer ring node toward the rim vertex
40.49098918, −3.57037578, 1 m stations, z over the patch's own
triangulation. Span 23.9 m (the whole distance from the ring node to the
rim).

| arm | transect fall | max 1 m step | pad z (spread) | pad ← plate? |
|---|---|---|---|---|
| round 0 (main) | −0.749 m | 0.033 | 598.488 (0.009) | yes (09c) |
| every pad row dropped (the pad-free reference) | +0.161 m | 0.007 | 598.919 (2.428) | — |
| round 1 (plate dropped at the contacts) — REFUTED | −0.345 m | 0.015 | 599.132 (0.342) | NO — 38 `pad_flat` rows |
| round 2 (A) HARD coplanarity, no plate — REFUTED | −1.395 m | 0.061 | 597.607 (0.054) | yes, hard |
| round 2 (B) as (A), leader = nearest own vertex — REFUTED | −1.001 m | 0.044 | 598.224 (0.572) | yes, hard |
| round 2 (C) as (B), leader = affine extrapolation — REFUTED | −3.298 m | 0.143 | 594.868 (0.263) | yes, hard |
| round 2 (E) as (A) with the level rows dropped | −1.032 m | 0.045 | 598.149 (0.212) | yes, hard |
| round 2 (G) the plate + one row per CONTACT — REFUTED | −0.494 m | 0.021 | 598.626 (0.073) | yes (09c), but WARPED: worst pad plane residual 0.569 m |
| round 2 SHIPPED (J): the plate + one LEVEL row per role | **−0.681 m** | 0.030 | 598.524 (0.038) | yes (09c); worst pad plane residual 0.147 m |

Readings that decided the design:

* The pad-free reference says the surface WANTS 598.92 there and the
  apron's last 24 m to RISE. Every arm that made the plane HARD landed
  BELOW round 0 — (A) and (E) are byte-identical in the pad's z to
  4 decimals, i.e. under a hard plane the level rows do nothing at all:
  the 94 hard identities carry the basin wall's 49 rim vertices at
  `hard_weight` 300000 while a level row is priced 3000.
* (B) shows why the leader cannot be the pavement's nearest own vertex:
  0.5 m from the pad, it reads 598.391 in the very arm whose pad sits at
  598.224 — the pad reading its own pull back.
* Arm G lifts the pad most (598.63) but each contact row pulls its own
  vertex against the plate: the worst pad's residual from its own plane
  goes 0.077 → 0.569 m and `pad_flat` verify rows 6 → 11. 09c's ONE PLANE
  outranks the extra 0.19 m of lift, so the SHIPPED arm is J.
* The SHIPPED arm (J) moves the pad's LEVEL only: +0.04 m over round 0 at
  the site, worst pad plane residual 0.147 m, transect fall 0.749 →
  0.681 m, and — the reading that matters beyond the site — the whole
  LEMD patch improves: verify rows 349 → 268 (`airside_no_step` 124 → 98,
  `within_shape` 132 → 118, `pad_flat` 6 → 7), census adjudicated
  268 → 228.

**The transect bar (≤ 0.10 m) is MISSED at 0.681 m** and is reported at
the attempt cap. ATTRIBUTION, which is the round's real finding: this
pad's rim is 49 vertices on the basin's RETAINING WALL and 11 on the apron
it fronts. One plane over that rim is a tug-of-war the frontage loses
11-to-49, and `why` on a contact reads "held by bending alone" — there is
no anchor on the pad at all beyond its frontage rows. Lifting it further
needs one of: the wall top FOLLOWING the pad it retains (a structure
ruling, not this one), or dropping 09c's one plane (refused by 10y). It is
an OWNER question, not a lane's.

BUILT ARMS (`build_airport.py LEMD/OTHH --engine v2`, control `--base-arm`
at `7e6eb5a6`): LEMD 498.8 s, DEFECTs 0 (no `runway_transverse`, no
`runway_vertical_curve` row in either arm); verify rows 349 → 268;
`pad_flat` 6 → 7 (bar ≤ 5: MISSED by one row, against round 1's 38);
census ADJUDICATED 268 → 228; pads 10 of 47 moved beyond 0.05 m (p50
0.351, p90 1.269, max 2.140; 3 rose, 7 fell), ring spread max 0.070 →
0.160 m; apron-edge → pad step 0.001 m (bar ≤ 0.05 MET). OTHH 645.0 s:
0 of 96 pads moved beyond 0.05 m, verify rows 16 → 13, and every rebake
family identical (43 corridors in 11 families, 4 door wells in 8, units
111 / members 948 / parts 140,273 / contacts 310,258 / skipped 263).

`pad_level` residual (LEMD): the family is one row per fronting pad and
role, so its line names the pads whose frontage the plane could not reach
— the reporting the ruling asks for.
---

## §21 THE RUNWAY PROFILE FOLLOWS THE AIRPORT — long gentle curves through the threshold pins (RULINGS 2026-09-10q/10r/10t) — lane `v2rwycurve`

### 21.1 The reading that founds it

SPJC 16L/34R (app 1.0.306): the built ridge reproduces the straight threshold
chord to ≤ 0.01 m at every 250 m station — zero vertical curves; z − DEM mean
+2.28, max +3.98; abeam the parallel taxiway the runway sits 26.71 m while the
lawful envelope (grade ≤ 1.5 %, end-zone 0.8 %, K ≥ 300 m per 1 %) admits 25.60,
and a lawful curved profile over the length cuts mean |z − DEM| 2.14 → 0.37 m.
Owner: "the runway also seems like it should be allowed to have a bit more
curvature, as in reality airports want to minimize the elevation variance between
adjacent paved areas when possible" (10q); "ideally the … profile would take into
consideration the whole airport layout, long gentle curves are best for fast moving
aircraft" (10r). The hard family laws stay (08v): K, longitudinal and end-zone
grades, transverse, the threshold and crossing pins.

### 21.2 The rule

1. **The target profile.** For a runway with two threshold pins, the ridge's fit
   target (`PlanarMap.preferred_z`, the channel `constraints/runway_chord.py`
   fills today with the straight chord) becomes the GROUND'S LONG-WAVE TREND along
   the ridge: at each ridge station the value of a moving quadratic least-squares
   fit of the production DEM over ±`[design] runway_profile_window_m` (default
   500 m — the scale of a K = 300 m vertical curve, so the target already has
   only long gentle curvature), the fit CONSTRAINED to pass through both threshold
   pins (the pins are the datum; the trend is shifted, not the pins). The crown
   drop at the lateral offset is subtracted exactly as today. The weight stays
   `[design] chord` (the row is the same row with a better target).
2. **The chord as fallback.** The straight chord remains the target where the DEM
   is absent or the frame is degraded (never an invented value, plan §2), and for a
   runway with fewer than two pins nothing changes (the DEM stays its target).
3. **The crossing pin (§17)** re-fits the TARGET PROFILE piecewise through the pinned
   node, exactly as it re-fit the chord.
4. **The hard laws are untouched.** The final projection (§16) still settles the
   family exactly; a target the laws refuse is simply not reached, and the report
   names the residual per runway (`runway_profile` block: target-vs-built RMS, the
   binding law).
5. **What the target is NOT:** a per-vertex DEM pull (08t (1)) — the window is
   longer than any DEM artefact the owner has read as "unrealistic undulation"
   (09b), and the fit is quadratic over ≥ 1 km of ridge; the runway cannot
   undulate with the ground, only bend with its trend.

Law keys: `[design] runway_profile_window_m` (schema-validated ≥ the largest
`vertical_curve_k_m`); no number in code.

### 21.3 Consumer table (RULINGS 2026-08-30l) — the lane completes the RULE column before editing

| # | reader | what it reads | rule |
|---|---|---|---|
| C1 | `constraints/runway_chord.py` `runway_chord_targets` | fills `preferred_z` per ridge station | the single derivation site: trend fit here; chord fallback here |
| C2 | `constraints/runway_chord.py` crossing pins (§17) | re-fits the chord through the pin | re-fits the trend |
| C3 | `solve/design.py` chord rows (:456-463) | `preferred_z` at weight `chord` | unchanged |
| C4 | `solve/project.py` (§16) | the hard family rows | unchanged; residual reported |
| C5 | `verify/runway.py` (`runway_vertical_curve`, `runway_crown`) | built profile vs the laws | unchanged; K rows now do work — DEFECT bar 0 |
| C6 | `tools/rwy_profile.py --binned --compare` (bows) | the bow against the STRAIGHT chord | the bow is no longer a target residual; the tool gains `--target` (built vs the trend target) and keeps the chord bow for continuity |
| C7 | the sidecar `design` block, `check_grade.SIDECAR_EVIDENCE_KEYS` | the chord record | carries the target kind (`trend|chord`) and window |
| C8 | the census `runway_*` families | rows | unchanged |
| C9 | taxi bodies touching the runway (10p/10t affine datum) | contact vertices | unchanged: contacts stay flush; the taxi body's tilt now follows its own DEM plane |
| C10 | `solve/why.py` `_terminal_kind` (:331) | `preferred_z.get(v)` — prints "held by its design target" | unchanged: it reads WHETHER a vertex has a published target, never which kind |
| C11 | `verify/roads.road_profile_agreement` (:29) | `preferred_z` whole-population mean/max \|z − preferred\| | unchanged in KIND (it already included the chord targets), but its whole-population figures now move with the runway target — read per face (`faces`), which is road-only, when comparing arms |
| C12 | `tools/v2_solve_replay.py` (:300-321) | calls `with_runway_chord` on the replayed stage | unchanged: it gets the new target for free; a replay of a pre-§21 stage is still comparable because the derivation is re-run, not cached |
| C13 | `pipeline/build.py` (:513) | gates `road_profile_agreement` on `pm.preferred_z` non-empty | unchanged |
| C14 | `airport/dem_production.ProductionDem.provenance['degraded']` | set only when a frame actually degraded | READ by the fallback (`runway_chord.dem_degraded`): the `--allow-degraded-dem` FLAG is not the test — the flag only accepts a degradation, and a warm frame under the flag still gets the trend |
| C15 | `law/model._check_cross_refs` | `emit.design` validation | gains the largest `rulesets.*.runway.vertical_curve_k_m`, handed to `check_design` (which imports nothing from v2) |

Verified by grep over `src/`, `tools/` and `tests/` for `preferred_z`,
`runway_chord`, `with_runway_chord`, `ChordReport` and `straight_z` (lane
`v2rwycurve`, before any edit). No other reader exists; the tests listed by
`blast.py` for `runway_chord.py` are the five in §21.4's run list plus
`test_v2cyxy.py` / `test_v2ground.py` / `test_v2smooth.py`, which construct
targets through `with_runway_chord` and are therefore C1's own consumers.

### 21.4 Twins and the closing tests

Twins (`tests/auto_patch_v2/test_v2rwycurve.py`): a ridge over a DEM with a 1 km
sag → the target passes through both pins and bends toward the sag with K ≥ law
(built profile: DEFECTs 0, target-vs-built RMS < 0.1 m); a DEM with 30 m noise at
20 m wavelength → the target is smooth (second difference below the taxi profile's
own bar), unchanged by the noise to 0.05 m; no pins → DEM target unchanged; a
crossing → the pinned node holds. Closing tests — SPJC (the site: 16L/34R abeam
the taxiway 26.71 → ≤ 25.7 m; mean |z − DEM| over the runway ≤ 0.6 m; DEFECTs 0)
and, because the family law changes globally, HECA and CYXY as the regression read
(HECA runway undulation RMS ≤ today's 0.0033; the 05C/23C and 05L/23R bows quoted
against v1's; CYXY's crossing profile monotone as 09ai; DEFECTs 0 everywhere) —
three airports, the stated exception for a family-law change. Site-first report.

## §22 A SKIRTED BUILDING NEEDS NO PAD (owner RULINGS 2026-09-10ag, over 10af) — lane `v2skirt`

### 22.1 THE SKIRT READER (`airport/skirt.py`, shared with Law C's narrow-cut test)

Per RESOURCE, in the AUTHORED frame, over the thickness-gated components
(`ResourceCache.genuine` — paint never witnesses), memoised on the cache so the
pack is parsed once for classify, planar and the re-seat plan:

* the FOOTPRINT = the plan union of every genuine triangle (a shell of vertical
  walls projects to zero area, so the floor/roof plates carry it); empty → the
  convex hull of the solid plan points. `footprint_perimeter_m` is its exterior
  length (every part's).
* the BELOW-ZERO geometry = each component Sutherland–Hodgman-clipped to
  `y <= 0` (`obj8_clip._clip_component`), its depth `-min_y`.
* `below_zero_perimeter_fraction` = the share of the footprint's exterior lying
  within `[skirt] edge_tolerance_m` of that below-zero union. A corridor or door
  well meets the perimeter only at its ends (small); a skirt runs all round.
* `is_skirt` ⇔ fraction ≥ `[skirt] perimeter_fraction` (0.5) AND the perimeter
  pieces' depths agree within `depth_tolerance_m` AND the shallowest ≥
  `min_depth_m`. `skirt_depth` = that SHALLOWEST depth `s` (conservative: relief
  ≤ s must hold against the thinnest part of the skirt).

A road-width cut is NOT a skirt by construction (its fraction is small);
`wall_corridors.py` is untouched — Law C's round imports this reader for 10af's
narrow-cut clause (ii).

### 22.1b A BASIN MEMBER IS NEVER SKIRTED (owner RULINGS 2026-09-10ax (2)) — lane `v2basinfix`

The reader above is per RESOURCE and answers "is the below-zero geometry uniform
across the footprint?".  A PIT answers yes: it is exactly that shape.  So the
basin admission runs FIRST and its members are exempt.

* `airport/basin_witness.py` — rule 1 of `planar/basins`' admission (a placement
  carrying a floor witness: 09ak's authored depth under the object's OWN datum
  as well as under the local ground), lifted out of the planar pass so classify
  can ask it.  `read_objects` moves here whole — ONE implementation, memoised on
  the shared `ResourceCache`, `planar/basins` re-exports the name — so asking at
  classify time costs the planar pass nothing.  No DEM, no basin member.
* the exemption sits at `skirt.skirted_placements`, the ONE derivation site of
  "skirted", so both §22.2 (the pad) and §22.3 (the seat) inherit it.
* `airport/rebake_plan.plan` exempts the members of the `below_grade` regions it
  is already handed from 09w (1)'s per-component below-grade skip: the basin's
  own exclusion / plate seat governs them.

Why (measured at LEMD, app 1.0.310): the T4S pit's own members
`Ground-FSX-LEMD36`/`LEMD85` read skirts of 7.014/7.03 m and covered 94 % of the
T4S terminal pad `building16` (relief 4.65 m), so §22.2 dropped it; with the pad
gone `planar/structures` no longer refused the OSM road bore `-5970` ("the mouth
stands against building pad building16"), its ramp became a `kind == "structure"`
cell on the pit's rim, and `planar/basins` rule 5 refused the basin — "27557 m2
overlaps a tunnel structure".  `basin_facilities` 1 → 0 between 1.0.308 and
1.0.309, the pit went uncut and `Ground-FSX-LEMD37` seated +4.7…+5.0 m onto the
uncut surface: the owner's "lip 2 m above the apron".

RESIDUAL, reported not fixed (outside 10ax (2)): the basin's floor is
`DEM(anchor) + agl + plate_y` while its rim takes the PAVEMENT's level (10ar), so
at LEMD the cut is 8.31–8.96 m deep where the object is 7.05 m and the plate seat
lands `Ground-FSX-LEMD37`'s authored wall crest (−1.88) 3.14–3.79 m under the rim
instead of 10aq's 1.9 m.  Whether the floor should be `rim − authored depth` is a
law question for the owner, not this lane's.

### 22.1c THE FLOOR IS THE OBJECT'S DEPTH BELOW THE RIM (owner RULINGS 2026-09-10ba) — lane `v2basinfix` round 2

22.1b's residual, ruled: the rim follows the pavement (10an/10ar) and the FLOOR
follows the RIM.  `constraints/structures.basins` no longer pins a floor vertex
at `Basin.floor_z` (= `DEM(anchor) + agl + plate_y`, an absolute datum the
pavement's own level never reached).  Each floor-ring vertex carries instead a
RELATIVE row against its NEAREST rim vertex — `z_floor − z_rim = −body_depth`,
where `body_depth = −Basin.solid_min_y_m` (the sidecar's `body_depth_m`, 7.05 m
at T4S).  The vocabulary's `Diff` is a symmetric grade cap with no offset, so
the law is ONE `Linear` EQUALITY (`lo == hi`, head `basin.floor = rim -
body_depth`), which the design solve carries as a two-sided target at `[design]
law` — the strongest tier below the active set — with `follows` naming the FLOOR
vertex: the floor follows, the rim is never pulled.  MEASURED AND REJECTED
first: the same equality as two opposing one-sided rows in `[design]
hard_rulings`.  Both halves are AT their bound at the solution, so the
augmented-Lagrangian polish escalates them against each other — at LEMD that arm
reported 1305/128088 hard rows active, max violation 0.3019 m, "HARD SET NOT
SETTLED", a runway projection moving 0.442 m and adjudicated 580 -> 1259
airport-wide, none of it near the pit.  A basin with no rim vertices or no
measured depth keeps the absolute pin (the fallback is reported, never silent).

THE CONSUMER TABLE (08-30l), every pass that reads the floor ring:

| consumer | ruling |
|---|---|
| `constraints/structures.basins` | the pin → the relative hard rows (the derivation site) |
| `constraints/structures.reconcile_datums` | a senior structure's Pin now also withdraws a junior basin's relative row |
| `solve/design` §8 | the row is an EQUALITY (`_law_sides`' `eqs`), priced at `[design] law`; NOT in `hard_rulings` (see above) |
| `solve/design` §9 | a vertex an EQUALITY with `follows` governs ANCHORS its sheet — the floor is no longer "detached" and takes no DEM plane of its own |
| `solve/why` | family `basin_floor` (`_FAMILY_KEYS`), so a trace on the floor names the rim it follows |
| `pipeline/build._plate_seats` | UNCHANGED — the stations are points ON the floor ring and the seat reads the solved surface, so the plate lands on the solved floor and the authored crest (−1.88) 1.9 m under the rim |
| `pipeline/publication.basin_facilities` | `floor_m` is the SOLVED floor (mean), with `floor_min_m` / `floor_max_m` / `floor_below_rim_m` (the law) and `floor_declared_m` (the object's own); `rim_law_m` is the SOLVED rim mean where the solve is known, `rim_estimate_m` stays R_est; `seat_expect_m` re-derived against the solved floor |
| `verify/structures.basin_floor_at_declaration` | the acceptance is now RELATIVE: every floor vertex within materiality of (its nearest published rim vertex − `floor_below_rim_m`) |
| `tools/check_grade._basin_facilities_declared` / `_basin_declared_drop` | the declared-floor JOIN is the published floor RANGE, the allowance `part − floor_min_m`; a sidecar without the range keys reads `floor_m` for both and is judged byte-identically |
| `verify/structures.basin_floor_declaration`, `structure_rim_gap`, `emit/rebake._plate_reading`, `airport/rebake_plan` | untouched (plan geometry, or the two bottom instruments, neither of which moves) |

### 22.2 WHICH PADS ARE NO LONGER MINTED

In `classify/evidence._pads`, BEFORE the pad is added and before every region is
differenced by `pad_union` (so the surrounding role covers the footprint and the
ground keeps its design surface — no hole, no new shape class): a candidate pad
is DROPPED when skirted placements' frame footprints cover at least
`[skirt] pad_cover_fraction` (0.5) of its area AND the DEM relief across its
ring ≤ the smallest `s` among those placements. Otherwise the pad stands exactly
as 09c/10y/10ah leave it — a skirt-less building, a mixed pad, or relief > s.

### 22.3 THE SEAT AT THE LOW-SIDE FOOT (a deviation from 10i's median)

`Member.skirted` (set in `airport/rebake_plan.plan` from the same reader, JSON
round-tripped, default false) reaches `emit/clusters.py`. Each ground part
already reads its own FEET; beside 09s (2)'s median it now also records the
MINIMUM over them (`_P.low`). A cluster EVERY one of whose parts belongs to a
skirted member takes `ground_m` = the min over the body's FEET instead of the
median over its parts' targets: the object's zero sits on the low ground and the
high side buries up to the relief, which is exactly what the skirt hides. Over
FEET, not over parts — a one-part body (a welded box) carries one target and
would otherwise not move at all. Every other body keeps 10i's median. `lifts`, the facility
coalition and the per-foot residual are unchanged (the residual now reports the
burial, which is intended, not a miss).

### 22.4 CONSUMER TABLE (owner RULINGS 2026-08-30l) — completed before editing

| # | consumer | reads | ruling |
|---|---|---|---|
| C1 | `classify/evidence._pads` → `Evidence.pads` / `pad_union` | building footprints | EDITED — the single derivation site. A dropped pad is dropped BEFORE `pad_union`, so `roles.classify` (:168, :315), the service-road difference and every downstream region see ordinary ground there. Prefer trimming at the derivation site over per-consumer vetoes (08-30l). |
| C2 | `classify/roles.classify` `add("building", …)`, `_cut_back_groundside` | `ev.pads` | UNAFFECTED IN KIND — fewer pads, so fewer groundside cutbacks. No role, no shape class, no sidecar key is added. |
| C3 | `constraints/pads.*` (`pad_flats`, `pad_slope_ceiling`, `pad_frontage_level`, `pad_datum_withdrawn`, `frontage_near_miss`) | rigid faces | UNAFFECTED IN KIND — they act per pad that EXISTS. A dropped pad mints no `pad_flat`, no ceiling and no level row; 09c's 1 % and 10y's fit stand for every pad that remains. |
| C4 | `planar/structures.py` (ramp stop at pads, `_pad_relief_m`, `ramp_crosses_pad`), `planar/wall_corridor_ramps`, `planar/structure_approach` | `role == "building"` | UNAFFECTED IN KIND — a dropped pad is no longer a stop for a Law-A/B/C ramp, which is 10ag's intent (no ramp is needed at a skirted building). `_pad_relief_m` now delegates to `skirt.ring_relief_m`, one implementation. |
| C5 | `planar/basins.py` (`cuts_pads`, the pad list at :351) and the basin RIM | pads | UNAFFECTED — 10k's rim is the apron's own hole ring and `basins` pins nothing where shared; with `building16`'s pad gone the rim is held by the apron alone, which IS the 10ah fix. |
| C6 | `airport/rebake_plan.plan` → `model/rebake.Member` | placements | EDITED — one new boolean field with a default, serialised both ways; `PLAN_VERSION` unchanged (an old plan reads `skirted=false` = today's law). |
| C7 | `emit/clusters.seat_clusters` | `gs` (the body's feet) | EDITED — §22.3, and ONLY the `ground_m` line. The cut law (10i (1)), the feet across the body (10i (2)), plates transitively (10i (3)), `PadRequest`s and `ClusterSeat.foot_res` are untouched. |
| C8 | `emit/clusters` facility rule / `lifts` / `coalition` | median lifts | UNAFFECTED deliberately — OTHH's deliberately separate datums (10i (4)) are judged on the same numbers as 1.0.308. |
| C9 | `verify/pads.py`, `verify/census`, `harness/census.py`, `tools/check_grade.py`, the `pad_flat` / `object_pad` families | emitted rings | UNAFFECTED — no new family, role or sidecar key; the counts fall because there are fewer pads, and that is reported, not adjudicated. |
| C10 | `tools/seat_feet_census.py`, `tools/v2_rebake_replay.py`, `tools/pad_level_report.py` | plan + result JSON | UNAFFECTED — additive plan field, unchanged result shape. |
| C11 | `airport/wall_corridors.py` (Law C) | below-zero geometry | UNTOUCHED this round — the reader is placed for its next round (10af (ii)). |
| C12 | Swift (`SceneryKit`) | JSONL event names | UNTOUCHED. |

### 22.5 The law values (`structures.toml [skirt]`, new)

`perimeter_fraction` 0.5 (10af proposes it), `depth_tolerance_m` 0.5,
`min_depth_m` 0.3 (= `basin.min_solid_thickness_m`'s scale: a lip is not a
foundation), `edge_tolerance_m` 0.5, `pad_cover_fraction` 0.5, `drops_pad` and
`seat_low_side` true (the two halves of the ruling, each a lawful value).

### 22.6 Twins and the closing test

`tests/auto_patch_v2/test_v2skirt.py`: a box building with a 2 m skirt on 1.5 m
of slope → no pad, seated at the low side, the high side buried 1.5 m, no wall
vertex floating; the same at 3 m relief → today's pad; no below-zero geometry →
today's pad; a road-width cut → not a skirt. Closing test LEMD patch only (pads
before/after, the T4S `building16` fall and the apron-edge → rim step,
`seat_feet_census` `> 3 m` and floating), OTHH patch only (pads and seat
families unchanged in kind).

### 22.7 MEASURED — LEMD and OTHH patch arms (lane `v2skirt`, branch `claude/v2skirt`)

LEMD, both arms `build_airport.py LEMD --patch-only --engine v2` (control
`--base-arm` at main `a85d16c2`), one shared corpus, DEFECTs **0** in both:

* the T4S terminal IS skirted, and `building16` is the ONE pad dropped
  (pad refs 21 → 20, emitted `role=building` ways 47 → 46). 72 of LEMD's 298
  plan members read as skirted.
* the transect (`pad_level_report.py transect`, `pav16`'s ring node toward
  40.49098918, −3.57037578, 1 m stations, solve-replay arms): FALL over the
  span **0.793 → 0.755 m** — the 0.10 m bar MISSED; max 1 m station step
  0.034 → **0.033 m**, the ≤ 0.05 apron-edge → rim step MET.
* ATTRIBUTION of the residual fall (`v2_solve_replay --why-vertex 21785`, a
  duals solve of the same LP): the pad is gone, and the rim end is now
  chained down by the apron's OWN rows — `apron_preference` 0.14 m over
  13.3 m, then `apron_within_shape` 0.10 m over 6.5 m — to v21779, an apron
  vertex SHARED WITH `retaining_wall#912`, which the trace calls FREE: "no
  binding row blocks it: above its DEM, held by bending alone". The T4S fall
  is the BASIN'S RETAINING WALL, not the pad and not the skirt (10ah named
  the pad's 49-to-11 loss to that wall; removing the pad hands the rim
  straight to it). z − DEM at the rim end −1.053 → −1.364. Outside 10ag/10af:
  STOPPED and reported, no fix attempted.
* `seat_feet_census.py` on the tile's existing +40−004 mesh (both arms the
  same terrain, `v2_rebake_replay seat` per arm): > 3 m **16 → 15**, 1–3 m
  34 → 28; feet standing more than 0.3 m ABOVE their ground 195 → 188
  overall and **14 → 7 for skirted placements** — the "0 for skirted bodies"
  bar MISSED, residual attributed: 3 of the 7 are ONE-FOOT bodies (a minimum
  over one foot is that foot — 10i's one-foot class, `Munoza-LEMDzaun`
  −5.96 m over a 5,157 m span), the other 4 are 0.34–0.75 m read against a
  mesh built from a DIFFERENT patch. Reported, not iterated on.
* census A/B: adjudicated 461 → 488 (+27), law-true 3,070 → 3,302; v2 verify
  `pad_flat` 6 → 4, `frontage_near_miss` 0 → 1; `retaining_wall` off-DEM
  > 0.5 m 42 → 8 (max 10.26 → 2.11 m). Pad MEAN levels: the largest move is
  0.49 m (`building10` 604.79 → 604.30). (`pad_level_report.py delta` reports
  a 33.8 m max: it joins ways by `shapeID`, which renumbers once a pad
  disappears — an instrument note, owed.)

OTHH, both arms `--patch-only --engine v2`: the patch is BYTE-IDENTICAL
(`body_sha f340732abaf1`), pads **33 → 33**, DEFECTs 0, `pad_flat` 0, verify
rows 4. The re-seat plan is identical member for member and part for part but
for the new `skirted_members: 13` count, and a seat replay of both plans on
the existing +25+051 mesh reads **58,826 parts, 0 differing deltas, max
0.000 m** — 10i (4)'s exemption holds exactly. The 13 skirted members are
Dewatering/Drainage 01–06, two tunnel objects, Bridge_03 (×2), DutyFree,
TerminalRoads_03 and Terminal_Parking.

## §23 THE GROUND'S OWN DATUM — adjacent ground follows the natural ground wherever the ground is lawful (owner RULINGS 2026-09-10av) — lane `v2grounddem`

### 23.1 The reading that founds it

CYXY, app 1.0.310: `bank_foot` node 60.7003105, −135.0581666 sits on the DEM (703.13 —
the daylight line of 09g, correct by construction); 44 m away inside the 14R/32L end
corridor's zone-2 strip (`adjacent_ground:runway:4:zone2#10`, shape 224) the strip is
graded to 700.1 where the natural ground is 701.96 — 1.9 m of cut where the ground is
lawful — and a 45 % cut bank climbs back to the foot over the 5 m minimum width. The
strip descended because 09b (3) made adjacent ground a pure law surface with NO DEM term
at all: with only one-sided rows the level is whatever bending leaves.

### 23.2 The rule

Every ADJACENT-GROUND vertex — the `graded_strip` family (zone 1, zone 2, the end
corridors, the clearance skirts: the vertices of the non-value, non-structure faces the
bending term prices at `bend_strip`) that is NOT also a pavement vertex — carries ONE
WEAK per-vertex row `z_v = DEM(v)` at `[design] ground_datum` (3.0). Its law rows are
unchanged: one-sided and ONE-WAY. Consequences, by construction: where the ground already
satisfies the zone law relative to its pavement, no law row is active and the datum is the
only term with a level, so the strip EQUALS the natural ground; where a law row binds, the
law (300) outprices the datum (3) by two orders and the strip is cut or filled TO THE LAW
LINE and no further. The ring is still emitted; it carries the DEM's own values where no
law binds.

09g (1) stands: INTERIOR ground (a strip pocket enclosed by pavement — one with no face on
the patch's outer boundary) is part of the design sheet and takes NO datum. The derivation
is one flood from the strip faces carrying an outside edge (`left_face`/`right_face` None)
through shared edges; `solve/design_ground.ground_datum_vertices` is its single site, and
`why` reads the same function rather than re-deriving it.

### 23.3 The one-way guarantee — proved by construction, and the one channel that is bounded

1. **The datum row itself.** `((v, 1.0),) = DEM(v)` carries exactly ONE column, v's, and v
   is never a pavement vertex (`pavement_roles` faces' ring vertices are subtracted at the
   derivation site). The pavement's normal equations therefore gain no row and no
   right-hand side from the datum: `AᵀA` acquires a diagonal entry at v alone.
2. **The law rows — one-way, with a MEASURED residue the lane REPORTS.** The zone corridor
   and the strip tie (`zones.zone_bands`, `zones.strip_transverse`) are minted with
   `follows = v` and their heads are in `[design] one_way_rulings`, so `solve/design` strips
   the LEADER coefficients out of `A1` into `A1_lead` and feeds them through the lagged
   `shift`: their pavement columns are absent from the matrix that is factorised, and a
   datum that moves v moves no pavement column through them, at any lag round. That is
   278 of the 290 mixed rows on the twin fixture. The RESIDUE — `rulesets.strip.longitudinal`,
   `rulesets.strip.arc_rate`, `rulesets.end_skirt.max_down_grade` (12 rows there), and a
   `no_step_pairs` pair that straddles a shared pavement/strip edge vertex — carries NO
   `follows` today and is priced two-way, so the datum reaches pavement through it. That
   predates this round (those heads were never one-way) but the datum is what makes it
   bite. DEVIATION REPORTED, never decided by the lane: making them one-way means minting
   `follows` in `constraints/strips.py`, outside 10av's text. Bounded here by the same
   measurement as (3).
3. **The bending sheet is the ONE remaining channel, and it transmits SHAPE, not LEVEL.**
   §6 deviation 1 keeps the strip inside the bending sheet (a blend with no bending term is
   not a blend), so a cotangent-Laplacian row centred on a pavement vertex at the pavement
   edge carries its strip neighbours' columns. A Laplacian row is a SECOND DIFFERENCE: it
   annihilates any affine field. The datum's dominant effect on a strip is a rigid level
   shift (and, over a zone width, a tilt) — both affine, both transmitted as exactly ZERO.
   Only the CURVATURE the DEM induces in the strip within ONE stencil of the pavement edge
   reaches pavement, priced there at the pavement vertex's own `bend_runway` / `bend_taxi` /
   `bend_apron` weight against `bend_strip` 30 and, where it matters, `law` 300 and the hard
   runway set. BOUNDED BY MEASUREMENT, not by assertion: HECA per-role `undulation.py` —
   `graded_strip`, `primary_parallel`, `junction`, `apron` each ≤ control + 5 %, bows
   unchanged, DEFECTs 0. A miss is a weight question first (the ruling says "tune").

### 23.4 Consumer table (owner RULINGS 2026-08-30l) — every pass that reads the affected geometry

| # | reader | what it reads | rule |
|---|---|---|---|
| G1 | `constraints/zones.zone_bands`, `zones.strip_transverse` | the zone-1 lip / zone-2 corridor bands and the strip tie, `follows = v` | UNCHANGED, and they are the guarantee (§23.3 (2)): the datum is an OBJECTIVE row, never a law row, so no generator, no bound and no census family changes |
| G2 | `emit/bank.daylight_feet` | `z_ring` vs its DEM along the outward normal | UNCHANGED code; the BEHAVIOUR follows: with the ring on the DEM, `sgn·(z0 − z_min) − slope·min_w ≤ tol` resolves at the first test, so the foot is at `bank_min_width_m` with zero drop — the ruled "the bank starts from a ring already on the DEM and vanishes there" is what the existing walk already does once the ring is right |
| G3 | `emit/bank` `no_bank` / `coverage_polygon` (§18 water, §19.3b edge collar) | the mask of boundary the bank skips | UNCHANGED — the datum changes the ring's VALUES, never the coverage geometry the mask is cut from |
| G4 | `planar/terrain_edge.clip_to_terrain_edge` (the crest flood) | the production DEM's outward slope on a 5 m grid, before the solve | UNCHANGED: the crest test reads the DEM only and never a design z, so the trim is bit-identical. The two laws compose — the corridor ends at the edge (§19), and what survives now sits on the ground |
| G5 | `verify/strips.py` (`resa_transverse`, `raoa`, `adjacent_ground_tear`, `strip_seam_tear`) and the census's `graded_strip` law families (`tools/check_grade.py`, `tools/harness/census.py`) | the BUILT surface | UNCHANGED — they report what the datum plus the one-way law produced. Counts are expected to FALL (a strip on its own ground tears against nothing); the lane quotes CYXY adjudicated before/after |
| G6 | `solve/why.py` `_terminal_kind` | a FREE terminal's note, today "held by bending alone" | a strip vertex the datum holds now reads "held by its ground datum" — `why` calls `ground_datum_vertices`, the same single derivation site, and invents no second rule |
| G7 | `solve/design.assemble` §9 (the ANCHORED test) | `preferred_z` / the zone ramp | a ground-datum vertex ANCHORS its sheet: a component holding datums takes no `detached_mean` plane on top of them (one level statement per body) |
| G8 | `DesignReport` / `report["design"]` / the `[v2] design` log line / the sidecar / `tools/v2_solve_replay.py` | the term counts | one new count `ground_datum_rows`; the replay's print is dict-generic and needs no edit. No new sidecar KEY and no wire-protocol name |
| G9 | `law/design_schema.DESIGN_TERMS`, `check_design`, `tests/auto_patch_v2/test_law_tables.py` | the term register | `ground_datum` joins `DESIGN_TERMS` and `Design`; validated positive and STRICTLY BELOW `law` (a datum that outprices a law row would cut where the law says fill) |
| G10 | `solve/rows._zone_weights`, `_Reduction.dem_fixed` | the ramp / the (always empty) fixed-terrain set | UNCHANGED: nothing is FIXED at the DEM — 09b (3)'s deletion of the beyond-the-ring fixing stands, and `bank_rows` still reads 0. A datum is a target, not a pin |

### 23.5 Twins (`tests/auto_patch_v2/test_v2grounddem.py`)

A runway end over lawful ground → the strip equals the DEM to 0.05 m AND the pavement
solution is byte-identical to the no-datum arm (the one-way guarantee, measured); ground
rising above the zone ceiling → cut to the law line exactly there and the DEM elsewhere;
ground falling faster than the lip law → filled at the law line; an enclosed strip pocket
takes no datum row.

### 23.6 Build-time impact statement

One extra objective row per adjacent-ground vertex (HECA order 5 k), each a single
diagonal entry in `AᵀA` — no new fill-in, no new factorisation, no new pass. Below the
1 % tripwire; the closing builds quote the solve wall.

### 23.7 MEASURED (lane `v2grounddem`, branch `claude/v2grounddem`, base `a88590c6`)

Weight: `[design] ground_datum = 3.0` as proposed — no tuning was needed, every bar held
at 3. Rows minted: CYXY 1,280 / HECA 5,518 / OTHH 4,858.

**THE SITE — CYXY, the 14R/32L end corridor** (`build_airport.py CYXY --engine v2`, arm
`CYXY_20260910T212708` body_sha `00e98af60b2a`; control `--base-arm` at `a88590c6`,
`CYXY_20260910T212759` body_sha `7b4eb532ab83`). `patch_transect.py --from 60.7009,-135.0560
--to 60.7003105,-135.0581666 --step 5` over the tile's own `Data+60-136.alt`, both arms:

| station | this arm | DEM | z−DEM | control | Δ |
|---|---|---|---|---|---|
| 80 m | 701.93 | 701.80 | **+0.12** | 699.96 | +1.97 |
| 85 m (the owner's point) | 701.94 | 701.92 | **+0.03** | 700.05 | +1.90 |
| 90 m (the ring's edge) | 701.96 | 702.00 | **−0.04** | 700.02 | +1.94 |
| 95–135 m | outside the patch (§19's trimmed corridor) | 702.09 → **703.13** (the `bank_foot`) | — | — | — |

The owner's exact point 60.7005131, −135.0573873 reads DEM **701.96** and lies just past the
§19 edge in BOTH arms; the last covered station is 0.03–0.04 m off its DEM against the
control's −1.90 m. Worst |z−DEM| anywhere on the transect 0.32 m (station 65), against the
control's 0.73–1.98 m. The largest station-to-station step is 0.50 m over 5 m = 10 %, far
under `bank_slope`; from the ring's edge to the foot the ground rises 1.17 m over 45 m =
2.6 %, so the 45 % cut bank of 10av is GONE. Bank rays resolving AT THE MINIMUM width
1,268 → 1,313 (daylighted 114 → 69) and bank slope p95 0.372 → 0.346: the ring now starts
on its DEM, which is the ruling's construction.

CYXY DEFECTs (`verify/census.DEFECT_KEYS`) **1 → 0** (`transverse` 1 → 0, `vertical_curve`
0 both). Census A/B (`tools/harness/census.py`, both arms): law-true 972 → 969 (−3),
ADJUDICATED 74 → 78 (+4: `airside_no_step` +13, `within_shape` −9, `taxi_box` −3,
`road_cross_section` −3, `transverse` −1). Crossings (09ai) unchanged: 8 runway crossings,
261 connected stations, 2 `crossing_pin` rows, both arms. Bows unchanged: −0.28 / −2.69 /
−5.31 m in both.

**HECA** (`--patch-only`; `HECA_20260910T214810` `6cf3e0269b0e` against control
`HECA_20260910T212839` `749db384728a`). `tools/undulation.py`, RMS second difference per
role, datum ÷ control — the bar is ≤ 1.05:

| role | control | this arm | ratio |
|---|---|---|---|
| graded_strip | 0.024684 | 0.022842 | **0.925** |
| primary_parallel | 0.009991 | 0.010380 | **1.039** |
| junction | 0.010711 | 0.010622 | **0.992** |
| apron | 0.013406 | 0.013445 | **1.003** |
| runway | 0.004426 | 0.004438 | 1.003 |
| whole patch | 0.017480 | 0.015557 | 0.890 |

Every role inside the bar; the strip is 7.5 % smoother and the taxiway edge is NOT dragged
(the bending channel of §23.3 (3), measured on a real airport). Bows −4.03/−1.77/−8.53 →
−4.02/−1.77/−8.53. DEFECTs `transverse` 640 → 641 (+1 against a standing 640 — HECA is not
a zero-DEFECT airport in either arm). Census A/B law-true 37,229 → 37,279 (+50, +0.13 %),
ADJUDICATED 6,264 → 6,281 (+17, +0.27 %).

**OTHH** (`--patch-only`): NOT byte-identical. `OTHH_20260910T213515` `585a18549564` →
`OTHH_20260910T215203` `9a4d01976d02`; v2 verify rows 46 → **34** (`within_shape` 14 → 1,
`airside_no_step` 1 → 2, `runway_crown` 31 both). Coordinate-joined (11-dp lat/lon, the
canonical identity join) over 29,813 shared plan positions: **2,298 changed**, |dz| mean
0.087, p95 0.320, max 2.180 m, and the change is the ground:

| role | changed | mean \|dz\| | max \|dz\| |
|---|---|---|---|
| graded_strip | 1,483 | 0.092 | 2.180 |
| (feature rings: bank foot / terrain edge) | 716 | 0.086 | 0.770 |
| tunnel_ramp | 61 | 0.036 | 0.150 |
| runway | 36 | 0.010 | 0.010 |
| apron | 1 | 0.010 | 0.010 |
| primary_parallel | 1 | 0.010 | 0.010 |

Every pavement vertex that moved at all moved 0.01 m — the rounding of the emitted
`alt_abs`. The strip's largest movers rise from 1.78–3.09 m to 3.94–3.96 m: OTHH's own
near-flat ground, which the law surface had been cutting below.

**Build-time.** Solve wall (one run per arm, ledgered, NOT a timing measurement): CYXY
6.95 → 3.34 s, HECA 56.41 → 43.27 s, OTHH 11.54 → 11.27 s. The datum adds a diagonal entry
per ground vertex and no fill-in; it does not slow the solve, and on these arms the
better-conditioned strip settled the active set sooner.

**Suite** `tests/auto_patch_v2` + `tests/test_harness.py`: 912 passed, 1 skipped, 2 failed
— `test_constraints.py::test_bench_style_instance_round_trip` and
`::test_cyxy_verify_matches_v1_census`, BOTH failing identically at the base sha (control
run). Five twins were RE-SCOPED where they held the superseded law, each with its measured
value in the test: `test_v2ground` (the strip's valley fill 1.06 → 0.70 m — 10av's own
point), `test_v2chord` (the chord-less control now has a level, 698.58 → 695.29), `test_why`
(a no-step chain step 0.020 → 0.141 m past its bound), `test_v2ridge3` (a box row 0.15 →
0.26 m, the same `bend_strip` channel its comment already named), `test_runway_transverse`
(with the crown generator OFF the census's WORST transverse row is no longer the pinned one).

**DEVIATION REPORTED (§23.3 (2)):** the two-way law-row residue. Never decided by the lane.

### 23.4 THE LEVEL BELT — no column reaches the solve without a level (RULINGS 2026-09-13m) — lane `v2zerocrater`

**MEASURED (the defect).** KCLT, build 2026-09-12 22:15, engine 1.50.1770,
`KCLT.graded.json`: **20 vertices at exactly z = 0.00**, all in apron face **661**
(`ref dsf:pol31`, role `apron`, side `airside`, ring indices 21–40 of 176), inside
lat 35.21391–35.21432, lon −80.94789–−80.94737. The built mesh carries a ~90 × 65 m pit to
sea level with a 130 m skirt of 100–200 m values and a rim at 215 m; four object bodies were
written at zero (`Charlotte_Airport_004_ALB__b20/b21`, `002_ALB__b8`, `001_ALB__b21`).

**ATTRIBUTION — it is not a no-data leak.** The production DEM at those four corners reads
**217.10 / 218.08 / 217.45 / 218.32 m** (`dem_production`, composed N35W081, inset
`KCLT:USGS3DEP`, coverage 100 %) — healthy ground. The pack's polygon carries no elevation
at all: `dsf:pol31` is `lib/airport/ground/pavement/asphalt/plain.pol` and
`airport/load.py:320` builds its ring from `_ring(poly.windings[0], to_xy)` — 2-D, no z.
The zero is minted by the SOLVE, in three steps:

1. `solve/rows._cotangent_laplacian` **clamps an obtuse cotangent weight to zero**
   (`if w <= 0.0: continue`, the line that keeps the operator PSD). Face 661's 20-vertex
   region touches the rest of its own face through exactly **one** triangle,
   `(14043, 14022, 14023)`, 186 m²; the angles opposite both of its crater-touching edges
   are obtuse, so both weights are clamped and **no bending row couples those 20 columns to
   anything**.
2. `solve/design` §9 ("a sheet carrying neither a pin nor a chord nor a zone fit floats — it
   takes its own DEM plane") judged connectivity with `_sheet_components(tris, red)`, i.e.
   on the **triangulation**, which that sliver joins. The piece therefore read as ANCHORED
   by the sheet's own anchors and was given no datum.
3. What was left in the matrix is a **homogeneous block** — bending rows only, every
   right-hand side zero — and the least-squares minimiser of a homogeneous block is exactly
   `0`. Measured on the captured KCLT problem: the crater's columns form a connected
   component of **20 of 21,873**, each column carrying 3–5 rows, all of them inside the
   component.

Same class as the degenerate hole of RULINGS 2026-09-10h (LEMD way −10892), whose note in
`planar/overlay.py` already described the mechanism — "the columns reach the least-squares
solve carrying no row at all, so their value is whatever the min-norm solution leaves
there". That fix trimmed the one GEOMETRY that produced it; this is the general closure.

**THE RULE — THE LEVEL BELT.** (1) `solve/design` §9c (`rows.apply_level_belt`): after every
row is minted, any column whose whole connected piece carries **no level at all** — every
row's coefficients summing to zero, which is bending, a second difference, a relative
equality, a `Diff` — takes its own terrain plane (`_plane_targets`, at `detached_mean`); a
piece with no DEM under it is **REFUSED BY NAME** rather than emitted at zero.
`DesignReport.level_belt_rows` reports it (a non-zero count names geometry no law levels).
A LEVEL is the coefficient SUM, never the right-hand side: a `Diff` bounding a difference at
0.3 m carries a non-zero rhs and levels nothing; a bending row one of whose feet the
reduction FIXED sums non-zero and IS levelled by that foot. The belt asks the only question
that cannot be got wrong — *does the matrix level this column?* — so the class is unreachable
however a future row family is wired.
(2) SHIP-SIDE: census family **`sentinel_elevation`** (`check_grade.LAW_FAMILIES`,
`law/families.toml`, cockpit class `sentinel`) — an emitted vertex more than
`emit.cockpit.sentinel_drop_m` (50 m) below the patch's own 5th-percentile elevation.
Patch-intrinsic (the census has no DEM) and read from a ROBUST floor, because the crater IS
the minimum. Cockpit class `sentinel` is CRITICAL unconditionally: a hole in the design
surface is not a height to price against a threshold and not a question of view.

**MEASURED (the fix), solve arm.** `tools/v2_solve_replay.py`, one KCLT capture
(22,294 vertices, 1,193 faces), both arms off it:

| | before | after |
|---|---|---|
| vertices at z = 0.00 | **20** | **0** |
| z min over the whole airport | **0.00** | **202.02** |
| vertices below 150 m | 20 | **0** |
| the 20 crater vertices | 0.00 | 217.51 … 218.04 (DEM 217.10 … 218.17, max abs z − DEM **0.67 m**) |
| level-belt rows | — | **20** (the crater, and nothing else at KCLT) |
| sheets / detached | 158 / 120 | 158 / 120 (**unchanged**) |
| vertices moved at all (> 0.01 m) | — | **20** — the crater, and NOTHING ELSE in the airport |

**DEVIATION REPORTED — never decided by the lane.** §9 (the per-piece DEM PLANE) still judges
anchoring on `_sheet_components(tris, red)`, i.e. the TRIANGULATION, which overstates the
objective's connectivity for exactly the reason above. Making it read the true coupling was
built and measured, and it is a LAW change, not a defect fix: at KCLT it splits the map's 158
sheets into 246 (120 → 193 detached), so 54 more pieces take a DEM plane of their own; at the
`test_v2aprontrend` fixture it splits the sheet 2 → 5 and improves the AFFINE CONTROL arm's
off-DEM from 0.877 to 0.180 m — i.e. it moves the very reading §8.7 exists to make. It is
therefore NOT landed; the level, which is the defect, is closed unconditionally by the belt.
The question for the owner: should a piece the objective holds apart take its own terrain
plane, or only its own level?

**MEASURED (the closing build).** ONE `build_airport.py KCLT --engine v2` (tag `v2zcfinal`,
468.7 s, rc 0, `body_sha fffa7c46a824`, v2-verify rows 4,190; the artifact ledger refused the
store — the tree's dirty flag moved between key and store time — so this run earns no ledger
entry). Against the owner's shipped 1.0.324 products (engine 1.50.1770, 2026-09-12 22:15;
a DIFFERENT base sha, so the totals are context, not an A/B):

| | shipped | this build |
|---|---|---|
| graded vertices at z = 0.00 | 20 | **0** |
| graded z min … max | **0.00** … 231.00 | **196.75** … 233.08 |
| face 661 (`dsf:pol31`) z | **0.00** … 216.56 | **213.90 … 218.04** |
| the 20 crater-box vertices | 0.00 | **217.51 … 218.04** (DEM 217.10 … 218.17) |
| census `sentinel_elevation` | **20** | **0** |
| cockpit CRITICAL visual | 22 (20 of them sentinel) | **2** (both pre-existing `strip_seam_tear` cliffs) |
| cockpit CRITICAL motion | 16 (worst **215.220 m** at the crater rim) | **15** (worst 3.640 m, an apron cliff 500 m away) |
| census law-true total | 12,383 | 12,353 (within 12,324, cross 26, steps 3) |
| ADJUDICATED | 4,406 | 4,386 |

THE FOUR BODIES WRITTEN AT ZERO were a CONSEQUENCE, not a second defect: all four anchor
inside the crater (`004_ALB__b20` and `002_ALB__b8` and `001_ALB__b21` at
35.2141301,−80.9475786; `004_ALB__b21` at 35.2141136,−80.9473902) and the senior one's
`anchor_reason` is literally *"surface at the body's zero"* — the placement stage sampled the
design surface and read 0.00. The surface it now reads there is **217.90** and **217.98 m**.
The re-anchoring itself is the object stage's (lane `v2unboxed`).

**MEASURED (the guard), on the SHIPPED patch** (`tools/harness/census.py`, law-true):
CRITICAL visual **22** of which **20 `sentinel_elevation`**, worst 209.470 m below the
floor at 35.2139084,−80.9478723 — the crater, named, at its own coordinate.

## §24 THE BASIN'S EDGE AND FLOOR (owner RULINGS 2026-09-11t) — lane `v2basinedge`

Owner, LEMD 1.0.315: "still a gap between the outer edge and the apron … the apron
elevation shape needs to be closer with less of a gap between the floor cutting
shape. The object also provides a floor … that should be visible instead of seeing
the terrain at the bottom of the basin."

1. **THE CUT HUGS THE WALL.** The basin's cut ring is the object's OUTER wall face at
   its top (the `basin_wall` ring of the floor witness's shell, read from the pack —
   not the OSM footprint, not a snap-out widening, not a buffer). The apron's rim
   vertices lie ON that ring at the rim level (§ rim_level: the rim IS the adjacent
   apron edge), so the pavement meets the wall top with no shelf outside it and no
   step down to it. Measured: horizontal distance from each rim vertex to the wall
   face ≤ `emit.weld_spacing_m` (1.0 m, the identity spacing); vertical step between
   the rim ring and the apron vertices it joins 0.00 m (materiality 0.01).
2. **THE FLOOR SITS UNDER THE OBJECT'S FLOOR.** The trench floor level = the object's
   floor-plate elevation (its authored y at the rim's zero, the 10bd depth) MINUS
   `[basin] floor_clearance_m` (new, default 0.5 m): the plate renders; the terrain
   is never seen through it. The basin's inner floor ring and every floor vertex
   take that level; the walls' bank between rim and floor is the object's wall
   (vertical in the object; the terrain bank is hidden behind it).
3. **Consumers**: the rim ring's derivation site (`planar/structures.py` basin /
   `basin_witness`), constraints `structures.rim_level` + the floor row, verify's
   basin family, `pad_level_report` leaders (a pad fronting the basin reads the rim),
   the placement anchor for a basin body (§6: a RIM point on the emitted ring). One
   table in the lane's report before any edit (08-30l).
4. **Measured first on the app's products** — `<Patches>/+40-010/+40-004/LEMD.graded.json`
   (T4S basin: rim ring vs the object's wall face, rim vs apron edge, floor vs plate) —
   then fixed, then LEMD once. Bars: (1) and (2) as stated; OTHH's Dewatering /
   tunnel basins unchanged by dry run; `> 3 m` unchanged.

**Measured** (lane `v2basinedge`, branch `claude/v2basinedge`; before = the app's
1.0.315 products, after = `LEMD_20260911T142115` `body_sha=0a6181fed68f`, rc 0,
360 s). T4S = `basin:0` (40.491701, −3.569256; members `Ground-FSX-LEMD36/37/85`),
the only basin LEMD admits:

| bar | before | after |
|---|---|---|
| (a) rim vertex → the object's outer wall face (≤ 1.0 m) | **+1.749 / +2.064 / +4.120 m, 56 of 56 OUTSIDE and over the bar** | **−0.251 / +0.010 / +0.264 m, 0 of 49 over** |
| rim ring area vs the shells' region | 28,971 m² over 27,557 m² (perimeter 705 vs 682 m) | 27,586 m² over 27,557 m² (682 vs 682 m) |
| (b) rim → apron vertical step (0.00, materiality 0.01) | 0.000 — all 71 rim vertices share their id with a ground face (23 apron, 51 pad) | 0.000 — all 59 do (14 apron, 47 pad) |
| (c) trench floor − the object's floor plate (−0.50 ± 0.01) | **+0.000 / +0.000 / +0.000 m** | **−0.510 / −0.500 / −0.500 m** |

Mechanism of (a): `planar/basins._rim` widened the region by whole grid steps until
it contained the floor (the plate ⊕ `floor_overlap_m`) and cleared it by the
stand-off; the T4S shell measures 0.00 m thick, so the loop ran to k = 4 = +2.0 m.
That is the owed `rim snap_out widening` item of RULINGS 08e deviation (2), now
closed: the rim is the region, and the stand-off comes out of the FLOOR
(`_floors_inside`, 1,066 m² trimmed at T4S).

OTHH dry run (planar replay of the new tree, no build): all **10** basins still
admitted, none refused; every rim vertex on its wall face (worst |0.494| m, 0 of
263 over the 1.0 m bar); the Dewatering pits' depths unchanged (13.142 m, the
04i/08d reading) and the drainage bowls' 3.816 / 4.201 m likewise, each now
+ 0.500 m of clearance. Basin verify families on the LEMD arm:
`basin_floor_declaration` 0, `basin_floor_at_declaration` 0, `structure_rim_gap` 0,
`wall_in_runway_strip` 0.

**DEVIATION REPORTED (§24 (1)), never decided by the lane.** A ZERO-THICKNESS
shell — LEMD's T4S, OTHH's drainage shells, and every synthetic box fixture —
cannot both keep the rim ON the wall face and give the floor its
`floor_overlap_m` outward past the plate: there is no wall thickness to spend.
The floor is therefore the plate TRIMMED to stand `rim_standoff` (0.5 m, the
identity spacing) inside the rim, which leaves a ≤ 0.5 m band of terrain inside
the wall line rising from the floor to the rim, its top standing up to the
clearance ABOVE the plate. The alternative is the shelf (1) exists to remove.

**NOT MEASURED by the lane**: `> 3 m` (the seat-feet census reads the object
stage, which needs the app's mesh) and a matched defect-gate control (the
1.0.315 products are a four-airport TILE build; a single-airport arm is a
different population, and a control build is a second build).

**MEASURED (lane `v2basinfoot`, 2026-09-13; branch `claude/v2basinfoot`, base
main `e5e04660`).** Before = the owner's 1.0.325 products (the four-airport TILE
build in the data repo: `Patches/+40-010/+40-004/LEMD.graded.json` +
`o4_v2_rebake_LEMD.json` + the copied patch); after = `LEMD --engine v2`
(`v2basinfoot3`, rc 0, 408 s, ledger `1c11f6fad3a2`, `body_sha 58a9ce7d3170`).

**(6) THE CONSUMER CENSUS, before any edit** — every pass that reads the basin
region / rim / floor, and what §24 (4)–(5) does to it:

| consumer | reads | ruling |
|---|---|---|
| `planar/basins.build_basins` | the region, the rim, the floors, the cut knife, the keep-outs | THE SINGLE DERIVATION SITE — both laws land here and nowhere else |
| `airport/obj8._witness` | the component's below-DEM clip (`FloorWitness.below`) | KEPT as rule 1's ADMISSION evidence; `outer` added beside it for the region |
| `constraints/structures.basins` | `faces_by_ref[floor_ref]` vertices, `wall_path`, `floor_below_rim_m` | EDITED: a floor vertex under a ramp corridor takes `deck − floor_clearance_m` (a senior pin); every other vertex keeps the 10ba relative row unchanged |
| `constraints/structures._rim_rows` / `rim_level` | the rim ring's vertices | UNCHANGED in form; the ring is a different (larger) ring, `rim_level` 11 design-target rows before and after |
| `planar/structures.py` `contact_band_m` reader (l. 352) | the LAW KNOB only, for tunnel-object wall bands | NO INTERACTION — it never reads the basin region |
| the pad cut (`cuts_pads`) | the knife vs `building` cells | UNCHANGED in form, and this is where the `building15` notch goes: the pad is now cut there (see below) |
| `building_pad.in_basin_sits_at_floor` | — | DEAD KNOB: declared in `law/structures.toml` + `law/model.py`, read by NO code (grepped). The pad is CUT, not lowered. Left alone, reported |
| `pipeline/build._plate_seats` | `Basin.ring` (the largest PLATE floor face) + `plate_y_m` | UNCHANGED: the ramp is a SEPARATE floor face (`basin_floor:0#1`), `ring` stays the plate's, so the witness's seat stations do not move onto the ramp |
| `pipeline/build._basin_polygon` | `b.region` (deck-signature evidence) | follows the larger region; LEMD deck families 0 before and after |
| `pipeline/publication.basin_facilities` | the record | EDITED: publishes `ramp_corridors` / `ramp_rings_ll` / `ramp_faces_ll` |
| `verify/structures.basin_floor_at_declaration` | the published depth vs every floor vertex | EDITED: under a corridor it expects `deck − clearance` (the SAME call, `model.structures.deck_z_on_faces`). Without this the law's own 42 pinned vertices report as violations — measured: 53 rows on the first arm |
| `verify/structures.basin_floor_declaration` / `structure_rim_gap` / `wall_in_runway_strip` | `solid_minimum_y_m` vs `body_depth_m`; rim-to-floor spacing; the strip | NO CHANGE: 0 / 0 / 0 before and after (the ramp floor is trimmed by the same `rim_standoff`) |
| `airport/basin_ring.py` (§14a arcs) | the EMITTED `basin_wall:0@k` ring from the graded doc | FOLLOWS AUTOMATICALLY, no edit: 6 arcs → 7, ring bar 0.19 → 0.18 m |
| `airport/placement_census` basin exemption | the plan's basin bodies | unchanged in form: basin carriers 24 → 25, exempt 20 → 20 |
| `tools/pad_level_report.py` | pads / refs in a solved pickle | no basin geometry of its own; reads whatever the pads became |
| harness `terrace_joints_ll` / `pad_relief` / `basin_floor_declaration` | the sidecar keys | `terrace_joints` 4 before and after, `basin_facilities` 1, `basin_floor_declaration` 0 |

**(4) THE RING IS THE SHELL'S OUTER FOOTPRINT.** Cause, reproduced on the
1.0.325 frame: `below` is `_clip_component` at ONE plane per component — the DEM
under the component's CENTROID, 593.00 for `Ground-FSX-LEMD85`, while the real
ground over the ramp runs 594.6 … 599.2. The road ramp is never above the DEM at
all (it lies 1.5 … 6.6 m under it its whole length); it leaves the REGION where it
climbs through 593.00, at **40.492259, −3.569411** — the exact closing point of
the below-clip, ~50 m short of the ramp's top.

| bar | before (1.0.325) | after |
|---|---|---|
| LEMD `basin:0` region | 27,557 m² | **28,345 m²** (+788: the notch) |
| rim ring | 59 nodes | **58 nodes**, Hausdorff **11.57 m** from the old ring |
| the notch at 40.4922455, −3.5695503 | `building/building15` z 598.36 … 598.48 | **`tunnel_trench/basin_floor:0` z 589.83 … 595.94** — the pad is cut, the ramp corridor is trench floor |
| §14a ring bar (`obj8_split_report --no-cut`, matched arms) | 0.19 m, 0 of 59 over 0.30 | **0.18 m, 0 of 58 over** |
| ring nodes the pit has NO WALL on (same instrument) | 3 (worst 1.11 m) | **3** (worst 1.31 m) |
| T4S tower cluster | `LEMDzaun`/`SWbaume` basin bodies on the rim, own-ground 7.59/7.57/7.55 m | **unchanged in kind** (7.71 m worst; the cluster stays on the rim) |
| OTHH, planar dry run, all 10 basins | — | **10 admitted, 41 refusals, rims moved (Hausdorff) 0.00 / 0.12 / 0.14 / 0.32 / 0.32 / 0.35 / 0.45 / 0.47 / 0.48 m — sub-grid, none over 0.48**; floor areas identical bar −15/−22 m² on the two Dewatering pits (rim re-snap) |

**(5) THE FLOOR FOLLOWS A RAMP.** The corridor is read off the shell's own
witness components: up-facing faces (`floor_plate_normal_y_min`) between the
floor and `R_est + contact_band_m`, joined in plan, admitted when the part SPANS
the pit (its own vertices reach within the band of both floor and rim) **and its
surface grade is drivable** — the area-weighted mean face slope, new law
`[basin] ramp_max_grade = 0.15`.

The grade test is not decoration: spanning alone admitted **three of OTHH
Drainage_01's banks (2,118 m², the pit's floor area 735 → 2,853 m²)**, because a
bowl's ring of banks climbs floor-to-rim like a ramp. Rise-over-plan-run does not
separate them either (that bank reads 3.61 m over 133.5 m = 0.03, a bowl
diameter apart); the SURFACE grade does: LEMD's ramp **0.09**, every OTHH bank
**0.20 … 0.29**. At 0.15 the LEMD ramp is the only deck either pack admits.

| bar | before | after |
|---|---|---|
| ramp corridors at LEMD `basin:0` | — | **1** (932 m² of floor, 36 deck faces; candidates refused: 2 m² × 2 "does not span", 101 m² "does not span", 2,043 m² `LEMD36` slab "does not span") |
| floor vertices on the ramp's profile | 0 | **42** (`basins.floor_ramp_vertices`) |
| emitted floor z vs `deck − floor_clearance_m` at every corridor vertex | — | **43 of 43 within 0.005 m** |
| the ramp deck vs the design surface under it | **−2.92 m worst over ~51 m (buried)** | **+0.50 m at every corridor floor vertex**; median +0.48 m over a 1 m grid inside the corridor |
| `basin_floor_at_declaration` | **5** | **4** |
| OTHH ramp corridors | — | **0 on all 10 basins** |

**Harness census (before = the 1.0.325 four-airport tile patch, after =
`v2basinfoot3`).** COCKPIT first: CRITICAL motion **2 → 3** (all three grade
BREAKS, worst 0.670 → 0.600 m, the same `strip_arc` site at 40.4625636,
−3.5525152 — nowhere near the basin), CRITICAL visual **0 → 0**. LAW-TRUE total
3,573 → 3,621; ADJUDICATED 1,143 → 1,172 (airside-for-acceptance 1,128 → 1,151);
`basin_floor_declaration` 0 → 0, `wall_in_runway_strip` 0 → 0.

**That census delta is NOT attributable to this change, and the lane says so.**
Two arms of THIS tree differing only in which deck faces the corridor publishes
(48 vs 42 pinned vertices) censused **1,089** and **1,172** adjudicated rows —
the LP's active set (`feasible`/"SET NOT SETTLED" vs `optimal`) moves more than
the basin does. The 1.0.325 arm is also a four-airport TILE build, a different
population from a single-airport arm (the same caveat §24 (1) recorded).

**NOT MET, with its cause named.** `_rim_open` read **57 of 69** open stations
before and **58 of 69** after (bar ≤ 5). The diagnostic's reference is
`at_grade_geometry`, whose linework is the shell clipped at ONE plane per
component — the very defect §24 (4) removed from the region. With LEMD's ground
running 593 … 599 across the pit and the plane at 592.00, the "at-grade line" is
a contour in the middle of the plate, not the wall top, so no ring can be close
to it. Fixing the rim diagnostic is a separate item and is OWED, not done here.

**NOT MEASURED by the lane.** The scout's `probe2.py` reading (11 of 59 ring
nodes 6.1–15.0 m from the nearest WRITTEN basin piece) needs
`o4_v2_placement_LEMD.json`, which only the app's write half produces; the
harness build entry stops at the patch, the graded doc and the rebake plan. The
engine's own §14a instrument (above, matched arms through `obj8_split_report`)
is what the lane could run, and it reads 3 → 3. A pack-geometry probe over the
nine basin resources' WALL faces reads the ring on the wall everywhere except
the new ramp stretch (nodes 15–20, 4.3 … 9.3 m), where the pack models a bare
deck and the mesh makes the trench's sides — which is the cut the owner asked
for. Also not measured: `> 3 m` seat feet against a matched control, and any
OTHH build (dry run only, as §24 (6) requires).

## §25 OSM RELATIONS ARE EVIDENCE — a multipolygon's outer ways carry its tags (Fable, 2026-09-11; RULINGS 2026-09-11aq item B) — lane `v2relations`

Owner (11ao): the large shape with a node at 40.4673861, −3.5681144 "is classified as
groundside, but it should be a building pad connected to apron". Scout `v2lemd319t`:
it is `pav146` / shapeID 105 (`parking_lot`, groundside, 63,643 m² emitted, apron
joints already 0.00 since 11af, pad steps +0.99 m against `building4`), read as a lot
because its mapped-apron cover is 5 % (`[lot] apron_cover_fraction` 0.1) and NO
building footprint lies under it. The session verified the cause in the extract
`+40-004_airports.osm.bz2`: `airport/osm.py:read_osm_file` reads `<node>` and `<way>`
only — the seven `<relation>` elements are skipped. Relation −1 is **Terminal 2**
(`building=transportation`, `aeroway=terminal`, `building:levels` 2; outer way −48,
31,956 m² inside pav146; inners −610/−611), and relations −2 … −7 are the aprons
R-1, R-2, R-4 … R-7 (`aeroway=apron`, type multipolygon; R-2's outer −1506 is 18,249 m²
inside pav146). Their outer ways arrive TAGLESS, so `classify/evidence._pads` never
sees the terminal and the apron cover reads 5 % instead of most of the shape.

1. **A RELATION'S OUTER WAYS CARRY ITS TAGS.** After the ways of a feed are read, every
   `<relation type=multipolygon>` (and `type=building`) hands its `TAGS_OF_INTEREST` to
   each member way of role `outer`; a member way's own tags win where both exist.
   An outer ring chained from several open ways is stitched into one closed way
   (count reported); an outer that cannot be closed is dropped and named.
2. **INNER RINGS ARE DROPPED THIS ROUND** (a courtyard in a pad is covered by the pad;
   an island in an apron reads as apron) — count and area reported; holes owed.
3. **CONSUMER CENSUS (owner ruling 08-30l), at spec time:** the only reader of the
   extract is `airport/osm.load_feed` → `OsmDoc.ways`; every consumer of `OsmDoc`
   (`classify/evidence.py` pads / aprons / lots / roads, `classify/sources.py`,
   `planar/structures.py` bores and cover, `airport/deck_signature.py`, `airport/
   tunnel_objects.py`) sees the same `RawWay` shape, now with tags on ways it
   already had. No new shape class, no new region: the change lands at the single
   derivation site. The lane greps `OsmDoc`/`load_feed` and confirms the list.
4. **THE OUTCOME AT LEMD**: Terminal 2's footprint (−48) becomes a `_pads` building
   pad unioned with its touching footprints (§20: the pad takes the apron's edge
   level, joint 0.00); pav146's apron cover rises (R-2's −1506, R-1's −64) so the
   remainder classifies as APRON or is absorbed; the `parking_lot` cell 15 is gone.
   The owner's intent — a pad joined to the apron — falls out of the data, not a
   new class. A pad across the approach of `tunnel:-17295+-7905@1` CLIPS its ramp
   (`ramp_crosses_pad = false`) — with §26 the bore is gone anyway.
5. **BARS**: at 40.4673861, −3.5681144 a `building` pad or `apron` face, joint to
   `pav176`/`pav92` 0.00, no `parking_lot`/`groundside_pavement` face containing the
   node; relation-derived ways at LEMD: 7 relations, N outer ways tagged (named);
   `explain LEMD --sources` before/after diffed (sources that change role, named);
   the same dry run on every airport whose products exist under the data repo's
   `Patches/` (OTHH, HECA, KCLT, CYXY, SPJC …) — relations found and roles changed,
   reported, none built; ONE LEMD build as the closing test (harness entry,
   ledger); harness census before/after; suite green.

## §26 A PASSAGE UNDER A BUILDING IS NOT A BORE (Fable, 2026-09-11; RULINGS 2026-09-11aq item A) — lane `v2relations`

Owner (11ao): "Still see a tunnel here: 40.4661521, −3.5708203 where there should be
no tunnel." Scout: the point is patch node −20478 in way −10946 = shapeID 933,
`tunnel_ramp` (192.5 × 24.2 m, floor 600.42 … 604.08, walls 5.09–6.97 m at the deck
end), the far portion of `tunnel:-17295+-7905@1` (mouth 596.90 = DEM 602.00 − 5.10,
top 432 m, one deck −11828). The seeds are OSM ways −17295 and −7905, 25.8 m each,
`tunnel=building_passage` — roads passing UNDER THE OLD TERMINAL, where the ground
does not drop. `airport/deck_signature.py:153` `is_tunnel_way` admits any `tunnel`
value other than `no`; `planar/structures.py:237` admits the bore because ≥ 1 m of
it lies under a classified cell (pav146). Class: 10 of LEMD's 33 covered bores are
`building_passage`; 27 of the 99 tunnel ways in the selection box.

1. **`tunnel=building_passage` IS NOT A BORE.** `is_tunnel_way` admits `tunnel=yes`
   (and the values `[tunnel] admitted_values` lists — default `["yes"]`) on a highway
   or railway; `building_passage`, `avalanche_protector`, `culvert`, `flooded` and
   `no` never seed a structure. The passage belongs to the building's pad (§22/§25).
2. **Railway bores are unchanged and REPORTED** (4 of LEMD's covered bores): whether a
   rail tunnel with no mouth inside the airport should seed a ramp is an OWNER
   question, asked with the count beside it.
3. **BARS**: no `tunnel_ramp` / `tunnel_mouth` / `tunnel_wall` face within 30 m of
   40.4661521, −3.5708203; LEMD structures line: covered bores 33 → 23, tunnels 18 →
   ≤ 13 (named), the 138 `within_shape` rows on shape 933 and the 4 + 1 mouth/deck
   rows gone; every remaining LEMD tunnel named with its OSM tag; the harness
   census before/after; the same ONE LEMD build as §25.

### 25.6 / 26.4 **MEASURED** (lane `v2relations`, branch `claude/v2relations`, base `0c7716a9`)

**THE READER (§25 (1)–(2)), one derivation site.** `airport/osm.read_osm_file` now
also reads `<relation>`; a `type=multipolygon` / `type=building` relation
(`RELATION_TYPES` — `type=route` and the rest hand nothing down) gives its
`TAGS_OF_INTEREST` to every member way of role `outer`, the way's OWN tag winning
key by key; open outer members are chained end-to-end into closed rings emitted as
extra ways `<ns><relid>#<k>` carrying the relation's tags (`_stitch`); a chain that
cannot close is DROPPED and its relation named (`RelationReport.unclosable`); inner
members are given nothing and counted with their area. `load_feed` merges the
per-file reports into `OsmDoc.relations`, `airport/load` into
`LoadReport.osm_relations`, and every `explain` run prints it:

    [LEMD] OSM relations (spec 25): relations 7, outer ways tagged 19,
           stitched 0, inners dropped 2 (6,171 m2)

`_osm_id`'s non-numeric fallback was `abs(hash(wid))`, which is SALTED per process
(PYTHONHASHSEED): the stitched rings are the first ids to reach it, and the same
extract would have named the same ring differently on every run. It folds through
`zlib.crc32` now.

**CONSUMER CENSUS (§25 (3)) — the lane's grep, against the spec's list.** The ONLY
importer of `airport/osm` in `src/`, `tools/` and `tests/` is
`airport/load.py:252` (`_osm.load_feed`, `_osm.FEEDS`); `terrain_edge.py:81` names
it in prose only. Nothing else constructs an `OsmDoc` or calls `read_osm_file`.
Every consumer the spec lists therefore reads `Airport.osm_ways` /
`Airport.buildings`, which `load_with_report` derives from `OsmDoc.ways` — the same
`OsmWay`/`Building` shape, now with tags on ways that already existed. The lane
found NO consumer the spec missed, and the list needs one addition of its own:
`airport/load._is_building` (a closed way with `building` / an aeroway building tag
becomes a `Building`), which is HOW Terminal 2's outer −48 becomes a pad. No new
shape class, no new region.

**AT LEMD (§25 (4)).** Extract `+40-004_airports.osm.bz2`: 7 relations — Terminal 2
(`-1`, `building=transportation` + `aeroway=terminal` + `building:levels`, outer
`-48`, inners `-610`/`-611` = 6,171 m²) and the six aprons R-1/R-2/R-4…R-7 — 19
outer ways tagged, 0 stitched (every LEMD outer is already a closed ring), 0
unclosable. `explain LEMD --sources`, before vs after, 308 source polygons both
sides, FOUR change class, none appears or disappears:

| source | before | after | apron cover |
| --- | --- | --- | --- |
| `pav146` (the owner's shape, 92,240 m²) | `lot` | `open` | 5 % → 27 % |
| `pav1` | `lot` | `open` | 0 % → 46 % |
| `dsf:pol33#0` | `lot` | `open` | 0 % → 100 % |
| `dsf:pol473#0` | `lot` | `open` | 0 % → 100 % |

Cells 601 → 597; source classes lot 41 → 37, open 256 → 260, strip 11 → 11. Apron
cover rises across the field wherever a relation drew the apron (`pav29` 0 → 59 %,
`pav165` 0 → 77 %, `pav47` 0 → 69 %, `pav172` 0 → 39 %, `pav92` 3 → 8 %). The owner's
node 40.4673861, −3.5681144 classifies `cell 18: role=apron side=airside kind=apron
ref=pav92` — the pad falls out of the data through `[lot] apron_cover_fraction`
(11af), with no new class.

**THE DRY RUN ON EVERY OTHER AIRPORT WITH PRODUCTS (§25 (5)) — reported, NONE
BUILT.** `explain ICAO --sources` in a base worktree at `0c7716a9` and in the lane,
same corpus:

| airport | relations | outer ways tagged | stitched | inners dropped | cells before → after | sources changing class |
| --- | --- | --- | --- | --- | --- | --- |
| LEMD | 7 | 19 | 0 | 2 (6,171 m²) | 601 → 597 | 4 (table above) |
| OTHH | 2 (`aeroway=aerodrome`, `aeroway=apron`) | 2 | 0 | 2 (773,141 m²) | 410 → 410 | 0 |
| HECA | 1 (`building=airport_terminal`) | 1 | 0 | 1 (619 m²) | 748 → 748 | 0 |
| KCLT | 30 (2 aerodrome, 8 apron, 18 hangar/terminal, 1 taxiway; incl. Rowan County in the 3×3 neighbourhood) | 164 | 30 | 1 (18,189 m²) | 605 → 599 | 7 (`pav33`, `pav34`, `pav65`, `pav108`, `pav109`, `pav113`, `pav127`: `lot` → `open`) |
| CYXY | 0 | 0 | 0 | 0 | 120 → 120 | 0 |
| SPJC | 2 (both `aeroway=terminal`) | 72 | 2 | 0 | 205 → 241 | 0 |

KCLT is where the STITCHER earns its place — 30 outer rings chained from 164 member
ways, zero unclosable. SPJC's two terminal relations add 36 cells with no source
reclassified: the terminal footprints are new pad geometry, not a new verdict on an
existing source. OTHH's two dropped inners are 773,141 m² of holes — the largest
"holes are owed" debt §25 (2) leaves, and the one to pay first.

**§26.** `[tunnel] admitted_values = ["yes"]` is the new law key (`law/model.Tunnel`);
`airport/deck_signature.is_tunnel_way(tags, admitted=DEFAULT_TUNNEL_VALUES)` is the
one predicate, and the law's value is threaded to it at all four call sites —
`planar/structures.py:227`, `airport/tunnel_objects.py:703`, and through
`planar/structure_approach.is_tunnel` / `approach` (from `mouths`, which holds the
law) and `planar/object_corridor.climb_path` (from `object_groups`). In LEMD's 0.05°
selection box the tag census is: `tunnel=yes` on a highway 52, on a railway 6,
`tunnel=building_passage` on a highway 22 — 80 ways seeded a structure before, 58
after. **The RAILWAY bores are the OWNER QUESTION §26 (2) names** (6 ways in the
box, 4 of them inside the built set): OSM ways `-26709`, `-26708`, `-22223`,
`-15314`, `-8677`, `-518`, all `railway` + `tunnel=yes`, none with a mouth inside
the field; they survive as `tunnel:-26708+-22223`, `tunnel:-26709+-8677` and the
mixed chain `tunnel:-5938+-26709+-8677+-26708+-22223`. Whether a rail tunnel with
no mouth on the field should seed a ramp at all is the owner's call, not the lane's.

**THE CLOSING TEST — ONE LEMD BUILD PER ARM, THE HARNESS ENTRY, MATCHED.**
`build_airport.py` defaults to `--engine v1`; a v2 lane's closing test MUST pass
`--engine v2` or it measures a patch none of this code touched (this lane proved it
the expensive way — the two `build_airport.py LEMD` runs came back BYTE-IDENTICAL,
body_sha `bcbc08883d14`, and are not reported here). The arms below are both
`--engine v2` on the shared corpus, DEM frame production, guard armed, shared repo
UNCHANGED, both stored in the artifact ledger:

| | BASE `0c7716a9` (`LEMD_20260911T223856`, ledger `af52d417abf3`) | LANE (`LEMD_20260911T223858`, ledger `93e48bce418e`) |
| --- | --- | --- |
| wall | 388.8 s | 391.0 s |
| ways / nodes | 1,101 / 24,067 | 1,089 / 23,703 |
| solve | optimal | optimal |
| body_sha | `646e612e55c2` | `775a8d4f3b29` |
| structures: bores | 91 (uncovered 62 ⇒ **covered 29**) | 68 (uncovered 47 ⇒ **covered 21**) |
| mouths / duals merged | 57 / 11 | 41 / 7 |
| **tunnels** | **18** | **16** |
| decks / cells cut / refused | 1 / 3 / 129 | 0 / 2 / 119 |
| v2 verify rows / DEFECTs | 2,691 / **0** | 2,433 / **0** |
| `within_shape` rows on shape 933 | **69** | **0** |
| `tunnel_mouth_canonical` / `tunnel_deck_clearance` | 7 / 1 | 3 / 0 |
| harness census LAW-TRUE | 4,559 | 4,600 |
| harness census ADJUDICATED | 1,995 (airside 1,877, gs 116) | **1,861** (airside 1,786, gs **73**) |

The base arm reproduces the SHIPPED 1.0.319 LEMD patch's census exactly (4,559 /
1,995) and its structures line exactly (bores 91, tunnels 18) — it is a true control.

**§26 BAR — MET.** Tunnel-family faces within 30 m of 40.4661521, −3.5708203:
**1 (`tunnel_ramp`, shape 933) → 0**. `tunnel:-17295+-7905` is gone from the built
tunnel list; `tunnel_ramp` faces 20 → 17. The 69 `within_shape` rows on shape 933
are 0, and the 4 mouth rows + 1 deck row §26 (3) names are gone
(`tunnel_mouth_canonical` 7 → 3, `tunnel_deck_clearance` 1 → 0). **Every remaining
LEMD tunnel, named with its OSM tag** — all 20 built tunnel names resolve to
`tunnel=yes` seeds and nothing else: `-12918` service, `-15327` service, `-15327+-5980`,
`-15347` tertiary, `-15349` tertiary, `-15349+-15347`, `-17028` service, `-17037`
service, `-17265+-5946+-6640+-1359` (service + primary), `-5772`, `-5780+-5727`,
`-5931`, `-5938`, `-5970`, `-5980`, `-6028`, `-9263` (all service), and the RAIL
pair `-26708+-22223`, `-26709+-8677`, plus the mixed chain
`-5938+-26709+-8677+-26708+-22223`. **RESIDUAL AGAINST THE BAR**: the spec expected
covered bores 33 → 23 and tunnels 18 → ≤ 13. The instrument reads covered bores
**29 → 21** (the same −8 the spec predicted, from a different base — 29 is what the
harness's own structures line says, on both the shipped patch and the control) and
tunnels **18 → 16**, not ≤ 13. Reported, not iterated (attempt cap): the remaining
16 are all `tunnel=yes`, so no further §26 narrowing is available — the ≤ 13
estimate counted bores, not built tunnels.

**§25 BAR — MET.** At 40.4673861, −3.5681144 the containing face is `apron`
(shapeID 84, ref `pav92`) in BOTH arms, but what stands beside it changes: in the
base arm a `groundside_pavement` face (shape 105, `pav146`) touches the node at
0.0 m and `pav146`'s two faces are both `groundside_pavement`; in the lane arm
`pav146`'s three faces are all **`apron`**, no `groundside_pavement` or
`parking_lot` face contains or touches the node, and `pav146` is ABSORBED into the
apron body rather than jointed to it (0 shared coordinates with `pav176`/`pav92`
faces — in the base arm the 30 + 46 shared coordinates already stepped 0.000 m, the
11af result). Groundside faces 71 → 66, apron 56 ← 54, and the census's groundside
adjudicated rows fall 116 → 73.

**BUILD-TIME IMPACT.** 388.8 s → 391.0 s at LEMD (+0.6 %, inside the ±25 % single-run
noise floor; the reader's extra work is one pass over the `<relation>` elements of
three feeds — LEMD has 7). No timing claim is made from one run per side.

**NOT MEASURED / NOT DONE by the lane**: the inner rings §25 (2) drops are NOT cut as
holes (owed — OTHH's 773,141 m² is the largest debt); no other airport was BUILT
(dry run only, per §25 (5)); the five-airport sweep is the orchestrator's; the
owner's other 1.0.319 items (floating signs, roof planes, basin gap) are other lanes'.

## §27 AN AIRSIDE EDGE MAKES A LOT AIRSIDE (owner RULINGS 2026-09-12c; Fable 2026-09-12e) — lane `v2airsideedge`

Owner: "shapeID 81 at 40.461514, −3.5732897 cannot be groundside because it shares a
long edge with an apron. Something can only be groundside if it has no connection to
airside other than a service road." Scout `v2lemd320t`: shape 81 is `pav137`
(2,571 m², `parking_lot`, groundside, apt.dat 110 polygon) sharing 140.2 m of its
270.9 m perimeter with the aprons `pav171` (77.8 m) and `pav92` (62.4 m); every joint
is welded at 0.00 — what the owner sees is the 5 % lot cap running a 2.2 % ramp and a
5.3 % corner through one continuous concrete page against an apron at 1.5 %. The
mechanism: `classify/roles.py:191-199` makes a `lot` source's face `parking_lot`
unconditionally (`continue` — it never reaches `_groundside`'s touch chain or the
apron-evidence ladder); v1's AIRSIDE-ADJACENCY VETO (`auto_patch/junction_repair.py:
2752-2789`, owner 2026-07-27, "a wide paved lot reachable ONLY via a service road",
shared edge ≥ 1.0 m) was dropped in the v2 port.

1. **THE RULE.** A lot-class face whose boundary shares at least `[lot]
   airside_edge_min_m` (10 m, weld-tolerant at `emit.weld_spacing_m` — the cell
   boundaries are pre-weld and under-read exact coincidence by ~30 %) with AIRSIDE
   PAVEMENT (the `side = airside` roles of `precedence.toml` except `building`) is
   NOT a lot: it is `apron`. A face whose only airside contact is through a
   `service_road` / `service_junction` face stays a lot. Slivers (area / perimeter
   < 1 m, an emit artefact) never flip.
2. **ONE DERIVATION SITE** (08-30l): the lot branch of `classify/roles.py` (and the
   symmetric guard on the 11ac demotion at `roles.py:300-313`); `side` stays a pure
   function of `role` (`law/tables.role_side`) and no downstream consumer changes.
3. **CLASS** (shipped 1.0.320 products): LEMD 13 substantive faces, 150,472 m²
   (`pav125` 79,408 m² / 828 m on apron; `pav124`; `pav119`; `pav25`; `pav3`; `pav70`
   ×6; `pav137` ×2); SPJC 5 / 167,163 m² (`pav46` 100,590 m², 2,089 m on `pav49`);
   HECA 5 / 56,231 m² (the twin terminal-frontage lots); CYXY 4 / 15,054 m²; OTHH 2 /
   8,443 m²; HEAZ 0; KCLT unmeasured (v1 patch). 41 LEMD slivers excluded by (1).
   A flipped face comes under airside law (1.5 % cap, `airside_no_step`, apron
   reach): by hand on the SHIPPED geometry the 13 carry ~294 pairs over 1.5 % —
   the solver regrades them; that is the intent.
4. **BARS**: shape 81's face `apron` (or absorbed into `pav171`/`pav92`), joints
   0.00, no pair over 1.5 % inside it after the solve; the 13 LEMD faces flipped and
   named; `explain --sources` dry runs on OTHH/HECA/CYXY/SPJC/HEAZ + a v2 `explain
   KCLT --sources` (flips named, none built); ONE `--engine v2` LEMD build as the
   closing test (base arm 4,600 / 1,861, groundside 73, in the ledger) — harness
   census before/after, airside adjudicated rows quoted; twins; INDEX; suite.
5. **ROADS FLIP TOO; THE EXEMPTION IS A MOUTH (owner RULINGS 2026-09-12f).** A
   `service_road` / `service_junction` face sharing >= `airside_edge_min_m` of
   LATERAL edge with airside pavement is `apron` (the free-road ruling, 2026-07-27).
   A groundside shape stays groundside only when every airside contact it has is a
   free road meeting it END-ON at the road's MOUTH — the strip's end cap, its
   cross-section (shared edge <= the strip's width x `[lot] mouth_width_factor`
   1.5, and transverse to the strip's axis) — never a lateral edge. Flips propagate
   along lateral shared edges (a lot beside a road that became apron is beside
   apron) and stop at mouths; the classifier iterates to the fixpoint. Bars add:
   LEMD's 61 apron-edged service-road faces named with their flip; the lots whose
   only contact is a mouth named as staying; the fixpoint's iteration count.

### §27 **MEASURED** (lane `v2airsideedge`, 2026-09-12, branch `claude/v2airsideedge`)

**Implementation.** One new module, ONE derivation site:
`src/auto_patch_v2/classify/airside_edge.py::airside_edge_flip`, called once by
`classify/roles.py` after every groundside verdict is in — the `lot` / `strip`
source branch, the 11ac demotion, the 04u open default AND the corridor roads cut
outside the pavement union (those are `final` entries now, so the free-road ruling
does not depend on which side of the pavement union a road was cut from). It lives
apart from `roles.py` only because that file is at its 1000-line ceiling
(`test_model.py`). `side` stays `law.tables.role_side(role)`; no consumer changed.
New keys: `[lot] airside_edge_min_m = 10.0`, `[lot] mouth_width_factor = 1.5`.

* **The measure is weld-tolerant** at `emit.identity.weld_spacing_m` (1.0 m): each
  airside boundary is buffered by the weld spacing and the candidate's boundary is
  measured inside the band, the non-mouth pieces unioned. Proven on the owner's
  face: LEMD `pav137` (shape 81) reads **95.0 m exact / 149.0 m welded** at
  classification time against **140.2 m** in the emitted patch — the exact reading
  under-counts by 32 %, the weld-tolerant one lands on the emitted number.
* **The mouth** is the FREE ROAD's end cap: the strip is the ROAD of the pair (by
  its ORIGINAL role, so a road that already flipped still offers its mouth), the
  contact at most `mouth_width_factor` strip-widths long AND within 45° of the
  strip axis' normal. Where NEITHER face is a road there is no mouth — a lot
  meeting an apron head-on is a lateral contact. (An earlier draft took the
  narrower of the two faces as the strip whatever it was; that exempted `pav3`'s
  178.9 m of apron edge as five short "mouths" and is wrong.)
* **The fixpoint** re-derives the airside set each round and stops when a round
  moves nothing; it terminates because a role only ever moves groundside → apron.
  Rounds: LEMD 3, OTHH 2, HECA 3, CYXY 3, SPJC 3, HEAZ 2, **KCLT 6**.

**Per-airport flips** (classification dry runs, both arms in ONE tree at one code
version, cell geometry read PRE pad-cutback — the frame the pass decides in):

| airport | lots flipped | m² | roads flipped | m² | rounds | `parking_lot` | `service_road`+`_junction` | `apron` |
|---|---|---|---|---|---|---|---|---|
| LEMD | 23 | 144,162 | 43 | 44,692 | 3 | 56 → 33 | 93 → 50 | 40 → 106 |
| KCLT | 64 | 347,785 | 26 | 52,195 | 6 | 172 → 108 | 91 → 65 | 29 → 119 |
| SPJC | 24 | 71,519 | 7 | 6,319 | 3 | 43 → 19 | 16 → 9 | 23 → 54 |
| CYXY | 4 | 18,037 | 3 | 2,941 | 3 | 27 → 23 | 21 → 18 | 7 → 14 |
| HECA | 0 | 0 | 15 | 67,084 | 3 | 3 → 3 | 25 → 10 | 20 → 35 |
| OTHH | 2 | 9,837 | 1 | 236 | 2 | 16 → 14 | 11 → 10 | 27 → 30 |
| HEAZ | 0 | 0 | 2 | 35,268 | 2 | 0 → 0 | 5 → 3 | 9 → 11 |

Kept groundside BY A MOUTH (the exemption doing its work): LEMD 0, CYXY 5, HECA 5,
OTHH 2, SPJC 2, HEAZ 1, KCLT 1. Every other kept face is a SLIVER (LEMD 40 of the
79 with airside contact). **No face anywhere reads ≥ 10 m of lateral airside edge
and stays groundside** — the pass is self-consistent at all seven airports.

**Closing test** — ONE `--engine v2` LEMD build, foreground, `--tag
v2airsideedge12f`, 385.9 s, rc 0, `body_sha 42f098178170`, artifact ledger
**`321c43eaba54`**, shared repo UNCHANGED. Base arm: the shipped 1.0.320 LEMD patch
(4,600 / 1,861 / groundside 73), reused, never rebuilt.

| census | BASE | AFTER |
|---|---|---|
| LAW-TRUE TOTAL | 4,600 | 4,812 |
| — within / cross / **steps** | 4,581 / 10 / **9** | 4,793 / 19 / **0** |
| ADJUDICATED | 1,861 | 1,983 |
| — airside / groundside / mixed | 1,786 / 73 / 2 | 1,817 / 166 / **0** |
| `vertex_to_edge_step` / `mid_edge_step` / `road_cross_section` | 1 / 8 / 3 | **0 / 0 / 0** |
| `apron\|apron` adjudicated | 442 | 357 |
| terrace joints (all three families) | 0 | 0 |

**BARS.**

1. **MET** — shape 81 is `apron`: `way -10085`, `ref pav137`, `role apron`,
   `shapeID 81` kept (its own face, NOT absorbed into `pav171` / `pav92`). Its one
   base row — `groundside_pavement|groundside_pavement` at **5.327 %** against the
   5 % lot cap, the owner's corner — is GONE. Terrace-joint families 0.00 / 0 rows.
2. **MET** — the class cleared on the EMITTED patch (`tools/role_edge_census.py`,
   promoted this round): groundside shapes sharing ≥ 10 m with airside pavement
   **71 substantive / 182,604 m² → 0**; the 13 LOT-class / 145,262 m² → 0; groundside
   shapes 175 → 68; the 28 that remain are all slivers (789 m² in total). The
   ruling's "61 apron-edged service-road faces" are inside the 58 non-lot
   substantive shapes that cleared.
3. **MET** — the site: rows within 130 m of 40.461514,−3.5732897 **16 → 7**; the 6
   `mid_edge_step` and 1 `vertex_to_edge_step` (`apron|building`) at the lot's old
   groundside boundary are gone.
4. **NOT MET** — "no pair over 1.5 % inside shape 81 after the solve": 3
   `apron|apron` within-shape rows remain inside `pav137`, **3.572 % / 1.887 % /
   1.869 %** at |de| 0.080 / 0.180 / 0.160 m. All three are SHORT pairs (2–10 m) at
   the `building4` frontage — the same pair carries the `frontage_near_miss` row —
   not the lot terracing the owner reported. Attribution, not a fix, and not this
   lane's to make.
5. **NOT MET (regression, attributed)** — adjudicated groundside 73 → 166. The rise
   is ENTIRELY one tunnel ramp: `tunnel_ramp|tunnel_ramp` 67 → 165 rows, 103 of them
   in the cluster at 40.495,−3.582 (25 in base). Same ramp (`ref tunnel_ramp`), its
   floor 597.34 → 596.99 m, worst grade 6.208 % → **7.890 %** against the 4 % cap;
   worst |de| essentially unchanged (11.16 → 11.13 m). The flip moved the apron the
   ramp's mouth sits on and the ramp got steeper. §26/§27 did not anticipate this
   coupling; it wants a ruling, not a lane fix.

**Collateral fix.** `planar/shapes.py::_joints_from` called
`linemerge(unary_union(segs))`, and `unary_union` of ONE segment is a bare
`LineString` that `linemerge` refuses ("Cannot linemerge LINESTRING ..."). Latent
since the joint pass landed; surfaced at CYXY when the flip left a single contour
joint. One line, guarded.

**OPEN, for the owner (not decided by this lane).**

* §27's candidate set is the class the rulings NAME — `parking_lot`,
  `service_road`, `service_junction`. `groundside_pavement` is left alone, so the
  synthetic page of `test_round3` is `apron` when a road reaches it (a lot, then
  flipped) and `groundside_pavement` when none does — on the SAME 200 m runway edge.
  Widening §27 to `groundside_pavement` would undo 04u ("open pavement is never
  apron by default") for every page welded to airside. That collision is a ruling.
* The tunnel-ramp regression above (bar 5).
* KCLT needed **6** rounds and flips 90 faces / 399,980 m² — by far the largest
  class, and unbuilt (v1 patch, no v2 arm). Nothing was built for it.

### §27 **ROUND 2 — MEASURED** (owner RULINGS 2026-09-12i; lane `v2airsideedge`, branch `claude/v2airsideedge`)

**(1) The class is widened to `groundside_pavement`.** `_AIRSIDE_EDGE_CANDIDATES`
is now `parking_lot`, `service_road`, `service_junction`, `groundside_pavement`.
The groundside STRUCTURE ramps (`tunnel_ramp`, `door_ramp`, `garage_ramp`,
`wall_corridor_ramp`) are not pavement an aircraft drives on and are never
candidates. Nothing else changed: same measure, same mouth, same fixpoint.

**It moves ONE face in the whole battery.** Re-dry-run, seven airports, both arms
in one tree at one code version:

| airport | lots | m² | roads | m² | **open pages** | m² | rounds |
|---|---|---|---|---|---|---|---|
| LEMD | 23 | 144,162 | 43 | 44,692 | **0** | 0 | 3 |
| KCLT | 64 | 347,785 | 26 | 52,195 | **0** | 0 | 6 |
| SPJC | 24 | 71,519 | 7 | 6,319 | **0** | 0 | 3 |
| CYXY | 4 | 18,037 | 3 | 2,941 | **1** | **518** | 3 |
| HECA | 0 | 0 | 15 | 67,084 | **0** | 0 | 3 |
| OTHH | 2 | 9,837 | 1 | 236 | **0** | 0 | 2 |
| HEAZ | 0 | 0 | 2 | 35,268 | **0** | 0 | 2 |

Kept by a MOUTH, named: HECA `route2` (505.6 m, all of it end-caps where the
corridor crosses taxiways), `route7` 25.0, `route18` 16.4, `route14` 16.0,
`route17` 8.0; CYXY `dsf:pol121` 138.3, `pav29` 42.9, `pav2` 9.9, `dsf:pol118`
8.8, `pav30` 7.8; OTHH `route6` 8.0, `dsf:pol16` 2.1; SPJC `route6` 6.5 lateral /
3.5 mouth, `route1` 8.0; HEAZ `pav17` 8.9; KCLT `dsf:pol66` 41.4. Every other kept
face is a sliver. No face anywhere reads ≥ 10 m of lateral airside edge and stays
groundside.

**LEMD is unchanged by the widening** — its 2 `groundside_pavement` cells carry no
lateral airside edge. Proven, not assumed: the round-2 build's patch body hash is
**`42f098178170`, byte-identical to round 1's**.

`test_round3` rewritten with the reason, plus a new twin
`test_an_open_page_welded_to_the_runway_is_apron`. 04u's default is now read on a
NARROW page (6 m) on the runway edge — still chain-seeded, so the open default is
what speaks rather than the touch-chain demotion, and every shared edge (with the
runway AND with its own proximity-band junction) is under 10 m. The same page at
its original 200 m width is `apron` with or without a road reaching it — before 12i
it flipped only when a road made it a lot, and read `groundside_pavement` without
one, on the SAME runway edge. That split is what 12i closed. Suite **1,133**.

**(2) THE TUNNEL-RAMP REGRESSION IS REFUTED AS A §27 MECHANISM.** Round 1 said
"the flip moved the apron the ramp's mouth sits on". Measured, that is FALSE.

* **Nothing at the mouth moved.** Every way within 60 m of the ramp's top
  (40.492496, −3.581971) reads the same altitude to the centimetre in both arms:
  `pav61` cross_connector 607.85–614.19/614.20, the two `tunnel_wall` rims
  609.26–610.11 and 602.16–610.00, `adjacent_ground:taxi:F:zone1#15` 609.66–614.19.
  The ramp's own TOP is 609.65 in both. At the floor end (40.495260, −3.583146) the
  only neighbour is the same `tunnel_wall` rim, identical in both arms. **No flipped
  face is adjacent to the ramp at either end.**
* **The plan geometry is identical**: 91 nodes, same top and floor coordinates,
  same 351.3 m longest chord. Only the elevations differ — the FLOOR moved
  597.34 → 596.99 m (−0.35 m) with the top pinned.
* **The corridor CAN hold 4 %.** Drop 12.66 m over a 323.4 m top→floor run =
  **3.91 %**, inside `[tunnel] ramp_max_grade` 0.040 with slack; a 4 % ramp needs
  **316 m** and `max_ramp_length_m` is **600**. So this is NOT a cap-versus-corridor
  conflict and NOT an owner question about the law. The law is satisfiable here and
  the solve does not satisfy it — the build's own line says so: "1820/126498 hard
  rows active (max violation 4.7518 m, **HARD SET NOT SETTLED**)".
* **The rows are not the same geometry.** Of 66 base row sites only **24** survive;
  **134** are new. Median pair distance 107.4 → 71.4 m, median |de| 4.33 → 2.92 m,
  and on the 24 shared sites the mean grade change is only **+0.06 pp**. The ramp's
  interior profile re-solved; it did not tilt.
* **A third arm settles it.** Round 1's FIRST build (`v2airsideedge`, ledger
  `7d95679b6539`) carried the 12e rule — lots only, no road flips, and no flipped
  face near the ramp either. Censused now:

  | arm | law-true | adjudicated | groundside | `tunnel_ramp` rows | worst grade | ramp floor |
  |---|---|---|---|---|---|---|
  | BASE (shipped 1.0.320) | 4,600 | 1,861 | 73 | 67 | 6.21 % | 597.34 |
  | A — 12e, lots only | 4,991 | 2,299 | 134 | 132 | **9.32 %** | 597.00 |
  | B — 12f/12i, lots+roads | 4,812 | 1,983 | 166 | **165** | 7.89 % | 596.99 |

  Two §27 variants with disjoint flip sets, neither touching the ramp, both move its
  floor ~0.35 m and multiply its over-cap rows — **non-monotonically** (A worse in
  grade, B worse in count). That is the signature of an LP re-solve of an unsettled
  interior, not of a mechanism. The base arm already missed the cap on 67 rows at
  6.21 %; §27 changes how much of a pre-existing miss is visible, not whether it
  exists.
* **Verdict:** not a §27 defect and not an owner question about `ramp_max_grade`.
  It belongs to the tunnel ramp's own unsettled solve (the ramp's interior is free,
  its top pinned, and its profile is whatever the objective leaves). Reported, not
  fixed, and the round-1 claim is withdrawn.

**(3) Closing test** — ONE `--engine v2` LEMD build, foreground, `--tag
v2airsideedge12i`, **378.9 s**, rc 0, `body_sha 42f098178170`, artifact ledger
**`3959b22219cb`**, shared repo UNCHANGED. Base arm reused from the ledger, never
rebuilt. Census identical to round 1 (same patch body):

| census | BASE | ROUND 2 |
|---|---|---|
| LAW-TRUE | 4,600 (within 4,581 / cross 10 / **steps 9**) | 4,812 (4,793 / 19 / **0**) |
| ADJUDICATED | 1,861 — airside 1,786 / gs 73 / mixed 2 | 1,983 — airside 1,817 / gs 166 / mixed **0** |
| `vertex_to_edge_step` / `mid_edge_step` / `road_cross_section` | 1 / 8 / 3 | **0 / 0 / 0** |
| terrace-joint families | 0 | 0 |

**BARS re-quoted.** 1 **MET** (shape 81 `apron`, own face, its 5.327 % corner gone).
2 **MET** (emitted groundside shapes sharing ≥ 10 m with airside pavement:
71 substantive / 182,604 m² → **0**; lot-class 13 / 145,262 m² → 0; groundside
shapes 175 → 68, the 28 remaining all slivers / 789 m²). 3 **MET** (rows within
130 m of the owner's point 16 → 7). 4 **NOT MET** (3 short `apron|apron` pairs
inside `pav137` over 1.5 %: 3.572 / 1.887 / 1.869 %, |de| ≤ 0.180 m, all at the
`building4` frontage). 5 **ATTRIBUTED AND WITHDRAWN as a §27 regression** — see (2).

## §28 GROUNDSIDE FRONTAGES TAKE THE PAD'S EDGE LEVEL (owner RULINGS 2026-09-11ai-1 → 2026-09-12r "grade frontages only") — lane `v2frontage`

Owner (11ah/11ai): `building4` (now 132,884 m² after §25) is one flat plateau; its
car-park and service-road neighbours terrace 1–2.6 m against it (`pav124` +2.63,
`pav137` +1.80, `route6` +1.80, `pav146` −1.01 at 1.0.317; the apron joints are 0.00
since 11af). The owner chose "grade frontages only": the plateau stays; the
neighbours meet it at its level.

1. **THE FRONTAGE RULE OF §20 (10l) EXTENDS TO PARKING AND ROAD FACES.** A
   `parking_lot` / `groundside_pavement` / `service_road` / `service_junction` face
   that shares an edge with a building pad takes the pad's edge level ALONG THAT
   EDGE (joint 0.00) and blends into its own body as a bank at the groundside
   terrace law's slope; where such a face fronts two pads at different levels, each
   frontage takes its own pad's level and the face grades between them under its
   own cap (8 %); where it cannot (the pads differ by more than the cap allows over
   the face's width), the SENIOR pad (largest shared edge) sets the level and the
   step is reported at the junior edge.
2. **THE PAD'S LEVEL IS UNCHANGED** — the apron frontage (§20's senior) still sets
   it; a groundside neighbour never pulls a pad (airside is king).
3. **CONSUMER CENSUS at spec time (08-30l)**: the pad-frontage constraint's
   derivation site (`constraints/` pad_level / frontage rows, `pad_level_report`
   leaders), the groundside terrace law (`constraints/groundside.py`), `no_step`
   pairing across the pad edge, `verify/steps`, and the harness families
   `terrace_joints_ll` / `pad_relief` — the lane confirms the list, adds nothing
   downstream, and lands the rule where the apron frontage lands today.
4. **BARS**: the `building4` pad's groundside joints 0.00 (today +2.63 / +1.80 /
   +1.80 / −1.01); every LEMD pad's parking/road frontage joints ≤ 0.3 unless
   reported as a junior-edge step with its numbers; no pad level moves (pad
   levels before/after byte-equal); harness census before/after (`pad_relief`,
   `terrace_joints_ll`, groundside rows); ONE `--engine v2` LEMD build against the
   ledger base; the other airports' pad-frontage census by dry run where the
   products exist; twins; suite.

### §28 **MEASURED** (lane `v2frontage`, 2026-09-12, branch `claude/v2frontage`, base `c00d97dc`)

**(3) THE CONSUMER CENSUS FIRST** (owner 2026-08-30l), ruled before any consumer
was edited. §28 (3)'s list was confirmed and NOTHING was added downstream:

| # | consumer | reads | ruling |
|---|---|---|---|
| F1 | `constraints/pads._fronting` / `pad_frontage` / `pad_frontage_leaders` / `pad_frontage_level` | the pad↔pavement frontage, the pad as follower | **EDITED, and this is where §28 (2) actually bites.** `pavement_roles` is every value non-structure role, GROUNDSIDE INCLUDED, so a car park entered §20 as a JUNIOR frontage and PULLED the pad — measured on the twin fixture, a lot 3 m above its pad moved the pad 0.032 m through exactly two `pad_level` rows. `pads._airside_only` now drops the groundside roles from a pad's frontage WHEREVER SOMETHING AIRSIDE FRONTS IT TOO (§28 (2): "the apron frontage — §20's senior — still sets it"). Where nothing airside does they are KEPT, and §28 mints no row back against that pad (`pads.pad_fronts_airside`), so the pair is stated ONCE and in one direction — never a circular lag. |
| F2 | `constraints/pads.pad_flats` / `pad_slope_ceiling` | the pad's rim pairs | UNCHANGED — the plate and the hard 1 % tilt. |
| F3 | `pads.pad_shared` / `pad_datum_withdrawn` | shared vertices, §9b | UNCHANGED: §28's rows govern GROUNDSIDE vertices and never a pad vertex. |
| F4 | `constraints/pad_relief.pad_relief_offsets` | rigid-face vertices only | UNAFFECTED — the relief target is the pad law's and returns pad vertices alone. Sidecar `pad_relief` 300 entries in BOTH arms; the census reads 304 pad vertices on their level plane. |
| F5 | `constraints/groundside.groundside_ramps` | the apron ring ↔ nearest groundside vertex across the stand-off, `[terrace] groundside_ramp_max` 5 % | UNCHANGED, and REFACTORED to read the new single derivation `groundside.groundside_face_roles` instead of re-spelling the predicate. It prices the APRON↔groundside stand-off (`building` is rigid, not `apron`), never the pad's, so §28 adds no row it duplicates. It is also the residual TWO-WAY channel — see the deviation below. |
| F6 | `constraints/no_step.pad_contacts` / `pad_only_vertices` / `pad_pavement_edges` | pad rim vertices shared with AIRSIDE pavement | UNCHANGED. "A rim vertex a groundside lot shares and no airside pavement does is the lot's (09-01g)" stands: pairing that stand-off minted 7.2 m `building|groundside_pavement` rows at SPJC. §28 REMOVES the step rather than pricing it as no_step; no new pairing. |
| F7 | `constraints/ceiling.pavement_ceiling` | every `Diff` / symmetric `Linear` over pavement vertices | EDITED — exactly §20's C5 case again: the two new LEVEL heads join the skip set, because a cap-0 one-way row twinned two-way at 5 % is a route by which the lot could pull the pad. |
| F8 | `solve/design` §9b per-body datum | `datum_roles` = APRON bodies only since 10v | UNAFFECTED, and the new heads are DELIBERATELY NOT in `pad_level_rulings`: a groundside face is not an apron body, so no datum mean contains the followers, and that register means "a PAD's vertices carry no DEM datum". |
| F9 | `solve/design` one-way lag | rows carrying `follows` | EXTENDED: both heads in `one_way_rulings`, follower = the single groundside vertex. LEMD one-way rows 13,831 → **13,897**. |
| F10 | `solve/design` row weights (`pad_flat_i`) | `pad_flat_rulings` | EDITED: the SENIOR head joins it (3,000); the junior keeps `law` (300) — §20's seniority pattern, seniority here by LARGEST CONTACT per §28 (1). No new law key, no new weight. |
| F11 | `solve/why._FAMILIES` / `DesignReport.families` | `row.source.generator` | EDITED: `groundside_frontage` is its own family, so `why` on a car-park edge names the pad holding it and the junior miss is a reported residual. |
| F12 | `law/design_schema.check_design` | the `[design]` registers | UNCHANGED code; the membership is twin-asserted (`test_v2frontage`), not re-spelled as a literal in the schema. |
| F13 | `constraints/roads`, `structures.rim_level`, `foot_rows` | `frontage_contacts` / `frontage_leaders` / `rigid_roles` | UNAFFECTED — no signature changed and none reads the new relation. |
| F14 | `planar/shapes.shape_joints` → `publication.terrace_joints_ll` → `check_grade._terrace_joints_to_m` | the emitted step across a shape joint | UNAFFECTED IN KIND. LEMD carries **4** joints in BOTH arms, the same shapes and lengths, steps 0.164/0.144/0.373/0.120 → 0.164/0.144/0.374/0.120 — and `building4` is in NONE of them: the owner's +3.03 m was never a declared terrace, which is why the census read zero rows on it. |
| F15 | `verify/steps`, `verify/census.DEFECT_KEYS`, `harness/census.py` | the emitted rings and declared joints | UNAFFECTED — no new shape class, role, feature class or sidecar key. `vertex_to_edge_step` / `mid_edge_step` 0/0 in both arms; `terrace_joint_route` / `terrace_joint_strip` / `terrace_actual_step` 0 in both. |
| F16 | `emit/*`, `pipeline/publication` | solved z | UNAFFECTED — no geometry added or removed. |
| F17 | Swift `SceneryKit` | JSONL event names | UNTOUCHED. |

**Implementation.** One new module, `src/auto_patch_v2/constraints/pad_frontage_gs.py`
(`groundside_frontage` = the relation as data, `groundside_frontage_level` = the
generator). It lives apart from `constraints/pads.py` only because that file stands at
the 1,000-line ceiling `test_model.py` enforces — the §27 precedent — and imports every
predicate from there, so there is ONE derivation of a pad's polygon, ONE of the frontage
radius (`[design] pad_frontage_m` 3.0) and ONE of the groundside pavement roles (the new
`groundside.groundside_face_roles`, which `groundside_ramps` now reads too). The rows are
one per FRONTAGE VERTEX against the pad's nearest 8 rim vertices, inverse-distance
weighted; the leader read carries NO minimum band, and the reason is stated at the
constant: 10y arm B needed the band because the leader already carried the FOLLOWER's own
pull, and here the leader is a rigid plate whose columns the one-way row strips out of the
matrix. **No blend row is minted** — the face's own within-shape cap
(`rulesets.<role>.longitudinal`, 8 % road / 5 % lot) IS the groundside terrace law, and a
second statement of it would be the census-wrapper defect in miniature.

**THE SITE — LEMD `building4`** (`tools/role_edge_census.py --pad-frontage`, promoted
this round). Base arm: the `v2ramp8` ledger patch `9a4a6b38bb6b`
(`/tmp/harness/LEMD_20260912T114310`), reused, never rebuilt.

| pad → neighbour | shared edge | pairs | BASE step | AFTER step |
|---|---|---|---|---|
| `building4` → `pav124` #881 (`parking_lot`) | 0.0 m (a 0.71–1.50 m gap) | 8 | **+3.03** (mean +1.79) | **+0.16** (mean +0.05) |
| `building4` → `pav124` #880 | 0.0 m | 1 | **+2.67** | **+0.09** |
| `building4` → `route6` #882 (`service_road`) | 0.0 m | 3 | **+0.38** | **+0.05** |
| `building4` → `route3` #74 | 0.0 m | 1 | +0.06 | +0.03 |
| `building12` → `pav70` #888 (`parking_lot`) | 0.0 m | 7 | −0.08 | **−0.02** |

Those five rows are the WHOLE LEMD population: at a 0.00 m floor the patch has exactly
TWO pads with any groundside neighbour within the frontage radius, and one pad
(`building4`) with a step over 0.10 m. The §25/§27 re-reading in the brief is confirmed —
`pav137` and `pav146` are `apron` now and join at +0.05 / +0.05, under §20.

**BARS (§28 (4)).**

1. **MET with a residual** — `building4`'s groundside joints **+3.03 / +2.67 / +0.38 /
   +0.06 → +0.16 / +0.09 / +0.05 / +0.03**. The bar's literal 0.00 is missed by 0.16 m at
   the worst vertex; that residual is REPORTED as its own family, not hidden — the design
   report's `groundside_frontage` line reads **15 rows, max miss 0.172 m** against a
   3.03 m starting step, and the miss is the lot's own 5 % cap pulling back (bar 5).
2. **MET** — every LEMD pad's parking/road frontage joint **≤ 0.16 m**, well inside the
   0.30 m bar, with no junior-edge step to report (no LEMD groundside face fronts two
   pads).
3. **NOT MET, ATTRIBUTED** — "pad levels byte-equal". `pad_level_report.py delta`, 46 of
   46 pads joined: **1 moved beyond 0.05 m** (`building17`, 614.096 → 613.987, −0.109 m);
   p50 0.000, p90 0.009, max 0.109; ring SPREAD identical in both arms (p50 0.020 → 0.020,
   max 4.540 → 4.540 — every pad is still the same plane). `building4` itself moved
   −0.012 m. The DIRECT channel is closed by construction and twin-proved: with the two
   PRE-EXISTING two-way rows across the stand-off held out of both arms
   (`groundside_ramp`, and the 5 % `pavement_ceiling` it is twinned into) turning §28 on
   leaves the pad byte-identical to 1e-9. What is left is those two rows: a lot standing
   3 m above what it stands off was LIFTING it, §28 stops the lift, and the surface
   settles. `building17` has NO groundside neighbour within 3 m in either arm, so its
   0.109 m arrives through the sheet, not through a frontage. **DEVIATION REPORTED, never
   decided by the lane** (the §23.3 (2) precedent): making `groundside_ramps` one-way — the
   groundside follows the apron, which is 08d (4b)'s own language — is outside 09-12r's
   text and is the owner's.
4. **MET** — harness census, both arms, one tree, one code version:

   | census | BASE `9a4a6b38bb6b` | AFTER |
   |---|---|---|
   | LAW-TRUE TOTAL | 4,408 (within 4,389 / cross 19 / **steps 0**) | 4,446 (4,427 / 19 / **0**) |
   | ADJUDICATED | **1,859** — airside 1,859 / gs 0 / mixed 0 | **1,783** — airside 1,782 / gs **1** / mixed 0 |
   | `airside_no_step` | 567 | **517** |
   | `taxi_box` / `transverse` / `strip_longitudinal` | 248 / 90 / 23 | 221 / 82 / 16 |
   | `within_shape` / `strip_arc` / `strip_transverse` | 3,407 / 7 / 41 | 3,527 / 13 / 45 |
   | `vertex_to_edge_step` / `mid_edge_step` | 0 / 0 | 0 / 0 |
   | terrace-joint families (route / strip / actual step) | 0 / 0 / 0 | 0 / 0 / 0 |
   | sidecar `terrace_joints` / `pad_relief` | 4 / 300 | 4 / 300 |
   | design target `pad_level` | 12 rows, max miss **1.819 m** | 9 rows, max miss **0.391 m** |
   | design target `groundside_frontage` | — | 15 rows, max miss 0.172 m |
   | design target `pads` / `roads` | 2,350 / 16 | 2,005 / 8 |

   **ADJUDICATED 1,859 → 1,783 (−76)**, and the `pad_level` family's worst miss falls
   1.819 → 0.391 m: dropping §20's unmeetable groundside junior rows is most of it.
5. **The one groundside adjudicated row, named.** It is a `within_shape` pair inside
   `pav124` #881: measured by hand on the emitted rings, the lot's worst own pair runs
   **5.15 %** against its 5 % lot cap over 35.7 m (BASE's worst inside the same lot was
   5.40 % over 7.2 m). That is the BANK §28 (1) grades away at, 0.15 pp over its cap — the
   frontage is held at the pad and the lot's 100 m body still has to climb 3 m back to its
   own ground. Groundside law-true pairs over cap 9 → 11 across the whole patch.
6. **Other airports, dry runs** on the shipped products (no build): **OTHH** 12 pads with
   a groundside neighbour, 55 neighbour rows, worst step **0.00 m** — nothing for §28 to
   do; **HECA** 6 pads / 14 rows, worst **6.05 m** (`building311`→`pav132`; `building7`→
   `pav48` −3.89 / −3.07); **CYXY** 4 pads / 5 rows, worst **3.99 m**
   (`building10`→`dsf:pol129`, `building9`→`pav4` +3.54); **SPJC** 15 pads / 16 rows,
   worst **3.84 m** (`building11`→`dsf:pol200`/`dsf:pol38`). Those four products predate
   this branch and none was rebuilt (BUILD ECONOMY: one airport per round); the class §28
   acts on is real at three of the four.

**Closing test** — ONE `--engine v2` LEMD build, foreground, `--tag v2frontage28`,
**424.4 s** wall, rc 0, `status optimal`, `body_sha 01f1d250c1d9`, artifact ledger
**`25fc9c8bcce1`**, shared repo UNCHANGED by the build (full-surface before/after
snapshot; 18 lock-churn operations, the allowed coordination class). Solve 57.40 s,
13,897 one-way rows in 3 lag rounds (LAG NOT SETTLED, worst leader move 0.383 m —
unchanged in kind), v2 verify rows 2,397.

**Twins.** `tests/auto_patch_v2/test_v2frontage.py`, 11 tests: the two heads registered
one-way with only the senior at the pad weight; the candidate class read as data and equal
to §28 (1)'s four names; the joint at the pad's level for EACH of the four roles, with the
face still grading away to its own ground; the frontage row unable to move a pad
(byte-identical with the two pre-existing two-way rows held out); the measured magnitude
and sign of the channel that IS left; the row shape (one groundside follower, every leader
a pad rim vertex, coefficients summing to zero so the row reads in metres); the senior /
junior split by contact length; and a face fronting no pad minting nothing.
`tests/test_role_edge_census.py` gains three for `--pad-frontage`. Suite
`tests/auto_patch_v2 tests/test_harness.py tests/test_role_edge_census.py
tests/test_mesh_sampler*.py`: **1,180 passed, 1 skipped** (1,169 / 1 on main; +11 new).

**Tool.** `tools/role_edge_census.py --pad-frontage [--near M] [--min-step M]` — the
near-fit extended, never forked (`7e90032`): same file, same parser, same node-identity
join, one index row updated in the same commit. The step must be read across the facing
gap and not by identity alone, because `building4` and `pav124` share NOT ONE node while
standing 0.71–1.50 m apart — and the harness census cannot answer this question at all,
since it forgives a declared terrace and the owner's +3.03 m was never declared.
## §29 A MOUTH IS BUILT ONLY ON THE FIELD (owner RULINGS 2026-09-12r; Fable 2026-09-12t) — lane `v2mouthgate`

Owner: "we should never emit anything for actual tunnels, only the tunnel mouths and
entrance/exit ramps … This applies to both rail and highway. The one exception is …
shallow tunnels with object based roofs that need an open trench." Scout
`v2tunnelmouths` on the 1.0.321 LEMD products: the bore already emits NOTHING
(`planar/structures.py:12-15`, cells cut 0); the exception is already the law twice
(`[cutout.sunken_road]` Law B requires a roof, `[cutout.wall_corridor]` Law C
requires headroom; `[tunnel.object]` REFUSES a roof) and never keyed on OSM. The
violation is the MOUTH: a bore is admitted by ≥ 1 m of cover under ANY cell
(`structures.py:238`) and then BOTH mapped ends become mouths with no containment
test (`structure_approach.py:282-294`). LEMD's two rail bores (4.9 km each) are
admitted by 125–162 m under the `building12` pad, their north mouths (on the field,
under T4) are refused against that pad, and their SOUTH-WEST mouths — 2.4 km outside
the OSM load box, 4.0 km west of every other patch feature, 95 m above the field —
are built: ramps 960/962, rims 691/692, banks 694/695 (149 vertices) that set the
patch's whole western bbox edge. They carry zero grade rows; the census cannot see it.

1. **A MOUTH IS BUILT WHERE A PILOT WOULD SEE IT** (owner 12ab, 12al): a `Mouth`
   whose point (and whose ramp reach) lies outside the governed region — the
   classified cover ⊕ `[tunnel] mouth_standoff_m` (150 m; 12aa/12ac) ∪ the APPROACH
   CORRIDOR of §31 (2) — is dropped at `mouths()`, named in the structures line
   (`mouths off-field N`); outside both it is raw DEM. A bore with no such mouth
   emits nothing. The corridor is ONE derivation shared with the cockpit block.
2. **ADMISSION FOLLOWS THE MOUTH, NOT THE BORE**: the cover test moves from "≥ 1 m of
   the bore under any cell" to "a mouth on the field" — a bore 5 km long admitted by
   one cell far from its only surviving mouth is the defect generator.
3. **DEAD KEY DELETED**: `[tunnel] bore_cut_clearance_m` (`structures.toml:12`,
   `model.py:297`) has no reader in v2 — removed with its schema line.
4. **BARS**: LEMD faces 960/962, rims 691/692, banks 694/695 gone; the patch bbox's
   west edge back at the airside extent (−3.594, was −3.641); every other LEMD
   structure byte-identical (15 highway corridors, Bridge4's cutting, the 2 decks);
   SPJC's two mouths and OTHH's object/wall-corridor set unchanged by dry read (their
   structures lines); ONE `--engine v2` LEMD build against the ledger base; the
   harness census unchanged (4,408 law-true on 1.0.321 — no tunnel rows exist);
   twins (an off-field mouth is dropped; an on-field one stays; a roofed corridor
   is untouched); suite.

**MEASURED** (lane `v2mouthgate`, branch `claude/v2mouthgate` off main `c1bcb73b`;
ONE tree, three arms, the shared corpus.  Rounds: the lane stopped on two misses,
RULINGS `2026-09-12aa` ruled `mouth_standoff_m` 100 m, and owner `2026-09-12ab`
answered 12aa-1 "Build them" — admission is BY THE MOUTH, the cover test deleted.)

Arms — BASE `c1bcb73b` (`v2mouthgate_base`, artifact `aafb8a0b4800`, body
`d3829dcb10c6`, 484 s) and the ruled tree (`v2mouthgate_r2`, artifact
`4a2a66a539fc`, body `b758bc344c3b`, 383 s).  The base reproduces the shipped
1.0.321 line and census exactly: `bores 68 (uncovered 47) mouths 41 duals merged 7
tunnels 17 decks 2 cells cut 0 refused 118`, 4,408 law-true / 1,859 adjudicated.

Ruled tree: `structures: bores 68 (no on-field mouth 36, mouth-only built 11,
replaced by objects 2)  mouths 48 (off-field 83)  duals merged 7  object corridors 1
door ramps 0  sunken roads 0  wall corridors 0  tunnels 26  decks 6  cells cut 2
refused 118`.

* **THE SITE IS GONE.**  The two rail mouths at 40.4805, −3.6395 build nothing:
  ramps 960/962, rims 691/692, banks 694/695 (149 vertices) absent, the 149 patch
  nodes west of −3.60 are 0, and the bbox west edge comes back 3.5 km — lon min
  −3.64071 → −3.59918 (the westernmost feature is now one of the newly built
  on-field portals at 40.48619, −3.59878; the airside extent is −3.59384).
* **ROUND 3, THE STANDOFF AT 150 m** (`v2mouthgate_r3`, artifact `d27130a304b3`,
  body `4d66e96d21b7`, 387 s; the 100 m arm `v2mouthgate_r2` / `4a2a66a539fc` /
  `b758bc344c3b` is the previous step).  Of the five on-field highway corridors the
  50 m standoff dropped, 100 m returned three (40.48701,−3.55443 / 40.48974,−3.54980
  / 40.49455,−3.55410) and 150 m returns a FOURTH byte-identically (40.48995,−3.55896,
  the same 16-vertex ramp, 0.3 m of centroid).  **40.51063,−3.56311 is still not
  built**: its mouth (bore `-6028`) stands **208 m** off the field — outside 150.
  The "natural gap" the value was chosen in (146 → 208) is exactly that corridor's
  own drop; keeping it needs ≥ 210 m, after which the next drops are 228, 267, 277,
  361, 383, 393, 429 m (the widest gap left is 208 → 228).  Unruled, so 150 stands
  and the corridor is OWED a decision.
  Line: `bores 68 (no on-field mouth 35, mouth-only built 12, replaced by objects 2)
  mouths 55 (off-field 76)  duals merged 9  object corridors 1  tunnels 29  decks 6
  cells cut 2  refused 118`; ramps 18 → 33.
  Census 4,408 → **4,576** law-true (+168), adjudicated 1,859 → **1,928** (+69):
  `within_shape` +132, `taxi_box` +65, `strip_transverse` +6; against
  `airside_no_step` −22, `strip_longitudinal` −6, `transverse` −4,
  `resa_transverse` −2, `frontage_near_miss` −1.  (At 100 m the same ruling read
  +104 / −87; the extra corridors admitted between 100 and 150 m carry the +64
  law-true and turn the adjudicated delta positive — the portals are real, so the
  rows are their surfaces meeting the field, not the rail defect.)
* **THE MOUTH-ONLY PORTALS ARE BUILT** (owner 12ab): at 150 m, **12** bores admitted
  on an on-field mouth alone, named in the build line — `-16684, -16683, -15336,
  -12795, -7847, -5284, -4054, -4043, -3829, -6339, -1581, -1568` — mostly 2–4 km
  south (40.4587…40.4798, −3.570…−3.583).  `tunnels` 17 → 29, `decks` 2 → 6,
  `mouths` 41 → 55 (76 ends dropped off-field).
* **CENSUS BY STANDOFF** (harness, one tree, against the same base): 50 m with the
  cover test deleted read 4,737 / 1,910 (+329 / +51); 100 m read 4,512 / 1,772
  (+104 / −87); **150 m, the ruled value, reads 4,576 / 1,928 (+168 / +69)**.
* **DEAD KEY** `bore_cut_clearance_m` deleted (toml + `model.py`; the law loader is
  strict, so a stale key refuses).
* **DRY READ (no build).**  OTHH's tunnel set is corridor-driven — object and
  kerb-wall corridors are built from the pack's own geometry through
  `object_groups` / `extra_groups`, which never pass through `mouths()`, and the
  corridors' footprints are inside the governed region — so its shipped line
  (`bores 22 (uncovered 13, replaced by objects 6) mouths 4 object corridors 8
  tunnels 9`) keeps its object-replaced mouths.  Its four remaining OSM mouths are
  NOT proven unchanged (LEMD drops that class beyond 100 m and no OTHH product on
  disk carries the distances), and under 12ab OTHH's 13 uncovered bores may now be
  ADMITTED wherever a mouth stands on the field — unmeasured.  SPJC's two on-field
  mouths are the scout's reading (`2026-09-12t`); no SPJC v2 product is in the tree.
* Twins: `tests/auto_patch_v2/test_v2mouthgate.py` (6) — an on-field mouth built,
  an off-field one dropped and counted, a bore under cover with no on-field mouth
  emits nothing, the standoff read from the law (both sides of the boundary), a
  mouth outside every standoff whose RAMP REACH runs onto a cell beyond it kept,
  and a mouth on the field whose bore covers nothing BUILT and named — plus
  `test_v2wallcorridor.py::test_the_mouth_gate_leaves_the_roofed_corridor_untouched`.
  Suite 1,176 passed / 1 skipped; targeted v1 tunnel set 151 passed with 12p's
  pre-existing `test_tunnel_portal_fidelity::TestClearanceAnnulus` red.
* A concurrent process wrote 11 New Zealand paths into the shared repo during the
  DISCARDED first arm (CONTAMINATED flag worked, artifact not stored); the base and
  both kept arms report the shared repo UNCHANGED.
### 29.1 **MEASURED, ROUND 2 — THE APPROACH CORRIDOR** (lane `v2approachcorridor`, branch `claude/v2approachcorridor` off main `19af2772`; owner RULINGS 2026-09-12al answering 12ae-1: "if it would be visible from an arriving or departing aircraft it should be cut, if not we can leave it raw DEM")

**THE CORRIDOR, ONE DERIVATION.**  `src/auto_patch_v2/law/approach_corridor.py`
(`ApproachCorridor`): per runway END, `[cockpit] approach_km` (5) beyond the
threshold along the extended centreline, `[cockpit] approach_half_width_m`
(2,000 m, the new key) to each side.  The ENGINE reaches it through
`planar/structure_approach.approach_corridor_of` (axes = `airport.runways`'
apt.dat thresholds) and `FieldRegion(polys, mouth_standoff_m, corridor)`; the
HARNESS through `check_grade.cockpit_geometry` (axes = the emitted runway
rings' principal axis, `grade_law.runway_axis_and_width`, joined by ref).  Same
class, same two law numbers, one rectangle — twinned on one fixture.  The 5 km
runway-axis DISC is deleted, and with it the `approach_m` argument of
`cockpit_in_view`, so no caller can pass a radius in.

**(1) THE SHIPPED LEMD PRODUCTS** (`Patches/+40-010/+40-004/`, the owner's
1.0.323 rebuild, `LEMD_auto.patch.osm` mtime 2026-09-12 12:11; copied before
reading).  4 runway axes -> **8 corridors**, 0 boundary rings (so at LEMD the
corridor is the WHOLE in-view test):

| corridor | threshold | outward | tip (5 km) |
|---|---|---|---|
| 14L/32R:0 | 40.49705,-3.55999 | 322.3° | 40.53258,-3.59611 |
| 14L/32R:1 | 40.46790,-3.53037 | 142.3° | 40.43237,-3.49426 |
| 14R/32L:0 | 40.48619,-3.57737 | 322.2° | 40.52170,-3.61352 |
| 14R/32L:1 | 40.45522,-3.54583 | 142.2° | 40.41970,-3.50967 |
| 18L/36R:0 | 40.53545,-3.55935 | 359.8° | 40.58036,-3.55954 |
| 18L/36R:1 | 40.49990,-3.55921 | 179.8° | 40.45499,-3.55903 |
| 18R/36L:0 | 40.53320,-3.57484 | 359.8° | 40.57812,-3.57509 |
| 18R/36L:1 | 40.49200,-3.57461 | 179.8° | 40.44708,-3.57437 |

(each corridor's four corners are in the lane's read; 14R/32L:0's ring is
40.49719,-3.55869 / 40.53270,-3.59485 / 40.51070,-3.63220 / 40.47519,-3.59604.)

* **`-6028`'s mouth at 40.51063,-3.56311 is IN** — corridor 14L/32R:0,
  **1,358 m along** its 5,000 and **716 m lateral** of its ±2,000; distance to
  the nearest corridor edge **0.0 m**.  12ae's open question is answered by the
  law: a portal 208 m off the classified surfaces, on the 32R approach, is what
  an arriving aircraft looks at.
* **The two rail mouths at 40.4805,-3.6395 are OUT** — nearest corridor
  14R/32L:0 (the 14R approach side the owner named), 2,720 m along it but
  **4,547 m lateral** of ±2,000: **2,547 m outside the nearest corridor edge**.
  They stay raw DEM, and the §29 round-1 result stands.
* **THE COCKPIT BLOCK'S VIEW TEST, before -> after, on the shipped products**
  (one tree, one parse, the retired disc rebuilt beside the corridor):
  rows that LEAVE "in view" — LEMD **90** of 4,408 (4,318 stay), HECA
  **29,242** of 37,364 (8,122 stay), SPJC **1,450** of 2,180 (730 stay), CYXY
  **0** of 972, OTHH **1** of 1.  Nothing ENTERS view anywhere: the corridor is
  strictly inside the disc.  The buckets barely move, because what the disc
  admitted was mostly under threshold or spanned: the ONLY bucket change on the
  five airports is **HECA CRITICAL VISUAL 1 -> 0** (the 0.531 m
  `vertex_to_edge_step [apron|building]` at 30.1213393,31.4072652, now REPORT
  `beyond_view`); LEMD 22 motion / 5 visual, SPJC 2 / 2, CYXY 0 / 0 and OTHH
  0 / 0 are identical on both readings, and every census TOTAL is unchanged.

**(2) THE BUILD.**  ONE `--engine v2` LEMD build of the change
(`v2approachcorridor`, **362.3 s** wall, rc 0, `status optimal`, body
`b27faf5ce243`, artifact ledger **`cf95ca6d8341`**) against a base arm built at
main `19af2772` (`v2approachcorridor_base`, 350.7 s, body `803760c824e4`,
ledger **`9f6558283155`**).  The named base `3510458499f8` (the §32 clamped
arm) is a DIFFERENT code tree (`57bca3fe…` against main's `ca0ff868…`), so it
was not quoted as the control — but the base built here reproduces its patch
body EXACTLY (`803760c824e4` both), so the two arms are the same surface the
ledger arm carried.  `shared repo UNCHANGED` on both (full before/after
snapshot; 18 lock-churn operations on the base, the allowed class).

* **The structures line**, base -> change:
  `bores 68 (no on-field mouth 35, mouth-only built 12, replaced by objects 2)
  mouths 55 (off-field 76) duals merged 9 object corridors 1 tunnels 29 decks 6
  cells cut 2 refused 118`
  ->
  `bores 68 (no on-field mouth 20, mouth-only built 27, replaced by objects 2)
  mouths 87 (off-field 44, on approach 37 of 8 corridors) duals merged 16
  object corridors 1 tunnels 50 decks 13 cells cut 2 refused 122`.
* **EVERY MOUTH THE CORRIDOR ADDED IS NAMED** (the report's first 12 of 37,
  each with its true distance off the field): `-15327` at 162 m and 171 m,
  **`-6028` at 208 m**, `-5388` at 1,535 / 1,550 m, `-5383` at 1,550 / 1,530 m,
  `-5377` at 1,420 / 1,429 m, `-4928` at 2,237 m, `-4439` at 2,802 / 2,803 m.
  Mouth-only bores BUILT: `-16684, -16683, -15336, -12795, -7847, -5284,
  -4054, -4043, -3829, -6339, -1581, -1568` -> `-16684, -16683, -15336,
  -12795, -7847, -5388, -5383, -5377, -5284, -4928, -4439, -4054` (12 -> 27,
  the first 12 named).  The nearest drops are now 67 / 135 / 141 / 192 / 198 /
  210 / 214 / 220 m off the field AND outside every corridor.
* **THE RAIL MOUTHS DO NOT RETURN.**  Patch bbox lat **40.44976..40.53638 ->
  40.42891..40.53638**, lon **-3.59918..-3.52877 -> -3.60536..-3.50982**; 191
  nodes now stand west of -3.60 (the `-4928` portal at -3,769,-2,518 m), and
  none anywhere near -3.6395.  The patch grows south and east where the new
  portals are: ways **1,144 -> 1,230**, nodes **23,989 -> 25,697**.
* **THE CENSUS, cockpit block first** (harness, both arms, one tree):
  CRITICAL motion **4 -> 2** (the worst goes 0.940 m over 61.71 m `strip_arc
  [primary_parallel|primary_parallel]` at 40.5006629,-3.5740136 -> 0.670 m over
  58.03 m `strip_arc [junction|junction]` at 40.4625636,-3.5525152 — two
  grade-break rows gone with the surfaces the new portals rebuilt), CRITICAL
  visual **0 -> 0**, REPORT **3,605 -> 3,571**.
  LAW-TRUE **3,609 -> 3,573** (-36), ADJUDICATED **1,183 -> 1,143** (-40), and
  the whole delta is GROUNDSIDE: airside 3,557 both, groundside **51 -> 15**.
  By family: `within_shape` 2,832 -> 2,792, `airside_no_step` 428 -> 419,
  `strip_arc` 9 -> 8, `resa_transverse` 2 -> 1, `cross_shape` 1 -> **0**;
  against `taxi_box` 198 -> 204, `transverse` 80 -> 87, `strip_longitudinal`
  13 -> 15, `strip_transverse` 42 -> 43.  Engine verify rows 1,369 -> 1,354,
  with `tunnel_mouth_canonical` 16 -> 26 and `tunnel_deck_clearance` 2 -> 7 —
  the new portals' own rows.

**(3) TWINS** — `tests/auto_patch_v2/test_v2approachcorridor.py` (8): the
corridor is the law beyond each threshold and never back over the runway; an
airport with no runway holds NOTHING (the empty region is empty, not vacuously
true); the schema refuses a zero half-width and one at or over the corridor's
length (the retired disc wearing a corridor's name); a mouth in the corridor
far from the cover is BUILT and counted `mouths_on_approach`; one outside both
is DROPPED and named "outside every approach corridor"; a bore with neither
kind of mouth emits nothing; the engine and the harness read ONE corridor (same
class object, and the apt.dat-threshold rectangle equals the emitted-ring
rectangle within 1 m); and THE RETIRED BUFFER IS GONE (`cockpit_in_view` takes
no radius, no `runway_pts` cloud survives, and a row 4 km ABEAM a runway —
inside the old disc — is `beyond`).  `test_v2mouthgate.py`'s fixture was
amended in the same commit: its off-region ends now run SOUTH, across the
fixture runway's axis instead of along it, because "far from the cover" is no
longer off the region when it stands on an extended centreline — the ruling
working, visible in the twins.  **Suite** `tests/auto_patch_v2 tests/test_harness.py
tests/test_role_edge_census.py tests/test_mesh_sampler*.py tests/test_post_mesh.py
tests/test_object_rebake.py`: **1,214 passed / 1 skipped**, run TWICE (main
`19af2772` collects 1,206 / 1; +8 new).

**NOT DONE, named:** no OTHH / SPJC / HECA / CYXY BUILD under the new gate
(their mouths are read only on the shipped products, where the corridor changes
no bucket but OTHH's 4 OSM mouths and 13 uncovered bores stay unmeasured under
12ab+12al — still owed from 12ae).  No app build, no five-airport sweep, no
merge.  The two arms above were built BEFORE the line-budget extraction that
moved `_under_cover` / the region assembly / the mouth report into
`structure_approach.py` (`structures.py` stood at 999 lines and the additions
crossed the 1,000-line file law); the extraction is textual — the same
expressions, the same `unary_union` — and the CONFIRMING REBUILD on the
committed tree (`v2approachcorridor_x`, 364.2 s, ledger `93c615b05a58`) comes
back **body `b27faf5ce243`, byte-identical** to the arm quoted above, with the
same structures line.

## §30 THE PAD CEILING CARRIES NO AUTHORED RELIEF (Fable 2026-09-12; RULINGS 2026-09-12u) — lane `v2padceiling`

Scout `v2unsettled` reproduced the shipped `v2ramp8` LEMD solve bit-for-bit (142
active-set rounds, `1457/125572`, 1.3037 m) and attributed `HARD SET NOT SETTLED`:
NOT the runway family (8,490 hard rows, clean), NOT convergence (deterministic across
seeds; the cap `polish_rounds_max` 2 is hit but no number of rounds resolves it), NOT
the tunnel ramp (`tunnel_ramp` is `structure = true` and carries no hard row at all —
12k's framing was wrong: its rows were soft targets re-forming with the active set).
It is a MUTUALLY INFEASIBLE PAIR of hard rows on APRON vertices at the T4S block
(40.4952, −3.5904): `pad_relief_offsets` (11j, `relief_radius_m` 12) applies pavement
seniority to the FOOT, not the PAD VERTEX, so an apron vertex on the pad's rim within
12 m of a foot inherits that foot's authored `y` (−2.20 m), and `pads.py:407-408`
puts that `rel` into the 1 % pad-slope CEILING (hard) — a 2.20 m step demanded over
3.0 m of apron, against the 5 % pavement ceiling (hard) allowing 0.15 m. No surface
satisfies both; the augmented Lagrangian splits the difference (1.30 / 1.29 m) and the
surface SHIPS with 725 violated hard rows (`pipeline/build.py:798-806`: the census
reports, never blocks). Control: the same hard set with no object-derived relief
settles to 0.0204 m.

1. **THE CEILING ROW CARRIES NO `rel`.** `pad_slope_ceiling` passes `rel = 0`: "no
   two points of the pad differ by more than 1 % of their separation" — its own
   docstring. The authored relief stays expressed by the `pad_flat` TARGET (weight
   3,000, ten times `law`), where a target belongs.
2. **PAVEMENT SENIORITY IS BY VERTEX**: a pad rim vertex shared with airside
   pavement takes relief offset 0 (extends `pad_relief.py:22-27` from feet to
   vertices) — the second, surgical half.
3. **THE INSTRUMENTS**: (a) `tools/v2_solve_replay.py --capture` omits the pack
   partition / `airport.groups` that `pipeline/build.py:288-318` runs before
   classify, so a replay silently solves a DIFFERENT problem (no foot rows, no
   relief) — the scout's `capture2.py` is folded in; (b) `hard_active` is re-read
   after the runway projection (today it is phase C's multiplier count, 1,457, not
   the 725 violated rows); (c) `_inner`'s `converged` is not asserted while the
   active set still flips thousands of rows per round.
4. **BARS**: ONE `--engine v2` LEMD build against the ledger base — `HARD SET
   SETTLED` (worst hard residual ≤ `hard_tol_m` 0.02 m; today 1.3037), the family
   table quoted (pad ceiling 365 → ~0, pavement ceiling 357 → ~0, runway 3 at the
   bar), the T4S block's apron within 0.05·d everywhere; harness census before/after
   (4,408 law-true on 1.0.321); the foot rows' own residual (the pad_flat target)
   quoted at the same block; `polish_rounds_max` and `hard_weight` untouched
   (refuted levers); twins; suite. Spec §8.3 deviation 16 corrected.

### §30 **MEASURED** (lane `v2padceiling`, 2026-09-12, branch `claude/v2padceiling`, base `ddd3c93f`)

**THE ATTRIBUTION REPRODUCED FIRST.**  Scout `v2unsettled`'s capture replayed on
this branch's tree reproduces the shipped `v2ramp8` solve BIT-FOR-BIT — 142
active-set rounds, `1457/125572`, worst 1.3037 m, `HARD SET NOT SETTLED`, 725
rows over `hard_tol_m` 0.02 (pad ceiling 365 / pavement ceiling 357 / runway 3),
worst row the pair at 40.49522735828, −3.59036487286 with `bound = −2.1700` over
3.0 m of apron.  Every arm below is that ONE capture, one tree, one code version.

**THE TWO HALVES, MATCHED ARMS** (offline, `LEMD2.pkl`, the hard set re-read on
each arm's own solved surface; the T4S column is the worst |Δz|/d over the 66
apron vertices within 80 m of the site, against the 5 % pavement cap):

| arm | hard rows violated | worst hard | pad ceil / pav ceil / runway | T4S apron worst pair | `pad_flat` worst miss at T4S | relief offsets (of which on an airside pavement vertex) |
|---|---|---|---|---|---|---|
| BASE `ddd3c93f` | **725** | **1.3037 m** | 365 / 357 / 3 | **241.15 %** | 1.3337 m | 300 (**220**) |
| §30 (1) alone — the ceiling carries no `rel` | **0** | 0.0171 m | 0 / 0 / 0 | 3.465 % | **2.2194 m** | 300 (220) |
| §30 (2) alone — seniority by vertex | 125 | 1.3620 m | 67 / 48 / 10 | 1.063 % | 0.0224 m | **80 (0)** |
| **both** | **0** | **0.0130 m** | 0 / 0 / 0 | **1.022 %** | **0.0203 m** | 80 (0) |

Each half answers a different thing and NEITHER is redundant.  (1) alone settles
the hard set — no surface is asked for a 2.20 m step any more — but the authored
relief is still written onto APRON vertices as a target, so the apron still tilts
3.47 % under the terminal and the `pad_flat` target misses by 2.22 m at the block
asking for it.  (2) alone takes the relief off the pavement's own vertices (300 →
80 offsets, 220 → 0 on airside pavement) and the block comes right (1.06 %), but
the hard set still does NOT settle: 125 rows at 1.3620 m, because the ceiling
still reads the relief that remains on pad-only vertices ELSEWHERE.  Together:
settled, and the site flat.

**BARS (§30 (4)).**  ONE `--engine v2` LEMD build, foreground, `--tag
v2padceiling30`, **337.5 s** wall, rc 0, `status feasible`, `body_sha
acd834a6ebb5`, artifact ledger **`d8267d91ef6f`**, shared repo UNCHANGED by the
build (full-surface before/after snapshot; 18 lock-churn operations, the allowed
coordination class).  Base arm: the ledger patch `9a4a6b38bb6b`
(`/tmp/harness/LEMD_20260912T114310`), reused, never rebuilt.

1. **MET** — `HARD SET SETTLED`, **0/125572 hard rows violated**, worst
   **0.0130 m** against `hard_tol_m` 0.02 (was 1,457-reported / 725-actual at
   1.3037 m).  The runway projection now has nothing to cut: `0 solved in 0 cut
   round(s)`, `held by the solve (nothing to settle)`, 0.01 s where the base paid
   34.8 s.
2. **MET — the family table** (the sidecar's own `design.families`):

   | family | BASE `9a4a6b38bb6b` | AFTER |
   |---|---|---|
   | hard set | 1,457/125,572 reported (725 violated), **NOT SETTLED**, 1.3037 m | **0/125,572**, **SETTLED**, 0.0130 m |
   | pad-slope ceiling rows violated | 365 | **0** |
   | pavement ceiling rows violated | 357 | **0** |
   | runway rows violated | 3 (at the 0.020 bar) | **0** |
   | target `pavement_ceiling` | 469/97,332 max 1.2907 m | **16/97,332 max 0.0091 m** |
   | target `pads` (`pad_flat`) | 6,376/39,792 max 1.3337 m | 3,713/39,792 max **2.1942 m** |
   | target `pad_level` | 14/28 max 1.819 m | 14/28 max 1.8199 m |
   | target `foot_rows` | 567/1,208 max 3.7919 m | 578/1,208 max 3.7915 m |
   | sidecar `pad_relief` | 300 | **80** |
3. **MET — the T4S block.**  Census rows (`census.py --rows-json`, law-true,
   within 80 m of the site): **236 → 0**.  The base's worst there was an
   `airside_no_step` `apron|apron` pair at **245.78 %** and a `cross_shape`
   `apron|building` pair at 240.31 %; after, the block carries no law-true row at
   all and the worst apron pair reads **1.022 %**, inside 0.05·d everywhere.
4. **MET, with the residual named — the `pad_flat` target at the same block.**
   Published `design_target` rows of family `pads` within 80 m: **418 rows, worst
   1.3337 m → 3 rows, worst 0.0203 m**.  Patch-wide the `pads` target's WORST miss
   RISES 1.3337 → 2.1942 m (at 40.49425, −3.59146, another pad of the same
   terminal block) while its missed rows fall 6,376 → 3,713 and its energy falls
   134,118 → 52,418.  That rise is the law working as ruled: the authored relief
   is now stated ONLY as a target, so where the ground cannot reproduce it the
   miss is REPORTED (§11a (2): the body anchors at its low-side foot and the
   residual is reported) instead of being demanded of the surface as a hard row
   no surface could hold.
5. **MET — the harness census, both arms, one tree, one code version:**

   | census | BASE `9a4a6b38bb6b` | AFTER |
   |---|---|---|
   | LAW-TRUE TOTAL | **4,408** | **3,471** (−937) |
   | ADJUDICATED | **1,859** | **927** (−932) |
   | `within_shape` | 3,407 | 2,737 |
   | `airside_no_step` | 567 | 407 |
   | `taxi_box` / `transverse` / `strip_transverse` | 248 / 90 / 41 | 177 / 79 / 38 |
   | `cross_shape` / `frontage_near_miss` | 8 / 11 | **0** / 4 |
   | `strip_longitudinal` / `strip_arc` / `resa_transverse` / `raoa` | 23 / 7 / 3 / 2 | 16 / 7 / 3 / 2 |
   | `strip_seam_tear` | 1 | 1 |
   | steps (`vertex_to_edge_step` / `mid_edge_step` / terrace joints) | 0 | 0 |
6. **MET** — `polish_rounds_max` and `hard_weight` UNTOUCHED (both refuted as
   levers by the scout); no law-table value changed by this round at all.

**THE INSTRUMENTS (§30 (3)), each with its twin.**

(a) `tools/v2_solve_replay.py --capture` now runs the PACK PARTITION and the
GROUP derivation (`pipeline/build.py:288-318`) before classify, with ONE
`ResourceCache` and the same objects handed to `build_planar` — the scout's
`capture2.py`, folded in, never a second tool.  A capture predating it is
REFUSED BY NAME at replay (`capture_has_groups`), because such a replay solves a
DIFFERENT problem: no `foot_rows`, no `pad_relief` targets, no basin bodies.  The
twin reads BOTH sources and fails if the capture skips a pre-solve stage
`pipeline.build.build` calls.

(b) `DesignReport.hard_active` is re-read AFTER the runway projection as the rows
over `hard_tol_m` on the surface that SHIPS.  LEMD base: reported **1,457**
(phase C's multiplier count), actual **725**.  The line now reads "hard rows
violated", and the twin pins the invariant `hard_settled == (hard_active == 0)`.

(c) `_inner`'s `converged` is asserted only under a SETTLED condition stated once
(`solve.design._settled`): no row changed label, or every row that did sits
within one tolerance band of its own bound (violation ≤ 2·`active_set_tol_m`).
The objective stalling within 1e-6 and the line search buying nothing remain
EXITS — there is nothing better to return — but no longer claim settlement, and
the flip they exit on is reported: `set_flips` / `set_flip_max_m`, on the line as
`SET NOT SETTLED: N rows flipped, worst X m`.  **Measured at LEMD: 240 rows
flipped, worst 0.019 m** — a genuinely unsettled exit that the base reported as
`converged=True`.  CONSEQUENCE, stated plainly: the build's `status` goes
`optimal → feasible` at LEMD.  Nothing gates on the difference
(`pipeline/build.py` accepts both) and the surface is byte-unaffected by the
flag; what changed is that the report stopped claiming a convergence it did not
have.

**Twins.** `tests/auto_patch_v2/test_v2padceiling.py`, 10 tests: the ceiling's
rows carry `rel = 0` over the same pairs at the same caps while `pad_flats`
carries the relief; the ceiling's ruling HEAD still names `[design]
hard_rulings`; a flat-footed body is the identity for both; a pad rim vertex
shared with airside pavement takes no relief while a pad-only vertex still takes
its foot; a GROUNDSIDE neighbour is not senior here (09-01g leaves that vertex
the lot's, and §28 is where a groundside frontage is stated); the capture refusal
predicate; the capture-runs-every-stage source read; and the two solve-report
invariants above.

**Spec §8.3 deviation 16 CORRECTED** in place (it read 0.023 m for LEMD where the
shipped surface violated 725 rows at 1.3037 m — the stale figure was itself a
reading of the mis-reported `hard_active`).

**Tool discipline.** No new tool: `v2_solve_replay.py` extended in place, its
`tools/INDEX.md` row updated in the same commit.  The lane's arm scripts stayed
in the scratchpad (one use each).

**Two consequences of (c), both landed and neither hidden.**  `solve/design.py`
stood EXACTLY at the 1,000-line ceiling `test_model.py` enforces, so the two new
readings are pure functions in `solve/design_report.py` — `settled_flip` (the
settled condition, one derivation) and `DesignReport.read_hard_set` /
`record_flip` — and `design.py` calls them.  The extraction is
behaviour-preserving: the LEMD arm after it reproduces the arm before it
line-for-line (199 rounds, `0/125572`, 0.0130 m, 240 flips at 0.019 m, T4S
1.022 %), so the build's numbers above stand for the committed tree.  And two
`tests/auto_patch_v2/test_v2shapes.py` assertions of `rep.converged` were reading
True off the old stall exit on fixtures whose sets do NOT settle (32 rows still
flipping at 0.031 m); they now assert a SOLVED surface with the flip REPORTED,
with the reason at the assertion.

**Suite** `tests/auto_patch_v2 tests/test_harness.py tests/test_role_edge_census.py
tests/test_mesh_sampler*.py`: **1,062 passed, 1 skipped**, run TWICE, no ERROR
batch (base `ddd3c93f` collects 1,052; +10 new).
## §31 THE COCKPIT FRAME — the reading rule for every bar (owner RULINGS 2026-09-12x/12y)

Owner: "our goal is to increase the realism of a simulated airports terrain so that it
looks believable to a pilot viewing the world from inside an airplane cockpit, so sharp,
unnatural cuts, or rises, things that would effect the airplanes motion are critical,
but centimeter accuracy or anything invisible to the pilot is not important."

1. **TWO THRESHOLDS.** MOTION: on any surface the aircraft rolls on (runway family,
   taxiway family, apron, stands), a step or ridge over `[cockpit] motion_step_m`
   **0.05 m** between welded neighbours, or a grade break the runway/taxi laws
   forbid, is CRITICAL. VISUAL: off those surfaces, a cut, rise, seam, float, burial
   or terrace under `[cockpit] visual_m` **0.5 m** is invisible — reported, never a
   gate; over it, a defect.
2. **TWO RANGES.** TAXI scale inside the airport boundary; APPROACH scale for the
   terrain a pilot sees on final and climb-out: THE APPROACH CORRIDOR — for each
   runway end, `[cockpit] approach_km` (5) beyond the threshold along the extended
   centreline, lateral half-width `[cockpit] approach_half_width_m` (2,000 m; owner
   12al) — a hillside cut there is visible, a 0.5 m terrace is not. The corridor is
   one derivation (`law/tables` or the harness's law-context), read by the cockpit
   block's "in view" test and by §29's mouth gate alike; "within 5 km of a runway
   axis" (the first reading) admitted the whole airport and is retired.
3. **LANDSIDE IS VISUAL ONLY, NATURAL SHAPES**: no cliffs, no floating or buried
   buildings, no torn objects; grade laws there are TARGETS, never gates; terraces
   under the visual threshold are lawful ground.
4. **CENTIMETRES ARE NOT A GOAL.** A bar that prices what the pilot cannot see or feel
   (a 0.3 m tolerance on a landside joint, a census family's count, a plan-stage
   second) is a REPORT. The 0.1 m pad residual of §28 is accepted under this rule.
5. **BUILD BUDGET**: 10 minutes per tile; speed work is dispatched only past it.
6a. **SPANNED IS A SLOPE; A CLIFF IS A CUT** (RULINGS 2026-09-12ad/12af). A
   step-family row whose ends stand more than `emit.instrument.step_contact_tol_m`
   (1 m, the weld spacing) apart is a slope, judged by its cap: REPORT. A grade-
   break row carries no span test. **(7)** A spanned row whose implied grade
   |Δz| / span exceeds `[cockpit] cliff_grade` — a law PATH to `emit.design.bank_slope`
   (1:3, the steepest slope the design surface builds as natural ground; never a
   second copy of the number) — is a CUT or RISE and is judged as if welded: CRITICAL
   VISUAL in view, CRITICAL MOTION on rolled-on pavement. Exactly 1:3 is the bank.
6. **THE INSTRUMENT** (lane `v2cockpit`): `tools/harness/census.py` and the placement
   census print a COCKPIT block from the existing families — CRITICAL motion rows
   (step families and grade breaks on rolled-on roles over 0.05 m), CRITICAL visual
   rows (cuts/rises/seams/floats over 0.5 m inside the boundary or the approach
   corridor), and REPORT (all else) — with the worst of each named by coordinate.
   No new measurement; a classification of what the families already carry. Every
   spec's MEASURED block from now on quotes the cockpit block first.

### 31.2 **MEASURED — THE APPROACH CORRIDOR REPLACES THE 5 km DISC** (lane `v2approachcorridor`; owner RULINGS 2026-09-12al)

The corridor of §31 (2) is ONE derivation, `law/approach_corridor.ApproachCorridor`,
read by the cockpit block's "in view" test and by §29 (1)'s mouth gate through the
same class; the numbers are `[cockpit] approach_km` (5) and the new
`[cockpit] approach_half_width_m` (2,000 m).  `cockpit_law` publishes both, the
block's frame line prints the corridor rather than a radius and states how many
corridors it ran with (a patch with NO runway geometry says so instead of
falling back to something), and `cockpit_in_view` no longer takes a radius
argument at all.

**WHAT THE DISC WAS ADMITTING** (the shipped products of 1.0.323, one tree, one
parse per airport, the retired reading rebuilt beside the corridor):

| airport | census rows | in view under the DISC | in view under the CORRIDOR | leave | enter |
|---|---|---|---|---|---|
| LEMD | 4,408 | 4,408 | 4,318 | **90** | 0 |
| HECA | 37,364 | 37,364 | 8,122 | **29,242** | 0 |
| SPJC | 2,180 | 2,180 | 730 | **1,450** | 0 |
| CYXY | 972 | 972 | 972 | 0 | 0 |
| OTHH | 1 | 1 | 0 | **1** | 0 |

The disc admitted EVERY located row at all five airports — 5 km around every
runway vertex is the airport and its whole neighbourhood — which is exactly why
it discriminated nothing.  The corridor keeps between 0 % (OTHH's single row)
and 100 % (CYXY, a small field entirely under its own approaches) of them.

**WHAT IT CHANGES IN THE BUCKETS: one row.**  HECA's CRITICAL VISUAL
**1 -> 0** — the 0.531 m `vertex_to_edge_step [apron|building]` at
30.1213393,31.4072652, which the disc called `approach` and the corridor leaves
`beyond_view` (REPORT 37,224 -> 37,225).  LEMD (22 motion / 5 visual), SPJC
(2 / 2), CYXY (0 / 0) and OTHH (0 / 0) read identically under both, and no
census total moves anywhere.  The rows the corridor drops from view are the
landside tail §31 (3) already calls targets: HECA's biggest are `within_shape`
readings of 16.1–16.4 m standing 719–740 m outside the nearest corridor, and
SPJC's are 5.5–6.0 m `within_shape` rows 8–279 m outside one.

**Twins** `tests/auto_patch_v2/test_v2approachcorridor.py` (8, listed in §29.1)
plus `tests/test_harness.py` §7, whose synthetic §31 (2) frame now carries a
real runway AXIS and builds its corridor with the shipped class instead of a
runway POINT with a radius.

## §32 THE ZONE BAND IS PROJECTED, LIKE THE RUNWAY (Fable 2026-09-12; RULINGS 2026-09-12ag) — lane `v2zoneclamp`

The cockpit block's first find (12ad): `strip_seam_tear` 8.270 m over 3.007 m at LEMD.
Scout `v2striptear`: the census coordinate (40.4609988, −3.5417888) is a ring
CENTROID 220 m from the pair — seam-tear rows carry no lat/lon (`check_grade.py:
9576-9589` fallback). The pair is at **40.4609867, −3.5443920**: node −12917 of
`adjacent_ground:taxi:E:zone2#65` (shape 474) at **569.75** against node −12474 of
`adjacent_ground:taxi:E:zone1#79` (shape 463, the pavement-welded lip of junction
`pav157`) at **578.02** — the 3.01 m IS `lip_width_m`. The DEM there reads 574.5–577
(a hollow at 570 is 20–30 m SSW). Triangulated: an inverted cone ~8 m deep, 40–90 m
across, apex 3 m from taxiway E's edge, 486 m beside runway 14R/32L. It persists on
the post-§29 and post-§30 arms (569.76 / 578.01) — live in 1.0.322.

Mechanism: the governing row exists — `constraints/zones.py:394-470` `zone_bands`,
ONE-WAY (`follows=v`), bound 0.09–0.15 m below the lip — and the design solve MISSED
it by 8.1195 m (the sidecar's worst `zones` miss; `foot_rows` 28 misses to 3.79 m and
`junction_mesh` 1.81 m at the same vertex, the airport's worst of each). Only the
RUNWAY family is projected onto its rows after the solve (`solve/project.py`, §16 /
09y); every other family is a 300-weight quadratic that can ship an 8 m residual.
Putting zone rows in the HARD set was REFUTED (KCLT/CYXY/SPJC/OTHH went infeasible —
`zones.py` docstrings): do not retry. Class: `strip_seam_tear` is the tail of the
`zones` miss distribution — LEMD 8.12 m → 1 row, SPJC 1.565 m → 2 rows (the same
zone1/zone2 vertex class at −12.0312738, −77.1071535), HECA 0.849 → 0.

1. **THE ADJACENT-GROUND ZONE BAND IS PROJECTED AFTER THE SOLVE**, the way the runway
   family is: per vertex, one-way, its feet are pavement vertices already fixed —
   a pure clamp of one ground vertex into `[lo, hi]` of its own band, no LP. Order:
   after the runway projection, before emit. At LEMD the pit vertex 569.75 → 577.87
   (smoother than what shipped: neighbours 578.03 / 575.78).
2. **CONSUMER CENSUS at spec time (08-30l)**: the vertices moved are zone-1/zone-2
   ground vertices; readers — the bank annulus (`bank_foot` rings, the 1:3 bank the
   emit builds from the ring's normal), `foot_rows` targets at the same vertices,
   `no_step` / `junction_mesh` rows that name them, the mesh's INTERP_ALT reading,
   `verify/steps` and the harness step families. The lane rules each in one table
   before editing; the bank must carry the drop the clamp restores.
3. **THE INSTRUMENT**: `_check_strip_seam_tears` (`check_grade.py:4844-4864`) carries
   the pair MIDPOINT as the row's lat/lon, exactly as `_check_airside_no_step` does
   (`:3970-3971`); the engine verify's identical row (`lat: null`) likewise. The
   cockpit block must send the owner to the defect, not 220 m away.
4. **BARS**: ONE `--engine v2` LEMD build against the ledger base (`d8267d91ef6f`,
   the §30 arm): the pit vertex within its band (≤ 0.151 m below the lip), the
   `strip_seam_tear` row gone, LEMD's zone misses (2,182, worst 8.12) at their bound
   by construction (worst quoted), the 16-row site's `airside_no_step` rows re-quoted
   (worst 1.90), `foot_rows` worst at the vertex quoted, the bank annulus and mesh
   counts quoted, the cockpit block first (critical visual expected 1 → 0 at LEMD;
   a cliff check on the whole patch); SPJC's and HECA's zone misses by dry replay
   where the capture exists (no build); census before/after; twins; suite twice.

### 32.5 **MEASURED** (lane `v2zoneclamp`, branch `claude/v2zoneclamp`)

**THE CONSUMER CENSUS (§32 (2)), ruled before any consumer was edited.** The
population is the ROWS' own — the `follows` vertex of a row whose ruling head is
exactly `zones.adjacent_ground` — not the `adjacent_ground:` face refs, which carry
the pavement-welded inner ring. Rulings:

| consumer | reads | ruling |
|---|---|---|
| `zone_bands` / `zone_bounds` (`constraints/zones.py:396`, `law/tables.py:352`) | xy + law only | THE LAW the clamp enforces; one derivation site, untouched |
| `zones.strip_transverse` (`zones.py:472`) | same generator, head `…band_max_down strip tie` | OUT by exact head match: two-way against a runway edge the runway projection just moved. A `startswith` would have swept it in — twinned |
| a detached pad's rim (`zones.py:421-428`) | one band on the nearest rim vertex, the `Flat` carries the level | OUT by COLUMN PURITY: the far rim is ungoverned, so the column is impure. This is the KCLT/CYXY/SPLP/SPJC/OTHH hard-set infeasibility, kept out by construction — twinned |
| a `Flat` straddling pavement (`solve/rows.py:36-44`) | one rigid column | OUT, same test — the runway projection cannot be undone |
| `foot_rows` (`constraints/foot_rows.py:184,371`) | DEM at row time; its rows NAME zone vertices (`graded_strip` is the `"ground"` class) | AFFECTED and MEASURED: this is the clamp's price (below) |
| `no_step` / `airside_no_step` (`constraints/no_step.py:97`) | `airside AND value`; `graded_strip` is `value=false` | NOT AFFECTED — measured identical (428 rows, worst 2.700 m, both arms) |
| `junction_mesh` (`emit.toml:67`, roles `["junction"]`) | junction faces | NOT AFFECTED — measured identical (625 targets, worst 1.824 m) |
| bank annulus / `bank_foot` (`emit/bank.py:558,642`) | the FINAL solved z of the coverage-boundary ring vertex | AFFECTED BY DESIGN — the bank carries the drop the clamp restores; measured below |
| mesh INTERP_ALT (`O4_Airport_Utils.py:1575`, `O4_Mesh_Utils.py:1596`) | a triangle attribute + the emitted `alt_abs` | reaches it only through the patch; no in-process solved z |
| `verify/steps`, `verify/within`, `check_grade` step families | `p.cap("graded_strip")` / `_role_grade_limit` is `None` | NOT AFFECTED — gated out at the cap |
| `verify/strips` (`strip_seam_tear`, `strip_transverse`, `strip_longitudinal`, `strip_arc`, `raoa`) | `sh.z[k]` of strip shapes | THE TARGET FAMILIES — measured below |
| terrace joints (`publication.py:282`), rebake deck datum, `seam_pins` | solved z of joint / ring / seam pairs | joints 4 both arms, max step 0.37 m; LEMD carries `seam_pins=0` |
| emit decimation | — | DOES NOT EXIST on the v2 path (v1's 60 m chord cap is not here) |

**THE MEASUREMENT.** Two LEMD `--engine v2` builds on ONE tree (`d77419b4`), the
harness's own entry, shared corpus, `shared repo UNCHANGED` on both:
`v2zoneclamp32_base` (`850c20b7a882`, 353.4 s) and `v2zoneclamp32`
(`3510458499f8`, 356.7 s). The §30 ledger arm `d8267d91ef6f` is a DIFFERENT tree
(`76dacea3…`, within_shape 392 vs 455 before this change) and its A/B is
cross-tree, so it is not quoted as the control — the lane paid one extra build
rather than quote a confounded delta.

**THE COCKPIT BLOCK FIRST (§31 (6)), base -> clamped:**

* CRITICAL motion **331 -> 331**, worst 2.700 m over 43.19 m `airside_no_step
  [junction|junction]` at 40.4643733, −3.5372944 — the same five rows, unmoved.
* CRITICAL visual **115 -> 114**; the WORST goes **8.250 m over 3.01 m (274 %)
  `strip_seam_tear` -> 2.590 m over 50.93 m (5.1 %) `airside_no_step
  [graded_strip|junction]`**. The 8 m cliff is gone; the new worst is a slope
  12af would file as report.
* REPORT 3165 -> 3164.

**THE BARS (§32 (4)):**

1. **The pit vertex is inside its band.** Node −12917 / v12940 at 40.4609867,
   −3.5443920: **569.761 -> 577.856 m**, its band `[577.855, 577.915]` (foot
   578.005 − `lip_max_down`·`lip_width_m`); zone miss **8.0951 -> 0.0000 m**. Its
   neighbour v13199 570.880 -> 575.418.
2. **The `strip_seam_tear` row is gone**: census family **1 -> 0**, engine verify
   **1 -> 0**, and `adjacent_ground_tear` **1 -> 0** with it.
3. **LEMD's zone misses are at their bound by construction.** Design report
   `zone projection (12ag)`: 10,418 corridor rows over 4,850 ground vertices,
   **4,850 columns clamped (0 impure, 0 fixed)**, 3,317 moved, max move 8.095 m,
   0.05 s, `optimal`. Worst zone miss **8.0951 -> 1.7515 m**, **owned 0.000000** —
   every row whose clamped column has a non-empty band is held EXACTLY. The
   1.7515 m residual is the **48 EMPTY BANDS**: a farther pavement's floor above
   the nearest's ceiling, where the pocket rule states no precedence. Those
   vertices go to the interval midpoint (the value minimising the worst of the
   two rows) and are counted, never adjudicated silently. Worst is at
   40.4872928, −3.5633279, 3.3 km from the site. Family targets **zones 2,055
   (max 8.095) -> 214 (max 1.752)**.
4. **The 16-row site's `airside_no_step`** is unchanged: 428 rows, worst 2.700 m;
   at the site the two `[graded_strip|junction]` rows read 2.590 / 2.510 m in
   both arms.
5. **`foot_rows` worst at the vertex — THE PRICE, REPORTED.** 337 -> **520**
   targets over materiality, worst **3.789 -> 7.071 m**, and the airport's worst
   is AT this site: the pit's triangles carry the feet of bare-ground bodies whose
   fitted level is ~570, and raising the sheet 8 m raises the interpolation under
   them by up to 5.2 m. `residual: diff 7.0713`. The shipped surface's worst HARD
   row likewise 0.0324 -> **0.1365 m** (`structures.building_pad pad_slope_max
   ceiling`), 20 -> 22 hard rows violated; `pavement_ceiling` 3 -> 4 targets,
   0.025 -> 0.036 m. The runway DEFECT families (`runway_transverse`,
   `runway_vertical_curve`) stay **ALL ZERO** and the runway projection's own
   numbers are byte-identical (24,624 rows, worst 0.0279 -> 0.020000, max move
   0.008 m). **DEVIATION FOR THE OWNER, not decided here:** whether an 8 m cliff
   3 m from taxiway E is worth up to 5 m of object-foot residual on the bodies in
   that hollow. The lane's read is yes under §31 (the cliff is on approach and
   over the visual threshold by 16x; a buried body is also §31 (3)) — but the
   placement census is the instrument that would price it and it is NOT run here.
6. **Bank annulus and mesh:** 27 rings banked both arms; 4,536 boundary vertices
   -> **1,980 -> 1,979** foot nodes; daylight **4,291 min / 242 daylighted ->
   4,283 / 250**; bank slope p95 0.408, max 1.256 both. Mesh triangles **37,324
   both**; emit ways 1,144 both, nodes 23,990 -> 23,989.
7. **Census totals (same tree):** LAW-TRUE **3,611 -> 3,609**, ADJUDICATED
   **1,034 -> 1,032**, out-of-scope 2,577 both. By family: `strip_seam_tear`
   −1, `raoa` 3 -> 1, `within_shape` +1; every other family +0.
8. **§32 (3), the instrument.** The census's `strip_seam_tear` row now reads at
   **40.4610002, −3.5443920** — the midpoint of node −12917 (40.4609867) and node
   −12474 (40.4610137). 12ad's coordinate was the ring centroid 220 m away.
   `check_grade._check_strip_seam_tears` takes the node table and sets the pair
   midpoint; `verify/strips.strip_seam_tear` carries `p.ll[vid]`/`p.ll[vid2]`.
   Twinned both sides (`tests/auto_patch_v2/test_v2zoneclamp.py`).

**NOT DONE, named:** SPJC's 1.565 m and HECA's 0.849 m were NOT replayed (no
capture exists and a capture is a 200 s load per airport — the class is the same
zone-vertex tail and the clamp is per-vertex, so it holds there by construction,
but it is unmeasured). The placement / object census was not run, so the
`foot_rows` price is quoted as a design residual and not as buried bodies. No
app build, no sweep, no merge.

### §24 (4)–(6) The ring is the shell's OUTER footprint; the floor follows a ramp (Fable 2026-09-13; RULINGS 2026-09-13g) — lane `v2basinfoot`

Owner (13d item 2): the SE corner still gaps; the NW corner's cut must reach the
midpoint of the north edge so the modeled road ramp is visible rising to apron level.
Scout `v2lemd325b` on the 1.0.325 frame (ring `basin_wall:0@849`, 59 nodes): the gap
is HORIZONTAL — 11 of 59 ring nodes have no wall within 6–15 m (the engine's own
`_rim_open` reports "57 of 69 rim stations beyond 2.0 m of the shells' at-grade
geometry", diagnostic only); at node 1 the design drops 6.7 m one metre inside the ring
and the nearest pit wall tops out 4 m BELOW the apron edge; five `basin_floor_at_
declaration` rows. Cause: `planar/basins.py:356` builds the region from each solid
component's footprint clipped BELOW the local DEM (`obj8.py:765`), exterior only,
rim inset 0.00 (the shell reads 0.00 m thick) — not §24 (1)'s "OUTER wall face at its
top". The same clip drops the road ramp (`Ground-FSX-LEMD85__b2`: 100.5 m, 591.4 →
597.5, 6.1 % mean, reaching apron level at −3.56946 — 11 m from the owner's midpoint)
out of the region as it rises: a 51.9 × 11.0 m notch that the pad `building15` fills at
598.4, burying ~51 m of the ramp, worst 2.92 m; the floor is one depth below the
nearest rim vertex (`constraints/structures.py:588`), never a ramp profile.

4. **THE RING IS THE SHELL'S OUTER FOOTPRINT AT THE TOP OF ITS WALLS** — every
   component of the basin resource(s) incl. its ramp — never the below-DEM clip.
   Trims the SE overhang and keeps the ramp corridor inside the cut in one edit at
   the single derivation site (`basins.py` region + `_rim`).
5. **THE FLOOR FOLLOWS A RAMP**: floor vertices under a ramp corridor (a deck of the
   basin resource climbing from the floor to the rim) take the deck's authored
   elevation minus `floor_clearance_m` per station; elsewhere the one depth stands.
   Bar: deck − design ≥ 0 over the ramp's whole run (today −2.92 m worst); the 5
   declaration rows → 0.
6. **CONSUMER CENSUS at spec time (08-30l)** — one table before editing: the basin
   rows in `constraints/structures.py`, `planar/structures.py`'s `contact_band_m`
   reader, the pad cut (`cuts_pads`, `building_pad.in_basin_sits_at_floor` — the
   `building15` notch), verify's basin families, `pad_level_report`, `airport/
   basin_ring.py`'s arcs (§14a — the SE node-3 straddle resolves once nodes 0/1/4/5
   have wall within the band), the placement census's basin exemption. OTHH: its 10
   basins / 21 carriers have shells with real thickness (0.75–2.5 m) — the planar
   replay is dry-run BEFORE the edit and re-quoted after (rims moved, m); no OTHH
   build. Bars: SE corner wall base within 0.3 m of the ring at every walled node
   and unwalled nodes 11 → 0; the ramp visible (bar in (5)); harness census; ONE
   `--engine v2` LEMD build against the 1.0.325 base; twins; suite.

## §33 THE PACK'S WALL OBJECTS GOVERN THE MOUTH (owner RULINGS 2026-09-13d item 5; Fable 2026-09-13i) — lane `v2wallplate`

Owner: "remember to use object based wall objects provided by the scenery package
when present as a guide for where the tunnel mouth is and what size it is." Scout
`v2lemd325t`: LEMD's pack models its bridges and tunnel walls as THIN PLATES —
`Bridges/Bridge3.obj` 354 × 25 m spanning the whole `-5931` bore, solids 1.03 m tall;
`Bridge2.obj` 168 × 90 m over the two `-6291/-6288` decks, 1.31 m; `Bridge1.obj`
1.50 m — and `[tunnel.object]`'s pre-screen refuses anything under `least_skirt` =
min(`skirt_min_depth_m` 3.0, `edge_wall_min_skirt_m` 1.5) (`tunnel_objects.py:702,
737-742`) and then SUPPRESSES the refusal from every report (`:772-776`, four
prefixes). So the OSM corridor stood alone: item 5's mouth 7.0 m wide (`lanes × 3.5`)
against the object's 25.1 m, 1.08 m off its centre, 83 m inside the object's end;
item 6's mouth floor set from the DEM over the overbridge EMBANKMENT (610.5 vs 605.8
twelve metres away) — a 5.0–5.8 m rim wall and a ramp that descends; item 9's decks
at trench floor + `clearance_m` 5.10 = 603.85 while the apron they must meet is at
606.5 and the road at 605.7+ — nothing ties a terrain deck to its ends.

1. **EVERY REFUSED RESOURCE IS NAMED.** The four suppressed prefixes are gone; the
   structures line and the inventory KML carry every screened resource and its
   verdict.
2. **THE THIN-PLATE WALL CLASS.** A pack object whose plan footprint lies over a
   mapped bore (`tunnel=yes`) or deck (`bridge=yes`) and whose solids span at least
   `[tunnel.object] thin_plate_min_m` (1.0 m) is an AUTHORED CORRIDOR: its plan ring
   gives the corridor's axis, width and portal positions (the object's ends); the
   depth stays `bore_datum_m` for a bore and, for a deck, the deck's top is the
   object's authored top. `source_precedence = ["object", "osm"]` then does what it
   says. Item 5's mouth: 25.1 m wide at the object's north end; item 6's: at its
   south end.
3. **THE MOUTH CREST IS THE ROAD'S GROUND, NOT THE OVERBRIDGE'S.** `crest = "dem"`
   samples the DEM at the mouth node; where that sample stands on an overbridge
   embankment (the DEM within `bore_datum_m` of the mouth rises more than
   `split_tol_m` above the DEM along the approach's first stations), the mouth crest
   reads the approach's ground; the top cap follows the ground per corner.
4. **A TERRAIN DECK IS TIED TO ITS ENDS.** Its datum is the higher of (trench floor +
   `clearance_m`) and the graded surface at its two ends (the apron on one side,
   the road on the other), the ramp beneath yielding downward; an object deck (2)
   hands its authored top directly.
5. **BARS**: item 5's mouth at the object's end, 25.1 m, axis on the object's centre
   (≤ 0.3 m); item 6's mouth wall ≤ `split_tol_m` above the road's ground, the ramp
   climbing monotonically to the DEM; item 9's decks meeting the apron (606.5) and
   the road within 0.3 m at their ends; every refused resource named (182 screened
   → N named); the other 15 LEMD corridors quoted before/after; OTHH's 9 object
   corridors and 43 wall corridors byte-identical (dry planar replay); consumer
   census of the corridor readers first (08-30l); ONE `--engine v2` LEMD build;
   harness census with the cockpit block; twins; suite.

**MEASURED** (lane `v2wallplate`, branch `claude/v2wallplate` off main `1d124ac2`;
ONE tree, the shared corpus.  Synthetic-first: four dry `--stage structures` planar
replays at LEMD and one at OTHH before the single `--engine v2` LEMD build.)

**BASE.**  The dry replay at `1d124ac2` reproduces the shipped 1.0.325 structures
line and the scout's read EXACTLY — `bores 68 (no on-field mouth 20, mouth-only
built 27, replaced by objects 2)  mouths 87 (off-field 44, on approach 37 of 8
corridors)  duals merged 16  object corridors 1 (signatures 28 of 182 resources)
tunnels 50  decks 13  cells cut 2`, 105 named object refusals.

**§33 CONSUMER CENSUS (08-30l), one table, before any consumer was edited.**

| # | Reader | What it reads | Ruled |
|---|---|---|---|
| 1 | `airport/tunnel_objects.read_corridors` | OBJ8 signatures → `Corridor` | **(1)** the four-prefix suppression DELETED; every SCREENED resource named, the never-screened counted (`not_screened`).  The corridor list itself is untouched. |
| 2 | `airport/thin_plates.read_plates` (NEW) | the same placements / cache | **(2)** reads exactly the class `read_corridors` refuses; `taken` = the resources already admitted as corridors, so an object is read ONCE. |
| 3 | `planar/structures.build_structures` | `corridors`, cells | `plates=` is a NEW additive keyword; nothing existing re-ordered. |
| 4 | `planar/structure_approach.mouths()` | bore ends → `Mouth` | unchanged; `apply_plates` runs after it and rewrites `xy` / `inward` / `width_m` / `approach` only. |
| 5 | `field_region_for` (§29 mouth gate) | cover ∪ corridors ⊕ standoff | UNCHANGED and runs FIRST — the gate judges the MAPPED end, never the moved one.  Measured: `mouths_off_field` 44 → 44. |
| 6 | `object_corridor.mouth_covered_by` (05n-3) | mouth xy vs corridor footprints | runs after the move; measured `mouths_replaced_by_object` 5 → 5, `bores_replaced_by_object` 2 → 2 (Bridge4 unaffected). |
| 7 | `object_corridor.object_groups` | corridors → `Group` | untouched: a plate never becomes an object corridor, it governs the OSM mouth. |
| 8 | `planar/structures` ramp geometry (`geometry`, `_pad_hit`, `beyond_strip`) | the mouth's width / inward | reads the plate's width, so ramp, void and cap are the object's 25.1 m. |
| 9 | `planar/structures._ramp_top` | mouth_z, axis | MOVED VERBATIM to `structure_approach.ramp_top` (both files' budget); no behaviour moved — 46 of 50 tunnels byte-identical proves it. |
| 10 | `model/structures.Deck` | `ref/way/s0/s1/ring/datum/z` | **(4)** three NEW optional fields (`end_z`, `end_ref`, `end_xy`), default `()`; every existing constructor and reader unaffected. |
| 11 | `constraints/structures` deck rows | `deck_top` → `Band`; else `Offset(clearance_m)` | **(4)** adds a per-vertex lower `Band` on the ends' profile and an `Offset` to the governed cell at each end.  The object-deck branch untouched. |
| 12 | `constraints/structures` mouth / rim rows | `tn.mouth_z`, `tn.mouth_dem_z`, `wall_path` | **(3)** changes the VALUE only; crest and floor move together, so the rows are unchanged. |
| 13 | `verify/structures.tunnel_mouth_canonical` | cap crest − ramp mouth = `bore_datum_m` | invariant preserved by construction (the cap moves the floor with it). |
| 14 | `verify/structures.tunnel_deck_clearance` | min(deck) − max(ramp) ≥ `clearance_m` | a LIFTED deck can only increase clearance — never a new row. |
| 15 | `emit/osm_adapter` sidecar `road_bridge_decks` | always empty in v2 | unchanged. |
| 16 | `pipeline/publication.tunnel_objects` | `tn.source != "osm"` | unchanged — a plate mouth stays `source = "osm"` (it IS an OSM bore; the object only placed its mouth). |
| 17 | `pipeline/build` structures line | stats | **(1)/(2)/(3)** `N not screened`, `thin plates N`, `plate mouths N`, `crest from approach N`, one named line each. |
| 18 | `planar/__main__ --stage structures` + `--kml` | the records | **(1)/(2)** `plates`, `plate_refused`, `plate_stats`, `plate_mouths`, `crest_from_approach`; a KML folder for each, plus `tunnel objects refused`. |
| 19 | `airport/rebake_plan` / `emit/rebake` | `ATTR_hard_deck` objects | untouched: a thin plate is not a hard deck and is not in `pm.structures`, so nothing re-seats it (see the OWED note below). |
| 20 | `planar/basins.object_decks` | `o.hard_deck` / `o.deck_top_z` | untouched. |
| 21 | `airport/deck_signature` | `is_bridge_way` / `is_tunnel_way` | reused UNCHANGED by the plate reader — one predicate, never a second. |
| 22 | `planar/zones`, `constraints/{zones,strips}` | `retaining_wall` faces | no new role, no new ref. |
| 23 | `tools/check_grade` `LAW_FAMILIES` | the emitted roles | no new role and no new ref ⇒ no family change. |

**(1) EVERY SCREENED RESOURCE IS NAMED.**  LEMD: **105 → 184** named object refusals
over the **182** screened resources (79 verdicts that no report had ever printed —
`no wall skirt` 40, `no genuine solid` / `no crest plate` / `a stub` the rest), plus
1 named thin-plate refusal.  `Bridge3.obj` and `Bridge2.obj` are among them: they had
been refused SILENTLY for having no skirt.

**(2) THE THIN-PLATE WALL CLASS.**  The class is the GAP the wall pre-screen leaves —
solids spanning `thin_plate_min_m` (1.0) up to `least_skirt` (1.5) — over a mapped
way, with the bore run measured ALONG the plate's own axis.  Both gates were found by
measurement: without the ceiling the class read **112 "plates" at LEMD**, a
1,035 × 557 m cargo terminal spanning 37 m among them; without the along-axis test a
750 × 89 m ground slab (`STRT4.obj`) claimed seven bores that merely CROSS its 89 m
width, and took bore `-9263`'s mouths to an 88.6 m wide ramp.  With both: **4 screened,
3 plates (1 bore, 2 deck), 1 refused by name**, 4 ms.

* `wall-plate:Bridge3.obj@0` — **354.2 × 25.1 m**, solids 1.03 m, over **223.7 m of
  bore `-5931` along its axis**.  Ends 40.4987906,−3.5849926 (north) and
  40.4956006,−3.5849914 (south).
* `wall-plate:Bridge2.obj@0` — 167.9 × 89.6 m, 1.31 m, over 84.3 m of bridge way
  `-6288`; and `LEMD50.obj@0` 155.3 × 33.7 m over `-6291` + `-6288`.
* refused: `Bridge1.obj` — its longest bore run along its axis is under
  `hull_min_length_m` (it clips `-15327` for 8.2 m of 2,234); named.

**The axis is the OBJECT'S OWN BOX, not the plan hull's rectangle.**  `minimum_
rotated_rectangle` minimises AREA, so Bridge3's tapered hull read **354.2 × 20.2 m**
on an axis off the object's centre; the authored box reads **354.2 × 25.1 m** — the
owner's number.

**BAR 5 — item 5's mouth.**  `tunnel:-5931@0`: mouth 40.4980351,−3.5850028 →
**40.4987906,−3.5849926** (the object's north end, moved **83.9 m**), width
**7.0 → 25.1 m**, axis on the object's box centre (0.0 m), ramp top 96 → 204 m,
mouth floor 598.73 → 599.18.  `tunnel:-5931@1` moved 46.6 m to the object's south end.

**(3) THE MOUTH CREST IS THE ROAD'S GROUND.**  Read as a CAP rather than a switch —
`crest = min(DEM(mouth), approach_ground + bore_datum_m)`, biting only past
`split_tol_m`, where `approach_ground` is the median DEM over the approach's stations
from `bore_datum_m` out to 4 × it.  **DEVIATION, flagged for Fable review**: the
clause's literal form ("the DEM within `bore_datum_m` of the mouth rises more than
`split_tol_m` above the DEM along the approach's first stations") fires on EVERY
ordinary portal — a portal's cover stands above the road it lets out onto by
construction (measured LEMD `-5931`'s NORTH mouth: 603.83 at the cap against 602.51 on
the approach, +1.32 m, and nothing wrong with it).  The cap form fires only where the
sample cannot be the portal's cover.  **Two mouths at LEMD**:
`tunnel:-15327+-5980@0` 582.68 → 580.74 (7.05 m over its approach's 575.64) and
`tunnel:-6028@1` 584.91 → 584.32 (5.69 m over 579.22).

**BAR 6 — item 6's mouth.**  `tunnel:-5931@1`, the DEM sample that stood on the
overbridge embankment: mouth ground **610.23 → 607.01**, floor **605.13 → 601.91**,
ramp **36 → 144 m**.  The site is fixed by clause (2) (the mouth moved off the
embankment to the object's end), not by clause (3) — the cap did not need to fire
there once the mouth stood where the object says.

**(4) A TERRAIN DECK IS TIED TO ITS ENDS.**  The record now carries the ground and the
governed cell at the mapped way's two ends; the generator bounds every deck vertex
below at the higher of (trench floor + `clearance_m`) and the ENDS' PROFILE
interpolated over the way's chord, and ties each end to the governed cell's own solved
value where one stands there.  A single flat datum at "the higher of" the two ends was
MEASURED and rejected: LEMD `-6288`'s ends read 609.99 (west road) and 606.10 (east,
beside the apron), so one datum would stand 3.5 m over the apron the owner asked it to
meet.  Trench floor + clearance at that site is 604.12 and the shipped decks emitted at
**603.81–603.85**.

**DRY PLANAR REPLAY, LEMD, base vs ruled (one tree).**  `bores 68 / no on-field mouth
20 / mouth-only 27 / mouths 87 / off-field 44 / on approach 37 / duals 16 / object
corridors 1 / tunnels 50 / decks 13 / cells cut 2 / bores replaced 2 / mouths replaced
5` — **every count identical**.  Per tunnel: **46 of 50 byte-identical**; the four that
move are `-5931@0`, `-5931@1` (clause 2) and `-15327+-5980@0`, `-6028@1` (clause 3).


**OTHH, DRY PLANAR REPLAY (no build).**  `corridors 9  wall corridors 73  tunnels
37  object corridors 9  bores replaced by object 8  mouths replaced 16  decks 0
object decks 1`, and **`plate mouths 0`, `crest from approach 0`** — the two code
paths that can move OTHH geometry never fire there.  Its only plates are two 78.7 ×
18.7 m bridge decks (`OTHH_Bridge_04/05_LOD0_004.obj`, 1.06 m), both DRAPED, so they
state no datum and change nothing; `not_screened` counts 1,103 library resources the
06f gate skips before reading.  `read_corridors` builds the same corridor list it
always did (only its refusal REPORTING changed) and `read_wall_corridors` is
untouched, so the 9 object corridors and the wall-corridor set are unchanged by
construction and by measurement alike.

**THE CLOSING TEST — ONE `--engine v2` LEMD BUILD** (`LEMD_20260913T085100`, artifact
ledger `024bfdf4297b`, body `4e2c8b856dbe`, **355 s, status optimal**, ways 1,229 /
nodes 25,776, v2-verify rows 1,372; shared repo UNCHANGED).  Base = the owner's
1.0.325 products.  Harness census, cockpit block first:

* **CRITICAL motion 2 → 1** (the survivor a forbidden grade break, `strip_arc` 0.610 m
  over 58 m at 40.4625636,−3.5525152); **CRITICAL visual 0 → 0**.
* law-true **3,573 → 3,588** (+15), adjudicated **1,143 → 1,178** (+35, verdict FAIL
  both sides).  The rise is groundside: `groundside 15 → 34`.
* structures line: `... object corridors 1 (signatures 28 of 182 resources screened,
  213 not screened, thin plates 3, merged 0)  plate mouths 2  crest from approach 2
  ... tunnels 50  decks 13  cells cut 2  refused 201`.

**BARS (5).**

* **item 5 — MET.**  The mouth stands at the object's north end
  **40.4987906,−3.5849926** (moved **83.9 m**), **25.1 m** wide, axis on the object's
  own box centre (**0.0 m**, against the OSM mouth's 1.08 m).  Emitted: ramp way
  −10962 (39 nodes) at 599.19 under a rim at 604.28 — exactly `bore_datum_m` 5.10.
  Nothing is emitted within 19 m of the owner's coordinate any more: the portal moved
  to where the object says it is.
* **item 6 — MET.**  `tunnel:-5931@1`: mouth ground **610.23 → 607.01**, floor
  **605.13 → 601.91**, ramp **36 → 144 m**.  The emitted ramp climbs MONOTONICALLY
  601.05 → 609.76 and reaches the DEM at its top (z − DEM −0.99 … +0.01 over the last
  three stations) instead of being clipped into a cliff; the mouth rim stands 603.91
  against the DEM 604.15 at the mouth — **0.24 m ≤ `split_tol_m` 0.3**.
* **item 9 — MISSED, and the residual is quoted.**  The decks are no longer too low:
  `bridge_deck:-6291` **603.81 → 608.74** and `bridge_deck:-6288` **603.83 → 608.63**
  against the apron `pav92` at **606.60** — from **2.77 m BELOW** the apron to
  **2.03–2.14 m ABOVE** it.  The WEST end is met (the decks reach 609.28 / 609.31
  against the emitted ground 608.16 there, 1.1 m); the EAST end is not.
  **ATTRIBUTED**: (a) the deck FACE is clipped to the corridor, so its east edge
  stands **19.2 m short** of the mapped way's east end, where the profile between the
  ends still reads 608.3; (b) the end value is the **DEM at the way's end** (606.10),
  and the apron's own SOLVED value is 606.60 — the `end_ref` cell lookup finds no
  governed cell AT the end point (the nearest apron node is 13.4 m away), so the
  relational tie never arms.  **ROUND 2 REFUTED** (a second LEMD build,
  `LEMD_20260913T090145`, ledger `66cd3ef96192`): making the profile span the deck
  FACE's extent moved the east edge the WRONG way (608.26 → **608.81**), cost 149
  verify rows (1,372 → 1,521, `road_cross_section` 22 → 72) and dropped the solve from
  **optimal to feasible** — the deck ring's vertices ARE the corridor RIM's (one node
  carries both ways), so the deck cannot move without the rim.  Reverted and recorded
  beside the law.  **OWED**: the rim/deck vertex coupling, and whether the end's
  ground should be read by walking the mapped road to the first governed cell
  (§34 (1)'s route reading) rather than at the way's own end.
* **every refused resource named — MET.**  182 screened → **184** named object
  refusals plus 1 named plate refusal; 213 never-screened resources counted.
* **the other LEMD corridors — MET.**  46 of 50 tunnels byte-identical; the 4 that
  move are the two the owner named and the two the crest cap corrects.
* **OTHH byte-identical — MET** (dry read above).
* Twins `tests/auto_patch_v2/test_v2wallplate.py` (9, one per clause plus the class's
  two gates).  Suite `tests/auto_patch_v2 tests/test_harness.py` **1,116 passed / 1
  skipped**, run TWICE.  Targeted v1 tunnel / bridge / portal / object set: 1,333
  passed, 11 skipped, **3 pre-existing reds** (`test_tunnel_portal_fidelity::
  TestClearanceAnnulus` — 12p's standing red — plus `test_object_anchor::
  test_kclt_eight_bake_pool_end_to_end` and `test_tunnel_ramp_run_merge::
  TestItIsNotAPostPass`; this lane touches no v1 file).

**OWED / NOT DONE.**  (i) `Bridge2.obj` and `LEMD50.obj` are DECK plates over the
item-9 bridge ways, and §33 (2)'s deck clause ("the deck's top is the object's
authored top") could not be applied: both are plain `OBJECT` placements DRAPED on the
solved surface, so their authored top (Bridge2: +1.310 m over an `anchor_z` of 608.36,
the DEM at the placement) is an OFFSET, not a datum — an absolute top exists only for
an `OBJECT_MSL` placement or a hard deck.  They are read, recorded and named with that
verdict, and the owner OWES a reading of whether a draped plate should instead be
RE-SEATED onto the deck the ends give it.  (ii) §33 (3) is implemented as a CAP rather
than the clause's literal trigger — flagged above for Fable review.  (iii) item 9's
bar is missed; the two candidate refinements are named above and neither was attempted
a third time (the attempt cap).

## §34 RAMPS FOLLOW THEIR ROUTE; ZONES YIELD TO ROADS; A BRIDGE STATES THE CROSSING (Fable 2026-09-13i) — lane `v2rampwalk`, after `v2wallplate`

Scout `v2lemd325t`, items 1, 7, 8: (7a) `_ramp_top` prices a curved approach by the
straight CHORD from the mouth (`planar/structures.py:225-226`), so a ramp whose DEM
condition is met at 271 m runs 420 m of axis (12 of 59 LEMD ramps have axis/chord >
1.3; worst 3.85); and `approach()` tests direction only on the first hop and then
takes the first candidate way at each node (`structure_approach.py:225-233`) — 7a's
second hop turned 90° onto an unrelated road. (7b) the mapped 180° hairpin `-5958`
exists; the ramp stops at 36 m because the DEM there is only 1.9 m above the floor,
then sawtooths (`constraints/structures.py:10-16` bounds consecutive stations by a
`Diff` only). (8) `planar/zones.py:74-78` subtracts CELLS from the zone band; an OSM
road with no cell is never subtracted, and §19's road rule is gated on a crest
(`terrain_edge.py:180-181`) — a 1.73 m step over 1.5 m inside `zone2#2` that no family
prices (`graded_strip` cap None; `adjacent_ground_tear` empty on v2). (1) no bore: the
roads under taxiway bridge F-6 (`aeroway=taxiway bridge=yes layer=1`, OSM −1230) carry
no `tunnel` tag; the DEM's 7.5 m cutting is unmodelled; the taxi surface bathtubs
2.66 m at 5.3 % across it.

1. **A RAMP IS PRICED ALONG ITS ROUTE.** `_ramp_top`'s reach and climb tests read the
   axis length walked, never the chord; the ramp ends at the first station where
   the DEM condition holds ALONG the route.
2. **THE APPROACH WALK KEEPS ITS HEADING.** After the first hop, the walk prefers the
   continuation with the smallest turn and refuses a turn over `[tunnel]
   approach_turn_max_deg` (60) unless the mapped way itself turns (a hairpin's own
   nodes turn gradually); the route stays on the way it entered until that way ends.
3. **A RAMP CLIMBS MONOTONICALLY** from the mouth to its top: the design profile is
   monotone (a one-way `Diff` ≥ 0 per station toward the top) at ≤ the cap.
4. **ZONES YIELD TO ROADS.** The zone band subtracts mapped road ribbons (OSM highway
   ways ⊕ `groundside_cutback_m`) at the single zone derivation site whether or not
   a cell exists; §19's rule 2 runs without a crest. `adjacent_ground:*` faces get a
   within-face step reading in the cockpit block (a welded step > 0.5 m is critical
   visual).
5. **A BRIDGE STATES THE CROSSING.** A road passing under an `aeroway=*` way tagged
   `bridge=yes` (`layer ≥ 1`) seeds an UNDERPASS: the aeroway is a terrain deck at the
   taxi surface (level across the cutting under taxi law), the road a bore with
   mouths and ramps where it leaves the deck's footprint (§29's gate applies).
6. **BARS**: 7a ends at 40.4947925, −3.5817713 ± 15 m at the DEM; 7b runs the hairpin
   and ends near 40.4938154, −3.5817946 at the DEM; item 8's zone face ends at the
   road ribbon (the 1.73 m step gone); item 1's taxiway level across F-6 (the 2.66 m
   bathtub gone) with mouths and ramps either side; axis/chord > 1.3 ramps 12 → 0;
   the other ramps quoted; ONE `--engine v2` LEMD build; census; twins; suite.

### 34.5 **MEASURED** (lane `v2rampwalk`, branch `claude/v2rampwalk` off main `c55141cf`)

ONE tree, one corpus.  Arms, both `--engine v2` LEMD through
`tools/harness/build_airport.py`: **BASE** = main `c55141cf`
(`--base-arm`, artifact `bdeaf64f86bb`, body `4e2c8b856dbe`, 400.0 s,
`status optimal`, verify 1,372) and the **LANE** tree (artifact
`e87162aa889b`, body `fefe03c84963`, 432.8 s, `status feasible`, verify
1,180).  A third, intermediate arm with §34 (5) ARMED is quoted under (5)
(`f4cf494dab92`, body `5e1f083560ab`, 443.8 s).  Dry planar replays
throughout (`planar --stage structures`, `tools/v2_solve_replay.py`
capture 279 s + ~50 s per arm).

**(1) A RAMP IS PRICED ALONG ITS ROUTE — LANDED.**  `ramp_top`'s chord
term is deleted; the reach is the axis walked.  LEMD dry replay: 38 of
49 ramps shorten, total ramp axis **6,158 → 4,658 m (−24 %)**; **axis/chord
> 1.3: 2 → 1** (my instrument counts 2 at base over the 50 tunnel
records, where the scout counted 12 of 59 over the emitted ramp FACES —
two populations, both quoted).  **7a `tunnel:-15327@0`: 420 → 144 m of
axis** (mouth 40.4947815, −3.5829176; top 40.4955757, −3.5823827, at the
DEM 607.50).  **BAR MISSED, and the bar is the thing that moved**: §34 (6)
puts 7a's end at 40.4947925, −3.5817713 ± 15 m, which is the far end of
way −5913 at s = 264 — the ruled mechanism ends the ramp at s = 144,
101 m short of it, because that is the first station where the 8 % climb
from 596.92 meets the DEM ALONG THE ROUTE (607.19 at s = 132 against a
reach of 10.56).  The bar's coordinate was where the DEFECT NODE stood
under the over-long ramp; under (1) no ramp vertex exists there at all.
Ruled tighter than the bar, not looser.

**(2) THE APPROACH WALK KEEPS ITS HEADING — LANDED.**  `[tunnel]
approach_turn_max_deg = 60`, schema'd.  ATTRIBUTION CORRECTION: 7a's
"90° second hop onto −5913's continuation" is not a hop — the walk takes
way −5913 whole (263.9 m, turn 0.4° at the mouth) and the 90° is INSIDE
−5913's own nodes, which §34 (2) exempts by construction.  The clause
DOES bite at 7b: at −5958's far end the old walk took the first candidate
in load order, −15331 at 33.3°, with −15328 at 2.3° beside it.  Corridor
churn from the shorter ramps: 3 bores lost, 2 gained (31h overlap pairs
swapping which side is refused); LEMD tunnels 50 → 49.

**(3) A RAMP CLIMBS MONOTONICALLY — LANDED, WITH A PRICE.**  One one-way
`Offset(hi, lo, 0)` per consecutive station of the climb, sense taken
from the ramp's own ends so a mouth topping BELOW its datum stays
feasible.  LEMD offsets 296 → 690.  THE PRICE, measured on the replay
(one variable, `RW_NO_MONO`): the design solve goes `optimal` →
`feasible` — the active set does not settle inside its round cap (175
rounds, 69 rows flipped, worst 0.010 m); with the monotone rows off, the
same tree solves `optimal`.  And with the profile pressed onto the cap
the emitter has no rounding headroom (12p's flagged class): `within_shape`
2,769 → 3,616, +847 rows, ALL `tunnel_ramp|tunnel_ramp` groundside pairs
at 8.02–8.03 % against the 8.00 % cap, worst |de| 19.02 m at
40.47968, −3.58206.  They are out of scope (groundside, priced at the
cap's own noise), and the ADJUDICATED count still falls — see the census
— but the instrument moves a long way and the solve status is worse.

**(4) ZONES YIELD TO ROADS — LANDED.**  `road_lines` now returns AT-GRADE
centrelines only (a bored or bridged road is not the surface — one
derivation, both consumers); `road_ribbons` grows them by
`road_profile.lane_width_m + groundside_cutback_m` ⊕ the snap; the ribbon
enters `clip_to_terrain_edge` as a BARRIER beside the crest, so the band
ends at it and does not resume beyond it; §19 rule 2 runs with an empty
crest.  RECORDED DEVIATION: §19.2 (2)'s "flush at the road's OUTER edge"
is amended to the INNER edge for a cell-less road — the outer-edge
reading was written for a road that HAS a cell, whose ⊕ cut-back is
subtracted anyway; read literally it leaves the band standing on the
road.  §19's own twin carries the amendment and its reason.  The new
census family `adjacent_ground_step` (§34 (4)'s cockpit reading) is
registered in `LAW_FAMILIES`, in `law/families.toml` (`cockpit = "step"`)
and in the engine's own `verify/strips.adjacent_ground_step`, so the
v1/v2 lockstep twin passes; its floor is `visual_m` AND `cliff_grade` in
ONE step — without the cliff term it counts the lawful hillside drape
(measured CYXY 296 rows).  RESULT: `adjacent_ground_step` **3 → 1** at
LEMD; the base's 1.63 m at 40.4856895, −3.5884014 and its 0.82 m at
40.4609353, −3.5409609 are gone.

**(5) A BRIDGE STATES THE CROSSING — IMPLEMENTED, NOT ARMED; A RULING IS
OWED.**  `planar/structure_underpass.py` (`is_aeroway_bridge`,
`underpass_bores`, `approach_along`) plus `[tunnel] underpass_min_layer`
/ `underpass_min_span_m`.  The predicate had to be LOCAL: the shared
`is_bridge_way` requires `highway` or `railway`, so an aeroway bridge is
invisible to every deck pass — which is exactly why nothing was seeded.
The deck's half-width is read off the taxi CELL the aeroway stands in
(`pavement_half_widths` cannot answer it: its ±2 m centre test asks
whether a pavement TRACES a road, and a junction blob's across-axis
centre is metres off the centreline it contains) — LEMD F-6 reads 7.6 m
where the lanes fallback reads 3.5.  MEASURED with it armed
(`f4cf494dab92`): `underpasses 1`, way −1230's two service roads bored,
31h-merged into ONE ramp, mouths at 40.4610903, −3.5446736 and
40.4612284, −3.5446741, ramps 96 / 84 m, floor 564.90 = DEM(mouth) 570.00
− `bore_datum_m`.  AND THE COCKPIT GOT WORSE: **CRITICAL VISUAL 3 → 10**,
seven of the ten at 40.46100, −3.54455, `strip_seam_tear` **0 → 4** — the
portal RIM takes `DEM(mouth)` = 570.0, the road's ground down in the
cutting, against a taxi surface solving ~573.5 above it, so the abutment
reads as a 3.52 m cliff.  §34 (5)'s other half — "the aeroway is a
terrain deck at the taxi surface, level across the cutting under taxi
law" — has NO DEM source (the DEM carries no bridge): the abutment rim
would have to take the TAXI CELL's own SOLVED value, a new relational
law.  That is an owner/Fable ruling, so the lane stopped at its attempt
cap, unwired the call, and left the module and its twins standing with
the measurement.  KCLT taxiway U (13q item 3) is UNMEASURED: every KCLT
load in a lane worktree is refused by the pack-dump freshness guard
(`airport/load.py:289`, 13q's own chip — the `.dsf.anchor_bak` is newer
than the cached dumps), and `--refresh-data` is not a lane's to run.

**(6) ITEM 9'S DECK END — HALF LANDED, THE RESIDUAL ATTRIBUTED.**
`deck_ends` now takes the nearest governed cell within `[bridge]
deck_end_reach_m` (25 m) when no cell stands under the mapped end, so
LEMD way −6288's east end reads `pav92` (13.3 m away, solved 606.60)
instead of nothing.  IT DOES NOT MOVE THE DECK, and the replay says why:
§33 (4)'s tie is a ONE-WAY lower bound (`Offset(deck, apron, 0)`) and the
deck already stands 2 m ABOVE the apron.  THE RIM/DECK VERTEX COUPLING,
ruled: six of the ten `bridge_deck:-6288` vertices carry the corridor
RIM as well, but the rim's DEM pin is already skipped there — a deck face
is `service_road`, a governed role, so `shared_with_ground` holds and the
DECK's law governs the shared node.  The coupling is therefore NOT what
holds the deck up.  What holds it up is its own end profile: the face
spans t 0.157…0.787 of the way (13.3…66.3 m of 84.3 — it is the CORRIDOR
crossing, and "the deck face reaches the way's end" is REFUSED as
geometry: beyond the trench the road is ordinary ground), and the
interpolated `Band` lo runs 609.29 at the west edge down to 606.93 at the
east, from a WEST end whose DEM is 609.99 — a real embankment the road
really comes off.  The solve leaves the deck at 608.26…609.31, i.e.
1.3–1.7 m ABOVE its own east lo, because nothing pulls it down: the lo is
one-way and the apron tie is one-way.  BAR MISSED (0.3 m of the apron at
the east end): the deck ends 1.66 m above it.  The lever that would meet
it is a two-sided materiality window on the end profile instead of a
lower bound — which §33 (4) ruled out ("a bound, never a pin") and 13r
measured as a regression in its face-extent form; it needs a ruling.

**CENSUS** (harness, law-true, both arms in this tree): TOTAL 3,591 →
4,278; **ADJUDICATED 1,181 → 1,055 (−126)**; out of scope 2,410 → 3,223.
By family: `airside_no_step` 417 → 338, `transverse` 79 → 48, `taxi_box`
235 → 178, `road_cross_section` 22 → 18, `strip_transverse` 39 → 37,
`adjacent_ground_step` 3 → 1, against `within_shape` 2,769 → 3,616 (the
(3) ramp-cap pairs above), `resa_transverse` 1 → 5, `strip_longitudinal`
14 → 19, `plane_gradient` 0 → 3, `mid_edge_step` 0 → 1.

**THE COCKPIT BLOCK.**  CRITICAL MOTION 1 → 2 (both `strip_arc` grade
breaks; worst 0.610 → 0.520 m, the new one 0.400 m over 25.76 m at
40.4597648, −3.5495209).  CRITICAL VISUAL 3 → 2 — but the WORST row is
worse: 1.630 m over 1.5 m → **8.500 m over 12.03 m** at
40.5331907, −3.5748496, and it is (4)'s.  Attributed: at 18R/36L's north
end the ribbon barrier trims `adjacent_ground:runway:4:zone2#21`
(155 nodes, 597.88…609.25) to `#23` (37 nodes, 599.45…607.95,
`o4_edge = "road"`), and the trimmed boundary runs straight down the
slope at the arrangement's own chord cap — one 12.03 m ring edge carrying
8.50 m where the untrimmed face spread the same drop over many.  The
trim's boundary needs densifying below the chord cap on a slope; owed.

**SUITE** `tests/auto_patch_v2` + `tests/test_harness.py`: 1,125 passed,
1 skipped, twice.  The v1 tunnel / bridge / ramp / portal set: 904
passed, the SAME three pre-existing reds 13r named
(`test_tunnel_portal_fidelity::TestClearanceAnnulus`,
`test_object_anchor::test_kclt_eight_bake_pool_end_to_end`,
`test_tunnel_ramp_run_merge::TestItIsNotAPostPass`).  One behaviour-
neutral move to stay under the 1,000-line budget: `StructureStats` out of
`planar/structures.py` into `planar/structure_stats.py`, proved by two
`--stage structures` LEMD replays whose `structures.json` differ only in
their timing fields.

### 34.6 **MEASURED, ROUND 2** (lane `v2rampwalk`, `claude/v2rampwalk` merged onto main `864e7577`)

Arms, both `--engine v2` LEMD, ONE tree, one corpus, the shared-repo guard
clean on both.  **BASE** = main `864e7577` (`--base-arm`, artifact
`439c6493b02c`, body `667e8c2761ed`, 430.5 s, `status optimal`, verify
1,431).  **LANE** = this tree (artifact `6afd79da37d2`, body
`c482e5366f6c`, 449.1 s, **`status optimal`**, verify 1,290).  An
intermediate lane arm — before the round-2 attempt 2 on §33 (4) / §34 (5)
and with the densifier still in — is `1498afa25daa` (body `2411176dea57`,
428.2 s, `feasible`) and is quoted where it isolates a mechanism.

**CENSUS**: TOTAL 3,698 → 4,363; **ADJUDICATED 1,215 → 1,154 (−61)**; out
of scope 2,483 → 3,209.  `taxi_box` 240 → 193, `transverse` 80 → 49,
`airside_no_step` 433 → 408, `strip_transverse` 44 → 37, against
`within_shape` 2,848 → 3,574 and `road_cross_section` 23 → 58.

**COCKPIT, both arms.**  BASE: CRITICAL motion 2 (worst 0.430 m over
58.03 m, `strip_arc` at 40.4625636, −3.5525152), CRITICAL visual 3 (worst
1.720 m over 1.5 m, `adjacent_ground_step` at 40.4856895, −3.5884014).
LANE: CRITICAL **motion 2 → 1** (worst 0.230 m over 66.18 m at
40.4928034, −3.5741300), CRITICAL **visual 3 → 11** (worst 8.490 m over
12.03 m at 40.5331907, −3.5748496; then 5.29 m at 40.4609964, −3.5416344
and 40.4610048, −3.5445453).  The visual regression is (3)'s and (5)'s,
attributed below.

**§34 (6) THE RAMP PROFILE SITS UNDER THE CAP — LANDED, BAR MET.**  Each
ramp pair is priced `cap − hard_tol_m / d`.  `within_shape`
`tunnel_ramp|tunnel_ramp` **20 (base) → 28 (lane)**: round 1's +847 rows
at 8.02–8.03 % against the 8.00 % cap are GONE (the +8 is the two extra
underpass ramps).  And the design solve is back to **`optimal`** — round
1's `optimal → feasible` was the monotone profile pressed onto the cap;
one `hard_tol_m` of headroom settles the active set (208 rounds, no
"SET NOT SETTLED" line).

**§33 (4) A DECK END IS AN EQUALITY — LANDED, BAR MET.**  The end group
takes a two-sided `Offset(deck, pavement, ±split_tol_m)` to the governed
cell `deck_ends` found, and the cell's nearest vertex is now measured
FROM THE WAY'S OWN END, not from the deck polygon (the face is the
corridor crossing and stops 18 m short, so the polygon's nearest apron
vertex stood 33.8 m away on a 470-node apron).  LEMD `bridge_deck:-6288`
east-most vertex **608.25 → 607.65** against the `pav92` vertex 13.4 m
from the way's east end at **607.47**: a gap of **0.18 m**, inside
`split_tol_m` 0.3 (round 1: 1.66 m).  NOTE FOR THE RECORD: the equality
is two-sided, so BOTH ends moved — that apron vertex went 606.60 → 607.47
while the deck came down 0.60 m.  West end 609.28 → 608.84 against its
DEM chord window 609.38 ± 0.3 (0.54 m under it; the west end runs onto an
unclassified road and has no governed cell to tie to).

**§34 (5) THE PORTAL RIM UNDER A DECK — PARTLY LANDED, BAR MISSED.**
`structure_underpass.py` is ARMED; LEMD reports `underpasses 1`, taxiway
F-6 way −1230 (deck half-width 7.6 m read off its own taxi cell, clip
5.5 m), both service roads bored and 31h-merged, `tunnel:-5821+-5820@0/@1`
mouths at the abutments, ramps 96 / 84 m, floor 564.90, and both records
carry the mark `underpass under aeroway -1230`.  TWO cures were built:
(a) the clip is shrunk by the rim stand-off so the corridor's end cap
lands ON the taxi cell, and (b) an underpass rim vertex standing inside a
governed pavement cell takes a two-sided `Offset` (offset 0) to that
cell's nearest vertex instead of `_rim_rows`' DEM pin.  MEASURED: the rim
way at the mouth now runs **570.0…576.07** where the taxi cell `pav157`
is at 576.45 — the shared half took the deck.  THE BAR IS STILL MISSED:
CRITICAL visual at the site is not 0 and `strip_seam_tear` is 2, not 0.
The residual is a DIFFERENT face: the 5.29 m row is
`graded_strip|junction` between `adjacent_ground:taxi:E:zone1#75`
(568.66…575.52), the ADJACENT-GROUND band the corridor cut, and the
taxiway at 576.45 — the zone band beside the trench follows the trench
down.  That is the zone law beside a structure, not the rim's datum, and
it is outside both this clause's text and this lane's attempt cap.

**KCLT ITEM 3 — MEASURED BY REPLAY (no build).**  Main's load cure works:
with `auto_patch.engine_v2.fresh_pack_dump` in the inputs KCLT loads in a
lane worktree.  KCLT carries **124** `aeroway` + `bridge` ways, of which
**3** reach `underpass_min_layer` — the 121 others are JET BRIDGES
(`aeroway=jet_bridge bridge=yes highway=footway`, no `layer`), which the
layer gate excludes by construction.  **Taxiway U, way −1560** (deck
half-width 18.0 m, clip 15.9 m): **2 roads bored**, one of them the
untagged tertiary −13664, mouths at **35.2015761, −80.9403453** and
**35.2018654, −80.9403264** — 21.4 m and 40.2 m inside 13ai's bar
coordinates (35.2013838 / 35.2022266, −80.94041), which mark the bridge's
own ends rather than the abutments the clip puts the mouths at.  Two more
underpasses at KCLT: taxiways −71 and −70 (deck half-widths 6.4 / 5.6 m,
one road each, 8.6 / 6.9 m of bore — just over `underpass_min_span_m`).
No KCLT BUILD was run: the LEMD build is the round's one closing build.

**§34 (4) A TRIMMED BOUNDARY IS DENSIFIED ON A SLOPE — REFUTED AND
DELETED.**  Built as ruled (`visual_m` of DEM change per ring edge, on the
trim's own new edges only): it inserted 402 stations and the 8.50 m row
DID NOT MOVE (8.500 → 8.490).  Attributed on the arm that removed it: the
edge carrying the row is **A 40.5332464, −3.5760707 z 599.45 → B
40.5331383, −3.5760707 z 607.94, 12.03 m apart** on
`adjacent_ground:runway:4:zone2#24`'s ORIGINAL outer ring — the trim
removed the material beside it, it did not create it, and the densifier
deliberately does not insert into a region's own welded edges.  The
`graded_strip|graded_strip` `within_shape` count is **671 without the
densifier and 704 with it** against **0** in the base, so the 671 are the
TRIM's price and only 33 were the densification's.  The builder is
deleted (the comment at the call site and git are its record); the open
question — a trim that follows the contour instead of cutting across it —
is named there and is not this lane's to rule.

**SUITE** `tests/auto_patch_v2` + `tests/test_harness.py`: **1,214 passed,
1 skipped, twice**, after the merge and again at the end.  The v1 tunnel /
bridge / ramp / portal set: 904 passed, the SAME three pre-existing reds
13r named.  Files under the 1,000-line budget throughout
(`structures.py` 953, `structure_approach.py` 898,
`constraints/structures.py` 961, `structure_underpass.py` 261).

### 34.7 **MEASURED, ROUND 3** (lane `v2rampwalk`, `claude/v2rampwalk` merged onto main `f866e8bb`)

§34 (4) NARROWED as ruled: the general road trim is WITHDRAWN (the ribbon
barrier, `road_ribbons`, and §19 rule 2's crest un-gating are deleted;
§19.2 (2) reads at the road's OUTER edge again, as originally ruled), and a
zone band now yields ONLY to a TUNNEL CORRIDOR — `Classification.keepouts`,
the mouth/ramp/trench/underpass outer rings the structure pass publishes —
subtracted with the SAME `groundside_cutback_m ⊕ snap` stand-off a
groundside cell gets, so the band never shares a vertex with the corridor's
rim and the gap terraces against the ramp walls.  §34 (5), §34 (6) and
§33 (4) stand exactly as round 2 landed them.  One derivation site, so
§19.3's consumer table still holds verbatim.

Arms, both `--engine v2` LEMD, one tree, one corpus, shared repo unchanged.
**BASE** = main `f866e8bb` (`--base-arm`, artifact `00ddff5c133a`, body
`667e8c2761ed` — byte-identical to round 2's base, which confirms
`f866e8bb` is docs-only over `864e7577` for LEMD — 418.0 s, `optimal`,
verify 1,431).  **LANE** artifact `0f6002e1aaf2`, body `bf66853f153a`,
444.2 s, **`optimal`**, verify 1,322.

**CENSUS**: TOTAL 3,698 → **3,572 (−126)**; **ADJUDICATED 1,215 → 1,156
(−59)**; out of scope 2,483 → 2,416.  `transverse` 80 → 51, `taxi_box`
240 → 210, `airside_no_step` 433 → 410, `strip_transverse` 44 → 36,
`within_shape` 2,848 → **2,785 (−63)**, `adjacent_ground_step` 3 → 1,
`raoa` 1 → 0, `cross_shape` 1 → 0, against `road_cross_section` 23 → 50.

**THE COCKPIT BLOCK, both arms.**  BASE: CRITICAL motion **2** (worst
0.430 m over 58.03 m, `strip_arc` at 40.4625636, −3.5525152), CRITICAL
visual **3** (worst 1.720 m over 1.5 m at 40.4856895, −3.5884014).
LANE: CRITICAL motion **2** (worst 0.430 → **0.070 m** at the same
`strip_arc`; the second is a NEW 0.060 m welded `frontage_near_miss` step
at 40.4668804, −3.5698264), CRITICAL visual **3 → 1**, worst
**0.560 m over 0.5 m**, `adjacent_ground_step [apron|graded_strip]` at
40.4609843, −3.5450536.

**BARS.**
* CRITICAL visual ≤ 3 — **1** ✅; NO row at 40.5331907, −3.5748496 ✅
  (the 8.49 m edge is back inside `zone2`'s interior, spread as before);
  none at F-6's 40.4609964 / 40.4610048 ✅ — the 5.29 m rows and both
  `strip_seam_tear` rows are GONE (`strip_seam_tear` 0 on both arms).  The
  ONE surviving visual row stands 33 m east of them at 40.4609843,
  −3.5450536 and is 0.560 m over 0.50 m — an apron↔band lip in the
  approach corridor, an order of magnitude under what it replaced.
* `graded_strip|graded_strip` `within_shape` ≤ base + 20 — **0**, against
  0 in the base (round 2: 671) ✅.
* item 8's 1.63 / 1.72 m row at 40.4856895, −3.5884014 — **absent** ✅
  (`adjacent_ground_step` 3 → 1): the road there is AT A TUNNEL, so the
  corridor subtraction is what removes it, which is the ruling's point.
* item 9's deck end ≤ 0.3 — `bridge_deck:-6288` east 608.25 → **607.67**
  against the `pav92` vertex 13.4 m from the way's east end 606.60 →
  607.49: gap 1.65 → **0.18 m** ✅.
* `optimal` — **held** ✅ (both arms).
* 7a / 7b — **held**: `tunnel:-15327@0` top **144 m** (was 420),
  `tunnel:-5980@0` top 36 m; `tunnel_ramp|tunnel_ramp` `within_shape`
  20 → **26**, no cap-riding population ✅.
* KCLT item 3 — **unchanged by replay**: 124 aeroway+bridge ways, 3 at
  `underpass_min_layer` (121 jet bridges), taxiway U −1560 bores 2 roads,
  mouths 35.2015761 / 35.2018654, −80.94034; taxiways −71 and −70 one road
  each.  No KCLT build.
* SUITE `tests/auto_patch_v2` + `tests/test_harness.py`: **1,220 passed, 1
  skipped, twice**.  The v1 tunnel / bridge / ramp / portal set: 860
  passed, the two pre-existing reds 13r named that live in it
  (`test_tunnel_portal_fidelity::TestClearanceAnnulus`,
  `test_tunnel_ramp_run_merge::TestItIsNotAPostPass`).

**WHAT ROUND 3 DID NOT SETTLE.**  `road_cross_section` 23 → 50 (+27) —
groundside road faces re-priced by the corridor stand-off; all out of
scope, none critical.  The new 0.060 m welded motion row at
40.4668804, −3.5698264.  The 0.560 m visual row above.  `road_lines`
keeps round 1's AT-GRADE filter (a `tunnel` / `bridge` way's centreline is
not the surface): it only NARROWS §19 rule 2 and creates no trim.

### §28 (6) A hillside terrace is not a frontage (Fable 2026-09-13; RULINGS 2026-09-13o) — lane `v2frontagestep`

Owner (13l item 1): at CYXY the groundside lots beside two buildings cut into a hill
used to sit a storey above them and are now graded flat. Scout `v2cyxy1t`: §28 (1)'s
`groundside_frontage` row (3,000-weight `pad_flat`) lands at the owner's exact
vertices and outprices the face's own DEM datum (`body_datum` 300) ten to one; the
frontage vertex set (`pad_frontage_gs.py:167-169`) carries NO DEM term. The DEM at the
frontage stands +4.08 / +3.02 m (median per pair) above the pads `building10` /
`building9` — one-plane pads at the downhill apron level over ground that spans 5.5 m
under each ring (2-D DSF facade footprints; no authored split level). BEFORE (the
pre-§28 arm) both faces sat on the DEM, +3.4 m above the pads; NOW +0.10 / −0.01, and
`dsf:pol129` (35 m long, 8 % cap) is a 3.4 m excavation it can never climb out of.

6. **THE BOUND IS PER PAIR.** A pad–frontage pair whose median |DEM(frontage) − pad
   level| exceeds `[lot] frontage_step_max_m` (2.8 m) mints no `groundside_frontage`
   row: the face keeps its own ground and the step is a lawful hillside terrace. Per
   pair, never per vertex (a per-vertex bound saw-tooths S2's 16-vertex frontage).
   Measured medians decide the number: CYXY +4.08 / +3.02 and SPJC's five (+3.20 …
   +4.01) disarm; LEMD's `building4` (+2.66, the case the owner ordered graded in
   11ai/12r), KCLT (+1.95), HECA (+1.02), OTHH (−1.03) stay armed. A 2.0 m bound would
   re-open `building4`. Bars: CYXY's two faces back on the DEM (frontage z − DEM
   within 0.3, +3.4 above the pads); `building4`'s joints unchanged (0.16 m); SPJC's
   five pairs named; the `groundside_frontage` family count before/after; ONE
   `--engine v2` CYXY build (28 s) against the ledger base; twin; suite.

### §28 (6) **MEASURED** (lane `v2frontagestep`, 2026-09-13, branch `claude/v2frontagestep`, base `1be04630`)

**THE QUANTITY CHANGED, AND THAT IS THE DEVIATION** (reported, never decided by
the lane — the §23.3 (2) precedent). 13o's bound is the median DEM step against the
pad's **SOLVED LEVEL**. A constraint generator cannot read it: the pad's level is what
§20's rows PRODUCE, three lag rounds later (LEMD's `building4` sits 0.32 m above its own
terrain once solved, CYXY's `building10` 0.61 m and `building9` 1.51 m). The quantity
implemented is **DEM vs DEM** — the median over the face's frontage vertices of
`dem_z` minus the pad footprint's OWN median `dem_z`, both from `Vertex.dem_z` (the
production DEM taken once at map build; never a second reader). Measured in the
engine's own frame on captured planar maps (`v2_solve_replay --capture`), that is the
WHOLE population of pad–face pairs at the two airports that carry the class:

| airport | pair | DEM-vs-DEM step | 13o's solved-level step | verdict at 3.2 |
|---|---|---|---|---|
| CYXY | `building9` → `pav4` (16 v) | **+3.76** | +3.02 | **DISARM** |
| CYXY | `building10` → `dsf:pol129` (8 v) | **+3.43** | +4.08 | **DISARM** |
| CYXY | `building1` → `pav29` / `pav29#1` | +0.05 / +0.02 | +0.28 / +0.23 | armed |
| LEMD | `building4` → `pav124` (3 v) | **+3.00** | +2.68 | **armed** |
| LEMD | `building4` → `pav124` (12 v) | +2.39 | +1.68 | armed |
| LEMD | `building4` → `route3` / `route6` | +2.03 / +2.00 | +1.69 / +1.68 | armed |
| LEMD | `building12` → `pav70` | +0.00 | −0.33 | armed |

`[design] frontage_step_max_m` **3.2** is the centre of the 3.00–3.43 gap that
population leaves — 2.8 on THIS quantity would disarm `building4`, the case 12r ordered
graded. It is a narrow gap and it is the one the data has; 13o's own margins on the
solved-level quantity (0.12 / 0.22 m) are narrower. The key lives in `emit.toml
[design]` beside `pad_frontage_m`, the radius of the same relation, and NOT in
`classify/rules.toml [lot]` as the brief placed it: `constraints` may not import
`classify` (`test_model.py::test_dependency_direction` enforces the layering by name).

**FRAME WARNING.** An EMITTED-patch read of the same pairs against the raw inset
raster gives +4.72 / +4.54 at CYXY and +3.00 at LEMD — the production DEM is SMOOTHED
(CYXY inset HRDEM 1 m, smoothing radius 1 px) and the planar map carries welded vertices
the patch does not. Quote the frame with the number; the law is written on the engine's.

**BARS.**

1. **MET** — `dsf:pol129` is back on the DEM over its WHOLE extent: z − DEM (engine
   frame, all 23 vertices) median **−3.49 → −0.00** (min −4.16 → −1.27, max −1.43 →
   +1.62); `pav4` (56 vertices) median **−1.35 → +0.05**, vertices off the DEM by more
   than 0.3 m **44 → 15** and **23 → 10**. The 3.4 m excavation an 8 % cap could never
   climb out of is gone.
2. **MET** — the two faces stand back above the pads: `building10` → `dsf:pol129`
   **+0.21 → +3.62** (mean +0.08 → +3.03) and `building9` → `pav4` **+0.21 → +3.35**
   (mean −0.01 → +3.05), read by `role_edge_census.py --pad-frontage --near 3.0`. The
   bar's +3.4 m is met at `dsf:pol129` and missed by 0.05 m at `pav4`, whose own DEM
   step is 3.02.
3. **MET** — no pad moved: `building10` 696.140 and `building9` 695.519 in BOTH arms,
   z − DEM per pad identical (`building10` +0.18 / `building9` +1.07 → +1.06);
   `building1` 704.920 → 704.900.
4. **MET** — `groundside_frontage` rows **58 → 10**, `pairs_held_as_terrace` **0 → 2**
   (the count is published beside the generator's own row count, `constraints.build`).
   Design target `groundside_frontage` **27 rows / max miss 0.214 m → 5 / 0.195 m**.
5. **MET** — harness census, ONE tree, ONE code version, the arms differing only in the
   law value (the BASE arm is the same build with the bound inert):

   | census | BASE `v2frontagestep28` | AFTER `v2frontagestep28b` |
   |---|---|---|
   | LAW-TRUE TOTAL | 1,047 (within 1,047 / cross 0 / steps 0) | **1,014** (1,014 / 0 / 0) |
   | ADJUDICATED | 406 — airside 381 / gs **25** | **374** — airside 368 / gs **6** |
   | `within_shape` / `road_cross_section` / `taxi_box` | 915 / 12 / 34 | 906 / **3** / 31 |
   | `transverse` / `airside_no_step` | 9 / 74 | **5** / **66** |
   | terrace-joint families (route / strip / actual step) | 0 / 0 / 0 | 0 / 0 / 0 |
   | sidecar `terrace_joints` | 1 | 1 |
   | design target `pads` / `roads` / `pad_level` | 55 / 84 / 10 | 8 / 38 / 8 |

   `groundside_ramps` is unchanged in kind — no groundside ramp row appears in either
   census and the joint count is the same 1 (apron/service_road, 0.45 m).

**Closing test** — ONE `--engine v2` CYXY build, foreground, `--tag v2frontagestep28b`,
**13.9 s** wall, rc 0, `status optimal`, `body_sha ea11413f8e5c`, artifact ledger
**`613cc27fedb2`**, shared repo UNCHANGED (full-surface before/after snapshot; 18
lock-churn operations, the allowed coordination class). v2 verify rows 312 → **279**.

**SPJC AND THE 13p CLUE — THE CLUE FAILS, the per-pair bound stands (13o).** The
clue 13p proposes is the PAD RING's own DEM span. Measured: CYXY's two rings span
**5.45 / 4.78 m** (emitted frame) and **4.90 / 4.46 m** (engine frame) — but LEMD's
`building4` ring spans **9.74 m** and `building12`'s **11.96 m**, and SPJC's east
terminal `building102` spans **7.68 m**. Every candidate ring at every airport spans
more than the bound, CYXY's included, so "ring span > bound" adds no discrimination
and would NOT keep SPJC's lot armed. 13p's own fallback applies: "If SPJC's terminal
ring spans a storey too, the clue fails and the per-pair bound stands as ruled".
SPJC's five pairs could NOT be named in the engine's frame: `v2_solve_replay --capture
SPJC` refuses on the pack-dump freshness guard (`--refresh-data airport_mod_cache`,
which a lane may not run — the same guard RULINGS 13q chipped), and the only SPJC
product on disk is a **v1 patch of 2026-07-25**. On it, 13o's own quantity gives no
pair anywhere near +3.20…+4.01: the largest are `building102` −2.71 (ring span 7.68)
and `building14` +2.00 (ring span 1.69), every one of them ARMED under 3.2 — which is
the outcome the owner wants for the east lot. **13o's SPJC numbers do not reproduce on
any frame available to this lane**, and SPJC needs its own build before that half of
the ruling can be measured.

**Twins.** `tests/auto_patch_v2/test_v2frontagestep.py`, 5 tests: a pair over the bound
mints no row and is COUNTED; a pair under it still takes the pad's level; the bound is
PER PAIR and never per vertex (one frontage vertex 10 m over the bound costs no vertex
its row while the pair's median is under it — the same followers in both arms); the
quantity is the planar map's own `dem_z`, frontage median minus pad-footprint median,
and a pair with no DEM never disarms; and the value is the law's, read through the
`[design]` schema. Suite `tests/auto_patch_v2 tests/test_harness.py`: **1,116 passed,

## §35 THE RUNWAY-END CORNER (Fable 2026-09-13; RULINGS 2026-09-13q, KCLT item 1) — lane `v2rwycorner`

Scout `v2kclt1t`: at 36C's end (18C/36C cut 6.44 m into the hill) two graded-strip
nodes 2.8–3.0 m outside the runway's half-width and 14 m beyond its end carry NO law
row — `constraints/zones.py:207-221` `abeam` binds a strip vertex only within the
runway's own extent (s ∈ [0, L]) and `constraints/strips.py:381-382` `_end_foot_rows`
binds only t ∈ [0, 1] along the end edge, whose docstring says such a vertex "keeps
the transverse rows" that `abeam` has just removed. They hold only §23's datum (the
DEM, 3.0) against a runway 6.4 m below: 4.98 m over 4.62 m and 5.07 m over 3.91 m,
the cockpit block's two CRITICAL VISUAL cliffs. Every runway end has four such
corners; §32's clamp cannot reach a vertex with no band.

1. **THE CORNER IS BOUND TO THE NEAREST POINT OF THE END EDGE.** A strip vertex
   beyond a runway end and lateral of its width takes `_end_foot_rows`' chord form
   against the nearest point of the end edge (t clamped to [0, 1]) over its true
   plan distance, under `end_skirt.max_down_grade`; equivalently the end corridor's
   rect is widened laterally by the zone-2 half-width so `abeam` and the chord tile
   the plane with no gap. One derivation, both gates.
2. **BARS**: the two 36C cliffs gone (steps ≤ `end_skirt.max_down_grade` × d); every
   corner of KCLT's 3 runways quoted (12 corners: worst step before/after); LEMD's,
   HECA's, CYXY's, SPJC's, OTHH's corners by dry replay of their frames (no build);
   `strip_seam_tear` 2 → 0 at KCLT; ONE `--engine v2` KCLT build; twin; suite.

### §35 **MEASURED** (lane `v2rwycorner`, 2026-09-13, branch `claude/v2rwycorner`, base `ec8723e9`)

**THE SITE REPRODUCED, on the owner's 1.0.324 KCLT products.** Node **−4762**
(35.1994462, −80.9510241) reads **209.27** m, 4.62 m from runway ring node −4685
at **204.29**; its mirror **−4763** (35.1994823, −80.9504531) reads **209.36**,
3.91 m from −3567 at **204.29** — the census's two `strip_seam_tear` rows,
**4.98 m over 4.62 m** and **5.07 m over 3.91 m**. Both carry
`adjacent_ground:runway:4:zone1#23` and `…:zone2#42` and no runway band: 18C/36C's
half-width fits at 23.6 m and both sit ~2.5 m outside it, 14 m beyond the end.

**THE DERIVATION CHOSEN, and why (§35 (1) gave two).** The CHORD, not a wider
rect: `runway_groups` ALREADY builds the end corridor at
`end_half = max(width, strip_half)` (`strips.py:121-133`), i.e. laterally the
zone-2 half-width (KCLT/FAA 76.2 m, LEMD/ICAO code 4 75 m) — so the corner
vertex is INSIDE `g.rings[end]` already and widening the rect a second time
changes nothing. The whole gap was `_end_foot_rows`' `if t < 0.0 or t > 1.0:
continue`. It now CLAMPS `t` and takes the bound over the TRUE PLAN DISTANCE to
that nearest point; for an abeam vertex the clamp is the identity and the plan
distance is the along-axis distance the old code used. `zones.abeam` is
UNTOUCHED — the lateral law stays the lateral law, and the two tile with no gap
because a vertex farther than the zone-2 half-width from every runway edge has
no band to lose. Twinned shut (`test_the_lateral_law_still_refuses_the_corner`).

**THE AMENDMENT, measured rather than reasoned.** Taking only the nearest end
edge DROPPED every vertex whose nearest (vertex, foot) pair was already in
`seen`, where the pre-§35 loop walked the edges in ring order and stated the
next one: LEMD went **64,902 → 63,668** design rows, a net LOSS of 1,234, and
its verify census **1,354 → 1,596** rows. With the fallback (the nearest edge
states the law; a nearer edge whose pair is already stated yields to the next)
the same arm states **66,660** rows, **+1,758** over base — the corner law added
and nothing lost.

**THE CLOSING TEST DID NOT RUN AT KCLT — REPORTED, NOT WORKED AROUND.**
`build_airport.py KCLT --engine v2` refuses in `airport/load.py:289`:

> KCLT: the pack DSF …/+35-081.dsf.anchor_bak is newer than every cached text
> dump under …/Airport_mod_cache/Nimbus Simulation - KCLT V1.4 - Charlotte XP12
> — the pack's objects would be read from a stale dump… Refresh it explicitly:
> build_airport.py --refresh-data airport_mod_cache

The message's premise is FALSE and the true condition is worth the chip's while:
the anchor_bak is dated **Jul 27 16:35**, OLDER than all three cached dumps, and
the dump of ITS OWN BYTES exists — `text_dump_tag(…anchor_bak)` = **7bf41307**
and `+35-081.dsf.7bf41307.text` (Sep 12 22:10) is in the cache. It is unreachable
only because `find_text_dump` keys the candidate set by the file's BASENAME
prefix (`+35-081.dsf.anchor_bak.`, RULINGS 2026-09-11m) while the dump was
written before the object stage renamed the file. The dump is CONTENT-keyed, so
the prefix is redundant for correctness. Lane-local vs shared root is NOT the
cause here (both cache roots hold identical files); the ruling's `chip` is real
but this is a second, distinct condition. No refresh was run.

**THE SUBSTITUTE ARMS, and their bars.** Two airports, each a true A/B on ONE
tree (base = `ec8723e9`'s `strips.py` in this worktree, `e9f02ed210a9`; arm =
`46c95984a692`), the harness's own entry, shared corpus, `shared repo UNCHANGED`
on every run. Instrument: `tools/runway_end_ground.py --corners ICAO`, promoted
out of this lane's scratchpad on its second use (INDEX row + twin in the same
commit), which reproduces the KCLT site numbers exactly.

1. **CYXY** (13–15 s per arm, `v2rwycorner_cyxy_base` `4a900e21a4df` →
   `v2rwycorner_cyxy2` `55e8e9898359`): the worst corner **0.99 m over 4.46 m
   (excess +0.63) → 0.37 m (excess +0.01)** at 14L/32R end2R; 8 corners, 25
   corner vertices, total over bound **1 → 1** (the same vertex, now AT its
   bound). Solve **optimal** both arms, **HARD SET SETTLED** both, 12,733 rows,
   engine verify **312 → 311**.
2. **LEMD** (`v2rwycorner_lemd_base2` `b27faf5ce243`, 546 s → `v2rwycorner_lemd2`
   `2c73ddc9dcd5`, 488 s): 16 corners, 72 corner vertices. **Worst corner excess
   2.19 m → 0.04 m**; by corner, 18R/36L end1L **6.24 → 4.07 m** (bound 4.05),
   end1R **6.25 → 4.10 m** (bound 4.06), 14R/32L end1L **4.70 → 4.08 m** (bound
   4.06). Total over bound 3 → 3, every residual **0.02–0.04 m** — the end-skirt
   rows are design TARGETS, so this is held-at-its-bound, reported as
   PASS-with-residual and not iterated.

**THE PRICE AT LEMD — A DEVIATION FOR THE OWNER, not decided here.** Census
(`tools/harness/census.py`, both arms this tree): **LAW-TRUE 3,573 → 3,593
(+20)**, **ADJUDICATED 1,143 → 1,199 (+56)**, verdict FAIL both. By family:
`airside_no_step` 419 → 437 (worst 2.670 → 2.700), `taxi_box` 204 → 216,
`strip_arc` 8 → 10, `strip_longitudinal` 15 → 16, `raoa` 1 → 3 (worst **0.020 →
0.680 m**), `cross_shape` 0 → 1, `resa_transverse` 1 → 1 (worst 1.830 → 1.920);
AGAINST it `within_shape` 2,792 → 2,782, `transverse` 87 → 83, `strip_transverse`
43 → 41. `strip_seam_tear`, `runway_end_skirt`, `adjacent_ground_tear`,
`drainage_minimum` and every other family: unchanged. The solve reports
**optimal → feasible**, hard rows violated **2 → 25** of 126,696 (max violation
0.1563 → 0.1288 m). The runway projection is unmoved (24,644 rows, worst hard row
0.020000 both). The lane's read is that a 6.25 m corner cliff on approach is worth
0.02–0.68 m of apron/taxi target residual 3 km away — but `raoa` worst 0.02 →
0.68 m is a RUNWAY-family reading and the owner should price it.

**Twins.** `tests/auto_patch_v2/test_v2rwycorner.py` (7 cases, **3 red on base**):
the corner quadrant exists; every corner vertex carries a row; the row's feet are
the end edge's two ends with weights summing to 1 and its bound is exactly
`cap·d + q`; the 3√2 m diagonal vertex; the falling DEM breaks the new rows (the
fix bites); `abeam` still refuses the corner; the rect is already zone-2 wide; an
abeam vertex is unchanged. `tests/test_runway_end_corners.py` (4 cases) twins the
instrument. TWO EXISTING TWINS MOVED, both named in place:
`test_runway_transverse.py` — §35 moved that fixture's worst edge to EXACTLY
`hard_tol_m` and it read 0.020000000000072793 against 0.02, so the comparison
carries a 1e-9 float epsilon (the tolerance itself is unchanged);
`test_why.py` — the chain trace now ends on a **BAND** rather than FREE
(`reached={'FREE': 16, 'BAND': 1}`), a holder like a pin, so BAND joins the
accepted terminal kinds with its own note asserted. Suite
(`tests/auto_patch_v2 tests/test_harness.py`) **1,114 passed, 1 skipped**, twice.

**NOT DONE, named.** No KCLT build and therefore **no after-numbers for the two
36C cliffs, no KCLT census, no `strip_seam_tear` 2 → 0** — the refusal above.
KCLT's 12 corners are quoted BEFORE only (7 vertices over their bound; worst
5.07 m over 3.91 m against a 0.34 m bound at 18C/36C end2R, then 4.98/4.62,
0.98/4.61, 0.83/4.25, 0.60/4.25). HECA's, SPJC's and OTHH's corners were NOT dry
-replayed: no v2 frame of them exists on this machine (the `dist/` and worktree
`Patches/` copies are v1 — their sidecars carry no `design` key — and the class
is read off the SOLVED surface, so a v1 patch would answer a different question).
An older HECA v2 patch of unknown provenance reads 3 corners over cap (worst
6.27 m over 78.4 m at 05C/23C end2R) and is quoted only as evidence the class is
not KCLT-only. No app build, no five-airport sweep, no merge.

## §36 THE EAT LAW, PORTED (owner RULINGS 2026-09-13j item 2; Fable 2026-09-13q) — lane `v2eat`

Owner: "The EAT here should be lower than the runway by law right?" — YES. v1's law
(`src/auto_patch/grade_law.py:2352 eat_pavement_ceiling`: ceiling(D) = max(0, D −
setback) · slope − tail_height, FAA 40:1 slope 0.025 from the departure end, tail
height by code letter (E 20.1 m), the hard ANCHOR RECT of `eat-anchor-rect-spec.md`,
recognition ≥ 300 m) was never ported: `auto_patch_v2` has no EAT law (zero matches
in `constraints/`, `planar/`, `law/*.toml`). KCLT's 18C end-around crossing at
D 372–416 m stands at runway end +0.9 m where the law puts it at −8.6 … −10.6 m —
the "pre-law, FLAT at end +0.9 m" state the v1 spec named as the thing to fix.

1. **THE EAT ANCHOR RECT IS A HARD PIN FAMILY IN v2**: recognition (a taxiway
   crossing the extended centreline beyond a departure end at ≥ `eat.min_crossing_m`
   300 m, routed wrap), value `end_z + max(0, D − setback) · slope − tail_height`,
   cut-only, ramps at the taxi caps to the pavement either side; the constants in
   `law/rulesets.toml [faa.eat]` / `[icao.eat]` (v1's `config.py:5828/5985-6015/5922`
   values, one copy, v1 asserted equal by a law-tables twin like the ramp cap's).
2. **BARS**: KCLT's crossing at 216.3–217.4 m (today 226.6–226.9); the ramps within the
   taxi caps; the other five airports' EAT recognition quoted (which have one; none
   moves that has none); ONE `--engine v2` KCLT build; census; twins; suite.

### §36 **MEASURED** (lane `v2eat`, 2026-09-13, branch `claude/v2eat`, base `ec8723e9`, sha `0d995474`)

**BELOW BAR ON TWO OF FOUR — the owner's sign-off is owed, the residual is
quoted.**  The site lands; the ramps do not fit the taxi cap, and the hard set
no longer settles.

**THE SITE REPRODUCED FIRST, OFFLINE.**  On scout `v2kclt1t`'s copy of the
shipped KCLT patch the 18C crown-spine end stands at 227.25 m and the crossing
pavement — `cross_connector pav11` (shapeID 104) / `junction pav118` (shapeID
69) — at 226.58–226.91 m, D 367–410 m beyond it: the runway end **+0.9 m**, the
"pre-law, FLAT" state.  The FAA ceiling there (code E tail 20.1 m, slope 0.025,
setback 0) is 216.6–217.1 m, i.e. **−10.1 … −10.7 m** below the end.  Every
offline arm below is ONE `v2_solve_replay` capture of KCLT (82 s; 22,294
vertices, 1,193 faces), one tree, one code version.

**THE CONSUMER CENSUS** (owner ruling RULINGS 2026-08-30l — ruled before any
consumer was edited; the region is "a hard `Pin` on taxi-family / apron
pavement vertices"):

| consumer | what it reads of the region | ruling |
|---|---|---|
| `solve/rows._reduce` | every `Pin` FIXES its vertex; two pins on one vertex resolve by generator ORDER, silently | **AFFECTED — the rect YIELDS**: `eat.withdraw_against_senior` (a post-pass in `constraints/__init__.generate`, counted as `eat_pin_withdrawn_senior`) drops an EAT pin on any vertex another generator pins or a rigid `Flat` group carries.  v1's own rule, stated rather than left to order.  KCLT: 0 withdrawn |
| `constraints/__init__.water_exempt` | withdraws every non-water row governing a water-pinned vertex | already total — an EAT pin on a water vertex is withdrawn there too |
| `constraints/__init__.seam_exempt` | pin↔pin pair exemption, SEAM pins only | unaffected: an EAT pin is not a seam pin, and a pair with ONE EAT foot stays — that pair IS the ramp |
| `structures.reconcile_datums` | tunnel / basin datum seniority | unaffected: no structure role is an EAT role |
| `constraints/ceiling.pavement_ceiling` | one HARD 5 % twin per pavement DIFFERENCE row | **AFFECTED and MEASURED** — the ramp's hard bound, and the bar the port misses (below) |
| `constraints/no_step`, `taxi.taxi_chain` / `taxi_centerlines` / `taxi_box`, `transverse`, `apron_within_shape` | the taxi / apron caps on rows whose feet include the rect | **the RAMP.**  The EAT mints no ramp row of its own — v1's lesson: one-sided pavement↔pavement interval edges blew the reach envelope up (KCLT killed at 15 min / 20.3 GB) |
| `constraints/taxi_trend` (`PlanarMap.taxi_trend_z`) | a DEM-trend target for every taxi-chain vertex; its own "pins" are RUNWAY CONTACTS, not `Pin` rows | **AFFECTED, priced**: a pinned vertex's neighbours keep a trend target pulling them back to the ground, charged at `[design] taxi_trend` 30 against `law` 300 — the measured ramp lands at 2.4–3.9 %, between the taxi cap and the trend |
| `solve/project.project_runway` | runway-family vertices only, everything else FIXED at the design value | unaffected: an EAT pin is outside the family and is one of the fixed feet moved to the right-hand side |
| `solve/project.project_zone_bands` | ground zone vertices | unaffected: every EAT role is pavement |
| `solve/design` §9b / `design_report.residual` | `cs.pins` for the ANCHORED-sheet test and the pin residual | correct as-is — the rect IS an anchor, which is the encoding the law asks for (`residual: pin 0.0000` on the build) |
| `verify/census.READERS` | one reader per family | **NEW** `verify/eat.eat_ceiling` |
| `check_grade.LAW_FAMILIES` / `run_checks` | the census register (the harness must price the EAT) | **NEW** family `eat_ceiling`, sidecar-declared, in the emission position after `basin_floor_declaration` |
| `emit/osm_adapter.SIDECAR_KEYS`, `pipeline/publication` | what the census may read | **NEW** key `eat_rects`, read off the FINAL constraint set (`publication(..., cs)`) so a withdrawn vertex is never reported |

**RECOGNITION, ALL SIX FRAMES** (the generator run DRY on each frame's own
capture — no solve; "none moves that has none"):

| frame | ruleset | ends | candidate rects | accepted | pins | verdict |
|---|---|---|---|---|---|---|
| **KCLT** | faa (0.025 / 0 m) | 6 | 1 | **1** — 18C, D 426.7–469.8, mid 448.3 | **4** | the owner's site |
| CYXY | icao (0.02 / 60 m) | 4 (one runway below code 3) | 0 | 0 | 0 | no EAT — nothing moves |
| HECA | icao | 6 | 0 | 0 | 0 | no EAT |
| SPJC | icao | 4 | 0 | 0 | 0 | no EAT |
| OTHH | icao | 4 | 3 | 0 | 0 | all three refused: **no routed wrap** (9/9/20 taxi-route crossings at the end, none in the rect's window) |
| LEMD | icao | 8 | 24 | 0 | 0 | every one refused BY NAME — 17 run ALONG the corridor, 4 beyond `max_crossing_m` 600 m, 3 no routed wrap.  The owner's "LEMD has no EATs", and v1's 149 false pins stay dead |

**THE SITE, BEFORE AND AFTER** (the same capture, arms `--drop-generator
eat_anchor_rect` vs default; z at the four pinned vertices):

| vertex | lat, lon | DEM | BEFORE | AFTER | the regulation |
|---|---|---|---|---|---|
| 2578 | 35.2314666, −80.9536558 | 228.33 | 226.58 | **217.26** | 217.26 |
| 2579 | 35.2314802, −80.9534306 | 228.36 | 226.91 | **217.26** | 217.26 |
| 2658 | 35.2316604, −80.9536668 | 228.44 | 226.69 | **217.26** | 217.26 |
| 3804 | 35.2312728, −80.9536229 | 228.29 | 226.88 | **217.26** | 217.26 |

**BAR 1 — the crossing at 216.3–217.4 m: MET.**  217.264 m, the FAA value at
D_mid = 448.3 m off an anchor of 226.158 m (18C/36C carries NO CIFP threshold on
either end, so the anchor is the runway's DEM-fitted profile at the end — v1's
anchor was the solved runway ring, which IS that profile).  The pin holds
EXACTLY: the census's new `eat_ceiling` family reads **0** rows on the built
patch, and the design report's pin residual is 0.0000 m.

**BAR 2 — the ramps within the taxi caps: MISSED, 2.37–3.87 %.**  Six ring edges
carry one pinned foot; their grades after are 3.87 / 3.05 / 2.97 / 2.57 / 2.44 /
2.37 % (before: 1.55–1.75 %), over 28.6–59.1 m.  None exceeds the hard 5 %
pavement ceiling, and the surface is smooth — 2,393 vertices move, max 9.64 m —
but the taxi cap is 1.5 %.  The mechanism is the consumer census's
`taxi_trend` row: the ramp's free neighbours carry a DEM-trend target (weight
30) against the taxi cap (300), so the solve trades ~1 % of grade for the
trend rather than running the ramp out along the loop.  **This is v1's own
outcome in v1's own words** — "a loop too short to ramp lawfully surfaces in the
both-hard step report … never a silent grade break" — and it is an INTENT
question for the owner, not a mechanism: is the EAT's ramp allowed to overrun
the taxi cap, or must the trend yield to it inside the rect's reach?

**BAR 3 — `HARD SET SETTLED` still: MISSED, by 0.028 m of surface.**  BEFORE:
`0/229114 hard rows violated`, max 0.0200 m, **HARD SET SETTLED**.  AFTER:
`13/229114`, max **0.0479 m**, HARD SET NOT SETTLED, `hard_worst =
rulesets.common.pavement_max_grade ceiling`.  The 9.65 m cut cannot be absorbed
under the 5 % ceiling to within `hard_tol_m` 0.02 m on 13 rows.  Identical in
the offline arm and in the closing build, so it is the law and not the run.

**BAR 4 — census before/after** (both arms replay-emitted from the same capture,
`tools/harness/census.py`):

| family | BEFORE | AFTER |
|---|---|---|
| LAW-TRUE TOTAL | 12,346 | **13,174** (+828) |
| `within_shape` | 9,343 | 9,980 (+637) |
| `airside_no_step` | 671 | 817 (+146) |
| `taxi_box` | 314 | 338 (+24) |
| `strip_transverse` | 13 | 18 |
| **`eat_ceiling` (NEW)** | **0** | **0** |

The +828 rows ARE bar 2 seen by the census: the ramp's pairs priced at the taxi
cap.  The COCKPIT block moves `CRITICAL motion` 16 → 18 (both new rows a
forbidden grade BREAK, neither at the EAT site — the site's own rows read as
SLOPES and are REPORT) and `CRITICAL visual` 2 → 2.  The 214 m `apron|apron` row
at 35.2138431, −80.9480288 is the z = 0 crater (lane `v2zerocrater`), present in
both arms.

**THE CLOSING BUILD.**  ONE `build_airport.py KCLT --engine v2`, wall **448.1 s**
(tag `KCLT_20260913T093620`, rc 0, `status=feasible`, `body_sha a33903eb3d1e`,
1,304 ways / 24,147 nodes, v2-verify 4,631 rows, shared repo UNCHANGED).
Generator counts: `eat_anchor_rect 4` rows in 0.037 s (ends 6, rects_accepted 1,
pins 4, every refusal counter 0), `eat_pin_withdrawn_senior 0`.  The artifact
ledger REFUSED the store (`CONTAMINATED-KEY`: the tree was committed between key
time and store time) — the build itself is unaffected; there is simply no
ledger artifact for it.

**THE INSTRUMENT HAD TO BE REPAIRED FIRST** (RULINGS 2026-09-13q named it a
chip).  `planar.__main__.default_inputs` resolves the mod cache to the ENGINE
TREE and reads no environment by design, so the pack-dump FRESHNESS guard
(`airport/load.py:289`) judged the SHARED root and refused **every** KCLT and
HECA v2 build, `explain` and `v2_solve_replay --capture` — no dump keyed to the
pristine `.dsf.anchor_bak` has ever existed for those packs.
`tools/harness/build_airport.py` now hands its own lane-local redirect to v2's
loader (`inputs.mod_cache_root`), which is where the env read belongs; the
build then derives its DSF text dumps in the same lane-local overlay as every
other derived cache.  `explain` and the replay tool still refuse — the same
line in `default_inputs` — and that half is left to the chip.

## §37 A ROAD KEEPS ITS OWN LONGITUDINAL LAW; A ROAD FLIPS BY SHARE; THE BANK IS EMITTED WHERE IT IS LOAD-BEARING (Fable 2026-09-13; RULINGS 2026-09-13q, KCLT items 5, 7, 8; CYXY item 2) — lane `v2roadcap`

Scout `v2kclt1t`: (5) the service road down to KCLT's east access road falls 1.4 %
where its DEM falls 9 % and ends +14.22 m in the air — `constraints/roads.py:38-70`
`road_law_caps` gives a road the STRICTEST longitudinal cap of any governed face it
touches (lateral contiguity, 2026-08-02 cl. 2) — 0.015 on 42 of KCLT's 121 groundside
faces; the 1:3 bank then walks 34 m to daylight it (lawful on that ray; airport-wide
17.6 % of foot stations are steeper than 1:3, max 1:0.4). (7) shapeID 791 (`dsf:pol82`,
8.4 m wide, 1,203 m perimeter, 575 m of road centreline inside, no taxi centreline —
a STRIP by evidence) was flipped to `apron` by §27 on 15.3 + 10.5 m of lateral apron
contact (2 % of its perimeter) and, under the apron's 1.5 %, climbs +12.3 m off its
ground; 60 ribbon aprons (< 12 m wide) carry 108,744 m². (8) the `bank_foot` ring is
the 1:3 transition from the patch COVERAGE (the union of every planar face — not an
aerodrome boundary; KCLT has none in OSM) to the DEM, emitted at every station: KCLT
34.2 km (42 % of stations carry < 0.5 m; 5.8 % over 5 m, max 19.2 m, stand-off to
89 m; 451 chords over 30 m up to 5.6 m off the DEM mid-chord), CYXY 14.8 km (51 %
under 0.5 m, max 2.4 m, none over 5 m).

1. **LATERAL CONTIGUITY BINDS THE TRANSVERSE CAP ONLY.** A road-family face takes
   the strictest cap of its contiguous faces for its TRANSVERSE law (it must not
   tear against the surface beside it); its LONGITUDINAL cap stays its own
   (`service_road` 8 %). Consumer census first (§28 frontages, §20 pad levels,
   `road_cross_section`, the lateral-contiguity family). KCLT's east road descends
   to its DEM.
2. **A ROAD FLIPS BY SHARE, A LOT BY EDGE.** §27's lateral test stays as ruled for
   lot-class faces (≥ 10 m); a STRIP-class face (a road by evidence) flips only when
   its lateral airside contact is at least `[lot] road_airside_edge_frac` (0.2) of
   its perimeter — LEMD's 61 apron-side lanes (edges to 828 m) stay apron; a
   through-road touching an apron for 2 % of its length stays a road (owner 13j
   item 7). Consumer: `airside_edge_flip` only.
3. **THE BANK IS EMITTED WHERE IT IS LOAD-BEARING.** A foot station is emitted only
   where |z_ring − DEM(foot)| exceeds `[design] bank_materiality_m` = `bank_min_width_m
   × bank_slope` (1.65 m); elsewhere the ring carries no foot and the mesh's own
   interpolation blends the sub-metre difference. Long foot chords are split at
   `bank_chord_max_m` (30 m) so no chord stands more than `split_tol_m` off the DEM
   mid-chord. The bank's own law is unchanged: it still daylights at 1:3 where it is
   emitted; the real reduction comes from (1) and (2), which remove the fill the
   bank was covering. The owner's question ("do we need it at all?") is answered
   with the numbers: CYXY's ring vanishes; KCLT's shrinks to its load-bearing
   stations, re-quoted after (1)/(2).
4. **BARS**: KCLT `dsf:pol51` within 2 m of its DEM at its east end (today +14.22),
   `service_road` off-DEM max 14.2 → < 3 m; shapeID 791 a `service_road` (its fill
   +12.3 → on its ground); ribbon aprons 60 → quoted; LEMD's §27 flips unchanged (dry
   replay); bank foot stations KCLT 1,855 → N (load-bearing only), CYXY 649 → 0 (dry
   replay), stations steeper than 1:3 quoted; chords over 30 m 451 → 0; ONE
   `--engine v2` KCLT build with the cockpit block first (critical motion 16 → quoted,
   the three item-5 cliffs gone); census; twins; suite. The census's 215 m apron
   step at 35.2138431, −80.9480288 is the z = 0 crater (lane `v2zerocrater`), excluded.
### §37.1 CONSUMER CENSUS (owner RULINGS 2026-08-30l), completed BEFORE any consumer was edited — lane `v2roadcap`

**A. THE LATERAL-CONTIGUITY CAP** (`constraints/roads.road_law_caps`; §37 (1)).

| # | consumer | reads | RULE |
|---|---|---|---|
| L1 | `constraints/roads.road_within_shape` | `road_law_caps` | **EDITED**: `cap_l` is the ROLE'S OWN longitudinal (`service_road` 8 %); `cap_t = min(role transverse, contiguity cap)`. |
| L2 | `constraints/taxi.triangle_planes` (`plane_gradient`) | `road_law_caps` | **EDITED — the contiguity min is DROPPED.** `|∇z| ≤ cap` is ISOTROPIC: a plane row has no transverse component to bind on its own, so it prices at the face's own longitudinal cap. Before §37 this branch flattened a road triangle in every direction. |
| L3 | `pipeline/publication.face_tags` | `road_law_caps` | **EDITED**: stamps `o4_grade_law_cap_t`, never the bare `o4_grade_law_cap` (which binds a way's WHOLE within-shape reading in the v1 census). |
| L4 | `pipeline/publication.publication` `station_caps` | `road_station_caps` | UNCHANGED. The per-station vector is the WALK, not a cap assignment; v1's fourth reader still reads it and, with it present, mints no row BY CONSTRUCTION (`_built = min(eff, published) ≤ _law_here`). |
| L5 | `constraints/contiguity.{station_caps,road_station_caps,cap_at,face_station_cap}` | the probe walk | UNCHANGED — the walk is the same; only what the cap BINDS changed. |
| L6 | `verify/contiguity.lateral_contiguity` | `p.cap(sh)` + published stations | **EDITED**: prices `p.cap_t(sh)` — the transverse binding — against the re-walked cross-section's strictest longitudinal law. |
| L7 | `verify/frame.Patch.cap` / `Shape.law_cap` | `law_caps` mapping | **EDITED**: `cap()` is now the role's longitudinal alone; new `cap_t()` folds the binding in. `Shape.law_cap` MEANS the transverse binding; every `census(surf, law, pub, road_law_caps(...))` call site is unchanged. |
| L8 | `verify/within.within_shape` / `road_cross_section` | `p.cap`, `rc.transverse` | **EDITED**: `cap_t = p.cap_t(sh)`; the longitudinal cap is the role's. |
| L9 | `verify/within.plane_gradient` | `p.cap` | follows L7 — the role's own longitudinal. Mirrors L2, so generator and reader move together. |
| L10 | `check_grade._role_grade_limit` / `_lateral_cap_tag` (`o4_grade_law_cap`) | the way tag | UNCHANGED IN MEANING. v2 no longer stamps it for contiguity, so a v2 road reads its role cap; **every v1 patch reads exactly as before** (08-02 clause 2 is untouched in `auto_patch/`). |
| L11 | `check_grade._xsec_allowance` (the `road_cross_section` family) | `cap_l` | **EDITED**: `min(road_cross_section_cap(cap_l), o4_grade_law_cap_t)` — the ONE site at which the contiguity cap reaches the v1 census. |
| L12 | `check_grade._check_lateral_contiguity` (the fourth reader) | published `station_caps` | UNCHANGED — vacuous by construction on a v2 sidecar (L4). |
| L13 | `emit/osm_adapter` oracle alias (`extra["o4_grade_law_cap"]` `prior`) | the face tags | UNCHANGED CODE. `prior` is now absent for road-family aliases, which is the intent: an alias's LONGITUDINAL cap must not be tightened by a transverse law. |
| L14 | §28 GROUNDSIDE FRONTAGES (`constraints/pad_frontage_gs.py`, `verify/frontage`) | pad ↔ frontage rows | UNAFFECTED — neither imports `road_law_caps`; a frontage row's cap is the pad law's. |
| L15 | §20 PAD LEVELS (`constraints/pads`, `[design] pad_level_rulings`) | pad rim / pavement edge | UNAFFECTED — same; and the relaxation FREES the road, it never pulls a pad (the one-way rulings). |
| L16 | `solve/why.family_of` (`road_within_shape` / `road_cross_section`) | the row's source | UNAFFECTED — labels unchanged. |
| L17 | `auto_patch/` v1 (`lateral_contiguity.py`, `grade_graph._body_cap`, `layout.py:3120`) | v1's own stamping | UNTOUCHED — §37 is v2 law. |

**B. `airside_edge_flip`'s callers** (§37 (2)).

| # | consumer | reads | RULE |
|---|---|---|---|
| B1 | `classify/roles.classify` | the ONE call | UNCHANGED signature and return; the share test lives inside the one derivation site (§27 (2)). |
| B2 | every downstream consumer of `role` | `law.tables.role_side` | UNAFFECTED BY CONSTRUCTION — `side` stays a pure function of `role`. |
| B3 | `tools/role_edge_census.py` | the emitted patch | UNAFFECTED — it reads the product, and reports the share it now measures against. |

**C. THE BANK's readers** (§37 (3)). A foot ring may now be one OPEN chain per load-bearing run.

| # | consumer | reads | RULE |
|---|---|---|---|
| C1 | `emit/osm_adapter` bank branch | `closed = vertices[0] == vertices[-1]`, `len ≥ 3` | UNCHANGED — it ALREADY emits an open chain (the tile-piece case, §9.4 deviation 2). Runs are padded so no chain is under 3 nodes. |
| C2 | `emit/osm_adapter.write_tile_pieces` | breakline runs | UNCHANGED — a chain splits at a seam exactly as a ring did. |
| C3 | `O4_Vector_Map.include_patches` | every CLOSED way | An OPEN `bank_foot` way is a constrained LINE carrying altitudes: it seeds no INTERP_ALT face and blocks no water flood. CORRECT — where no foot is emitted there is no bank to seed. |
| C4 | `O4_Mesh_Utils._bank_rings_from_patches` / `bank_annulus_polygon` | CLOSED `bank_foot` ways only | **EDITED**: an open chain is closed into its RIBBON — the chain and its own nearest-point projection onto the design coverage — and REFUSED when the swept area is implausible for a bank of that length. Without this, one immaterial station would have taken the whole ring's annulus out of the linear blend. A refusal leaves those vertices to the harmonic extension, which is this module's standing rule. |
| C5 | `O4_Mesh_Utils.bank_annulus_blend_values` / `_bank_foot_along_normal` / `BANK_BLEND_STATS` | the annulus + the feet | UNCHANGED via C4. Where a run carries no foot, `interpolate_free_interior_altitudes`' harmonic extension carries the sub-materiality difference — §37 (3)'s own words. |
| C6 | `O4_Mesh_Utils.bank_annulus_region_areas` (Triangle's region sizing) | `bank_annulus_polygon` | follows C4. |
| C7 | `check_grade._parse_osm` / `ROLE_LESS_FEATURE_CLASSES` | `o4_feature=bank_foot` | UNCHANGED — routed to `feature_out` open or closed; it mints no row (§9 A10/A11). |
| C8 | `verify/frame.Patch.of` | `runway_profile` / `structure_rim` kinds | UNAFFECTED (§9 A8). |
| C9 | `emit/surface.GradedSurface.to_json` / `SCHEMA` | breaklines as vertex tuples | UNAFFECTED. |
| C10 | `emit/rebake.deck_datum_from_surface`, `airport/rebake_plan` | the PRE-bank surface | UNAFFECTED (§9 A7). |
| C11 | `emit/terrain_edge.no_bank_region` | the banked region cut | UNCHANGED — the region is cut before any station is emitted. |

### §37 **MEASURED** (lane `v2roadcap`, 2026-09-13, branch `claude/v2roadcap`, base `ec8723e9`)

**THE CLOSING TEST MOVED FROM KCLT TO LEMD — KCLT CANNOT BE BUILT ON THIS
CORPUS, AND THE LANE DID NOT MAKE IT BUILDABLE.**  `build_airport.py KCLT
--engine v2` refuses at the loader, before classify:

> `KCLT: the pack DSF …/+35-081.dsf.anchor_bak is newer than every cached
> text dump under …/Airport_mod_cache/Nimbus Simulation - KCLT V1.4 …`

The refusal is `airport/load.py:289` and it is CORRECT.  The PRISTINE read
frame (RULINGS 2026-09-11m) reads `+35-081.dsf.anchor_bak`, and
`dsf.find_text_dump` keys the candidate dumps on *that* basename: the
shared mod cache holds `+35-081.dsf.{1334c2dd,7bf41307,b698274b}.text` —
dumps of the WRITTEN DSF — and **no `+35-081.dsf.anchor_bak.*.text` at
all** (LEMD, OTHH, NZQN and NZVL each have one; KCLT has never had one).
The cure is `--refresh-data airport_mod_cache`, which this lane's brief
forbids and which changes every lane's corpus stamp.  **It is the
orchestrator's call, not the lane's.**  The same guard is what refused the
scout's `explain KCLT` (13q).  Consequences, stated rather than papered
over: every KCLT bar of §37 (4) — `dsf:pol51`, shapeID 791, the ribbon
aprons, the cockpit block, the KCLT census — is **NOT MEASURED**.  What is
measured below is LEMD (the closing build) and CYXY (the control), both
`--engine v2`, both against a `--base-arm` at the same base `ec8723e9`,
plus the KCLT BASE numbers read offline from the 1.0.324 products.

#### KCLT, BASE ONLY (the 1.0.324 products, read with the emitter's own instruments)

Reproduced exactly, so the sites are not in doubt — only the fix is
unmeasured:

| site | 1.0.324 |
|---|---|
| `dsf:pol51` shapeID 946 | `o4_grade_law_cap=0.015`, worst **+14.22 m** at 35.2074982, −80.9296586, east end +8.09 |
| `dsf:pol51` shapeID 945 | `o4_grade_law_cap=0.015`, worst +14.07 m, east end +8.02 |
| `service_road` (whole airport) | 864 vertices, **max +14.22 / −4.14 m** off the DEM |
| shapeID 791 (`dsf:pol82`) | role **`apron`**, 81 vertices, **+12.33 m** at 35.2209280, −80.9275739 |
| bank | 49 closed rings, **1,855 stations**, 34,212 m, **451 chords over 30 m**, max chord 130.1 m |
| bank materiality (§37 (3), read with `_inner`'s own rule) | **526 of 1,855 stations (28.4 %) load-bearing** at 1.65 m; 57.8 % carry over 0.5 m, 7.1 % over 5 m |
| ribbon aprons (< 12 m min-rect width, emitted apron ways) | **43 / 5,010 m²** — NOT the spec's 60 / 108,744 m², a different instrument; quoted here on the one used for both arms |

#### LEMD — the closing build

ONE `--engine v2 --patch-only` build per arm, one tree, one corpus
(`e512b4ea8cca`), both at base `ec8723e9`, both rc 0, shared repo
UNCHANGED:

* BASE — tag `v2roadcapLEMDbase`, 523.6 s engine, artifact ledger
  **`11c63567bce3`**;
* §37 — tag `v2roadcapLEMD2`, 510.5 s engine, artifact ledger
  **`648c9198fba3`** (the first §37 arm, `v2roadcapLEMD`, 400.0 s, is the
  same patch outside the bank: it carried the padded-run overlap the
  twin now forbids).

**§37 (2) — LEMD's flips STAND, PROVEN BY IDENTITY.**  The two arms'
patches carry **1,075 role-carrying faces with byte-identical roles: 0
changed**.  `tools/role_edge_census.py` reads the same figure on both:
124 groundside shapes, 28 sharing ≥ 10 m with airside pavement, **0
substantive (all 28 slivers, 789 m²), 0 LOT-class**.  A lane that runs
828 m ALONGSIDE its apron is a share, not a graze; none came back.

**§37 (3) — the bank.**

| | BASE | §37 |
|---|---|---|
| foot nodes | **2,594** in 48 closed rings | **836** in 78 chains, 76 open |
| foot length | 60,986 m | **11,544 m** |
| chords over 30 m | **820** (max 131.7 m) | **0** (max 30.0 m) |
| duplicate foot coordinates | **5** (pre-existing) | **0** |
| load-bearing stations | — | **489 of 2,596** (2,107 under the 1.65 m floor; 11 rings carry no bank at all); 153 split stations |
| bank slope p95 / max |  0.433 / 1.255 | **0.580** / 1.260 |

The slope p95 rises because it is the pre-existing `slope to the nearest
DESIGN vertex` statistic now read over LOAD-BEARING stations only — the
minimum-width feet that held it down are exactly the ones §37 (3)
removes.  It is the §9.5 residual, reported and not fixed.

**§37 (1) — THE CENSUS MOVED THE WRONG WAY AT LEMD, AND THE LANE DOES NOT
PAPER OVER IT.**

| harness census | BASE | §37 |
|---|---|---|
| LAW-TRUE | 3,573 (within 3,570 / cross 3 / steps 0) | 3,798 (3,795 / 3 / 0) |
| **ADJUDICATED** | **1,143** — airside 1,127 / gs 15 / mixed 1 | **1,379** — airside **1,345** / gs 33 / mixed 1 |
| `within_shape` | 2,792 | 2,821 |
| `taxi_box` | 204 | **326** |
| `airside_no_step` | 419 | **481** |
| `road_cross_section` | 0 | 2 |
| `strip_transverse` / `strip_longitudinal` | 43 / 15 | 49 / 20 |

**+236 adjudicated, +218 of it airside — and the roads are groundside.**
Attribution, in the order the rulings require:

1. **It is not §37 (2)**: the classification is byte-identical (above).
2. **It is not §37 (3)**: the bank is built AFTER the solve and is
   census-skipped; the pre-fix and post-fix §37 arms — which differ ONLY
   in the bank — census **identically** (3,798 / 1,379, family for
   family).  The same holds at CYXY (1,049 / 345 in both).
3. **§37 (1) is a STRICT RELAXATION of the road family, proven by
   construction.**  The transverse cap is arithmetically unchanged —
   `min(rc.transverse, cap_l)` with `cap_l = min(long, law_cap)` equals
   `min(rc.transverse, long, law_cap)` — and the longitudinal cap only
   ever rises (0.015 → 0.080 on a contiguous road).  The generator row
   COUNTS are identical in both arms, line for line, all 62 of them.  So
   no row was tightened and none was added.
4. **What is left is the LP landing on a different optimum of an
   UNSETTLED system.**  Both arms report `HARD SET NOT SETTLED` (2 and
   25 of 126,696 rows violated) and `LAG NOT SETTLED`; the assembled
   design system moves 64,902 → 66,830 rows (the one-sided split, not
   the generators); and the same mechanism at CYXY moves the census the
   OTHER WAY, −61 adjudicated / −75 airside.  Non-monotone across two
   airports from one strictly-relaxing change is the signature RULINGS
   2026-09-12i named for §27's tunnel ramp: an LP re-solve of a free
   interior, not a mechanism.  **The census is not the objective.**
5. **What this lane did NOT do**: it did not tune the objective, gate the
   change, or iterate a third time.  The regression is REPORTED with its
   site numbers for the owner's adjudication.  Nothing here says the
   +218 rows are lawful — only that they are not a groundside pull the
   code can be shown to make.

#### CYXY — the control, both arms at `ec8723e9`, one tree, one corpus

| | BASE (`163c4e7f50dc`) | §37 (`cc9c86490555`) |
|---|---|---|
| harness census LAW-TRUE | 1,047 | 1,049 |
| harness census **ADJUDICATED** | **406** (airside 381 / gs 25) | **345** (airside **306** / gs 39) |
| `within_shape` | 915 | 968 — the whole rise is `withdrawn_law_05aa` taxi chords, 625 → 688, never adjudicated |
| `road_cross_section` | 12 | 17 |
| `taxi_box` | 34 | **17** |
| `airside_no_step` | 74 | **40** |
| `plane_gradient` | 1 | **0** — §37 (1)'s L2: the isotropic plane row is no longer bound to a contiguous class |
| `transverse` | 9 | 5 |
| bank foot nodes | **649** in 20 closed rings | **153** in 19 chains, all open |
| bank foot length | 14,835 m | **2,346 m** |
| bank chords over 30 m | **218** (max 82.3 m) | **0** (max 29.8 m) |
| bank load-bearing stations | — | **79 of 648** |
| duplicate foot coordinates | 0 | 0 |
| groundside shapes ≥ 10 m airside edge, substantive | 3 (10,295 m²) | 4 (11,546 m²) — one road came back, exactly §37 (2) |
| `service_road` off-DEM > 0.5 m | 83 / 292 (max 2.99 m) | 93 / 314 (max 3.14 m) |

**−61 adjudicated at CYXY, −75 of them airside**, the gain in
`airside_no_step` (74 → 40) and `taxi_box` (34 → 17).

**CYXY's ring does NOT vanish.**  §37 (3) predicted 649 → 0 from the
scout's headline ("max 2.4 m").  Read with the emitter's OWN inner-end
rule — the nearest point of the coverage with its z interpolated ALONG
the boundary edge, which is `emit/bank.py::_inner`, not the nearest
design VERTEX — CYXY carries 115 stations over 1.65 m and 27 over 5 m.
The measured answer to the owner's question "do we need it at all" is
therefore: **yes, but only for a sixth of it** — 79 load-bearing
stations, 2,346 m of foot instead of 14,835 m, 84 % of the ring gone.
At LEMD the same reading leaves 489 of 2,596 and 81 % of the foot gone;
the KCLT products read 526 of 1,855 (28.4 %).

#### A DEFECT §37 (3) INTRODUCED AND THE TWIN NOW FORBIDS

Padding each load-bearing run separately makes two runs one station
apart OVERLAP, and two chains over the same ground re-emit the same edge
on two sets of nodes — the duplicate constrained segments RULINGS
2026-09-09t measured Triangle's recovery spinning on.  Measured on the
first arms: **3 duplicate foot coordinates at CYXY, 14 at LEMD**.  The
padding is now part of the MEMBERSHIP (`keep[i] = flags[i-1] or flags[i]
or flags[i+1]`, then maximal cyclic runs of `keep`), twinned, and both
arms read 0 — the LEMD base's own 5 duplicates are gone with them.

#### Build-time impact statement

Bank pass: CYXY 0.14 s both arms, LEMD 0.54 → 0.51 s.  §37 (1) removes a
`min`; §37 (2) adds one comparison per candidate; §37 (3) reads `_inner`
for every region station instead of only for emitted ones and re-reads it
for the kept ones, which the bank pass absorbs.  Whole-build wall is a
re-solve of a changed system on a machine running four lanes
concurrently, so no A/B is quoted (standing law: never one run per side).
Nothing here is within 1 % of either budget.

#### What this lane did NOT do

KCLT (blocked — the pristine-DSF dump, above); the five-airport sweep
(the orchestrator's, once per merged batch); any `--refresh-data`; any
new tool (nothing here needed one — the bank's own census is
`BankReport.line()`, the share census is `tools/role_edge_census.py`,
the defect counts are `tools/harness/census.py`), so no `tools/INDEX.md`
row; any merge.

### §36 (5) THE RAMP REACH IS DERIVED; THE TREND YIELDS (Fable 2026-09-13; RULINGS 2026-09-13aa) — lane `v2eatramp`

Lane `v2eat` measured the six ramp edges off the pinned feet at 2.37–3.87 %
over 28.6–59.1 m against the 1.5 % taxi cap: the ramp's free neighbours keep
a `taxi_trend` DEM target (weight 30) against the cap (300) — v1's "loop too
short to ramp lawfully" outcome. The taxi cap is law (§31: a 3.9 % taxiway is
a slope a pilot feels; the DEM target is the unreliable witness).

5. **THE RAMP RUNS BACK ALONG THE LOOP UNTIL THE CAP IS MET.** From each
   pinned foot the ramp follows the EAT loop's own centreline (the routed
   wrap the rect was recognised on) until the loop's DEM-fitted profile is
   reached at ≤ the taxi longitudinal cap: reach = drop / cap (KCLT: ~9 m /
   0.015 ≈ 600 m per side, which the end-around loop affords). Over that
   reach `taxi_trend` is WITHDRAWN for the loop's vertices (not outweighed)
   and the loop's transverse rows carry its shoulders with it. Where the loop
   is too short to ramp lawfully, the crossing KEEPS the regulation value and
   the report names the overrun as a forbidden grade under the taxi family —
   never a silent 3.9 %. The `[design] hard_rulings` register is untouched
   (a Pin holds exactly; §36 MEASURED).

BARS (KCLT, same capture both arms, then ONE build): every edge on the EAT
loop ≤ 1.5 % (today six at 2.37–3.87 %); the crossing 217.26 ± 0.05 at all
four vertices; the hard set SETTLED (today 13 `pavement_max_grade ceiling`
rows, max 0.0479 m — name them and show they are the ramp's neighbours before
claiming the fix clears them); cockpit CRITICAL motion ≤ 16 with the two
grade breaks v2eat introduced named and placed; `eat_ceiling` 0; the five
other frames unchanged (no rect recognised); suite twice.


### §36 (5) **MEASURED** (lane `v2eatramp`, 2026-09-13, branch `claude/v2eatramp`, base `2002c7dc` merged to main `864e7577`, sha `9b34fe6d`)

**THE RAMP CAME DOWN AND THE COCKPIT WENT QUIET; THE RAMP DID NOT REACH
THE CAP, AND THE HARD SET MOVED THE WRONG WAY.**  Worst ramp edge
3.87 % → **2.13 %**, the loop's own centreline 2.44 % → **1.90 %** with a
uniform **1.60–1.66 %** running leg, against the 1.5 % taxi cap — the loop
is 10 % TOO SHORT and the law's own report now says so by name.  Cockpit
CRITICAL motion **12 → 7** (bar ≤ 16, MET, and below the no-EAT arm's 13);
law-true census 11,792 → 11,259, adjudicated 3,883 → 3,798.  Hard rows
violated **13 → 70** — all 61 new rows `structures.building_pad`, on
buildings 3.5 km from the crossing: BELOW BAR, reported for the owner.

**THE FRAME, STATED** (owner RULINGS 2026-09-13ak).  Base `2002c7dc`
carried a silent main regression — `pack_partition` built `Member`
positionally, every KCLT member came back with a non-`None` `plate_y`,
`planar/group._eligible` reads that as "another law governs this body",
and the whole pad group law was OFF (KCLT groups 7,007 → 0, relief bodies
1,261 → 0, infeasible 1,032 → 0, off an IDENTICAL partition: bodies 7,163,
abutment pairs 5,054, units 60).  This lane measured it, reported it and
did NOT patch it; main fixed it in `db5b99ca` and the arms below were all
re-cut on the merged tree.  Every offline arm is ONE `v2_solve_replay`
capture of KCLT taken on THAT tree (`--capture`, 86 s, 22,328 vertices,
1,175 faces, groups 7,007), replayed three ways under this branch:
`--drop-generator eat_anchor_rect` (no EAT), `--drop-generator
eat_ramp_reach` (the pins, no reach — today), and the default.  One
capture, one tree, one code version.

**THE CONSUMER CENSUS** (owner RULINGS 2026-08-30l), ruled before any
consumer was edited.  The region is "the ground-trend TARGET on the EAT
loop's vertices" (`PlanarMap.taxi_trend_z` / `apron_trend_z`) and the rect
that derives the reach:

| # | consumer | what it reads | RULING |
|---|---|---|---|
| 1 | `solve/design` §5c (`for vid, target in planar.taxi_trend_z`) | the channel, one row per vertex at `[design] taxi_trend` 30 | **THE ROW THAT YIELDS.**  Withdrawn by ABSENCE from the channel, never by weight: `solve` imports `law` and `model` only (M0 §1), so the derivation cannot live at the row site — and a re-weighting would still TRADE, and the trade is what §31 forbids. |
| 2 | `constraints/apron_trend` (`taxi_held = set(pm.taxi_trend_z)`) | claims every vertex the taxi trend does NOT hold | **AFFECTED — it yields on the same terms.**  Withdrawing one channel alone hands the same DEM pull back at `[design] apron_trend`.  ONE withdrawal, BOTH channels, run AFTER both are published so neither claim is re-opened by the other's absence.  KCLT: taxi 3,035 → 2,881, apron 5,310 → 5,291. |
| 3 | `constraints/taxi_trend._face_extension` (face → chain ownership) | which chain speaks for a face | **SHARED, NOT COPIED** — lifted verbatim into `taxi_chains` / `chain_of_face`, so the reach reads the loop's centreline in the SAME station frame the trend was fitted along.  Two derivations of "the loop's centreline" would withdraw on one frame and price on another. |
| 4 | `constraints/eat.eat_pins` | the rect, the pins | UNCHANGED.  The reach is derived from the pins the generator would mint on this very map, so pin and withdrawal cannot disagree (0.04 s, run twice per build). |
| 5 | `constraints/eat.withdraw_against_senior` | an EAT pin junior to another authority | REPORTED, not fixed: a pin later withdrawn as junior leaves its reach withdrawn, so those vertices are FREE rather than trend-pulled — the conservative direction.  KCLT withdraws 0 (`eat_pin_withdrawn_senior 0` on the build). |
| 6 | `taxi_trend.taxi_trend_block` / `design_report.taxi_trend_rows` | the residual per chain | CORRECT BY CONSTRUCTION — it reads the FINAL channel, so a withdrawn vertex is neither priced nor reported. |
| 7 | `pipeline/why` | its own LP | **EDITED** — publishes the withdrawal in the pipeline's position; without it a ramp vertex reads as held by a `taxi_trend` row the build does not have. |
| 8 | `tools/v2_solve_replay._targets` | the build's target channels | **EDITED** — third entry, plus the `eat_ramp_reach` pseudo-generator: the withdrawal is a CHANNEL edit made before the solve, so `--drop-generator` cannot reach it by row filter and it is named instead.  That is the before-arm. |
| 9 | `[design] hard_rulings` | which heads are hard | **UNTOUCHED**, as §36 (5) requires.  A `Pin` never enters `one`/`eqs`; the taxi cap stays a soft law row at `law` 300. |
| 10 | the transverse / `no_step` / `taxi_box` rows on the loop's shoulders | pairs whose feet include a withdrawn vertex | UNCHANGED — and they are what carries the shoulders down with the spine (§36 (5)'s own sentence): the withdrawal covers the chain's own vertices AND every vertex of the faces that chain owns. |
| 11 | `verify/eat.eat_ceiling`, the `eat_rects` sidecar key | the census family | UNAFFECTED — the pins are unchanged; `eat_ceiling` reads 0 rows in every arm and on the build. |
| 12 | the five other frames | no rect recognised (§36 MEASURED) | UNAFFECTED BY CONSTRUCTION — `withdraw_trend_over_reach` returns the map OBJECT-IDENTICAL when the generator mints no pin; twinned. |

**THE REACH, DERIVED** (`report.load.eat_reach`).  All four pinned feet sit
on ONE loop — breakline chain 4, the 18C end-around, 1,310 m long:

| foot | station | drop vs the loop's own trend | cap | reach = drop / cap | loop back / fwd | verdict |
|---|---|---|---|---|---|---|
| 2536 | 625.9 m | 10.53 m | 0.015 | **702.1 m** | 625.9 / 683.8 | SHORT — forced **1.54 %** |
| 2537 | 646.5 m | 10.79 m | 0.015 | **719.4 m** | 646.5 / 663.3 | SHORT — forced **1.63 %** |
| 2616 | 626.5 m | 10.54 m | 0.015 | **702.6 m** | 626.5 / 683.3 | SHORT — forced **1.54 %** |
| 3760 | 627.4 m | 10.55 m | 0.015 | **703.4 m** | 627.4 / 682.4 | SHORT — forced **1.55 %** |

177 vertices fall inside the reach; 173 carried a trend target and lost it
(154 taxi + 19 apron).  **The whole 32-vertex chain is inside the reach** —
the loop is saturated, so there is no reach knob left to turn: the residual
is the loop's own length, not a tuning.

**BAR 1 — every edge on the EAT loop ≤ 1.5 %: MISSED at 2.13 %** (today
3.87 %).  The six ring edges carrying one pinned foot:

| edge | span | BEFORE | AFTER |
|---|---|---|---|
| 3759–3760 | 49.1 m | 3.05 % | **2.13 %** |
| 2535–2536 | 48.6 m | 2.44 % | **1.90 %** |
| 2616–2617 | 59.1 m | 2.57 % | **1.84 %** |
| 2537–2538 | 28.6 m | 3.87 % | **1.58 %** |
| 3760–3761 | 49.1 m | 2.98 % | **1.58 %** |
| 2615–2616 | 58.6 m | 2.37 % | **1.13 %** |

Along the loop's OWN centreline the profile is now one clean ramp: the
forward leg a uniform **1.60–1.66 %** over 660 m (before: 1.68–3.87 %
spent in the first 100 m and FLAT beyond), the back leg 1.0–1.90 %.
1.60–1.66 % is the forced grade the reach table predicts to within
0.03 pp — the measurement saying the holder is the loop's LENGTH and
nothing else.  The 0.4–0.6 pp above it on the ring edges is the bending
term shaping the last 50 m into the pin; closing that would take the taxi
cap into `hard_rulings`, which §36 (5) forbids.  (The identical figures
came off the pre-merge frame too, on lane `v2eat`'s `ec8723e9` capture:
the site result is frame-robust.)

**BAR 2 — the crossing 217.26 ± 0.05: MET.**  `alt_abs 217.26` at all four
nodes of the CLOSING BUILD's patch (35.23146663387,−80.95365582614 ·
35.23148016243,−80.95343062726 · 35.23166042348,−80.95366682242 ·
35.23127284508,−80.95362285927); pin residual 0.0000 m; `eat_ceiling` 0.

**BAR 3 — the hard set SETTLED: MISSED, AND IT MOVED BACKWARDS**
(`v2_solve_replay --why-hard`):

| arm | hard rows violated / 241,556 | max | by generator |
|---|---|---|---|
| no EAT | **1** | 0.0200 m | runway_profile 1 |
| EAT, no reach (today) | **13** | 0.0334 m | pavement_ceiling 8, runway_profile 5 |
| EAT + reach | **70** | **0.0760 m** | **pads 61**, pavement_ceiling 6, runway_profile 3 |

**THE 13 NAMED, AND THE 70.**  Today's 13 are 8
`rulesets.common.pavement_max_grade ceiling` and 5 runway-profile rows;
the worst four pavement rows are `parking_lot`↔`parking_lot` pairs at
(35.21333896,−80.92936611) 0.0334 · (35.20325433,−80.94420462) 0.0274 ·
(35.21096060,−80.93927847) 0.0273 · (35.21387543,−80.93042035) 0.0251 —
**terminal-side car parks 2–3 km from the crossing at (35.2313,−80.9536);
not one is a ramp neighbour, and none is inside the reach.**  The fix
therefore never claimed them, and it did not clear them: 6 remain.  What
it DID do is add 61 `structures.building_pad pad_slope_max ceiling` rows,
worst 0.0760 m, every one on BUILDING vertices at (35.20120,−80.93023) and
(35.20964,−80.93273) — 3.5 km from the EAT, on the other side of the
field.  No row of any arm touches an EAT pin or a withdrawn vertex.  All
three arms report `HARD SET NOT SETTLED` and `LAG NOT SETTLED` (4,104 of
11,266 one-way rows still moving, worst 0.4304 m on `zones.adjacent_ground`),
and the active set flips 868–1,676 rows: this is KCLT's own instance of
13y (B), and a strictly-local withdrawal 3.5 km away landing 61 pad rows is
the signature RULINGS 2026-09-12i named — an LP re-solve of an unsettled
free interior, not a mechanism.  **Nothing here says those 61 rows are
lawful.**  The lane did not tune the objective, gate the change or iterate
a third time; the regression is reported with its coordinates for the
owner's adjudication.

**BAR 4 — the census** (`tools/harness/census.py`, all three arms
replay-emitted from the one capture):

| | no EAT | EAT, no reach | EAT + reach |
|---|---|---|---|
| LAW-TRUE TOTAL | 11,095 | 11,792 | **11,259** |
| ADJUDICATED | 3,657 (airside 3,266) | 3,883 (airside 3,479) | **3,798** (airside 3,362) |
| `within_shape` | 8,357 | 8,917 | **8,483** |
| `airside_no_step` | 608 | 718 | **612** |
| `taxi_box` | 327 | 328 | **317** |
| `strip_arc` | 12 | 11 | **6** |
| `transverse` | 106 | 114 | **109** |
| `eat_ceiling` | 0 | 0 | **0** |

The reach gives back 533 law-true rows and 85 adjudicated of the 697 / 226
the EAT costs; `airside_no_step` returns to within 4 rows of the no-EAT
arm and `within_shape` to within 126.

**BAR 5 — cockpit CRITICAL motion ≤ 16: MET, 7** (no EAT 13, EAT without
the reach 12).  CRITICAL visual **0** in all three.  The whole movement is
`strip_arc` forbidden grade BREAKs — the graded strip's longitudinal
grade-CHANGE rate where the ramp starts and stops: **9 → 8 → 3**, with
`step_on_pavement` 4 and the `frontage_near_miss` 2 / `mid_edge_step` 2
unmoved in every arm.  The ramp the reach builds is smooth enough that the
strip beside it stops breaking: six of the nine breaks the pre-EAT surface
carried are gone.  The CLOSING BUILD reads the same: motion **7**, visual
**0**, worst 0.603 m over 0.9 m `mid_edge_step`.

**THE FIVE OTHER FRAMES: UNCHANGED, BY CONSTRUCTION.**  The withdrawal is
gated on `eat_pins` minting a row; §36 MEASURED recognised no rect at
CYXY, HECA, SPJC, OTHH or LEMD and that code is untouched, so
`withdraw_trend_over_reach` returns the same PlanarMap OBJECT there
(twinned: `test_an_airport_with_no_eat_is_returned_unchanged`).

**THE CLOSING BUILD.**  ONE `build_airport.py KCLT --engine v2 --tag
v2eatramp2`, wall **355.7 s**, rc 0, `status=feasible`, `body_sha
47ab51d3c20f`, 1,307 ways / 23,094 nodes, v2-verify 3,908 rows, **shared
repo UNCHANGED**, artifact ledger **`3d37ac3788da`**.  Its design line
reproduces the AFTER replay exactly (580 active-set rounds, 2,881 taxi
trend rows, 70/241,556 hard rows, max 0.0760 m) — the replay IS the
build's own LP, arm for arm.  Census of the built patch:
LAW-TRUE 11,274, ADJUDICATED 3,813 (airside 3,379), `eat_ceiling` 0,
cockpit motion 7 / visual 0.  Generator: `eat_anchor_rect` 4 pins,
`eat_pin_withdrawn_senior` 0.  **Suite** (`tests/auto_patch_v2`,
`test_harness.py`, `test_role_edge_census.py`): 1,218 passed / 1 skipped,
twice.

**Build-time impact.**  `eat_reach_plan` runs the EAT generator a second
time (0.04 s at KCLT) plus one projection of 177 candidate vertices onto
one 32-segment chain; the whole withdrawal is under 0.1 s of a 356 s
build, and nothing here is within 1 % of either budget.  It costs nothing
at all on an airport with no EAT (the generator returns before any chain
is built).

#### What this lane did NOT do

The five-airport sweep (the orchestrator's); any `--refresh-data`; any
merge to main; any RULINGS entry; any change to `[design] hard_rulings`,
to the objective weights or to `planar/group._eligible` / the
`capture_has_groups` predicate (both another lane's ground — the group
regression was reported, and main fixed it); any third iteration on bar 1
or bar 3; and any new tool — the `eat_ramp_reach` ablation is a value of
`v2_solve_replay`'s existing `--drop-generator`, documented in its
docstring and twinned.

### §37 (5) THE SECOND MECHANISM UNDER THE EAST ROAD (Fable 2026-09-13; RULINGS 2026-09-13ab) — lane `v2roadcap2`

Scout `v2roadcapkclt` on main 064e244e: §37 (1) moved `dsf:pol51` 0.94 m
(+14.22 → +13.28 m) — the DEM grade along its chain is 6.8 %, under the 8 %
road cap, so the longitudinal cap was never what held it (follow ratio
0.287 over 179 m). `dsf:pol82` (owner's shapeID 791) is STILL `apron` at
+11.52 m though §37 (2)'s share rule should have left a face with 2 % of its
perimeter on airside a road. Both attributions were incomplete. The lane
first makes `explain KCLT` run (the `planar.__main__.default_inputs` half of
the 13q chip: honour `O4_AIRPORT_MOD_CACHE_DIR` / the harness redirect as
`build_airport.py` now does — one resolution, not two), then NAMES the rows
holding `dsf:pol51` up (transverse rows to an apron edge? a bank or zone
band? a pad frontage? the `taxi_trend` of a neighbour?) and the PASS that
classes `dsf:pol82` apron (scorer role before §27, or a share read on the
wrong perimeter), and fixes what it names.

BARS (KCLT, ONE build): `dsf:pol51` within 2 m of the DEM over its chain
(follow ratio ≥ 0.8), no service road over 3 m off the DEM airport-wide
(today max +13.28 / −4.25); `dsf:pol82` classed `service_road` on its own
ground; the 1:3 bank at the east edge shrinks with the fill it daylighted;
cockpit CRITICAL motion ≤ 9 (13ab's block) with no new row on the east road;
LEMD role census byte-identical (§37 (2) holds: the 61 apron-side lanes stay
apron); suite twice.

### §32 (4) PURITY OF A POST-SOLVE PROJECTION; §20a THE LAG IS A CONVERGENCE CONDITION; §30 (3) THE PAD PLANE IS PROJECTED (Fable 2026-09-13; RULINGS 2026-09-13ac) — lane `v2settle`

Scout `v2unsettled2`: LEMD's hard set was never settled on merged main (12ac
read the lane tip); the merge's §28 rows (42 one-way rows in the pad columns)
leave a 2–3 cm shortfall of a coupled fixed point under a lag capped at three
rounds (`LAG NOT SETTLED` on every arm, 0.30–0.68 m leader motion) and a
polish that does not converge; and main's worst row (0.129 m at v8276/v8273,
`building` + `graded_strip`) is minted AFTER the solve by `project_zone_bands`
clamping a pad-rim vertex independently of its pad. Three laws, in order:

**§32 (4) PURITY.** A post-solve projection may clamp only a column that
carries NO hard row it does not own. `project_zone_bands` refuses a zone
vertex that also carries a pad-ceiling, pavement-ceiling or runway row and
leaves it to the solve (measured alone: main 0.1292 → 0.0271 m). The same
test guards every projection that follows.

**§20a THE LAG.** The one-way leader/follower fixed point iterates to
`one_way_tol_m` (0.01 m) or REPORTS the named failure — which rows, which
leader, its last move — BEFORE the augmented-Lagrangian polish;
`one_way_max_rounds` becomes a safety ceiling (≥ 20) whose hit is a named
failure, never a silent stop. Raising `polish_rounds_max` / `hard_weight`
is refuted (12u, 13ac: 8 rounds → 2 rows, still unsettled).

**§30 (3) THE PAD PLANE.** If (4) and §20a leave the pad ceiling unsettled,
each pad's rigid plane takes the runway's and the zone band's treatment: a
post-solve per-body QP on its free columns onto its own 1 % ceiling
(`project_runway` / `project_zone_bands` discipline), run after purity so no
two projections share a column; `HARD SET SETTLED` is then a re-read after
every projection, and the design report states it for MERGED MAIN.

Instrument: `v2_solve_replay.py --why-hard` (promoted from the scout's
`hardrows.py`: every violated hard row with its vertices, coordinates,
demanded vs allowed metres).

BARS: LEMD on a fresh main capture `HARD SET SETTLED` and `LAG SETTLED`
(today 5 rows / 0.129 m; lag 0.678 m), v8276/v8273 and v9295/v9696 at ≤
0.02 m; KCLT's three counters re-read on its capture (13ab: 644 rounds, 21
rows / 0.4144 m, lag 0.332 m) SETTLED or the failure named; solve wall not
worse than +10 % (`--runs 3`); runway and zone projections unchanged on pure
columns; suite twice; ONE LEMD build.

**MEASURED (lane `v2settle`, branch `claude/v2settle` off `6fe94558`).** ONE
fresh LEMD capture on merged main (`v2_solve_replay.py --capture LEMD`,
199 s, 23,191 vertices / 1,149 faces), four arms replayed off it, each law
measured ALONE and then combined. Every run `[guard] shared repo UNCHANGED`;
lane-local `O4_AIRPORT_MOD_CACHE_DIR` / `O4_DSF_CACHE_DIR`.

**THE CAPTURE REFUSED TO BE MADE FIRST — a main regression, fixed here.**
The first capture read `pack partition 95 s bodies 14,256 groups 0 relief 0
infeasible 0` against the scout's `groups 9,820 relief 5,036 infeasible
3,163`: the WHOLE PAD GROUP LAW was off at LEMD on merged main, silently,
exit 0. `airport/pack_partition._member_of` builds every pack member with a
POSITIONAL tail, and `5fc707eb` (§16e (2)) inserted `deck_end_stations` into
`model.rebake.Member` ahead of it, sliding `plate_y` onto the `()` meant for
`plate_stations`. `plate_y is not None` is `planar.group._eligible`'s FIRST
test, so all 14,256 bodies were refused — no groups, no relief bodies, no
pad rows to settle. It is the SECOND time an inserted field has shifted that
call (2026-09-11t's `plate_clearance_m`, whose warning comment sat two lines
above). Fixed by naming every field; `tests/auto_patch_v2/test_v2settle.py`
now asserts on the AST that the call passes no positional argument. Nothing
below could be measured until this landed, and it is not this spec's law:
it wants its own ruling.

| arm | hard rows violated / 127,380 | worst | lag | solve wall |
|---|---|---|---|---|
| A base (main + the fix) | 4 | **0.0985 m** | NOT SETTLED, 0.399 m in 3 rounds | 62.1 s |
| B §32 (4) purity ALONE | **3** | **0.0299 m** | NOT SETTLED, 0.399 m in 3 | 68.0 s |
| C §20a ceiling 20 ALONE | 25 | 0.1225 m | NOT SETTLED, 0.289 m in 20 | 118.2 s |
| D purity + ceiling 20 | 23 | 0.0324 m | NOT SETTLED, 0.289 m in 20 | 124.6 s |

**§32 (4) PURITY — LANDED.** Arm B against arm A: the worst hard row
0.0985 → 0.0299 m and the violated set 4 → 3, for exactly ONE column of
4,850 refused (`hard_columns 1`). The corridor's own reading is unchanged to
the digit — worst zone miss `8.1029 → 1.756762 m (owned 0.000000)` on BOTH
arms, 3,322 → 3,321 columns moved — so purity buys the hard set 0.069 m and
costs the zone law nothing. The row that goes is main's worst, the pad-slope
ceiling between the two rim vertices at 40.48527108321,−3.59323243501 /
40.48527109147,−3.59320294912 that the clamp had moved independently. This
matches the scout's `--design-weight zone_projection=0` control (3 rows /
0.0271 m) while keeping the projection ON, which the control could not.

**§20a — HALF LANDED, HALF REFUTED.** The NAMED FAILURE is landed
(`design_report.read_lag_failure` / `lag_failure_line`): the cap's hit now
reports which rows still move, the worst row's generator and ruling, its
LEADER vertex with the canonical lat/lon and that leader's last move, into
the design line and the sidecar — `LAG NOT SETTLED after 20 of 20 round(s):
1,132 of 13,932 one-way rows still move more than 0.01 m; worst 0.2890 m on
row … (pads: structures.building_pad frontage_level …), leader v… at …`.
THE ≥ 20 SAFETY CEILING IS REFUTED, in both combinations: the
leader/follower iteration does not contract at LEMD. Twenty rounds buy
0.110 m of leader motion (0.399 → 0.289 m, tol 0.01), take the violated hard
set from 4 to 25 rows (worst 0.0985 → 0.1225 m; with purity, 3 → 23 and
0.0299 → 0.0324) and cost +90 % of the solve against a +10 % bar. So
`one_way_max_rounds` stays 3 with the measurement recorded in
`law/emit.toml`, and `tests/auto_patch_v2/test_v2lag.py` pins the
refutation. THIS IS A DEVIATION FROM THE SPEC TEXT and is reported for the
Fable author's ruling, not decided in the lane.

**§30 (3) THE PAD PLANE — NOT BUILT, and it could not have reached the
bar.** Its condition is met (`pads` is still unsettled after (4)) but the
residual is under the convergence guard's materiality floor and the co-equal
residual is outside the pad plane's reach. What arm B leaves is three rows:
`pavement_ceiling` 0.0299 m at 40.45850655257,−3.56962843176 (apron|apron),
`pads` 0.0298 m at 40.49433943943,−3.59364375649 (building|building), and
`pavement_ceiling` 0.0200 m at the runway projection's own held bar. Over
`hard_tol_m` 0.02 that is 0.0099 / 0.0098 / 0.0000 m — the pad row is 0.0098
m over, BELOW the 0.01 m elevation materiality floor, and the pavement
ceiling beside it is the same size and is not a pad ceiling, so a per-body
pad QP would leave `HARD SET SETTLED` unreached anyway. Building a third
projection to move one row by 1 cm, when an equal row it cannot touch stays,
is the kind of mechanism the build economy refuses. Reported, not built.

**THE BARS.**

* `HARD SET SETTLED` at LEMD: **NOT MET** — 3 rows, worst 0.0299 m (from 4 /
  0.0985). The residual over the bar is 0.0099 m, under the materiality
  floor: PASS-with-residual, quoted for the owner's sign-off.
* `LAG SETTLED`: **NOT MET and refuted as reachable by the ceiling** — the
  failure is now NAMED instead of silent, which is the half that landed.
* v8276/v8273 (40.48527108321,−3.59323243501): **MET** — 0.0985 m → off the
  violated set entirely (≤ 0.02 m).
* v9295/v9696 (40.49615941816,−3.59037117965 / 40.49424548294,
  −3.59145556585): **MET on arm B** — neither carries a violated row after
  purity (both DO carry one on the refuted ceiling arms C/D, 0.0324 m).
* KCLT's three counters: **NOT MEASURED.** The capture refuses at load —
  the pack DSF `.anchor_bak` is newer than every cached text dump, and the
  only lawful cure is `build_airport.py --refresh-data airport_mod_cache`,
  which this lane's brief forbids. Same refusal `59a67dac` recorded.
* Solve wall +10 %: **MET.** The added work is one pass over the hard set
  inside the projection, and the projection's OWN instrumented wall reads it
  directly: 0.05 / 0.06 / 0.08 s base → 0.07 / 0.08 / 0.09 s with purity,
  +0.02 s on a ~60 s solve = **+0.03 %**. The whole-replay wall cannot
  resolve that: three runs a side, exclusive and foreground, read base 59.8
  / 63.0 / 82.0 s and purity 57.3 / 78.5 / 72.9 s — a ±37 % spread on
  IDENTICAL code (min 59.8 vs 57.3, median 63.0 vs 72.9).
* Runway and zone projections unchanged on pure columns: **MET.** Zone
  columns clamped 4,850 → 4,849 (the one refused column), moved 3,322 →
  3,321, worst zone miss and `owned` identical to six digits. The runway
  projection line is unchanged (24,642 hard rows, 2,827 free columns,
  0.0493 → 0.020000 m, 0.035 m max move) — purity does not touch it.
* Instrument: `v2_solve_replay.py --why-hard [N]` promoted with its
  `tools/INDEX.md` row and twins in `tests/auto_patch_v2/test_v2padceiling.py`.

**THE CLOSING BUILD** — `build_airport.py LEMD --engine v2 --tag v2settle`,
578.6 s, rc 0, `body_sha ccc706451007`, ledger `9b08303ac583`, `shared repo
UNCHANGED by this build (full-surface before/after snapshot)`, v2-verify
1,441 rows. The design report's three lines, verbatim:

    4/127380 hard rows violated (max violation 0.0299 m in 2 polish
    round(s), HARD SET NOT SETTLED)

    13932 one-way rows in 3 lag round(s) (worst leader move 0.399 m, LAG NOT
    SETTLED after 3 of 3 round(s): 2980 of 13932 one-way rows still move more
    than 0.01 m; worst 0.3988 m on row 910478 (rim_level:
    structures.structure_rim frontage_level (service_road; owner 2026-09-10an:
    the rim is flush with the pavement it sits in), leader v19987 at
    40.48346832042,-3.58072988310, v19988 at 40.48346831636,-3.58075347118,
    v19986 at 40.48343689447,-3.58018145109, v20001 at
    40.48349993554,-3.58016377812)

    zone projection (12ag): 10418 corridor rows over 4850 ground vertices,
    4849 columns clamped (0 impure, 1 carrying a foreign hard row, 0 fixed
    vertices, 3321 moved, 47 empty bands), worst zone miss 8.1029 ->
    1.756762 m (owned 0.000000), max move 8.103 m, 0.23 s (optimal)

The build's worst hard row is the replay's, to the digit: 0.0299 m, down
from main's 0.0985. The named lag failure earns its first keep immediately —
LEMD's worst leader is NOT a pad frontage row at all but a
`structures.structure_rim frontage_level` on a SERVICE ROAD at
40.48346832042,−3.58072988310, which `LAG NOT SETTLED` alone could never
have said. (The report counts 4 violated rows where `--why-hard` counts 3:
the third is the runway projection's row sitting EXACTLY on `hard_tol_m`
0.020000, and the two readers round it opposite ways. Cosmetic, named here
so nobody attributes it twice.)

### §37 (5) **MEASURED** (lane `v2roadcap2`, 2026-09-13, branch `claude/v2roadcap2`, base `2002c7dc` + main `05050624`)

ONE `--engine v2` KCLT build, tag **`v2roadcap2`**, 371.1 s engine / 418.5 s
wall, rc 0, `status optimal`, `body_sha a7651dd35206`, artifact ledger
**`0e50c1a921f1`**, `[guard] shared repo UNCHANGED`.  The BASE it is quoted
against is scout `v2roadcapkclt`'s build on main `064e244e` (RULINGS
2026-09-13ab, ledger `2951cfc994bd`) — a DIFFERENT sha, stated because this
lane did not spend a second 7-minute build on a control the ledger already
holds.

#### THE INSTRUMENT

`explain KCLT` and `v2_solve_replay --capture KCLT` RUN in a lane worktree,
under `O4_AIRPORT_MOD_CACHE_DIR` pointed at a copy-on-write overlay, with the
shared repo untouched.  Three halves, of which the lane wrote two:

* the mod-cache resolution — **the owner's own `modcacheguard` chip, main
  `05050624`**, merged into this branch; the lane's parallel implementation
  was dropped in its favour;
* `tools/v2_solve_replay.py --capture` now makes its own PRISTINE pack dump
  through the build entry's own `auto_patch.engine_v2.fresh_pack_dump` (one
  implementation, three callers).  v2 never runs DSFTool itself and KCLT has
  never had a `+35-081.dsf.anchor_bak.*.text`, so without this every capture
  of KCLT refused at `airport/load.py:289` whatever root it resolved;
* `capture_has_groups` read `bool(groups.groups)` and so refused every
  COMPLETE capture of an airport that HAS no groups — **KCLT partitions
  7,163 bodies into 0 groups**.  The predicate is now "the derivation ran";
  `partition is None` is what actually catches a pre-12u capture.

#### (b) `dsf:pol82` — ATTRIBUTED, FIXED, MEASURED

13ab offered two hypotheses ("the scorer's role before §27, or §37 (2)'s
share read on the wrong perimeter").  `explain KCLT --at
35.2208425,-80.9278375` names a third, and it is neither:

> `cell 226: role=apron ... ref=dsf:pol82` — `source_class=lot`,
> `source_reason=5 road(s) reach it (04u), no taxi centreline, no startup,
> width 8.4 m`, `airside_edge_m=20.8`, `airside_edge_flip=1`,
> `airside_edge_round=2`, `airside_edge_was=parking_lot`.

§27's flip is READ CORRECTLY on the right perimeter, and the scorer never
touched the face.  The face was born **`parking_lot`**, so
`airside_edge.airside_edge_flip`'s `was_road[i]` is False and §37 (2)'s share
test — which asks whether a face was born `service_road` / `service_junction`
— never applied; the LOT rule (20.8 m ≥ `airside_edge_min_m` 10 m) flipped it.

Why it was born a lot is `classify/sources.py:_record`.  `narrow_road_width_m`
(12 m) says in its own words "a source polygon at most this wide that carries
ANY road centreline IS the road", but its branch is gated on `carries` =
`road_m ≥ min_road_fraction × HALF-PERIMETER`.  On a ribbon the half-perimeter
is a LENGTH, not a width: `dsf:pol82` is 8.44 m × 601 m, so `carries` demanded
**120.3 m** of mapped centreline and OSM maps **70.5 m** inside it (the
centreline wanders in and out of an 8.4 m page; five roads reach it).  The
strip branch never fired, and the face fell through to the LOT ladder's
weakest rung — `reach > 0`, RULINGS 2026-09-04u.  **Twelve KCLT pages
6.7–10.3 m wide read the same way.**

THE LAW (`[lot] min_lot_width_m` = 11.0 m): a 90-degree car park's minimum
module is one 5.0 m stall row plus one 6.0 m one-way aisle.  In the band
`[service.road_width_m, min_lot_width_m]` = [6.0, 11.0] m a page never reaches
the two WEAKEST lot rungs (`carries_osm`, the 04u `reach` rung), and it is the
ROAD where it carries a road centreline that is not noise
(`osm_roads.min_len_m` 10 m).  MAPPED evidence still outranks the width in
both directions: `amenity=parking` cover, an OSM parking aisle, `aeroway=apron`
cover, an apron name and a 1300 startup all keep their verdicts.  BELOW 6.0 m
the page is an EMIT SLIVER and §27's own sliver class owns it — the first arm
of this rule took 26 LEMD slivers (`dsf:pol255#2` and family, 0.1–0.3 m across)
out of the lot class and moved LEMD's cell count 597 → 578 for no reason
connected to §37 (5); the floor is why the rule is a band.

| KCLT | BASE (13ab, main 064e244e) | §37 (5) (`0e50c1a921f1`) |
|---|---|---|
| `dsf:pol82` role | **`apron`** | **`service_road`** (emitted shapeID 783) |
| `dsf:pol82` off-DEM max | +11.52 m (13ab) / +12.33 m (1.0.324) | **+6.13 m** at 35.2206623,−80.9287108 |
| source classes | lot 60 / open 193 / strip 30 | lot 48 / open 197 / strip 38 (12 moved) |
| cockpit CRITICAL motion | 9 (worst 0.790 m `strip_arc`) | **5** (worst 0.610 m `mid_edge_step [apron\|apron]` at 35.2082082,−80.9412547, a 13ab row) |
| cockpit CRITICAL visual | 2 (pre-§35) | **0** |
| census LAW-TRUE | 11,504 | 11,541 |
| census ADJUDICATED | 3,959 (airside 3,592) | **3,739 (airside 3,357)** |
| road ramps (08r-2) | — | `dsf:pol82` now appears as a ROAD ramp: 0.73 m over 62 m = 1.18 % |

No new row stands on the east road: the census's worst ten are all
`cross_connector` at 35.230,−80.952 (the west side).

CONTROLS, dry (`explain --sources`, classify only, no build):

| | BASE | §37 (5) |
|---|---|---|
| **CYXY** | 120 cells; lot 16 / open 48 / strip 7 | **BYTE-IDENTICAL** — 0 source classes changed. `pav4` (11.5 m, 41 m of road on a 464 m half-perimeter — the case `min_road_fraction` was written for, 09-04j) is ABOVE the floor and unmoved |
| **LEMD** | 597 cells; lot 37 / open 260 / strip 11 | 597 cells; lot 36 / open 260 / strip 12 — **ONE source changed**, `pav119` (8.9 m, 130 m of OSM road) lot → strip |

**§37 (2) HOLDS at LEMD and the bar is quoted honestly**: the 61 apron-side
lanes are `service_road`-born faces and this rule does not touch them; but the
role census is NOT byte-identical — `pav119` moves from `parking_lot` to
`service_road` (both groundside), which is §37 (5) doing exactly what it says
on the one LEMD page in its class.

#### (a) `dsf:pol51` — ATTRIBUTED, EVERY NAMED CANDIDATE REFUTED, NOT FIXED

`dsf:pol51` classifies CORRECTLY: `explain KCLT --at 35.2074982,-80.9296586`
reads `role=service_road side=groundside kind=strip`, `source_class=strip`,
`source_reason=width 11.1 m <= narrow 12, road 385 m` (through 385 m, 4
pieces).  Nothing in the classification holds it up.

The binding read is `tools/v2_solve_replay.py --why-from … --why-at
35.2074982,-80.9296586 --site-radius 25` — `solve.why`'s duals on a pressure
solve of the SAME LP (`|z_pressure − z| max 0.000 m`), off a capture of this
tree:

> `ridge vertex v19369  z 213.15  DEM 199.91 (z-DEM +13.24)`
> `binding rows on v19369 by family: (none: no row binds the vertex — the
> objective holds it)`
> `chain trace: no terminal reached — the objective holds it`

**ZERO rows bind the owner's site.**  Every mechanism §37 (5) named as a
candidate is REFUTED at this vertex: no transverse row to an apron edge, no
zone band, no pad frontage, no neighbour's `taxi_trend`, no bank row.  There
is no cap to relax and no generator to fix.

What holds it is the OBJECTIVE, and the road's own fit target is not where the
road is.  Read off the solved set at the same vertex:

| v19369 | m |
|---|---|
| DEM | 199.91 |
| `PlanarMap.preferred_z` (the core-clamp adapter, `airport/road_profile.preferred_road_z`) | **203.44 (+3.53 over the DEM)** |
| solved z | **213.15 (+13.24 over the DEM, +9.71 over its own target)** |

So the second mechanism is TWO terms, neither of them a constraint:

1. the road's fit TARGET is already +3.53 m up — `cap_lipschitz_profile`'s
   mid-envelope over the whole OSM way, not the terrain under the page (the
   build's own reading: `roads vs core profile: 3096 vertices, mean
   |z−profile| 0.789 m, max 9.890 m, 2710 off beyond materiality in 202 of
   223 faces`);
2. the solve then sits **+9.71 m above that target** with nothing binding it,
   because the smoothing / coupling terms that tie the road to the airside
   FILL beside it outweigh the road's fit weight.  The site read shows the
   region is one smooth surface at the fill's level — 74 vertices within 60 m,
   `z−DEM` mean 6.92 / min 0.94 / max 13.24, roles `building`,
   `graded_strip`, `junction`, `service_road`, **max step over a short edge
   0.02 m**; airport-wide `graded_strip` 12.48 m, `building` 12.61 m,
   `junction` 11.18 m off the DEM.

THE LANE STOPPED HERE AND DID NOT FIX IT.  The fix is an OBJECTIVE-WEIGHT law
— which term wins where a groundside road meets an airside fill — and RULINGS
2026-09-13y already ruled that class a STOP-and-report for a lane ("the
census is not the objective"; the lane did not tune the objective).  Owner law
1a puts a new weight law behind a Fable spec.  The measurement it needs is
already cheap and reproducible: the capture is 76 s and `--why-at` is 93 s.

BARS, stated as measured:

| bar | before | after |
|---|---|---|
| `dsf:pol51` within 2 m of the DEM, follow ratio ≥ 0.8 | 0.287, +13.28 m | **0.283, +13.29 m — NOT MET** (attributed above) |
| no `service_road` over 3 m off the DEM airport-wide | max +13.28 / −4.25 | **max +13.29 / −4.17 — NOT MET** (same mechanism; 5 refs over 3 m, next worst `dsf:pol70` +8.16) |
| `dsf:pol82` classed `service_road` on its own ground | `apron`, +11.52 m | **`service_road`, +6.13 m — ROLE MET, GROUND NOT** (the (a) mechanism) |
| the 1:3 bank at the east edge shrinks with the fill | 401/1,876 load-bearing, 732 foot nodes | **421/2,408 load-bearing, 754 foot nodes — NOT MET**: (a) removed no fill, so the bank has none to give back |
| cockpit CRITICAL motion ≤ 9, no new row on the east road | 9 | **5, none on the east road — MET** |
| LEMD role census byte-identical | — | **ONE source moved (`pav119`) — see above** |
| CYXY control | — | **byte-identical** |

#### CONSUMER CENSUS (owner RULINGS 2026-08-30l) — the source-class change

The change moves faces between two GROUNDSIDE roles (`parking_lot` →
`service_road`) at their single derivation site (`classify/sources.py:_record`,
the source classifier), so `side` stays a pure function of `role` and no
consumer is edited.

| # | consumer | reads | RULE |
|---|---|---|---|
| S1 | `classify/roles.classify` source branch | `src.cls` | THE ONE derivation site — `strip` → `service_road`, `lot` → `parking_lot`, unchanged code. |
| S2 | `classify/airside_edge.airside_edge_flip` | the BORN role (`_ROAD_ROLES`) | UNCHANGED CODE, and this is the point: a face born a road now takes §37 (2)'s SHARE test. `dsf:pol82` 20.8 m of a 1,203 m perimeter = 1.7 % < 0.2 → no flip. |
| S3 | `law.tables.role_side` | the role | UNAFFECTED — both roles are groundside. |
| S4 | `constraints/roads.road_family_roles` (`families.road_cross_section.roles`) | the role | The face GAINS the `road_cross_section` family and the 8 % / 2 % road caps, and LOSES the lot's 5 % cap. This is the intent (§37 (1)); measured: `road_cross_section` 733 verify rows, `lateral_contiguity` 20, no new census family. |
| S5 | `airport/road_profile.road_family_vertices` / `axis_roles` | the role | The face gains a core-clamp fit target (`road_fit_vertices` 1,748 → 2,585). Intended: a road is fitted to the core's profile, a lot is not. |
| S6 | §20 pad levels (`constraints/pads`) / §28 frontages (`constraints/pad_frontage_gs`) | `parking_lot` by class tag | A frontage neighbour changes CLASS but not side; `groundside_frontage` 164 → 148 design-target rows, max miss 1.384 → 0.717 m. |
| S7 | `tools/role_edge_census.py` `_GROUNDSIDE_ROLES` | the emitted patch | UNAFFECTED — both roles are in the set; the LOT-class split moves, which is what it is there to report. |
| S8 | `tools/road_terrain_conformance.py` `_ROAD_FAMILY_ROLES` (= `grade_law.ROAD_ROLES`) | the emitted patch | The face ENTERS the road population: KCLT road vertices 2,533, and `dsf:pol82` is now readable as a road (`--by-ref`). |
| S9 | `check_grade.law_role` / `LAW_FAMILIES` | the way tag | UNCHANGED — no family added, no key added; the harness census reads it as a road. |
| S10 | `emit/osm_adapter` oracle aliases | the role | UNCHANGED — `service_road` already has its alias. |
| S11 | §27 `_LOT_SLIVER_RADIUS_M` | the face | UNTOUCHED, deliberately: the 6.0 m floor keeps every emit sliver on the old path (the 26-LEMD-sliver arm above). |
| S12 | v1 `auto_patch/` | its own classifier | UNTOUCHED — §37 is v2 law. |

#### Build-time impact statement

`_record` gains two comparisons per source polygon (596 at KCLT); the classify
stage is unmeasurable against it.  The road population grows
(`road_fit_vertices` 1,748 → 2,585), which is rows the solve already prices for
every other road.  KCLT engine wall 373.3 s (13ab, main) → 371.1 s here, on a
machine running other lanes — no A/B is quoted (standing law).  Nothing is
within 1 % of either budget.

#### What this lane did NOT do

The (a) fix (attributed to the objective; a weight law needs a Fable spec — see
above); any `--refresh-data`; the five-airport sweep; any LEMD or CYXY BUILD
(the LEMD and CYXY arms above are DRY classify reads, as the brief required);
a fresh KCLT BASE build (13ab's ledger `2951cfc994bd` is quoted instead, and
its sha is stated); `constraints/eat.py` or the EAT loop (lane `v2eatramp`);
any merge; any RULINGS entry.

## §38 THE TILE SEAM IS A PIN (owner 2026-07-04 / 2026-07-24 / 2026-07-26 / RULINGS 2026-09-13ah; Fable 2026-09-13) — lane `v2seampin`

Owner (13ah): seam boundaries "must be kept at DEM and treated as an anchor
like CIFP thresholds that everything else grades to." `constraints/seams.py`
(M3a) minted the seam as a PREFERENCE (`Linear.soft`) after the SPLP class of
2026-09-04 (runway edge 55.51 m and strip vertex 57.00 m on one seam line);
a deviating vertex was reported as a "seam residual" and not published as a
pin. Overruled.

1. **A SEAM VERTEX IS A `Pin`** — the same object as a CIFP threshold: its
   value is its own tile's baked DEM sample (the value the neighbouring
   tile's mesh meets), its column is eliminated (`solve/rows._reduce`), it
   holds exactly, it is published in the sidecar as `seam_pins` and the
   census prices pin↔free pairs at the body cap. Every seam-band vertex of
   every role, the runway included.
2. **EVERYTHING GRADES TO THE SEAM.** Between two seam pins the pin↔pin
   row is exempt (terrain against terrain, `constraints.seam_exempt`); the
   free vertices between them take the hard family re-fitted between the
   pins — the runway chord between a threshold and a seam pin, or between
   two seam pins, exactly as §21.2 re-fits between thresholds. A family
   that cannot be met between two pins is NAMED in the design report (the
   two pins, the family, demanded vs allowed metres) — never a moved pin,
   never a silent residual, never a preference.
3. **NO BANK ALONG A SEAM.** The coverage edge at a tile seam is a pin line
   already at the DEM; §37 (3)'s bank is not derived there, and a bank
   chain crossing a seam line is a defect the census names
   (`bank_across_seam`).
4. **ONE AIRPORT, ONE SOLVE.** A seam-straddling airport is solved once on
   the whole map and written as per-tile pieces (§9.2 A5/C3); the two pieces
   share every seam vertex by identity (the 11-dp lat/lon join carries the
   node id), so the runway meets itself across the seam at the pin.

BARS (SPLP, both tiles, after scout `v2splpseam`'s attribution): every seam
vertex at its DEM sample (0 seam residuals); runway z on either side of the
seam identical at every shared vertex; no `bank_foot` chain within
`half_width_m` of the meridian; the texture tear at −12.1610968, −77.0000457
attributed (mesh side or patch side) and, if patch side, gone; cockpit block
on both pieces with no CRITICAL row on the seam; LEMD/KCLT/CYXY (single-tile)
byte-identical; the design report's settled lines; suite twice.

### §33 (4) TWO-SIDED, §34 (4)–(6) AMENDED, §19.2 (2) AMENDED (Fable 2026-09-13; RULINGS 2026-09-13ai) — lane `v2rampwalk` round 2

- **§33 (4) A DECK END IS AN EQUALITY.** The deck end takes the level of the
  pavement it connects to (`deck_ends`'s face — LEMD `bridge_deck:-6288` →
  `pav92` east, the road west) within `split_tol_m` as an EQUALITY, not a
  lower bound; the deck's own profile runs between its two end levels under
  the road cap. Bar: item 9's deck within 0.3 m of the apron at its east end
  (today 1.66 m) and of the road at its west end.
- **§34 (4) A TRIMMED BOUNDARY IS DENSIFIED ON A SLOPE.** Where the ribbon
  trim's boundary runs across DEM relief, its stations are spaced so that no
  ring edge carries more than `visual_m` of DEM change (below the chord cap).
  Bar: the 8.50 m edge at 40.5331907, −3.5748496 (`zone2#23`, 18R/36L north)
  → ≤ 0.5 m; cockpit CRITICAL visual worst back under round 1's 1.63 m.
- **§34 (5) THE PORTAL RIM UNDER A DECK TAKES THE TAXI CELL'S SOLVED SURFACE.**
  The DEM carries no bridge, so `DEM(mouth)` is the road in the cutting; the
  abutment rim vertex takes an equality row to the deck cell's surface at the
  same plan point (offset 0 — the `frontage_level` Linear's mechanism) and the
  mouth's ramp floor descends from that rim. `structure_underpass.py` is
  ARMED. Bar: LEMD F-6 (40.4610903 / 40.4612284, −3.54467): mouths and ramps
  both sides, CRITICAL visual at the site 0 (armed today: 3 → 10),
  `strip_seam_tear` 0; KCLT item 3 (35.2022266, −80.9404106 /
  35.2013838, −80.9404162) mouths and ramps both sides.
- **§34 (6) THE RAMP PROFILE SITS UNDER THE CAP.** The monotone profile
  targets `ramp_max_grade − hard_tol_m / L` per edge so the emitted rows read
  under the cap after 2-dp rounding. Bar: the +847 `within_shape` rows at
  8.02 % → 0 (round 1: 2,769 → 3,616).
- **§19.2 (2)** "flush at the road's OUTER edge" reads INNER edge for a
  cell-less road (§34 (4) subtracts the ribbon whether or not a cell exists).

### §37 (6) A GROUNDSIDE ROAD IS A RAMP FROM ITS AIRSIDE CONTACT TO THE DEM (Fable 2026-09-13; RULINGS 2026-09-13aj) — lane `v2roadramp`

Lane `v2roadcap2`: KCLT `dsf:pol51` (owner item 5) is held +13.24 m over the
DEM by NO row — `--why-at` on a pressure solve names zero binding rows; the
objective holds it, +9.71 m above its own `preferred_road_z` target (203.44),
welded by smoothness to the airside fill beside it (`graded_strip` 12.48 /
`building` 12.61 m off the DEM). A weight contest is not a law.

6. **THE ROAD'S PROFILE IS DERIVED ALONG ITS ROUTE.** From each AIRSIDE
   CONTACT of a groundside road (the mouth where it meets an apron, pad or
   lot; that level is the airside's — airside is king), the road target along
   route distance s is `max(DEM(s), z_contact − road_cap × s)`: it descends at
   the road cap until it meets the DEM and follows the DEM from there (and
   climbs at the cap where the DEM rises above the contact); between two
   contacts the two ramps meet at their higher envelope; a road with no
   airside contact targets the DEM. The target is a DESIGN TARGET (§31 (3)
   class, design-target weight — not the `preferred_road_z` soft fit, which
   this supersedes for groundside roads) with a HARD ceiling
   `z ≤ target + visual_m`, so smoothness can never lift the road back onto
   the fill. The road's own longitudinal cap (§37 (1)) and cross-section
   stand; the bank (§37 (3)) then daylights only the short fill at the
   contact. §34 (1) and §36 (5) are the same law for tunnel and EAT ramps.

Consumer census first (owner 2026-08-30l): every reader of `preferred_road_z`,
the road envelope / core clamp, `road_law_caps`, the mouth (§27), the bank's
load-bearing test, `road_terrain_conformance`.

BARS (KCLT, ONE build, base = 3e7dd382 with `--base-arm`): `dsf:pol51` follow
ratio 0.283 → ≥ 0.8 and within 2 m of the DEM over its chain (`--by-ref`);
no service road > 3 m off the DEM airport-wide (today 5 refs, worst +13.29);
`dsf:pol82` on its ground (+6.13 → ≤ 0.5); the east-edge bank shrinks with
the fill (`BankReport.line()`, load-bearing stations 421 → fewer, named);
cockpit CRITICAL motion ≤ 5 with no new east-road row; LEMD dry replay: the
61 apron-side lanes untouched (apron), every groundside road whose worst
off-DEM changes by > 0.5 m NAMED with its contact; CYXY control byte-identical
or named; solve settled lines quoted; suite twice.



#### §37 (6) CONSUMER CENSUS (owner RULINGS 2026-08-30l), completed BEFORE any consumer was edited — lane `v2roadramp`

**A. EVERY READER OF `preferred_road_z` / `PlanarMap.preferred_z`.**

| # | consumer | reads | RULE |
|---|---|---|---|
| P1 | `pipeline/build.py:499` (the only production caller) | `preferred_road_z` | **EDITED**: `with_road_ramp` runs LAST of the target channels (after the runway chord, the taxi trend, the apron trend), because a MOUTH's level is read from the airside's own published target where it carries one. It is the ONE superseding site. |
| P2 | `solve/design.py:295` — `road_fit` rows at `[design] road` (3) | `pm.preferred_z` | UNCHANGED CODE. A ramp-governed vertex is simply ABSENT, so it carries one target, not two in a weight contest (KCLT: `road_fit_vertices` 2,314 → 825). |
| P3 | `solve/why.py:362` — the "what holds this vertex" narrative | `pm.preferred_z.get(v)` | UNCHANGED. The ramp is ROWS (`Linear` + `Band`), so `why` names them as binding rows under the `road_ramp` generator instead of the "its design target" prose branch. |
| P4 | `constraints/taxi_trend.py:303` | `preferred_z` at a chain's RUNWAY pins | UNAFFECTED — only runway-contact vertices, never a road vertex; and it runs BEFORE the withdrawal. |
| P5 | `constraints/runway_chord.py:567-575` (merges the chord into `preferred_z`) | the mapping | UNAFFECTED — runway vertices are never road-owned, and it runs BEFORE the withdrawal. |
| P6 | `verify/roads.road_profile_agreement` ("roads vs core profile") | `pm.preferred_z` | **CHANGED IN MEANING, a report figure**: it now measures the roads the ramp does NOT govern (KCLT arm: 1,336 vertices, mean 0.310 m, max 3.940 m). The agreement with the core clamp is no longer the road's contract where §37 (6) supersedes it. |
| P7 | `model/planar.PlanarMap` | the target channels | **ADDED** `road_ramp_z`, beside `taxi_trend_z` / `apron_trend_z` (own channel, own weight). A capture pickled before it cannot be replayed — re-capture (the 12u rule). |
| P8 | `tools/v2_solve_replay.py::_targets` | the build's channel order | **EDITED** — publishes the ramp last, so a replay arm solves the build's problem. |
| P9 | `airport/road_profile.core_profiles` | the ways + the answer index | **EDITED, additive**: `RoadProfiles.per_face` now carries `core_profiles`' second return, so §37 (6) reads the SAME profiles `preferred_road_z` built (one construction per build, not two). |
| P10 | `tests/test_m3c_roads.py`, `test_v2smooth.py`, `test_v2padceiling.py` | `preferred_z` | UNAFFECTED — they do not run the publisher; all green. |

**B. THE ROAD ENVELOPE / THE CORE CLAMP, `road_law_caps`, THE MOUTH, THE BANK, THE INSTRUMENT.**

| # | consumer | RULE |
|---|---|---|
| C1 | the core clamp (`clamp_profile` = `O4_Vector_Utils.cap_lipschitz_profile`) | UNCHANGED. §37 (6) reads the ways' `dem`, not their clamped `z`: the RAMP is the profile, and the clamp stays the core's own answer for every road the ramp does not govern (P6) and for the core-levelled roads outside the patch. |
| C2 | `constraints/roads.road_law_caps` and every one of §37.1 A's L1–L17 | UNAFFECTED — §37 (6) neither reads nor writes the contiguity cap; §37 (1)'s longitudinal cap and the cross-section still shape the face. |
| C3 | §27 `airside_edge_flip` / `classify/roles` (THE MOUTH) | UNAFFECTED — the ramp reads its contacts from the planar weld (`roles_at`, an airside `role_side`), never from the flip. A face the flip makes an apron leaves the road population by role; `dsf:pol82`, which §37 (5) returned to `service_road`, is governed (fill +6.17 → +0.80 m). MEASURED: 0 apron-face vertices carry a ramp target at KCLT (78 apron faces), LEMD (159) or CYXY (16). |
| C4 | `emit/bank.py` `_inner` / `material_runs` (the load-bearing test) | UNCHANGED CODE — the bank is derived from the SOLVED surface, so it shrinks with the fill it daylighted (measured below). |
| C5 | `tools/road_terrain_conformance.py` (`--by-ref`, `--site`) | UNAFFECTED — it reads the emitted patch. It is the instrument both arms are read with. |
| C6 | `solve/design.is_hard` / `[design] hard_rulings` / `solve/project.py` | **EDITED, additive**: the ceiling's ruling head `roads.groundside_road ramp ceiling` is registered, so the ceiling is a CONSTRAINT of the active set (KCLT: hard rows 133,148 → 134,953 on the replay = +1,805, one per governed vertex). The runway and zone projections are untouched (they select their own families). |
| C7 | `planar/structures.py` decks (`bridge_deck:<way>`, role `service_road`) | **EXCLUDED FROM THE POPULATION** (`airport/road_ramp.deck_refs`, read off `pm.structures`, never off the ref string). A deck's level is STATED by the structure (§33 (4): tied to its two mapped ends, over the ramp's clearance). Without the exclusion the ramp pulled LEMD's decks to the terrain under the crossing: `bridge_deck:-3923` −4.72 m, `-3731` −4.20 m, KCLT `-3595` −2.84 m from their own profile — a hard ceiling against a structure's own datum. MEASURED after: every LEMD deck moves ≤ 0.02 m. **This scoping is not in §37 (6)'s text: it is the census's finding and wants Fable's ruling.** |

### §37 (6) **MEASURED** (lane `v2roadramp`, 2026-09-13, branch `claude/v2roadramp`, base `864e7577`)

ONE `--engine v2 --patch-only` KCLT build, tag **`v2roadramp`**, 426.5 s,
rc 0, `status feasible`, `body_sha 589f23c23ba1`, artifact ledger
**`497728ff051c`**, `[guard] shared repo UNCHANGED`.  The BASE is the
SHARED control `ctl-KCLT` (lane `v2seampinctl`, tree `c29238cd3fa8` =
main `864e7577`, ledger **`8e6288563291`**, `body_sha bb022a77f067`),
SERVED from the artifact ledger — no control was rebuilt.  Same corpus
`99f8ad879c83` on both arms.  Synthetic-first: two solve replays off one
KCLT capture (89 s) before the build, plus LEMD and CYXY replay pairs.

#### THE OWNER'S SITE — item 5, `dsf:pol51` (`road_terrain_conformance --site`, radius 60 m)

| | BASE `8e6288563291` | §37 (6) `497728ff051c` |
|---|---|---|
| chain span / DEM relief | 179.3 m / 12.15 m | (same chain) |
| emitted relief | 3.57 m | **10.41 m** |
| **FOLLOW RATIO** | **0.294** | **0.857** (bar ≥ 0.8 **MET**) |
| highest FILL | **+13.31 m** at 35.2074982,−80.9296586 | **+1.62 m** |
| deepest CUT | 0.86 m | **5.58 m** |
| \|emitted−DEM\| median / p95 | 0.43 / 10.54 m | 2.33 / 4.11 m |

The road no longer flies: the owner's coordinate reads **+13.31 → +1.62 m**
of fill and the chain rides the hill.  "Within 2 m of the DEM over its
chain" is **NOT met** — the residual is a CUT, attributed below.

#### AIRPORT-WIDE ROADS (`--by-ref`, both arms, same options)

| ref | BASE fill / cut | §37 (6) fill / cut |
|---|---|---|
| `dsf:pol51` | **+13.31** / 1.64 | +1.62 / **6.78** |
| `dsf:pol70` | +8.17 / −1.24 | +0.51 / 3.88 |
| `dsf:pol50` | +6.53 / 1.32 | +0.62 / 6.07 |
| `dsf:pol82` (item 7) | +6.17 / 1.41 | **+0.80** / 3.66 |
| `dsf:pol63` | +3.84 / 0.09 | under 2 m |
| `dsf:pol39` | +3.64 / 3.36 | +0.96 / 3.26 |
| `dsf:pol86` / `route19` / `route18` / `dsf:pol62` | +3.46 / +3.46 / +3.16 / +3.25 | all under 2 m |
| `bridge_deck:-3595` (EXCLUDED, C7) | +4.09 / 0.26 | +4.11 / 0.19 |

Whole population, 2,533 road vertices: \|emitted−DEM\| median **0.708 →
0.352 m**, p95 3.348 → 3.510, worst 4.17 → 6.78.  **Refs over 3 m of FILL:
9 → 1, and the one is the bridge deck the law excludes.**  Refs over 3 m
of CUT: 3 → 8.  The bar as written ("no service road > 3 m off the DEM";
base "5 refs, worst +13.29") is **NOT met on the |off-DEM| reading**: the
worst halves (13.31 → 6.78) and the FILL class is gone, the CUT class
grows.  `dsf:pol82` **+6.13/+6.17 → +0.80 m: MET.**

#### THE COCKPIT BLOCK (harness census, both patches)

| | BASE | §37 (6) |
|---|---|---|
| CRITICAL **motion** | **12** — worst 0.920 m over 59.87 m `strip_arc [runway|runway]` at 35.2239471,−80.9530979 | **8** — worst 0.620 m over 0.90 m `mid_edge_step [apron|apron]` at 35.2082082,−80.9412547 |
| CRITICAL **visual** | 0 | **0** |
| new row on the east road | — | **none** (every critical row is an apron/runway row, none within 500 m of the east access road) |

Motion 12 → 8 with the worst row 0.920 → 0.620 m; the bar (≤ 5) is NOT
met, and no critical row is a road row in either arm.

#### THE BANK (§37 (3)) — it shrinks with the fill

Arm build's `BankReport.line()`: 69 rings, 7,764 boundary vertices → **665
foot nodes**, LOAD-BEARING **342 / 2,430** stations (2,088 under the 1.65 m
floor; 27 rings carry no bank at all), 63 open chains, longest chord 30.0 m.
Read on the two PATCHES (the same geometry count on both arms): bank_foot
ways 72 → 69, foot nodes **776 → 671**; **within 300 m of the owner's
bank_foot coordinate 35.2077804,−80.928713: 89 → 61 nodes** (−31 %), now
in 12 short chains instead of 5 long ones.

#### THE CENSUS MOVED THE WRONG WAY, AND THE MECHANISM IS §37 (1)'s CHORD

| harness census | BASE | §37 (6) |
|---|---|---|
| LAW-TRUE | 11,809 | 17,030 |
| **ADJUDICATED** | **3,900** (airside 3,496 / gs 404) | **7,622** (airside 5,517 / gs 2,105) |
| `within_shape` | 8,934 | 11,540 |
| `road_cross_section` | 310 | **1,691** |
| `airside_no_step` | 718 | 1,374 |
| `transverse` | 114 | 470 |
| v2 verify `road_cross_section` | 763 | **5,263** |

ATTRIBUTION, measured on the capture before the build and not inferred:
**§37 (1) prices a road ring's pairs by their PLAN CHORD, and a road page
is not a plan chord.**  For every face carrying vertices over 3 m from
their ramp target, the face's own worst pair is one the within-shape /
cross-section law forbids the target to reach — and **7 of the 10 worst
are followable ALONG THE ROUTE at the road's own 8 % cap**:

| face | ref | worst pair | \|Δtarget\| | plan chord (cap) | ROUTE distance (8 % bound) |
|---|---|---|---|---|---|
| 827 | `dsf:pol51` | v16797–v16836 | 13.55 m | 45.6 m (long. 3.65 m) | **279.9 m (22.39 m) — followable** |
| 777 | `dsf:pol50` | v15699–v15740 | 10.07 m | 161.4 m (transv. 3.23 m) | **440.4 m (35.23 m) — followable** |
| 792 | `dsf:pol70` | v15484–v15955 | 7.66 m | 64.0 m (transv. 1.28 m) | **263.4 m — followable** |
| 764 | `dsf:pol53` | v15415–v15474 | 3.40 m | 22.3 m (transv. 0.45 m) | **575.8 m — followable** |
| 828 | `dsf:pol51` | v16797–v16791 | 13.30 m | 77.6 m (6.21 m) | 87.0 m (6.96 m) — steeper than the cap along the route too |

`dsf:pol51` is a HAIRPIN: two branches of one page 45 m apart in plan and
280 m apart along the road, with 13.6 m of terrain between them.  Before
§37 (6) both branches floated together on the airside fill and every pair
was satisfied; with the lower branch on its ground (a HARD ceiling) the
pair rows drag the upper branch down — `--why-at 35.2073045,−80.9301802`
on a pressure solve of the same LP names exactly two families holding it:
`road_within_shape` (4 rows, cap 8 % × 45.6 m = 3.65 m, chain terminal
v16797 at the §37 (6) ceiling) and `road_cross_section` (9 rows, cap 2 % ×
44.2 m).  **This is the withdrawn-chord law (owner 2026-09-05aa) stated
for the taxi family and NOT for the road family**, and it is why the cut
class grows and why `road_cross_section` reports 5,263 rows.  §37 (6)'s
brief says §37 (1) and the cross-section STAND, so this lane did not touch
them: it is the intent question below, with its numbers.

#### LEMD — dry read + a replay pair on one capture (239 s), base tree `864e7577` vs this branch

* **The 61 apron-side lanes are UNTOUCHED**: 0 of 159 apron faces carry a
  ramp target (the population is road-family faces by role; §27's flip is
  read, never re-derived — C3).
* LEMD's road faces are almost entirely BRIDGE DECKS: 13 decks, and after
  C7's exclusion only **6 groundside-road vertices** are governed, each
  within **0.02 m** of the DEM and of its core fit.
* Solved arms (`--solved-out`, same capture, base tree vs branch): whole
  surface max |arm − base| **1.231 m**, 44 vertices over 0.5 m; **no
  groundside road's worst off-DEM moves by more than 0.5 m** — the two that
  move at all are `route3` (worst 1.67 → 1.47 m, move 0.23 m) and `route6`
  (1.63 → 1.41, 0.22 m), both toward the DEM, both contacting the T4
  apron; every `bridge_deck:*` moves ≤ 0.02 m.  `service_road` max off-DEM
  9.31 m in BOTH arms (a deck).  The solve went `feasible` → `optimal`.

#### CYXY — the control, NOT byte-identical, named

Dry: 314 governed vertices, 34 mouths, and the target is within **0.01 m**
of the core clamp everywhere (one vertex, `route6`).  Replay pair on one
capture: whole surface max |arm − base| **1.378 m**, 63 vertices over
0.5 m; `service_road` max off-DEM **2.43 → 2.06 m** and vertices over
0.5 m **65 → 30**; apron 4.09 → 3.99; `graded_strip` 5.11 both.  Every
road ref moves TOWARD its ground: `dsf:pol120` 1.38 → 0.52, `pav29` 1.30 →
0.29, `pav0` 1.36 → 0.38, `pav30` 1.01 → 0.34, `dsf:pol121` 1.90 → 1.30,
`route13` 1.81 → 1.10.  The solve went `feasible` → `optimal`.

#### THE SOLVE'S SETTLED LINES

| | BASE (replay) | §37 (6) (replay) | §37 (6) (the build) |
|---|---|---|---|
| status | optimal | feasible | feasible |
| hard rows violated | 1 / 133,148 (max 0.0215 m) | **0 / 134,953 (max 0.0200 m, HARD SET SETTLED)** | 7 / 243,511 (max 0.0458 m, NOT SETTLED) |
| lag | NOT SETTLED, worst leader move 0.365 m | NOT SETTLED, 0.359 m | NOT SETTLED, 0.649 m |
| active-set | 717 rounds, settled | 567 rounds, SET NOT SETTLED (229 flips, worst 0.467 m) | 495 rounds, SET NOT SETTLED (403 flips, worst 0.048 m) |
| road ramp targets | — | — | 1,876 of 3,910 unmet, max 6.648 m |

The build's unsettled counters are KCLT's own standing instance of
RULINGS 2026-09-13y (B) / 13ab; the ramp adds 1,955 hard ceilings to it.

#### Build-time impact statement

The derivation is one Dijkstra over the road vertices plus one answer per
governed vertex, reading the road profiles `preferred_road_z` ALREADY
built (P9, so no second `core_profiles`): **1.4 s measured standalone at
KCLT including a cold `core_profiles`, and the profiles are shared in the
build**.  The solve carries 1,955 extra targets and 1,955 hard ceilings
(rows 62,804 → 73,115 on the replay, wall 85 → 68 s there; the build's
solve is 104.6 s).  Whole-build wall 426.5 s against the control's 463.3 s,
measured on a machine running other lanes — no A/B is claimed (standing
law: never one run per side).

#### The intent question (measured, for the owner / Fable)

**A ROAD PAGE IS PRICED BY ITS PLAN CHORD; A ROAD IS WALKED.**  Owner
2026-09-05aa withdrew the chord reading for the TAXI family ("the route
graph follows every curve; never a chord across open pavement"); the road
family still prices ALL PAIRS of a ring by plan distance, and the
cross-section cap (2 %) by plan DIRECTION against the ring's long axis.
On a hairpin or a page that follows a hillside, that forbids the road to
stand on the ground §37 (6) sends it to: 7 of the 10 worst pairs are
followable along the route at the road's own 8 % cap (table above), and
the price of holding them is `dsf:pol51` cut 6.78 m into its hill and
`road_cross_section` 763 → 5,263 verify rows.  Does the withdrawn-chord
law extend to the road family (a road pair priced over the ROUTE between
its stations, as §37 (6) prices the target), or does the road page keep
its plan-chord law and §37 (6) yield where the two disagree?

#### What this lane did NOT do

The five-airport sweep (the orchestrator's); any `--refresh-data`; any
merge into main; any RULINGS entry; any change to §37 (1)'s caps, the
cross-section, `road_law_caps`, the bank, §27's flip or anything in
`solve/`, `constraints/eat.py`, `planar/structures*.py`, `planar/zones.py`
or `constraints/structures.py` (the parallel lanes' files); a second KCLT
build (the attempt cap: two replay arms, then one build); a LEMD or CYXY
BUILD (both were read as replay pairs on one capture each, which is the
dry frame the brief asked for); a new tool, so no `tools/INDEX.md` row.
### §38 AMENDED after scout `v2splpseam` (Fable 2026-09-13; RULINGS 2026-09-13am) — lane `v2seampin`

Measured on SPLP (864e7577): one solve, per-tile pieces, 0 shared vertices
between the pieces (the west piece ends at −5.0 m, the east begins at +1.8 m;
the 10 m band is the mesh's draped DEM); seam pass oscillates 45 → 28 → 27 →
28 …, `27/150 vertices on the DEM; 123 residual, max 3.430 m` (a 3 m berm
10 m wide along the seam through the runway strip); runway band-edge vertices
+0.51 … +0.63 m above the DEM (the dip and rise the owner reads); the
relax arm names the graded-strip ZONE BAND as what holds the seam off its DEM;
`_Chord.knots` takes only crossing pins; bank chain −10045 has 2 nodes inside
the band; the coverage slit is closed only because `bank_min_width_m` ==
`seam.half_width_m` (5.0 == 5.0).

1. **(1) stands.** `constraints/seams.py` mints `Pin`; the seam pass in
   `pipeline/build.py` (598–660) is DELETED — a pin needs no pass. The
   sidecar publishes ALL seam pins (150 at SPLP, not the 27 honoured).
2. **(2) names its mechanism.** Between two seam pins the graded-strip zone
   band YIELDS (a soft escalation group, the `runway_profile` end-zone
   pattern); the runway chord takes seam pins as KNOTS in `_Chord.knots`
   exactly as `runway_crossing_pins` are taken, so the end-zone preference
   absorbs the curvature between a threshold and a seam pin. A family still
   unmet between two pins is NAMED (pins, family, demanded vs allowed).
3. **(3) at one derivation site.** `emit/bank.py` cuts the banked region by
   the seam bands beside the water and terrain-edge cuts, and unions the
   seam bands into the coverage EXPLICITLY before the collar; the equality
   of the two 5.0 m constants is no longer load-bearing.
4. **(4) REWRITTEN — ONE AIRPORT, ONE SOLVE, PER-TILE PIECES.** The band is
   draped DEM; the pins are the band-edge vertices at ±`half_width_m`, each
   at its own tile's DEM sample, so each piece meets the drape at zero step.
5. **NEW CENSUS FAMILIES** in `check_grade.LAW_FAMILIES` (twins in
   `test_harness.py`): `seam_residual` — every band-edge vertex against its
   own DEM sample (CRITICAL motion on runway/taxi roles, visual elsewhere);
   `bank_across_seam` — any bank foot node within `half_width_m`.

BARS (SPLP, one build, `--base-arm` 864e7577): `seam: 150/150 vertices on the
DEM` (0 residuals); runway band-edge vertices z−DEM ≤ 0.05 m (today +0.51 …
+0.63); vertex 1408 at 54.50 (today 51.07); no bank foot node within
`half_width_m` (today 2); `seam_residual` 0 and `bank_across_seam` 0 (both
> 0 on the base arm, proving the instruments); cockpit CRITICAL: no row on
the seam; solve settled lines quoted both arms; LEMD / KCLT / CYXY dry
replays byte-identical (no seam vertices); suite twice. The mesh-side
cluster (16,298 border nodes in 1.92 m at lat −12.1609306 on tile −13−077)
is scout `v2splpmesh`'s, not this lane's.

### §38 MEASURED (lane `v2seampin`, base b78f8f32, SPLP `--engine v2`)

**THE CONSUMER CENSUS FIRST** (owner 2026-08-30l). Every reader of the
seam region, ruled in one table before any consumer was edited:

| Reader | file:site | what it read | ruling |
|---|---|---|---|
| the band's DERIVATION | `planar/overlay.py:305 seam_bands` | buffers the sampled graticule line by `half_width_m` of FRAME metre | **CHANGED (13an b)**: each edge is its own polyline at the graticule value ± the DEGREES that measure `half_width_m` there; the band is the polygon between them. The single derivation site. |
| the band's faces | `planar/overlay.py:153/171` | faces inside a band are dropped (`dropped_seam_faces 34`) | unchanged |
| the band's VERTICES | `planar/build.py:314 _seam_vertices` | the band boundary's noded vertices → `PlanarMap.seam_vertices` | unchanged (150 → 149 under the symmetric band) |
| the band's GEOMETRY downstream | — | nothing carried it; `emit/bank.py` could not see it | **NEW**: `PlanarMap.seam_band_rings`, written by `planar/build.py` from `arr.seam_bands` — the record, so no consumer re-derives the graticule |
| the seam ROW | `constraints/seams.py seam_pins` | `Linear.soft` preference, one group per vertex | **CHANGED (1)**: `Pin` — column eliminated, held exactly |
| the pair exemption | `constraints/__init__.py seam_exempt` | dropped rows whose every vertex was an honoured seam pin; took a `honoured` set | **CHANGED**: no honoured set; adds the SENIOR-pin withdrawal (a CIFP threshold outranks the seam: 1 vertex at SPLP) and the (2) zone-band yield |
| the seam PASS | `pipeline/build.py:598-660`, `pipeline/why.py:90-101` | re-solved up to 6× to a fixed point of the honoured set | **DELETED** (oscillated 45 → 28 → 27 → 28 …; 12.0 s of a 24.0 s build) |
| `Config.seam_passes_max` | `pipeline/build.py:53` | the pass's cap | **DELETED** |
| the generator plumbing | `constraints.generate`, `pipeline/shapes.shape_constraints` | `seam_honoured` parameter | **DELETED**; replaced by `yielded_out` (the rows the seam made yield, for the report) |
| the SIDECAR | `pipeline/publication.py:160` | `seam_pins` = the HONOURED subset, `[lat, lon]` | **CHANGED (1)**: every pin, `[lat, lon, dem_z]`; new key `seam_half_width_m` |
| the sidecar KEY register | `emit/osm_adapter.py:77 SIDECAR_KEYS` | — | **NEW** `seam_half_width_m` |
| the census's seam read | `check_grade.py:723 _seam_nids_from_pins` | unpacked `(lat, lon)` | **CHANGED**: reads by position, so 2- and 3-element pins both work (a pre-§38 patch is unchanged) |
| the runway CHORD | `constraints/runway_chord.py:393-408 _Chord.knots` | crossing pins only; a seam vertex was never a control point | **CHANGED (2)**: `_with_seam_knots` adds this runway's own ridge seam pins as knots, at both chord sites |
| the graded-strip ZONE BAND | `constraints/zones.py:396 zone_bands` (one-way, `follows=v`) | with `v` pinned it survived as a two-way PULL on the pavement | **CHANGED (2)**: yields (the `water_exempt` clause) — 67 rows at SPLP |
| the design solve's law pricing | `solve/design.py:370-390` | a row footed on a fixed vertex is priced one-sided | unchanged |
| the ZONE PROJECTION | `solve/project.py:683 project_zone_bands` | clamps a governed vertex into its band | unchanged and now a no-op on seam pins: a pinned vertex carries no column, so it is never a "pure" column |
| the RUNWAY PROJECTION | `solve/project.py:412 coupled` | `n_free < n_all` over the REDUCED matrix — a fixed foot carries no column, so a row footed on two seam pins read self-contained | **CHANGED**: the coupling test reads the ROW'S OWN TERMS. Without it the QP and its relaxation LP are both **Infeasible** and the runway rows ship uncertified. |
| the BANK | `emit/bank.py:792` | closed the 10 m slit with `cov.buffer(bank_min_width_m)` — the 5.0 == 5.0 coincidence | **CHANGED (3)**: the derived pieces are cut by the band and the band is unioned into the coverage before the collar (`emit/seam_band.py`) |
| the bank's LAW constants | `emit.toml:445` / `:86` | independently typed, silently equal | **CHANGED (13an e)**: `law/model.py` refuses `bank_min_width_m < seam.half_width_m` by name at law load |
| `write_tile_pieces` | `emit/osm_adapter.py:317-358` | split breaklines by `floor(lon)` with no seam test | **CHANGED (13an c)**: refuses any breakline vertex inside the band |
| the CENSUS | `check_grade.LAW_FAMILIES` | no patch-edge-vs-DEM family; `strip_seam_tear` read 0 over a 3 m berm | **NEW**: `seam_residual` (cockpit `step`) and `bank_across_seam` (cockpit `keepout`) |

**THE ARMS** (each piece measured alone on SPLP before combining; base
served from the artifact ledger, `v2splpseam2` at 864e7577, body_sha
`f2e8a8226b18`).

| arm | seam on DEM | verify rows | hard set | runway projection | bank foot ≤ 5 m of the meridian |
|---|---|---|---|---|---|
| base b78f8f32 | 27/150, max 3.430 m | 239 | SETTLED 0/12498, max 0.0163 | held by the solve (0.0104) | **2** (closest 1.79 m) |
| (1) pins, pass deleted | **150/150, 0** | 320 | NOT SETTLED 2/12312, max 0.0358 | **Infeasible / relaxation LP Infeasible** | 2 |
| (2) + knots + zone yield | 150/150, 0 | 298 | NOT SETTLED 1/12312, max 0.0394 | optimal (elastic), family 0.0200 | 2 |
| (2) + the coupling fix | 150/150, 0 | **230** | NOT SETTLED 1/12312, max 0.0366 | optimal (elastic), family 0.0193 | 2 |
| (3) bank cut + union | 149/149, 0 | 226 | NOT SETTLED 1/12310, max 0.0363 | optimal (elastic), family 0.0154 | **0** (closest 12.09 m) |

Two attributions the arms bought:

* **the seam KNOTS are worth 68 census rows and half the lag.** With them
  off (diagnostic arm, everything else on): verify 298 vs 230,
  `airside_no_step` 81 vs 48, `within_shape` 144 vs 109, worst leader move
  0.190 vs 0.072 m (base 0.082). They cost fit to the CHANGED target:
  `target RMS` 0.304 → 0.366 m, because the target now passes through the
  seam pins and the K law will not follow a kink exactly. `|z − DEM|` mean
  improves 0.541 → 0.471 m.
* **`bank_min_width_m == seam.half_width_m` was load-bearing and is not
  now.** Unioning the WHOLE band into the coverage (the literal reading)
  extended the coverage a kilometre down the meridian and the collar
  followed it: foot distance mean 5.6 → 302.9 m, max 1042 m, 116 → 326
  foot nodes. The band is therefore clipped to the SLIT — intersected
  with the coverage grown by its own `half_width_m` — and the cut lands on
  the derived PIECES, never on the final banked region (differencing the
  band out after the collar re-opens the slit it exists to close).

**BARS.**

| bar | base | lane |
|---|---|---|
| `seam: N/N vertices on the DEM` | 27/150, 123 residual, max 3.430 m | **149/149, 0 residual** |
| runway band-edge vertices z − DEM | +0.51 … +0.63 m (vids 82/357/81/358) | **0.000** (a `Pin` holds exactly; `residual: pin 0.0000`) |
| vertex 1408 (−12.1664934, −76.9999539) | 51.07 vs DEM 54.50 | **at 54.50** (`seam_residual` 0) |
| bank foot within `half_width_m` | 2 (chain −10045/−10172, closest 1.79 m) | **0** (closest 12.09 m) |
| `seam_residual` | **106 rows, max 3.433 m** | **0** |
| `bank_across_seam` | **2 rows** | **0** |
| cockpit CRITICAL motion | **32** (31 of them `seam_residual [runway\|runway]`, worst 0.629 m at −12.1637725,−76.9999539) | **0** |
| cockpit CRITICAL visual | 0 | 0 |
| `HARD SET` | `SETTLED 0/12498 max 0.0163` | `NOT SETTLED 1/12310 max 0.0363` (the runway projection certifies the family at 0.0154 ≤ `hard_tol_m` 0.02) |
| `LAG` | `NOT SETTLED 0.082` | `NOT SETTLED 0.158` |
| runway 02/20 | `target RMS 0.0412 m, max 0.1506 m; bow −1.44 m` | `target RMS 0.367 m, max 0.794 m; bow −2.00 m` |
| build wall | 23.95 s (7 solve passes) | **9.31 s** |

The two arms' cockpit read is measured on the SAME instrument: the base
geometry priced against the published pins (`v2seampin-baseprobe`), since
the base build's own sidecar predates the key and declares no seam.

**§38 (2) NAMED, NOT SILENT.** 67 zone-band rows yield to a seam pin; 46
are still unmet at the solved surface, worst 3.609 m —
`zones.adjacent_ground` at pin 1408 (−12.1664934, −76.9999539): demanded
+2.502 m, allowed −2.183 … −1.107 m. That is §38 (2)'s "a family that
cannot be met between two pins is NAMED": the corridor between the runway
edge and the seam-pinned strip cannot be met with the pin held, so the
BAND yields and the report says by how much, per pin, every build.

**DEVIATIONS AND RESIDUALS, reported not decided.**

1. **§38 (2) says the zone band yields "as a soft escalation group".** The
   design solve has no slack machinery for a non-hard row — `soft` is read
   only for a row whose ruling head is in `[design] hard_rulings`
   (`solve/design.py:382`), and `zones.adjacent_ground` is not one. A
   `soft` group on that row is a NO-OP. What is implemented is the
   WITHDRAWAL the one-way law already implies (a row that governs a fixed
   vertex can only pull the pavement it was written to follow), reported
   per row with demanded-vs-allowed. Needs the spec author's ruling.
2. **13an (b)'s bar `coverage edges at ±5.000 ± 0.01 m` is not reached.**
   The tmerc round trip is REFUTED as the cause: a Newton correction
   against `to_ll(to_xy(·))` changed the emitted patch by nothing at all
   (`v2seampin-p3b` and `-p3c` are identical). What remains is the
   arrangement's own snap: `unary_union(..., grid_size=emit.identity.
   min_distinct_spacing_m = 0.5 m)` quantises every noded coordinate, so
   band-edge placement is quantised at 0.5 m and ±0.01 m is unreachable at
   this grid. Measured: base east edge +1.79 m (that node is the BANK FOOT
   in the crack), lane +5.016 / −4.973 m. The crack the bar exists to
   close is closed by the explicit coverage union instead.
3. **13an (d) — `seam_residual` comparing the two pieces' border
   POLYLINES — is NOT what landed.** A census reads a patch, and in the
   patch the two band edges are 10 m apart with draped DEM between: the
   west-edge-to-east-edge gap is real terrain and can never read zero. The
   family implemented is the spec's own §38 (5) wording — every band-edge
   vertex against its OWN published DEM sample — which is the same defect
   read where a patch can see it, and it zeroes. The polyline-vs-polyline
   read belongs to the mesh/DSF stage.
4. `LAG` worsens 0.082 → 0.158 m and the hard set stops settling (1 row of
   12,310 at 0.0363 m, certified back to 0.0154 m by the runway
   projection). 150 new hard equalities on the map's boundary is the
   cause; the residual is under the census's rounding envelope and mints
   no defect row.

**THE 13an ADDENDUM BARS.**

| bar (13an) | base | lane |
|---|---|---|
| (a) bank chain in the collar crack | chain −10172/−10045, closest node 1.79 m east of the meridian | none — closest bank foot 12.09 m; the band is unioned into the coverage and the pieces are cut by it |
| (b) coverage edges ±5.000 ± 0.01 m | +5.0228 / −4.9754 m | +5.016 / −4.973 m — **BAR MISSED**, attributed: the round trip is refuted (a Newton correction changed nothing), the residue is the arrangement's own 0.5 m snap grid (`emit.identity.min_distinct_spacing_m`) |
| (c) a breakline vertex inside the band in a tile piece | the chain, written verbatim into −13−077 | refused by `write_tile_pieces` |
| (d) the two edges' polylines, interpolated (patch side) | 72 stations, 39 gaps > 0.10 m, max 2.878 m, worst rolled-on 0.727 m | 70 stations, 25 > 0.10 m, **max 0.360 m**, worst rolled-on **0.251 m** — the residue is the DEM's OWN change across the 10 m draped band, which is why this reading is not the census family (see deviation 3) |
| (e) the two constants | silently equal | `law/model.py` refuses `bank_min_width_m < seam.half_width_m` by name; twin `test_v2bank.py::test_the_law_refuses_a_collar_that_cannot_reach_the_band` |
| the MESH, tile −13−077 (interventional) | 18,638 border nodes within 1 m of lon −77; 16,298 of them inside 1.92 m at lat −12.1609306 | **2,282** border nodes (bar ≤ 2,500); densest 1.92 m latitude window **3** |

The tile arm ran `build_airport.py SPLP --tile -13 -77 --engine v2` and the
harness REFUSED to report it: the engine's DEM prep tried to rewrite
`Elevation_data/-20-080/S13W077_airport_insets/index.json` and the
shared-repo guard blocked it (no `--refresh-data` was given and none was
wanted). The mesh it wrote is therefore a DEGRADED-frame reading and is
quoted as one. It is still decisive for this class: the 16,298-node fan
was a Triangle4XP segment-splitting degeneracy against a constrained
segment 2.37 cm from the unsplittable border, and the segment is gone —
no DEM frame puts it back.

### §34 (4) NARROWED — A ZONE BAND YIELDS ONLY TO A TUNNEL CORRIDOR (Fable 2026-09-13; RULINGS 2026-09-13ar) — lane `v2rampwalk` round 3

Round 2 (8e101597): the general "zones yield to roads" trim exposed
`zone2#24`'s original outer ring (8.49 m over 12.03 m at 40.5331907,
−3.5748496 — the band used to spread that terrain across its interior) and
cost 671 `graded_strip|graded_strip` rows; the densifier cannot insert into a
region's own welded edges (refuted). At F-6 the zone-1 band followed the
underpass trench down (5.29 m rows).

4. **THE CORRIDOR, NOT THE ROAD.** A zone band yields only to a TUNNEL
   CORRIDOR — the mouth, the ramp, the trench and the underpass corridor as
   §34 (1)–(3) and (5) price them — which is SUBTRACTED from the band; the
   band's boundary there is the corridor's own edge (terraced by the ramp
   walls). A road elsewhere inside adjacent ground grades WITH the zone (the
   standing law). Owner item 8 (a road at a tunnel) is the corridor case.

BARS (round 3, ONE LEMD build with `--base-arm`): CRITICAL visual ≤ 3 with
no row at 40.5331907, −3.5748496 and none at F-6 (40.4609964 …
40.4610048); `graded_strip|graded_strip` `within_shape` ≤ base + 20 (round
2: 671); item 8's 1.63 m row absent; item 9's deck end ≤ 0.3 (round 2:
0.18); `optimal`; 7a / 7b ramp bars hold; KCLT item 3 by replay unchanged;
suite twice.

### §37 (6) AMENDED (decks out), §37 (7) A ROAD PAIR IS PRICED ALONG THE ROUTE (Fable 2026-09-13; RULINGS 2026-09-13av) — lane `v2roadramp` round 2

Lane v2roadramp (4172e698): the ramp works (KCLT `dsf:pol51` follow 0.29 →
0.86) but the census regressed 3,900 → 7,622: `road_within_shape` (8 % × a
45.6 m PLAN chord) and `road_cross_section` (2 % × 44.2 m) hold a hairpin's
upper branch to the lower branch's ceiling — the two branches are 280 m apart
along the road.

- **§37 (6) amended:** a `bridge_deck:*` face is OUT of the ramp population —
  its datum is §33 (4) (the deck end equals the pavement it connects to).
7. **A ROAD PAIR IS PRICED ALONG THE ROUTE.** The road's longitudinal rows
   (the 8 % cap, `road_within_shape`) pair vertices by ROUTE distance along
   the road's own centreline, never by plan chord (09-05aa's withdrawn chord;
   §34 (1)'s route-priced ramp). A cross-section pair is a pair ACROSS the
   road's width at ONE station; `road_cross_section` prices only those. Two
   branches of one road within a road width in plan (a switchback) are not a
   pair; the ground between them is adjacent ground (§19 / §31, terraced,
   visual only).

BARS (round 2, ONE KCLT build against the shared control `ctl-KCLT`):
`road_cross_section` 1,691 → ≤ 310; adjudicated ≤ 3,900; the ten worst pairs
named route-followable or transverse; `dsf:pol51` follow ≥ 0.85 holds;
`dsf:pol82` ≤ 0.5 m (today 0.80); cockpit CRITICAL motion ≤ 8, no road row;
LEMD / CYXY dry re-read; suite twice.

### §37 (6)/(7) **MEASURED — ROUND 2** (lane `v2roadramp`, 2026-09-13, branch `claude/v2roadramp`, base `70646dc8`)

ONE `--engine v2 --patch-only` KCLT build, tag **`v2roadramp2`**, 311.0 s,
rc 0, `status feasible`, `body_sha 3db860e1d3c7`, artifact ledger
**`5dcfccc142b9`**, `[guard] shared repo UNCHANGED`.  The BASE is a
control built for this round at the SAME base — tag `ctlkclt70646dc8`,
ledger **`1f83c7a053d9`**, 315.2 s, tree `70646dc8` — because the shared
`ctl-KCLT` stands at `864e7577` and main has since taken v2seampin,
v2eatramp and v2settle; every number below is against the SAME-TREE
control, and the round-1 column (`497728ff051c`, §37 (6) alone on
`864e7577`) is quoted beside it so §37 (7)'s own movement is visible.

#### WHAT LANDED

* §37 (6) AMENDED: the deck exclusion (round 1's finding) is ratified law.
* §37 (7): `airport/road_ramp.road_route_frame` derives, for EVERY
  road-family ring vertex, `(route id, station s, signed lateral t)` off
  the SAME ways the ramp reads its DEM on; `PlanarMap.road_route_frame`
  carries it, `pipeline/publication` publishes it (sidecar
  `road_route_frame`, LAW INPUT in `check_grade.SIDECAR_LAW_KEYS`), and
  ONE reading — `constraints/roads.road_pair_reading` — is imported by
  the generator, by `verify/within` and by `check_grade`, so the three
  cannot drift (the census-wrapper precedent).
* THE READING: `bound = cap_l·|Δs| + cap_t·|Δt|` (the taxi family's box,
  06q/06s) with Δs the ROUTE distance and Δt the offset across it;
  TRANSVERSE — and so `road_cross_section` — iff the pair's direction in
  ROUTE coordinates is at least `road_transverse_axis_min_deg` off the
  centreline; **NOT A PAIR** on two different routes; the chord law where
  no route answers.  Two floors keep it a RELAXATION: a RING EDGE is
  always priced (an adjacent pair keeps the chord reading across a route
  boundary, so a way boundary mid-road cannot leave a step unpriced), and
  no bound is under `cap_t × the pair's plan distance` (a projection can
  collapse on a bend).
* THE FRAME COVERS EVERY ROAD VERTEX: a way running THROUGH a face
  answers its outer kerbs too (the ramp TARGET keeps the face's answer
  radius).  Without that, 174 of KCLT's 2,026 road vertices were unframed
  — the wide pages' outer kerbs — and their pairs fell back to the chord
  law that held the switchback (measured: `dsf:pol51` cut 6.75 m).

Generator population at KCLT: `road_within_shape` 76,261 rows — **routed
24,741, chord 51,520** (the parking lots and groundside pavement, which
are not roads and keep the chord law), **not_a_pair 47,965**, ring_edge
578.  Published frame: 2,177 vertices.

#### THE OWNER'S SITE — `dsf:pol51` (`--site`, radius 60 m)

| | `ctl-KCLT` (864e7577) | §37 (6) | §37 (6)+(7) |
|---|---|---|---|
| FOLLOW RATIO | 0.294 | 0.857 | **1.007** |
| highest FILL | +13.31 m | +1.62 | **+1.59** |
| deepest CUT | 0.86 m | 5.58 | **5.33** |
| \|emitted−DEM\| median / p95 | 0.43 / 10.54 | 2.33 / 4.11 | **0.61 / 3.78** |

#### AIRPORT-WIDE ROADS (`--by-ref`, same options)

All 2,533 road vertices: \|emitted−DEM\| median **0.708 → 0.171 m**, p95
**3.348 → 1.674 m**, worst 4.17 → 5.33 m.  **Refs over 3 m off the DEM:
8 → 2** — `dsf:pol51` (5.33 m of CUT at 35.2068764,−80.9301639) and
`bridge_deck:-3595` (+4.08 m, the face §37 (6) excludes, unchanged from
its 4.09 m).  `dsf:pol70` 8.17 → **1.65**, `dsf:pol50` 6.53 → **1.25**,
`dsf:pol82` (owner item 7) 6.17 → **0.68 m** (bar ≤ 0.5: 0.18 m over,
reported under §31 (4) as a residual).  `dsf:pol39` 3.64 → 2.22,
`dsf:pol86` 3.46 → 1.67, `dsf:pol63` 3.84 → under 1.7.

#### THE TEN WORST PAIRS, NAMED (the round-1 attribution, re-read under (7))

| face | ref | plan chord | §37 (7) verdict |
|---|---|---|---|
| 827 | `dsf:pol51` (the switchback) | 45.6 m | **not a pair** (two routes) |
| 777 | `dsf:pol50` | 161.4 m | **not a pair** |
| 792 | `dsf:pol70` | 64.0 m | **not a pair** |
| 600 | `dsf:pol39` | 93.7 m | **not a pair** |
| 729 | `dsf:pol62` | 41.9 m | **not a pair** |
| 737 | `dsf:pol82` | 81.7 m | **not a pair** |
| 764 | `dsf:pol53` | 22.3 m | **not a pair** |
| 828 | `dsf:pol51` | 77.6 m | route-followable, bound 6.97 m |
| 597 | `dsf:pol39` | 84.2 m | route-followable, bound 8.07 m (target Δ 6.74 — met) |
| 595 | `dsf:pol66` | 7.0 m | TRANSVERSE, bound 0.47 m (a real cross-section) |

Seven of the ten are the switchback class the ruling frees; two are
route-followable; one is a genuine cross-section.

#### THE CENSUS AND THE VERIFY

| | BASE `1f83c7a053d9` | §37 (6) (r1) | §37 (6)+(7) |
|---|---|---|---|
| harness LAW-TRUE | 11,274 | 17,030 | 13,128 |
| harness **ADJUDICATED** | **3,813** (airside 3,379 / gs 434) | 7,622 | **5,684** (airside **3,801** / gs 1,883) |
| `road_cross_section` | 330 | 1,691 | **642** |
| `within_shape` | 8,500 | 11,541 | 9,743 |
| `airside_no_step` | 612 | 1,374 | **657** |
| `transverse` | 109 | 470 | 348 |
| v2 VERIFY rows | 3,908 | 12,264 | **4,439** |
| v2 VERIFY `road_cross_section` | **781** | 5,263 | **462** |
| cockpit CRITICAL motion / visual | 7 / 0 | 8 / 0 | **12 / 0** |

**THE TWO BARS ARE NOT MET AND THE LANE SAYS SO**: `road_cross_section`
642 against ≤ 310 (the base at this tree is 330), adjudicated 5,684
against ≤ 3,900, cockpit motion 12 against ≤ 8 (NO road row in either
arm — the rolled-on set is airside by definition; the 12 are runway
`strip_arc` grade breaks and two apron `mid_edge_step` rows, the same
families as the base's 7).  What IS measured:

1. §37 (7) removed two thirds of what §37 (6) cost: adjudicated 7,622 →
   5,684, `road_cross_section` 1,691 → 642, `airside_no_step` 1,374 → 657
   (below the base), v2 verify rows 12,264 → 4,439.
2. **The two instruments now disagree in DIRECTION on the road family**:
   the v2 VERIFY — which prices exactly the generator's rows, under the
   same imported reading — reads `road_cross_section` **781 → 462**, an
   improvement on the base; the v1 census reads 330 → 642.  Both now
   PAIR the same way (the twin asserts the census imports the
   generator's function); what still differs is the pair SELECTION
   (`grade_graph.shape_constraints(road_path_metric=True)`, v1's own) and
   the allowance envelope.  The residual is not a pairing artefact.
3. The rows that remain are a road surface that now RIDES ITS TERRAIN
   (median off-DEM 0.708 → 0.171 m): a section that rolls with the ground
   breaks the 2 % cross-section, and the census counts it.  Whether a
   groundside road's cross-section is a LAW or a target under §31 (3)
   ("landside is visual only, grade laws there are TARGETS") is the
   question this residual asks; it is not one this lane may answer.

#### Build-time impact statement

The frame is one extra answer per road vertex over the profiles
`preferred_road_z` already built (KCLT: 2,177 vertices, inside the road
stage's own 1.4 s); the pair law itself is arithmetic on two 3-tuples and
DROPS 47,965 of 76,261 rows, so the solve got smaller (LP rows 95,797 →
84,606) and faster (solve 104.6 → 71.5 s; whole build 426.5 → 311.0 s
against the control's 315.2 s).  Nothing here is within 1 % of either
budget on the wrong side.

#### What round 2 did NOT do

Merge into main; write RULINGS; touch §37 (1)'s caps, the bank, §27's
flip, `solve/`, `constraints/eat.py` or the other lanes' files; a third
KCLT build (the attempt cap: the route pairing, then the collapse floor,
which moved the census 646 → 642 and was kept as a safety floor, not
re-built for); a LEMD or CYXY BUILD (both re-read DRY on their captures:
LEMD 157 road vertices all framed, 486 routed pairs / 184 not-a-pair, the
61 apron-side lanes still carrying 0 ramp targets, the 13 decks excluded,
6 governed vertices within 0.02 m of the DEM; CYXY 348 framed, 3,347
routed / 2,902 not-a-pair, targets within 0.01 m of the core clamp); a
new tool (no `tools/INDEX.md` row).

### §37 (8) THE CROSS-SECTION IS LAW ON A GROUNDSIDE ROAD; THE RAMP BINDS THE CENTRELINE (owner 2026-09-13; RULINGS 2026-09-13bb) — lane `v2roadramp` round 3

Owner: "The base engine should be correcting road banking, confirm that is
running before we try to grade it or test it." Confirmed: the rows run
(`road_cross_section`, 2 %, weight 300, not hard) and lose — KCLT verify 781
violated pairs on the control, 462 with the ramp. A hillside road keeps its
crossfall on a BENCH, not by tilting.

8. **LAW, NOT TARGET.** The 2 % cross-section is law on every road-family
   face, groundside included; `road_cross_section (2026-08-25g)` joins
   `[design] hard_rulings` and the polish certifies it. The ramp target
   (§37 (6)) is the road's CENTRELINE profile per station; the kerbs follow
   the centreline through the cross-section rows, so the hard ramp ceiling
   binds one value per station and never a kerb against another station;
   the adjacent ground takes the bench (§19; §37 (3)'s bank where
   load-bearing).

BARS (round 3; attribution of the 462 rows FIRST, `--why-at`): v2 verify
`road_cross_section` 462 → ≤ 20, survivors named; v1 census 642 → ≤ 330
once its selection reads `road_route_frame`; `dsf:pol51` follow ≥ 0.85 and
section ≤ 2 % at every station; `dsf:pol82` ≤ 0.5 m; cockpit motion ≤ 7;
LEMD / CYXY dry as before; ONE KCLT build against `ctlkclt70646dc8`.

### §37 (6) AMENDED (the ramp's floor is the core clamp), §37 (9) THE COVERAGE-EDGE JOIN (Fable 2026-09-13; RULINGS 2026-09-13be) — lane `v2roadramp` round 3

Scout `roadlevel`: the core's `include_roads` levelling runs for every
airport-area way and is then REMOVED inside the patch coverage + 6 m
(`O4_Vector_Map.py:1749-1757`); inside the coverage the patch is the sole
road authority and v2 computes the core's clamp itself
(`airport/road_profile.py` → `cap_lipschitz_profile`). At KCLT's east road
the mesh shows the patch (214.24) over the core (203.48) and the DEM
(200.31); at the coverage edge the patch's kerb meets the core ribbon with a
2.36 m drop over 7.9 m.

- **§37 (6) amended — THE FLOOR IS THE CLAMP.** The ramp target is
  `max(clamp(s), z_contact − cap × s)` along the route, `clamp(s)` the
  in-process `cap_lipschitz_profile` value (`preferred_road_z`'s own
  profile): the road descends at the cap to the core's answer and follows
  it. Where the DEM is within the cap the two coincide; where it is not,
  the road takes the lift/cut the core would have given it.
9. **THE COVERAGE-EDGE JOIN.** A road-family face whose way leaves the
   coverage takes, at its last station inside, the core ribbon's altitude
   at the first station outside (the clamp value) as an EQUALITY; census
   family `road_coverage_join` prices the step (twin: a road exiting the
   coverage, step 0). Bar at KCLT way 10826 station 0: 2.36 m → ≤ 0.05 m in
   the patch.

BARS (round 3, with §37 (8)'s): as 13bb, plus `road_coverage_join` 0 on the
lane arm and > 0 on the control; the mesh confirmation of the join is the
app build's tile.

### §37 (8)/(9) + §37 (6) amended **MEASURED — ROUND 3** (lane `v2roadramp`, 2026-09-13, branch `claude/v2roadramp`, base `661cb2e7`)

ONE KCLT build, tag **`v2roadramp3`**, 326.6 s, rc 0, `status feasible`,
`body_sha 5f3a70d28599`, artifact ledger **`91ab5a7c8e15`**, `[guard]
shared repo UNCHANGED`.  The control is round 2's same-corpus
`ctlkclt70646dc8` (ledger `1f83c7a053d9`) at main `70646dc8`; main has
since taken `661cb2e7` (v2rampwalk's bridges and adjacent-ground steps,
the v1 retirement — `build_airport.py` no longer has `--engine`), so the
NON-ROAD families below carry that movement too and are marked.

#### THE ATTRIBUTION FIRST — why 462 `road_cross_section` rows survived §37 (7)

Measured on the KCLT capture, over the 2,155 pairs §37 (7) calls a
CROSS-SECTION, by comparing each pair's own §37 (6) TARGETS against its
2 % bound (`cap_t·|Δt| + cap_l·|Δs|`):

| the target's reading | pairs whose TARGETS already break their own 2 % bound | worst |
|---|---|---|
| per VERTEX, floor = the raw DEM along the route (round 2) | **145** of 2,155 | 3.51 m against a 0.60 m bound, Δs 5.8 m, `dsf:pol51` |
| per VERTEX, floor = the core clamp | **129** | 3.67 m against 0.19 m, Δs **1.2 m** |
| per (ROUTE, STATION), floor = the core clamp (this round) | **0** | — |

The suspicion in the brief is confirmed and made precise: the target was
read PER VERTEX — its own nearest-way answer for the floor and its own
graph distance for the descent — so two kerbs of ONE station could take
values 3.67 m apart over 1.2 m of station, and the hard ramp ceiling then
held that tilt against the 2 % cross-section.  The raw DEM made it worse
(it is not cap-Lipschitz), which is why (2) and (8) are one fix:

* the FLOOR is the core's clamp on THE ROUTE THE FRAME NAMES
  (`cap_lipschitz_profile`, already carried by `RoadProfiles`), and
* the target is `max(clamp_r(s), envelope_r(s))` — the descent lifted onto
  the route as a cap-Lipschitz upper envelope — so it is a function of
  (route, station) alone.

Both terms are cap-Lipschitz, so a section's two kerbs differ by at most
`cap_l·|Δs|`, always inside the pair bound: **the ceiling cannot tilt a
section, by construction**.

#### THE THREE RULES AS BUILT

* §37 (8): `road_cross_section (2026-08-25g)` is in `[design]
  hard_rulings` — the 2 % is a CONSTRAINT of the active set on every
  road-family face.
* §37 (6) amended: `airport/road_ramp._floor_along_route` reads the clamp
  (`_dem_twin` keeps the terrain reading for the report only).
* §37 (9): `emit/road_join.py` (the coverage is `emit/bank.coverage_polygon`,
  one implementation) walks each route's stations against the coverage and
  pins the last station inside at the CORE ribbon's altitude at the first
  station outside; published as `PlanarMap.road_coverage_join` and sidecar
  `road_coverage_join`, minted as `Pin` rows by
  `constraints/road_ramp.road_join_rows`, priced by the new census family
  **`road_coverage_join`** (`check_grade.LAW_FAMILIES` + `families.toml`
  `cockpit = "step"`, `solver = "pin"`, four twins in `test_harness.py`).

#### PER BAR

| bar | control `1f83c7a053d9` | round 2 `5dcfccc142b9` | **round 3 `91ab5a7c8e15`** |
|---|---|---|---|
| v2 verify `road_cross_section` ≤ 20 | 781 | 462 | **7** ✅ |
| v1 census `road_cross_section` ≤ 330 | 330 | 642 | **300** ✅ |
| `dsf:pol51` follow ≥ 0.85 | 0.286 | 1.007 | **1.017** ✅ |
| `dsf:pol82` ≤ 0.5 m | 6.17 | 0.68 | **0.68** ❌ (0.18 m over) |
| `road_coverage_join` 0 on the arm, > 0 on the control | — | — | **0 rows**; the same 22 coordinates on the control stand up to **7.93 m** off the ribbon (`dsf:pol70`), 5.17 / 5.15 m at the owner's site 35.2077280 / 35.2077325, −80.929 → **arm 0.004 m max** ✅ |
| cockpit CRITICAL motion ≤ 7 | 7 | 12 | **9** ❌ (visual 0 → **1**, an `adjacent_ground_step [apron\|graded_strip]` cliff 0.820 m over 2.01 m at 35.2267703,−80.9552263 — `adjacent_ground_step` is `661cb2e7`'s new family, not this lane's) |
| all-road \|z−DEM\| | median 0.708 / p95 3.348 | 0.171 / 1.674 | **0.198 / 2.206**, worst 4.40 m |
| adjudicated | 3,813 | 5,684 | 5,864 (airside 4,228 / gs 1,636) — the airside rise is `661cb2e7`'s |

THE 7 SURVIVORS (the v2 verify's own count; the build prints counts, so
they are named through the v1 census's reading of the same law on the same
patch — 300 rows, p50 0.34 m, p95 1.40 m, max 2.01 m): they concentrate on
**`dsf:pol53` way −10858** (55 rows, every one of the worst eight, at
35.21603,−80.92880–80.92890, pairs 36–48 m apart on a page 170 vertices
long) and on `−10862` (40), `−10879` (39), `−10507` (23).  These are the
WIDE pages whose section spans tens of metres: at Δt ≈ 40 m the 2 % bound
is 0.8 m and the built section carries up to 2.01 m.  They are a bench the
solve did not fully cut, not a tilt the law admits.

Other readings: `road_ramp` 1,955 targets from **244** contacts (137 on
the ramp, up to 1.80 m over 596 m of route), clamp over the DEM up to
3.67 m, core fit withdrawn on 1,760; `road_within_shape` 76,393 rows
(routed 24,871 / chord 51,522 / not-a-pair 47,988 / ring-edge 580);
`road_coverage_join` 22 rows from 42 exits on 26 routes; hard rows
28/238,729 violated (max 0.0883 m), `SET NOT SETTLED` 645 flips worst
0.024 m — KCLT's standing 13y (B) condition.  `bridge_deck:-14469`
(`661cb2e7`'s new deck) reads +11.10 m off the DEM and is OUTSIDE the ramp
population by §37 (6) as amended.

LEMD / CYXY dry, on their captures: LEMD 6 governed vertices (13 decks
excluded), targets within 0.01 m of the core clamp, 0 apron-face targets
of 159; CYXY 314 targets, 10 on the ramp, clamp over the DEM up to 1.08 m,
targets within 0.22 m of the clamp.  Suite **1,332 / 0 twice**.

#### What round 3 did NOT do

A second KCLT build or a new control at `661cb2e7` (the bar named
`ctlkclt70646dc8`); the `check_grade` SELECTION re-point (the bar's ≤ 330
was met by the law itself — the census's selection still reads
`grade_graph.shape_constraints`, and its 300 rows are the same population
the verify reads 7 of, the difference being v1's allowance envelope);
chasing the `strip_arc` rows (13ba: the unsettled lag's, and this build's
cockpit block carries one of them at 0.090 m); `dsf:pol82`'s last 0.18 m;
any merge, RULINGS entry, or new tool.

### §30 (4) THE CLUSTER PAD (owner RULINGS 2026-09-13bj; Fable 2026-09-13) — lane `v2clusterpad`

Owner: "it's acceptable to flatten large apron areas around big terminals if
needed to accommodate a large terminal cluster", as long as the grade laws
and the taxiways stay feasible.

4. **ONE PAD UNDER A TERMINAL CLUSTER.** Where the object stage's family
   census names a cluster (object spec §16f (7): footprint union over
   `cluster_pad_min_m2`), the design surface emits ONE `building` pad over
   the footprint union — one plane (the pad law, 1 %) — and the apron faces
   within `cluster_apron_reach_m` of it take that plane as their target
   where the apron caps allow; the reach stops at any taxiway family band
   (never moved). The pad's level is the pad law's (the median ground under
   the union, then the plane), published in the sidecar (`cluster_pads`) so
   the object stage seats the cluster on it. Feasibility is the solve's:
   where the reach cannot be met under the caps the report names the apron
   faces that stayed graded.

## §39 THE HAIRLINE LAW (Fable 2026-09-13; RULINGS 2026-09-13an / 13bk; owner reads SPLP 13ag, LEMD 13bi, KCLT 13bj) — lane `v2hairline`

Three sightings in one day of one class: a constrained edge laid within
millimetres of, and parallel to, another — the SPLP bank chain 2.37 cm from
the meridian (16,298 Triangle4XP nodes in 1.92 m), LEMD's two patch pavement
rings 0.06–0.26 mm from the retention basins' water edges (2.30 M sub-0.1 m²
triangles, 73 % of the tile, X-Plane stalled), and (pending the scout) KCLT's
tearing. Triangle4XP must recover both segments and fills the wedge with a
Steiner cascade; GEOS's OverlayNG falls back to its snapping noder on the
same inputs (13bi's 35 GB union is the suspect twin).

1. **NO EDGE BESIDE ANOTHER.** An emitted ring vertex or edge may not lie
   within `identity.min_distinct_spacing_m` (0.5 m) of a FOREIGN constrained
   edge — an OSM water edge, a tile border, a core road ribbon, another
   face's ring — unless it SHARES that edge's vertices exactly (the 11-dp
   identity join). A ring edge within the spacing of a water edge is
   SNAPPED onto the water edge's own vertices (the shore weld: water is a
   datum and already carries the vertex), never laid beside it. Applied at
   ONE site: the emitter's ring writer, after every face is final.
2. **THE CENSUS FAMILY `hairline_pair`** prices every emitted ring edge
   against every foreign constrained edge of the tile's vector map within
   the spacing and within 5° of parallel — CRITICAL unconditionally (a
   load-time and texture defect, not a height).
3. **THE MESH PRE-FLIGHT.** `O4_Mesh_Utils` audits the assembled `.poly`
   before Triangle4XP: any non-adjacent constrained pair within the spacing
   and within 5° of parallel is REFUSED by name (pair, markers, coordinates)
   — the tile fails in seconds, never after a 40-minute Triangle run.
   `mesh_region_tris.py --hairline-audit` is the instrument (promoted from
   the scouts' `nearpar.py`).
4. **THE LEMD CAUSE IS NAMED AT ITS SITE.** Bisect the 1773 batch on the
   LEMD capture for the pass that moved the pavement ring onto the water
   edge (the shore weld count fell 403,636 → 145,257): the seam-band and
   bank-coverage changes (13as), the level belt (13w), the bank cut (§37
   (3)), the basin footprint (§24 (4)) are the suspects, in that order.

BARS: LEMD (`Data+40-004.mesh` from ONE harness tile build or the app's):
sub-0.1 m² triangles 2,301,676 → low hundreds, aspect p50 7,549 → < 5, DSF
≤ 23 MB, triangles ≈ 2.93 M; `hairline_pair` 0 at LEMD, KCLT, SPLP, CYXY
and > 0 on the LEMD control; the pre-flight refuses a synthetic hairline
`.poly` and passes the four tiles; F-6, the basin, the ramps byte-identical
where they are not the cause; suite twice.
