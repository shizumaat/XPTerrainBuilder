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
| tag / ledger key | `spjc_v2law2d` / 461d3ed51f79 | `kclt_v2law2d` / 8f335f3af651 | `heca_v2law2d` / e79f7ec04cf5 |
| body sha | 38fe21f60fd2 | b8a680bb8b74 | ac6543cac4b4 |
| load / planar / constraints s | 3.7 / 3.2 / 1.6 | 31.2 / 5.7 / 6.6 | 4.6 / 8.1 / 4.5 (classify 1.9) |
| faces / vertices | 411 / 9,332 | 1,181 / 22,843 | 1,219 / 23,609 |
| rows (diffs / flats / linears / pins / offsets) | 395,419 / 157 / 13,179 / 148 / 0 | 1,856,382 / 455 / 29,498 / 179 / 62 | 908,182 / 489 / 26,995 / 6 / 0 |
| no-step pairs (pavement + pad) | 55,828 | 183,961 | 117,965 |
| LP (hard) rows_ub / columns / nnz | 837,982 / 20,562 / 1.71 M | 3,818,441 / 48,520 / 7.71 M | 1,920,538 / 51,180 / 3.92 M (k_min 1: 964,718 columns, 5.75 M nnz, 914,675 slack groups) |
| hard set | feasible, OPTIMAL 6.3 s | INFEASIBLE (33 s) | INFEASIBLE |
| depth search | — | k_min 7 optimal 93 s (19,926 rows soft) | k_min 7 infeasible 40 s → 4 infeasible 30 s → 2 numerics 115 s, flat ladder infeasible 132 s → **1 optimal 1,242 s** (913,538 rows soft, ratio 2.42) |
| yields | none | tier 7: 1 row (structures, a tunnel crest/datum), 1.97 m | tier 1 taxi 4,063 rows (taxi 1,941, no_step 2,106, transverse 16) max 3.02 m; tier 3 apron 6,826 (apron 4,971, no_step 1,845) max 3.67 m; tier 4 service_road 487 max 1.71 m; tier 5 25; tier 7 2,694 (pad/strip no-step pairs) max 5.89 m; runway end-zone caps escalated to their 1.5 % ceiling on all three runways, crown floors escalated up to 0.30 |
| solve wall | 6.3 s | 118.6 s | 1,598 s |
| total | 19.5 s | 168.5 s | 1,621 s |
| v2 verify rows | 0 | 47 (strip_seam_tear 29, tunnel_wall_top_flat 13, mid_edge_step 2, lateral_contiguity 1, vertex_to_edge_step 1, tunnel_mouth_canonical 1) | 10,856 (within_shape 5,351, airside_no_step 5,317, road_cross_section 122, lateral_contiguity 26, transverse 21, strip_seam_tear 6, …) |
| oracle census adjudicated / airside | **0 / 0** | 58 / 48 | **4,364 / 4,285** (within_shape 1,372, airside_no_step 2,909, road_cross_section 40, transverse 21, strip_seam_tear 6, steps 9, cross_shape 4, frontage 3) |

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

**The contradiction, attributed (offline on the captured HECA set,
`v2_capture` / ablations, ~45 s a probe).** The hard set is infeasible.
Removing `runway_profile` (the six CIFP pins and the runway rows) makes
it feasible in 4 s; removing the taxi rows, the no-step rows, the apron,
roads, zones, strips or pads alone does not. `runway_profile + no_step`
ALONE is infeasible (141 k rows, 7 s); `runway_profile + taxi` is
feasible. So the tier-0 constants are the three runways' CIFP thresholds
— 05R/23L 136.55 / 142.34 m, 05C/23C 116.43 / 114.30 m, **05L/23R 57.91 /
60.66 m** — and the chain that cannot reach them is the 08-27
direct-distance membrane: 05C and 05L are parallel ~2.8 km apart with
~55 m between their thresholds (a 2.0 % mean terrain grade), and a chain
of K/sector pairs (≤ 150 m each, at 1.5 % or 1 % where an apron vertex
is an endpoint) between them climbs at most cap × Σd ≈ 43 m along a
straight path. The pins are ≤ 2.6 m from the smoothed DEM (05R +2.56,
23L +1.38, 05C +0.51, 23C +1.37, 05L +0.21, 23R +1.37) — the DEM is not
the culprit; the relief is real (memory `heca-is-not-flat`). Depth
search: the lowest tier (pads, strips, walls: 23,637 rows) cannot close
it, nor tiers 4–7, nor 2–7 — the taxi family itself must yield to the
runways, exactly 04i's "taxiways yield to runways". (The owner's R1.3
sites are NOT where it lands: 30.11056/31.39529 and 30.1108/31.3984
carry **0** census rows within 150 m; 30.1224/31.4080 carries 267, worst
1.82 m, `building|service_road` pad pairs.)

