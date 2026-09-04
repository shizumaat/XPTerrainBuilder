# R1.3 — WHO MINTED the pass-2 contradictory pins (lane `r1pins`, 2026-09-03)

Zero-airside plan §3 R1, step 3.  ATTRIBUTION ONLY — no mechanism changes on
this branch; every edit is a write-only, env-gated instrument or this document.
Evidence base: `r1-attribution-20260903.md` (R1.1, control body `134e5eadc7b0`)
and the parked R1.2 ledger (`lane/r1solve` @ `6acef114`, arm-A build `r1a`,
`O4_STALL_GUARD_ADJUDICATE=1`): pass-2 `membrane_conform` exits on a PROVEN
INFEASIBLE pin set — 1,368 of 4,498 reachable nodes with L > U, max gap
19.64 m, exit carrier (2379, 24595) budget 3.76 m vs dz −20.64 m
(pinned/free), detect carrier (24595, 24935) budget 0.81 m vs dz −18.13 m
(free/pinned).  Node 24595 is a FREE membrane node between two CONSTANTS
whose values differ by ≈ 38.8 m across a two-edge chain whose budgets sum
to 4.57 m.

Standing law framing this round: *feasibility is guaranteed* (a real
airport with real thresholds has a lawful surface, so an infeasible pin set
means a pass MINTED contradictory pins) and *intent questions route to the
owner*.

## 0. What "a pin" is in pass 2 (read, no build)

`airside_no_step.membrane_conform` (`src/auto_patch/airside_no_step.py:1123`)
holds EVERY node that is not tier-4 airside membrane CONSTANT at its pass-1
value (`membrane_free_nodes`, :966): tier 1 = runway ring nodes
(`_runway_node_set`), tier 2 = taxiway-family rings + interiors
(`route_profile.anchors._ROUTE_ROLES`) + the round-3 apron spine STATIONS,
tier 3 = building pad rings.  The cap graph the envelope judges is (a) the
IMPOSED no-step pairs touching the membrane (`airside_no_step` enumeration,
budget = `classify_pair` cap × direct distance, window
`AIRSIDE_NO_STEP_WINDOW_M` = 150 m, k = 16) and (b) the membrane's OWN law
edges — within-shape / lattice / station / transverse — with every budget
RAISED to its pass-1 residual under the §H1.2 do-no-harm relaxation
(`PASS2_RELAXATION`; arm A: 4,244 budgets raised, worst raise 19.425 m).
The "pins" are therefore pass 1's values on tier-1/2/3 nodes, and the
contradiction the envelope proves is: two constants ``v_a`` (high) and
``v_b`` (low) with ``v_a − v_b > d(a,i) + d(b,i)`` for some membrane node
``i`` — the shortest cap-weighted chains from each.

The instrument this lane adds (`O4_STALL_ENVELOPE_DUMP=<dir>`, write-only)
dumps the exact envelope inputs at every adjudicated projection (the same
columns `_stall_envelope_gap` reads — ONE code path, the analysis re-runs
that function offline with predecessor tracking) plus, at the pass-2 call
site, the pin provenance of every constant: tier, FGP hard-set family
(runway-datum / tile-seam / terrain / seed-pin / free-in-FGP), plan xy / ll,
and the shape roles carrying the node.  The vertex history of the SAME
surface (control body = replay body, R1.2 proved byte-identity) is the R1.1
`who_wrote --vertex-dump` of the control (`r1ctl/vertices.jsonl`): the last
value-changing writer of each constant BEFORE `final_grade_projection`, and
whether FGP's own main projection moved it, answers "who pinned it".

## 1. Pre-registered predictions (written BEFORE the replay)

