# seat2 notes — implementing spec §62 (pad seats from pavement), sub-steps a–d

Lane `seat2` (Opus, implementation). Worktree `.claude/worktrees/seat2`, branch `claude/seat2` off `origin/claude/seatspec`
b6eecfed. Scratch `<scratch>/seat2/` (`.progress`). Arms run from a second ritual worktree `.claude/worktrees/seat2run`,
frozen per arm by `<scratch>/seat2/snap.sh` (`git stash create` of the seat2 tree, checked out detached) so edits never
reach a running replay — the first baseline chain was killed for exactly that (the tree was edited under it).

## Frame

* Captures: the registered pads67 captures `/Users/noah/XPTerrainBuilderData/.harness/frames/pads67/{HECA,KCLT}.pkl`.
* Arm = the late-stage replay pair of spec §62 (5a): `--from classify --gap-free --workers 9 --solved-out` then
  `--from classify --late-from` with `--emit`; `tools/pad_edge_read.py` on the emit; classes by the pads67 logic
  (`<scratch>/seatspec/cmp_arm.py`, list `<scratch>/seat2/prow.py`); `tools/airside_value_delta.py --tol 0.02`;
  `tools/harness/census.py` on the pair's two patches.
* HECA BASE = `<scratch>/seatspec/late/` — seatspec's own late pair. Its code is this base: the seatspec branch merged
  main f314564d at 09:16:20 (83416762) and that pair was solved 10:07–10:11; b6eecfed adds docs only. KCLT BASE =
  `<scratch>/seat2/kbase/`, run from the untouched seatspec worktree (same sha).
* The spec's `--from constraints` arms (A1, E, RR) read the CAPTURED road profile (pads67 head, before #484); the late
  pair re-runs it under this tree (`road ramps built: 38 … at the design grade 5.0 %, 593 m`), so the late pair is the
  frame every number below is in.

## Step a — R-F + R-C rule 1

What landed in the tree:

* R-F `constraints/pavement_cap.pavement_road_cap`: a welded-neighbour pair with a PAD'S OWN vertex (one no pavement
  face shares) at either end mints nothing. A vertex a pad shares with pavement is the pavement's (09-01g) and keeps
  its pairs; a pad's own ring edges keep theirs.
* R-C rule 1 `constraints/pad_seat.py` (new): `landside_seats` — per plane group that fronts no airside pavement, ONE
  leader FACE: senior tier (the road family as one tier, then `groundside_pavement`, then `parking_lot`), ties by the
  longest contact (§28 (1)'s ring edges with both ends on the frontage). `pads.pad_frontage_level` mints the one level
  row from it under the head `structures.building_pad frontage_level seat`; the role-wide senior row and the junior
  rows are not minted for a seated pad.
* The head is in `[design] hard_rulings`, `one_way_rulings`, `pad_level_rulings`, the pad tier of
  `hard_conflict_ranks`, and the ceiling twin's skip set.
* SOLVER (found, fixed in this step): a head in BOTH the hard and the one-way register was not solvable.
  `solve/design` keeps one `shift` vector; phase C wrote `shift[hard_i] = mu / rho` over the lagged leader term and
  read the violation without it, so the hard one-way seat row drove the pad's mean to 0 m (the twin's first run: pad at
  −0.0004 m against a road at 700). `emit.toml` recorded this as "not structurally impossible … 0 rows at HECA/KCLT".
  Now the lag is frozen into the hard rows' target (`bh = b1 − lag`, `shift = lag + mu/rho`) and the lagged leader
  term is taken in the hard rows' metre scale. `lag` is zero on every hard row that is not one-way, so that arithmetic
  is unchanged to the bit.

### Step a measured (arm `a` = R-F + R-C rule 1; HECA late pair vs BASE; KCLT `ka` vs `kbase`)

