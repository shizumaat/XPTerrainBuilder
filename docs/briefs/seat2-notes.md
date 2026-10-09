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
