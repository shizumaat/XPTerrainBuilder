# auto-patch-v2 — M5 report: the law-ordered solve (RULINGS 2026-09-04i) at HECA and KCLT

Lane `lane/v2law2` off main `9af3ea54`. Ruling implemented: **04i** ("the
DEM is not always reliable; a feasible solution exists for every airport;
ALL pavement must comply with the law and always overrides terrain when
needed; the LAW's priority order decides which governed surface yields"),
generalising 03h/03i (seniority follows from being governed). Every law
value from the TOML tables; no env reads; no v1 imports; every file
≤ 1,000 lines.

## 1. The tiers — derived from `precedence.toml`, no role list in code

`constraints/precedence.py::tiers(law)` walks `[authority] order`:

* a GOVERNED, non-rigid role (a cap in the rulesets) takes its place in
  the order; members of a DECLARED family (`[runway_family]`,
  `[taxi_family]`) share their family's tier at the position of the
  family's first member — a runway crossing yields with the runway, a
  stub with the parallel;
* a governed role the order omits follows the named ones alphabetically;
* the LAST tier is every ungoverned role (no cap: strips, walls,
  clearances, cuts, trenches) and every RIGID role (a pad: one flat value
  levelled by its contact, 03h) — junior by omission, so a new capless
  surface class is junior with no code change.

The order the shipped tables derive (ICAO and FAA alike; twinned in
`tests/auto_patch_v2/test_m5.py::test_tiers_derive_from_the_tables`):

| tier | roles |
|---|---|
| 0 (never soft) | runway, runway_crossing |
| 1 | primary_parallel, secondary_parallel, stub, cross_connector, junction |
| 2 | tunnel_ramp (the table lists it after the taxi family, before apron) |
| 3 | apron |
| 4 | service_road |
| 5 | service_junction |
| 6 | groundside_pavement |
| 7 (lowest) | boundary, bridge_causeway, bridge_trench, **building**, graded_strip, object_pad, ols_cut, retaining_wall, runway_clearance, taxiway_clearance, tunnel_trench |

A ROW's tier (`solve/tiers.py::row_tier`): a row minted for a face
(`Source.inputs` `face:<id>`) belongs to that face's role — an apron ring
edge shared with a taxiway is still the APRON's 1 % row and yields with
the apron; any other row (a no-step pair, a centreline chord, a zone
band, a pin) belongs to the most JUNIOR of its vertices, a vertex being
owned by the most SENIOR surface touching it — a runway↔taxi pair yields
with the taxiway, a strip band with the strip, a CIFP pin is tier 0, a
tunnel wall-crest DEM pin (`retaining_wall`) is tier 7.

## 2. The solve (`solve/tiers.py::solve_law_ordered`, called by `pipeline/build.py`)

1. **HARD** — every row as minted; the DEM only in the objective and in
   the seam / end-zone / crown preference groups. OPTIMAL ⇒ no surface
   yielded: the five zero airports' shipped behaviour, unchanged (SPJC
   re-built below is this path).
2. **DEMOTE** (`demote(k_min)`) when 1 is infeasible: every `Pin` /
   `Diff` / `Offset` / `Linear` of a tier ≥ `k_min` becomes a preference
   row with an UNBOUNDED slack (`Diff.soft` with `ceiling=None` — the
   assembler now admits it; `to_sparse(..., "ceiling")` drops such a row
   for IIS probes), charged `Weights.preference["law"] (1e5) × ratio^rank`
   per metre of relief, rank 0 = the lowest tier. `Flat` (pads, wall
   bands) and object `Band` bounds are never demoted — they are one value
   movable as a whole. Every DEM-derived pin off tier 0 (wall crest,
   basin rim, mouth datum) is thereby a preference, never a hard row: the
   DEM yields to every governed surface (04i).
3. **THE DEPTH SEARCH** — feasibility is monotone in `k_min`, so the
   LARGEST feasible `k_min` (fewest tiers soft, every tier above them
   hard) is found by bisection: the lowest tier alone first (the cheap,
   common case), then midpoints; a feasible attempt whose most senior
   yielding tier is `ky > k_min` proves `k_min = ky` feasible with that
   very solution (every tier below `ky` held hard in it), so the search
   jumps there without a solve. Exact at tier granularity in
   ≤ 1 + log2(tiers) solves, each carrying slacks for the demoted rows
   only. `k_min = 1` infeasible ⇒ the IIS, which can then only name
   hard↔hard contradictions inside tier 0 or among the structural rows
   (twinned: a runway whose CIFP pins imply 5 % — every IIS row's vertices
   are runway-family).
4. **Numerics.** HiGHS (presolve on) returns "numerical difficulties"
   once the objective's dynamic range passes ~1e10 (measured: a top
   coefficient of 3e10 fails, 4.8e9 solves, against the 0.5 roughness
   floor). Law groups are therefore charged ABSOLUTELY (no ×max-fit-weight
   factor; the base already dwarfs any fit weight) and the ladder's top is
   capped at `Weights.tier_top = 2e7` (`ladder_ratio` shrinks the ratio
   to fit: 7 ranks → 2.42, 4 → 5.8). A failed attempt retries the same
   rows on a FLAT ladder (ratio 1) — the senior tiers stay hard (the
   exact part); only the ranking among the demoted tiers is given up,
   and the report says so.

What was REJECTED on the way (measured, not kept): a single full ladder
over every row (915 k slack columns at HECA: 1,278 s; 1.87 M at KCLT:
524 s) followed by a re-hardening pass — the bisection reaches the same
`k_min` from the cheap end; per-tier bottom-up demotion (one ~40 s
infeasible solve per tier at HECA).