**Where the yield went (census of the ledgered patch, rows within
150 m of a site).** `within_shape` 1,372 rows: apron|apron 547,
stub|stub 372, cross_connector 320, primary_parallel 87, junction 22;
p50 0.88 m, p90 5.19 m, 587 rows > 1 m; the worst five are all on ONE
1.7 km-long `stub` face at 30.1070/31.4179 — 25.6 m over its 1.5 % cap on
a 1,700 m all-pairs chord (3.0 % end to end: this face carries the
05C↔05L relief). `airside_no_step` 2,909 rows: apron|junction 879,
apron|apron 383, junction|junction 222, cross_connector 210,
apron|building 183; p50 0.92 m, p90 2.19 m, worst 5.21 m (graded_strip|
stub at 30.0986/31.4176; apron|apron 5.13 m at 30.1288/31.4134).

**Junior-surface vertices moved > 0.5 m off the DEM, by role (a vertex
counts for its senior role):** runway 1,677 / 2,111 (max 14.14 m),
cross_connector 1,892 / 2,254 (13.61), junction 1,476 / 1,596 (15.24),
stub 1,085 / 1,324 (11.84), primary_parallel 987 / 1,542 (13.47),
secondary_parallel 621 / 658 (8.96), apron 1,099 / 1,216 (14.97),
service_road 648 / 797 (14.59), service_junction 63 / 63 (8.29),
groundside_pavement 12 / 328 (2.33), graded_strip 3,657 / 5,755
(14.55), building 4,040 / 5,965 (16.86). The RUNWAYS themselves leave
the DEM by up to 14 m mid-length (05L/23R DEM 55.7–60.0 m, solved
55.9–72.4 m): with every junior law row charged 1e5+ per metre and the
runway's DEM fit 20 per metre, the LP bends each runway to the limit its
own cap, end-zone ceiling and crown floor allow (all three end-zone
groups escalated to 1.5 %; crown floors escalated up to 0.30) to shave
junior yields — lawful under 04i's letter ("the DEM preference yields to
every governed surface"), absurd in intent (open question 1).

**v1 control for the same airport:** adjudicated 2,809 / airside 1,069
(04g instrument correction; R1.4) — v1's solve does not hold the CIFP
pins hard against the membrane, it demotes/backfills ring constants
(R1.3/R1.4) and reports the 03k rows. v2 M5 reports MORE rows (4,285
airside) because the law's answer under 04i is exactly that: the taxi
family and the apron are the surfaces that yield, and every yielded row
is a census row until the census learns the tiers (open question 2).

### The five-airport table on main + these two

| airport | v1 control (adjudicated / airside) | v2 on main, ledgered (04g) | v2 M5 (this lane) |
|---|---|---|---|
| CYXY | 157 (04g instrument) | 0 / 0 (c23880b3e574) | not rebuilt (hard path unchanged) |
| SPLP | 35 (STATUS sweep) | 0 / 0 (a4a3758be45b) | not rebuilt |
| SPJC | 686 / 596 (M3b) | 0 / 0 (0a79668a0b63) | **0 / 0** (461d3ed51f79) |
| OTHH | — | 0 / 0 (42a253005ec9) | not rebuilt |
| LEMD | — | 0 / 0 (4d96b4d41c41) | not rebuilt |
| KCLT | 2,174 (STATUS sweep, 1.0.274) | — | 58 / 48 (8f335f3af651) |
| HECA | 2,809 / 1,069 airside (04g instrument; R1.4) | — | 4,364 / 4,285 (e79f7ec04cf5) |

## 5. Mesh, +30+031, `run_tile_mesh_only.py 30 31 --patches-as-is`, 3 runs per arm

Foreground (nice 0, machine quiet — no other build running), `Patches/+30+030/+30+031/`
holding HEAZ's v1 patch in both arms and HECA's patch swapped: arm v1 = the
main tree's HECA patch (provenance sha 951f7c42, 2026-09-04 07:15); arm v2 =
`heca_v2law2e.osm` (body ac6543cac4b4).

| | v1 patch | v2 M5 patch |
|---|---|---|
| step 1 input segments (constrained edges) | 410,666 | **404,540** (−1.5 %) |
| step 2 constrained subsegments | 581,124 | **475,273** (−18 %) |
| mesh triangles | 1,374,112 | **1,167,242** (−15 %) |
| step 1 wall (3 runs, median) | 55.73 / 55.73 / 55.74 → **55.73 s** | 56.07 / 55.65 / 55.57 → **55.65 s** |
| step 2 wall (3 runs, median) | 64 / 63 / 61 → **63 s** | 55.5 / 58.0 / 56.4 → **56.4 s** (−10 %) |
| whole run (timestamps) | 121 / 120 / 118 s | 113 / 115 / 113 s |

The 04d mesh bar (v2 no slower, fewer edges) holds at HECA: fewer constrained
edges and triangles, step 2 faster, step 1 equal. (Patch coverage differs by
construction: v1 seats 104,289 free interior vertices on its lattice, v2 2,497 —
v2 has no interior lattice, M0 open question 3.)