| | HECA base → a | KCLT base → a |
|---|---|---|
| `hard_conflict` groundside / pad / taxi | 233 / 101 / 64 → 224 / **17** / 63 | 279 / 31 / 51 → 268 / 28 / 51 |
| held platform datums moved > 0.02 m | 0 of 47 | 0 of 55 |
| solve-owned airside movers (runway / taxi / apron) | **0** | 0 |
| row-side movers | 789 (worst 4.14 m, `building8`'s rim: the pad rose to `route3`) | — |
| P:GS-NEAR (class C) runs / m | 16 / 570 → 17 / **1,722** | 9 / 95 → 10 / 110 |
| P:ARMED (class B) | 1 / 66 → 2 / 123 (`building75` \| `small_roads:-20325` −3.52 m over 57 m surfaces: the road the fallback welded to the pad rim is held by its ramp ceiling — R-B's population) | 2 / 0 → 4 / 54 (`building26` \| `pol50` 42 m) |
| P:AIR-TOUCH / AIR-NEAR (class E) | 21 / 232 = ; 7 / 231 → 7 / 295 | 3 / 28 = |
| P:GAP (class D) | 51 / 339 → 48 / 339 | — |

READING. `building75`'s 81 pad-tier conflicts are gone and nothing airside moves — R-F does what the spec's arm A1 said.
The landside pads now stand on their ONE leader (`building15` \| `route3` +1.91 over 117 m: gone; `building8` \|
`route3` +3.87: gone) — but class C's METRES RISE, as in A1: the junior lots (`objpav394` −5 … −7.4 m over 300 m of
`building15` / `building8` rim) were welded to the pad by the fallback and are now rule 2's population, with no row.
Step a is not readable alone: R-C rule 2 (step b) is the other half of the same seat.

## Step b — R-C rule 2 (probe)

Code: `pad_frontage_gs.groundside_frontage` — the leaders are the pads with a SEAT (airside-fronting, or landside-only
with a leader, `pad_seat.seat_of_face`); a seated pad's leader face is skipped as its follower. The §28 (6) terrace
test is untouched (`pair_dem_step_m` falls back to the pad's area-weighted DEM for a landside pad). The seat is
published (`platforms[]`: `seat: "landside"`, leader, followers, held pairs, seat / leader level).

### Step a+b measured (arm `b`, `kb`)

| | HECA base → a+b | KCLT base → a+b |
|---|---|---|
| P:GS-NEAR runs / m | 16 / 570 → 16 / **891** | 9 / 95 → **7 / 42** |
| P:ARMED | 1 / 66 → 2 / 123 | 2 / 0 → 4 / 54 |
| `hard_conflict` gs / pad / taxi | 233 / 101 / 64 → 221 / 17 / 63 | 279 / 31 / 51 → 268 / 28 / 51 |
| held datums moved / solve-owned airside movers | 0 of 47 / 0 | 0 of 55 / 0 (structure frame: 9 `tunnel_ramp` nodes, worst 0.14 m) |

HECA does NOT fall below the base. Three things are in the 891 m, read off the arm's own records:

1. **Ramp landings were seated** (`building4/landing2` … `landing4`, leader `parking_lot:dsf:pol10`): a landing is held
   at its deck's level by a hard row (RULINGS 2026-10-03e) and the hard seat stood 6.9 / 8.1 m against it — the only two
   seat rows in `hard_conflict`, and the row-side "apron" movers (1.05 m at 30.11426101446,31.39756732305). A defect of
   this lane's first cut, fixed: a landing has no landside seat (`pad_seat.landside_seats`).
2. **The lag does not carry a chain two deep.** The seat row is ONE-WAY (the pad follows the road), §28's row is ONE-WAY
   (the lot follows the pad): road → pad → lot. `one_way_max_rounds` is 3 with `one_way_relax` 0.5 and the one-way rows
   are OFF in the warm-up, so the lot's first target is the pad's warm-up level and it closes half the rest per round:
   stage 2 reports `LAG NOT SETTLED after 3 of 3 round(s)`, worst leader move 1.540 m (base 0.604 m), and 411 hard rows
   over tolerance, worst the seat rows themselves (1.51 m `building19`, whose leader `pav57` is itself a follower of
   `building12`). `building8` \| `objpav394`: an ARMED follower still 2.16 m under a pad that rose 4.17 m.
3. **Held terraces read as class C.** The pads67 class counter knows §28 pairs only from pads67's pair list
   (airside-fronting pads); a face §28 (6) now HOLDS against a landside pad (`building15` / `building12`: `objpav394`,
   `pav57`, one `route3` face) is a declared split-level terrace (09f) and still counts GS-NEAR.

Arms queued: `b2` = a+b with the landing fix; `t` = the same with the seat row TWO-WAY (scratch `armT.py`: the head out
of the one-way register at assembly, so the chain is one deep) — the intervention that attributes item 2.

### Step a+b: the attribution arms (HECA late pair vs BASE; every arm: held datums 0 of 47 moved, solve-owned airside movers 0, structure frame 0)

| arm | P:GS-NEAR runs / m | of which, by the arm's own seat records (m): LEADER / FOLLOWER / HELD-or-FOLLOWER | P:GAP | `hard_conflict` gs / pad / taxi | stage-2 lag (worst leader move) / hard rows over tol (worst) |
|---|---|---|---|---|---|
| BASE | 16 / 570 | — | 51 / 339 | 233 / 101 / 64 | 0.604 m / — |
| `a` R-F + rule 1 | 17 / 1,722 | — | 48 / 339 | 224 / 17 / 63 | — |
| `b` + rule 2 | 16 / 891 | 172 / 139 / 574 | 48 / 338 | 221 / 17 / 63 | 1.540 m / 411 (4.28 m, the landing seats) |
| `b2` + landings not seated (the spec-literal form) | 19 / **963** | 246 / 139 / 570 | 49 / 339 | 209 / 15 / 63 | 1.540 m / 46 (1.65 m) |
| `r8` = `b2` with `one_way_max_rounds` 8 (scratch law edit) | 14 / **525** | 153 / 23 / 340 | 51 / 440 | 210 / 15 / 63 | 0.594 m after 8 of 8 / 41 (0.71 m); stage 2 47.4 → 53.3 s |
| `t` = `b2` with the seat row TWO-WAY (scratch `armT.py`) | 14 / **400** | 100 / 6 / 285 | 50 / 440 | 202 / 15 / 63 | 0.379 m / 23 (0.044 m) |

* ATTRIBUTED BY INTERVENTION: the rise of class C under the spec-literal rule is the LAG. With the chain one deep (`t`)
  the armed followers arrive (FOLLOWER 139 → 6 m) and C falls 570 → 400 m; with eight lag rounds instead of three it
  falls to 525 m and the lag is still not settled (0.594 m after 8 of 8 — the damped fixed point does not contract on
  this chain).
* `t` is NOT the rule: with the leader's columns in the matrix the pad PULLS ITS LEADER — `route3` moves on 110 of 210
  nodes, worst 1.59 m (`b2` → `t`, `airside_value_delta --by-ref`), `small_roads:-20209` 1.42 m. Q1 (the pad follows the
  road, the road never gives) holds only one-way.
* What stays in class C in every arm: `building12`'s CLUSTER (16 bodies, one plane, leader `route3` over 92.8 m of
  contact) stands 2.2–3.5 m over `route3` along 100–143 m of rim — one mean-level row seats a 1 % plane on a road that
  slopes past it; and `building15` | `objpav394` (−1.2 … −3.9 m over 340–570 m of rim), where `objpav394` is several
  faces of one ref, one HELD as a §28 (6) terrace and others armed — the records name faces by `role:ref`, so the split
  between "held terrace (class A, 09f)" and "armed follower still off" is not readable per run.
* P:GAP + 101 m in `r8` and `t` is ONE new run, `building14` (0 → 100 m): the gap part beside a pad that moved.
* KCLT (`kb`, three lag rounds): C 9 / 95 → 7 / 42 m, B 2 / 0 → 4 / 54 m, pad conflicts 31 → 28, airside 0.

VERDICT (sub-steps a and b): STOPPED, not on the lane branch. The real code path does not reproduce the brief's bar at
HECA in the spec's own form (class C 570 → 963 m; 525 m only with a solver constant changed for every airport, and
then with class D + 101 m). The code is kept whole on `claude/seat2-rc` for the spec author.

