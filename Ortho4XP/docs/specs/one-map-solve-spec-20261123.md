# One map, one path: the fastest legal airport solve (#2206, RULINGS 2026-11-23e, 23g)

**WITHDRAWN 2026-11-24** by the two-round-cap review: no design deleting the late derive meets RULINGS 23e (KBUF null control exact; one map, predicted knives and ring cut each add real rows). Replaced by `exact-prefix-speedups-20261124.md`. The deletion list below is void.

Design round read-only at d0a8b5f0e; nothing here has been built or replayed. Tags: [M] measured from
a record, [C] read from code, [E] estimate. Paths are under `Ortho4XP/src/auto_patch_v2/`.
Replaces item 3 of `fastest-pipeline-spec.md`, whose post-solve re-derive fallback the owner rejected (23g).

## Design

Build the planar map and the constraint rows ONCE, on the final classification, before any solve. Run
four solves on it: the airside on its own ribbon-free map (unchanged), the standing groundside, then gap
pieces, pad roads and car lots as small follower solves. The post-solve cut and the late re-derive are
deleted. Late-cell plan geometry stops depending on solved heights:

- **Gap pieces:** cut before the solve along the lines midway between neighbours (one cell per
  neighbouring ring), a knife strip on every such line. After the base solve each seam is tied flush
  where the two neighbours' solved levels pass today's consistency test, and is a declared step where
  they do not. No knife is predicted, so nothing is checked or redone.
- **Pad-road exits and ramp run-outs:** sized from the pad's predicted level plus a margin (R1, 21b). A
  short run is handled by the laws the late solve already applies (13d/13e/13f), never a re-cut.
- **Car lots:** cut against the finished non-late faces, which exist inside the planar build before the
  late cells join (`planar/ribbons.py:30-60`).

Pipeline, identical for every airport: load, partition, classify; worker: ribbon-free prefix; main: one
prefix on the full classification, late cells cut inside planar before pass C; stage 0 and 1 on the
ribbon-free map; stage 2 on the one map with late faces dormant; gap, pad-road and car-lot solves on the
same map; emit, verify. An airport with no late cells runs the same code with empty follower sets.

Expected saving: the whole late derive. KATL about 650 s [E, range 331-650], KDFW 298 s [M], KRDU 96 s
[M], KBUF 58 s [M]; about 12 % of fleet airport time [E]. It does NOT bring KATL (about 1,500 s after) or
KDFW (about 900 s after) under 5 minutes [E].

## Where the time goes on this branch

| Stage (s) | KATL | KDFW | KBUF | KBIL |
|---|---|---|---|---|
| partition | 39 (555 cold) | 81 | 42.4 | 0.5 |
| classify | 215 | 75 | 26.2 | 9.6 |
| planar | 241 | 223 | 54.0 | 6.1 |
| constraints | 84 | 199 | 12.3 | 6.5 |
| solve wall | 380 [E] | 105 [E] | 35.7 | 19.7 |
| late cut | 101 | 18 | 2.3 | none |
| late derive | 650 [E] | 298 | 57.8 | none |
| late solves | 35 | 2 | 2.7 | none |
| emit, rebake screen | 98 | 27 | 7.5 | 1.7 |
| verify | 99 | 88 [E] | 7.9 | 5.0 |
| total | about 2,140 [E] | about 1,200 [E] | 272.2 | 60.6 |

KATL and KDFW stage rows are app reports at 1.0.569 or lfast1 replays; KBUF and KBIL are the integration
build. Bar: 85.1 % of 101 phased airports are at or under 300 s as recorded [M]; 86 % on this branch and
87 % with one map [E, conservative: KBUF measured 272 s against 414 s estimated].

## Work done more than once, by seconds

| # | Repeat | Seconds | Removable? |
|---|---|---|---|
| 1 | Full prefix on the late map | KATL 650 [E], KDFW 298, KRDU 96, KBUF 58; 9.7 % of ledger time | Yes: this design |
| 2 | Straddling airport built once per tile (10 airports) | 12,642 s, 11.9 % of report wall | Yes: fastest-pipeline item 7, independent of this design |
| 3 | Ribbon-free prefix for stage 1 | CPU KATL 397, KDFW 168; wall 0 to about 66 | Not without airside movement (HECA up to 0.74-1.10 m) |
| 4 | Stage-1 full solves (3-4) | KATL 164; KDFW 27.4; KBIL 12.7 | Partly: memoise the feasibility LP on an unchanged hard set |
| 5 | Stage-2 shadow solve for decks | KDFW 44, KRDU about 75 | Yes: local solve near decks |
| 6 | Late joins and three full assemblies | KATL 35, KBUF 2.7 | Yes: vanish with one map |
| 7 | Stage-cache records | KATL 35 main, 58 writer; 0.17 % hit rate | Partly: about 40 % fewer |
| 8 | Verify re-derives geometry | KATL 99 | No: it is the independent census; profile it |

## Rejected designs

- Memoise the late derive: no structural gain; sized by Step 0's clocks.
- Insert late cells locally after the solve: the arrangement is one global `unary_union`
  (`planar/overlay.py:661,697`), the per-consumer veto of #100 rounds 4-7.
- Late cells as ordinary stage-2 members: KBNA 229 standing nodes move over 0.1 m, road ends 4.6 m.
- Stage 1 as a view of the one map: moves the airside.
- Predicted knives committed with no check: a piece welded to two disagreeing aprons has no lawful
  surface without a knife there. Only if the ring-cut experiment fails.
- Per-component or warm-factorised QP: later, after a profile.
- Held in reserve, H: one planar, two row sets (costs one constraints pass), if the one-map experiment
  shows row residue.

