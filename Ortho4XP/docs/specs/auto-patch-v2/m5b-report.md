# auto-patch-v2 — M5b report: the ROUTE law (RULINGS 2026-09-04o / 04q) — feasibility follows the taxi routes

Lane `lane/v2route` off main `39cf7dfb`. Rulings implemented: **04o**
("feasible elevations propagate out from runway thresholds and have to
follow taxi routes … aircraft can't travel straight across the grass"),
**04q-1** (a no-step pair is priced at the cap of the TRAVEL PATH over the
ROUTE distance, never a plan chord), **04q-2** (a route-proximity junction
inherits the code letter of the taxi chains it serves), **04q-3**
(`solve/` imports law and model only). Every law value from the TOML
tables; no env reads; no v1 imports; every file ≤ 1,000 lines.

## 1. The dependency fix (04q-3) — `test_dependency_direction` green

`tests/auto_patch_v2/test_model.py::test_dependency_direction` was RED on
main: `solve/tiers.py` imported `constraints.precedence`, and `solve/why.py`
imported `airport`, `classify`, `constraints`, `pipeline` and `planar`.

* the tier derivation (`is_governed`, `governed_roles`, `ungoverned_roles`,
  `tiers`, `role_tier`, `tier_of_roles`) is a function of `precedence.toml`
  alone and now lives in **`law/tables.py`**;
* the vertex-ownership view is **`model/planar.py`**: `PlanarMap.roles_at(v)`
  (I5, the record) and `vertex_tier(pm, v, tier_of, lowest)`;
* `solve/tiers.py` imports `law.tables.tiers` + `model.planar.vertex_tier`;
  `row_tier` / `demote` take the planar map, not the generators' `View`;
* `solve/why.py` keeps the LP analysis (bindings, chain trace, relax-one,
  report — `report(..., letters=)` takes the evidence lines from its caller);
  the pipeline rebuild (`prepare`), target resolution (`resolve_faces`,
  the `--patch` overlap match) and the apt.dat 1202 letter evidence
  (`taxi_letters`) moved to **`pipeline/why.py`**; the CLI is unchanged;
* `constraints/precedence.py` exports `View` / `view` / `face_cap` only.

## 2. The route graph — `constraints/routes.py` (390 lines)

NODES: planar vertices on airside pavement (`route_roles`: airside,
value-carrying, governed, not rigid — the no-step population of 03i; the
groundside roles — service roads, service junctions, lots, ramps — never
contribute a node or an edge: v1 `REACH_NO_SERVICE_SPINES`). EDGES: the
travel paths the law itself prices — every ring edge of an airside
pavement face (a taxi centreline is a ring edge of the faces it splits:
first-class, marked `CENTRELINE`), every chord of a taxi-family face (a
plane shape), and on an apron the movement chords the apron law names
(to a spine / pad vertex at any distance, body chords ≤ 60 m) — **across
all the rings of a face** (measured CYXY: pads building6/7 are apron
holes 3.6 m apart; with same-ring chords only they had no route and
solved 1.59 m apart, the oracle's `cross_shape` 2 / `vertex_to_edge_step` 2
/ `mid_edge_step` 2). Each edge carries its plan length and the cap of
the face it lies in — the strictest where two faces share it (the budget
the solve grants along it). `scipy.sparse.csgraph.dijkstra` does the
walking: bounded per-source runs in chunks of 256 for the K-nearest
(edges longer than the window dropped first — they lie on no path inside
it), one multi-source run over budget weights for the reach.

It lives under `constraints/`, not `planar/`: the generators read it and
the dependency law allows a generator law + model only.

| | nodes | edges | ring | chord | centreline | faces |
|---|---|---|---|---|---|---|
| CYXY | 2,454 | 49,494 | 2,302 | 46,950 | 242 | 79 |
| HECA | 23,777 vertices / 1,225 faces (graph stats not printed by the build) | | | | | |

## 3. No-step re-derived (04o / 04q-1) — `constraints/no_step.py`

* `emit.toml [no_step]`: `metric = "route"` (with the ruling comment),
  `window_m = 150` now ROUTE metres, `k = 16` = the K nearest BY ROUTE
  DISTANCE; `law/model.py NoStep.metric`; a chord metric is refused
  (`LawError`) — the refuted 08-27 reading cannot be configured back.
* §1.1 pairs: for every airside vertex its K nearest airside vertices by
  route distance within the window (`routes.route_neighbours`); each
  `Diff(a, b, cap, d)` with `d` the route distance and `cap = budget / d`
  so `bound_m = Σ cap_e · len_e` along the pair's own path — an
  apron↔taxiway pair carries the taxiway's cap on the taxiway stretch and
  the apron's on the apron stretch (CYXY: 280 of 22,544 pairs carry a
  mixed cap strictly between 1 % and 1.5 %). A pair with no pavement path
  inside the window does not exist.