## 6. Residuals

* **HECA solve wall 1,598 s** (budget 60 s, adjudicated in the final
  profiling round): the k_min 1 attempt alone is 1,242 s — 964,718
  columns once every row off tier 0 carries a slack (a flat ladder is no
  faster: 1,536 s offline). The bisection's failed attempts cost 40 + 30
  + 115 + 132 s. KCLT closes in its first attempt (93 s), SPJC never
  leaves the hard path (6.3 s). Owed: a warm-started or IPM path for the
  deep attempt, or slacks only on rows the infeasible dual names.
* **HiGHS numerics** on the k_min 2 attempt at HECA (status 4) at a
  capped ladder — the flat-ladder retry answered it (infeasible, the
  same verdict the offline probe gave with ratio 5.8 in 31 s); the
  threshold is a dynamic range of ~1e10, not a fixed coefficient.
* **The yield's SHAPE is L1's**: a weighted sum of slack metres puts the
  relief on the fewest rows (25.6 m on one 1.7 km stub chord) rather than
  spreading it (a max-norm or a per-face equal-share objective would);
  and the ranking among the demoted tiers is a weight ratio (2.42 at
  HECA), exact only at tier granularity (which tiers are soft at all).
* **The runway family's own preferences (end zone 1e3, crown 1e2) rank
  BELOW the junior law tiers (1e5+)**, so the runways bend to their
  ceilings to spare taxiway rows (HECA: all three end zones at 1.5 %).
* **KCLT 58 / 48** is not M5's class: `within_shape` 25 junction rows
  ≤ 0.64 m, `strip_seam_tear` 23 at one tunnel site (35.2152/−80.9442,
  8.75 m over 3 m; the v2 tunnel readers flag the same structure), 10
  groundside lot steps at 35.200/−80.931. Not touched (scope, attempt cap).
* **The v1 oracle cannot price pad↔pavement pairs**: its proximity join
  resolves a pad endpoint to a mixed pad's cut-back node; the pairs are
  therefore published under their own key and priced by v2 verify only.
* DEFERRED_VERIFICATION: no five-airport sweep (orchestrator); CYXY /
  SPLP / OTHH / LEMD not rebuilt (their hard path is byte-identical in
  code; the pad key is additive); only the directly covering suites ran
  (`tests/auto_patch_v2`: test_m5 9, test_constraints, test_m3b, test_m4,
  test_m4b, test_crown, test_verify_plane green); HECA / KCLT single
  builds only.

## 7. Open questions (≤ 3)

1. **Does a senior surface's DEM fidelity outrank a junior surface's
   law row?** 04i's letter says the DEM yields to every governed
   surface; at HECA that bends the runways 14 m off real terrain (within
   their caps) to shave taxiway yields. If the intent is "the runway
   holds ITS terrain shape and the taxiways carry the relief", the
   runway family's DEM fit (and its end-zone / crown preferences) must
   rank above the junior tiers' law rows — a one-line change of the
   weight ladder, but an intent call.
2. **What does the census count once a tier has lawfully yielded?** The
   oracle prices every yielded row as a violation (HECA 4,285 airside,
   v1 1,069). Under 04i a yielded junior row is the law's own answer, not
   a defect — should the solve publish the demoted rows (tier, slack)
   so the census reports them under their own heading (like
   VERSION-DEFERRED), leaving "adjudicated" = rows the solve did NOT
   grant?
3. **Should the yield spread?** L1 concentrates the 05C↔05L relief on
   one 1.7 km stub face (25.6 m over cap). A max-norm (minimise the
   largest escalation per tier) or a per-face share would spread it
   along the whole chain at ~2 % — is that the intent, and is 2 % over
   1.7 km "steps in airside pavement" or a lawful ramp?

## 8. Commits (branch `lane/v2law2`, not merged)

* `300f7f67` — tiers derived from the tables (`constraints/precedence.py::tiers/role_tier/vertex_tier`), `solve/tiers.py` (demote / law-ordered solve), assembler: unbounded soft rows + `preference_weight`, `Weights.tier_ratio`, pipeline report `law_tiers` / `off_dem_by_role`, M5 twins.
* `3f9b099c` — ladder-then-tighten (superseded), law groups charged absolutely, `Weights.tier_top`, `Offset` demotion (KCLT replay crash).
* `4aae1a9f` — the demotion-depth bisection.
* `a51dda7c` — pad-only endpoint = every incident face rigid (SPJC 7.2 m rows).
* `28cf13fa` — pad↔pavement pairs as their own list + sidecar key `pad_pavement_no_step_edges` (v2 verify prices it); flat-ladder retry on HiGHS numerics.
* `484b1689` — v2 verify: an endpoint no shape names is priced, not a KeyError; report draft.
* (this commit) — the report with the closing numbers.
