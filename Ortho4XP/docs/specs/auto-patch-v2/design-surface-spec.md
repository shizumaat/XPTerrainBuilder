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