* Published unchanged in shape: `airside_no_step_edges` `{a, b, budget_m,
  dist_m}` with `dist_m` = the ROUTE distance; `verify/no_step.py` prices
  the published budget over the published distance (the reader never
  re-derives a chord); the v1 oracle prices `budget_m` by identity as
  before.
* §1.2 rate rows unchanged. The pad↔pavement pairs (M5) stay K-per-sector
  at DIRECT distance: a pad is not pavement and lies on no route (open
  question 3).
* **Reach bands** (`no_step.reach_bands`, generator `reach`,
  `model.constraints.REACH_GENERATOR`): the CIFP threshold pins
  (`runway_profile.threshold_pins`, factored out of the pin rows)
  propagated along every route at the path caps — `(max_p z_p − B,
  min_p z_p + B)` per vertex, `B` the least Σ cap·len from pin `p` — as
  `Band` rows (variable bounds, zero LP rows). They are the envelope the
  hard path rows imply (twin: the solve without them lands inside them and
  is the same surface with them); `solve/tiers.demote` WITHDRAWS them once
  a tier yields — held against a demoted taxiway they would refuse the
  very yield the tier order grants, and a tier-0 vertex's band would
  otherwise carry a taxi route's contradiction into the never-demoted
  tier. `why`'s relax arms drop them with the family (an arm without the
  family has no envelope of its own; measured: every arm read 1e-13 m
  with the envelope kept).

Pair counts, chord law → route law (pavement + pad):

| | chord (M5 / why-report) | route |
|---|---|---|
| CYXY | 22,610 | 23,213 (22,544 + 669 pad) |
| SPJC | 55,828 | 54,502 |
| OTHH | ≈143 k (M4) | 150,426 |
| HECA | 117,965 | 117,119 |

## 4. Junction letter (04q-2) — `classify/roles.py`

`_junction_letter(part, touching, through, rules)`: a junction part minted
by the route-proximity cut serves the taxi chains running through or
along it (≥ `cells.min_shared_m` inside `on_tol_m`) and the through-routes
whose proximity minted it (within `apron.route_proximity_m`); it inherits
the STRICTEST of their letters (`max` over `_LETTERS`, as a corridor
does). Evidence field `letter_chains` = the chains counted. Twin:
`test_routes.py::test_junction_inherits_the_letter_of_the_chains_it_serves`
(the classify fixture's junction spans route A class C and the parallel P
class D → D).

**The oracle had to learn it.** v1 never stamps `code_letter` on a
junction (`config.TAXI_GRADE_WIDTH_ROLES` excludes it; its solver keeps
"the tighter rate"), so the law-true census priced a v2 junction at its
spine's cap or the nearest connected sized shape — CYXY junction 154
(letter A, solved at 3 %) read 3 `within_shape` rows at cap 1.5 %.
`tools/check_grade.py` now adopts the taxi law at the stamped letter for
a junction way carrying `code_letter` (`_soft_grade_shape`, and the
way-cap read) — a v1 patch, carrying none, reads exactly as before
(`tests/test_harness.py` 300 passed). CYXY census 3 → **0**.