## Kill experiments, run first

1. **One-map premise, no new code.** On an airport with pad roads and no knives (KBUF or KDFW), compare
   the law-true census by family against control, restricted to vertices away from late cells. If
   standing ground gains rows, this design is dead whatever the cut: go to H.
2. **Ring cut, about 30 lines of scratch.** Group by ring in `terrace_cut`, skip `_lot_cut`, replay the
   late stage on `KRDU_base.pkl` (8 parts, 4 knives). Seam steps over 1.0 m at seams the level test calls
   consistent mean the ties are essential. Added law-true rows with ties in place kill the ring cut.

## Steps

- **Step 0, clocks (exact).** Each prefix run's step walls (`Deriver.last.wall`, `pipeline/prefix.py:453-486`),
  the stage-1 worker's outcome and clock (`pipeline/stage_one_ahead.py:291-322`) and the `fc.finish()`
  tail go into `report.json`.
- **Step 1, gap pieces.** `classify/gap_terrace.py`: `terrace_cut` groups stations by `Station.ring`, not
  `level_groups`. Keep `_voronoi_candidates`, `_merge_floors`, `_knife`. Delete `_lot_cut`, the level
  branch and law key `gap_cut_sample_m` (`law/emit.toml:314`). `pipeline/late_stage.py`: in `late_solve`,
  before `gap_follow_rows`, run `level_groups` per piece on true levels; build each `PartStations` with
  `own` = the stations in its ring's group, `lot_rows` true when its ring is a road and the piece meets
  roads and aprons only. Extend `slab_weld_rows` (`constraints/slab_weld.py:38`) to pair rim vertices of
  two parts across their knife when in the same group (hard `Diff` at the piece cap over their distance);
  no tie between groups. Census first: readers of `gap_part_kind` lot/ramp and `_takes_lot_rows`.
- **Step 2, exits and run-outs.** `extend_pad_roads` (`classify/pad_road_exit.py:128`) and
  `mint_ramp_runouts` (`classify/ramp_runout.py:333`) take predicted levels plus one law margin (2.0 m was
  clean in the 3a replay). No check after. The exit's far end counts as a standing level for
  `pad_road_reach`. Synthetic twin: an exit deliberately 3 m short.
- **Step 3, the one map.** New `planar/late_cells.py`, called at the head of `_ribbons_pass_c`: ring cut,
  exits, run-outs, wall cutback, car lots. `pipeline/build.py`: drop the `gap_free` split, run `run_prefix`
  on `cl`. Stage 2: withhold late faces with `withheld_view`; dormant = vertices of late faces carried by
  no hard standing face (`soft_roles` of `late_followers`); drop rows naming a dormant vertex; pass them at
  survey level through `stage2_fixed`; airside rim nodes the ribbon-free map lacks take their stage-1 edge
  level via `late_rim_levels`. `run_last_stages` runs on the main prefix with `base_solution["withheld"]`
  set to the dormant vertices. Keep report keys `late_stage.wall_s.{cut,derive,solve}` with derive 0.0.
- **Delete after Step 3:** `late_cut`, `cut_classification`, `late_derive`, `LateCut`, `with_cells`,
  `run_late_stage`, `_carry_pin_yield`, `gap_free`, `late_fixed`, `_notched_levels`, `_dissolve`,
  `dissolved_levels`, `_carry_rows`, `_carry_published`, `LateRecords.cut`, the `--gap-free` and
  `--late-from` replay arms, and `arrangement_memo` if it records no hit. Keys change once: every patch
  rebuilds once.
- **Step 4, exact extras.** Memoise the feasibility LP across stage-1 passes with an unchanged hard set
  (`solve/feasibility.py:437`); assemble the late solves once.

## Verification

- Replay first (17r): `tools/v2_solve_replay.py --replay <capture> --from classify --emit DIR --verify`.
  Captures: KATL, KDFW (`frames/lfast1`); KRDU, KBUF, KMCO (`frames/lkrdue2`); KDEN (`frames/lkden`, may be
  stale). CYXY needs a fresh `--capture`.
- Law-true grade: `tools/harness/census.py ARM.osm CONTROL.osm`; no family rises.
- Airside: `--stage1-dump` both arms and `--stage1-diff`, expect zero movers. Report separately the
  airside vertices stage 2 owns (door-pad give, at most 0.5 m).
- Movers: `--movers` against 23e's 3 m. Knife airports: HECA 69, KMCI 31, OTHH 22, MMUN 5, ELLX 5, KHMP 5,
  KATL 4, KRDU 4, KMCO 1.
- Owner's five: KATL (46 pieces, 285 pad roads), KRDU (2 pieces in 8 parts, 72 pad roads, car lots), KDFW
  (0 pieces, 52 pad roads), KDEN (5 uncut pieces, 29 pad roads), CYXY (no late stage: expect an identical
  patch body; its twin #2133 is already red and is not a gate).

## Rulings this would amend (record under 23g when it lands)

§55 (1)-(3), 10-04u, 10-06d (terraces by level groups, lot/ramp breakline); 10-13a (1)/13d, 10-04o/q
("solved against the map without it"); 11-21b (true-cut check and fallback deleted); 11-16p (car lots
cut before the solve).

## Not verified

No build or replay ran for this spec. KATL and KDFW on this branch are estimates. How a short pre-sized
exit behaves is read from docstrings. How often the stage-1 worker is refused is unrecorded. Whether
full-map generators mint rows on standing vertices because of late faces is uncounted (experiment 1).
Whether pass C's ribbon-free faces equal stage 1's map when the pad sets match was not checked. The
straddling-airport figures are the perf map's.