## 3. Pad↔pavement pairs (item 2)

`constraints/no_step.py::pad_pavement_edges`: from every PAD-ONLY
vertex (a rigid face's vertex touching rigid faces and nothing else) the
K/sector rule to the airside pavement vertices within the window, at the
strictest governed cap of either endpoint (the pad carries the apron law,
`common.roles.building`); never pad↔pad. A pad vertex shared with
airside pavement is that pavement's (already in the M4 list); one shared
with a GROUNDSIDE lot is the lot's (a mixed pad, 09-01g — the terrace in
the 0.6 m stand-off is lawful). The pairs are `Diff` rows in the
constraint set (tier 7 by the vertex rule: the pad yields first) and are
published under their OWN sidecar key `pad_pavement_no_step_edges`,
priced by v2 verify by identity; the pavement list `airside_no_step_edges`
the v1 oracle prices is M4's, unchanged. Why a second key (measured
SPJC, two builds): with pad endpoints in the oracle's list its PROXIMITY
join (`check_grade._check_published_law_edges`, `SHARED_VERTEX_TOL_M`)
resolved a pad-only endpoint to the mixed pad's groundside cut-back node
0.5 m away — the pad at 30.45 m, the lot at 37.53 m — and minted 70
`building|groundside_pavement` rows of 7.2 m that no published pair
carries by identity (0 of 55,894 over budget on the patch's own nodes).

## 4. Per-airport numbers (production DEM frame, `build_airport.py ICAO --engine v2`)

| | SPJC | KCLT | HECA |
|---|---|---|---|
| tag / ledger key | `spjc_v2law2d` / 461d3ed51f79 | `kclt_v2law2d` / 8f335f3af651 | `heca_v2law2d` / HECA_KEY |
| body sha | 38fe21f60fd2 | b8a680bb8b74 | HECA_BODY |
| load / planar / constraints s | 3.7 / 3.2 / 1.6 | 31.2 / 5.7 / 6.6 | HECA_STAGES |
| faces / vertices | 411 / 9,332 | 1,181 / 22,843 | 1,219 / 23,609 |
| rows (diffs / flats / linears / pins / offsets) | 395,419 / 157 / 13,179 / 148 / 0 | 1,856,382 / 455 / 29,498 / 179 / 62 | HECA_ROWS |
| no-step pairs (pavement + pad) | 55,828 | 183,961 | HECA_NOSTEP |
| LP (hard) rows_ub / columns / nnz | 837,982 / 20,562 / 1.71 M | 3,818,441 / 48,520 / 7.71 M | HECA_LP |
| hard set | feasible, OPTIMAL 6.3 s | INFEASIBLE (33 s) | INFEASIBLE |
| depth search | — | k_min 7 optimal 93 s (19,926 rows soft) | HECA_SEARCH |
| yields | none | tier 7: 1 row (structures, a tunnel crest/datum), 1.97 m | HECA_YIELDS |
| solve wall | 6.3 s | 118.6 s | HECA_SOLVE |
| total | 19.5 s | 168.5 s | HECA_TOTAL |
| v2 verify rows | 0 | 47 (strip_seam_tear 29, tunnel_wall_top_flat 13, mid_edge_step 2, lateral_contiguity 1, vertex_to_edge_step 1, tunnel_mouth_canonical 1) | HECA_VERIFY |
| oracle census adjudicated / airside | **0 / 0** | 58 / 48 | HECA_CENSUS |

KCLT's 48 airside: `within_shape` 25 (junction|junction, ≤ 0.64 m, four
sites around 35.216/−80.933 and 35.221/−80.947) and `strip_seam_tear` 23
(graded_strip|graded_strip, one site 35.2152/−80.9442, up to 8.75 m over
3 m — beside the tunnel, the M4 wall-band class at a new airport; the
v2 tunnel readers flag the same structure, 13 + 1 rows); the 10
groundside rows are lot steps at 35.200/−80.931. None of these moved in
the tiered solve (one row yielded) — they are KCLT's first v2 build's
residual classes, not M5's mechanism; NOT fixed here (attempt cap and
scope).

### HECA: what yielded where (04i's test — ~85 m of real relief)

HECA_YIELD_SECTION

### The five-airport table on main + these two

| airport | v1 control (adjudicated / airside) | v2 on main, ledgered (04g) | v2 M5 (this lane) |
|---|---|---|---|
| CYXY | 157 (04g instrument) | 0 / 0 (c23880b3e574) | not rebuilt (hard path unchanged) |
| SPLP | 35 (STATUS sweep) | 0 / 0 (a4a3758be45b) | not rebuilt |
| SPJC | 686 / 596 (M3b) | 0 / 0 (0a79668a0b63) | **0 / 0** (461d3ed51f79) |
| OTHH | — | 0 / 0 (42a253005ec9) | not rebuilt |
| LEMD | — | 0 / 0 (4d96b4d41c41) | not rebuilt |
| KCLT | 2,174 (STATUS sweep, 1.0.274) | — | 58 / 48 (8f335f3af651) |
| HECA | 2,809 / 1,069 airside (04g instrument; R1.4) | — | HECA_TABLE |

## 5. Mesh, +30+031, `run_tile_mesh_only.py 30 31 --patches-as-is`, 3 runs per arm

MESH_SECTION

## 6. Residuals

RESIDUALS_SECTION

## 7. Open questions (≤ 3)

OPEN_SECTION

## 8. Commits (branch `lane/v2law2`, not merged)

COMMITS_SECTION