At the owner's site the inherited letter is **D**, not A: junction 100
(the shipped 103) serves several chains and the strictest of them is D
(open question 1).

## 5. Builds (`build_airport.py ICAO --engine v2`, ledgered)

| | CYXY | SPJC | OTHH | HECA |
|---|---|---|---|---|
| tag | `CYXY_20260904T102408` | `SPJC_20260904T102758` | `OTHH_20260904T102905` | `HECA_20260904T103238` |
| artifact ledger | a9ea8577e0d3 | — | — | |
| body sha | d6f8a1b9cebb | 016e50b28dfc | 051933ec780b | d001357a0d50 |
| vertices / faces | 4,451 / 273 | 9,449 / 423 | 23,883 / 963 | 23,777 / 1,225 |
| no-step pairs / reach bands | 23,213 / 2,443 | 54,502 / 5,385 | 150,426 / 13,879 | 117,119 / 10,859 |
| LP rows_ub | 191,872 | 833,369 | 2,483,274 | 1,861,042 |
| hard set | feasible, OPTIMAL | feasible, OPTIMAL | feasible, OPTIMAL | **INFEASIBLE** (3.6 s) → k_min 3 (runways AND taxi family hard) |
| solve wall | 0.51 s | 5.39 s | **6.65 s** (M4c: 28.9 s) | 248 s (M5: 1,598 s) |
| total wall | 4.8 s | 53.2 s (planar 40 s) | 72 s (planar 42 s) | 269 s (M5: 1,621 s) |
| v2 verify rows | 0 | 2 (`adjacent_ground_tear`) | 0 | 1,038 (airside_no_step 974 — the yielded pad pairs, within_shape 21, lateral_contiguity 26, …) |
| oracle census (adjudicated / airside) | **0 / 0** | **0 / 0** | **0 / 0** | **50 / 50** (M5 chord law 4,364 / 4,285; v1 1,069) |

### CYXY apron 156 (the owner's site) — before → after, with `why`

`python -m auto_patch_v2 why CYXY --shape 156 --patch
/Users/noah/XPTerrainBuilderData/Patches/+60-140/+60-136/CYXY_auto.patch.osm`
(face ids moved with the classification; the shipped shapeID 156 is face
150 by overlap 10,017 / 11,673 m²):

| | chord law (why-report-cyxy) | route law |
|---|---|---|
| z − DEM median (min / max) | **−4.38** (−4.73 / −3.28) | **−1.78** (−2.11 / −0.71) |
| rise | | **+2.60 m** (predicted ≈ +2.8) |
| limiter | no_step CHORD 1 % × 149.9 m to junction 103 | taxi within-shape 1.5 % × 222.0 m on junction 100 (letter D) |
| chain | apron → junction (no_step +1.50) → parallel (+0.51) → runway edge (taxi +1.88) → pin 694.33 | apron → junction 100 (taxi_within_shape +3.33) → parallel 6 (+2.99) → pin 694.33; 3 hops, Σ +6.28 |
| relax no_step_pairs alone | +2.78 m | +0.07 m (the route pairs are redundant with the path rows) |
| relax taxi_within_shape alone | 0.00 m | +0.34 m |

The chord is gone as a limiter; what holds the apron now is the taxi
family's all-pairs 1.5 % on junction 100's 222 m diagonal and on the
parallel's 199 m — the second level the why-report predicted — and the
junction's inherited letter is D (1.5 %), so the 3 % of taxiway G does not
reach it. The remaining −1.78 m is the route law's own answer at 1.5 %.

### HECA

