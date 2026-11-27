# Stage-1 prefix and late derive: what repeats, what may be reused (#2206, lane lprefix, 2026-11-27)

Target: lperf's ranked item 1, "stage-1 prefix + late derive repeated" (418 s at KATL).
Base: `claude/lsolvecache` 85cd3ce94 + `claude/lpadbeside` bc393a0c4 (merge c67299b6e).
Instrument: `tools/v2_solve_replay.py --replay frames/lvec/KATL.pkl --from classify --prefix-twice off`
(`tools/prefix_twice_arm.py`: the build's `Deriver` on the base classification, then on the whole one with
the first run's airport, as `pipeline/build` hands the late stage its derive; now also prints the planar
laps, the slowest generators and the item memos' reads).

## 1. What repeats (measured, KATL, loaded machine)

The build derives its prefix (planar → flat site → road profile → channels → shapes → constraints →
strips → hold) three times: the main pass (base classification), stage 1's ribbon-free map (in a pool
WORKER beside the main pass, `pipeline/stage_one_ahead`) and the one late map (`late_stage.run_last_stages`,
serial, after the base solve).  Stage 1's derive is CPU, not wall, unless the build waits for the
worker; the late derive is wall.  So the reuse that moves the build's clock is main pass → late derive,
in one process.

| step (s) | base derive | late derive |
|---|---|---|
| planar | 295.7 | 161.4 |
| — pack_reads / decks / structures | 100.0 / 59.5 / 9.9 | 5.8 / 19.8 / 11.3 (already served: `held_read`, routes, axis index) |
| — arrangement | 108.2 | 111.4 |
| road_profile | 11.0 | 11.0 |
| channels | 33.4 | 34.1 |
| constraints | 112.5 | 52.5 |
| total | 458.6 | 263.9 |