| P | claim | falsifier |
|---|---|---|
| P1 | The HIGH side of the worst contradictions (top-10 by gap) is a **tier-3 building pad ring** seated at the pad's flat datum (pad law 09-01g; the solve writeback `solve.py:6246` carries the seat) and the LOW side is a **tier-2 apron spine station / taxiway ring** carrying the centerline profile; the free node between them sits on the frontage chord.  ≥ 6 of the top 10 chains have one pad anchor. | < 4 of 10 chains touch a tier-3 anchor |
| P2 | The budget that makes the chain rigid is the **no-step pair budget** `classify_pair` cap × direct distance at `APRON_MAX_GRADE` = 0.01 (`config.py:1004`) — a 3.76 m budget is a ≈ 376 m pair at 1 %, or ≈ 250 m at `TAXI_MAX_GRADE` 0.015 (`config.py:821`) — NOT an own-law edge: the relaxed own-law edges (budget = pass-1 residual) are by construction satisfiable at pass-1 values, so the envelope's rigidity comes from the imposed pairs whose budgets were never relaxed. | the carrier edge (2379, 24595) is an own-law edge (`membrane_own_law`) |
| P3 | Runway datum (tier 1) anchors < 5 % of the 1,368 infeasible nodes' (a_L, a_U) pairs; the runway-adjacent residual is R5's 12 rows, not this. | ≥ 10 % have a tier-1 side |
| P4 | Groundside pins never anchor pass 2 (a service-road-shared apron vertex is tier 4 = free; groundside roles are not senior) — zero anchors carry `service_ring` / `gs_weld` / `terrain_pin` sources.  If groundside DOES appear it is through FGP's own hard set on a tier-2 node (seed-pin), which is R6's channel. | any anchor whose FGP pin family is terrain / seed-pin with a groundside role |
| P5 | Grouping the 1,368 by (senior-side tier pair): tier3↔tier2 ≥ 50 %, tier2↔tier2 ≥ 25 %, tier1↔any ≤ 10 %.  The tier2↔tier2 group is the OD-2/apron-relief class (two centerline profiles on real relief, ~85 m across HECA) and is TRUE GEOMETRY under the 1 % apron cap; the tier3↔tier2 group dissolves under ONE owner ruling (pad yields to spine, or the frontage no-step pair is not law across a pad seat). | tier2↔tier2 < 10 % (then a single ruling on pads closes nearly everything) |
| P6 | The 38.8 m disagreement behind the worst carrier is NOT real relief between two neighbouring senior surfaces: one of the two constants was written by a pass other than the solve's profile writer (a pad seat, a groundside weld, or FGP's own main projection), i.e. it is MINTED.  Check: the anchor's DEM vs its value differs by > 5 m on exactly one side. | both anchors sit within 2 m of their own DEM (then the relief is real and the cap cannot span it) |
| P7 | The main solve's airside-pass infeasibility (8,674 nodes, 6.06 m; carriers (29199,29201), (6557,6857), (1293,7843)) is the SAME population seen earlier in the build: the R1.1 "inherited junction/apron" class at 30.1102816,31.4067699 — pinned by `rod_interval` / junction rows, i.e. the seat-anchor class, not the pad class. | its anchors are tier-3 pads |

Arm plan: ONE `solve_cut.py --replay` of the R1.2 arm-A capture
(`r1a_capture/HECA`, phases 1–4 frozen) under the CONTROL configuration
(main code, no `O4_FGP_HOLD_RELEASE` gate exists on main) with the dump
instruments; R1.2 proved this replay reproduces the control body
`134e5eadc7b0`, so the 1,368-node population is measured on the control
surface, not the parked arm.  A full HECA build only if the replay cannot
carry the dump (it can: the instruments are inside the solve stage).
No sweep; CYXY not needed.

(Measured results follow.)

## Measured (2026-09-03, lane r1pins, ONE replay — no full build)

Instruments on this branch (all env-gated, write-only, byte-inert OFF —
CYXY smoke build `CYXY_20260903T171026` body `3a4217e5571d` = the CYXY
control): `O4_STALL_ENVELOPE_DUMP=<dir>` — `one_solve._dump_envelope_inputs`
(one_solve.py:1540, called from both adjudication sites), the
`want_pred` predecessor return of `_stall_envelope_gap` (one_solve.py:1354),
`solve._dump_pass2_pins` at the pass-2 call site (solve.py:8147 / :10906),
`airside_no_step.membrane_free_nodes(detail_out=)` and the
`ENVELOPE_DUMP_LABEL` stamps around pass 2's two projections.  Twin:
`tests/test_stall_envelope_dump.py`.  Offline reader (re-runs the ENGINE's
own envelope function on the dumped columns with predecessor tracking):
`r1-pins-attribution-tables/analyze_pins.py` (scratch, single use).