## The two items the spec left

* **HECA `hard_conflict` taxi 63 → 64** (sw7 main `729e140d` vs sw8 pads branch, the two sidecars joined on
  row + vertices): 62 rows identical; one 0.0432 m `pavement_max_grade ceiling` row re-homed 24 m (30.10873452702,
  31.38967247811 → 30.10867810252,31.38943385557, `pav1` | pad 1323); the NEW row is ONE stage-2 `rulesets.common
  .pavement_max_grade ceiling` twin on the gap part `gap:0/s0/ramp0` at 30.12730360576,31.4050836324, relaxed 0.568 m.
  It is a groundside last-stage pair that ranks in the "taxi" tier because the 5 % ceiling head does (30bj (6)); no
  taxiway row. (This lane's arms read 63.)
* **CYXY adjudicated airside 254 → 265**: under ONE tool (this tree's census on both built patches, `/tmp/harness/
  sw7_CYXY.osm` and `frames/pads67/sw8_CYXY.osm`) it is 245 → 265 — main's own tool counted 9 `platform_rim_relief` rows
  the collar deletion retired. Row join (`census_rows_diff --side airside`): EXACT 1,165, GONE 59, NEW 64. The
  adjudicated NEW rows: `within_shape primary_parallel|runway` 10 on way −10008 (six 3.4–7.2 m chords at 1.52–1.58 %
  against 1.5 %, four 0.58–0.79 m pairs at 1.66–1.89 % at 60.7117,−135.0718), `strip_longitudinal graded_strip|stub`
  3, `strip_arc` 2 (0.93 m at 60.701803,−135.059273), `hard_conflict` 2, `plane_gradient` 1, `within_shape` stub 4 /
  cross_connector 1 / building|cross_connector 2; GONE: one `primary_parallel|runway`, one `cross_connector` (the other
  57 / 39 are out-of-scope `withdrawn_law` rows churning). Located by row; the mechanism is the pads branch's stage-1
  re-solve moving the parallel taxiway a few centimetres over its cap (pads67: 306 solve-owned movers, worst 1.02 m) —
  NOT attributed by intervention here (no CYXY replay was run: the two builds answer "which rows").

## Step c — R-B (STOPPED: the spec's attribution is stale on this base)

Code (kept on `claude/seat2-rc`): `road_ramp.frontage_release`, LAST in `reach_seed_rewrite` (the rewrites read every
vertex's §37 (6) row as the floor of their profiles): a §28 frontage vertex (`pad_frontage_gs.frontage_vertices`, the
armed pairs' followers, published by the one derivation) loses its `ramp to the DEM` target, its `ramp ceiling` Band
and its `coverage_edge join` pin; a withdrawn join is recorded in `welded_join_release`'s form (stage `2f`) so the core
ribbon yields. The `pavement_road_cap` clause of R-B (no fallback pair with a frontage-vertex end) was NOT built: it
would lift the 29ac cap off a road's own ring edge beside a pad.

| arm (R-B alone on the base) | HECA base → c | KCLT base → kc |
|---|---|---|
| release fired on | 0 class movement (33 row-side nodes ≤ 0.05 m) | 170 frontage vertices: 146 targets, 143 ceilings, 4 join pins (`v20654` = `building26`'s) |
| P:ARMED (class B) | 1 / 66 m = (`building164` \| `objpav405` +2.70 → +2.65) | 2 → 1 (`building27` gone; `building26` \| `pol50` −1.60 at one vertex stays) |
| P:GS-NEAR | 16 / 570 = | 9 / 95 → 9 / 86 |
| `hard_conflict` gs / pad / taxi | 233 / 101 / 64 → 220 / 105 / 64 | 279 / 31 / 51 → 259 / 32 / 44 |
| held datums / solve-owned airside | 0 of 47 / 0 | 0 of 55 / **2 apron nodes, 0.24 m** at 35.20848542138,−80.93089931101 (the apron sliver at `building27` the road was dragging) |

RE-TAKE OF THE RR ATTRIBUTION ON THIS BASE (the brief's caution was right). The spec's arm RR ran `--from constraints`,
i.e. on the CAPTURED road profile (pads67 head, before #484). On this tree's own ramps (`--from classify`: 38 ramps at
the 5 % design grade, first meet) the row set on `building164`'s frontage vertices (v31843 77.76, v31846 77.96; pad
77.36) holds NO `road_ramp` row at all: 21 `longitudinal` 10 % rows over 206–254 m, the hard cross-section to each
other, 2 §28 rows, and one 29ac fallback pair 10 % × 52.2 m to v31844 at 82.24. The 66 m "ARMED" run is the MID-SPAN of
that 52 m ring edge: the road page has two vertices inside the pad's frontage and its next vertex, 36 m along the rim
and outside the 3 m frontage, stands at its own ramp level 4.5 m higher — the edge read finds the road +2.65 m over the
rim at 16 m along it. No road law fixes a frontage VERTEX here; the page has no vertex where the pad's level must be
carried. R-B as written (a vertex relation) has no population at `building164` on this base. What would answer it is
outside §62's text (noding the road's edge along a seated pad's frontage, or reading the frontage by EDGE): reported,
not built.
