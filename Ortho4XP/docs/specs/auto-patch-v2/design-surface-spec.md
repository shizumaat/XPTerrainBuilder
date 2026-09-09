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