Replay: `solve_cut.py --replay` of the R1.2 arm-A capture (`r1a_capture/HECA`,
phases 1–4 frozen) on THIS tree (main `4f2cc234` + instruments), gates unset,
`--allow-env-drift`, lane caches: **wall 12.6 min** (replayed [5]+[6]), 3,722
shapes, body `a62bd5b96447` (`replay_report.json`).  **DIVERGED from the R1.1
control `134e5eadc7b0`: the tree moved** (`7c0513cf` wallcrest merge landed
between the R1.1 control at `3f9e008f` and main `4f2cc234`: FGP node space
121,716 → 121,722, final1_exit 2,167 → 1,985).  The pass-2 population is the
same to within the drift: **1,362 of 4,496 reachable nodes INFEASIBLE, max
gap 19.640689 m** (R1.2: 1,368 / 4,498 / 19.640689), exit carrier
(2379, 24601) budget 3.7638 dz −20.6435 (R1.2's 24595 is this tree's 24601 —
same coordinate 30.1087,31.3907).  Node histories are joined against the
R1.1 control vertex dump (`r1ctl/vertices.jsonl`); every joined anchor's
pass-2 value agreed with its control history, stations/lattice are not
ring vertices and do not join (marked UNJOINED).

### THE HEADLINE — the high side of the contradiction is a NEARBY-RUNWAY BACKFILL SEED, not a solved value

* Every infeasible node is bracketed by a HIGH anchor (sets L) and a LOW
  anchor (sets U).  **977 of 1,362 (72 %) have an apron SPINE STATION as one
  anchor, and the 14 such stations sit 12.7–18.5 m ABOVE THEIR OWN DEM**
  (stations 24938–24941 z = 116.5 exactly, DEM 98.0–98.5; 24934–24937
  114.5–115.0 vs 99.5; 24945–24949 113.2–113.6 vs 99–101; four more at
  −5 to −6 m).  The pads / service roads / taxi junctions on the other side
  sit ON the DEM (pad building170 95.05 vs DEM 95.5; service road 95.66 vs
  96.9; junction 4154 99.13 vs 98.8).
* **The 116.5 m is not the solve's value for those stations.  The emitted
  patch carries them at 99.05 m** (way `-14395`, nodes −52423…−52426) and
  the lattice nodes 24594/24595/24601/24602 at 98.4–98.9 m (ways −14261/
  −14262/−14270/−14271) — the `apron_spine_station_emit` /
  `apron_lattice_emit` lists minted from `_elev_emit` at the solve
  writeback (solve.py:6441/:6468).  The pass-2 CONSTANT 116.5 comes from
  the `solved_values` store, which is minted by RE-READING the layout
  through `_seed_elevations(readonly=True, dem=None)` (solve.py:6296–6313):
  `_writeback` stamps pavement RINGS only, a station / lattice / drainage-
  spine node has no layout altitude, no DEM is passed, so it takes branch
  3 — **`nearest_hard_backfill` (solver_primitives.py:4161–4186): the
  elevation of the geometrically nearest CIFP runway corner.**  Measured:
  the store holds **100,109 non-ring nodes on only 335 distinct values**
  (116.5 × 1,893, 136.16 × 2,291, 136.28 × 2,101, 62.51 × 1,902, …), and
  46 of the 527 lattice + station nodes carry exactly 116.5.  FGP's own
  entry seed (solve.py:8596, same seeder, no dem) reproduces it, so pass 2
  holds every station CONSTANT at the runway-corner backfill and pulls the
  lattice to it (24601 → 116.5, then the do-no-harm-relaxed lattice edge
  24602→24601 carries dz −17.55 m on a 0.75 m budget).
* So the "contradiction" the envelope proves is between a **phantom
  runway-corner elevation stamped on non-ring membrane nodes** and the
  real DEM-level pads / roads / junctions.  It never emits — the census
  rows at the two sites are priced on the 99 m surface — but it is the
  pin set every pass-2 / FGP projection at HECA is driven against, and it
  is why R1.2's hold-release arm could re-mint apron rows there.

### Predictions vs measured