cProfile of the late derive alone (468 s profiled): `build_arrangement` 197 (`platform_split` 75 —
`unit_levels` 31, `low_level_split` 21, landings 11, block plans 6.5; pass C 45 — of it the ring
re-densify `follow_ground` 16; `zone_regions` 19; shelf 13; plateau 10); `road_profile.answer` 32
(112,355 calls: the preferred road z, the road ramp's route frame and targets); constraints
`zones._nearest_edge` 25; `inscribed_width_m` 9; `_road_barriers` 10.

## 2. Census: the passes' inputs are NOT equal (why no pass-level memo)

Each candidate pass was wrapped and its arguments digested (pickle sha256 per argument; the `Airport`
field by field) in both derives (scratch census, KATL):

| pass | base s | late s | inputs equal? | the arguments that differ |
|---|---|---|---|---|
| `weld_cells` | 1.9 | 2.3 | no | the non-late cells |
| `zone_regions` | 8.2 | 8.4 | no | the cells |
| `platform_split` | 42.6 | 35.2 | no | base regions, airport (flat site, deck stacks), registries |
| `unit_levels` | 14.2 | 12.9 | no | the airport only: `flat_site` (read via `inset_class.ground_class`) and `deck_stacks`; `air` and `ground` EQUAL |
| `low_level_split`, `landing_regions`, `plan_blocks`, `shelf_regions`, `plateau_cut`, `pad_terrace_split`, `join_zones` | 0.6–8 each | | no | regions / airport / registries |
| `core_profiles`, `road_route_frame` | 2.8, 3.6 | | no | the map |

The late classification is not the base plus late cells at the arrangement's front: the gap pieces and
pad roads change the cells the front reads, the airport carries the late flat-site verdict, and every
pass writes the run's registries.  This is the deleted arrangement memo's finding again (lane lmemo:
served, it changed the late map).  Pass-level reuse is refused.

## 3. The reuse: one answer per ITEM content (`geom/item_memo`)

Inside those passes many small items ARE equal: a ring, a zone part, a face, a road vertex the late
cells do not reach.  `ItemMemo` holds `key -> answer` where the key IS the item's content, compared by
`==` (no digest, no identity: RULINGS 2026-11-24d, `model/map_memo`'s rule), for the current and the
previous prefix run (`next_run()` in `run_prefix`), so the late map reads the main pass's and nothing
outlives two runs.

WHY IT IS SAFE.  Each memoised function was read for everything it reads; the key is all of it:

| item | key (the identity) | what it reads besides | DEM |
|---|---|---|---|
| `RoadProfiles.answer` (`airport/road_answer`) | vertex x, y; the DEM fallback value; the core radius; the walls (by identity: airport objects); each `through` way by content (kind, ref, xy dtype/shape/bytes, s, z) with its radius, in order; each near way by content, in order (after `skip`) | nothing: the station tables, lines, `at`, `_same_side` are functions of those | none (the DEM value is handed in) |
| `ground_chords.follow_ground` | the ring (coordinates and their type), the ground it was handed (`z_all` bytes), the mouth flags, tol, sample, min piece, the ramp law | nothing | READ every time, before the key (a cached build's DEM witness names every question a record asked, `pipeline/front_cache`) |
| `proportions.inscribed_width_m` | the polygon's WKB, tol | nothing | none |

Served answers are rebuilt around the asking run's own objects (`Answer.way` is `cands[k]` of THIS run:
equal content, own identity) or are immutable (tuples, floats).  No memoised function reads a registry,
`model/stage_one` flag or any other module state.

Exact speedups beside them (every run): the mouth test is one STRtree query per ring
(`near_any.many`, the same `dwithin` per pair); `_road_barriers` builds the part's buffer once per
distance and skips a road whose box misses it (its intersection is empty, the loop's own `continue`);
`unit_storey._unit_plans` once per partition and frame (`model/map_memo.per_map`, checked by identity).

## 4. Not done (and why)

- `unit_levels` (~13 s per derive): its inputs differ only by the airport's flat-site verdict, which it
  reads lazily through `ground_class`, and it READS THE DEM (`_grounds`, `face_clues`).  A memo would
  hide those questions from the late record's DEM witness; serving it needs the witness replayed on a
  hit (`DemRecorder.replay` of a per-item record), not built.
- `zones._nearest_edge` (constraints, 25 s profiled) — lane l412's package.
- Pass C's re-ringing and `platform_split`'s per-unit passes: they read whole region sets and write the
  registries; an item key there needs a locality proof the code does not give.
- Stage 1's worker derive: another process; it gains only the within-run reuse (the road ramp re-reads).
- A possible pre-existing hazard, NOT verified and not changed here: the pack store's cross-derive
  readings (`pack_reads.held_read`: level seeds, storey shells, object floors) are served to the late
  run, whose re-opened window (`FrontCache.reopen`: a fresh DEM record) would then not record any DEM
  question those readings asked in the main run.  Worth one read by the stage-cache owner.

## 5. Bars and results (measured)

Identity, `--replay --from classify --emit --rebake-plan`, base c67299b6e vs head: all six emitted files
sha256-identical at KATL (patch f4b7afdeea0d, graded 6e2855a9451f: lvec's reference), KDFW, BIKF, OMDB,
LGAV, KDEN, KEGE.  `--prefix-twice`: KATL late map digest identical (pm 796685780bee997c, cs
b46f25a4055565dd) on every arm.

KATL late derive (`--prefix-twice`; base and head run CONCURRENTLY as pairs, the machine loaded by other
lanes): 198.9 -> 170.8 s and 152.9 -> 137.8 s (-28 / -15 s, -14 % / -10 %); the main pass 276.5 ->
267.2 and 256.7 -> 245.3 s.  By step (pair means): planar -12 s, channels -5.7 s, road profile -2.6 s.
Late-run hits: road answers 93,841 / 111,742, widths 1,601 / 1,659, rings 4,688 / 13,506; the main pass
also hits 19,508 / 104,371 answers (the road ramp's re-reads).  Alternating single runs did not resolve
the effect (load drift 150-260 s).  Peak memory: +0.1 GB.
