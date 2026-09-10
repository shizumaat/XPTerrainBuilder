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

### 19.4 Twins and the closing test

Twins (`tests/auto_patch_v2/test_v2edge.py`): a flat DEM → byte-identical regions; a
plateau fixture (DEM steps 20 m over 15 m at x = 100) with a zone extending to x = 150
→ the region ends at the crest (within `edge_grid_m`), no bank segment there; the same
with a road at x = 92 → the region ends at the road's outer edge; a gentle slope
(20 %) → untouched. Closing test: ONE airport, CYXY (`build_airport.py CYXY --engine
v2`, control `--base-arm`), then the transect of RULINGS 10b through the site (stations
every 5 m from +200 to −200 along the site→road axis, `mesh_elevation_sampler.py` on a
mesh-only tile run): bar — the strip's edge lies within one lane width of the rim
road's outer edge, no station steps more than 1 m, every station past the road within
1 m of the DEM; DEFECTs 0; the crossings of 09ai unchanged; KML of the edge segments
sent up. Site-first report.