| P | verdict | measured |
|---|---|---|
| P1 pad HIGH vs station LOW | **REFUTED (inverted)** | top-10 chains: HIGH = spine station (9/10) at 116.5 (backfill), LOW = pad building170 (5), service road (3), pad 2378/2377 (2) |
| P2 rigidity from the no-step pair budget at `APRON_MAX_GRADE` | **REFUTED** | the worst chain is `own-law within-shape` 0.253 m + published lattice 0.750 / 0.805 m; the imposed no-step edges appear only in 3 of 10 chains (t3–t4 at 0.01, t4–t4 at 0.015) |
| P3 runway datum < 5 % | HELD | tier-1 anchors: 0 of 1,362 |
| P4 groundside never anchors | **REFUTED** | non-airside service_junction / service_road / groundside_pavement nodes anchor 428 rows (U side 326: pinned by `pipeline.py:7270` `_enf_pre` 107, FGP main projection 73, 7127 48, 7062 58; L side 102) — through FGP's own hard set and the rebuilt graph (R6's channel) |
| P5 tier3↔tier2 ≥ 50 %, tier2↔tier2 ≥ 25 % | HALF | station↔pad 471 (35 %), station↔groundside 428 (31 %), taxi↔station 285 (21 %), tier2↔tier2 peer 51 (4 %) |
| P6 one side minted (> 5 m off DEM) | **HELD** | 1,100 of 1,362 rows have a > 5 m-off-DEM anchor (L 697 + U 264 + both 139); 262 rows have both anchors near-DEM (p50 gap ≈ 0.1 m, max 1.4 m) |
| P7 main-solve carriers = seat-anchor class | NOT MEASURED | the solve's node space is not reconstructible from the capture (`_build_node_list` on the captured layout gives 30,019 nodes, not 133,465); needs the pin dump at the solve's own node list (a second replay) |

### Top-10 distinct (HIGH, LOW) anchor pairs by gap (`top10_pairs.json`)

| # | node (gap m) | HIGH anchor L — who pinned it, value / DEM | LOW anchor U — who pinned it, value / DEM | chain (budget law) | senior under precedence |
|---|---|---|---|---|---|
| 1 | pad 2379 (19.64; 17 nodes share) | station 24941 t2 — `nearest_hard_backfill` via `solved_values` (solve.py:6296) & FGP seed (:8596); 116.5 / 98.0 | pad building170 ring 2379 t3 — solve writeback 94.9, FGP main projection → 95.05 / 95.5 | own-law within-shape 0.253 (`APRON_MAX_GRADE` 0.01 × 25 m) + lattice 0.750 + 0.805 (published `_apron_lattice_edges_ll`, 50 m spacing × cap) | station (tier 2 > tier 3) |
| 2 | membrane 4221 (19.52) | same 24941 | pad 2378 t3 — FGP main 95.05 / 94.8 | + relaxed own-law 0.009 | station |
| 3 | pad 2377 (19.43) | same 24941 | pad 2377 — FGP main 95.05 / 94.6 | relaxed 0.050 + 0.157 + chain 1 | station |
| 4 | lattice 24599 (18.56; 7) | station 24940 — backfill 116.5 / 98.4 | pad 2379 | relaxed 0.383 vs 4 × lattice 0.750 + 0.253 | station |
| 5 | lattice 24598 (17.78; 8) | station 24939 — backfill 116.5 / 98.5 | pad 2379 | lattice 0.418 vs 5 × 0.750 + 0.253 | station |
| 6 | pad 2380 (17.53; 24) | 24941 | pad 2380 — FGP main 95.05 / 96.4 | no_step t3–t4 IMPOSED 0.660 (`APRON_MAX_GRADE` × 66 m) + 1.453 + chain 1 | station |
| 7 | service_road 4286 (17.13) | 24941 | service road 4286 non-airside — solve writeback 95.66 / 96.9 | own-law 0.095 + no_step t4–t4 0.352 (`TAXI_MAX_GRADE` × 23.5 m) + 1.453 + chain 1 | station |
| 8 | service_road 4285 (17.05) | 24941 | 4285 — solve writeback 95.66 / 96.9 | as 7 | station |
| 9 | lattice 24597 (16.95; 11) | station 24938 — backfill 116.5 / 98.5 | pad 2379 | lattice 0.491 vs 6 × 0.750 + 0.253 | station |
| 10 | service_road 4284 (16.95) | 24941 | 4284 — solve writeback 95.68 / 96.9 | as 7 | station |