Prediction "hard set FEASIBLE" — **missed, halfway**: the hard set is
still infeasible (3.6 s), but the depth search now stops at **k_min 3**:
the runway family AND the taxi family hold HARD (M5's k_min 1 bent the
runways up to 14.1 m). Attempts: k_min 8 infeasible 70.9 s, k_min 4
infeasible 68.7 s, k_min 2 optimal 103.5 s → proven k_min 3. What yielded:
tier 3 apron 156 rows, max 0.443 m (apron 92, no_step 58, pads 6); tier 8
(pads / strips / walls) **1,181 rows, all `no_step`, max 1.809 m** — the
PAD↔PAVEMENT pairs, the one population this lane left at DIRECT distance.
That is the attribution for the residual contradiction: the taxi routes
carry the 05C↔05L relief now; what the routes cannot satisfy is the chord
population still minted against the pads (and the apron rows they pull).
The reach bands are withdrawn in the tiered solve by design (§3).

Oracle census (`census.py`, `HECA_20260904T103238.osm`): **50 adjudicated
/ 50 airside** — within_shape 18 (worst 1.11 m), airside_no_step 17
(1.05 m), strip_seam_tear 3 (2.60 m), cross_shape 4, frontage_near_miss 4,
mid_edge_step 4 — against 4,364 / 4,285 under the chord law (M5) and v1's
1,069. Solve wall 248 s (budget 60 s, adjudicated in the final profiling
round; M5: 1,598 s). The artifact ledger did not store this build: the
report draft was being written during the run, so the tree hash at store
time differed from the key cut at start (the store re-check refused, as
designed); the harness tag and `/tmp/harness/HECA_20260904T103238.*` are
the record.

## 6. Twins — `tests/auto_patch_v2/test_routes.py` (8) + re-founded fixtures

* route graph: service excluded, every taxi-centreline edge on the graph
  marked `CENTRELINE`, stats agree with the arrays;
* the loop fixture (apron 17.5 m from the runway edge, joined only by an
  ~830 m taxi loop): no route inside the window, no apron↔runway pair;
  the apron↔stub pairs exist; every pair's `dist` equals the shortest
  route and `cap·d` equals Σ cap·len along it; mixed pairs carry a cap
  strictly between the two roles';
* reach bands: the pin vertex is its own value, floors ≤ ceilings, the
  far corner's ceiling = pin + route budget, the solve without the bands
  lands inside them and is byte-identical with them;
* K / window discipline of `route_neighbours`; the chord metric refused;
* junction letter inheritance and its cap;
* sidecar / verify population equality: record-for-record identity,
  `dist_m` = route, `budget_m` = the bound; a hand-minted step at one
  published pair is read back on that pair.
* `test_why.py` fixture re-founded for the route law (flat runway, 6 %
  DEM away from it: the chain apron → taxiway → stub → pin); its relax
  test now asserts the redundancy (no single family lifts the apron,
  the travel-path families together do).
* `tests/auto_patch_v2/` 171 passed; `tests/test_harness.py` 300 passed.

## 7. Not done / open questions (≤ 3)

1. **Which letter does a junction inherit when its chains differ?** The
   ruling says the strictest; at CYXY junction 100 that is D (1.5 %),
   so taxiway G's code A (3 %) never reaches the apron's stretch and the
   apron stays −1.78 m under the lidar. Per-stretch inheritance (the
   letter of the chain serving each part of the junction) is an intent
   question for the owner.
2. **The taxi-family all-pairs within-shape law on large junctions** is
   now the CYXY limiter (222 m diagonal at 1.5 %); the owner may want the
   junction's within-shape population to be route-priced too (the same
   metric as the no-step pairs), which this lane did not touch.
3. **Pad↔pavement pairs** stay direct-distance (a pad is not pavement) —
   and at HECA they are the whole tier-8 yield (1,181 rows, 1.81 m): the
   next lane should route-price them too (a pad's route = its contact
   apron's) or rule them out; the second attempt on HECA's hard set is
   not spent here (attempt cap). SPJC's v2 verify reads 2
   `adjacent_ground_tear` rows (oracle 0/0) — not attributed. KCLT not
   built (time).