Physical reading, all ten: the terrain drops from ~116 m at the 05C end
(runway ON its DEM there: 05C/23C ring z − DEM p50 −2.45 m) to 95–99 m at
this apron 600 m away; every DEM-level authority (pads, roads, junction
4154 at 99.13) agrees with the ground; only the non-ring membrane nodes
carry 116.5, and they carry it because nothing valued them in the layout
the store re-reads.

### The 1,362 grouped (`groups_dem.json`; HIGH class · > 5 m off DEM? · LOW class · off DEM? · senior)

| HIGH (L) | L vs DEM | LOW (U) | U vs DEM | senior | n | gap p50 | max |
|---|---|---|---|---|---|---|---|
| spine station | MINTED | pad | near | L | 246 | 6.38 | 19.64 |
| spine station | MINTED | service_junction (groundside, FGP-hard / 7270 / 7062 / 7127) | near | U | 232 | 10.13 | 12.81 |
| taxi family (FGP main / 7127) | near | spine station | MINTED | L | 175 | 1.81 | 1.94 |
| pad (solve 6246 / FGP main) | near | spine station | near | U | 101 | 1.30 | 7.10 |
| pad | MINTED | spine station | MINTED | U | 76 | 0.96 | 1.86 |
| spine station | MINTED | taxi family | near | U | 72 | 4.93 | 7.64 |
| taxi family | near | taxi family | near | peer | 51 | 0.08 | 0.69 |
| pad | near | spine station | MINTED | U | 48 | 1.91 | 2.02 |
| spine station | MINTED | groundside_pavement+service_junction (7062) | near | U | 47 | 11.78 | 12.81 |
| pad | MINTED | taxi family | near | U | 45 | 0.22 | 0.78 |
| (17 smaller groups) | | | | | 269 | | |

Dissolved by ONE ruling (a non-ring membrane node's "solved value" is the
value the solve EMITS for it, never a runway-corner backfill — i.e.
`solved_values` / the FGP seed read `apron_lattice_emit` /
`apron_spine_station_emit` for lattice and station nodes): every row with
a MINTED station anchor, **977 rows**, plus most of the 76 + 45 rows whose
pad is > 5 m off DEM (those pads are the ones the station plateau dragged:
building170 is 0.5 m under its DEM, the "minted" pads are elsewhere and
need their own read).  True geometry the caps cannot span: the **262
near-DEM/near-DEM rows** (p50 0.10 m, max 1.38 m — taxi↔taxi peers 51, pad
↔station 101, pad↔taxi 30 …), i.e. the real HECA relief class, small.

### The two arm-A census sites

* apron −10270 @ 30.11056,31.39529: 44 infeasible nodes within 25 m; worst
  gap 11.86 m at membrane 4327 (apron ∩ service_junction; solve 102.25 →
  FGP main 96.42); HIGH = station 24937 (114.47, DEM 99.5, backfill);
  LOW = service_junction 4356, FGP-HARD, pinned by `pipeline.py:7270`
  (`_enf_pre` weld) at 96.25 (DEM 93.3).
* apron −10165 / building −10749 @ 30.1108,31.3984: 8 nodes; worst 6.89 m
  at membrane 5948 (solve 103.02 → FGP 99.36); HIGH = station 24949 (113.2,
  DEM 99.4, backfill); LOW = service_junction 6238, FGP main projection
  98.51 (DEM 99.7).
  Both sites: the station plateau above, a groundside pin below, the apron
  membrane torn between them — the R1.2 +22 rows are this pin set priced.

### Not done
* P7 (main solve's own airside-pass carriers): needs the pin dump at the
  solve's node list — one more replay (12.6 min), not spent.
* Which runway corner each backfilled node took (the `O4_SEED_BRANCH_ATTRIB=1`
  instrument already exists and would name the branch per node) — one more
  replay; the mechanism is read from the code and the 335-value census.
* A current-main HECA control build (the R1.1 control is one tree behind);
  the R1.1 vertex histories were used for the join and agreed everywhere
  they joined.
* Promotion of `analyze_pins.py` into `who_wrote.py` (single use so far).
